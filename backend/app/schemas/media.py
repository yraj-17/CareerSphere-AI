from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MediaUploadResponse(BaseModel):
    id: str
    object_key: str
    filename: str
    content_type: str
    size_bytes: int
    purpose: str
    created_at: Optional[datetime] = None
    url: Optional[str] = None

    model_config = {"from_attributes": True}


class MediaUrlResponse(BaseModel):
    id: str
    url: str
    expires_in_hours: int = Field(default=1)


class MediaListResponse(BaseModel):
    items: list[MediaUploadResponse]
