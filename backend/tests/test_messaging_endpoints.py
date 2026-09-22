"""
Phase 5.8.3 — Messaging REST API tests.

Tests exercise every messaging endpoint through the FastAPI TestClient against
a real PostgreSQL + Redis database.  The test pattern exactly mirrors
test_networking_api.py: register users via /api/auth/register (with a
Redis-seeded OTP token), log in, then hit the messaging endpoints.

Requires Docker infrastructure:
  docker compose up -d postgres redis
and valid DATABASE_URL / REDIS_URL in the environment or .env.

Test index
──────────
AUTHENTICATION (1–6)
CONVERSATION CREATE (7–14)
CONVERSATION LIST (15–20)
MESSAGES — send + history (21–29)
UNREAD COUNT (26–29)
DELIVERED (30–33)
READ (34–37)
REGRESSION (38–40)
"""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import or_

from app.db.models import Connection, ConnectionStatus, User
from app.db.session import Base, SessionLocal, engine
from app.db.redis_client import redis_client
from app.core.config import settings
from app.main import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# Helpers — identical pattern to test_networking_api.py
# ---------------------------------------------------------------------------

_CTR = 0


def _unique_tag() -> str:
    global _CTR
    _CTR += 1
    return f"{_CTR}_{uuid.uuid4().hex[:6]}"


def _seed_otp(email: str) -> str:
    token = f"test-token-{uuid.uuid4().hex}"
    token_hash = hashlib.sha256(
        f"{email}:{token}:{settings.SECRET_KEY}".encode()
    ).hexdigest()
    payload = json.dumps({"otp": "123456", "verified_token": token_hash, "token_raw": token})
    redis_client.set(f"otp:{email}", payload, ex=600)
    return token


def _register_user(tag: Optional[str] = None) -> dict:
    if tag is None:
        tag = _unique_tag()
    email = f"msgapi_{tag}@example.com"
    username = f"msgapi_{tag}"[:30]
    res = client.post("/api/auth/register", json={
        "first_name": "Msg",
        "last_name": "User",
        "username": username,
        "email": email,
        "password": "Password123",
        "email_verification_token": _seed_otp(email),
    })
    assert res.status_code == 201, f"Register failed: {res.text}"
    uid = res.json()["id"]
    login = client.post("/api/auth/login", json={
        "identifier": username, "password": "Password123"
    })
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {
        "user_id": uid, "username": username, "email": email,
        "headers": {"Authorization": f"Bearer {token}"},
    }


def _cleanup_users(*emails: str) -> None:
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.email.in_(emails)).all()
        ids = [u.id for u in users]
        if ids:
            db.query(Connection).filter(
                or_(Connection.requester_id.in_(ids), Connection.receiver_id.in_(ids))
            ).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(ids)).delete(synchronize_session=False)
            db.commit()
    finally:
        db.close()


def _make_accepted_connection(user_a: dict, user_b: dict) -> str:
    """Send + accept a connection between user_a and user_b. Returns conn_id."""
    send = client.post(
        f"/api/networking/connections/{user_b['user_id']}",
        headers=user_a["headers"],
    )
    assert send.status_code == 201, send.text
    conn_id = send.json()["id"]
    accept = client.post(
        f"/api/networking/requests/{conn_id}/accept",
        headers=user_b["headers"],
    )
    assert accept.status_code == 200
    return conn_id


def _open_conversation(user_a: dict, user_b: dict) -> str:
    """Open a conversation between already-connected users. Returns conv_id."""
    res = client.post(
        f"/api/messaging/conversations/{user_b['user_id']}",
        headers=user_a["headers"],
    )
    assert res.status_code == 200, res.text
    return res.json()["id"]


def _send_message(user: dict, conv_id: str, content: str = "Hello") -> dict:
    res = client.post(
        f"/api/messaging/conversations/{conv_id}/messages",
        json={"content": content},
        headers=user["headers"],
    )
    assert res.status_code == 201, res.text
    return res.json()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def ensure_tables():
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def user_a():
    u = _register_user()
    yield u
    _cleanup_users(u["email"])


