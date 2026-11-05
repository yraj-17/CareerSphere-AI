"""
Coding assessment execution (Run Code / Submit Solution) on Judge0.

Correctness comes only from real execution: Judge0 compiles and runs the code;
the backend compares outputs with the problem's own checker. No AI is involved.

Request pipeline (both Run and Submit)
  1. Ownership: the interview must belong to the caller and still accept work
     (IN_PROGRESS, before deadline + grace); the question must be a coding slot
     with an assigned, verified, active problem; language must be allowed.
  2. Abuse limits (Redis): per-user per-minute rate limits for run and submit,
     and an in-flight lock so a user has at most one execution running.
     If Redis is unreachable, execution is refused (fail closed) to protect Judge0.
  3. Idempotency: the (user, idempotency_key) pair is unique in the database, so a
     retried or concurrently duplicated request returns the same submission.
  4. Execution: tests are sent to Judge0 as one batch; tokens are stored; the
     request waits up to JUDGE0_INLINE_WAIT_SECONDS, then returns RUNNING and the
     client polls GET .../coding-submissions/{id}, which resumes from stored tokens
     (so interrupted polling and restarts lose nothing).

Run      → sample tests (+ optional custom input, which has no expected output)
Submit   → every test, public and hidden; weighted correctness; final verdict

Hidden tests: inputs and expected outputs are read only here; responses carry only
the verdict and metrics; the candidate's stdout/stderr on hidden tests are neither
returned nor stored; nothing about hidden tests is logged.

SQL (SQLite) and Bash workspace problems are executed through coding_harness, which
builds the exact program Judge0 runs (e.g. schema + seed data + candidate SQL).
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from typing import Optional

from fastapi import HTTPException, status
from datetime import timedelta

from sqlalchemy import and_, or_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.data.coding_languages import (
    LANGUAGE_BY_KEY,
    LANGUAGES,
    MAX_CPU_TIME_SECONDS,
    MAX_MEMORY_KB,
    MAX_WALL_TIME_SECONDS,
)
from app.db.models import (
    CodingProblem,
    CodingSubmission,
    CodingTestCase,
    InterviewAIStatus,
    InterviewAnswer,
    InterviewMode,
    InterviewQuestion,
    InterviewReport,
    InterviewStatus,
    User,
)
from app.db.redis_client import redis_client
from app.db.session import SessionLocal
from app.schemas.coding import (
    ExampleOut,
    HiddenTestResult,
    LanguageOut,
    LanguagesResponse,
    ProblemOut,
    RunCodeRequest,
    SubmissionListResponse,
    SubmissionOut,
    SubmitSolutionRequest,
    VisibleTestResult,
)
from app.services import coding_harness as harness
from app.services import coding_verdicts as verdicts
from app.services import code_review
from app.services import interview_ai_service as ai
from app.services import interview_service
from app.services.judge0_client import ExecutionRequest, ExecutionResult, Judge0Client, Judge0Error, resolve_languages

logger = logging.getLogger(__name__)

VISIBLE_OUTPUT_LIMIT = 8 * 1024
EXECUTABLE_KINDS = frozenset({"coding", "sql"})
STATUS_QUEUED, STATUS_RUNNING, STATUS_COMPLETED, STATUS_FAILED = "QUEUED", "RUNNING", "COMPLETED", "FAILED"


def _error(code: int, message: str, **extra) -> HTTPException:
    return HTTPException(status_code=code, detail={"message": message, **extra} if extra else message)


def _client() -> Judge0Client:
    try:
        return Judge0Client.from_settings()
    except Judge0Error:
        raise _error(status.HTTP_503_SERVICE_UNAVAILABLE, "Code execution is not configured on this server.", stage="judge0_not_configured")


# ---------------------------------------------------------------------------
# Limits derived from backend problem configuration only
# ---------------------------------------------------------------------------


def execution_limits(problem: CodingProblem, language_key: str) -> dict:
    lang = LANGUAGE_BY_KEY[language_key]
    cpu = min(MAX_CPU_TIME_SECONDS, round(problem.time_limit_seconds * lang.time_multiplier, 2))
    wall = min(MAX_WALL_TIME_SECONDS, round(cpu * 2 + 1, 2))
    memory = min(MAX_MEMORY_KB, int(problem.memory_limit_kb))
    return {"cpu_time_limit": cpu, "wall_time_limit": wall, "memory_limit_kb": memory}


# ---------------------------------------------------------------------------
# Languages and problem view
# ---------------------------------------------------------------------------


async def _resolved_languages() -> tuple[bool, dict]:
    try:
        client = Judge0Client.from_settings()
    except Judge0Error:
        return False, {l.key: {"judge0_id": l.fallback_judge0_id, "label": l.fallback_label} for l in LANGUAGES}
    return True, await resolve_languages(client)


def _language_out(key: str, resolved: dict) -> LanguageOut:
    lang = LANGUAGE_BY_KEY[key]
    return LanguageOut(key=key, label=resolved[key]["label"], monaco_language=lang.monaco_language, notes=lang.notes)


async def list_languages() -> LanguagesResponse:
    available, resolved = await _resolved_languages()
    return LanguagesResponse(execution_available=available, languages=[_language_out(l.key, resolved) for l in LANGUAGES])


def _owned_coding_question(db: Session, user: User, interview_id: str, question_id: str):
    session = interview_service._get_owned_session(db, user, interview_id)  # 404 for other users' interviews
    question = next((q for q in session.questions if q.id == question_id), None)
    if question is None:
        raise _error(status.HTTP_404_NOT_FOUND, "Question not found in this interview.")
    if (question.kind or "question") not in EXECUTABLE_KINDS:
        raise _error(status.HTTP_409_CONFLICT, "This question is not a coding assessment.", status="NOT_CODING")
    problem = db.get(CodingProblem, question.problem_id) if question.problem_id else None
    if problem is None or not problem.is_active:
        raise _error(status.HTTP_409_CONFLICT, "No coding problem is assigned to this question yet.", status="NO_PROBLEM")
    return session, question, problem


def allowed_languages(question: InterviewQuestion, problem: CodingProblem) -> list[str]:
    """Languages the candidate may use: chosen when the problem was assigned, always within the problem's."""
    problem_languages = [key for key in problem.languages if key in LANGUAGE_BY_KEY]
    chosen = (question.practical or {}).get("languages") if isinstance(question.practical, dict) else None
    narrowed = [key for key in problem_languages if key in (chosen or [])]
    return narrowed or problem_languages


