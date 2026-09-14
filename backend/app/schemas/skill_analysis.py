"""
Pydantic schemas for the Skill Analysis API (Phase 2A + Phase 2B).

Phase 2A models (deterministic):
    SkillMatch, SkillCoverage, SkillAnalysisResponse

Phase 2B models (AI explanation layer):
    SkillGapPriorityItem, SkillGapRoadmapStep,
    SkillGapAIInsights, SkillAnalysisWithAIResponse

No database models are changed.  The source data is:

    - career_preferences.target_job_role   (existing field, PostgreSQL)
    - profile_skills                       (existing table)
    - project_technologies                 (existing table)
    - career_knowledge.py                  (Phase 1 dataset)
    - Qdrant career_content collection     (Phase 1 vectors)
    - Ollama/Qwen                          (AI explanation — Phase 2B only)
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Individual skill with match status
# ---------------------------------------------------------------------------


class SkillMatch(BaseModel):
    """A single required or recommended skill with the user's ownership status."""

    name: str
    """Display name from the Phase 1 skill catalog."""

    category: str
    """Broad category, e.g. 'programming', 'devops', 'design'."""

    have: bool
    """True if the user's profile/projects already include this skill."""


# ---------------------------------------------------------------------------
# Coverage breakdown
# ---------------------------------------------------------------------------


class SkillCoverage(BaseModel):
    """Percentage breakdown of skills the user already has."""

    required_pct: int
    """Percentage of required skills the user currently has (0–100)."""

    recommended_pct: int
    """Percentage of recommended skills the user currently has (0–100)."""

    overall_pct: int
    """Percentage of all target skills (required + recommended) the user has."""


# ---------------------------------------------------------------------------
# Main response
# ---------------------------------------------------------------------------


class SkillAnalysisResponse(BaseModel):
    """
    Full skill analysis result for the authenticated user.

    status values
    -------------
    "ok"              — target role resolved and analysis completed
    "no_target_role"  — user has no Target Role in Career Preferences
    "no_match"        — target role could not be mapped to any Phase 1 role
    """

    status: Literal["ok", "no_target_role", "no_match"]

    target_role: Optional[str] = None
    """Raw value from career_preferences.target_job_role."""

    resolved_roles: List[str] = []
    """
    Phase 1 role names matched to the user's target.
    May contain 1–3 roles for hybrid targets.
    Empty on no_target_role or no_match.
    """

    resolution_scores: Dict[str, float] = {}
    """
    Cosine similarity score for each resolved role.
    Key is the Phase 1 role name; value is the Qdrant score (0.0–1.0).
    All 1.0 for exact matches.
    Empty on no_target_role or no_match.
    """

    resolution_method: Optional[Literal["exact", "semantic"]] = None
    """
    How the target role was resolved:
    "exact"    — case-insensitive name match, no Qdrant call
    "semantic" — Qdrant cosine similarity search
    None       — resolution not attempted (no_target_role / no_match)
    """

    required_skills: List[SkillMatch] = []
    """
    Union of required skills from all resolved roles, sorted by name.
    Each entry indicates whether the user currently has that skill.
    """

    recommended_skills: List[SkillMatch] = []
    """
    Union of recommended skills from all resolved roles (minus any that
    appear in required_skills), sorted by name.
    """

    skills_have: List[str] = []
    """Skill display names the user has that appear in required or recommended."""

    skills_missing_required: List[str] = []
    """Required skill display names the user does not yet have."""

    skills_missing_recommended: List[str] = []
    """Recommended skill display names the user does not yet have."""

    coverage: Optional[SkillCoverage] = None
    """Coverage percentages. None on no_target_role or no_match."""

    message: Optional[str] = None
    """
    Human-readable explanation shown on fallback statuses.
    None when status is "ok".
    """


# ---------------------------------------------------------------------------
# Phase 2B — AI Explanation Layer
# ---------------------------------------------------------------------------


class SkillGapPriorityItem(BaseModel):
    """A single skill identified by Qwen as a priority gap."""

    skill: str
    """Skill display name — must appear in the Phase 2A missing skills list."""

    priority: Literal["high", "medium", "low"]
    """
    Importance tier:
    "high"   — required skill, missing; blocks core job function
    "medium" — recommended skill, significantly improves employability
    "low"    — nice-to-have; lower urgency
    """

    reason: str
    """Brief (1–2 sentence) explanation of why this skill matters for the target role."""


class SkillGapRoadmapStep(BaseModel):
    """A single ordered step in the AI-generated learning roadmap."""

    step: int
    """1-indexed position in the learning sequence."""

    skill: str
    """Skill display name for this step."""

    focus: str
    """What to focus on when learning this skill (concise, 1–2 sentences)."""

    suggested_practice: str
    """Practical exercise or mini-project to build this skill (1–2 sentences)."""


class SkillGapAIInsights(BaseModel):
    """
    Structured AI explanation produced by Qwen based on the Phase 2A
    deterministic skill analysis.

    Qwen is strictly grounded in the Phase 2A result:
    - It may not add skills not in the provided gap analysis.
    - It may not recalculate coverage.
    - It may not remove or modify the determined skill lists.
    - It explains, prioritises, and recommends a learning order only.
    """

    summary: str
    """
    2–4 sentence overall assessment of the user's readiness for their target role.
    Must reference the resolved role(s) and the overall coverage percentage.
    """

    strengths: List[str]
    """
    Skills the user already has that are directly relevant to the target role.
    Sourced from the Phase 2A skills_have list.
    """

    priority_gaps: List[SkillGapPriorityItem]
    """
    Ordered list of skill gaps to address.  Required missing skills appear first
    (high priority), followed by recommended missing skills (medium/low priority).
    Only skills from the Phase 2A missing lists are included.
    """

    learning_order: List[str]
    """
    Flat ordered list of skill names representing the recommended learning sequence.
    Each entry should appear in priority_gaps.
    """

    roadmap: List[SkillGapRoadmapStep]
    """
    Step-by-step learning roadmap.  Each step corresponds to one skill in
    learning_order and contains focused guidance and a practical exercise.
    """


class SkillAnalysisWithAIResponse(SkillAnalysisResponse):
    """
    Full skill analysis response including optional Qwen AI insights.

    Extends SkillAnalysisResponse with two additional fields:

    ai_insights:
        Populated when include_ai=true and Qwen responds successfully.
        None when include_ai=false, or when Qwen is unavailable/fails.

    ai_status:
        "ok"          — AI insights were generated successfully
        "skipped"     — include_ai=false (default, no AI call made)
        "unavailable" — Qwen timed out, failed, or returned unparseable output
        "not_applicable" — status is no_target_role or no_match (no gap to explain)
    """

    ai_insights: Optional[SkillGapAIInsights] = None
    ai_status: Literal["ok", "skipped", "unavailable", "not_applicable"] = "skipped"
