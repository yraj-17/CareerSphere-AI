"""
AI Interviewer V1 — session lifecycle.

Lifecycle
---------
IN_PROGRESS ──► COMPLETED  user ended the interview before the deadline with ≥1 answer
            ├─► EXPIRED    deadline passed (detected lazily on any access, or ended after the deadline)
            └─► ABANDONED  user ended the interview without submitting any answer
All three end states are terminal; no transition leaves them.

Time policy (server-authoritative)
----------------------------------
* started_at/deadline_at are set by the server when the session is created.
* New questions are only issued before deadline_at.
* Answers are accepted until deadline_at + INTERVIEW_SUBMISSION_GRACE_SECONDS
  (covers request latency); later submissions are rejected with 409.
* When the deadline (+grace) passes, the session becomes EXPIRED. Already
  accepted answers are kept. An unanswered question is shown as "not answered"
  and excluded from scoring. A report is produced from the saved answers.

Reliability
-----------
* Answers are committed (evaluation PENDING) before the model is called.
* An evaluation/report is claimed with an atomic conditional UPDATE so retries
  and double clicks never run duplicate model calls for the same artifact.
* Only COMPLETED evaluations carry a score; a failed evaluation never invents one.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, or_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.models import (
    InterviewAIStatus,
    InterviewAnswer,
    InterviewDifficulty,
    InterviewMode,
    InterviewQuestion,
    InterviewReport,
    InterviewSession,
    InterviewStatus,
    InterviewType,
    Profile,
    User,
)
from app.schemas.interviews import (
    DEFAULT_DURATION_MINUTES,
    DIFFICULTIES,
    DURATION_QUESTION_LIMITS,
    INTERACTION_MODES,
    INTERVIEW_TYPES,
    MAX_ANSWER_LENGTH,
    MAX_FOCUS_AREAS,
    AnswerSubmitResponse,
    InterviewAnswerOut,
    InterviewAnswerSubmitRequest,
    InterviewCreateRequest,
    InterviewListResponse,
    InterviewOptionsResponse,
    InterviewQuestionOut,
    InterviewReportOut,
    InterviewSessionOut,
    InterviewSessionSummary,
    InterviewSuggestionsResponse,
)
from app.services import interview_ai_service as ai
from app.services import interview_scoring as scoring
from app.services import transcription_service

logger = logging.getLogger(__name__)

MAX_EVALUATION_ATTEMPTS = 3
MAX_REPORT_ATTEMPTS = 5
TERMINAL_STATUSES = {InterviewStatus.COMPLETED, InterviewStatus.EXPIRED, InterviewStatus.ABANDONED}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _grace() -> timedelta:
    return timedelta(seconds=max(0, settings.INTERVIEW_SUBMISSION_GRACE_SECONDS))


def _stale_after() -> timedelta:
    """A PENDING claim older than this is treated as abandoned (e.g. server restart mid-call)."""
    return timedelta(seconds=settings.OLLAMA_INTERVIEW_TIMEOUT_SECONDS * ai.MAX_ATTEMPTS + 60)


def _error(code: int, message: str, **extra) -> HTTPException:
    if extra:
        return HTTPException(status_code=code, detail={"message": message, **extra})
    return HTTPException(status_code=code, detail=message)


def category_for(interview_type: InterviewType, question_order: int) -> str:
    """Server-decided question category. MIXED alternates, starting with technical."""
    if interview_type == InterviewType.MIXED:
        return "TECHNICAL" if question_order % 2 == 1 else "BEHAVIORAL"
    return interview_type.value


# ---------------------------------------------------------------------------
# Loading, ownership, expiry
# ---------------------------------------------------------------------------


def _session_query(db: Session):
    return db.query(InterviewSession).options(
        selectinload(InterviewSession.questions).selectinload(InterviewQuestion.answer),
        selectinload(InterviewSession.report),
    )


def _get_owned_session(db: Session, user: User, interview_id: str) -> InterviewSession:
    """Ownership is part of the query: another user's interview is indistinguishable from a missing one."""
    session = (
        _session_query(db)
        .filter(InterviewSession.id == interview_id, InterviewSession.user_id == user.id)
        .first()
    )
    if session is None:
        raise _error(status.HTTP_404_NOT_FOUND, "Interview not found.")
    _refresh_expiry(db, session)
    return session


