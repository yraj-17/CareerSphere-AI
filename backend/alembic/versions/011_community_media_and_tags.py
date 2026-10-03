"""Community media and tags.

Revision ID: 011_community_media_and_tags
Revises: 010_community_post_interactions
Create Date: 2026-10-02

Adds:
- communities.image_key   — optional MinIO object key for community profile photo
- community_post_media    — per-post image attachments (up to 4)
- community_post_tags     — topic hashtags for community posts (up to 5)

Constraints / indexes follow the conventions in 009 and 010.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "011_community_media_and_tags"
down_revision: Union[str, None] = "010_community_post_interactions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in set(inspector.get_table_names()):
        return set()
    return {col["name"] for col in inspector.get_columns(table_name)}


def _existing_tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _index_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in set(inspector.get_table_names()):
        return set()
    return {ix["name"] for ix in inspector.get_indexes(table_name)}


def upgrade() -> None:
    # ── 1. Add optional image_key column to communities ─────────────────────
    if "image_key" not in _existing_columns("communities"):
        op.add_column(
            "communities",
            sa.Column("image_key", sa.String(512), nullable=True),
        )

    # ── 2. community_post_media ─────────────────────────────────────────────
    tables = _existing_tables()
    if "community_post_media" not in tables:
        op.create_table(
            "community_post_media",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("post_id", sa.String(36), nullable=False),
            sa.Column("object_key", sa.String(512), nullable=False),
            sa.Column("media_type", sa.String(20), nullable=False, server_default="image"),
            sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["post_id"], ["community_posts.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    existing_media_indexes = _index_names("community_post_media")
    for name, columns in (
        ("ix_community_post_media_id", ["id"]),
        ("ix_community_post_media_post_id", ["post_id"]),
        ("ix_community_post_media_post_order", ["post_id", "sort_order"]),
    ):
        if name not in existing_media_indexes:
            op.create_index(name, "community_post_media", columns, unique=False)

    # ── 3. community_post_tags ──────────────────────────────────────────────
    tables = _existing_tables()
    if "community_post_tags" not in tables:
        op.create_table(
            "community_post_tags",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("post_id", sa.String(36), nullable=False),
            sa.Column("tag", sa.String(30), nullable=False),
            sa.Column("tag_normalized", sa.String(30), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["post_id"], ["community_posts.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
            # Each post can have each normalized tag at most once.
            sa.UniqueConstraint(
                "post_id", "tag_normalized", name="uq_community_post_tag_normalized"
            ),
        )

    existing_tag_indexes = _index_names("community_post_tags")
    for name, columns in (
        ("ix_community_post_tags_id", ["id"]),
        ("ix_community_post_tags_post_id", ["post_id"]),
        ("ix_community_post_tags_tag_normalized", ["tag_normalized"]),
    ):
        if name not in existing_tag_indexes:
            op.create_index(name, "community_post_tags", columns, unique=False)

    # Also allow nullable content for posts that have images but no text
    # We handle this at application layer (content can be empty string when images present)
    # No DB change needed — content TEXT column allows empty strings already.


def downgrade() -> None:
    # Tags
    op.drop_index("ix_community_post_tags_tag_normalized", table_name="community_post_tags")
    op.drop_index("ix_community_post_tags_post_id", table_name="community_post_tags")
    op.drop_index("ix_community_post_tags_id", table_name="community_post_tags")
    op.drop_table("community_post_tags")

    # Media
    op.drop_index("ix_community_post_media_post_order", table_name="community_post_media")
    op.drop_index("ix_community_post_media_post_id", table_name="community_post_media")
    op.drop_index("ix_community_post_media_id", table_name="community_post_media")
    op.drop_table("community_post_media")

    # Community image column
    op.drop_column("communities", "image_key")
