"""
Auth API tests against PostgreSQL + Redis (no SQLite).

Requires Docker infrastructure:
  docker compose up -d postgres redis
and a valid DATABASE_URL / REDIS_URL in the environment or .env.
"""
import json
import hashlib
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import or_

from app.main import app
from app.db.session import SessionLocal, Base, engine
from app.db.models import User, Profile, MediaObject, Conversation, ChatMessage
from app.db.redis_client import redis_client
from app.core.config import settings
from app.core.security import create_access_token, hash_password

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_state():
    """Ensure tables exist and remove leftover test users / related media."""
    Base.metadata.create_all(bind=engine)
    yield
    db = SessionLocal()
    try:
        test_users = (
            db.query(User)
            .filter(or_(User.email.like("%@example.com"), User.username.like("test_%")))
            .all()
        )
        test_ids = [u.id for u in test_users]
        if test_ids:
            conv_ids = [
                row.id
                for row in db.query(Conversation).filter(Conversation.user_id.in_(test_ids)).all()
            ]
            if conv_ids:
                db.query(ChatMessage).filter(ChatMessage.conversation_id.in_(conv_ids)).delete(
                    synchronize_session=False
                )
                db.query(Conversation).filter(Conversation.id.in_(conv_ids)).delete(
                    synchronize_session=False
                )
            db.query(MediaObject).filter(MediaObject.user_id.in_(test_ids)).delete(
                synchronize_session=False
            )
            db.query(User).filter(User.id.in_(test_ids)).delete(synchronize_session=False)
            db.commit()
    finally:
        db.close()


def _seed_verified_email(email: str) -> str:
    """Put a verified OTP record in Redis and return the verification token."""
    token = f"test-token-{uuid.uuid4().hex}"
    token_hash = hashlib.sha256(
        f"{email}:{token}:{settings.SECRET_KEY}".encode()
    ).hexdigest()
    payload = json.dumps({"otp": "123456", "verified_token": token_hash, "token_raw": token})
    redis_client.set(f"otp:{email}", payload, ex=600)
    return token


def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded")
    assert data["postgres"] == "connected"
    assert data["redis"] == "connected"
    assert "CareerSphere AI" in data["service"]


def test_check_username_availability():
    res = client.get("/api/auth/check-username", params={"username": "test_available_user"})
    assert res.status_code == 200
    assert res.json()["available"] is True

    res = client.get("/api/auth/check-username", params={"username": "raj yadav"})
    assert res.status_code == 200
    assert res.json()["available"] is False
    assert "spaces" in res.json()["message"]

    res = client.get("/api/auth/check-username", params={"username": "ab"})
    assert res.status_code == 200
    assert res.json()["available"] is False


def test_register_validation_rules():
    res = client.post("/api/auth/register", json={
        "first_name": "  ",
        "last_name": "Yadav",
        "username": "test_raj123",
        "email": "test_val1@example.com",
        "password": "Password123",
        "email_verification_token": "dummy",
    })
    assert res.status_code == 422

    res = client.post("/api/auth/register", json={
        "first_name": "Raj",
        "last_name": "Yadav",
        "username": "raj yadav",
        "email": "test_val2@example.com",
        "password": "Password123",
        "email_verification_token": "dummy",
    })
    assert res.status_code == 422

    res = client.post("/api/auth/register", json={
        "first_name": "Raj",
        "last_name": "Yadav",
        "username": "test_raj123",
        "email": "test_val3@example.com",
        "password": "Pass1",
        "email_verification_token": "dummy",
    })
    assert res.status_code == 422


def test_register_and_login_flow():
    email = "test_raj@example.com"
    username = "test_raj_yadav"
    verification_token = _seed_verified_email(email)

    signup_data = {
        "first_name": "Raj",
        "last_name": "Yadav",
        "username": username,
        "email": email,
        "password": "Password123",
        "email_verification_token": verification_token,
    }
    reg_res = client.post("/api/auth/register", json=signup_data)
    assert reg_res.status_code == 201, reg_res.text
    user = reg_res.json()
    assert user["username"] == username
    assert user["email"] == email
    assert "password_hash" not in user

    check_res = client.get("/api/auth/check-username", params={"username": username})
    assert check_res.status_code == 200
    assert check_res.json()["available"] is False

    dup_user_res = client.post("/api/auth/register", json={
        "first_name": "Raj",
        "last_name": "Kumar",
        "username": username,
        "email": "test_different@example.com",
        "password": "Password123",
        "email_verification_token": _seed_verified_email("test_different@example.com"),
    })
    assert dup_user_res.status_code == 409

    dup_email_res = client.post("/api/auth/register", json={
        "first_name": "Raj",
        "last_name": "Kumar",
        "username": "test_raj_other",
        "email": email,
        "password": "Password123",
        "email_verification_token": _seed_verified_email(email),
    })
    assert dup_email_res.status_code in (400, 409)

    login_user_res = client.post("/api/auth/login", json={
        "identifier": username,
        "password": "Password123",
    })
    assert login_user_res.status_code == 200
    token_data = login_user_res.json()
    assert token_data["token_type"] == "bearer"
    token = token_data["access_token"]

    login_email_res = client.post("/api/auth/login", json={
        "identifier": email,
        "password": "Password123",
    })
    assert login_email_res.status_code == 200

    wrong_pwd_res = client.post("/api/auth/login", json={
        "identifier": username,
        "password": "WrongPassword123",
    })
    assert wrong_pwd_res.status_code == 401

    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["username"] == username

    unauth_res = client.get("/api/auth/me")
    assert unauth_res.status_code == 401

    logout_res = client.post("/api/auth/logout")
    assert logout_res.status_code == 200