async def get_problem(db: Session, user: User, interview_id: str, question_id: str) -> ProblemOut:
    _, question, problem = _owned_coding_question(db, user, interview_id, question_id)
    _, resolved = await _resolved_languages()
    languages = allowed_languages(question, problem)
    tests = problem.test_cases
    return ProblemOut(
        id=problem.id,
        slug=problem.slug,
        title=problem.title,
        difficulty=problem.difficulty,
        statement=problem.statement,
        input_format=problem.input_format,
        output_format=problem.output_format,
        constraints=problem.constraints,
        examples=[ExampleOut(**e) for e in (problem.examples or [])],
        instructions=problem.instructions,
        category=problem.category,
        languages=[_language_out(k, resolved) for k in languages],
        starter_code={k: v for k, v in (problem.starter_code or {}).items() if k in languages},
        time_limit_seconds=problem.time_limit_seconds,
        memory_limit_kb=problem.memory_limit_kb,
        estimated_minutes=problem.estimated_minutes,
        sample_test_count=sum(1 for t in tests if not t.is_hidden),
        hidden_test_count=sum(1 for t in tests if t.is_hidden),
    )


# ---------------------------------------------------------------------------
# Abuse limits (Redis, fail closed)
# ---------------------------------------------------------------------------


def _rate_limit(user: User, kind: str) -> None:
    limit = settings.CODING_SUBMIT_RATE_LIMIT_PER_MINUTE if kind == "SUBMIT" else settings.CODING_RUN_RATE_LIMIT_PER_MINUTE
    key = f"coding:rate:{kind}:{user.id}:{int(interview_service.utcnow().timestamp() // 60)}"
    try:
        count = redis_client.incr(key)
        if count == 1:
            redis_client.expire(key, 120)
    except Exception:
        logger.warning("[Coding] rate limiter unavailable; refusing execution")
        raise _error(status.HTTP_503_SERVICE_UNAVAILABLE, "Code execution is temporarily unavailable. Please try again.")
    if count > limit:
        raise _error(status.HTTP_429_TOO_MANY_REQUESTS, f"Too many {'submissions' if kind == 'SUBMIT' else 'runs'}. Please wait a minute.", status="RATE_LIMITED")


def _inflight_key(user_id: str) -> str:
    return f"coding:inflight:{user_id}"


def _acquire_inflight(user: User, submission_id: str) -> None:
    try:
        acquired = redis_client.set(_inflight_key(user.id), submission_id, nx=True, ex=settings.CODING_INFLIGHT_LOCK_SECONDS)
    except Exception:
        raise _error(status.HTTP_503_SERVICE_UNAVAILABLE, "Code execution is temporarily unavailable. Please try again.")
    if not acquired:
        raise _error(status.HTTP_429_TOO_MANY_REQUESTS, "Another run or submission is still executing. Please wait for it to finish.", status="IN_FLIGHT")


def _release_inflight(user_id: str, submission_id: str) -> None:
    try:
        if redis_client.get(_inflight_key(user_id)) == submission_id:
            redis_client.delete(_inflight_key(user_id))
    except Exception:
        pass  # the lock expires on its own


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


def _source_fingerprint(language: str, source: str, custom_input: Optional[str]) -> str:
    return hashlib.sha256(f"{language}\0{source}\0{custom_input or ''}".encode("utf-8")).hexdigest()


def _plan(problem: CodingProblem, submission_type: str, custom_input: Optional[str]) -> list[dict]:
    """Which inputs to execute, in order. Inputs/expected outputs stay server-side."""
    tests: list[CodingTestCase] = list(problem.test_cases)
    if submission_type == "RUN":
        plan = [{"ordinal": t.ordinal, "kind": "sample", "test_id": t.id} for t in tests if not t.is_hidden]
        if custom_input is not None:
            plan.append({"ordinal": 0, "kind": "custom", "test_id": None})
        return plan
    return [{"ordinal": t.ordinal, "kind": "hidden" if t.is_hidden else "sample", "test_id": t.id} for t in tests]


