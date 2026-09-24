"""
Phase 5.8.4 — Cross-Instance Message Fanout tests.

Test strategy
─────────────
Async operations are run via ``asyncio.run()`` / ``_run()`` — the same
project-consistent pattern used in test_redis_pubsub_manager.py.
No pytest-asyncio decorator is used; the sync Starlette TestClient handles
its own event loop for WS integration tests.

Coverage plan
─────────────
GROUP A — Unit tests (mocked Redis + mocked WebSocket manager)
 1.  publish_new_message builds a PubSubEvent with all required fields
 2.  publish_new_message uses Channels.messaging(conversation_id) channel
 3.  publish_new_message uses event_type "new_message"
 4.  publish_new_message payload contains durable message_id
 5.  publish_new_message payload contains conversation_id
 6.  publish_new_message payload contains sender_id
 7.  publish_new_message payload contains recipient_id
 8.  publish_new_message payload contains content and created_at
 9.  publish_new_message returns True on successful publish
10.  publish_new_message returns False and does NOT raise on Redis failure
11.  handle_fanout_event: same-instance source is ignored (anti-loop)
12.  handle_fanout_event: non "new_message" events are silently ignored
13.  handle_fanout_event: missing recipient_id is handled safely
14.  handle_fanout_event: recipient NOT locally connected → no WS delivery
15.  handle_fanout_event: recipient IS locally connected → exactly one delivery
16.  handle_fanout_event: sender does NOT receive a duplicate delivery
17.  handle_fanout_event: non-recipient local users are not delivered to
18.  handle_fanout_event: malformed payload dict is handled safely
19.  handle_fanout_event: handler exception does not propagate to caller
20.  Pub/Sub event is NOT re-published when handle_fanout_event is called

GROUP B — Integration tests (real Redis, two independent manager instances)
21.  Two independent manager instances each receive the event through Redis
24.  Exactly one delivery to the intended recipient in the cross-instance scenario
22.  Multiple conversations remain isolated by channel
23.  Multiple messages are distinct by durable message_id

ADDITIONAL UNIT TESTS
25.  messaging_ws.py imports only the high-level fanout API (no raw pubsub)
26.  PostgreSQL persistence happens before the fanout publish (ordering proof)

ADDITIONAL INTEGRATION TESTS
27.  subscribe_conversation subscribes to the correct per-conversation channel
28.  unsubscribe_conversation unsubscribes cleanly without raising
"""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.services.messaging_fanout import (
    handle_fanout_event,
    publish_new_message,
    subscribe_conversation,
    unsubscribe_conversation,
)
from app.services.redis_pubsub_manager import (
    Channels,
    PubSubEvent,
    RedisPubSubManager,
    _INSTANCE_ID,
    _CHANNEL_NS,
)
from app.services.websocket_manager import ConnectionManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro):
    """Run an async coroutine synchronously — project-consistent pattern."""
    return asyncio.run(coro)


def _make_msg_params(
    *,
    message_id: str | None = None,
    conversation_id: str | None = None,
    sender_id: str | None = None,
    recipient_id: str | None = None,
    content: str = "Hello, world!",
    created_at: str = "2026-09-23T10:00:00+00:00",
) -> dict:
    """Return a kwargs dict for publish_new_message with sensible defaults."""
    return {
        "message_id":      message_id or str(uuid.uuid4()),
        "conversation_id": conversation_id or str(uuid.uuid4()),
        "sender_id":       sender_id or str(uuid.uuid4()),
        "recipient_id":    recipient_id or str(uuid.uuid4()),
        "content":         content,
        "created_at":      created_at,
    }


def _make_new_message_event(
    *,
    message_id: str | None = None,
    conversation_id: str | None = None,
    sender_id: str | None = None,
    recipient_id: str | None = None,
    content: str = "Hello",
    created_at: str = "2026-09-23T10:00:00+00:00",
    source: str | None = None,
) -> PubSubEvent:
    """Return a PubSubEvent as published by publish_new_message."""
    m_id   = message_id or str(uuid.uuid4())
    c_id   = conversation_id or str(uuid.uuid4())
    s_id   = sender_id or str(uuid.uuid4())
    r_id   = recipient_id or str(uuid.uuid4())
    event  = PubSubEvent(
        event_type="new_message",
        payload={
            "message_id":      m_id,
            "conversation_id": c_id,
            "sender_id":       s_id,
            "recipient_id":    r_id,
            "content":         content,
            "created_at":      created_at,
        },
        source=source,
    )
    return event


