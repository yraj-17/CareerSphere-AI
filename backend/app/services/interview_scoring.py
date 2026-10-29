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
    "Each answer is scored from AI-rated dimensions using fixed weights for its category "
    "(technical: accuracy 40%, reasoning 25%, relevance 20%, clarity 15%; behavioral: "
    "structure 30%, relevance 25%, clarity 25%, reflection 20%). The overall score is the "
    "mean of evaluated answer scores. Unanswered or unevaluated questions are excluded."
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


def aggregate(rows: list[dict]) -> dict:
    """
    Build report aggregates from saved question/answer rows.

    Each row: {question_id, question_order, competency, category,
               answered: bool, score: int|None, dimensions: dict|None}
    """
    evaluated = [row for row in rows if row.get("score") is not None]

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

    return {
        "overall_score": _mean(row["score"] for row in evaluated),
        "aggregates": {
            "question_count": len(rows),
            "answered_count": sum(1 for row in rows if row.get("answered")),
            "evaluated_count": len(evaluated),
            "dimension_scores": dimension_scores,
            "category_scores": category_scores,
            "strongest": [ref(row) for row in strongest],
            "weakest": [ref(row) for row in weakest],
            "methodology": METHODOLOGY,
        },
    }