@pytest.fixture()
def user_b():
    u = _register_user()
    yield u
    _cleanup_users(u["email"])


@pytest.fixture()
def user_c():
    u = _register_user()
    yield u
    _cleanup_users(u["email"])


@pytest.fixture()
def connected_pair(user_a, user_b):
    """user_a and user_b with an accepted connection."""
    _make_accepted_connection(user_a, user_b)
    return user_a, user_b


@pytest.fixture()
def open_conversation(connected_pair):
    """An open conversation between user_a and user_b."""
    user_a, user_b = connected_pair
    conv_id = _open_conversation(user_a, user_b)
    return conv_id, user_a, user_b


# ===========================================================================
# AUTHENTICATION (1–6)
# ===========================================================================


def test_01_unauthenticated_conversation_create_rejected():
    res = client.post("/api/messaging/conversations/some-id")
    assert res.status_code == 401


def test_02_unauthenticated_conversation_list_rejected():
    res = client.get("/api/messaging/conversations")
    assert res.status_code == 401


def test_03_unauthenticated_message_history_rejected():
    res = client.get("/api/messaging/conversations/some-id/messages")
    assert res.status_code == 401


def test_04_unauthenticated_unread_count_rejected():
    res = client.get("/api/messaging/unread-count")
    assert res.status_code == 401


def test_05_unauthenticated_delivered_rejected():
    res = client.post("/api/messaging/conversations/some-id/delivered")
    assert res.status_code == 401


def test_06_unauthenticated_read_rejected():
    res = client.post("/api/messaging/conversations/some-id/read")
    assert res.status_code == 401


# ===========================================================================
# CONVERSATION CREATE (7–14)
# ===========================================================================


def test_07_accepted_connection_can_create_conversation(connected_pair):
    user_a, user_b = connected_pair
    res = client.post(
        f"/api/messaging/conversations/{user_b['user_id']}",
        headers=user_a["headers"],
    )
    assert res.status_code == 200
    data = res.json()
    assert "id" in data
    assert data["other_participant"]["id"] == user_b["user_id"]
    assert data["other_participant"]["username"] == user_b["username"]


def test_08_existing_conversation_returned_not_duplicated(connected_pair):
    user_a, user_b = connected_pair
    res1 = client.post(
        f"/api/messaging/conversations/{user_b['user_id']}",
        headers=user_a["headers"],
    )
    res2 = client.post(
        f"/api/messaging/conversations/{user_b['user_id']}",
        headers=user_a["headers"],
    )
    assert res1.status_code == 200
    assert res2.status_code == 200
    assert res1.json()["id"] == res2.json()["id"]


def test_09_self_conversation_rejected(user_a):
    res = client.post(
        f"/api/messaging/conversations/{user_a['user_id']}",
        headers=user_a["headers"],
    )
    assert res.status_code == 400
    assert "yourself" in res.json()["detail"].lower()


def test_10_nonexistent_target_user_rejected(user_a):
    res = client.post(
        f"/api/messaging/conversations/{uuid.uuid4()}",
        headers=user_a["headers"],
    )
    assert res.status_code == 404


def test_11_pending_connection_rejected(user_a, user_b):
    # Send but do NOT accept
    client.post(
        f"/api/networking/connections/{user_b['user_id']}",
        headers=user_a["headers"],
    )
    res = client.post(
        f"/api/messaging/conversations/{user_b['user_id']}",
        headers=user_a["headers"],
    )
    assert res.status_code == 403


def test_12_rejected_connection_blocked(user_a, user_b):
    send = client.post(
        f"/api/networking/connections/{user_b['user_id']}",
        headers=user_a["headers"],
    )
    conn_id = send.json()["id"]
    client.post(f"/api/networking/requests/{conn_id}/reject", headers=user_b["headers"])
    res = client.post(
        f"/api/messaging/conversations/{user_b['user_id']}",
        headers=user_a["headers"],
    )
    assert res.status_code == 403


