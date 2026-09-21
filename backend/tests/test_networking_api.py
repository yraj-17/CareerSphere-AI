"""
Networking Phase 5.3 — REST API tests.

Tests exercise every networking endpoint through the FastAPI TestClient against
a real PostgreSQL database.  Each test class manages its own users so that
suites can run in any order without stepping on each other.

Requires Docker infrastructure:
  docker compose up -d postgres redis
and valid DATABASE_URL / REDIS_URL in the environment or .env.

Test index
----------
Authentication
  1.  Unauthenticated request is rejected (401)

Send connection request
  2.  Authenticated user can send a request
  3.  Self-request returns 400
  4.  Duplicate same-direction returns 409
  5.  Duplicate reverse-direction returns 409
  6.  Non-existent target user returns 404

Incoming / outgoing lists
  7.  Incoming only shows requests received by current user
  8.  Outgoing only shows requests sent by current user

Accept
  9.  Receiver can accept
  10. Requester cannot accept (403)
  11. Unrelated user cannot accept (403)
  12. Non-existent connection returns 404

Reject
  13. Receiver can reject
  14. Requester cannot reject (403)
  15. Unrelated user cannot reject (403)

Cancel
  16. Requester can cancel
  17. Receiver cannot cancel (403)
  18. Unrelated user cannot cancel (403)

Remove
  19. Participant can remove accepted connection (204)
  20. Unrelated user cannot remove (403)
  21. Pending connection cannot be removed (422)

Relationship check
  22. No relationship → status=none
  23. Pending relationship returned correctly
  24. Accepted relationship returned correctly

Discovery
  25. /users requires authentication
  26. Authenticated user is excluded from results
  27. Search filters by username / name
  28. Pagination works (limit / offset)
  29. Returned users do not expose sensitive fields
  30. Connection status is correctly attached to discovered users

User isolation
  31. User A cannot read User B's incoming requests
  32. User A cannot read User B's outgoing requests
  33. User A cannot accept a request directed at User B
"""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import or_

from app.db.models import Connection, User
from app.db.session import Base, SessionLocal, engine
from app.db.redis_client import redis_client
from app.core.config import settings
from app.main import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_USER_COUNTER = 0


def _unique_tag() -> str:
    global _USER_COUNTER
    _USER_COUNTER += 1
    return f"{_USER_COUNTER}_{uuid.uuid4().hex[:6]}"


def _seed_verified_email(email: str) -> str:
    """Plant a verified OTP record in Redis and return the raw token."""
    token = f"test-token-{uuid.uuid4().hex}"
    token_hash = hashlib.sha256(
        f"{email}:{token}:{settings.SECRET_KEY}".encode()
    ).hexdigest()
    payload = json.dumps({"otp": "123456", "verified_token": token_hash, "token_raw": token})
    redis_client.set(f"otp:{email}", payload, ex=600)
    return token


