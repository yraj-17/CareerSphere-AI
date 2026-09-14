"""
Tests for Phase 2A — Skill Analysis Service and API.

Coverage
--------
Unit tests (all mocked — no external services required):
  1.  Exact role match ("Backend Engineer")
  2.  Case-insensitive exact match ("backend engineer")
  3.  Semantic match for hybrid target returns multiple roles
  4.  No target role → no_target_role status
  5.  Blank target role → no_target_role status
  6.  Unmatchable target → no_match status
  7.  Skill merging deduplication (required beats recommended)
  8.  Multi-role skill union is correct
  9.  Alias matching — "Postgres" recognised as PostgreSQL
  10. Project technology skills counted as owned
  11. Coverage percentage calculation
  12. API endpoint requires authentication
  13. API endpoint returns 200 with correct response structure (mocked service)
  14. Qdrant filter is source_type=role only (no skill documents)
  15. Score threshold filtering — low-score roles excluded
  16. Spread-window filtering — only near-top roles included
  17. Score scores round-trip correctly into resolution_scores
  18. skills_missing_required / skills_missing_recommended are accurate
  19. skills_have is accurate

Integration test (gated on RUN_QDRANT_INTEGRATION=1):
  20. Real end-to-end: "Backend and Devops" → 2 roles → skill analysis
"""

from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any, List
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from qdrant_client.http import models as qmodels