def _answered(session: InterviewSession) -> list[InterviewQuestion]:
    return [q for q in session.questions if q.answer is not None]


def _ensure_report_row(db: Session, session: InterviewSession) -> None:
    if session.report is None and _answered(session):
        session.report = InterviewReport(session_id=session.id, status=InterviewAIStatus.PENDING, attempts=0)
        db.add(session.report)


def _end_session(db: Session, session: InterviewSession, new_status: InterviewStatus, now: datetime) -> None:
    if session.status != InterviewStatus.IN_PROGRESS:
        raise _error(status.HTTP_409_CONFLICT, "This interview has already ended.")
    session.status = new_status
    session.completed_at = min(now, _aware(session.deadline_at))
    _ensure_report_row(db, session)


def _refresh_expiry(db: Session, session: InterviewSession, now: Optional[datetime] = None) -> None:
    now = now or utcnow()
    if session.status == InterviewStatus.IN_PROGRESS and now > _aware(session.deadline_at) + _grace():
        _end_session(db, session, InterviewStatus.EXPIRED, now)
        db.commit()


def _current_question(session: InterviewSession) -> Optional[InterviewQuestion]:
    for question in reversed(session.questions):
        if question.answer is None:
            return question
    return None


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def _answer_out(answer: InterviewAnswer, report_completed: bool) -> InterviewAnswerOut:
    can_retry = (
        answer.evaluation_status == InterviewAIStatus.FAILED
        and answer.evaluation_attempts < MAX_EVALUATION_ATTEMPTS
        and not report_completed
    )
    evaluation = answer.evaluation if answer.evaluation_status == InterviewAIStatus.COMPLETED else None
    return InterviewAnswerOut(
        id=answer.id,
        question_id=answer.question_id,
        answer_text=answer.answer_text,
        answer_source=answer.answer_source.value,
        submitted_at=answer.submitted_at,
        evaluation_status=answer.evaluation_status.value,
        score=answer.score if evaluation else None,
        evaluation=evaluation,
        can_retry_evaluation=can_retry,
    )


def _question_out(question: InterviewQuestion, report_completed: bool) -> InterviewQuestionOut:
    return InterviewQuestionOut(
        id=question.id,
        question_order=question.question_order,
        question_text=question.question_text,
        category=question.category,
        competency=question.competency,
        difficulty=question.difficulty.value,
        interviewer_context=question.interviewer_context,
        created_at=question.created_at,
        answer=_answer_out(question.answer, report_completed) if question.answer else None,
    )


def _summary_fields(session: InterviewSession) -> dict:
    return dict(
        id=session.id,
        target_role=session.target_role,
        interview_type=session.interview_type.value,
        interaction_mode=session.interaction_mode.value,
        difficulty=session.difficulty.value,
        duration_minutes=session.duration_minutes,
        status=session.status.value,
        started_at=session.started_at,
        deadline_at=session.deadline_at,
        completed_at=session.completed_at,
        final_score=session.final_score,
        question_count=len(session.questions),
        answered_count=len(_answered(session)),
        report_status=session.report.status.value if session.report else None,
    )


def serialize_session(session: InterviewSession, now: Optional[datetime] = None) -> InterviewSessionOut:
    now = now or utcnow()
    report_completed = bool(session.report and session.report.status == InterviewAIStatus.COMPLETED)
    in_progress = session.status == InterviewStatus.IN_PROGRESS
    remaining = max(0, int((_aware(session.deadline_at) - now).total_seconds())) if in_progress else 0
    current = _current_question(session) if in_progress else None
    can_next = (
        in_progress
        and current is None
        and remaining > 0
        and len(session.questions) < session.max_questions
    )
    return InterviewSessionOut(
        **_summary_fields(session),
        focus_areas=list(session.focus_areas or []),
        instructions=session.instructions,
        max_questions=session.max_questions,
        server_time=now,
        remaining_seconds=remaining,
        current_question=_question_out(current, report_completed) if current else None,
        can_request_next_question=can_next,
        questions=[_question_out(q, report_completed) for q in session.questions],
    )


