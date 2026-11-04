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

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, or_, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.models import (
    InterviewAIStatus,
    InterviewAnswer,
    InterviewDifficulty,
    InterviewMode,
    InterviewQuestion,
    InterviewReport,
    InterviewRoleProfile,
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
    BlueprintPreviewResponse,
    DraftSaveRequest,
    DraftSaveResponse,
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
    RoleCatalogResponse,
    RoleSummaryOut,
)
from app.data.interview_roles import ROLES as ROLE_CATALOG
from app.db.redis_client import redis_client
from app.db.session import SessionLocal
from app.services import interview_ai_service as ai
from app.services import interview_blueprint as blueprints
from app.services import interview_role_service as roles
from app.services import interview_scoring as scoring
from app.services import network_calc
from app.services import practical_service as practicals
from app.services import transcription_service

logger = logging.getLogger(__name__)

MAX_EVALUATION_ATTEMPTS = 3
MAX_REPORT_ATTEMPTS = 5
ROLE_ANALYSIS_PER_MINUTE = 10
TERMINAL_STATUSES = {InterviewStatus.COMPLETED, InterviewStatus.EXPIRED, InterviewStatus.ABANDONED}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _grace() -> timedelta:
    return timedelta(seconds=max(0, settings.INTERVIEW_SUBMISSION_GRACE_SECONDS))


# How long report generation waits for answer evaluations already running in another request.
REPORT_INFLIGHT_WAIT_SECONDS = 150.0
REPORT_INFLIGHT_POLL_SECONDS = 1.0


async def _await_inflight_evaluations(db: Session, session_id: str) -> None:
    """
    An answer submitted just before the interview ended may still be evaluating in its own
    request (claimed, PENDING). Wait — bounded — for those, so the report scores them instead
    of silently computing without them. Abandoned claims are not waited on (stale window).
    """
    deadline = asyncio.get_running_loop().time() + REPORT_INFLIGHT_WAIT_SECONDS
    while True:
        fresh = utcnow() - _stale_after()
        inflight = (
            db.query(InterviewAnswer.id)
            .filter(
                InterviewAnswer.session_id == session_id,
                InterviewAnswer.evaluation_status == InterviewAIStatus.PENDING,
                InterviewAnswer.evaluation_attempts > 0,
                InterviewAnswer.updated_at >= fresh,
            )
            .count()
        )
        if not inflight or asyncio.get_running_loop().time() >= deadline:
            return
        await asyncio.sleep(REPORT_INFLIGHT_POLL_SECONDS)
        db.expire_all()


def _stale_after() -> timedelta:
    """A PENDING claim older than this is treated as abandoned (e.g. server restart mid-call)."""
    return timedelta(seconds=settings.OLLAMA_INTERVIEW_TIMEOUT_SECONDS * ai.MAX_ATTEMPTS + 60)


def _error(code: int, message: str, **extra) -> HTTPException:
    if extra:
        return HTTPException(status_code=code, detail={"message": message, **extra})
    return HTTPException(status_code=code, detail=message)


# Practical assessment kinds that can be answered inside the interview:
#   coding / sql  verified problems, answered in the code editor and executed on Judge0;
#                 the latest completed SUBMIT is the answer (coding_service.record_interview_answer)
#   calculation   deterministic IPv4 tasks, auto-graded (network_calc)
#   scenario      curated scenarios, AI-reviewed against a fixed rubric (not executed)
# A slot with no verified assessment is shown as unavailable and excluded from scoring —
# never replaced by a theoretical question.
AVAILABLE_PRACTICAL_KINDS: frozenset[str] = frozenset({"coding", "sql", "calculation", "scenario"})

PRACTICAL_KIND_LABELS = {
    "coding": "Coding assessment",
    "sql": "SQL assessment",
    "calculation": "Practical calculation",
    "scenario": "Practical scenario",
}


def practical_available(kind: str) -> bool:
    return kind == "question" or kind in AVAILABLE_PRACTICAL_KINDS


def _is_code(question: InterviewQuestion) -> bool:
    return (question.kind or "question") in practicals.EXECUTABLE_KINDS


