"""
Career Matching orchestration over real, provider-sourced job listings.

PostgreSQL (active listings) → deterministic eligibility + scoring → pagination
→ optional Gemini rerank notes / Qwen explanations for the top results → Redis cache.

Candidate retrieval is a PostgreSQL query, not vector search: it cannot go stale
when listings change and does not depend on the embedding model being reachable.
Every empty response carries a specific status explaining why it is empty.
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.db.models import Opportunity, Profile, ProfileProject, User
from app.schemas.career_matching_api import (
    AppliedFilters,
    CareerMatchingAPIResponse,
    CareerMatchingCacheInfo,
    FilterOptions,
    JobMatchResult,
    ListingAvailability,
    ProfileMatchSummary,
)
from app.services.career_matching_cache_service import (
    career_matching_cache_key,
    get_cached_career_matching,
    set_cached_career_matching,
)
from app.services.career_matching_service import (
    CITY_ALIASES,
    city_tokens,
    ALGORITHM_VERSION,
    MatchFilters,
    MatchRun,
    ProfileFacts,
    ScoredListing,
    profile_facts,
    rank_listings,
    to_matching_response,
)
from app.services.job_sync_service import (
    PROVIDER_KEYS,
    UNSEEN_STALE_DAYS,
    get_dataset_version,
    listing_availability,
)

logger = logging.getLogger(__name__)

SOURCE_LABELS = {"greenhouse": "Greenhouse", "lever": "Lever", "ashby": "Ashby", "adzuna": "Adzuna", "remotive": "Remotive"}
AI_TOP_N = 5


def load_profile_for_career_matching(db: Session, user: User) -> Optional[Profile]:
    return (
        db.query(Profile)
        .options(
            selectinload(Profile.skills),
            selectinload(Profile.experience),
            selectinload(Profile.education),
            selectinload(Profile.projects).selectinload(ProfileProject.technologies),
            selectinload(Profile.career_preferences),
        )
        .filter(Profile.user_id == user.id)
        .one_or_none()
    )


def load_active_listings(db: Session, now: Optional[datetime] = None) -> list[Opportunity]:
    """Active, unexpired, recently confirmed provider listings."""
    now = now or datetime.now(timezone.utc)
    return (
        db.query(Opportunity)
        .options(selectinload(Opportunity.required_skills), selectinload(Opportunity.preferred_skills))
        .filter(
            Opportunity.is_active.is_(True),
            Opportunity.source.in_(PROVIDER_KEYS),
            Opportunity.last_seen_at >= now - timedelta(days=UNSEEN_STALE_DAYS),
            or_(Opportunity.expires_at.is_(None), Opportunity.expires_at > now),
        )
        .all()
    )


def _summary(facts: ProfileFacts) -> ProfileMatchSummary:
    return ProfileMatchSummary(
        target_roles=facts.target_roles,
        skills_count=len(facts.skill_ids),
        experience_level=facts.level_name,
        experience_years=facts.experience_years,
        preferred_work_type=facts.preferred_work_type,
        preferred_locations=facts.preferred_locations,
    )


def _match_label(score: float) -> str:
    if score >= 75:
        return "Strong match"
    if score >= 60:
        return "Good match"
    return "Partial match"


def _to_result(scored: ScoredListing) -> JobMatchResult:
    opp = scored.opportunity
    score = scored.result.final_score
    explanation = " ".join(scored.reasons[:2]) or "Matches parts of your profile."
    return JobMatchResult(
        opportunity_id=opp.id,
        title=opp.title,
        company=opp.company,
        location=opp.location,
        country=opp.country,
        work_mode=opp.work_mode or ("remote" if opp.is_remote else None),
        is_remote=bool(opp.is_remote),
        employment_type=opp.employment_type,
        opportunity_type=opp.opportunity_type,
        target_role=opp.target_role,
        experience_level=opp.experience_level,
        experience_min_years=opp.experience_min_years,
        experience_max_years=opp.experience_max_years,
        salary_min=opp.salary_min,
        salary_max=opp.salary_max,
        salary_currency=opp.salary_currency,
        salary_period=opp.salary_period,
        salary_text=opp.salary_text,
        posted_at=opp.published_at,
        source=opp.source,
        source_label=SOURCE_LABELS.get(opp.source, opp.source),
        source_board=opp.source_board,
        attribution=opp.source_attribution,
        job_url=opp.job_url or opp.application_url,
        application_url=opp.application_url or opp.job_url,
        match_score=score,
        match_label=_match_label(score),  # type: ignore[arg-type]
        matched_skills=scored.matched_skills,
        missing_skills=scored.missing_skills[:8],
        match_reasons=scored.reasons,
        explanation=explanation,
        breakdown=scored.result.breakdown,
    )


def _filter_options(listings: list[Opportunity]) -> FilterOptions:
    cities: Counter = Counter()
    for opp in listings:
        if opp.location and opp.work_mode != "remote":
            known = city_tokens(opp.location)
            canonical = sorted(c for c in known if c in CITY_ALIASES.values())
            if canonical:  # "Bangalore" / "Bengaluru" collapse into one option
                cities[canonical[0].title()] += 1
    return FilterOptions(
        locations=[city for city, _ in cities.most_common(15)],
        work_modes=sorted({opp.work_mode for opp in listings if opp.work_mode}),
        employment_types=sorted({opp.employment_type for opp in listings if opp.employment_type}),
        sources=sorted({opp.source for opp in listings}),
    )


def _suggestions(facts: ProfileFacts, run: MatchRun, filters: MatchFilters) -> list[str]:
    tips: list[str] = []
    if any(getattr(filters, name) for name in ("location", "work_mode", "employment_type", "experience", "source")):
        filtered_out = sum(v for k, v in run.excluded.items() if k.startswith("filter_"))
        tips.append(f"Your filters excluded {filtered_out} listing(s). Clear or widen the filters to see more.")
    if not facts.target_roles:
        tips.append("Add a target role in Career Preferences so listings can be matched by job title.")
    if len(facts.skill_ids) < 5:
        tips.append("Add more skills, including the technologies used in your projects; matching compares them to each listing.")
    if run.excluded.get("far_above_experience"):
        tips.append(f"{run.excluded['far_above_experience']} listing(s) were for lead/staff/management roles above your current experience.")
    if run.excluded.get("low_relevance") and facts.target_roles:
        tips.append(f"Current listings did not match your target role ({', '.join(facts.target_roles)}). "
                    "Consider adding related roles (e.g. 'Software Engineer') to your target roles.")
    work_type = (facts.preferred_work_type or "").lower()
    if work_type and "flexible" not in work_type and not filters.work_mode:
        tips.append("Setting your preferred work type to 'Flexible' ranks on-site, hybrid and remote listings more evenly.")
    return tips


def _empty(status: str, message: str, **kwargs) -> CareerMatchingAPIResponse:
    return CareerMatchingAPIResponse(status=status, message=message, **kwargs)  # type: ignore[arg-type]


async def _annotate_with_ai(profile: Profile, run: MatchRun, page_results: list[JobMatchResult]) -> tuple[str, str]:
    """Attach Gemini rerank notes and Qwen explanations to the top results. Scores/order never change."""
    from app.services.gemini_reranking_service import rerank_career_matches
    from app.services.qwen_match_explanation_service import generate_match_explanations

    reranked = await rerank_career_matches(profile, to_matching_response(profile.id, run, limit=10))
    explanations, qwen_status = await generate_match_explanations(profile, reranked.final_results[:AI_TOP_N])
    notes = {r.opportunity_id: r for r in reranked.final_results}
    for item in page_results:
        note = notes.get(item.opportunity_id)
        if note is not None:
            item.rerank_reason = note.rerank_reason
            item.confidence = note.confidence
        item.ai_explanation = explanations.get(item.opportunity_id)
    return reranked.gemini_status, qwen_status


async def run_career_matching_pipeline(
    db: Session,
    user: User,
    include_ai: bool = False,
    filters: Optional[MatchFilters] = None,
    page: int = 1,
    page_size: int = 10,
) -> CareerMatchingAPIResponse:
    filters = filters or MatchFilters()
    applied = AppliedFilters(**filters.__dict__)
    profile = load_profile_for_career_matching(db, user)
    if profile is None:
        return _empty("no_profile", "Create your profile to get matched with real job listings.",
                      missing_profile_fields=["profile"], applied_filters=applied)

    facts = profile_facts(profile)
    summary = _summary(facts)
    if not facts.is_complete:
        return _empty("incomplete_profile",
                      "Add a target role or at least a few skills so CareerSphere can match you with real job listings.",
                      missing_profile_fields=["target_job_role", "skills"], profile_summary=summary, applied_filters=applied)

    availability = ListingAvailability(**listing_availability(db))
    if availability.active_listings == 0:
        if not availability.configured_providers:
            return _empty("no_jobs_available", "No job providers are configured yet, so there are no listings to match.",
                          profile_summary=summary, availability=availability, applied_filters=applied)
        if availability.providers_with_errors:
            return _empty("provider_error",
                          f"Job listings could not be loaded from: {', '.join(availability.providers_with_errors)}. "
                          "We'll retry automatically.", profile_summary=summary, availability=availability, applied_filters=applied)
        message = ("Job listings are being imported right now. Please check back in a few minutes."
                   if availability.sync_running or availability.last_successful_sync_at is None
                   else "No active job listings are available from the configured providers right now.")
        return _empty("no_jobs_available", message, profile_summary=summary, availability=availability, applied_filters=applied)

    page = max(1, page)
    page_size = max(1, min(page_size, 50))
    cache_key = career_matching_cache_key(
        user.id, profile, extra=f"{ALGORITHM_VERSION}|{get_dataset_version()}|{sorted(filters.__dict__.items())}|{page}|{page_size}|{include_ai}")
    cached = get_cached_career_matching(cache_key)
    if cached:
        try:
            response = CareerMatchingAPIResponse.model_validate(cached)
            response.cache = CareerMatchingCacheInfo(hit=True, key=cache_key)
            response.availability = availability
            return response
        except Exception:
            logger.warning("[CareerMatchingPipeline] Ignoring malformed cached response.")

    listings = load_active_listings(db)
    run = rank_listings(facts, listings, filters)
    filter_options = _filter_options(listings)
    total = len(run.matches)
    common = dict(
        target_role=facts.target_role_text, profile_summary=summary, candidates_considered=run.considered,
        excluded_counts=run.excluded, availability=availability, applied_filters=applied, filter_options=filter_options,
        page=page, page_size=page_size,
    )
    if total == 0:
        return _empty("no_relevant_matches",
                      f"None of the {run.considered} active listings is a relevant match for your profile"
                      f"{' and filters' if any(filters.__dict__.values()) else ''} right now.",
                      suggestions=_suggestions(facts, run, filters), **common)

    start = (page - 1) * page_size
    page_results = [_to_result(scored) for scored in run.matches[start:start + page_size]]
    gemini_status, qwen_status = "not_configured", "skipped"
    if include_ai and page == 1:
        try:
            gemini_status, qwen_status = await _annotate_with_ai(profile, run, page_results)
        except Exception as exc:  # AI is optional; deterministic results stand on their own
            logger.warning("[CareerMatchingPipeline] AI annotation failed: %s", exc)
            gemini_status, qwen_status = "unavailable", "unavailable"

    response = CareerMatchingAPIResponse(
        status="success",
        results=page_results,
        total_matches=total,
        total_pages=math.ceil(total / page_size),
        suggestions=_suggestions(facts, run, filters) if total < 3 else [],
        gemini_status=gemini_status,  # type: ignore[arg-type]
        qwen_status=qwen_status,  # type: ignore[arg-type]
        used_deterministic_fallback=gemini_status != "success",
        used_qwen_fallback=qwen_status != "success",
        cache=CareerMatchingCacheInfo(hit=False, key=cache_key),
        **common,
    )
    set_cached_career_matching(cache_key, response.model_dump(mode="json"))
    return response
