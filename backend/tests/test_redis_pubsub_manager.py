"""
Phase 5.8.3 — Redis Pub/Sub Manager tests.

Test strategy
─────────────
Async operations are run via ``asyncio.run()`` — consistent with the
project's existing approach of not requiring pytest-asyncio.  The project
uses anyio-4.14.2 as a plugin but the existing test suite (test_messaging_ws,
test_session_tracking, etc.) doesn't use ``@pytest.mark.anyio``; instead
the async WebSocket endpoints are exercised through the synchronous
Starlette TestClient which handles the event loop internally.

For the Pub/Sub manager we wrap async calls in ``asyncio.run()`` directly,
which is the least-invasive approach that matches the project's conventions.

Most tests mock redis.asyncio so no external Redis server is needed.
Three integration tests use the real Redis server (same as test_presence_service.py
and test_session_tracking.py).

Test index
──────────
UNIT TESTS (mocked Redis):
 1.  Manager initialises with expected defaults
 2.  Channels constants follow naming convention
 3.  PubSubEvent serialises to JSON with required fields
 4.  PubSubEvent deserialises from JSON correctly
 5.  PubSubEvent round-trip preserves all fields
 6.  Malformed JSON raises ValueError
 7.  Missing event_type raises ValueError
 8.  Non-dict JSON raises ValueError
 9.  publish() returns True on success (mocked)
10.  publish() returns False on Redis error (mocked)
11.  subscribe() returns True on success (mocked)
12.  subscribe() returns False on Redis error (mocked)
13.  unsubscribe() clears subscribed channels (mocked)
14.  start_listener() launches background task (mocked)
15.  stop_listener() cancels task and closes connections (mocked)
16.  Listener receives event and calls handler (mocked)
17.  Listener skips malformed JSON safely (mocked)
18.  Listener handles malformed event_type safely (mocked)
19.  Listener exits cleanly on Redis read error (mocked)
20.  Multiple channels are supported (mocked)

INTEGRATION TESTS (real Redis):
21.  publish() succeeds on real Redis
22.  subscriber receives published event via real Redis
23.  stop_listener() releases resources cleanly
24.  Frozen Phase 5.8.1/5.8.2 presence service is unaffected
25.  No Pub/Sub symbols in presence_service.py
"""
from __future__ import annotations

