"""
Phase 5.8.5.1 — Redis Presence Service tests.

Tests run against a real Redis instance (Docker).
Requires:
  docker compose up -d redis

No fakeredis — the project's existing test pattern uses real Redis
(see test_auth.py, test_messaging_endpoints.py).

Key cleanup
───────────
Each test explicitly deletes the presence keys it creates so tests are
fully isolated.  A module-level autouse fixture also removes any keys
matching the 'careersphere:presence:*' pattern before each test.

Test index
──────────
 1.  Register first session → first_session=True
 2.  Register second session for same user → first_session=False
 3.  User with three sessions is online
 4.  Remove one of three sessions → last_session=False
 5.  Remove second of three → last_session=False
 6.  Remove final session → last_session=True
 7.  is_user_online=True while session exists
 8.  is_user_online=False after all sessions removed
 9.  Session refresh extends TTL
10.  Session expiration eventually removes presence (short TTL)
11.  Different users have isolated presence
12.  Session IDs are unique (server-generated)
13.  Client cannot choose session ID (server generates it)
14.  Duplicate registration of same session is handled safely
15.  Removing unknown session does not mark user offline
16.  Concurrent-style registration produces correct first-session state
17.  Concurrent-style removal produces correct last-session state
18.  Redis key design: session key contains user_id value
19.  No Pub/Sub functionality is present in the service
20.  Existing Redis cache keys are unaffected by presence operations
"""
from __future__ import annotations

import time
import uuid

import pytest