def test_13_unrelated_user_blocked(user_a, user_b):
    # No connection at all between a and b
    res = client.post(
        f"/api/messaging/conversations/{user_b['user_id']}",
        headers=user_a["headers"],
    )
    assert res.status_code == 403


def test_14_jwt_user_is_the_initiator_not_other_party(connected_pair):
    """
    The other_participant in the response must be user_b (the URL param),
    not user_a (the authenticated caller).
    """
    user_a, user_b = connected_pair
    res = client.post(
        f"/api/messaging/conversations/{user_b['user_id']}",
        headers=user_a["headers"],
    )
    assert res.status_code == 200
    assert res.json()["other_participant"]["id"] == user_b["user_id"]
    assert res.json()["other_participant"]["id"] != user_a["user_id"]


# ===========================================================================
# CONVERSATION LIST (15–20)
# ===========================================================================


def test_15_conversation_list_works(open_conversation):
    conv_id, user_a, user_b = open_conversation
    res = client.get("/api/messaging/conversations", headers=user_a["headers"])
    assert res.status_code == 200
    data = res.json()
    assert "conversations" in data
    ids = [c["id"] for c in data["conversations"]]
    assert conv_id in ids


def test_16_conversation_list_pagination(user_a, user_b, user_c):
    # Create connections and conversations to paginate
    _make_accepted_connection(user_a, user_b)
    _make_accepted_connection(user_a, user_c)
    _open_conversation(user_a, user_b)
    _open_conversation(user_a, user_c)

    page1 = client.get(
        "/api/messaging/conversations?limit=1&offset=0",
        headers=user_a["headers"],
    )
    page2 = client.get(
        "/api/messaging/conversations?limit=1&offset=1",
        headers=user_a["headers"],
    )
    assert page1.status_code == 200
    assert page2.status_code == 200
    ids1 = {c["id"] for c in page1.json()["conversations"]}
    ids2 = {c["id"] for c in page2.json()["conversations"]}
    assert ids1.isdisjoint(ids2)


def test_17_latest_message_returned_in_list(open_conversation):
    conv_id, user_a, user_b = open_conversation
    _send_message(user_a, conv_id, "First")
    _send_message(user_a, conv_id, "Latest")

    res = client.get("/api/messaging/conversations", headers=user_a["headers"])
    conv = next(c for c in res.json()["conversations"] if c["id"] == conv_id)
    assert conv["latest_message"] is not None
    assert conv["latest_message"]["content"] == "Latest"


def test_18_unread_count_in_list(open_conversation):
    conv_id, user_a, user_b = open_conversation
    # user_a sends 2 messages → user_b has 2 unread
    _send_message(user_a, conv_id, "Msg 1")
    _send_message(user_a, conv_id, "Msg 2")

    res = client.get("/api/messaging/conversations", headers=user_b["headers"])
    conv = next(c for c in res.json()["conversations"] if c["id"] == conv_id)
    assert conv["unread_count"] == 2


def test_19_other_participant_returned_in_list(open_conversation):
    conv_id, user_a, user_b = open_conversation
    res = client.get("/api/messaging/conversations", headers=user_a["headers"])
    conv = next(c for c in res.json()["conversations"] if c["id"] == conv_id)
    assert conv["other_participant"]["id"] == user_b["user_id"]


def test_20_user_only_sees_own_conversations(user_a, user_b, user_c):
    _make_accepted_connection(user_a, user_b)
    _make_accepted_connection(user_b, user_c)
    conv_ab = _open_conversation(user_a, user_b)
    conv_bc = _open_conversation(user_b, user_c)

    res_a = client.get("/api/messaging/conversations", headers=user_a["headers"])
    ids_a = {c["id"] for c in res_a.json()["conversations"]}

    assert conv_ab in ids_a
    # user_a must not see the user_b ↔ user_c conversation
    assert conv_bc not in ids_a