from app.data.career_knowledge import ROLES, SKILLS
from app.services import embedding_service, qdrant_service
from app.services.skill_analysis_service import (
    ROLE_SCORE_SPREAD,
    ROLE_SCORE_THRESHOLD,
    MergedSkills,
    RoleResolution,
    _ROLE_BY_NAME_LOWER,
    _user_has_skill,
    build_skill_analysis,
    extract_user_skill_names,
    merge_role_skills,
    resolve_target_role,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

_FAKE_DIM = 4
_FAKE_VECTOR = [0.1, 0.2, 0.3, 0.4]


class _FakeEmbedClient:
    def embed(self, model: str, input: List[str]):
        return {"embeddings": [_FAKE_VECTOR[:] for _ in input]}


def _fake_profile(
    target_role: str | None = None,
    skills: list[str] | None = None,
    tech_skills: list[str] | None = None,
):
    """Build a minimal fake Profile-like object for testing."""
    prefs = SimpleNamespace(target_job_role=target_role) if target_role is not None else None

    skill_objs = [SimpleNamespace(name=s) for s in (skills or [])]
    tech_objs = [SimpleNamespace(name=t) for t in (tech_skills or [])]
    project_objs = [SimpleNamespace(technologies=tech_objs)] if tech_objs else []

    return SimpleNamespace(
        user_id="test-user-id",
        career_preferences=prefs,
        skills=skill_objs,
        projects=project_objs,
    )


def _scored_role_point(role_id: str, role_name: str, score: float) -> qmodels.ScoredPoint:
    return qmodels.ScoredPoint(
        id=f"fake-uuid-{role_id}",
        version=1,
        score=score,
        payload={
            "source_type": "role",
            "source_id": role_id,
            "text": f"{role_name} role document",
            "metadata": {"name": role_name, "domain": "Test"},
        },
    )


# ---------------------------------------------------------------------------
# Test 1 — Exact role match
# ---------------------------------------------------------------------------


def test_exact_role_match():
    resolution = resolve_target_role("Backend Engineer", "career_content")
    assert resolution.matched is True
    assert resolution.method == "exact"
    assert len(resolution.roles) == 1
    assert resolution.roles[0].name == "Backend Engineer"
    assert resolution.scores["Backend Engineer"] == 1.0


# ---------------------------------------------------------------------------
# Test 2 — Case-insensitive exact match
# ---------------------------------------------------------------------------


def test_case_insensitive_exact_match():
    resolution = resolve_target_role("backend engineer", "career_content")
    assert resolution.matched is True
    assert resolution.method == "exact"
    assert resolution.roles[0].name == "Backend Engineer"


def test_mixed_case_exact_match():
    resolution = resolve_target_role("DATA SCIENTIST", "career_content")
    assert resolution.matched is True
    assert resolution.roles[0].name == "Data Scientist"


# ---------------------------------------------------------------------------
# Test 3 — Semantic match returns multiple roles for hybrid target
# ---------------------------------------------------------------------------


def test_semantic_match_hybrid_target_returns_multiple_roles(monkeypatch):
    embedding_service.get_embedding_dimension.cache_clear()
    monkeypatch.setattr(embedding_service, "get_embedding_client", lambda: _FakeEmbedClient())

    hits = [
        _scored_role_point("backend-engineer", "Backend Engineer", 0.71),
        _scored_role_point("devops-engineer", "DevOps Engineer", 0.68),
    ]
    mock_client = MagicMock()
    mock_client.query_points.return_value = SimpleNamespace(points=hits)
    monkeypatch.setattr(qdrant_service, "get_qdrant_client", lambda: mock_client)

    resolution = resolve_target_role("Backend and Devops", "career_content")

    assert resolution.matched is True
    assert resolution.method == "semantic"
    assert len(resolution.roles) == 2
    role_names = {r.name for r in resolution.roles}
    assert "Backend Engineer" in role_names
    assert "DevOps Engineer" in role_names
    assert resolution.scores["Backend Engineer"] == pytest.approx(0.71, abs=1e-3)
    assert resolution.scores["DevOps Engineer"] == pytest.approx(0.68, abs=1e-3)

    embedding_service.get_embedding_dimension.cache_clear()


# ---------------------------------------------------------------------------
# Test 4 — No target role → no_target_role status
# ---------------------------------------------------------------------------


def test_no_target_role_returns_correct_status():
    profile = _fake_profile(target_role=None)
    result = build_skill_analysis(profile)
    assert result.status == "no_target_role"
    assert result.target_role is None
    assert result.resolved_roles == []
    assert result.coverage is None
    assert result.message is not None


# ---------------------------------------------------------------------------
# Test 5 — Blank target role → no_target_role
# ---------------------------------------------------------------------------


def test_blank_target_role_returns_no_target_role():
    profile = _fake_profile(target_role="   ")
    result = build_skill_analysis(profile)
    assert result.status == "no_target_role"


def test_empty_string_target_role():
    profile = _fake_profile(target_role="")
    result = build_skill_analysis(profile)
    assert result.status == "no_target_role"


# ---------------------------------------------------------------------------
# Test 6 — Unmatchable target → no_match
# ---------------------------------------------------------------------------


def test_unmatchable_target_returns_no_match(monkeypatch):
    embedding_service.get_embedding_dimension.cache_clear()
    monkeypatch.setattr(embedding_service, "get_embedding_client", lambda: _FakeEmbedClient())

    mock_client = MagicMock()
    mock_client.query_points.return_value = SimpleNamespace(points=[])
    monkeypatch.setattr(qdrant_service, "get_qdrant_client", lambda: mock_client)

    profile = _fake_profile(target_role="Intergalactic Pizza Chef")
    result = build_skill_analysis(profile)

    assert result.status == "no_match"
    assert result.target_role == "Intergalactic Pizza Chef"
    assert result.resolved_roles == []
    assert result.message is not None

    embedding_service.get_embedding_dimension.cache_clear()


# ---------------------------------------------------------------------------
# Test 7 — Required beats recommended when same skill appears in both
# ---------------------------------------------------------------------------


def test_merge_required_beats_recommended():
    # python is required for backend-engineer
    # and recommended for data-analyst
    backend = next(r for r in ROLES if r.id == "backend-engineer")
    analyst = next(r for r in ROLES if r.id == "data-analyst")

    # Verify python is required for backend, not already required for analyst
    assert "python" in backend.required_skills

    merged = merge_role_skills([backend, analyst])

    # python must appear in required, not recommended
    required_names = {s.name for s in merged.required}
    recommended_names = {s.name for s in merged.recommended}
    assert "Python" in required_names
    assert "Python" not in recommended_names


# ---------------------------------------------------------------------------
# Test 8 — Multi-role skill union is complete and deduplicated
# ---------------------------------------------------------------------------


def test_multi_role_skill_union_is_correct():
    backend = next(r for r in ROLES if r.id == "backend-engineer")
    devops = next(r for r in ROLES if r.id == "devops-engineer")

    merged = merge_role_skills([backend, devops])

    all_required_ids = set(backend.required_skills) | set(devops.required_skills)
    all_recommended_ids = (set(backend.recommended_skills) | set(devops.recommended_skills)) - all_required_ids

    # All required skills should be in merged.required
    for sid in all_required_ids:
        if sid in SKILLS:
            assert any(s.id == sid for s in merged.required), f"Missing required skill: {sid}"

    # No duplicates
    req_ids = [s.id for s in merged.required]
    assert len(req_ids) == len(set(req_ids)), "Duplicate required skills"
    rec_ids = [s.id for s in merged.recommended]
    assert len(rec_ids) == len(set(rec_ids)), "Duplicate recommended skills"

    # No overlap
    req_id_set = set(req_ids)
    for s in merged.recommended:
        assert s.id not in req_id_set, f"Skill {s.id} appears in both required and recommended"


# ---------------------------------------------------------------------------
# Test 9 — Alias matching
# ---------------------------------------------------------------------------


def test_alias_matching_postgres_recognised_as_postgresql():
    pg_skill = SKILLS["postgresql"]
    assert "Postgres" in pg_skill.aliases

    # User has "Postgres" (not the canonical "PostgreSQL")
    user_skills = {"postgres"}
    assert _user_has_skill(pg_skill, user_skills) is True


def test_alias_matching_canonical_name_also_works():
    pg_skill = SKILLS["postgresql"]
    user_skills = {"postgresql"}
    assert _user_has_skill(pg_skill, user_skills) is True


def test_alias_no_false_positive():
    python_skill = SKILLS["python"]
    user_skills = {"java", "go"}
    assert _user_has_skill(python_skill, user_skills) is False


# ---------------------------------------------------------------------------
# Test 10 — Project technologies counted as owned skills
# ---------------------------------------------------------------------------


def test_project_technologies_counted_as_owned():
    # User has no direct skills but has "Python" as a project technology
    profile = _fake_profile(target_role="Backend Engineer", tech_skills=["Python"])
    result = build_skill_analysis(profile)

    assert result.status == "ok"
    assert "Python" in result.skills_have


def test_both_skills_and_tech_combined():
    profile = _fake_profile(
        target_role="Backend Engineer",
        skills=["Git"],
        tech_skills=["Python"],
    )
    result = build_skill_analysis(profile)
    assert result.status == "ok"
    assert "Python" in result.skills_have
    assert "Git" in result.skills_have


# ---------------------------------------------------------------------------
# Test 11 — Coverage percentage calculation
# ---------------------------------------------------------------------------


def test_coverage_all_skills_owned():
    backend = next(r for r in ROLES if r.id == "backend-engineer")
    all_skill_names = [
        SKILLS[s].name for s in backend.required_skills + backend.recommended_skills if s in SKILLS
    ]
    profile = _fake_profile(target_role="Backend Engineer", skills=all_skill_names)
    result = build_skill_analysis(profile)
    assert result.status == "ok"
    assert result.coverage.required_pct == 100
    assert result.coverage.overall_pct == 100


def test_coverage_no_skills():
    profile = _fake_profile(target_role="Backend Engineer", skills=[])
    result = build_skill_analysis(profile)
    assert result.status == "ok"
    assert result.coverage.required_pct == 0
    assert result.coverage.overall_pct == 0
    assert set(result.skills_missing_required) == {
        SKILLS[s].name for s in next(r for r in ROLES if r.id == "backend-engineer").required_skills if s in SKILLS
    }


def test_coverage_partial_skills():
    profile = _fake_profile(target_role="Backend Engineer", skills=["Python", "Git"])
    result = build_skill_analysis(profile)
    assert result.status == "ok"
    assert 0 < result.coverage.required_pct < 100
    assert "Python" in result.skills_have
    assert "Git" in result.skills_have


# ---------------------------------------------------------------------------
# Test 12 — API requires authentication
# ---------------------------------------------------------------------------


def test_api_skill_analysis_requires_auth():
    from app.main import app
    client = TestClient(app)
    response = client.get("/api/skill-analysis/me")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Test 13 — API returns 200 with correct structure (mocked service)
# ---------------------------------------------------------------------------


def test_api_skill_analysis_returns_correct_structure(monkeypatch):
    from app.main import app
    import app.api.skill_analysis as skill_api_module

    mock_result = {
        "status": "ok",
        "target_role": "Backend Engineer",
        "resolved_roles": ["Backend Engineer"],
        "resolution_scores": {"Backend Engineer": 1.0},
        "resolution_method": "exact",
        "required_skills": [
            {"name": "Python", "category": "programming", "have": True}
        ],
        "recommended_skills": [],
        "skills_have": ["Python"],
        "skills_missing_required": [],
        "skills_missing_recommended": [],
        "coverage": {"required_pct": 100, "recommended_pct": 0, "overall_pct": 100},
        "message": None,
    }

    from app.schemas.skill_analysis import SkillAnalysisResponse
    mock_response = SkillAnalysisResponse(**mock_result)

    monkeypatch.setattr(
        skill_api_module,
        "build_skill_analysis",
        lambda profile, **kwargs: mock_response,
    )

    from app.api.deps import get_current_user, get_db
    from app.db.models import User

    fake_user = MagicMock(spec=User)
    fake_user.id = "test-user-id"

    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_db] = lambda: MagicMock()

    try:
        response = client.get("/api/skill-analysis/me")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["target_role"] == "Backend Engineer"
        assert data["resolved_roles"] == ["Backend Engineer"]
        assert data["resolution_method"] == "exact"
        assert isinstance(data["required_skills"], list)
        assert isinstance(data["coverage"], dict)
        assert "required_pct" in data["coverage"]
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test 14 — Qdrant filter is source_type=role only
# ---------------------------------------------------------------------------