from app.db.redis_client import redis_client
from app.services import presence_service as ps
from app.services.presence_service import (
    _session_key,
    _user_sessions_key,
    new_session_id,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _new_uid(tag: str = "") -> str:
    return f"test-uid-{tag}-{uuid.uuid4().hex[:8]}"


def _cleanup(*user_ids: str) -> None:
    """Delete all presence keys for the given users + any session keys."""
    for uid in user_ids:
        try:
            members = redis_client.smembers(_user_sessions_key(uid))
            for sid in members:
                redis_client.delete(_session_key(sid))
            redis_client.delete(_user_sessions_key(uid))
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_presence_keys():
    """Delete all careersphere:presence:* keys before each test."""
    try:
        keys = redis_client.keys("careersphere:presence:*")
        if keys:
            redis_client.delete(*keys)
    except Exception:
        pass
    yield
    # Post-test cleanup too.
    try:
        keys = redis_client.keys("careersphere:presence:*")
        if keys:
            redis_client.delete(*keys)
    except Exception:
        pass


# ===========================================================================
# 1. Register first session → first_session=True
# ===========================================================================


def test_01_register_first_session():
    uid = _new_uid("first")
    sid = new_session_id()

    first, status = ps.register_session(uid, sid)

    assert status == "ok"
    assert first is True


# ===========================================================================
# 2. Register second session → first_session=False
# ===========================================================================


def test_02_register_second_session():
    uid = _new_uid("second")
    sid1 = new_session_id()
    sid2 = new_session_id()

    ps.register_session(uid, sid1)
    first, status = ps.register_session(uid, sid2)

    assert status == "ok"
    assert first is False


# ===========================================================================
# 3. Three sessions → is_user_online=True
# ===========================================================================


def test_03_three_sessions_user_is_online():
    uid = _new_uid("three")
    for _ in range(3):
        ps.register_session(uid, new_session_id())

    assert ps.is_user_online(uid) is True
    assert ps.get_active_session_count(uid) == 3


# ===========================================================================
# 4. Remove one of three → last_session=False
# ===========================================================================


def test_04_remove_one_of_three():
    uid = _new_uid("r1of3")
    sids = [new_session_id() for _ in range(3)]
    for sid in sids:
        ps.register_session(uid, sid)

    last, status = ps.remove_session(uid, sids[0])

    assert status == "ok"
    assert last is False
    assert ps.get_active_session_count(uid) == 2


# ===========================================================================
# 5. Remove second of three → last_session=False
# ===========================================================================


def test_05_remove_second_of_three():
    uid = _new_uid("r2of3")
    sids = [new_session_id() for _ in range(3)]
    for sid in sids:
        ps.register_session(uid, sid)

    ps.remove_session(uid, sids[0])
    last, status = ps.remove_session(uid, sids[1])

    assert status == "ok"
    assert last is False
    assert ps.get_active_session_count(uid) == 1


# ===========================================================================
# 6. Remove final session → last_session=True
# ===========================================================================


def test_06_remove_final_session():
    uid = _new_uid("rfinal")
    sid = new_session_id()
    ps.register_session(uid, sid)

    last, status = ps.remove_session(uid, sid)

    assert status == "ok"
    assert last is True
    assert ps.is_user_online(uid) is False


# ===========================================================================
# 7. is_user_online=True while session exists
# ===========================================================================


def test_07_is_online_true_while_session_exists():
    uid = _new_uid("online")
    sid = new_session_id()

    assert ps.is_user_online(uid) is False
    ps.register_session(uid, sid)
    assert ps.is_user_online(uid) is True


# ===========================================================================
# 8. is_user_online=False after all sessions removed
# ===========================================================================


def test_08_is_online_false_after_all_removed():
    uid = _new_uid("offline")
    sids = [new_session_id() for _ in range(2)]
    for sid in sids:
        ps.register_session(uid, sid)

    for sid in sids:
        ps.remove_session(uid, sid)

    assert ps.is_user_online(uid) is False


# ===========================================================================
# 9. Session refresh extends TTL
# ===========================================================================


def test_09_refresh_extends_ttl():
    uid = _new_uid("refresh")
    sid = new_session_id()
    ps.register_session(uid, sid)

    key = _session_key(sid)
    ttl_before = redis_client.ttl(key)
    assert ttl_before > 0

    # Overwrite with a short TTL manually to simulate near-expiry.
    redis_client.expire(key, 5)
    ttl_short = redis_client.ttl(key)
    assert ttl_short <= 5

    # Refresh should restore the full TTL.
    result = ps.refresh_session(uid, sid)
    assert result is True
    ttl_after = redis_client.ttl(key)
    assert ttl_after > 5  # restored to full TTL


# ===========================================================================
# 10. Session expiration removes presence (short TTL)
# ===========================================================================


def test_10_session_expiration_removes_presence():
    uid = _new_uid("expire")
    sid = new_session_id()
    ps.register_session(uid, sid)

    # Manually set a very short TTL on the session key.
    redis_client.expire(_session_key(sid), 1)

    # Before expiry: online.
    assert ps.is_user_online(uid) is True

    # Wait for expiry.
    time.sleep(1.5)

    # After expiry: session key gone → correctly reported offline.
    assert ps.is_user_online(uid) is False


# ===========================================================================
# 11. Different users have isolated presence
# ===========================================================================


def test_11_user_isolation():
    uid_a = _new_uid("iso_a")
    uid_b = _new_uid("iso_b")
    sid_a = new_session_id()

    ps.register_session(uid_a, sid_a)

    # user_a online, user_b still offline.
    assert ps.is_user_online(uid_a) is True
    assert ps.is_user_online(uid_b) is False

    # Removing user_a's session does not affect user_b.
    ps.remove_session(uid_a, sid_a)
    assert ps.is_user_online(uid_a) is False
    assert ps.is_user_online(uid_b) is False


# ===========================================================================
# 12. Session IDs are unique
# ===========================================================================


def test_12_session_ids_are_unique():
    sids = {new_session_id() for _ in range(1000)}
    assert len(sids) == 1000  # all distinct


# ===========================================================================
# 13. Client cannot choose session ID (server generates it)
# ===========================================================================


def test_13_server_generates_session_id():
    """
    new_session_id() generates a UUID4 server-side.
    The function must produce a valid UUID and must not use a fixed value.
    """
    sid = new_session_id()
    # Must be a valid UUID4.
    parsed = uuid.UUID(sid, version=4)
    assert str(parsed) == sid

    # Must differ from a second call.
    sid2 = new_session_id()
    assert sid != sid2


# ===========================================================================
# 14. Duplicate registration is handled safely
# ===========================================================================


def test_14_duplicate_registration_safe():
    uid = _new_uid("dup")
    sid = new_session_id()

    first1, status1 = ps.register_session(uid, sid)
    first2, status2 = ps.register_session(uid, sid)  # same sid

    assert status1 == "ok"
    assert first1 is True

    # Second call should be a no-op / duplicate — not counted as a new session.
    assert status2 == "duplicate"
    assert first2 is False

    # Count should still be 1.
    assert ps.get_active_session_count(uid) == 1


# ===========================================================================
# 15. Removing unknown session does not mark user offline
# ===========================================================================


def test_15_remove_unknown_session_safe():
    uid = _new_uid("unk")
    real_sid = new_session_id()
    fake_sid = new_session_id()

    ps.register_session(uid, real_sid)

    last, status = ps.remove_session(uid, fake_sid)  # fake_sid was never registered

    assert status == "not_found"
    assert last is False  # real session still active
    assert ps.is_user_online(uid) is True  # user still online


# ===========================================================================
# 16. Concurrent-style registration: first-session correctness
# ===========================================================================


def test_16_concurrent_registration_first_session():
    """
    Simulate near-simultaneous registrations:
    call register_session twice in rapid succession.
    Exactly one should return first_session=True.
    """
    uid = _new_uid("conc_reg")
    sid1 = new_session_id()
    sid2 = new_session_id()

    r1, _ = ps.register_session(uid, sid1)
    r2, _ = ps.register_session(uid, sid2)

    # Exactly one of them should be first.
    assert r1 is True
    assert r2 is False


# ===========================================================================
# 17. Concurrent-style removal: last-session correctness
# ===========================================================================


def test_17_concurrent_removal_last_session():
    """
    Three sessions; remove two.
    Only the final removal should return last_session=True.
    """
    uid = _new_uid("conc_rem")
    sids = [new_session_id() for _ in range(3)]
    for sid in sids:
        ps.register_session(uid, sid)

    results = [ps.remove_session(uid, sid) for sid in sids]
    last_flags = [r[0] for r in results]
    statuses   = [r[1] for r in results]

    # All statuses ok.
    assert all(s == "ok" for s in statuses)
    # Exactly one last-session=True.
    assert last_flags.count(True) == 1
    # last_session=True for the removal that left 0 sessions.
    assert last_flags[-1] is True


# ===========================================================================
# 18. Redis key design: session key stores user_id
# ===========================================================================


def test_18_redis_key_design():
    uid = _new_uid("keys")
    sid = new_session_id()

    ps.register_session(uid, sid)

    # The STRING key value must be the user_id.
    stored_uid = redis_client.get(_session_key(sid))
    assert stored_uid == uid

    # The SET must contain the session ID.
    members = redis_client.smembers(_user_sessions_key(uid))
    assert sid in members

    # The STRING key must have a TTL.
    ttl = redis_client.ttl(_session_key(sid))
    assert ttl > 0


# ===========================================================================
# 19. No Pub/Sub functionality in presence_service
# ===========================================================================


def test_19_no_pubsub_in_service():
    """
    Verify that the presence_service module does not import or use
    any Redis Pub/Sub functionality.
    """
    import inspect
    import app.services.presence_service as mod
    source = inspect.getsource(mod)

    # No Pub/Sub-related symbols.
    assert "pubsub" not in source.lower()
    assert "publish(" not in source
    assert "subscribe(" not in source
    assert "psubscribe(" not in source


# ===========================================================================
# 20. Existing Redis cache keys are unaffected by presence operations
# ===========================================================================


def test_20_existing_cache_unaffected():
    """
    Presence operations must not delete or corrupt unrelated Redis keys.
    """
    from app.services.cache_service import (
        set_cached_availability,
        get_cached_availability,
    )

    # Plant a cache key.
    set_cached_availability("username", "testuser_presence", '{"available":true}')

    # Perform various presence operations.
    uid = _new_uid("noconflict")
    sid = new_session_id()
    ps.register_session(uid, sid)
    ps.refresh_session(uid, sid)
    ps.remove_session(uid, sid)

    # Cache key must still exist and be correct.
    result = get_cached_availability("username", "testuser_presence")
    assert result is not None
    assert "available" in result

    # Cleanup the planted cache key.
    from app.services.cache_service import invalidate_availability
    invalidate_availability("username", "testuser_presence")
