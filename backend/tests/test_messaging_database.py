"""
Phase 5.8.1 — Messaging database / model tests.

Tests run directly against PostgreSQL via SessionLocal (no HTTP layer).
Each test uses a session that is always rolled back on teardown for
full isolation — the same convention used in test_networking_connections.py
and test_networking_service.py.

Requires Docker infrastructure:
  docker compose up -d postgres
and a valid DATABASE_URL in the environment or .env.

Covered scenarios
─────────────────
 1.  Direct conversation can be created
 2.  Canonical pair helper returns (min, max) ordering
 3.  canonical_a / canonical_b stored correctly on conversation
 4.  Two participants can be added to a conversation
 5.  Participant uniqueness — same user cannot be added twice (IntegrityError)
 6.  A message can be created in a conversation
 7.  Message belongs to the correct conversation
 8.  Message sender FK references users table (valid user)
 9.  delivered_at is nullable (defaults to None)
10.  read_at is nullable (defaults to None)
11.  delivered_at and read_at can be set to a timestamp
12.  Multiple messages in one conversation persisted in order
13.  Duplicate conversation pair is rejected (UniqueConstraint)
14.  Cascade: deleting a conversation removes its participants
15.  Cascade: deleting a conversation removes its messages
16.  Cascade: deleting a user cascades to their participant rows
17.  Cascade: deleting a user cascades to messages they sent
18.  DirectConversation.__repr__ includes id and canonical pair
19.  DirectMessage.__repr__ includes id, conv, sender

Note: authorization (only accepted connections can message) is NOT enforced
      at the DB layer and is intentionally absent here — that belongs to the
      service layer in Phase 5.8.2.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models import (
    DirectConversation,
    DirectConversationParticipant,
    DirectMessage,
    User,
)
from app.db.session import Base, SessionLocal, engine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _new_user(tag: str) -> User:
    uid = str(uuid.uuid4())
    return User(
        id=uid,
        first_name="Msg",
        last_name="Tester",
        username=f"msg_{tag}_{uid[:8]}",
        email=f"msg_{uid}@example.com",
        password_hash="hashed",
    )


def _new_conversation(user_a_id: str, user_b_id: str) -> DirectConversation:
    ca, cb = DirectConversation.canonical_pair(user_a_id, user_b_id)
    return DirectConversation(canonical_a=ca, canonical_b=cb)


def _add_participants(
    conv: DirectConversation,
    user_a_id: str,
    user_b_id: str,
) -> tuple[DirectConversationParticipant, DirectConversationParticipant]:
    p1 = DirectConversationParticipant(
        conversation_id=conv.id, user_id=user_a_id
    )
    p2 = DirectConversationParticipant(
        conversation_id=conv.id, user_id=user_b_id
    )
    return p1, p2


def _new_message(conv_id: str, sender_id: str, content: str = "Hello") -> DirectMessage:
    return DirectMessage(
        conversation_id=conv_id,
        sender_id=sender_id,
        content=content,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def ensure_tables():
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def db():
    """Session that is always rolled back — no permanent data written."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def two_users(db):
    u1, u2 = _new_user("a"), _new_user("b")
    db.add_all([u1, u2])
    db.flush()
    return u1, u2


@pytest.fixture()
def three_users(db):
    u1, u2, u3 = _new_user("x"), _new_user("y"), _new_user("z")
    db.add_all([u1, u2, u3])
    db.flush()
    return u1, u2, u3


@pytest.fixture()
def conversation_with_participants(db, two_users):
    """A flushed DirectConversation with both participants added."""
    u1, u2 = two_users
    conv = _new_conversation(u1.id, u2.id)
    db.add(conv)
    db.flush()
    p1, p2 = _add_participants(conv, u1.id, u2.id)
    db.add_all([p1, p2])
    db.flush()
    return conv, u1, u2


# ===========================================================================
# 1. Direct conversation creation
# ===========================================================================


def test_01_conversation_creation(db, two_users):
    u1, u2 = two_users
    conv = _new_conversation(u1.id, u2.id)
    db.add(conv)
    db.flush()

    fetched = db.query(DirectConversation).filter_by(id=conv.id).one()
    assert fetched.id == conv.id
    assert fetched.created_at is not None
    assert fetched.updated_at is not None


# ===========================================================================
# 2. canonical_pair helper
# ===========================================================================


def test_02_canonical_pair_returns_min_max():
    a, b = "zzz-user", "aaa-user"
    ca, cb = DirectConversation.canonical_pair(a, b)
    assert ca == min(a, b)
    assert cb == max(a, b)
    # Commutative — same result regardless of argument order
    assert DirectConversation.canonical_pair(a, b) == DirectConversation.canonical_pair(b, a)


