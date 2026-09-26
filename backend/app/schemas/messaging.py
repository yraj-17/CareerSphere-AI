"""
Phase 5.8.3 — Direct Messaging API schemas.
Phase 5.8   — Extended with message management schemas.

All response models follow the existing Pydantic conventions in this project:
  - BaseModel with model_config = {"from_attributes": True} where ORM objects
    are passed directly.
  - Optional[datetime] = None for nullable timestamp columns.
  - str for UUID fields (stored as VARCHAR(36)).
  - No password_hash, email, tokens, or internal DB fields exposed.

Sensitive field exclusion
─────────────────────────
MessageParticipantSummary intentionally omits:
  - email
  - password_hash
  - access_token / refresh_token
  - career preferences, completeness metrics
  - profile_photo_media_id (internal FK)

Security: deleted-for-everyone content is NEVER returned.
  DirectMessageResponse.content is sanitised at the SERVICE layer;
  the schema trusts the service to have already replaced the content with the
  placeholder.  The is_deleted_for_everyone flag signals the UI to render the
  placeholder style.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.services.messaging_service import DM_MAX_CONTENT_CHARS


# ---------------------------------------------------------------------------
# Participant summary — safe public identity for the other user
# ---------------------------------------------------------------------------


class MessageParticipantSummary(BaseModel):
    """Minimal public identity for a conversation participant."""

    id: str
    username: str
    first_name: str
    last_name: str

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Conversation responses
# ---------------------------------------------------------------------------


class ConversationResponse(BaseModel):
    """
    Single conversation row as returned by the POST /conversations/{user_id}
    endpoint.  Contains enough context for the frontend to identify and
    display the conversation.
    """

    id: str
    other_participant: MessageParticipantSummary
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class LatestMessageSummary(BaseModel):
    """Latest message snippet embedded in a conversation list item."""

    id: str
    sender_id: str
    content: str
    created_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None


class ConversationListItem(BaseModel):
    """
    One item in the paginated conversation list.

    Contains enough information for a messaging sidebar:
      - conversation identity
      - other participant (public summary)
      - latest message snippet
      - unread message count
      - last-activity timestamp for ordering
    """

    id: str
    other_participant: MessageParticipantSummary
    latest_message: Optional[LatestMessageSummary] = None
    unread_count: int = 0
    updated_at: Optional[datetime] = None


class ConversationListResponse(BaseModel):
    """Paginated conversation list."""

    conversations: list[ConversationListItem]
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Phase 5.8 — Reply-to preview
# ---------------------------------------------------------------------------


class ReplyToPreview(BaseModel):
    """
    Minimal preview of the message being replied to.

    If the original message was deleted for everyone, content is replaced
    with the safe placeholder at the service layer before reaching here.
    """

    id: str
    sender_id: str
    content: str
    is_deleted_for_everyone: bool = False

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Message responses
# ---------------------------------------------------------------------------


class DirectMessageResponse(BaseModel):
    """
    A single persisted direct message.

    Phase 5.8 additions:
      reply_to_message_id    — FK to the replied-to message (or None).
      reply_to_message       — Inline preview of the replied-to message (or None).
      is_deleted_for_everyone — True when the sender deleted this for all.
      deleted_for_everyone_at — Timestamp of global deletion (or None).
      is_pinned              — True when this message is pinned in the conv.
      pinned_at              — Timestamp of pinning (or None).
      pinned_by_user_id      — Who pinned it (or None).
      is_forwarded           — True when this is a forwarded copy.
      forwarded_from_message_id — Original source message ID (or None).
      is_starred             — True when the current user starred this message.
      is_deleted_for_me      — True when the current user deleted this for themselves.

    Security: content is already sanitised by the service layer when
    is_deleted_for_everyone is True.  This schema NEVER re-exposes raw content.
    """

    id: str
    conversation_id: str
    sender_id: str
    content: str
    created_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None

    # Phase 5.8 management fields
    reply_to_message_id: Optional[str] = None
    reply_to_message: Optional[ReplyToPreview] = None
    is_deleted_for_everyone: bool = False
    deleted_for_everyone_at: Optional[datetime] = None
    is_pinned: bool = False
    pinned_at: Optional[datetime] = None
    pinned_by_user_id: Optional[str] = None
    is_forwarded: bool = False
    forwarded_from_message_id: Optional[str] = None
    is_starred: bool = False
    is_deleted_for_me: bool = False

    model_config = {"from_attributes": True}

    @classmethod
    def from_dict(cls, d: dict) -> "DirectMessageResponse":
        """Build from the dict returned by message_management_service helpers."""
        reply_to = None
        if d.get("reply_to_message"):
            reply_to = ReplyToPreview(**d["reply_to_message"])
        return cls(
            id=d["id"],
            conversation_id=d["conversation_id"],
            sender_id=d["sender_id"],
            content=d["content"],
            created_at=d.get("created_at"),
            delivered_at=d.get("delivered_at"),
            read_at=d.get("read_at"),
            reply_to_message_id=d.get("reply_to_message_id"),
            reply_to_message=reply_to,
            is_deleted_for_everyone=d.get("is_deleted_for_everyone", False),
            deleted_for_everyone_at=d.get("deleted_for_everyone_at"),
            is_pinned=d.get("is_pinned", False),
            pinned_at=d.get("pinned_at"),
            pinned_by_user_id=d.get("pinned_by_user_id"),
            is_forwarded=d.get("is_forwarded", False),
            forwarded_from_message_id=d.get("forwarded_from_message_id"),
            is_starred=d.get("is_starred", False),
            is_deleted_for_me=d.get("is_deleted_for_me", False),
        )


class MessageListResponse(BaseModel):
    """Paginated message history for one conversation."""

    messages: list[DirectMessageResponse]
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Send message request
# ---------------------------------------------------------------------------


class SendMessageRequest(BaseModel):
    """Request body for POST /conversations/{conversation_id}/messages."""

    content: str = Field(
        ...,
        min_length=1,
        max_length=DM_MAX_CONTENT_CHARS,
        description=(
            "Message content. Surrounding whitespace is stripped. "
            f"Maximum {DM_MAX_CONTENT_CHARS} characters."
        ),
    )
    reply_to_message_id: Optional[str] = Field(
        default=None,
        description=(
            "Optional ID of the message being replied to. "
            "Must belong to the same conversation."
        ),
    )


# ---------------------------------------------------------------------------
# Forward message request
# ---------------------------------------------------------------------------


class ForwardMessageRequest(BaseModel):
    """Request body for POST /messages/{message_id}/forward."""

    destination_conversation_id: str = Field(
        ...,
        description="ID of the conversation to forward the message to.",
    )


# ---------------------------------------------------------------------------
# Simple state-update response
# ---------------------------------------------------------------------------


class MessageStateUpdateResponse(BaseModel):
    """
    Returned by the mark-delivered and mark-read endpoints.

    ``updated_count`` is the number of messages whose status changed.
    0 indicates the operation was a no-op (already in the target state).
    """

    updated_count: int


# ---------------------------------------------------------------------------
# Unread count
# ---------------------------------------------------------------------------


class UnreadCountResponse(BaseModel):
    """Global unread message count for the authenticated user."""

    unread_count: int


# ---------------------------------------------------------------------------
# Message action response
# ---------------------------------------------------------------------------


class MessageActionResponse(BaseModel):
    """Generic response for single-message action endpoints (star, pin, etc.)."""

    success: bool
    message: Optional[DirectMessageResponse] = None
