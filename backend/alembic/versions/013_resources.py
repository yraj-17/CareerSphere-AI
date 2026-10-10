"""Resource Sharing V1.

Revision ID: 013_resources
Revises: 012_notifications
Create Date: 2026-10-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "013_resources"
down_revision: Union[str, None] = "012_notifications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _index_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table_name not in set(inspector.get_table_names()):
        return set()
    return {ix["name"] for ix in inspector.get_indexes(table_name)}


def _unique_constraint_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table_name not in set(inspector.get_table_names()):
        return set()
    return {uc["name"] for uc in inspector.get_unique_constraints(table_name)}


def upgrade() -> None:
    tables = _existing_tables()
    resource_type = sa.Enum(
        "ARTICLE",
        "COURSE",
        "VIDEO",
        "DOCUMENTATION",
        "GITHUB_REPOSITORY",
        "TOOL",
        "BOOK",
        "TUTORIAL",
        "OTHER",
        name="resourcetype",
        create_constraint=True,
    )

    if "resources" not in tables:
        resource_type.create(op.get_bind(), checkfirst=True)
        op.create_table(
            "resources",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("author_id", sa.String(36), nullable=False),
            sa.Column("title", sa.String(180), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("url", sa.String(1000), nullable=False),
            sa.Column("source_domain", sa.String(255), nullable=True),
            sa.Column("resource_type", resource_type, nullable=False),
            sa.Column("category", sa.String(80), nullable=True),
            sa.Column("tags", sa.JSON(), nullable=False),
            sa.Column("normalized_tags", sa.JSON(), nullable=False),
            sa.Column("thumbnail_url", sa.String(1000), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    if "saved_resources" not in tables:
        op.create_table(
            "saved_resources",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column("resource_id", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["resource_id"], ["resources.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    resource_indexes = _index_names("resources")
    for name, columns in (
        ("ix_resources_id", ["id"]),
        ("ix_resources_author_id", ["author_id"]),
        ("ix_resources_source_domain", ["source_domain"]),
        ("ix_resources_resource_type", ["resource_type"]),
        ("ix_resources_category", ["category"]),
        ("ix_resources_created_at", ["created_at"]),
        ("ix_resources_author_created", ["author_id", "created_at"]),
        ("ix_resources_type_created", ["resource_type", "created_at"]),
        ("ix_resources_category_created", ["category", "created_at"]),
    ):
        if name not in resource_indexes:
            op.create_index(name, "resources", columns, unique=False)

    saved_indexes = _index_names("saved_resources")
    for name, columns in (
        ("ix_saved_resources_id", ["id"]),
        ("ix_saved_resources_user_id", ["user_id"]),
        ("ix_saved_resources_resource_id", ["resource_id"]),
        ("ix_saved_resources_user_created", ["user_id", "created_at"]),
    ):
        if name not in saved_indexes:
            op.create_index(name, "saved_resources", columns, unique=False)

    saved_constraints = _unique_constraint_names("saved_resources")
    if "uq_saved_resource_user_resource" not in saved_constraints:
        op.create_unique_constraint(
            "uq_saved_resource_user_resource",
            "saved_resources",
            ["user_id", "resource_id"],
        )


def downgrade() -> None:
    for name in (
        "ix_saved_resources_user_created",
        "ix_saved_resources_resource_id",
        "ix_saved_resources_user_id",
        "ix_saved_resources_id",
    ):
        op.drop_index(name, table_name="saved_resources")
    op.drop_constraint("uq_saved_resource_user_resource", "saved_resources", type_="unique")
    op.drop_table("saved_resources")

    for name in (
        "ix_resources_category_created",
        "ix_resources_type_created",
        "ix_resources_author_created",
        "ix_resources_created_at",
        "ix_resources_category",
        "ix_resources_resource_type",
        "ix_resources_source_domain",
        "ix_resources_author_id",
        "ix_resources_id",
    ):
        op.drop_index(name, table_name="resources")
    op.drop_table("resources")
    sa.Enum(name="resourcetype").drop(op.get_bind(), checkfirst=True)
