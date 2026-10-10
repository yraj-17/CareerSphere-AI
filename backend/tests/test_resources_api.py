from __future__ import annotations

import hashlib
import json
import uuid
from typing import Optional

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.models import Resource, SavedResource, User
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
    email = f"resource_{tag}@example.com"
    username = f"res_{tag}"[:30]
    res = client.post(
        "/api/auth/register",
        json={
            "first_name": "Resource",
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


def _resource_payload(**overrides) -> dict:
    payload = {
        "title": "FastAPI Production Guide",
        "description": "A practical guide to FastAPI deployment and testing.",
        "url": "https://example.com/fastapi-guide",
        "resource_type": "ARTICLE",
        "category": "backend",
        "tags": ["FastAPI", " python ", "FASTAPI", ""],
    }
    payload.update(overrides)
    return payload


def _create_resource(user: dict, **overrides) -> dict:
    res = client.post("/api/resources", json=_resource_payload(**overrides), headers=user["headers"])
    assert res.status_code == 201, res.text
    return res.json()


def test_create_resource_normalizes_tags_and_uses_authenticated_author():
    user = _register_user()
    try:
        resource = _create_resource(user)
        assert resource["author_id"] == user["id"]
        assert resource["author"]["username"] == user["username"]
        assert resource["tags"] == ["FastAPI", "python"]
        assert resource["source_domain"] == "example.com"
        assert resource["resource_type"] == "ARTICLE"
        assert resource["is_owner"] is True
        assert resource["is_saved"] is False
    finally:
        _cleanup_users(user["email"])


def test_resource_create_validation_and_authorization():
    user = _register_user()
    try:
        unauth = client.post("/api/resources", json=_resource_payload())
        assert unauth.status_code == 401

        bad_url = client.post(
            "/api/resources",
            json=_resource_payload(url="not-a-url"),
            headers=user["headers"],
        )
        assert bad_url.status_code == 422

        bad_type = client.post(
            "/api/resources",
            json=_resource_payload(resource_type="PODCAST"),
            headers=user["headers"],
        )
        assert bad_type.status_code == 422

        too_many_tags = client.post(
            "/api/resources",
            json=_resource_payload(tags=[f"tag{i}" for i in range(10)]),
            headers=user["headers"],
        )
        assert too_many_tags.status_code == 422
    finally:
        _cleanup_users(user["email"])


def test_list_resources_supports_pagination_search_type_category_and_tag_filters():
    user = _register_user()
    try:
        r1 = _create_resource(
            user,
            title="React Hooks Tutorial",
            description="Learn useEffect and useMemo.",
            url="https://react.dev/learn",
            resource_type="TUTORIAL",
            category="frontend",
            tags=["React", "JavaScript"],
        )
        _create_resource(
            user,
            title="Kubernetes Course",
            description="Cloud native operations.",
            url="https://example.com/kubernetes",
            resource_type="COURSE",
            category="cloud",
            tags=["Kubernetes", "DevOps"],
        )

        page = client.get("/api/resources", params={"limit": 1, "offset": 0}, headers=user["headers"])
        assert page.status_code == 200
        assert page.json()["limit"] == 1
        assert page.json()["total"] >= 2
        assert len(page.json()["resources"]) == 1

        search = client.get("/api/resources", params={"q": "hooks"}, headers=user["headers"])
        assert search.status_code == 200
        assert [item["id"] for item in search.json()["resources"]] == [r1["id"]]

        by_type = client.get("/api/resources", params={"resource_type": "TUTORIAL"}, headers=user["headers"])
        assert by_type.status_code == 200
        assert all(item["resource_type"] == "TUTORIAL" for item in by_type.json()["resources"])

        by_category = client.get("/api/resources", params={"category": "frontend"}, headers=user["headers"])
        assert by_category.status_code == 200
        assert [item["id"] for item in by_category.json()["resources"]] == [r1["id"]]

        by_tag = client.get("/api/resources", params={"tag": "react"}, headers=user["headers"])
        assert by_tag.status_code == 200
        assert [item["id"] for item in by_tag.json()["resources"]] == [r1["id"]]
    finally:
        _cleanup_users(user["email"])


def test_resource_detail_save_duplicate_unsave_and_saved_resources_list():
    owner = _register_user("owner_" + _unique_tag())
    viewer = _register_user("viewer_" + _unique_tag())
    try:
        resource = _create_resource(owner, title="Python Docs", resource_type="DOCUMENTATION", tags=["Python"])

        detail = client.get(f"/api/resources/{resource['id']}", headers=viewer["headers"])
        assert detail.status_code == 200
        assert detail.json()["is_saved"] is False
        assert detail.json()["is_owner"] is False

        save_1 = client.post(f"/api/resources/{resource['id']}/save", headers=viewer["headers"])
        save_2 = client.post(f"/api/resources/{resource['id']}/save", headers=viewer["headers"])
        assert save_1.status_code == 200
        assert save_2.status_code == 200
        assert save_2.json()["is_saved"] is True

        saved = client.get("/api/resources", params={"saved": True}, headers=viewer["headers"])
        assert saved.status_code == 200
        assert [item["id"] for item in saved.json()["resources"]] == [resource["id"]]
        assert saved.json()["resources"][0]["is_saved"] is True

        detail_saved = client.get(f"/api/resources/{resource['id']}", headers=viewer["headers"])
        assert detail_saved.json()["is_saved"] is True
        assert detail_saved.json()["save_count"] == 1

        unsave = client.delete(f"/api/resources/{resource['id']}/save", headers=viewer["headers"])
        assert unsave.status_code == 200
        assert unsave.json()["is_saved"] is False

        empty_saved = client.get("/api/resources", params={"saved": True}, headers=viewer["headers"])
        assert empty_saved.status_code == 200
        assert empty_saved.json()["resources"] == []
    finally:
        _cleanup_users(owner["email"], viewer["email"])


def test_owner_can_edit_resource_and_other_users_cannot():
    owner = _register_user("edit_owner_" + _unique_tag())
    other = _register_user("edit_other_" + _unique_tag())
    try:
        resource = _create_resource(owner)

        forbidden = client.patch(
            f"/api/resources/{resource['id']}",
            json={"title": "Stolen edit"},
            headers=other["headers"],
        )
        assert forbidden.status_code == 403

        edited = client.patch(
            f"/api/resources/{resource['id']}",
            json={
                "title": "Updated FastAPI Guide",
                "url": "https://docs.example.com/fastapi",
                "resource_type": "DOCUMENTATION",
                "category": "backend-docs",
                "tags": ["Docs", "docs", "FastAPI"],
            },
            headers=owner["headers"],
        )
        assert edited.status_code == 200
        payload = edited.json()
        assert payload["title"] == "Updated FastAPI Guide"
        assert payload["resource_type"] == "DOCUMENTATION"
        assert payload["category"] == "backend-docs"
        assert payload["tags"] == ["Docs", "FastAPI"]
        assert payload["source_domain"] == "docs.example.com"
    finally:
        _cleanup_users(owner["email"], other["email"])


def test_owner_can_delete_resource_and_other_users_cannot():
    owner = _register_user("delete_owner_" + _unique_tag())
    other = _register_user("delete_other_" + _unique_tag())
    try:
        resource = _create_resource(owner)
        client.post(f"/api/resources/{resource['id']}/save", headers=other["headers"])

        forbidden = client.delete(f"/api/resources/{resource['id']}", headers=other["headers"])
        assert forbidden.status_code == 403

        deleted = client.delete(f"/api/resources/{resource['id']}", headers=owner["headers"])
        assert deleted.status_code == 200
        assert deleted.json()["success"] is True

        missing = client.get(f"/api/resources/{resource['id']}", headers=owner["headers"])
        assert missing.status_code == 404

        db = SessionLocal()
        try:
            assert db.query(SavedResource).filter(SavedResource.resource_id == resource["id"]).count() == 0
        finally:
            db.close()
    finally:
        _cleanup_users(owner["email"], other["email"])


def test_resource_missing_paths_return_404():
    user = _register_user()
    missing_id = str(uuid.uuid4())
    try:
        assert client.get(f"/api/resources/{missing_id}", headers=user["headers"]).status_code == 404
        assert client.post(f"/api/resources/{missing_id}/save", headers=user["headers"]).status_code == 404
        assert client.delete(f"/api/resources/{missing_id}/save", headers=user["headers"]).status_code == 404
        assert client.patch(f"/api/resources/{missing_id}", json={"title": "Nope"}, headers=user["headers"]).status_code == 404
        assert client.delete(f"/api/resources/{missing_id}", headers=user["headers"]).status_code == 404
    finally:
        _cleanup_users(user["email"])
