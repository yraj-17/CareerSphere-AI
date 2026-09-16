"""
Deterministic career opportunity matching engine.

This phase deliberately does not use Qdrant scores, Gemini, Qwen, profile
embeddings, or random ranking. PostgreSQL profile data and PostgreSQL
opportunity rows are compared with stable, explainable rules.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Iterable, Optional, Sequence

from sqlalchemy.orm import Session, selectinload

from app.data.career_knowledge import ROLES, SKILLS
from app.db.models import Opportunity, Profile, ProfileProject
from app.schemas.career_matching import (
    CareerMatchBreakdown,
    CareerMatchingResponse,
    CareerMatchResult,
    ExperienceMatch,
    LocationMatch,
    PreferenceMatchItem,
    SkillMatchSummary,
    TargetRoleMatch,
)


WEIGHTS = {
    "required_skills": 0.35,
    "preferred_skills": 0.15,
    "target_role": 0.15,
    "experience": 0.12,
    "location_remote": 0.08,
    "career_preferences": 0.15,
}

EXPERIENCE_LEVELS = {
    "intern": 0,
    "entry level": 1,
    "junior": 2,
    "mid level": 3,
}

STRONGLY_RELATED_ROLES = {
    frozenset(("Backend Engineer", "Full Stack Developer")),
    frozenset(("Frontend Developer", "Full Stack Developer")),
    frozenset(("DevOps Engineer", "Cloud Engineer")),
    frozenset(("Machine Learning Engineer", "Data Scientist")),
    frozenset(("Data Scientist", "Data Analyst")),
    frozenset(("Product Manager", "Business Analyst")),
    frozenset(("UI/UX Designer", "Product Designer")),
}

PARTIALLY_RELATED_GROUPS = (
    {
        "Backend Engineer",
        "Full Stack Developer",
        "Frontend Developer",
        "DevOps Engineer",
        "Cloud Engineer",
        "Machine Learning Engineer",
        "Data Scientist",
        "Data Analyst",
    },
    {"Product Manager", "Business Analyst", "UI/UX Designer", "Product Designer"},
    {"Data Scientist", "Data Analyst", "Business Analyst", "Financial Analyst"},
)

_ROLE_BY_LOWER = {role.name.lower(): role.name for role in ROLES}
_SKILL_CANONICAL_BY_KEY: dict[str, str] = {}


def _canonical_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").strip().lower())


for _skill_id, _skill in SKILLS.items():
    for _value in [_skill_id, _skill.name, *_skill.aliases]:
        _SKILL_CANONICAL_BY_KEY[_canonical_key(_value)] = _skill_id


def normalize_skill_name(value: str) -> str:
    key = _canonical_key(value)
    return _SKILL_CANONICAL_BY_KEY.get(key, key)


def _score_pct(matched: int, total: int, empty_score: float = 0.0) -> float:
    if total == 0:
        return empty_score
    return round((matched / total) * 100, 2)


def _skill_summary(required_or_preferred: Iterable, user_skill_keys: set[str]) -> SkillMatchSummary:
    matched: list[str] = []
    missing: list[str] = []
    for skill in required_or_preferred:
        if normalize_skill_name(skill.normalized_name or skill.name) in user_skill_keys:
            matched.append(skill.name)
        else:
            missing.append(skill.name)
    return SkillMatchSummary(matched=matched, missing=missing)


def extract_user_skill_keys(profile: Profile) -> set[str]:
    keys: set[str] = set()
    for skill in profile.skills:
        keys.add(normalize_skill_name(skill.normalized_name or skill.name))
        keys.add(normalize_skill_name(skill.name))
    for project in profile.projects:
        for tech in project.technologies:
            keys.add(normalize_skill_name(tech.normalized_name or tech.name))
            keys.add(normalize_skill_name(tech.name))
    keys.discard("")
    return keys


def calculate_required_skill_score(opportunity: Opportunity, user_skill_keys: set[str]) -> tuple[float, SkillMatchSummary]:
    summary = _skill_summary(opportunity.required_skills, user_skill_keys)
    total = len(summary.matched) + len(summary.missing)
    return _score_pct(len(summary.matched), total), summary


def calculate_preferred_skill_score(opportunity: Opportunity, user_skill_keys: set[str]) -> tuple[float, SkillMatchSummary]:
    summary = _skill_summary(opportunity.preferred_skills, user_skill_keys)
    total = len(summary.matched) + len(summary.missing)
    return _score_pct(len(summary.matched), total, empty_score=100.0), summary


def _normalize_role(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    value = value.strip()
    return _ROLE_BY_LOWER.get(value.lower(), value)


def parse_target_roles(value: Optional[str]) -> list[str]:
    if not value or not value.strip():
        return []
    parts = re.split(r"[,/;|]+|\band\b", value, flags=re.IGNORECASE)
    roles: list[str] = []
    seen: set[str] = set()
    for part in parts:
        role = _normalize_role(part)
        if role and role.lower() not in seen:
            roles.append(role)
            seen.add(role.lower())
    return roles


def role_relationship_score(user_role: Optional[str], opportunity_role: str) -> tuple[float, str]:
    user_role = _normalize_role(user_role)
    opportunity_role = _normalize_role(opportunity_role) or opportunity_role
    if not user_role:
        return 100.0, "no_target_role_neutral"
    if user_role == opportunity_role:
        return 100.0, "exact"
    if frozenset((user_role, opportunity_role)) in STRONGLY_RELATED_ROLES:
        return 75.0, "strongly_related"
    if any(user_role in group and opportunity_role in group for group in PARTIALLY_RELATED_GROUPS):
        return 50.0, "partially_related"
    return 0.0, "unrelated"


def calculate_target_role_score(target_roles: Sequence[str], opportunity: Opportunity) -> tuple[float, TargetRoleMatch]:
    if not target_roles:
        score, relationship = role_relationship_score(None, opportunity.target_role)
        return score, TargetRoleMatch(
            user_target_roles=[],
            opportunity_target_role=opportunity.target_role,
            relationship=relationship,
            score=score,
        )

    scored = [(*role_relationship_score(role, opportunity.target_role), role) for role in target_roles]
    score, relationship, best_role = max(scored, key=lambda item: item[0])
    return score, TargetRoleMatch(
        user_target_roles=list(target_roles),
        opportunity_target_role=opportunity.target_role,
        relationship=f"{relationship}:{best_role}",
        score=score,
    )


def _months_between(start: Optional[date], end: Optional[date]) -> int:
    if not start:
        return 0
    end = end or date.today()
    return max(0, (end.year - start.year) * 12 + (end.month - start.month))


def determine_user_experience_level(profile: Profile) -> str:
    total_months = 0
    internship_months = 0
    for exp in profile.experience:
        months = _months_between(exp.start_date, None if exp.currently_working else exp.end_date)
        total_months += months
        title_blob = f"{exp.job_title or ''} {exp.employment_type or ''}".lower()
        if "intern" in title_blob:
            internship_months += months

    non_intern_months = max(0, total_months - internship_months)
    if non_intern_months == 0 and internship_months > 0:
        return "Intern"
    if non_intern_months < 6:
        return "Entry Level"
    if non_intern_months < 18:
        return "Entry Level"
    if non_intern_months < 36:
        return "Junior"
    return "Mid Level"


def calculate_experience_score(user_level: str, opportunity_level: Optional[str]) -> tuple[float, ExperienceMatch]:
    opp_level = opportunity_level or "Entry Level"
    user_rank = EXPERIENCE_LEVELS.get(user_level.lower(), 1)
    opp_rank = EXPERIENCE_LEVELS.get(opp_level.lower(), 1)
    diff = abs(user_rank - opp_rank)
    if diff == 0:
        score, relationship = 100.0, "exact"
    elif diff == 1:
        score, relationship = 75.0, "adjacent"
    elif diff == 2:
        score, relationship = 50.0, "two_levels_apart"
    else:
        score, relationship = 25.0, "large_mismatch"
    return score, ExperienceMatch(
        user_level=user_level,
        opportunity_level=opportunity_level,
        relationship=relationship,
        score=score,
    )


def _load_json_list(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    try:
        values = json.loads(raw)
        if isinstance(values, list):
            return [str(value) for value in values if str(value).strip()]
    except Exception:
        pass
    return [part.strip() for part in raw.split(",") if part.strip()]


def _norm_location(value: Optional[str]) -> str:
    if not value:
        return ""
    value = value.lower().replace("remote -", "").replace("india", "")
    return re.sub(r"[^a-z0-9]+", "", value)


def _locations_match(expected: Optional[str], actual: Optional[str]) -> bool:
    exp = _norm_location(expected)
    act = _norm_location(actual)
    return bool(exp and act and (exp == act or exp in act or act in exp))


def _prefers_remote(work_type: Optional[str]) -> bool:
    return bool(work_type and "remote" in work_type.lower())


def _prefers_onsite(work_type: Optional[str]) -> bool:
    if not work_type:
        return False
    lowered = work_type.lower()
    return any(token in lowered for token in ("onsite", "office", "hybrid"))


def requires_remote_only(work_type: Optional[str]) -> bool:
    if not work_type:
        return False
    lowered = work_type.lower()
    return "remote only" in lowered or "remote-only" in lowered


def explicit_opportunity_type(work_type: Optional[str]) -> Optional[str]:
    if not work_type:
        return None
    lowered = work_type.lower()
    if "internship" in lowered and ("only" in lowered or lowered.strip() == "internship"):
        return "internship"
    if any(token in lowered for token in ("full-time", "full time", "job only", "job")) and "internship" not in lowered:
        return "job"
    return None


def calculate_location_remote_score(profile: Profile, opportunity: Opportunity) -> tuple[float, LocationMatch]:
    pref = profile.career_preferences
    work_type = pref.preferred_work_type if pref else None
    preferred_locations = _load_json_list(pref.preferred_locations if pref else None)

    if opportunity.is_remote:
        if not work_type or _prefers_remote(work_type):
            score, relationship = 100.0, "remote_matches_or_no_preference"
        elif _prefers_onsite(work_type):
            score, relationship = 75.0, "remote_with_onsite_preference"
        else:
            score, relationship = 100.0, "remote_no_strong_conflict"
    else:
        if any(_locations_match(location, opportunity.location) for location in preferred_locations):
            score, relationship = 100.0, "preferred_location_match"
        elif _locations_match(profile.location, opportunity.location):
            score, relationship = 100.0, "profile_location_match"
        elif preferred_locations:
            score, relationship = 50.0, "preferred_location_differs"
        else:
            score, relationship = 80.0, "onsite_no_location_preference"

    return score, LocationMatch(
        profile_location=profile.location,
        preferred_locations=preferred_locations,
        preferred_work_type=work_type,
        opportunity_location=opportunity.location,
        opportunity_is_remote=bool(opportunity.is_remote),
        relationship=relationship,
        score=score,
    )


def calculate_career_preference_score(profile: Profile, opportunity: Opportunity) -> tuple[float, list[PreferenceMatchItem]]:
    pref = profile.career_preferences
    if not pref:
        return 100.0, []

    matches: list[PreferenceMatchItem] = []

    requested_type = explicit_opportunity_type(pref.preferred_work_type)
    if requested_type:
        matched = opportunity.opportunity_type == requested_type
        matches.append(PreferenceMatchItem(
            dimension="opportunity_type",
            expected=requested_type,
            actual=opportunity.opportunity_type,
            matched=matched,
            score=100.0 if matched else 0.0,
        ))

    if pref.preferred_industry:
        matched = pref.preferred_industry.strip().lower() == (opportunity.industry or "").strip().lower()
        matches.append(PreferenceMatchItem(
            dimension="industry",
            expected=pref.preferred_industry,
            actual=opportunity.industry or "",
            matched=matched,
            score=100.0 if matched else 0.0,
        ))

    if pref.preferred_work_type:
        if _prefers_remote(pref.preferred_work_type):
            score = 100.0 if opportunity.is_remote else 50.0
            matched = opportunity.is_remote
            actual = "remote" if opportunity.is_remote else "onsite"
        elif _prefers_onsite(pref.preferred_work_type):
            score = 100.0 if not opportunity.is_remote else 75.0
            matched = not opportunity.is_remote
            actual = "onsite" if not opportunity.is_remote else "remote"
        else:
            score = 100.0
            matched = True
            actual = "not_applicable"
        matches.append(PreferenceMatchItem(
            dimension="work_mode",
            expected=pref.preferred_work_type,
            actual=actual,
            matched=matched,
            score=score,
        ))

    preferred_locations = _load_json_list(pref.preferred_locations)
    if preferred_locations and not opportunity.is_remote:
        matched = any(_locations_match(location, opportunity.location) for location in preferred_locations)
        matches.append(PreferenceMatchItem(
            dimension="location",
            expected=", ".join(preferred_locations),
            actual=opportunity.location or "",
            matched=matched,
            score=100.0 if matched else 50.0,
        ))

    target_roles = parse_target_roles(pref.target_job_role)
    if target_roles:
        score, role_match = calculate_target_role_score(target_roles, opportunity)
        matches.append(PreferenceMatchItem(
            dimension="target_role",
            expected=", ".join(target_roles),
            actual=opportunity.target_role,
            matched=score >= 75.0,
            score=score,
        ))

    if not matches:
        return 100.0, []
    return round(sum(item.score for item in matches) / len(matches), 2), matches


def calculate_final_score(
    required_skill_score: float,
    preferred_skill_score: float,
    target_role_score: float,
    experience_score: float,
    location_remote_score: float,
    career_preference_score: float,
) -> float:
    score = (
        required_skill_score * WEIGHTS["required_skills"]
        + preferred_skill_score * WEIGHTS["preferred_skills"]
        + target_role_score * WEIGHTS["target_role"]
        + experience_score * WEIGHTS["experience"]
        + location_remote_score * WEIGHTS["location_remote"]
        + career_preference_score * WEIGHTS["career_preferences"]
    )
    return round(max(0.0, min(100.0, score)), 2)


def _is_expired(opportunity: Opportunity, now: datetime) -> bool:
    if not opportunity.expires_at:
        return False
    expires_at = opportunity.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at < now


def apply_hard_filters(profile: Profile, opportunity: Opportunity, now: Optional[datetime] = None) -> tuple[bool, Optional[str]]:
    now = now or datetime.now(timezone.utc)
    if _is_expired(opportunity, now):
        return False, "expired"

    pref = profile.career_preferences
    work_type = pref.preferred_work_type if pref else None
    requested_type = explicit_opportunity_type(work_type)
    if requested_type and opportunity.opportunity_type != requested_type:
        return False, "opportunity_type_mismatch"

    if requires_remote_only(work_type) and not opportunity.is_remote:
        return False, "remote_only_required"

    return True, None


def score_opportunity(profile: Profile, opportunity: Opportunity) -> CareerMatchResult:
    user_skill_keys = extract_user_skill_keys(profile)
    target_roles = parse_target_roles(profile.career_preferences.target_job_role if profile.career_preferences else None)
    user_experience_level = determine_user_experience_level(profile)

    required_score, required_summary = calculate_required_skill_score(opportunity, user_skill_keys)
    preferred_score, preferred_summary = calculate_preferred_skill_score(opportunity, user_skill_keys)
    target_score, target_match = calculate_target_role_score(target_roles, opportunity)
    experience_score, experience_match = calculate_experience_score(user_experience_level, opportunity.experience_level)
    location_score, location_match = calculate_location_remote_score(profile, opportunity)
    preference_score, preference_matches = calculate_career_preference_score(profile, opportunity)
    final_score = calculate_final_score(
        required_score,
        preferred_score,
        target_score,
        experience_score,
        location_score,
        preference_score,
    )

    return CareerMatchResult(
        opportunity_id=opportunity.id,
        title=opportunity.title,
        company=opportunity.company,
        final_score=final_score,
        breakdown=CareerMatchBreakdown(
            required_skill_score=required_score,
            preferred_skill_score=preferred_score,
            target_role_score=target_score,
            experience_score=experience_score,
            location_remote_score=location_score,
            career_preference_score=preference_score,
            matched_required_skills=required_summary.matched,
            missing_required_skills=required_summary.missing,
            matched_preferred_skills=preferred_summary.matched,
            missing_preferred_skills=preferred_summary.missing,
            target_role_match=target_match,
            experience_match=experience_match,
            location_match=location_match,
            preference_matches=preference_matches,
        ),
    )


def rank_opportunities(
    profile: Profile,
    opportunities: Sequence[Opportunity],
    limit: int = 10,
    now: Optional[datetime] = None,
) -> list[CareerMatchResult]:
    results: list[CareerMatchResult] = []
    for opportunity in opportunities:
        include, _reason = apply_hard_filters(profile, opportunity, now=now)
        if include:
            results.append(score_opportunity(profile, opportunity))

    return sorted(
        results,
        key=lambda result: (
            -result.final_score,
            -result.breakdown.required_skill_score,
            result.opportunity_id,
        ),
    )[:limit]


def match_opportunities(
    profile: Profile,
    candidate_opportunities: Sequence[Opportunity],
    limit: int = 10,
    now: Optional[datetime] = None,
) -> CareerMatchingResponse:
    filtered_count = sum(
        1 for opportunity in candidate_opportunities if apply_hard_filters(profile, opportunity, now=now)[0]
    )
    return CareerMatchingResponse(
        profile_id=profile.id,
        candidates_considered=len(candidate_opportunities),
        candidates_after_filters=filtered_count,
        results=rank_opportunities(profile, candidate_opportunities, limit=limit, now=now),
    )


def load_profile_for_matching(db: Session, profile_id: str) -> Optional[Profile]:
    return (
        db.query(Profile)
        .options(
            selectinload(Profile.skills),
            selectinload(Profile.experience),
            selectinload(Profile.projects).selectinload(ProfileProject.technologies),
            selectinload(Profile.career_preferences),
        )
        .filter(Profile.id == profile_id)
        .one_or_none()
    )


def load_candidate_opportunities(db: Session, opportunity_ids: Sequence[str]) -> list[Opportunity]:
    if not opportunity_ids:
        return []
    ordering = {opportunity_id: index for index, opportunity_id in enumerate(opportunity_ids)}
    opportunities = (
        db.query(Opportunity)
        .filter(Opportunity.id.in_(opportunity_ids))
        .all()
    )
    return sorted(opportunities, key=lambda opportunity: ordering.get(opportunity.id, 9999))
