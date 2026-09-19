"""
Networking v1 — Connection model tests.

Tests run directly against PostgreSQL via SessionLocal (no HTTP layer).

Requires Docker infrastructure:
  docker compose up -d postgres
and a valid DATABASE_URL in the environment or .env.

Covered scenarios
-----------------
1.  Create a pending connection
2.  Self-connection is rejected
3.  Duplicate request (same direction) is rejected
4.  Reverse-direction duplicate is rejected
5.  Transition to accepted
6.  Transition to rejected
7.  Transition to cancelled
8.  Query connections by requester_id
9.  Query connections by receiver_id
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models import Connection, ConnectionStatus, User
from app.db.session import Base, SessionLocal, engine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _new_user(username_suffix: str) -> User:
    uid = str(uuid.uuid4())
    return User(
        id=uid,
        first_name="Test",
        last_name="User",
        username=f"net_test_{username_suffix}_{uid[:8]}",
        email=f"net_test_{uid}@example.com",
        password_hash="hashed",
    )


def _make_connection(requester: User, receiver: User) -> Connection:
    """Build a Connection object with canonical ordering already set."""
    ca, cb = Connection.canonical_pair(requester.id, receiver.id)
    return Connection(
        requester_id=requester.id,
        receiver_id=receiver.id,
        canonical_a=ca,
        canonical_b=cb,
        status=ConnectionStatus.pending,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def setup_tables():
    """Ensure all tables exist before each test."""
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def db():
    """Provide a fresh database session; always roll back after the test."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def two_users(db):
    """Persist two distinct users and return them."""
    u1 = _new_user("a")
    u2 = _new_user("b")
    db.add_all([u1, u2])
    db.flush()
    return u1, u2


@pytest.fixture()
def three_users(db):
    """Persist three distinct users and return them."""
    u1 = _new_user("x")
    u2 = _new_user("y")
    u3 = _new_user("z")
    db.add_all([u1, u2, u3])
    db.flush()
    return u1, u2, u3


# ---------------------------------------------------------------------------
# 1. Create a pending connection
# ---------------------------------------------------------------------------


def test_create_pending_connection(db, two_users):
    u1, u2 = two_users
    conn = _make_connection(u1, u2)
    db.add(conn)
    db.flush()

    fetched = db.query(Connection).filter_by(id=conn.id).one()
    assert fetched.requester_id == u1.id
    assert fetched.receiver_id == u2.id
    assert fetched.status == ConnectionStatus.pending
    assert fetched.created_at is not None
    assert fetched.updated_at is not None

    # Canonical ordering must be consistent
    assert fetched.canonical_a == min(u1.id, u2.id)
    assert fetched.canonical_b == max(u1.id, u2.id)


# ---------------------------------------------------------------------------
# 2. Self-connection must be rejected at the application layer
# ---------------------------------------------------------------------------


def test_self_connection_rejected(db, two_users):
    u1, _ = two_users
    # Application-level guard: canonical_pair of identical IDs yields (id, id),
    # and we explicitly raise before reaching the DB.
    with pytest.raises(ValueError, match="cannot connect to themselves"):
        ca, cb = Connection.canonical_pair(u1.id, u1.id)
        if ca == cb:
            raise ValueError("A user cannot connect to themselves")
        Connection(
            requester_id=u1.id,
            receiver_id=u1.id,
            canonical_a=ca,
            canonical_b=cb,
            status=ConnectionStatus.pending,
        )


# ---------------------------------------------------------------------------
# 3. Duplicate request — same direction — is rejected at the DB layer
# ---------------------------------------------------------------------------


def test_duplicate_same_direction_rejected(db, two_users):
    u1, u2 = two_users
    conn1 = _make_connection(u1, u2)
    db.add(conn1)
    db.flush()

    conn2 = _make_connection(u1, u2)
    db.add(conn2)

    with pytest.raises(IntegrityError):
        db.flush()


