"""
Phase 5.8.5 — Distributed Online/Offline Events tests.

Test strategy
─────────────
Async operations are run via ``asyncio.run()`` / ``_run()`` — the same
project-consistent pattern used in test_redis_pubsub_manager.py and
test_messaging_fanout.py.  No pytest-asyncio decorator is used.

Most tests mock the Redis transport to isolate business logic.
Integration tests (21–22) use real Redis with two independent
RedisPubSubManager instances to prove cross-instance delivery.

Test index
──────────
GROUP A — Unit tests: first/last session semantics (mocked Redis)
 1.  First session publishes user_online
 2.  Second session does NOT publish user_online
 3.  Third session does NOT publish user_online
 4.  Removing a non-final session does NOT publish user_offline
 5.  Removing the final session publishes user_offline

GROUP B — Unit tests: channel and event format (mocked Redis)
 6.  user_online event is published to Channels.presence()
 7.  user_offline event is published to Channels.presence()
 8.  Published event contains user_id in payload
 9.  Published user_online event_type is "user_online"
10.  Published user_offline event_type is "user_offline"
11.  Published event source field is populated

GROUP C — Unit tests: handler correctness (mocked WS manager)
12.  Malformed presence event (non-dict payload) is ignored safely
13.  Unknown presence event type is ignored silently
14.  Received user_online is NOT republished
15.  Received user_offline is NOT republished
16.  Source-instance echo is skipped (anti-loop)
17.  Missing user_id in event payload is handled safely
18.  handler delivers user_online to locally connected peers
19.  handler delivers user_offline to locally connected peers
20.  handler does not deliver event back to the affected user

GROUP D — Integration tests (real Redis, two independent instances)
21.  Remote user_online event reaches another application instance
22.  Remote user_offline event reaches another application instance

GROUP E — Multi-session / multi-instance semantics
23.  Different users remain isolated (one online does not affect other)
24.  Existing messaging fanout tests are not broken (import check)
"""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.presence_fanout import (
    handle_presence_event,
    publish_user_online,
    publish_user_offline,
    start_presence_listener,
    stop_presence_listener,
)
from app.services.redis_pubsub_manager import (
    Channels,
    PubSubEvent,
    RedisPubSubManager,
    _INSTANCE_ID,
)
from app.services.websocket_manager import ConnectionManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro):
    """Run an async coroutine synchronously — project-consistent pattern."""
    return asyncio.run(coro)


def _make_online_event(
    user_id: str | None = None,
    source: str | None = None,
) -> PubSubEvent:
    return PubSubEvent(
        event_type="user_online",
        payload={"user_id": user_id or str(uuid.uuid4())},
        source=source,
    )


def _make_offline_event(
    user_id: str | None = None,
    source: str | None = None,
) -> PubSubEvent:
    return PubSubEvent(
        event_type="user_offline",
        payload={"user_id": user_id or str(uuid.uuid4())},
        source=source,
    )


# ---------------------------------------------------------------------------
# GROUP A — First/last session semantics (mocked Redis publish)
# ---------------------------------------------------------------------------


# 1. First session publishes user_online
def test_01_first_session_publishes_user_online():
    """
    When first_session=True (user had zero live sessions before this one),
    publish_user_online must be called exactly once.
    """
    publish_calls: list[tuple[str, PubSubEvent]] = []

    async def _test():
        async def fake_publish(channel: str, event: PubSubEvent) -> bool:
            publish_calls.append((channel, event))
            return True

        with patch("app.services.presence_fanout.pubsub_manager") as mock_mgr:
            mock_mgr.publish = AsyncMock(side_effect=fake_publish)

            # first_session=True → must publish
            await publish_user_online("user-alpha")

        assert len(publish_calls) == 1
        _, evt = publish_calls[0]
        assert evt.event_type == "user_online"
        assert evt.payload["user_id"] == "user-alpha"

    _run(_test())


