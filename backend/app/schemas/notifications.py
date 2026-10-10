from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class NotificationActorSummary(BaseModel):
    id: str
    username: str
    first_name: str
    last_name: str
    name: str
    profile_photo_url: Optional[str] = None


class NotificationResponse(BaseModel):
    id: str
    type: str
    actor: Optional[NotificationActorSummary] = None
    message: str
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    action_url: Optional[str] = None
    is_read: bool
    created_at: datetime


class NotificationListResponse(BaseModel):
    notifications: list[NotificationResponse]
    total: int
    limit: int
    offset: int


class NotificationUnreadCountResponse(BaseModel):
    unread_count: int


class NotificationMutationResponse(BaseModel):
    success: bool = True
    updated: int = 0
