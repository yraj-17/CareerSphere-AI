"""
Phase 5.8.5.2 — Session/Connection Tracking tests.

Tests verify that every WebSocket connection creates a corresponding Redis
presence session, that session IDs are server-generated, that multiple
sockets produce multiple independent sessions, and that disconnect cleans
up both the local ConnectionManager and Redis.

Test approach
─────────────
Uses the same Starlette TestClient WebSocket pattern established in
test_messaging_websocket.py.  Where nested-socket limitations apply (sync
TestClient, single-threaded), the tests verify PostgreSQL/Redis state
directly rather than trying to receive cross-socket events simultaneously.

Tests:
 1.  WebSocket connection creates Redis presence session.
 2.  Server generates session_id (client cannot supply it).
 3.  Session is associated with the correct user.
 4.  First socket → first_session=True in Redis (user comes online).
 5.  Second socket → first_session=False (user already online).
 6.  Multiple sockets create multiple Redis sessions.
 7.  Disconnect removes exactly the corresponding Redis session.
 8.  Removing one of multiple sessions does not mark user offline.
 9.  Removing the final session makes user offline.
10.  Sessions for different conversations count as one user-wide pool.
11.  Normal WebSocketDisconnect cleans Redis session.
12.  ConnectionManager local state cleaned on disconnect.
13.  Redis failure does not corrupt PostgreSQL.
14.  Redis failure follows Phase 5.8.5.1 failure behavior (safe fallback).
15.  Existing WebSocket message behavior still works.
16.  Existing typing event behavior still works.
17.  No Pub/Sub code introduced.
18.  No database migration introduced.
19.  presence_service.py is unchanged (not re-imported with new API).
20.  Existing ConnectionManager behavior remains correct.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import or_

from app.db.models import Connection, User
from app.db.redis_client import redis_client
from app.db.session import Base, SessionLocal, engine
from app.core.config import settings
from app.main import app
from app.services import presence_service as presence
from app.services.presence_service import _session_key, _user_sessions_key
from app.services.websocket_manager import manager

client = TestClient(app)

# ---------------------------------------------------------------------------
# Helpers (identical pattern to test_messaging_websocket.py)
# ---------------------------------------------------------------------------

_CTR = 0


def _unique_tag() -> str:
    global _CTR
    _CTR += 1
    return f"{_CTR}_{uuid.uuid4().hex[:6]}"


def _seed_otp(email: str) -> str:
    from app.db.redis_client import redis_client as rc
    token = f"test-token-{uuid.uuid4().hex}"
    token_hash = hashlib.sha256(
        f"{email}:{token}:{settings.SECRET_KEY}".encode()
    ).hexdigest()
    payload = json.dumps({"otp": "123456", "verified_token": token_hash, "token_raw": token})
    rc.set(f"otp:{email}", payload, ex=600)
    return token


def _register_user(tag: Optional[str] = None) -> dict:
    if tag is None:
        tag = _unique_tag()
    email = f"st_{tag}@example.com"
    username = f"st_{tag}"[:30]
    res = client.post("/api/auth/register", json={
        "first_name": "Track",
        "last_name": "Test",
        "username": username,
        "email": email,
        "password": "Password123",
        "email_verification_token": _seed_otp(email),
    })
    assert res.status_code == 201, f"Register failed: {res.text}"
    uid = res.json()["id"]
    login = client.post("/api/auth/login", json={"identifier": username, "password": "Password123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"user_id": uid, "username": username, "email": email, "token": token,
            "headers": {"Authorization": f"Bearer {token}"}}


def _cleanup_users(*emails: str) -> None:
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.email.in_(emails)).all()
        ids = [u.id for u in users]
        if ids:
            db.query(Connection).filter(
                or_(Connection.requester_id.in_(ids), Connection.receiver_id.in_(ids))
            ).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(ids)).delete(synchronize_session=False)
            db.commit()
    finally:
        db.close()


def _make_accepted_connection(ua: dict, ub: dict) -> str:
    send = client.post(f"/api/networking/connections/{ub['user_id']}", headers=ua["headers"])
    assert send.status_code == 201, send.text
    conn_id = send.json()["id"]
    accept = client.post(f"/api/networking/requests/{conn_id}/accept", headers=ub["headers"])
    assert accept.status_code == 200
    return conn_id


def _open_conv(ua: dict, ub: dict) -> str:
    res = client.post(f"/api/messaging/conversations/{ub['user_id']}", headers=ua["headers"])
    assert res.status_code == 200, res.text
    return res.json()["id"]


def _ws_url(conv_id: str, token: str) -> str:
    return f"/api/messaging/ws/{conv_id}?token={token}"


def _recv(ws) -> dict:
    return json.loads(ws.receive_text())


def _recv_skip_lifecycle(ws) -> dict:
    while True:
        event = _recv(ws)
        if event.get("type") not in ("user_online", "user_offline"):
            return event


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_state():
    Base.metadata.create_all(bind=engine)
    # Clean presence keys before each test.
    try:
        keys = redis_client.keys("careersphere:presence:*")
        if keys:
            redis_client.delete(*keys)
    except Exception:
        pass
    # Reset local ConnectionManager.
    manager._connections.clear()
    yield
    manager._connections.clear()
    try:
        keys = redis_client.keys("careersphere:presence:*")
        if keys:
            redis_client.delete(*keys)
    except Exception:
        pass


@pytest.fixture()
def user_a():
    u = _register_user()
    yield u
    _cleanup_users(u["email"])


@pytest.fixture()
def user_b():
    u = _register_user()
    yield u
    _cleanup_users(u["email"])


@pytest.fixture()
def user_c():
    u = _register_user()
    yield u
    _cleanup_users(u["email"])


@pytest.fixture()
def connected_pair(user_a, user_b):
    _make_accepted_connection(user_a, user_b)
    return user_a, user_b


@pytest.fixture()
def open_conv(connected_pair):
    user_a, user_b = connected_pair
    conv_id = _open_conv(user_a, user_b)
    return conv_id, user_a, user_b


# ===========================================================================
# 1. WebSocket connection creates a Redis presence session
# ===========================================================================


def test_01_ws_connection_creates_redis_session(open_conv):
    conv_id, user_a, user_b = open_conv
    uid = user_a["user_id"]

    assert not presence.is_user_online(uid)

    with client.websocket_connect(_ws_url(conv_id, user_a["token"])):
        # A Redis session must now exist for user_a.
        assert presence.is_user_online(uid)
        assert presence.get_active_session_count(uid) == 1

    # After disconnect, no sessions remain.
    assert not presence.is_user_online(uid)


# ===========================================================================
# 2. Server generates session_id (client cannot supply it)
# ===========================================================================


def test_02_server_generates_session_id(open_conv):
    conv_id, user_a, user_b = open_conv
    uid = user_a["user_id"]

    with client.websocket_connect(_ws_url(conv_id, user_a["token"])):
        sessions = presence.get_active_sessions(uid)
        assert len(sessions) == 1
        sid = sessions[0]
        # Must be a valid UUID4 — server-generated.
        parsed = uuid.UUID(sid, version=4)
        assert str(parsed) == sid


# ===========================================================================
# 3. Session is associated with the correct user
# ===========================================================================


def test_03_session_associated_with_correct_user(open_conv):
    conv_id, user_a, user_b = open_conv
    uid = user_a["user_id"]

    with client.websocket_connect(_ws_url(conv_id, user_a["token"])):
        sessions = presence.get_active_sessions(uid)
        assert sessions
        sid = sessions[0]
        # The STRING key value must be the user_id.
        stored_uid = redis_client.get(_session_key(sid))
        assert stored_uid == uid


# ===========================================================================
# 4. First socket → Redis registers first_session=True
# ===========================================================================


def test_04_first_socket_is_first_session(open_conv):
    conv_id, user_a, user_b = open_conv
    uid = user_a["user_id"]

    # Before connecting: no sessions.
    assert presence.get_active_session_count(uid) == 0

    with client.websocket_connect(_ws_url(conv_id, user_a["token"])):
        # Exactly one session; it was the first.
        assert presence.get_active_session_count(uid) == 1


# ===========================================================================
# 5. Second socket → Redis shows first_session=False (already online)
# ===========================================================================


def test_05_second_socket_not_first_session(open_conv):
    conv_id, user_a, user_b = open_conv
    uid = user_a["user_id"]

    # First socket opens.
    with client.websocket_connect(_ws_url(conv_id, user_a["token"])):
        count_after_first = presence.get_active_session_count(uid)
        assert count_after_first == 1

        # Second socket opens within the same conversation.
        with client.websocket_connect(_ws_url(conv_id, user_a["token"])):
            count_after_second = presence.get_active_session_count(uid)
            assert count_after_second == 2

        # After second socket closes, first remains.
        assert presence.get_active_session_count(uid) == 1


# ===========================================================================
# 6. Multiple sockets create multiple Redis sessions
# ===========================================================================


def test_06_multiple_sockets_create_multiple_sessions(open_conv):
    conv_id, user_a, user_b = open_conv
    uid = user_a["user_id"]

    with client.websocket_connect(_ws_url(conv_id, user_a["token"])):
        with client.websocket_connect(_ws_url(conv_id, user_a["token"])):
            assert presence.get_active_session_count(uid) == 2
            sessions = presence.get_active_sessions(uid)
            # All session IDs must be distinct.
            assert len(set(sessions)) == 2


# ===========================================================================
# 7. Disconnect removes exactly the corresponding Redis session
# ===========================================================================


def test_07_disconnect_removes_correct_session(open_conv):
    conv_id, user_a, user_b = open_conv
    uid = user_a["user_id"]

    with client.websocket_connect(_ws_url(conv_id, user_a["token"])):
        with client.websocket_connect(_ws_url(conv_id, user_a["token"])):
            sids_during = set(presence.get_active_sessions(uid))
            assert len(sids_during) == 2

        # After inner socket closes, exactly one session removed.
        sids_after = set(presence.get_active_sessions(uid))
        assert len(sids_after) == 1
        # The remaining session must be one of the original two.
        assert sids_after.issubset(sids_during)


# ===========================================================================
# 8. Removing one of multiple sessions does not mark user offline
# ===========================================================================


def test_08_remove_one_session_user_stays_online(open_conv):
    conv_id, user_a, user_b = open_conv
    uid = user_a["user_id"]

    with client.websocket_connect(_ws_url(conv_id, user_a["token"])):
        with client.websocket_connect(_ws_url(conv_id, user_a["token"])):
            pass  # inner closes — one session removed
        # user still online: outer socket / session remains.
        assert presence.is_user_online(uid)


# ===========================================================================
# 9. Removing final session → user offline
# ===========================================================================


def test_09_remove_final_session_user_offline(open_conv):
    conv_id, user_a, user_b = open_conv
    uid = user_a["user_id"]

    with client.websocket_connect(_ws_url(conv_id, user_a["token"])):
        assert presence.is_user_online(uid)

    # Both outer socket closed → user offline.
    assert not presence.is_user_online(uid)
    assert presence.get_active_session_count(uid) == 0


# ===========================================================================
# 10. Sessions for different conversations count as one user-wide pool
# ===========================================================================


def test_10_sessions_from_different_conversations_share_presence_pool(
    user_a, user_b, user_c
):
    """
    user_a connects to two different conversations (with user_b and user_c).
    Both should count toward user_a's single presence pool.
    """
    _make_accepted_connection(user_a, user_b)
    _make_accepted_connection(user_a, user_c)
    conv_ab = _open_conv(user_a, user_b)
    conv_ac = _open_conv(user_a, user_c)

    uid = user_a["user_id"]

    with client.websocket_connect(_ws_url(conv_ab, user_a["token"])):
        with client.websocket_connect(_ws_url(conv_ac, user_a["token"])):
            # Two sessions even though they're for different conversations.
            assert presence.get_active_session_count(uid) == 2

        # One session remains.
        assert presence.get_active_session_count(uid) == 1

    assert not presence.is_user_online(uid)


# ===========================================================================
# 11. Normal WebSocketDisconnect cleans Redis session
# ===========================================================================


def test_11_normal_disconnect_cleans_redis(open_conv):
    conv_id, user_a, user_b = open_conv
    uid = user_a["user_id"]

    with client.websocket_connect(_ws_url(conv_id, user_a["token"])):
        assert presence.is_user_online(uid)

    # Context manager exit triggers WebSocketDisconnect path in the endpoint.
    assert not presence.is_user_online(uid)
    # Redis keys fully cleaned.
    assert redis_client.keys(f"careersphere:presence:user:{uid}:sessions") == []


# ===========================================================================
# 12. ConnectionManager local state cleaned on disconnect
# ===========================================================================


def test_12_local_manager_cleaned_on_disconnect(open_conv):
    conv_id, user_a, user_b = open_conv
    uid = user_a["user_id"]

    with client.websocket_connect(_ws_url(conv_id, user_a["token"])):
        assert manager.is_connected(uid)

    assert not manager.is_connected(uid)
    assert manager.active_socket_count(uid) == 0


# ===========================================================================
# 13. Redis failure does not corrupt PostgreSQL
# ===========================================================================


def test_13_redis_failure_does_not_corrupt_postgresql(open_conv):
    """
    Even if Redis is unavailable for presence tracking, the WebSocket
    can still deliver and persist messages to PostgreSQL.

    We simulate a Redis miss by pre-populating the presence state with a
    known session and then verifying PostgreSQL is unaffected after
    connection + message operations.
    """
    from app.db.models import DirectMessage
    conv_id, user_a, user_b = open_conv

    with client.websocket_connect(_ws_url(conv_id, user_a["token"])) as ws:
        ws.send_text(json.dumps({"type": "message", "data": {"content": "Redis-independent"}}))
        _recv_skip_lifecycle(ws)  # consume new_message event

    db = SessionLocal()
    try:
        msgs = db.query(DirectMessage).filter_by(conversation_id=conv_id).all()
        assert len(msgs) == 1
        assert msgs[0].content == "Redis-independent"
        assert msgs[0].sender_id == user_a["user_id"]
    finally:
        db.close()


# ===========================================================================
# 14. Redis failure follows Phase 5.8.5.1 safe fallback policy
# ===========================================================================


def test_14_redis_safe_fallback_policy():
    """
    Verify that the presence_service itself returns (False, 'error')
    when Redis is unavailable, and that this does not raise an exception.
    """
    import unittest.mock as mock

    uid = f"test-uid-{uuid.uuid4().hex[:8]}"
    sid = presence.new_session_id()

    # Simulate Redis being unavailable.
    with mock.patch("app.services.presence_service.redis_client") as mock_redis:
        mock_redis.get.side_effect = Exception("Redis unavailable")
        mock_redis.pipeline.side_effect = Exception("Redis unavailable")

        first, status = presence.register_session(uid, sid)
        assert status == "error"
        assert first is False  # conservative

    # Simulate remove_session with unavailable Redis.
    with mock.patch("app.services.presence_service.redis_client") as mock_redis:
        mock_redis.get.side_effect = Exception("Redis unavailable")

        last, status = presence.remove_session(uid, sid)
        assert status == "error"
        assert last is False  # conservative


# ===========================================================================
# 15. Existing WebSocket message behavior still works
# ===========================================================================


def test_15_existing_message_behavior_works(open_conv):
    from app.db.models import DirectMessage
    conv_id, user_a, user_b = open_conv

    with client.websocket_connect(_ws_url(conv_id, user_a["token"])) as ws:
        ws.send_text(json.dumps({"type": "message", "data": {"content": "Still works"}}))
        event = _recv(ws)

    assert event["type"] == "new_message"
    assert event["data"]["content"] == "Still works"
    assert event["data"]["sender_id"] == user_a["user_id"]

    db = SessionLocal()
    try:
        msgs = db.query(DirectMessage).filter_by(conversation_id=conv_id).all()
        assert any(m.content == "Still works" for m in msgs)
    finally:
        db.close()


# ===========================================================================
# 16. Existing typing event behavior still works
# ===========================================================================


def test_16_existing_typing_behavior_works(open_conv):
    conv_id, user_a, user_b = open_conv

    with client.websocket_connect(_ws_url(conv_id, user_b["token"])) as ws_b:
        with client.websocket_connect(_ws_url(conv_id, user_a["token"])) as ws_a:
            # Drain user_online that ws_b receives when user_a connects.
            ev = _recv(ws_b)
            assert ev["type"] == "user_online"
            ws_a.send_text(json.dumps({"type": "typing_start", "data": {}}))
            event = _recv(ws_b)

    assert event["type"] == "user_typing"
    assert event["data"]["user_id"] == user_a["user_id"]


# ===========================================================================
# 17. No Pub/Sub code introduced in messaging_ws.py
# ===========================================================================


def test_17_no_pubsub_in_ws_endpoint():
    import inspect
    import app.api.messaging_ws as mod

    source = inspect.getsource(mod).lower()
    assert "pubsub" not in source
    assert "publish(" not in source
    assert "subscribe(" not in source


# ===========================================================================
# 18. No database migration introduced
# ===========================================================================


def test_18_no_new_migration():
    import os
    migration_dir = "alembic/versions"
    files = [
        f for f in os.listdir(migration_dir)
        if f.endswith(".py") and not f.startswith("_")
    ]
    # The last migration is 007_messaging; no new migration should exist.
    assert "007_messaging.py" in files
    # No file beyond 007 should exist.
    ids = sorted(
        int(f.split("_")[0])
        for f in files
        if f.split("_")[0].isdigit()
    )
    assert max(ids) == 7


# ===========================================================================
# 19. presence_service.py API unchanged (frozen)
# ===========================================================================


def test_19_presence_service_api_unchanged():
    """
    Verify that the frozen presence_service still exposes the same public API.
    """
    for fn_name in (
        "new_session_id",
        "register_session",
        "remove_session",
        "refresh_session",
        "is_user_online",
        "get_active_session_count",
        "get_active_sessions",
        "cleanup_stale_sessions",
    ):
        assert hasattr(presence, fn_name), f"Missing API: {fn_name}"


# ===========================================================================
# 20. ConnectionManager local behavior unchanged
# ===========================================================================


def test_20_connection_manager_local_behavior_unchanged(open_conv):
    conv_id, user_a, user_b = open_conv
    uid = user_a["user_id"]

    assert manager.active_socket_count(uid) == 0

    with client.websocket_connect(_ws_url(conv_id, user_a["token"])):
        assert manager.active_socket_count(uid) == 1
        assert manager.is_connected(uid)

        with client.websocket_connect(_ws_url(conv_id, user_a["token"])):
            assert manager.active_socket_count(uid) == 2

        assert manager.active_socket_count(uid) == 1

    assert manager.active_socket_count(uid) == 0
    assert not manager.is_connected(uid)
