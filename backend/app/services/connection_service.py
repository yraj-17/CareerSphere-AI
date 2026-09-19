"""
Networking v1 — Connection Service.

All business rules for professional connection lifecycle live here so that
future API endpoints remain thin and never duplicate logic.

Error contract
--------------
Every function raises ``fastapi.HTTPException`` for rule violations so callers
(API layer or tests) get consistent, typed errors:

  400 Bad Request  — self-connection attempt
  403 Forbidden    — action attempted by the wrong user
  409 Conflict     — duplicate connection pair already exists
  422 Unprocessable Entity — invalid status transition

The DB session is *not* committed by the service on read-only operations.
Write operations call ``db.commit()`` and ``db.refresh()`` so the returned
object is always fully populated, matching the convention used throughout the
project.
"""
from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.db.models import Connection, ConnectionStatus, User


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_connection(requester: User, receiver: User) -> Connection:
    """Construct a Connection with canonical ordering applied."""
    ca, cb = Connection.canonical_pair(requester.id, receiver.id)
    return Connection(
        requester_id=requester.id,
        receiver_id=receiver.id,
        canonical_a=ca,
        canonical_b=cb,
        status=ConnectionStatus.pending,
    )


def _require_pending(connection: Connection, action: str) -> None:
    """Raise 422 if the connection is not in pending status."""
    if connection.status != ConnectionStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Cannot {action} a connection that is not pending "
                   f"(current status: {connection.status.value}).",
        )


def _require_accepted(connection: Connection, action: str) -> None:
    """Raise 422 if the connection is not in accepted status."""
    if connection.status != ConnectionStatus.accepted:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Cannot {action} a connection that is not accepted "
                   f"(current status: {connection.status.value}).",
        )


# ---------------------------------------------------------------------------
# 1. send_connection_request
# ---------------------------------------------------------------------------


def send_connection_request(
    db: Session,
    requester: User,
    receiver: User,
) -> Connection:
    """
    Create a pending connection request from *requester* to *receiver*.

    Raises:
        400  — requester and receiver are the same user.
        409  — a connection (in any status) already exists for this pair.
    """
    if requester.id == receiver.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user cannot send a connection request to themselves.",
        )

    # Check for any existing relationship between this pair before hitting the
    # DB uniqueness constraint, so we can return a clear 409 message.
    existing = get_connection_between_users(db, requester.id, receiver.id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"A connection between these users already exists "
                f"(status: {existing.status.value})."
            ),
        )

    connection = _build_connection(requester, receiver)
    db.add(connection)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A connection between these users already exists.",
        )
    db.refresh(connection)
    return connection


# ---------------------------------------------------------------------------
# 2. accept_connection_request
# ---------------------------------------------------------------------------


def accept_connection_request(
    db: Session,
    connection: Connection,
    receiver: User,
) -> Connection:
    """
    Accept a pending connection request.

    Only the *receiver* of the original request may accept it.

    Raises:
        403  — caller is not the receiver of this request.
        422  — connection is not in pending status.
    """
    if connection.receiver_id != receiver.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the receiver of a connection request can accept it.",
        )
    _require_pending(connection, "accept")

    connection.status = ConnectionStatus.accepted
    db.commit()
    db.refresh(connection)
    return connection


# ---------------------------------------------------------------------------
# 3. reject_connection_request
# ---------------------------------------------------------------------------


def reject_connection_request(
    db: Session,
    connection: Connection,
    receiver: User,
) -> Connection:
    """
    Reject a pending connection request.

    Only the *receiver* of the original request may reject it.

    Raises:
        403  — caller is not the receiver of this request.
        422  — connection is not in pending status.
    """
    if connection.receiver_id != receiver.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the receiver of a connection request can reject it.",
        )
    _require_pending(connection, "reject")

    connection.status = ConnectionStatus.rejected
    db.commit()
    db.refresh(connection)
    return connection


# ---------------------------------------------------------------------------
# 4. cancel_connection_request
# ---------------------------------------------------------------------------


def cancel_connection_request(
    db: Session,
    connection: Connection,
    requester: User,
) -> Connection:
    """
    Cancel a pending connection request.

    Only the original *requester* may cancel their own request.

    Raises:
        403  — caller is not the requester of this request.
        422  — connection is not in pending status.
    """
    if connection.requester_id != requester.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the requester of a connection request can cancel it.",
        )
    _require_pending(connection, "cancel")

    connection.status = ConnectionStatus.cancelled
    db.commit()
    db.refresh(connection)
    return connection


# ---------------------------------------------------------------------------
# 5. remove_connection
# ---------------------------------------------------------------------------


def remove_connection(
    db: Session,
    connection: Connection,
    current_user: User,
) -> None:
    """
    Remove (permanently delete) an accepted connection.

    Either party of the accepted connection may remove it.

    Raises:
        403  — caller is neither the requester nor the receiver.
        422  — connection is not in accepted status.
    """
    is_party = (
        connection.requester_id == current_user.id
        or connection.receiver_id == current_user.id
    )
    if not is_party:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a participant of this connection.",
        )
    _require_accepted(connection, "remove")

    db.delete(connection)
    db.commit()


# ---------------------------------------------------------------------------
# 6. get_connection_between_users
# ---------------------------------------------------------------------------


def get_connection_between_users(
    db: Session,
    user_a_id: str,
    user_b_id: str,
) -> Connection | None:
    """
    Return the connection row for a user pair regardless of request direction.

    Uses the canonical_a / canonical_b columns so the lookup is always O(1)
    via the unique index, no OR-join needed.

    Returns ``None`` if no relationship exists.
    """
    ca, cb = Connection.canonical_pair(user_a_id, user_b_id)
    return (
        db.query(Connection)
        .filter(Connection.canonical_a == ca, Connection.canonical_b == cb)
        .first()
    )


# ---------------------------------------------------------------------------
# 7. get_pending_requests_for_user  (incoming)
# ---------------------------------------------------------------------------


def get_pending_requests_for_user(
    db: Session,
    user: User,
) -> list[Connection]:
    """
    Return all *incoming* pending connection requests for *user*
    (i.e. rows where receiver_id == user.id and status == pending).
    """
    return (
        db.query(Connection)
        .filter(
            Connection.receiver_id == user.id,
            Connection.status == ConnectionStatus.pending,
        )
        .order_by(Connection.created_at.desc())
        .all()
    )


# ---------------------------------------------------------------------------
# 8. get_sent_pending_requests  (outgoing)
# ---------------------------------------------------------------------------


def get_sent_pending_requests(
    db: Session,
    user: User,
) -> list[Connection]:
    """
    Return all *outgoing* pending connection requests sent by *user*
    (i.e. rows where requester_id == user.id and status == pending).
    """
    return (
        db.query(Connection)
        .filter(
            Connection.requester_id == user.id,
            Connection.status == ConnectionStatus.pending,
        )
        .order_by(Connection.created_at.desc())
        .all()
    )


# ---------------------------------------------------------------------------
# 9. get_accepted_connections
# ---------------------------------------------------------------------------


def get_accepted_connections(
    db: Session,
    user: User,
) -> list[Connection]:
    """
    Return all accepted connections where *user* is either party.
    """
    return (
        db.query(Connection)
        .filter(
            Connection.status == ConnectionStatus.accepted,
            (Connection.requester_id == user.id)
            | (Connection.receiver_id == user.id),
        )
        .order_by(Connection.created_at.desc())
        .all()
    )