def _answerable(question: InterviewQuestion) -> bool:
    kind = question.kind or "question"
    if kind == "question":
        return True
    spec = question.practical if isinstance(question.practical, dict) else None
    return practical_available(kind) and spec is not None and spec.get("type") == kind


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
    """
    The next question to answer: the first unanswered, answerable question in order.
    Reserved practical slots are skipped. (Where the candidate currently *is* is
    tracked separately in session.current_position — candidates may answer in any order.)
    """
    for question in session.questions:
        if question.answer is None and _answerable(question):
            return question
    return None


def _missing_positions(session: InterviewSession) -> list[int]:
    """Blueprint positions whose question has not been prepared yet."""
    have = {q.question_order for q in session.questions}
    return [p for p in range(1, session.max_questions + 1) if p not in have]


def question_status(question: InterviewQuestion) -> str:
    """
    NOT_STARTED  never opened, nothing typed
    SKIPPED      opened and left without a draft or answer
    IN_PROGRESS  an autosaved draft exists but nothing was submitted
    SUBMITTED    submitted; feedback pending or not available
    ANSWERED     submitted and evaluated
    UNAVAILABLE  reserved practical slot whose assessment engine is not enabled
    """
    if not _answerable(question):
        return "UNAVAILABLE"
    if question.answer is not None:
        return "ANSWERED" if question.answer.evaluation_status == InterviewAIStatus.COMPLETED else "SUBMITTED"
    if (question.draft_text or "").strip() or question.draft_meta:
        return "IN_PROGRESS"
    if question.first_viewed_at is not None:
        return "SKIPPED"
    return "NOT_STARTED"


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
        kind=question.kind or "question",
        assessment_available=_answerable(question),
        competency=question.competency,
        difficulty=question.difficulty.value,
        interviewer_context=question.interviewer_context,
        created_at=question.created_at,
        answer=_answer_out(question.answer, report_completed) if question.answer else None,
        status=question_status(question),
        # Code questions keep their editor draft after a submission (candidates may resubmit).
        draft_text=question.draft_text if question.answer is None or _is_code(question) else None,
        draft_meta=question.draft_meta if question.answer is None or _is_code(question) else None,
        draft_revision=question.draft_revision or 0,
        draft_updated_at=question.draft_updated_at,
        practical=practicals.public_view(question),
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
    missing = _missing_positions(session)
    can_next = in_progress and current is None and remaining > 0 and bool(missing)
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
        job_description=session.job_description,
        blueprint=session.blueprint,
        current_position=session.current_position,
        preparing=in_progress and remaining > 0 and bool(missing),
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


def get_suggestions(db: Session, user: User, role_title: Optional[str] = None) -> InterviewSuggestionsResponse:
    """
    Suggestions come only from data the user saved in their profile — nothing is inferred.
    When a role is given, only profile skills that belong to that role are suggested.
    """
    profile = _load_profile(db, user)
    if profile is None:
        return InterviewSuggestionsResponse(target_role=None, skills=[], has_profile=False)
    role = None
    if profile.career_preferences and profile.career_preferences.target_job_role:
        role = profile.career_preferences.target_job_role.strip()[:120] or None
    if not role and profile.experience:
        role = profile.experience[0].job_title.strip()[:120] or None
    skills = [skill.name for skill in profile.skills]
    if role_title:
        catalog_role = roles.resolve_catalog_role(role_title)
        skills = roles.relevant_profile_skills(skills, roles.from_catalog(catalog_role, role_title)) if catalog_role else []
    return InterviewSuggestionsResponse(target_role=role, skills=skills[:12], has_profile=True)


def _relevant_profile_skills(db: Session, user: User, role: roles.ResolvedRole, focus_areas: list[str]) -> list[str]:
    """Profile skills personalise questions only when they belong to the selected role."""
    profile = _load_profile(db, user)
    if profile is None:
        return []
    return roles.relevant_profile_skills([s.name for s in profile.skills], role, focus_areas)


# ---------------------------------------------------------------------------
# Roles and blueprints
# ---------------------------------------------------------------------------


