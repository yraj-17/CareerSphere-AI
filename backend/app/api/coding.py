from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models import User
from app.schemas.coding import (
    LanguagesResponse,
    ProblemOut,
    RunCodeRequest,
    SubmissionListResponse,
    SubmissionOut,
    SubmitSolutionRequest,
)
from app.services import coding_service as svc


router = APIRouter(tags=["Coding Assessment"])


@router.get("/coding/languages", response_model=LanguagesResponse, summary="Supported languages (labels from the Judge0 server)")
async def list_languages(current_user: User = Depends(get_current_user)) -> LanguagesResponse:
    return await svc.list_languages()


@router.get(
    "/interviews/{interview_id}/questions/{question_id}/problem",
    response_model=ProblemOut,
    summary="Problem statement, samples and starter code (no hidden tests)",
)
async def get_problem(
    interview_id: str,
    question_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProblemOut:
    return await svc.get_problem(db, current_user, interview_id, question_id)


@router.post(
    "/interviews/{interview_id}/questions/{question_id}/run",
    response_model=SubmissionOut,
    summary="Run code on the sample tests and optional custom input",
)
async def run_code(
    interview_id: str,
    question_id: str,
    payload: RunCodeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SubmissionOut:
    return await svc.run_code(db, current_user, interview_id, question_id, payload)


@router.post(
    "/interviews/{interview_id}/questions/{question_id}/submit",
    response_model=SubmissionOut,
    summary="Submit a solution against every public and hidden test",
)
async def submit_solution(
    interview_id: str,
    question_id: str,
    payload: SubmitSolutionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SubmissionOut:
    return await svc.submit_solution(db, current_user, interview_id, question_id, payload)


@router.get(
    "/interviews/{interview_id}/questions/{question_id}/submissions",
    response_model=SubmissionListResponse,
    summary="Run and submission history for a coding question",
)
def list_submissions(
    interview_id: str,
    question_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SubmissionListResponse:
    return svc.list_submissions(db, current_user, interview_id, question_id)


@router.get(
    "/interviews/{interview_id}/coding-submissions/{submission_id}",
    response_model=SubmissionOut,
    summary="Submission status and results (resumes polling while running)",
)
async def get_submission(
    interview_id: str,
    submission_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SubmissionOut:
    return await svc.get_submission(db, current_user, interview_id, submission_id)