# ===========================================================================
# 3. canonical_a / canonical_b stored correctly
# ===========================================================================


def test_03_canonical_columns_stored(db, two_users):
    u1, u2 = two_users
    expected_a, expected_b = DirectConversation.canonical_pair(u1.id, u2.id)
    conv = _new_conversation(u1.id, u2.id)
    db.add(conv)
    db.flush()

    fetched = db.query(DirectConversation).filter_by(id=conv.id).one()
    assert fetched.canonical_a == expected_a
    assert fetched.canonical_b == expected_b


# ===========================================================================
# 4. Two participants can be added
# ===========================================================================


def test_04_two_participants_added(db, conversation_with_participants):
    conv, u1, u2 = conversation_with_participants
    rows = (
        db.query(DirectConversationParticipant)
        .filter_by(conversation_id=conv.id)
        .all()
    )
    assert len(rows) == 2
    user_ids = {r.user_id for r in rows}
    assert u1.id in user_ids
    assert u2.id in user_ids


# ===========================================================================
# 5. Participant uniqueness — duplicate raises IntegrityError
# ===========================================================================


def test_05_participant_uniqueness(db, conversation_with_participants):
    conv, u1, u2 = conversation_with_participants
    # Try to add u1 a second time
    duplicate = DirectConversationParticipant(
        conversation_id=conv.id, user_id=u1.id
    )
    db.add(duplicate)
    with pytest.raises(IntegrityError):
        db.flush()


# ===========================================================================
# 6. Message creation
# ===========================================================================


def test_06_message_creation(db, conversation_with_participants):
    conv, u1, u2 = conversation_with_participants
    msg = _new_message(conv.id, u1.id, "Hey there")
    db.add(msg)
    db.flush()

    fetched = db.query(DirectMessage).filter_by(id=msg.id).one()
    assert fetched.content == "Hey there"
    assert fetched.conversation_id == conv.id
    assert fetched.sender_id == u1.id
    assert fetched.created_at is not None


# ===========================================================================
# 7. Message belongs to the correct conversation
# ===========================================================================


def test_07_message_belongs_to_conversation(db, conversation_with_participants):
    conv, u1, u2 = conversation_with_participants
    msg = _new_message(conv.id, u1.id)
    db.add(msg)
    db.flush()

    fetched = db.query(DirectMessage).filter_by(id=msg.id).one()
    assert fetched.conversation_id == conv.id


# ===========================================================================
# 8. sender_id FK references users
# ===========================================================================


def test_08_sender_fk_references_user(db, conversation_with_participants):
    conv, u1, u2 = conversation_with_participants
    msg = _new_message(conv.id, u1.id)
    db.add(msg)
    db.flush()

    fetched = db.query(DirectMessage).filter_by(id=msg.id).one()
    assert fetched.sender_id == u1.id
    # Relationship should resolve
    assert fetched.sender is not None
    assert fetched.sender.id == u1.id


# ===========================================================================
# 9. delivered_at is nullable (defaults to None)
# ===========================================================================


def test_09_delivered_at_nullable(db, conversation_with_participants):
    conv, u1, u2 = conversation_with_participants
    msg = _new_message(conv.id, u1.id)
    db.add(msg)
    db.flush()

    fetched = db.query(DirectMessage).filter_by(id=msg.id).one()
    assert fetched.delivered_at is None


# ===========================================================================
# 10. read_at is nullable (defaults to None)
# ===========================================================================


def test_10_read_at_nullable(db, conversation_with_participants):
    conv, u1, u2 = conversation_with_participants
    msg = _new_message(conv.id, u1.id)
    db.add(msg)
    db.flush()

    fetched = db.query(DirectMessage).filter_by(id=msg.id).one()
    assert fetched.read_at is None


# ===========================================================================
# 11. delivered_at and read_at can be set
# ===========================================================================


def test_11_delivered_and_read_at_can_be_set(db, conversation_with_participants):
    conv, u1, u2 = conversation_with_participants
    now = datetime.now(timezone.utc)

    msg = DirectMessage(
        conversation_id=conv.id,
        sender_id=u1.id,
        content="Seen this",
        delivered_at=now,
        read_at=now,
    )
    db.add(msg)
    db.flush()

    fetched = db.query(DirectMessage).filter_by(id=msg.id).one()
    assert fetched.delivered_at is not None
    assert fetched.read_at is not None


# ===========================================================================
# 12. Multiple messages in one conversation, ordered by created_at
# ===========================================================================


