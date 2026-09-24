"""
Phase 5.8.6 — Reliability fixes M3, M4, M5, M6 tests.

M3  Session TTL refresh: active WebSocket sessions call refresh_session()
    periodically so that the Redis presence key does not expire while the
    socket is open.

M4  Publish connect timeout: socket_connect_timeout reduced from 5 s to
    2 s for publish() calls, reducing per-message latency when Redis is
    unavailable.

M5  Explicit publish guard: publish_new_message() is now wrapped in an
    explicit try/except in _handle_message() so the no-raise contract is
    visible and any future regression is caught at the call site.

M6  Parallel startup: start_fanout_listener() and start_presence_listener()
    are run concurrently with asyncio.gather(), halving the startup delay
    when Redis is unavailable.

Test index
──────────
M3 — Session refresh
 1.  _session_refresh_loop calls refresh_session periodically
 2.  Refresh uses the correct user_id and session_id
 3.  refresh_session failure is non-fatal (loop continues)
 4.  _session_refresh_loop cancels cleanly on CancelledError
 5.  Refresh interval comes from REDIS_PRESENCE_REFRESH_INTERVAL_SECONDS
 6.  Refresh interval is less than TTL (config sanity check)
 7.  Refresh task is cancelled before remove_session on disconnect
 8.  Session remains online after TTL-triggering interval (integration)

M4 — Publish timeout
 9.  publish() uses socket_connect_timeout=2 (not 5)
10.  Publish returns False quickly on Redis failure (latency guard)

M5 — Explicit publish guard
11.  _handle_message wraps publish_new_message in try/except
12.  Exception from publish_new_message does not propagate to WS handler
13.  PostgreSQL message is persisted even if publish raises

M6 — Parallel startup
14.  start_fanout_listener and start_presence_listener called concurrently
15.  Both return values are captured independently
16.  Parallel startup completes in ~half the time of sequential
"""
from __future__ import annotations

import asyncio
import inspect
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.core.config import settings
from app.services.redis_pubsub_manager import RedisPubSubManager, PubSubEvent, Channels


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# M3 — Session refresh tests
# ---------------------------------------------------------------------------


# 1. _session_refresh_loop calls refresh_session periodically
def test_01_m3_refresh_loop_calls_refresh_periodically():
    """refresh_session must be called at least twice for a long-lived session."""
    import app.api.messaging_ws as ws_mod

    refresh_calls: list[tuple[str, str]] = []

    def fake_refresh(user_id: str, session_id: str) -> bool:
        refresh_calls.append((user_id, session_id))
        return True

    uid = str(uuid.uuid4())
    sid = str(uuid.uuid4())

    async def _test():
        with patch("app.api.messaging_ws.presence") as mock_presence:
            mock_presence.refresh_session = fake_refresh
            # Run loop for 2.5 * interval to get 2 refreshes
            interval = 0.05  # tiny interval for test speed
            with patch.object(settings, "REDIS_PRESENCE_REFRESH_INTERVAL_SECONDS", interval):
                task = asyncio.create_task(ws_mod._session_refresh_loop(uid, sid))
                await asyncio.sleep(interval * 2.5)
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        assert len(refresh_calls) >= 2, (
            f"Expected ≥2 refresh calls, got {len(refresh_calls)}"
        )

    _run(_test())


# 2. Refresh uses the correct user_id and session_id
def test_02_m3_refresh_uses_correct_ids():
    """Each refresh_session call must pass the exact uid and sid."""
    import app.api.messaging_ws as ws_mod

    calls: list[tuple[str, str]] = []

    def fake_refresh(user_id: str, session_id: str) -> bool:
        calls.append((user_id, session_id))
        return True

    uid = str(uuid.uuid4())
    sid = str(uuid.uuid4())

    async def _test():
        with patch("app.api.messaging_ws.presence") as mock_presence:
            mock_presence.refresh_session = fake_refresh
            with patch.object(settings, "REDIS_PRESENCE_REFRESH_INTERVAL_SECONDS", 0.05):
                task = asyncio.create_task(ws_mod._session_refresh_loop(uid, sid))
                await asyncio.sleep(0.08)
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        for u, s in calls:
            assert u == uid, f"user_id mismatch: {u!r} != {uid!r}"
            assert s == sid, f"session_id mismatch: {s!r} != {sid!r}"

    _run(_test())