def test_auth_responses_include_profile_photo_url_without_sensitive_fields(monkeypatch):
    monkeypatch.setattr("app.api.auth.presigned_get_url", lambda object_key: f"https://cdn.example.com/{object_key}")

    email = "test_avatar@example.com"
    username = "test_avatar_user"
    verification_token = _seed_verified_email(email)

    reg_res = client.post("/api/auth/register", json={
        "first_name": "Raj",
        "last_name": "Yadav",
        "username": username,
        "email": email,
        "password": "Password123",
        "email_verification_token": verification_token,
    })
    assert reg_res.status_code == 201, reg_res.text
    user_id = reg_res.json()["id"]

    db = SessionLocal()
    try:
        media = MediaObject(
            user_id=user_id,
            object_key="profiles/test-avatar.png",
            filename="avatar.png",
            content_type="image/png",
            size_bytes=128,
            purpose="profile_image",
        )
        db.add(media)
        db.flush()
        db.add(Profile(user_id=user_id, profile_photo_media_id=media.id))
        db.commit()
    finally:
        db.close()

    login_res = client.post("/api/auth/login", json={
        "identifier": username,
        "password": "Password123",
    })
    assert login_res.status_code == 200
    login_user = login_res.json()["user"]
    assert login_user["profile_photo_url"] == "https://cdn.example.com/profiles/test-avatar.png"
    assert "password_hash" not in login_user
    assert "profile_photo_media_id" not in login_user

    token = login_res.json()["access_token"]
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_user = me_res.json()
    assert me_user["profile_photo_url"] == "https://cdn.example.com/profiles/test-avatar.png"
    assert "password_hash" not in me_user
    assert "profile_photo_media_id" not in me_user


def test_authenticated_account_update_normalizes_username_and_changes_password():
    db = SessionLocal()
    try:
        user = User(
            first_name="Account",
            last_name="Owner",
            username="test_account_owner",
            email="test_account_owner@example.com",
            password_hash=hash_password("Password123"),
        )
        duplicate = User(
            first_name="Other",
            last_name="User",
            username="test_account_taken",
            email="test_account_taken@example.com",
            password_hash=hash_password("Password123"),
        )
        db.add_all([user, duplicate])
        db.commit()
        db.refresh(user)
    finally:
        db.close()

    headers = {"Authorization": f"Bearer {create_access_token(subject=user.id)}"}

    updated = client.patch(
        "/api/auth/me",
        headers=headers,
        json={"first_name": "Updated", "last_name": "Owner", "username": "  Updated.Owner  "},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["id"] == user.id
    assert updated.json()["username"] == "updated.owner"
    assert updated.json()["first_name"] == "Updated"

    duplicate_response = client.patch(
        "/api/auth/me",
        headers=headers,
        json={"username": "TEST_ACCOUNT_TAKEN"},
    )
    assert duplicate_response.status_code == 409

    invalid_response = client.patch(
        "/api/auth/me",
        headers=headers,
        json={"username": "bad username"},
    )
    assert invalid_response.status_code == 422

    wrong_password = client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"current_password": "WrongPassword123", "new_password": "NewPassword456"},
    )
    assert wrong_password.status_code == 400

    changed = client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"current_password": "Password123", "new_password": "NewPassword456"},
    )
    assert changed.status_code == 200, changed.text

    login = client.post(
        "/api/auth/login",
        json={"identifier": "updated.owner", "password": "NewPassword456"},
    )
    assert login.status_code == 200, login.text


def test_media_upload_requires_auth():
    res = client.post(
        "/api/media/upload",
        data={"purpose": "resume"},
        files={"file": ("resume.txt", b"hello resume", "text/plain")},
    )
    assert res.status_code == 401
