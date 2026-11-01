from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.db.models import User
from app.schemas.interviews import (
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
    InterviewSuggestionsResponse,
    NavigateRequest,
    RoleAnalyzeRequest,
    RoleCatalogResponse,
    RoleSummaryOut,
    TranscriptionResponse,
)
from app.services import interview_service as svc


router = APIRouter(prefix="/interviews", tags=["AI Interviewer"])

INTERVIEW_LIST_LIMIT_MAX = 50


@router.get("/options", response_model=InterviewOptionsResponse, summary="Supported interview configuration")
def get_options(current_user: User = Depends(get_current_user)) -> InterviewOptionsResponse:
    return svc.get_options()


@router.get("/suggestions", response_model=InterviewSuggestionsResponse, summary="Role and skill suggestions from the profile")
def get_suggestions(
    role: Optional[str] = Query(None, max_length=120, description="Only return profile skills relevant to this role"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InterviewSuggestionsResponse:
    return svc.get_suggestions(db, current_user, role)


@router.get("/roles", response_model=RoleCatalogResponse, summary="Interview role catalog")
def list_roles(current_user: User = Depends(get_current_user)) -> RoleCatalogResponse:
    return svc.list_roles()


@router.post("/roles/analyze", response_model=RoleSummaryOut, summary="Resolve or analyse a job title")
async def analyze_role(
    payload: RoleAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RoleSummaryOut:
    return await svc.analyze_role_title(db, current_user, payload.title)


@router.post("/blueprint/preview", response_model=BlueprintPreviewResponse, summary="Preview the interview blueprint")
async def preview_blueprint(
    payload: InterviewCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BlueprintPreviewResponse:
    return await svc.preview_blueprint(db, current_user, payload)


@router.post("", response_model=InterviewSessionOut, status_code=status.HTTP_201_CREATED, summary="Start an interview")
async def create_interview(
    payload: InterviewCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InterviewSessionOut:
    interview = await svc.create_interview(db, current_user, payload)
    # The first question is ready; the rest of the plan is prepared after the response.
    if interview.preparing:
        background_tasks.add_task(svc.prepare_remaining_questions, interview.id, current_user.id)
    return interview


@router.get("", response_model=InterviewListResponse, summary="Interview history")
def list_interviews(
    limit: int = Query(10, ge=1, le=INTERVIEW_LIST_LIMIT_MAX),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InterviewListResponse:
    return svc.list_interviews(db, current_user, limit, offset)


@router.get("/{interview_id}", response_model=InterviewSessionOut, summary="Interview detail and status")
def get_interview(
    interview_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InterviewSessionOut:
    return svc.get_interview(db, current_user, interview_id)


@router.get("/{interview_id}/questions/current", response_model=Optional[InterviewQuestionOut], summary="Current unanswered question")
def get_current_question(
    interview_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Optional[InterviewQuestionOut]:
    return svc.get_current_question(db, current_user, interview_id)


@router.post("/{interview_id}/next-question", response_model=InterviewSessionOut, summary="Prepare the next question")
async def next_question(
    interview_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InterviewSessionOut:
    return await svc.request_next_question(db, current_user, interview_id)


@router.post("/{interview_id}/navigate", response_model=InterviewSessionOut, summary="Open a question (no submission or evaluation)")
def navigate(
    interview_id: str,
    payload: NavigateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InterviewSessionOut:
    interview, needs_preparation = svc.navigate(db, current_user, interview_id, payload.position, payload.seq)
    if needs_preparation:
        background_tasks.add_task(svc.prepare_remaining_questions, interview.id, current_user.id)
    return interview


@router.put("/{interview_id}/questions/{question_id}/draft", response_model=DraftSaveResponse, summary="Autosave an unsubmitted answer")
def save_draft(
    interview_id: str,
    question_id: str,
    payload: DraftSaveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftSaveResponse:
    return svc.save_draft(db, current_user, interview_id, question_id, payload)


@router.post("/{interview_id}/answers", response_model=AnswerSubmitResponse, status_code=status.HTTP_201_CREATED, summary="Submit an answer")
async def submit_answer(
    interview_id: str,
    payload: InterviewAnswerSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AnswerSubmitResponse:
    return await svc.submit_answer(db, current_user, interview_id, payload)


@router.post("/{interview_id}/answers/{answer_id}/evaluate", response_model=InterviewAnswerOut, summary="Retry a failed evaluation")
async def retry_evaluation(
    interview_id: str,
    answer_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InterviewAnswerOut:
    return await svc.retry_evaluation(db, current_user, interview_id, answer_id)


@router.post("/{interview_id}/complete", response_model=InterviewSessionOut, summary="End the interview")
def complete_interview(
    interview_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InterviewSessionOut:
    return svc.complete_interview(db, current_user, interview_id)


@router.get("/{interview_id}/report", response_model=InterviewReportOut, summary="Final report")
def get_report(
    interview_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InterviewReportOut:
    return svc.get_report(db, current_user, interview_id)


@router.post("/{interview_id}/report/generate", response_model=InterviewReportOut, summary="Generate the final report")
@router.post("/{interview_id}/report/retry", response_model=InterviewReportOut, summary="Retry final report generation")
async def generate_report(
    interview_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InterviewReportOut:
    return await svc.generate_report(db, current_user, interview_id)


@router.post("/{interview_id}/transcribe", response_model=TranscriptionResponse, summary="Transcribe a recorded voice answer")
async def transcribe_answer(
    interview_id: str,
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TranscriptionResponse:
    # Read at most one byte past the limit so oversized uploads are rejected without buffering them fully.
    data = await audio.read(settings.INTERVIEW_MAX_AUDIO_BYTES + 1)
    await audio.close()
    if len(data) > settings.INTERVIEW_MAX_AUDIO_BYTES:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="The recording is too large.")
    transcript, duration = await svc.transcribe_audio(db, current_user, interview_id, data)
    return TranscriptionResponse(transcript=transcript, duration_seconds=round(duration, 1))
