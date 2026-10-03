from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


COMMUNITY_CATEGORIES = {
    "technology",
    "ai_ml",
    "cloud_devops",
    "web_development",
    "data_science",
    "cyber_security",
    "career",
    "design",
    "entrepreneurship",
    "other",
}
COMMUNITY_VISIBILITIES = {"public", "private"}
MAX_COMMUNITY_NAME = 80
MAX_COMMUNITY_DESCRIPTION = 500
MAX_TAGS = 8
MAX_TAG_LENGTH = 40
MAX_POST_CONTENT = 2000
MAX_COMMENT_CONTENT = 1000
COMMUNITY_REACTION_TYPES = {
    "LIKE",
    "LOVE",
    "CELEBRATE",
    "SUPPORT",
    "INSIGHTFUL",
    "FUNNY",
}

# ── Post media / tag limits ───────────────────────────────────────────────────
MAX_POST_IMAGES = 4
MAX_POST_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB per image
ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}

MAX_POST_TAGS = 5
MAX_POST_TAG_LENGTH = 30

# ── Community image limits ────────────────────────────────────────────────────
MAX_COMMUNITY_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB


def default_reaction_counts() -> dict[str, int]:
    return {reaction_type: 0 for reaction_type in sorted(COMMUNITY_REACTION_TYPES)}


def _clean_tags(tags: list[str] | None) -> list[str]:
    if not tags:
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in tags:
        tag = str(raw).strip()
        if not tag:
            continue
        normalized = tag.lower()
        if normalized in seen:
            continue
        if len(tag) > MAX_TAG_LENGTH:
            raise ValueError(f"Tags must be {MAX_TAG_LENGTH} characters or fewer.")
        seen.add(normalized)
        cleaned.append(tag)
        if len(cleaned) > MAX_TAGS:
            raise ValueError(f"Communities support at most {MAX_TAGS} tags.")
    return cleaned


def clean_post_tags(raw_tags: list[str] | None) -> list[str]:
    """
    Normalise post topic tags:
    - strip whitespace
    - strip leading/trailing '#'
    - case-insensitive duplicate detection
    - max length MAX_POST_TAG_LENGTH
    - max count MAX_POST_TAGS
    Returns cleaned list (display-form preserved from first occurrence).
    """
    if not raw_tags:
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in raw_tags:
        tag = str(raw).strip().lstrip("#").rstrip("#").strip()
        if not tag:
            raise ValueError("Empty tag is not allowed.")
        if len(tag) > MAX_POST_TAG_LENGTH:
            raise ValueError(
                f"Tag '{tag[:20]}…' exceeds the {MAX_POST_TAG_LENGTH}-character limit."
            )
        normalized = tag.lower()
        if normalized in seen:
            raise ValueError(f"Duplicate tag '{tag}' (case-insensitive).")
        seen.add(normalized)
        cleaned.append(tag)
        if len(cleaned) > MAX_POST_TAGS:
            raise ValueError(f"Posts support at most {MAX_POST_TAGS} topic tags.")
    return cleaned


class CommunityCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=MAX_COMMUNITY_NAME)
    description: str = Field(..., min_length=1, max_length=MAX_COMMUNITY_DESCRIPTION)
    category: str
    tags: list[str] = []
    visibility: str = "public"

    @field_validator("name", "description", mode="before")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in COMMUNITY_CATEGORIES:
            raise ValueError("Invalid community category.")
        return value

    @field_validator("visibility")
    @classmethod
    def validate_visibility(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in COMMUNITY_VISIBILITIES:
            raise ValueError("Visibility must be public or private.")
        return value

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: list[str] | None) -> list[str]:
        return _clean_tags(value)


class CommunityPostCreateRequest(BaseModel):
    """
    JSON body for text-only or text+tag post creation.
    Images are handled separately as multipart/form-data in the API layer.
    """
    content: str = Field(default="", max_length=MAX_POST_CONTENT)
    tags: list[str] = Field(default_factory=list)

    @field_validator("content", mode="before")
    @classmethod
    def strip_content(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("tags")
    @classmethod
    def validate_post_tags(cls, value: list[str] | None) -> list[str]:
        return clean_post_tags(value or [])


class CommunityReactionRequest(BaseModel):
    reaction_type: str

    @field_validator("reaction_type")
    @classmethod
    def validate_reaction_type(cls, value: str) -> str:
        value = value.strip().upper()
        if value not in COMMUNITY_REACTION_TYPES:
            raise ValueError("Invalid community post reaction.")
        return value


class CommunityPostCommentCreateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=MAX_COMMENT_CONTENT)

    @field_validator("content", mode="before")
    @classmethod
    def strip_content(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value


class CommunityUserSummary(BaseModel):
    id: str
    username: str
    first_name: str
    last_name: str
    headline: Optional[str] = None
    location: Optional[str] = None
    profile_photo_url: Optional[str] = None


class CommunityResponse(BaseModel):
    id: str
    name: str
    description: str
    category: str
    tags: list[str] = []
    visibility: str
    creator_id: str
    creator: Optional[CommunityUserSummary] = None
    member_count: int = 0
    joined: bool = False
    is_joined: bool = False
    is_owner: bool = False
    membership_status: str = "none"
    image_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CommunityListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    communities: list[CommunityResponse]


class CommunityMembershipResponse(BaseModel):
    success: bool
    community_id: str
    joined: bool


class CommunityMemberResponse(BaseModel):
    id: str
    username: str
    first_name: str
    last_name: str
    headline: Optional[str] = None
    location: Optional[str] = None
    profile_photo_url: Optional[str] = None
    role: str = "member"
    joined_at: Optional[datetime] = None


class CommunityMembersResponse(BaseModel):
    total: int
    limit: int
    offset: int
    members: list[CommunityMemberResponse]


class CommunityPostMediaResponse(BaseModel):
    id: str
    url: str
    media_type: str = "image"
    sort_order: int = 0


class CommunityPostResponse(BaseModel):
    id: str
    community_id: str
    author_id: str
    author: CommunityUserSummary
    content: str
    like_count: int = 0
    reaction_counts: dict[str, int] = Field(default_factory=default_reaction_counts)
    total_reactions: int = 0
    my_reaction: Optional[str] = None
    comment_count: int = 0
    can_delete: bool = False
    media: List[CommunityPostMediaResponse] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CommunityPostsResponse(BaseModel):
    total: int
    limit: int
    offset: int
    posts: list[CommunityPostResponse]


class CommunityReactionSummaryResponse(BaseModel):
    post_id: str
    my_reaction: Optional[str] = None
    counts: dict[str, int] = Field(default_factory=default_reaction_counts)
    total: int = 0


class CommunityPostCommentResponse(BaseModel):
    id: str
    post_id: str
    author_id: str
    author: CommunityUserSummary
    content: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CommunityPostCommentsResponse(BaseModel):
    total: int
    limit: int
    offset: int
    comments: list[CommunityPostCommentResponse]


class CommunityPostDeleteResponse(BaseModel):
    success: bool
    post_id: str


class CommunityImageUpdateResponse(BaseModel):
    success: bool
    community_id: str
    image_url: Optional[str] = None
