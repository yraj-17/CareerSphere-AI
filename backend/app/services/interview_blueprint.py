"""
Interview blueprint: the server-decided plan for every question slot.

The blueprint is built deterministically from the selected role before any
question is generated. The LLM later writes question text for one slot at a
time but cannot choose the topic: each slot's competency comes from here.

Slot rules
----------
* TECHNICAL : all slots technical; practical = ceil(total / 3)
* MIXED     : technical = ceil(total / 2), behavioral = the rest;
              practical = ceil(technical / 3), reserved inside the technical part
* BEHAVIORAL: all slots behavioral; no practical slots
Practical slots are part of the configured total, never extra questions.

Placement: practical slot i (0-based) of p sits at position
floor((i + 0.5) * n / p) + 1 within the technical sequence, so practical work is
spread out and never the opening question. MIXED alternates technical and
behavioral, starting with technical.

Competency choice
-----------------
Priority: role → focus areas → difficulty → type. Profile data is not an input.
* Focus areas that match the role's focus groups restrict the competency pool;
  if the pool is too small it is topped up from the rest of the role by weight.
* Practical slots cycle through the role's preferred practical kinds, picking
  the highest-weighted unused competency of each kind (so a Frontend interview
  gets a JavaScript coding task and a React implementation task, not two of one).
* Practical supply: when the caller passes the set of (kind, competency) that has a
  verified problem / validated scenario / calculation engine, practical slots are
  planned only on supplied competencies (focus areas are still preferred). If the
  role has no supplied practical competency at all, the slots are still planned
  (they are mandatory) but marked assessment_available = False — never filled with
  unrelated material.
* Conceptual slots take the highest-weighted competencies, preferring ones not
  already covered by a practical slot; with more slots than competencies, extra
  slots are apportioned by weight (largest remainder).
"""

from __future__ import annotations

import math
from typing import Iterable

from app.data.interview_roles import BEHAVIORAL_COMPETENCIES
from app.services.interview_role_service import ResolvedRole

BLUEPRINT_VERSION = 1
MIN_QUESTIONS = 3
MAX_QUESTIONS = 12


def practical_count(interview_type: str, total: int) -> int:
    if interview_type == "TECHNICAL":
        return math.ceil(total / 3)
    if interview_type == "MIXED":
        return math.ceil(math.ceil(total / 2) / 3)
    return 0


def _practical_positions(technical_count: int, practical: int) -> set[int]:
    """1-based positions within the technical sequence."""
    if practical <= 0:
        return set()
    return {math.floor((i + 0.5) * technical_count / practical) + 1 for i in range(practical)}


def _ranked(competencies: list[dict]) -> list[dict]:
    # stable sort: weight desc, then catalog order
    return sorted(competencies, key=lambda c: -c["weight"])


def _pool(role: ResolvedRole, focus_areas: Iterable[str]) -> tuple[list[dict], list[str]]:
    wanted = {f.strip().lower() for f in focus_areas if f and f.strip()}
    matched_focus = [f for f in role.focus_areas if f.lower() in wanted]
    if not matched_focus:
        return _ranked(role.competencies), []
    focused = [c for c in role.competencies if c["focus"] in matched_focus]
    rest = [c for c in role.competencies if c["focus"] not in matched_focus]
    return _ranked(focused) + _ranked(rest), matched_focus


def _pick_practical(preferred_kinds: list[str], candidates: list[dict], count: int) -> list[dict]:
    if count <= 0 or not candidates:
        return []
    kinds = [k for k in preferred_kinds if any(c["practical"] == k for c in candidates)]
    if not kinds:
        kinds = list(dict.fromkeys(c["practical"] for c in candidates))
    picked: list[dict] = []
    used: set[str] = set()
    kind_index = 0
    while len(picked) < count:
        progressed = False
        for _ in range(len(kinds)):
            kind = kinds[kind_index % len(kinds)]
            kind_index += 1
            choice = next((c for c in candidates if c["practical"] == kind and c["id"] not in used), None)
            if choice:
                picked.append(choice)
                used.add(choice["id"])
                progressed = True
                break
        if not progressed:
            used.clear()  # every practical competency used once; cycle again by kind preference
        if len(picked) >= count:
            break
    return picked


