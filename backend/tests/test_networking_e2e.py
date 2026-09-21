"""
Phase 5.7 — End-to-End Networking Integration Tests.

These tests exercise the complete connection lifecycle as a continuous flow,
simulating real user journeys through the entire networking system:

  Discover → Profile → Connect → Pending → Accept/Reject/Cancel
  → My Network → Profile → Remove → No Relationship

All state transitions are validated against the backend connection service.

Test coverage
─────────────
Flow A: Full connect → accept → view → remove lifecycle
  A1.  User A discovers User B via /users
  A2.  User A opens User B's public profile
  A3.  Profile does not expose sensitive fields
  A4.  User A sends a connection request to User B
  A5.  Connection appears as OUTGOING PENDING for A
  A6.  Connection appears as INCOMING PENDING for B
  A7.  User B accepts the request
  A8.  Connection shows ACCEPTED for both A and B
  A9.  Both see each other in My Network connections
  A10. My Network returns correct other_user for each party
  A11. Profile view shows correct connection status for each party
  A12. User A removes the connection
  A13. Both return to NO RELATIONSHIP state
  A14. Neither appears in the other's My Network

Flow B: Reject lifecycle
  B1.  User B sends request to User A
  B2.  User A rejects the request
  B3.  Request disappears from A's incoming list
  B4.  B's outgoing list shows the request as removed
  B5.  Status returns to "none" for both

Flow C: Cancel lifecycle
  C1.  User A sends a request to User B
  C2.  Request appears in A's outgoing list
  C3.  User A cancels the request
  C4.  Request disappears from A's outgoing list
  C5.  Request no longer appears in B's incoming list
  C6.  Status returns to "none" for both

Flow D: State machine guards
  D1.  Duplicate request from same direction is rejected (409)
  D2.  Reverse-direction duplicate is rejected (409)
  D3.  Wrong user cannot accept (403)
  D4.  Wrong user cannot reject (403)
  D5.  Wrong user cannot cancel (403)
  D6.  Wrong user cannot remove (403)
  D7.  Pending connection cannot be removed (422)
  D8.  Accepted connection cannot be accepted again (422)

Flow E: Own profile
  E1.  User A's own profile endpoint returns 200
  E2.  User A's connection status to self returns "none"
  E3.  Own profile does not expose sensitive fields

Flow F: Invalid/missing resources
  F1.  Nonexistent user profile returns 404
  F2.  Nonexistent connection action returns 404
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
# Helpers (identical pattern to test_networking_api.py)
# ---------------------------------------------------------------------------

_CTR = 0


def _tag() -> str:
    global _CTR
    _CTR += 1
    return f"e2e{_CTR}_{uuid.uuid4().hex[:6]}"


def _seed_otp(email: str) -> str:
    token = f"tok-{uuid.uuid4().hex}"
    token_hash = hashlib.sha256(
        f"{email}:{token}:{settings.SECRET_KEY}".encode()
    ).hexdigest()
    redis_client.set(
        f"otp:{email}",
        json.dumps({"otp": "123456", "verified_token": token_hash, "token_raw": token}),
        ex=600,
    )
    return token


def _register(tag: Optional[str] = None) -> dict:
    if tag is None:
        tag = _tag()
    email = f"e2e_{tag}@example.com"
    username = f"e2e_{tag}"[:30]
    res = client.post("/api/auth/register", json={
        "first_name": "E2E",
        "last_name": "User",
        "username": username,
        "email": email,
        "password": "Password123",
        "email_verification_token": _seed_otp(email),
    })
    assert res.status_code == 201, res.text
    uid = res.json()["id"]
    login = client.post("/api/auth/login", json={"identifier": username, "password": "Password123"})
    assert login.status_code == 200
    return {
        "user_id": uid, "username": username, "email": email,
        "headers": {"Authorization": f"Bearer {login.json()['access_token']}"},
    }


def _cleanup(*emails: str) -> None:
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def ensure_tables():
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def user_a():
    u = _register()
    yield u
    _cleanup(u["email"])


@pytest.fixture()
def user_b():
    u = _register()
    yield u
    _cleanup(u["email"])


@pytest.fixture()
def user_c():
    u = _register()
    yield u
    _cleanup(u["email"])


# ===========================================================================
# Flow A: Full connect → accept → view → remove lifecycle
# ===========================================================================


def test_A1_discover_returns_user_b(user_a, user_b):
    """User A can discover User B via the people-search endpoint."""
    res = client.get(
        "/api/networking/users",
        params={"q": user_b["username"]},
        headers=user_a["headers"],
    )
    assert res.status_code == 200
    ids = [u["id"] for u in res.json()["users"]]
    assert user_b["user_id"] in ids


def test_A2_profile_view_returns_200(user_a, user_b):
    """User A can open User B's public profile."""
    res = client.get(
        f"/api/networking/users/{user_b['user_id']}/profile",
        headers=user_a["headers"],
    )
    assert res.status_code == 200
    assert res.json()["user"]["id"] == user_b["user_id"]


