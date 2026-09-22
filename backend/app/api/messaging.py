"""
Phase 5.8.3 — Direct Messaging REST API.

Architecture:
    JWT → current_user (via get_current_user dep)
        → this router (thin HTTP layer, zero business logic)
            → messaging_service (authoritative)
                → PostgreSQL

Security contract
─────────────────
- Every endpoint requires JWT authentication (get_current_user).
- sender_id / current_user_id is NEVER accepted from the request body
  or query params.  Identity always comes from the authenticated token.
- The messaging_service performs all authorization checks:
    - accepted-connection enforcement
    - participant membership
    - self-messaging rejection
- No business logic is duplicated here.

Naming note
───────────
The project already has an AI-chat router at prefix /ai.
This router uses prefix /messaging to avoid any route conflict.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models import DirectConversation, User
from app.schemas.messaging import (
    ConversationListItem,
    ConversationListResponse,
    ConversationResponse,
    DirectMessageResponse,
    LatestMessageSummary,
    MessageListResponse,
    MessageParticipantSummary,
    MessageStateUpdateResponse,
    SendMessageRequest,
    UnreadCountResponse,
)
from app.services import messaging_service as svc

router = APIRouter(prefix="/messaging", tags=["Messaging"])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _participant_summary(db: Session, user_id: str) -> MessageParticipantSummary:
    """Load a User row and project it to the safe public summary schema."""
    user: User | None = db.query(User).filter(User.id == user_id).first()
    if user is None:
        # Defensive — participant rows always reference valid users via FK.
        return MessageParticipantSummary(
            id=user_id, username="unknown", first_name="Deleted", last_name="User"
        )
    return MessageParticipantSummary(
        id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )


def _conversation_response(
    db: Session,
    conv: DirectConversation,
    current_user_id: str,
) -> ConversationResponse:
    """Build a ConversationResponse from a DirectConversation ORM object."""
    # Determine which participant is the other one.
    from app.db.models import DirectConversationParticipant
    participants = (
        db.query(DirectConversationParticipant.user_id)
        .filter_by(conversation_id=conv.id)
        .all()
    )
    other_id = next(
        (uid for (uid,) in participants if uid != current_user_id),
        current_user_id,  # fallback — should never happen for valid conversations
    )
    return ConversationResponse(
        id=conv.id,
        other_participant=_participant_summary(db, other_id),
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


# ---------------------------------------------------------------------------
# Endpoint 1 — GET OR CREATE CONVERSATION
# POST /messaging/conversations/{user_id}
# ---------------------------------------------------------------------------


@router.post(
    "/conversations/{user_id}",
    response_model=ConversationResponse,
    status_code=status.HTTP_200_OK,
    summary="Open or retrieve a direct conversation with another user",
)
def get_or_create_conversation(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConversationResponse:
    """
    Open (or retrieve an existing) 1-to-1 conversation with **user_id**.

    - ``user_id`` identifies the *other* user; the authenticated caller is
      always the initiator.
    - Requires an **accepted** professional connection with the other user.
    - If a conversation already exists for this pair it is returned as-is
      (idempotent).
    - Self-messaging returns **400**; missing user returns **404**;
      no accepted connection returns **403**.
    """
    conv = svc.get_or_create_direct_conversation(db, current_user, user_id)
    return _conversation_response(db, conv, current_user.id)


# ---------------------------------------------------------------------------
# Endpoint 2 — LIST CONVERSATIONS
# GET /messaging/conversations
# ---------------------------------------------------------------------------


@router.get(
    "/conversations",
    response_model=ConversationListResponse,
    summary="List all direct conversations for the authenticated user",
)
def list_conversations(
    limit: int = Query(default=20, ge=1, le=100, description="Page size (max 100)."),
    offset: int = Query(default=0, ge=0, description="Pagination offset."),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConversationListResponse:
    """
    Return a paginated list of the current user's direct conversations,
    ordered by most recent activity.

    Each item includes:
    - conversation ID + timestamps
    - other participant public identity (username, display name)
    - latest message snippet
    - unread message count

    Uses 4 DB queries regardless of page size (no N+1).
    """
    summaries = svc.list_direct_conversations(db, current_user, limit=limit, offset=offset)

    # Batch-load participant User rows to avoid N+1.
    other_ids = list({s.other_user_id for s in summaries if s.other_user_id})
    users_by_id: dict[str, User] = {}
    if other_ids:
        rows = db.query(User).filter(User.id.in_(other_ids)).all()
        users_by_id = {u.id: u for u in rows}

    items: list[ConversationListItem] = []
    for s in summaries:
        u = users_by_id.get(s.other_user_id)
        other = (
            MessageParticipantSummary(
                id=u.id,
                username=u.username,
                first_name=u.first_name,
                last_name=u.last_name,
            )
            if u
            else MessageParticipantSummary(
                id=s.other_user_id,
                username="unknown",
                first_name="Deleted",
                last_name="User",
            )
        )
        latest: Optional[LatestMessageSummary] = None
        if s.latest_message_id:
            latest = LatestMessageSummary(
                id=s.latest_message_id,
                sender_id=s.latest_message_sender_id or "",
                content=s.latest_message_content or "",
                created_at=s.latest_message_at,
            )
        items.append(
            ConversationListItem(
                id=s.conversation_id,
                other_participant=other,
                latest_message=latest,
                unread_count=s.unread_count,
                updated_at=s.updated_at,
            )
        )

    return ConversationListResponse(
        conversations=items,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# Endpoint 3 — SEND MESSAGE
# POST /messaging/conversations/{conversation_id}/messages
# ---------------------------------------------------------------------------


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=DirectMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send a direct message in a conversation",
)
def send_message(
    conversation_id: str,
    body: SendMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DirectMessageResponse:
    """
    Send a message in the specified conversation.

    - The authenticated user is always the sender (``sender_id`` is derived
      from the JWT, never from the request body).
    - Requires the two participants to still share an **accepted** connection.
    - Empty or whitespace-only content returns **400**.
    - Content is trimmed of surrounding whitespace before persistence.
    - ``delivered_at`` and ``read_at`` are ``null`` at creation; they are
      set later by the WebSocket delivery layer.
    """
    msg = svc.send_direct_message(db, conversation_id, current_user, body.content)
    return DirectMessageResponse.model_validate(msg)


# ---------------------------------------------------------------------------
# Endpoint 4 — MESSAGE HISTORY
# GET /messaging/conversations/{conversation_id}/messages
# ---------------------------------------------------------------------------


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=MessageListResponse,
    summary="Retrieve message history for a conversation",
)
def list_messages(
    conversation_id: str,
    limit: int = Query(default=50, ge=1, le=200, description="Page size (max 200)."),
    offset: int = Query(default=0, ge=0, description="Pagination offset."),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageListResponse:
    """
    Return paginated messages for a conversation in chronological order
    (oldest first).

    - Only accessible to conversation participants.
    - Non-participants receive **403**.
    - Messages are ordered by ``created_at ASC, id ASC`` for stable pagination.
    """
    msgs = svc.list_direct_messages(
        db, conversation_id, current_user, limit=limit, offset=offset
    )
    return MessageListResponse(
        messages=[DirectMessageResponse.model_validate(m) for m in msgs],
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# Endpoint 5 — UNREAD COUNT
# GET /messaging/unread-count
# ---------------------------------------------------------------------------


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    summary="Get total unread message count for the authenticated user",
)
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UnreadCountResponse:
    """
    Return the total number of unread messages across all of the current
    user's conversations.

    - Only messages sent by the *other* participant are counted.
    - Messages the current user sent are never counted.
    - Messages already marked as read are not counted.
    """
    count = svc.get_unread_count(db, current_user)
    return UnreadCountResponse(unread_count=count)


# ---------------------------------------------------------------------------
# Endpoint 6 — MARK DELIVERED
# POST /messaging/conversations/{conversation_id}/delivered
# ---------------------------------------------------------------------------


@router.post(
    "/conversations/{conversation_id}/delivered",
    response_model=MessageStateUpdateResponse,
    summary="Mark received messages as delivered in a conversation",
)
def mark_delivered(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageStateUpdateResponse:
    """
    Mark all messages sent by the *other* participant as delivered.

    - Only the *receiver* of messages can mark them delivered.
    - The sender's own messages are never affected.
    - Operation is idempotent: calling it again returns ``updated_count: 0``.
    - Returns the number of messages whose ``delivered_at`` was updated.
    """
    updated = svc.mark_messages_delivered(db, conversation_id, current_user)
    return MessageStateUpdateResponse(updated_count=updated)


# ---------------------------------------------------------------------------
# Endpoint 7 — MARK READ
# POST /messaging/conversations/{conversation_id}/read
# ---------------------------------------------------------------------------


@router.post(
    "/conversations/{conversation_id}/read",
    response_model=MessageStateUpdateResponse,
    summary="Mark received messages as read in a conversation",
)
def mark_read(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageStateUpdateResponse:
    """
    Mark all messages sent by the *other* participant as read.

    - Only the *receiver* of messages can mark them read.
    - Reading a message automatically sets ``delivered_at`` if not already set
      (invariant: ``read_at`` IS NOT NULL ⟹ ``delivered_at`` IS NOT NULL).
    - Operation is idempotent.
    - Returns the number of messages whose ``read_at`` was updated.
    """
    updated = svc.mark_messages_read(db, conversation_id, current_user)
    return MessageStateUpdateResponse(updated_count=updated)
