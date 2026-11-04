"""
Deterministic scoring for the AI Interviewer.

The model rates individual dimensions (0-100); the backend — never the model —
turns those into answer scores and report aggregates so the methodology is
consistent, documented, and testable.

Answer score
    Weighted sum of the dimensions that apply to the question's category:
      TECHNICAL : accuracy 40%, reasoning 25%, relevance 20%, clarity 15%
      BEHAVIORAL: structure 30%, relevance 25%, clarity 25%, reflection 20%
    Technical-correctness criteria are never applied to behavioral answers.

Overall interview score
    Mean of the per-answer scores of evaluated answers. Each answer score
    already uses the criteria appropriate to its category, so a mixed interview
    is not judged by averaging unrelated dimensions together. Unanswered or
    unevaluated questions are excluded and reported in the counts.

Dimension breakdown
    Each dimension is averaged only over the answers where it applies.
"""

from __future__ import annotations

from typing import Iterable, Optional

CATEGORY_WEIGHTS: dict[str, dict[str, float]] = {
    "TECHNICAL": {"accuracy": 0.40, "reasoning": 0.25, "relevance": 0.20, "clarity": 0.15},
    "BEHAVIORAL": {"structure": 0.30, "relevance": 0.25, "clarity": 0.25, "reflection": 0.20},
}
ALL_DIMENSIONS = ("relevance", "clarity", "accuracy", "reasoning", "structure", "reflection")

METHODOLOGY = (
    "Conceptual and behavioral answers are each scored from AI-rated dimensions using fixed weights "
    "for their category (technical: accuracy 40%, reasoning 25%, relevance 20%, clarity 15%; "
    "behavioral: structure 30%, relevance 25%, clarity 25%, reflection 20%). The overall interview "
    "score is the mean of evaluated answer scores. Practical assessments are scored separately: "
    "calculations are auto-graded against values computed deterministically (Python ipaddress); "
    "practical scenarios are AI-reviewed against a fixed rubric and are not executed; coding uses "
    "70% weighted test results + 30% AI code review once the in-interview editor is enabled. Practical "
    "slots with no verified assessment are reported but never scored. Unanswered or unevaluated "
    "questions are excluded."
)


def _mean(values: Iterable[int]) -> Optional[int]:
    items = list(values)
    if not items:
        return None
    return int(round(sum(items) / len(items)))


def applicable_dimensions(category: str) -> tuple[str, ...]:
    return tuple(CATEGORY_WEIGHTS[category].keys())


def answer_score(category: str, dimensions: dict[str, int]) -> int:
    """Weighted 0-100 score for one answer. Raises KeyError if a required dimension is missing."""
    weights = CATEGORY_WEIGHTS[category]
    total = sum(weight * max(0, min(100, int(dimensions[name]))) for name, weight in weights.items())
    return int(round(total))


def _competency_scores(conceptual_rows: list[dict]) -> list[dict]:
    """Role-specific competency breakdown, in the order competencies were asked."""
    groups: dict[tuple[str, str], list[dict]] = {}
    for row in conceptual_rows:
        groups.setdefault((row["category"], row["competency"]), []).append(row)
    return [
        {
            "competency": competency,
            "category": category,
            "score": _mean(r["score"] for r in items if r.get("score") is not None),
            "questions": len(items),
            "evaluated": sum(1 for r in items if r.get("score") is not None),
        }
        for (category, competency), items in groups.items()
    ]