def _register_user(tag: Optional[str] = None) -> dict:
    """Register a fresh user and return {token, user_id, username, email, headers}."""
    if tag is None:
        tag = _unique_tag()
    email = f"net_api_{tag}@example.com"
    username = f"netapi_{tag}"[:30]
    verification_token = _seed_verified_email(email)
    res = client.post("/api/auth/register", json={
        "first_name": "Net",
        "last_name": "Test",
        "username": username,
        "email": email,
        "password": "Password123",
        "email_verification_token": verification_token,
    })
    assert res.status_code == 201, f"Register failed: {res.text}"
    user_id = res.json()["id"]

    login_res = client.post("/api/auth/login", json={
        "identifier": username,
        "password": "Password123",
    })
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    return {
        "token": token,
        "user_id": user_id,
        "username": username,
        "email": email,
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


def _send_request(from_headers: dict, to_user_id: str) -> dict:
    res = client.post(f"/api/networking/connections/{to_user_id}", headers=from_headers)
    return res


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
def pending_connection(user_a, user_b):
    """A→B pending connection. Returns (connection_id, user_a, user_b)."""
    res = _send_request(user_a["headers"], user_b["user_id"])
    assert res.status_code == 201, res.text
    return res.json()["id"], user_a, user_b


@pytest.fixture()
def accepted_connection(user_a, user_b):
    """A→B accepted connection. Returns (connection_id, user_a, user_b)."""
    send_res = _send_request(user_a["headers"], user_b["user_id"])
    assert send_res.status_code == 201, send_res.text
    conn_id = send_res.json()["id"]
    accept_res = client.post(
        f"/api/networking/requests/{conn_id}/accept",
        headers=user_b["headers"],
    )
    assert accept_res.status_code == 200, accept_res.text
    return conn_id, user_a, user_b


# ===========================================================================
# 1. Authentication — unauthenticated requests are rejected
# ===========================================================================


def test_unauthenticated_send_request_rejected():
    res = client.post("/api/networking/connections/some-user-id")
    assert res.status_code == 401


def test_unauthenticated_get_connections_rejected():
    res = client.get("/api/networking/connections")
    assert res.status_code == 401


def test_unauthenticated_incoming_rejected():
    res = client.get("/api/networking/requests/incoming")
    assert res.status_code == 401


def test_unauthenticated_outgoing_rejected():
    res = client.get("/api/networking/requests/outgoing")
    assert res.status_code == 401


def test_unauthenticated_users_rejected():
    res = client.get("/api/networking/users")
    assert res.status_code == 401


# ===========================================================================
# 2. Send connection request — success
# ===========================================================================


def test_send_connection_request_success(user_a, user_b):
    res = _send_request(user_a["headers"], user_b["user_id"])
    assert res.status_code == 201
    data = res.json()
    assert data["requester_id"] == user_a["user_id"]
    assert data["receiver_id"] == user_b["user_id"]
    assert data["status"] == "pending"
    assert "id" in data
    assert "created_at" in data
    # No password or hash in response
    assert "password" not in data
    assert "password_hash" not in data


# ===========================================================================
# 3. Self-request → 400
# ===========================================================================


def test_send_self_request_returns_400(user_a):
    res = _send_request(user_a["headers"], user_a["user_id"])
    assert res.status_code == 400


# ===========================================================================
# 4. Duplicate same-direction → 409
# ===========================================================================


def test_duplicate_same_direction_returns_409(user_a, user_b):
    r1 = _send_request(user_a["headers"], user_b["user_id"])
    assert r1.status_code == 201
    r2 = _send_request(user_a["headers"], user_b["user_id"])
    assert r2.status_code == 409


# ===========================================================================
# 5. Duplicate reverse-direction → 409
# ===========================================================================


def test_duplicate_reverse_direction_returns_409(user_a, user_b):
    r1 = _send_request(user_a["headers"], user_b["user_id"])
    assert r1.status_code == 201
    r2 = _send_request(user_b["headers"], user_a["user_id"])
    assert r2.status_code == 409


# ===========================================================================
# 6. Non-existent target user → 404
# ===========================================================================


def test_send_request_nonexistent_user_returns_404(user_a):
    fake_id = str(uuid.uuid4())
    res = _send_request(user_a["headers"], fake_id)
    assert res.status_code == 404


# ===========================================================================
# 7. Incoming requests — only shows requests *received* by current user
# ===========================================================================


def test_incoming_requests_only_shows_received(user_a, user_b, user_c):
    # B → A  (incoming for A)
    _send_request(user_b["headers"], user_a["user_id"])
    # A → C  (outgoing from A, not incoming for A)
    _send_request(user_a["headers"], user_c["user_id"])

    res = client.get("/api/networking/requests/incoming", headers=user_a["headers"])
    assert res.status_code == 200
    data = res.json()
    receiver_ids = {r["receiver_id"] for r in data}
    requester_ids = {r["requester_id"] for r in data}

    # Only requests where A is the receiver should appear
    assert all(rid == user_a["user_id"] for rid in receiver_ids)
    # A→C should NOT appear in A's incoming
    a_to_c_entries = [r for r in data if r["requester_id"] == user_a["user_id"]]
    assert len(a_to_c_entries) == 0


# ===========================================================================
# 8. Outgoing requests — only shows requests *sent* by current user
# ===========================================================================


def test_outgoing_requests_only_shows_sent(user_a, user_b, user_c):
    # A → B  (outgoing from A)
    _send_request(user_a["headers"], user_b["user_id"])
    # C → A  (incoming for A, not outgoing)
    _send_request(user_c["headers"], user_a["user_id"])

    res = client.get("/api/networking/requests/outgoing", headers=user_a["headers"])
    assert res.status_code == 200
    data = res.json()
    requester_ids = {r["requester_id"] for r in data}

    assert all(rid == user_a["user_id"] for rid in requester_ids)
    c_to_a_entries = [r for r in data if r["requester_id"] == user_c["user_id"]]
    assert len(c_to_a_entries) == 0


# ===========================================================================
# 9. Accept — receiver can accept
# ===========================================================================


def test_receiver_can_accept(pending_connection):
    conn_id, user_a, user_b = pending_connection
    res = client.post(
        f"/api/networking/requests/{conn_id}/accept",
        headers=user_b["headers"],
    )
    assert res.status_code == 200
    assert res.json()["status"] == "accepted"


# ===========================================================================
# 10. Accept — requester cannot accept (403)
# ===========================================================================


def test_requester_cannot_accept(pending_connection):
    conn_id, user_a, user_b = pending_connection
    res = client.post(
        f"/api/networking/requests/{conn_id}/accept",
        headers=user_a["headers"],
    )
    assert res.status_code == 403


# ===========================================================================
# 11. Accept — unrelated user cannot accept (403)
# ===========================================================================


def test_unrelated_user_cannot_accept(pending_connection, user_c):
    conn_id, user_a, user_b = pending_connection
    res = client.post(
        f"/api/networking/requests/{conn_id}/accept",
        headers=user_c["headers"],
    )
    assert res.status_code == 403


# ===========================================================================
# 12. Accept — non-existent connection returns 404
# ===========================================================================


def test_accept_nonexistent_connection_returns_404(user_a):
    fake_id = str(uuid.uuid4())
    res = client.post(
        f"/api/networking/requests/{fake_id}/accept",
        headers=user_a["headers"],
    )
    assert res.status_code == 404


# ===========================================================================
# 13. Reject — receiver can reject
# ===========================================================================


def test_receiver_can_reject(pending_connection):
    conn_id, user_a, user_b = pending_connection
    res = client.post(
        f"/api/networking/requests/{conn_id}/reject",
        headers=user_b["headers"],
    )
    assert res.status_code == 200
    assert res.json()["status"] == "rejected"


# ===========================================================================
# 14. Reject — requester cannot reject (403)
# ===========================================================================


def test_requester_cannot_reject(pending_connection):
    conn_id, user_a, user_b = pending_connection
    res = client.post(
        f"/api/networking/requests/{conn_id}/reject",
        headers=user_a["headers"],
    )
    assert res.status_code == 403


# ===========================================================================
# 15. Reject — unrelated user cannot reject (403)
# ===========================================================================


def test_unrelated_user_cannot_reject(pending_connection, user_c):
    conn_id, user_a, user_b = pending_connection
    res = client.post(
        f"/api/networking/requests/{conn_id}/reject",
        headers=user_c["headers"],
    )
    assert res.status_code == 403


# ===========================================================================
# 16. Cancel — requester can cancel
# ===========================================================================


def test_requester_can_cancel(pending_connection):
    conn_id, user_a, user_b = pending_connection
    res = client.post(
        f"/api/networking/requests/{conn_id}/cancel",
        headers=user_a["headers"],
    )
    assert res.status_code == 200
    assert res.json()["status"] == "cancelled"


# ===========================================================================
# 17. Cancel — receiver cannot cancel (403)
# ===========================================================================


def test_receiver_cannot_cancel(pending_connection):
    conn_id, user_a, user_b = pending_connection
    res = client.post(
        f"/api/networking/requests/{conn_id}/cancel",
        headers=user_b["headers"],
    )
    assert res.status_code == 403


# ===========================================================================
# 18. Cancel — unrelated user cannot cancel (403)
# ===========================================================================


def test_unrelated_user_cannot_cancel(pending_connection, user_c):
    conn_id, user_a, user_b = pending_connection
    res = client.post(
        f"/api/networking/requests/{conn_id}/cancel",
        headers=user_c["headers"],
    )
    assert res.status_code == 403


# ===========================================================================
# 19. Remove — participant can remove accepted connection (204)
# ===========================================================================


def test_requester_can_remove_accepted(accepted_connection):
    conn_id, user_a, user_b = accepted_connection
    res = client.delete(
        f"/api/networking/connections/{conn_id}",
        headers=user_a["headers"],
    )
    assert res.status_code == 204

    # Confirm gone
    check = client.get(
        f"/api/networking/users/{user_b['user_id']}/connection",
        headers=user_a["headers"],
    )
    assert check.json()["status"] == "none"


def test_receiver_can_remove_accepted(accepted_connection):
    conn_id, user_a, user_b = accepted_connection
    res = client.delete(
        f"/api/networking/connections/{conn_id}",
        headers=user_b["headers"],
    )
    assert res.status_code == 204


# ===========================================================================
# 20. Remove — unrelated user cannot remove (403)
# ===========================================================================


def test_unrelated_user_cannot_remove(accepted_connection, user_c):
    conn_id, user_a, user_b = accepted_connection
    res = client.delete(
        f"/api/networking/connections/{conn_id}",
        headers=user_c["headers"],
    )
    assert res.status_code == 403


# ===========================================================================
# 21. Remove — pending connection cannot be removed (422)
# ===========================================================================


def test_pending_connection_cannot_be_removed(pending_connection):
    conn_id, user_a, user_b = pending_connection
    res = client.delete(
        f"/api/networking/connections/{conn_id}",
        headers=user_a["headers"],
    )
    assert res.status_code == 422


# ===========================================================================
# 22. Relationship check — no relationship → status=none
# ===========================================================================


def test_relationship_check_no_relationship(user_a, user_b):
    res = client.get(
        f"/api/networking/users/{user_b['user_id']}/connection",
        headers=user_a["headers"],
    )
    assert res.status_code == 200
    assert res.json()["status"] == "none"


# ===========================================================================
# 23. Relationship check — pending
# ===========================================================================


def test_relationship_check_pending(pending_connection):
    conn_id, user_a, user_b = pending_connection

    # Check from requester's side
    res_a = client.get(
        f"/api/networking/users/{user_b['user_id']}/connection",
        headers=user_a["headers"],
    )
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert data_a["status"] == "pending"
    assert data_a["connection_id"] == conn_id

    # Check from receiver's side — same result
    res_b = client.get(
        f"/api/networking/users/{user_a['user_id']}/connection",
        headers=user_b["headers"],
    )
    assert res_b.status_code == 200
    assert res_b.json()["status"] == "pending"
    assert res_b.json()["connection_id"] == conn_id


# ===========================================================================
# 24. Relationship check — accepted
# ===========================================================================


def test_relationship_check_accepted(accepted_connection):
    conn_id, user_a, user_b = accepted_connection
    res = client.get(
        f"/api/networking/users/{user_b['user_id']}/connection",
        headers=user_a["headers"],
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "accepted"
    assert data["connection_id"] == conn_id


# ===========================================================================
# 25. Discovery — requires authentication
# ===========================================================================


def test_discover_users_requires_auth():
    res = client.get("/api/networking/users")
    assert res.status_code == 401


# ===========================================================================
# 26. Discovery — authenticated user excluded from results
# ===========================================================================


def test_discover_users_excludes_self(user_a):
    res = client.get("/api/networking/users", headers=user_a["headers"])
    assert res.status_code == 200
    data = res.json()
    user_ids = [u["id"] for u in data["users"]]
    assert user_a["user_id"] not in user_ids


# ===========================================================================
# 27. Discovery — search filters by username / name
# ===========================================================================


def test_discover_users_search_filters(user_a, user_b):
    # Search for user_b's exact username
    res = client.get(
        "/api/networking/users",
        params={"q": user_b["username"]},
        headers=user_a["headers"],
    )
    assert res.status_code == 200
    data = res.json()
    matched_ids = [u["id"] for u in data["users"]]
    assert user_b["user_id"] in matched_ids
    # user_a must not be in results
    assert user_a["user_id"] not in matched_ids


def test_discover_users_search_no_match(user_a):
    res = client.get(
        "/api/networking/users",
        params={"q": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx_no_match"},
        headers=user_a["headers"],
    )
    assert res.status_code == 200
    assert res.json()["total"] == 0
    assert res.json()["users"] == []


# ===========================================================================
# 28. Discovery — pagination
# ===========================================================================


def test_discover_users_pagination(user_a):
    # Request page 1 with limit=1
    res1 = client.get(
        "/api/networking/users",
        params={"limit": 1, "offset": 0},
        headers=user_a["headers"],
    )
    assert res1.status_code == 200
    page1 = res1.json()
    assert len(page1["users"]) <= 1
    assert page1["limit"] == 1
    assert page1["offset"] == 0

    if page1["total"] > 1:
        res2 = client.get(
            "/api/networking/users",
            params={"limit": 1, "offset": 1},
            headers=user_a["headers"],
        )
        assert res2.status_code == 200
        page2 = res2.json()
        # The two pages must return different users
        ids1 = {u["id"] for u in page1["users"]}
        ids2 = {u["id"] for u in page2["users"]}
        assert ids1.isdisjoint(ids2)


# ===========================================================================
# 29. Discovery — no sensitive fields exposed
# ===========================================================================


def test_discover_users_no_sensitive_fields(user_a, user_b):
    res = client.get(
        "/api/networking/users",
        params={"q": user_b["username"]},
        headers=user_a["headers"],
    )
    assert res.status_code == 200
    users = res.json()["users"]
    assert len(users) >= 1
    found = next((u for u in users if u["id"] == user_b["user_id"]), None)
    assert found is not None

    forbidden_fields = {"password", "password_hash", "email", "access_token"}
    for field in forbidden_fields:
        assert field not in found, f"Sensitive field '{field}' must not appear in discovery response"


# ===========================================================================
# 30. Discovery — connection status correctly attached
# ===========================================================================


def test_discover_users_connection_status_none(user_a, user_b):
    res = client.get(
        "/api/networking/users",
        params={"q": user_b["username"]},
        headers=user_a["headers"],
    )
    users = res.json()["users"]
    found = next((u for u in users if u["id"] == user_b["user_id"]), None)
    assert found is not None
    assert found["connection_status"] == "none"


def test_discover_users_connection_status_pending(pending_connection):
    conn_id, user_a, user_b = pending_connection
    res = client.get(
        "/api/networking/users",
        params={"q": user_b["username"]},
        headers=user_a["headers"],
    )
    users = res.json()["users"]
    found = next((u for u in users if u["id"] == user_b["user_id"]), None)
    assert found is not None
    assert found["connection_status"] == "pending"


def test_discover_users_connection_status_accepted(accepted_connection):
    conn_id, user_a, user_b = accepted_connection
    res = client.get(
        "/api/networking/users",
        params={"q": user_b["username"]},
        headers=user_a["headers"],
    )
    users = res.json()["users"]
    found = next((u for u in users if u["id"] == user_b["user_id"]), None)
    assert found is not None
    assert found["connection_status"] == "accepted"


# ===========================================================================
# 31–33. User isolation
# ===========================================================================


def test_user_a_cannot_see_user_b_incoming_by_spoofing(user_a, user_b, user_c):
    """A's incoming list must only contain A's incoming — not B's."""
    # C → B  (incoming for B, not A)
    _send_request(user_c["headers"], user_b["user_id"])
    # C → A  (incoming for A)
    _send_request(user_c["headers"], user_a["user_id"])

    res = client.get("/api/networking/requests/incoming", headers=user_a["headers"])
    assert res.status_code == 200
    data = res.json()

    # All entries in A's incoming must have receiver_id == A's id
    for entry in data:
        assert entry["receiver_id"] == user_a["user_id"], (
            f"Isolation failure: found receiver_id={entry['receiver_id']} "
            f"in user_a's incoming list"
        )


def test_user_a_cannot_see_user_b_outgoing_by_spoofing(user_a, user_b, user_c):
    """A's outgoing list must only contain A's outgoing — not B's."""
    # B → C  (outgoing from B)
    _send_request(user_b["headers"], user_c["user_id"])
    # A → C conflicts since B → C used the B/C canonical pair, not A/C.
    # Send A → B instead.
    _send_request(user_a["headers"], user_b["user_id"])

    res = client.get("/api/networking/requests/outgoing", headers=user_a["headers"])
    assert res.status_code == 200
    data = res.json()

    for entry in data:
        assert entry["requester_id"] == user_a["user_id"], (
            f"Isolation failure: found requester_id={entry['requester_id']} "
            f"in user_a's outgoing list"
        )


def test_user_a_cannot_accept_connection_directed_at_user_b(pending_connection, user_c):
    """
    The pending connection is A→B. user_c attempts to accept it.
    Must get 403, not 200.
    """
    conn_id, user_a, user_b = pending_connection
    res = client.post(
        f"/api/networking/requests/{conn_id}/accept",
        headers=user_c["headers"],
    )
    assert res.status_code == 403


def test_invalid_status_transition_via_api(pending_connection):
    """Cancel a pending request, then try to cancel again — must get 422."""
    conn_id, user_a, user_b = pending_connection
    r1 = client.post(
        f"/api/networking/requests/{conn_id}/cancel",
        headers=user_a["headers"],
    )
    assert r1.status_code == 200

    r2 = client.post(
        f"/api/networking/requests/{conn_id}/cancel",
        headers=user_a["headers"],
    )
    assert r2.status_code == 422


def test_relationship_check_unknown_user_returns_404(user_a):
    fake_id = str(uuid.uuid4())
    res = client.get(
        f"/api/networking/users/{fake_id}/connection",
        headers=user_a["headers"],
    )
    assert res.status_code == 404


def test_get_accepted_connections_list(accepted_connection):
    conn_id, user_a, user_b = accepted_connection
    res = client.get("/api/networking/connections", headers=user_a["headers"])
    assert res.status_code == 200
    ids = [c["id"] for c in res.json()]
    assert conn_id in ids

    # Pending connection should NOT appear in accepted list
    res_b = client.get("/api/networking/connections", headers=user_b["headers"])
    assert res_b.status_code == 200
    ids_b = [c["id"] for c in res_b.json()]
    assert conn_id in ids_b
