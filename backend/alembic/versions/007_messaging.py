"""Phase 5.8.1 — Direct messaging database foundation.

Revision ID: 007_messaging
Revises: 006_connections
Create Date: 2026-09-22

Tables created
──────────────
direct_conversations
    Represents a one-to-one messaging thread between exactly two users.
    canonical_a / canonical_b (min/max of the two participant IDs) carry a
    UNIQUE constraint so that only one thread can exist per user pair.

direct_conversation_participants
    Associates users with their conversations.
    Composite PK on (conversation_id, user_id) prevents duplicate membership.

direct_messages
    Individual messages within a thread.
    delivered_at / read_at are nullable timestamps (NULL = not yet occurred).
    No typing or online-presence state is persisted here; those are handled
    by the WebSocket / Redis layer introduced in Phase 5.8.2+.

Design notes
────────────
*  No new PostgreSQL enum type is needed — delivery tracking uses nullable
   timestamps, not a status enum.
*  All FKs use ondelete="CASCADE" consistent with the rest of the project.
*  Index names follow the op.f() convention used throughout this project.
*  Composite indexes are created explicitly for the most common queries:
     - messages in a conversation ordered by created_at
     - unread messages (conversation_id, read_at IS NULL)
     - messages by sender
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007_messaging"
down_revision: Union[str, None] = "006_connections"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. direct_conversations ───────────────────────────────────────────
    op.create_table(
        "direct_conversations",
        sa.Column("id", sa.String(length=36), nullable=False),
        # Canonical pair columns (lexicographic ordering of participant IDs).
        sa.Column("canonical_a", sa.String(length=36), nullable=False),
        sa.Column("canonical_b", sa.String(length=36), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        # One thread per user pair regardless of who initiated it.
        sa.UniqueConstraint("canonical_a", "canonical_b", name="uq_direct_conversation_pair"),
    )
    op.create_index(
        op.f("ix_direct_conversations_id"),
        "direct_conversations",
        ["id"],
        unique=False,
    )

    # ── 2. direct_conversation_participants ───────────────────────────────
    op.create_table(
        "direct_conversation_participants",
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["direct_conversations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        # Composite PK enforces (conversation, user) uniqueness.
        sa.PrimaryKeyConstraint("conversation_id", "user_id"),
    )
    op.create_index(
        "ix_direct_conv_participants_conversation_id",
        "direct_conversation_participants",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        "ix_direct_conv_participants_user_id",
        "direct_conversation_participants",
        ["user_id"],
        unique=False,
    )

    # ── 3. direct_messages ────────────────────────────────────────────────
    op.create_table(
        "direct_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("sender_id", sa.String(length=36), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # Nullable tracking timestamps — NULL means event has not occurred.
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["direct_conversations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sender_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_direct_messages_id"),
        "direct_messages",
        ["id"],
        unique=False,
    )
    # Ordered message fetch for a conversation.
    op.create_index(
        "ix_direct_messages_conversation_created",
        "direct_messages",
        ["conversation_id", "created_at"],
        unique=False,
    )
    # Messages by sender.
    op.create_index(
        "ix_direct_messages_sender_id",
        "direct_messages",
        ["sender_id"],
        unique=False,
    )
    # Unread-message queries (conversation_id, read_at IS NULL).
    op.create_index(
        "ix_direct_messages_conversation_read_at",
        "direct_messages",
        ["conversation_id", "read_at"],
        unique=False,
    )


def downgrade() -> None:
    # Drop in reverse dependency order.
    op.drop_index("ix_direct_messages_conversation_read_at", table_name="direct_messages")
    op.drop_index("ix_direct_messages_sender_id", table_name="direct_messages")
    op.drop_index("ix_direct_messages_conversation_created", table_name="direct_messages")
    op.drop_index(op.f("ix_direct_messages_id"), table_name="direct_messages")
    op.drop_table("direct_messages")

    op.drop_index("ix_direct_conv_participants_user_id", table_name="direct_conversation_participants")
    op.drop_index("ix_direct_conv_participants_conversation_id", table_name="direct_conversation_participants")
    op.drop_table("direct_conversation_participants")

    op.drop_index(op.f("ix_direct_conversations_id"), table_name="direct_conversations")
    op.drop_table("direct_conversations")