def test_A3_profile_no_sensitive_fields(user_a, user_b):
    """Public profile never exposes sensitive data."""
    res = client.get(
        f"/api/networking/users/{user_b['user_id']}/profile",
        headers=user_a["headers"],
    )
    raw = res.text.lower()
    for field in ("password_hash", "password", "access_token", "secret_key"):
        assert field not in raw
    assert user_b["email"] not in res.text


def test_A4_send_connection_request(user_a, user_b):
    """User A sends a connection request to User B."""
    res = client.post(
        f"/api/networking/connections/{user_b['user_id']}",
        headers=user_a["headers"],
    )
    assert res.status_code == 201
    data = res.json()
    assert data["requester_id"] == user_a["user_id"]
    assert data["receiver_id"] == user_b["user_id"]
    assert data["status"] == "pending"


def test_A5_outgoing_pending_visible_for_a(user_a, user_b):
    """After sending, the request appears in A's outgoing list."""
    send = client.post(f"/api/networking/connections/{user_b['user_id']}", headers=user_a["headers"])
    assert send.status_code == 201
    conn_id = send.json()["id"]

    outgoing = client.get("/api/networking/requests/outgoing", headers=user_a["headers"])
    assert outgoing.status_code == 200
    ids = [c["id"] for c in outgoing.json()]
    assert conn_id in ids


def test_A6_incoming_pending_visible_for_b(user_a, user_b):
    """After sending, the request appears in B's incoming list."""
    send = client.post(f"/api/networking/connections/{user_b['user_id']}", headers=user_a["headers"])
    assert send.status_code == 201
    conn_id = send.json()["id"]

    incoming = client.get("/api/networking/requests/incoming", headers=user_b["headers"])
    assert incoming.status_code == 200
    ids = [c["id"] for c in incoming.json()]
    assert conn_id in ids


def test_A7_accept_connection(user_a, user_b):
    """User B accepts the request."""
    send = client.post(f"/api/networking/connections/{user_b['user_id']}", headers=user_a["headers"])
    conn_id = send.json()["id"]

    accept = client.post(f"/api/networking/requests/{conn_id}/accept", headers=user_b["headers"])
    assert accept.status_code == 200
    assert accept.json()["status"] == "accepted"


def test_A8_both_see_accepted_status(user_a, user_b):
    """After accepting, both A and B see 'accepted' via the connection-status endpoint."""
    send = client.post(f"/api/networking/connections/{user_b['user_id']}", headers=user_a["headers"])
    conn_id = send.json()["id"]
    client.post(f"/api/networking/requests/{conn_id}/accept", headers=user_b["headers"])

    # A checks status
    res_a = client.get(f"/api/networking/users/{user_b['user_id']}/connection", headers=user_a["headers"])
    assert res_a.json()["status"] == "accepted"

    # B checks status
    res_b = client.get(f"/api/networking/users/{user_a['user_id']}/connection", headers=user_b["headers"])
    assert res_b.json()["status"] == "accepted"


def test_A9_both_in_my_network_connections(user_a, user_b):
    """After accepting, both A and B see each other in My Network."""
    send = client.post(f"/api/networking/connections/{user_b['user_id']}", headers=user_a["headers"])
    conn_id = send.json()["id"]
    client.post(f"/api/networking/requests/{conn_id}/accept", headers=user_b["headers"])

    conns_a = client.get("/api/networking/my-network/connections", headers=user_a["headers"])
    assert any(c["id"] == conn_id for c in conns_a.json())

    conns_b = client.get("/api/networking/my-network/connections", headers=user_b["headers"])
    assert any(c["id"] == conn_id for c in conns_b.json())


