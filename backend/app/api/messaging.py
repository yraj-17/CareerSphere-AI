"""
Phase 5.8.3 — Direct Messaging REST API.
Phase 5.8   — Extended with message management endpoints.

Architecture:
    JWT → current_user (via get_current_user dep)
        → this router (thin HTTP layer, zero business logic)
            → messaging_service / message_management_service (authoritative)
                → PostgreSQL

Security contract
─────────────────
- Every endpoint requires JWT authentication (get_current_user).
- sender_id / current_user_id is NEVER accepted from the request body
  or query params.  Identity always comes from the authenticated token.
- The messaging_service / message_management_service perform ALL authorization:
    - accepted-connection enforcement
    - participant membership
    - sender-only delete-for-everyone
    - cross-conversation reference prevention
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
    ForwardMessageRequest,
    LatestMessageSummary,
    MessageActionResponse,
    MessageListResponse,
    MessageParticipantSummary,
    MessageStateUpdateResponse,
    SendMessageRequest,
    UnreadCountResponse,
)
from app.services import messaging_service as svc
from app.services import message_management_service as mgmt

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
# Endpoint 3 — SEND MESSAGE  (extended with reply_to support)
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
    - ``reply_to_message_id`` is optional; if provided it must reference a
      message in the same conversation.
    - ``delivered_at`` and ``read_at`` are ``null`` at creation; they are
      set later by the WebSocket delivery layer.
    """
    if body.reply_to_message_id:
        # Use the extended service that handles reply validation
        msg = mgmt.send_direct_message_extended(
            db,
            conversation_id,
            current_user,
            body.content,
            reply_to_message_id=body.reply_to_message_id,
        )
        d = mgmt.serialize_message(db, msg, current_user.id)
        return DirectMessageResponse.from_dict(d)
    else:
        # Use the original service for plain messages (preserves existing behavior)
        msg = svc.send_direct_message(db, conversation_id, current_user, body.content)
        d = mgmt.serialize_message(db, msg, current_user.id)
        return DirectMessageResponse.from_dict(d)


