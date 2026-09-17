"""Qwen explanation layer for final career matches."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from pydantic import BaseModel, Field, ValidationError

from app.db.models import Profile
from app.schemas.career_matching_api import MatchExplanation
from app.schemas.gemini_reranking import CareerMatchRerankedResult
from app.services.ollama_service import AIServiceError, generate_response

logger = logging.getLogger(__name__)


class QwenExplanationItem(BaseModel):
    opportunity_id: str
    why_match: str = Field(..., min_length=1, max_length=700)
    strengths: list[str] = []
    skill_gaps: list[str] = []
    recommendation: str = Field(..., min_length=1, max_length=500)
    match_summary: str


class QwenExplanationResponse(BaseModel):
    explanations: list[QwenExplanationItem] = []


_SYSTEM_PROMPT = """\
You are CareerSphere AI's match explanation layer.

STRICT RULES:
- Explain only the supplied final career matches.
- Use ONLY the supplied user profile, matching data, and opportunity information.
- Do not calculate or change scores.
- Do not invent skills, projects, companies, responsibilities, requirements, salary, locations, or experience.
- If information is unavailable, say it is unavailable.
- Return ONLY JSON with this schema:
{
  "explanations": [
    {
      "opportunity_id": "id from supplied final results",
      "why_match": "short personalized explanation",
      "strengths": ["skill from supplied matched skills only"],
      "skill_gaps": ["skill from supplied missing skills only"],
      "recommendation": "short practical next step",
      "match_summary": "Strong Match|Good Match|Partial Match"
    }
  ]
}"""

_ALLOWED_SUMMARIES = {"Strong Match", "Good Match", "Partial Match"}


def _extract_json_object(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL | re.IGNORECASE).strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise AIServiceError("Qwen returned unparseable JSON for match explanations.")
        parsed = json.loads(cleaned[start : end + 1])
    if not isinstance(parsed, dict):
        raise AIServiceError("Qwen returned unexpected response type for match explanations.")
    return parsed


def _profile_context(profile: Optional[Profile]) -> dict[str, Any]:
    if not profile:
        return {}
    pref = profile.career_preferences
    return {
        "target_role": pref.target_job_role if pref else None,
        "skills": [skill.name for skill in profile.skills[:30]],
        "projects": [
            {
                "name": project.name,
                "description": project.description,
                "technologies": [tech.name for tech in project.technologies[:10]],
            }
            for project in profile.projects[:5]
        ],
        "experience": [
            {
                "job_title": exp.job_title,
                "company": exp.company,
                "employment_type": exp.employment_type,
            }
            for exp in profile.experience[:5]
        ],
        "preferences": {
            "industry": pref.preferred_industry if pref else None,
            "work_mode": pref.preferred_work_type if pref else None,
            "preferred_locations": pref.preferred_locations if pref else None,
        },
    }


def build_qwen_prompt(profile: Optional[Profile], final_results: list[CareerMatchRerankedResult]) -> str:
    payload = {
        "user_context": _profile_context(profile),
        "final_results": [
            {
                "opportunity_id": result.opportunity_id,
                "title": result.title,
                "company": result.company,
                "deterministic_score": result.final_score,
                "semantic_rank": result.semantic_rank,
                "rerank_reason": result.rerank_reason,
                "confidence": result.confidence,
                "component_scores": {
                    "required_skill_score": result.breakdown.required_skill_score,
                    "preferred_skill_score": result.breakdown.preferred_skill_score,
                    "target_role_score": result.breakdown.target_role_score,
                    "experience_score": result.breakdown.experience_score,
                    "location_remote_score": result.breakdown.location_remote_score,
                    "career_preference_score": result.breakdown.career_preference_score,
                },
                "matched_required_skills": result.breakdown.matched_required_skills,
                "missing_required_skills": result.breakdown.missing_required_skills,
                "matched_preferred_skills": result.breakdown.matched_preferred_skills,
                "missing_preferred_skills": result.breakdown.missing_preferred_skills,
            }
            for result in final_results
        ],
    }
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


def validate_qwen_response(raw_response: str, allowed_ids: set[str]) -> dict[str, MatchExplanation]:
    try:
        parsed = _extract_json_object(raw_response)
        response = QwenExplanationResponse.model_validate(parsed)
    except (ValidationError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise AIServiceError("Qwen match explanation validation failed.") from exc

    if not response.explanations:
        raise AIServiceError("Qwen returned no explanations.")

    seen: set[str] = set()
    explanations: dict[str, MatchExplanation] = {}
    for item in response.explanations:
        if item.opportunity_id not in allowed_ids:
            raise AIServiceError(f"Qwen returned unknown opportunity_id: {item.opportunity_id}")
        if item.opportunity_id in seen:
            raise AIServiceError(f"Qwen returned duplicate opportunity_id: {item.opportunity_id}")
        if item.match_summary not in _ALLOWED_SUMMARIES:
            raise AIServiceError(f"Qwen returned invalid match_summary: {item.match_summary}")
        seen.add(item.opportunity_id)
        explanations[item.opportunity_id] = MatchExplanation(
            why_match=item.why_match,
            strengths=item.strengths,
            skill_gaps=item.skill_gaps,
            recommendation=item.recommendation,
            match_summary=item.match_summary,  # type: ignore[arg-type]
        )
    return explanations


async def generate_match_explanations(
    profile: Optional[Profile],
    final_results: list[CareerMatchRerankedResult],
) -> tuple[dict[str, MatchExplanation], str]:
    if not final_results:
        return {}, "skipped"

    allowed_ids = {result.opportunity_id for result in final_results}
    prompt = build_qwen_prompt(profile, final_results)
    try:
        raw = await generate_response(prompt=prompt, system_prompt=_SYSTEM_PROMPT, think=False)
        return validate_qwen_response(raw, allowed_ids), "success"
    except AIServiceError as exc:
        logger.warning("[QwenMatchExplanation] Failed: %s", exc)
        return {}, "unavailable"
    except Exception as exc:
        logger.warning("[QwenMatchExplanation] Unexpected failure: %s", exc)
        return {}, "unavailable"
