"""Career Matching API — real job listings matched against the authenticated user's profile."""

from __future__ import annotations

import asyncio
import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_current_user, get_db
from app.db.models import User
from app.schemas.career_matching_api import (
    CareerMatchingAPIResponse,
    ProviderStatusResponse,
    SyncTriggerResponse,
)
from app.services.career_matching_pipeline_service import run_career_matching_pipeline
from app.services.career_matching_service import MatchFilters
from app.services.job_sync_service import is_sync_running, provider_status, run_full_sync

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/career-matching", tags=["Career Matching"])

# Strong references so manual sync tasks are not garbage-collected mid-run.
_background_tasks: set[asyncio.Task] = set()

ProviderKey = Literal["greenhouse", "lever", "ashby", "adzuna", "remotive"]


@router.get("/me", response_model=CareerMatchingAPIResponse)
async def get_my_career_matches(
    include_ai: bool = Query(
        default=False,
        description="Annotate the top results with Gemini rerank notes and Qwen explanations (slower). "
                    "Scores and ordering are always deterministic.",
    ),
    location: Optional[str] = Query(default=None, max_length=80),
    work_mode: Optional[Literal["remote", "hybrid", "onsite"]] = Query(default=None),
    employment_type: Optional[Literal["full_time", "part_time", "contract", "internship", "temporary"]] = Query(default=None),
    experience: Optional[Literal["internship", "entry", "mid", "senior"]] = Query(default=None),
    source: Optional[ProviderKey] = Query(default=None),
    page: int = Query(default=1, ge=1, le=500),
    page_size: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CareerMatchingAPIResponse:
    filters = MatchFilters(
        location=location.strip() if location and location.strip() else None,
        work_mode=work_mode,
        employment_type=employment_type,
        experience=experience,
        source=source,
    )
    try:
        return await run_career_matching_pipeline(
            db=db, user=current_user, include_ai=include_ai, filters=filters, page=page, page_size=page_size,
        )
    except Exception as exc:
        logger.exception("[CareerMatching] Matching failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Career matching is temporarily unavailable. Please try again shortly.",
        ) from exc


@router.get("/providers/status", response_model=ProviderStatusResponse)
def get_provider_status(
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> ProviderStatusResponse:
    """Provider health: configuration (no secrets), last sync, last error, active listings."""
    return ProviderStatusResponse(**provider_status(db))


@router.post("/admin/sync", response_model=SyncTriggerResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_job_sync(
    provider: Optional[ProviderKey] = Query(default=None, description="Limit the sync to one provider."),
    _admin: User = Depends(get_current_admin),
) -> SyncTriggerResponse:
    """Start a synchronisation in the background (admin only)."""
    if is_sync_running():
        return SyncTriggerResponse(status="already_running", message="A job synchronisation is already running.")

    async def _run() -> None:
        try:
            await asyncio.to_thread(run_full_sync, "manual", provider)
        except Exception:
            logger.exception("[JobSync] Manual sync failed")

    task = asyncio.get_running_loop().create_task(_run())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return SyncTriggerResponse(status="started", message="Job synchronisation started. Check /providers/status for progress.")
