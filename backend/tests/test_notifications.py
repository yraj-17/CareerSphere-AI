import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import or_

from app.core.security import create_access_token, hash_password
from app.db.models import Connection, MediaObject, Notification, User
from app.db.session import Base, SessionLocal, engine
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_state():
    Base.metadata.create_all(bind=engine)
    yield
    db = SessionLocal()
    try:
        users = (
            db.query(User)
            .filter(or_(User.email.like("%@notifications.example.com"), User.username.like("notif_%")))
            .all()
        )
        ids = [user.id for user in users]
        if ids:
            db.query(Notification).filter(
                (Notification.recipient_id.in_(ids)) | (Notification.actor_id.in_(ids))
            ).delete(synchronize_session=False)
            db.query(Connection).filter(
                (Connection.requester_id.in_(ids)) | (Connection.receiver_id.in_(ids))
            ).delete(synchronize_session=False)
            db.query(MediaObject).filter(MediaObject.user_id.in_(ids)).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(ids)).delete(synchronize_session=False)
            db.commit()
    finally:
        db.close()


def _create_user(tag: str, first_name: str = "Test", last_name: str = "User") -> dict:
    uid = uuid.uuid4().hex[:8]
    username = f"notif_{tag}_{uid}"[:30]
    db = SessionLocal()
    try:
        user = User(
            first_name=first_name,
            last_name=last_name,
            username=username,
            email=f"{username}@notifications.example.com",
            password_hash=hash_password("Password123"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_access_token(subject=user.id)
        return {
            "id": user.id,
            "username": username,
            "headers": {"Authorization": f"Bearer {token}"},
        }
    finally:
        db.close()


def test_connection_request_creates_recipient_notification_and_isolated_from_sender():
    requester = _create_user("requester", "Raj", "Yadav")
    receiver = _create_user("receiver", "Priya", "Sharma")

    res = client.post(f"/api/networking/connections/{receiver['id']}", headers=requester["headers"])
    assert res.status_code == 201, res.text
    connection_id = res.json()["id"]

    receiver_notifications = client.get("/api/notifications", headers=receiver["headers"])
    assert receiver_notifications.status_code == 200
    data = receiver_notifications.json()
    assert data["total"] == 1
    notification = data["notifications"][0]
    assert notification["type"] == "CONNECTION_REQUEST"
    assert notification["reference_id"] == connection_id
    assert notification["actor"]["id"] == requester["id"]
    assert "sent you a connection request" in notification["message"]
    assert notification["action_url"] == "/dashboard/networking/my-network?tab=requests"

    sender_notifications = client.get("/api/notifications", headers=requester["headers"])
    assert sender_notifications.status_code == 200
    assert sender_notifications.json()["total"] == 0


def test_failed_duplicate_connection_request_does_not_create_duplicate_notification():
    requester = _create_user("dupe_requester")
    receiver = _create_user("dupe_receiver")

    first = client.post(f"/api/networking/connections/{receiver['id']}", headers=requester["headers"])
    assert first.status_code == 201
    duplicate = client.post(f"/api/networking/connections/{receiver['id']}", headers=requester["headers"])
    assert duplicate.status_code == 409

    unread = client.get("/api/notifications/unread-count", headers=receiver["headers"])
    assert unread.status_code == 200
    assert unread.json()["unread_count"] == 1


def test_accept_and_reject_create_requester_notifications():
    requester = _create_user("accept_requester", "Raj", "Yadav")
    receiver = _create_user("accept_receiver", "Priya", "Sharma")
    request = client.post(f"/api/networking/connections/{receiver['id']}", headers=requester["headers"])
    connection_id = request.json()["id"]

    accepted = client.post(f"/api/networking/requests/{connection_id}/accept", headers=receiver["headers"])
    assert accepted.status_code == 200

    requester_notifications = client.get("/api/notifications", headers=requester["headers"])
    assert requester_notifications.status_code == 200
    accepted_notification = requester_notifications.json()["notifications"][0]
    assert accepted_notification["type"] == "CONNECTION_ACCEPTED"
    assert accepted_notification["reference_id"] == connection_id
    assert "accepted your connection request" in accepted_notification["message"]

    requester_2 = _create_user("reject_requester", "Asha", "Rao")
    receiver_2 = _create_user("reject_receiver", "Neel", "Mehta")
    request_2 = client.post(f"/api/networking/connections/{receiver_2['id']}", headers=requester_2["headers"])
    connection_id_2 = request_2.json()["id"]

    rejected = client.post(f"/api/networking/requests/{connection_id_2}/reject", headers=receiver_2["headers"])
    assert rejected.status_code == 200

    rejected_notifications = client.get("/api/notifications", headers=requester_2["headers"])
    assert rejected_notifications.status_code == 200
    rejected_notification = rejected_notifications.json()["notifications"][0]
    assert rejected_notification["type"] == "CONNECTION_REJECTED"
    assert rejected_notification["reference_id"] == connection_id_2
    assert "declined your connection request" in rejected_notification["message"]


def test_notification_api_pagination_and_mark_read_behaviour():
    requester = _create_user("pager_requester")
    receiver = _create_user("pager_receiver")
    for _ in range(3):
        other = _create_user(f"actor_{uuid.uuid4().hex[:4]}")
        client.post(f"/api/networking/connections/{receiver['id']}", headers=other["headers"])

    page = client.get("/api/notifications", params={"limit": 2, "offset": 0}, headers=receiver["headers"])
    assert page.status_code == 200
    assert page.json()["total"] == 3
    assert len(page.json()["notifications"]) == 2

    unread = client.get("/api/notifications/unread-count", headers=receiver["headers"])
    assert unread.json()["unread_count"] == 3

    notification_id = page.json()["notifications"][0]["id"]
    mark_one = client.patch(f"/api/notifications/{notification_id}/read", headers=receiver["headers"])
    assert mark_one.status_code == 200
    assert mark_one.json()["updated"] == 1
    unread_after_one = client.get("/api/notifications/unread-count", headers=receiver["headers"])
    assert unread_after_one.json()["unread_count"] == 2

    forbidden_mark = client.patch(f"/api/notifications/{notification_id}/read", headers=requester["headers"])
    assert forbidden_mark.status_code == 404

    mark_all = client.patch("/api/notifications/read-all", headers=receiver["headers"])
    assert mark_all.status_code == 200
    assert mark_all.json()["updated"] == 2
    unread_after_all = client.get("/api/notifications/unread-count", headers=receiver["headers"])
    assert unread_after_all.json()["unread_count"] == 0
