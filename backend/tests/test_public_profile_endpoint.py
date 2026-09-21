"""
Phase 5.6 — Public Profile endpoint tests.

Covers: GET /api/networking/users/{user_id}/profile

Test index
----------
A. Authentication
  A1. Unauthenticated request is rejected (401)
  A2. Authenticated request succeeds (200)

B. Profile retrieval
  B1. Returns 404 for non-existent user
  B2. Returns user basics when profile has not been created yet
  B3. Returns populated profile fields when profile exists
  B4. Returns correct username/name for the target user

C. User scoping / JWT isolation
  C1. Viewer A fetches User B's profile — receives B's data, not A's
  C2. Viewer A cannot manipulate the URL to receive User C's data when requesting B
  C3. Endpoint always reflects the URL user_id, never the JWT user_id

D. Response safety
  D1. Response does NOT contain password_hash
  D2. Response does NOT contain email
  D3. Response does NOT contain access_token or any auth field
  D4. Top-level keys match the expected PublicProfileResponse schema exactly
  D5. other_user / career_preferences / completeness are absent
  D6. Sensitive string values do not appear anywhere in the raw JSON

E. Profile data correctness
  E1. Skills are returned correctly
  E2. Experience is returned correctly
  E3. Education is returned correctly
  E4. Certifications are returned correctly
  E5. Empty sections return [] not null

F. Connection status (reuse existing endpoint — verified for integration)
  F1. Connection status endpoint /users/{id}/connection still returns correct status
      for authenticated viewer — confirming both endpoints work together
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date
from typing import Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import or_

from app.db.models import (
    Connection, Profile, ProfileEducation, ProfileExperience,
    ProfileSkill, ProfileCertification, User,
)
from app.db.session import Base, SessionLocal, engine
from app.db.redis_client import redis_client
from app.core.config import settings
from app.main import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# Expected schema keys
# ---------------------------------------------------------------------------

_EXPECTED_TOP_KEYS = {
    "user", "headline", "location", "about",
    "profile_photo_url", "skills", "experience",
    "education", "projects", "certifications",
}
_EXPECTED_USER_KEYS = {"id", "username", "first_name", "last_name"}
_FORBIDDEN_EVERYWHERE = {
    "password_hash", "password", "email",
    "access_token", "refresh_token", "secret_key",
    "hashed", "career_preferences", "completeness",
    "profile_photo_media_id",
}

# ---------------------------------------------------------------------------
# Helpers — same pattern as test_networking_api.py
# ---------------------------------------------------------------------------

_CTR = 0


def _tag() -> str:
    global _CTR
    _CTR += 1
    return f"pp{_CTR}_{uuid.uuid4().hex[:6]}"


def _seed_otp(email: str) -> str:
    token = f"tok-{uuid.uuid4().hex}"
    token_hash = hashlib.sha256(
        f"{email}:{token}:{settings.SECRET_KEY}".encode()
    ).hexdigest()
    redis_client.set(
        f"otp:{email}",
        json.dumps({"otp": "123456", "verified_token": token_hash, "token_raw": token}),
        ex=600,
    )
    return token


def _register(tag: Optional[str] = None) -> dict:
    if tag is None:
        tag = _tag()
    email = f"pp_{tag}@example.com"
    username = f"pp_{tag}"[:30]
    res = client.post("/api/auth/register", json={
        "first_name": "Profile",
        "last_name": "Viewer",
        "username": username,
        "email": email,
        "password": "Password123",
        "email_verification_token": _seed_otp(email),
    })
    assert res.status_code == 201, res.text
    uid = res.json()["id"]
    login = client.post("/api/auth/login", json={"identifier": username, "password": "Password123"})
    assert login.status_code == 200
    return {
        "user_id": uid,
        "username": username,
        "email": email,
        "headers": {"Authorization": f"Bearer {login.json()['access_token']}"},
    }


def _cleanup(*emails: str) -> None:
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.email.in_(emails)).all()
        ids = [u.id for u in users]
        if ids:
            db.query(Connection).filter(
                or_(Connection.requester_id.in_(ids), Connection.receiver_id.in_(ids))
            ).delete(synchronize_session=False)
            db.query(Profile).filter(Profile.user_id.in_(ids)).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(ids)).delete(synchronize_session=False)
            db.commit()
    finally:
        db.close()


def _seed_profile(user_id: str) -> None:
    """Insert a minimal profile with one skill, experience, education, cert."""
    db = SessionLocal()
    try:
        profile = Profile(
            user_id=user_id,
            headline="Senior Engineer",
            location="Mumbai, India",
            about="Passionate about building great software.",
        )
        db.add(profile)
        db.flush()

        db.add(ProfileSkill(profile_id=profile.id, name="Python", normalized_name="python"))
        db.add(ProfileExperience(
            profile_id=profile.id,
            company="Tech Corp",
            job_title="Software Engineer",
            employment_type="Full-time",
            start_date=date(2022, 1, 1),
            currently_working=True,
        ))
        db.add(ProfileEducation(
            profile_id=profile.id,
            institution="IIT Bombay",
            degree="B.Tech",
            field_of_study="Computer Science",
            start_date=date(2018, 7, 1),
            end_date=date(2022, 5, 1),
        ))
        db.add(ProfileCertification(
            profile_id=profile.id,
            name="AWS Solutions Architect",
            issuing_organization="Amazon Web Services",
            issue_date=date(2023, 3, 1),
        ))
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def ensure_tables():
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def viewer():
    u = _register()
    yield u
    _cleanup(u["email"])


@pytest.fixture()
def target():
    u = _register()
    yield u
    _cleanup(u["email"])


@pytest.fixture()
def target_with_profile(target):
    _seed_profile(target["user_id"])
    yield target


@pytest.fixture()
def third_user():
    u = _register()
    yield u
    _cleanup(u["email"])


# ===========================================================================
# A. Authentication
# ===========================================================================


def test_A1_unauthenticated_rejected(target):
    res = client.get(f"/api/networking/users/{target['user_id']}/profile")
    assert res.status_code == 401


def test_A2_authenticated_succeeds(viewer, target):
    res = client.get(
        f"/api/networking/users/{target['user_id']}/profile",
        headers=viewer["headers"],
    )
    assert res.status_code == 200


# ===========================================================================
# B. Profile retrieval
# ===========================================================================


def test_B1_nonexistent_user_returns_404(viewer):
    fake_id = str(uuid.uuid4())
    res = client.get(
        f"/api/networking/users/{fake_id}/profile",
        headers=viewer["headers"],
    )
    assert res.status_code == 404


def test_B2_user_without_profile_returns_basics(viewer, target):
    """A user who has never created a profile still returns user basics with empty sections."""
    res = client.get(
        f"/api/networking/users/{target['user_id']}/profile",
        headers=viewer["headers"],
    )
    assert res.status_code == 200
    data = res.json()
    assert data["user"]["id"] == target["user_id"]
    assert data["user"]["username"] == target["username"]
    assert data["skills"] == []
    assert data["experience"] == []
    assert data["education"] == []
    assert data["projects"] == []
    assert data["certifications"] == []


def test_B3_populated_profile_returns_fields(viewer, target_with_profile):
    res = client.get(
        f"/api/networking/users/{target_with_profile['user_id']}/profile",
        headers=viewer["headers"],
    )
    assert res.status_code == 200
    data = res.json()
    assert data["headline"] == "Senior Engineer"
    assert data["location"] == "Mumbai, India"
    assert data["about"] == "Passionate about building great software."


def test_B4_returns_correct_user_identity(viewer, target_with_profile):
    res = client.get(
        f"/api/networking/users/{target_with_profile['user_id']}/profile",
        headers=viewer["headers"],
    )
    data = res.json()
    assert data["user"]["id"] == target_with_profile["user_id"]
    assert data["user"]["username"] == target_with_profile["username"]


# ===========================================================================
# C. User scoping / JWT isolation
# ===========================================================================


def test_C1_viewer_receives_target_data_not_own(viewer, target_with_profile):
    """When A views B's profile, the response contains B's data, not A's."""
    res = client.get(
        f"/api/networking/users/{target_with_profile['user_id']}/profile",
        headers=viewer["headers"],
    )
    data = res.json()
    # user field is B, not A
    assert data["user"]["id"] == target_with_profile["user_id"]
    assert data["user"]["id"] != viewer["user_id"]
    assert data["user"]["username"] == target_with_profile["username"]