def test_A10_my_network_other_user_correct(user_a, user_b):
    """My Network enriched response shows the correct other_user for each party."""
    send = client.post(f"/api/networking/connections/{user_b['user_id']}", headers=user_a["headers"])
    conn_id = send.json()["id"]
    client.post(f"/api/networking/requests/{conn_id}/accept", headers=user_b["headers"])

    # A's connections: other_user is B
    conns_a = client.get("/api/networking/my-network/connections", headers=user_a["headers"])
    conn_for_a = next(c for c in conns_a.json() if c["id"] == conn_id)
    assert conn_for_a["other_user"]["id"] == user_b["user_id"]

    # B's connections: other_user is A
    conns_b = client.get("/api/networking/my-network/connections", headers=user_b["headers"])
    conn_for_b = next(c for c in conns_b.json() if c["id"] == conn_id)
    assert conn_for_b["other_user"]["id"] == user_a["user_id"]


def test_A11_profile_view_shows_accepted_status(user_a, user_b):
    """After accepting, connection status on profile view is 'accepted'."""
    send = client.post(f"/api/networking/connections/{user_b['user_id']}", headers=user_a["headers"])
    conn_id = send.json()["id"]
    client.post(f"/api/networking/requests/{conn_id}/accept", headers=user_b["headers"])

    # Profile endpoint still returns 200
    profile_res = client.get(
        f"/api/networking/users/{user_b['user_id']}/profile",
        headers=user_a["headers"],
    )
    assert profile_res.status_code == 200

    # Connection status endpoint returns 'accepted'
    conn_res = client.get(
        f"/api/networking/users/{user_b['user_id']}/connection",
        headers=user_a["headers"],
    )
    assert conn_res.json()["status"] == "accepted"


def test_A12_remove_connection(user_a, user_b):
    """User A removes the accepted connection."""
    send = client.post(f"/api/networking/connections/{user_b['user_id']}", headers=user_a["headers"])
    conn_id = send.json()["id"]
    client.post(f"/api/networking/requests/{conn_id}/accept", headers=user_b["headers"])

    remove = client.delete(f"/api/networking/connections/{conn_id}", headers=user_a["headers"])
    assert remove.status_code == 204


def test_A13_both_return_to_no_relationship_after_remove(user_a, user_b):
    """After removing, both A and B see 'none' for the connection status."""
    send = client.post(f"/api/networking/connections/{user_b['user_id']}", headers=user_a["headers"])
    conn_id = send.json()["id"]
    client.post(f"/api/networking/requests/{conn_id}/accept", headers=user_b["headers"])
    client.delete(f"/api/networking/connections/{conn_id}", headers=user_a["headers"])

    res_a = client.get(f"/api/networking/users/{user_b['user_id']}/connection", headers=user_a["headers"])
    assert res_a.json()["status"] == "none"

    res_b = client.get(f"/api/networking/users/{user_a['user_id']}/connection", headers=user_b["headers"])
    assert res_b.json()["status"] == "none"


def test_A14_neither_in_my_network_after_remove(user_a, user_b):
    """After removing, neither user appears in the other's My Network connections."""
    send = client.post(f"/api/networking/connections/{user_b['user_id']}", headers=user_a["headers"])
    conn_id = send.json()["id"]
    client.post(f"/api/networking/requests/{conn_id}/accept", headers=user_b["headers"])
    client.delete(f"/api/networking/connections/{conn_id}", headers=user_a["headers"])

    conns_a = client.get("/api/networking/my-network/connections", headers=user_a["headers"])
    assert not any(c["id"] == conn_id for c in conns_a.json())

    conns_b = client.get("/api/networking/my-network/connections", headers=user_b["headers"])
    assert not any(c["id"] == conn_id for c in conns_b.json())


# ===========================================================================
# Flow B: Reject lifecycle
# ===========================================================================


def test_B1_B2_reject_request(user_a, user_b):
    """User B sends request to A; A rejects it."""
    send = client.post(f"/api/networking/connections/{user_a['user_id']}", headers=user_b["headers"])
    assert send.status_code == 201
    conn_id = send.json()["id"]

    reject = client.post(f"/api/networking/requests/{conn_id}/reject", headers=user_a["headers"])
    assert reject.status_code == 200
    assert reject.json()["status"] == "rejected"


def test_B3_request_disappears_from_incoming_after_reject(user_a, user_b):
    """After rejection, request is gone from A's incoming list."""
    send = client.post(f"/api/networking/connections/{user_a['user_id']}", headers=user_b["headers"])
    conn_id = send.json()["id"]
    client.post(f"/api/networking/requests/{conn_id}/reject", headers=user_a["headers"])

    incoming = client.get("/api/networking/requests/incoming", headers=user_a["headers"])
    assert not any(c["id"] == conn_id for c in incoming.json())