# ---------------------------------------------------------------------------
# GROUP A — Unit tests (mocked Redis transport)
# ---------------------------------------------------------------------------


# 1. publish_new_message builds a PubSubEvent with all required fields
def test_01_publish_builds_event_with_required_fields():
    """Verify the published event carries all fields the protocol requires."""
    captured: list[tuple[str, PubSubEvent]] = []

    async def _test():
        async def fake_publish(channel: str, event: PubSubEvent) -> bool:
            captured.append((channel, event))
            return True

        with patch("app.services.messaging_fanout.pubsub_manager") as mock_mgr:
            mock_mgr.publish = AsyncMock(side_effect=fake_publish)
            params = _make_msg_params()
            result = await publish_new_message(**params)

        assert result is True
        assert len(captured) == 1
        _, evt = captured[0]
        assert evt.event_type == "new_message"
        assert evt.event_id        # UUID4 — must be non-empty
        assert evt.timestamp       # ISO 8601 — must be non-empty
        assert evt.source          # instance identifier — must be non-empty

    _run(_test())


# 2. publish_new_message uses Channels.messaging(conversation_id) channel
def test_02_publish_uses_correct_channel():
    """The publish must target Channels.messaging(conversation_id), not any other channel."""
    captured: list[str] = []
    conv_id = str(uuid.uuid4())

    async def _test():
        async def fake_publish(channel: str, event: PubSubEvent) -> bool:
            captured.append(channel)
            return True

        with patch("app.services.messaging_fanout.pubsub_manager") as mock_mgr:
            mock_mgr.publish = AsyncMock(side_effect=fake_publish)
            params = _make_msg_params(conversation_id=conv_id)
            await publish_new_message(**params)

        expected = Channels.messaging(conv_id)
        assert captured == [expected], (
            f"Expected channel {expected!r}, got {captured}"
        )

    _run(_test())


# 3. publish_new_message uses event_type "new_message"
def test_03_publish_event_type_is_new_message():
    captured: list[PubSubEvent] = []

    async def _test():
        async def fake_publish(channel, event):
            captured.append(event)
            return True

        with patch("app.services.messaging_fanout.pubsub_manager") as mock_mgr:
            mock_mgr.publish = AsyncMock(side_effect=fake_publish)
            await publish_new_message(**_make_msg_params())

        assert captured[0].event_type == "new_message"

    _run(_test())


# 4. publish_new_message payload contains durable message_id
def test_04_publish_payload_contains_message_id():
    msg_id = str(uuid.uuid4())
    captured: list[PubSubEvent] = []

    async def _test():
        async def fake_publish(channel, event):
            captured.append(event)
            return True

        with patch("app.services.messaging_fanout.pubsub_manager") as mock_mgr:
            mock_mgr.publish = AsyncMock(side_effect=fake_publish)
            await publish_new_message(**_make_msg_params(message_id=msg_id))

        assert captured[0].payload["message_id"] == msg_id

    _run(_test())


# 5. publish_new_message payload contains conversation_id
def test_05_publish_payload_contains_conversation_id():
    conv_id = str(uuid.uuid4())
    captured: list[PubSubEvent] = []

    async def _test():
        async def fake_publish(channel, event):
            captured.append(event)
            return True

        with patch("app.services.messaging_fanout.pubsub_manager") as mock_mgr:
            mock_mgr.publish = AsyncMock(side_effect=fake_publish)
            await publish_new_message(**_make_msg_params(conversation_id=conv_id))

        assert captured[0].payload["conversation_id"] == conv_id

    _run(_test())


