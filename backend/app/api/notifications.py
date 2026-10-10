from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models import User
from app.schemas.notifications import (
    NotificationListResponse,
    NotificationMutationResponse,
    NotificationUnreadCountResponse,
)
from app.services import notification_service as svc

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=NotificationListResponse, summary="List authenticated user's notifications")
def list_notifications(
    limit: int = Query(default=10, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    unread_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationListResponse:
    total, notifications = svc.list_notifications(
        db,
        current_user,
        limit=limit,
        offset=offset,
        unread_only=unread_only,
    )
    return NotificationListResponse(
        notifications=[svc.notification_response(notification) for notification in notifications],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/unread-count", response_model=NotificationUnreadCountResponse, summary="Get unread notification count")
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationUnreadCountResponse:
    return NotificationUnreadCountResponse(unread_count=svc.unread_count(db, current_user))


@router.patch("/{notification_id}/read", response_model=NotificationMutationResponse, summary="Mark a notification read")
def mark_read(
    notification_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationMutationResponse:
    updated = svc.mark_notification_read(db, current_user, notification_id)
    return NotificationMutationResponse(updated=updated)


@router.patch("/read-all", response_model=NotificationMutationResponse, summary="Mark all notifications read")
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationMutationResponse:
    updated = svc.mark_all_read(db, current_user)
    return NotificationMutationResponse(updated=updated)
