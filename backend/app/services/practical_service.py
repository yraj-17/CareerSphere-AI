"""
Role-specific practical assessments: supply, assignment and public views.

Kinds (from the role catalog / blueprint)
-----------------------------------------
coding, sql   a verified problem from the bank, executed on Judge0
calculation   a deterministic IPv4 task (network_calc), auto-graded
scenario      a curated scenario with a fixed rubric, AI-reviewed (not executed)

Supply
------
practical_supply(db, role) is the set of (kind, competency_id) the platform can really
assess for a role. The blueprint only plans practical slots on supplied competencies, so
an interview never gets an unrelated problem just because the bank is small. A practical
slot with no supply is kept (practical slots are mandatory and part of the question
count) but recorded as unavailable with an explicit reason — never replaced by a
theoretical question, and never filled from another role's material.

Custom (non-catalog) roles have no supply: problems and scenario rubrics are written for
specific catalog roles, and an improvised rubric would not be validated.

Selection
---------
Problems: verified, active, mapped to the role and the slot's competency, sharing a
language with the role (coding). Ranked by distance from the interview difficulty, then
by how often this candidate has already seen the problem, then by a per-session hash so
different candidates and sessions do not all get the same sequence. A problem is never
repeated within one interview. Scenarios are ranked the same way; calculations are
generated from a per-session seed.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from typing import Optional

from sqlalchemy.orm import Session

from app.data.practical_scenarios import LABEL as SCENARIO_LABEL
from app.data.practical_scenarios import SCENARIO_BY_ID, scenarios_for
from app.db.models import CodingProblem, InterviewDifficulty, InterviewQuestion, InterviewSession
from app.services import interview_blueprint as blueprints
from app.services import network_calc
from app.services.coding_bank_service import practical_kind
from app.services.interview_role_service import ResolvedRole

EXECUTABLE_KINDS = frozenset({"coding", "sql"})
CALCULATION_COMPETENCIES = frozenset({"ip-subnetting"})
DIFFICULTY_RANK = {"EASY": 0, "MEDIUM": 1, "HARD": 2}
# Interview difficulty (InterviewDifficulty) → problem / scenario / calculation difficulty.
LEVEL_FOR_INTERVIEW = {"BEGINNER": "EASY", "INTERMEDIATE": "MEDIUM", "ADVANCED": "HARD"}


def assessment_level(interview_difficulty: str) -> str:
    return LEVEL_FOR_INTERVIEW.get(interview_difficulty, interview_difficulty if interview_difficulty in DIFFICULTY_RANK else "MEDIUM")
EXECUTED_LABEL = "Executed on Judge0 — verdicts come from real test runs"
UNAVAILABLE_REASON = (
    "No verified problem or validated assessment is available for this role and competency yet, "
    "so this practical slot is recorded but not scored."
)


def _stable(seed: str) -> int:
    return int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12], 16)


# ---------------------------------------------------------------------------
# Supply
# ---------------------------------------------------------------------------


def _verified_problems(db: Session) -> list[CodingProblem]:
    return (
        db.query(CodingProblem)
        .filter(CodingProblem.is_active.is_(True), CodingProblem.verified_at.isnot(None))
        .order_by(CodingProblem.slug)
        .all()
    )


def problem_eligible(problem: CodingProblem, role: ResolvedRole, competency_id: str, kind: str) -> bool:
    if not role.slug or role.slug not in (problem.roles or []):
        return False
    if competency_id not in (problem.competencies or []) or practical_kind(problem.category) != kind:
        return False
    if kind == "coding" and role.languages and not set(problem.languages or []) & set(role.languages):
        return False
    return True


def practical_supply(db: Session, role: ResolvedRole) -> set[tuple[str, str]]:
    if not role.slug:
        return set()
    practical = {c["id"]: c["practical"] for c in role.competencies if c.get("practical")}
    supply: set[tuple[str, str]] = set()
    for problem in _verified_problems(db):
        kind = practical_kind(problem.category)
        for competency_id in problem.competencies or []:
            if practical.get(competency_id) == kind and problem_eligible(problem, role, competency_id, kind):
                supply.add((kind, competency_id))
    for competency_id, kind in practical.items():
        if kind == "scenario" and scenarios_for(role.slug, competency_id):
            supply.add(("scenario", competency_id))
        if kind == "calculation" and competency_id in CALCULATION_COMPETENCIES:
            supply.add(("calculation", competency_id))
    return supply


# ---------------------------------------------------------------------------
# Assignment
# ---------------------------------------------------------------------------


def _history(db: Session, user_id: str, exclude_session_id: str) -> tuple[Counter, Counter]:
    rows = (
        db.query(InterviewQuestion.problem_id, InterviewQuestion.practical)
        .join(InterviewSession, InterviewSession.id == InterviewQuestion.session_id)
        .filter(InterviewSession.user_id == user_id, InterviewSession.id != exclude_session_id, InterviewQuestion.kind != "question")
        .all()
    )
    problems, scenarios = Counter(), Counter()
    for problem_id, practical in rows:
        if problem_id:
            problems[problem_id] += 1
        if isinstance(practical, dict) and practical.get("scenario_id"):
            scenarios[practical["scenario_id"]] += 1
    return problems, scenarios


def assign(db: Session, user_id: str, session: InterviewSession, slot: dict) -> Optional[dict]:
    """Choose the assessment for one practical slot, or None if nothing verified fits."""
    blueprint = session.blueprint
    role = blueprints.role_from_blueprint(blueprint)
    kind, competency_id = slot["kind"], slot["competency_id"]
    difficulty = assessment_level(blueprint["difficulty"])
    taken_problems = {q.problem_id for q in session.questions if q.problem_id}
    taken_scenarios = {(q.practical or {}).get("scenario_id") for q in session.questions if isinstance(q.practical, dict)}
    seen_problems, seen_scenarios = _history(db, user_id, session.id)
    salt = f"{session.id}:{slot['position']}"

    if kind in EXECUTABLE_KINDS:
        candidates = [
            p for p in _verified_problems(db)
            if problem_eligible(p, role, competency_id, kind) and p.id not in taken_problems
        ]
        if not candidates:
            return None
        target = DIFFICULTY_RANK.get(difficulty, 1)
        problem = min(
            candidates,
            key=lambda p: (abs(DIFFICULTY_RANK.get(p.difficulty, 1) - target), seen_problems[p.id], _stable(f"{salt}:{p.slug}")),
        )
        languages = [lang for lang in problem.languages if lang in role.languages] or list(problem.languages)
        return {
            "type": kind,
            "problem_id": problem.id,
            "problem_slug": problem.slug,
            "title": problem.title,
            "difficulty": problem.difficulty,
            "planned_difficulty": difficulty,
            "difficulty_fallback": problem.difficulty != difficulty,
            "languages": languages,
        }

    if kind == "scenario":
        if not role.slug:
            return None
        pool = [s for s in scenarios_for(role.slug, competency_id) if s.id not in taken_scenarios]
        if not pool:
            return None
        matching = [s for s in pool if difficulty in s.difficulties] or pool
        scenario = min(matching, key=lambda s: (seen_scenarios[s.id], _stable(f"{salt}:{s.id}")))
        target = DIFFICULTY_RANK.get(difficulty, 1)
        assessed = (
            difficulty if difficulty in scenario.difficulties
            else min(scenario.difficulties, key=lambda level: abs(DIFFICULTY_RANK.get(level, 1) - target))
        )
        return {
            "type": "scenario", "scenario_id": scenario.id, "title": scenario.title,
            "difficulty": assessed, "planned_difficulty": difficulty, "difficulty_fallback": assessed != difficulty,
        }

    if kind == "calculation":
        if not role.slug or competency_id not in CALCULATION_COMPETENCIES:
            return None
        used = tuple(
            q.practical["task"]["type"] for q in session.questions
            if isinstance(q.practical, dict) and q.practical.get("type") == "calculation"
        )
        task = network_calc.generate_task(salt, difficulty, avoid_types=used)
        # Calculations are generated at exactly the planned level, so there is never a fallback.
        return {"type": "calculation", "task": task, "difficulty": difficulty, "planned_difficulty": difficulty,
                "difficulty_fallback": False}
    return None


def build_question(blueprint: dict, slot: dict, spec: dict, *, answerable: bool) -> InterviewQuestion:
    kind = slot["kind"]
    if kind in EXECUTABLE_KINDS:
        label = "SQL assessment" if kind == "sql" else "Coding assessment"
        text = f"{label}: {spec['title']}"
        context = (
            f"Assigned problem ({spec['difficulty'].title()}). Your code runs on Judge0 against public and hidden tests."
            if answerable else
            f"Assigned problem: {spec['title']}. The in-interview code editor is not enabled in this build yet, "
            "so this assessment is recorded but not scored."
        )
        problem_id = spec["problem_id"]
    elif kind == "scenario":
        scenario = SCENARIO_BY_ID[spec["scenario_id"]]
        text = f"Practical scenario: {scenario.title}"
        context = f"{SCENARIO_LABEL}. Read the situation and answer every task in writing."
        problem_id = None
    else:
        view = network_calc.public_view(spec["task"])
        text = f"Practical calculation: {view['title']}. {view['prompt']}"
        context = f"{network_calc.LABEL}."
        problem_id = None
    return InterviewQuestion(
        question_order=slot["position"],
        question_text=text,
        category=slot["category"],
        kind=kind,
        competency=slot["competency"],
        difficulty=InterviewDifficulty(blueprint["difficulty"]),
        interviewer_context=context,
        problem_id=problem_id,
        practical=spec,
    )


# ---------------------------------------------------------------------------
# Public view (what the client may see — never answers or rubrics)
# ---------------------------------------------------------------------------


def difficulty_view(spec: dict) -> dict:
    """
    Planned vs assessed level of an assigned practical. `difficulty_fallback` is True when no
    verified assessment exists at the planned level and the closest verified level was used;
    it is shown to the candidate and recorded in the report, never hidden.
    """
    assessed = spec.get("difficulty") or ""
    planned = spec.get("planned_difficulty") or assessed
    return {
        "difficulty": assessed,
        "planned_difficulty": planned,
        "difficulty_fallback": bool(spec.get("difficulty_fallback")) or (bool(assessed) and assessed != planned),
    }


def public_view(question: InterviewQuestion) -> Optional[dict]:
    spec = question.practical if isinstance(question.practical, dict) else None
    kind = question.kind or "question"
    if kind == "question":
        return None
    if spec is None or spec.get("type") == "unavailable":
        return {"type": kind, "available": False, "reason": (spec or {}).get("reason") or UNAVAILABLE_REASON}
    if kind in EXECUTABLE_KINDS:
        return {
            "type": kind,
            "available": True,
            "label": EXECUTED_LABEL,
            "problem_id": spec.get("problem_id") or question.problem_id,
            "title": spec.get("title") or question.question_text,
            **difficulty_view(spec),
            "languages": list(spec.get("languages") or []),
        }
    if kind == "scenario":
        scenario = SCENARIO_BY_ID.get(spec.get("scenario_id"))
        if scenario is None:
            return {"type": kind, "available": False, "reason": UNAVAILABLE_REASON}
        return {
            "type": "scenario",
            "available": True,
            "label": SCENARIO_LABEL,
            "title": scenario.title,
            "context": scenario.context,
            "tasks": list(scenario.tasks),
            "deliverable": scenario.deliverable,
            "estimated_minutes": scenario.estimated_minutes,
            "criteria": [c.title for c in scenario.rubric],  # what is assessed (titles only)
            **difficulty_view(spec),
        }
    if kind == "calculation":
        return {**network_calc.public_view(spec["task"]), "available": True, **difficulty_view(spec)}
    return None


def unavailable_spec(reason: str = UNAVAILABLE_REASON) -> dict:
    return {"type": "unavailable", "reason": reason}


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------


def scenario_rubric(scenario_id: str) -> list[dict]:
    scenario = SCENARIO_BY_ID[scenario_id]
    return [{"id": c.id, "title": c.title, "points": c.points, "expectations": c.expectations} for c in scenario.rubric]


def rubric_score(rubric: list[dict], ratings: dict[str, int]) -> int:
    """Backend-computed scenario score: rubric points weighted by the per-criterion ratings."""
    total = sum(c["points"] for c in rubric)
    earned = sum(c["points"] * max(0, min(100, int(ratings[c["id"]]))) / 100 for c in rubric)
    return int(round(100 * earned / total)) if total else 0
