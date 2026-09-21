"""
Phase 5.5 — My Network enriched endpoint tests.

Tests cover the three enriched endpoints added for the My Network page:

  GET /api/networking/my-network/connections
  GET /api/networking/my-network/requests/incoming
  GET /api/networking/my-network/requests/outgoing

Each endpoint returns EnrichedConnectionResponse which embeds an
``other_user`` (ConnectionUserSummary) so the frontend can render
cards without secondary per-user requests.

Test index
----------
Authentication
  A1. Unauthenticated requests are rejected (401)
  A2. Authenticated requests succeed (200)

My Connections — /my-network/connections
  B1. Returns accepted connection where current user is requester
  B2. Returns accepted connection where current user is receiver
  B3. other_user is the counterpart (not the current user)
  B4. Status in response is "accepted"
  B5. Unrelated accepted connections are not returned
  B6. Returns empty list when user has no accepted connections

Incoming Requests — /my-network/requests/incoming
  C1. Returns pending request received by current user
  C2. other_user is the requester
  C3. Status in response is "pending"
  C4. Outgoing requests are not returned in incoming
  C5. Unrelated incoming requests are not returned
  C6. Returns empty list when user has no incoming requests

Outgoing Requests — /my-network/requests/outgoing
  D1. Returns pending request sent by current user
  D2. other_user is the receiver
  D3. Status in response is "pending"
  D4. Incoming requests are not returned in outgoing
  D5. Unrelated outgoing requests are not returned
  D6. Returns empty list when user has no outgoing requests

User scoping / JWT isolation
  E1. User A's connections endpoint only returns A's data (not B's)
  E2. User A's incoming endpoint only returns A's incoming (not B's)
  E3. User A's outgoing endpoint only returns A's outgoing (not B's)
  E4. Current user is always derived from JWT, not any query parameter

Response safety — other_user field
  F1. other_user contains expected public fields
  F2. other_user does NOT contain password_hash or email
  F3. other_user does NOT contain any authentication token
  F4. Top-level response does not expose sensitive user data
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
# Expected public fields on other_user
# ---------------------------------------------------------------------------

_EXPECTED_OTHER_USER_FIELDS = {"id", "username", "first_name", "last_name", "headline", "location", "profile_photo_url"}
_FORBIDDEN_FIELDS = {"password_hash", "password", "email", "access_token", "secret_key", "token"}

# ---------------------------------------------------------------------------
# Helpers — reuse the same pattern as test_networking_api.py
# ---------------------------------------------------------------------------

_COUNTER = 0


def _tag() -> str:
    global _COUNTER
    _COUNTER += 1
    return f"mn{_COUNTER}_{uuid.uuid4().hex[:6]}"


def _seed_otp(email: str) -> str:
    token = f"test-token-{uuid.uuid4().hex}"
    token_hash = hashlib.sha256(
        f"{email}:{token}:{settings.SECRET_KEY}".encode()
    ).hexdigest()
    payload = json.dumps({"otp": "123456", "verified_token": token_hash, "token_raw": token})
    redis_client.set(f"otp:{email}", payload, ex=600)
    return token


def _register(tag: Optional[str] = None) -> dict:
    if tag is None:
        tag = _tag()
    email = f"mn_{tag}@example.com"
    username = f"mn_{tag}"[:30]
    res = client.post("/api/auth/register", json={
        "first_name": "MyNet",
        "last_name": "Tester",
        "username": username,
        "email": email,
        "password": "Password123",
        "email_verification_token": _seed_otp(email),
    })
    assert res.status_code == 201, f"Register failed: {res.text}"
    uid = res.json()["id"]

    login = client.post("/api/auth/login", json={"identifier": username, "password": "Password123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"user_id": uid, "username": username, "email": email,
            "headers": {"Authorization": f"Bearer {token}"}}


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


def _send(from_headers: dict, to_user_id: str) -> str:
    """Send a connection request; return the connection_id."""
    res = client.post(f"/api/networking/connections/{to_user_id}", headers=from_headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _accept(conn_id: str, receiver_headers: dict) -> None:
    res = client.post(f"/api/networking/requests/{conn_id}/accept", headers=receiver_headers)
    assert res.status_code == 200, res.text


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


@pytest.fixture()
def accepted_ab(user_a, user_b):
    """Accepted A→B connection. Returns conn_id."""
    conn_id = _send(user_a["headers"], user_b["user_id"])
    _accept(conn_id, user_b["headers"])
    return conn_id


@pytest.fixture()
def pending_ba(user_b, user_a):
    """Pending B→A request (incoming for A). Returns conn_id."""
    return _send(user_b["headers"], user_a["user_id"])


@pytest.fixture()
def pending_ab(user_a, user_b):
    """Pending A→B request (outgoing from A). Returns conn_id."""
    return _send(user_a["headers"], user_b["user_id"])


# ===========================================================================
# A. Authentication
# ===========================================================================


def test_A1_unauthenticated_connections_rejected():
    assert client.get("/api/networking/my-network/connections").status_code == 401


def test_A1_unauthenticated_incoming_rejected():
    assert client.get("/api/networking/my-network/requests/incoming").status_code == 401


def test_A1_unauthenticated_outgoing_rejected():
    assert client.get("/api/networking/my-network/requests/outgoing").status_code == 401


def test_A2_authenticated_connections_succeeds(user_a):
    res = client.get("/api/networking/my-network/connections", headers=user_a["headers"])
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_A2_authenticated_incoming_succeeds(user_a):
    res = client.get("/api/networking/my-network/requests/incoming", headers=user_a["headers"])
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_A2_authenticated_outgoing_succeeds(user_a):
    res = client.get("/api/networking/my-network/requests/outgoing", headers=user_a["headers"])
    assert res.status_code == 200
    assert isinstance(res.json(), list)


# ===========================================================================
# B. My Connections
# ===========================================================================


def test_B1_accepted_connection_appears_for_requester(accepted_ab, user_a, user_b):
    res = client.get("/api/networking/my-network/connections", headers=user_a["headers"])
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1
    conn_ids = [c["id"] for c in data]
    assert accepted_ab in conn_ids


def test_B2_accepted_connection_appears_for_receiver(accepted_ab, user_a, user_b):
    res = client.get("/api/networking/my-network/connections", headers=user_b["headers"])
    assert res.status_code == 200
    data = res.json()
    conn_ids = [c["id"] for c in data]
    assert accepted_ab in conn_ids


def test_B3_other_user_is_counterpart_for_requester(accepted_ab, user_a, user_b):
    """When A fetches connections, other_user must be B (not A)."""
    res = client.get("/api/networking/my-network/connections", headers=user_a["headers"])
    conn = next(c for c in res.json() if c["id"] == accepted_ab)
    assert conn["other_user"]["id"] == user_b["user_id"]
    assert conn["other_user"]["username"] == user_b["username"]


def test_B3_other_user_is_counterpart_for_receiver(accepted_ab, user_a, user_b):
    """When B fetches connections, other_user must be A (not B)."""
    res = client.get("/api/networking/my-network/connections", headers=user_b["headers"])
    conn = next(c for c in res.json() if c["id"] == accepted_ab)
    assert conn["other_user"]["id"] == user_a["user_id"]
    assert conn["other_user"]["username"] == user_a["username"]


def test_B4_status_is_accepted(accepted_ab, user_a, user_b):
    res = client.get("/api/networking/my-network/connections", headers=user_a["headers"])
    conn = next(c for c in res.json() if c["id"] == accepted_ab)
    assert conn["status"] == "accepted"


def test_B5_unrelated_connections_not_returned(accepted_ab, user_a, user_b, user_c):
    """A's connections endpoint must not include B→C connection."""
    # Create a separate B→C accepted connection that A has nothing to do with
    conn_bc_id = _send(user_b["headers"], user_c["user_id"])
    _accept(conn_bc_id, user_c["headers"])

    res = client.get("/api/networking/my-network/connections", headers=user_a["headers"])
    conn_ids = [c["id"] for c in res.json()]
    assert conn_bc_id not in conn_ids


