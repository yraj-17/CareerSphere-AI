"""AI Interviewer role engine: role/blueprint fields, question kinds, custom-role cache.

Revision ID: 018_interview_role_engine
Revises: 017_ai_interviews
Create Date: 2026-11-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "018_interview_role_engine"
down_revision: Union[str, None] = "017_ai_interviews"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table: str) -> set[str]:
    return {col["name"] for col in sa.inspect(op.get_bind()).get_columns(table)}


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    session_cols = _columns("interview_sessions")
    for name, column in (
        ("role_slug", sa.Column("role_slug", sa.String(80), nullable=True)),
        ("role_source", sa.Column("role_source", sa.String(10), nullable=True)),
        ("job_description", sa.Column("job_description", sa.Text(), nullable=True)),
        ("blueprint", sa.Column("blueprint", sa.JSON(), nullable=True)),
    ):
        if name not in session_cols:
            op.add_column("interview_sessions", column)

    if "kind" not in _columns("interview_questions"):
        # Existing questions are conceptual questions; the server default backfills them.
        op.add_column(
            "interview_questions",
            sa.Column("kind", sa.String(20), nullable=False, server_default="question"),
        )

    if "interview_role_profiles" not in _tables():
        op.create_table(
            "interview_role_profiles",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("normalized_title", sa.String(160), nullable=False),
            sa.Column("title", sa.String(120), nullable=False),
            sa.Column("analysis", sa.JSON(), nullable=False),
            sa.Column("model_name", sa.String(120), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_interview_role_profiles_id", "interview_role_profiles", ["id"], unique=False)
        op.create_index("ix_interview_role_profiles_normalized_title", "interview_role_profiles", ["normalized_title"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_interview_role_profiles_normalized_title", table_name="interview_role_profiles")
    op.drop_index("ix_interview_role_profiles_id", table_name="interview_role_profiles")
    op.drop_table("interview_role_profiles")
    op.drop_column("interview_questions", "kind")
    for name in ("blueprint", "job_description", "role_source", "role_slug"):
        op.drop_column("interview_sessions", name)
