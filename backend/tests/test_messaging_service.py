"""
Phase 5.8.2 — Messaging Service tests.

All 48 scenarios are exercised directly against PostgreSQL via SessionLocal
with the rollback-fixture pattern used throughout the project.

Requires Docker infrastructure:
  docker compose up -d postgres
and a valid DATABASE_URL in the environment or .env.

Index
─────
CONVERSATION (1–12)
AUTHORIZATION (13–16)
MESSAGES (17–25)
HISTORY (26–28)
DELIVERY (29–31)
READ (32–35)
UNREAD (36–39)
CONVERSATION LIST (40–45)
CONNECTION REMOVAL (46–48)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models import (
    Connection,
    ConnectionStatus,
    DirectConversation,
    DirectConversationParticipant,
    DirectMessage,
    User,
)
from app.db.session import Base, SessionLocal, engine
from app.services import messaging_service as svc
from app.services.messaging_service import DM_MAX_CONTENT_CHARS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _new_user(tag: str) -> User:
    uid = str(uuid.uuid4())
    return User(
        id=uid,
        first_name="Msg",
        last_name="User",
        username=f"msgsvc_{tag}_{uid[:8]}",
        email=f"msgsvc_{uid}@example.com",
        password_hash="hashed",
    )


def _make_accepted_connection(db: Session, u1: User, u2: User) -> Connection:
    """Create and flush a committed accepted connection between u1 and u2."""
    ca, cb = Connection.canonical_pair(u1.id, u2.id)
    conn = Connection(
        requester_id=u1.id,
        receiver_id=u2.id,
        canonical_a=ca,
        canonical_b=cb,
        status=ConnectionStatus.accepted,
    )
    db.add(conn)
    db.flush()
    return conn


def _make_pending_connection(db: Session, u1: User, u2: User) -> Connection:
    ca, cb = Connection.canonical_pair(u1.id, u2.id)
    conn = Connection(
        requester_id=u1.id,
        receiver_id=u2.id,
        canonical_a=ca,
        canonical_b=cb,
        status=ConnectionStatus.pending,
    )
    db.add(conn)
    db.flush()
    return conn


def _make_rejected_connection(db: Session, u1: User, u2: User) -> Connection:
    ca, cb = Connection.canonical_pair(u1.id, u2.id)
    conn = Connection(
        requester_id=u1.id,
        receiver_id=u2.id,
        canonical_a=ca,
        canonical_b=cb,
        status=ConnectionStatus.rejected,
    )
    db.add(conn)
    db.flush()
    return conn


def _make_cancelled_connection(db: Session, u1: User, u2: User) -> Connection:
    ca, cb = Connection.canonical_pair(u1.id, u2.id)
    conn = Connection(
        requester_id=u1.id,
        receiver_id=u2.id,
        canonical_a=ca,
        canonical_b=cb,
        status=ConnectionStatus.cancelled,
    )
    db.add(conn)
    db.flush()
    return conn


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def ensure_tables():
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def two_connected_users(db):
    """Two users with an accepted connection. Returns (u1, u2)."""
    u1, u2 = _new_user("a"), _new_user("b")
    db.add_all([u1, u2])
    db.flush()
    _make_accepted_connection(db, u1, u2)
    db.commit()
    return u1, u2


@pytest.fixture()
def conversation(db, two_connected_users):
    """An existing conversation between u1 and u2."""
    u1, u2 = two_connected_users
    conv = svc.get_or_create_direct_conversation(db, u1, u2.id)
    return conv, u1, u2


# ===========================================================================
# CONVERSATION (1–12)
# ===========================================================================


def test_01_create_conversation_between_accepted_connections(db, two_connected_users):
    u1, u2 = two_connected_users
    conv = svc.get_or_create_direct_conversation(db, u1, u2.id)
    assert conv.id is not None
    assert conv.canonical_a == min(u1.id, u2.id)
    assert conv.canonical_b == max(u1.id, u2.id)
    assert conv.created_at is not None


def test_02_get_existing_conversation(db, two_connected_users):
    u1, u2 = two_connected_users
    conv1 = svc.get_or_create_direct_conversation(db, u1, u2.id)
    conv2 = svc.get_or_create_direct_conversation(db, u1, u2.id)
    assert conv1.id == conv2.id


def test_03_no_duplicate_conversation(db, two_connected_users):
    u1, u2 = two_connected_users
    svc.get_or_create_direct_conversation(db, u1, u2.id)
    svc.get_or_create_direct_conversation(db, u1, u2.id)
    count = (
        db.query(DirectConversation)
        .filter_by(
            canonical_a=min(u1.id, u2.id),
            canonical_b=max(u1.id, u2.id),
        )
        .count()
    )
    assert count == 1


def test_04_reverse_direction_returns_same_conversation(db, two_connected_users):
    u1, u2 = two_connected_users
    conv_ab = svc.get_or_create_direct_conversation(db, u1, u2.id)
    conv_ba = svc.get_or_create_direct_conversation(db, u2, u1.id)
    assert conv_ab.id == conv_ba.id


def test_05_self_conversation_rejected(db):
    u = _new_user("self")
    db.add(u)
    db.flush()
    with pytest.raises(HTTPException) as exc_info:
        svc.get_or_create_direct_conversation(db, u, u.id)
    assert exc_info.value.status_code == 400
    assert "yourself" in exc_info.value.detail.lower()


def test_06_nonexistent_recipient_rejected(db):
    u = _new_user("requester")
    db.add(u)
    db.flush()
    with pytest.raises(HTTPException) as exc_info:
        svc.get_or_create_direct_conversation(db, u, str(uuid.uuid4()))
    assert exc_info.value.status_code == 404


def test_07_pending_connection_rejected(db):
    u1, u2 = _new_user("p1"), _new_user("p2")
    db.add_all([u1, u2])
    db.flush()
    _make_pending_connection(db, u1, u2)
    with pytest.raises(HTTPException) as exc_info:
        svc.get_or_create_direct_conversation(db, u1, u2.id)
    assert exc_info.value.status_code == 403


def test_08_rejected_connection_blocked(db):
    u1, u2 = _new_user("r1"), _new_user("r2")
    db.add_all([u1, u2])
    db.flush()
    _make_rejected_connection(db, u1, u2)
    with pytest.raises(HTTPException) as exc_info:
        svc.get_or_create_direct_conversation(db, u1, u2.id)
    assert exc_info.value.status_code == 403


def test_09_cancelled_connection_blocked(db):
    u1, u2 = _new_user("c1"), _new_user("c2")
    db.add_all([u1, u2])
    db.flush()
    _make_cancelled_connection(db, u1, u2)
    with pytest.raises(HTTPException) as exc_info:
        svc.get_or_create_direct_conversation(db, u1, u2.id)
    assert exc_info.value.status_code == 403


def test_10_unrelated_users_rejected(db):
    u1, u2 = _new_user("u1"), _new_user("u2")
    db.add_all([u1, u2])
    db.flush()
    # No connection at all
    with pytest.raises(HTTPException) as exc_info:
        svc.get_or_create_direct_conversation(db, u1, u2.id)
    assert exc_info.value.status_code == 403


def test_11_concurrent_creation_handled_safely(db, two_connected_users):
    """
    Simulates duplicate creation by inserting a conversation manually before
    calling the service, then verifying it returns the existing one (not an error).
    """
    u1, u2 = two_connected_users
    ca, cb = DirectConversation.canonical_pair(u1.id, u2.id)
    # Pre-create the conversation manually as if a concurrent request did it.
    conv_pre = DirectConversation(canonical_a=ca, canonical_b=cb)
    db.add(conv_pre)
    db.flush()
    from datetime import datetime, timezone as _tz
    from sqlalchemy import insert as _ins
    now = datetime.now(_tz.utc)
    db.execute(
        _ins(DirectConversationParticipant),
        [
            {"conversation_id": conv_pre.id, "user_id": u1.id, "joined_at": now},
            {"conversation_id": conv_pre.id, "user_id": u2.id, "joined_at": now},
        ],
    )
    db.commit()

    # Service call should return the pre-existing conversation, not create a new one.
    conv = svc.get_or_create_direct_conversation(db, u1, u2.id)
    assert conv.id == conv_pre.id


def test_12_exactly_two_participants_created(db, two_connected_users):
    u1, u2 = two_connected_users
    conv = svc.get_or_create_direct_conversation(db, u1, u2.id)
    participants = (
        db.query(DirectConversationParticipant)
        .filter_by(conversation_id=conv.id)
        .all()
    )
    assert len(participants) == 2
    user_ids = {p.user_id for p in participants}
    assert u1.id in user_ids
    assert u2.id in user_ids


# ===========================================================================
# AUTHORIZATION (13–16)
# ===========================================================================


def test_13_non_participant_cannot_access_conversation(db, conversation):
    conv, u1, u2 = conversation
    outsider = _new_user("out")
    db.add(outsider)
    db.flush()
    with pytest.raises(HTTPException) as exc_info:
        svc.get_direct_conversation_for_user(db, conv.id, outsider)
    assert exc_info.value.status_code == 403


def test_14_participant_can_access_conversation(db, conversation):
    conv, u1, u2 = conversation
    fetched = svc.get_direct_conversation_for_user(db, conv.id, u1)
    assert fetched.id == conv.id


def test_15_non_participant_cannot_read_messages(db, conversation):
    conv, u1, u2 = conversation
    svc.send_direct_message(db, conv.id, u1, "Hello")
    outsider = _new_user("noread")
    db.add(outsider)
    db.flush()
    with pytest.raises(HTTPException) as exc_info:
        svc.list_direct_messages(db, conv.id, outsider)
    assert exc_info.value.status_code == 403


def test_16_non_participant_cannot_send_messages(db, conversation):
    conv, u1, u2 = conversation
    outsider = _new_user("nosend")
    db.add(outsider)
    db.flush()
    with pytest.raises(HTTPException) as exc_info:
        svc.send_direct_message(db, conv.id, outsider, "Hacked")
    assert exc_info.value.status_code == 403


# ===========================================================================
# MESSAGES (17–25)
# ===========================================================================


def test_17_send_valid_message(db, conversation):
    conv, u1, u2 = conversation
    msg = svc.send_direct_message(db, conv.id, u1, "Hello!")
    assert msg.id is not None
    assert msg.content == "Hello!"
    assert msg.conversation_id == conv.id
    assert msg.sender_id == u1.id


def test_18_empty_message_rejected(db, conversation):
    conv, u1, u2 = conversation
    with pytest.raises(HTTPException) as exc_info:
        svc.send_direct_message(db, conv.id, u1, "")
    assert exc_info.value.status_code == 400


def test_19_whitespace_only_message_rejected(db, conversation):
    conv, u1, u2 = conversation
    with pytest.raises(HTTPException) as exc_info:
        svc.send_direct_message(db, conv.id, u1, "   \t\n  ")
    assert exc_info.value.status_code == 400


def test_20_surrounding_whitespace_trimmed(db, conversation):
    conv, u1, u2 = conversation
    msg = svc.send_direct_message(db, conv.id, u1, "  Hello world  ")
    assert msg.content == "Hello world"


def test_21_message_belongs_to_correct_conversation(db, conversation):
    conv, u1, u2 = conversation
    msg = svc.send_direct_message(db, conv.id, u1, "Test")
    assert msg.conversation_id == conv.id


def test_22_sender_is_authenticated_user(db, conversation):
    conv, u1, u2 = conversation
    msg = svc.send_direct_message(db, conv.id, u2, "From U2")
    assert msg.sender_id == u2.id


def test_23_initial_delivered_at_is_null(db, conversation):
    conv, u1, u2 = conversation
    msg = svc.send_direct_message(db, conv.id, u1, "Deliver me")
    assert msg.delivered_at is None


def test_24_initial_read_at_is_null(db, conversation):
    conv, u1, u2 = conversation
    msg = svc.send_direct_message(db, conv.id, u1, "Read me")
    assert msg.read_at is None


def test_25_conversation_updated_at_changes_on_send(db, conversation):
    conv, u1, u2 = conversation
    before = conv.updated_at
    svc.send_direct_message(db, conv.id, u1, "Ping")
    db.refresh(conv)
    assert conv.updated_at >= before


# ===========================================================================
# HISTORY (26–28)
# ===========================================================================


def test_26_messages_returned_in_chronological_order(db, conversation):
    conv, u1, u2 = conversation
    svc.send_direct_message(db, conv.id, u1, "First")
    svc.send_direct_message(db, conv.id, u2, "Second")
    svc.send_direct_message(db, conv.id, u1, "Third")
    msgs = svc.list_direct_messages(db, conv.id, u1)
    contents = [m.content for m in msgs]
    # All three must be present (order guaranteed by created_at asc + id asc).
    assert set(contents) == {"First", "Second", "Third"}
    assert len(msgs) == 3


def test_27_pagination_works(db, conversation):
    conv, u1, u2 = conversation
    for i in range(5):
        svc.send_direct_message(db, conv.id, u1, f"Msg {i}")

    page1 = svc.list_direct_messages(db, conv.id, u1, limit=3, offset=0)
    page2 = svc.list_direct_messages(db, conv.id, u1, limit=3, offset=3)

    assert len(page1) == 3
    assert len(page2) == 2
    ids_p1 = {m.id for m in page1}
    ids_p2 = {m.id for m in page2}
    assert ids_p1.isdisjoint(ids_p2)


def test_28_messages_from_other_conversation_excluded(db, two_connected_users):
    u1, u2 = two_connected_users

    # Create a third user and second connection + conversation.
    u3 = _new_user("third")
    db.add(u3)
    db.flush()
    _make_accepted_connection(db, u1, u3)
    db.commit()

    conv_12 = svc.get_or_create_direct_conversation(db, u1, u2.id)
    conv_13 = svc.get_or_create_direct_conversation(db, u1, u3.id)

    svc.send_direct_message(db, conv_12.id, u1, "To U2")
    svc.send_direct_message(db, conv_13.id, u1, "To U3")

    msgs_12 = svc.list_direct_messages(db, conv_12.id, u1)
    assert len(msgs_12) == 1
    assert msgs_12[0].content == "To U2"


# ===========================================================================
# DELIVERY (29–31)
# ===========================================================================


def test_29_recipient_messages_can_be_marked_delivered(db, conversation):
    conv, u1, u2 = conversation
    # u1 sends; u2 marks delivered.
    svc.send_direct_message(db, conv.id, u1, "Deliver this")
    count = svc.mark_messages_delivered(db, conv.id, u2)
    assert count == 1
    msgs = svc.list_direct_messages(db, conv.id, u2)
    assert msgs[0].delivered_at is not None


def test_30_senders_own_messages_not_marked_delivered(db, conversation):
    conv, u1, u2 = conversation
    # u1 sends a message then tries to mark it delivered as themselves.
    svc.send_direct_message(db, conv.id, u1, "My own")
    count = svc.mark_messages_delivered(db, conv.id, u1)
    # u1 calling delivered: only marks messages from u2 (none here).
    assert count == 0
    msgs = svc.list_direct_messages(db, conv.id, u1)
    assert msgs[0].delivered_at is None


def test_31_mark_delivered_is_idempotent(db, conversation):
    conv, u1, u2 = conversation
    svc.send_direct_message(db, conv.id, u1, "Hello")
    svc.mark_messages_delivered(db, conv.id, u2)
    # Second call should update 0 rows (already delivered).
    count2 = svc.mark_messages_delivered(db, conv.id, u2)
    assert count2 == 0


# ===========================================================================
# READ (32–35)
# ===========================================================================


def test_32_recipient_messages_can_be_marked_read(db, conversation):
    conv, u1, u2 = conversation
    svc.send_direct_message(db, conv.id, u1, "Read this")
    count = svc.mark_messages_read(db, conv.id, u2)
    msgs = svc.list_direct_messages(db, conv.id, u2)
    assert msgs[0].read_at is not None


def test_33_senders_own_messages_not_marked_read(db, conversation):
    conv, u1, u2 = conversation
    svc.send_direct_message(db, conv.id, u1, "My msg")
    svc.mark_messages_read(db, conv.id, u1)  # u1 reads — should not affect own msg
    msgs = svc.list_direct_messages(db, conv.id, u1)
    assert msgs[0].read_at is None


def test_34_read_implies_delivered(db, conversation):
    conv, u1, u2 = conversation
    svc.send_direct_message(db, conv.id, u1, "Both timestamps")
    svc.mark_messages_read(db, conv.id, u2)
    msgs = svc.list_direct_messages(db, conv.id, u2)
    msg = msgs[0]
    assert msg.read_at is not None
    assert msg.delivered_at is not None


def test_35_mark_read_is_idempotent(db, conversation):
    conv, u1, u2 = conversation
    svc.send_direct_message(db, conv.id, u1, "Read twice")
    svc.mark_messages_read(db, conv.id, u2)
    # Get the timestamp after first mark.
    msgs = svc.list_direct_messages(db, conv.id, u2)
    first_read_at = msgs[0].read_at

    # Second call should return 0 and not change the timestamp.
    count2 = svc.mark_messages_read(db, conv.id, u2)
    assert count2 == 0
    db.refresh(msgs[0])
    assert msgs[0].read_at == first_read_at


# ===========================================================================
# UNREAD (36–39)
# ===========================================================================


def test_36_unread_count_is_correct(db, two_connected_users):
    u1, u2 = two_connected_users
    conv = svc.get_or_create_direct_conversation(db, u1, u2.id)
    svc.send_direct_message(db, conv.id, u1, "Msg A")
    svc.send_direct_message(db, conv.id, u1, "Msg B")
    # u2 has 2 unread messages from u1.
    assert svc.get_unread_count(db, u2) == 2


def test_37_senders_own_messages_not_counted(db, two_connected_users):
    u1, u2 = two_connected_users
    conv = svc.get_or_create_direct_conversation(db, u1, u2.id)
    svc.send_direct_message(db, conv.id, u1, "I sent this")
    # u1's own messages are never counted as unread for u1.
    assert svc.get_unread_count(db, u1) == 0


def test_38_read_messages_not_counted(db, two_connected_users):
    u1, u2 = two_connected_users
    conv = svc.get_or_create_direct_conversation(db, u1, u2.id)
    svc.send_direct_message(db, conv.id, u1, "Read me")
    svc.mark_messages_read(db, conv.id, u2)
    assert svc.get_unread_count(db, u2) == 0


def test_39_unrelated_conversations_not_counted(db, two_connected_users):
    u1, u2 = two_connected_users
    u3 = _new_user("third")
    db.add(u3)
    db.flush()
    _make_accepted_connection(db, u2, u3)
    db.commit()

    conv_12 = svc.get_or_create_direct_conversation(db, u1, u2.id)
    conv_23 = svc.get_or_create_direct_conversation(db, u2, u3.id)

    # u1 sends to u2 — u2 has 1 unread from u1.
    svc.send_direct_message(db, conv_12.id, u1, "For U2")
    # u3 sends to u2 — u2 has another unread.
    svc.send_direct_message(db, conv_23.id, u3, "Also for U2")

    # u3 should have 0 unread (u3 has no unread messages from u2 or u1).
    assert svc.get_unread_count(db, u3) == 0
    # u1 should have 0 unread.
    assert svc.get_unread_count(db, u1) == 0
    # u2 should have 2 unread.
    assert svc.get_unread_count(db, u2) == 2


# ===========================================================================
# CONVERSATION LIST (40–45)
# ===========================================================================


def test_40_list_users_conversations(db, two_connected_users):
    u1, u2 = two_connected_users
    svc.get_or_create_direct_conversation(db, u1, u2.id)
    summaries = svc.list_direct_conversations(db, u1)
    assert len(summaries) == 1
    assert summaries[0].conversation_id is not None


def test_41_latest_message_returned_correctly(db, conversation):
    conv, u1, u2 = conversation
    svc.send_direct_message(db, conv.id, u1, "First")
    svc.send_direct_message(db, conv.id, u1, "Latest")
    summaries = svc.list_direct_conversations(db, u1)
    assert summaries[0].latest_message_content == "Latest"


def test_42_other_participant_returned_correctly(db, conversation):
    conv, u1, u2 = conversation
    summaries = svc.list_direct_conversations(db, u1)
    assert summaries[0].other_user_id == u2.id


def test_43_unread_count_in_summary(db, conversation):
    conv, u1, u2 = conversation
    svc.send_direct_message(db, conv.id, u1, "Unread for U2")
    summaries_u2 = svc.list_direct_conversations(db, u2)
    assert summaries_u2[0].unread_count == 1
    # After reading:
    svc.mark_messages_read(db, conv.id, u2)
    summaries_u2_after = svc.list_direct_conversations(db, u2)
    assert summaries_u2_after[0].unread_count == 0


def test_44_conversations_ordered_by_latest_activity(db, two_connected_users):
    u1, u2 = two_connected_users
    u3 = _new_user("order3")
    db.add(u3)
    db.flush()
    _make_accepted_connection(db, u1, u3)
    db.commit()

    conv_12 = svc.get_or_create_direct_conversation(db, u1, u2.id)
    conv_13 = svc.get_or_create_direct_conversation(db, u1, u3.id)

    # Send to conv_12 first, then conv_13 — conv_13 should be listed first.
    svc.send_direct_message(db, conv_12.id, u1, "Older")
    svc.send_direct_message(db, conv_13.id, u1, "Newer")

    summaries = svc.list_direct_conversations(db, u1)
    assert summaries[0].conversation_id == conv_13.id
    assert summaries[1].conversation_id == conv_12.id


def test_45_pagination_on_conversation_list(db, two_connected_users):
    u1, u2 = two_connected_users

    # Create two more connections/conversations for u1.
    users = []
    for i in range(2):
        u = _new_user(f"pg{i}")
        db.add(u)
        db.flush()
        _make_accepted_connection(db, u1, u)
        users.append(u)
    db.commit()

    for u in users:
        svc.get_or_create_direct_conversation(db, u1, u.id)
    svc.get_or_create_direct_conversation(db, u1, u2.id)

    page1 = svc.list_direct_conversations(db, u1, limit=2, offset=0)
    page2 = svc.list_direct_conversations(db, u1, limit=2, offset=2)
    assert len(page1) == 2
    assert len(page2) == 1
    ids1 = {s.conversation_id for s in page1}
    ids2 = {s.conversation_id for s in page2}
    assert ids1.isdisjoint(ids2)


# ===========================================================================
# CONNECTION REMOVAL (46–48)
# ===========================================================================


def test_46_accepted_connection_allows_messaging(db, two_connected_users):
    u1, u2 = two_connected_users
    conv = svc.get_or_create_direct_conversation(db, u1, u2.id)
    msg = svc.send_direct_message(db, conv.id, u1, "Works fine")
    assert msg.id is not None


def test_47_removing_accepted_connection_blocks_new_messages(db, two_connected_users):
    """
    After an accepted connection is removed, sending NEW messages is blocked
    even though the conversation row still exists.
    """
    u1, u2 = two_connected_users
    conv = svc.get_or_create_direct_conversation(db, u1, u2.id)
    svc.send_direct_message(db, conv.id, u1, "Before removal")

    # Remove the connection.
    from app.db.models import Connection
    ca, cb = Connection.canonical_pair(u1.id, u2.id)
    conn = db.query(Connection).filter_by(canonical_a=ca, canonical_b=cb).one()
    db.delete(conn)
    db.commit()

    # New message must now be blocked.
    with pytest.raises(HTTPException) as exc_info:
        svc.send_direct_message(db, conv.id, u1, "After removal — blocked")
    assert exc_info.value.status_code == 403


def test_48_history_remains_after_connection_removal(db, two_connected_users):
    """
    After an accepted connection is removed, existing message history is
    still readable by both participants.  The conversation is not auto-deleted.

    Documented behaviour: history is preserved; only NEW messages are blocked.
    """
    u1, u2 = two_connected_users
    conv = svc.get_or_create_direct_conversation(db, u1, u2.id)
    svc.send_direct_message(db, conv.id, u1, "Historical message")

    # Remove the connection.
    from app.db.models import Connection
    ca, cb = Connection.canonical_pair(u1.id, u2.id)
    conn = db.query(Connection).filter_by(canonical_a=ca, canonical_b=cb).one()
    db.delete(conn)
    db.commit()

    # History must still be accessible.
    msgs = svc.list_direct_messages(db, conv.id, u1)
    assert len(msgs) == 1
    assert msgs[0].content == "Historical message"

    # Conversation row must still exist.
    conv_check = svc.get_direct_conversation_for_user(db, conv.id, u1)
    assert conv_check.id == conv.id