def test_B6_empty_list_when_no_connections(user_a):
    res = client.get("/api/networking/my-network/connections", headers=user_a["headers"])
    assert res.status_code == 200
    assert res.json() == []


# ===========================================================================
# C. Incoming Requests
# ===========================================================================


def test_C1_incoming_request_appears(pending_ba, user_a, user_b):
    res = client.get("/api/networking/my-network/requests/incoming", headers=user_a["headers"])
    assert res.status_code == 200
    conn_ids = [c["id"] for c in res.json()]
    assert pending_ba in conn_ids


def test_C2_other_user_is_requester(pending_ba, user_a, user_b):
    """For incoming requests, other_user is the sender (B), not the receiver (A)."""
    res = client.get("/api/networking/my-network/requests/incoming", headers=user_a["headers"])
    conn = next(c for c in res.json() if c["id"] == pending_ba)
    assert conn["other_user"]["id"] == user_b["user_id"]


def test_C3_status_is_pending(pending_ba, user_a, user_b):
    res = client.get("/api/networking/my-network/requests/incoming", headers=user_a["headers"])
    conn = next(c for c in res.json() if c["id"] == pending_ba)
    assert conn["status"] == "pending"


def test_C4_outgoing_not_in_incoming(user_a, user_b, user_c):
    """A→C outgoing request must not appear in A's incoming list."""
    outgoing_id = _send(user_a["headers"], user_c["user_id"])

    res = client.get("/api/networking/my-network/requests/incoming", headers=user_a["headers"])
    conn_ids = [c["id"] for c in res.json()]
    assert outgoing_id not in conn_ids


