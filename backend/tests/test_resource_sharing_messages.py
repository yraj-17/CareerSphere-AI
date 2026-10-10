from __future__ import annotations

import hashlib
import json
import uuid
from typing import Optional

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.models import Connection, ConnectionStatus, DirectMessage, Resource, SavedResource, User
from app.db.redis_client import redis_client
from app.db.session import SessionLocal
from app.main import app


client = TestClient(app)

_USER_COUNTER = 0


def _unique_tag() -> str:
    global _USER_COUNTER
    _USER_COUNTER += 1
    return f"{_USER_COUNTER}_{uuid.uuid4().hex[:6]}"


def _seed_verified_email(email: str) -> str:
    token = f"test-token-{uuid.uuid4().hex}"
    token_hash = hashlib.sha256(f"{email}:{token}:{settings.SECRET_KEY}".encode()).hexdigest()
    redis_client.set(
        f"otp:{email}",
        json.dumps({"otp": "123456", "verified_token": token_hash, "token_raw": token}),
        ex=600,
    )
    return token


def _register_user(tag: Optional[str] = None) -> dict:
    if tag is None:
        tag = _unique_tag()
    email = f"share_{tag}@example.com"
    username = f"share_{tag}"[:30]
    res = client.post(
        "/api/auth/register",
        json={
            "first_name": "Share",
            "last_name": "User",
            "username": username,
            "email": email,
            "password": "Password123",
            "email_verification_token": _seed_verified_email(email),
        },
    )
    assert res.status_code == 201, res.text
    user_id = res.json()["id"]
    login = client.post("/api/auth/login", json={"identifier": username, "password": "Password123"})
    assert login.status_code == 200, login.text
    return {
        "id": user_id,
        "username": username,
        "email": email,
        "headers": {"Authorization": f"Bearer {login.json()['access_token']}"},
    }


def _cleanup_users(*emails: str) -> None:
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.email.in_(emails)).all()
        ids = [user.id for user in users]
        if ids:
            resource_ids = [row.id for row in db.query(Resource.id).filter(Resource.author_id.in_(ids)).all()]
            db.query(SavedResource).filter(SavedResource.user_id.in_(ids)).delete(synchronize_session=False)
            if resource_ids:
                db.query(SavedResource).filter(SavedResource.resource_id.in_(resource_ids)).delete(synchronize_session=False)
                db.query(Resource).filter(Resource.id.in_(resource_ids)).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _create_resource(user: dict, **overrides) -> dict:
    payload = {
        "title": "Kubernetes Documentation",
        "description": "Learn Kubernetes from the official documentation.",
        "url": "https://kubernetes.io/docs/home/",
        "resource_type": "DOCUMENTATION",
        "category": "cloud_devops",
        "tags": ["Kubernetes", "Docker", "DevOps"],
    }
    payload.update(overrides)
    res = client.post("/api/resources", json=payload, headers=user["headers"])
    assert res.status_code == 201, res.text
    return res.json()


def _connect(a: dict, b: dict) -> str:
    req = client.post(f"/api/networking/connections/{b['id']}", headers=a["headers"])
    assert req.status_code == 201, req.text
    connection_id = req.json()["id"]
    accepted = client.post(f"/api/networking/requests/{connection_id}/accept", headers=b["headers"])
    assert accepted.status_code == 200, accepted.text
    return connection_id


def _conversation(sender: dict, recipient: dict) -> str:
    res = client.post(f"/api/messaging/conversations/{recipient['id']}", headers=sender["headers"])
    assert res.status_code == 200, res.text
    return res.json()["id"]


def _share(sender: dict, conversation_id: str, resource_id: str, message: str = "Check this out", **extra) -> dict:
    payload = {"resource_id": resource_id, "message": message}
    payload.update(extra)
    res = client.post(
        f"/api/messaging/conversations/{conversation_id}/resource-share",
        json=payload,
        headers=sender["headers"],
    )
    assert res.status_code == 201, res.text
    return res.json()


def test_share_own_resource_with_accepted_connection_persists_message_and_reference():
    sender = _register_user("sender_" + _unique_tag())
    recipient = _register_user("recipient_" + _unique_tag())
    try:
        _connect(sender, recipient)
        resource = _create_resource(sender)
        conv_id = _conversation(sender, recipient)

        msg = _share(sender, conv_id, resource["id"], message="Check this out for Kubernetes.", sender_id=recipient["id"])
        assert msg["sender_id"] == sender["id"]
        assert msg["message_type"] == "RESOURCE_SHARE"
        assert msg["content"] == "Check this out for Kubernetes."
        assert msg["resource_id"] == resource["id"]
        assert msg["resource"]["title"] == "Kubernetes Documentation"

        history = client.get(f"/api/messaging/conversations/{conv_id}/messages", headers=recipient["headers"])
        assert history.status_code == 200
        assert history.json()["messages"][0]["resource"]["id"] == resource["id"]

        db = SessionLocal()
        try:
            row = db.query(DirectMessage).filter(DirectMessage.id == msg["id"]).first()
            assert row is not None
            assert row.message_type == "RESOURCE_SHARE"
            assert row.resource_id == resource["id"]
        finally:
            db.close()
    finally:
        _cleanup_users(sender["email"], recipient["email"])