def _role_summary_out(role: roles.ResolvedRole, aliases: list[str] | None = None) -> RoleSummaryOut:
    return RoleSummaryOut(
        slug=role.slug,
        title=role.canonical_title if role.source == "catalog" else role.title,
        family=role.family,
        source=role.source,
        summary=role.summary,
        aliases=aliases or [],
        focus_areas=role.focus_areas,
        competencies=[
            {k: c[k] for k in ("id", "name", "focus", "practical", "description")} for c in role.competencies
        ],
        practical_kinds=role.practical_kinds,
        languages=role.languages,
    )


def list_roles() -> RoleCatalogResponse:
    return RoleCatalogResponse(
        roles=[_role_summary_out(roles.from_catalog(r, r.title), list(r.aliases)) for r in ROLE_CATALOG]
    )


def _check_analysis_rate(user: User) -> None:
    """Bound LLM role analyses per user. Fails open if Redis is unavailable."""
    key = f"interview:role-analysis:{user.id}:{int(utcnow().timestamp() // 60)}"
    try:
        count = redis_client.incr(key)
        if count == 1:
            redis_client.expire(key, 120)
    except Exception:
        logger.warning("[Interview] role-analysis rate limit unavailable (Redis)")
        return
    if count > ROLE_ANALYSIS_PER_MINUTE:
        raise _error(status.HTTP_429_TOO_MANY_REQUESTS, "Too many role analyses. Please wait a minute and try again.")


async def resolve_role(
    db: Session, user: User, title: str, job_description: Optional[str] = None
) -> roles.ResolvedRole:
    """
    Catalog roles resolve by exact title or alias. Anything else is analysed as a
    custom role — never silently mapped to a different catalog role. Title-only
    analyses are cached; job-description analyses are specific to one session.
    """
    catalog_role = roles.resolve_catalog_role(title)
    if catalog_role is not None:
        return roles.from_catalog(catalog_role, title)

    normalized = roles.title_key(title)[:160]
    if not job_description:
        cached = db.query(InterviewRoleProfile).filter(InterviewRoleProfile.normalized_title == normalized).first()
        if cached is not None:
            return roles.from_analysis(title, cached.analysis)

    _check_analysis_rate(user)
    try:
        analysis = await ai.analyze_role(roles.clean_title(title), job_description)
    except ai.InterviewAIError:
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The AI interviewer couldn't analyse this job title right now. Please try again.",
            stage="role_analysis",
        )
    data = analysis.model_dump()
    if not job_description:
        db.add(
            InterviewRoleProfile(
                normalized_title=normalized,
                title=roles.clean_title(title)[:120],
                analysis=data,
                model_name=settings.OLLAMA_MODEL[:120],
            )
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()  # another request cached the same title concurrently; either analysis is valid
    return roles.from_analysis(title, data)


async def analyze_role_title(db: Session, user: User, title: str) -> RoleSummaryOut:
    role = await resolve_role(db, user, title)
    return _role_summary_out(role)


def _build_blueprint(db: Session, role: roles.ResolvedRole, payload: InterviewCreateRequest) -> dict:
    try:
        return blueprints.build_blueprint(
            role,
            interview_type=payload.interview_type,
            difficulty=payload.difficulty,
            total_questions=payload.question_count,
            focus_areas=payload.focus_areas,
            practical_supply=practicals.practical_supply(db, role),
        )
    except ValueError as exc:
        raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))


async def preview_blueprint(db: Session, user: User, payload: InterviewCreateRequest) -> BlueprintPreviewResponse:
    role = await resolve_role(db, user, payload.target_role, payload.job_description)
    return BlueprintPreviewResponse(
        role=_role_summary_out(role),
        blueprint=_build_blueprint(db, role, payload),
        assessment_kinds_available=sorted(AVAILABLE_PRACTICAL_KINDS),
    )


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


