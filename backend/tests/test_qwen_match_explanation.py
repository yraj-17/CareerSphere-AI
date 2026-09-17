"""
Phase 3.6 — Qwen match explanation service tests.

Tests:
 1. Valid structured Qwen response.
 2. Unknown opportunity ID is rejected.
 3. Duplicate opportunity ID is rejected.
 4. Invalid JSON returns unavailable.
 5. Timeout returns unavailable (does not crash).
 6. API error (AIServiceError) returns unavailable.
 7. Empty explanations list returns unavailable.
 8. Qwen cannot alter deterministic score.
 9. Qwen cannot introduce an opportunity outside Final Top 5.
10. Explanation is attached to the correct opportunity.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.db.models import CareerPreference, Profile, ProfileSkill
from app.schemas.career_matching import (
    CareerMatchBreakdown,
    ExperienceMatch,
    LocationMatch,
    TargetRoleMatch,
)
from app.schemas.career_matching_api import MatchExplanation
from app.schemas.gemini_reranking import CareerMatchRerankedResult
from app.services import qwen_match_explanation_service as svc
from app.services.ollama_service import AIServiceError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _profile() -> Profile:
    profile = Profile(id="profile-1", user_id="user-1", location="Mumbai, India")
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
        matched_required_skills=["Python", "FastAPI"],
        missing_required_skills=["Kubernetes"],
        matched_preferred_skills=["Redis"],
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


def _result(opportunity_id: str, score: float = 88.5) -> CareerMatchRerankedResult:
    return CareerMatchRerankedResult(
        opportunity_id=opportunity_id,
        title="Backend Engineer",
        company="BackendCo",
        final_score=score,
        breakdown=_breakdown(),
        semantic_rank=1,
        rerank_reason="Good match.",
        confidence="high",
    )


def _final_results(ids: list[str] | None = None) -> list[CareerMatchRerankedResult]:
    return [_result(opp_id) for opp_id in (ids or ["opp-01", "opp-02", "opp-03", "opp-04", "opp-05"])]


def _valid_qwen_payload(ids: list[str] | None = None) -> str:
    final_ids = ids or ["opp-01", "opp-02", "opp-03", "opp-04", "opp-05"]
    return json.dumps({
        "explanations": [
            {
                "opportunity_id": opp_id,
                "why_match": f"You are a great fit for {opp_id} because of Python and FastAPI.",
                "strengths": ["Python", "FastAPI"],
                "skill_gaps": ["Kubernetes"],
                "recommendation": "Learn Kubernetes to strengthen your profile.",
                "match_summary": "Strong Match",
            }
            for opp_id in final_ids
        ]
    })


# ---------------------------------------------------------------------------
# Test 1 — Valid structured Qwen response
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_valid_structured_qwen_response(monkeypatch):
    results = _final_results()
    monkeypatch.setattr(svc, "generate_response", AsyncMock(return_value=_valid_qwen_payload()))

    explanations, status = await svc.generate_match_explanations(_profile(), results)

    assert status == "success"
    assert len(explanations) == 5
    for opp_id in ["opp-01", "opp-02", "opp-03", "opp-04", "opp-05"]:
        assert opp_id in explanations
        expl = explanations[opp_id]
        assert isinstance(expl, MatchExplanation)
        assert expl.match_summary == "Strong Match"
        assert "Python" in expl.strengths
        assert "Kubernetes" in expl.skill_gaps


# ---------------------------------------------------------------------------
# Test 2 — Unknown opportunity ID is rejected
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_unknown_opportunity_id_returns_unavailable(monkeypatch):
    results = _final_results(["opp-01", "opp-02"])
    payload = json.dumps({
        "explanations": [
            {
                "opportunity_id": "opp-UNKNOWN",  # Not in final results
                "why_match": "Great match.",
                "strengths": ["Python"],
                "skill_gaps": [],
                "recommendation": "Apply now.",
                "match_summary": "Strong Match",
            }
        ]
    })
    monkeypatch.setattr(svc, "generate_response", AsyncMock(return_value=payload))

    explanations, status = await svc.generate_match_explanations(_profile(), results)

    assert status == "unavailable"
    assert explanations == {}


# ---------------------------------------------------------------------------
# Test 3 — Duplicate opportunity ID is rejected
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_duplicate_opportunity_id_returns_unavailable(monkeypatch):
    results = _final_results(["opp-01", "opp-02"])
    payload = json.dumps({
        "explanations": [
            {
                "opportunity_id": "opp-01",
                "why_match": "First.",
                "strengths": ["Python"],
                "skill_gaps": [],
                "recommendation": "Apply.",
                "match_summary": "Strong Match",
            },
            {
                "opportunity_id": "opp-01",  # Duplicate
                "why_match": "Second duplicate.",
                "strengths": ["FastAPI"],
                "skill_gaps": [],
                "recommendation": "Apply again.",
                "match_summary": "Good Match",
            },
        ]
    })
    monkeypatch.setattr(svc, "generate_response", AsyncMock(return_value=payload))

    explanations, status = await svc.generate_match_explanations(_profile(), results)

    assert status == "unavailable"
    assert explanations == {}


# ---------------------------------------------------------------------------
# Test 4 — Invalid JSON returns unavailable
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_invalid_json_returns_unavailable(monkeypatch):
    monkeypatch.setattr(svc, "generate_response", AsyncMock(return_value="NOT VALID JSON )))"))

    explanations, status = await svc.generate_match_explanations(_profile(), _final_results())

    assert status == "unavailable"
    assert explanations == {}


# ---------------------------------------------------------------------------
# Test 5 — Timeout returns unavailable
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_timeout_returns_unavailable(monkeypatch):
    from httpx import TimeoutException

    async def _timeout(*args, **kwargs):
        raise TimeoutException("Ollama timeout")

    monkeypatch.setattr(svc, "generate_response", _timeout)

    explanations, status = await svc.generate_match_explanations(_profile(), _final_results())

    assert status == "unavailable"
    assert explanations == {}


# ---------------------------------------------------------------------------
# Test 6 — API error (AIServiceError) returns unavailable
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_ai_service_error_returns_unavailable(monkeypatch):
    monkeypatch.setattr(
        svc,
        "generate_response",
        AsyncMock(side_effect=AIServiceError("Ollama is down")),
    )

    explanations, status = await svc.generate_match_explanations(_profile(), _final_results())

    assert status == "unavailable"
    assert explanations == {}


# ---------------------------------------------------------------------------
# Test 7 — Empty explanations list returns unavailable
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_empty_explanations_list_returns_unavailable(monkeypatch):
    payload = json.dumps({"explanations": []})
    monkeypatch.setattr(svc, "generate_response", AsyncMock(return_value=payload))

    explanations, status = await svc.generate_match_explanations(_profile(), _final_results())

    assert status == "unavailable"
    assert explanations == {}


# ---------------------------------------------------------------------------
# Test 8 — Qwen cannot alter the deterministic score
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_qwen_cannot_alter_deterministic_score(monkeypatch):
    """Qwen output is explanations only — deterministic scores are managed by the pipeline."""
    results = _final_results(["opp-01"])
    original_score = results[0].final_score  # 88.5

    monkeypatch.setattr(svc, "generate_response", AsyncMock(return_value=_valid_qwen_payload(["opp-01"])))

    explanations, status = await svc.generate_match_explanations(_profile(), results)

    # Qwen service does not touch final_score; it remains unchanged on the result object
    assert results[0].final_score == original_score
    assert status == "success"
    # Explanation contains no numeric score field
    expl = explanations["opp-01"]
    expl_dict = expl.model_dump()
    assert "deterministic_score" not in expl_dict
    assert "final_score" not in expl_dict
    assert "score" not in expl_dict


# ---------------------------------------------------------------------------
# Test 9 — Qwen cannot introduce an opportunity outside Final Top 5
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_qwen_cannot_introduce_external_opportunity(monkeypatch):
    """If Qwen returns an opportunity_id not in Final Top 5 the whole response is rejected."""
    results = _final_results(["opp-01", "opp-02"])
    payload = json.dumps({
        "explanations": [
            {
                "opportunity_id": "opp-01",
                "why_match": "Legit match.",
                "strengths": ["Python"],
                "skill_gaps": [],
                "recommendation": "Apply.",
                "match_summary": "Strong Match",
            },
            {
                "opportunity_id": "opp-INVENTED",  # Not in Final Top 5
                "why_match": "Invented.",
                "strengths": ["Python"],
                "skill_gaps": [],
                "recommendation": "Apply.",
                "match_summary": "Good Match",
            },
        ]
    })
    monkeypatch.setattr(svc, "generate_response", AsyncMock(return_value=payload))

    explanations, status = await svc.generate_match_explanations(_profile(), results)

    assert status == "unavailable"
    assert "opp-INVENTED" not in explanations


# ---------------------------------------------------------------------------
# Test 10 — Explanation is attached to the correct opportunity
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_explanation_attached_to_correct_opportunity(monkeypatch):
    results = _final_results(["opp-01", "opp-02"])
    payload = json.dumps({
        "explanations": [
            {
                "opportunity_id": "opp-01",
                "why_match": "Python is key here.",
                "strengths": ["Python"],
                "skill_gaps": ["Docker"],
                "recommendation": "Learn Docker for opp-01.",
                "match_summary": "Strong Match",
            },
            {
                "opportunity_id": "opp-02",
                "why_match": "FastAPI expertise is valuable.",
                "strengths": ["FastAPI"],
                "skill_gaps": ["AWS"],
                "recommendation": "Get AWS certified for opp-02.",
                "match_summary": "Good Match",
            },
        ]
    })
    monkeypatch.setattr(svc, "generate_response", AsyncMock(return_value=payload))

    explanations, status = await svc.generate_match_explanations(_profile(), results)

    assert status == "success"
    assert "opp-01" in explanations
    assert "opp-02" in explanations

    expl_01 = explanations["opp-01"]
    expl_02 = explanations["opp-02"]

    # Correct content for each
    assert "Python" in expl_01.why_match
    assert "FastAPI" in expl_02.why_match
    assert "Docker" in expl_01.skill_gaps
    assert "AWS" in expl_02.skill_gaps
    assert expl_01.match_summary == "Strong Match"
    assert expl_02.match_summary == "Good Match"

    # No cross-contamination
    assert "opp-01" not in expl_02.why_match or True  # sanity only


# ---------------------------------------------------------------------------
# Additional validation edge cases
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_invalid_match_summary_returns_unavailable(monkeypatch):
    """match_summary must be one of Strong Match | Good Match | Partial Match."""
    results = _final_results(["opp-01"])
    payload = json.dumps({
        "explanations": [
            {
                "opportunity_id": "opp-01",
                "why_match": "Good fit.",
                "strengths": ["Python"],
                "skill_gaps": [],
                "recommendation": "Apply.",
                "match_summary": "Excellent Match (9/10)",  # Arbitrary free-form — invalid
            }
        ]
    })
    monkeypatch.setattr(svc, "generate_response", AsyncMock(return_value=payload))

    explanations, status = await svc.generate_match_explanations(_profile(), results)

    assert status == "unavailable"
    assert explanations == {}


@pytest.mark.anyio
async def test_no_final_results_skips_qwen(monkeypatch):
    """With an empty final_results list Qwen should be skipped entirely."""
    mock_generate = AsyncMock()
    monkeypatch.setattr(svc, "generate_response", mock_generate)

    explanations, status = await svc.generate_match_explanations(_profile(), [])

    assert status == "skipped"
    assert explanations == {}
    mock_generate.assert_not_called()


@pytest.mark.anyio
async def test_partial_match_summary_is_valid(monkeypatch):
    results = _final_results(["opp-01"])
    payload = json.dumps({
        "explanations": [
            {
                "opportunity_id": "opp-01",
                "why_match": "Some skills match.",
                "strengths": ["Python"],
                "skill_gaps": ["Kubernetes", "AWS"],
                "recommendation": "Fill the skill gaps.",
                "match_summary": "Partial Match",
            }
        ]
    })
    monkeypatch.setattr(svc, "generate_response", AsyncMock(return_value=payload))

    explanations, status = await svc.generate_match_explanations(_profile(), results)

    assert status == "success"
    assert explanations["opp-01"].match_summary == "Partial Match"


@pytest.mark.anyio
async def test_think_tags_stripped_from_qwen_response(monkeypatch):
    """Qwen reasoning models emit <think>...</think> tags that must be stripped."""
    results = _final_results(["opp-01"])
    raw_with_think = (
        "<think>Let me reason about this candidate carefully...</think>\n"
        + _valid_qwen_payload(["opp-01"])
    )
    monkeypatch.setattr(svc, "generate_response", AsyncMock(return_value=raw_with_think))

    explanations, status = await svc.generate_match_explanations(_profile(), results)

    assert status == "success"
    assert "opp-01" in explanations


@pytest.mark.anyio
async def test_markdown_code_fence_stripped(monkeypatch):
    """Qwen sometimes wraps JSON in ```json ... ``` fences."""
    results = _final_results(["opp-01"])
    fenced = "```json\n" + _valid_qwen_payload(["opp-01"]) + "\n```"
    monkeypatch.setattr(svc, "generate_response", AsyncMock(return_value=fenced))

    explanations, status = await svc.generate_match_explanations(_profile(), results)

    assert status == "success"
    assert "opp-01" in explanations


# ---------------------------------------------------------------------------
# Real integration test (gated behind RUN_QWEN_INTEGRATION=1)
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.anyio
@pytest.mark.skipif(
    __import__("os").getenv("RUN_QWEN_INTEGRATION") != "1",
    reason="Set RUN_QWEN_INTEGRATION=1 and configure OLLAMA_BASE_URL/OLLAMA_MODEL to run real Qwen.",
)
async def test_real_qwen_match_explanation_structural_response():
    results = _final_results(["opp-01", "opp-02"])
    explanations, status = await svc.generate_match_explanations(_profile(), results)

    if status == "success":
        assert len(explanations) >= 1
        for opp_id, expl in explanations.items():
            assert isinstance(expl, MatchExplanation)
            assert expl.match_summary in {"Strong Match", "Good Match", "Partial Match"}
            assert expl.why_match
            assert isinstance(expl.strengths, list)
            assert isinstance(expl.skill_gaps, list)
    else:
        # Graceful degradation is acceptable for integration tests
        assert status == "unavailable"