def test_share_another_users_public_resource_with_accepted_connection():
    owner = _register_user("owner_" + _unique_tag())
    sender = _register_user("sender_public_" + _unique_tag())
    recipient = _register_user("recipient_public_" + _unique_tag())
    try:
        _connect(sender, recipient)
        resource = _create_resource(owner, title="React Docs", url="https://react.dev", tags=["React"])
        conv_id = _conversation(sender, recipient)

        msg = _share(sender, conv_id, resource["id"], message="")
        assert msg["message_type"] == "RESOURCE_SHARE"
        assert msg["content"] == ""
        assert msg["resource"]["id"] == resource["id"]
        assert msg["resource"]["title"] == "React Docs"
    finally:
        _cleanup_users(owner["email"], sender["email"], recipient["email"])


def test_resource_share_rejects_non_participant_conversation_access():
    sender = _register_user("sender_np_" + _unique_tag())
    recipient = _register_user("recipient_np_" + _unique_tag())
    intruder = _register_user("intruder_np_" + _unique_tag())
    try:
        _connect(sender, recipient)
        resource = _create_resource(sender)
        conv_id = _conversation(sender, recipient)

        res = client.post(
            f"/api/messaging/conversations/{conv_id}/resource-share",
            json={"resource_id": resource["id"], "message": "forged"},
            headers=intruder["headers"],
        )
        assert res.status_code == 403
    finally:
        _cleanup_users(sender["email"], recipient["email"], intruder["email"])


def test_resource_share_rejects_non_connection_pending_and_rejected_states():
    sender = _register_user("sender_state_" + _unique_tag())
    recipient = _register_user("recipient_state_" + _unique_tag())
    try:
        connection_id = _connect(sender, recipient)
        resource = _create_resource(sender)
        conv_id = _conversation(sender, recipient)

        db = SessionLocal()
        try:
            conn = db.query(Connection).filter(Connection.id == connection_id).first()
            conn.status = ConnectionStatus.pending
            db.commit()
        finally:
            db.close()

        pending = client.post(
            f"/api/messaging/conversations/{conv_id}/resource-share",
            json={"resource_id": resource["id"], "message": "pending"},
            headers=sender["headers"],
        )
        assert pending.status_code == 403

        db = SessionLocal()
        try:
            conn = db.query(Connection).filter(Connection.id == connection_id).first()
            conn.status = ConnectionStatus.rejected
            db.commit()
        finally:
            db.close()

        rejected = client.post(
            f"/api/messaging/conversations/{conv_id}/resource-share",
            json={"resource_id": resource["id"], "message": "rejected"},
            headers=sender["headers"],
        )
        assert rejected.status_code == 403

        db = SessionLocal()
        try:
            db.query(Connection).filter(Connection.id == connection_id).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

        non_connection = client.post(
            f"/api/messaging/conversations/{conv_id}/resource-share",
            json={"resource_id": resource["id"], "message": "none"},
            headers=sender["headers"],
        )
        assert non_connection.status_code == 403
    finally:
        _cleanup_users(sender["email"], recipient["email"])


def test_resource_share_rejects_nonexistent_resource_and_normal_messages_still_work():
    sender = _register_user("sender_missing_" + _unique_tag())
    recipient = _register_user("recipient_missing_" + _unique_tag())
    try:
        _connect(sender, recipient)
        conv_id = _conversation(sender, recipient)
        missing = str(uuid.uuid4())

        res = client.post(
            f"/api/messaging/conversations/{conv_id}/resource-share",
            json={"resource_id": missing, "message": "missing"},
            headers=sender["headers"],
        )
        assert res.status_code == 404

        normal = client.post(
            f"/api/messaging/conversations/{conv_id}/messages",
            json={"content": "Normal message still works"},
            headers=sender["headers"],
        )
        assert normal.status_code == 201
        assert normal.json()["message_type"] == "TEXT"
        assert normal.json()["resource"] is None
    finally:
        _cleanup_users(sender["email"], recipient["email"])


def test_deleted_resource_share_message_renders_safe_fallback_payload():
    sender = _register_user("sender_deleted_" + _unique_tag())
    recipient = _register_user("recipient_deleted_" + _unique_tag())
    try:
        _connect(sender, recipient)
        resource = _create_resource(sender)
        conv_id = _conversation(sender, recipient)
        msg = _share(sender, conv_id, resource["id"], message="Useful while it lasts")

        deleted = client.delete(f"/api/resources/{resource['id']}", headers=sender["headers"])
        assert deleted.status_code == 200

        history = client.get(f"/api/messaging/conversations/{conv_id}/messages", headers=recipient["headers"])
        assert history.status_code == 200
        shared = next(item for item in history.json()["messages"] if item["id"] == msg["id"])
        assert shared["message_type"] == "RESOURCE_SHARE"
        assert shared["resource"] is None
    finally:
        _cleanup_users(sender["email"], recipient["email"])
