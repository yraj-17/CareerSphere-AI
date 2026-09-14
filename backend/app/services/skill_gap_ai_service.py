"""
Skill Gap AI Service — Phase 2B.

Responsibility
--------------
Accept the deterministic Phase 2A SkillAnalysisResponse, build a grounded
Qwen prompt, call Ollama, parse the structured JSON response, and return a
validated SkillGapAIInsights object.

Design principles
-----------------
* Phase 2A result is the sole source of truth — Qwen explains, never recalculates.
* Uses a dedicated AsyncClient with OLLAMA_SKILL_GAP_TIMEOUT_SECONDS (default 360s)
  so the skill gap prompt can have a longer budget than the chat timeout.
* Reuses existing ollama AsyncClient infrastructure (same host, model).
* Prompts are kept short and directive to stay within model response time.
* Never raises — returns (None, "unavailable") on any failure so the deterministic
  Phase 2A analysis always succeeds.
* Zero Qwen calls when status != "ok".
* One Qwen call maximum per skill analysis request.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional, Tuple

from ollama import AsyncClient
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.skill_analysis import (
    SkillAnalysisResponse,
    SkillGapAIInsights,
    SkillGapPriorityItem,
    SkillGapRoadmapStep,
)
from app.services.ollama_service import AIServiceError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dedicated client with a longer timeout for skill gap generation
# (the system prompt + structured JSON output takes more tokens than chat)
# ---------------------------------------------------------------------------

_client = AsyncClient(
    host=settings.OLLAMA_BASE_URL,
    timeout=settings.OLLAMA_SKILL_GAP_TIMEOUT_SECONDS,
)

# ---------------------------------------------------------------------------
# Prompt templates — kept intentionally short to reduce model latency
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a career skill-gap advisor. You receive a deterministic skill analysis result.
Your job: explain the gaps, identify strengths, and provide a learning roadmap.

STRICT RULES:
- Only include skills from the provided missing_required and missing_recommended lists.
- Do not add, invent, or remove any skill.
- Do not recalculate coverage percentages.
- missing_required skills → priority "high"; missing_recommended → "medium" or "low".
- Limit roadmap to 6 steps maximum.
- Return ONLY valid JSON, no markdown, no extra text.

JSON schema:
{
  "summary": "2-3 sentences on readiness for the target role",
  "strengths": ["skill from matched list only"],
  "priority_gaps": [{"skill": "name", "priority": "high|medium|low", "reason": "1 sentence"}],
  "learning_order": ["skill1", "skill2"],
  "roadmap": [{"step": 1, "skill": "name", "focus": "1 sentence", "suggested_practice": "1 sentence"}]
}"""


_USER_PROMPT_TEMPLATE = """\
TARGET: {target_role}
RESOLVED ROLES: {resolved_roles}
COVERAGE: required={required_pct}%, recommended={recommended_pct}%, overall={overall_pct}%

ALREADY HAS: {matched_skills}
MISSING REQUIRED (high priority): {missing_required}
MISSING RECOMMENDED (medium/low priority): {missing_recommended}

Return valid JSON only."""


# ---------------------------------------------------------------------------
# JSON extraction — same pattern as profile_optimizer_service
# ---------------------------------------------------------------------------


def _extract_json_object(text: str) -> dict:
    """Strip think tags and markdown fences, then parse JSON."""
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise AIServiceError("Qwen returned unparseable JSON for skill gap insights.")
        try:
            parsed = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            raise AIServiceError("Qwen returned unparseable JSON for skill gap insights.") from exc
    if not isinstance(parsed, dict):
        raise AIServiceError("Qwen returned unexpected response type for skill gap insights.")
    return parsed


# ---------------------------------------------------------------------------
# Grounding enforcement — strip any hallucinated skills from Qwen output
# ---------------------------------------------------------------------------