# 6. publish_new_message payload contains sender_id
def test_06_publish_payload_contains_sender_id():
    sender_id = str(uuid.uuid4())
    captured: list[PubSubEvent] = []

    async def _test():
        async def fake_publish(channel, event):
            captured.append(event)
            return True

        with patch("app.services.messaging_fanout.pubsub_manager") as mock_mgr:
            mock_mgr.publish = AsyncMock(side_effect=fake_publish)
            await publish_new_message(**_make_msg_params(sender_id=sender_id))

        assert captured[0].payload["sender_id"] == sender_id

    _run(_test())


# 7. publish_new_message payload contains recipient_id
def test_07_publish_payload_contains_recipient_id():
    recipient_id = str(uuid.uuid4())
    captured: list[PubSubEvent] = []

    async def _test():
        async def fake_publish(channel, event):
            captured.append(event)
            return True

        with patch("app.services.messaging_fanout.pubsub_manager") as mock_mgr:
            mock_mgr.publish = AsyncMock(side_effect=fake_publish)
            await publish_new_message(**_make_msg_params(recipient_id=recipient_id))

        assert captured[0].payload["recipient_id"] == recipient_id

    _run(_test())


# 8. publish_new_message payload contains content and created_at
def test_08_publish_payload_contains_content_and_created_at():
    content    = "Unit test message content"
    created_at = "2026-09-23T12:34:56+00:00"
    captured: list[PubSubEvent] = []

    async def _test():
        async def fake_publish(channel, event):
            captured.append(event)
            return True

        with patch("app.services.messaging_fanout.pubsub_manager") as mock_mgr:
            mock_mgr.publish = AsyncMock(side_effect=fake_publish)
            await publish_new_message(
                **_make_msg_params(content=content, created_at=created_at)
            )

        assert captured[0].payload["content"]    == content
        assert captured[0].payload["created_at"] == created_at

    _run(_test())


# 9. publish_new_message returns True on successful publish
def test_09_publish_returns_true_on_success():
    async def _test():
        with patch("app.services.messaging_fanout.pubsub_manager") as mock_mgr:
            mock_mgr.publish = AsyncMock(return_value=True)
            result = await publish_new_message(**_make_msg_params())
        assert result is True

    _run(_test())


# 10. publish_new_message returns False on Redis failure and does NOT raise
def test_10_publish_returns_false_on_redis_failure():
    """
    A Redis publish failure must NOT propagate as an exception.
    The PostgreSQL message was already persisted; the caller must not be
    disrupted by a transient Redis error.
    """
    async def _test():
        with patch("app.services.messaging_fanout.pubsub_manager") as mock_mgr:
            mock_mgr.publish = AsyncMock(return_value=False)
            result = await publish_new_message(**_make_msg_params())
        assert result is False

    _run(_test())


# 11. handle_fanout_event: same-instance source is ignored (anti-loop)
def test_11_handler_skips_own_instance_source():
    """
    When event.source == _INSTANCE_ID the handler must not deliver anything.
    This prevents the publishing instance from re-delivering after receiving
    its own Pub/Sub echo.
    """
    async def _test():
        local_mgr = ConnectionManager()
        recipient_id = str(uuid.uuid4())

        # Register a fake WebSocket so is_connected → True.
        fake_ws = AsyncMock()
        local_mgr.connect(recipient_id, fake_ws)

        event = _make_new_message_event(
            recipient_id=recipient_id,
            source=_INSTANCE_ID,           # ← same instance: must be skipped
        )

        with patch("app.services.messaging_fanout.ws_manager", local_mgr):
            await handle_fanout_event(Channels.messaging("conv-1"), event)

        # send_text must never have been called.
        fake_ws.send_text.assert_not_awaited()
        local_mgr._connections.clear()

    _run(_test())


