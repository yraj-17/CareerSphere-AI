from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


MAX_POST_CONTENT = 3000
MAX_COMMENT_CONTENT = 1000
MAX_POST_IMAGES = 4


def _trim_required(value: str) -> str:
    value = (value or "").strip()
    if not value:
        raise ValueError("Content is required.")
    return value


class PostCreateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=MAX_POST_CONTENT)
    resource_id: Optional[str] = None
    image_media_ids: list[str] = Field(default_factory=list, max_length=MAX_POST_IMAGES)

    @field_validator("content", mode="before")
    @classmethod
    def clean_content(cls, value: str) -> str:
        value = _trim_required(value)
        if len(value) > MAX_POST_CONTENT:
            raise ValueError(f"Post content must be {MAX_POST_CONTENT} characters or fewer.")
        return value


class PostUpdateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=MAX_POST_CONTENT)
    resource_id: Optional[str] = None

    @field_validator("content", mode="before")
    @classmethod
    def clean_content(cls, value: str) -> str:
        return _trim_required(value)


class PostAuthorResponse(BaseModel):
    id: str
    username: str
    first_name: str
    last_name: str
    headline: Optional[str] = None
    profile_photo_url: Optional[str] = None


class PostMediaResponse(BaseModel):
    id: str
    url: Optional[str] = None
    content_type: str


class PostResourceResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    url: str
    source_domain: Optional[str] = None
    resource_type: str


class PostResponse(BaseModel):
    id: str
    content: str
    created_at: datetime
    updated_at: datetime
    author: PostAuthorResponse
    media: list[PostMediaResponse] = Field(default_factory=list)
    resource: Optional[PostResourceResponse] = None
    like_count: int = 0
    comment_count: int = 0
    liked_by_me: bool = False
    is_owner: bool = False


class PostListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    posts: list[PostResponse]


class LikeResponse(BaseModel):
    post_id: str
    like_count: int
    liked_by_me: bool


class CommentCreateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=MAX_COMMENT_CONTENT)

    @field_validator("content", mode="before")
    @classmethod
    def clean_content(cls, value: str) -> str:
        value = _trim_required(value)
        if len(value) > MAX_COMMENT_CONTENT:
            raise ValueError(f"Comment must be {MAX_COMMENT_CONTENT} characters or fewer.")
        return value


class CommentUpdateRequest(CommentCreateRequest):
    pass


class CommentResponse(BaseModel):
    id: str
    post_id: str
    content: str
    created_at: datetime
    updated_at: datetime
    author: PostAuthorResponse
    is_owner: bool = False


class CommentListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    comments: list[CommentResponse]