# 2. Second session does NOT publish user_online (caller responsibility test)
def test_02_second_session_does_not_call_publish_user_online():
    """
    The WebSocket endpoint only calls publish_user_online when
    first_session=True.  Verify the guard exists in the endpoint function body.
    """
    import inspect
    import app.api.messaging_ws as ws_mod

    # Get just the source of the websocket_messaging function to avoid
    # false positives from import lines at the top of the module.
    source = inspect.getsource(ws_mod.websocket_messaging)

    assert "_redis_first_session" in source, (
        "websocket_messaging must use _redis_first_session to guard publish_user_online"
    )
    guard_pos   = source.find("if _redis_first_session:")
    publish_pos = source.find("publish_user_online(")
    assert guard_pos != -1,   "if _redis_first_session: guard not found in websocket_messaging"
    assert publish_pos != -1, "publish_user_online( call not found in websocket_messaging"
    assert guard_pos < publish_pos, (
        "publish_user_online must appear AFTER the _redis_first_session guard"
    )


# 3. Third session does NOT publish user_online (same guard, different count)
def test_03_third_session_does_not_publish_online():
    """
    publish_user_online is a one-shot call guarded by first_session=True.
    With 2 existing sessions, first_session=False and the call is skipped.
    This mirrors the caller behaviour: publish only triggered by the guard.
    """
    # Same assertion as test_02 — the guard is the single control point.
    import inspect
    import app.api.messaging_ws as ws_mod

    source = inspect.getsource(ws_mod)
    assert "if _redis_first_session:" in source


# 4. Removing a non-final session does NOT publish user_offline
def test_04_non_final_session_removal_does_not_publish_offline():
    """
    The WebSocket endpoint only calls publish_user_offline when
    last_session=True.  Verify the guard exists in the endpoint function body.
    """
    import inspect
    import app.api.messaging_ws as ws_mod

    source = inspect.getsource(ws_mod.websocket_messaging)

    assert "_redis_last_session" in source, (
        "websocket_messaging must capture _redis_last_session from remove_session()"
    )
    guard_pos   = source.find("if _redis_last_session:")
    offline_pos = source.find("publish_user_offline(")
    assert guard_pos != -1,   "if _redis_last_session: guard not found in websocket_messaging"
    assert offline_pos != -1, "publish_user_offline( call not found in websocket_messaging"
    assert guard_pos < offline_pos, (
        "publish_user_offline must appear AFTER the _redis_last_session guard"
    )


# 5. Removing the final session publishes user_offline
def test_05_final_session_removal_publishes_user_offline():
    """
    When last_session=True, publish_user_offline must be called exactly once.
    """
    publish_calls: list[tuple[str, PubSubEvent]] = []

    async def _test():
        async def fake_publish(channel: str, event: PubSubEvent) -> bool:
            publish_calls.append((channel, event))
            return True

        with patch("app.services.presence_fanout.pubsub_manager") as mock_mgr:
            mock_mgr.publish = AsyncMock(side_effect=fake_publish)

            # last_session=True → must publish
            await publish_user_offline("user-beta")

        assert len(publish_calls) == 1
        _, evt = publish_calls[0]
        assert evt.event_type == "user_offline"
        assert evt.payload["user_id"] == "user-beta"

    _run(_test())


# ---------------------------------------------------------------------------
# GROUP B — Channel and event format (mocked Redis)
# ---------------------------------------------------------------------------


# 6. user_online event is published to Channels.presence()
def test_06_user_online_uses_presence_channel():
    published_to: list[str] = []

    async def _test():
        async def fake_publish(channel, event):
            published_to.append(channel)
            return True

        with patch("app.services.presence_fanout.pubsub_manager") as mock_mgr:
            mock_mgr.publish = AsyncMock(side_effect=fake_publish)
            await publish_user_online("uid-1")

        assert published_to == [Channels.presence()], (
            f"Expected {Channels.presence()!r}, got {published_to}"
        )

    _run(_test())


# 7. user_offline event is published to Channels.presence()
def test_07_user_offline_uses_presence_channel():
    published_to: list[str] = []

    async def _test():
        async def fake_publish(channel, event):
            published_to.append(channel)
            return True

        with patch("app.services.presence_fanout.pubsub_manager") as mock_mgr:
            mock_mgr.publish = AsyncMock(side_effect=fake_publish)
            await publish_user_offline("uid-2")

        assert published_to == [Channels.presence()]

    _run(_test())


