"""Add persisted pin and favorite preferences to AI conversations.

Revision ID: 015_ai_conversation_preferences
Revises: 014_resource_share_messages
Create Date: 2026-10-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "015_ai_conversation_preferences"
down_revision: Union[str, None] = "014_resource_share_messages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if "conversations" not in set(inspector.get_table_names()):
        return set()
    return {column["name"] for column in inspector.get_columns("conversations")}


def upgrade() -> None:
    columns = _columns()
    if "is_pinned" not in columns:
        op.add_column(
            "conversations",
            sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
    if "is_favorite" not in columns:
        op.add_column(
            "conversations",
            sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
    inspector = sa.inspect(op.get_bind())
    indexes = {index["name"] for index in inspector.get_indexes("conversations")}
    if "ix_conversations_is_pinned" not in indexes:
        op.create_index("ix_conversations_is_pinned", "conversations", ["is_pinned"], unique=False)
    if "ix_conversations_is_favorite" not in indexes:
        op.create_index("ix_conversations_is_favorite", "conversations", ["is_favorite"], unique=False)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    indexes = {index["name"] for index in inspector.get_indexes("conversations")}
    if "ix_conversations_is_favorite" in indexes:
        op.drop_index("ix_conversations_is_favorite", table_name="conversations")
    if "ix_conversations_is_pinned" in indexes:
        op.drop_index("ix_conversations_is_pinned", table_name="conversations")
    columns = _columns()
    if "is_favorite" in columns:
        op.drop_column("conversations", "is_favorite")
    if "is_pinned" in columns:
        op.drop_column("conversations", "is_pinned")