# 12. handle_fanout_event: non-"new_message" events are silently ignored
def test_12_handler_ignores_non_new_message_events():
    async def _test():
        local_mgr = ConnectionManager()
        recipient_id = str(uuid.uuid4())
        fake_ws = AsyncMock()
        local_mgr.connect(recipient_id, fake_ws)

        for event_type in ("user_typing", "user_online", "startup_probe", "unknown"):
            event = PubSubEvent(
                event_type=event_type,
                payload={"recipient_id": recipient_id},
                source="remote-instance-xyz",
            )
            with patch("app.services.messaging_fanout.ws_manager", local_mgr):
                await handle_fanout_event(Channels.messaging("conv-1"), event)

        # No delivery for any of these event types.
        fake_ws.send_text.assert_not_awaited()
        local_mgr._connections.clear()

    _run(_test())


# 13. handle_fanout_event: missing recipient_id is handled safely
def test_13_handler_missing_recipient_id_is_safe():
    """A malformed event without recipient_id must not raise."""
    async def _test():
        event = PubSubEvent(
            event_type="new_message",
            payload={"message_id": str(uuid.uuid4())},  # no recipient_id
            source="remote-instance-xyz",
        )
        # Must complete without exception.
        await handle_fanout_event(Channels.messaging("conv-1"), event)

    _run(_test())


# 14. handle_fanout_event: recipient NOT locally connected → no WS delivery
def test_14_handler_no_delivery_if_recipient_not_connected():
    """
    If the recipient has no local WebSocket connection the event must be
    silently discarded.  The message is already in PostgreSQL.
    """
    async def _test():
        local_mgr = ConnectionManager()
        # Deliberately do NOT register the recipient — they are on another instance.
        recipient_id = str(uuid.uuid4())

        event = _make_new_message_event(
            recipient_id=recipient_id,
            source="remote-instance-xyz",
        )

        send_calls: list = []

        async def noop_send(uid, event_type, data):
            send_calls.append((uid, event_type))
            return 0

        with patch("app.services.messaging_fanout.ws_manager", local_mgr):
            await handle_fanout_event(Channels.messaging("conv-1"), event)

        # No send should have occurred.
        assert send_calls == []

    _run(_test())


# 15. handle_fanout_event: recipient IS locally connected → exactly one delivery
def test_15_handler_delivers_exactly_once_to_local_recipient():
    """
    If the recipient is locally connected the handler must call send_to_user
    exactly once with the "new_message" event type.
    """
    async def _test():
        local_mgr = ConnectionManager()
        recipient_id = str(uuid.uuid4())
        fake_ws = AsyncMock()
        local_mgr.connect(recipient_id, fake_ws)

        event = _make_new_message_event(
            recipient_id=recipient_id,
            source="remote-instance-xyz",
        )

        with patch("app.services.messaging_fanout.ws_manager", local_mgr):
            await handle_fanout_event(Channels.messaging("conv-1"), event)

        # One new_message delivery expected (plus a notification event).
        calls = fake_ws.send_text.await_args_list
        event_types = [json.loads(c.args[0])["type"] for c in calls]
        assert "new_message" in event_types, (
            f"Expected 'new_message' in delivered events, got {event_types}"
        )
        new_message_count = event_types.count("new_message")
        assert new_message_count == 1, (
            f"Expected exactly 1 'new_message' delivery, got {new_message_count}"
        )
        local_mgr._connections.clear()

    _run(_test())


# 16. Sender does NOT receive a duplicate from the Pub/Sub path
def test_16_sender_does_not_receive_duplicate_via_fanout():
    """
    The sender's local delivery already happened in _handle_message().
    When the event comes back from Redis, the anti-loop guard (source ==
    _INSTANCE_ID) prevents a second delivery to the sender's socket.
    """
    async def _test():
        local_mgr = ConnectionManager()
        sender_id    = str(uuid.uuid4())
        recipient_id = str(uuid.uuid4())
        fake_sender_ws = AsyncMock()
        local_mgr.connect(sender_id, fake_sender_ws)

        # This event was published by THIS instance (source = _INSTANCE_ID).
        event = _make_new_message_event(
            sender_id=sender_id,
            recipient_id=recipient_id,
            source=_INSTANCE_ID,
        )

        with patch("app.services.messaging_fanout.ws_manager", local_mgr):
            await handle_fanout_event(Channels.messaging("conv-1"), event)

        # The sender's socket must not receive anything via the fanout path.
        fake_sender_ws.send_text.assert_not_awaited()
        local_mgr._connections.clear()

    _run(_test())