def test_C2_url_user_id_determines_profile_not_jwt(viewer, target, third_user):
    """
    When A fetches /users/B/profile while authenticated, the response is B's data.
    Passing B's user_id in the URL cannot return C's data.
    """
    _seed_profile(target["user_id"])

    res_b = client.get(
        f"/api/networking/users/{target['user_id']}/profile",
        headers=viewer["headers"],
    )
    res_c = client.get(
        f"/api/networking/users/{third_user['user_id']}/profile",
        headers=viewer["headers"],
    )
    assert res_b.json()["user"]["id"] == target["user_id"]
    assert res_c.json()["user"]["id"] == third_user["user_id"]
    # They are different users
    assert res_b.json()["user"]["id"] != res_c.json()["user"]["id"]


def test_C3_viewing_own_profile_works(viewer):
    """A user can view their own public profile without error."""
    res = client.get(
        f"/api/networking/users/{viewer['user_id']}/profile",
        headers=viewer["headers"],
    )
    assert res.status_code == 200
    data = res.json()
    assert data["user"]["id"] == viewer["user_id"]


# ===========================================================================
# D. Response safety
# ===========================================================================


def test_D1_no_password_hash_in_response(viewer, target_with_profile):
    res = client.get(
        f"/api/networking/users/{target_with_profile['user_id']}/profile",
        headers=viewer["headers"],
    )
    raw = res.text.lower()
    assert "password_hash" not in raw
    assert "password" not in raw


