"""
Skill Analysis Service — Phase 2A.

Responsibilities
----------------
1. Read the user's target_job_role from CareerPreference (PostgreSQL).
2. Resolve that free-text string to one or more Phase 1 RoleEntry objects:
       a. Exact case-insensitive name match  → no Qdrant call needed
       b. Qdrant semantic search filtered to source_type="role"
3. Merge skills from all resolved roles (dedup, required beats recommended).
4. Compare merged skills against the user's profile skills and project
   technologies.
5. Return a fully populated SkillAnalysisResult.

Design principles
-----------------
* No Qwen / LLM involvement — resolution is deterministic via Qdrant cosine.
* Never modifies the profile schema.
* Reads target_job_role directly from the existing CareerPreference model.
* All Phase 1 role/skill data comes from career_knowledge.py (in-memory).
* Qdrant is used only for semantic role resolution — not for skill comparison.
* Alias matching uses career_knowledge.py aliases — no extra Qdrant call.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from qdrant_client.http import models as qmodels

from app.core.config import settings
from app.data.career_knowledge import ROLES, SKILLS, RoleEntry, SkillEntry
from app.db.models import Profile
from app.schemas.skill_analysis import SkillAnalysisResponse, SkillCoverage, SkillMatch
from app.services.qdrant_service import similarity_search
from app.services.embedding_service import embed_text

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tunable thresholds (constants — easy to adjust without touching logic)
# ---------------------------------------------------------------------------

#: Minimum cosine similarity for a role to be considered a semantic match.
ROLE_SCORE_THRESHOLD: float = 0.45

#: Maximum number of roles to resolve for any single target.
ROLE_MAX_RESULTS: int = 3

#: A secondary role is only included if its score is within this delta of
#: the top-scoring role.  Prevents unrelated roles from being added.
ROLE_SCORE_SPREAD: float = 0.12

# ---------------------------------------------------------------------------
# Pre-built lookup structures (constructed once at module load)
# ---------------------------------------------------------------------------

# Map lowercase role name → RoleEntry for O(1) exact-match lookup.
_ROLE_BY_NAME_LOWER: Dict[str, RoleEntry] = {
    r.name.lower(): r for r in ROLES
}

# Map role ID → RoleEntry for O(1) Qdrant source_id lookup.
_ROLE_BY_ID: Dict[str, RoleEntry] = {r.id: r for r in ROLES}

# Flat alias map: lowercase alias/name → SkillEntry for user skill matching.
# Built once; covers both canonical names and declared aliases.
_SKILL_ALIAS_MAP: Dict[str, SkillEntry] = {}
for _skill in SKILLS.values():
    _SKILL_ALIAS_MAP[_skill.name.lower()] = _skill
    for _alias in _skill.aliases:
        _SKILL_ALIAS_MAP[_alias.lower()] = _skill


# ---------------------------------------------------------------------------
# Internal data structures
# ---------------------------------------------------------------------------


@dataclass
class RoleResolution:
    """Result of resolving a free-text target role to Phase 1 roles."""

    roles: List[RoleEntry] = field(default_factory=list)
    scores: Dict[str, float] = field(default_factory=dict)  # role.name → score
    method: Optional[str] = None  # "exact" | "semantic" | None
    matched: bool = False


@dataclass
class MergedSkills:
    """Skill sets merged from multiple resolved roles."""

    required: List[SkillEntry] = field(default_factory=list)
    recommended: List[SkillEntry] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Step 1 — User skill extraction
# ---------------------------------------------------------------------------


def extract_user_skill_names(profile: Profile) -> Set[str]:
    """
    Return a normalised set of all skill strings the user already has.

    Sources:
    - profile_skills (ProfileSkill.name)
    - project_technologies (ProjectTechnology.name for each project)

    Normalisation: lowercase + collapsed whitespace, matching the same
    treatment applied to Phase 1 skill names and aliases.
    """
    names: Set[str] = set()
    for ps in profile.skills:
        names.add((ps.name or "").strip().lower())
    for project in profile.projects:
        for tech in project.technologies:
            names.add((tech.name or "").strip().lower())
    names.discard("")
    return names


def _user_has_skill(skill: SkillEntry, user_skills_lower: Set[str]) -> bool:
    """
    Check whether the user already has a given Phase 1 skill.

    Matching strategy (in order, short-circuit on first hit):
    1. Canonical skill name (lowercase)
    2. Each declared alias (lowercase)
    """
    if skill.name.lower() in user_skills_lower:
        return True
    for alias in skill.aliases:
        if alias.lower() in user_skills_lower:
            return True
    return False


# ---------------------------------------------------------------------------
# Step 2 — Target role resolution
# ---------------------------------------------------------------------------


def resolve_target_role(
    target_role_str: str,
    collection: str,
) -> RoleResolution:
    """
    Resolve a free-text target role string to one or more Phase 1 RoleEntry
    objects.

    Algorithm
    ---------
    1. Exact case-insensitive name match against all 30 Phase 1 roles.
       If found, return immediately (score 1.0, method="exact").
    2. Embed the target string and run a Qdrant similarity search filtered
       to source_type="role" only.
    3. Apply threshold and spread-window filters.
    4. Map source_id values back to RoleEntry objects.

    Parameters
    ----------
    target_role_str:
        Raw value from career_preferences.target_job_role.
    collection:
        Qdrant collection name (defaults to settings.QDRANT_COLLECTION_CONTENT).

    Returns
    -------
    RoleResolution
        .matched=True  if at least one role was found.
        .matched=False if no role cleared the threshold.
    """
    target_clean = target_role_str.strip()
    if not target_clean:
        return RoleResolution(matched=False)

    # ── Stage 1: exact name match ─────────────────────────────────────────
    exact = _ROLE_BY_NAME_LOWER.get(target_clean.lower())
    if exact:
        logger.debug("[SkillAnalysis] Exact match: '%s' → %s", target_clean, exact.name)
        return RoleResolution(
            roles=[exact],
            scores={exact.name: 1.0},
            method="exact",
            matched=True,
        )

    # ── Stage 2: semantic search ──────────────────────────────────────────
    logger.debug(
        "[SkillAnalysis] No exact match for '%s'. Trying semantic search.", target_clean
    )
    query_vector = embed_text(target_clean)

    role_filter = qmodels.Filter(
        must=[
            qmodels.FieldCondition(
                key="source_type",
                match=qmodels.MatchValue(value="role"),
            )
        ]
    )

    hits = similarity_search(
        collection_name=collection,
        query_vector=query_vector,
        limit=ROLE_MAX_RESULTS + 2,  # fetch a few extras before spread filtering
        score_threshold=ROLE_SCORE_THRESHOLD,
        query_filter=role_filter,
        vector_size=len(query_vector),
    )

    if not hits:
        logger.debug(
            "[SkillAnalysis] No roles above threshold %.2f for '%s'.",
            ROLE_SCORE_THRESHOLD,
            target_clean,
        )
        return RoleResolution(matched=False, method="semantic")

    # Apply spread-window: only include roles within ROLE_SCORE_SPREAD of top
    top_score = hits[0].score
    spread_hits = [h for h in hits if (top_score - h.score) <= ROLE_SCORE_SPREAD]
    spread_hits = spread_hits[:ROLE_MAX_RESULTS]

    resolved_roles: List[RoleEntry] = []
    scores: Dict[str, float] = {}
    for hit in spread_hits:
        source_id = (hit.payload or {}).get("source_id", "")
        role = _ROLE_BY_ID.get(source_id)
        if role:
            resolved_roles.append(role)
            scores[role.name] = round(hit.score, 4)
            logger.debug(
                "[SkillAnalysis] Resolved role: %s (score=%.4f)", role.name, hit.score
            )

    if not resolved_roles:
        return RoleResolution(matched=False, method="semantic")

    return RoleResolution(
        roles=resolved_roles,
        scores=scores,
        method="semantic",
        matched=True,
    )


# ---------------------------------------------------------------------------
# Step 3 — Skill merging
# ---------------------------------------------------------------------------


def merge_role_skills(roles: List[RoleEntry]) -> MergedSkills:
    """
    Merge required and recommended skills from multiple roles.

    Rules
    -----
    - Collect required skill IDs across all roles → union.
    - Collect recommended skill IDs across all roles → union.
    - If a skill ID appears in both sets, it stays in required (required wins).
    - Unknown skill IDs (not in SKILLS catalog) are silently skipped.
    - Final lists are sorted by display name.

    Returns
    -------
    MergedSkills with two sorted lists of SkillEntry objects.
    """
    required_ids: Set[str] = set()
    recommended_ids: Set[str] = set()

    for role in roles:
        required_ids.update(role.required_skills)
        recommended_ids.update(role.recommended_skills)

    # Required wins over recommended
    recommended_only_ids = recommended_ids - required_ids

    required: List[SkillEntry] = sorted(
        [SKILLS[sid] for sid in required_ids if sid in SKILLS],
        key=lambda s: s.name.lower(),
    )
    recommended: List[SkillEntry] = sorted(
        [SKILLS[sid] for sid in recommended_only_ids if sid in SKILLS],
        key=lambda s: s.name.lower(),
    )
    return MergedSkills(required=required, recommended=recommended)


# ---------------------------------------------------------------------------
# Step 4 — Coverage calculation
# ---------------------------------------------------------------------------


def _coverage_pct(have: int, total: int) -> int:
    if total == 0:
        return 0
    return round((have / total) * 100)


# ---------------------------------------------------------------------------
# Step 5 — Main entry point
# ---------------------------------------------------------------------------


def build_skill_analysis(
    profile: Profile,
    collection: Optional[str] = None,
) -> SkillAnalysisResponse:
    """
    Build the full skill analysis for an authenticated user.

    Reads career_preferences.target_job_role from the already-loaded profile.
    Does NOT make any additional database queries.

    Parameters
    ----------
    profile:
        Fully loaded Profile ORM object (including skills, projects,
        career_preferences).
    collection:
        Qdrant collection override; defaults to settings.QDRANT_COLLECTION_CONTENT.

    Returns
    -------
    SkillAnalysisResponse
        status="ok"             — analysis complete
        status="no_target_role" — user has no target role set
        status="no_match"       — target could not be mapped to Phase 1 roles
    """
    col = collection or settings.QDRANT_COLLECTION_CONTENT

    # ── Guard: no target role ─────────────────────────────────────────────
    prefs = profile.career_preferences
    raw_target = (prefs.target_job_role or "").strip() if prefs else ""

    if not raw_target:
        return SkillAnalysisResponse(
            status="no_target_role",
            target_role=None,
            message=(
                "No Target Role has been set in your Career Preferences. "
                "Add a target role (e.g. 'Backend Engineer') to see your skill analysis."
            ),
        )

    # ── Resolve target role ───────────────────────────────────────────────
    resolution = resolve_target_role(raw_target, col)

    if not resolution.matched:
        return SkillAnalysisResponse(
            status="no_match",
            target_role=raw_target,
            resolution_method=resolution.method,
            message=(
                f"Your target role '{raw_target}' could not be matched to any role "
                "in the current career knowledge base. "
                "Try a more specific role name such as 'Backend Engineer' or 'Data Scientist'."
            ),
        )

    # ── Merge skills ──────────────────────────────────────────────────────
    merged = merge_role_skills(resolution.roles)

    # ── Extract user skills ───────────────────────────────────────────────
    user_skills_lower = extract_user_skill_names(profile)

    # ── Build SkillMatch lists ────────────────────────────────────────────
    required_matches: List[SkillMatch] = [
        SkillMatch(name=s.name, category=s.category, have=_user_has_skill(s, user_skills_lower))
        for s in merged.required
    ]
    recommended_matches: List[SkillMatch] = [
        SkillMatch(name=s.name, category=s.category, have=_user_has_skill(s, user_skills_lower))
        for s in merged.recommended
    ]

    # ── Derived skill lists ───────────────────────────────────────────────
    skills_have = sorted(
        {m.name for m in required_matches + recommended_matches if m.have}
    )
    skills_missing_required = [m.name for m in required_matches if not m.have]
    skills_missing_recommended = [m.name for m in recommended_matches if not m.have]

    # ── Coverage ─────────────────────────────────────────────────────────
    req_have = sum(1 for m in required_matches if m.have)
    rec_have = sum(1 for m in recommended_matches if m.have)
    total_have = req_have + rec_have
    total_skills = len(required_matches) + len(recommended_matches)

    coverage = SkillCoverage(
        required_pct=_coverage_pct(req_have, len(required_matches)),
        recommended_pct=_coverage_pct(rec_have, len(recommended_matches)),
        overall_pct=_coverage_pct(total_have, total_skills),
    )

    logger.info(
        "[SkillAnalysis] user=%s target='%s' resolved=%s method=%s "
        "required=%d recommended=%d coverage=%d%%",
        profile.user_id,
        raw_target,
        [r.name for r in resolution.roles],
        resolution.method,
        len(required_matches),
        len(recommended_matches),
        coverage.overall_pct,
    )

    return SkillAnalysisResponse(
        status="ok",
        target_role=raw_target,
        resolved_roles=[r.name for r in resolution.roles],
        resolution_scores=resolution.scores,
        resolution_method=resolution.method,
        required_skills=required_matches,
        recommended_skills=recommended_matches,
        skills_have=skills_have,
        skills_missing_required=skills_missing_required,
        skills_missing_recommended=skills_missing_recommended,
        coverage=coverage,
    )