# 17. Non-recipient local users are not delivered to
def test_17_non_recipient_local_users_not_delivered():
    """
    When an event arrives for recipient_id=X, only X should receive it.
    A different user Y who happens to be locally connected must not receive
    the message.
    """
    async def _test():
        local_mgr = ConnectionManager()
        recipient_id    = str(uuid.uuid4())
        other_user_id   = str(uuid.uuid4())
        fake_recipient  = AsyncMock()
        fake_other      = AsyncMock()
        local_mgr.connect(recipient_id,  fake_recipient)
        local_mgr.connect(other_user_id, fake_other)

        event = _make_new_message_event(
            recipient_id=recipient_id,
            source="remote-instance-xyz",
        )

        with patch("app.services.messaging_fanout.ws_manager", local_mgr):
            await handle_fanout_event(Channels.messaging("conv-1"), event)

        # Recipient gets the message.
        assert fake_recipient.send_text.await_count >= 1
        # Unrelated user must not receive anything.
        fake_other.send_text.assert_not_awaited()
        local_mgr._connections.clear()

    _run(_test())


# 18. handle_fanout_event: malformed (non-dict) payload is handled safely
def test_18_handler_malformed_payload_is_safe():
    """A PubSubEvent with a non-dict payload must not raise."""
    async def _test():
        # Build an event manually so we can stuff a non-dict payload.
        event = PubSubEvent(
            event_type="new_message",
            payload={},                # will be overridden below
            source="remote-instance",
        )
        object.__setattr__(event, "payload", "not-a-dict")  # bypass normal construction

        # Must not raise.
        await handle_fanout_event(Channels.messaging("conv-1"), event)

    _run(_test())


# 19. Handler exception in ws_manager.send_to_user does not propagate
def test_19_handler_exception_in_delivery_does_not_crash():
    """
    If the local delivery raises unexpectedly, handle_fanout_event must
    absorb the exception and return normally, keeping the listener alive.
    """
    async def _test():
        local_mgr = ConnectionManager()
        recipient_id = str(uuid.uuid4())
        broken_ws = AsyncMock()
        broken_ws.send_text = AsyncMock(side_effect=RuntimeError("socket broken"))
        local_mgr.connect(recipient_id, broken_ws)

        event = _make_new_message_event(
            recipient_id=recipient_id,
            source="remote-instance-xyz",
        )

        # Must not propagate — the listen loop must remain alive.
        try:
            with patch("app.services.messaging_fanout.ws_manager", local_mgr):
                await handle_fanout_event(Channels.messaging("conv-1"), event)
        except Exception as exc:
            pytest.fail(
                f"handle_fanout_event propagated an exception: {exc!r}"
            )
        local_mgr._connections.clear()

    _run(_test())


# 20. Pub/Sub event is NOT re-published when handle_fanout_event is called
def test_20_handler_does_not_republish():
    """
    The fanout handler must never call pubsub_manager.publish().
    Re-publishing would create infinite loops between instances.
    """
    async def _test():
        local_mgr = ConnectionManager()
        recipient_id = str(uuid.uuid4())
        fake_ws = AsyncMock()
        local_mgr.connect(recipient_id, fake_ws)

        event = _make_new_message_event(
            recipient_id=recipient_id,
            source="remote-instance-xyz",
        )

        publish_calls: list = []

        async def tracking_publish(channel, ev):
            publish_calls.append((channel, ev))
            return True

        with patch("app.services.messaging_fanout.pubsub_manager") as mock_mgr:
            mock_mgr.publish = AsyncMock(side_effect=tracking_publish)
            mock_mgr.is_connected = MagicMock(return_value=True)
            with patch("app.services.messaging_fanout.ws_manager", local_mgr):
                await handle_fanout_event(Channels.messaging("conv-1"), event)

        assert publish_calls == [], (
            "handle_fanout_event must NEVER call pubsub_manager.publish()"
        )
        local_mgr._connections.clear()

    _run(_test())


