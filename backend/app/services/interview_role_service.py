"""
Role resolution and role-relevance rules for the AI Interviewer.

Everything here is deterministic (no LLM, no database) so the rules that keep an
interview on the selected role can be unit tested:

* resolve_catalog_role  — exact title/alias match only. There is deliberately no
  fuzzy or semantic matching: an unrecognised title becomes a custom role and is
  analysed on its own terms, never silently mapped to Backend/Software Engineer.
* relevant_profile_skills — keeps only profile skills that belong to the role's
  competencies, so profile data can personalise but never redirect an interview.
* off_role_terms — finds technologies in a generated question that belong to a
  different role, so drifting questions are rejected and regenerated.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Iterable, Optional

from app.data.interview_roles import (
    CODING_LANGUAGES,
    PRACTICAL_KINDS,
    ROLES,
    TECH_TERMS,
    InterviewRole,
)

# Words that describe seniority or level rather than the role itself.
_SENIORITY_WORDS = {
    "senior", "sr", "junior", "jr", "lead", "principal", "staff", "associate", "intern",
    "trainee", "graduate", "fresher", "entry", "level", "mid", "chief", "head", "experienced",
}
_LEVEL_SUFFIX = {"i", "ii", "iii", "iv", "1", "2", "3", "4"}


def title_key(title: str) -> str:
    """Matching key: lowercase, punctuation → spaces (keeping + # /), collapsed."""
    lowered = (title or "").lower()
    lowered = re.sub(r"\(.*?\)", " ", lowered)
    return " ".join(re.sub(r"[^a-z0-9+#/]+", " ", lowered).split())


def clean_title(title: str) -> str:
    """The user's title exactly as entered, only whitespace-normalised. This is what the interview shows and uses."""
    return " ".join((title or "").split())


def _build_index() -> dict[str, InterviewRole]:
    index: dict[str, InterviewRole] = {}
    for role in ROLES:
        for name in (role.title, *role.aliases):
            key = title_key(name)
            existing = index.get(key)
            if existing is not None and existing.slug != role.slug:
                raise ValueError(f"Interview role alias '{name}' is shared by {existing.slug} and {role.slug}")
            index[key] = role
    return index


_ROLE_INDEX = _build_index()


def _candidate_keys(title: str) -> list[str]:
    key = title_key(title)
    words = key.split()
    stripped = [w for w in words if w not in _SENIORITY_WORDS]
    candidates = [key, " ".join(stripped)]
    if stripped and stripped[-1] in _LEVEL_SUFFIX:
        candidates.append(" ".join(stripped[:-1]))
    return [c for c in dict.fromkeys(candidates) if c]


def resolve_catalog_role(title: str) -> Optional[InterviewRole]:
    for key in _candidate_keys(title):
        role = _ROLE_INDEX.get(key)
        if role is not None:
            return role
    return None


# ---------------------------------------------------------------------------
# Runtime role representation (catalog or custom), snapshotted into blueprints
# ---------------------------------------------------------------------------


@dataclass
class ResolvedRole:
    title: str  # exactly what the user selected or typed
    slug: Optional[str]
    canonical_title: str
    source: str  # "catalog" | "custom"
    family: str
    summary: str
    competencies: list[dict] = field(default_factory=list)
    practical_kinds: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)

    @property
    def focus_areas(self) -> list[str]:
        return list(dict.fromkeys(c["focus"] for c in self.competencies))

    @property
    def allowed_terms(self) -> set[str]:
        return {kw.lower() for c in self.competencies for kw in c.get("keywords", [])}

    def to_dict(self) -> dict:
        return asdict(self)


def from_catalog(role: InterviewRole, user_title: str) -> ResolvedRole:
    return ResolvedRole(
        title=clean_title(user_title) or role.title,
        slug=role.slug,
        canonical_title=role.title,
        source="catalog",
        family=role.family,
        summary=role.summary,
        competencies=[
            {
                "id": c.id,
                "name": c.name,
                "focus": c.focus,
                "weight": c.weight,
                "practical": c.practical,
                "keywords": list(c.keywords),
                "description": c.description,
            }
            for c in role.competencies
        ],
        practical_kinds=list(role.practical_kinds),
        languages=list(role.languages),
    )


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:60] or "competency"


def from_analysis(user_title: str, analysis: dict) -> ResolvedRole:
    """
    Build a custom role from a validated LLM role analysis.

    Practical kinds are restricted to what can be assessed for an arbitrary role
    (coding, sql, scenario). Deterministic "calculation" tasks only exist for
    catalog roles. If the analysis marks no competency as practical, the
    highest-weighted competency gets a scenario task, because technical
    interviews must always reserve practical slots.
    """
    competencies = []
    for item in analysis["competencies"]:
        practical = item.get("practical")
        if practical not in ("coding", "sql", "scenario"):
            practical = None
        competencies.append(
            {
                "id": _slugify(item["name"]),
                "name": item["name"],
                "focus": item.get("focus") or item["name"],
                "weight": float(item.get("weight", 1)),
                "practical": practical,
                "keywords": [k.lower() for k in item.get("keywords", [])],
                "description": item.get("description", ""),
            }
        )
    if not any(c["practical"] for c in competencies):
        top = max(competencies, key=lambda c: c["weight"])
        top["practical"] = "scenario"

    languages = [lang for lang in analysis.get("coding_languages", []) if lang in CODING_LANGUAGES]
    kinds_present = [k for k in PRACTICAL_KINDS if any(c["practical"] == k for c in competencies)]
    if "coding" in kinds_present and not languages:
        languages = list(CODING_LANGUAGES)
    title = clean_title(user_title)
    return ResolvedRole(
        title=title,
        slug=None,
        canonical_title=title,
        source="custom",
        family=analysis.get("family") or "Custom role",
        summary=analysis.get("summary", ""),
        competencies=competencies,
        practical_kinds=kinds_present,
        languages=languages,
    )


# ---------------------------------------------------------------------------
# Relevance rules
# ---------------------------------------------------------------------------


def _contains_term(text: str, term: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text) is not None


def relevant_profile_skills(skills: Iterable[str], role: ResolvedRole, focus_areas: Iterable[str] = ()) -> list[str]:
    """
    Keep a profile skill only if it matches a technology of the selected role
    (or a focus area the user chose explicitly). Everything else is dropped
    before it can reach a prompt.
    """
    allowed = role.allowed_terms
    focus = {f.strip().lower() for f in focus_areas if f and f.strip()}
    kept: list[str] = []
    for skill in skills:
        name = (skill or "").strip()
        lowered = name.lower()
        if not lowered:
            continue
        matches = lowered in focus or any(
            _contains_term(lowered, term) or (len(lowered) >= 2 and _contains_term(term, lowered)) for term in allowed
        )
        if matches and name not in kept:
            kept.append(name)
    return kept


def off_role_terms(text: str, role: ResolvedRole, extra_allowed: Iterable[str] = ()) -> list[str]:
    """Technologies mentioned in `text` that belong to other roles and were not requested by the user."""
    lowered = (text or "").lower()
    allowed = role.allowed_terms
    # Mask the role's own terms first (longest first) so "react native" for a mobile
    # role is not read as the frontend term "react".
    for term in sorted(allowed, key=len, reverse=True):
        lowered = re.sub(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", " ", lowered)
    extra = " ".join(e.lower() for e in extra_allowed if e)
    found = []
    for term in TECH_TERMS:
        if term in allowed or not _contains_term(lowered, term):
            continue
        if extra and _contains_term(extra, term):
            continue
        found.append(term)
    return found