import asyncio
import json
import uuid
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.redis_pubsub_manager import (
    Channels,
    PubSubEvent,
    RedisPubSubManager,
    _CHANNEL_NS,
    get_instance_id,
    pubsub_manager,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(event_type: str = "test_event", payload: dict | None = None) -> PubSubEvent:
    return PubSubEvent(event_type, payload or {"key": "value"})


def _make_raw_message(channel: str, event: PubSubEvent) -> dict:
    """Simulate the dict redis.asyncio returns from get_message()."""
    return {"type": "message", "channel": channel, "data": event.to_json()}


def _run(coro):
    """Run an async coroutine synchronously — project-consistent pattern."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# UNIT TESTS (mocked Redis)
# ---------------------------------------------------------------------------


# 1. Manager initialises with expected defaults
def test_01_manager_defaults():
    mgr = RedisPubSubManager()
    assert mgr._sub_client is None
    assert mgr._pubsub is None
    assert mgr._listener_task is None
    assert mgr._running is False
    assert mgr.subscribed_channels == frozenset()
    assert not mgr.is_running


# 2. Channel naming convention
def test_02_channel_naming():
    assert Channels.BROADCAST.startswith("careersphere:pubsub:")
    assert Channels.messaging("conv-1") == f"{_CHANNEL_NS}:messaging:conv-1"
    assert Channels.presence() == f"{_CHANNEL_NS}:presence"
    assert Channels.custom("foo") == f"{_CHANNEL_NS}:foo"


# 3. PubSubEvent serialises to JSON with required fields
def test_03_event_serialisation():
    evt = _make_event()
    data = json.loads(evt.to_json())
    assert "event_type" in data
    assert "event_id" in data
    assert "timestamp" in data
    assert "source" in data
    assert "payload" in data
    assert data["event_type"] == "test_event"
    assert data["payload"] == {"key": "value"}


# 4. PubSubEvent deserialises from JSON
def test_04_event_deserialisation():
    raw = json.dumps({
        "event_type": "new_message",
        "event_id": str(uuid.uuid4()),
        "timestamp": "2026-01-01T00:00:00+00:00",
        "source": "instance-abc",
        "payload": {"msg": "hello"},
    })
    evt = PubSubEvent.from_json(raw)
    assert evt.event_type == "new_message"
    assert evt.payload == {"msg": "hello"}
    assert evt.source == "instance-abc"


# 5. PubSubEvent round-trip
def test_05_event_round_trip():
    original = PubSubEvent("ping", {"a": 1, "b": [1, 2, 3]})
    restored = PubSubEvent.from_json(original.to_json())
    assert restored == original
    assert restored.event_type == original.event_type
    assert restored.payload == original.payload
    assert restored.source == original.source


# 6. Malformed JSON raises ValueError
def test_06_malformed_json_raises():
    with pytest.raises(ValueError, match="Malformed JSON"):
        PubSubEvent.from_json("not json {{{")


# 7. Missing event_type raises ValueError
def test_07_missing_event_type_raises():
    raw = json.dumps({"payload": {}, "event_id": str(uuid.uuid4())})
    with pytest.raises(ValueError, match="event_type"):
        PubSubEvent.from_json(raw)


# 8. Non-dict JSON raises ValueError
def test_08_non_dict_json_raises():
    with pytest.raises(ValueError, match="JSON object"):
        PubSubEvent.from_json(json.dumps([1, 2, 3]))


# 9. publish() returns True on success (mocked)
def test_09_publish_success():
    mgr = RedisPubSubManager()
    mock_redis_ctx = AsyncMock()
    mock_redis_ctx.__aenter__ = AsyncMock(return_value=mock_redis_ctx)
    mock_redis_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_redis_ctx.publish = AsyncMock()

    with patch("app.services.redis_pubsub_manager.aioredis.from_url",
               return_value=mock_redis_ctx):
        result = _run(mgr.publish(Channels.BROADCAST, _make_event()))

    assert result is True
    mock_redis_ctx.publish.assert_awaited_once()


# 10. publish() returns False on Redis error (mocked)
def test_10_publish_failure():
    mgr = RedisPubSubManager()
    mock_redis_ctx = AsyncMock()
    mock_redis_ctx.__aenter__ = AsyncMock(return_value=mock_redis_ctx)
    mock_redis_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_redis_ctx.publish = AsyncMock(side_effect=Exception("Redis down"))

    with patch("app.services.redis_pubsub_manager.aioredis.from_url",
               return_value=mock_redis_ctx):
        result = _run(mgr.publish(Channels.BROADCAST, _make_event()))

    assert result is False


# 11. subscribe() returns True on success (mocked)
def test_11_subscribe_success():
    mgr = RedisPubSubManager()
    mock_client = AsyncMock()
    mock_pubsub = AsyncMock()
    mock_client.pubsub = MagicMock(return_value=mock_pubsub)

    with patch("app.services.redis_pubsub_manager.aioredis.from_url",
               return_value=mock_client):
        result = _run(mgr.subscribe(Channels.BROADCAST))

    assert result is True
    assert Channels.BROADCAST in mgr.subscribed_channels


# 12. subscribe() returns False on Redis error (mocked)
def test_12_subscribe_failure():
    mgr = RedisPubSubManager()
    mock_client = AsyncMock()
    mock_pubsub = AsyncMock()
    mock_pubsub.subscribe = AsyncMock(side_effect=Exception("Redis unavailable"))
    mock_client.pubsub = MagicMock(return_value=mock_pubsub)

    with patch("app.services.redis_pubsub_manager.aioredis.from_url",
               return_value=mock_client):
        result = _run(mgr.subscribe(Channels.BROADCAST))

    assert result is False


# 13. unsubscribe() clears subscribed channels (mocked)
def test_13_unsubscribe_clears_channels():
    mgr = RedisPubSubManager()
    mock_client = AsyncMock()
    mock_pubsub = AsyncMock()
    mock_client.pubsub = MagicMock(return_value=mock_pubsub)

    with patch("app.services.redis_pubsub_manager.aioredis.from_url",
               return_value=mock_client):
        _run(mgr.subscribe(Channels.BROADCAST))

    assert Channels.BROADCAST in mgr.subscribed_channels
    _run(mgr.unsubscribe(Channels.BROADCAST))
    assert Channels.BROADCAST not in mgr.subscribed_channels


# 14. start_listener() launches background task (mocked)
def test_14_start_listener_launches_task():
    async def _test():
        mgr = RedisPubSubManager()
        mock_client = AsyncMock()
        mock_pubsub = AsyncMock()
        # Raise CancelledError so the loop exits quickly.
        mock_pubsub.get_message = AsyncMock(side_effect=asyncio.CancelledError)
        mock_client.pubsub = MagicMock(return_value=mock_pubsub)

        async def noop_handler(channel, event):
            pass

        with patch("app.services.redis_pubsub_manager.aioredis.from_url",
                   return_value=mock_client):
            result = await mgr.start_listener([Channels.BROADCAST], noop_handler)

        assert result is True
        await mgr.stop_listener()

    _run(_test())


# 15. stop_listener() cancels task and closes connections (mocked)
def test_15_stop_listener_cancels_task():
    async def _test():
        mgr = RedisPubSubManager()
        mock_client = AsyncMock()
        mock_pubsub = AsyncMock()

        async def _stall(*args, **kwargs):
            await asyncio.sleep(3600)
            return None

        mock_pubsub.get_message = _stall
        mock_client.pubsub = MagicMock(return_value=mock_pubsub)

        async def noop_handler(channel, event):
            pass

        with patch("app.services.redis_pubsub_manager.aioredis.from_url",
                   return_value=mock_client):
            await mgr.start_listener([Channels.BROADCAST], noop_handler)
            assert mgr.is_running
            await mgr.stop_listener()

        assert not mgr.is_running
        assert mgr._listener_task is None

    _run(_test())


# 16. Listener receives event and calls handler (mocked)
def test_16_listener_calls_handler():
    async def _test():
        mgr = RedisPubSubManager()
        received: list[tuple[str, PubSubEvent]] = []

        evt = _make_event("hello")
        call_count = 0

        async def get_msg(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_raw_message(Channels.BROADCAST, evt)
            mgr._running = False
            return None

        mock_client = AsyncMock()
        mock_pubsub = AsyncMock()
        mock_pubsub.get_message = get_msg
        mock_client.pubsub = MagicMock(return_value=mock_pubsub)

        async def handler(channel: str, event: PubSubEvent):
            received.append((channel, event))

        with patch("app.services.redis_pubsub_manager.aioredis.from_url",
                   return_value=mock_client):
            await mgr.subscribe(Channels.BROADCAST)
            mgr._handler = handler
            mgr._running = True
            await mgr._listen_loop()

        assert len(received) == 1
        assert received[0][0] == Channels.BROADCAST
        assert received[0][1].event_type == "hello"

    _run(_test())


# 17. Listener skips malformed JSON safely (mocked)
def test_17_listener_skips_malformed_json():
    async def _test():
        mgr = RedisPubSubManager()
        received: list = []
        bad_message = {"type": "message", "channel": Channels.BROADCAST,
                       "data": "NOT JSON {{{"}
        call_count = 0

        async def get_msg(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return bad_message
            mgr._running = False
            return None

        mock_client = AsyncMock()
        mock_pubsub = AsyncMock()
        mock_pubsub.get_message = get_msg
        mock_client.pubsub = MagicMock(return_value=mock_pubsub)

        async def handler(channel, event):
            received.append(event)

        with patch("app.services.redis_pubsub_manager.aioredis.from_url",
                   return_value=mock_client):
            await mgr.subscribe(Channels.BROADCAST)
            mgr._handler = handler
            mgr._running = True
            await mgr._listen_loop()

        # Handler must NOT have been called.
        assert received == []

    _run(_test())


# 18. Listener handles missing event_type safely (mocked)
def test_18_listener_skips_missing_event_type():
    async def _test():
        mgr = RedisPubSubManager()
        received: list = []
        bad_data = json.dumps({"payload": {}, "event_id": str(uuid.uuid4())})
        bad_msg = {"type": "message", "channel": Channels.BROADCAST, "data": bad_data}
        call_count = 0

        async def get_msg(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return bad_msg
            mgr._running = False
            return None

        mock_client = AsyncMock()
        mock_pubsub = AsyncMock()
        mock_pubsub.get_message = get_msg
        mock_client.pubsub = MagicMock(return_value=mock_pubsub)

        async def handler(channel, event):
            received.append(event)

        with patch("app.services.redis_pubsub_manager.aioredis.from_url",
                   return_value=mock_client):
            await mgr.subscribe(Channels.BROADCAST)
            mgr._handler = handler
            mgr._running = True
            await mgr._listen_loop()

        assert received == []

    _run(_test())


# 19. Listener exits cleanly on Redis read error (mocked)
def test_19_listener_exits_on_redis_error():
    async def _test():
        mgr = RedisPubSubManager()
        mock_client = AsyncMock()
        mock_pubsub = AsyncMock()
        mock_pubsub.get_message = AsyncMock(side_effect=Exception("Connection reset"))
        mock_client.pubsub = MagicMock(return_value=mock_pubsub)

        async def noop_handler(channel, event):
            pass

        with patch("app.services.redis_pubsub_manager.aioredis.from_url",
                   return_value=mock_client):
            await mgr.subscribe(Channels.BROADCAST)
            mgr._handler = noop_handler
            mgr._running = True
            # Must exit cleanly, not raise.
            await mgr._listen_loop()

    _run(_test())


# 20. Multiple channels are supported (mocked)
def test_20_multiple_channels_supported():
    async def _test():
        mgr = RedisPubSubManager()
        mock_client = AsyncMock()
        mock_pubsub = AsyncMock()
        mock_client.pubsub = MagicMock(return_value=mock_pubsub)

        channels = [Channels.BROADCAST, Channels.messaging("conv-1"), Channels.presence()]

        with patch("app.services.redis_pubsub_manager.aioredis.from_url",
                   return_value=mock_client):
            result = await mgr.subscribe(*channels)

        assert result is True
        for ch in channels:
            assert ch in mgr.subscribed_channels
        assert len(mgr.subscribed_channels) == len(channels)

    _run(_test())


# ---------------------------------------------------------------------------
# INTEGRATION TESTS (real Redis)
# ---------------------------------------------------------------------------


# 21. publish() succeeds on real Redis
def test_21_integration_publish_real_redis():
    async def _test():
        mgr = RedisPubSubManager()
        evt = PubSubEvent("integration_test", {"check": True})
        result = await mgr.publish(Channels.BROADCAST, evt)
        assert result is True

    _run(_test())


# 22. subscriber receives published event via real Redis
def test_22_integration_subscribe_receive_real_redis():
    async def _test():
        received: list[PubSubEvent] = []

        async def handler(channel: str, event: PubSubEvent) -> None:
            received.append(event)

        channel = Channels.custom(f"test:{uuid.uuid4().hex[:8]}")
        mgr = RedisPubSubManager()

        ok = await mgr.start_listener([channel], handler)
        assert ok is True

        # Give the listener task a moment to establish the subscription.
        await asyncio.sleep(0.3)

        evt = PubSubEvent("round_trip", {"ping": 1})
        await mgr.publish(channel, evt)

        # Wait for the event to propagate (up to 2 s).
        for _ in range(20):
            await asyncio.sleep(0.1)
            if received:
                break

        await mgr.stop_listener()

        assert len(received) >= 1
        assert received[0].event_type == "round_trip"
        assert received[0].payload == {"ping": 1}

    _run(_test())


# 23. stop_listener() releases resources cleanly (integration)
def test_23_integration_stop_listener_clean():
    async def _test():
        mgr = RedisPubSubManager()

        async def noop(channel, event):
            pass

        await mgr.start_listener([Channels.BROADCAST], noop)
        assert mgr.is_running
        await mgr.stop_listener()
        assert not mgr.is_running
        assert mgr._sub_client is None
        assert mgr._pubsub is None

    _run(_test())


# 24. Frozen Phase 5.8.1/5.8.2 presence service is unaffected
def test_24_presence_service_unaffected():
    from app.services import presence_service as ps
    assert hasattr(ps, "register_session")
    assert hasattr(ps, "remove_session")
    assert hasattr(ps, "is_user_online")
    # The pubsub_manager must not touch any presence keys.
    from app.db.redis_client import redis_client
    presence_keys = redis_client.keys("careersphere:presence:*")
    assert presence_keys == []


# 25. No Pub/Sub symbols in presence_service.py
def test_25_no_pubsub_in_presence_service():
    import inspect
    import app.services.presence_service as mod
    src = inspect.getsource(mod).lower()
    assert "pubsub" not in src
    assert ".publish" not in src.lower()
    assert ".subscribe" not in src.lower()
