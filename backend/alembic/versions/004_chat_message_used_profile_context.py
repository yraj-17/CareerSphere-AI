"""Add used_profile_context column to chat_messages.

Revision ID: 004_chat_message_profile_flag
Revises: 003_profiles
Create Date: 2026-09-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004_chat_message_profile_flag"
down_revision: Union[str, None] = "003_profiles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column(
            "used_profile_context",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "used_profile_context")
