"""Problem bank metadata and per-question practical assessment specs.

* coding_problems.category      dsa | frontend | backend | sql | bash
* coding_problems.harness       runtime harness config (see coding_harness), nullable
* coding_problems.content_hash  hash of the seeded bank entry, so re-seeding is idempotent
                                and any content change forces re-verification
* interview_questions.practical backend-only spec of the assigned practical assessment
                                (problem / scenario / calculation parameters)

Revision ID: 021_practical_assessments
Revises: 020_coding_assessment
Create Date: 2026-11-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "021_practical_assessments"
down_revision: Union[str, None] = "020_coding_assessment"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table: str) -> set[str]:
    return {col["name"] for col in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    problem_columns = _columns("coding_problems")
    if "category" not in problem_columns:
        op.add_column("coding_problems", sa.Column("category", sa.String(20), nullable=False, server_default="dsa"))
        op.create_index("ix_coding_problems_category", "coding_problems", ["category"], unique=False)
    if "harness" not in problem_columns:
        op.add_column("coding_problems", sa.Column("harness", sa.JSON(), nullable=True))
    if "content_hash" not in problem_columns:
        op.add_column("coding_problems", sa.Column("content_hash", sa.String(64), nullable=True))
    if "practical" not in _columns("interview_questions"):
        op.add_column("interview_questions", sa.Column("practical", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("interview_questions", "practical")
    op.drop_column("coding_problems", "content_hash")
    op.drop_column("coding_problems", "harness")
    op.drop_index("ix_coding_problems_category", table_name="coding_problems")
    op.drop_column("coding_problems", "category")
