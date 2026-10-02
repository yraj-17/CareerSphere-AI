"""Community post interactions.

Revision ID: 010_community_post_interactions
Revises: 009_communities
Create Date: 2026-10-02

Creates:
- community_post_reactions
- community_post_comments
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "010_community_post_interactions"
down_revision: Union[str, None] = "009_communities"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _index_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in set(inspector.get_table_names()):
        return set()
    return {ix["name"] for ix in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "community_post_reactions" not in existing_tables:
        op.create_table(
            "community_post_reactions",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("post_id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("reaction_type", sa.String(length=20), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["post_id"], ["community_posts.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("post_id", "user_id", name="uq_community_post_reaction_user"),
        )

    existing_reaction_indexes = _index_names("community_post_reactions")
    for name, columns in (
        ("ix_community_post_reactions_id", ["id"]),
        ("ix_community_post_reactions_post_id", ["post_id"]),
        ("ix_community_post_reactions_user_id", ["user_id"]),
        ("ix_community_post_reactions_post_type", ["post_id", "reaction_type"]),
    ):
        if name not in existing_reaction_indexes:
            op.create_index(name, "community_post_reactions", columns, unique=False)

    existing_tables = set(sa.inspect(bind).get_table_names())
    if "community_post_comments" not in existing_tables:
        op.create_table(
            "community_post_comments",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("post_id", sa.String(length=36), nullable=False),
            sa.Column("author_id", sa.String(length=36), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["post_id"], ["community_posts.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    existing_comment_indexes = _index_names("community_post_comments")
    for name, columns in (
        ("ix_community_post_comments_id", ["id"]),
        ("ix_community_post_comments_post_id", ["post_id"]),
        ("ix_community_post_comments_author_id", ["author_id"]),
        ("ix_community_post_comments_post_created", ["post_id", "created_at"]),
    ):
        if name not in existing_comment_indexes:
            op.create_index(name, "community_post_comments", columns, unique=False)


def downgrade() -> None:
    op.drop_index("ix_community_post_comments_post_created", table_name="community_post_comments")
    op.drop_index("ix_community_post_comments_author_id", table_name="community_post_comments")
    op.drop_index("ix_community_post_comments_post_id", table_name="community_post_comments")
    op.drop_index("ix_community_post_comments_id", table_name="community_post_comments")
    op.drop_table("community_post_comments")

    op.drop_index("ix_community_post_reactions_post_type", table_name="community_post_reactions")
    op.drop_index("ix_community_post_reactions_user_id", table_name="community_post_reactions")
    op.drop_index("ix_community_post_reactions_post_id", table_name="community_post_reactions")
    op.drop_index("ix_community_post_reactions_id", table_name="community_post_reactions")
    op.drop_table("community_post_reactions")
