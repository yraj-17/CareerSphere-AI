"""AI Interviewer V1: sessions, questions, answers, and final reports.

Revision ID: 017_ai_interviews
Revises: 016_global_posts
Create Date: 2026-10-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "017_ai_interviews"
down_revision: Union[str, None] = "016_global_posts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ENUMS = {
    "interviewtype": ("TECHNICAL", "BEHAVIORAL", "MIXED"),
    "interviewmode": ("TEXT", "VOICE"),
    "interviewdifficulty": ("BEGINNER", "INTERMEDIATE", "ADVANCED"),
    "interviewstatus": ("IN_PROGRESS", "COMPLETED", "ABANDONED", "EXPIRED"),
    "interviewaistatus": ("PENDING", "COMPLETED", "FAILED"),
}


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _enum(name: str) -> postgresql.ENUM:
    # create_type=False: types are created once, explicitly, below and then shared by columns.
    return postgresql.ENUM(*ENUMS[name], name=name, create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    for name, labels in ENUMS.items():
        postgresql.ENUM(*labels, name=name).create(bind, checkfirst=True)

    tables = _tables()

    if "interview_sessions" not in tables:
        op.create_table(
            "interview_sessions",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column("target_role", sa.String(120), nullable=False),
            sa.Column("interview_type", _enum("interviewtype"), nullable=False),
            sa.Column("interaction_mode", _enum("interviewmode"), nullable=False),
            sa.Column("difficulty", _enum("interviewdifficulty"), nullable=False),
            sa.Column("duration_minutes", sa.Integer(), nullable=False),
            sa.Column("max_questions", sa.Integer(), nullable=False),
            sa.Column("focus_areas", sa.JSON(), nullable=False),
            sa.Column("instructions", sa.Text(), nullable=True),
            sa.Column("status", _enum("interviewstatus"), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("final_score", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_interview_sessions_id", "interview_sessions", ["id"], unique=False)
        op.create_index("ix_interview_sessions_user_id", "interview_sessions", ["user_id"], unique=False)
        op.create_index("ix_interview_sessions_user_created", "interview_sessions", ["user_id", "created_at"], unique=False)
        op.create_index("ix_interview_sessions_user_status", "interview_sessions", ["user_id", "status"], unique=False)

    if "interview_questions" not in tables:
        op.create_table(
            "interview_questions",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("session_id", sa.String(36), nullable=False),
            sa.Column("question_order", sa.Integer(), nullable=False),
            sa.Column("question_text", sa.Text(), nullable=False),
            sa.Column("category", sa.String(20), nullable=False),
            sa.Column("competency", sa.String(120), nullable=False),
            sa.Column("difficulty", _enum("interviewdifficulty"), nullable=False),
            sa.Column("interviewer_context", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("session_id", "question_order", name="uq_interview_question_order"),
        )
        op.create_index("ix_interview_questions_id", "interview_questions", ["id"], unique=False)
        op.create_index("ix_interview_questions_session_id", "interview_questions", ["session_id"], unique=False)

    if "interview_answers" not in tables:
        op.create_table(
            "interview_answers",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("session_id", sa.String(36), nullable=False),
            sa.Column("question_id", sa.String(36), nullable=False),
            sa.Column("answer_text", sa.Text(), nullable=False),
            sa.Column("answer_source", _enum("interviewmode"), nullable=False),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("evaluation_status", _enum("interviewaistatus"), nullable=False),
            sa.Column("evaluation_attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("score", sa.Integer(), nullable=True),
            sa.Column("evaluation", sa.JSON(), nullable=True),
            sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["question_id"], ["interview_questions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("question_id", name="uq_interview_answer_question"),
        )
        op.create_index("ix_interview_answers_id", "interview_answers", ["id"], unique=False)
        op.create_index("ix_interview_answers_session_id", "interview_answers", ["session_id"], unique=False)
        op.create_index("ix_interview_answers_session_submitted", "interview_answers", ["session_id", "submitted_at"], unique=False)

    if "interview_reports" not in tables:
        op.create_table(
            "interview_reports",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("session_id", sa.String(36), nullable=False),
            sa.Column("status", _enum("interviewaistatus"), nullable=False),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("overall_score", sa.Integer(), nullable=True),
            sa.Column("aggregates", sa.JSON(), nullable=True),
            sa.Column("narrative", sa.JSON(), nullable=True),
            sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("session_id", name="uq_interview_report_session"),
        )
        op.create_index("ix_interview_reports_id", "interview_reports", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_interview_reports_id", table_name="interview_reports")
    op.drop_table("interview_reports")
    for name in ("ix_interview_answers_session_submitted", "ix_interview_answers_session_id", "ix_interview_answers_id"):
        op.drop_index(name, table_name="interview_answers")
    op.drop_table("interview_answers")
    for name in ("ix_interview_questions_session_id", "ix_interview_questions_id"):
        op.drop_index(name, table_name="interview_questions")
    op.drop_table("interview_questions")
    for name in (
        "ix_interview_sessions_user_status",
        "ix_interview_sessions_user_created",
        "ix_interview_sessions_user_id",
        "ix_interview_sessions_id",
    ):
        op.drop_index(name, table_name="interview_sessions")
    op.drop_table("interview_sessions")
    bind = op.get_bind()
    for name in reversed(list(ENUMS)):
        postgresql.ENUM(name=name).drop(bind, checkfirst=True)