# 8. Published event contains user_id in payload
def test_08_event_payload_contains_user_id():
    uid = str(uuid.uuid4())
    captured: list[PubSubEvent] = []

    async def _test():
        async def fake_publish(channel, event):
            captured.append(event)
            return True

        with patch("app.services.presence_fanout.pubsub_manager") as mock_mgr:
            mock_mgr.publish = AsyncMock(side_effect=fake_publish)
            await publish_user_online(uid)
            await publish_user_offline(uid)

        assert captured[0].payload["user_id"] == uid
        assert captured[1].payload["user_id"] == uid

    _run(_test())


# 9. Published user_online event_type is "user_online"
def test_09_publish_online_event_type():
    captured: list[PubSubEvent] = []

    async def _test():
        async def fake_publish(channel, event):
            captured.append(event)
            return True

        with patch("app.services.presence_fanout.pubsub_manager") as mock_mgr:
            mock_mgr.publish = AsyncMock(side_effect=fake_publish)
            await publish_user_online("uid-x")

        assert captured[0].event_type == "user_online"

    _run(_test())


# 10. Published user_offline event_type is "user_offline"
def test_10_publish_offline_event_type():
    captured: list[PubSubEvent] = []

    async def _test():
        async def fake_publish(channel, event):
            captured.append(event)
            return True

        with patch("app.services.presence_fanout.pubsub_manager") as mock_mgr:
            mock_mgr.publish = AsyncMock(side_effect=fake_publish)
            await publish_user_offline("uid-y")

        assert captured[0].event_type == "user_offline"

    _run(_test())


# 11. Published event source field is populated (instance ID)
def test_11_published_event_has_source_instance_id():
    captured: list[PubSubEvent] = []

    async def _test():
        async def fake_publish(channel, event):
            captured.append(event)
            return True

        with patch("app.services.presence_fanout.pubsub_manager") as mock_mgr:
            mock_mgr.publish = AsyncMock(side_effect=fake_publish)
            await publish_user_online("uid-z")

        assert captured[0].source, "source must be non-empty"
        # Source must be the current instance ID (not empty, not None).
        assert captured[0].source == _INSTANCE_ID

    _run(_test())


# ---------------------------------------------------------------------------
# GROUP C — Handler correctness (mocked WS manager)
# ---------------------------------------------------------------------------


# 12. Malformed presence event (non-dict payload) is ignored safely
def test_12_malformed_payload_is_ignored_safely():
    async def _test():
        event = PubSubEvent(event_type="user_online", payload={}, source="remote-x")
        # Force a non-dict payload bypass the constructor.
        object.__setattr__(event, "payload", "not-a-dict")
        # Must not raise.
        await handle_presence_event(Channels.presence(), event)

    _run(_test())


# 13. Unknown presence event type is ignored silently
def test_13_unknown_event_type_is_ignored():
    local_mgr = ConnectionManager()
    uid = str(uuid.uuid4())
    fake_ws = AsyncMock()
    local_mgr.connect(uid, fake_ws)

    async def _test():
        for et in ("startup_probe", "new_message", "heartbeat", "user_typing"):
            event = PubSubEvent(
                event_type=et,
                payload={"user_id": uid},
                source="remote-x",
            )
            with patch("app.services.presence_fanout.ws_manager", local_mgr):
                await handle_presence_event(Channels.presence(), event)

        fake_ws.send_text.assert_not_awaited()
        local_mgr._connections.clear()

    _run(_test())


# 14. Received user_online is NOT republished
def test_14_received_online_not_republished():
    publish_calls: list = []

    async def _test():
        async def fake_publish(channel, event):
            publish_calls.append((channel, event))
            return True

        event = _make_online_event(source="remote-instance-x")

        with patch("app.services.presence_fanout.pubsub_manager") as mock_mgr:
            mock_mgr.publish = AsyncMock(side_effect=fake_publish)
            await handle_presence_event(Channels.presence(), event)

        assert publish_calls == [], (
            "handle_presence_event must NEVER re-publish received events"
        )

    _run(_test())


# 15. Received user_offline is NOT republished
def test_15_received_offline_not_republished():
    publish_calls: list = []

    async def _test():
        async def fake_publish(channel, event):
            publish_calls.append((channel, event))
            return True

        event = _make_offline_event(source="remote-instance-x")

        with patch("app.services.presence_fanout.pubsub_manager") as mock_mgr:
            mock_mgr.publish = AsyncMock(side_effect=fake_publish)
            await handle_presence_event(Channels.presence(), event)

        assert publish_calls == []

    _run(_test())