async def _execute(db: Session, submission: CodingSubmission, problem: CodingProblem) -> None:
    """Send the planned executions to Judge0 and store the tokens (status RUNNING)."""
    client = _client()
    resolved = await resolve_languages(client)
    lang = LANGUAGE_BY_KEY[submission.language]
    limits = execution_limits(problem, submission.language)
    tests_by_id = {t.id: t for t in problem.test_cases}
    plan = _plan(problem, submission.submission_type, submission.custom_input)
    requests = []
    for item in plan:
        test_input = submission.custom_input if item["kind"] == "custom" else tests_by_id[item["test_id"]].input
        program = harness.build_program(submission.language, submission.source_code, test_input or "", problem.harness)
        requests.append(
            ExecutionRequest(
                language_id=resolved[submission.language]["judge0_id"],
                source_code=program.source_code,
                stdin=program.stdin,
                compiler_options=lang.compiler_options,
                **limits,
            )
        )
        item["line_offset"] = program.line_offset
    tokens = await client.submit_batch(requests)
    submission.judge_tokens = [{**item, "token": token} for item, token in zip(plan, tokens)]
    submission.language_label = resolved[submission.language]["label"]
    submission.status = STATUS_RUNNING
    db.commit()


def _finalize(db: Session, submission: CodingSubmission, problem: CodingProblem, results: list[ExecutionResult]) -> None:
    tests_by_id = {t.id: t for t in problem.test_cases}
    memory_limit = execution_limits(problem, submission.language)["memory_limit_kb"]
    outcomes: list[tuple[dict, verdicts.TestOutcome]] = []
    for item, result in zip(submission.judge_tokens, results):
        test = tests_by_id.get(item.get("test_id"))
        outcome = verdicts.evaluate_test(
            result,
            ordinal=item["ordinal"],
            stdin=submission.custom_input if item["kind"] == "custom" else test.input,
            expected=None if item["kind"] == "custom" else test.expected_output,
            checker=problem.checker,
            memory_limit_kb=memory_limit,
            weight=test.weight if test else 0.0,
            required=test.is_required if test else False,
            hidden=item["kind"] == "hidden",
        )
        outcomes.append((item, outcome))

    graded = [o for item, o in outcomes if item["kind"] != "custom"]
    summary = verdicts.summarise(graded) if graded else None
    stored = []
    for item, o in outcomes:
        record = {
            "ordinal": o.ordinal,
            "kind": item["kind"],
            "test_id": item.get("test_id"),
            "verdict": o.verdict,
            "passed": o.passed if item["kind"] != "custom" else None,
            "judge0_status_id": o.judge0_status_id,
            "judge0_status": o.judge0_status,
            "time": o.time,
            "memory": o.memory,
        }
        if item["kind"] != "hidden":  # program output on hidden tests is never kept
            stderr = harness.present_stderr(submission.language, o.stderr, item.get("line_offset", 0))
            record.update(stdout=o.stdout[:VISIBLE_OUTPUT_LIMIT], stderr=stderr[:VISIBLE_OUTPUT_LIMIT], reason=o.reason)
        stored.append(record)

    compile_output = next((r.compile_output for r in results if r.compile_output), None)
    custom = next((o for item, o in outcomes if item["kind"] == "custom"), None)
    if summary is not None:
        submission.verdict = summary.verdict
        submission.tests_passed, submission.tests_total = summary.tests_passed, summary.tests_total
        submission.correctness_score = summary.correctness_score
        submission.max_time_seconds, submission.max_memory_kb = summary.max_time, summary.max_memory
    elif custom is not None:  # Run with custom input only (no samples)
        submission.verdict = custom.verdict
        submission.max_time_seconds, submission.max_memory_kb = custom.time, custom.memory
    submission.results = stored
    submission.compile_output = (compile_output or "")[:VISIBLE_OUTPUT_LIMIT] or None
    submission.status = STATUS_COMPLETED
    if submission.submission_type == "SUBMIT" and submission.verdict != verdicts.JUDGE_ERROR:
        submission.ai_review_status = REVIEW_PENDING  # reviewed asynchronously; never blocks the verdict
    submission.completed_at = interview_service.utcnow()
    db.commit()
    _release_inflight(submission.user_id, submission.id)
    if submission.submission_type == "SUBMIT":
        record_interview_answer(db, submission)
    logger.info(
        "[Coding] %s %s completed: verdict=%s passed=%s/%s",
        submission.submission_type,
        submission.id,
        submission.verdict,
        submission.tests_passed,
        submission.tests_total,
    )


EXECUTED_ANSWER_LABEL = "Executed on Judge0 — scored by test results"

# ---------------------------------------------------------------------------
# AI Code Review (asynchronous; one per completed SUBMIT; never changes a verdict)
# ---------------------------------------------------------------------------

REVIEW_PENDING, REVIEW_RUNNING, REVIEW_COMPLETED, REVIEW_FAILED = "PENDING", "RUNNING", "COMPLETED", "FAILED"
REVIEW_MAX_ATTEMPTS = 3  # claims per submission (each claim makes at most ai.MAX_ATTEMPTS model calls)
REPORT_REVIEW_WAIT_SECONDS = 150.0


def _review_stale_after() -> timedelta:
    return timedelta(seconds=settings.OLLAMA_INTERVIEW_TIMEOUT_SECONDS * ai.MAX_ATTEMPTS + 60)


def coding_score_of(submission: CodingSubmission) -> Optional[float]:
    if submission.ai_review_status != REVIEW_COMPLETED:
        return None
    return code_review.combined_score(submission.correctness_score, submission.ai_quality_score)