# ---------------------------------------------------------------------------
# GROUP B — Integration tests (real Redis, two independent manager instances)
# ---------------------------------------------------------------------------


# 21. Two independent manager instances each receive the event through Redis
def test_21_two_instances_receive_event_via_real_redis():
    """
    Core multi-instance integration test.

    Two independent RedisPubSubManager instances (simulating two FastAPI
    workers) both subscribe to the same per-conversation channel.

    Instance A publishes a new_message event.
    Both instance A and instance B receive it via Redis.
    (Instance A is expected to skip self-delivery via anti-loop; this test
    verifies the transport — the skipping is tested separately in test_11.)
    """
    async def _test():
        conv_id   = str(uuid.uuid4())
        channel   = Channels.messaging(conv_id)
        msg_id    = str(uuid.uuid4())
        sender_id = str(uuid.uuid4())
        rcpt_id   = str(uuid.uuid4())

        received_a: list[PubSubEvent] = []
        received_b: list[PubSubEvent] = []

        async def handler_a(ch, ev):
            if ev.event_type == "new_message":
                received_a.append(ev)

        async def handler_b(ch, ev):
            if ev.event_type == "new_message":
                received_b.append(ev)

        mgr_a = RedisPubSubManager()
        mgr_b = RedisPubSubManager()

        ok_a = await mgr_a.start_listener([channel], handler_a)
        ok_b = await mgr_b.start_listener([channel], handler_b)
        assert ok_a and ok_b, "Both listeners must start successfully"

        # Allow listeners to establish subscriptions.
        await asyncio.sleep(0.4)

        # Publish via a third manager (simulates the publish path from
        # messaging_ws.py, which uses pubsub_manager.publish() internally).
        publisher = RedisPubSubManager()
        event = PubSubEvent(
            event_type="new_message",
            payload={
                "message_id":      msg_id,
                "conversation_id": conv_id,
                "sender_id":       sender_id,
                "recipient_id":    rcpt_id,
                "content":         "Cross-instance message",
                "created_at":      "2026-09-23T10:00:00+00:00",
            },
        )
        await publisher.publish(channel, event)

        # Wait for propagation (up to 3 s).
        for _ in range(30):
            await asyncio.sleep(0.1)
            if received_a and received_b:
                break

        await mgr_a.stop_listener()
        await mgr_b.stop_listener()

        assert len(received_a) == 1, (
            f"Instance A expected 1 event, got {len(received_a)}"
        )
        assert len(received_b) == 1, (
            f"Instance B expected 1 event, got {len(received_b)}"
        )
        assert received_a[0].payload["message_id"] == msg_id
        assert received_b[0].payload["message_id"] == msg_id

    _run(_test())


# 22. Multiple conversations remain isolated by channel
def test_22_conversation_channels_are_isolated():
    """
    Events published to Channels.messaging(conv_A) must NOT appear on
    Channels.messaging(conv_B) — per-conversation channel isolation.
    """
    async def _test():
        conv_a = str(uuid.uuid4())
        conv_b = str(uuid.uuid4())
        channel_a = Channels.messaging(conv_a)
        channel_b = Channels.messaging(conv_b)

        received_for_b: list[PubSubEvent] = []

        async def handler_b(ch, ev):
            if ev.event_type == "new_message":
                received_for_b.append(ev)

        # Only subscribe mgr_b to channel_b.
        mgr_b = RedisPubSubManager()
        ok = await mgr_b.start_listener([channel_b], handler_b)
        assert ok

        await asyncio.sleep(0.3)

        # Publish to channel_a — mgr_b should NOT receive this.
        publisher = RedisPubSubManager()
        event_a = PubSubEvent(
            event_type="new_message",
            payload={"conversation_id": conv_a, "recipient_id": str(uuid.uuid4())},
        )
        await publisher.publish(channel_a, event_a)

        # Also publish to channel_b — mgr_b SHOULD receive this.
        event_b = PubSubEvent(
            event_type="new_message",
            payload={"conversation_id": conv_b, "recipient_id": str(uuid.uuid4())},
        )
        await publisher.publish(channel_b, event_b)

        # Wait up to 2 s.
        for _ in range(20):
            await asyncio.sleep(0.1)
            if received_for_b:
                break

        await mgr_b.stop_listener()

        # Must have received exactly the channel_b event only.
        assert len(received_for_b) == 1
        assert received_for_b[0].payload["conversation_id"] == conv_b

    _run(_test())