async def _generate_for_slot(
    db: Session,
    user: User,
    *,
    blueprint: dict,
    slot: dict,
    instructions: Optional[str],
    job_description: Optional[str],
    previous: list[str],
) -> InterviewQuestion:
    """Generate the question text for one conceptual blueprint slot (competency fixed by the slot)."""
    role = blueprints.role_from_blueprint(blueprint)
    competency = blueprints.competency_detail(blueprint, slot["competency_id"]) or {}
    focus_areas = list(blueprint.get("focus_areas", []))
    allowed_context = [*focus_areas, instructions or "", job_description or "", slot["competency"], competency.get("description", "")]
    try:
        generated = await ai.generate_question(
            role_title=role.title,
            role_summary=role.summary,
            category=slot["category"],
            competency=slot["competency"],
            competency_description=competency.get("description", ""),
            difficulty=blueprint["difficulty"],
            question_number=slot["position"],
            max_questions=blueprint["total_questions"],
            focus_areas=focus_areas,
            instructions=instructions,
            job_description=job_description,
            relevant_skills=_relevant_profile_skills(db, user, role, focus_areas),
            previous_questions=previous,
            off_role_check=lambda text: roles.off_role_terms(text, role, allowed_context),
        )
    except ai.InterviewAIError as exc:
        code, message = GENERATION_FAILURES.get(exc.category, GENERATION_FAILURES[ai.INVALID_RESPONSE])
        logger.warning(
            "[Interview] question generation failed: category=%s slot=%s competency=%s role=%s",
            exc.category, slot["position"], slot["competency_id"], role.slug or "custom",
        )
        raise _error(code, message, stage="generation", category=exc.category)
    return InterviewQuestion(
        question_order=slot["position"],
        question_text=generated.question_text,
        category=slot["category"],
        kind="question",
        competency=slot["competency"],
        difficulty=InterviewDifficulty(blueprint["difficulty"]),
        interviewer_context=generated.interviewer_context,
    )


# Candidate-facing explanation per failure category (no internals). Nothing has been saved when
# the first question fails, so "try again" is always safe: it never duplicates a session.
GENERATION_FAILURES = {
    ai.LLM_TIMEOUT: (
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "The AI model is busy with other requests, so your first question took too long to prepare. "
        "Nothing was saved — please try again in a minute.",
    ),
    ai.LLM_UNAVAILABLE: (
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "The AI interviewer can't reach the AI model right now. Nothing was saved — please try again shortly.",
    ),
    ai.INVALID_RESPONSE: (
        status.HTTP_502_BAD_GATEWAY,
        "The AI model returned a question that couldn't be read. Nothing was saved — please try again.",
    ),
    ai.VALIDATION_REJECTED: (
        status.HTTP_502_BAD_GATEWAY,
        "The AI model didn't produce a question that fits this role and competency. Nothing was saved — please try again.",
    ),
}


def _reserved_practical_question(blueprint: dict, slot: dict, reason: Optional[str] = None) -> InterviewQuestion:
    """A practical slot that cannot be assessed: recorded with the reason, shown, and not scored."""
    label = PRACTICAL_KIND_LABELS.get(slot["kind"], "Practical assessment")
    reason = reason or (
        "This practical slot is reserved for this interview. The assessment environment is not "
        "enabled yet, so it is skipped and not scored."
    )
    return InterviewQuestion(
        question_order=slot["position"],
        question_text=f"{label}: {slot['competency']}",
        category=slot["category"],
        kind=slot["kind"],
        competency=slot["competency"],
        difficulty=InterviewDifficulty(blueprint["difficulty"]),
        interviewer_context=reason,
        practical=practicals.unavailable_spec(reason),
    )


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

    role = await resolve_role(db, user, payload.target_role, payload.job_description)
    blueprint = _build_blueprint(db, role, payload)
    # The first slot is always conceptual (practical slots are never placed first).
    # Generate it before persisting anything, so a model failure never leaves
    # behind a session whose clock is already running.
    first_question = await _generate_for_slot(
        db,
        user,
        blueprint=blueprint,
        slot=blueprints.slot_at(blueprint, 1),
        instructions=payload.instructions,
        job_description=payload.job_description,
        previous=[],
    )

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
        target_role=role.title,
        interview_type=InterviewType(payload.interview_type),
        interaction_mode=InterviewMode(payload.interaction_mode),
        difficulty=InterviewDifficulty(payload.difficulty),
        duration_minutes=payload.duration_minutes,
        max_questions=blueprint["total_questions"],
        focus_areas=payload.focus_areas,
        instructions=payload.instructions,
        role_slug=role.slug,
        role_source=role.source,
        job_description=payload.job_description,
        blueprint=blueprint,
        status=InterviewStatus.IN_PROGRESS,
        started_at=now,
        deadline_at=now + timedelta(minutes=payload.duration_minutes),
    )
    try:
        db.add(session)
        db.flush()
        first_question.session_id = session.id
        db.add(first_question)
        db.commit()
    except SQLAlchemyError:
        db.rollback()  # all-or-nothing: no session without its first question
        logger.exception("[Interview] could not persist the new interview for user %s", user.id)
        raise _error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Your interview couldn't be saved. Nothing was created — please try again.",
            stage="persistence",
            category="database_persistence",
        )
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