def review_out(submission: CodingSubmission):
    from app.schemas.coding import CodeReviewCriterionOut, CodeReviewOut

    status_ = submission.ai_review_status
    if submission.submission_type != "SUBMIT" or status_ is None:
        return None
    compiled = submission.verdict != verdicts.COMPILATION_ERROR
    note = code_review.EXECUTION_NOTE if compiled else (
        "Judge0 reported a compilation error, so nothing was executed. The review explains likely causes from the code only."
    )
    if status_ != REVIEW_COMPLETED:
        return CodeReviewOut(
            status=status_, note=note, compiled=compiled,
            can_retry=status_ == REVIEW_FAILED and submission.ai_review_attempts < REVIEW_MAX_ATTEMPTS,
        )
    review = submission.ai_review or {}
    criteria = review.get("criteria") or {}
    return CodeReviewOut(
        status=status_,
        note=note,
        compiled=compiled,
        quality_score=submission.ai_quality_score,
        criteria=[CodeReviewCriterionOut(**c) for c in code_review.criteria_view(criteria)],
        summary=review.get("summary", ""),
        strengths=review.get("strengths", []),
        weaknesses=review.get("weaknesses", []),
        improvements=review.get("improvements", []),
        alternative_approaches=review.get("alternative_approaches", []),
        time_complexity=review.get("time_complexity", ""),
        space_complexity=review.get("space_complexity", ""),
        missing_edge_cases=review.get("missing_edge_cases", []),
        recommendations=review.get("recommendations", []),
        reviewed_at=submission.ai_reviewed_at,
    )


def execution_facts(submission: CodingSubmission) -> str:
    """Aggregate Judge0 outcome only — never hidden inputs or outputs."""
    label = verdicts.VERDICT_LABELS.get(submission.verdict, submission.verdict or "unknown")
    if submission.verdict == verdicts.COMPILATION_ERROR:
        return f"{label}: the code did not compile, so no test was executed."
    return (
        f"{label}; {submission.tests_passed or 0} of {submission.tests_total or 0} tests passed "
        f"(weighted correctness {round(submission.correctness_score or 0)}/100); "
        f"max time {submission.max_time_seconds}s, max memory {submission.max_memory_kb} KB."
    )


