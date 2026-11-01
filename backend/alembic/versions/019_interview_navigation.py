"""AI Interviewer navigation: current position and server-side answer drafts.

Revision ID: 019_interview_navigation
Revises: 018_interview_role_engine
Create Date: 2026-11-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "019_interview_navigation"
down_revision: Union[str, None] = "018_interview_role_engine"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table: str) -> set[str]:
    return {col["name"] for col in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    session_cols = _columns("interview_sessions")
    if "current_position" not in session_cols:
        op.add_column("interview_sessions", sa.Column("current_position", sa.Integer(), nullable=True))
    if "position_seq" not in session_cols:
        op.add_column("interview_sessions", sa.Column("position_seq", sa.BigInteger(), nullable=True))

    question_cols = _columns("interview_questions")
    for name, column in (
        ("draft_text", sa.Column("draft_text", sa.Text(), nullable=True)),
        ("draft_meta", sa.Column("draft_meta", sa.JSON(), nullable=True)),
        ("draft_revision", sa.Column("draft_revision", sa.BigInteger(), nullable=False, server_default="0")),
        ("draft_updated_at", sa.Column("draft_updated_at", sa.DateTime(timezone=True), nullable=True)),
        ("first_viewed_at", sa.Column("first_viewed_at", sa.DateTime(timezone=True), nullable=True)),
    ):
        if name not in question_cols:
            op.add_column("interview_questions", column)


def downgrade() -> None:
    for name in ("first_viewed_at", "draft_updated_at", "draft_revision", "draft_meta", "draft_text"):
        op.drop_column("interview_questions", name)
    op.drop_column("interview_sessions", "position_seq")
    op.drop_column("interview_sessions", "current_position")
