"""
Networking Phase 5.2 — Connection Service tests.

Tests exercise the service layer directly against PostgreSQL (no HTTP layer).
Each test gets a session that is always rolled back on teardown so tests are
fully isolated without needing to truncate tables.

Requires Docker infrastructure:
  docker compose up -d postgres
and a valid DATABASE_URL in the environment or .env.

Covered scenarios
-----------------
 1. Successful connection request
 2. Self-request is rejected (400)
 3. Duplicate same-direction request is rejected (409)
 4. Duplicate reverse-direction request is rejected (409)
 5. Accept by receiver succeeds
 6. Accept by wrong user is rejected (403)
 7. Reject by receiver succeeds
 8. Reject by wrong user is rejected (403)
 9. Cancel by requester succeeds
10. Cancel by wrong user is rejected (403)
11. Invalid status transitions (accept/reject/cancel non-pending)
12. Remove accepted connection by a party succeeds
13. Remove by unrelated user is rejected (403)
14. Direction-independent relationship lookup
15. get_pending_requests_for_user returns only incoming pending
16. get_sent_pending_requests returns only outgoing pending
17. get_accepted_connections returns connections for either party
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.db.models import Connection, ConnectionStatus, User
from app.db.session import Base, SessionLocal, engine
from app.services import connection_service as svc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _new_user(tag: str) -> User:
    uid = str(uuid.uuid4())
    return User(
        id=uid,
        first_name="Net",
        last_name="Test",
        username=f"svc_test_{tag}_{uid[:8]}",
        email=f"svc_test_{uid}@example.com",
        password_hash="hashed",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def ensure_tables():
    """Ensure all tables exist before each test."""
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def db():
    """
    DB session that is always rolled back on teardown.
    The service functions commit internally; the rollback here undoes those
    commits for test isolation because PostgreSQL supports transactional DDL
    only for schema, not data — so we rely on the explicit rollback.

    Note: because the service commits inside the *same* connection, the
    rollback at the end of each test undoes all data changes made during
    that test.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def two_users(db):
    u1 = _new_user("p")
    u2 = _new_user("q")
    db.add_all([u1, u2])
    db.flush()
    return u1, u2


@pytest.fixture()
def three_users(db):
    u1 = _new_user("r")
    u2 = _new_user("s")
    u3 = _new_user("t")
    db.add_all([u1, u2, u3])
    db.flush()
    return u1, u2, u3


@pytest.fixture()
def pending_conn(db, two_users):
    """A single pending connection u1 -> u2, already committed."""
    u1, u2 = two_users
    return svc.send_connection_request(db, u1, u2), u1, u2


@pytest.fixture()
def accepted_conn(db, two_users):
    """A single accepted connection u1 -> u2."""
    u1, u2 = two_users
    conn = svc.send_connection_request(db, u1, u2)
    conn = svc.accept_connection_request(db, conn, u2)
    return conn, u1, u2


# ---------------------------------------------------------------------------
# 1. Successful connection request
# ---------------------------------------------------------------------------


def test_send_connection_request_creates_pending(db, two_users):
    u1, u2 = two_users
    conn = svc.send_connection_request(db, u1, u2)

    assert conn.id is not None
    assert conn.requester_id == u1.id
    assert conn.receiver_id == u2.id
    assert conn.status == ConnectionStatus.pending
    assert conn.canonical_a == min(u1.id, u2.id)
    assert conn.canonical_b == max(u1.id, u2.id)
    assert conn.created_at is not None
    assert conn.updated_at is not None


# ---------------------------------------------------------------------------
# 2. Self-request is rejected
# ---------------------------------------------------------------------------


def test_send_request_to_self_raises_400(db, two_users):
    u1, _ = two_users
    with pytest.raises(HTTPException) as exc_info:
        svc.send_connection_request(db, u1, u1)
    assert exc_info.value.status_code == 400
    assert "themselves" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# 3. Duplicate same-direction request is rejected
# ---------------------------------------------------------------------------


def test_duplicate_same_direction_raises_409(db, two_users):
    u1, u2 = two_users
    svc.send_connection_request(db, u1, u2)

    with pytest.raises(HTTPException) as exc_info:
        svc.send_connection_request(db, u1, u2)
    assert exc_info.value.status_code == 409


# ---------------------------------------------------------------------------
# 4. Duplicate reverse-direction request is rejected
# ---------------------------------------------------------------------------


def test_duplicate_reverse_direction_raises_409(db, two_users):
    u1, u2 = two_users
    svc.send_connection_request(db, u1, u2)

    with pytest.raises(HTTPException) as exc_info:
        svc.send_connection_request(db, u2, u1)
    assert exc_info.value.status_code == 409


# ---------------------------------------------------------------------------
# 5. Accept by receiver succeeds
# ---------------------------------------------------------------------------