async def _ensure_blueprint(db: Session, user: User, session: InterviewSession) -> dict:
    """Sessions created before the role engine get a blueprint the first time they need one."""
    if session.blueprint:
        return session.blueprint
    role = await resolve_role(db, user, session.target_role)
    blueprint = blueprints.build_blueprint(
        role,
        interview_type=session.interview_type.value,
        difficulty=session.difficulty.value,
        total_questions=max(blueprints.MIN_QUESTIONS, min(blueprints.MAX_QUESTIONS, session.max_questions)),
        focus_areas=list(session.focus_areas or []),
        practical_supply=practicals.practical_supply(db, role),
    )
    session.blueprint = blueprint
    session.role_slug, session.role_source = role.slug, role.source
    db.commit()
    return blueprint


async def _prepare_position(db: Session, user: User, session: InterviewSession, position: int) -> Optional[InterviewQuestion]:
    """Build (but do not insert) the question row for one planned position."""
    blueprint = session.blueprint
    slot = blueprints.slot_at(blueprint, position)
    if slot is None:
        return None
    if slot["kind"] != "question":
        if slot.get("assessment_available") is False:
            return _reserved_practical_question(blueprint, slot, practicals.UNAVAILABLE_REASON)
        spec = practicals.assign(db, user.id, session, slot)
        if spec is None:
            return _reserved_practical_question(blueprint, slot, practicals.UNAVAILABLE_REASON)
        return practicals.build_question(blueprint, slot, spec, answerable=practical_available(slot["kind"]))
    return await _generate_for_slot(
        db,
        user,
        blueprint=blueprint,
        slot=slot,
        instructions=session.instructions,
        job_description=session.job_description,
        previous=[q.question_text for q in session.questions if (q.kind or "question") == "question"],
    )


def _insert_question(db: Session, session_id: str, row: InterviewQuestion) -> bool:
    """Insert a prepared question; the unique (session, order) constraint makes this idempotent."""
    row.session_id = session_id
    db.add(row)
    try:
        db.commit()
        return True
    except IntegrityError:
        db.rollback()  # another request prepared this position first
        return False


_PREPARE_LOCK_SECONDS = 600


async def prepare_remaining_questions(session_id: str, user_id: str) -> None:
    """
    Background task: prepare every planned question that does not exist yet, in order.

    Runs after the interview is created (and again after navigation if anything is
    still missing). A Redis lock keeps one preparer per session; the unique
    (session, question_order) constraint guarantees no position is ever duplicated
    even without the lock. Stops at the deadline, when the interview ends, or on the
    first model failure (navigating to an unprepared question restarts it).
    """
    lock_key = f"interview:prepare:{session_id}"
    token = str(uuid.uuid4())
    try:
        if not redis_client.set(lock_key, token, nx=True, ex=_PREPARE_LOCK_SECONDS):
            return
    except Exception:
        logger.warning("[Interview] preparation lock unavailable (Redis); continuing without it")
        token = None

    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        while user is not None:
            db.expire_all()
            session = _session_query(db).filter(InterviewSession.id == session_id, InterviewSession.user_id == user_id).first()
            if session is None or session.status != InterviewStatus.IN_PROGRESS or utcnow() >= _aware(session.deadline_at):
                break
            if not session.blueprint:
                break
            missing = _missing_positions(session)
            if not missing:
                break
            try:
                row = await _prepare_position(db, user, session, missing[0])
            except HTTPException:
                logger.warning("[Interview] background preparation stopped at position %s (model unavailable)", missing[0])
                break
            if row is None:
                break
            _insert_question(db, session.id, row)
    except Exception:
        logger.exception("[Interview] background preparation failed for session %s", session_id)
    finally:
        db.close()
        if token:
            try:
                if redis_client.get(lock_key) == token:
                    redis_client.delete(lock_key)
            except Exception:
                pass