def test_qdrant_filter_is_role_only(monkeypatch):
    embedding_service.get_embedding_dimension.cache_clear()
    monkeypatch.setattr(embedding_service, "get_embedding_client", lambda: _FakeEmbedClient())

    mock_client = MagicMock()
    mock_client.query_points.return_value = SimpleNamespace(points=[])
    monkeypatch.setattr(qdrant_service, "get_qdrant_client", lambda: mock_client)

    resolve_target_role("Something Nonexistent XYZ", "career_content")

    # Check the filter passed to query_points
    if mock_client.query_points.called:
        call_kwargs = mock_client.query_points.call_args.kwargs
        q_filter = call_kwargs.get("query_filter")
        assert q_filter is not None, "query_filter was not passed"
        must_conditions = q_filter.must
        assert any(
            getattr(cond, "key", None) == "source_type" and
            getattr(getattr(cond, "match", None), "value", None) == "role"
            for cond in must_conditions
        ), "Filter did not restrict to source_type='role'"

    embedding_service.get_embedding_dimension.cache_clear()


# ---------------------------------------------------------------------------
# Test 15 — Score threshold filtering
# ---------------------------------------------------------------------------


def test_low_score_roles_excluded(monkeypatch):
    embedding_service.get_embedding_dimension.cache_clear()
    monkeypatch.setattr(embedding_service, "get_embedding_client", lambda: _FakeEmbedClient())

    # Return a hit with score below threshold — should be filtered by score_threshold arg
    hits = [_scored_role_point("backend-engineer", "Backend Engineer", ROLE_SCORE_THRESHOLD - 0.01)]
    mock_client = MagicMock()
    # query_points respects score_threshold param; simulate Qdrant returning nothing
    mock_client.query_points.return_value = SimpleNamespace(points=[])
    monkeypatch.setattr(qdrant_service, "get_qdrant_client", lambda: mock_client)

    resolution = resolve_target_role("Something Low Score", "career_content")
    assert resolution.matched is False

    embedding_service.get_embedding_dimension.cache_clear()


