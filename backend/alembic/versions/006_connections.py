"""Professional networking: connections table.

Revision ID: 006_connections
Revises: 005_opportunities
Create Date: 2026-09-19

Design notes
------------
* ``canonical_a`` / ``canonical_b`` hold the lexicographically ordered pair of
  user IDs (min, max).  The UNIQUE constraint on these two columns ensures that
  only one row can ever exist for any pair of users, regardless of which user
  sent the request.
* The ``connectionstatus`` PostgreSQL enum type is created via a PL/pgSQL DO
  block so the statement is fully idempotent (safe on fresh DBs and re-runs).
* ``postgresql.ENUM(..., create_type=False)`` is used for the column so that
  SQLAlchemy's automatic CREATE TYPE DDL listener is suppressed — the type is
  already guaranteed to exist by the DO block above it.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "006_connections"
down_revision: Union[str, None] = "005_opportunities"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_STATUS_VALUES = ("pending", "accepted", "rejected", "cancelled")
_ENUM_NAME = "connectionstatus"

# Quoted values list for use in SQL literals, e.g. 'pending', 'accepted', ...
_ENUM_LITERALS = ", ".join(f"'{v}'" for v in _STATUS_VALUES)


def upgrade() -> None:
    # ── 1. Create enum type idempotently via PL/pgSQL ────────────────────
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_type WHERE typname = '{_ENUM_NAME}'
            ) THEN
                CREATE TYPE {_ENUM_NAME} AS ENUM ({_ENUM_LITERALS});
            END IF;
        END
        $$;
        """
    )

    # ── 2. Create connections table ──────────────────────────────────────
    # create_type=False on the ENUM column: the type already exists from step 1;
    # this suppresses SQLAlchemy's own CREATE TYPE DDL event listener so it
    # doesn't try to create it again (which would raise DuplicateObject).
    op.create_table(
        "connections",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("requester_id", sa.String(length=36), nullable=False),
        sa.Column("receiver_id", sa.String(length=36), nullable=False),
        # Canonical ordering — always (min(requester,receiver), max(requester,receiver))
        sa.Column("canonical_a", sa.String(length=36), nullable=False),
        sa.Column("canonical_b", sa.String(length=36), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(*_STATUS_VALUES, name=_ENUM_NAME, create_type=False),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["requester_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["receiver_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        # Bidirectional uniqueness: only one row per user pair
        sa.UniqueConstraint("canonical_a", "canonical_b", name="uq_connection_pair"),
    )

    # ── 3. Indexes ────────────────────────────────────────────────────────
    op.create_index(op.f("ix_connections_id"), "connections", ["id"], unique=False)
    op.create_index(
        op.f("ix_connections_requester_id"), "connections", ["requester_id"], unique=False
    )
    op.create_index(
        op.f("ix_connections_receiver_id"), "connections", ["receiver_id"], unique=False
    )
    op.create_index(
        op.f("ix_connections_status"), "connections", ["status"], unique=False
    )
    # Composite indexes for bidirectional lookup
    op.create_index(
        "ix_connections_requester_receiver",
        "connections",
        ["requester_id", "receiver_id"],
        unique=False,
    )
    op.create_index(
        "ix_connections_receiver_requester",
        "connections",
        ["receiver_id", "requester_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_connections_receiver_requester", table_name="connections")
    op.drop_index("ix_connections_requester_receiver", table_name="connections")
    op.drop_index(op.f("ix_connections_status"), table_name="connections")
    op.drop_index(op.f("ix_connections_receiver_id"), table_name="connections")
    op.drop_index(op.f("ix_connections_requester_id"), table_name="connections")
    op.drop_index(op.f("ix_connections_id"), table_name="connections")
    op.drop_table("connections")
    op.execute(f"DROP TYPE IF EXISTS {_ENUM_NAME}")