async def request_next_question(db: Session, user: User, interview_id: str) -> InterviewSessionOut:
    """
    Legacy sequential flow: return the next unanswered question, preparing the next
    missing planned question synchronously if none is ready. Navigation does not use
    this endpoint and never generates questions.
    """
    session = _get_owned_session(db, user, interview_id)
    _require_in_progress(session)
    if _current_question(session) is not None:
        return serialize_session(session)
    if utcnow() >= _aware(session.deadline_at):
        raise _error(status.HTTP_409_CONFLICT, "Time is up. No more questions can be asked.", status="TIME_UP")
    blueprint = await _ensure_blueprint(db, user, session)
    if not _missing_positions(session):
        raise _error(status.HTTP_409_CONFLICT, "All questions for this interview have been asked.", status="LIMIT_REACHED")

    # Prepare missing positions in order until an answerable one exists (reserved practical
    # slots are recorded on the way).
    for position in _missing_positions(session):
        row = await _prepare_position(db, user, session, position)
        if row is None:
            break
        answerable = _answerable(row)
        _insert_question(db, session.id, row)
        db.expire_all()
        session = _get_owned_session(db, user, interview_id)
        _require_in_progress(session)
        if answerable or _current_question(session) is not None:
            break
    return get_interview(db, user, interview_id)


# ---------------------------------------------------------------------------
# Navigation and drafts
# ---------------------------------------------------------------------------


def navigate(db: Session, user: User, interview_id: str, position: int, seq: int) -> tuple[InterviewSessionOut, bool]:
    """
    Record which question the candidate has open. Navigation never submits, evaluates,
    or generates anything. Returns (session, needs_preparation) so the caller can
    restart background preparation if planned questions are still missing.
    """
    session = _get_owned_session(db, user, interview_id)
    _require_in_progress(session)
    if position > session.max_questions:
        raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, f"This interview has {session.max_questions} questions.")

    db.execute(
        update(InterviewSession)
        .where(
            InterviewSession.id == session.id,
            or_(InterviewSession.position_seq.is_(None), InterviewSession.position_seq < seq),
        )
        .values(current_position=position, position_seq=seq)
        .execution_options(synchronize_session=False)
    )
    question = next((q for q in session.questions if q.question_order == position), None)
    if question is not None and question.first_viewed_at is None:
        db.execute(
            update(InterviewQuestion)
            .where(InterviewQuestion.id == question.id, InterviewQuestion.first_viewed_at.is_(None))
            .values(first_viewed_at=utcnow())
            .execution_options(synchronize_session=False)
        )
    db.commit()
    out = get_interview(db, user, interview_id)
    return out, out.preparing


def save_draft(
    db: Session, user: User, interview_id: str, question_id: str, payload: DraftSaveRequest
) -> DraftSaveResponse:
    """
    Autosave unsubmitted work. Applied only when payload.revision is newer than the
    stored revision and the question has no submitted answer, so a delayed older save
    can never overwrite newer text and a draft can never touch a submitted answer.
    """
    session = _get_owned_session(db, user, interview_id)
    if session.status != InterviewStatus.IN_PROGRESS:
        raise _error(status.HTTP_409_CONFLICT, "This interview has ended.", status=session.status.value)
    question = next((q for q in session.questions if q.id == question_id), None)
    if question is None:
        raise _error(status.HTTP_404_NOT_FOUND, "Question not found in this interview.")
    if not _answerable(question):
        raise _error(status.HTTP_409_CONFLICT, "This practical assessment is not available yet.", status="ASSESSMENT_UNAVAILABLE")
    code = _is_code(question)
    if question.answer is not None and not code:
        raise _error(status.HTTP_409_CONFLICT, "This question has already been submitted.", status="ALREADY_SUBMITTED")

    now = utcnow()
    conditions = [
        InterviewQuestion.id == question_id,
        InterviewQuestion.session_id == session.id,
        InterviewQuestion.draft_revision < payload.revision,
    ]
    if not code:  # a draft can never touch a submitted written answer
        conditions.append(~db.query(InterviewAnswer.id).filter(InterviewAnswer.question_id == question_id).exists())
    result = db.execute(
        update(InterviewQuestion)
        .where(*conditions)
        .values(
            draft_text=payload.text,
            draft_meta=payload.meta,
            draft_revision=payload.revision,
            draft_updated_at=now,
            first_viewed_at=func.coalesce(InterviewQuestion.first_viewed_at, now),
        )
        .execution_options(synchronize_session=False)
    )
    db.commit()
    db.expire_all()
    stored = db.get(InterviewQuestion, question_id)
    return DraftSaveResponse(
        question_id=question_id,
        saved=result.rowcount == 1,
        revision=stored.draft_revision or 0,
        updated_at=stored.draft_updated_at,
    )


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


