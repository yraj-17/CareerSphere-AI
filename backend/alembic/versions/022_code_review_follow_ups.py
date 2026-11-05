"""AI code review per coding submission, and follow-up questions linked to their parent.

coding_submissions (one AI review per SUBMIT, stored on the submission itself so a review
can never be attached to different code):
* ai_review_status      NULL (not applicable, e.g. RUN) | PENDING | RUNNING | COMPLETED | FAILED
* ai_review_attempts    claimed attempts (bounded; failed reviews can be retried)
* ai_review             validated review JSON (criteria, strengths, complexity, ...)
* ai_quality_score      backend-computed weighted quality score 0-100
* ai_review_model       model that produced the review
* ai_review_updated_at  claim timestamp (stale RUNNING claims can be re-claimed)
* ai_reviewed_at        completion time

interview_questions:
* parent_question_id    follow-up -> its parent question (unique: at most one per parent)
* follow_up_state       on a parent: NULL | PENDING | CREATED | SKIPPED | FAILED (atomic claim,
                        so a follow-up is generated at most once)

Revision ID: 022_code_review_follow_ups
Revises: 021_practical_assessments
Create Date: 2026-11-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "022_code_review_follow_ups"
down_revision: Union[str, None] = "021_practical_assessments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SUBMISSION_COLUMNS = [
    ("ai_review_status", lambda: sa.Column("ai_review_status", sa.String(12), nullable=True)),
    ("ai_review_attempts", lambda: sa.Column("ai_review_attempts", sa.Integer(), nullable=False, server_default="0")),
    ("ai_review", lambda: sa.Column("ai_review", sa.JSON(), nullable=True)),
    ("ai_quality_score", lambda: sa.Column("ai_quality_score", sa.Float(), nullable=True)),
    ("ai_review_model", lambda: sa.Column("ai_review_model", sa.String(80), nullable=True)),
    ("ai_review_updated_at", lambda: sa.Column("ai_review_updated_at", sa.DateTime(timezone=True), nullable=True)),
    ("ai_reviewed_at", lambda: sa.Column("ai_reviewed_at", sa.DateTime(timezone=True), nullable=True)),
]


def _columns(table: str) -> set[str]:
    return {col["name"] for col in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    existing = _columns("coding_submissions")
    for name, column in SUBMISSION_COLUMNS:
        if name not in existing:
            op.add_column("coding_submissions", column())
    question_columns = _columns("interview_questions")
    if "parent_question_id" not in question_columns:
        op.add_column(
            "interview_questions",
            sa.Column(
                "parent_question_id",
                sa.String(36),
                sa.ForeignKey("interview_questions.id", ondelete="CASCADE", name="fk_interview_questions_parent"),
                nullable=True,
            ),
        )
        op.create_index("ix_interview_questions_parent_unique", "interview_questions", ["parent_question_id"], unique=True)
    if "follow_up_state" not in question_columns:
        op.add_column("interview_questions", sa.Column("follow_up_state", sa.String(10), nullable=True))


def downgrade() -> None:
    question_columns = _columns("interview_questions")
    if "follow_up_state" in question_columns:
        op.drop_column("interview_questions", "follow_up_state")
    if "parent_question_id" in question_columns:
        op.drop_index("ix_interview_questions_parent_unique", table_name="interview_questions")
        op.drop_constraint("fk_interview_questions_parent", "interview_questions", type_="foreignkey")
        op.drop_column("interview_questions", "parent_question_id")
    existing = _columns("coding_submissions")
    for name, _ in reversed(SUBMISSION_COLUMNS):
        if name in existing:
            op.drop_column("coding_submissions", name)
