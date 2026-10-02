"""Communities V1.

Revision ID: 009_communities
Revises: 008_message_management
Create Date: 2026-10-02

Creates:
- communities
- community_memberships
- community_posts
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "009_communities"
down_revision: Union[str, None] = "008_message_management"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "communities" not in existing_tables:
        op.create_table(
            "communities",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=80), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("category", sa.String(length=80), nullable=False),
            sa.Column("tags", sa.JSON(), nullable=False),
            sa.Column("visibility", sa.String(length=20), nullable=False, server_default="public"),
            sa.Column("creator_id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["creator_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(bind)
    existing_community_indexes = (
        {ix["name"] for ix in inspector.get_indexes("communities")}
        if "communities" in set(inspector.get_table_names())
        else set()
    )
    for name, columns in (
        ("ix_communities_id", ["id"]),
        ("ix_communities_creator_id", ["creator_id"]),
        ("ix_communities_category", ["category"]),
        ("ix_communities_visibility", ["visibility"]),
        ("ix_communities_created_at", ["created_at"]),
    ):
        if name not in existing_community_indexes:
            op.create_index(name, "communities", columns, unique=False)

    existing_tables = set(sa.inspect(bind).get_table_names())
    if "community_memberships" not in existing_tables:
        op.create_table(
            "community_memberships",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("community_id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("role", sa.String(length=20), nullable=False, server_default="member"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["community_id"], ["communities.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("community_id", "user_id", name="uq_community_membership_user"),
        )

    inspector = sa.inspect(bind)
    existing_membership_indexes = (
        {ix["name"] for ix in inspector.get_indexes("community_memberships")}
        if "community_memberships" in set(inspector.get_table_names())
        else set()
    )
    for name, columns in (
        ("ix_community_memberships_id", ["id"]),
        ("ix_community_memberships_community_id", ["community_id"]),
        ("ix_community_memberships_user_id", ["user_id"]),
    ):
        if name not in existing_membership_indexes:
            op.create_index(name, "community_memberships", columns, unique=False)

    existing_tables = set(sa.inspect(bind).get_table_names())
    if "community_posts" not in existing_tables:
        op.create_table(
            "community_posts",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("community_id", sa.String(length=36), nullable=False),
            sa.Column("author_id", sa.String(length=36), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["community_id"], ["communities.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(bind)
    existing_post_indexes = (
        {ix["name"] for ix in inspector.get_indexes("community_posts")}
        if "community_posts" in set(inspector.get_table_names())
        else set()
    )
    for name, columns in (
        ("ix_community_posts_id", ["id"]),
        ("ix_community_posts_community_id", ["community_id"]),
        ("ix_community_posts_author_id", ["author_id"]),
        ("ix_community_posts_created_at", ["created_at"]),
        ("ix_community_posts_community_created", ["community_id", "created_at"]),
    ):
        if name not in existing_post_indexes:
            op.create_index(name, "community_posts", columns, unique=False)


def downgrade() -> None:
    op.drop_index("ix_community_posts_community_created", table_name="community_posts")
    op.drop_index("ix_community_posts_created_at", table_name="community_posts")
    op.drop_index("ix_community_posts_author_id", table_name="community_posts")
    op.drop_index("ix_community_posts_community_id", table_name="community_posts")
    op.drop_index("ix_community_posts_id", table_name="community_posts")
    op.drop_table("community_posts")

    op.drop_index("ix_community_memberships_user_id", table_name="community_memberships")
    op.drop_index("ix_community_memberships_community_id", table_name="community_memberships")
    op.drop_index("ix_community_memberships_id", table_name="community_memberships")
    op.drop_table("community_memberships")

    op.drop_index("ix_communities_created_at", table_name="communities")
    op.drop_index("ix_communities_visibility", table_name="communities")
    op.drop_index("ix_communities_category", table_name="communities")
    op.drop_index("ix_communities_creator_id", table_name="communities")
    op.drop_index("ix_communities_id", table_name="communities")
    op.drop_table("communities")