def _practical_section(rows: list[dict], blueprint: Optional[dict], available: Iterable[str]) -> dict:
    """
    Practical slots, one item each:
      not_available  no verified assessment for this slot (or the kind is not enabled)
      awaiting_editor  a verified coding/SQL problem is assigned, but candidate code submission
                     is not enabled in the interview yet (code editor phase) — not scored
      not_reached    planned but never prepared (interview ended first)
      not_answered   prepared and answerable but not submitted
      not_assessed   submitted, evaluation pending or failed
      assessed       scored (method: deterministic | ai_rubric | ...)
    """
    available = set(available)
    planned = [s for s in (blueprint or {}).get("question_slots", []) if s.get("kind", "question") != "question"]
    reached = {row["question_order"]: row for row in rows if row.get("kind", "question") != "question"}
    items = []
    for slot in planned:
        row = reached.get(slot["position"])
        if row is not None and not row.get("available", True):
            item_status = "awaiting_editor" if row.get("problem_assigned") else "not_available"
        elif row is None and (slot["kind"] not in available or slot.get("assessment_available") is False):
            item_status = "not_available"
        elif row is None:
            item_status = "not_reached"
        elif row.get("score") is not None:
            item_status = "assessed"
        elif row.get("answered"):
            item_status = "not_assessed"
        else:
            item_status = "not_answered"
        items.append({
            "position": slot["position"],
            "kind": slot["kind"],
            "competency": slot["competency"],
            "status": item_status,
            "score": row.get("score") if row is not None and item_status == "assessed" else None,
            "method": row.get("method") if row is not None and item_status == "assessed" else None,
            # {difficulty, planned_difficulty, difficulty_fallback} of the assigned assessment, if any
            "difficulty": row.get("difficulty") if row is not None else None,
        })
    assessed = [i["score"] for i in items if i["status"] == "assessed"]
    return {
        "reserved": len(planned),
        "reached": len(reached),
        "assessed": len(assessed),
        "score": _mean(assessed),
        "available": bool(planned) and all(i["status"] not in ("not_available", "awaiting_editor") for i in items),
        "kinds": sorted({slot["kind"] for slot in planned}),
        "items": items,
    }


def aggregate(rows: list[dict], blueprint: Optional[dict] = None, available_practical_kinds: Iterable[str] = ()) -> dict:
    """
    Build report aggregates from saved question/answer rows.

    Each row: {question_id, question_order, competency, category, kind,
               answered: bool, score: int|None, dimensions: dict|None}
    Rows with kind != "question" are practical slots and are scored separately.
    """
    conceptual = [row for row in rows if row.get("kind", "question") == "question"]
    evaluated = [row for row in conceptual if row.get("score") is not None]

    dimension_scores: dict[str, Optional[int]] = {}
    for name in ALL_DIMENSIONS:
        dimension_scores[name] = _mean(
            row["dimensions"][name]
            for row in evaluated
            if row.get("dimensions") and row["dimensions"].get(name) is not None
        )

    category_scores = {
        category: _mean(row["score"] for row in evaluated if row["category"] == category)
        for category in CATEGORY_WEIGHTS
    }

    def ref(row: dict) -> dict:
        return {
            "question_id": row["question_id"],
            "question_order": row["question_order"],
            "competency": row["competency"],
            "category": row["category"],
            "score": row["score"],
        }

    ranked = sorted(evaluated, key=lambda row: (-row["score"], row["question_order"]))
    strongest = ranked[: min(2, (len(ranked) + 1) // 2)]
    strongest_ids = {row["question_id"] for row in strongest}
    weakest = [row for row in reversed(ranked) if row["question_id"] not in strongest_ids][:2]

    technical_evaluated = sum(1 for row in evaluated if row["category"] == "TECHNICAL")
    sections = {
        "conceptual": {
            "score": category_scores["TECHNICAL"],
            "evaluated": technical_evaluated,
            "questions": sum(1 for row in conceptual if row["category"] == "TECHNICAL"),
        },
        "behavioral": {
            "score": category_scores["BEHAVIORAL"],
            "evaluated": len(evaluated) - technical_evaluated,
            "questions": sum(1 for row in conceptual if row["category"] == "BEHAVIORAL"),
        },
        "communication": {"score": dimension_scores["clarity"]},
        "problem_solving": {"score": dimension_scores["reasoning"]},
        "practical": _practical_section(rows, blueprint, available_practical_kinds),
    }

    return {
        "overall_score": _mean(row["score"] for row in evaluated),
        "aggregates": {
            "question_count": len(rows),
            "answered_count": sum(1 for row in rows if row.get("answered")),
            "evaluated_count": len(evaluated),
            "dimension_scores": dimension_scores,
            "category_scores": category_scores,
            "competency_scores": _competency_scores(conceptual),
            "sections": sections,
            "strongest": [ref(row) for row in strongest],
            "weakest": [ref(row) for row in weakest],
            "methodology": METHODOLOGY,
        },
    }