def _claim_review(db: Session, submission_id: str) -> bool:
    """Atomically take the review job: PENDING/FAILED, or RUNNING but abandoned. Bounded attempts."""
    now = interview_service.utcnow()
    result = db.execute(
        update(CodingSubmission)
        .where(
            CodingSubmission.id == submission_id,
            CodingSubmission.submission_type == "SUBMIT",
            CodingSubmission.status == STATUS_COMPLETED,
            CodingSubmission.ai_review_attempts < REVIEW_MAX_ATTEMPTS,
            or_(
                CodingSubmission.ai_review_status.in_([REVIEW_PENDING, REVIEW_FAILED]),
                and_(
                    CodingSubmission.ai_review_status == REVIEW_RUNNING,
                    CodingSubmission.ai_review_updated_at < now - _review_stale_after(),
                ),
            ),
        )
        .values(
            ai_review_status=REVIEW_RUNNING,
            ai_review_attempts=CodingSubmission.ai_review_attempts + 1,
            ai_review_updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    db.commit()
    return result.rowcount == 1


async def run_review(db: Session, submission_id: str) -> bool:
    """Review one submission if it can be claimed. Returns True if this call produced a review."""
    if not _claim_review(db, submission_id):
        return False
    db.expire_all()
    submission = db.get(CodingSubmission, submission_id)
    problem = db.get(CodingProblem, submission.problem_id)
    question = db.get(InterviewQuestion, submission.question_id)
    session = question.session
    role = interview_service.blueprints.role_from_blueprint(session.blueprint) if session.blueprint else None
    try:
        result = await ai.review_code(
            role=role.title if role else session.target_role,
            role_summary=role.summary if role else "",
            difficulty=problem.difficulty,
            title=problem.title,
            statement=problem.statement,
            constraints=problem.constraints,
            examples=list(problem.examples or []),
            language_label=submission.language_label,
            source_code=submission.source_code,
            execution_facts=execution_facts(submission),
        )
    except ai.InterviewAIError as exc:
        submission.ai_review_status = REVIEW_FAILED
        submission.ai_review = {"error_category": exc.category}
        submission.ai_review_updated_at = interview_service.utcnow()
        db.commit()
        logger.warning("[Coding] AI review of %s failed (%s, attempt %d)", submission.id, exc.category, submission.ai_review_attempts)
        apply_review_to_answer(db, submission)
        return False
    criteria = result.criteria.model_dump()
    now = interview_service.utcnow()
    submission.ai_review = result.model_dump()
    submission.ai_quality_score = code_review.quality_score(criteria)
    submission.ai_review_status = REVIEW_COMPLETED
    submission.ai_review_model = settings.OLLAMA_MODEL
    submission.ai_reviewed_at = now
    submission.ai_review_updated_at = now
    db.commit()
    logger.info("[Coding] AI review of %s completed: quality=%s", submission.id, submission.ai_quality_score)
    apply_review_to_answer(db, submission)
    return True


async def review_submission(submission_id: str) -> None:
    """Background task (own DB session): review a completed SUBMIT once."""
    db = SessionLocal()
    try:
        await run_review(db, submission_id)
    except Exception:  # noqa: BLE001 — a review failure must never affect anything else
        logger.exception("[Coding] AI review task failed for %s", submission_id)
    finally:
        db.close()


def apply_review_to_answer(db: Session, submission: CodingSubmission) -> bool:
    """
    If this submission is the question's recorded answer and the report is not finalised,
    reflect the review: quality score, combined coding score (correctness 70% + quality 30%)
    and review status. A finalised report is never changed; the review stays on the submission.
    """
    answer = db.query(InterviewAnswer).filter(InterviewAnswer.question_id == submission.question_id).first()
    if answer is None or (answer.evaluation or {}).get("submission_id") != submission.id:
        return False
    report_done = (
        db.query(InterviewReport.id)
        .filter(InterviewReport.session_id == submission.session_id, InterviewReport.status == InterviewAIStatus.COMPLETED)
        .first()
    )
    if report_done:
        return False
    evaluation = dict(answer.evaluation or {})
    combined = coding_score_of(submission)
    evaluation["review_status"] = submission.ai_review_status
    evaluation["quality_score"] = submission.ai_quality_score if combined is not None else None
    evaluation["coding_score"] = combined
    answer.evaluation = evaluation
    # The answer score is the combined score once it exists; until then, correctness only.
    answer.score = code_review.round_half_up(combined if combined is not None else (submission.correctness_score or 0))
    db.commit()
    return True


async def settle_pending_reviews(db: Session, session_id: str, wait_seconds: Optional[float] = None) -> None:
    """Before a report: run unstarted reviews of recorded answers, and wait (bounded) for running ones."""
    import asyncio

    wait_seconds = REPORT_REVIEW_WAIT_SECONDS if wait_seconds is None else wait_seconds
    answered_ids = {
        (a.evaluation or {}).get("submission_id")
        for a in db.query(InterviewAnswer).filter(InterviewAnswer.session_id == session_id).all()
    }
    answered_ids.discard(None)
    if not answered_ids:
        return
    deadline = asyncio.get_running_loop().time() + wait_seconds
    while True:
        db.expire_all()
        for row in db.query(CodingSubmission).filter(CodingSubmission.id.in_(answered_ids)).all():
            if row.ai_review_status == REVIEW_PENDING:
                await run_review(db, row.id)
        db.expire_all()
        running = [
            r for r in db.query(CodingSubmission).filter(CodingSubmission.id.in_(answered_ids)).all()
            if r.ai_review_status in (REVIEW_PENDING, REVIEW_RUNNING)
        ]
        if not running or asyncio.get_running_loop().time() >= deadline:
            return
        await asyncio.sleep(1.0)


async def retry_review(db: Session, user: User, interview_id: str, submission_id: str) -> SubmissionOut:
    submission = _owned_submission(db, user, interview_id, submission_id)
    if submission.submission_type != "SUBMIT" or submission.ai_review_status is None:
        raise _error(status.HTTP_409_CONFLICT, "Only completed submissions get an AI code review.", status="NOT_REVIEWABLE")
    if submission.ai_review_status in (REVIEW_FAILED, REVIEW_PENDING):
        if submission.ai_review_attempts >= REVIEW_MAX_ATTEMPTS:
            raise _error(status.HTTP_409_CONFLICT, "The retry limit for this code review has been reached.", status="RETRY_LIMIT")
        await run_review(db, submission.id)
    db.expire_all()
    submission = db.get(CodingSubmission, submission_id)
    return serialize(submission, db.get(CodingProblem, submission.problem_id))


def record_interview_answer(db: Session, submission: CodingSubmission) -> bool:
    """
    A completed SUBMIT is the candidate's answer to its coding/SQL question: the latest
    completed submission is recorded (a newer one replaces an older one; RUN never counts).
    The score is the backend's weighted test correctness from Judge0 — no model involved.
    Once the final report is completed, answers are frozen. Returns True if recorded.
    """
    if submission.submission_type != "SUBMIT" or submission.status != STATUS_COMPLETED:
        return False
    report_done = (
        db.query(InterviewReport.id)
        .filter(InterviewReport.session_id == submission.session_id, InterviewReport.status == InterviewAIStatus.COMPLETED)
        .first()
    )
    if report_done:
        logger.info("[Coding] submission %s finished after the report was completed; not recorded", submission.id)
        return False
    answer = db.query(InterviewAnswer).filter(InterviewAnswer.question_id == submission.question_id).first()
    previous = (answer.evaluation or {}) if answer is not None else {}
    if previous.get("submission_created_at") and previous["submission_created_at"] > submission.created_at.isoformat():
        return False  # an older submission finishing late never replaces a newer one
    passed, total = submission.tests_passed or 0, submission.tests_total or 0
    score = int(round(submission.correctness_score or 0))
    verdict_label = verdicts.VERDICT_LABELS.get(submission.verdict, submission.verdict) if submission.verdict else "No verdict"
    evaluation = {
        "score": score,
        "method": "judge0",
        "label": EXECUTED_ANSWER_LABEL,
        "verdict": submission.verdict,
        "verdict_label": verdict_label,
        "correct": passed,
        "total": total,
        "language": submission.language,
        "language_label": submission.language_label,
        "submission_id": submission.id,
        "submission_created_at": submission.created_at.isoformat(),
        # Correctness (Judge0) and code quality (AI review) are kept separate; the combined
        # score exists only once the review has completed (see apply_review_to_answer).
        "correctness_score": submission.correctness_score,
        "review_status": submission.ai_review_status,
        "quality_score": None,
        "coding_score": None,
        "strengths": [],
        "improvements": [],
        "feedback": f"{verdict_label}: {passed} of {total} tests passed ({submission.language_label}).",
        "key_points": [],
    }
    now = interview_service.utcnow()
    if answer is None:
        answer = InterviewAnswer(
            session_id=submission.session_id,
            question_id=submission.question_id,
            answer_source=InterviewMode.TEXT,
            evaluation_attempts=0,
        )
        db.add(answer)
    answer.answer_text = submission.source_code
    answer.submitted_at = submission.created_at
    answer.evaluation_status = InterviewAIStatus.COMPLETED
    answer.score = score
    answer.evaluation = evaluation
    answer.evaluated_at = now
    try:
        db.commit()
    except IntegrityError:  # a concurrent finalisation created the row first; retry as an update
        db.rollback()
        return record_interview_answer(db, submission)
    if submission.ai_review_status == REVIEW_COMPLETED:  # review finished before the answer was recorded
        apply_review_to_answer(db, submission)
    return True


async def settle_pending_submissions(db: Session, session_id: str, wait_seconds: float = 15.0) -> None:
    """Before a report is computed, finish SUBMITs accepted before the deadline that are still running."""
    pending = (
        db.query(CodingSubmission)
        .filter(
            CodingSubmission.session_id == session_id,
            CodingSubmission.submission_type == "SUBMIT",
            CodingSubmission.status.in_([STATUS_QUEUED, STATUS_RUNNING]),
        )
        .all()
    )
    for submission in pending:
        problem = db.get(CodingProblem, submission.problem_id)
        try:
            await _advance(db, submission, problem, wait_seconds=wait_seconds)
        except Exception:  # noqa: BLE001 — Judge0 down: the submission stays pending and unscored
            logger.warning("[Coding] could not settle submission %s before the report", submission.id)


async def _advance(db: Session, submission: CodingSubmission, problem: CodingProblem, wait_seconds: float) -> None:
    """Poll Judge0 for a RUNNING submission and finalize it when every execution finished."""
    if submission.status != STATUS_RUNNING or not submission.judge_tokens:
        return
    client = _client()
    try:
        results = await client.wait([t["token"] for t in submission.judge_tokens], wait_seconds)
    except Judge0Error as exc:
        logger.warning("[Coding] polling %s failed (%s); will resume on the next poll", submission.id, exc.kind)
        return  # tokens are stored; nothing is lost
    if all(r.finished for r in results):
        _finalize(db, submission, problem, results)


async def _start(
    db: Session,
    user: User,
    interview_id: str,
    question_id: str,
    *,
    submission_type: str,
    language: str,
    source_code: str,
    custom_input: Optional[str],
    idempotency_key: Optional[str],
) -> SubmissionOut:
    session, question, problem = _owned_coding_question(db, user, interview_id, question_id)
    now = interview_service.utcnow()
    if session.status != InterviewStatus.IN_PROGRESS or now > interview_service._aware(session.deadline_at) + interview_service._grace():
        raise _error(status.HTTP_409_CONFLICT, "This interview has ended, so code can no longer be run or submitted.", status="ENDED")
    if problem.verified_at is None:
        raise _error(status.HTTP_409_CONFLICT, "This problem has not been verified yet.", status="UNVERIFIED")
    if language not in allowed_languages(question, problem):
        raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "This language is not available for this problem.")
    try:
        harness.validate_source(language, source_code)
        harness.validate_custom_input(language, custom_input)
        if custom_input is not None and (problem.harness or {}).get("type") == "bash_workspace":
            harness.parse_workspace_input(custom_input)
    except harness.HarnessError as exc:
        raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))

    key = idempotency_key or f"run-{uuid.uuid4().hex}"
    fingerprint = _source_fingerprint(language, source_code, custom_input)

    existing = (
        db.query(CodingSubmission)
        .filter(CodingSubmission.user_id == user.id, CodingSubmission.idempotency_key == key)
        .first()
    )
    if existing is not None:
        return await _resume_duplicate(db, existing, problem, question_id, submission_type, fingerprint)

    if submission_type == "SUBMIT":
        counted = (
            db.query(CodingSubmission)
            .filter(
                CodingSubmission.question_id == question.id,
                CodingSubmission.submission_type == "SUBMIT",
                CodingSubmission.status != STATUS_FAILED,
                (CodingSubmission.verdict.is_(None)) | (CodingSubmission.verdict != verdicts.JUDGE_ERROR),
            )
            .count()
        )
        if counted >= settings.CODING_MAX_SUBMISSIONS_PER_QUESTION:
            raise _error(status.HTTP_429_TOO_MANY_REQUESTS, "The submission limit for this question has been reached.", status="SUBMISSION_LIMIT")

    _rate_limit(user, submission_type)
    submission = CodingSubmission(
        user_id=user.id,
        session_id=session.id,
        question_id=question.id,
        problem_id=problem.id,
        submission_type=submission_type,
        language=language,
        language_label=LANGUAGE_BY_KEY[language].fallback_label,
        source_code=source_code,
        custom_input=custom_input,
        idempotency_key=key,
        status=STATUS_QUEUED,
    )
    db.add(submission)
    try:
        db.commit()  # the unique (user, idempotency_key) constraint resolves concurrent duplicates here
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(CodingSubmission)
            .filter(CodingSubmission.user_id == user.id, CodingSubmission.idempotency_key == key)
            .first()
        )
        return await _resume_duplicate(db, existing, problem, question_id, submission_type, fingerprint)

    try:
        _acquire_inflight(user, submission.id)
    except HTTPException:
        db.delete(submission)
        db.commit()
        raise
    return await _run_submission(db, submission, problem)