def test_C5_unrelated_incoming_not_returned(pending_ba, user_a, user_b, user_c):
    """B→C incoming (from C's perspective) must not appear in A's incoming."""
    bc_id = _send(user_b["headers"], user_c["user_id"])

    res = client.get("/api/networking/my-network/requests/incoming", headers=user_a["headers"])
    conn_ids = [c["id"] for c in res.json()]
    assert bc_id not in conn_ids


def test_C6_empty_list_when_no_incoming(user_a):
    res = client.get("/api/networking/my-network/requests/incoming", headers=user_a["headers"])
    assert res.status_code == 200
    assert res.json() == []


# ===========================================================================
# D. Outgoing Requests
# ===========================================================================


def test_D1_outgoing_request_appears(pending_ab, user_a, user_b):
    res = client.get("/api/networking/my-network/requests/outgoing", headers=user_a["headers"])
    assert res.status_code == 200
    conn_ids = [c["id"] for c in res.json()]
    assert pending_ab in conn_ids


def test_D2_other_user_is_receiver(pending_ab, user_a, user_b):
    """For outgoing requests, other_user is the receiver (B), not A."""
    res = client.get("/api/networking/my-network/requests/outgoing", headers=user_a["headers"])
    conn = next(c for c in res.json() if c["id"] == pending_ab)
    assert conn["other_user"]["id"] == user_b["user_id"]


def test_D3_status_is_pending(pending_ab, user_a, user_b):
    res = client.get("/api/networking/my-network/requests/outgoing", headers=user_a["headers"])
    conn = next(c for c in res.json() if c["id"] == pending_ab)
    assert conn["status"] == "pending"


def test_D4_incoming_not_in_outgoing(user_a, user_b, user_c):
    """C→A incoming must not appear in A's outgoing list."""
    incoming_id = _send(user_c["headers"], user_a["user_id"])

    res = client.get("/api/networking/my-network/requests/outgoing", headers=user_a["headers"])
    conn_ids = [c["id"] for c in res.json()]
    assert incoming_id not in conn_ids


def test_D5_unrelated_outgoing_not_returned(pending_ab, user_a, user_b, user_c):
    """B→C outgoing (from B's perspective) must not appear in A's outgoing."""
    bc_id = _send(user_b["headers"], user_c["user_id"])

    res = client.get("/api/networking/my-network/requests/outgoing", headers=user_a["headers"])
    conn_ids = [c["id"] for c in res.json()]
    assert bc_id not in conn_ids


def test_D6_empty_list_when_no_outgoing(user_a):
    res = client.get("/api/networking/my-network/requests/outgoing", headers=user_a["headers"])
    assert res.status_code == 200
    assert res.json() == []


# ===========================================================================
# E. User scoping / JWT isolation
# ===========================================================================


def test_E1_connections_scoped_to_jwt_user(accepted_ab, user_a, user_b, user_c):
    """
    user_c has no connections. Calling the endpoint as user_c must return []
    even though A and B have an accepted connection.
    user_c cannot see A-B data simply by calling the same endpoint.
    """
    res = client.get("/api/networking/my-network/connections", headers=user_c["headers"])
    assert res.status_code == 200
    assert res.json() == []