# ===========================================================================
# MESSAGES — send + history (21–25)
# ===========================================================================


def test_21_participant_can_retrieve_message_history(open_conversation):
    conv_id, user_a, user_b = open_conversation
    _send_message(user_a, conv_id, "Hello")
    res = client.get(
        f"/api/messaging/conversations/{conv_id}/messages",
        headers=user_b["headers"],
    )
    assert res.status_code == 200
    assert len(res.json()["messages"]) == 1


def test_22_non_participant_cannot_retrieve_history(open_conversation, user_c):
    conv_id, user_a, user_b = open_conversation
    _send_message(user_a, conv_id, "Private")
    res = client.get(
        f"/api/messaging/conversations/{conv_id}/messages",
        headers=user_c["headers"],
    )
    assert res.status_code == 403


def test_23_message_history_pagination(open_conversation):
    conv_id, user_a, user_b = open_conversation
    for i in range(5):
        _send_message(user_a, conv_id, f"Msg {i}")

    p1 = client.get(
        f"/api/messaging/conversations/{conv_id}/messages?limit=3&offset=0",
        headers=user_a["headers"],
    )
    p2 = client.get(
        f"/api/messaging/conversations/{conv_id}/messages?limit=3&offset=3",
        headers=user_a["headers"],
    )
    assert len(p1.json()["messages"]) == 3
    assert len(p2.json()["messages"]) == 2
    ids1 = {m["id"] for m in p1.json()["messages"]}
    ids2 = {m["id"] for m in p2.json()["messages"]}
    assert ids1.isdisjoint(ids2)


def test_24_message_response_contains_expected_fields(open_conversation):
    conv_id, user_a, user_b = open_conversation
    msg = _send_message(user_a, conv_id, "Check fields")
    for field in ("id", "conversation_id", "sender_id", "content", "created_at"):
        assert field in msg, f"Missing field: {field}"
    assert "delivered_at" in msg
    assert "read_at" in msg
    assert msg["sender_id"] == user_a["user_id"]
    assert msg["content"] == "Check fields"
    assert msg["delivered_at"] is None
    assert msg["read_at"] is None


def test_25_messages_from_another_conversation_excluded(user_a, user_b, user_c):
    _make_accepted_connection(user_a, user_b)
    _make_accepted_connection(user_a, user_c)
    conv_ab = _open_conversation(user_a, user_b)
    conv_ac = _open_conversation(user_a, user_c)
    _send_message(user_a, conv_ab, "For B")
    _send_message(user_a, conv_ac, "For C")

    msgs_ab = client.get(
        f"/api/messaging/conversations/{conv_ab}/messages",
        headers=user_a["headers"],
    ).json()["messages"]
    assert len(msgs_ab) == 1
    assert msgs_ab[0]["content"] == "For B"


# ===========================================================================
# UNREAD COUNT (26–29)
# ===========================================================================


def test_26_unread_count_correct(open_conversation):
    conv_id, user_a, user_b = open_conversation
    _send_message(user_a, conv_id, "Unread 1")
    _send_message(user_a, conv_id, "Unread 2")

    res = client.get("/api/messaging/unread-count", headers=user_b["headers"])
    assert res.status_code == 200
    assert res.json()["unread_count"] == 2


def test_27_own_messages_not_counted(open_conversation):
    conv_id, user_a, user_b = open_conversation
    _send_message(user_a, conv_id, "I sent this")

    res = client.get("/api/messaging/unread-count", headers=user_a["headers"])
    assert res.json()["unread_count"] == 0


def test_28_read_messages_not_counted(open_conversation):
    conv_id, user_a, user_b = open_conversation
    _send_message(user_a, conv_id, "Read me")

    # user_b marks as read
    client.post(
        f"/api/messaging/conversations/{conv_id}/read",
        headers=user_b["headers"],
    )

    res = client.get("/api/messaging/unread-count", headers=user_b["headers"])
    assert res.json()["unread_count"] == 0


