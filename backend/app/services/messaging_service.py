"""
Phase 5.8.2 — Direct Messaging Service.

This is the authoritative layer for all persistent 1-to-1 messaging logic.
No WebSocket, Redis, or HTTP-specific code belongs here.

Error contract (mirrors connection_service.py conventions)
──────────────────────────────────────────────────────────
  400  Bad Request          — self-messaging, empty/invalid content
  403  Forbidden            — non-participant access, wrong user
  404  Not Found            — conversation or user does not exist
  409  Conflict             — conversation already exists (concurrent create)
  403  Forbidden            — no accepted connection between users

Write operations call db.commit() + db.refresh() and return the persisted
object so the caller always has a fully populated row.

Read operations do NOT commit.

Message content limit
─────────────────────
Direct messages are conversational; the cap is set at 4 000 characters —
below the AI_MAX_PROMPT_CHARS = 8 000 limit used by the AI chat, and well
above any reasonable single message in practice.  The constant is exported
so the future API layer can use it in its validation schema without
duplicating the value.

Pagination
──────────
The project uses simple offset/limit throughout (no cursor tokens).
list_direct_messages() and list_direct_conversations() follow that pattern.

Connection-removal behaviour
─────────────────────────────
If an accepted connection is removed after a conversation exists:
  - existing message history remains readable by both participants.
  - sending NEW messages is blocked (403 "No accepted connection").
  - the conversation row itself is NOT deleted automatically.
This matches the spec and is documented in test_47/test_48.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, insert as sa_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    Connection,
    ConnectionStatus,
    DirectConversation,
    DirectConversationParticipant,
    DirectMessage,
    User,
)
from app.services.connection_service import get_connection_between_users

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Maximum character length for a single direct message.
#: Deliberately below AI_MAX_PROMPT_CHARS (8 000) to stay in conversational range.
DM_MAX_CONTENT_CHARS: int = 4_000

# ---------------------------------------------------------------------------
# Service-level result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ConversationSummary:
    """
    Lightweight projection used by list_direct_conversations().

    Carries the fields needed to render a conversation list item without
    extra round-trips.  Phase 5.8.3 will serialise this into a Pydantic
    response schema.
    """

    conversation_id: str
    updated_at: datetime
    other_user_id: str
    latest_message_id: Optional[str]
    latest_message_content: Optional[str]
    latest_message_at: Optional[datetime]
    latest_message_sender_id: Optional[str]
    unread_count: int


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _require_accepted_connection(db: Session, user_a_id: str, user_b_id: str) -> None:
    """
    Raise 403 unless an ACCEPTED connection exists between the two users.
    Uses the canonical-pair lookup from connection_service (direction-independent).
    """
    conn: Connection | None = get_connection_between_users(db, user_a_id, user_b_id)
    if conn is None or conn.status != ConnectionStatus.accepted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must have an accepted connection with this user to message them.",
        )


def _get_other_participant_id(db: Session, conversation_id: str, current_user_id: str) -> str:
    """Return the ID of the other participant in a two-person conversation."""
    rows = (
        db.query(DirectConversationParticipant.user_id)
        .filter(DirectConversationParticipant.conversation_id == conversation_id)
        .all()
    )
    for (uid,) in rows:
        if uid != current_user_id:
            return uid
    # Defensive — should never happen for a valid two-party conversation
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Conversation is malformed: could not find the other participant.",
    )


def _require_participant(db: Session, conversation_id: str, user: User) -> None:
    """Raise 403 if *user* is not a participant of *conversation_id*."""
    row = (
        db.query(DirectConversationParticipant)
        .filter_by(conversation_id=conversation_id, user_id=user.id)
        .first()
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a participant of this conversation.",
        )


# ---------------------------------------------------------------------------
# 1. get_or_create_direct_conversation
# ---------------------------------------------------------------------------


def get_or_create_direct_conversation(
    db: Session,
    current_user: User,
    other_user_id: str,
) -> DirectConversation:
    """
    Return the existing conversation between current_user and other_user, or
    create one if none exists.

    Rules enforced
    ──────────────
    - Self-messaging is rejected (400).
    - The other user must exist in the database (404).
    - An ACCEPTED connection must exist between the two users (403).
    - Concurrent creation is handled safely via the DB unique constraint:
      if an IntegrityError is raised, the existing conversation is returned.
    - Exactly two DirectConversationParticipant rows are created.
    - Canonical pair ordering matches Connection.canonical_pair().

    Raises:
        400  — self-messaging attempt.
        403  — no accepted connection.
        404  — other user does not exist.
    """
    if current_user.id == other_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot start a conversation with yourself.",
        )

    # Resolve the other user.
    other_user: User | None = db.query(User).filter(User.id == other_user_id).first()
    if other_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    # Enforce accepted connection before any write.
    _require_accepted_connection(db, current_user.id, other_user_id)

    # Check for an existing conversation (canonical-pair lookup).
    ca, cb = DirectConversation.canonical_pair(current_user.id, other_user_id)
    existing = (
        db.query(DirectConversation)
        .filter_by(canonical_a=ca, canonical_b=cb)
        .first()
    )
    if existing is not None:
        return existing

    # Create new conversation + two participants.
    # Participants are inserted via Core INSERT (not the ORM) to avoid a
    # psycopg3 + SQLAlchemy composite-PK RETURNING bug that emits only
    # (user_id) in the INSERT column list, leaving conversation_id NULL.
        # Create new conversation + two participants.
    conv = DirectConversation(canonical_a=ca, canonical_b=cb)
    db.add(conv)

    try:
        db.flush()  # persist conv so conv.id is available for participant rows

        now = datetime.now(timezone.utc)
        db.execute(
            sa_insert(DirectConversationParticipant),
            [
                {"conversation_id": conv.id, "user_id": current_user.id, "joined_at": now},
                {"conversation_id": conv.id, "user_id": other_user_id,   "joined_at": now},
            ],
        )

        db.commit()
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(DirectConversation)
            .filter_by(canonical_a=ca, canonical_b=cb)
            .first()
        )
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create or retrieve conversation. Please retry.",
            )
        return existing

    db.refresh(conv)
    return conv
    


# ---------------------------------------------------------------------------
# 2. get_direct_conversation_for_user
# ---------------------------------------------------------------------------


def get_direct_conversation_for_user(
    db: Session,
    conversation_id: str,
    current_user: User,
) -> DirectConversation:
    """
    Retrieve a conversation by ID and verify the current user is a participant.

    Raises:
        404  — conversation does not exist.
        403  — current user is not a participant.
    """
    conv = db.query(DirectConversation).filter_by(id=conversation_id).first()
    if conv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )
    _require_participant(db, conversation_id, current_user)
    return conv


# ---------------------------------------------------------------------------
# 3. send_direct_message
# ---------------------------------------------------------------------------


def send_direct_message(
    db: Session,
    conversation_id: str,
    sender: User,
    content: str,
) -> DirectMessage:
    """
    Persist a new message in the conversation.

    Rules enforced
    ──────────────
    - Conversation must exist and sender must be a participant (403/404).
    - The two participants must still share an ACCEPTED connection (403).
    - Content must be non-empty after stripping surrounding whitespace (400).
    - Content may not exceed DM_MAX_CONTENT_CHARS characters (400).
    - delivered_at and read_at are intentionally left NULL at creation;
      delivery is confirmed by the WebSocket layer in Phase 5.8.3+.
    - conversation.updated_at is refreshed so the conversation list
      reflects the latest activity.

    Raises:
        400  — empty/whitespace-only content, or content too long.
        403  — sender not a participant, or no accepted connection.
        404  — conversation not found.
    """
    # Existence + participant check.
    conv = get_direct_conversation_for_user(db, conversation_id, sender)

    # Validate content (strip surrounding whitespace; preserve internal).
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

    # Enforce accepted connection for NEW messages even if the conversation exists.
    other_user_id = _get_other_participant_id(db, conversation_id, sender.id)
    _require_accepted_connection(db, sender.id, other_user_id)

    # Create the message — delivered_at and read_at start as NULL.
    msg = DirectMessage(
        conversation_id=conversation_id,
        sender_id=sender.id,
        content=stripped,
    )
    db.add(msg)

    # Touch conversation.updated_at so the conversation list stays ordered.
    conv.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(msg)
    return msg


# ---------------------------------------------------------------------------
# 4. list_direct_messages
# ---------------------------------------------------------------------------


def list_direct_messages(
    db: Session,
    conversation_id: str,
    current_user: User,
    limit: int = 50,
    offset: int = 0,
) -> list[DirectMessage]:
    """
    Return messages for a conversation in stable chronological order (oldest first).

    Pagination is offset-based (consistent with the rest of the project).
    The caller should request reasonable page sizes; the default of 50 is
    suitable for most chat UIs.

    Raises:
        403  — current user is not a participant.
        404  — conversation not found.
    """
    # Authorization: must be a participant.
    get_direct_conversation_for_user(db, conversation_id, current_user)

    return (
        db.query(DirectMessage)
        .filter(DirectMessage.conversation_id == conversation_id)
        .order_by(DirectMessage.created_at.asc(), DirectMessage.id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )


# ---------------------------------------------------------------------------
# 5. mark_messages_delivered
# ---------------------------------------------------------------------------


def mark_messages_delivered(
    db: Session,
    conversation_id: str,
    current_user: User,
) -> int:
    """
    Mark as delivered all messages in the conversation that were sent by the
    OTHER participant and whose delivered_at is still NULL.

    Returns the number of rows updated (0 if already all delivered).
    This operation is idempotent.

    Rules
    ─────
    - current_user must be a participant (403/404).
    - Only messages sent by the OTHER user are touched; the sender's own
      messages are never self-delivered.
    - Uses the current UTC timestamp for delivered_at.

    Raises:
        403  — not a participant.
        404  — conversation not found.
    """
    # Authorization.
    get_direct_conversation_for_user(db, conversation_id, current_user)

    now = datetime.now(timezone.utc)
    updated = (
        db.query(DirectMessage)
        .filter(
            DirectMessage.conversation_id == conversation_id,
            DirectMessage.sender_id != current_user.id,
            DirectMessage.delivered_at == None,  # noqa: E711
        )
        .update({"delivered_at": now}, synchronize_session="fetch")
    )
    db.commit()
    return updated


# ---------------------------------------------------------------------------
# 6. mark_messages_read
# ---------------------------------------------------------------------------


def mark_messages_read(
    db: Session,
    conversation_id: str,
    current_user: User,
) -> int:
    """
    Mark as read all messages sent by the OTHER participant that have not yet
    been read.  If a message is being read but was not yet delivered, both
    timestamps are set atomically.

    Invariant: read_at != NULL  ⟹  delivered_at != NULL

    Returns the number of messages whose read_at was updated.
    This operation is idempotent.

    Rules
    ─────
    - current_user must be a participant (403/404).
    - Only messages from the other user are affected.
    - Messages already read (read_at IS NOT NULL) are left unchanged.

    Raises:
        403  — not a participant.
        404  — conversation not found.
    """
    get_direct_conversation_for_user(db, conversation_id, current_user)

    now = datetime.now(timezone.utc)

    # Mark both delivered_at and read_at for messages that have neither.
    db.query(DirectMessage).filter(
        DirectMessage.conversation_id == conversation_id,
        DirectMessage.sender_id != current_user.id,
        DirectMessage.read_at == None,   # noqa: E711
        DirectMessage.delivered_at == None,  # noqa: E711
    ).update({"delivered_at": now, "read_at": now}, synchronize_session="fetch")

    # Mark only read_at for messages already delivered but not yet read.
    updated = (
        db.query(DirectMessage)
        .filter(
            DirectMessage.conversation_id == conversation_id,
            DirectMessage.sender_id != current_user.id,
            DirectMessage.read_at == None,   # noqa: E711
            DirectMessage.delivered_at != None,  # noqa: E711
        )
        .update({"read_at": now}, synchronize_session="fetch")
    )

    db.commit()
    return updated


# ---------------------------------------------------------------------------
# 7. get_unread_count
# ---------------------------------------------------------------------------


def get_unread_count(
    db: Session,
    current_user: User,
) -> int:
    """
    Return the total number of unread messages across ALL conversations
    the current user participates in.

    Only messages sent by the OTHER participant that have read_at IS NULL
    are counted.  The user's own messages are never counted.

    Uses the (conversation_id, read_at) composite index created in 007_messaging.
    """
    # Subquery: conversation IDs the user participates in.
    my_convs = (
        db.query(DirectConversationParticipant.conversation_id)
        .filter(DirectConversationParticipant.user_id == current_user.id)
        .scalar_subquery()
    )

    count = (
        db.query(func.count(DirectMessage.id))
        .filter(
            DirectMessage.conversation_id.in_(my_convs),
            DirectMessage.sender_id != current_user.id,
            DirectMessage.read_at == None,  # noqa: E711
        )
        .scalar()
    )
    return count or 0


# ---------------------------------------------------------------------------
# 8. list_direct_conversations
# ---------------------------------------------------------------------------


def list_direct_conversations(
    db: Session,
    current_user: User,
    limit: int = 20,
    offset: int = 0,
) -> list[ConversationSummary]:
    """
    Return a paginated list of conversation summaries for the current user,
    ordered by most recent activity (updated_at DESC).

    Each summary includes:
      - conversation_id
      - updated_at
      - other_user_id
      - latest_message_id, latest_message_content, latest_message_at,
        latest_message_sender_id
      - unread_count (messages from the other user with read_at IS NULL)

    Query strategy — avoids N+1
    ────────────────────────────
    1. Fetch the paginated conversation IDs in updated_at order via a
       join to direct_conversation_participants (one query).
    2. Fetch all participant rows for those IDs (one query).
    3. Fetch the latest message per conversation using a subquery with
       MAX(created_at) then a join (one query).
    4. Fetch per-conversation unread counts using a GROUP BY (one query).

    Total: 4 queries regardless of the number of conversations returned.
    """
    # ── Step 1: paginated conversation IDs ──────────────────────────────
    conv_rows = (
        db.query(DirectConversation)
        .join(
            DirectConversationParticipant,
            DirectConversationParticipant.conversation_id == DirectConversation.id,
        )
        .filter(DirectConversationParticipant.user_id == current_user.id)
        .order_by(DirectConversation.updated_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    if not conv_rows:
        return []

    conv_ids = [c.id for c in conv_rows]

    # ── Step 2: all participant rows for these conversations ─────────────
    all_participants = (
        db.query(DirectConversationParticipant)
        .filter(DirectConversationParticipant.conversation_id.in_(conv_ids))
        .all()
    )
    # Map: conversation_id → other_user_id
    other_user_map: dict[str, str] = {}
    for p in all_participants:
        if p.user_id != current_user.id:
            other_user_map[p.conversation_id] = p.user_id

    # ── Step 3: latest message per conversation ──────────────────────────
    # Subquery: MAX(created_at) per conversation_id among the target IDs.
    latest_ts_sub = (
        db.query(
            DirectMessage.conversation_id,
            func.max(DirectMessage.created_at).label("max_created"),
        )
        .filter(DirectMessage.conversation_id.in_(conv_ids))
        .group_by(DirectMessage.conversation_id)
        .subquery()
    )
    latest_msgs = (
        db.query(DirectMessage)
        .join(
            latest_ts_sub,
            (DirectMessage.conversation_id == latest_ts_sub.c.conversation_id)
            & (DirectMessage.created_at == latest_ts_sub.c.max_created),
        )
        .all()
    )
    # Map: conversation_id → DirectMessage (take first if tie at same timestamp)
    latest_msg_map: dict[str, DirectMessage] = {}
    for msg in latest_msgs:
        if msg.conversation_id not in latest_msg_map:
            latest_msg_map[msg.conversation_id] = msg

    # ── Step 4: unread counts ────────────────────────────────────────────
    unread_rows = (
        db.query(
            DirectMessage.conversation_id,
            func.count(DirectMessage.id).label("cnt"),
        )
        .filter(
            DirectMessage.conversation_id.in_(conv_ids),
            DirectMessage.sender_id != current_user.id,
            DirectMessage.read_at == None,  # noqa: E711
        )
        .group_by(DirectMessage.conversation_id)
        .all()
    )
    unread_map: dict[str, int] = {cid: cnt for cid, cnt in unread_rows}

    # ── Assemble results ─────────────────────────────────────────────────
    results: list[ConversationSummary] = []
    for conv in conv_rows:
        lm = latest_msg_map.get(conv.id)
        results.append(
            ConversationSummary(
                conversation_id=conv.id,
                updated_at=conv.updated_at,
                other_user_id=other_user_map.get(conv.id, ""),
                latest_message_id=lm.id if lm else None,
                latest_message_content=lm.content if lm else None,
                latest_message_at=lm.created_at if lm else None,
                latest_message_sender_id=lm.sender_id if lm else None,
                unread_count=unread_map.get(conv.id, 0),
            )
        )
    return results
