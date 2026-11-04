"""Coding assessment: problems, test cases, submissions, and the question→problem link.

Builds on 018 (interview_questions.kind = "coding"); 018 had no coding tables.

Revision ID: 020_coding_assessment
Revises: 019_interview_navigation
Create Date: 2026-11-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "020_coding_assessment"
down_revision: Union[str, None] = "019_interview_navigation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    return {col["name"] for col in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    tables = _tables()
    now = sa.text("now()")

    if "coding_problems" not in tables:
        op.create_table(
            "coding_problems",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("slug", sa.String(120), nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("difficulty", sa.String(10), nullable=False),
            sa.Column("statement", sa.Text(), nullable=False),
            sa.Column("input_format", sa.Text(), nullable=False),
            sa.Column("output_format", sa.Text(), nullable=False),
            sa.Column("constraints", sa.Text(), nullable=False),
            sa.Column("examples", sa.JSON(), nullable=False),
            sa.Column("instructions", sa.Text(), nullable=True),
            sa.Column("starter_code", sa.JSON(), nullable=False),
            sa.Column("languages", sa.JSON(), nullable=False),
            sa.Column("checker", sa.JSON(), nullable=False),
            sa.Column("time_limit_seconds", sa.Float(), nullable=False),
            sa.Column("memory_limit_kb", sa.Integer(), nullable=False),
            sa.Column("roles", sa.JSON(), nullable=False),
            sa.Column("competencies", sa.JSON(), nullable=False),
            sa.Column("estimated_minutes", sa.Integer(), nullable=False),
            sa.Column("reference_solutions", sa.JSON(), nullable=False),
            sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("verification", sa.JSON(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_coding_problems_id", "coding_problems", ["id"], unique=False)
        op.create_index("ix_coding_problems_slug", "coding_problems", ["slug"], unique=True)

    if "coding_test_cases" not in tables:
        op.create_table(
            "coding_test_cases",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("problem_id", sa.String(36), nullable=False),
            sa.Column("ordinal", sa.Integer(), nullable=False),
            sa.Column("input", sa.Text(), nullable=False),
            sa.Column("expected_output", sa.Text(), nullable=False),
            sa.Column("is_hidden", sa.Boolean(), nullable=False),
            sa.Column("weight", sa.Float(), nullable=False),
            sa.Column("is_required", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
            sa.ForeignKeyConstraint(["problem_id"], ["coding_problems.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("problem_id", "ordinal", name="uq_coding_test_case_ordinal"),
        )
        op.create_index("ix_coding_test_cases_id", "coding_test_cases", ["id"], unique=False)
        op.create_index("ix_coding_test_cases_problem_id", "coding_test_cases", ["problem_id"], unique=False)

    if "problem_id" not in _columns("interview_questions"):
        op.add_column("interview_questions", sa.Column("problem_id", sa.String(36), nullable=True))
        op.create_foreign_key(
            "fk_interview_questions_problem_id", "interview_questions", "coding_problems", ["problem_id"], ["id"], ondelete="SET NULL"
        )
        op.create_index("ix_interview_questions_problem_id", "interview_questions", ["problem_id"], unique=False)

    if "coding_submissions" not in tables:
        op.create_table(
            "coding_submissions",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column("session_id", sa.String(36), nullable=False),
            sa.Column("question_id", sa.String(36), nullable=False),
            sa.Column("problem_id", sa.String(36), nullable=False),
            sa.Column("submission_type", sa.String(10), nullable=False),
            sa.Column("language", sa.String(20), nullable=False),
            sa.Column("language_label", sa.String(80), nullable=False),
            sa.Column("source_code", sa.Text(), nullable=False),
            sa.Column("custom_input", sa.Text(), nullable=True),
            sa.Column("idempotency_key", sa.String(64), nullable=False),
            sa.Column("status", sa.String(12), nullable=False),
            sa.Column("verdict", sa.String(30), nullable=True),
            sa.Column("judge_tokens", sa.JSON(), nullable=True),
            sa.Column("results", sa.JSON(), nullable=True),
            sa.Column("tests_passed", sa.Integer(), nullable=True),
            sa.Column("tests_total", sa.Integer(), nullable=True),
            sa.Column("correctness_score", sa.Float(), nullable=True),
            sa.Column("max_time_seconds", sa.Float(), nullable=True),
            sa.Column("max_memory_kb", sa.Integer(), nullable=True),
            sa.Column("compile_output", sa.Text(), nullable=True),
            sa.Column("error", sa.String(300), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["question_id"], ["interview_questions.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["problem_id"], ["coding_problems.id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "idempotency_key", name="uq_coding_submission_idempotency"),
        )
        op.create_index("ix_coding_submissions_id", "coding_submissions", ["id"], unique=False)
        op.create_index("ix_coding_submissions_user_id", "coding_submissions", ["user_id"], unique=False)
        op.create_index("ix_coding_submissions_session_id", "coding_submissions", ["session_id"], unique=False)
        op.create_index("ix_coding_submissions_problem_id", "coding_submissions", ["problem_id"], unique=False)
        op.create_index("ix_coding_submissions_question_created", "coding_submissions", ["question_id", "created_at"], unique=False)


def downgrade() -> None:
    for name in (
        "ix_coding_submissions_question_created",
        "ix_coding_submissions_problem_id",
        "ix_coding_submissions_session_id",
        "ix_coding_submissions_user_id",
        "ix_coding_submissions_id",
    ):
        op.drop_index(name, table_name="coding_submissions")
    op.drop_table("coding_submissions")
    op.drop_index("ix_interview_questions_problem_id", table_name="interview_questions")
    op.drop_constraint("fk_interview_questions_problem_id", "interview_questions", type_="foreignkey")
    op.drop_column("interview_questions", "problem_id")
    for name in ("ix_coding_test_cases_problem_id", "ix_coding_test_cases_id"):
        op.drop_index(name, table_name="coding_test_cases")
    op.drop_table("coding_test_cases")
    for name in ("ix_coding_problems_slug", "ix_coding_problems_id"):
        op.drop_index(name, table_name="coding_problems")
    op.drop_table("coding_problems")
