"""Career opportunity tables.

Revision ID: 005_opportunities
Revises: 004_chat_message_profile_flag
Create Date: 2026-09-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005_opportunities"
down_revision: Union[str, None] = "004_chat_message_profile_flag"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── opportunities ────────────────────────────────────────────────────
    op.create_table(
        "opportunities",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("company", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("opportunity_type", sa.String(length=50), nullable=False),
        sa.Column("target_role", sa.String(length=160), nullable=False),
        sa.Column("location", sa.String(length=160), nullable=True),
        sa.Column("is_remote", sa.Boolean(), nullable=False),
        sa.Column("experience_level", sa.String(length=80), nullable=True),
        sa.Column("industry", sa.String(length=160), nullable=True),
        sa.Column("salary_min", sa.BigInteger(), nullable=True),
        sa.Column("salary_max", sa.BigInteger(), nullable=True),
        sa.Column("application_url", sa.String(length=500), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_opportunities_id"), "opportunities", ["id"], unique=False)
    op.create_index(op.f("ix_opportunities_opportunity_type"), "opportunities", ["opportunity_type"], unique=False)
    op.create_index(op.f("ix_opportunities_target_role"), "opportunities", ["target_role"], unique=False)
    op.create_index(op.f("ix_opportunities_location"), "opportunities", ["location"], unique=False)
    op.create_index(op.f("ix_opportunities_is_remote"), "opportunities", ["is_remote"], unique=False)
    op.create_index(op.f("ix_opportunities_experience_level"), "opportunities", ["experience_level"], unique=False)
    op.create_index(op.f("ix_opportunities_source"), "opportunities", ["source"], unique=False)
    op.create_index(op.f("ix_opportunities_published_at"), "opportunities", ["published_at"], unique=False)
    op.create_index(op.f("ix_opportunities_expires_at"), "opportunities", ["expires_at"], unique=False)
    # Partial unique index: enforce (source, external_id) uniqueness only when external_id IS NOT NULL.
    # This allows multiple curated opportunities with NULL external_id.
    op.create_index(
        "uq_opportunity_source_external_id",
        "opportunities",
        ["source", "external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )

    # ── opportunity_required_skills ───────────────────────────────────────
    op.create_table(
        "opportunity_required_skills",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("opportunity_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("normalized_name", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("opportunity_id", "normalized_name", name="uq_opportunity_required_skill_name"),
    )
    op.create_index(op.f("ix_opportunity_required_skills_id"), "opportunity_required_skills", ["id"], unique=False)
    op.create_index(op.f("ix_opportunity_required_skills_opportunity_id"), "opportunity_required_skills", ["opportunity_id"], unique=False)

    # ── opportunity_preferred_skills ──────────────────────────────────────
    op.create_table(
        "opportunity_preferred_skills",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("opportunity_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("normalized_name", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("opportunity_id", "normalized_name", name="uq_opportunity_preferred_skill_name"),
    )
    op.create_index(op.f("ix_opportunity_preferred_skills_id"), "opportunity_preferred_skills", ["id"], unique=False)
    op.create_index(op.f("ix_opportunity_preferred_skills_opportunity_id"), "opportunity_preferred_skills", ["opportunity_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_opportunity_preferred_skills_opportunity_id"), table_name="opportunity_preferred_skills")
    op.drop_index(op.f("ix_opportunity_preferred_skills_id"), table_name="opportunity_preferred_skills")
    op.drop_table("opportunity_preferred_skills")
    op.drop_index(op.f("ix_opportunity_required_skills_opportunity_id"), table_name="opportunity_required_skills")
    op.drop_index(op.f("ix_opportunity_required_skills_id"), table_name="opportunity_required_skills")
    op.drop_table("opportunity_required_skills")
    op.drop_index("uq_opportunity_source_external_id", table_name="opportunities")
    op.drop_index(op.f("ix_opportunities_expires_at"), table_name="opportunities")
    op.drop_index(op.f("ix_opportunities_published_at"), table_name="opportunities")
    op.drop_index(op.f("ix_opportunities_source"), table_name="opportunities")
    op.drop_index(op.f("ix_opportunities_experience_level"), table_name="opportunities")
    op.drop_index(op.f("ix_opportunities_is_remote"), table_name="opportunities")
    op.drop_index(op.f("ix_opportunities_location"), table_name="opportunities")
    op.drop_index(op.f("ix_opportunities_target_role"), table_name="opportunities")
    op.drop_index(op.f("ix_opportunities_opportunity_type"), table_name="opportunities")
    op.drop_index(op.f("ix_opportunities_id"), table_name="opportunities")
    op.drop_table("opportunities")
