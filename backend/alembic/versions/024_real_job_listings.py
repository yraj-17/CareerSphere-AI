"""Real job listings: provider provenance, lifecycle tracking, sync runs, demo cleanup.

Revision ID: 024_real_job_listings
Revises: 023_user_networking_eligibility
Create Date: 2026-11-05

* Adds provenance / lifecycle columns to ``opportunities`` so every listing can
  be traced to its provider and marked inactive when withdrawn or stale.
* Adds ``job_sync_runs`` (per-source synchronisation log).
* Removes the fabricated Phase 3.2 demo listings. They are identified by two
  independent markers that real data can never carry: ``source = 'curated'``
  AND an application URL on the non-existent ``careersphere.local`` host.
  Rows left behind by the automated test suites (``source`` of ``test`` /
  ``phase-3-2-test``) are removed too. Nothing else is touched.

The migration is idempotent because ``Base.metadata.create_all`` at API start-up
may already have created the new table/columns.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "024_real_job_listings"
down_revision: Union[str, None] = "023_user_networking_eligibility"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_NEW_COLUMNS = [
    ("source_board", sa.String(length=120), True),
    ("source_attribution", sa.String(length=300), False),
    ("job_url", sa.String(length=1000), False),
    ("country", sa.String(length=80), True),
    ("work_mode", sa.String(length=20), True),
    ("employment_type", sa.String(length=40), True),
    ("experience_min_years", sa.Integer(), False),
    ("experience_max_years", sa.Integer(), False),
    ("salary_currency", sa.String(length=10), False),
    ("salary_period", sa.String(length=20), False),
    ("salary_text", sa.String(length=200), False),
    ("source_updated_at", sa.DateTime(timezone=True), False),
    ("first_seen_at", sa.DateTime(timezone=True), False),
    ("last_seen_at", sa.DateTime(timezone=True), True),
    ("inactive_reason", sa.String(length=40), False),
    ("content_hash", sa.String(length=64), False),
]

DEMO_CLEANUP_WHERE = (
    "(source = 'curated' AND application_url LIKE 'https://careersphere.local/opportunities/%') "
    "OR source IN ('test', 'phase-3-2-test')"
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {column["name"] for column in inspector.get_columns("opportunities")}
    existing_indexes = {index["name"] for index in inspector.get_indexes("opportunities")}

    for name, column_type, indexed in _NEW_COLUMNS:
        if name not in existing:
            op.add_column("opportunities", sa.Column(name, column_type, nullable=True))
        index_name = f"ix_opportunities_{name}"
        if indexed and index_name not in existing_indexes:
            op.create_index(index_name, "opportunities", [name], unique=False)

    if "is_active" not in existing:
        op.add_column(
            "opportunities",
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        )
    if "ix_opportunities_is_active" not in existing_indexes:
        op.create_index("ix_opportunities_is_active", "opportunities", ["is_active"], unique=False)

    if not inspector.has_table("job_sync_runs"):
        op.create_table(
            "job_sync_runs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("provider", sa.String(length=40), nullable=False),
            sa.Column("source_board", sa.String(length=120), nullable=True),
            sa.Column("trigger", sa.String(length=20), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("fetched_count", sa.Integer(), nullable=False),
            sa.Column("kept_count", sa.Integer(), nullable=False),
            sa.Column("inserted_count", sa.Integer(), nullable=False),
            sa.Column("updated_count", sa.Integer(), nullable=False),
            sa.Column("unchanged_count", sa.Integer(), nullable=False),
            sa.Column("deactivated_count", sa.Integer(), nullable=False),
            sa.Column("invalid_count", sa.Integer(), nullable=False),
            sa.Column("error_message", sa.String(length=500), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_job_sync_runs_provider", "job_sync_runs", ["provider"], unique=False)
        op.create_index("ix_job_sync_runs_started_at", "job_sync_runs", ["started_at"], unique=False)

    # Child skill rows cascade at the FK level (ON DELETE CASCADE).
    op.execute(sa.text(f"DELETE FROM opportunities WHERE {DEMO_CLEANUP_WHERE}"))


def downgrade() -> None:
    # Demo rows are not restored: they were fabricated data.
    op.drop_index("ix_job_sync_runs_started_at", table_name="job_sync_runs")
    op.drop_index("ix_job_sync_runs_provider", table_name="job_sync_runs")
    op.drop_table("job_sync_runs")
    op.drop_index("ix_opportunities_is_active", table_name="opportunities")
    op.drop_column("opportunities", "is_active")
    for name, _column_type, indexed in reversed(_NEW_COLUMNS):
        if indexed:
            op.drop_index(f"ix_opportunities_{name}", table_name="opportunities")
        op.drop_column("opportunities", name)