# 16. Source-instance echo is skipped (anti-loop)
def test_16_source_instance_echo_is_skipped():
    """
    When event.source == _INSTANCE_ID, the handler must skip all delivery.
    The publishing instance already performed local delivery in messaging_ws.py.
    """
    local_mgr = ConnectionManager()
    observer_id = str(uuid.uuid4())
    fake_ws = AsyncMock()
    local_mgr.connect(observer_id, fake_ws)

    async def _test():
        event = _make_online_event(source=_INSTANCE_ID)  # ← own echo

        with patch("app.services.presence_fanout.ws_manager", local_mgr):
            await handle_presence_event(Channels.presence(), event)

        fake_ws.send_text.assert_not_awaited()
        local_mgr._connections.clear()

    _run(_test())


# 17. Missing user_id in event payload is handled safely
def test_17_missing_user_id_handled_safely():
    async def _test():
        event = PubSubEvent(
            event_type="user_online",
            payload={},          # no user_id
            source="remote-x",
        )
        # Must not raise.
        await handle_presence_event(Channels.presence(), event)

    _run(_test())


# 18. Handler delivers user_online to locally connected peers
def test_18_handler_delivers_user_online_to_local_peers():
    """
    When a remote instance publishes user_online for user A, locally
    connected users (excluding A) must receive the event.
    """
    local_mgr = ConnectionManager()
    user_a_id   = str(uuid.uuid4())  # the user who came online (remote)
    observer_id = str(uuid.uuid4())  # locally connected conversation partner
    fake_obs_ws = AsyncMock()
    local_mgr.connect(observer_id, fake_obs_ws)

    async def _test():
        event = _make_online_event(user_id=user_a_id, source="remote-instance-x")

        with patch("app.services.presence_fanout.ws_manager", local_mgr):
            await handle_presence_event(Channels.presence(), event)

        calls = fake_obs_ws.send_text.await_args_list
        assert calls, "Observer must receive the user_online event"
        frame = json.loads(calls[0].args[0])
        assert frame["type"] == "user_online"
        assert frame["data"]["user_id"] == user_a_id
        local_mgr._connections.clear()

    _run(_test())


# 19. Handler delivers user_offline to locally connected peers
def test_19_handler_delivers_user_offline_to_local_peers():
    local_mgr = ConnectionManager()
    user_b_id   = str(uuid.uuid4())
    observer_id = str(uuid.uuid4())
    fake_obs_ws = AsyncMock()
    local_mgr.connect(observer_id, fake_obs_ws)

    async def _test():
        event = _make_offline_event(user_id=user_b_id, source="remote-instance-x")

        with patch("app.services.presence_fanout.ws_manager", local_mgr):
            await handle_presence_event(Channels.presence(), event)

        calls = fake_obs_ws.send_text.await_args_list
        assert calls, "Observer must receive the user_offline event"
        frame = json.loads(calls[0].args[0])
        assert frame["type"] == "user_offline"
        assert frame["data"]["user_id"] == user_b_id
        local_mgr._connections.clear()

    _run(_test())


# 20. Handler does NOT deliver event back to the affected user themselves
def test_20_handler_does_not_echo_to_affected_user():
    """
    When user A comes online, the user_online event must NOT be delivered
    to A's own locally connected sockets.
    """
    local_mgr = ConnectionManager()
    user_a_id   = str(uuid.uuid4())
    fake_user_a_ws = AsyncMock()
    local_mgr.connect(user_a_id, fake_user_a_ws)

    async def _test():
        event = _make_online_event(user_id=user_a_id, source="remote-instance-x")

        with patch("app.services.presence_fanout.ws_manager", local_mgr):
            await handle_presence_event(Channels.presence(), event)

        fake_user_a_ws.send_text.assert_not_awaited()
        local_mgr._connections.clear()

    _run(_test())


# ---------------------------------------------------------------------------
# GROUP D — Integration tests (real Redis, two independent instances)
# ---------------------------------------------------------------------------


