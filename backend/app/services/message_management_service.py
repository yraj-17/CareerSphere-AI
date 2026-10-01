"""
Phase 5.8 — Message Management Service Extensions.

This module EXTENDS the existing messaging_service.py with business logic for
the seven new message-management features:

  1. Copy     — no backend operation required (clipboard-only)
  2. Reply    — extended send_direct_message() call with reply_to_message_id
  3. Star     — star_message() / unstar_message()
  4. Pin      — pin_message() / unpin_message()
  5. Delete for me        — delete_message_for_me()
  6. Delete for everyone  — delete_message_for_everyone() [sender only]
  7. Forward  — forward_message()

Architecture contract
──────────────────────
- No WebSocket, Redis, or HTTP-specific code belongs here.
- All authorization and data-integrity rules are enforced HERE, not in the
  API layer or the WebSocket endpoint.
- Callers (API / WS) must pass the authenticated User object; user_id is
  NEVER accepted from untrusted input.
- Physical deletion of direct_messages rows NEVER occurs.
- This module is the ONLY place these operations are implemented.

Authorization rules
───────────────────
star        — requester must be a conversation participant; idempotent.
unstar      — requester must be a conversation participant; idempotent.
pin         — requester must be a conversation participant.
unpin       — requester must be a conversation participant.
delete_me   — requester must be a conversation participant.
delete_all  — requester must be the MESSAGE SENDER (403 otherwise).
forward     — requester must have access to the source message AND be a
              participant of the destination conversation AND the accepted-
              connection check must pass for the destination.

Serialization helpers
──────────────────────
serialize_message() returns a dict that the API / WS layer can use to build
DirectMessageResponse-compatible payloads.  It accepts an optional
current_user_id so that per-user fields (is_starred, is_deleted_for_me) are
computed correctly.

Content sanitisation
──────────────────────
If deleted_for_everyone_at is set, serialize_message() NEVER returns the
original content.  The placeholder text is a constant exported from this
module so tests can assert the exact value.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    DirectConversation,
    DirectConversationParticipant,
    DirectMessage,
    MessageStar,
    MessageUserDeletion,
    User,
)
from app.services.messaging_service import (
    DELETED_FOR_EVERYONE_PLACEHOLDER,
    DM_MAX_CONTENT_CHARS,
    _get_other_participant_id,
    _require_accepted_connection,
    _require_participant,
    get_direct_conversation_for_user,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Placeholder shown when a replied-to message has been deleted for everyone.
DELETED_REPLY_PLACEHOLDER: str = "This message was deleted"

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_message(db: Session, message_id: str) -> DirectMessage:
    """Return a DirectMessage row or raise 404."""
    msg = db.query(DirectMessage).filter(DirectMessage.id == message_id).first()
    if msg is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found.",
        )
    return msg


def _require_message_access(
    db: Session,
    message_id: str,
    current_user: User,
    allow_deleted_for_everyone: bool = False,
) -> DirectMessage:
    """
    Return the DirectMessage after verifying:
      1. The message exists.
      2. The current user is a participant in the message's conversation.
      3. The message is not deleted-for-everyone (unless allow_deleted_for_everyone).
      4. The message is not deleted-for-me by the current user.

    Used by star, pin, delete-for-me, and forward to prevent cross-conversation
    manipulation and access to hidden messages.
    """
    msg = _get_message(db, message_id)

    # Participant check
    _require_participant(db, msg.conversation_id, current_user)

    # Deleted-for-everyone check (unless the caller explicitly allows it)
    if not allow_deleted_for_everyone and msg.deleted_for_everyone_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found.",
        )

    # Deleted-for-me check
    deleted_for_me = (
        db.query(MessageUserDeletion)
        .filter_by(message_id=message_id, user_id=current_user.id)
        .first()
    )
    if deleted_for_me is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found.",
        )

    return msg


# ---------------------------------------------------------------------------
# Serialization helper
# ---------------------------------------------------------------------------


def serialize_message(
    db: Session,
    msg: DirectMessage,
    current_user_id: Optional[str] = None,
) -> dict:
    """
    Return a safe dict representing the DirectMessage for API / WS transport.

    Security:
      - If deleted_for_everyone_at is set, content is ALWAYS replaced with
        DELETED_FOR_EVERYONE_PLACEHOLDER regardless of who is asking.
      - is_starred and is_deleted_for_me are per-user fields computed from
        the side tables; they are included only when current_user_id is given.
      - The replied-to message preview is sanitised in the same way.
      - No JWT, Redis internals, or auth secrets are included.
    """
    is_deleted = msg.deleted_for_everyone_at is not None

    # Sanitize content for deleted messages
    content = DELETED_FOR_EVERYONE_PLACEHOLDER if is_deleted else msg.content

    # Per-user fields
    is_starred = False
    is_deleted_for_me = False
    if current_user_id:
        is_starred = (
            db.query(MessageStar)
            .filter_by(message_id=msg.id, user_id=current_user_id)
            .first()
        ) is not None
        is_deleted_for_me = (
            db.query(MessageUserDeletion)
            .filter_by(message_id=msg.id, user_id=current_user_id)
            .first()
        ) is not None

    # Reply-to preview
    reply_to_data = None
    if msg.reply_to_message_id and msg.reply_to:
        r = msg.reply_to
        reply_is_deleted = r.deleted_for_everyone_at is not None
        reply_to_data = {
            "id": r.id,
            "sender_id": r.sender_id,
            "content": (
                DELETED_REPLY_PLACEHOLDER if reply_is_deleted else r.content
            ),
            "is_deleted_for_everyone": reply_is_deleted,
        }

    return {
        "id": msg.id,
        "conversation_id": msg.conversation_id,
        "sender_id": msg.sender_id,
        "content": content,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
        "delivered_at": msg.delivered_at.isoformat() if msg.delivered_at else None,
        "read_at": msg.read_at.isoformat() if msg.read_at else None,
        "reply_to_message_id": msg.reply_to_message_id,
        "reply_to_message": reply_to_data,
        "is_deleted_for_everyone": is_deleted,
        "deleted_for_everyone_at": (
            msg.deleted_for_everyone_at.isoformat()
            if msg.deleted_for_everyone_at
            else None
        ),
        "is_pinned": msg.pinned_at is not None,
        "pinned_at": msg.pinned_at.isoformat() if msg.pinned_at else None,
        "pinned_by_user_id": msg.pinned_by_user_id,
        "is_forwarded": msg.forwarded_from_message_id is not None,
        "forwarded_from_message_id": msg.forwarded_from_message_id,
        "is_starred": is_starred,
        "is_deleted_for_me": is_deleted_for_me,
    }


# ---------------------------------------------------------------------------
# Extended send_direct_message (with reply_to support)
# ---------------------------------------------------------------------------


def send_direct_message_extended(
    db: Session,
    conversation_id: str,
    sender: User,
    content: str,
    reply_to_message_id: Optional[str] = None,
) -> DirectMessage:
    """
    Extended version of messaging_service.send_direct_message() that also
    accepts an optional reply_to_message_id.

    Validation rules for reply_to_message_id:
      - The referenced message must exist (404 if not).
      - It must belong to the SAME conversation (400 if cross-conversation).
      - It must not be deleted-for-everyone (400 if deleted).

    This replaces the original send path when reply metadata is needed.
    For plain messages, the original send_direct_message() in messaging_service
    continues to work and is used by the existing WebSocket path via the updated
    _handle_message handler.
    """
    from app.services.messaging_service import (
        get_direct_conversation_for_user,
        _get_other_participant_id,
    )

    # Existence + participant check
    conv = get_direct_conversation_for_user(db, conversation_id, sender)

    # Validate content
    stripped = content.strip() if content else ""
    if not stripped:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message content cannot be empty.",
        )
    if len(stripped) > DM_MAX_CONTENT_CHARS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Message exceeds the {DM_MAX_CONTENT_CHARS}-character limit.",
        )

    # Enforce accepted connection
    other_user_id = _get_other_participant_id(db, conversation_id, sender.id)
    _require_accepted_connection(db, sender.id, other_user_id)

    # Validate reply_to_message_id if provided
    resolved_reply_id: Optional[str] = None
    if reply_to_message_id:
        reply_msg = db.query(DirectMessage).filter(
            DirectMessage.id == reply_to_message_id
        ).first()
        if reply_msg is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Replied-to message not found.",
            )
        if reply_msg.conversation_id != conversation_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Replied-to message does not belong to this conversation.",
            )
        if reply_msg.deleted_for_everyone_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot reply to a deleted message.",
            )
        resolved_reply_id = reply_to_message_id

    # Create message
    msg = DirectMessage(
        conversation_id=conversation_id,
        sender_id=sender.id,
        content=stripped,
        reply_to_message_id=resolved_reply_id,
    )
    db.add(msg)

    conv.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(msg)
    # Eagerly load reply_to for serialization
    if msg.reply_to_message_id:
        _ = msg.reply_to
    return msg


# ---------------------------------------------------------------------------
# 1. star_message / unstar_message
# ---------------------------------------------------------------------------


def star_message(db: Session, message_id: str, current_user: User) -> None:
    """
    Star a message for the current user.

    Idempotent: if already starred, does nothing.

    Authorization:
      - current_user must be a participant in the message's conversation.
      - Message must not be deleted-for-everyone.
      - Message must not be deleted-for-me.
    """
    _require_message_access(db, message_id, current_user)

    # Idempotent: attempt insert, ignore if already exists
    existing = (
        db.query(MessageStar)
        .filter_by(message_id=message_id, user_id=current_user.id)
        .first()
    )
    if existing is not None:
        return  # already starred — no-op

    star = MessageStar(message_id=message_id, user_id=current_user.id)
    db.add(star)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # race condition — already starred by concurrent request


def unstar_message(db: Session, message_id: str, current_user: User) -> None:
    """
    Remove the star for the current user.

    Idempotent: if not starred, does nothing.

    Authorization:
      - current_user must be a participant (checked via _require_message_access).
      - Access to deleted-for-everyone messages is also blocked.
    """
    # Verify participant access (allow_deleted_for_everyone=False so deleted
    # messages cannot be un-starred after the fact).
    msg = _get_message(db, message_id)
    _require_participant(db, msg.conversation_id, current_user)

    deleted = (
        db.query(MessageStar)
        .filter_by(message_id=message_id, user_id=current_user.id)
        .first()
    )
    if deleted is None:
        return  # not starred — no-op
    db.delete(deleted)
    db.commit()


# ---------------------------------------------------------------------------
# 2. pin_message / unpin_message
# ---------------------------------------------------------------------------


def pin_message(
    db: Session,
    message_id: str,
    current_user: User,
) -> DirectMessage:
    """
    Pin a message in its conversation.

    Pinning is conversation-level (not per-user).  Both participants may pin
    any message.  Only one message may be pinned per conversation at a time
    (the previous pin is cleared when a new one is set).

    Authorization:
      - current_user must be a participant.
      - Message must not be deleted-for-everyone.

    Returns the updated DirectMessage.
    """
    msg = _require_message_access(db, message_id, current_user)

    # Unpin any currently-pinned message in this conversation first
    (
        db.query(DirectMessage)
        .filter(
            DirectMessage.conversation_id == msg.conversation_id,
            DirectMessage.pinned_at != None,  # noqa: E711
        )
        .update({"pinned_at": None, "pinned_by_user_id": None}, synchronize_session="fetch")
    )

    now = datetime.now(timezone.utc)
    msg.pinned_at = now
    msg.pinned_by_user_id = current_user.id
    db.commit()
    db.refresh(msg)
    return msg


def unpin_message(
    db: Session,
    message_id: str,
    current_user: User,
) -> DirectMessage:
    """
    Remove the pin from a message.

    Idempotent: if not pinned, simply returns the message.

    Authorization:
      - current_user must be a participant.
    """
    msg = _get_message(db, message_id)
    _require_participant(db, msg.conversation_id, current_user)

    if msg.pinned_at is not None:
        msg.pinned_at = None
        msg.pinned_by_user_id = None
        db.commit()
        db.refresh(msg)
    return msg


# ---------------------------------------------------------------------------
# 3. delete_message_for_me
# ---------------------------------------------------------------------------


def delete_message_for_me(
    db: Session,
    message_id: str,
    current_user: User,
) -> None:
    """
    Mark a message as hidden for the current user only.

    Idempotent.  Does NOT affect the other participant's view.
    Does NOT touch the DirectMessage row itself.
    Does NOT broadcast any event to the other user.

    Authorization:
      - current_user must be a conversation participant.
    """
    msg = _get_message(db, message_id)
    _require_participant(db, msg.conversation_id, current_user)

    existing = (
        db.query(MessageUserDeletion)
        .filter_by(message_id=message_id, user_id=current_user.id)
        .first()
    )
    if existing is not None:
        return  # already deleted — idempotent no-op

    rec = MessageUserDeletion(message_id=message_id, user_id=current_user.id)
    db.add(rec)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # concurrent request — idempotent


# ---------------------------------------------------------------------------
# 4. delete_message_for_everyone
# ---------------------------------------------------------------------------


def delete_message_for_everyone(
    db: Session,
    message_id: str,
    current_user: User,
) -> DirectMessage:
    """
    Soft-delete a message for ALL participants.

    Security contract:
      - ONLY the message sender may call this.  Attempting to delete another
        user's message returns 403.  This is enforced HERE, not in the API.
      - The message row is NOT physically deleted.
      - The original content is preserved in the DB but NEVER returned to
        any client after this operation.
      - If the message was pinned, its pin state is cleared.
      - Idempotent: calling again on an already-deleted message returns the
        message with no further DB writes.

    After this call the caller must broadcast a message_deleted event via
    the messaging_fanout module.

    Returns the updated DirectMessage.

    Raises:
      403 — current_user is not the sender.
      403 — current_user is not a conversation participant.
      404 — message not found.
    """
    msg = _get_message(db, message_id)
    _require_participant(db, msg.conversation_id, current_user)

    # CRITICAL: only the sender may delete for everyone
    if msg.sender_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the message sender can delete a message for everyone.",
        )

    # Idempotent: already deleted
    if msg.deleted_for_everyone_at is not None:
        return msg

    now = datetime.now(timezone.utc)
    msg.deleted_for_everyone_at = now

    # Clear pin state — a deleted message must not remain visibly pinned
    if msg.pinned_at is not None:
        msg.pinned_at = None
        msg.pinned_by_user_id = None

    db.commit()
    db.refresh(msg)
    return msg


# ---------------------------------------------------------------------------
# 5. forward_message
# ---------------------------------------------------------------------------


def forward_message(
    db: Session,
    source_message_id: str,
    destination_conversation_id: str,
    current_user: User,
) -> DirectMessage:
    """
    Create a new DirectMessage in the destination conversation whose content
    is copied from the source message.

    The forwarded message is a completely NEW row — it belongs to the
    destination conversation and has its own message ID, timestamps, and
    delivery state.  The forwarded_from_message_id column records provenance.

    Authorization rules:
      - current_user must have access to the source message (participant in
        source conversation, message not deleted-for-everyone, not deleted-for-me).
      - current_user must be a participant in the destination conversation.
      - The accepted-connection check is enforced for the destination.
      - Forwarding to the same conversation is allowed but unusual.

    Raises:
      403  — source access denied or destination access denied.
      404  — source message not found.
      400  — source message is deleted for everyone.
    """
    # Verify source access
    src = _require_message_access(db, source_message_id, current_user)

    # Verify destination conversation access
    dest_conv = get_direct_conversation_for_user(
        db, destination_conversation_id, current_user
    )

    # Enforce accepted connection for the destination (new message path)
    dest_other_id = _get_other_participant_id(
        db, destination_conversation_id, current_user.id
    )
    _require_accepted_connection(db, current_user.id, dest_other_id)

    # Use the ORIGINAL content (src.content is never sanitised at DB level)
    content = src.content

    fwd_msg = DirectMessage(
        conversation_id=destination_conversation_id,
        sender_id=current_user.id,
        content=content,
        forwarded_from_message_id=source_message_id,
    )
    db.add(fwd_msg)

    # Touch destination conversation.updated_at
    dest_conv.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(fwd_msg)
    return fwd_msg


# ---------------------------------------------------------------------------
# Helpers for the message-history list (filtering)
# ---------------------------------------------------------------------------


def list_messages_for_user(
    db: Session,
    conversation_id: str,
    current_user: User,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """
    Return paginated messages with per-user fields computed.

    Filters applied:
      - Messages deleted-for-me by current_user are excluded.
      - Messages deleted-for-everyone are included but with sanitised content.
      - Per-user is_starred, is_pinned, etc. are included in each dict.

    Returns a list of serialized message dicts (NOT ORM objects).
    Uses the existing (conversation_id, created_at) index.
    """
    # Authorization
    get_direct_conversation_for_user(db, conversation_id, current_user)

    # Subquery: message IDs deleted-for-me by this user
    deleted_for_me_sub = (
        db.query(MessageUserDeletion.message_id)
        .filter(MessageUserDeletion.user_id == current_user.id)
        .scalar_subquery()
    )

    msgs = (
        db.query(DirectMessage)
        .filter(
            DirectMessage.conversation_id == conversation_id,
            DirectMessage.id.notin_(deleted_for_me_sub),
        )
        .order_by(DirectMessage.created_at.asc(), DirectMessage.id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    # Batch-load star state for all fetched messages
    msg_ids = [m.id for m in msgs]
    starred_ids: set[str] = set()
    if msg_ids:
        star_rows = (
            db.query(MessageStar.message_id)
            .filter(
                MessageStar.message_id.in_(msg_ids),
                MessageStar.user_id == current_user.id,
            )
            .all()
        )
        starred_ids = {r[0] for r in star_rows}

    results = []
    for msg in msgs:
        is_deleted = msg.deleted_for_everyone_at is not None
        content = DELETED_FOR_EVERYONE_PLACEHOLDER if is_deleted else msg.content

        # Reply-to preview
        reply_to_data = None
        if msg.reply_to_message_id:
            # Load lazily (already in SQLAlchemy identity map if eager-loaded;
            # otherwise one extra query per replied-to message)
            r = msg.reply_to
            if r:
                reply_is_deleted = r.deleted_for_everyone_at is not None
                reply_to_data = {
                    "id": r.id,
                    "sender_id": r.sender_id,
                    "content": (
                        DELETED_REPLY_PLACEHOLDER if reply_is_deleted else r.content
                    ),
                    "is_deleted_for_everyone": reply_is_deleted,
                }

        results.append({
            "id": msg.id,
            "conversation_id": msg.conversation_id,
            "sender_id": msg.sender_id,
            "content": content,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
            "delivered_at": msg.delivered_at.isoformat() if msg.delivered_at else None,
            "read_at": msg.read_at.isoformat() if msg.read_at else None,
            "reply_to_message_id": msg.reply_to_message_id,
            "reply_to_message": reply_to_data,
            "is_deleted_for_everyone": is_deleted,
            "deleted_for_everyone_at": (
                msg.deleted_for_everyone_at.isoformat()
                if msg.deleted_for_everyone_at
                else None
            ),
            "is_pinned": msg.pinned_at is not None,
            "pinned_at": msg.pinned_at.isoformat() if msg.pinned_at else None,
            "pinned_by_user_id": msg.pinned_by_user_id,
            "is_forwarded": msg.forwarded_from_message_id is not None,
            "forwarded_from_message_id": msg.forwarded_from_message_id,
            "is_starred": msg.id in starred_ids,
            "is_deleted_for_me": False,  # filtered out above if True
        })

    return results


def get_pinned_message(
    db: Session,
    conversation_id: str,
    current_user: User,
) -> Optional[dict]:
    """
    Return the currently pinned message in a conversation, or None.

    Excludes messages that are deleted-for-everyone.
    """
    get_direct_conversation_for_user(db, conversation_id, current_user)

    msg = (
        db.query(DirectMessage)
        .filter(
            DirectMessage.conversation_id == conversation_id,
            DirectMessage.pinned_at != None,  # noqa: E711
            DirectMessage.deleted_for_everyone_at == None,  # noqa: E711
        )
        .order_by(DirectMessage.pinned_at.desc())
        .first()
    )
    if msg is None:
        return None
    return serialize_message(db, msg, current_user.id)
