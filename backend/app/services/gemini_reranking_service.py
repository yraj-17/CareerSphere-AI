"""
Gemini semantic reranking for Phase 3.5.

Gemini receives only the deterministic Phase 3.4 Top 10 and may only reorder
those candidates into a final Top 5. The deterministic score and all
opportunity metadata remain backend-owned and unchanged.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Optional

from pydantic import ValidationError

from app.core.config import settings
from app.db.models import Profile
from app.schemas.career_matching import CareerMatchingResponse, CareerMatchResult
from app.schemas.gemini_reranking import (
    CareerMatchingWithRerankResponse,
    CareerMatchRerankedResult,
    GeminiRerankItem,
    GeminiRerankResponse,
    GeminiStatus,
)

logger = logging.getLogger(__name__)

_MAX_FINAL_RESULTS = 5
_MAX_DESCRIPTION_CHARS = 700


class GeminiRerankingError(Exception):
    """Raised when Gemini reranking cannot produce a trusted response."""


_SYSTEM_PROMPT = """\
You are a second-stage semantic reranker for CareerSphere AI.

STRICT RULES:
- The backend has already calculated deterministic compatibility scores.
- Deterministic scores are authoritative. Do not recalculate, modify, or replace them.
- Rerank ONLY the supplied deterministic Top 10 opportunities.
- Return at most Top 5.
- Do not invent opportunities, user skills, user experience, or job facts.
- Use only supplied user and opportunity information.
- Consider contextual relevance beyond keyword matching.
- Return ONLY strict JSON with this schema:
{
  "ranked_opportunities": [
    {
      "opportunity_id": "id from supplied list",
      "semantic_rank": 1,
      "rerank_reason": "concise contextual reason",
      "confidence": "high|medium|low"
    }
  ]
}"""


def _trim(value: Optional[str], limit: int = _MAX_DESCRIPTION_CHARS) -> str:
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _list(values: list[str]) -> list[str]:
    return [value for value in values if value]


def _profile_context(profile: Optional[Profile]) -> dict[str, Any]:
    if profile is None:
        return {}

    pref = profile.career_preferences
    preferred_locations: list[str] = []
    career_interests: list[str] = []
    if pref:
        for attr, target in (
            ("preferred_locations", preferred_locations),
            ("career_interests", career_interests),
        ):
            raw = getattr(pref, attr) or "[]"
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    target.extend(str(item) for item in parsed if str(item).strip())
            except Exception:
                target.extend(part.strip() for part in raw.split(",") if part.strip())

    projects = []
    for project in profile.projects[:5]:
        projects.append(
            {
                "name": project.name,
                "description": _trim(project.description, 300),
                "technologies": [tech.name for tech in project.technologies[:10]],
            }
        )

    experience = []
    for exp in profile.experience[:5]:
        experience.append(
            {
                "job_title": exp.job_title,
                "company": exp.company,
                "employment_type": exp.employment_type,
                "description": _trim(exp.description, 300),
            }
        )

    return {
        "target_role": pref.target_job_role if pref else None,
        "skills": [skill.name for skill in profile.skills[:30]],
        "projects": projects,
        "experience": experience,
        "preferences": {
            "industry": pref.preferred_industry if pref else None,
            "work_mode": pref.preferred_work_type if pref else None,
            "locations": preferred_locations,
            "career_interests": career_interests,
        },
    }


def _candidate_context(result: CareerMatchResult) -> dict[str, Any]:
    breakdown = result.breakdown
    return {
        "opportunity_id": result.opportunity_id,
        "title": result.title,
        "company": result.company,
        "deterministic_score": result.final_score,
        "component_scores": {
            "required_skills": breakdown.required_skill_score,
            "preferred_skills": breakdown.preferred_skill_score,
            "target_role": breakdown.target_role_score,
            "experience": breakdown.experience_score,
            "location_remote": breakdown.location_remote_score,
            "career_preferences": breakdown.career_preference_score,
        },
        "matched_required_skills": breakdown.matched_required_skills,
        "missing_required_skills": breakdown.missing_required_skills,
        "matched_preferred_skills": breakdown.matched_preferred_skills,
        "missing_preferred_skills": breakdown.missing_preferred_skills,
        "target_role_match": breakdown.target_role_match.model_dump(),
        "experience_match": breakdown.experience_match.model_dump(),
        "location_match": breakdown.location_match.model_dump(),
        "preference_matches": [item.model_dump() for item in breakdown.preference_matches],
    }


def build_gemini_prompt(profile: Optional[Profile], deterministic_response: CareerMatchingResponse) -> str:
    payload = {
        "task": "Rerank the deterministic Top 10 into the most contextually relevant Top 5.",
        "rules": [
            "Use only the supplied opportunity IDs.",
            "Do not modify deterministic scores.",
            "Return JSON only.",
        ],
        "user_context": _profile_context(profile),
        "opportunities": [
            _candidate_context(result)
            for result in deterministic_response.results[:10]
        ],
    }
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


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
            raise GeminiRerankingError("Gemini returned invalid JSON")
        parsed = json.loads(cleaned[start : end + 1])
    if not isinstance(parsed, dict):
        raise GeminiRerankingError("Gemini returned a non-object response")
    return parsed


def validate_gemini_response(
    raw_response: str,
    allowed_ids: set[str],
) -> GeminiRerankResponse:
    try:
        parsed = _extract_json_object(raw_response)
        response = GeminiRerankResponse.model_validate(parsed)
    except (json.JSONDecodeError, ValidationError, ValueError, TypeError) as exc:
        raise GeminiRerankingError("Gemini response failed schema validation") from exc

    if not response.ranked_opportunities:
        raise GeminiRerankingError("Gemini response was empty")

    seen_ids: set[str] = set()
    seen_ranks: set[int] = set()
    for item in response.ranked_opportunities:
        if item.opportunity_id not in allowed_ids:
            raise GeminiRerankingError(f"Gemini returned unknown opportunity_id: {item.opportunity_id}")
        if item.opportunity_id in seen_ids:
            raise GeminiRerankingError(f"Gemini returned duplicate opportunity_id: {item.opportunity_id}")
        if item.semantic_rank in seen_ranks:
            raise GeminiRerankingError(f"Gemini returned duplicate semantic_rank: {item.semantic_rank}")
        seen_ids.add(item.opportunity_id)
        seen_ranks.add(item.semantic_rank)

    return response


def _fallback_response(
    deterministic_response: CareerMatchingResponse,
    status: GeminiStatus,
) -> CareerMatchingWithRerankResponse:
    final_results = [
        CareerMatchRerankedResult(
            **result.model_dump(),
            semantic_rank=index,
            rerank_reason=None,
            confidence=None,
        )
        for index, result in enumerate(deterministic_response.results[:_MAX_FINAL_RESULTS], start=1)
    ]
    return CareerMatchingWithRerankResponse(
        deterministic_results=[result.model_copy(deep=True) for result in deterministic_response.results],
        final_results=final_results,
        gemini_status=status,
        used_deterministic_fallback=True,
    )


def _merge_response(
    deterministic_response: CareerMatchingResponse,
    rerank_response: GeminiRerankResponse,
) -> CareerMatchingWithRerankResponse:
    by_id = {result.opportunity_id: result for result in deterministic_response.results}
    sorted_items = sorted(rerank_response.ranked_opportunities, key=lambda item: item.semantic_rank)
    final_results = [
        CareerMatchRerankedResult(
            **by_id[item.opportunity_id].model_dump(),
            semantic_rank=index,
            rerank_reason=item.rerank_reason,
            confidence=item.confidence,
        )
        for index, item in enumerate(sorted_items[:_MAX_FINAL_RESULTS], start=1)
    ]
    return CareerMatchingWithRerankResponse(
        deterministic_results=[result.model_copy(deep=True) for result in deterministic_response.results],
        final_results=final_results,
        gemini_status="success",
        used_deterministic_fallback=False,
    )


async def _call_gemini(prompt: str) -> str:
    if not settings.GEMINI_API_KEY:
        raise GeminiRerankingError("Gemini API key is not configured")

    def _generate() -> str:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0.2,
                max_output_tokens=900,
            ),
        )
        text = getattr(response, "text", None)
        if not isinstance(text, str) or not text.strip():
            raise GeminiRerankingError("Gemini returned an empty response")
        return text

    return await asyncio.wait_for(
        asyncio.to_thread(_generate),
        timeout=settings.GEMINI_RERANK_TIMEOUT_SECONDS,
    )


async def rerank_career_matches(
    profile: Optional[Profile],
    deterministic_response: CareerMatchingResponse,
) -> CareerMatchingWithRerankResponse:
    if not settings.GEMINI_API_KEY:
        logger.info("[GeminiRerank] Gemini not configured; using deterministic fallback.")
        return _fallback_response(deterministic_response, "not_configured")

    if not deterministic_response.results:
        logger.info("[GeminiRerank] No deterministic candidates; using deterministic fallback.")
        return _fallback_response(deterministic_response, "unavailable")

    allowed_ids = {result.opportunity_id for result in deterministic_response.results[:10]}
    prompt = build_gemini_prompt(profile, deterministic_response)

    try:
        logger.info("[GeminiRerank] Reranking started; candidates=%d.", len(allowed_ids))
        raw = await _call_gemini(prompt)
        validated = validate_gemini_response(raw, allowed_ids)
        result = _merge_response(deterministic_response, validated)
        logger.info("[GeminiRerank] Reranking succeeded; final=%d.", len(result.final_results))
        return result
    except asyncio.TimeoutError:
        logger.warning("[GeminiRerank] Gemini timed out; using deterministic fallback.")
        return _fallback_response(deterministic_response, "unavailable")
    except GeminiRerankingError as exc:
        message = str(exc).lower()
        status: GeminiStatus = "invalid_response"
        if "not configured" in message or "api key" in message:
            status = "not_configured"
        elif "unavailable" in message or "timeout" in message:
            status = "unavailable"
        logger.warning("[GeminiRerank] Validation/service failure: %s; fallback=%s.", exc, status)
        return _fallback_response(deterministic_response, status)
    except Exception as exc:
        logger.warning("[GeminiRerank] Gemini failed: %s; using deterministic fallback.", exc)
        return _fallback_response(deterministic_response, "unavailable")