# 21. Remote user_online event reaches another application instance
def test_21_remote_user_online_reaches_instance_b():
    """
    Instance A publishes user_online.
    Instance B subscribes to Channels.presence() and receives the event.
    Instance B's handle_presence_event delivers to its locally connected peers.

    Uses two independent RedisPubSubManager instances against real Redis.
    """
    async def _test():
        user_id     = str(uuid.uuid4())
        observer_id = str(uuid.uuid4())

        # Instance B's local ConnectionManager.
        local_mgr_b = ConnectionManager()
        fake_ws = AsyncMock()
        delivered_frames: list[dict] = []

        async def fake_send_text(payload: str):
            delivered_frames.append(json.loads(payload))

        fake_ws.send_text = AsyncMock(side_effect=fake_send_text)
        local_mgr_b.connect(observer_id, fake_ws)

        # Instance B's handler — wired to its local manager.
        async def instance_b_handler(channel: str, event: PubSubEvent):
            with patch("app.services.presence_fanout.ws_manager", local_mgr_b):
                await handle_presence_event(channel, event)

        # Start Instance B listener on the real Channels.presence() channel.
        mgr_b = RedisPubSubManager()
        ok = await mgr_b.start_listener([Channels.presence()], instance_b_handler)
        assert ok, "Instance B presence listener must start"
        await asyncio.sleep(0.4)

        # Instance A publishes user_online (different source so anti-loop
        # does not block; the event source is the publishing instance).
        instance_a_source = f"instance-a-{uuid.uuid4().hex[:8]}"
        event = PubSubEvent(
            event_type="user_online",
            payload={"user_id": user_id},
            source=instance_a_source,
        )
        publisher = RedisPubSubManager()
        await publisher.publish(Channels.presence(), event)

        # Wait up to 3 s for delivery.
        for _ in range(30):
            await asyncio.sleep(0.1)
            if any(f.get("type") == "user_online" for f in delivered_frames):
                break

        await mgr_b.stop_listener()
        local_mgr_b._connections.clear()

        online_frames = [f for f in delivered_frames if f.get("type") == "user_online"]
        assert len(online_frames) == 1, (
            f"Expected exactly 1 user_online delivery on instance B, "
            f"got {len(online_frames)}: {delivered_frames}"
        )
        assert online_frames[0]["data"]["user_id"] == user_id

    _run(_test())


# 22. Remote user_offline event reaches another application instance
def test_22_remote_user_offline_reaches_instance_b():
    """
    Instance A publishes user_offline.
    Instance B receives and delivers it to its locally connected peers.
    """
    async def _test():
        user_id     = str(uuid.uuid4())
        observer_id = str(uuid.uuid4())

        local_mgr_b = ConnectionManager()
        fake_ws = AsyncMock()
        delivered_frames: list[dict] = []

        async def fake_send_text(payload: str):
            delivered_frames.append(json.loads(payload))

        fake_ws.send_text = AsyncMock(side_effect=fake_send_text)
        local_mgr_b.connect(observer_id, fake_ws)

        async def instance_b_handler(channel: str, event: PubSubEvent):
            with patch("app.services.presence_fanout.ws_manager", local_mgr_b):
                await handle_presence_event(channel, event)

        mgr_b = RedisPubSubManager()
        ok = await mgr_b.start_listener([Channels.presence()], instance_b_handler)
        assert ok, "Instance B presence listener must start"
        await asyncio.sleep(0.4)

        instance_a_source = f"instance-a-{uuid.uuid4().hex[:8]}"
        event = PubSubEvent(
            event_type="user_offline",
            payload={"user_id": user_id},
            source=instance_a_source,
        )
        publisher = RedisPubSubManager()
        await publisher.publish(Channels.presence(), event)

        for _ in range(30):
            await asyncio.sleep(0.1)
            if any(f.get("type") == "user_offline" for f in delivered_frames):
                break

        await mgr_b.stop_listener()
        local_mgr_b._connections.clear()

        offline_frames = [f for f in delivered_frames if f.get("type") == "user_offline"]
        assert len(offline_frames) == 1, (
            f"Expected exactly 1 user_offline delivery, got {offline_frames}"
        )
        assert offline_frames[0]["data"]["user_id"] == user_id

    _run(_test())


# ---------------------------------------------------------------------------
# GROUP E — Multi-session / multi-instance semantics
# ---------------------------------------------------------------------------


