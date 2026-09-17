"""
Phase 3.6 — Career Matching API tests.

Tests:
 1. Authenticated user receives career matching response.
 2. Unauthenticated request is rejected.
 3. User ID comes from JWT (current_user dependency).
 4. Frontend cannot request another user's matching results.
 5. Final results contain at most 5 opportunities.
 6. Deterministic score remains unchanged through pipeline.
 7. Gemini metadata remains attached on success.
 8. Qwen explanation attaches to correct opportunity.
 9. Qwen failure does not break API.
10. Gemini failure uses deterministic fallback.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db.models import CareerPreference, Profile, ProfileSkill, User
from app.main import app
from app.schemas.career_matching import (
    CareerMatchBreakdown,
    CareerMatchingResponse,
    CareerMatchResult,
    ExperienceMatch,
    LocationMatch,
    TargetRoleMatch,
)
from app.schemas.career_matching_api import (
    CareerMatchingAPIResponse,
    CareerMatchingCacheInfo,
    CareerMatchingFinalResult,
    MatchExplanation,
)
from app.schemas.gemini_reranking import CareerMatchRerankedResult, CareerMatchingWithRerankResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user(user_id: str = "user-abc") -> User:
    return User(id=user_id, username="testuser", email="test@example.com")


def _profile(user_id: str = "user-abc") -> Profile:
    profile = Profile(id="profile-1", user_id=user_id, location="Mumbai, India")
    profile.skills = [
        ProfileSkill(name="Python", normalized_name="python"),
        ProfileSkill(name="FastAPI", normalized_name="fastapi"),
    ]
    profile.projects = []
    profile.experience = []
    profile.career_preferences = CareerPreference(
        target_job_role="Backend Engineer",
        preferred_work_type="Remote",
        preferred_locations=json.dumps(["Remote - India"]),
    )
    return profile


def _breakdown() -> CareerMatchBreakdown:
    return CareerMatchBreakdown(
        required_skill_score=80.0,
        preferred_skill_score=70.0,
        target_role_score=100.0,
        experience_score=75.0,
        location_remote_score=100.0,
        career_preference_score=90.0,
        matched_required_skills=["Python"],
        missing_required_skills=["Kubernetes"],
        matched_preferred_skills=["FastAPI"],
        missing_preferred_skills=["AWS"],
        target_role_match=TargetRoleMatch(
            user_target_roles=["Backend Engineer"],
            opportunity_target_role="Backend Engineer",
            relationship="exact",
            score=100.0,
        ),
        experience_match=ExperienceMatch(
            user_level="Entry Level",
            opportunity_level="Junior",
            relationship="adjacent",
            score=75.0,
        ),
        location_match=LocationMatch(
            profile_location="Mumbai, India",
            preferred_locations=["Remote - India"],
            preferred_work_type="Remote",
            opportunity_location="Remote - India",
            opportunity_is_remote=True,
            relationship="remote_matches_or_no_preference",
            score=100.0,
        ),
        preference_matches=[],
    )


def _reranked_result(index: int, score: float = 88.5) -> CareerMatchRerankedResult:
    return CareerMatchRerankedResult(
        opportunity_id=f"opp-{index:02d}",
        title=f"Backend Engineer {index}",
        company="BackendCo",
        final_score=score,
        breakdown=_breakdown(),
        semantic_rank=index,
        rerank_reason=f"Good semantic fit for opp-{index:02d}",
        confidence="high",
    )


def _rerank_response(count: int = 5) -> CareerMatchingWithRerankResponse:
    deterministic = CareerMatchingResponse(
        profile_id="profile-1",
        candidates_considered=30,
        candidates_after_filters=10,
        results=[
            CareerMatchResult(
                opportunity_id=f"opp-{i:02d}",
                title=f"Backend Engineer {i}",
                company="BackendCo",
                final_score=round(90.0 - i, 2),
                breakdown=_breakdown(),
            )
            for i in range(1, 11)
        ],
    )
    return CareerMatchingWithRerankResponse(
        deterministic_results=deterministic.results,
        final_results=[_reranked_result(i) for i in range(1, count + 1)],
        gemini_status="success",
        used_deterministic_fallback=False,
    )


def _final_result(index: int, explanation: MatchExplanation | None = None) -> CareerMatchingFinalResult:
    return CareerMatchingFinalResult(
        opportunity_id=f"opp-{index:02d}",
        title=f"Backend Engineer {index}",
        company="BackendCo",
        location="Remote - India",
        is_remote=True,
        opportunity_type="job",
        target_role="Backend Engineer",
        experience_level="Junior",
        industry="Technology",
        deterministic_score=88.5,
        breakdown=_breakdown(),
        semantic_rank=index,
        rerank_reason=f"Good semantic fit for opp-{index:02d}",
        confidence="high",
        explanation=explanation,
    )


def _api_response(
    count: int = 5,
    gemini_status: str = "success",
    qwen_status: str = "success",
    used_fallback: bool = False,
    explanations: dict[str, MatchExplanation] | None = None,
) -> CareerMatchingAPIResponse:
    def _expl(i: int) -> MatchExplanation | None:
        if explanations is not None:
            return explanations.get(f"opp-{i:02d}")
        return MatchExplanation(
            why_match="Strong Python/FastAPI skills match.",
            strengths=["Python", "FastAPI"],
            skill_gaps=["Kubernetes"],
            recommendation="Learn Kubernetes.",
            match_summary="Strong Match",
        )

    return CareerMatchingAPIResponse(
        status="success",
        target_role="Backend Engineer",
        deterministic_results=[],
        final_results=[_final_result(i, _expl(i)) for i in range(1, count + 1)],
        gemini_status=gemini_status,  # type: ignore[arg-type]
        qwen_status=qwen_status,  # type: ignore[arg-type]
        used_deterministic_fallback=used_fallback,
        used_qwen_fallback=(qwen_status != "success"),
        cache=CareerMatchingCacheInfo(hit=False),
    )


# ---------------------------------------------------------------------------
# FastAPI TestClient with overridden dependencies
# ---------------------------------------------------------------------------

from app.api.deps import get_current_user, get_db


def _override_db():
    """Provide a no-op DB session mock."""
    yield MagicMock()


def _make_client(user: User | None = None) -> TestClient:
    """
    Build a TestClient; if user is None the auth dependency raises 401.
    Overrides DB with a mock to avoid real PostgreSQL.
    """
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    else:
        # Remove any prior override so real get_current_user raises 401
        app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides[get_db] = _override_db
    return TestClient(app, raise_server_exceptions=False)


def _cleanup():
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Test 1 — Authenticated user receives career matching response
# ---------------------------------------------------------------------------

def test_authenticated_user_receives_response():
    user = _user()
    client = _make_client(user)
    expected = _api_response()
    try:
        with patch(
            "app.api.career_matching.run_career_matching_pipeline",
            new=AsyncMock(return_value=expected),
        ):
            response = client.get("/api/career-matching/me")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"
        assert len(body["final_results"]) == 5
        assert body["target_role"] == "Backend Engineer"
    finally:
        _cleanup()


# ---------------------------------------------------------------------------
# Test 2 — Unauthenticated request is rejected
# ---------------------------------------------------------------------------

def test_unauthenticated_request_rejected():
    # Remove any user override so real 401 logic fires
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app, raise_server_exceptions=False)
    try:
        response = client.get("/api/career-matching/me")
        assert response.status_code == 401
    finally:
        _cleanup()


# ---------------------------------------------------------------------------
# Test 3 — User ID comes from JWT (not from request body/query)
# ---------------------------------------------------------------------------

def test_user_id_comes_from_jwt(monkeypatch):
    """The pipeline is called with the authenticated user from the JWT dependency."""
    user = _user("jwt-extracted-user-id")
    client = _make_client(user)
    captured: list[User] = []

    async def _capture(db, user: User, include_ai: bool = True) -> CareerMatchingAPIResponse:
        captured.append(user)
        return _api_response()

    try:
        with patch("app.api.career_matching.run_career_matching_pipeline", new=_capture):
            response = client.get("/api/career-matching/me")
        assert response.status_code == 200
        assert len(captured) == 1
        assert captured[0].id == "jwt-extracted-user-id"
    finally:
        _cleanup()


# ---------------------------------------------------------------------------
# Test 4 — Frontend cannot request another user's matching results
# ---------------------------------------------------------------------------

def test_frontend_cannot_request_other_users_results():
    """
    The endpoint has no user_id parameter — the authenticated user is always used.
    Even if query params are passed they are ignored.
    """
    user = _user("my-user-id")
    client = _make_client(user)
    captured: list[str] = []

    async def _capture(db, user: User, include_ai: bool = True) -> CareerMatchingAPIResponse:
        captured.append(user.id)
        return _api_response()

    try:
        with patch("app.api.career_matching.run_career_matching_pipeline", new=_capture):
            # Attempt to sneak someone else's user_id as a query param — must be ignored
            response = client.get("/api/career-matching/me?user_id=other-user-id")
        assert response.status_code == 200
        assert len(captured) == 1
        assert captured[0] == "my-user-id"
    finally:
        _cleanup()


# ---------------------------------------------------------------------------
# Test 5 — Final results contain at most 5 opportunities
# ---------------------------------------------------------------------------

def test_final_results_at_most_5():
    user = _user()
    client = _make_client(user)
    expected = _api_response(count=5)
    try:
        with patch(
            "app.api.career_matching.run_career_matching_pipeline",
            new=AsyncMock(return_value=expected),
        ):
            response = client.get("/api/career-matching/me")
        assert response.status_code == 200
        assert len(response.json()["final_results"]) <= 5
    finally:
        _cleanup()


# ---------------------------------------------------------------------------
# Test 6 — Deterministic score remains unchanged
# ---------------------------------------------------------------------------

def test_deterministic_score_is_preserved():
    user = _user()
    client = _make_client(user)
    expected = _api_response()
    try:
        with patch(
            "app.api.career_matching.run_career_matching_pipeline",
            new=AsyncMock(return_value=expected),
        ):
            response = client.get("/api/career-matching/me")
        assert response.status_code == 200
        for result in response.json()["final_results"]:
            assert result["deterministic_score"] == 88.5
            assert result["breakdown"]["required_skill_score"] == 80.0
            assert result["breakdown"]["preferred_skill_score"] == 70.0
            assert result["breakdown"]["target_role_score"] == 100.0
    finally:
        _cleanup()


# ---------------------------------------------------------------------------
# Test 7 — Gemini metadata remains attached
# ---------------------------------------------------------------------------

def test_gemini_metadata_attached():
    user = _user()
    client = _make_client(user)
    expected = _api_response(gemini_status="success")
    try:
        with patch(
            "app.api.career_matching.run_career_matching_pipeline",
            new=AsyncMock(return_value=expected),
        ):
            response = client.get("/api/career-matching/me")
        assert response.status_code == 200
        body = response.json()
        assert body["gemini_status"] == "success"
        for result in body["final_results"]:
            assert "semantic_rank" in result
            assert "rerank_reason" in result
            assert "confidence" in result
    finally:
        _cleanup()


# ---------------------------------------------------------------------------
# Test 8 — Qwen explanation attaches to the correct opportunity
# ---------------------------------------------------------------------------

def test_qwen_explanation_attaches_to_correct_opportunity():
    user = _user()
    client = _make_client(user)
    explanations = {
        "opp-01": MatchExplanation(
            why_match="First match.",
            strengths=["Python"],
            skill_gaps=[],
            recommendation="Continue learning.",
            match_summary="Strong Match",
        ),
        "opp-02": MatchExplanation(
            why_match="Second match.",
            strengths=["FastAPI"],
            skill_gaps=["Docker"],
            recommendation="Learn Docker.",
            match_summary="Good Match",
        ),
    }
    expected = _api_response(count=2, explanations=explanations)
    try:
        with patch(
            "app.api.career_matching.run_career_matching_pipeline",
            new=AsyncMock(return_value=expected),
        ):
            response = client.get("/api/career-matching/me")
        assert response.status_code == 200
        final = response.json()["final_results"]
        by_id = {r["opportunity_id"]: r for r in final}

        assert by_id["opp-01"]["explanation"]["why_match"] == "First match."
        assert by_id["opp-01"]["explanation"]["match_summary"] == "Strong Match"
        assert by_id["opp-02"]["explanation"]["why_match"] == "Second match."
        assert by_id["opp-02"]["explanation"]["match_summary"] == "Good Match"
        # Cross-contamination check
        assert by_id["opp-01"]["explanation"]["strengths"] == ["Python"]
        assert by_id["opp-02"]["explanation"]["strengths"] == ["FastAPI"]
    finally:
        _cleanup()


# ---------------------------------------------------------------------------
# Test 9 — Qwen failure does not break API
# ---------------------------------------------------------------------------

def test_qwen_failure_does_not_break_api():
    user = _user()
    client = _make_client(user)
    # Simulate pipeline where Qwen failed
    expected = _api_response(qwen_status="unavailable", explanations={})
    expected.used_qwen_fallback = True
    for result in expected.final_results:
        result.explanation = None
    try:
        with patch(
            "app.api.career_matching.run_career_matching_pipeline",
            new=AsyncMock(return_value=expected),
        ):
            response = client.get("/api/career-matching/me")
        assert response.status_code == 200
        body = response.json()
        assert body["qwen_status"] == "unavailable"
        assert body["used_qwen_fallback"] is True
        # Final results still present, just without explanation
        assert len(body["final_results"]) == 5
        for result in body["final_results"]:
            assert result["explanation"] is None
    finally:
        _cleanup()


# ---------------------------------------------------------------------------
# Test 10 — Gemini failure uses deterministic fallback
# ---------------------------------------------------------------------------

def test_gemini_failure_uses_deterministic_fallback():
    user = _user()
    client = _make_client(user)
    # Simulate pipeline where Gemini failed → used_deterministic_fallback=True
    expected = _api_response(gemini_status="unavailable", used_fallback=True)
    try:
        with patch(
            "app.api.career_matching.run_career_matching_pipeline",
            new=AsyncMock(return_value=expected),
        ):
            response = client.get("/api/career-matching/me")
        assert response.status_code == 200
        body = response.json()
        assert body["gemini_status"] == "unavailable"
        assert body["used_deterministic_fallback"] is True
        # Final results still at most 5
        assert len(body["final_results"]) <= 5
    finally:
        _cleanup()