def serialize_report(session: InterviewSession) -> InterviewReportOut:
    report = session.report
    return InterviewReportOut(
        interview_id=session.id,
        status=report.status.value,
        overall_score=report.overall_score,
        aggregates=report.aggregates,
        narrative=report.narrative if report.status == InterviewAIStatus.COMPLETED else None,
        generated_at=report.generated_at,
        can_retry=report.status != InterviewAIStatus.COMPLETED and report.attempts < MAX_REPORT_ATTEMPTS,
    )


# ---------------------------------------------------------------------------
# Options and profile suggestions
# ---------------------------------------------------------------------------


def get_options() -> InterviewOptionsResponse:
    return InterviewOptionsResponse(
        interview_types=list(INTERVIEW_TYPES),
        interaction_modes=list(INTERACTION_MODES),
        difficulties=list(DIFFICULTIES),
        durations=list(DURATION_QUESTION_LIMITS),
        default_duration_minutes=DEFAULT_DURATION_MINUTES,
        max_answer_length=MAX_ANSWER_LENGTH,
        max_focus_areas=MAX_FOCUS_AREAS,
        transcription_available=transcription_service.is_available(),
        max_audio_seconds=settings.INTERVIEW_MAX_AUDIO_SECONDS,
        max_audio_bytes=settings.INTERVIEW_MAX_AUDIO_BYTES,
    )


def _load_profile(db: Session, user: User) -> Optional[Profile]:
    return (
        db.query(Profile)
        .options(
            selectinload(Profile.skills),
            selectinload(Profile.experience),
            selectinload(Profile.career_preferences),
        )
        .filter(Profile.user_id == user.id)
        .first()
    )


def get_suggestions(db: Session, user: User) -> InterviewSuggestionsResponse:
    """Suggestions come only from data the user saved in their profile — nothing is inferred."""
    profile = _load_profile(db, user)
    if profile is None:
        return InterviewSuggestionsResponse(target_role=None, skills=[], has_profile=False)
    role = None
    if profile.career_preferences and profile.career_preferences.target_job_role:
        role = profile.career_preferences.target_job_role.strip()[:120] or None
    if not role and profile.experience:
        role = profile.experience[0].job_title.strip()[:120] or None
    skills = [skill.name for skill in profile.skills][:12]
    return InterviewSuggestionsResponse(target_role=role, skills=skills, has_profile=True)


def _profile_summary(db: Session, user: User) -> Optional[str]:
    """Compact, non-identifying profile context for question generation."""
    profile = _load_profile(db, user)
    if profile is None:
        return None
    lines = []
    if profile.headline:
        lines.append(f"Headline: {profile.headline}")
    if profile.skills:
        lines.append("Listed skills: " + ", ".join(s.name for s in profile.skills[:15]))
    titles = [f"{e.job_title} at {e.company}" for e in profile.experience[:3]]
    if titles:
        lines.append("Listed experience: " + "; ".join(titles))
    return "\n".join(lines)[:1200] or None


# ---------------------------------------------------------------------------
# Create / list / get
# ---------------------------------------------------------------------------


def _active_session_id(db: Session, user: User) -> Optional[str]:
    active = (
        _session_query(db)
        .filter(InterviewSession.user_id == user.id, InterviewSession.status == InterviewStatus.IN_PROGRESS)
        .all()
    )
    for session in active:
        _refresh_expiry(db, session)
    for session in active:
        if session.status == InterviewStatus.IN_PROGRESS:
            return session.id
    return None


async def _generate_question(db: Session, user: User, session_like: dict, order: int, previous: list[str]):
    category = category_for(session_like["interview_type"], order)
    try:
        generated = await ai.generate_question(
            role=session_like["target_role"],
            category=category,
            difficulty=session_like["difficulty"].value,
            question_number=order,
            max_questions=session_like["max_questions"],
            focus_areas=session_like["focus_areas"],
            instructions=session_like["instructions"],
            profile_summary=_profile_summary(db, user),
            previous_questions=previous,
        )
    except ai.InterviewAIError:
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The AI interviewer couldn't prepare a question right now. Please try again.",
            stage="generation",
        )
    return category, generated


