from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends
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
from app.services import interview_service


def _schedule_follow_ups(background_tasks: BackgroundTasks, out: SubmissionOut, interview_id: str, user: User) -> None:
    """After a completed SUBMIT: AI review (once per submission) and the question's follow-up (once)."""
    if out.submission_type != "SUBMIT" or out.status != "COMPLETED":
        return
    if out.ai_review is not None and out.ai_review.status == "PENDING":
        background_tasks.add_task(svc.review_submission, out.id)
    background_tasks.add_task(interview_service.generate_follow_up_task, interview_id, user.id, out.question_id)


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
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SubmissionOut:
    out = await svc.submit_solution(db, current_user, interview_id, question_id, payload)
    _schedule_follow_ups(background_tasks, out, interview_id, current_user)
    return out


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
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SubmissionOut:
    out = await svc.get_submission(db, current_user, interview_id, submission_id)
    # A submission that finished while being polled gets its review/follow-up scheduled here
    # (claims make repeated scheduling a no-op).
    _schedule_follow_ups(background_tasks, out, interview_id, current_user)
    return out


@router.post(
    "/interviews/{interview_id}/coding-submissions/{submission_id}/review",
    response_model=SubmissionOut,
    summary="Run or retry the AI code review of a submission (code quality only; never changes the verdict)",
)
async def retry_review(
    interview_id: str,
    submission_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SubmissionOut:
    return await svc.retry_review(db, current_user, interview_id, submission_id)
