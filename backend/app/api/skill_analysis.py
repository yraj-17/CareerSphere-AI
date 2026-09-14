"""
Skill Analysis API — Phase 2A + Phase 2B.

Endpoints
---------
GET /api/skill-analysis/me
GET /api/skill-analysis/me?include_ai=true

Phase 2A (deterministic):
    Always returned.  Reads career_preferences.target_job_role, resolves to
    Phase 1 roles via exact match or Qdrant semantic search, merges skills,
    compares against profile skills and project technologies.

Phase 2B (AI explanation — optional):
    Activated by ?include_ai=true.  Sends the Phase 2A result to Qwen via
    the existing ollama_service.  If Qwen is unavailable, the deterministic
    result is still returned with ai_status="unavailable".

Responsibility boundary:
    PostgreSQL → user profile/skills/preferences
    Qdrant     → role resolution + career knowledge
    Backend    → deterministic skill comparison and coverage
    Qwen       → explanation, prioritisation, learning roadmap
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_db
from app.db.models import Profile, ProfileProject, User
from app.schemas.skill_analysis import SkillAnalysisWithAIResponse
from app.services.embedding_service import EmbeddingServiceError
from app.services.skill_analysis_service import build_skill_analysis
from app.services.skill_gap_ai_service import generate_skill_gap_insights

router = APIRouter(prefix="/skill-analysis", tags=["Skill Analysis"])


def _load_profile_for_analysis(db: Session, user: User) -> Profile:
    """
    Load the user's profile with all relationships needed for skill analysis.
    Returns a stub profile if none exists so the response is always meaningful.
    """
    profile = (
        db.query(Profile)
        .options(
            selectinload(Profile.user),
            selectinload(Profile.skills),
            selectinload(Profile.projects).selectinload(ProfileProject.technologies),
            selectinload(Profile.career_preferences),
        )
        .filter(Profile.user_id == user.id)
        .first()
    )
    if profile is None:
        profile = Profile(user_id=user.id)
        profile.skills = []
        profile.projects = []
        profile.career_preferences = None
    return profile


@router.get(
    "/me",
    response_model=SkillAnalysisWithAIResponse,
    summary="Get skill analysis for the current user",
    description=(
        "Returns a full skill gap analysis for the authenticated user based on "
        "their Career Preferences → Target Role.\n\n"
        "**Phase 2A — Deterministic (always returned):**\n"
        "- Reads `career_preferences.target_job_role` (no new fields)\n"
        "- Exact name match or Qdrant semantic search (filtered to roles only)\n"
        "- Supports hybrid targets e.g. 'Backend and Devops' → 2 resolved roles\n"
        "- Merges required/recommended skills; required beats recommended\n"
        "- Compares against `profile_skills` + `project_technologies`\n"
        "- Returns coverage percentages\n\n"
        "**Phase 2B — AI Explanation (opt-in via `?include_ai=true`):**\n"
        "- Sends the Phase 2A result to Qwen via the existing Ollama service\n"
        "- Returns `ai_insights` with summary, strengths, priority gaps, "
        "learning order, and roadmap\n"
        "- Qwen is strictly grounded: it cannot modify the deterministic skill lists\n"
        "- If Qwen is unavailable, `ai_insights=null` and `ai_status='unavailable'`; "
        "the deterministic result is unaffected\n\n"
        "Returns `status='no_target_role'` if no Target Role is set.\n"
        "Returns `status='no_match'` if the target cannot be mapped to any known role."
    ),
)
async def get_skill_analysis(
    include_ai: bool = Query(
        default=False,
        description=(
            "Set to true to include Qwen AI skill-gap explanation, learning priority, "
            "and roadmap alongside the deterministic analysis."
        ),
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SkillAnalysisWithAIResponse:
    """Skill analysis (deterministic + optional AI insights) for the authenticated user."""

    # ── Phase 2A: deterministic analysis ─────────────────────────────────
    profile = _load_profile_for_analysis(db, current_user)

    try:
        det_result = build_skill_analysis(profile)
    except EmbeddingServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "The embedding service is currently unavailable. "
                "Ensure Ollama is running with the nomic-embed-text model. "
                f"Details: {exc}"
            ),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Skill analysis is temporarily unavailable. Details: {exc}",
        )

    # Wrap in SkillAnalysisWithAIResponse (superset of SkillAnalysisResponse)
    combined = SkillAnalysisWithAIResponse(
        **det_result.model_dump(),
        ai_insights=None,
        ai_status="skipped",
    )

    # ── Phase 2B: AI insights (optional, never breaks deterministic result) ──
    if not include_ai:
        return combined

    # No gap to explain for fallback statuses
    if det_result.status != "ok":
        combined.ai_status = "not_applicable"
        return combined

    ai_insights, ai_status = await generate_skill_gap_insights(det_result)
    combined.ai_insights = ai_insights
    combined.ai_status = ai_status  # type: ignore[assignment]

    return combined
