"""Phase 5.8 — Message Management Features.

Revision ID: 008_message_management
Revises: 007_messaging
Create Date: 2026-09-25

Schema changes
──────────────

1. direct_messages — new nullable columns:
   - reply_to_message_id  (FK → direct_messages.id SET NULL)
     Allows a message to reference the message it replies to.
     Must belong to the same conversation (enforced by the service layer).
   - deleted_for_everyone_at  (DATETIME nullable)
     Marks a message as deleted for all participants when non-NULL.
     Content is hidden from all API responses when this is set.
   - pinned_at  (DATETIME nullable)
     Records when the message was pinned in the conversation.
   - pinned_by_user_id  (FK → users.id SET NULL)
     Records which participant pinned the message.
   - forwarded_from_message_id  (FK → direct_messages.id SET NULL)
     Records the original source message when a message is forwarded.
     A forwarded message is a NEW row in the destination conversation;
     this FK is just metadata linking back to the original.

2. message_stars — new table (per-user star/save):
   - message_id   (FK → direct_messages.id CASCADE)
   - user_id      (FK → users.id CASCADE)
   - created_at
   - UNIQUE (message_id, user_id)

3. message_user_deletions — new table (per-user "delete for me"):
   - message_id   (FK → direct_messages.id CASCADE)
   - user_id      (FK → users.id CASCADE)
   - deleted_at
   - UNIQUE (message_id, user_id)

Design notes
────────────
- Physical deletion never happens; soft-delete columns / side tables are used.
- No PostgreSQL ENUM types added (nullable timestamps for state tracking).
- All FKs use ondelete consistent with the rest of the project.
- Indexes cover the most common access patterns without over-indexing.
- Pin state is stored directly on the message row for simplicity (one pinned
  message per context is the primary product requirement).
- The service layer enforces cross-conversation reference prevention, sender
  authorization for delete-for-everyone, and participant-only access for all ops.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "008_message_management"
down_revision: Union[str, None] = "007_messaging"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Extend direct_messages with management columns ─────────────────
    # Use connection to check existing columns, then add only missing ones.

    bind = op.get_bind()

    import sqlalchemy as _sa
    inspector = _sa.inspect(bind)
    existing_dm_cols = {c["name"] for c in inspector.get_columns("direct_messages")}

    if "reply_to_message_id" not in existing_dm_cols:
        op.add_column(
            "direct_messages",
            sa.Column(
                "reply_to_message_id",
                sa.String(length=36),
                sa.ForeignKey("direct_messages.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
        op.create_index(
            "ix_direct_messages_reply_to",
            "direct_messages",
            ["reply_to_message_id"],
            unique=False,
        )

    if "deleted_for_everyone_at" not in existing_dm_cols:
        op.add_column(
            "direct_messages",
            sa.Column("deleted_for_everyone_at", sa.DateTime(timezone=True), nullable=True),
        )

    if "pinned_at" not in existing_dm_cols:
        op.add_column(
            "direct_messages",
            sa.Column("pinned_at", sa.DateTime(timezone=True), nullable=True),
        )

    if "pinned_by_user_id" not in existing_dm_cols:
        op.add_column(
            "direct_messages",
            sa.Column(
                "pinned_by_user_id",
                sa.String(length=36),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )

    if "forwarded_from_message_id" not in existing_dm_cols:
        op.add_column(
            "direct_messages",
            sa.Column(
                "forwarded_from_message_id",
                sa.String(length=36),
                sa.ForeignKey("direct_messages.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )

    # Composite index for pinned message lookup (safe to recreate, ignore if exists)
    existing_indexes = {ix["name"] for ix in inspector.get_indexes("direct_messages")}
    if "ix_direct_messages_conversation_pinned_at" not in existing_indexes:
        op.create_index(
            "ix_direct_messages_conversation_pinned_at",
            "direct_messages",
            ["conversation_id", "pinned_at"],
            unique=False,
        )

    # ── 2. message_stars ──────────────────────────────────────────────────
    existing_tables = set(inspector.get_table_names())

    if "message_stars" not in existing_tables:
        op.create_table(
            "message_stars",
            sa.Column("message_id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["message_id"],
                ["direct_messages.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("message_id", "user_id"),
            sa.UniqueConstraint("message_id", "user_id", name="uq_message_star_user"),
        )

    # Add indexes only if they don't exist
    existing_star_indexes = {ix["name"] for ix in inspector.get_indexes("message_stars")} if "message_stars" in existing_tables else set()
    if "ix_message_stars_user_id" not in existing_star_indexes:
        op.create_index(
            "ix_message_stars_user_id",
            "message_stars",
            ["user_id"],
            unique=False,
        )
    if "ix_message_stars_message_id" not in existing_star_indexes:
        op.create_index(
            "ix_message_stars_message_id",
            "message_stars",
            ["message_id"],
            unique=False,
        )

    # ── 3. message_user_deletions ─────────────────────────────────────────
    if "message_user_deletions" not in existing_tables:
        op.create_table(
            "message_user_deletions",
            sa.Column("message_id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column(
                "deleted_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["message_id"],
                ["direct_messages.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("message_id", "user_id"),
            sa.UniqueConstraint("message_id", "user_id", name="uq_message_user_deletion"),
        )

    existing_del_indexes = {ix["name"] for ix in inspector.get_indexes("message_user_deletions")} if "message_user_deletions" in existing_tables else set()
    if "ix_message_user_deletions_user_id" not in existing_del_indexes:
        op.create_index(
            "ix_message_user_deletions_user_id",
            "message_user_deletions",
            ["user_id"],
            unique=False,
        )
    if "ix_message_user_deletions_message_id" not in existing_del_indexes:
        op.create_index(
            "ix_message_user_deletions_message_id",
            "message_user_deletions",
            ["message_id"],
            unique=False,
        )



def downgrade() -> None:
    # Drop new tables first (no dependents)
    op.drop_index("ix_message_user_deletions_message_id", table_name="message_user_deletions")
    op.drop_index("ix_message_user_deletions_user_id", table_name="message_user_deletions")
    op.drop_table("message_user_deletions")

    op.drop_index("ix_message_stars_message_id", table_name="message_stars")
    op.drop_index("ix_message_stars_user_id", table_name="message_stars")
    op.drop_table("message_stars")

    # Drop indexes before dropping columns
    op.drop_index("ix_direct_messages_conversation_pinned_at", table_name="direct_messages")
    op.drop_index("ix_direct_messages_reply_to", table_name="direct_messages")

    # Drop columns from direct_messages
    op.drop_column("direct_messages", "forwarded_from_message_id")
    op.drop_column("direct_messages", "pinned_by_user_id")
    op.drop_column("direct_messages", "pinned_at")
    op.drop_column("direct_messages", "deleted_for_everyone_at")
    op.drop_column("direct_messages", "reply_to_message_id")