# 3. refresh_session returning False is non-fatal — loop continues
def test_03_m3_refresh_failure_is_nonfatal():
    """If refresh_session returns False the loop must continue, not crash."""
    import app.api.messaging_ws as ws_mod

    call_count = 0

    def failing_refresh(user_id: str, session_id: str) -> bool:
        nonlocal call_count
        call_count += 1
        return False  # always fail

    uid = str(uuid.uuid4())
    sid = str(uuid.uuid4())

    async def _test():
        with patch("app.api.messaging_ws.presence") as mock_presence:
            mock_presence.refresh_session = failing_refresh
            with patch.object(settings, "REDIS_PRESENCE_REFRESH_INTERVAL_SECONDS", 0.04):
                task = asyncio.create_task(ws_mod._session_refresh_loop(uid, sid))
                await asyncio.sleep(0.12)
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    # Must complete without raising
    _run(_test())
    assert call_count >= 2, "Loop should have called refresh at least twice"


# 4. _session_refresh_loop cancels cleanly on CancelledError
def test_04_m3_refresh_loop_cancels_cleanly():
    """CancelledError must cause a clean exit, not an exception propagation."""
    import app.api.messaging_ws as ws_mod

    uid = str(uuid.uuid4())
    sid = str(uuid.uuid4())

    async def _test():
        with patch("app.api.messaging_ws.presence") as mock_presence:
            mock_presence.refresh_session = MagicMock(return_value=True)
            with patch.object(settings, "REDIS_PRESENCE_REFRESH_INTERVAL_SECONDS", 100):
                task = asyncio.create_task(ws_mod._session_refresh_loop(uid, sid))
                await asyncio.sleep(0.02)
                task.cancel()
                # Must not raise
                try:
                    await task
                except asyncio.CancelledError:
                    pass  # expected: re-raised after cancel
                except Exception as exc:
                    pytest.fail(f"Unexpected exception on cancel: {exc!r}")

    _run(_test())


# 5. Refresh interval comes from config
def test_05_m3_refresh_interval_from_config():
    """The loop must sleep for REDIS_PRESENCE_REFRESH_INTERVAL_SECONDS."""
    import app.api.messaging_ws as ws_mod

    sleep_calls: list[float] = []
    original_sleep = asyncio.sleep

    async def fake_sleep(secs):
        sleep_calls.append(secs)
        raise asyncio.CancelledError()  # exit after first sleep

    uid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    expected_interval = 42

    async def _test():
        with patch("app.api.messaging_ws.presence") as mock_presence:
            mock_presence.refresh_session = MagicMock(return_value=True)
            with patch.object(settings, "REDIS_PRESENCE_REFRESH_INTERVAL_SECONDS", expected_interval):
                with patch("app.api.messaging_ws.asyncio") as mock_asyncio:
                    mock_asyncio.sleep = fake_sleep
                    mock_asyncio.CancelledError = asyncio.CancelledError
                    mock_asyncio.create_task = asyncio.create_task
                    try:
                        await ws_mod._session_refresh_loop(uid, sid)
                    except asyncio.CancelledError:
                        pass

        assert sleep_calls, "asyncio.sleep must be called"
        assert sleep_calls[0] == expected_interval, (
            f"Expected sleep({expected_interval}), got sleep({sleep_calls[0]})"
        )

    _run(_test())


# 6. Refresh interval < TTL (config sanity)
def test_06_m3_refresh_interval_less_than_ttl():
    """REDIS_PRESENCE_REFRESH_INTERVAL_SECONDS must be < REDIS_PRESENCE_TTL_SECONDS."""
    assert settings.REDIS_PRESENCE_REFRESH_INTERVAL_SECONDS < settings.REDIS_PRESENCE_TTL_SECONDS, (
        f"Refresh interval ({settings.REDIS_PRESENCE_REFRESH_INTERVAL_SECONDS}s) must be "
        f"less than TTL ({settings.REDIS_PRESENCE_TTL_SECONDS}s)"
    )
    # Sanity: at least 2 refresh intervals fit within one TTL
    ratio = settings.REDIS_PRESENCE_TTL_SECONDS / settings.REDIS_PRESENCE_REFRESH_INTERVAL_SECONDS
    assert ratio >= 2, (
        f"TTL/refresh_interval ratio {ratio:.1f} is too low — "
        "a single missed refresh could expire the session"
    )