def test_E2_incoming_scoped_to_jwt_user(pending_ba, user_a, user_b, user_c):
    """
    B→A pending request is only in A's incoming, not C's.
    """
    res = client.get("/api/networking/my-network/requests/incoming", headers=user_c["headers"])
    assert res.status_code == 200
    conn_ids = [c["id"] for c in res.json()]
    assert pending_ba not in conn_ids


def test_E3_outgoing_scoped_to_jwt_user(pending_ab, user_a, user_b, user_c):
    """
    A→B pending request is only in A's outgoing, not C's.
    """
    res = client.get("/api/networking/my-network/requests/outgoing", headers=user_c["headers"])
    assert res.status_code == 200
    conn_ids = [c["id"] for c in res.json()]
    assert pending_ab not in conn_ids


def test_E4_endpoints_have_no_user_id_override(accepted_ab, user_a, user_b):
    """
    These endpoints accept no user_id query parameter — the current user is
    always derived from the JWT.  Passing a spurious user_id param must not
    return a different user's data (it is simply ignored).
    """
    # user_b has accepted_ab but user_a is querying; passing user_b's id
    # as a query param must have no effect — the response is still A's view.
    res = client.get(
        "/api/networking/my-network/connections",
        params={"user_id": user_b["user_id"]},
        headers=user_a["headers"],
    )
    assert res.status_code == 200
    # A is also a participant so the connection IS returned, but other_user
    # must be B — not A trying to impersonate B.
    data = res.json()
    conn = next((c for c in data if c["id"] == accepted_ab), None)
    assert conn is not None
    assert conn["other_user"]["id"] == user_b["user_id"]  # other_user is B from A's perspective


# ===========================================================================
# F. Response safety — other_user field
# ===========================================================================


def test_F1_other_user_contains_expected_public_fields(accepted_ab, user_a, user_b):
    res = client.get("/api/networking/my-network/connections", headers=user_a["headers"])
    conn = next(c for c in res.json() if c["id"] == accepted_ab)
    other = conn["other_user"]

    # All expected public fields must be present
    for field in ("id", "username", "first_name", "last_name"):
        assert field in other, f"Expected field '{field}' missing from other_user"

    # Optional public fields should be present (may be None)
    for field in ("headline", "location", "profile_photo_url"):
        assert field in other, f"Optional field '{field}' missing from other_user"


def test_F2_other_user_has_no_password_hash(accepted_ab, user_a, user_b):
    res = client.get("/api/networking/my-network/connections", headers=user_a["headers"])
    conn = next(c for c in res.json() if c["id"] == accepted_ab)
    other = conn["other_user"]

    for forbidden in _FORBIDDEN_FIELDS:
        assert forbidden not in other, (
            f"Sensitive field '{forbidden}' must NOT appear in other_user"
        )


def test_F3_other_user_has_no_auth_token(accepted_ab, user_a, user_b):
    """Verify no token/secret leaks anywhere in the enriched response."""
    res = client.get("/api/networking/my-network/connections", headers=user_a["headers"])
    conn = next(c for c in res.json() if c["id"] == accepted_ab)
    raw_json = json.dumps(conn)

    for forbidden in ("password_hash", "access_token", "secret_key", "hashed"):
        assert forbidden not in raw_json.lower(), (
            f"Sensitive value '{forbidden}' found in response JSON"
        )


def test_F4_top_level_response_safe(accepted_ab, user_a, user_b):
    """Top-level fields on EnrichedConnectionResponse must not expose user data."""
    res = client.get("/api/networking/my-network/connections", headers=user_a["headers"])
    conn = next(c for c in res.json() if c["id"] == accepted_ab)

    top_level_keys = set(conn.keys())
    expected_top = {"id", "requester_id", "receiver_id", "status", "created_at", "updated_at", "other_user"}
    assert top_level_keys == expected_top, (
        f"Unexpected top-level keys: {top_level_keys - expected_top}"
    )

    # email must not appear anywhere at the top level
    for forbidden in _FORBIDDEN_FIELDS:
        assert forbidden not in conn, (
            f"Sensitive field '{forbidden}' found at top level of EnrichedConnectionResponse"
        )
