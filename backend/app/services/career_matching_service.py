"""
Deterministic, explainable matching of real job listings against a user profile.

Two separate stages:

1. **Hard eligibility** (``eligibility``) — only facts that genuinely rule a
   listing out: inactive/expired, the user's explicit filters, and listings
   pitched far above the user's level (lead/staff/management for a fresher).
   Missing listing data never excludes a listing.
2. **Relevance scoring** (``score_opportunity``) — weighted components with
   neutral (not perfect) scores for unknown data, so missing fields neither
   exclude nor inflate a listing:

   ===================  ======  ===========================================
   component            weight  basis
   ===================  ======  ===========================================
   skills               0.40    user skills found among skills the listing mentions
   target role          0.30    role family of the title vs the user's targets
   experience           0.15    stated years / level vs the user's experience
   location / remote    0.10    work mode + city/country vs preferences
   preferences          0.05    interests, industry, education relevance
   ===================  ======  ===========================================

A listing is only returned as a *match* when it is relevant to the user's
target role or clearly overlaps their skills, and scores at least
``MIN_MATCH_SCORE``. No AI is involved; Gemini/Qwen only annotate results.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Iterable, Optional, Sequence

from app.data.job_taxonomy import (
    LEVEL_NAMES,
    RELATED_ROLES,
    canonical_skill_id,
    classify_role,
    level_from_title,
    level_from_years,
    normalize_target_roles,
    skill_display_name,
    title_keywords,
)
from app.db.models import Opportunity, Profile
from app.schemas.career_matching import (
    CareerMatchBreakdown,
    CareerMatchingResponse,
    CareerMatchResult,
    ExperienceMatch,
    LocationMatch,
    PreferenceMatchItem,
    TargetRoleMatch,
)

WEIGHTS = {
    "skills": 0.40,
    "target_role": 0.30,
    "experience": 0.15,
    "location_remote": 0.10,
    "career_preferences": 0.05,
}
MIN_MATCH_SCORE = 40.0
# Bump whenever scoring/eligibility logic changes so cached responses are not reused.
ALGORITHM_VERSION = "jobs-v5"
SKILL_DENOMINATOR_CAP = 6  # matching 6 of the listing's skills is full skill coverage
NEUTRAL = 50.0

PROVIDER_PRIORITY = {"greenhouse": 0, "lever": 0, "ashby": 0, "remotive": 1, "adzuna": 2}

CITY_ALIASES = {
    "bangalore": "bengaluru", "bengaluru": "bengaluru", "gurgaon": "gurugram", "gurugram": "gurugram",
    "new delhi": "delhi", "delhi": "delhi", "ncr": "delhi", "delhi ncr": "delhi", "noida": "noida",
    "bombay": "mumbai", "mumbai": "mumbai", "navi mumbai": "mumbai", "thane": "mumbai", "madras": "chennai",
    "chennai": "chennai", "pune": "pune", "hyderabad": "hyderabad", "secunderabad": "hyderabad",
    "kolkata": "kolkata", "calcutta": "kolkata", "ahmedabad": "ahmedabad", "kochi": "kochi", "cochin": "kochi",
    "jaipur": "jaipur", "indore": "indore", "chandigarh": "chandigarh", "coimbatore": "coimbatore",
}
_TECH_FIELDS = ("computer", "software", "information technology", " it", "data", "electronics", "electrical",
                "mathematics", "statistics", "artificial intelligence", "machine learning", "engineering")
_TECH_FAMILIES = {"Backend Engineer", "Full Stack Developer", "Frontend Developer", "Mobile Developer", "DevOps Engineer",
                  "Cloud Engineer", "Security Engineer", "QA Engineer", "Data Engineer", "Machine Learning Engineer",
                  "Data Scientist", "Data Analyst", "Software Engineer", "Technical Support Engineer",
                  "Security Analyst", "Network Engineer"}


# ─────────────────────────────────────────────────────────────────────────────
# Profile facts
# ─────────────────────────────────────────────────────────────────────────────

def _load_json_list(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    try:
        values = json.loads(raw)
        if isinstance(values, list):
            return [str(v).strip() for v in values if str(v).strip()]
    except Exception:
        pass
    return [part.strip() for part in raw.split(",") if part.strip()]


def _months_between(start: Optional[date], end: Optional[date]) -> int:
    if not start:
        return 0
    end = end or date.today()
    return max(0, (end.year - start.year) * 12 + (end.month - start.month))


@dataclass
class ProfileFacts:
    skill_ids: set[str]
    skill_names: dict[str, str]
    target_roles: list[str]
    target_role_text: Optional[str]
    experience_years: float
    level: int
    level_name: str
    has_internship: bool
    preferred_work_type: Optional[str]
    preferred_locations: list[str]
    profile_location: Optional[str]
    career_interests: list[str]
    preferred_industry: Optional[str]
    tech_education: bool

    @property
    def is_complete(self) -> bool:
        return bool(self.target_roles or self.skill_ids)


def _split_skill_entry(value: str) -> list[str]:
    """Users sometimes type several skills in one entry ("Python, Postgres; Node")."""
    return [part.strip() for part in re.split(r"[,;|\n]+", value or "") if part.strip()]


def profile_facts(profile: Profile) -> ProfileFacts:
    skill_ids: set[str] = set()
    names: dict[str, str] = {}
    raw_skills = [skill.name for skill in profile.skills]
    raw_skills += [tech.name for project in profile.projects for tech in project.technologies]
    for raw in raw_skills:
        for name in _split_skill_entry(raw):
            sid = canonical_skill_id(name)
            if sid:
                skill_ids.add(sid)
                names.setdefault(sid, name)

    total = intern = 0
    for exp in profile.experience:
        months = _months_between(exp.start_date, None if exp.currently_working else exp.end_date)
        total += months
        if re.search(r"intern", f"{exp.job_title or ''} {exp.employment_type or ''}", re.IGNORECASE):
            intern += months
    years = max(0, total - intern) / 12.0
    if years == 0:
        level = 1  # fresher / entry level (internships alone do not raise the level)
    elif years < 1:
        level = 1
    elif years < 2.5:
        level = 2
    elif years < 5:
        level = 3
    elif years < 8:
        level = 4
    else:
        level = 5

    pref = profile.career_preferences
    target_text = pref.target_job_role if pref and pref.target_job_role else None
    education = getattr(profile, "education", None) or []
    tech_education = any(
        any(token in f" {(edu.field_of_study or '')} {(edu.degree or '')}".lower() for token in _TECH_FIELDS)
        for edu in education
    )
    return ProfileFacts(
        skill_ids=skill_ids,
        skill_names=names,
        target_roles=normalize_target_roles(target_text),
        target_role_text=target_text,
        experience_years=round(years, 1),
        level=level,
        level_name=LEVEL_NAMES[level],
        has_internship=intern > 0,
        preferred_work_type=pref.preferred_work_type if pref else None,
        preferred_locations=_load_json_list(pref.preferred_locations if pref else None),
        profile_location=profile.location,
        career_interests=_load_json_list(pref.career_interests if pref else None),
        preferred_industry=pref.preferred_industry if pref else None,
        tech_education=tech_education,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Component scores
# ─────────────────────────────────────────────────────────────────────────────

def listing_skill_ids(opportunity: Opportunity) -> list[str]:
    ids = []
    for skill in list(opportunity.required_skills) + list(opportunity.preferred_skills):
        sid = canonical_skill_id(skill.normalized_name or skill.name)
        if sid and sid not in ids:
            ids.append(sid)
    return ids


def skill_score(facts: ProfileFacts, opportunity: Opportunity) -> tuple[float, list[str], list[str]]:
    listed = listing_skill_ids(opportunity)
    if not listed:
        return NEUTRAL, [], []
    matched = [sid for sid in listed if sid in facts.skill_ids]
    missing = [sid for sid in listed if sid not in facts.skill_ids]
    denominator = min(len(listed), SKILL_DENOMINATOR_CAP)
    score = min(1.0, len(matched) / denominator) * 100
    return round(score, 2), [skill_display_name(s) for s in matched], [skill_display_name(s) for s in missing]


def role_score(facts: ProfileFacts, opportunity: Opportunity) -> tuple[float, TargetRoleMatch]:
    families = classify_role(opportunity.title)  # always from the title, never a stale stored value
    if not facts.target_roles:
        return NEUTRAL, TargetRoleMatch(user_target_roles=[], opportunity_target_role=opportunity.target_role,
                                         relationship="no_target_role", score=NEUTRAL)
    best, relationship, best_role = 0.0, "unrelated", facts.target_roles[0]
    for target in facts.target_roles:
        if target in families:
            score, rel = 100.0, "exact"
        elif any(family in RELATED_ROLES.get(target, set()) for family in families):
            score, rel = 70.0, "related"
        elif title_keywords(target) & title_keywords(opportunity.title):
            score, rel = 55.0, "keyword_overlap"
        else:
            score, rel = 0.0, "unrelated"
        if score > best:
            best, relationship, best_role = score, rel, target
    return best, TargetRoleMatch(user_target_roles=facts.target_roles, opportunity_target_role=opportunity.target_role,
                                 relationship=f"{relationship}:{best_role}", score=best)


def listing_level(opportunity: Opportunity) -> Optional[int]:
    level = level_from_title(opportunity.title)
    if level is None:
        level = level_from_years(opportunity.experience_min_years)
    return level


def experience_score(facts: ProfileFacts, opportunity: Opportunity) -> tuple[float, ExperienceMatch]:
    min_years = opportunity.experience_min_years
    level = listing_level(opportunity)
    if min_years is not None:
        gap = min_years - facts.experience_years
        if gap <= 0:
            score, rel = (100.0, "meets_stated_years") if gap > -6 else (70.0, "overqualified")
        elif gap <= 1:
            score, rel = 75.0, "slightly_below_stated_years"
        elif gap <= 2:
            score, rel = 50.0, "below_stated_years"
        else:
            score, rel = 15.0, "well_below_stated_years"
    elif level is not None:
        if level == 0:  # internship
            score, rel = (100.0, "internship") if facts.level <= 1 else (40.0, "internship_overqualified")
        else:
            diff = level - facts.level
            score, rel = {0: (100.0, "level_match"), 1: (70.0, "one_level_above"), -1: (85.0, "one_level_below")}.get(
                diff, (30.0, "far_above") if diff >= 2 else (60.0, "well_below_your_level"))
            if diff >= 3:
                score = 10.0
    else:
        score, rel = 70.0, "not_stated"
    return score, ExperienceMatch(user_level=facts.level_name, opportunity_level=opportunity.experience_level,
                                  relationship=rel, score=score)


def city_tokens(value: Optional[str]) -> set[str]:
    text = (value or "").lower()
    found = {canonical for alias, canonical in CITY_ALIASES.items() if re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", text)}
    if not found and text.strip():
        first = re.split(r"[,(/-]", text)[0].strip()
        if first and first not in ("remote", "india", "hybrid"):
            found.add(first)
    return found


def _prefers(work_type: Optional[str], mode: str) -> bool:
    return bool(work_type) and mode in work_type.lower().replace("-", "").replace(" ", "")


def location_score(facts: ProfileFacts, opportunity: Opportunity) -> tuple[float, LocationMatch]:
    mode = opportunity.work_mode or ("remote" if opportunity.is_remote else None)
    work_type = facts.preferred_work_type
    wanted_cities = set().union(*[city_tokens(loc) for loc in facts.preferred_locations]) if facts.preferred_locations else set()
    home_cities = city_tokens(facts.profile_location)
    job_cities = city_tokens(opportunity.location)

    if mode == "remote":
        score, rel = (70.0, "remote_but_prefers_onsite") if _prefers(work_type, "onsite") else (100.0, "remote")
        job_country = opportunity.country
        if job_country and job_country != "India" and opportunity.location and "india" not in (opportunity.location or "").lower():
            score, rel = min(score, 60.0), "remote_restricted_elsewhere"
    else:
        if job_cities and job_cities & wanted_cities:
            score, rel = 100.0, "preferred_location"
        elif job_cities and job_cities & home_cities:
            score, rel = 95.0, "profile_location"
        elif not opportunity.location:
            score, rel = NEUTRAL, "location_not_stated"
        elif opportunity.country == "India":
            score, rel = (55.0, "other_city_in_india") if (wanted_cities or home_cities) else (75.0, "india_no_city_preference")
        elif opportunity.country:
            score, rel = 15.0, "other_country"
        else:
            score, rel = 40.0, "location_unclear"
        if _prefers(work_type, "remote") and mode in ("onsite", "hybrid", None):
            score, rel = score * 0.7, f"{rel}+prefers_remote"
        elif _prefers(work_type, "hybrid") and mode == "onsite":
            score, rel = score * 0.9, f"{rel}+prefers_hybrid"
    return round(score, 2), LocationMatch(
        profile_location=facts.profile_location, preferred_locations=facts.preferred_locations, preferred_work_type=work_type,
        opportunity_location=opportunity.location, opportunity_is_remote=mode == "remote", relationship=rel, score=round(score, 2))


def preference_score(facts: ProfileFacts, opportunity: Opportunity) -> tuple[float, list[PreferenceMatchItem]]:
    items: list[PreferenceMatchItem] = []
    blob = f"{opportunity.title}\n{opportunity.description or ''}".lower()
    if facts.career_interests:
        hits = [i for i in facts.career_interests if re.search(rf"(?<![a-z]){re.escape(i.lower())}(?![a-z])", blob)]
        items.append(PreferenceMatchItem(dimension="career_interests", expected=", ".join(facts.career_interests),
                                         actual=", ".join(hits) or "none mentioned", matched=bool(hits), score=100.0 if hits else 30.0))
    if facts.preferred_industry:
        # "Information Technology / Cybersecurity" → any listed part may match.
        parts = [p.strip().lower() for p in re.split(r"[/,;|]+", facts.preferred_industry) if p.strip()]
        hit = any(re.search(rf"(?<![a-z]){re.escape(part)}(?![a-z])", blob) for part in parts)
        items.append(PreferenceMatchItem(dimension="industry", expected=facts.preferred_industry,
                                         actual="mentioned" if hit else "not mentioned", matched=hit, score=100.0 if hit else 40.0))
    families = set(classify_role(opportunity.title))
    if facts.tech_education and families & _TECH_FAMILIES:
        items.append(PreferenceMatchItem(dimension="education", expected="technical degree", actual="technical role",
                                         matched=True, score=100.0))
    if not items:
        return NEUTRAL, []
    return round(sum(i.score for i in items) / len(items), 2), items


# ─────────────────────────────────────────────────────────────────────────────
# Eligibility, scoring, explanation
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class MatchFilters:
    location: Optional[str] = None
    work_mode: Optional[str] = None  # remote | hybrid | onsite
    employment_type: Optional[str] = None
    experience: Optional[str] = None  # internship | entry | mid | senior
    source: Optional[str] = None


_EXPERIENCE_FILTER_LEVELS = {"internship": {0}, "entry": {1, 2}, "mid": {3}, "senior": {4, 5, 6}}


def eligibility(facts: ProfileFacts, opportunity: Opportunity, filters: MatchFilters, now: datetime) -> Optional[str]:
    """Return an exclusion reason, or None when the listing is eligible."""
    if not opportunity.is_active:
        return "inactive"
    expires = opportunity.expires_at
    if expires is not None and (expires if expires.tzinfo else expires.replace(tzinfo=timezone.utc)) < now:
        return "expired"
    mode = opportunity.work_mode or ("remote" if opportunity.is_remote else None)
    if filters.work_mode and mode != filters.work_mode:
        return "filter_work_mode"
    if filters.employment_type and opportunity.employment_type != filters.employment_type:
        return "filter_employment_type"
    if filters.location:
        wanted = filters.location.strip().lower()
        loc = (opportunity.location or "").lower()
        if wanted not in loc and not (city_tokens(wanted) & city_tokens(loc)) and not (wanted == "india" and opportunity.country == "India"):
            return "filter_location"
    if filters.source and opportunity.source != filters.source:
        return "filter_source"
    level = listing_level(opportunity)
    if filters.experience:
        allowed = _EXPERIENCE_FILTER_LEVELS.get(filters.experience, set())
        if level is not None and level not in allowed:
            return "filter_experience"
        if level is None and filters.experience == "internship" and opportunity.employment_type != "internship":
            return "filter_experience"
    # Genuine ineligibility, only from facts the listing states: a level three or
    # more steps above the user's (e.g. Senior/Lead for an entry-level profile),
    # or an explicit minimum experience at least 4 years beyond the user's.
    if level is not None and level - facts.level >= 3:
        return "far_above_experience"
    if opportunity.experience_min_years is not None and opportunity.experience_min_years - facts.experience_years >= 4:
        return "far_above_experience"
    return None


def _reasons(facts: ProfileFacts, opportunity: Opportunity, matched: list[str], missing: list[str],
             role: TargetRoleMatch, exp: ExperienceMatch, loc: LocationMatch) -> list[str]:
    reasons: list[str] = []
    rel, _, target = role.relationship.partition(":")
    if rel == "exact":
        reasons.append(f"Title matches your target role ({target}).")
    elif rel == "related":
        reasons.append(f"Closely related to your target role ({target}).")
    elif rel == "keyword_overlap":
        reasons.append(f"Title shares keywords with your target role ({target}).")
    if matched:
        total = len(matched) + len(missing)
        reasons.append(f"You have {len(matched)} of the {total} skills this listing mentions: {', '.join(matched[:5])}.")
    elif not missing:
        reasons.append("The listing does not name specific skills.")
    if opportunity.experience_min_years is not None:
        span = f"{opportunity.experience_min_years}–{opportunity.experience_max_years}" if opportunity.experience_max_years else f"{opportunity.experience_min_years}+"
        reasons.append(f"Asks for {span} years of experience; your profile shows about {facts.experience_years:g}.")
    elif exp.relationship == "not_stated":
        reasons.append("Experience requirement is not stated.")
    elif exp.relationship in ("level_match", "internship"):
        reasons.append(f"Pitched at your level ({opportunity.experience_level or facts.level_name}).")
    if loc.relationship.startswith("remote") and loc.relationship != "remote_restricted_elsewhere":
        reasons.append("Remote role.")
    elif loc.relationship.startswith("preferred_location"):
        reasons.append(f"Located in one of your preferred locations ({opportunity.location}).")
    elif loc.relationship.startswith("profile_location"):
        reasons.append(f"Located near you ({opportunity.location}).")
    return reasons


def calculate_final_score(components: dict[str, float]) -> float:
    score = sum(components[key] * weight for key, weight in WEIGHTS.items())
    return round(max(0.0, min(100.0, score)), 2)


@dataclass
class ScoredListing:
    opportunity: Opportunity
    result: CareerMatchResult
    matched_skills: list[str]
    missing_skills: list[str]
    reasons: list[str]
    relevant: bool


def score_opportunity(facts: ProfileFacts, opportunity: Opportunity) -> ScoredListing:
    s_score, matched, missing = skill_score(facts, opportunity)
    r_score, role_match = role_score(facts, opportunity)
    e_score, exp_match = experience_score(facts, opportunity)
    l_score, loc_match = location_score(facts, opportunity)
    p_score, prefs = preference_score(facts, opportunity)
    final = calculate_final_score({"skills": s_score, "target_role": r_score, "experience": e_score,
                                   "location_remote": l_score, "career_preferences": p_score})
    reasons = _reasons(facts, opportunity, matched, missing, role_match, exp_match, loc_match)
    # Relevance: related to a target role, or (no usable role signal) clear skill overlap.
    role_relevant = r_score >= 55.0
    skill_relevant = len(matched) >= 2 and s_score >= 40.0
    relevant = final >= MIN_MATCH_SCORE and (role_relevant or (skill_relevant and r_score > 0) or (not facts.target_roles and skill_relevant))
    breakdown = CareerMatchBreakdown(
        required_skill_score=s_score, preferred_skill_score=0.0, target_role_score=r_score, experience_score=e_score,
        location_remote_score=l_score, career_preference_score=p_score,
        matched_required_skills=matched, missing_required_skills=missing,
        matched_preferred_skills=[], missing_preferred_skills=[],
        target_role_match=role_match, experience_match=exp_match, location_match=loc_match, preference_matches=prefs,
        match_reasons=reasons,
    )
    result = CareerMatchResult(opportunity_id=opportunity.id, title=opportunity.title, company=opportunity.company,
                               final_score=final, breakdown=breakdown)
    return ScoredListing(opportunity, result, matched, missing, reasons, relevant)


def dedupe_listings(opportunities: Iterable[Opportunity]) -> list[Opportunity]:
    """Collapse the same job published through several providers (company board wins)."""
    best: dict[tuple, Opportunity] = {}
    for opp in opportunities:
        key = (re.sub(r"[^a-z0-9]", "", (opp.company or "").lower()),
               re.sub(r"[^a-z0-9]", "", (opp.title or "").lower()),
               re.sub(r"[^a-z0-9]", "", (opp.location or "").lower()))
        current = best.get(key)
        if current is None or PROVIDER_PRIORITY.get(opp.source, 9) < PROVIDER_PRIORITY.get(current.source, 9):
            best[key] = opp
    return list(best.values())


@dataclass
class MatchRun:
    matches: list[ScoredListing]
    considered: int
    excluded: dict[str, int] = field(default_factory=dict)


def rank_listings(facts: ProfileFacts, opportunities: Sequence[Opportunity], filters: Optional[MatchFilters] = None,
                  now: Optional[datetime] = None) -> MatchRun:
    filters = filters or MatchFilters()
    now = now or datetime.now(timezone.utc)
    excluded: dict[str, int] = {}
    eligible: list[Opportunity] = []
    for opp in opportunities:
        reason = eligibility(facts, opp, filters, now)
        if reason:
            excluded[reason] = excluded.get(reason, 0) + 1
        else:
            eligible.append(opp)
    # De-duplicate only among eligible listings, so an inactive copy can never
    # shadow an active one.
    unique = dedupe_listings(eligible)
    if len(unique) < len(eligible):
        excluded["duplicate"] = len(eligible) - len(unique)
    matches: list[ScoredListing] = []
    for opp in unique:
        scored = score_opportunity(facts, opp)
        if not scored.relevant:
            excluded["low_relevance"] = excluded.get("low_relevance", 0) + 1
            continue
        matches.append(scored)
    matches.sort(key=lambda s: (-s.result.final_score, -s.result.breakdown.target_role_score,
                                -(s.opportunity.published_at.timestamp() if s.opportunity.published_at else 0), s.opportunity.id))
    return MatchRun(matches=matches, considered=len(opportunities) - excluded.get("duplicate", 0), excluded=excluded)


def to_matching_response(profile_id: str, run: MatchRun, limit: int = 10) -> CareerMatchingResponse:
    """Shape consumed by the Gemini reranker (top-N deterministic results)."""
    return CareerMatchingResponse(profile_id=profile_id, candidates_considered=run.considered,
                                  candidates_after_filters=len(run.matches),
                                  results=[m.result for m in run.matches[:limit]])