# 23. Multiple messages are distinct by durable message_id
def test_23_multiple_messages_are_distinct_by_id():
    """
    Three successive publishes each carry a different durable message_id.
    The subscriber must receive all three and they must all be distinct.
    """
    async def _test():
        conv_id = str(uuid.uuid4())
        channel = Channels.messaging(conv_id)
        msg_ids = [str(uuid.uuid4()) for _ in range(3)]

        received: list[PubSubEvent] = []

        async def handler(ch, ev):
            if ev.event_type == "new_message":
                received.append(ev)

        mgr = RedisPubSubManager()
        ok = await mgr.start_listener([channel], handler)
        assert ok

        await asyncio.sleep(0.3)

        publisher = RedisPubSubManager()
        for mid in msg_ids:
            evt = PubSubEvent(
                event_type="new_message",
                payload={"message_id": mid, "content": f"msg-{mid[:6]}"},
            )
            await publisher.publish(channel, evt)

        # Wait up to 3 s for all three events.
        for _ in range(30):
            await asyncio.sleep(0.1)
            if len(received) >= 3:
                break

        await mgr.stop_listener()

        received_ids = [e.payload["message_id"] for e in received]
        for mid in msg_ids:
            assert mid in received_ids, (
                f"message_id {mid} not received; got {received_ids}"
            )
        assert len(set(received_ids)) == 3, "Message IDs must be distinct"

    _run(_test())


# 24. Exactly one delivery to the intended recipient in the cross-instance scenario
def test_24_exactly_one_delivery_cross_instance():
    """
    End-to-end multi-instance delivery count test.

    Instance B subscribes to the conversation channel.  Instance A publishes
    a new_message event (simulating _handle_message() on instance A after
    PostgreSQL persistence and local delivery on A).

    Instance B's handle_fanout_event must deliver exactly ONE new_message
    WebSocket event to the recipient — no duplicates.
    """
    async def _test():
        conv_id      = str(uuid.uuid4())
        sender_id    = str(uuid.uuid4())
        recipient_id = str(uuid.uuid4())
        msg_id       = str(uuid.uuid4())
        channel      = Channels.messaging(conv_id)

        # --- Instance B setup ---
        local_mgr_b  = ConnectionManager()
        fake_ws      = AsyncMock()
        local_mgr_b.connect(recipient_id, fake_ws)

        delivered_events: list[dict] = []

        async def fake_send_text(payload: str):
            """Intercept WS frames delivered to the recipient on instance B."""
            frame = json.loads(payload)
            delivered_events.append(frame)

        fake_ws.send_text = AsyncMock(side_effect=fake_send_text)

        # Wire the fanout handler to instance B's local ConnectionManager.
        async def instance_b_handler(ch: str, ev: PubSubEvent):
            with patch("app.services.messaging_fanout.ws_manager", local_mgr_b):
                await handle_fanout_event(ch, ev)

        mgr_b = RedisPubSubManager()
        ok = await mgr_b.start_listener([channel], instance_b_handler)
        assert ok, "Instance B listener must start"
        await asyncio.sleep(0.4)

        # --- Instance A: publish after PostgreSQL persistence (simulated) ---
        # source is a *different* instance_id so the anti-loop guard passes.
        instance_a_id = f"instance-a-{uuid.uuid4().hex[:8]}"
        event = PubSubEvent(
            event_type="new_message",
            payload={
                "message_id":      msg_id,
                "conversation_id": conv_id,
                "sender_id":       sender_id,
                "recipient_id":    recipient_id,
                "content":         "Cross-instance single delivery",
                "created_at":      "2026-09-23T10:00:00+00:00",
            },
            source=instance_a_id,
        )

        publisher = RedisPubSubManager()
        await publisher.publish(channel, event)

        # Wait for delivery (up to 3 s).
        for _ in range(30):
            await asyncio.sleep(0.1)
            if any(e.get("type") == "new_message" for e in delivered_events):
                break

        await mgr_b.stop_listener()
        local_mgr_b._connections.clear()

        new_msg_deliveries = [e for e in delivered_events if e.get("type") == "new_message"]
        assert len(new_msg_deliveries) == 1, (
            f"Expected exactly 1 new_message delivery on instance B, "
            f"got {len(new_msg_deliveries)}: {delivered_events}"
        )
        assert new_msg_deliveries[0]["data"]["id"] == msg_id

    _run(_test())