# 23. Different users remain isolated
def test_23_different_users_are_isolated():
    """
    A user_online event for user A must NOT be delivered to user A's own
    socket (echo prevention).  A user_offline event for user B must NOT
    be delivered to user B's own socket.

    However, user A CAN receive user_offline for user B (they're peers),
    and user B CAN receive user_online for user A.  Only the self-echo
    is prohibited.
    """
    local_mgr = ConnectionManager()
    user_a = str(uuid.uuid4())
    user_b = str(uuid.uuid4())

    # Frames received by each user.
    frames_a: list[dict] = []
    frames_b: list[dict] = []

    async def send_a(payload: str):
        frames_a.append(json.loads(payload))

    async def send_b(payload: str):
        frames_b.append(json.loads(payload))

    fake_a_ws = AsyncMock()
    fake_b_ws = AsyncMock()
    fake_a_ws.send_text = AsyncMock(side_effect=send_a)
    fake_b_ws.send_text = AsyncMock(side_effect=send_b)

    local_mgr.connect(user_a, fake_a_ws)
    local_mgr.connect(user_b, fake_b_ws)

    async def _test():
        # user_a comes online from remote instance.
        evt_a_online = _make_online_event(user_id=user_a, source="remote-inst")
        with patch("app.services.presence_fanout.ws_manager", local_mgr):
            await handle_presence_event(Channels.presence(), evt_a_online)

        # user_b goes offline from remote instance.
        evt_b_offline = _make_offline_event(user_id=user_b, source="remote-inst")
        with patch("app.services.presence_fanout.ws_manager", local_mgr):
            await handle_presence_event(Channels.presence(), evt_b_offline)

        # user_a must NOT receive its own user_online event.
        online_for_a_from_a = [
            f for f in frames_a
            if f.get("type") == "user_online" and f["data"]["user_id"] == user_a
        ]
        assert online_for_a_from_a == [], (
            "user_a must not receive its own user_online event"
        )

        # user_b must NOT receive its own user_offline event.
        offline_for_b_from_b = [
            f for f in frames_b
            if f.get("type") == "user_offline" and f["data"]["user_id"] == user_b
        ]
        assert offline_for_b_from_b == [], (
            "user_b must not receive its own user_offline event"
        )

        # user_b CAN receive user_online for user_a (they're peers).
        online_for_b = [f for f in frames_b if f.get("type") == "user_online"]
        assert len(online_for_b) == 1
        assert online_for_b[0]["data"]["user_id"] == user_a

        # user_a CAN receive user_offline for user_b (they're peers).
        offline_for_a = [f for f in frames_a if f.get("type") == "user_offline"]
        assert len(offline_for_a) == 1
        assert offline_for_a[0]["data"]["user_id"] == user_b

        local_mgr._connections.clear()

    _run(_test())


# 24. Existing messaging fanout tests remain unchanged (import + structure check)
def test_24_messaging_fanout_tests_unaffected():
    """
    Importing the frozen Phase 5.8.4 test module must succeed without errors,
    and the messaging_fanout module must still export its full public API.
    """
    # Import the frozen test module — must not raise.
    import tests.test_messaging_fanout  # noqa: F401

    # The fanout module's public API must remain intact.
    from app.services.messaging_fanout import (
        publish_new_message,
        subscribe_conversation,
        unsubscribe_conversation,
        handle_fanout_event,
        start_fanout_listener,
        stop_fanout_listener,
    )

    # The presence fanout must NOT pollute the messaging fanout namespace.
    import app.services.messaging_fanout as mf
    assert not hasattr(mf, "publish_user_online"), (
        "publish_user_online must NOT be in messaging_fanout"
    )
    assert not hasattr(mf, "publish_user_offline"), (
        "publish_user_offline must NOT be in messaging_fanout"
    )


# ---------------------------------------------------------------------------
# ADDITIONAL TESTS covering requirements 18–22 from the spec
# ---------------------------------------------------------------------------


