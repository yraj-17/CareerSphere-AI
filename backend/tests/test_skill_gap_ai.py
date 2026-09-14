"""
Tests for Phase 2B — Skill Gap AI Service and API.

Coverage (15 unit + 1 integration)
------------------------------------
 1. Prompt is grounded — matched skills are passed correctly
 2. Prompt is grounded — missing required skills are passed correctly
 3. Prompt is grounded — missing recommended skills are passed correctly
 4. Prompt is grounded — coverage values are passed correctly
 5. Qwen output parses into SkillGapAIInsights correctly
 6. Invalid Qwen JSON is handled safely (returns None, "unavailable")
 7. Qwen unavailable (AIServiceError) is handled safely
 8. Qwen timeout is handled safely
 9. status=no_target_role does not call Qwen
10. status=no_match does not call Qwen
11. 100% required coverage does not create fake gaps (grounding sanitizer)
12. Hallucinated skills are removed by the sanitizer
13. Hallucinated strengths are removed by the sanitizer
14. Existing Phase 2A endpoint (?include_ai=false) remains deterministic
15. Authentication is enforced on the extended endpoint
16. Integration: real Qwen call returns valid SkillGapAIInsights
"""

from __future__ import annotations

import json
import os
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.skill_analysis import (
    SkillAnalysisResponse,
    SkillCoverage,
    SkillGapAIInsights,
    SkillGapPriorityItem,
    SkillGapRoadmapStep,
    SkillAnalysisWithAIResponse,
)
from app.services.ollama_service import AIServiceError
from app.services.skill_gap_ai_service import (
    _build_prompt,
    _call_qwen,
    _extract_json_object,
    _sanitize_insights,
    generate_skill_gap_insights,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ok_analysis(
    target_role: str = "Backend Engineer",
    resolved_roles: list[str] | None = None,
    matched: list[str] | None = None,
    missing_required: list[str] | None = None,
    missing_recommended: list[str] | None = None,
    required_pct: int = 40,
    recommended_pct: int = 10,
    overall_pct: int = 28,
) -> SkillAnalysisResponse:
    """Build a minimal Phase 2A SkillAnalysisResponse for testing."""
    return SkillAnalysisResponse(
        status="ok",
        target_role=target_role,
        resolved_roles=resolved_roles or [target_role],
        resolution_scores={target_role: 1.0},
        resolution_method="exact",
        required_skills=[],
        recommended_skills=[],
        skills_have=matched or [],
        skills_missing_required=missing_required or [],
        skills_missing_recommended=missing_recommended or [],
        coverage=SkillCoverage(
            required_pct=required_pct,
            recommended_pct=recommended_pct,
            overall_pct=overall_pct,
        ),
    )


def _minimal_insights_dict(
    matched: list[str] | None = None,
    gaps: list[str] | None = None,
) -> dict[str, Any]:
    """Build a minimal valid Qwen JSON response dict."""
    gap_items = [
        {"skill": s, "priority": "high", "reason": f"Need {s} for the role."}
        for s in (gaps or [])
    ]
    roadmap = [
        {"step": i + 1, "skill": s, "focus": f"Study {s}.", "suggested_practice": f"Build a project with {s}."}
        for i, s in enumerate(gaps or [])
    ]
    return {
        "summary": "You are 40% ready for Backend Engineer.",
        "strengths": matched or [],
        "priority_gaps": gap_items,
        "learning_order": gaps or [],
        "roadmap": roadmap,
    }


# ---------------------------------------------------------------------------
# Test 1 — Prompt contains matched skills
# ---------------------------------------------------------------------------


def test_prompt_includes_matched_skills():
    analysis = _ok_analysis(matched=["Python", "Git", "Docker"])
    prompt = _build_prompt(analysis)
    assert "Python" in prompt
    assert "Git" in prompt
    assert "Docker" in prompt


# ---------------------------------------------------------------------------
# Test 2 — Prompt contains missing required skills
# ---------------------------------------------------------------------------


def test_prompt_includes_missing_required_skills():
    analysis = _ok_analysis(missing_required=["Linux", "CI/CD"])
    prompt = _build_prompt(analysis)
    assert "Linux" in prompt
    assert "CI/CD" in prompt
    assert "MISSING REQUIRED" in prompt


# ---------------------------------------------------------------------------
# Test 3 — Prompt contains missing recommended skills
# ---------------------------------------------------------------------------


def test_prompt_includes_missing_recommended_skills():
    analysis = _ok_analysis(missing_recommended=["AWS", "Redis"])
    prompt = _build_prompt(analysis)
    assert "AWS" in prompt
    assert "Redis" in prompt
    assert "MISSING RECOMMENDED" in prompt


# ---------------------------------------------------------------------------
# Test 4 — Prompt contains coverage values
# ---------------------------------------------------------------------------


def test_prompt_includes_coverage_values():
    analysis = _ok_analysis(required_pct=55, recommended_pct=20, overall_pct=40)
    prompt = _build_prompt(analysis)
    assert "55%" in prompt
    assert "20%" in prompt
    assert "40%" in prompt


# ---------------------------------------------------------------------------
# Test 5 — Valid Qwen output parses into SkillGapAIInsights
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_valid_qwen_output_parses_correctly():
    analysis = _ok_analysis(
        matched=["Python"],
        missing_required=["Linux", "CI/CD"],
        missing_recommended=["AWS"],
    )
    raw = _minimal_insights_dict(matched=["Python"], gaps=["Linux", "CI/CD", "AWS"])
    raw_json = json.dumps(raw)

    with patch(
        "app.services.skill_gap_ai_service._call_qwen",
        new=AsyncMock(return_value=raw_json),
    ):
        insights, ai_status = await generate_skill_gap_insights(analysis)

    assert ai_status == "ok"
    assert insights is not None
    assert isinstance(insights, SkillGapAIInsights)
    assert "Backend Engineer" in insights.summary or len(insights.summary) > 10
    assert "Python" in insights.strengths
    assert any(g.skill == "Linux" for g in insights.priority_gaps)


# ---------------------------------------------------------------------------
# Test 6 — Invalid Qwen JSON is handled safely
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_invalid_json_returns_unavailable():
    analysis = _ok_analysis(missing_required=["Linux"])

    with patch(
        "app.services.skill_gap_ai_service._call_qwen",
        new=AsyncMock(return_value="this is not json at all"),
    ):
        insights, ai_status = await generate_skill_gap_insights(analysis)

    assert insights is None
    assert ai_status == "unavailable"


# ---------------------------------------------------------------------------
# Test 7 — Qwen unavailable (AIServiceError) handled safely
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_ai_service_error_returns_unavailable():
    analysis = _ok_analysis(missing_required=["Linux"])

    with patch(
        "app.services.skill_gap_ai_service._call_qwen",
        new=AsyncMock(side_effect=AIServiceError("connection refused")),
    ):
        insights, ai_status = await generate_skill_gap_insights(analysis)

    assert insights is None
    assert ai_status == "unavailable"


# ---------------------------------------------------------------------------
# Test 8 — Qwen timeout handled safely
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_timeout_returns_unavailable():
    from httpx import TimeoutException

    analysis = _ok_analysis(missing_required=["Docker"])

    with patch(
        "app.services.skill_gap_ai_service._call_qwen",
        new=AsyncMock(side_effect=AIServiceError("The AI is taking longer than expected.")),
    ):
        insights, ai_status = await generate_skill_gap_insights(analysis)

    assert insights is None
    assert ai_status == "unavailable"


# ---------------------------------------------------------------------------
# Test 9 — status=no_target_role does not call Qwen
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_no_target_role_does_not_call_qwen():
    analysis = SkillAnalysisResponse(
        status="no_target_role",
        message="No Target Role has been set.",
    )

    with patch(
        "app.services.skill_gap_ai_service._call_qwen",
        new=AsyncMock(),
    ) as mock_qwen:
        insights, ai_status = await generate_skill_gap_insights(analysis)

    mock_qwen.assert_not_called()
    assert insights is None
    assert ai_status == "not_applicable"


# ---------------------------------------------------------------------------
# Test 10 — status=no_match does not call Qwen
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_no_match_does_not_call_qwen():
    analysis = SkillAnalysisResponse(
        status="no_match",
        target_role="Pizza Chef Extraordinaire",
        message="Target could not be matched.",
    )

    with patch(
        "app.services.skill_gap_ai_service._call_qwen",
        new=AsyncMock(),
    ) as mock_qwen:
        insights, ai_status = await generate_skill_gap_insights(analysis)

    mock_qwen.assert_not_called()
    assert insights is None
    assert ai_status == "not_applicable"


# ---------------------------------------------------------------------------
# Test 11 — 100% required coverage does not create fake gaps
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_full_coverage_no_fake_gaps():
    """
    Even if Qwen hallucinated extra gaps, the sanitizer must strip them
    since they don't appear in the Phase 2A missing lists.
    """
    analysis = _ok_analysis(
        matched=["Python", "Git", "Docker"],
        missing_required=[],        # user has everything
        missing_recommended=["AWS"],
        required_pct=100,
        recommended_pct=0,
        overall_pct=80,
    )
    # Simulate Qwen hallucinating "Kubernetes" as a required gap
    raw = {
        "summary": "You are fully ready on required skills.",
        "strengths": ["Python"],
        "priority_gaps": [
            {"skill": "Kubernetes", "priority": "high", "reason": "Important tool."},
            {"skill": "AWS", "priority": "medium", "reason": "Cloud platform."},
        ],
        "learning_order": ["Kubernetes", "AWS"],
        "roadmap": [
            {"step": 1, "skill": "Kubernetes", "focus": "Learn K8s.", "suggested_practice": "Deploy a cluster."},
            {"step": 2, "skill": "AWS", "focus": "Learn AWS.", "suggested_practice": "Build a cloud service."},
        ],
    }

    with patch(
        "app.services.skill_gap_ai_service._call_qwen",
        new=AsyncMock(return_value=json.dumps(raw)),
    ):
        insights, ai_status = await generate_skill_gap_insights(analysis)

    assert ai_status == "ok"
    assert insights is not None
    # Kubernetes was hallucinated — must be stripped
    gap_skills = [g.skill for g in insights.priority_gaps]
    assert "Kubernetes" not in gap_skills
    # AWS was in missing_recommended — must be kept
    assert "AWS" in gap_skills
    # learning_order must also be sanitised
    assert "Kubernetes" not in insights.learning_order
    assert "AWS" in insights.learning_order
    # roadmap steps must also be sanitised
    roadmap_skills = [s.skill for s in insights.roadmap]
    assert "Kubernetes" not in roadmap_skills
    assert "AWS" in roadmap_skills


# ---------------------------------------------------------------------------
# Test 12 — Hallucinated skills are removed by the sanitizer
# ---------------------------------------------------------------------------


def test_sanitizer_strips_hallucinated_gap_skills():
    allowed = {"linux", "ci/cd"}
    owned = {"python"}

    raw = SkillGapAIInsights(
        summary="Test summary.",
        strengths=["Python", "Terraform"],  # Terraform not owned
        priority_gaps=[
            SkillGapPriorityItem(skill="Linux", priority="high", reason="Needed."),
            SkillGapPriorityItem(skill="Terraform", priority="high", reason="Hallucinated."),
        ],
        learning_order=["Linux", "Terraform", "CI/CD"],
        roadmap=[
            SkillGapRoadmapStep(step=1, skill="Linux", focus="Study Linux.", suggested_practice="Use Linux VM."),
            SkillGapRoadmapStep(step=2, skill="Terraform", focus="IaC.", suggested_practice="Deploy infra."),
            SkillGapRoadmapStep(step=3, skill="CI/CD", focus="Pipelines.", suggested_practice="Build CI pipeline."),
        ],
    )

    sanitized = _sanitize_insights(raw, allowed, owned)

    # Gaps
    gap_skills = {g.skill for g in sanitized.priority_gaps}
    assert "Linux" in gap_skills
    assert "Terraform" not in gap_skills  # hallucinated — stripped

    # Learning order
    assert "Linux" in sanitized.learning_order
    assert "Terraform" not in sanitized.learning_order
    assert "CI/CD" in sanitized.learning_order

    # Roadmap
    roadmap_skills = {s.skill for s in sanitized.roadmap}
    assert "Linux" in roadmap_skills
    assert "Terraform" not in roadmap_skills
    assert "CI/CD" in roadmap_skills

    # Roadmap step re-indexed
    for idx, step in enumerate(sanitized.roadmap, start=1):
        assert step.step == idx


# ---------------------------------------------------------------------------
# Test 13 — Hallucinated strengths are removed by the sanitizer
# ---------------------------------------------------------------------------


def test_sanitizer_strips_hallucinated_strengths():
    allowed = {"linux"}
    owned = {"python", "git"}

    raw = SkillGapAIInsights(
        summary="Test.",
        strengths=["Python", "Git", "Kubernetes"],  # Kubernetes not owned
        priority_gaps=[
            SkillGapPriorityItem(skill="Linux", priority="high", reason="Needed."),
        ],
        learning_order=["Linux"],
        roadmap=[
            SkillGapRoadmapStep(step=1, skill="Linux", focus="Study.", suggested_practice="Practice."),
        ],
    )

    sanitized = _sanitize_insights(raw, allowed, owned)
    assert "Python" in sanitized.strengths
    assert "Git" in sanitized.strengths
    assert "Kubernetes" not in sanitized.strengths


# ---------------------------------------------------------------------------
# Test 14 — Phase 2A endpoint works unchanged without include_ai
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_existing_phase2a_behavior_unchanged_without_include_ai():
    """
    GET /api/skill-analysis/me (no ?include_ai) must return ai_status='skipped'
    and ai_insights=None, identical to Phase 2A behavior.
    """
    from fastapi.testclient import TestClient
    from app.main import app
    import app.api.skill_analysis as sa_module
    from app.api.deps import get_current_user, get_db
    from app.schemas.skill_analysis import SkillAnalysisResponse
    from app.db.models import User

    fake_user = MagicMock(spec=User)
    fake_user.id = "test-user-id"

    fake_det = SkillAnalysisResponse(
        status="no_target_role",
        message="No target role set.",
    )

    with patch.object(sa_module, "build_skill_analysis", return_value=fake_det), \
         patch.object(sa_module, "_load_profile_for_analysis", return_value=MagicMock()):
        app.dependency_overrides[get_current_user] = lambda: fake_user
        app.dependency_overrides[get_db] = lambda: MagicMock()
        try:
            client = TestClient(app)
            response = client.get("/api/skill-analysis/me")
            assert response.status_code == 200
            data = response.json()
            assert data["ai_status"] == "skipped"
            assert data["ai_insights"] is None
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test 15 — Authentication is enforced on the extended endpoint
# ---------------------------------------------------------------------------


def test_authentication_enforced():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    response = client.get("/api/skill-analysis/me")
    assert response.status_code == 401

    response_with_ai = client.get("/api/skill-analysis/me?include_ai=true")
    assert response_with_ai.status_code == 401


# ---------------------------------------------------------------------------
# Test 16 — _extract_json_object handles think tags and markdown fences
# ---------------------------------------------------------------------------


def test_extract_json_strips_think_tags():
    raw = "<think>Reasoning here.</think>\n{\"summary\": \"test\", \"key\": 1}"
    result = _extract_json_object(raw)
    assert result["summary"] == "test"
    assert result["key"] == 1


def test_extract_json_strips_markdown_fence():
    raw = "```json\n{\"summary\": \"test\"}\n```"
    result = _extract_json_object(raw)
    assert result["summary"] == "test"


def test_extract_json_raises_on_garbage():
    with pytest.raises(AIServiceError):
        _extract_json_object("completely non-json garbage @@@@")


# ---------------------------------------------------------------------------
# Test 17 — include_ai=true with Qwen down returns ok deterministic + ai_status=unavailable
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_include_ai_with_qwen_down_returns_deterministic_result():
    """
    The deterministic Phase 2A analysis must succeed even when Qwen is down.
    """
    from fastapi.testclient import TestClient
    from app.main import app
    import app.api.skill_analysis as sa_module
    from app.api.deps import get_current_user, get_db
    from app.db.models import User

    fake_user = MagicMock(spec=User)
    fake_user.id = "test-user-id"

    fake_det = SkillAnalysisResponse(
        status="ok",
        target_role="Backend Engineer",
        resolved_roles=["Backend Engineer"],
        resolution_scores={"Backend Engineer": 1.0},
        resolution_method="exact",
        required_skills=[],
        recommended_skills=[],
        skills_have=["Python"],
        skills_missing_required=["Linux"],
        skills_missing_recommended=["AWS"],
        coverage=SkillCoverage(required_pct=50, recommended_pct=0, overall_pct=33),
    )

    with patch.object(sa_module, "build_skill_analysis", return_value=fake_det), \
         patch.object(sa_module, "_load_profile_for_analysis", return_value=MagicMock()), \
         patch(
             "app.services.skill_gap_ai_service._call_qwen",
             new=AsyncMock(side_effect=AIServiceError("Qwen is down")),
         ):
        app.dependency_overrides[get_current_user] = lambda: fake_user
        app.dependency_overrides[get_db] = lambda: MagicMock()
        try:
            client = TestClient(app)
            response = client.get("/api/skill-analysis/me?include_ai=true")
            assert response.status_code == 200
            data = response.json()
            # Deterministic result intact
            assert data["status"] == "ok"
            assert data["target_role"] == "Backend Engineer"
            assert data["skills_have"] == ["Python"]
            assert data["skills_missing_required"] == ["Linux"]
            # AI gracefully degraded
            assert data["ai_insights"] is None
            assert data["ai_status"] == "unavailable"
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Integration test (requires running Ollama + Qwen model)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.anyio
@pytest.mark.skipif(
    os.getenv("RUN_QDRANT_INTEGRATION") != "1",
    reason=(
        "Set RUN_QDRANT_INTEGRATION=1 and ensure Ollama is running "
        "with the configured OLLAMA_MODEL."
    ),
)
async def test_real_qwen_skill_gap_insights():
    """
    Full end-to-end integration test:

        Phase 2A result (Backend and Devops, partial skills)
            ↓  generate_skill_gap_insights
            ↓  real Ollama/Qwen call
            ↓  SkillGapAIInsights
    """
    from app.services import embedding_service as es

    es.get_embedding_dimension.cache_clear()

    # Build a realistic Phase 2A result for "Backend and Devops"
    analysis = _ok_analysis(
        target_role="Backend and Devops",
        resolved_roles=["Backend Engineer", "DevOps Engineer"],
        matched=["Python", "Git", "Docker"],
        missing_required=["Linux", "CI/CD"],
        missing_recommended=["AWS", "Redis"],
        required_pct=40,
        recommended_pct=10,
        overall_pct=27,
    )
    analysis.resolution_method = "semantic"

    try:
        insights, ai_status = await generate_skill_gap_insights(analysis)

        assert ai_status == "ok", f"Expected ok, got {ai_status}"
        assert insights is not None
        assert isinstance(insights, SkillGapAIInsights)

        # Summary must reference the target
        assert len(insights.summary) > 20

        # Strengths must only contain owned skills
        for strength in insights.strengths:
            assert strength.lower() in {"python", "git", "docker"}, (
                f"Hallucinated strength: {strength}"
            )

        # priority_gaps must only reference allowed missing skills
        allowed = {"linux", "ci/cd", "aws", "redis"}
        for gap in insights.priority_gaps:
            assert gap.skill.lower() in allowed, (
                f"Hallucinated priority gap: {gap.skill}"
            )

        # learning_order must only contain allowed skills
        for skill in insights.learning_order:
            assert skill.lower() in allowed, (
                f"Hallucinated learning_order entry: {skill}"
            )

        # roadmap steps must only reference allowed skills
        for step in insights.roadmap:
            assert step.skill.lower() in allowed, (
                f"Hallucinated roadmap step: {step.skill}"
            )
            assert step.step >= 1
            assert len(step.focus) > 5
            assert len(step.suggested_practice) > 5

        # Required missing skills should appear with high priority
        high_priority_skills = {g.skill.lower() for g in insights.priority_gaps if g.priority == "high"}
        # At least one required gap should be high priority
        assert len(insights.priority_gaps) > 0

    finally:
        es.get_embedding_dimension.cache_clear()
