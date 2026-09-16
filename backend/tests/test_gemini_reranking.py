"""Tests for Phase 3.5 Gemini semantic reranking."""

from __future__ import annotations

import asyncio
import json
import os
from unittest.mock import AsyncMock

import pytest

from app.db.models import CareerPreference, Profile, ProfileProject, ProfileSkill, ProjectTechnology
from app.schemas.career_matching import (
    CareerMatchBreakdown,
    CareerMatchingResponse,
    CareerMatchResult,
    ExperienceMatch,
    LocationMatch,
    TargetRoleMatch,
)
from app.services import gemini_reranking_service as svc


def _result(index: int, score: float | None = None) -> CareerMatchResult:
    opportunity_id = f"opp-{index:02d}"
    return CareerMatchResult(
        opportunity_id=opportunity_id,
        title=f"Backend Engineer {index}",
        company="BackendCo",
        final_score=score if score is not None else round(95 - index, 2),
        breakdown=CareerMatchBreakdown(
            required_skill_score=90.0,
            preferred_skill_score=80.0,
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
        ),
    )


def _response(count: int = 10) -> CareerMatchingResponse:
    return CareerMatchingResponse(
        profile_id="profile-1",
        candidates_considered=30,
        candidates_after_filters=count,
        results=[_result(index) for index in range(1, count + 1)],
    )


def _profile() -> Profile:
    profile = Profile(id="profile-1", user_id="user-1", location="Mumbai, India")
    profile.skills = [
        ProfileSkill(name="Python", normalized_name="python"),
        ProfileSkill(name="FastAPI", normalized_name="fastapi"),
        ProfileSkill(name="PostgreSQL", normalized_name="postgresql"),
        ProfileSkill(name="Docker", normalized_name="docker"),
        ProfileSkill(name="Redis", normalized_name="redis"),
    ]
    project = ProfileProject(name="AI chatbot", description="Dockerized REST API chatbot backend")
    project.technologies = [
        ProjectTechnology(name="FastAPI", normalized_name="fastapi"),
        ProjectTechnology(name="Docker", normalized_name="docker"),
    ]
    profile.projects = [project]
    profile.experience = []
    profile.career_preferences = CareerPreference(
        target_job_role="Backend Engineer",
        preferred_work_type="Remote",
        preferred_locations=json.dumps(["Remote - India"]),
    )
    return profile


def _gemini_payload(ids: list[str]) -> str:
    return json.dumps(
        {
            "ranked_opportunities": [
                {
                    "opportunity_id": opportunity_id,
                    "semantic_rank": rank,
                    "rerank_reason": f"Reason for {opportunity_id}",
                    "confidence": "high" if rank == 1 else "medium",
                }
                for rank, opportunity_id in enumerate(ids, start=1)
            ]
        }
    )


async def _run_with_payload(monkeypatch, payload: str, response: CareerMatchingResponse | None = None):
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(svc, "_call_gemini", AsyncMock(return_value=payload))
    return await svc.rerank_career_matches(_profile(), response or _response())


@pytest.mark.anyio
async def test_valid_top_10_to_valid_top_5(monkeypatch):
    result = await _run_with_payload(monkeypatch, _gemini_payload(["opp-03", "opp-01", "opp-04", "opp-02", "opp-05"]))

    assert result.gemini_status == "success"
    assert result.used_deterministic_fallback is False
    assert [item.opportunity_id for item in result.final_results] == ["opp-03", "opp-01", "opp-04", "opp-02", "opp-05"]
    assert len(result.final_results) == 5


@pytest.mark.anyio
async def test_gemini_preserves_opportunity_ids_and_attaches_reason(monkeypatch):
    result = await _run_with_payload(monkeypatch, _gemini_payload(["opp-02"]))

    assert result.final_results[0].opportunity_id == "opp-02"
    assert result.final_results[0].rerank_reason == "Reason for opp-02"
    assert result.final_results[0].confidence == "high"


