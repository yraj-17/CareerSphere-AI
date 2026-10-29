from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.db.models import User
from app.schemas.interviews import (
    AnswerSubmitResponse,
    InterviewAnswerOut,
    InterviewAnswerSubmitRequest,
    InterviewCreateRequest,
    InterviewListResponse,
    InterviewOptionsResponse,
    InterviewQuestionOut,
    InterviewReportOut,
    InterviewSessionOut,
    InterviewSuggestionsResponse,
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InterviewSuggestionsResponse:
    return svc.get_suggestions(db, current_user)


@router.post("", response_model=InterviewSessionOut, status_code=status.HTTP_201_CREATED, summary="Start an interview")
async def create_interview(
    payload: InterviewCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InterviewSessionOut:
    return await svc.create_interview(db, current_user, payload)


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