async def _run_scenario_evaluation(db: Session, session: InterviewSession, answer: InterviewAnswer) -> None:
    question = answer.question
    scenario_id = (question.practical or {}).get("scenario_id")
    scenario = practicals.SCENARIO_BY_ID[scenario_id]
    rubric = practicals.scenario_rubric(scenario_id)
    try:
        result = await ai.evaluate_scenario(
            role=session.target_role,
            role_summary=(session.blueprint or {}).get("role", {}).get("summary", ""),
            difficulty=question.difficulty.value,
            title=scenario.title,
            context=scenario.context,
            tasks=list(scenario.tasks),
            rubric=rubric,
            answer_text=answer.answer_text,
        )
    except ai.InterviewAIError:
        db.refresh(answer)
        answer.evaluation_status = InterviewAIStatus.FAILED
        db.commit()
        return
    ratings = {c.id: c.score for c in result.criteria}
    comments = {c.id: c.comment for c in result.criteria}
    score = practicals.rubric_score(rubric, ratings)
    db.refresh(answer)
    answer.score = score
    answer.evaluation = {
        "method": "ai_rubric",
        "label": practicals.SCENARIO_LABEL,
        "score": score,
        "criteria": [
            {"id": c["id"], "title": c["title"], "points": c["points"], "score": ratings[c["id"]], "comment": comments[c["id"]]}
            for c in rubric
        ],
        "strengths": result.strengths,
        "improvements": result.improvements,
        "feedback": result.feedback,
        "key_points": result.key_points,
    }
    answer.evaluated_at = utcnow()
    answer.evaluation_status = InterviewAIStatus.COMPLETED
    db.commit()


def _calculation_evaluation(question: InterviewQuestion, answers: dict) -> dict:
    graded = network_calc.grade(question.practical["task"], answers)
    wrong = [f["label"] for f in graded["fields"] if not f["correct"]]
    return {
        "method": "deterministic",
        "label": network_calc.LABEL,
        "score": graded["score"],
        "correct": graded["correct"],
        "total": graded["total"],
        "fields": graded["fields"],
        "strengths": [f"{graded['correct']} of {graded['total']} values correct."] if graded["correct"] else [],
        "improvements": [f"Re-check: {', '.join(wrong)}."] if wrong else [],
        "feedback": (
            "Every value is correct." if not wrong else
            "Each value is compared with the result computed by Python's ipaddress module. Review the fields marked incorrect."
        ),
        "key_points": [],
    }


