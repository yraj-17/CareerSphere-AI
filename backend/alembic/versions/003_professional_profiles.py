"""Professional profile system.

Revision ID: 003_profiles
Revises: 002_conversations
Create Date: 2026-09-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003_profiles"
down_revision: Union[str, None] = "002_conversations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("profile_photo_media_id", sa.String(length=36), nullable=True),
        sa.Column("headline", sa.String(length=160), nullable=True),
        sa.Column("location", sa.String(length=160), nullable=True),
        sa.Column("about", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["profile_photo_media_id"], ["media_objects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(op.f("ix_profiles_id"), "profiles", ["id"], unique=False)
    op.create_index(op.f("ix_profiles_user_id"), "profiles", ["user_id"], unique=True)

    op.create_table(
        "profile_skills",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("normalized_name", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "normalized_name", name="uq_profile_skill_name"),
    )
    op.create_index(op.f("ix_profile_skills_id"), "profile_skills", ["id"], unique=False)
    op.create_index(op.f("ix_profile_skills_profile_id"), "profile_skills", ["profile_id"], unique=False)

    op.create_table(
        "profile_education",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        sa.Column("institution", sa.String(length=180), nullable=False),
        sa.Column("degree", sa.String(length=140), nullable=False),
        sa.Column("field_of_study", sa.String(length=140), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_profile_education_id"), "profile_education", ["id"], unique=False)
    op.create_index(op.f("ix_profile_education_profile_id"), "profile_education", ["profile_id"], unique=False)

    op.create_table(
        "profile_experience",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        sa.Column("company", sa.String(length=180), nullable=False),
        sa.Column("job_title", sa.String(length=160), nullable=False),
        sa.Column("employment_type", sa.String(length=40), nullable=True),
        sa.Column("location", sa.String(length=160), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("currently_working", sa.Boolean(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_profile_experience_id"), "profile_experience", ["id"], unique=False)
    op.create_index(op.f("ix_profile_experience_profile_id"), "profile_experience", ["profile_id"], unique=False)

    op.create_table(
        "profile_projects",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("github_url", sa.String(length=500), nullable=True),
        sa.Column("live_url", sa.String(length=500), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_profile_projects_id"), "profile_projects", ["id"], unique=False)
    op.create_index(op.f("ix_profile_projects_profile_id"), "profile_projects", ["profile_id"], unique=False)

    op.create_table(
        "project_technologies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("normalized_name", sa.String(length=80), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["profile_projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "normalized_name", name="uq_project_technology_name"),
    )
    op.create_index(op.f("ix_project_technologies_id"), "project_technologies", ["id"], unique=False)
    op.create_index(op.f("ix_project_technologies_project_id"), "project_technologies", ["project_id"], unique=False)

    op.create_table(
        "profile_certifications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("issuing_organization", sa.String(length=180), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("expiration_date", sa.Date(), nullable=True),
        sa.Column("credential_id", sa.String(length=160), nullable=True),
        sa.Column("credential_url", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_profile_certifications_id"), "profile_certifications", ["id"], unique=False)
    op.create_index(op.f("ix_profile_certifications_profile_id"), "profile_certifications", ["profile_id"], unique=False)

    op.create_table(
        "career_preferences",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        sa.Column("target_job_role", sa.String(length=160), nullable=True),
        sa.Column("preferred_industry", sa.String(length=160), nullable=True),
        sa.Column("preferred_work_type", sa.String(length=80), nullable=True),
        sa.Column("preferred_locations", sa.Text(), nullable=True),
        sa.Column("career_interests", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id"),
    )
    op.create_index(op.f("ix_career_preferences_id"), "career_preferences", ["id"], unique=False)
    op.create_index(op.f("ix_career_preferences_profile_id"), "career_preferences", ["profile_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_career_preferences_profile_id"), table_name="career_preferences")
    op.drop_index(op.f("ix_career_preferences_id"), table_name="career_preferences")
    op.drop_table("career_preferences")
    op.drop_index(op.f("ix_profile_certifications_profile_id"), table_name="profile_certifications")
    op.drop_index(op.f("ix_profile_certifications_id"), table_name="profile_certifications")
    op.drop_table("profile_certifications")
    op.drop_index(op.f("ix_project_technologies_project_id"), table_name="project_technologies")
    op.drop_index(op.f("ix_project_technologies_id"), table_name="project_technologies")
    op.drop_table("project_technologies")
    op.drop_index(op.f("ix_profile_projects_profile_id"), table_name="profile_projects")
    op.drop_index(op.f("ix_profile_projects_id"), table_name="profile_projects")
    op.drop_table("profile_projects")
    op.drop_index(op.f("ix_profile_experience_profile_id"), table_name="profile_experience")
    op.drop_index(op.f("ix_profile_experience_id"), table_name="profile_experience")
    op.drop_table("profile_experience")
    op.drop_index(op.f("ix_profile_education_profile_id"), table_name="profile_education")
    op.drop_index(op.f("ix_profile_education_id"), table_name="profile_education")
    op.drop_table("profile_education")
    op.drop_index(op.f("ix_profile_skills_profile_id"), table_name="profile_skills")
    op.drop_index(op.f("ix_profile_skills_id"), table_name="profile_skills")
    op.drop_table("profile_skills")
    op.drop_index(op.f("ix_profiles_user_id"), table_name="profiles")
    op.drop_index(op.f("ix_profiles_id"), table_name="profiles")
    op.drop_table("profiles")