def _fingerprint_of(submission: CodingSubmission) -> str:
    """Recomputed from the stored row, so duplicate detection works across processes."""
    return _source_fingerprint(submission.language, submission.source_code, submission.custom_input)


async def _resume_duplicate(
    db: Session, existing: CodingSubmission, problem: CodingProblem, question_id: str, submission_type: str, fingerprint: str
) -> SubmissionOut:
    if existing.question_id != question_id or existing.submission_type != submission_type or _fingerprint_of(existing) != fingerprint:
        raise _error(status.HTTP_409_CONFLICT, "This idempotency key was already used for a different request.", status="IDEMPOTENCY_CONFLICT")
    if existing.status == STATUS_FAILED and not existing.judge_tokens:
        # Never reached Judge0 (e.g. it was unavailable): the same request may be retried.
        existing.status, existing.error = STATUS_QUEUED, None
        db.commit()
        try:
            _acquire_inflight(db.get(User, existing.user_id), existing.id)
        except HTTPException:
            existing.status = STATUS_FAILED
            db.commit()
            raise
        return await _run_submission(db, existing, problem)
    await _advance(db, existing, problem, wait_seconds=0)
    return serialize(existing, problem)


async def _run_submission(db: Session, submission: CodingSubmission, problem: CodingProblem) -> SubmissionOut:
    try:
        await _execute(db, submission, problem)
    except (Judge0Error, HTTPException) as exc:
        submission.status = STATUS_FAILED
        submission.error = "The code execution service is temporarily unavailable. Please try again."
        db.commit()
        _release_inflight(submission.user_id, submission.id)
        kind = getattr(exc, "kind", "unavailable")
        logger.warning("[Coding] %s %s could not be queued (%s)", submission.submission_type, submission.id, kind)
        raise _error(status.HTTP_503_SERVICE_UNAVAILABLE, submission.error, stage="judge0_unavailable", submission_id=submission.id)
    await _advance(db, submission, problem, wait_seconds=settings.JUDGE0_INLINE_WAIT_SECONDS)
    db.refresh(submission)
    return serialize(submission, problem)