async def create_interview(db: Session, user: User, payload: InterviewCreateRequest) -> InterviewSessionOut:
    if payload.interaction_mode == "VOICE" and not transcription_service.is_available():
        raise _error(
            status.HTTP_400_BAD_REQUEST,
            "Voice interviews are unavailable because speech transcription is not configured. Choose a text interview.",
        )

    existing = _active_session_id(db, user)
    if existing:
        raise _error(
            status.HTTP_409_CONFLICT,
            "You already have an interview in progress. Resume or end it before starting another.",
            interview_id=existing,
        )

    config = dict(
        target_role=payload.target_role,
        interview_type=InterviewType(payload.interview_type),
        difficulty=InterviewDifficulty(payload.difficulty),
        max_questions=DURATION_QUESTION_LIMITS[payload.duration_minutes],
        focus_areas=payload.focus_areas,
        instructions=payload.instructions,
    )
    # Generate the first question before persisting anything, so a model failure
    # never leaves behind a session whose clock is already running.
    category, generated = await _generate_question(db, user, config, 1, [])

    # Serialize concurrent creates for the same user, then re-check.
    db.query(User).filter(User.id == user.id).with_for_update().first()
    existing = _active_session_id(db, user)
    if existing:
        db.rollback()
        raise _error(
            status.HTTP_409_CONFLICT,
            "You already have an interview in progress. Resume or end it before starting another.",
            interview_id=existing,
        )

    now = utcnow()
    session = InterviewSession(
        user_id=user.id,
        interaction_mode=InterviewMode(payload.interaction_mode),
        duration_minutes=payload.duration_minutes,
        status=InterviewStatus.IN_PROGRESS,
        started_at=now,
        deadline_at=now + timedelta(minutes=payload.duration_minutes),
        **config,
    )
    db.add(session)
    db.flush()
    db.add(
        InterviewQuestion(
            session_id=session.id,
            question_order=1,
            question_text=generated.question_text,
            category=category,
            competency=generated.competency,
            difficulty=session.difficulty,
            interviewer_context=generated.interviewer_context,
        )
    )
    db.commit()
    return get_interview(db, user, session.id)