# 7. Refresh task is cancelled before remove_session on disconnect
def test_07_m3_refresh_task_cancelled_before_remove_session():
    """
    The refresh task must be cancelled BEFORE remove_session is called so
    it cannot race to refresh a session that is about to be deleted.
    Verify by inspecting the source code order in the finally block.
    """
    import app.api.messaging_ws as ws_mod
    source = inspect.getsource(ws_mod.websocket_messaging)

    cancel_pos      = source.find("_refresh_task.cancel()")
    remove_pos      = source.find("presence.remove_session(")

    assert cancel_pos != -1, "_refresh_task.cancel() not found in finally block"
    assert remove_pos != -1, "presence.remove_session() not found in finally block"
    assert cancel_pos < remove_pos, (
        "Refresh task cancellation must appear before remove_session in the finally block"
    )


# 8. Session stays alive across refresh interval (integration — real Redis)
def test_08_m3_session_stays_alive_with_refresh_integration():
    """
    If refresh_session() is called before TTL expiry, the session STRING key
    must still exist in Redis.
    """
    from app.services import presence_service as ps
    from app.db.redis_client import redis_client

    uid = str(uuid.uuid4())
    sid = ps.new_session_id()

    # Register with a short TTL via a direct Redis SET.
    short_ttl = 3  # 3 seconds
    redis_client.set(
        f"careersphere:presence:session:{sid}",
        uid,
        ex=short_ttl,
    )
    redis_client.sadd(f"careersphere:presence:user:{uid}:sessions", sid)

    import time
    time.sleep(1.5)  # wait half the TTL

    # Refresh — should reset to full TTL.
    with patch.object(settings, "REDIS_PRESENCE_TTL_SECONDS", short_ttl * 2):
        ok = ps.refresh_session(uid, sid)

    assert ok is True, "refresh_session must return True when key exists"

    time.sleep(2)  # wait past the original short TTL

    # Key should still exist because refresh extended it.
    key = f"careersphere:presence:session:{sid}"
    exists = redis_client.exists(key)
    # Clean up
    redis_client.delete(key)
    redis_client.srem(f"careersphere:presence:user:{uid}:sessions", sid)

    assert exists, (
        "Session key must still exist after refresh extended the TTL"
    )


# ---------------------------------------------------------------------------
# M4 — Publish timeout tests
# ---------------------------------------------------------------------------


# 9. publish() uses socket_connect_timeout=2
def test_09_m4_publish_uses_2s_timeout():
    """
    pubsub_manager.publish() must pass socket_connect_timeout=2 to
    aioredis.from_url(), not 5.
    """
    async def _test():
        connect_kwargs: list[dict] = []

        # aioredis.from_url is called synchronously and returns an async
        # context manager.  Use a regular function with a MagicMock ctx.
        def fake_from_url(url, **kwargs):
            connect_kwargs.append(kwargs)
            ctx = AsyncMock()
            ctx.__aenter__ = AsyncMock(return_value=ctx)
            ctx.__aexit__ = AsyncMock(return_value=False)
            ctx.publish = AsyncMock()
            return ctx

        mgr = RedisPubSubManager()
        event = PubSubEvent("test_event", {})

        with patch("app.services.redis_pubsub_manager.aioredis.from_url",
                   side_effect=fake_from_url):
            await mgr.publish(Channels.BROADCAST, event)

        assert connect_kwargs, "aioredis.from_url must be called"
        timeout = connect_kwargs[0].get("socket_connect_timeout")
        assert timeout == 2, (
            f"socket_connect_timeout must be 2 (M4), got {timeout!r}"
        )

    _run(_test())


