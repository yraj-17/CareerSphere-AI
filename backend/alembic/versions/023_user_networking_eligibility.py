"""Add explicit user eligibility metadata for networking.

Revision ID: 023_user_networking_eligibility
Revises: 022_code_review_follow_ups
Create Date: 2026-11-05

The migration does not infer or delete accounts from names, usernames, or
emails. Existing rows retain ordinary-member defaults and can be marked by an
operator when their ownership/purpose has been verified.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "023_user_networking_eligibility"
down_revision: Union[str, None] = "022_code_review_follow_ups"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    user_flags = (
        ("is_active", True),
        ("is_deleted", False),
        ("is_test_account", False),
        ("is_demo_account", False),
        ("is_system_account", False),
        ("is_discoverable", True),
    )
    for name, default in user_flags:
        op.add_column(
            "users",
            sa.Column(
                name,
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true" if default else "false"),
            ),
        )
        op.create_index(f"ix_users_{name}", "users", [name], unique=False)

    # The application bootstrap calls Base.metadata.create_all(), so a fresh
    # app process may already have created this new table before Alembic runs.
    # Reuse it and add only any missing indexes instead of failing on a
    # DuplicateTable error.
    if not inspector.has_table("user_blocks"):
        op.create_table(
            "user_blocks",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("blocker_id", sa.String(length=36), nullable=False),
            sa.Column("blocked_id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["blocker_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["blocked_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("blocker_id", "blocked_id", name="uq_user_block_pair"),
        )

    existing_indexes = {
        index["name"] for index in sa.inspect(bind).get_indexes("user_blocks")
    }
    for name, columns in (
        ("ix_user_blocks_id", ["id"]),
        ("ix_user_blocks_blocker_id", ["blocker_id"]),
        ("ix_user_blocks_blocked_id", ["blocked_id"]),
    ):
        if name not in existing_indexes:
            op.create_index(name, "user_blocks", columns, unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_blocks_blocked_id", table_name="user_blocks")
    op.drop_index("ix_user_blocks_blocker_id", table_name="user_blocks")
    op.drop_index("ix_user_blocks_id", table_name="user_blocks")
    op.drop_table("user_blocks")

    for name, _ in reversed(
        (
            ("is_active", True),
            ("is_deleted", False),
            ("is_test_account", False),
            ("is_demo_account", False),
            ("is_system_account", False),
            ("is_discoverable", True),
        )
    ):
        op.drop_index(f"ix_users_{name}", table_name="users")
        op.drop_column("users", name)