def test_accept_by_receiver_succeeds(db, pending_conn):
    conn, u1, u2 = pending_conn
    updated = svc.accept_connection_request(db, conn, u2)

    assert updated.status == ConnectionStatus.accepted


# ---------------------------------------------------------------------------
# 6. Accept by wrong user is rejected
# ---------------------------------------------------------------------------


def test_accept_by_requester_raises_403(db, pending_conn):
    conn, u1, u2 = pending_conn
    with pytest.raises(HTTPException) as exc_info:
        svc.accept_connection_request(db, conn, u1)  # u1 is requester, not receiver
    assert exc_info.value.status_code == 403


def test_accept_by_unrelated_user_raises_403(db, pending_conn, three_users):
    conn, u1, u2 = pending_conn
    u_other = three_users[2]
    with pytest.raises(HTTPException) as exc_info:
        svc.accept_connection_request(db, conn, u_other)
    assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# 7. Reject by receiver succeeds
# ---------------------------------------------------------------------------


def test_reject_by_receiver_succeeds(db, pending_conn):
    conn, u1, u2 = pending_conn
    updated = svc.reject_connection_request(db, conn, u2)

    assert updated.status == ConnectionStatus.rejected


# ---------------------------------------------------------------------------
# 8. Reject by wrong user is rejected
# ---------------------------------------------------------------------------


def test_reject_by_requester_raises_403(db, pending_conn):
    conn, u1, u2 = pending_conn
    with pytest.raises(HTTPException) as exc_info:
        svc.reject_connection_request(db, conn, u1)
    assert exc_info.value.status_code == 403


def test_reject_by_unrelated_user_raises_403(db, pending_conn, three_users):
    conn, u1, u2 = pending_conn
    u_other = three_users[2]
    with pytest.raises(HTTPException) as exc_info:
        svc.reject_connection_request(db, conn, u_other)
    assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# 9. Cancel by requester succeeds
# ---------------------------------------------------------------------------


def test_cancel_by_requester_succeeds(db, pending_conn):
    conn, u1, u2 = pending_conn
    updated = svc.cancel_connection_request(db, conn, u1)

    assert updated.status == ConnectionStatus.cancelled


# ---------------------------------------------------------------------------
# 10. Cancel by wrong user is rejected
# ---------------------------------------------------------------------------


def test_cancel_by_receiver_raises_403(db, pending_conn):
    conn, u1, u2 = pending_conn
    with pytest.raises(HTTPException) as exc_info:
        svc.cancel_connection_request(db, conn, u2)  # u2 is receiver, not requester
    assert exc_info.value.status_code == 403


def test_cancel_by_unrelated_user_raises_403(db, pending_conn, three_users):
    conn, u1, u2 = pending_conn
    u_other = three_users[2]
    with pytest.raises(HTTPException) as exc_info:
        svc.cancel_connection_request(db, conn, u_other)
    assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# 11. Invalid status transitions
# ---------------------------------------------------------------------------


def test_accept_already_accepted_raises_422(db, accepted_conn):
    conn, u1, u2 = accepted_conn
    with pytest.raises(HTTPException) as exc_info:
        svc.accept_connection_request(db, conn, u2)
    assert exc_info.value.status_code == 422


def test_reject_already_accepted_raises_422(db, accepted_conn):
    conn, u1, u2 = accepted_conn
    with pytest.raises(HTTPException) as exc_info:
        svc.reject_connection_request(db, conn, u2)
    assert exc_info.value.status_code == 422


def test_cancel_already_accepted_raises_422(db, accepted_conn):
    conn, u1, u2 = accepted_conn
    with pytest.raises(HTTPException) as exc_info:
        svc.cancel_connection_request(db, conn, u1)
    assert exc_info.value.status_code == 422


def test_accept_rejected_request_raises_422(db, pending_conn):
    conn, u1, u2 = pending_conn
    svc.reject_connection_request(db, conn, u2)
    with pytest.raises(HTTPException) as exc_info:
        svc.accept_connection_request(db, conn, u2)
    assert exc_info.value.status_code == 422


def test_cancel_cancelled_request_raises_422(db, pending_conn):
    conn, u1, u2 = pending_conn
    svc.cancel_connection_request(db, conn, u1)
    with pytest.raises(HTTPException) as exc_info:
        svc.cancel_connection_request(db, conn, u1)
    assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# 12. Remove accepted connection by a party
# ---------------------------------------------------------------------------


def test_remove_accepted_by_requester(db, accepted_conn):
    conn, u1, u2 = accepted_conn
    conn_id = conn.id
    svc.remove_connection(db, conn, u1)

    remaining = db.query(Connection).filter_by(id=conn_id).first()
    assert remaining is None


def test_remove_accepted_by_receiver(db, accepted_conn):
    conn, u1, u2 = accepted_conn
    conn_id = conn.id
    svc.remove_connection(db, conn, u2)

    remaining = db.query(Connection).filter_by(id=conn_id).first()
    assert remaining is None


