"""
Communities V1 REST API tests.

These tests intentionally cover only the scoped V1 surface:
community discovery/create/detail, public/private visibility, join/leave,
members, and text posts. They do not exercise chat, realtime, Redis pub/sub,
AI, media, comments, likes, invitations, or moderation features.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.db.models import (
    Community,
    CommunityMembership,
    CommunityPost,
    CommunityPostComment,
    CommunityPostMedia,
    CommunityPostReaction,
    CommunityPostTag,
    Connection,
    User,
)
from app.db.redis_client import redis_client
from app.db.session import Base, SessionLocal, engine
from app.main import app

client = TestClient(app)

_USER_COUNTER = 0


def _unique_tag() -> str:
    global _USER_COUNTER
    _USER_COUNTER += 1
    return f"{_USER_COUNTER}_{uuid.uuid4().hex[:6]}"


def _seed_verified_email(email: str) -> str:
    token = f"test-token-{uuid.uuid4().hex}"
    token_hash = hashlib.sha256(
        f"{email}:{token}:{settings.SECRET_KEY}".encode()
    ).hexdigest()
    payload = json.dumps({"otp": "123456", "verified_token": token_hash, "token_raw": token})
    redis_client.set(f"otp:{email}", payload, ex=600)
    return token


def _register_user(tag: Optional[str] = None) -> dict:
    if tag is None:
        tag = _unique_tag()
    email = f"community_{tag}@example.com"
    username = f"comm_{tag}"[:30]
    res = client.post("/api/auth/register", json={
        "first_name": "Community",
        "last_name": "User",
        "username": username,
        "email": email,
        "password": "Password123",
        "email_verification_token": _seed_verified_email(email),
    })
    assert res.status_code == 201, f"Register failed: {res.text}"
    user_id = res.json()["id"]

    login = client.post("/api/auth/login", json={
        "identifier": username,
        "password": "Password123",
    })
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return {
        "user_id": user_id,
        "username": username,
        "email": email,
        "headers": {"Authorization": f"Bearer {token}"},
    }


def _cleanup_users(*emails: str) -> None:
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.email.in_(emails)).all()
        ids = [u.id for u in users]
        if ids:
            community_ids = [
                c.id
                for c in db.query(Community.id)
                .filter(Community.creator_id.in_(ids))
                .all()
            ]
            if community_ids:
                post_ids = [
                    p.id
                    for p in db.query(CommunityPost.id)
                    .filter(CommunityPost.community_id.in_(community_ids))
                    .all()
                ]
                if post_ids:
                    db.query(CommunityPostReaction).filter(
                        CommunityPostReaction.post_id.in_(post_ids)
                    ).delete(synchronize_session=False)
                    db.query(CommunityPostComment).filter(
                        CommunityPostComment.post_id.in_(post_ids)
                    ).delete(synchronize_session=False)
                db.query(CommunityPost).filter(
                    CommunityPost.community_id.in_(community_ids)
                ).delete(synchronize_session=False)
                db.query(CommunityMembership).filter(
                    CommunityMembership.community_id.in_(community_ids)
                ).delete(synchronize_session=False)
                db.query(Community).filter(
                    Community.id.in_(community_ids)
                ).delete(synchronize_session=False)

            db.query(CommunityPostReaction).filter(
                CommunityPostReaction.user_id.in_(ids)
            ).delete(synchronize_session=False)
            db.query(CommunityPostComment).filter(
                CommunityPostComment.author_id.in_(ids)
            ).delete(synchronize_session=False)
            user_post_ids = [
                p.id
                for p in db.query(CommunityPost.id)
                .filter(CommunityPost.author_id.in_(ids))
                .all()
            ]
            if user_post_ids:
                db.query(CommunityPostReaction).filter(
                    CommunityPostReaction.post_id.in_(user_post_ids)
                ).delete(synchronize_session=False)
                db.query(CommunityPostComment).filter(
                    CommunityPostComment.post_id.in_(user_post_ids)
                ).delete(synchronize_session=False)
                db.query(CommunityPost).filter(
                    CommunityPost.id.in_(user_post_ids)
                ).delete(synchronize_session=False)
            db.query(CommunityMembership).filter(
                CommunityMembership.user_id.in_(ids)
            ).delete(synchronize_session=False)
            db.query(Connection).filter(
                or_(Connection.requester_id.in_(ids), Connection.receiver_id.in_(ids))
            ).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(ids)).delete(synchronize_session=False)
            db.commit()
    finally:
        db.close()


def _community_payload(**overrides) -> dict:
    payload = {
        "name": f"AI Builders {uuid.uuid4().hex[:6]}",
        "description": "A focused group for practical AI engineers.",
        "category": "ai_ml",
        "tags": ["AI", "RAG"],
        "visibility": "public",
    }
    payload.update(overrides)
    return payload


def _create_community(user: dict, **overrides) -> dict:
    res = client.post(
        "/api/communities",
        json=_community_payload(**overrides),
        headers=user["headers"],
    )
    assert res.status_code == 201, res.text
    return res.json()


def _join(user: dict, community_id: str):
    return client.post(f"/api/communities/{community_id}/join", headers=user["headers"])


def _create_post(user: dict, community_id: str, content: str = "Community post", tags: list | None = None) -> dict:
    import json as _json
    data = {"content": content, "tags": _json.dumps(tags or [])}
    res = client.post(
        f"/api/communities/{community_id}/posts",
        data=data,
        headers=user["headers"],
    )
    assert res.status_code == 201, res.text
    return res.json()


def _add_membership(community_id: str, user_id: str, role: str = "member") -> None:
    db = SessionLocal()
    try:
        db.add(CommunityMembership(
            community_id=community_id,
            user_id=user_id,
            role=role,
        ))
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def ensure_tables():
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def user_a():
    u = _register_user()
    yield u
    _cleanup_users(u["email"])


@pytest.fixture()
def user_b():
    u = _register_user()
    yield u
    _cleanup_users(u["email"])


@pytest.fixture()
def user_c():
    u = _register_user()
    yield u
    _cleanup_users(u["email"])


def test_01_unauthenticated_list_rejected():
    assert client.get("/api/communities").status_code == 401


def test_02_unauthenticated_create_rejected():
    res = client.post("/api/communities", json=_community_payload())
    assert res.status_code == 401


def test_03_unauthenticated_join_rejected():
    res = client.post(f"/api/communities/{uuid.uuid4()}/join")
    assert res.status_code == 401


def test_04_unauthenticated_posts_rejected():
    assert client.get(f"/api/communities/{uuid.uuid4()}/posts").status_code == 401
    res = client.post(f"/api/communities/{uuid.uuid4()}/posts", json={"content": "Hi"})
    assert res.status_code == 401


def test_05_create_public_community_creates_owner_membership(user_a):
    community = _create_community(user_a, name="  Practical AI Guild  ")

    assert community["name"] == "Practical AI Guild"
    assert community["visibility"] == "public"
    assert community["creator_id"] == user_a["user_id"]
    assert community["joined"] is True
    assert community["is_joined"] is True
    assert community["is_owner"] is True
    assert community["membership_status"] == "joined"
    assert community["member_count"] == 1
    assert community["creator"]["id"] == user_a["user_id"]
    assert "email" not in community["creator"]
    assert "password_hash" not in community["creator"]


def test_06_create_private_community_persists_visibility(user_a):
    community = _create_community(user_a, visibility="private")
    assert community["visibility"] == "private"

    detail = client.get(f"/api/communities/{community['id']}", headers=user_a["headers"])
    assert detail.status_code == 200
    assert detail.json()["visibility"] == "private"


def test_07_create_validation_rejects_invalid_category(user_a):
    res = client.post(
        "/api/communities",
        json=_community_payload(category="not_a_category"),
        headers=user_a["headers"],
    )
    assert res.status_code == 422


def test_08_create_validation_rejects_blank_required_text(user_a):
    res = client.post(
        "/api/communities",
        json=_community_payload(name="   "),
        headers=user_a["headers"],
    )
    assert res.status_code == 422


def test_09_create_validation_cleans_duplicate_tags(user_a):
    community = _create_community(user_a, tags=[" AI ", "ai", "", "RAG"])
    assert community["tags"] == ["AI", "RAG"]


def test_10_discovery_shows_public_but_hides_private(user_a, user_b):
    public = _create_community(user_a, name="Discoverable Cloud Crew", category="cloud_devops")
    private = _create_community(user_a, name="Hidden Cloud Crew", visibility="private")

    res = client.get("/api/communities", headers=user_b["headers"])
    assert res.status_code == 200
    ids = {c["id"] for c in res.json()["communities"]}
    assert public["id"] in ids
    assert private["id"] not in ids


def test_11_discovery_search_and_category_filters(user_a, user_b):
    target = _create_community(
        user_a,
        name="Quantum Data Lab",
        description="Analytics and warehouse patterns.",
        category="data_science",
    )
    _create_community(user_a, name="Frontend Circle", category="web_development")

    res = client.get(
        "/api/communities",
        params={"q": "quantum", "category": "data_science"},
        headers=user_b["headers"],
    )
    assert res.status_code == 200
    ids = {c["id"] for c in res.json()["communities"]}
    assert target["id"] in ids

    miss = client.get(
        "/api/communities",
        params={"q": "quantum", "category": "web_development"},
        headers=user_b["headers"],
    )
    assert miss.status_code == 200
    assert target["id"] not in {c["id"] for c in miss.json()["communities"]}


def test_12_discovery_pagination_returns_distinct_pages(user_a, user_b):
    _create_community(user_a, name=f"Paged Alpha {uuid.uuid4().hex[:4]}")
    _create_community(user_a, name=f"Paged Beta {uuid.uuid4().hex[:4]}")

    page1 = client.get(
        "/api/communities",
        params={"limit": 1, "offset": 0},
        headers=user_b["headers"],
    )
    page2 = client.get(
        "/api/communities",
        params={"limit": 1, "offset": 1},
        headers=user_b["headers"],
    )
    assert page1.status_code == 200
    assert page2.status_code == 200
    assert page1.json()["limit"] == 1
    assert page1.json()["offset"] == 0
    if page1.json()["total"] > 1:
        assert {c["id"] for c in page1.json()["communities"]}.isdisjoint(
            {c["id"] for c in page2.json()["communities"]}
        )


def test_13_public_detail_is_visible_to_authenticated_non_member(user_a, user_b):
    community = _create_community(user_a)
    res = client.get(f"/api/communities/{community['id']}", headers=user_b["headers"])

    assert res.status_code == 200
    data = res.json()
    assert data["id"] == community["id"]
    assert data["joined"] is False
    assert data["membership_status"] == "none"


def test_14_private_detail_is_hidden_from_non_member(user_a, user_b):
    community = _create_community(user_a, visibility="private")
    res = client.get(f"/api/communities/{community['id']}", headers=user_b["headers"])
    assert res.status_code == 404


def test_15_private_detail_visible_to_member(user_a, user_b):
    community = _create_community(user_a, visibility="private")
    _add_membership(community["id"], user_b["user_id"])

    res = client.get(f"/api/communities/{community['id']}", headers=user_b["headers"])
    assert res.status_code == 200
    assert res.json()["joined"] is True
    assert res.json()["is_owner"] is False


def test_16_nonexistent_community_detail_returns_404(user_a):
    res = client.get(f"/api/communities/{uuid.uuid4()}", headers=user_a["headers"])
    assert res.status_code == 404


def test_17_public_join_creates_membership_and_updates_detail(user_a, user_b):
    community = _create_community(user_a)
    join = _join(user_b, community["id"])
    assert join.status_code == 200
    assert join.json()["joined"] is True

    detail = client.get(f"/api/communities/{community['id']}", headers=user_b["headers"])
    assert detail.status_code == 200
    assert detail.json()["joined"] is True
    assert detail.json()["member_count"] == 2


def test_18_duplicate_join_returns_409_and_does_not_duplicate_rows(user_a, user_b):
    community = _create_community(user_a)
    assert _join(user_b, community["id"]).status_code == 200
    assert _join(user_b, community["id"]).status_code == 409

    db = SessionLocal()
    try:
        count = db.query(CommunityMembership).filter(
            CommunityMembership.community_id == community["id"],
            CommunityMembership.user_id == user_b["user_id"],
        ).count()
        assert count == 1
    finally:
        db.close()


def test_19_database_unique_constraint_blocks_duplicate_membership(user_a, user_b):
    community = _create_community(user_a)
    _add_membership(community["id"], user_b["user_id"])

    db = SessionLocal()
    try:
        db.add(CommunityMembership(
            community_id=community["id"],
            user_id=user_b["user_id"],
            role="member",
        ))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()


def test_20_private_direct_join_is_forbidden(user_a, user_b):
    community = _create_community(user_a, visibility="private")
    res = _join(user_b, community["id"])
    assert res.status_code == 403


def test_21_member_can_leave_public_community(user_a, user_b):
    community = _create_community(user_a)
    assert _join(user_b, community["id"]).status_code == 200

    res = client.post(f"/api/communities/{community['id']}/leave", headers=user_b["headers"])
    assert res.status_code == 200
    assert res.json()["joined"] is False

    detail = client.get(f"/api/communities/{community['id']}", headers=user_b["headers"])
    assert detail.status_code == 200
    assert detail.json()["joined"] is False
    assert detail.json()["member_count"] == 1


def test_22_owner_cannot_leave_community_v1(user_a):
    community = _create_community(user_a)
    res = client.post(f"/api/communities/{community['id']}/leave", headers=user_a["headers"])
    assert res.status_code == 400


def test_23_non_member_leave_returns_404(user_a, user_b):
    community = _create_community(user_a)
    res = client.post(f"/api/communities/{community['id']}/leave", headers=user_b["headers"])
    assert res.status_code == 404


def test_24_joined_filter_returns_public_and_private_memberships(user_a, user_b):
    public = _create_community(user_a, name="Joined Public Guild")
    private = _create_community(user_a, name="Joined Private Guild", visibility="private")
    _join(user_b, public["id"])
    _add_membership(private["id"], user_b["user_id"])

    res = client.get(
        "/api/communities",
        params={"membership": "joined"},
        headers=user_b["headers"],
    )
    assert res.status_code == 200
    ids = {c["id"] for c in res.json()["communities"]}
    assert public["id"] in ids
    assert private["id"] in ids


def test_25_members_list_contains_safe_public_fields(user_a, user_b):
    community = _create_community(user_a)
    _join(user_b, community["id"])

    res = client.get(f"/api/communities/{community['id']}/members", headers=user_a["headers"])
    assert res.status_code == 200
    members = res.json()["members"]
    assert {m["id"] for m in members} == {user_a["user_id"], user_b["user_id"]}
    for member in members:
        assert "email" not in member
        assert "password" not in member
        assert "password_hash" not in member
        assert member["role"] in {"owner", "member"}
        assert member["joined_at"] is not None


def test_26_private_members_are_forbidden_to_non_member(user_a, user_b):
    community = _create_community(user_a, visibility="private")
    res = client.get(f"/api/communities/{community['id']}/members", headers=user_b["headers"])
    assert res.status_code == 403


def test_27_member_can_create_post_and_response_has_safe_author(user_a, user_b):
    community = _create_community(user_a)
    _join(user_b, community["id"])

    res = client.post(
        f"/api/communities/{community['id']}/posts",
        data={"content": "  Excited to learn with everyone.  ", "tags": "[]"},
        headers=user_b["headers"],
    )
    assert res.status_code == 201
    post = res.json()
    assert post["community_id"] == community["id"]
    assert post["author_id"] == user_b["user_id"]
    assert post["author"]["id"] == user_b["user_id"]
    assert post["content"] == "Excited to learn with everyone."
    assert post["like_count"] == 0
    assert post["comment_count"] == 0
    assert "email" not in post["author"]
    assert "password_hash" not in post["author"]


def test_28_non_member_cannot_create_post(user_a, user_b):
    community = _create_community(user_a)
    res = client.post(
        f"/api/communities/{community['id']}/posts",
        data={"content": "I should not be allowed.", "tags": "[]"},
        headers=user_b["headers"],
    )
    assert res.status_code == 403


def test_29_post_validation_rejects_blank_and_too_long_content(user_a):
    community = _create_community(user_a)
    blank = client.post(
        f"/api/communities/{community['id']}/posts",
        data={"content": "   ", "tags": "[]"},
        headers=user_a["headers"],
    )
    assert blank.status_code == 422

    too_long = client.post(
        f"/api/communities/{community['id']}/posts",
        data={"content": "x" * 2001, "tags": "[]"},
        headers=user_a["headers"],
    )
    assert too_long.status_code == 422


def test_30_posts_list_is_scoped_ordered_and_paginated(user_a, user_b):
    community_a = _create_community(user_a)
    community_b = _create_community(user_a)
    _join(user_b, community_a["id"])

    first = client.post(
        f"/api/communities/{community_a['id']}/posts",
        data={"content": "First post", "tags": "[]"},
        headers=user_a["headers"],
    ).json()
    second = client.post(
        f"/api/communities/{community_a['id']}/posts",
        data={"content": "Second post", "tags": "[]"},
        headers=user_b["headers"],
    ).json()
    client.post(
        f"/api/communities/{community_b['id']}/posts",
        data={"content": "Other community", "tags": "[]"},
        headers=user_a["headers"],
    )

    db = SessionLocal()
    try:
        db.query(CommunityPost).filter(CommunityPost.id == first["id"]).update(
            {"created_at": datetime.now(timezone.utc) - timedelta(minutes=2)}
        )
        db.query(CommunityPost).filter(CommunityPost.id == second["id"]).update(
            {"created_at": datetime.now(timezone.utc)}
        )
        db.commit()
    finally:
        db.close()

    page1 = client.get(
        f"/api/communities/{community_a['id']}/posts",
        params={"limit": 1, "offset": 0},
        headers=user_b["headers"],
    )
    page2 = client.get(
        f"/api/communities/{community_a['id']}/posts",
        params={"limit": 1, "offset": 1},
        headers=user_b["headers"],
    )

    assert page1.status_code == 200
    assert page2.status_code == 200
    assert page1.json()["total"] == 2
    assert page1.json()["posts"][0]["id"] == second["id"]
    assert page2.json()["posts"][0]["id"] == first["id"]


def test_31_private_posts_are_forbidden_to_non_member(user_a, user_b):
    community = _create_community(user_a, visibility="private")
    client.post(
        f"/api/communities/{community['id']}/posts",
        data={"content": "Private update", "tags": "[]"},
        headers=user_a["headers"],
    )

    res = client.get(f"/api/communities/{community['id']}/posts", headers=user_b["headers"])
    assert res.status_code == 403


def test_32_private_member_can_list_and_create_posts(user_a, user_b):
    community = _create_community(user_a, visibility="private")
    _add_membership(community["id"], user_b["user_id"])

    create = client.post(
        f"/api/communities/{community['id']}/posts",
        data={"content": "Member-only discussion", "tags": "[]"},
        headers=user_b["headers"],
    )
    assert create.status_code == 201

    posts = client.get(f"/api/communities/{community['id']}/posts", headers=user_b["headers"])
    assert posts.status_code == 200
    assert posts.json()["total"] == 1
    assert posts.json()["posts"][0]["content"] == "Member-only discussion"


def test_33_community_responses_do_not_expose_sensitive_fields(user_a, user_b):
    community = _create_community(user_a)
    _join(user_b, community["id"])
    client.post(
        f"/api/communities/{community['id']}/posts",
        data={"content": "Privacy check", "tags": "[]"},
        headers=user_b["headers"],
    )

    detail = client.get(f"/api/communities/{community['id']}", headers=user_b["headers"])
    members = client.get(f"/api/communities/{community['id']}/members", headers=user_b["headers"])
    posts = client.get(f"/api/communities/{community['id']}/posts", headers=user_b["headers"])

    combined = "\n".join([detail.text, members.text, posts.text]).lower()
    assert "password_hash" not in combined
    assert "password" not in combined
    assert user_a["email"].lower() not in combined
    assert user_b["email"].lower() not in combined


def test_34_authenticated_user_can_react_and_current_reaction_is_returned(user_a, user_b):
    community = _create_community(user_a)
    post = _create_post(user_a, community["id"])

    res = client.post(
        f"/api/communities/posts/{post['id']}/reaction",
        json={"reaction_type": "LIKE", "user_id": user_a["user_id"]},
        headers=user_b["headers"],
    )
    assert res.status_code == 200
    data = res.json()
    assert data["post_id"] == post["id"]
    assert data["my_reaction"] == "LIKE"
    assert data["counts"]["LIKE"] == 1
    assert data["total"] == 1

    posts = client.get(f"/api/communities/{community['id']}/posts", headers=user_b["headers"])
    returned = next(item for item in posts.json()["posts"] if item["id"] == post["id"])
    assert returned["my_reaction"] == "LIKE"
    assert returned["reaction_counts"]["LIKE"] == 1
    assert returned["total_reactions"] == 1
    assert returned["like_count"] == 1


def test_35_same_reaction_click_removes_reaction(user_a):
    community = _create_community(user_a)
    post = _create_post(user_a, community["id"])

    first = client.post(
        f"/api/communities/posts/{post['id']}/reaction",
        json={"reaction_type": "LIKE"},
        headers=user_a["headers"],
    )
    second = client.post(
        f"/api/communities/posts/{post['id']}/reaction",
        json={"reaction_type": "LIKE"},
        headers=user_a["headers"],
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["my_reaction"] is None
    assert second.json()["counts"]["LIKE"] == 0
    assert second.json()["total"] == 0


def test_36_reaction_can_be_changed_and_only_one_row_exists(user_a):
    community = _create_community(user_a)
    post = _create_post(user_a, community["id"])

    client.post(
        f"/api/communities/posts/{post['id']}/reaction",
        json={"reaction_type": "LIKE"},
        headers=user_a["headers"],
    )
    changed = client.post(
        f"/api/communities/posts/{post['id']}/reaction",
        json={"reaction_type": "LOVE"},
        headers=user_a["headers"],
    )
    assert changed.status_code == 200
    assert changed.json()["my_reaction"] == "LOVE"
    assert changed.json()["counts"]["LIKE"] == 0
    assert changed.json()["counts"]["LOVE"] == 1

    db = SessionLocal()
    try:
        rows = db.query(CommunityPostReaction).filter(
            CommunityPostReaction.post_id == post["id"],
            CommunityPostReaction.user_id == user_a["user_id"],
        ).all()
        assert len(rows) == 1
        assert rows[0].reaction_type == "LOVE"
    finally:
        db.close()


def test_37_duplicate_reaction_database_constraint_blocks_multiple_rows(user_a):
    community = _create_community(user_a)
    post = _create_post(user_a, community["id"])
    _ = client.post(
        f"/api/communities/posts/{post['id']}/reaction",
        json={"reaction_type": "LIKE"},
        headers=user_a["headers"],
    )

    db = SessionLocal()
    try:
        db.add(CommunityPostReaction(
            post_id=post["id"],
            user_id=user_a["user_id"],
            reaction_type="FUNNY",
        ))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()


def test_38_unauthenticated_reaction_rejected(user_a):
    community = _create_community(user_a)
    post = _create_post(user_a, community["id"])
    res = client.post(
        f"/api/communities/posts/{post['id']}/reaction",
        json={"reaction_type": "LIKE"},
    )
    assert res.status_code == 401


def test_39_private_post_reaction_requires_private_access(user_a, user_b):
    community = _create_community(user_a, visibility="private")
    post = _create_post(user_a, community["id"])
    res = client.post(
        f"/api/communities/posts/{post['id']}/reaction",
        json={"reaction_type": "LIKE"},
        headers=user_b["headers"],
    )
    assert res.status_code == 404


def test_40_authenticated_user_can_create_and_list_comments(user_a, user_b):
    community = _create_community(user_a)
    post = _create_post(user_a, community["id"])

    create = client.post(
        f"/api/communities/posts/{post['id']}/comments",
        json={"content": "  Good point.  ", "post_id": "fake"},
        headers=user_b["headers"],
    )
    assert create.status_code == 201
    comment = create.json()
    assert comment["post_id"] == post["id"]
    assert comment["author_id"] == user_b["user_id"]
    assert comment["content"] == "Good point."
    assert "email" not in comment["author"]
    assert "password_hash" not in comment["author"]

    listed = client.get(f"/api/communities/posts/{post['id']}/comments", headers=user_a["headers"])
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["comments"][0]["id"] == comment["id"]

    posts = client.get(f"/api/communities/{community['id']}/posts", headers=user_a["headers"])
    returned = next(item for item in posts.json()["posts"] if item["id"] == post["id"])
    assert returned["comment_count"] == 1


def test_41_comment_validation_rejects_empty_and_oversized(user_a):
    community = _create_community(user_a)
    post = _create_post(user_a, community["id"])

    empty = client.post(
        f"/api/communities/posts/{post['id']}/comments",
        json={"content": "   "},
        headers=user_a["headers"],
    )
    assert empty.status_code == 422

    oversized = client.post(
        f"/api/communities/posts/{post['id']}/comments",
        json={"content": "x" * 1001},
        headers=user_a["headers"],
    )
    assert oversized.status_code == 422


def test_42_private_post_comments_respect_authorization(user_a, user_b):
    community = _create_community(user_a, visibility="private")
    post = _create_post(user_a, community["id"])

    create = client.post(
        f"/api/communities/posts/{post['id']}/comments",
        json={"content": "No access"},
        headers=user_b["headers"],
    )
    listed = client.get(f"/api/communities/posts/{post['id']}/comments", headers=user_b["headers"])
    assert create.status_code == 404
    assert listed.status_code == 404


def test_43_post_author_can_delete_own_post_and_it_disappears(user_a):
    community = _create_community(user_a)
    post = _create_post(user_a, community["id"])
    client.post(
        f"/api/communities/posts/{post['id']}/reaction",
        json={"reaction_type": "LIKE"},
        headers=user_a["headers"],
    )
    client.post(
        f"/api/communities/posts/{post['id']}/comments",
        json={"content": "Deleting soon"},
        headers=user_a["headers"],
    )

    res = client.delete(f"/api/communities/posts/{post['id']}", headers=user_a["headers"])
    assert res.status_code == 200
    assert res.json()["success"] is True

    posts = client.get(f"/api/communities/{community['id']}/posts", headers=user_a["headers"])
    assert post["id"] not in {item["id"] for item in posts.json()["posts"]}

    db = SessionLocal()
    try:
        assert db.query(CommunityPostReaction).filter(CommunityPostReaction.post_id == post["id"]).count() == 0
        assert db.query(CommunityPostComment).filter(CommunityPostComment.post_id == post["id"]).count() == 0
    finally:
        db.close()


def test_44_community_owner_can_delete_another_users_post(user_a, user_b):
    community = _create_community(user_a)
    assert _join(user_b, community["id"]).status_code == 200
    post = _create_post(user_b, community["id"], "Member post")

    res = client.delete(f"/api/communities/posts/{post['id']}", headers=user_a["headers"])
    assert res.status_code == 200
    assert res.json()["post_id"] == post["id"]


def test_45_normal_member_cannot_delete_another_users_post(user_a, user_b, user_c):
    community = _create_community(user_a)
    assert _join(user_b, community["id"]).status_code == 200
    assert _join(user_c, community["id"]).status_code == 200
    post = _create_post(user_b, community["id"], "Member post")

    res = client.delete(f"/api/communities/posts/{post['id']}", headers=user_c["headers"])
    assert res.status_code == 403


def test_46_unauthenticated_delete_rejected(user_a):
    community = _create_community(user_a)
    post = _create_post(user_a, community["id"])
    res = client.delete(f"/api/communities/posts/{post['id']}")
    assert res.status_code == 401


def test_47_private_post_delete_does_not_leak_to_non_member(user_a, user_b):
    community = _create_community(user_a, visibility="private")
    post = _create_post(user_a, community["id"])
    res = client.delete(f"/api/communities/posts/{post['id']}", headers=user_b["headers"])
    assert res.status_code == 404


# ────────────────────────────────────────────────────────────────────────────
# V2 features: post topic tags
# ────────────────────────────────────────────────────────────────────────────

def test_48_post_with_valid_tags_persists_and_returns_tags(user_a):
    community = _create_community(user_a)
    import json as _json

    res = client.post(
        f"/api/communities/{community['id']}/posts",
        data={"content": "Post about DevOps and cloud", "tags": _json.dumps(["DevOps", "Cloud"])},
        headers=user_a["headers"],
    )
    assert res.status_code == 201, res.text
    post = res.json()
    assert "DevOps" in post["tags"]
    assert "Cloud" in post["tags"]
    assert len(post["tags"]) == 2

    # Verify tags are returned in list
    listed = client.get(f"/api/communities/{community['id']}/posts", headers=user_a["headers"])
    listed_post = next(p for p in listed.json()["posts"] if p["id"] == post["id"])
    assert set(listed_post["tags"]) == {"DevOps", "Cloud"}


def test_49_duplicate_tags_are_rejected(user_a):
    community = _create_community(user_a)
    import json as _json

    res = client.post(
        f"/api/communities/{community['id']}/posts",
        data={"content": "Duplicate tags test", "tags": _json.dumps(["AI", "ai"])},
        headers=user_a["headers"],
    )
    assert res.status_code == 422


def test_50_too_many_tags_are_rejected(user_a):
    community = _create_community(user_a)
    import json as _json

    # More than 5 tags
    many_tags = [f"Tag{i}" for i in range(6)]
    res = client.post(
        f"/api/communities/{community['id']}/posts",
        data={"content": "Too many tags", "tags": _json.dumps(many_tags)},
        headers=user_a["headers"],
    )
    assert res.status_code == 422


def test_51_tag_too_long_is_rejected(user_a):
    community = _create_community(user_a)
    import json as _json

    long_tag = "A" * 31  # 31 chars, max is 30
    res = client.post(
        f"/api/communities/{community['id']}/posts",
        data={"content": "Long tag test", "tags": _json.dumps([long_tag])},
        headers=user_a["headers"],
    )
    assert res.status_code == 422


def test_52_post_with_empty_content_and_no_images_rejected(user_a):
    community = _create_community(user_a)
    import json as _json

    res = client.post(
        f"/api/communities/{community['id']}/posts",
        data={"content": "   ", "tags": _json.dumps([])},
        headers=user_a["headers"],
    )
    assert res.status_code == 422


def test_53_tags_preserved_through_delete(user_a):
    """Deleting a post should also remove all associated tags (cascade)."""
    community = _create_community(user_a)
    post = _create_post(user_a, community["id"], tags=["Python", "Backend"])
    post_id = post["id"]

    db = SessionLocal()
    try:
        assert db.query(CommunityPostTag).filter(CommunityPostTag.post_id == post_id).count() == 2
    finally:
        db.close()

    res = client.delete(f"/api/communities/posts/{post_id}", headers=user_a["headers"])
    assert res.status_code == 200

    db = SessionLocal()
    try:
        assert db.query(CommunityPostTag).filter(CommunityPostTag.post_id == post_id).count() == 0
    finally:
        db.close()


# ────────────────────────────────────────────────────────────────────────────
# V2 features: community image upload/remove (owner only)
# ────────────────────────────────────────────────────────────────────────────

def _make_minimal_jpeg() -> bytes:
    """Return a minimal valid 1x1 JPEG for testing uploads."""
    # Smallest valid JPEG (1x1 white pixel)
    return (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
        b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
        b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'"
        b"9=82<.342\x1edL\t\x10\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b"
        b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"
        b"\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b"
        b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xf5\xd0\xff\xd9"
    )


def test_54_unauthenticated_image_upload_rejected(user_a):
    community = _create_community(user_a)
    res = client.patch(
        f"/api/communities/{community['id']}/image",
        files={"file": ("photo.jpg", _make_minimal_jpeg(), "image/jpeg")},
    )
    assert res.status_code == 401


def test_55_non_owner_cannot_upload_community_image(user_a, user_b):
    community = _create_community(user_a)
    _join(user_b, community["id"])

    res = client.patch(
        f"/api/communities/{community['id']}/image",
        files={"file": ("photo.jpg", _make_minimal_jpeg(), "image/jpeg")},
        headers=user_b["headers"],
    )
    assert res.status_code == 403


def test_56_owner_can_remove_community_image(user_a):
    community = _create_community(user_a)
    # Remove on a community that has no image — should succeed gracefully
    res = client.delete(
        f"/api/communities/{community['id']}/image",
        headers=user_a["headers"],
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["image_url"] is None


def test_57_community_response_has_image_url_field(user_a):
    community = _create_community(user_a)
    res = client.get(f"/api/communities/{community['id']}", headers=user_a["headers"])
    assert res.status_code == 200
    # image_url should be present (null for communities without a photo)
    assert "image_url" in res.json()


def test_58_post_response_has_media_and_tags_fields(user_a):
    """Response schema must include 'media' and 'tags' lists even for text-only posts."""
    community = _create_community(user_a)
    post = _create_post(user_a, community["id"])

    listed = client.get(f"/api/communities/{community['id']}/posts", headers=user_a["headers"])
    returned = next(p for p in listed.json()["posts"] if p["id"] == post["id"])

    assert isinstance(returned.get("media"), list)
    assert isinstance(returned.get("tags"), list)
    assert returned["media"] == []
    assert returned["tags"] == []


# ────────────────────────────────────────────────────────────────────────────
# Bug-fix regression: sort_order must be stored as INTEGER, not VARCHAR
# Tests 59–68 specifically target the DatatypeMismatch bug.
# ────────────────────────────────────────────────────────────────────────────

def _make_jpeg(pixel_color: int = 0xFF) -> bytes:
    """Return a minimal 1×1 JPEG for upload tests. pixel_color varies bytes so
    files differ enough to get distinct MinIO keys."""
    return (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
        b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
        b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'"
        b"9=82<.342\x1edL\t\x10\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b"
        b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"
        b"\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b"
        + bytes([pixel_color]) +
        b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xf5\xd0\xff\xd9"
    )


def _post_with_images(user: dict, community_id: str, n: int, content: str = "") -> dict:
    """POST a community post with n JPEG images."""
    import json as _json
    files = [("images", (f"img{i}.jpg", _make_jpeg(i + 1), "image/jpeg")) for i in range(n)]
    data = {"content": content, "tags": _json.dumps([])}
    res = client.post(
        f"/api/communities/{community_id}/posts",
        data=data,
        files=files,
        headers=user["headers"],
    )
    return res


def test_59_text_only_post_still_works(user_a):
    """Regression: text-only posts must not be broken by the image fix."""
    community = _create_community(user_a)
    post = _create_post(user_a, community["id"], content="Hello community")
    assert post["content"] == "Hello community"
    assert post["media"] == []


def test_60_single_image_post_succeeds_and_sort_order_is_zero(user_a):
    community = _create_community(user_a)
    res = _post_with_images(user_a, community["id"], n=1, content="One image")
    assert res.status_code == 201, res.text
    post = res.json()
    assert len(post["media"]) == 1
    media = post["media"][0]
    # sort_order must be an integer 0, not a string "0"
    assert media["sort_order"] == 0
    assert isinstance(media["sort_order"], int)
    assert media["url"]  # presigned URL is populated


def test_61_two_image_post_sort_order_is_sequential_integers(user_a):
    community = _create_community(user_a)
    res = _post_with_images(user_a, community["id"], n=2, content="Two images")
    assert res.status_code == 201, res.text
    post = res.json()
    assert len(post["media"]) == 2
    orders = [m["sort_order"] for m in post["media"]]
    assert orders == [0, 1], f"Expected [0, 1], got {orders}"
    for order in orders:
        assert isinstance(order, int), f"sort_order {order!r} is not an int"


def test_62_four_image_post_sort_order_is_0_1_2_3(user_a):
    community = _create_community(user_a)
    res = _post_with_images(user_a, community["id"], n=4, content="Four images")
    assert res.status_code == 201, res.text
    post = res.json()
    assert len(post["media"]) == 4
    orders = [m["sort_order"] for m in post["media"]]
    assert orders == [0, 1, 2, 3], f"Expected [0,1,2,3], got {orders}"
    for order in orders:
        assert isinstance(order, int)


def test_63_image_only_post_succeeds(user_a):
    """A post with no text content but at least one image must be accepted."""
    community = _create_community(user_a)
    res = _post_with_images(user_a, community["id"], n=1, content="")
    assert res.status_code == 201, res.text
    post = res.json()
    assert post["content"] == ""
    assert len(post["media"]) == 1


def test_64_text_and_image_post_succeeds(user_a):
    community = _create_community(user_a)
    res = _post_with_images(user_a, community["id"], n=2, content="Text and images")
    assert res.status_code == 201, res.text
    post = res.json()
    assert post["content"] == "Text and images"
    assert len(post["media"]) == 2


def test_65_sort_order_is_integer_in_postgresql(user_a):
    """Verify the value stored in PostgreSQL is INTEGER, not a varchar.
    This directly exercises the DatatypeMismatch bug — if sort_order were
    inserted as a string the SELECT would still succeed (Postgres would coerce
    it on read in some drivers) but the INSERT itself would have failed.
    We verify via the SQLAlchemy ORM that the column type is integer and the
    value round-trips correctly."""
    community = _create_community(user_a)
    res = _post_with_images(user_a, community["id"], n=2, content="DB type check")
    assert res.status_code == 201, res.text
    post = res.json()
    post_id = post["id"]

    db = SessionLocal()
    try:
        rows = (
            db.query(CommunityPostMedia)
            .filter(CommunityPostMedia.post_id == post_id)
            .order_by(CommunityPostMedia.sort_order)
            .all()
        )
        assert len(rows) == 2
        for expected, row in enumerate(rows):
            # The ORM should return a Python int because the column is Integer
            assert row.sort_order == expected, f"Row {expected}: sort_order={row.sort_order!r}"
            assert isinstance(row.sort_order, int), (
                f"sort_order is {type(row.sort_order).__name__}, expected int"
            )
    finally:
        db.close()


def test_66_listed_posts_include_media_with_integer_sort_orders(user_a):
    """After creation, listing posts must return integer sort_order values."""
    community = _create_community(user_a)
    _post_with_images(user_a, community["id"], n=3, content="List check")

    listed = client.get(f"/api/communities/{community['id']}/posts", headers=user_a["headers"])
    assert listed.status_code == 200
    posts = listed.json()["posts"]
    media_post = next((p for p in posts if len(p.get("media", [])) == 3), None)
    assert media_post is not None, "Expected a post with 3 media items in the list"
    orders = [m["sort_order"] for m in media_post["media"]]
    assert orders == [0, 1, 2]
    for order in orders:
        assert isinstance(order, int)


def test_67_post_with_five_images_rejected(user_a):
    """More than 4 images must be rejected."""
    community = _create_community(user_a)
    res = _post_with_images(user_a, community["id"], n=5, content="Too many")
    assert res.status_code == 422


def test_68_existing_reactions_comments_delete_unaffected(user_a, user_b):
    """Full regression: reactions, comments, and delete still work after the fix."""
    community = _create_community(user_a)
    post = _create_post(user_a, community["id"], "Regression check")

    # Reaction
    react = client.post(
        f"/api/communities/posts/{post['id']}/reaction",
        json={"reaction_type": "LIKE"},
        headers=user_a["headers"],
    )
    assert react.status_code == 200
    assert react.json()["my_reaction"] == "LIKE"

    # Comment
    comment = client.post(
        f"/api/communities/posts/{post['id']}/comments",
        json={"content": "Still works"},
        headers=user_a["headers"],
    )
    assert comment.status_code == 201
    assert comment.json()["content"] == "Still works"

    # Delete
    delete = client.delete(
        f"/api/communities/posts/{post['id']}",
        headers=user_a["headers"],
    )
    assert delete.status_code == 200
    assert delete.json()["success"] is True
