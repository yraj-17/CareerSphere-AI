from __future__ import annotations

from datetime import datetime
from typing import Optional

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
    content: str = Field(..., min_length=1, max_length=MAX_POST_CONTENT)

    @field_validator("content", mode="before")
    @classmethod
    def strip_content(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value


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
