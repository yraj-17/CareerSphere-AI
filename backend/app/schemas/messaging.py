"""
Phase 5.8.3 — Direct Messaging API schemas.

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
# Message responses
# ---------------------------------------------------------------------------


class DirectMessageResponse(BaseModel):
    """A single persisted direct message."""

    id: str
    conversation_id: str
    sender_id: str
    content: str
    created_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


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