async def run_code(db: Session, user: User, interview_id: str, question_id: str, payload: RunCodeRequest) -> SubmissionOut:
    return await _start(
        db, user, interview_id, question_id,
        submission_type="RUN", language=payload.language, source_code=payload.source_code,
        custom_input=payload.custom_input, idempotency_key=payload.idempotency_key,
    )


async def submit_solution(db: Session, user: User, interview_id: str, question_id: str, payload: SubmitSolutionRequest) -> SubmissionOut:
    return await _start(
        db, user, interview_id, question_id,
        submission_type="SUBMIT", language=payload.language, source_code=payload.source_code,
        custom_input=None, idempotency_key=payload.idempotency_key,
    )


def _owned_submission(db: Session, user: User, interview_id: str, submission_id: str) -> CodingSubmission:
    interview_service._get_owned_session(db, user, interview_id)
    submission = (
        db.query(CodingSubmission)
        .filter(CodingSubmission.id == submission_id, CodingSubmission.session_id == interview_id, CodingSubmission.user_id == user.id)
        .first()
    )
    if submission is None:
        raise _error(status.HTTP_404_NOT_FOUND, "Submission not found.")
    return submission


async def get_submission(db: Session, user: User, interview_id: str, submission_id: str) -> SubmissionOut:
    """Return a submission, resuming polling (from stored tokens) if it is still running."""
    submission = _owned_submission(db, user, interview_id, submission_id)
    problem = db.get(CodingProblem, submission.problem_id)
    await _advance(db, submission, problem, wait_seconds=2.0)
    db.refresh(submission)
    return serialize(submission, problem)


def list_submissions(db: Session, user: User, interview_id: str, question_id: str) -> SubmissionListResponse:
    _, question, problem = _owned_coding_question(db, user, interview_id, question_id)
    rows = (
        db.query(CodingSubmission)
        .filter(CodingSubmission.question_id == question.id, CodingSubmission.user_id == user.id)
        .order_by(CodingSubmission.created_at.desc())
        .limit(50)
        .all()
    )
    return SubmissionListResponse(submissions=[serialize(r, problem) for r in rows])


# ---------------------------------------------------------------------------
# Serialization (the only place results leave the backend)
# ---------------------------------------------------------------------------


