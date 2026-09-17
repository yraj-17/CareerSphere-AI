"""Final Career Matching orchestration for Phase 3.6."""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session, selectinload

from app.db.models import Opportunity, Profile, ProfileProject, User
from app.schemas.career_matching_api import (
    CareerMatchingAPIResponse,
    CareerMatchingCacheInfo,
    CareerMatchingFinalResult,
)
from app.schemas.gemini_reranking import CareerMatchRerankedResult
from app.services.career_matching_cache_service import (
    career_matching_cache_key,
    get_cached_career_matching,
    set_cached_career_matching,
)
from app.services.career_matching_service import match_opportunities
from app.services.gemini_reranking_service import rerank_career_matches
from app.services.opportunity_embedding_service import search_opportunities
from app.services.qwen_match_explanation_service import generate_match_explanations

logger = logging.getLogger(__name__)


def load_profile_for_career_matching(db: Session, user: User) -> Optional[Profile]:
    return (
        db.query(Profile)
        .options(
            selectinload(Profile.skills),
            selectinload(Profile.experience),
            selectinload(Profile.projects).selectinload(ProfileProject.technologies),
            selectinload(Profile.career_preferences),
        )
        .filter(Profile.user_id == user.id)
        .one_or_none()
    )


def _target_role(profile: Profile) -> Optional[str]:
    pref = profile.career_preferences
    return pref.target_job_role if pref and pref.target_job_role else None


def _retrieval_query(profile: Profile) -> str:
    pref = profile.career_preferences
    skills = ", ".join(skill.name for skill in profile.skills[:12])
    projects = ", ".join(project.name for project in profile.projects[:5])
    parts = [
        pref.target_job_role if pref else "",
        pref.preferred_industry if pref else "",
        pref.preferred_work_type if pref else "",
        profile.location or "",
        skills,
        projects,
    ]
    return " ".join(part for part in parts if part).strip() or "career opportunity"


def _load_retrieved_opportunities(db: Session, profile: Profile, limit: int = 30) -> list[Opportunity]:
    hits = search_opportunities(_retrieval_query(profile), limit=limit)
    ids = []
    for hit in hits:
        opportunity_id = (hit.payload or {}).get("opportunity_id")
        if opportunity_id and opportunity_id not in ids:
            ids.append(opportunity_id)
    if not ids:
        return []
    ordering = {opportunity_id: index for index, opportunity_id in enumerate(ids)}
    opportunities = db.query(Opportunity).filter(Opportunity.id.in_(ids)).all()
    return sorted(opportunities, key=lambda opportunity: ordering.get(opportunity.id, 9999))


def _final_result(
    reranked: CareerMatchRerankedResult,
    opportunity: Optional[Opportunity],
    explanation,
) -> CareerMatchingFinalResult:
    return CareerMatchingFinalResult(
        opportunity_id=reranked.opportunity_id,
        title=reranked.title,
        company=reranked.company,
        location=opportunity.location if opportunity else None,
        is_remote=bool(opportunity.is_remote) if opportunity else False,
        opportunity_type=opportunity.opportunity_type if opportunity else "job",
        target_role=opportunity.target_role if opportunity else reranked.breakdown.target_role_match.opportunity_target_role,
        experience_level=opportunity.experience_level if opportunity else None,
        industry=opportunity.industry if opportunity else None,
        deterministic_score=reranked.final_score,
        breakdown=reranked.breakdown,
        semantic_rank=reranked.semantic_rank,
        rerank_reason=reranked.rerank_reason,
        confidence=reranked.confidence,
        explanation=explanation,
    )


async def run_career_matching_pipeline(
    db: Session,
    user: User,
    include_ai: bool = True,
) -> CareerMatchingAPIResponse:
    profile = load_profile_for_career_matching(db, user)
    if profile is None:
        return CareerMatchingAPIResponse(
            status="no_profile",
            target_role=None,
            gemini_status="unavailable",
            qwen_status="skipped",
            used_deterministic_fallback=True,
            used_qwen_fallback=True,
            cache=CareerMatchingCacheInfo(hit=False),
        )

    target_role = _target_role(profile)
    if not target_role:
        return CareerMatchingAPIResponse(
            status="no_target_role",
            target_role=None,
            gemini_status="unavailable",
            qwen_status="skipped",
            used_deterministic_fallback=True,
            used_qwen_fallback=True,
            cache=CareerMatchingCacheInfo(hit=False),
        )

    cache_key = career_matching_cache_key(user.id, profile)
    cached = get_cached_career_matching(cache_key)
    if cached:
        try:
            response = CareerMatchingAPIResponse.model_validate(cached)
            response.cache = CareerMatchingCacheInfo(hit=True, key=cache_key)
            return response
        except Exception:
            logger.warning("[CareerMatchingPipeline] Ignoring malformed cached response.")

    opportunities = _load_retrieved_opportunities(db, profile, limit=30)
    deterministic = match_opportunities(profile, opportunities, limit=10)

    if include_ai:
        reranked = await rerank_career_matches(profile, deterministic)
    else:
        from app.services.gemini_reranking_service import _fallback_response

        reranked = _fallback_response(deterministic, "unavailable")

    explanations = {}
    qwen_status = "skipped"
    if include_ai:
        explanations, qwen_status = await generate_match_explanations(profile, reranked.final_results)

    opportunity_by_id = {opportunity.id: opportunity for opportunity in opportunities}
    final_results = [
        _final_result(result, opportunity_by_id.get(result.opportunity_id), explanations.get(result.opportunity_id))
        for result in reranked.final_results
    ]

    response = CareerMatchingAPIResponse(
        status="success",
        target_role=target_role,
        deterministic_results=reranked.deterministic_results,
        final_results=final_results,
        gemini_status=reranked.gemini_status,
        qwen_status=qwen_status,  # type: ignore[arg-type]
        used_deterministic_fallback=reranked.used_deterministic_fallback,
        used_qwen_fallback=(qwen_status != "success"),
        cache=CareerMatchingCacheInfo(hit=False, key=cache_key),
    )
    set_cached_career_matching(cache_key, response.model_dump(mode="json"))
    return response