@pytest.mark.anyio
async def test_unknown_opportunity_id_falls_back(monkeypatch):
    result = await _run_with_payload(monkeypatch, _gemini_payload(["unknown-id"]))

    assert result.gemini_status == "invalid_response"
    assert result.used_deterministic_fallback is True
    assert [item.opportunity_id for item in result.final_results] == ["opp-01", "opp-02", "opp-03", "opp-04", "opp-05"]


@pytest.mark.anyio
async def test_duplicate_opportunity_ids_fall_back(monkeypatch):
    result = await _run_with_payload(monkeypatch, _gemini_payload(["opp-01", "opp-01"]))

    assert result.gemini_status == "invalid_response"
    assert result.used_deterministic_fallback is True


@pytest.mark.anyio
async def test_output_limited_to_top_5(monkeypatch):
    ids = [f"opp-{index:02d}" for index in range(1, 7)]
    result = await _run_with_payload(monkeypatch, _gemini_payload(ids))

    assert result.gemini_status == "invalid_response"
    assert len(result.final_results) == 5
    assert result.used_deterministic_fallback is True


@pytest.mark.anyio
async def test_deterministic_scores_remain_unchanged(monkeypatch):
    response = _response()
    original_score = response.results[2].final_score
    result = await _run_with_payload(monkeypatch, _gemini_payload(["opp-03"]), response)

    assert result.final_results[0].opportunity_id == "opp-03"
    assert result.final_results[0].final_score == original_score


@pytest.mark.anyio
async def test_opportunity_metadata_remains_backend_owned(monkeypatch):
    payload = json.dumps(
        {
            "ranked_opportunities": [
                {
                    "opportunity_id": "opp-01",
                    "semantic_rank": 1,
                    "rerank_reason": "Relevant backend work",
                    "confidence": "high",
                    "title": "Gemini tried to replace title",
                    "final_score": 0,
                }
            ]
        }
    )
    result = await _run_with_payload(monkeypatch, payload)

    assert result.final_results[0].title == "Backend Engineer 1"
    assert result.final_results[0].final_score == _response().results[0].final_score


@pytest.mark.anyio
async def test_gemini_ranking_metadata_is_merged_correctly(monkeypatch):
    result = await _run_with_payload(monkeypatch, _gemini_payload(["opp-04", "opp-02"]))

    assert result.final_results[0].semantic_rank == 1
    assert result.final_results[0].rerank_reason == "Reason for opp-04"
    assert result.final_results[1].semantic_rank == 2
    assert result.final_results[1].confidence == "medium"


@pytest.mark.anyio
async def test_gemini_timeout_uses_deterministic_fallback(monkeypatch):
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(svc, "_call_gemini", AsyncMock(side_effect=asyncio.TimeoutError()))

    result = await svc.rerank_career_matches(_profile(), _response())

    assert result.gemini_status == "unavailable"
    assert result.used_deterministic_fallback is True


@pytest.mark.anyio
async def test_gemini_api_error_uses_deterministic_fallback(monkeypatch):
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(svc, "_call_gemini", AsyncMock(side_effect=RuntimeError("rate limit")))

    result = await svc.rerank_career_matches(_profile(), _response())

    assert result.gemini_status == "unavailable"
    assert result.used_deterministic_fallback is True


@pytest.mark.anyio
async def test_missing_api_key_uses_not_configured_fallback(monkeypatch):
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "")

    result = await svc.rerank_career_matches(_profile(), _response())

    assert result.gemini_status == "not_configured"
    assert result.used_deterministic_fallback is True


@pytest.mark.anyio
async def test_invalid_json_uses_fallback(monkeypatch):
    result = await _run_with_payload(monkeypatch, "not json")

    assert result.gemini_status == "invalid_response"
    assert result.used_deterministic_fallback is True