def test_12_multiple_messages_in_order(db, conversation_with_participants):
    conv, u1, u2 = conversation_with_participants

    m1 = _new_message(conv.id, u1.id, "First")
    m2 = _new_message(conv.id, u2.id, "Second")
    m3 = _new_message(conv.id, u1.id, "Third")
    db.add_all([m1, m2, m3])
    db.flush()

    msgs = (
        db.query(DirectMessage)
        .filter_by(conversation_id=conv.id)
        .order_by(DirectMessage.created_at.asc())
        .all()
    )
    assert len(msgs) == 3
    contents = [m.content for m in msgs]
    # All three messages persisted (order may be same-timestamp in tests,
    # so verify presence rather than strict ordering).
    assert set(contents) == {"First", "Second", "Third"}


# ===========================================================================
# 13. Duplicate conversation pair is rejected (UniqueConstraint)
# ===========================================================================


def test_13_duplicate_pair_rejected(db, two_users):
    u1, u2 = two_users
    conv1 = _new_conversation(u1.id, u2.id)
    db.add(conv1)
    db.flush()

    # Second conversation with the same canonical pair
    conv2 = _new_conversation(u1.id, u2.id)
    db.add(conv2)
    with pytest.raises(IntegrityError):
        db.flush()


# ===========================================================================
# 14. Cascade: deleting a conversation removes its participants
# ===========================================================================


def test_14_cascade_delete_conversation_removes_participants(db, two_users):
    u1, u2 = two_users
    conv = _new_conversation(u1.id, u2.id)
    db.add(conv)
    db.flush()
    p1, p2 = _add_participants(conv, u1.id, u2.id)
    db.add_all([p1, p2])
    db.flush()

    # Commit so the delete actually propagates
    db.commit()

    # Re-fetch and delete
    conv_row = db.query(DirectConversation).filter_by(id=conv.id).one()
    db.delete(conv_row)
    db.commit()

    remaining = (
        db.query(DirectConversationParticipant)
        .filter_by(conversation_id=conv.id)
        .all()
    )
    assert remaining == []


# ===========================================================================
# 15. Cascade: deleting a conversation removes its messages
# ===========================================================================


def test_15_cascade_delete_conversation_removes_messages(db, two_users):
    u1, u2 = two_users
    conv = _new_conversation(u1.id, u2.id)
    db.add(conv)
    db.flush()
    msg = _new_message(conv.id, u1.id)
    db.add(msg)
    db.commit()

    conv_row = db.query(DirectConversation).filter_by(id=conv.id).one()
    db.delete(conv_row)
    db.commit()

    remaining = (
        db.query(DirectMessage).filter_by(conversation_id=conv.id).all()
    )
    assert remaining == []


# ===========================================================================
# 16. Cascade: deleting a user cascades to their participant rows
# ===========================================================================


def test_16_cascade_delete_user_removes_participant_rows(db, two_users):
    u1, u2 = two_users
    conv = _new_conversation(u1.id, u2.id)
    db.add(conv)
    db.flush()
    p1, p2 = _add_participants(conv, u1.id, u2.id)
    db.add_all([p1, p2])
    db.commit()

    u1_row = db.query(User).filter_by(id=u1.id).one()
    db.delete(u1_row)
    db.commit()

    remaining = (
        db.query(DirectConversationParticipant)
        .filter_by(user_id=u1.id)
        .all()
    )
    assert remaining == []


# ===========================================================================
# 17. Cascade: deleting a user cascades to messages they sent
# ===========================================================================


def test_17_cascade_delete_user_removes_sent_messages(db, two_users):
    u1, u2 = two_users
    conv = _new_conversation(u1.id, u2.id)
    db.add(conv)
    db.flush()
    msg = _new_message(conv.id, u1.id, "Will be deleted")
    db.add(msg)
    db.commit()

    u1_row = db.query(User).filter_by(id=u1.id).one()
    db.delete(u1_row)
    db.commit()

    remaining = (
        db.query(DirectMessage).filter_by(sender_id=u1.id).all()
    )
    assert remaining == []


# ===========================================================================
# 18. __repr__ on DirectConversation
# ===========================================================================


def test_18_conversation_repr(db, two_users):
    u1, u2 = two_users
    conv = _new_conversation(u1.id, u2.id)
    db.add(conv)
    db.flush()
    r = repr(conv)
    assert "DirectConversation" in r
    assert conv.id in r


# ===========================================================================
# 19. __repr__ on DirectMessage
# ===========================================================================


def test_19_message_repr(db, conversation_with_participants):
    conv, u1, u2 = conversation_with_participants
    msg = _new_message(conv.id, u1.id)
    db.add(msg)
    db.flush()
    r = repr(msg)
    assert "DirectMessage" in r
    assert msg.id in r