# ---------------------------------------------------------------------------
# Endpoint 4 — MESSAGE HISTORY  (extended with per-user fields)
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
    - Messages deleted-for-me are excluded.
    - Messages deleted-for-everyone are included with sanitised content.
    - Per-user fields (is_starred, is_pinned, etc.) are computed for the caller.
    """
    dicts = mgmt.list_messages_for_user(
        db, conversation_id, current_user, limit=limit, offset=offset
    )
    return MessageListResponse(
        messages=[DirectMessageResponse.from_dict(d) for d in dicts],
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


# ---------------------------------------------------------------------------
# Phase 5.8 — Message Management Endpoints
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Endpoint 8 — STAR
# POST /messaging/messages/{message_id}/star
# ---------------------------------------------------------------------------


@router.post(
    "/messages/{message_id}/star",
    response_model=MessageActionResponse,
    summary="Star a message (per-user save)",
)
def star_message(
    message_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageActionResponse:
    """
    Star/save a message for the current user.

    - Star state is **per-user**: User A starring has no effect on User B.
    - Idempotent: starring an already-starred message is a no-op.
    - Message must not be deleted-for-everyone.
    - Current user must be a conversation participant.
    """
    mgmt.star_message(db, message_id, current_user)
    return MessageActionResponse(success=True)


# ---------------------------------------------------------------------------
# Endpoint 9 — UNSTAR
# DELETE /messaging/messages/{message_id}/star
# ---------------------------------------------------------------------------


@router.delete(
    "/messages/{message_id}/star",
    response_model=MessageActionResponse,
    summary="Unstar a message",
)
def unstar_message(
    message_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageActionResponse:
    """
    Remove the star for the current user.

    Idempotent: if the message is not starred, returns success with no change.
    """
    mgmt.unstar_message(db, message_id, current_user)
    return MessageActionResponse(success=True)


# ---------------------------------------------------------------------------
# Endpoint 10 — PIN
# POST /messaging/messages/{message_id}/pin
# ---------------------------------------------------------------------------


@router.post(
    "/messages/{message_id}/pin",
    response_model=MessageActionResponse,
    summary="Pin a message in the conversation",
)
def pin_message(
    message_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageActionResponse:
    """
    Pin a message at the conversation level.

    - Any participant may pin any accessible message.
    - Only one message may be pinned per conversation; the previous pin is
      cleared when a new one is set.
    - Pinning a deleted-for-everyone message is rejected (404).
    """
    msg = mgmt.pin_message(db, message_id, current_user)
    d = mgmt.serialize_message(db, msg, current_user.id)
    return MessageActionResponse(success=True, message=DirectMessageResponse.from_dict(d))


# ---------------------------------------------------------------------------
# Endpoint 11 — UNPIN
# DELETE /messaging/messages/{message_id}/pin
# ---------------------------------------------------------------------------


@router.delete(
    "/messages/{message_id}/pin",
    response_model=MessageActionResponse,
    summary="Unpin a message",
)
def unpin_message(
    message_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageActionResponse:
    """
    Remove the pin from a message.

    Idempotent: if the message is not pinned, returns success with no change.
    """
    msg = mgmt.unpin_message(db, message_id, current_user)
    d = mgmt.serialize_message(db, msg, current_user.id)
    return MessageActionResponse(success=True, message=DirectMessageResponse.from_dict(d))


# ---------------------------------------------------------------------------
# Endpoint 12 — DELETE FOR ME
# POST /messaging/messages/{message_id}/delete-for-me
# ---------------------------------------------------------------------------


@router.post(
    "/messages/{message_id}/delete-for-me",
    response_model=MessageActionResponse,
    summary="Delete a message for the current user only",
)
def delete_for_me(
    message_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageActionResponse:
    """
    Hide a message from the current user's view only.

    - The other participant is **not** affected.
    - The message row is **not** physically deleted.
    - Idempotent.
    - Current user must be a conversation participant.
    """
    mgmt.delete_message_for_me(db, message_id, current_user)
    return MessageActionResponse(success=True)


# ---------------------------------------------------------------------------
# Endpoint 13 — DELETE FOR EVERYONE
# POST /messaging/messages/{message_id}/delete-for-everyone
# ---------------------------------------------------------------------------


@router.post(
    "/messages/{message_id}/delete-for-everyone",
    response_model=MessageActionResponse,
    summary="Delete a message for all participants (sender only)",
)
def delete_for_everyone(
    message_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageActionResponse:
    """
    Soft-delete a message so it is hidden for **all** participants.

    - **Only the message sender** may call this endpoint.
    - Attempting to delete another user's message returns **403**.
    - The message row is **not** physically deleted; content is preserved
      in the database but NEVER returned to any client after this call.
    - Idempotent: calling again on an already-deleted message returns success.
    - Callers should broadcast the ``message_deleted`` WebSocket event after
      this REST call succeeds.

    Security: Authorization is enforced server-side.  The frontend must not
    rely on hiding this option — the backend enforces sender identity.
    """
    msg = mgmt.delete_message_for_everyone(db, message_id, current_user)
    d = mgmt.serialize_message(db, msg, current_user.id)
    return MessageActionResponse(success=True, message=DirectMessageResponse.from_dict(d))


# ---------------------------------------------------------------------------
# Endpoint 14 — FORWARD
# POST /messaging/messages/{message_id}/forward
# ---------------------------------------------------------------------------


@router.post(
    "/messages/{message_id}/forward",
    response_model=DirectMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Forward a message to another conversation",
)
def forward_message(
    message_id: str,
    body: ForwardMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DirectMessageResponse:
    """
    Forward a message to a different 1-to-1 conversation.

    - The forwarded message is a **new** message row in the destination
      conversation.  It has its own ID, timestamps, and delivery state.
    - The original source message ID is recorded as provenance.
    - The current user must have access to the source message (participant,
      not deleted-for-everyone, not deleted-for-me).
    - The current user must be a participant in the destination conversation.
    - The accepted-connection check is enforced for the destination.
    - Forwarding a deleted-for-everyone message is rejected (404).
    """
    msg = mgmt.forward_message(
        db,
        source_message_id=message_id,
        destination_conversation_id=body.destination_conversation_id,
        current_user=current_user,
    )
    d = mgmt.serialize_message(db, msg, current_user.id)
    return DirectMessageResponse.from_dict(d)


# ---------------------------------------------------------------------------
# Endpoint 15 — GET PINNED MESSAGE
# GET /messaging/conversations/{conversation_id}/pinned
# ---------------------------------------------------------------------------


@router.get(
    "/conversations/{conversation_id}/pinned",
    response_model=MessageActionResponse,
    summary="Get the currently pinned message in a conversation",
)
def get_pinned_message(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageActionResponse:
    """
    Return the currently pinned message in the conversation, or success=True
    with message=None if no message is pinned.

    - Current user must be a participant.
    """
    d = mgmt.get_pinned_message(db, conversation_id, current_user)
    if d is None:
        return MessageActionResponse(success=True, message=None)
    return MessageActionResponse(
        success=True, message=DirectMessageResponse.from_dict(d)
    )