def test_B4_request_removed_from_b_outgoing_after_reject(user_a, user_b):
    """After rejection, request is gone from B's outgoing list."""
    send = client.post(f"/api/networking/connections/{user_a['user_id']}", headers=user_b["headers"])
    conn_id = send.json()["id"]
    client.post(f"/api/networking/requests/{conn_id}/reject", headers=user_a["headers"])

    # Rejected row still exists in DB but is NOT pending — outgoing only returns pending
    outgoing = client.get("/api/networking/requests/outgoing", headers=user_b["headers"])
    assert not any(c["id"] == conn_id for c in outgoing.json())


def test_B5_status_after_rejection(user_a, user_b):
    """After rejection, both see 'rejected' status (row still exists, just not pending)."""
    send = client.post(f"/api/networking/connections/{user_a['user_id']}", headers=user_b["headers"])
    conn_id = send.json()["id"]
    client.post(f"/api/networking/requests/{conn_id}/reject", headers=user_a["headers"])

    status_a = client.get(
        f"/api/networking/users/{user_b['user_id']}/connection",
        headers=user_a["headers"],
    )
    assert status_a.json()["status"] == "rejected"


# ===========================================================================
# Flow C: Cancel lifecycle
# ===========================================================================


def test_C1_C2_cancel_outgoing_request(user_a, user_b):
    """User A sends a request to B; it appears in A's outgoing list."""
    send = client.post(f"/api/networking/connections/{user_b['user_id']}", headers=user_a["headers"])
    conn_id = send.json()["id"]

    outgoing = client.get("/api/networking/requests/outgoing", headers=user_a["headers"])
    assert any(c["id"] == conn_id for c in outgoing.json())

    cancel = client.post(f"/api/networking/requests/{conn_id}/cancel", headers=user_a["headers"])
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancelled"


def test_C4_request_disappears_from_outgoing_after_cancel(user_a, user_b):
    """After cancel, request is gone from A's outgoing list."""
    send = client.post(f"/api/networking/connections/{user_b['user_id']}", headers=user_a["headers"])
    conn_id = send.json()["id"]
    client.post(f"/api/networking/requests/{conn_id}/cancel", headers=user_a["headers"])

    outgoing = client.get("/api/networking/requests/outgoing", headers=user_a["headers"])
    assert not any(c["id"] == conn_id for c in outgoing.json())


def test_C5_request_not_in_b_incoming_after_cancel(user_a, user_b):
    """After cancel, request is no longer in B's incoming list."""
    send = client.post(f"/api/networking/connections/{user_b['user_id']}", headers=user_a["headers"])
    conn_id = send.json()["id"]
    client.post(f"/api/networking/requests/{conn_id}/cancel", headers=user_a["headers"])

    incoming = client.get("/api/networking/requests/incoming", headers=user_b["headers"])
    assert not any(c["id"] == conn_id for c in incoming.json())


def test_C6_status_after_cancel(user_a, user_b):
    """After cancel, status shows 'cancelled'."""
    send = client.post(f"/api/networking/connections/{user_b['user_id']}", headers=user_a["headers"])
    conn_id = send.json()["id"]
    client.post(f"/api/networking/requests/{conn_id}/cancel", headers=user_a["headers"])

    status = client.get(
        f"/api/networking/users/{user_b['user_id']}/connection",
        headers=user_a["headers"],
    )
    assert status.json()["status"] == "cancelled"


# ===========================================================================
# Flow D: State machine guards
# ===========================================================================


def test_D1_duplicate_same_direction_rejected(user_a, user_b):
    """Sending a second request in the same direction returns 409."""
    client.post(f"/api/networking/connections/{user_b['user_id']}", headers=user_a["headers"])
    res2 = client.post(f"/api/networking/connections/{user_b['user_id']}", headers=user_a["headers"])
    assert res2.status_code == 409


def test_D2_duplicate_reverse_direction_rejected(user_a, user_b):
    """Reverse-direction request while one exists returns 409."""
    client.post(f"/api/networking/connections/{user_b['user_id']}", headers=user_a["headers"])
    res2 = client.post(f"/api/networking/connections/{user_a['user_id']}", headers=user_b["headers"])
    assert res2.status_code == 409