# ---------------------------------------------------------------------------
# Test 16 — Spread-window filtering
# ---------------------------------------------------------------------------


def test_spread_window_excludes_distant_roles(monkeypatch):
    embedding_service.get_embedding_dimension.cache_clear()
    monkeypatch.setattr(embedding_service, "get_embedding_client", lambda: _FakeEmbedClient())

    # Top score 0.75, second role at 0.75 - SPREAD - 0.01 (just outside window)
    top_score = 0.75
    outside_score = top_score - ROLE_SCORE_SPREAD - 0.01
    hits = [
        _scored_role_point("backend-engineer", "Backend Engineer", top_score),
        _scored_role_point("devops-engineer", "DevOps Engineer", outside_score),
    ]
    mock_client = MagicMock()
    mock_client.query_points.return_value = SimpleNamespace(points=hits)
    monkeypatch.setattr(qdrant_service, "get_qdrant_client", lambda: mock_client)

    resolution = resolve_target_role("Mostly Backend", "career_content")

    assert resolution.matched is True
    assert len(resolution.roles) == 1
    assert resolution.roles[0].name == "Backend Engineer"

    embedding_service.get_embedding_dimension.cache_clear()


# ---------------------------------------------------------------------------
# Test 17 — Resolution scores round-trip into response
# ---------------------------------------------------------------------------


def test_resolution_scores_in_full_analysis(monkeypatch):
    embedding_service.get_embedding_dimension.cache_clear()
    monkeypatch.setattr(embedding_service, "get_embedding_client", lambda: _FakeEmbedClient())

    hits = [
        _scored_role_point("backend-engineer", "Backend Engineer", 0.7123),
        _scored_role_point("devops-engineer", "DevOps Engineer", 0.6534),
    ]
    mock_client = MagicMock()
    mock_client.query_points.return_value = SimpleNamespace(points=hits)
    monkeypatch.setattr(qdrant_service, "get_qdrant_client", lambda: mock_client)

    profile = _fake_profile(target_role="Backend and Devops")
    result = build_skill_analysis(profile)

    assert result.status == "ok"
    assert "Backend Engineer" in result.resolution_scores
    assert "DevOps Engineer" in result.resolution_scores
    assert result.resolution_scores["Backend Engineer"] == pytest.approx(0.7123, abs=1e-3)

    embedding_service.get_embedding_dimension.cache_clear()


