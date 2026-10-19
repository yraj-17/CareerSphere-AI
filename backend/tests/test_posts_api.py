from __future__ import annotations

import hashlib
import json
import uuid

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.models import GlobalPost, User
from app.db.redis_client import redis_client
from app.db.session import SessionLocal
from app.main import app


client = TestClient(app)


def _register_user(label: str) -> dict:
    email = f"post_{label}_{uuid.uuid4().hex[:8]}@example.com"
    username = f"post_{label}_{uuid.uuid4().hex[:6]}"
    token = f"verified-{uuid.uuid4().hex}"
    token_hash = hashlib.sha256(f"{email}:{token}:{settings.SECRET_KEY}".encode()).hexdigest()
    redis_client.set(
        f"otp:{email}",
        json.dumps({"otp": "123456", "verified_token": token_hash, "token_raw": token}),
        ex=600,
    )
    registered = client.post(
        "/api/auth/register",
        json={
            "first_name": label.title(),
            "last_name": "Tester",
            "username": username,
            "email": email,
            "password": "Password123",
            "email_verification_token": token,
        },
    )
    assert registered.status_code == 201, registered.text
    login = client.post("/api/auth/login", json={"identifier": username, "password": "Password123"})
    assert login.status_code == 200, login.text
    return {"email": email, "id": registered.json()["id"], "headers": {"Authorization": f"Bearer {login.json()['access_token']}"}}


def _cleanup(*emails: str) -> None:
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.email.in_(emails)).all()
        ids = [user.id for user in users]
        if ids:
            db.query(GlobalPost).filter(GlobalPost.author_id.in_(ids)).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_global_post_feed_ownership_likes_and_comments():
    owner = _register_user("owner")
    viewer = _register_user("viewer")
    try:
        unauthenticated = client.get("/api/posts")
        assert unauthenticated.status_code == 401

        invalid = client.post("/api/posts", json={"content": "   "}, headers=owner["headers"])
        assert invalid.status_code == 422

        created = client.post(
            "/api/posts",
            json={"content": "Shipping a focused Home feed today."},
            headers=owner["headers"],
        )
        assert created.status_code == 201, created.text
        post = created.json()
        assert post["author"]["id"] == owner["id"]
        assert post["is_owner"] is True
        assert post["like_count"] == 0
        assert post["comment_count"] == 0

        feed = client.get("/api/posts", params={"limit": 1}, headers=viewer["headers"])
        assert feed.status_code == 200
        assert feed.json()["posts"][0]["id"] == post["id"]
        assert feed.json()["posts"][0]["author"]["username"]

        forbidden_edit = client.patch(
            f"/api/posts/{post['id']}",
            json={"content": "Not the owner's update."},
            headers=viewer["headers"],
        )
        assert forbidden_edit.status_code == 403

        liked = client.post(f"/api/posts/{post['id']}/like", headers=viewer["headers"])
        duplicate_like = client.post(f"/api/posts/{post['id']}/like", headers=viewer["headers"])
        assert liked.status_code == duplicate_like.status_code == 200
        assert duplicate_like.json()["like_count"] == 1
        assert duplicate_like.json()["liked_by_me"] is True

        comment = client.post(
            f"/api/posts/{post['id']}/comments",
            json={"content": "Useful update."},
            headers=viewer["headers"],
        )
        assert comment.status_code == 201
        comment_id = comment.json()["id"]
        edited_comment = client.patch(
            f"/api/posts/comments/{comment_id}",
            json={"content": "Thoughtful update."},
            headers=viewer["headers"],
        )
        assert edited_comment.status_code == 200
        assert edited_comment.json()["content"] == "Thoughtful update."

        owner_edit = client.patch(
            f"/api/posts/{post['id']}",
            json={"content": "Updated by the owner."},
            headers=owner["headers"],
        )
        assert owner_edit.status_code == 200
        assert owner_edit.json()["content"] == "Updated by the owner."

        unlike = client.delete(f"/api/posts/{post['id']}/like", headers=viewer["headers"])
        assert unlike.status_code == 200
        assert unlike.json()["like_count"] == 0

        owner_can_moderate = client.delete(f"/api/posts/comments/{comment_id}", headers=owner["headers"])
        assert owner_can_moderate.status_code == 204
        deleted = client.delete(f"/api/posts/{post['id']}", headers=viewer["headers"])
        assert deleted.status_code == 403
    finally:
        _cleanup(owner["email"], viewer["email"])