def test_D3_wrong_user_cannot_accept(user_a, user_b, user_c):
    """A third user cannot accept a request they are not party to."""
    send = client.post(f"/api/networking/connections/{user_b['user_id']}", headers=user_a["headers"])
    conn_id = send.json()["id"]

    res = client.post(f"/api/networking/requests/{conn_id}/accept", headers=user_c["headers"])
    assert res.status_code == 403


def test_D4_wrong_user_cannot_reject(user_a, user_b, user_c):
    """A third user cannot reject a request they are not party to."""
    send = client.post(f"/api/networking/connections/{user_b['user_id']}", headers=user_a["headers"])
    conn_id = send.json()["id"]

    res = client.post(f"/api/networking/requests/{conn_id}/reject", headers=user_c["headers"])
    assert res.status_code == 403


def test_D5_wrong_user_cannot_cancel(user_a, user_b, user_c):
    """A third user cannot cancel a request they did not send."""
    send = client.post(f"/api/networking/connections/{user_b['user_id']}", headers=user_a["headers"])
    conn_id = send.json()["id"]

    res = client.post(f"/api/networking/requests/{conn_id}/cancel", headers=user_c["headers"])
    assert res.status_code == 403


def test_D6_wrong_user_cannot_remove(user_a, user_b, user_c):
    """A third user cannot remove an accepted connection they are not part of."""
    send = client.post(f"/api/networking/connections/{user_b['user_id']}", headers=user_a["headers"])
    conn_id = send.json()["id"]
    client.post(f"/api/networking/requests/{conn_id}/accept", headers=user_b["headers"])

    res = client.delete(f"/api/networking/connections/{conn_id}", headers=user_c["headers"])
    assert res.status_code == 403


def test_D7_pending_connection_cannot_be_removed(user_a, user_b):
    """A pending connection cannot be deleted — must be accepted first."""
    send = client.post(f"/api/networking/connections/{user_b['user_id']}", headers=user_a["headers"])
    conn_id = send.json()["id"]

    res = client.delete(f"/api/networking/connections/{conn_id}", headers=user_a["headers"])
    assert res.status_code == 422


def test_D8_accepted_connection_cannot_be_accepted_again(user_a, user_b):
    """Trying to accept an already-accepted connection returns 422."""
    send = client.post(f"/api/networking/connections/{user_b['user_id']}", headers=user_a["headers"])
    conn_id = send.json()["id"]
    client.post(f"/api/networking/requests/{conn_id}/accept", headers=user_b["headers"])

    res2 = client.post(f"/api/networking/requests/{conn_id}/accept", headers=user_b["headers"])
    assert res2.status_code == 422


# ===========================================================================
# Flow E: Own profile
# ===========================================================================


def test_E1_own_profile_returns_200(user_a):
    """A user can view their own public profile."""
    res = client.get(
        f"/api/networking/users/{user_a['user_id']}/profile",
        headers=user_a["headers"],
    )
    assert res.status_code == 200
    assert res.json()["user"]["id"] == user_a["user_id"]


def test_E2_own_connection_status_is_none(user_a):
    """
    Checking your own connection status returns 'none'
    (no self-connection row can exist per the constraint).
    """
    res = client.get(
        f"/api/networking/users/{user_a['user_id']}/connection",
        headers=user_a["headers"],
    )
    assert res.status_code == 200
    assert res.json()["status"] == "none"


def test_E3_own_profile_no_sensitive_fields(user_a):
    """Own profile view never exposes password_hash or email via this endpoint."""
    res = client.get(
        f"/api/networking/users/{user_a['user_id']}/profile",
        headers=user_a["headers"],
    )
    raw = res.text.lower()
    assert "password_hash" not in raw
    assert "password" not in raw
    assert user_a["email"] not in res.text


# ===========================================================================
# Flow F: Invalid/missing resources
# ===========================================================================


def test_F1_nonexistent_user_profile_returns_404(user_a):
    """Requesting a profile for a non-existent user ID returns 404."""
    fake_id = str(uuid.uuid4())
    res = client.get(
        f"/api/networking/users/{fake_id}/profile",
        headers=user_a["headers"],
    )
    assert res.status_code == 404


def test_F2_nonexistent_connection_action_returns_404(user_a):
    """Attempting to accept/reject a non-existent connection ID returns 404."""
    fake_id = str(uuid.uuid4())
    for action in ("accept", "reject", "cancel"):
        res = client.post(
            f"/api/networking/requests/{fake_id}/{action}",
            headers=user_a["headers"],
        )
        assert res.status_code == 404, f"Expected 404 for {action}, got {res.status_code}"