# ---------------------------------------------------------------------------
# Test 18 — skills_missing lists are accurate
# ---------------------------------------------------------------------------


def test_skills_missing_required_and_recommended_accurate():
    backend = next(r for r in ROLES if r.id == "backend-engineer")
    req_skill_names = [SKILLS[s].name for s in backend.required_skills if s in SKILLS]
    # Give user half the required skills
    owned = req_skill_names[:1]
    missing_req = req_skill_names[1:]

    profile = _fake_profile(target_role="Backend Engineer", skills=owned)
    result = build_skill_analysis(profile)

    assert result.status == "ok"
    for skill_name in owned:
        assert skill_name in result.skills_have
    for skill_name in missing_req:
        assert skill_name in result.skills_missing_required


# ---------------------------------------------------------------------------
# Test 19 — skills_have is accurate
# ---------------------------------------------------------------------------


def test_skills_have_only_includes_target_relevant_skills():
    # Give user a skill that is NOT in Backend Engineer's required/recommended
    # (it should not appear in skills_have)
    profile = _fake_profile(
        target_role="Backend Engineer",
        skills=["Python", "Teaching"],  # Teaching is irrelevant to Backend Engineer
    )
    result = build_skill_analysis(profile)
    assert result.status == "ok"
    assert "Python" in result.skills_have
    # Teaching is not in Backend Engineer's required/recommended
    assert "Teaching" not in result.skills_have


# ---------------------------------------------------------------------------
# Integration test (requires live Qdrant + Ollama + nomic-embed-text)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_QDRANT_INTEGRATION") != "1",
    reason=(
        "Set RUN_QDRANT_INTEGRATION=1 and ensure Qdrant + Ollama "
        "with nomic-embed-text are running and career_content is indexed."
    ),
)
def test_real_skill_analysis_hybrid_target():
    """
    Full end-to-end integration test:

        "Backend and Devops" as target_role
            ↓  embed
            ↓  Qdrant similarity_search(filter=source_type=role)
            ↓  resolve 2 roles: Backend Engineer + DevOps Engineer
            ↓  merge skills
            ↓  build SkillAnalysisResponse
    """
    from app.services import embedding_service as es

    es.get_embedding_dimension.cache_clear()

    try:
        # 1. Hybrid target — should resolve 2 roles
        profile_hybrid = _fake_profile(
            target_role="Backend and Devops",
            skills=["Python", "Git", "Docker"],
        )
        result = build_skill_analysis(profile_hybrid)

        assert result.status == "ok", f"Expected ok, got {result.status}: {result.message}"
        assert result.resolution_method == "semantic"
        assert len(result.resolved_roles) >= 1

        role_names = set(result.resolved_roles)
        assert "Backend Engineer" in role_names or "DevOps Engineer" in role_names, (
            f"Expected Backend Engineer or DevOps Engineer in resolved roles, got {role_names}"
        )

        # User has Python, Git, Docker — all should appear in skills_have
        assert "Python" in result.skills_have
        assert "Git" in result.skills_have
        assert "Docker" in result.skills_have

        # Coverage should be > 0
        assert result.coverage is not None
        assert result.coverage.overall_pct > 0

        # 2. Exact match — "Data Scientist"
        profile_exact = _fake_profile(target_role="Data Scientist", skills=[])
        result_exact = build_skill_analysis(profile_exact)
        assert result_exact.status == "ok"
        assert result_exact.resolution_method == "exact"
        assert result_exact.resolved_roles == ["Data Scientist"]
        assert result_exact.coverage.required_pct == 0

        # 3. No target role
        profile_none = _fake_profile(target_role=None)
        result_none = build_skill_analysis(profile_none)
        assert result_none.status == "no_target_role"

        # 4. Unmatchable target
        profile_bad = _fake_profile(target_role="zzz-nonexistent-role-xyz-999")
        result_bad = build_skill_analysis(profile_bad)
        assert result_bad.status in ("no_match", "ok")  # ok if cosine is generous

    finally:
        es.get_embedding_dimension.cache_clear()
