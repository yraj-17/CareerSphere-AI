"""Regression tests for REST-originated real-time messaging events."""

from unittest.mock import AsyncMock, patch

import pytest

from app.api.messaging import _deliver_management_event, _deliver_new_message


@pytest.mark.anyio
async def test_rest_new_message_delivers_locally_and_publishes():
    payload = {
        "id": "msg-1",
        "conversation_id": "conv-1",
        "content": "Forwarded content",
        "created_at": "2026-10-01T00:00:00+00:00",
        "reply_to_message_id": None,
        "reply_to_message": None,
        "is_forwarded": True,
        "forwarded_from_message_id": "source-1",
    }
    with (
        patch("app.api.messaging.ws_manager.send_to_user", new=AsyncMock()) as send,
        patch("app.api.messaging.publish_new_message", new=AsyncMock(return_value=True)) as publish,
    ):
        await _deliver_new_message(payload, "user-a", "user-c")

    assert send.await_count == 3
    publish.assert_awaited_once_with(
        message_id="msg-1",
        conversation_id="conv-1",
        sender_id="user-a",
        recipient_id="user-c",
        content="Forwarded content",
        created_at="2026-10-01T00:00:00+00:00",
        reply_to_message_id=None,
        reply_to_content=None,
        reply_to_sender_id=None,
        is_forwarded=True,
        forwarded_from_message_id="source-1",
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("event_type", "publisher"),
    [
        ("message_deleted", "publish_message_deleted"),
        ("message_pinned", "publish_message_pinned"),
        ("message_unpinned", "publish_message_pinned"),
    ],
)
async def test_rest_management_event_delivers_locally_and_publishes(
    event_type, publisher
):
    with (
        patch("app.api.messaging.ws_manager.send_to_user", new=AsyncMock()) as send,
        patch(f"app.api.messaging.{publisher}", new=AsyncMock(return_value=True)) as publish,
    ):
        await _deliver_management_event(
            event_type, "msg-1", "conv-1", "user-a", "user-b"
        )

    send.assert_awaited_once()
    publish.assert_awaited_once()


@pytest.mark.anyio
async def test_rest_fanout_failure_does_not_undo_persisted_operation():
    with (
        patch("app.api.messaging.ws_manager.send_to_user", new=AsyncMock()),
        patch(
            "app.api.messaging.publish_message_deleted",
            new=AsyncMock(side_effect=RuntimeError("redis unavailable")),
        ),
    ):
        await _deliver_management_event(
            "message_deleted", "msg-1", "conv-1", "user-a", "user-b"
        )