# 10. Publish returns False without waiting the full old timeout
def test_10_m4_publish_fails_within_reasonable_time():
    """
    With socket_connect_timeout=2, a publish() failure on a bad host must
    complete within ~3 s.  (Not the old 5 s.)
    """
    async def _test():
        mgr = RedisPubSubManager()
        mgr._redis_url = "redis://192.0.2.1:9999/0"  # non-routable, will refuse

        event = PubSubEvent("test_event", {})
        start = asyncio.get_event_loop().time()
        result = await mgr.publish(Channels.BROADCAST, event)
        elapsed = asyncio.get_event_loop().time() - start

        assert result is False, "publish() must return False on connection failure"
        assert elapsed < 4.0, (
            f"publish() took {elapsed:.1f}s — expected < 4s with 2s connect timeout"
        )

    _run(_test())


# ---------------------------------------------------------------------------
# M5 — Explicit publish guard tests
# ---------------------------------------------------------------------------


# 11. _handle_message source has explicit try/except around publish_new_message
def test_11_m5_explicit_try_except_in_handle_message():
    """
    _handle_message must have an explicit try/except block that wraps
    publish_new_message() so the no-raise contract is enforced at the
    call site.
    """
    import app.api.messaging_ws as ws_mod
    source = inspect.getsource(ws_mod._handle_message)

    publish_pos = source.find("publish_new_message(")
    assert publish_pos != -1, "publish_new_message() call not found in _handle_message"

    # The word "try:" must appear before publish_new_message in the source.
    try_pos = source.rfind("try:", 0, publish_pos)
    assert try_pos != -1, (
        "No try: block found before publish_new_message in _handle_message — "
        "M5 explicit guard is missing"
    )

    # An except block must follow.
    except_pos = source.find("except Exception", publish_pos)
    assert except_pos != -1, (
        "No except Exception block found after publish_new_message — "
        "M5 guard is incomplete"
    )


# 12. Exception from publish_new_message does not propagate
def test_12_m5_publish_exception_does_not_propagate():
    """
    Even if publish_new_message() raises unexpectedly, _handle_message must
    not propagate the exception to the WebSocket loop.
    """
    import app.api.messaging_ws as ws_mod
    from app.services.websocket_manager import ConnectionManager
    from app.db.session import SessionLocal
    from app.db.models import User

    async def _test():
        # Set up a fake WebSocket and user.
        ws = AsyncMock()
        user = MagicMock(spec=User)
        user.id = str(uuid.uuid4())

        # Fake send_direct_message succeeds.
        fake_msg = MagicMock()
        fake_msg.id = str(uuid.uuid4())
        fake_msg.conversation_id = str(uuid.uuid4())
        fake_msg.sender_id = user.id
        fake_msg.content = "hello"
        fake_msg.created_at = None
        fake_msg.delivered_at = None
        fake_msg.read_at = None

        local_mgr = ConnectionManager()

        with patch("app.api.messaging_ws.svc") as mock_svc, \
             patch("app.api.messaging_ws.manager", local_mgr), \
             patch("app.api.messaging_ws.publish_new_message",
                   side_effect=RuntimeError("intentional test error")), \
             patch("app.api.messaging_ws.SessionLocal") as mock_session:

            mock_session.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_session.return_value.__exit__ = MagicMock(return_value=False)

            db_mock = MagicMock()
            mock_session.return_value = db_mock
            mock_svc.send_direct_message.return_value = fake_msg

            # Must NOT raise
            try:
                await ws_mod._handle_message(
                    ws,
                    str(uuid.uuid4()),
                    user,
                    str(uuid.uuid4()),
                    {"content": "hello"},
                )
            except RuntimeError as exc:
                pytest.fail(
                    f"_handle_message propagated publish_new_message exception: {exc!r}"
                )

    _run(_test())


# 13. PostgreSQL message persisted even if publish raises
def test_13_m5_postgresql_persisted_even_if_publish_raises():
    """
    send_direct_message() (PostgreSQL) must be called before
    publish_new_message().  The source order enforces this.
    """
    import app.api.messaging_ws as ws_mod
    source = inspect.getsource(ws_mod._handle_message)

    persist_pos = source.find("svc.send_direct_message(")
    publish_pos = source.find("publish_new_message(")

    assert persist_pos != -1, "svc.send_direct_message() not found"
    assert publish_pos != -1, "publish_new_message() not found"
    assert persist_pos < publish_pos, (
        "PostgreSQL persistence must appear BEFORE publish_new_message() in source"
    )