def _apportion(pool: list[dict], count: int, avoid_ids: set[str], priority_ids: frozenset[str] = frozenset()) -> list[dict]:
    """
    Pick `count` competencies. Priority (focus) competencies come first even if a
    practical slot already covers them — focus outranks variety. Other competencies
    already covered by a practical slot go last.
    """
    if count <= 0:
        return []
    preferred = (
        [c for c in pool if c["id"] in priority_ids]
        + [c for c in pool if c["id"] not in priority_ids and c["id"] not in avoid_ids]
        + [c for c in pool if c["id"] not in priority_ids and c["id"] in avoid_ids]
    )
    if count <= len(preferred):
        return preferred[:count]
    total_weight = sum(c["weight"] for c in preferred)
    extra = count - len(preferred)
    shares = [(c, extra * c["weight"] / total_weight) for c in preferred]
    allocation = {c["id"]: 1 + int(share) for c, share in shares}
    remaining = count - sum(allocation.values())
    for c, share in sorted(shares, key=lambda item: -(item[1] - int(item[1]))):
        if remaining <= 0:
            break
        allocation[c["id"]] += 1
        remaining -= 1
    # Spread repeats out: round-robin over competencies in priority order.
    ordered: list[dict] = []
    while len(ordered) < count:
        for c in preferred:
            if allocation[c["id"]] > 0 and len(ordered) < count:
                ordered.append(c)
                allocation[c["id"]] -= 1
    return ordered


def _slot(position: int, kind: str, category: str, competency: dict) -> dict:
    return {
        "position": position,
        "kind": kind,
        "category": category,
        "competency_id": competency["id"],
        "competency": competency["name"],
        "focus": competency["focus"],
    }