def test_D2_no_email_in_response(viewer, target_with_profile):
    res = client.get(
        f"/api/networking/users/{target_with_profile['user_id']}/profile",
        headers=viewer["headers"],
    )
    # email of the target user must not appear
    assert target_with_profile["email"] not in res.text


def test_D3_no_auth_fields_in_response(viewer, target_with_profile):
    res = client.get(
        f"/api/networking/users/{target_with_profile['user_id']}/profile",
        headers=viewer["headers"],
    )
    raw = res.text.lower()
    for field in ("access_token", "refresh_token", "secret_key", "hashed"):
        assert field not in raw, f"Auth field '{field}' must not appear in public profile response"


def test_D4_top_level_keys_match_schema(viewer, target_with_profile):
    res = client.get(
        f"/api/networking/users/{target_with_profile['user_id']}/profile",
        headers=viewer["headers"],
    )
    top_keys = set(res.json().keys())
    assert top_keys == _EXPECTED_TOP_KEYS, (
        f"Unexpected top-level keys: {top_keys.symmetric_difference(_EXPECTED_TOP_KEYS)}"
    )


def test_D5_forbidden_fields_absent_from_response(viewer, target_with_profile):
    res = client.get(
        f"/api/networking/users/{target_with_profile['user_id']}/profile",
        headers=viewer["headers"],
    )
    data = res.json()
    for forbidden in _FORBIDDEN_EVERYWHERE:
        assert forbidden not in data, (
            f"Forbidden field '{forbidden}' found at top level"
        )
    # Check nested user object
    for forbidden in _FORBIDDEN_EVERYWHERE:
        assert forbidden not in data.get("user", {}), (
            f"Forbidden field '{forbidden}' found in user object"
        )


def test_D6_user_object_keys_match_schema(viewer, target):
    res = client.get(
        f"/api/networking/users/{target['user_id']}/profile",
        headers=viewer["headers"],
    )
    user_keys = set(res.json()["user"].keys())
    assert user_keys == _EXPECTED_USER_KEYS, (
        f"Unexpected user keys: {user_keys.symmetric_difference(_EXPECTED_USER_KEYS)}"
    )


# ===========================================================================
# E. Profile data correctness
# ===========================================================================


def test_E1_skills_returned_correctly(viewer, target_with_profile):
    res = client.get(
        f"/api/networking/users/{target_with_profile['user_id']}/profile",
        headers=viewer["headers"],
    )
    skills = res.json()["skills"]
    assert len(skills) >= 1
    skill_names = [s["name"] for s in skills]
    assert "Python" in skill_names


def test_E2_experience_returned_correctly(viewer, target_with_profile):
    res = client.get(
        f"/api/networking/users/{target_with_profile['user_id']}/profile",
        headers=viewer["headers"],
    )
    exp = res.json()["experience"]
    assert len(exp) >= 1
    assert exp[0]["company"] == "Tech Corp"
    assert exp[0]["job_title"] == "Software Engineer"
    assert exp[0]["currently_working"] is True


def test_E3_education_returned_correctly(viewer, target_with_profile):
    res = client.get(
        f"/api/networking/users/{target_with_profile['user_id']}/profile",
        headers=viewer["headers"],
    )
    edu = res.json()["education"]
    assert len(edu) >= 1
    assert edu[0]["institution"] == "IIT Bombay"
    assert edu[0]["degree"] == "B.Tech"
    assert edu[0]["field_of_study"] == "Computer Science"


def test_E4_certifications_returned_correctly(viewer, target_with_profile):
    res = client.get(
        f"/api/networking/users/{target_with_profile['user_id']}/profile",
        headers=viewer["headers"],
    )
    certs = res.json()["certifications"]
    assert len(certs) >= 1
    assert certs[0]["name"] == "AWS Solutions Architect"
    assert certs[0]["issuing_organization"] == "Amazon Web Services"


def test_E5_empty_sections_return_lists_not_null(viewer, target):
    """User without profile: all section fields must be [] not None/null."""
    res = client.get(
        f"/api/networking/users/{target['user_id']}/profile",
        headers=viewer["headers"],
    )
    data = res.json()
    for section in ("skills", "experience", "education", "projects", "certifications"):
        assert isinstance(data[section], list), (
            f"Section '{section}' must be a list, got {type(data[section])}"
        )


# ===========================================================================
# F. Connection status integration
# ===========================================================================


def test_F1_connection_status_works_alongside_profile(viewer, target):
    """
    After sending a request, the connection status endpoint returns 'pending'
    and the profile endpoint still returns 200 — both work together.
    """
    # Send connection request
    conn_res = client.post(
        f"/api/networking/connections/{target['user_id']}",
        headers=viewer["headers"],
    )
    assert conn_res.status_code == 201

    # Profile still accessible
    profile_res = client.get(
        f"/api/networking/users/{target['user_id']}/profile",
        headers=viewer["headers"],
    )
    assert profile_res.status_code == 200

    # Connection status shows pending
    status_res = client.get(
        f"/api/networking/users/{target['user_id']}/connection",
        headers=viewer["headers"],
    )
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "pending"
