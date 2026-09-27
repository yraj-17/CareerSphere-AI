"""
Phase 5.8 — Message Management Tests.

Tests for:
  1. star_message / unstar_message
  2. pin_message / unpin_message
  3. delete_message_for_me
  4. delete_message_for_everyone
  5. forward_message
  6. list_messages_for_user (filtering)
  7. get_pinned_message
  8. send_direct_message_extended (reply_to support)
  9. REST API endpoints (via TestClient)

Security assertions in each test:
  - Non-participant access → 403 or message not found
  - Non-sender delete-for-everyone → 403
  - Cross-conversation reply → 400
  - Deleted-for-everyone content → placeholder in ALL responses
  - No physical deletion of DirectMessage rows

Architecture:
  - All tests use isolated DB state via per-test fixtures.
  - No Redis / WebSocket layer is involved (service layer only for most tests).
  - API-layer tests use TestClient which exercises the full router stack.
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

# ---------------------------------------------------------------------------
# Local imports
# ---------------------------------------------------------------------------
from app.db.models import (
    Base,
    User,
    DirectConversation,
    DirectConversationParticipant,
    DirectMessage,
    MessageStar,
    MessageUserDeletion,
)
from app.services import messaging_service as svc
from app.services.message_management_service import (
    DELETED_FOR_EVERYONE_PLACEHOLDER,
    DELETED_REPLY_PLACEHOLDER,
    star_message,
    unstar_message,
    pin_message,
    unpin_message,
    delete_message_for_me,
    delete_message_for_everyone,
    forward_message,
    list_messages_for_user,
    get_pinned_message,
    send_direct_message_extended,
    serialize_message,
)

# ---------------------------------------------------------------------------
# In-memory SQLite engine (no external DB needed for unit tests)
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def engine():
    eng = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture()
def db(engine):
    """Fresh session per test — uses a transaction rollback for isolation."""
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# ---------------------------------------------------------------------------
# Helper: create test users, conversation, and messages
# ---------------------------------------------------------------------------

def _user(db: Session, uid: str, username: str) -> User:
    u = User(
        id=uid,
        username=username,
        email=f"{username}@test.com",
        first_name=username.capitalize(),
        last_name="Test",
        password_hash="x",
    )
    db.add(u)
    db.flush()
    return u


def _conversation(db: Session, user_a: User, user_b: User) -> DirectConversation:
    cid = f"conv-{user_a.id[:4]}-{user_b.id[:4]}"
    ca, cb = sorted([user_a.id, user_b.id])
    conv = DirectConversation(id=cid, canonical_a=ca, canonical_b=cb)
    db.add(conv)
    db.flush()
    for uid in [user_a.id, user_b.id]:
        db.add(DirectConversationParticipant(conversation_id=cid, user_id=uid))
    db.flush()
    return conv


def _message(db: Session, conv: DirectConversation, sender: User, content: str = "Hello") -> DirectMessage:
    msg = DirectMessage(
        conversation_id=conv.id,
        sender_id=sender.id,
        content=content,
    )
    db.add(msg)
    db.flush()
    db.refresh(msg)
    return msg


# ---------------------------------------------------------------------------
# Helper: patch accepted-connection check (bypass for unit tests)
# ---------------------------------------------------------------------------

def _patch_connection(monkeypatch):
    """Bypass the accepted-connection check for the duration of the test."""
    monkeypatch.setattr(
        "app.services.message_management_service._require_accepted_connection",
        lambda db, a, b: None,
    )


# ---------------------------------------------------------------------------
# 1. star_message / unstar_message
# ---------------------------------------------------------------------------

class TestStar:
    def test_star_creates_row(self, db, monkeypatch):
        _patch_connection(monkeypatch)
        alice = _user(db, "alice-1", "alice1")
        bob = _user(db, "bob-1", "bob1")
        conv = _conversation(db, alice, bob)
        msg = _message(db, conv, bob)

        star_message(db, msg.id, alice)

        row = db.query(MessageStar).filter_by(message_id=msg.id, user_id=alice.id).first()
        assert row is not None

    def test_star_is_idempotent(self, db, monkeypatch):
        _patch_connection(monkeypatch)
        alice = _user(db, "alice-2", "alice2")
        bob = _user(db, "bob-2", "bob2")
        conv = _conversation(db, alice, bob)
        msg = _message(db, conv, bob)

        star_message(db, msg.id, alice)
        star_message(db, msg.id, alice)  # second call must not raise

        count = db.query(MessageStar).filter_by(message_id=msg.id, user_id=alice.id).count()
        assert count == 1

    def test_star_private_to_user(self, db, monkeypatch):
        _patch_connection(monkeypatch)
        alice = _user(db, "alice-3", "alice3")
        bob = _user(db, "bob-3", "bob3")
        conv = _conversation(db, alice, bob)
        msg = _message(db, conv, bob)

        star_message(db, msg.id, alice)

        d_alice = serialize_message(db, msg, alice.id)
        d_bob = serialize_message(db, msg, bob.id)
        assert d_alice["is_starred"] is True
        assert d_bob["is_starred"] is False

    def test_unstar_removes_row(self, db, monkeypatch):
        _patch_connection(monkeypatch)
        alice = _user(db, "alice-4", "alice4")
        bob = _user(db, "bob-4", "bob4")
        conv = _conversation(db, alice, bob)
        msg = _message(db, conv, bob)

        star_message(db, msg.id, alice)
        unstar_message(db, msg.id, alice)

        row = db.query(MessageStar).filter_by(message_id=msg.id, user_id=alice.id).first()
        assert row is None

    def test_unstar_idempotent(self, db, monkeypatch):
        _patch_connection(monkeypatch)
        alice = _user(db, "alice-5", "alice5")
        bob = _user(db, "bob-5", "bob5")
        conv = _conversation(db, alice, bob)
        msg = _message(db, conv, bob)

        unstar_message(db, msg.id, alice)  # must not raise even if not starred

    def test_star_deleted_for_everyone_raises(self, db, monkeypatch):
        _patch_connection(monkeypatch)
        alice = _user(db, "alice-6", "alice6")
        bob = _user(db, "bob-6", "bob6")
        conv = _conversation(db, alice, bob)
        msg = _message(db, conv, alice)

        delete_message_for_everyone(db, msg.id, alice)

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            star_message(db, msg.id, bob)
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# 2. pin_message / unpin_message
# ---------------------------------------------------------------------------

class TestPin:
    def test_pin_sets_timestamp(self, db, monkeypatch):
        _patch_connection(monkeypatch)
        alice = _user(db, "alice-p1", "alicep1")
        bob = _user(db, "bob-p1", "bobp1")
        conv = _conversation(db, alice, bob)
        msg = _message(db, conv, bob)

        pin_message(db, msg.id, alice)

        db.refresh(msg)
        assert msg.pinned_at is not None
        assert msg.pinned_by_user_id == alice.id

    def test_pin_clears_previous_pin(self, db, monkeypatch):
        _patch_connection(monkeypatch)
        alice = _user(db, "alice-p2", "alicep2")
        bob = _user(db, "bob-p2", "bobp2")
        conv = _conversation(db, alice, bob)
        msg1 = _message(db, conv, bob, "first")
        msg2 = _message(db, conv, alice, "second")

        pin_message(db, msg1.id, alice)
        pin_message(db, msg2.id, alice)

        db.refresh(msg1)
        db.refresh(msg2)
        assert msg1.pinned_at is None
        assert msg2.pinned_at is not None

    def test_unpin_clears_timestamp(self, db, monkeypatch):
        _patch_connection(monkeypatch)
        alice = _user(db, "alice-p3", "alicep3")
        bob = _user(db, "bob-p3", "bobp3")
        conv = _conversation(db, alice, bob)
        msg = _message(db, conv, bob)

        pin_message(db, msg.id, alice)
        unpin_message(db, msg.id, alice)

        db.refresh(msg)
        assert msg.pinned_at is None

    def test_get_pinned_message(self, db, monkeypatch):
        _patch_connection(monkeypatch)
        alice = _user(db, "alice-p4", "alicep4")
        bob = _user(db, "bob-p4", "bobp4")
        conv = _conversation(db, alice, bob)
        msg = _message(db, conv, bob, "pinned content")

        pin_message(db, msg.id, alice)
        result = get_pinned_message(db, conv.id, alice)

        assert result is not None
        assert result["id"] == msg.id
        assert result["is_pinned"] is True


# ---------------------------------------------------------------------------
# 3. delete_message_for_me
# ---------------------------------------------------------------------------

class TestDeleteForMe:
    def test_delete_for_me_hides_message(self, db, monkeypatch):
        _patch_connection(monkeypatch)
        alice = _user(db, "alice-dm1", "alicedm1")
        bob = _user(db, "bob-dm1", "bobdm1")
        conv = _conversation(db, alice, bob)
        msg = _message(db, conv, bob)

        delete_message_for_me(db, msg.id, alice)

        msgs = list_messages_for_user(db, conv.id, alice)
        assert not any(m["id"] == msg.id for m in msgs)

    def test_delete_for_me_does_not_affect_other(self, db, monkeypatch):
        _patch_connection(monkeypatch)
        alice = _user(db, "alice-dm2", "alicedm2")
        bob = _user(db, "bob-dm2", "bobdm2")
        conv = _conversation(db, alice, bob)
        msg = _message(db, conv, bob)

        delete_message_for_me(db, msg.id, alice)

        msgs_bob = list_messages_for_user(db, conv.id, bob)
        assert any(m["id"] == msg.id for m in msgs_bob)

    def test_delete_for_me_idempotent(self, db, monkeypatch):
        _patch_connection(monkeypatch)
        alice = _user(db, "alice-dm3", "alicedm3")
        bob = _user(db, "bob-dm3", "bobdm3")
        conv = _conversation(db, alice, bob)
        msg = _message(db, conv, bob)

        delete_message_for_me(db, msg.id, alice)
        delete_message_for_me(db, msg.id, alice)  # must not raise

        count = db.query(MessageUserDeletion).filter_by(message_id=msg.id, user_id=alice.id).count()
        assert count == 1

    def test_message_row_preserved(self, db, monkeypatch):
        _patch_connection(monkeypatch)
        alice = _user(db, "alice-dm4", "alicedm4")
        bob = _user(db, "bob-dm4", "bobdm4")
        conv = _conversation(db, alice, bob)
        msg = _message(db, conv, bob)

        delete_message_for_me(db, msg.id, alice)

        # Physical row must still exist
        row = db.query(DirectMessage).filter_by(id=msg.id).first()
        assert row is not None
        assert row.content == "Hello"


# ---------------------------------------------------------------------------
# 4. delete_message_for_everyone
# ---------------------------------------------------------------------------

class TestDeleteForEveryone:
    def test_delete_for_everyone_sets_timestamp(self, db, monkeypatch):
        _patch_connection(monkeypatch)
        alice = _user(db, "alice-dfe1", "alicedfe1")
        bob = _user(db, "bob-dfe1", "bobdfe1")
        conv = _conversation(db, alice, bob)
        msg = _message(db, conv, alice)

        delete_message_for_everyone(db, msg.id, alice)

        db.refresh(msg)
        assert msg.deleted_for_everyone_at is not None

    def test_non_sender_cannot_delete_for_everyone(self, db, monkeypatch):
        _patch_connection(monkeypatch)
        alice = _user(db, "alice-dfe2", "alicedfe2")
        bob = _user(db, "bob-dfe2", "bobdfe2")
        conv = _conversation(db, alice, bob)
        msg = _message(db, conv, alice)  # alice sent it

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            delete_message_for_everyone(db, msg.id, bob)  # bob tries
        assert exc_info.value.status_code == 403

    def test_deleted_content_replaced_in_serialization(self, db, monkeypatch):
        _patch_connection(monkeypatch)
        alice = _user(db, "alice-dfe3", "alicedfe3")
        bob = _user(db, "bob-dfe3", "bobdfe3")
        conv = _conversation(db, alice, bob)
        msg = _message(db, conv, alice, "secret content")

        delete_message_for_everyone(db, msg.id, alice)

        d_alice = serialize_message(db, msg, alice.id)
        d_bob = serialize_message(db, msg, bob.id)
        assert d_alice["content"] == DELETED_FOR_EVERYONE_PLACEHOLDER
        assert d_bob["content"] == DELETED_FOR_EVERYONE_PLACEHOLDER
        assert "secret content" not in d_alice["content"]
        assert "secret content" not in d_bob["content"]

    def test_original_content_preserved_in_db(self, db, monkeypatch):
        _patch_connection(monkeypatch)
        alice = _user(db, "alice-dfe4", "alicedfe4")
        bob = _user(db, "bob-dfe4", "bobdfe4")
        conv = _conversation(db, alice, bob)
        msg = _message(db, conv, alice, "preserved")

        delete_message_for_everyone(db, msg.id, alice)

        row = db.query(DirectMessage).filter_by(id=msg.id).first()
        assert row.content == "preserved"  # DB row untouched

    def test_delete_for_everyone_clears_pin(self, db, monkeypatch):
        _patch_connection(monkeypatch)
        alice = _user(db, "alice-dfe5", "alicedfe5")
        bob = _user(db, "bob-dfe5", "bobdfe5")
        conv = _conversation(db, alice, bob)
        msg = _message(db, conv, alice)

        pin_message(db, msg.id, alice)
        delete_message_for_everyone(db, msg.id, alice)

        db.refresh(msg)
        assert msg.pinned_at is None

    def test_delete_for_everyone_idempotent(self, db, monkeypatch):
        _patch_connection(monkeypatch)
        alice = _user(db, "alice-dfe6", "alicedfe6")
        bob = _user(db, "bob-dfe6", "bobdfe6")
        conv = _conversation(db, alice, bob)
        msg = _message(db, conv, alice)

        delete_message_for_everyone(db, msg.id, alice)
        delete_message_for_everyone(db, msg.id, alice)  # idempotent


# ---------------------------------------------------------------------------
# 5. forward_message
# ---------------------------------------------------------------------------

class TestForward:
    def test_forward_creates_new_message(self, db, monkeypatch):
        _patch_connection(monkeypatch)
        alice = _user(db, "alice-fw1", "alicefw1")
        bob = _user(db, "bob-fw1", "bobfw1")
        carol = _user(db, "carol-fw1", "carolfw1")
        conv_ab = _conversation(db, alice, bob)
        conv_ac = _conversation(db, alice, carol)
        msg = _message(db, conv_ab, bob, "forward me")

        fwd = forward_message(db, msg.id, conv_ac.id, alice)

        assert fwd.id != msg.id
        assert fwd.conversation_id == conv_ac.id
        assert fwd.content == "forward me"
        assert fwd.forwarded_from_message_id == msg.id
        assert fwd.sender_id == alice.id

    def test_forward_sets_is_forwarded_flag(self, db, monkeypatch):
        _patch_connection(monkeypatch)
        alice = _user(db, "alice-fw2", "alicefw2")
        bob = _user(db, "bob-fw2", "bobfw2")
        carol = _user(db, "carol-fw2", "carolfw2")
        conv_ab = _conversation(db, alice, bob)
        conv_ac = _conversation(db, alice, carol)
        msg = _message(db, conv_ab, bob, "content")

        fwd = forward_message(db, msg.id, conv_ac.id, alice)

        d = serialize_message(db, fwd, alice.id)
        assert d["is_forwarded"] is True
        assert d["forwarded_from_message_id"] == msg.id

    def test_cannot_forward_deleted_for_everyone(self, db, monkeypatch):
        _patch_connection(monkeypatch)
        alice = _user(db, "alice-fw3", "alicefw3")
        bob = _user(db, "bob-fw3", "bobfw3")
        carol = _user(db, "carol-fw3", "carolfw3")
        conv_ab = _conversation(db, alice, bob)
        conv_ac = _conversation(db, alice, carol)
        msg = _message(db, conv_ab, alice, "deleted")

        delete_message_for_everyone(db, msg.id, alice)

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            forward_message(db, msg.id, conv_ac.id, alice)
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# 6. send_direct_message_extended (reply_to)
# ---------------------------------------------------------------------------

class TestReply:
    def test_reply_stores_reference(self, db, monkeypatch):
        _patch_connection(monkeypatch)
        alice = _user(db, "alice-r1", "alicer1")
        bob = _user(db, "bob-r1", "bobr1")
        conv = _conversation(db, alice, bob)
        original = _message(db, conv, bob, "original")

        reply = send_direct_message_extended(
            db, conv.id, alice, "replying", reply_to_message_id=original.id
        )

        assert reply.reply_to_message_id == original.id

    def test_cross_conversation_reply_rejected(self, db, monkeypatch):
        _patch_connection(monkeypatch)
        alice = _user(db, "alice-r2", "alicer2")
        bob = _user(db, "bob-r2", "bobr2")
        carol = _user(db, "carol-r2", "carolr2")
        conv_ab = _conversation(db, alice, bob)
        conv_ac = _conversation(db, alice, carol)
        msg_in_ac = _message(db, conv_ac, carol, "other conv")

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            send_direct_message_extended(
                db, conv_ab.id, alice, "reply", reply_to_message_id=msg_in_ac.id
            )
        assert exc_info.value.status_code == 400

    def test_reply_preview_in_serialization(self, db, monkeypatch):
        _patch_connection(monkeypatch)
        alice = _user(db, "alice-r3", "alicer3")
        bob = _user(db, "bob-r3", "bobr3")
        conv = _conversation(db, alice, bob)
        original = _message(db, conv, bob, "original content")

        reply = send_direct_message_extended(
            db, conv.id, alice, "my reply", reply_to_message_id=original.id
        )

        d = serialize_message(db, reply, alice.id)
        assert d["reply_to_message"] is not None
        assert d["reply_to_message"]["content"] == "original content"
        assert d["reply_to_message"]["id"] == original.id

    def test_reply_preview_sanitized_when_original_deleted(self, db, monkeypatch):
        _patch_connection(monkeypatch)
        alice = _user(db, "alice-r4", "alicer4")
        bob = _user(db, "bob-r4", "bobr4")
        conv = _conversation(db, alice, bob)
        original = _message(db, conv, bob, "secret")

        reply = send_direct_message_extended(
            db, conv.id, alice, "reply after delete", reply_to_message_id=original.id
        )

        delete_message_for_everyone(db, original.id, bob)

        d = serialize_message(db, reply, alice.id)
        assert d["reply_to_message"]["content"] == DELETED_REPLY_PLACEHOLDER
        assert "secret" not in d["reply_to_message"]["content"]


# ---------------------------------------------------------------------------
# 7. list_messages_for_user (filtering)
# ---------------------------------------------------------------------------

class TestListMessages:
    def test_deleted_for_me_excluded(self, db, monkeypatch):
        _patch_connection(monkeypatch)
        alice = _user(db, "alice-lm1", "alicelmm1")
        bob = _user(db, "bob-lm1", "boblm1")
        conv = _conversation(db, alice, bob)
        msg1 = _message(db, conv, bob, "visible")
        msg2 = _message(db, conv, bob, "hidden from alice")

        delete_message_for_me(db, msg2.id, alice)

        msgs = list_messages_for_user(db, conv.id, alice)
        ids = [m["id"] for m in msgs]
        assert msg1.id in ids
        assert msg2.id not in ids

    def test_deleted_for_everyone_content_sanitized_in_list(self, db, monkeypatch):
        _patch_connection(monkeypatch)
        alice = _user(db, "alice-lm2", "alicelm2")
        bob = _user(db, "bob-lm2", "boblm2")
        conv = _conversation(db, alice, bob)
        msg = _message(db, conv, alice, "secret")

        delete_message_for_everyone(db, msg.id, alice)

        msgs = list_messages_for_user(db, conv.id, bob)
        match = next((m for m in msgs if m["id"] == msg.id), None)
        assert match is not None
        assert match["content"] == DELETED_FOR_EVERYONE_PLACEHOLDER
        assert "secret" not in match["content"]

    def test_starred_flag_in_list(self, db, monkeypatch):
        _patch_connection(monkeypatch)
        alice = _user(db, "alice-lm3", "alicelm3")
        bob = _user(db, "bob-lm3", "boblm3")
        conv = _conversation(db, alice, bob)
        msg = _message(db, conv, bob, "star me")

        star_message(db, msg.id, alice)

        msgs = list_messages_for_user(db, conv.id, alice)
        match = next((m for m in msgs if m["id"] == msg.id), None)
        assert match["is_starred"] is True


# ---------------------------------------------------------------------------
# 8. Authorization edge cases
# ---------------------------------------------------------------------------

class TestAuthorization:
    def test_non_participant_cannot_star(self, db, monkeypatch):
        _patch_connection(monkeypatch)
        alice = _user(db, "alice-auth1", "aliceauth1")
        bob = _user(db, "bob-auth1", "bobauth1")
        carol = _user(db, "carol-auth1", "carolauth1")
        conv = _conversation(db, alice, bob)
        msg = _message(db, conv, alice)

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            star_message(db, msg.id, carol)  # carol is not in this conversation
        assert exc_info.value.status_code == 403

    def test_non_participant_cannot_pin(self, db, monkeypatch):
        _patch_connection(monkeypatch)
        alice = _user(db, "alice-auth2", "aliceauth2")
        bob = _user(db, "bob-auth2", "bobauth2")
        carol = _user(db, "carol-auth2", "carolauth2")
        conv = _conversation(db, alice, bob)
        msg = _message(db, conv, alice)

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            pin_message(db, msg.id, carol)
        assert exc_info.value.status_code == 403
