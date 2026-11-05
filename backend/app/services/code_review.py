"""
AI Code Review: rubric, deterministic scoring, and integrity rules (no I/O here).

Judge0 is the only authority on execution: verdicts, test results and correctness come
from coding_service. The model only rates code *quality* against the fixed rubric below;
the backend computes every aggregate score from the validated per-criterion ratings, and
any review text claiming execution outcomes (compiled, passed tests, Accepted...) is
rejected rather than shown.
"""
from __future__ import annotations

import math
import re
from typing import Optional

LABEL = "AI Code Review"
EXECUTION_NOTE = "Correctness comes only from Judge0 execution; this review rates code quality and is not an execution result."

# (key, title, weight %) — weights sum to 100.
CRITERIA: tuple[tuple[str, str, int], ...] = (
    ("problem_solving", "Problem-solving approach", 25),
    ("code_quality", "Code quality and readability", 20),
    ("efficiency", "Algorithm efficiency", 20),
    ("time_complexity", "Time complexity analysis", 15),
    ("space_complexity", "Space complexity analysis", 10),
    ("edge_cases", "Edge-case handling and best practices", 10),
)
WEIGHTS = {key: weight for key, _, weight in CRITERIA}
TITLES = {key: title for key, title, _ in CRITERIA}
assert sum(WEIGHTS.values()) == 100

CORRECTNESS_WEIGHT = 0.70
QUALITY_WEIGHT = 0.30


def quality_score(criteria: dict[str, int]) -> float:
    """Weighted mean of the six criterion scores (each 0-100), rounded to one decimal."""
    missing = set(WEIGHTS) - set(criteria)
    if missing:
        raise ValueError(f"missing criteria: {sorted(missing)}")
    for key in WEIGHTS:
        value = criteria[key]
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 100:
            raise ValueError(f"criterion {key} must be an integer 0-100")
    return round(sum(criteria[key] * weight for key, weight in WEIGHTS.items()) / 100, 1)


def round_half_up(value: float) -> int:
    """Integer score rounding that matches the UI (92.5 -> 93; Python's round() would give 92)."""
    return int(math.floor(value + 0.5))


def combined_score(correctness: Optional[float], quality: Optional[float]) -> Optional[float]:
    """
    Coding Score = Correctness x 0.70 + AI Quality x 0.30.
    None when either part is missing — a combined score is never manufactured.
    """
    if correctness is None or quality is None:
        return None
    return round(correctness * CORRECTNESS_WEIGHT + quality * QUALITY_WEIGHT, 1)


# Phrases asserting execution outcomes. The model is told the real Judge0 summary only so it
# can reason about it; it may not restate or invent verdicts, compilation, or test results.
_EXECUTION_CLAIMS = [
    r"\b(compiles?|compiled|compiling)\s+(successfully|fine|correctly|cleanly|without (any )?errors?)\b",
    r"\b(successfully|correctly)\s+compiled\b",
    r"\b(passe[sd]|passing|pass)\s+(all|every|each|the)\s+(of\s+the\s+)?(hidden\s+|sample\s+|public\s+)?(test|test cases|tests|cases)\b",
    r"\ball\s+(the\s+)?(hidden\s+|sample\s+)?tests?\s+(pass|passed|succeed|succeeded)\b",
    r"\b(solution|code|submission|program|query|script)\s+(is|was|would be|will be|gets|got)\s+accepted\b",
    r"\b(i|we)\s+(ran|executed|tested|verified)\b",
    r"\bverified\s+(that\s+)?(the\s+)?(fix|solution|code)\b",
]
_CLAIM_RE = re.compile("|".join(f"(?:{p})" for p in _EXECUTION_CLAIMS), re.IGNORECASE)


def execution_claims(texts: list[str]) -> list[str]:
    """Execution claims found in review text (empty list = acceptable)."""
    found = []
    for text in texts:
        found.extend(match.group(0) for match in _CLAIM_RE.finditer(text or ""))
    return found


def review_texts(review: dict) -> list[str]:
    texts = [review.get("summary", ""), review.get("time_complexity", ""), review.get("space_complexity", "")]
    for key in ("strengths", "weaknesses", "improvements", "alternative_approaches", "missing_edge_cases", "recommendations"):
        texts.extend(review.get(key) or [])
    return texts


def criteria_view(criteria: dict[str, int]) -> list[dict]:
    return [{"id": key, "title": title, "weight": weight, "score": criteria.get(key)} for key, title, weight in CRITERIA]
