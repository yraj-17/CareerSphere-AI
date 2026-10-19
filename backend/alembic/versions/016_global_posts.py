"""Add the authenticated global Home feed.

Revision ID: 016_global_posts
Revises: 015_ai_conversation_preferences
Create Date: 2026-10-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "016_global_posts"
down_revision: Union[str, None] = "015_ai_conversation_preferences"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    tables = _tables()
    if "global_posts" not in tables:
        op.create_table(
            "global_posts",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("author_id", sa.String(36), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("resource_id", sa.String(36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["resource_id"], ["resources.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_global_posts_id", "global_posts", ["id"], unique=False)
        op.create_index("ix_global_posts_author_id", "global_posts", ["author_id"], unique=False)
        op.create_index("ix_global_posts_author_created", "global_posts", ["author_id", "created_at"], unique=False)
        op.create_index("ix_global_posts_created_id", "global_posts", ["created_at", "id"], unique=False)
        op.create_index("ix_global_posts_resource_id", "global_posts", ["resource_id"], unique=False)

    if "global_post_media" not in tables:
        op.create_table(
            "global_post_media",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("post_id", sa.String(36), nullable=False),
            sa.Column("media_id", sa.String(36), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["post_id"], ["global_posts.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["media_id"], ["media_objects.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_global_post_media_id", "global_post_media", ["id"], unique=False)
        op.create_index("ix_global_post_media_post_id", "global_post_media", ["post_id"], unique=False)
        op.create_index("ix_global_post_media_media_id", "global_post_media", ["media_id"], unique=False)

    if "global_post_likes" not in tables:
        op.create_table(
            "global_post_likes",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("post_id", sa.String(36), nullable=False),
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["post_id"], ["global_posts.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("post_id", "user_id", name="uq_global_post_like_user"),
        )
        op.create_index("ix_global_post_likes_id", "global_post_likes", ["id"], unique=False)
        op.create_index("ix_global_post_likes_post_id", "global_post_likes", ["post_id"], unique=False)
        op.create_index("ix_global_post_likes_user_id", "global_post_likes", ["user_id"], unique=False)

    if "global_post_comments" not in tables:
        op.create_table(
            "global_post_comments",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("post_id", sa.String(36), nullable=False),
            sa.Column("author_id", sa.String(36), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["post_id"], ["global_posts.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_global_post_comments_id", "global_post_comments", ["id"], unique=False)
        op.create_index("ix_global_post_comments_post_id", "global_post_comments", ["post_id"], unique=False)
        op.create_index("ix_global_post_comments_author_id", "global_post_comments", ["author_id"], unique=False)
        op.create_index("ix_global_post_comments_post_created", "global_post_comments", ["post_id", "created_at"], unique=False)


def downgrade() -> None:
    for name in ("ix_global_post_comments_post_created", "ix_global_post_comments_author_id", "ix_global_post_comments_post_id", "ix_global_post_comments_id"):
        op.drop_index(name, table_name="global_post_comments")
    op.drop_table("global_post_comments")
    for name in ("ix_global_post_likes_user_id", "ix_global_post_likes_post_id", "ix_global_post_likes_id"):
        op.drop_index(name, table_name="global_post_likes")
    op.drop_table("global_post_likes")
    for name in ("ix_global_post_media_media_id", "ix_global_post_media_post_id", "ix_global_post_media_id"):
        op.drop_index(name, table_name="global_post_media")
    op.drop_table("global_post_media")
    for name in ("ix_global_posts_resource_id", "ix_global_posts_created_id", "ix_global_posts_author_created", "ix_global_posts_author_id", "ix_global_posts_id"):
        op.drop_index(name, table_name="global_posts")
    op.drop_table("global_posts")