def test_29_unrelated_conversations_not_counted(user_a, user_b, user_c):
    _make_accepted_connection(user_a, user_b)
    _make_accepted_connection(user_b, user_c)
    conv_ab = _open_conversation(user_a, user_b)
    conv_bc = _open_conversation(user_b, user_c)

    # user_a sends to user_b — unread for user_b
    _send_message(user_a, conv_ab, "For B")
    # user_c sends to user_b — also unread for user_b
    _send_message(user_c, conv_bc, "From C to B")

    # user_a should have 0 unread (nothing sent to them yet)
    assert client.get(
        "/api/messaging/unread-count", headers=user_a["headers"]
    ).json()["unread_count"] == 0

    # user_b should have 2 unread
    assert client.get(
        "/api/messaging/unread-count", headers=user_b["headers"]
    ).json()["unread_count"] == 2


# ===========================================================================
# DELIVERED (30–33)
# ===========================================================================


def test_30_participant_can_mark_received_messages_delivered(open_conversation):
    conv_id, user_a, user_b = open_conversation
    _send_message(user_a, conv_id, "Deliver me")

    res = client.post(
        f"/api/messaging/conversations/{conv_id}/delivered",
        headers=user_b["headers"],
    )
    assert res.status_code == 200
    assert res.json()["updated_count"] == 1

    msgs = client.get(
        f"/api/messaging/conversations/{conv_id}/messages",
        headers=user_b["headers"],
    ).json()["messages"]
    assert msgs[0]["delivered_at"] is not None


def test_31_non_participant_cannot_mark_delivered(open_conversation, user_c):
    conv_id, user_a, user_b = open_conversation
    _send_message(user_a, conv_id, "Msg")

    res = client.post(
        f"/api/messaging/conversations/{conv_id}/delivered",
        headers=user_c["headers"],
    )
    assert res.status_code == 403


def test_32_mark_delivered_is_idempotent(open_conversation):
    conv_id, user_a, user_b = open_conversation
    _send_message(user_a, conv_id, "Msg")

    client.post(
        f"/api/messaging/conversations/{conv_id}/delivered",
        headers=user_b["headers"],
    )
    res2 = client.post(
        f"/api/messaging/conversations/{conv_id}/delivered",
        headers=user_b["headers"],
    )
    assert res2.json()["updated_count"] == 0


def test_33_own_messages_not_marked_delivered(open_conversation):
    conv_id, user_a, user_b = open_conversation
    _send_message(user_a, conv_id, "My message")

    # user_a calls delivered — should not affect their own message
    res = client.post(
        f"/api/messaging/conversations/{conv_id}/delivered",
        headers=user_a["headers"],
    )
    assert res.json()["updated_count"] == 0

    msgs = client.get(
        f"/api/messaging/conversations/{conv_id}/messages",
        headers=user_a["headers"],
    ).json()["messages"]
    assert msgs[0]["delivered_at"] is None


# ===========================================================================
# READ (34–37)
# ===========================================================================


def test_34_participant_can_mark_received_messages_read(open_conversation):
    conv_id, user_a, user_b = open_conversation
    _send_message(user_a, conv_id, "Read me")

    res = client.post(
        f"/api/messaging/conversations/{conv_id}/read",
        headers=user_b["headers"],
    )
    assert res.status_code == 200

    msgs = client.get(
        f"/api/messaging/conversations/{conv_id}/messages",
        headers=user_b["headers"],
    ).json()["messages"]
    assert msgs[0]["read_at"] is not None


def test_35_non_participant_cannot_mark_read(open_conversation, user_c):
    conv_id, user_a, user_b = open_conversation
    _send_message(user_a, conv_id, "Msg")

    res = client.post(
        f"/api/messaging/conversations/{conv_id}/read",
        headers=user_c["headers"],
    )
    assert res.status_code == 403


