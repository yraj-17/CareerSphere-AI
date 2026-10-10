"""Resource-share direct messages.

Revision ID: 014_resource_share_messages
Revises: 013_resources
Create Date: 2026-10-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "014_resource_share_messages"
down_revision: Union[str, None] = "013_resources"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table_name not in set(inspector.get_table_names()):
        return set()
    return {col["name"] for col in inspector.get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table_name not in set(inspector.get_table_names()):
        return set()
    return {ix["name"] for ix in inspector.get_indexes(table_name)}


def _foreign_key_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table_name not in set(inspector.get_table_names()):
        return set()
    return {fk["name"] for fk in inspector.get_foreign_keys(table_name)}


def upgrade() -> None:
    columns = _columns("direct_messages")
    if "message_type" not in columns:
        op.add_column(
            "direct_messages",
            sa.Column("message_type", sa.String(30), server_default="TEXT", nullable=False),
        )
    if "resource_id" not in columns:
        op.add_column("direct_messages", sa.Column("resource_id", sa.String(36), nullable=True))

    indexes = _index_names("direct_messages")
    if "ix_direct_messages_message_type" not in indexes:
        op.create_index("ix_direct_messages_message_type", "direct_messages", ["message_type"], unique=False)
    if "ix_direct_messages_resource_id" not in indexes:
        op.create_index("ix_direct_messages_resource_id", "direct_messages", ["resource_id"], unique=False)

    foreign_keys = _foreign_key_names("direct_messages")
    if "fk_direct_messages_resource_id_resources" not in foreign_keys:
        op.create_foreign_key(
            "fk_direct_messages_resource_id_resources",
            "direct_messages",
            "resources",
            ["resource_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    op.drop_constraint("fk_direct_messages_resource_id_resources", "direct_messages", type_="foreignkey")
    op.drop_index("ix_direct_messages_resource_id", table_name="direct_messages")
    op.drop_index("ix_direct_messages_message_type", table_name="direct_messages")
    op.drop_column("direct_messages", "resource_id")
    op.drop_column("direct_messages", "message_type")