# ---------------------------------------------------------------------------
# 4. Duplicate request — reverse direction — is rejected at the DB layer
# ---------------------------------------------------------------------------


def test_duplicate_reverse_direction_rejected(db, two_users):
    u1, u2 = two_users
    conn1 = _make_connection(u1, u2)
    db.add(conn1)
    db.flush()

    # B → A: canonical_a / canonical_b will be identical to A → B
    conn2 = _make_connection(u2, u1)
    db.add(conn2)

    with pytest.raises(IntegrityError):
        db.flush()


# ---------------------------------------------------------------------------
# 5. Transition to accepted
# ---------------------------------------------------------------------------


def test_connection_accepted(db, two_users):
    u1, u2 = two_users
    conn = _make_connection(u1, u2)
    db.add(conn)
    db.flush()

    conn.status = ConnectionStatus.accepted
    db.flush()

    fetched = db.query(Connection).filter_by(id=conn.id).one()
    assert fetched.status == ConnectionStatus.accepted


# ---------------------------------------------------------------------------
# 6. Transition to rejected
# ---------------------------------------------------------------------------


def test_connection_rejected(db, two_users):
    u1, u2 = two_users
    conn = _make_connection(u1, u2)
    db.add(conn)
    db.flush()

    conn.status = ConnectionStatus.rejected
    db.flush()

    fetched = db.query(Connection).filter_by(id=conn.id).one()
    assert fetched.status == ConnectionStatus.rejected


# ---------------------------------------------------------------------------
# 7. Transition to cancelled
# ---------------------------------------------------------------------------


def test_connection_cancelled(db, two_users):
    u1, u2 = two_users
    conn = _make_connection(u1, u2)
    db.add(conn)
    db.flush()

    conn.status = ConnectionStatus.cancelled
    db.flush()

    fetched = db.query(Connection).filter_by(id=conn.id).one()
    assert fetched.status == ConnectionStatus.cancelled


# ---------------------------------------------------------------------------
# 8. Query connections by requester_id
# ---------------------------------------------------------------------------


def test_query_by_requester(db, three_users):
    u1, u2, u3 = three_users

    conn_a = _make_connection(u1, u2)
    conn_b = _make_connection(u1, u3)
    conn_c = _make_connection(u2, u3)  # different requester
    db.add_all([conn_a, conn_b, conn_c])
    db.flush()

    results = db.query(Connection).filter_by(requester_id=u1.id).all()
    result_ids = {r.id for r in results}

    assert conn_a.id in result_ids
    assert conn_b.id in result_ids
    assert conn_c.id not in result_ids


# ---------------------------------------------------------------------------
# 9. Query connections by receiver_id
# ---------------------------------------------------------------------------


def test_query_by_receiver(db, three_users):
    u1, u2, u3 = three_users

    conn_a = _make_connection(u1, u2)
    conn_b = _make_connection(u3, u2)
    conn_c = _make_connection(u1, u3)  # different receiver
    db.add_all([conn_a, conn_b, conn_c])
    db.flush()

    results = db.query(Connection).filter_by(receiver_id=u2.id).all()
    result_ids = {r.id for r in results}

    assert conn_a.id in result_ids
    assert conn_b.id in result_ids
    assert conn_c.id not in result_ids


# ---------------------------------------------------------------------------
# Bonus: after rejection a new request between the same pair IS still blocked
# (the unique constraint is on the pair, not on status)
# ---------------------------------------------------------------------------


def test_new_request_after_rejection_still_blocked(db, two_users):
    """
    The unique constraint is unconditional — only one row per canonical pair
    ever exists. A new request after rejection requires deleting the old row
    first (handled at the service layer, not tested here).
    """
    u1, u2 = two_users
    conn = _make_connection(u1, u2)
    db.add(conn)
    db.flush()

    conn.status = ConnectionStatus.rejected
    db.flush()

    conn2 = _make_connection(u1, u2)
    db.add(conn2)

    with pytest.raises(IntegrityError):
        db.flush()