def test_36_mark_read_is_idempotent(open_conversation):
    conv_id, user_a, user_b = open_conversation
    _send_message(user_a, conv_id, "Msg")
    client.post(
        f"/api/messaging/conversations/{conv_id}/read",
        headers=user_b["headers"],
    )
    res2 = client.post(
        f"/api/messaging/conversations/{conv_id}/read",
        headers=user_b["headers"],
    )
    assert res2.json()["updated_count"] == 0


def test_37_read_messages_have_delivered_state(open_conversation):
    conv_id, user_a, user_b = open_conversation
    _send_message(user_a, conv_id, "Both timestamps")

    client.post(
        f"/api/messaging/conversations/{conv_id}/read",
        headers=user_b["headers"],
    )

    msgs = client.get(
        f"/api/messaging/conversations/{conv_id}/messages",
        headers=user_b["headers"],
    ).json()["messages"]
    msg = msgs[0]
    assert msg["read_at"] is not None
    assert msg["delivered_at"] is not None


# ===========================================================================
# REGRESSION (38–40)
# ===========================================================================


def test_38_send_message_never_accepts_sender_id_from_body(open_conversation):
    """
    Passing a fake sender_id in the body must not be respected — the server
    must always use the JWT-authenticated user.
    """
    conv_id, user_a, user_b = open_conversation
    # user_b sends a message but injects user_a's id as sender — must be ignored
    res = client.post(
        f"/api/messaging/conversations/{conv_id}/messages",
        json={"content": "Spoofed sender", "sender_id": user_a["user_id"]},
        headers=user_b["headers"],
    )
    # The SendMessageRequest schema has no sender_id field, so extra fields
    # are either ignored or cause a 422.  Either way sender_id in the
    # response must be user_b.
    if res.status_code == 201:
        assert res.json()["sender_id"] == user_b["user_id"]


def test_39_networking_connection_endpoints_still_work(connected_pair):
    """Networking endpoints must not be broken by the messaging router."""
    user_a, user_b = connected_pair
    res = client.get("/api/networking/connections", headers=user_a["headers"])
    assert res.status_code == 200


def test_40_response_schema_has_no_sensitive_fields(open_conversation):
    """Conversation and message responses must not expose password_hash or email."""
    conv_id, user_a, user_b = open_conversation
    _send_message(user_a, conv_id, "Privacy check")

    conv_res = client.get("/api/messaging/conversations", headers=user_a["headers"])
    raw_conv = conv_res.text.lower()
    assert "password_hash" not in raw_conv
    assert "password" not in raw_conv

    msg_res = client.get(
        f"/api/messaging/conversations/{conv_id}/messages",
        headers=user_a["headers"],
    )
    raw_msg = msg_res.text.lower()
    assert "password_hash" not in raw_msg

    # email must not appear in participant summaries
    assert user_b["email"] not in conv_res.text
    assert user_a["email"] not in msg_res.text


def test_41_empty_message_body_rejected(open_conversation):
    conv_id, user_a, user_b = open_conversation
    res = client.post(
        f"/api/messaging/conversations/{conv_id}/messages",
        json={"content": ""},
        headers=user_a["headers"],
    )
    assert res.status_code in (400, 422)


def test_42_whitespace_only_message_rejected(open_conversation):
    conv_id, user_a, user_b = open_conversation
    res = client.post(
        f"/api/messaging/conversations/{conv_id}/messages",
        json={"content": "   "},
        headers=user_a["headers"],
    )
    # Pydantic min_length=1 on stripped content catches this at 422,
    # or the service catches it at 400 — either is valid rejection.
    assert res.status_code in (400, 422)


def test_43_message_too_long_rejected(open_conversation):
    from app.services.messaging_service import DM_MAX_CONTENT_CHARS
    conv_id, user_a, user_b = open_conversation
    res = client.post(
        f"/api/messaging/conversations/{conv_id}/messages",
        json={"content": "x" * (DM_MAX_CONTENT_CHARS + 1)},
        headers=user_a["headers"],
    )
    assert res.status_code in (400, 422)
