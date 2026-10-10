"""Persistent platform notifications.

Revision ID: 012_notifications
Revises: 011_community_media_and_tags
Create Date: 2026-10-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "012_notifications"
down_revision: Union[str, None] = "011_community_media_and_tags"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _index_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table_name not in set(inspector.get_table_names()):
        return set()
    return {ix["name"] for ix in inspector.get_indexes(table_name)}


def upgrade() -> None:
    tables = _existing_tables()
    notification_type = sa.Enum(
        "CONNECTION_REQUEST",
        "CONNECTION_ACCEPTED",
        "CONNECTION_REJECTED",
        "NEW_MESSAGE",
        name="notificationtype",
        create_constraint=True,
    )

    if "notifications" not in tables:
        notification_type.create(op.get_bind(), checkfirst=True)
        op.create_table(
            "notifications",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("recipient_id", sa.String(36), nullable=False),
            sa.Column("actor_id", sa.String(36), nullable=True),
            sa.Column("type", notification_type, nullable=False),
            sa.Column("message", sa.String(500), nullable=False),
            sa.Column("reference_type", sa.String(50), nullable=True),
            sa.Column("reference_id", sa.String(36), nullable=True),
            sa.Column("action_url", sa.String(255), nullable=True),
            sa.Column("is_read", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["recipient_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    existing_indexes = _index_names("notifications")
    for name, columns in (
        ("ix_notifications_id", ["id"]),
        ("ix_notifications_recipient_id", ["recipient_id"]),
        ("ix_notifications_actor_id", ["actor_id"]),
        ("ix_notifications_type", ["type"]),
        ("ix_notifications_is_read", ["is_read"]),
        ("ix_notifications_created_at", ["created_at"]),
        ("ix_notifications_recipient_read_created", ["recipient_id", "is_read", "created_at"]),
        ("ix_notifications_reference", ["reference_type", "reference_id"]),
    ):
        if name not in existing_indexes:
            op.create_index(name, "notifications", columns, unique=False)


def downgrade() -> None:
    for name in (
        "ix_notifications_reference",
        "ix_notifications_recipient_read_created",
        "ix_notifications_created_at",
        "ix_notifications_is_read",
        "ix_notifications_type",
        "ix_notifications_actor_id",
        "ix_notifications_recipient_id",
        "ix_notifications_id",
    ):
        op.drop_index(name, table_name="notifications")
    op.drop_table("notifications")
    sa.Enum(name="notificationtype").drop(op.get_bind(), checkfirst=True)