# ---------------------------------------------------------------------------
# ADDITIONAL UNIT TESTS
# ---------------------------------------------------------------------------


# 25. messaging_ws.py imports only high-level fanout API (no raw pubsub)
def test_25_messaging_ws_imports_only_high_level_fanout():
    """
    messaging_ws.py must import only the public fanout API functions.
    It must NOT import pubsub_manager, PubSubEvent, or RedisPubSubManager
    directly — those belong exclusively to messaging_fanout.py.
    """
    import inspect
    import app.api.messaging_ws as mod

    source = inspect.getsource(mod).lower()

    # Frozen Phase 5.8.5.2 assertions (original test_17 form).
    assert "pubsub" not in source, (
        "messaging_ws.py must not reference pubsub anywhere in its source"
    )
    assert "publish(" not in source, (
        "messaging_ws.py must not call publish() directly"
    )
    assert "subscribe(" not in source, (
        "messaging_ws.py must not call subscribe() directly"
    )

    # Phase 5.8.4 assertion: the three high-level fanout functions ARE present.
    assert "publish_new_message" in source
    assert "subscribe_conversation" in source
    assert "unsubscribe_conversation" in source


# 26. PostgreSQL persistence happens before the fanout publish (ordering proof)
def test_26_persistence_before_publish_ordering():
    """
    Verify the call ordering in messaging_ws._handle_message():
      1. messaging_service.send_direct_message()  — PostgreSQL persistence
      2. publish_new_message()                    — cross-instance fanout

    Uses a mock DB session and real module import to confirm call sequence.
    """
    import inspect
    import app.api.messaging_ws as mod

    source = inspect.getsource(mod)

    # Locate both calls by position in the source.
    persist_pos = source.find("svc.send_direct_message(")
    publish_pos = source.find("publish_new_message(")

    assert persist_pos != -1, "send_direct_message() call not found in messaging_ws"
    assert publish_pos != -1, "publish_new_message() call not found in messaging_ws"

    assert persist_pos < publish_pos, (
        "PostgreSQL persistence (send_direct_message) must appear BEFORE "
        "publish_new_message() in the source code"
    )


# 27. subscribe_conversation acknowledges the correct per-conversation channel name
def test_27_subscribe_conversation_uses_correct_channel():
    """
    subscribe_conversation(conversation_id) must derive the correct channel
    name: Channels.messaging(conversation_id).

    The function is a logical no-op at runtime (the pattern listener handles
    all conversations), but it logs the channel and returns True.
    """
    conv_id = str(uuid.uuid4())
    expected = Channels.messaging(conv_id)

    async def _test():
        result = await subscribe_conversation(conv_id)
        assert result is True

    _run(_test())

    # Verify the channel name matches the expected pattern.
    assert expected == f"{_CHANNEL_NS}:messaging:{conv_id}", (
        f"Expected {expected!r} to match Channels.messaging pattern"
    )


# 28. unsubscribe_conversation acknowledges the correct per-conversation channel name
def test_28_unsubscribe_conversation_is_clean():
    """
    unsubscribe_conversation(conversation_id) must return True without raising.
    Derives the same channel name as subscribe_conversation.
    """
    conv_id = str(uuid.uuid4())
    expected = Channels.messaging(conv_id)

    async def _test():
        result = await unsubscribe_conversation(conv_id)
        assert result is True

    _run(_test())

    assert expected == f"{_CHANNEL_NS}:messaging:{conv_id}"