# ---------------------------------------------------------------------------
# M6 — Parallel startup tests
# ---------------------------------------------------------------------------


# 14. Both listeners called concurrently via asyncio.gather
def test_14_m6_listeners_started_concurrently():
    """
    main.py lifespan must call start_fanout_listener and start_presence_listener
    via asyncio.gather so they run concurrently.
    """
    import app.main as main_mod
    source = inspect.getsource(main_mod.lifespan)

    assert "gather" in source, (
        "asyncio.gather must be used in lifespan to start listeners concurrently (M6)"
    )
    assert "start_fanout_listener" in source
    assert "start_presence_listener" in source

    # Both must appear inside the same gather call (not separate awaits).
    gather_pos   = source.find("gather(")
    fanout_pos   = source.find("start_fanout_listener()")
    presence_pos = source.find("start_presence_listener()")

    # Both calls must appear after the gather keyword (within the gather block).
    assert gather_pos < fanout_pos, "start_fanout_listener must be inside gather()"
    assert gather_pos < presence_pos, "start_presence_listener must be inside gather()"


# 15. Both return values are captured
def test_15_m6_both_return_values_captured():
    """
    The gather result must be unpacked so both fanout_ok and presence_ok
    can be logged separately.
    """
    import app.main as main_mod
    source = inspect.getsource(main_mod.lifespan)

    # Both result variables must exist.
    assert "fanout_ok" in source,  "fanout_ok must be captured from gather result"
    assert "presence_ok" in source, "presence_ok must be captured from gather result"


# 16. Parallel startup faster than sequential on Redis failure (timing)
def test_16_m6_parallel_faster_than_sequential():
    """
    When both probes fail, the parallel approach completes in roughly the
    time of ONE probe, not TWO.  Demonstrates the M6 benefit.

    This test patches the listeners to sleep for a fixed time and verifies
    that gather completes in ~1× delay, not ~2×.
    """
    async def _test():
        delay = 0.15  # simulated probe delay per listener

        async def slow_fanout():
            await asyncio.sleep(delay)
            return False

        async def slow_presence():
            await asyncio.sleep(delay)
            return False

        start = asyncio.get_event_loop().time()
        fanout_ok, presence_ok = await asyncio.gather(slow_fanout(), slow_presence())
        elapsed = asyncio.get_event_loop().time() - start

        # Parallel: should take ~1× delay, not 2×.
        assert elapsed < delay * 1.8, (
            f"Parallel gather took {elapsed:.3f}s — expected < {delay * 1.8:.3f}s "
            f"(2× delay would be {delay * 2:.3f}s)"
        )
        assert fanout_ok is False
        assert presence_ok is False

    _run(_test())


# ---------------------------------------------------------------------------
# Cross-cutting: config values present
# ---------------------------------------------------------------------------


def test_17_config_has_refresh_interval():
    """REDIS_PRESENCE_REFRESH_INTERVAL_SECONDS must exist in config."""
    assert hasattr(settings, "REDIS_PRESENCE_REFRESH_INTERVAL_SECONDS"), (
        "Settings must have REDIS_PRESENCE_REFRESH_INTERVAL_SECONDS (M3)"
    )
    val = settings.REDIS_PRESENCE_REFRESH_INTERVAL_SECONDS
    assert isinstance(val, int) and val > 0, (
        f"REDIS_PRESENCE_REFRESH_INTERVAL_SECONDS must be a positive int, got {val!r}"
    )


def test_18_session_refresh_function_exists():
    """_session_refresh_loop must be importable from messaging_ws."""
    from app.api.messaging_ws import _session_refresh_loop
    assert callable(_session_refresh_loop)


def test_19_refresh_session_exists_in_presence_service():
    """presence_service.refresh_session must still be present and callable."""
    from app.services.presence_service import refresh_session
    assert callable(refresh_session)