async def _run_evaluation(db: Session, session: InterviewSession, answer_id: str) -> None:
    """Evaluate one claimed answer and persist the outcome. Never raises for model failures."""
    answer = db.get(InterviewAnswer, answer_id)
    question = answer.question
    if (question.kind or "question") == "scenario":
        await _run_scenario_evaluation(db, session, answer)
        return
    role_summary, competency_description = "", ""
    if session.blueprint:
        role_summary = session.blueprint.get("role", {}).get("summary", "")
        detail = next((c for c in session.blueprint.get("competencies", []) if c["name"] == question.competency), None)
        competency_description = (detail or {}).get("description", "")
    try:
        result = await ai.evaluate_answer(
            role=session.target_role,
            category=question.category,
            difficulty=question.difficulty.value,
            question_text=question.question_text,
            competency=question.competency,
            answer_text=answer.answer_text,
            role_summary=role_summary,
            competency_description=competency_description,
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
    if not _answerable(question):
        # A typed answer must never stand in for a coding/SQL/practical assessment.
        raise _error(
            status.HTTP_409_CONFLICT,
            "This practical assessment is not available yet, so it can't be answered as text.",
            status="ASSESSMENT_UNAVAILABLE",
        )
    if _is_code(question):
        # Code is answered only by executing it: a typed answer never stands in for a submission.
        raise _error(
            status.HTTP_409_CONFLICT,
            "This is a coding assessment: submit your code with Submit Solution.",
            status="CODE_SUBMISSION_REQUIRED",
        )
    if question.answer is not None:
        raise _error(status.HTTP_409_CONFLICT, "This question has already been answered.", answer_id=question.answer.id)
    if payload.answer_source == "VOICE" and session.interaction_mode != InterviewMode.VOICE:
        raise _error(status.HTTP_400_BAD_REQUEST, "Voice answers are only accepted in voice interviews.")

    kind = question.kind or "question"
    calculation = None
    if kind == "calculation":
        if payload.structured_answer is None:
            raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "This calculation expects an answer for each field.")
        try:
            calculation = _calculation_evaluation(question, payload.structured_answer)
        except network_calc.CalcAnswerError as exc:
            raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))
        answer_text = network_calc.answer_summary(question.practical["task"], payload.structured_answer)
    else:
        if payload.structured_answer is not None:
            raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "This question expects a written answer.")
        if not payload.answer_text:
            raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Answer cannot be empty.")
        answer_text = payload.answer_text

    now = utcnow()
    answer = InterviewAnswer(
        session_id=session.id,
        question_id=question.id,
        answer_text=answer_text,
        answer_source=InterviewMode(payload.answer_source),
        submitted_at=now,
        evaluation_status=InterviewAIStatus.COMPLETED if calculation else InterviewAIStatus.PENDING,
        evaluation_attempts=0,
    )
    if calculation:  # deterministic: graded on submission, no model call
        answer.score = calculation["score"]
        answer.evaluation = calculation
        answer.evaluated_at = now
    db.add(answer)
    # The submitted answer now holds this text; the draft is no longer needed.
    question.draft_text = None
    question.draft_meta = None
    try:
        db.commit()  # the answer is durable before any model call
    except IntegrityError:
        db.rollback()
        raise _error(status.HTTP_409_CONFLICT, "This question has already been answered.")

    if calculation is None and _claim(db, InterviewAnswer, answer.id, True):
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


def _practical_difficulty(q: InterviewQuestion) -> Optional[dict]:
    spec = q.practical if isinstance(q.practical, dict) else None
    if (q.kind or "question") == "question" or spec is None or spec.get("type") != q.kind:
        return None
    return practicals.difficulty_view(spec)


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
                "kind": q.kind or "question",
                "available": _answerable(q),
                # A verified coding/SQL problem is assigned, but candidate code submission is not part
                # of the interview flow until the code editor phase — reported distinctly, never scored.
                "problem_assigned": bool(
                    q.problem_id
                    and (q.kind or "question") in practicals.EXECUTABLE_KINDS
                    and isinstance(q.practical, dict)
                    and q.practical.get("type") == q.kind
                ),
                "difficulty": _practical_difficulty(q),
                "method": (a.evaluation or {}).get("method") if evaluated else None,
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

    # Code submitted before the deadline but still executing is settled first, so its
    # Judge0 result is part of the report (imported here: coding_service imports this module).
    from app.services import coding_service

    await coding_service.settle_pending_submissions(db, session.id)

    # Give unevaluated answers one more bounded attempt so the report covers as much as possible.
    for question in session.questions:
        answer = question.answer
        if answer is None or answer.evaluation_status == InterviewAIStatus.COMPLETED:
            continue
        if _claim(db, InterviewAnswer, answer.id, True):
            await _run_evaluation(db, session, answer.id)
    await _await_inflight_evaluations(db, session.id)

    db.expire_all()
    session = _session_query(db).filter(InterviewSession.id == interview_id).first()
    report = session.report
    rows = _report_rows(session)
    computed = scoring.aggregate(rows, blueprint=session.blueprint, available_practical_kinds=AVAILABLE_PRACTICAL_KINDS)

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