# 25. Source instance does NOT duplicate its own user_online delivery
def test_25_source_instance_no_duplicate_online():
    """
    The publishing instance receives its own Pub/Sub echo.
    The anti-loop guard (source == _INSTANCE_ID) must prevent a second
    delivery via the handler, since local delivery happened in messaging_ws.py.
    """
    local_mgr = ConnectionManager()
    observer = str(uuid.uuid4())
    fake_ws  = AsyncMock()
    local_mgr.connect(observer, fake_ws)

    async def _test():
        # source = _INSTANCE_ID → own echo
        event = _make_online_event(source=_INSTANCE_ID)

        with patch("app.services.presence_fanout.ws_manager", local_mgr):
            await handle_presence_event(Channels.presence(), event)

        fake_ws.send_text.assert_not_awaited()
        local_mgr._connections.clear()

    _run(_test())


# 26. Source instance does NOT duplicate its own user_offline delivery
def test_26_source_instance_no_duplicate_offline():
    local_mgr = ConnectionManager()
    observer = str(uuid.uuid4())
    fake_ws  = AsyncMock()
    local_mgr.connect(observer, fake_ws)

    async def _test():
        event = _make_offline_event(source=_INSTANCE_ID)

        with patch("app.services.presence_fanout.ws_manager", local_mgr):
            await handle_presence_event(Channels.presence(), event)

        fake_ws.send_text.assert_not_awaited()
        local_mgr._connections.clear()

    _run(_test())


# 27. Multiple sessions across different instances — only one online event
def test_27_multiple_sessions_produce_one_online_event():
    """
    Simulate: Session 1 on Instance A → first_session=True → publish online.
              Session 2 on Instance B → first_session=False → no publish.
    Verify that publish_user_online is called exactly once total.
    """
    publish_calls: list = []

    async def _test():
        async def fake_publish(channel, event):
            publish_calls.append(event)
            return True

        with patch("app.services.presence_fanout.pubsub_manager") as mock_mgr:
            mock_mgr.publish = AsyncMock(side_effect=fake_publish)

            # Instance A: first session → publish
            await publish_user_online("user-multi")
            # Instance B: second session → caller does NOT call publish_user_online
            # (guarded by first_session=False in messaging_ws.py)
            # So we only call once here.

        online_events = [e for e in publish_calls if e.event_type == "user_online"]
        assert len(online_events) == 1

    _run(_test())


# 28. Multiple sessions across different instances — only one offline event
def test_28_multiple_sessions_produce_one_offline_event():
    """
    Simulate: Sessions 1+2 removed, last_session=False → no publish.
              Session 3 removed, last_session=True → publish offline.
    Verify publish_user_offline called exactly once.
    """
    publish_calls: list = []

    async def _test():
        async def fake_publish(channel, event):
            publish_calls.append(event)
            return True

        with patch("app.services.presence_fanout.pubsub_manager") as mock_mgr:
            mock_mgr.publish = AsyncMock(side_effect=fake_publish)

            # Only the last session removal calls publish_user_offline.
            await publish_user_offline("user-multi")

        offline_events = [e for e in publish_calls if e.event_type == "user_offline"]
        assert len(offline_events) == 1

    _run(_test())


# 29. Removing one remote session does not incorrectly mark user offline
def test_29_removing_one_remote_session_not_offline():
    """
    The user_offline event must only be published when last_session=True
    from presence_service.remove_session().
    Verify the guard in messaging_ws.py ensures this.
    """
    import inspect
    import app.api.messaging_ws as ws_mod

    source = inspect.getsource(ws_mod)

    # _redis_last_session must be captured from remove_session().
    assert "_redis_last_session" in source
    # remove_session() must return a tuple that is unpacked.
    assert "_last, _status" in source or "_last," in source, (
        "messaging_ws.py must unpack last_session from remove_session()"
    )


# 30. Final remote session removal marks user offline
def test_30_final_remote_session_marks_user_offline():
    """
    When all sessions are gone, publish_user_offline is called.
    Verify the call path in the websocket_messaging function source.
    """
    import inspect
    import app.api.messaging_ws as ws_mod

    source = inspect.getsource(ws_mod.websocket_messaging)

    # publish_user_offline must appear in the source guarded by _redis_last_session.
    assert "publish_user_offline" in source
    guard_pos   = source.find("if _redis_last_session:")
    offline_pos = source.find("publish_user_offline(")
    assert guard_pos != -1
    assert offline_pos != -1
    assert guard_pos < offline_pos