def list_interviews(db: Session, user: User, limit: int, offset: int) -> InterviewListResponse:
    _active_session_id(db, user)  # applies lazy expiry before listing
    base = db.query(InterviewSession).filter(InterviewSession.user_id == user.id)
    total = base.with_entities(func.count(InterviewSession.id)).scalar() or 0
    sessions = (
        _session_query(db)
        .filter(InterviewSession.user_id == user.id)
        .order_by(InterviewSession.created_at.desc(), InterviewSession.id.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return InterviewListResponse(
        total=total,
        limit=limit,
        offset=offset,
        interviews=[InterviewSessionSummary(**_summary_fields(s)) for s in sessions],
    )


def get_interview(db: Session, user: User, interview_id: str) -> InterviewSessionOut:
    db.expire_all()
    return serialize_session(_get_owned_session(db, user, interview_id))


def get_current_question(db: Session, user: User, interview_id: str) -> Optional[InterviewQuestionOut]:
    session = _get_owned_session(db, user, interview_id)
    if session.status != InterviewStatus.IN_PROGRESS:
        return None
    current = _current_question(session)
    return _question_out(current, False) if current else None


# ---------------------------------------------------------------------------
# Next question
# ---------------------------------------------------------------------------


def _require_in_progress(session: InterviewSession) -> None:
    if session.status != InterviewStatus.IN_PROGRESS:
        raise _error(
            status.HTTP_409_CONFLICT,
            "This interview has ended.",
            status=session.status.value,
        )


async def request_next_question(db: Session, user: User, interview_id: str) -> InterviewSessionOut:
    """Idempotent: returns the existing unanswered question if there is one."""
    session = _get_owned_session(db, user, interview_id)
    _require_in_progress(session)
    if _current_question(session) is not None:
        return serialize_session(session)
    if utcnow() >= _aware(session.deadline_at):
        raise _error(status.HTTP_409_CONFLICT, "Time is up. No more questions can be asked.", status="TIME_UP")
    if len(session.questions) >= session.max_questions:
        raise _error(status.HTTP_409_CONFLICT, "All questions for this interview have been asked.", status="LIMIT_REACHED")

    order = len(session.questions) + 1
    config = dict(
        target_role=session.target_role,
        interview_type=session.interview_type,
        difficulty=session.difficulty,
        max_questions=session.max_questions,
        focus_areas=list(session.focus_areas or []),
        instructions=session.instructions,
    )
    previous = [q.question_text for q in session.questions]
    category, generated = await _generate_question(db, user, config, order, previous)

    # Re-read: the interview may have ended or another request may have added a question meanwhile.
    db.expire_all()
    session = _get_owned_session(db, user, interview_id)
    _require_in_progress(session)
    if len(session.questions) >= order:
        return serialize_session(session)
    db.add(
        InterviewQuestion(
            session_id=session.id,
            question_order=order,
            question_text=generated.question_text,
            category=category,
            competency=generated.competency,
            difficulty=session.difficulty,
            interviewer_context=generated.interviewer_context,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    return get_interview(db, user, interview_id)


# ---------------------------------------------------------------------------
# Answers and evaluation
# ---------------------------------------------------------------------------


_CLAIM_COLUMNS = {
    InterviewAnswer: ("evaluation_status", "evaluation_attempts", MAX_EVALUATION_ATTEMPTS),
    InterviewReport: ("status", "attempts", MAX_REPORT_ATTEMPTS),
}


def _claim(db: Session, model, row_id: str, allow_fresh_pending: bool) -> bool:
    """
    Atomically move a row into an in-flight PENDING claim and count the attempt.

    Claimable: FAILED rows, PENDING rows abandoned longer than the stale window,
    and (when allow_fresh_pending) never-attempted PENDING rows. Returns False if
    another request holds the claim or the attempt budget is exhausted.
    """
    status_name, attempts_name, max_attempts = _CLAIM_COLUMNS[model]
    status_col = getattr(model, status_name)
    attempts_col = getattr(model, attempts_name)
    claimable = [
        status_col == InterviewAIStatus.FAILED,
        (status_col == InterviewAIStatus.PENDING) & (model.updated_at < utcnow() - _stale_after()),
    ]
    if allow_fresh_pending:
        claimable.append((status_col == InterviewAIStatus.PENDING) & (attempts_col == 0))
    result = db.execute(
        update(model)
        .where(model.id == row_id, attempts_col < max_attempts, or_(*claimable))
        .values({attempts_name: attempts_col + 1, status_name: InterviewAIStatus.PENDING, "updated_at": utcnow()})
        .execution_options(synchronize_session=False)
    )
    db.commit()
    return result.rowcount == 1


async def _run_evaluation(db: Session, session: InterviewSession, answer_id: str) -> None:
    """Evaluate one claimed answer and persist the outcome. Never raises for model failures."""
    answer = db.get(InterviewAnswer, answer_id)
    question = answer.question
    try:
        result = await ai.evaluate_answer(
            role=session.target_role,
            category=question.category,
            difficulty=question.difficulty.value,
            question_text=question.question_text,
            competency=question.competency,
            answer_text=answer.answer_text,
        )
    except ai.InterviewAIError:
        db.refresh(answer)
        answer.evaluation_status = InterviewAIStatus.FAILED
        db.commit()
        return

    dims = {name: getattr(result, name) for name in scoring.applicable_dimensions(question.category)}
    score = scoring.answer_score(question.category, dims)
    db.refresh(answer)
    answer.score = score
    answer.evaluation = {
        "score": score,
        "dimensions": dims,
        "strengths": result.strengths,
        "improvements": result.improvements,
        "feedback": result.feedback,
        "key_points": result.key_points,
    }
    answer.evaluated_at = utcnow()
    answer.evaluation_status = InterviewAIStatus.COMPLETED
    db.commit()


async def submit_answer(
    db: Session, user: User, interview_id: str, payload: InterviewAnswerSubmitRequest
) -> AnswerSubmitResponse:
    session = _get_owned_session(db, user, interview_id)
    if session.status != InterviewStatus.IN_PROGRESS:
        raise _error(
            status.HTTP_409_CONFLICT,
            "This interview has ended, so new answers can't be accepted.",
            status=session.status.value,
        )
    question = next((q for q in session.questions if q.id == payload.question_id), None)
    if question is None:
        raise _error(status.HTTP_404_NOT_FOUND, "Question not found in this interview.")
    if question.answer is not None:
        raise _error(status.HTTP_409_CONFLICT, "This question has already been answered.", answer_id=question.answer.id)
    if payload.answer_source == "VOICE" and session.interaction_mode != InterviewMode.VOICE:
        raise _error(status.HTTP_400_BAD_REQUEST, "Voice answers are only accepted in voice interviews.")

    answer = InterviewAnswer(
        session_id=session.id,
        question_id=question.id,
        answer_text=payload.answer_text,
        answer_source=InterviewMode(payload.answer_source),
        submitted_at=utcnow(),
        evaluation_status=InterviewAIStatus.PENDING,
        evaluation_attempts=0,
    )
    db.add(answer)
    try:
        db.commit()  # the answer is durable before any model call
    except IntegrityError:
        db.rollback()
        raise _error(status.HTTP_409_CONFLICT, "This question has already been answered.")

    if _claim(db, InterviewAnswer, answer.id, True):
        await _run_evaluation(db, session, answer.id)

    db.expire_all()
    session = _session_query(db).filter(InterviewSession.id == interview_id).first()
    saved = next(q.answer for q in session.questions if q.id == payload.question_id)
    return AnswerSubmitResponse(answer=_answer_out(saved, False), interview=serialize_session(session))


async def retry_evaluation(db: Session, user: User, interview_id: str, answer_id: str) -> InterviewAnswerOut:
    session = _get_owned_session(db, user, interview_id)
    answer = next((q.answer for q in session.questions if q.answer and q.answer.id == answer_id), None)
    if answer is None:
        raise _error(status.HTTP_404_NOT_FOUND, "Answer not found in this interview.")
    report_completed = bool(session.report and session.report.status == InterviewAIStatus.COMPLETED)
    if answer.evaluation_status == InterviewAIStatus.COMPLETED:
        return _answer_out(answer, report_completed)  # nothing to do; no model call
    if report_completed:
        raise _error(status.HTTP_409_CONFLICT, "The final report has already been generated for this interview.")

    if not _claim(db, InterviewAnswer, answer.id, False):
        db.refresh(answer)
        if answer.evaluation_status == InterviewAIStatus.PENDING:
            raise _error(status.HTTP_409_CONFLICT, "This answer is already being evaluated.")
        raise _error(status.HTTP_409_CONFLICT, "The retry limit for this evaluation has been reached.")
    await _run_evaluation(db, session, answer.id)
    db.expire_all()
    return _answer_out(db.get(InterviewAnswer, answer_id), False)


# ---------------------------------------------------------------------------
# Completion and report
# ---------------------------------------------------------------------------


def complete_interview(db: Session, user: User, interview_id: str) -> InterviewSessionOut:
    """End the interview. Idempotent for sessions that have already ended."""
    session = _get_owned_session(db, user, interview_id)
    if session.status in TERMINAL_STATUSES:
        return serialize_session(session)
    now = utcnow()
    if not _answered(session):
        new_status = InterviewStatus.ABANDONED
    elif now >= _aware(session.deadline_at):
        new_status = InterviewStatus.EXPIRED
    else:
        new_status = InterviewStatus.COMPLETED
    _end_session(db, session, new_status, now)
    db.commit()
    return get_interview(db, user, interview_id)


def _report_rows(session: InterviewSession) -> list[dict]:
    rows = []
    for q in session.questions:
        a = q.answer
        evaluated = a is not None and a.evaluation_status == InterviewAIStatus.COMPLETED
        rows.append(
            {
                "question_id": q.id,
                "question_order": q.question_order,
                "competency": q.competency,
                "category": q.category,
                "answered": a is not None,
                "score": a.score if evaluated else None,
                "dimensions": (a.evaluation or {}).get("dimensions") if evaluated else None,
                "evaluation": a.evaluation if evaluated else None,
            }
        )
    return rows


def get_report(db: Session, user: User, interview_id: str) -> InterviewReportOut:
    session = _get_owned_session(db, user, interview_id)
    if session.status == InterviewStatus.IN_PROGRESS:
        raise _error(status.HTTP_409_CONFLICT, "The final report is available after the interview ends.")
    if session.report is None:
        raise _error(status.HTTP_404_NOT_FOUND, "No report is available because no answers were submitted.")
    return serialize_report(session)


async def generate_report(db: Session, user: User, interview_id: str) -> InterviewReportOut:
    """Generate (or retry) the final report. Returns the stored report without a model call if complete."""
    session = _get_owned_session(db, user, interview_id)
    if session.status == InterviewStatus.IN_PROGRESS:
        raise _error(status.HTTP_409_CONFLICT, "The final report is available after the interview ends.")
    if session.report is None:
        raise _error(status.HTTP_404_NOT_FOUND, "No report is available because no answers were submitted.")
    report = session.report
    if report.status == InterviewAIStatus.COMPLETED:
        return serialize_report(session)

    if not _claim(db, InterviewReport, report.id, True):
        db.refresh(report)
        if report.status == InterviewAIStatus.COMPLETED:
            return serialize_report(session)
        if report.status == InterviewAIStatus.PENDING:
            raise _error(status.HTTP_409_CONFLICT, "The report is already being generated.")
        raise _error(status.HTTP_409_CONFLICT, "The retry limit for this report has been reached.")

    # Give unevaluated answers one more bounded attempt so the report covers as much as possible.
    for question in session.questions:
        answer = question.answer
        if answer is None or answer.evaluation_status == InterviewAIStatus.COMPLETED:
            continue
        if _claim(db, InterviewAnswer, answer.id, True):
            await _run_evaluation(db, session, answer.id)

    db.expire_all()
    session = _session_query(db).filter(InterviewSession.id == interview_id).first()
    report = session.report
    rows = _report_rows(session)
    computed = scoring.aggregate(rows)

    # Persist deterministic results first so they survive a narrative failure.
    report.overall_score = computed["overall_score"]
    report.aggregates = computed["aggregates"]
    session.final_score = computed["overall_score"]
    db.commit()

    evaluated_items = [
        {
            "question_order": row["question_order"],
            "category": row["category"],
            "competency": row["competency"],
            "score": row["score"],
            "strengths": row["evaluation"].get("strengths", []),
            "improvements": row["evaluation"].get("improvements", []),
            "feedback": row["evaluation"].get("feedback", ""),
        }
        for row in rows
        if row["score"] is not None
    ]
    if not evaluated_items:
        report.status = InterviewAIStatus.FAILED
        db.commit()
        return serialize_report(session)

    try:
        narrative = await ai.generate_narrative(
            role=session.target_role,
            interview_type=session.interview_type.value,
            difficulty=session.difficulty.value,
            overall_score=computed["overall_score"],
            category_scores=computed["aggregates"]["category_scores"],
            dimension_scores=computed["aggregates"]["dimension_scores"],
            evaluated_items=evaluated_items,
        )
    except ai.InterviewAIError:
        db.refresh(report)
        report.status = InterviewAIStatus.FAILED
        db.commit()
        return serialize_report(session)

    db.refresh(report)
    report.narrative = narrative.model_dump()
    report.status = InterviewAIStatus.COMPLETED
    report.generated_at = utcnow()
    db.commit()
    return serialize_report(session)


# ---------------------------------------------------------------------------
# Voice transcription
# ---------------------------------------------------------------------------


async def transcribe_audio(db: Session, user: User, interview_id: str, data: bytes) -> tuple[str, float]:
    session = _get_owned_session(db, user, interview_id)
    _require_in_progress(session)
    if session.interaction_mode != InterviewMode.VOICE:
        raise _error(status.HTTP_400_BAD_REQUEST, "Transcription is only available in voice interviews.")
    try:
        return await transcription_service.transcribe(data)
    except transcription_service.TranscriptionUnavailable:
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Speech transcription is not configured on this server. Please type your answer instead.",
            stage="transcription_unavailable",
        )
    except transcription_service.TranscriptionError as exc:
        raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc), stage="transcription")