# ---------------------------------------------------------------------------
# 13. Remove by unrelated user is rejected
# ---------------------------------------------------------------------------


def test_remove_by_unrelated_user_raises_403(db, accepted_conn, three_users):
    conn, u1, u2 = accepted_conn
    u_other = three_users[2]
    with pytest.raises(HTTPException) as exc_info:
        svc.remove_connection(db, conn, u_other)
    assert exc_info.value.status_code == 403
    # Connection must still exist
    assert db.query(Connection).filter_by(id=conn.id).first() is not None


def test_remove_pending_connection_raises_422(db, pending_conn):
    conn, u1, u2 = pending_conn
    with pytest.raises(HTTPException) as exc_info:
        svc.remove_connection(db, conn, u1)
    assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# 14. Direction-independent relationship lookup
# ---------------------------------------------------------------------------


def test_get_connection_between_users_a_to_b(db, pending_conn):
    conn, u1, u2 = pending_conn
    found = svc.get_connection_between_users(db, u1.id, u2.id)
    assert found is not None
    assert found.id == conn.id


def test_get_connection_between_users_b_to_a(db, pending_conn):
    """Lookup in the reverse direction must return the same row."""
    conn, u1, u2 = pending_conn
    found = svc.get_connection_between_users(db, u2.id, u1.id)
    assert found is not None
    assert found.id == conn.id


def test_get_connection_between_users_no_relationship(db, two_users):
    u1, u2 = two_users
    assert svc.get_connection_between_users(db, u1.id, u2.id) is None


# ---------------------------------------------------------------------------
# 15. get_pending_requests_for_user  (incoming)
# ---------------------------------------------------------------------------


def test_get_pending_requests_for_user_returns_incoming(db, three_users):
    u1, u2, u3 = three_users
    # u1 -> u2 and u3 -> u2 are both incoming for u2
    conn_a = svc.send_connection_request(db, u1, u2)
    conn_b = svc.send_connection_request(db, u3, u2)
    # u1 -> u3 is not directed at u2, so must not appear in u2's incoming list
    conn_c = svc.send_connection_request(db, u1, u3)

    incoming = svc.get_pending_requests_for_user(db, u2)
    incoming_ids = {c.id for c in incoming}

    assert conn_a.id in incoming_ids
    assert conn_b.id in incoming_ids
    assert conn_c.id not in incoming_ids


def test_get_pending_requests_for_user_excludes_non_pending(db, two_users):
    u1, u2 = two_users
    conn = svc.send_connection_request(db, u1, u2)
    svc.accept_connection_request(db, conn, u2)

    incoming = svc.get_pending_requests_for_user(db, u2)
    assert all(c.id != conn.id for c in incoming)


# ---------------------------------------------------------------------------
# 16. get_sent_pending_requests  (outgoing)
# ---------------------------------------------------------------------------


def test_get_sent_pending_requests_returns_outgoing(db, three_users):
    u1, u2, u3 = three_users
    conn_a = svc.send_connection_request(db, u1, u2)
    conn_b = svc.send_connection_request(db, u1, u3)
    # u2->u1 would conflict; send u2->u3 as an unrelated request
    conn_c = svc.send_connection_request(db, u2, u3)

    outgoing = svc.get_sent_pending_requests(db, u1)
    outgoing_ids = {c.id for c in outgoing}

    assert conn_a.id in outgoing_ids
    assert conn_b.id in outgoing_ids
    assert conn_c.id not in outgoing_ids


def test_get_sent_pending_requests_excludes_non_pending(db, two_users):
    u1, u2 = two_users
    conn = svc.send_connection_request(db, u1, u2)
    svc.reject_connection_request(db, conn, u2)

    outgoing = svc.get_sent_pending_requests(db, u1)
    assert all(c.id != conn.id for c in outgoing)


# ---------------------------------------------------------------------------
# 17. get_accepted_connections returns connections for either party
# ---------------------------------------------------------------------------


def test_get_accepted_connections_returns_for_requester(db, accepted_conn):
    conn, u1, u2 = accepted_conn
    results = svc.get_accepted_connections(db, u1)
    assert any(c.id == conn.id for c in results)


def test_get_accepted_connections_returns_for_receiver(db, accepted_conn):
    conn, u1, u2 = accepted_conn
    results = svc.get_accepted_connections(db, u2)
    assert any(c.id == conn.id for c in results)


def test_get_accepted_connections_excludes_pending(db, pending_conn):
    conn, u1, u2 = pending_conn
    assert all(c.id != conn.id for c in svc.get_accepted_connections(db, u1))
    assert all(c.id != conn.id for c in svc.get_accepted_connections(db, u2))


def test_get_accepted_connections_excludes_unrelated_user(db, accepted_conn, three_users):
    conn, u1, u2 = accepted_conn
    u_other = three_users[2]
    results = svc.get_accepted_connections(db, u_other)
    assert all(c.id != conn.id for c in results)
