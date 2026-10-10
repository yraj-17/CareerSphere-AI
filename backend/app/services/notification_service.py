from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.db.models import Notification, NotificationType, Profile, User
from app.schemas.notifications import (
    NotificationActorSummary,
    NotificationResponse,
)
from app.services.storage_service import presigned_get_url


CONNECTION_REQUEST_URL = "/dashboard/networking/my-network?tab=requests"
CONNECTION_ACCEPTED_URL = "/dashboard/networking/my-network"
CONNECTION_REJECTED_URL = "/dashboard/networking/my-network?tab=sent"


def _display_name(user: User | None) -> str:
    if user is None:
        return "Someone"
    return f"{user.first_name} {user.last_name}".strip() or user.username


def _profile_photo_url(profile: Profile | None) -> str | None:
    if not profile or not profile.profile_photo:
        return None
    try:
        return presigned_get_url(profile.profile_photo.object_key)
    except Exception:
        return None


def _actor_summary(user: User | None) -> NotificationActorSummary | None:
    if user is None:
        return None
    return NotificationActorSummary(
        id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        name=_display_name(user),
        profile_photo_url=_profile_photo_url(user.profile),
    )


def notification_response(notification: Notification) -> NotificationResponse:
    return NotificationResponse(
        id=notification.id,
        type=notification.type.value if hasattr(notification.type, "value") else str(notification.type),
        actor=_actor_summary(notification.actor),
        message=notification.message,
        reference_type=notification.reference_type,
        reference_id=notification.reference_id,
        action_url=notification.action_url,
        is_read=bool(notification.is_read),
        created_at=notification.created_at,
    )


def create_notification(
    db: Session,
    *,
    recipient_id: str,
    actor_id: str | None,
    type_: NotificationType,
    message: str,
    reference_type: str | None = None,
    reference_id: str | None = None,
    action_url: str | None = None,
) -> Notification:
    notification = Notification(
        recipient_id=recipient_id,
        actor_id=actor_id,
        type=type_,
        message=message,
        reference_type=reference_type,
        reference_id=reference_id,
        action_url=action_url,
    )
    db.add(notification)
    return notification


def create_unique_notification(
    db: Session,
    *,
    recipient_id: str,
    actor_id: str | None,
    type_: NotificationType,
    message: str,
    reference_type: str | None = None,
    reference_id: str | None = None,
    action_url: str | None = None,
) -> Notification:
    existing = (
        db.query(Notification)
        .filter(
            Notification.recipient_id == recipient_id,
            Notification.actor_id == actor_id,
            Notification.type == type_,
            Notification.reference_type == reference_type,
            Notification.reference_id == reference_id,
        )
        .first()
    )
    if existing:
        return existing
    return create_notification(
        db,
        recipient_id=recipient_id,
        actor_id=actor_id,
        type_=type_,
        message=message,
        reference_type=reference_type,
        reference_id=reference_id,
        action_url=action_url,
    )


def create_connection_request_notification(db: Session, *, connection_id: str, requester: User, receiver: User) -> Notification:
    return create_unique_notification(
        db,
        recipient_id=receiver.id,
        actor_id=requester.id,
        type_=NotificationType.connection_request,
        message=f"{_display_name(requester)} sent you a connection request.",
        reference_type="connection",
        reference_id=connection_id,
        action_url=CONNECTION_REQUEST_URL,
    )


def create_connection_accepted_notification(db: Session, *, connection_id: str, requester: User, receiver: User) -> Notification:
    return create_unique_notification(
        db,
        recipient_id=requester.id,
        actor_id=receiver.id,
        type_=NotificationType.connection_accepted,
        message=f"{_display_name(receiver)} accepted your connection request.",
        reference_type="connection",
        reference_id=connection_id,
        action_url=CONNECTION_ACCEPTED_URL,
    )


def create_connection_rejected_notification(db: Session, *, connection_id: str, requester: User, receiver: User) -> Notification:
    return create_unique_notification(
        db,
        recipient_id=requester.id,
        actor_id=receiver.id,
        type_=NotificationType.connection_rejected,
        message=f"{_display_name(receiver)} declined your connection request.",
        reference_type="connection",
        reference_id=connection_id,
        action_url=CONNECTION_REJECTED_URL,
    )


def list_notifications(
    db: Session,
    current_user: User,
    *,
    limit: int = 10,
    offset: int = 0,
    unread_only: bool = False,
) -> tuple[int, list[Notification]]:
    query = (
        db.query(Notification)
        .options(joinedload(Notification.actor).joinedload(User.profile).joinedload(Profile.profile_photo))
        .filter(Notification.recipient_id == current_user.id)
    )
    if unread_only:
        query = query.filter(Notification.is_read == False)  # noqa: E712
    total = query.count()
    notifications = (
        query.order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return total, notifications


def unread_count(db: Session, current_user: User) -> int:
    return (
        db.query(func.count(Notification.id))
        .filter(Notification.recipient_id == current_user.id, Notification.is_read == False)  # noqa: E712
        .scalar()
        or 0
    )


def mark_notification_read(db: Session, current_user: User, notification_id: str) -> int:
    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.recipient_id == current_user.id)
        .first()
    )
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")
    if notification.is_read:
        return 0
    notification.is_read = True
    db.commit()
    return 1


def mark_all_read(db: Session, current_user: User) -> int:
    updated = (
        db.query(Notification)
        .filter(Notification.recipient_id == current_user.id, Notification.is_read == False)  # noqa: E712
        .update({"is_read": True}, synchronize_session="fetch")
    )
    db.commit()
    return updated