def build_blueprint(
    role: ResolvedRole,
    *,
    interview_type: str,
    difficulty: str,
    total_questions: int,
    focus_areas: Iterable[str] = (),
    practical_supply: set[tuple[str, str]] | None = None,
) -> dict:
    if not MIN_QUESTIONS <= total_questions <= MAX_QUESTIONS:
        raise ValueError(f"total_questions must be between {MIN_QUESTIONS} and {MAX_QUESTIONS}")
    focus_areas = list(focus_areas)

    if interview_type == "TECHNICAL":
        technical, behavioral = total_questions, 0
    elif interview_type == "MIXED":
        technical = math.ceil(total_questions / 2)
        behavioral = total_questions - technical
    else:
        technical, behavioral = 0, total_questions

    practical = practical_count(interview_type, total_questions)
    conceptual = technical - practical

    pool, matched_focus = _pool(role, focus_areas)
    focused_ids = {c["id"] for c in role.competencies if c["focus"] in matched_focus}
    practical_pool = [c for c in pool if c["practical"]]
    if practical_supply is not None:
        # Plan practical work only where it can really be assessed; keep the full pool
        # only when nothing is supplied (those slots are then marked unavailable).
        practical_pool = [c for c in practical_pool if (c["practical"], c["id"]) in practical_supply] or practical_pool
    if matched_focus:
        # Prefer practical work inside the chosen focus; fall back to the whole role
        # because practical slots are mandatory for technical interviews.
        practical_pool = [c for c in practical_pool if c["id"] in focused_ids] or practical_pool
    practical_comps = _pick_practical(role.practical_kinds, practical_pool, practical)
    if practical and len(practical_comps) < practical:
        raise ValueError(f"Role '{role.title}' has no practical-capable competencies")
    conceptual_pool = [c for c in pool if c["id"] in focused_ids] if matched_focus else pool
    if matched_focus and len(conceptual_pool) < conceptual:
        conceptual_pool = pool
    conceptual_comps = _apportion(
        conceptual_pool, conceptual, {c["id"] for c in practical_comps}, frozenset(focused_ids)
    )
    behavioral_comps = _apportion(list(BEHAVIORAL_COMPETENCIES_DICTS), behavioral, set())

    # Technical sequence with practical slots placed at their positions.
    practical_at = _practical_positions(technical, practical)
    technical_slots: list[tuple[str, dict]] = []
    p_iter, c_iter = iter(practical_comps), iter(conceptual_comps)
    for index in range(1, technical + 1):
        if index in practical_at:
            comp = next(p_iter)
            technical_slots.append((comp["practical"], comp))
        else:
            technical_slots.append(("question", next(c_iter)))

    slots: list[dict] = []
    if interview_type == "MIXED":
        b_iter = iter(behavioral_comps)
        t_iter = iter(technical_slots)
        for position in range(1, total_questions + 1):
            if position % 2 == 1:
                kind, comp = next(t_iter)
                slots.append(_slot(position, kind, "TECHNICAL", comp))
            else:
                slots.append(_slot(position, "question", "BEHAVIORAL", next(b_iter)))
    elif interview_type == "TECHNICAL":
        slots = [_slot(i, kind, "TECHNICAL", comp) for i, (kind, comp) in enumerate(technical_slots, start=1)]
    else:
        slots = [_slot(i, "question", "BEHAVIORAL", comp) for i, comp in enumerate(behavioral_comps, start=1)]

    if practical_supply is not None:
        for s in slots:
            if s["kind"] != "question":
                s["assessment_available"] = (s["kind"], s["competency_id"]) in practical_supply

    slot_counts: dict[str, int] = {}
    for s in slots:
        if s["category"] == "TECHNICAL":
            slot_counts[s["competency_id"]] = slot_counts.get(s["competency_id"], 0) + 1
    return {
        "version": BLUEPRINT_VERSION,
        "target_role": role.title,
        "role": {
            "slug": role.slug,
            "canonical_title": role.canonical_title,
            "source": role.source,
            "family": role.family,
            "summary": role.summary,
            "languages": role.languages,
        },
        "interview_type": interview_type,
        "difficulty": difficulty,
        "focus_areas": focus_areas,
        "matched_focus_areas": matched_focus,
        "total_questions": total_questions,
        "technical_questions": technical,
        "behavioral_questions": behavioral,
        "practical_question_count": practical,
        "conceptual_question_count": conceptual,
        # Full role snapshot so the session never depends on later catalog edits.
        "competencies": [
            {**{k: c[k] for k in ("id", "name", "focus", "weight", "practical", "description", "keywords")},
             "planned_slots": slot_counts.get(c["id"], 0)}
            for c in role.competencies
        ],
        "role_practical_kinds": role.practical_kinds,
        "practical_supply_checked": practical_supply is not None,
        "question_slots": slots,
    }


def role_from_blueprint(blueprint: dict) -> ResolvedRole:
    meta = blueprint["role"]
    return ResolvedRole(
        title=blueprint["target_role"],
        slug=meta.get("slug"),
        canonical_title=meta.get("canonical_title") or blueprint["target_role"],
        source=meta.get("source", "custom"),
        family=meta.get("family", ""),
        summary=meta.get("summary", ""),
        competencies=[{k: v for k, v in c.items() if k != "planned_slots"} for c in blueprint["competencies"]],
        practical_kinds=list(blueprint.get("role_practical_kinds", [])),
        languages=list(meta.get("languages", [])),
    )


def slot_at(blueprint: dict, position: int) -> dict | None:
    slots = blueprint.get("question_slots", [])
    return slots[position - 1] if 1 <= position <= len(slots) else None


def competency_detail(blueprint: dict, competency_id: str) -> dict | None:
    for c in blueprint.get("competencies", []):
        if c["id"] == competency_id:
            return c
    return next((c for c in BEHAVIORAL_COMPETENCIES_DICTS if c["id"] == competency_id), None)


BEHAVIORAL_COMPETENCIES_DICTS = tuple(
    {"id": c.id, "name": c.name, "focus": c.focus, "weight": 1.0, "practical": None, "keywords": [], "description": c.description}
    for c in BEHAVIORAL_COMPETENCIES
)