@pytest.mark.anyio
async def test_empty_response_uses_fallback(monkeypatch):
    result = await _run_with_payload(monkeypatch, json.dumps({"ranked_opportunities": []}))

    assert result.gemini_status == "invalid_response"
    assert result.used_deterministic_fallback is True


@pytest.mark.anyio
async def test_invalid_rank_values_are_handled_safely(monkeypatch):
    payload = json.dumps(
        {"ranked_opportunities": [{"opportunity_id": "opp-01", "semantic_rank": 0, "rerank_reason": "x", "confidence": "high"}]}
    )
    result = await _run_with_payload(monkeypatch, payload)

    assert result.gemini_status == "invalid_response"
    assert result.used_deterministic_fallback is True


@pytest.mark.anyio
async def test_duplicate_ranks_are_handled_safely(monkeypatch):
    payload = json.dumps(
        {
            "ranked_opportunities": [
                {"opportunity_id": "opp-01", "semantic_rank": 1, "rerank_reason": "x", "confidence": "high"},
                {"opportunity_id": "opp-02", "semantic_rank": 1, "rerank_reason": "y", "confidence": "medium"},
            ]
        }
    )
    result = await _run_with_payload(monkeypatch, payload)

    assert result.gemini_status == "invalid_response"
    assert result.used_deterministic_fallback is True


@pytest.mark.anyio
async def test_confidence_values_are_validated(monkeypatch):
    payload = json.dumps(
        {"ranked_opportunities": [{"opportunity_id": "opp-01", "semantic_rank": 1, "rerank_reason": "x", "confidence": "certain"}]}
    )
    result = await _run_with_payload(monkeypatch, payload)

    assert result.gemini_status == "invalid_response"
    assert result.used_deterministic_fallback is True


@pytest.mark.anyio
async def test_original_deterministic_top_10_remains_available(monkeypatch):
    response = _response()
    result = await _run_with_payload(monkeypatch, _gemini_payload(["opp-02"]), response)

    assert len(result.deterministic_results) == 10
    assert [item.opportunity_id for item in result.deterministic_results] == [item.opportunity_id for item in response.results]


@pytest.mark.anyio
async def test_phase_3_4_result_is_not_mutated(monkeypatch):
    response = _response()
    before = response.model_dump()

    await _run_with_payload(monkeypatch, _gemini_payload(["opp-05", "opp-01"]), response)

    assert response.model_dump() == before


@pytest.mark.anyio
async def test_no_unknown_opportunity_can_reach_final_top_5(monkeypatch):
    result = await _run_with_payload(monkeypatch, _gemini_payload(["opp-01", "unknown-id", "opp-02"]))

    assert result.used_deterministic_fallback is True
    allowed = {item.opportunity_id for item in _response().results}
    assert {item.opportunity_id for item in result.final_results} <= allowed


def test_prompt_contains_only_compact_allowed_context():
    prompt = svc.build_gemini_prompt(_profile(), _response())
    payload = json.loads(prompt)

    assert len(payload["opportunities"]) == 10
    assert "password" not in prompt.lower()
    assert "api_key" not in prompt.lower()
    assert payload["user_context"]["target_role"] == "Backend Engineer"


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_GEMINI_INTEGRATION") != "1",
    reason="Set RUN_GEMINI_INTEGRATION=1 and configure GEMINI_API_KEY to call the real Gemini API.",
)
@pytest.mark.anyio
async def test_real_gemini_reranking_structural_response():
    if not svc.settings.GEMINI_API_KEY:
        pytest.skip("GEMINI_API_KEY is not configured.")

    deterministic = _response()
    result = await svc.rerank_career_matches(_profile(), deterministic)

    assert result.gemini_status in {"success", "unavailable", "invalid_response"}
    assert len(result.final_results) <= 5
    allowed = {item.opportunity_id for item in deterministic.results}
    assert {item.opportunity_id for item in result.final_results} <= allowed
    for item in result.final_results:
        assert item.final_score == next(original.final_score for original in deterministic.results if original.opportunity_id == item.opportunity_id)
