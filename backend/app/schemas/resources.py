from __future__ import annotations

from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


RESOURCE_TYPES = {
    "ARTICLE",
    "COURSE",
    "VIDEO",
    "DOCUMENTATION",
    "GITHUB_REPOSITORY",
    "TOOL",
    "BOOK",
    "TUTORIAL",
    "OTHER",
}

MAX_RESOURCE_TITLE = 180
MAX_RESOURCE_DESCRIPTION = 1200
MAX_RESOURCE_CATEGORY = 80
MAX_RESOURCE_URL = 1000
MAX_RESOURCE_TAGS = 8
MAX_RESOURCE_TAG_LENGTH = 40


def normalize_resource_tags(tags: list[str] | None) -> tuple[list[str], list[str]]:
    if not tags:
        return [], []

    cleaned: list[str] = []
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in tags:
        tag = str(raw).strip()
        if not tag:
            continue
        norm = tag.lower()
        if norm in seen:
            continue
        if len(tag) > MAX_RESOURCE_TAG_LENGTH:
            raise ValueError(f"Tags must be {MAX_RESOURCE_TAG_LENGTH} characters or fewer.")
        seen.add(norm)
        cleaned.append(tag)
        normalized.append(norm)
        if len(cleaned) > MAX_RESOURCE_TAGS:
            raise ValueError(f"Resources support at most {MAX_RESOURCE_TAGS} tags.")
    return cleaned, normalized


def resource_domain(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def validate_resource_url(value: str) -> str:
    value = value.strip()
    if len(value) > MAX_RESOURCE_URL:
        raise ValueError(f"URL must be {MAX_RESOURCE_URL} characters or fewer.")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Resource URL must be a valid http(s) URL.")
    return value


class ResourceAuthorSummary(BaseModel):
    id: str
    username: str
    first_name: str
    last_name: str
    headline: Optional[str] = None
    location: Optional[str] = None
    profile_photo_url: Optional[str] = None


class ResourceBaseRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=MAX_RESOURCE_TITLE)
    description: Optional[str] = Field(default=None, max_length=MAX_RESOURCE_DESCRIPTION)
    url: str = Field(..., min_length=1, max_length=MAX_RESOURCE_URL)
    resource_type: str
    category: Optional[str] = Field(default=None, max_length=MAX_RESOURCE_CATEGORY)
    tags: list[str] = Field(default_factory=list)
    thumbnail_url: Optional[str] = Field(default=None, max_length=MAX_RESOURCE_URL)

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, value: str) -> str:
        if isinstance(value, str):
            value = value.strip()
        return value

    @field_validator("description", mode="before")
    @classmethod
    def strip_description(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return validate_resource_url(value)

    @field_validator("thumbnail_url")
    @classmethod
    def validate_thumbnail_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        return validate_resource_url(value)

    @field_validator("resource_type")
    @classmethod
    def validate_resource_type(cls, value: str) -> str:
        value = value.strip().upper()
        if value not in RESOURCE_TYPES:
            raise ValueError("Invalid resource type.")
        return value

    @field_validator("category", mode="before")
    @classmethod
    def clean_category(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: list[str] | None) -> list[str]:
        cleaned, _ = normalize_resource_tags(value)
        return cleaned


class ResourceCreateRequest(ResourceBaseRequest):
    pass


class ResourceUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=MAX_RESOURCE_TITLE)
    description: Optional[str] = Field(default=None, max_length=MAX_RESOURCE_DESCRIPTION)
    url: Optional[str] = Field(default=None, min_length=1, max_length=MAX_RESOURCE_URL)
    resource_type: Optional[str] = None
    category: Optional[str] = Field(default=None, max_length=MAX_RESOURCE_CATEGORY)
    tags: Optional[list[str]] = None
    thumbnail_url: Optional[str] = Field(default=None, max_length=MAX_RESOURCE_URL)

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("description", mode="before")
    @classmethod
    def strip_description(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        return validate_resource_url(value) if value is not None else None

    @field_validator("thumbnail_url")
    @classmethod
    def validate_thumbnail_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        return validate_resource_url(value)

    @field_validator("resource_type")
    @classmethod
    def validate_resource_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().upper()
        if value not in RESOURCE_TYPES:
            raise ValueError("Invalid resource type.")
        return value

    @field_validator("category", mode="before")
    @classmethod
    def clean_category(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned, _ = normalize_resource_tags(value)
        return cleaned


class ResourceResponse(BaseModel):
    id: str
    author_id: str
    author: Optional[ResourceAuthorSummary] = None
    title: str
    description: Optional[str] = None
    url: str
    source_domain: Optional[str] = None
    resource_type: str
    category: Optional[str] = None
    tags: list[str] = []
    thumbnail_url: Optional[str] = None
    is_owner: bool = False
    is_saved: bool = False
    save_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ResourceListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    resources: list[ResourceResponse]


class ResourceSaveResponse(BaseModel):
    success: bool
    resource_id: str
    is_saved: bool