def serialize(submission: CodingSubmission, problem: CodingProblem) -> SubmissionOut:
    tests_by_id = {t.id: t for t in problem.test_cases}
    results = []
    for record in submission.results or []:
        label = verdicts.VERDICT_LABELS.get(record["verdict"], record["verdict"])
        if record["kind"] == "hidden":
            results.append(
                HiddenTestResult(
                    ordinal=record["ordinal"], verdict=record["verdict"], verdict_label=label, passed=bool(record["passed"]),
                    time=record.get("time"), memory=record.get("memory"), judge0_status=record.get("judge0_status", ""),
                )
            )
            continue
        test = tests_by_id.get(record.get("test_id"))
        if record["kind"] == "sample" and (test is None or test.is_hidden):
            continue  # defensive: never describe a test that is (now) hidden
        results.append(
            VisibleTestResult(
                ordinal=record["ordinal"],
                kind=record["kind"],
                verdict=record["verdict"],
                verdict_label=label,
                passed=record.get("passed"),
                time=record.get("time"),
                memory=record.get("memory"),
                judge0_status=record.get("judge0_status", ""),
                input=(submission.custom_input or "") if record["kind"] == "custom" else test.input,
                expected_output=None if record["kind"] == "custom" else test.expected_output,
                stdout=record.get("stdout", ""),
                stderr=record.get("stderr", ""),
                reason=record.get("reason", ""),
            )
        )
    return SubmissionOut(
        id=submission.id,
        question_id=submission.question_id,
        submission_type=submission.submission_type,
        language=submission.language,
        language_label=submission.language_label,
        status=submission.status,
        verdict=submission.verdict,
        verdict_label=verdicts.VERDICT_LABELS.get(submission.verdict) if submission.verdict else None,
        tests_passed=submission.tests_passed,
        tests_total=submission.tests_total,
        correctness_score=submission.correctness_score,
        max_time_seconds=submission.max_time_seconds,
        max_memory_kb=submission.max_memory_kb,
        compile_output=submission.compile_output,
        error=submission.error,
        created_at=submission.created_at,
        completed_at=submission.completed_at,
        results=results,
        ai_review=review_out(submission),
        coding_score=coding_score_of(submission),
    )


# ---------------------------------------------------------------------------
# Problem verification (reference solutions must pass every test)
# ---------------------------------------------------------------------------


async def _run_against_tests(client: Judge0Client, resolved: dict, problem: CodingProblem, language: str, source: str,
                             max_wait_seconds: float) -> verdicts.SubmissionSummary:
    lang = LANGUAGE_BY_KEY[language]
    limits = execution_limits(problem, language)
    tests = list(problem.test_cases)
    requests = []
    for t in tests:
        program = harness.build_program(language, source, t.input, problem.harness)
        requests.append(
            ExecutionRequest(
                language_id=resolved[language]["judge0_id"], source_code=program.source_code, stdin=program.stdin,
                compiler_options=lang.compiler_options, **limits,
            )
        )
    tokens = await client.submit_batch(requests)
    results = await client.wait(tokens, max_wait_seconds)
    outcomes = [
        verdicts.evaluate_test(
            r, ordinal=t.ordinal, stdin=t.input, expected=t.expected_output, checker=problem.checker,
            memory_limit_kb=limits["memory_limit_kb"], weight=t.weight, required=t.is_required, hidden=t.is_hidden,
        )
        for r, t in zip(results, tests)
    ]
    return verdicts.summarise(outcomes)


async def verify_problem(
    db: Session,
    problem: CodingProblem,
    max_wait_seconds: float = 120.0,
    *,
    wrong_solutions: tuple = (),
    check_starters: bool = False,
) -> dict:
    """
    Verify a problem on real Judge0 before it is published (verified_at set):

    * every reference solution is Accepted on every test, so independent implementations
      agree with the stored expected outputs and the configured checker;
    * every known-wrong solution (language, source, note) is rejected with a genuine
      verdict (not a judge error), so the tests actually catch wrong answers;
    * with check_starters, every starter template runs to Wrong Answer: it compiles and
      executes, and does not already pass.
    """
    client = _client()
    resolved = await resolve_languages(client)
    tests = list(problem.test_cases)
    if not tests or not any(t.is_hidden for t in tests) or not any(not t.is_hidden for t in tests):
        raise ValueError("A problem needs at least one sample test and one hidden test.")
    report: dict = {}
    for language, source in (problem.reference_solutions or {}).items():
        if language not in LANGUAGE_BY_KEY or language not in problem.languages:
            raise ValueError(f"Reference solution language {language} is not enabled for this problem.")
        summary = await _run_against_tests(client, resolved, problem, language, source, max_wait_seconds)
        report[language] = {
            "label": resolved[language]["label"],
            "verdict": summary.verdict,
            "passed": summary.tests_passed,
            "total": summary.tests_total,
            "max_time": summary.max_time,
            "max_memory": summary.max_memory,
        }
    if not report:
        raise ValueError("A problem needs at least one reference solution.")

    wrong_report = []
    for language, source, note in wrong_solutions:
        summary = await _run_against_tests(client, resolved, problem, language, source, max_wait_seconds)
        detected = summary.verdict not in (verdicts.ACCEPTED, verdicts.JUDGE_ERROR)
        wrong_report.append({"language": language, "note": note, "verdict": summary.verdict,
                             "passed": summary.tests_passed, "total": summary.tests_total, "detected": detected})

    starter_report = {}
    if check_starters:
        for language, source in (problem.starter_code or {}).items():
            summary = await _run_against_tests(client, resolved, problem, language, source, max_wait_seconds)
            starter_report[language] = {"verdict": summary.verdict, "ok": summary.verdict == verdicts.WRONG_ANSWER}

    verified = (
        all(r["verdict"] == verdicts.ACCEPTED for r in report.values())
        and all(w["detected"] for w in wrong_report)
        and all(st["ok"] for st in starter_report.values())
    )
    problem.verification = {
        "verified": verified,
        "languages": report,
        "wrong_solutions": wrong_report,
        "starters": starter_report,
        "at": interview_service.utcnow().isoformat(),
    }
    problem.verified_at = interview_service.utcnow() if verified else None
    db.commit()
    return problem.verification
