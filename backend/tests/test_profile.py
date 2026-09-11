import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import or_

from app.core.security import create_access_token, hash_password
from app.db.models import MediaObject, User
from app.db.session import Base, SessionLocal, engine
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_profile_users():
    Base.metadata.create_all(bind=engine)
    yield
    db = SessionLocal()
    try:
        users = (
            db.query(User)
            .filter(or_(User.email.like("%@profile-test.example.com"), User.username.like("test_profile_%")))
            .all()
        )
        ids = [user.id for user in users]
        if ids:
            db.query(User).filter(User.id.in_(ids)).delete(synchronize_session=False)
            db.commit()
    finally:
        db.close()


def _create_user(username: str) -> tuple[User, dict[str, str]]:
    db = SessionLocal()
    try:
        user = User(
            first_name="Test",
            last_name="User",
            username=username,
            email=f"{username}@profile-test.example.com",
            password_hash=hash_password("Password123"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_access_token(subject=user.id)
        return user, {"Authorization": f"Bearer {token}"}
    finally:
        db.close()


def test_profile_crud_and_user_scoping():
    user_a, headers_a = _create_user("test_profile_a")
    _, headers_b = _create_user("test_profile_b")

    res = client.get("/api/profile/me", headers=headers_a)
    assert res.status_code == 200, res.text
    profile = res.json()
    assert profile["user"]["username"] == "test_profile_a"
    assert profile["skills"] == []

    db = SessionLocal()
    try:
        media = MediaObject(
            user_id=user_a.id,
            object_key=f"test/{uuid.uuid4().hex}.png",
            filename="avatar.png",
            content_type="image/png",
            size_bytes=12,
            purpose="profile_image",
        )
        db.add(media)
        db.commit()
        db.refresh(media)
        media_id = media.id
    finally:
        db.close()

    basic = client.patch(
        "/api/profile/me",
        headers=headers_a,
        json={
            "first_name": "Raj",
            "last_name": "Sharma",
            "headline": "Backend Developer | Python | FastAPI",
            "location": "Mumbai, India",
            "about": "Backend developer interested in scalable APIs.",
            "profile_photo_media_id": media_id,
        },
    )
    assert basic.status_code == 200, basic.text
    assert basic.json()["user"]["first_name"] == "Raj"
    assert basic.json()["profile_photo_media_id"] == media_id

    skill = client.post("/api/profile/me/skills", headers=headers_a, json={"name": "Python"})
    assert skill.status_code == 201, skill.text
    skill_id = skill.json()["id"]
    duplicate = client.post("/api/profile/me/skills", headers=headers_a, json={"name": " python "})
    assert duplicate.status_code == 409

    education = client.post(
        "/api/profile/me/education",
        headers=headers_a,
        json={"institution": "XYZ University", "degree": "B.Tech", "field_of_study": "Computer Science", "start_date": "2023-01-01", "end_date": "2027-01-01"},
    )
    assert education.status_code == 201, education.text

    bad_dates = client.post(
        "/api/profile/me/experience",
        headers=headers_a,
        json={"company": "Acme", "job_title": "Intern", "start_date": "2026-01-01", "end_date": "2025-01-01"},
    )
    assert bad_dates.status_code == 422

    experience = client.post(
        "/api/profile/me/experience",
        headers=headers_a,
        json={"company": "Acme", "job_title": "Software Engineering Intern", "employment_type": "Internship", "currently_working": True},
    )
    assert experience.status_code == 201, experience.text

    bad_project = client.post(
        "/api/profile/me/projects",
        headers=headers_a,
        json={"name": "Bad URL", "github_url": "not-a-url"},
    )
    assert bad_project.status_code == 422

    project = client.post(
        "/api/profile/me/projects",
        headers=headers_a,
        json={"name": "CareerSphere AI", "technologies": ["FastAPI", "Next.js", "FastAPI"], "github_url": "https://github.com/example/careersphere"},
    )
    assert project.status_code == 201, project.text
    assert project.json()["technologies"] == ["FastAPI", "Next.js"]

    cert = client.post(
        "/api/profile/me/certifications",
        headers=headers_a,
        json={"name": "AWS Cloud Practitioner", "issuing_organization": "AWS", "credential_url": "https://example.com/credential"},
    )
    assert cert.status_code == 201, cert.text

    pref = client.patch(
        "/api/profile/me/preferences",
        headers=headers_a,
        json={"target_job_role": "Backend Developer", "preferred_work_type": "Remote", "preferred_locations": ["Mumbai", "Remote"], "career_interests": ["Cloud", "DevOps"]},
    )
    assert pref.status_code == 200, pref.text

    scoped_delete = client.delete(f"/api/profile/me/skills/{skill_id}", headers=headers_b)
    assert scoped_delete.status_code == 404

    final_profile = client.get("/api/profile/me", headers=headers_a).json()
    assert final_profile["completeness"]["percentage"] == 100
    assert final_profile["career_preferences"]["career_interests"] == ["Cloud", "DevOps"]