def _sanitize_insights(
    raw: SkillGapAIInsights,
    allowed_skills_lower: set[str],
    owned_skills_lower: set[str],
) -> SkillGapAIInsights:
    """
    Remove hallucinated skills from AI output.

    - priority_gaps, learning_order, roadmap: only keep entries in allowed set
    - strengths: only keep entries in owned set
    - Re-index roadmap step numbers after filtering
    """
    def _n(s: str) -> str:
        return (s or "").strip().lower()

    clean_gaps = [g for g in raw.priority_gaps if _n(g.skill) in allowed_skills_lower]
    clean_order = [s for s in raw.learning_order if _n(s) in allowed_skills_lower]
    clean_roadmap = [s for s in raw.roadmap if _n(s.skill) in allowed_skills_lower]
    for idx, step in enumerate(clean_roadmap, start=1):
        step.step = idx
    clean_strengths = [s for s in raw.strengths if _n(s) in owned_skills_lower]

    return raw.model_copy(update={
        "priority_gaps": clean_gaps,
        "learning_order": clean_order,
        "roadmap": clean_roadmap,
        "strengths": clean_strengths,
    })


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def _build_prompt(analysis: SkillAnalysisResponse) -> str:
    """Build the compact grounded user prompt from the Phase 2A result."""
    coverage = analysis.coverage

    def _fmt(items: list[str]) -> str:
        return ", ".join(items) if items else "none"

    return _USER_PROMPT_TEMPLATE.format(
        target_role=analysis.target_role or "(unknown)",
        resolved_roles=", ".join(analysis.resolved_roles) if analysis.resolved_roles else "none",
        required_pct=coverage.required_pct if coverage else 0,
        recommended_pct=coverage.recommended_pct if coverage else 0,
        overall_pct=coverage.overall_pct if coverage else 0,
        matched_skills=_fmt(analysis.skills_have),
        missing_required=_fmt(analysis.skills_missing_required),
        missing_recommended=_fmt(analysis.skills_missing_recommended),
    )


# ---------------------------------------------------------------------------
# Internal Ollama call using the dedicated client
# ---------------------------------------------------------------------------


async def _call_qwen(prompt: str) -> str:
    """Call Ollama using the dedicated skill-gap client (longer timeout)."""
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    try:
        response = await _client.chat(
            model=settings.OLLAMA_MODEL,
            messages=messages,
            think=False,
        )
    except Exception as exc:
        raise AIServiceError(str(exc)) from exc

    message = response.get("message") if isinstance(response, dict) else getattr(response, "message", None)
    if isinstance(message, dict):
        content = message.get("content")
    else:
        content = getattr(message, "content", None) if message is not None else None

    if not isinstance(content, str):
        raise AIServiceError("Qwen returned an unexpected response for skill gap insights.")
    return content


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def generate_skill_gap_insights(
    analysis: SkillAnalysisResponse,
) -> Tuple[Optional[SkillGapAIInsights], str]:
    """
    Generate AI skill gap insights for the given Phase 2A analysis.

    Parameters
    ----------
    analysis:
        Completed Phase 2A SkillAnalysisResponse.

    Returns
    -------
    (SkillGapAIInsights, "ok")           — success
    (None, "not_applicable")             — status != "ok", no gap to explain
    (None, "unavailable")                — Qwen failed / timed out / bad JSON
    """
    if analysis.status != "ok":
        logger.debug("[SkillGapAI] Skipping — analysis status='%s'", analysis.status)
        return None, "not_applicable"

    all_missing_lower = {
        s.strip().lower()
        for s in analysis.skills_missing_required + analysis.skills_missing_recommended
    }
    owned_lower = {s.strip().lower() for s in analysis.skills_have}

    prompt = _build_prompt(analysis)

    try:
        logger.debug(
            "[SkillGapAI] Calling Qwen for target='%s' resolved=%s",
            analysis.target_role,
            analysis.resolved_roles,
        )
        content = await _call_qwen(prompt)
        raw_dict = _extract_json_object(content)
        raw_insights = SkillGapAIInsights.model_validate(raw_dict)
        insights = _sanitize_insights(raw_insights, all_missing_lower, owned_lower)

        logger.info(
            "[SkillGapAI] Success: target='%s' priority_gaps=%d roadmap_steps=%d",
            analysis.target_role,
            len(insights.priority_gaps),
            len(insights.roadmap),
        )
        return insights, "ok"

    except AIServiceError as exc:
        logger.warning("[SkillGapAI] AI service error: %s", exc)
        return None, "unavailable"
    except (ValidationError, KeyError, TypeError, ValueError) as exc:
        logger.warning("[SkillGapAI] Failed to parse Qwen response: %s", exc)
        return None, "unavailable"
    except Exception as exc:
        logger.warning("[SkillGapAI] Unexpected error: %s", exc)
        return None, "unavailable"
