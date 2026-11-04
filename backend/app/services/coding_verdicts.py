"""
Map real Judge0 results to CareerSphere verdicts, per test and per submission.

Per test (Judge0 1.13.1 status ids):
  6            → COMPILATION_ERROR
  5            → TIME_LIMIT_EXCEEDED
  7-12         → MEMORY_LIMIT_EXCEEDED when there is evidence (see below), otherwise RUNTIME_ERROR
  3            → program ran to completion; ACCEPTED / WRONG_ANSWER is decided by the
                 problem's own checker (expected outputs are never sent to Judge0)
  13, 14, else → JUDGE_ERROR (an execution-service fault, not the candidate's)

Judge0 1.13.1 has no Memory Limit Exceeded status: an out-of-memory program ends as a
runtime error. MLE is reported only when the runtime error coincides with evidence —
peak memory at (>= 95% of) the configured limit, or a recognised out-of-memory message.
Other runtime errors stay RUNTIME_ERROR. The original Judge0 status is always kept.

Submission verdict: COMPILATION_ERROR if compilation failed; otherwise ACCEPTED only if
every required test passed; otherwise the verdict of the first failing test (in order).
Correctness = passed weight / total weight × 100. No AI input is involved.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from app.services.coding_checkers import run_checker
from app.services.judge0_client import ExecutionResult

ACCEPTED = "ACCEPTED"
WRONG_ANSWER = "WRONG_ANSWER"
COMPILATION_ERROR = "COMPILATION_ERROR"
RUNTIME_ERROR = "RUNTIME_ERROR"
TIME_LIMIT_EXCEEDED = "TIME_LIMIT_EXCEEDED"
MEMORY_LIMIT_EXCEEDED = "MEMORY_LIMIT_EXCEEDED"
JUDGE_ERROR = "JUDGE_ERROR"
EXECUTED = "EXECUTED"  # ran with no expected output to compare (custom input)

# Verified on the CareerSphere Judge0 instance: program stdout is truncated at exactly
# 64 KiB. Problem bank outputs are kept well below it (coding_bank_service).
JUDGE0_STDOUT_LIMIT_BYTES = 65536

VERDICT_LABELS = {
    ACCEPTED: "Accepted",
    WRONG_ANSWER: "Wrong Answer",
    COMPILATION_ERROR: "Compilation Error",
    RUNTIME_ERROR: "Runtime Error",
    TIME_LIMIT_EXCEEDED: "Time Limit Exceeded",
    MEMORY_LIMIT_EXCEEDED: "Memory Limit Exceeded",
    JUDGE_ERROR: "Execution Service Error",
    EXECUTED: "Executed",
}

MLE_MEMORY_RATIO = 0.95
_OOM_PATTERNS = re.compile(
    r"MemoryError|OutOfMemoryError|std::bad_alloc|bad_alloc|heap out of memory|Cannot allocate memory|"
    r"Allocation failed|out of memory",
    re.IGNORECASE,
)


def _is_memory_limit(result: ExecutionResult, memory_limit_kb: int) -> bool:
    if result.memory is not None and memory_limit_kb and result.memory >= MLE_MEMORY_RATIO * memory_limit_kb:
        return True
    return bool(_OOM_PATTERNS.search(result.stderr or "") or _OOM_PATTERNS.search(result.message or ""))


def classify_execution(result: ExecutionResult, memory_limit_kb: int) -> str:
    """Verdict from Judge0 alone (before any output comparison)."""
    if result.status_id == 6:
        return COMPILATION_ERROR
    if result.status_id == 5:
        return TIME_LIMIT_EXCEEDED
    if 7 <= result.status_id <= 12:
        return MEMORY_LIMIT_EXCEEDED if _is_memory_limit(result, memory_limit_kb) else RUNTIME_ERROR
    if result.status_id in (3, 4):
        return EXECUTED
    return JUDGE_ERROR


@dataclass
class TestOutcome:
    ordinal: int
    verdict: str
    judge0_status_id: int
    judge0_status: str
    time: Optional[float]
    memory: Optional[int]
    passed: bool
    weight: float
    required: bool
    hidden: bool
    reason: str = ""
    stdout: str = ""
    stderr: str = ""


def evaluate_test(
    result: ExecutionResult,
    *,
    ordinal: int,
    stdin: str,
    expected: Optional[str],
    checker: Optional[dict],
    memory_limit_kb: int,
    weight: float = 1.0,
    required: bool = True,
    hidden: bool = False,
) -> TestOutcome:
    verdict = classify_execution(result, memory_limit_kb)
    reason = ""
    if verdict == EXECUTED and expected is not None:
        passed, reason = run_checker(checker, stdin=stdin, expected=expected, actual=result.stdout)
        verdict = ACCEPTED if passed else WRONG_ANSWER
    if verdict in (WRONG_ANSWER, EXECUTED) and len((result.stdout or "").encode("utf-8")) >= JUDGE0_STDOUT_LIMIT_BYTES:
        reason = "Output reached the 64 KB limit of the execution server and was truncated."
    return TestOutcome(
        ordinal=ordinal,
        verdict=verdict,
        judge0_status_id=result.status_id,
        judge0_status=result.status_description,
        time=result.time,
        memory=result.memory,
        passed=verdict == ACCEPTED,
        weight=weight,
        required=required,
        hidden=hidden,
        reason=reason,
        stdout=result.stdout,
        stderr=result.stderr,
    )


@dataclass
class SubmissionSummary:
    verdict: str
    tests_passed: int
    tests_total: int
    correctness_score: float
    max_time: Optional[float]
    max_memory: Optional[int]
    first_failed_ordinal: Optional[int] = None
    judge_error: bool = False
    outcomes: list[TestOutcome] = field(default_factory=list)


def summarise(outcomes: list[TestOutcome]) -> SubmissionSummary:
    ordered = sorted(outcomes, key=lambda o: o.ordinal)
    total_weight = sum(o.weight for o in ordered) or 1.0
    passed_weight = sum(o.weight for o in ordered if o.passed)
    times = [o.time for o in ordered if o.time is not None]
    memories = [o.memory for o in ordered if o.memory is not None]
    first_failed = next((o for o in ordered if not o.passed), None)

    if any(o.verdict == JUDGE_ERROR for o in ordered):
        verdict = JUDGE_ERROR
    elif any(o.verdict == COMPILATION_ERROR for o in ordered):
        verdict = COMPILATION_ERROR
    elif all(o.passed for o in ordered if o.required):
        verdict = ACCEPTED
    else:
        verdict = next(o.verdict for o in ordered if o.required and not o.passed)

    return SubmissionSummary(
        verdict=verdict,
        tests_passed=sum(1 for o in ordered if o.passed),
        tests_total=len(ordered),
        correctness_score=round(100.0 * passed_weight / total_weight, 2),
        max_time=max(times) if times else None,
        max_memory=max(memories) if memories else None,
        first_failed_ordinal=first_failed.ordinal if first_failed else None,
        judge_error=verdict == JUDGE_ERROR,
        outcomes=ordered,
    )
