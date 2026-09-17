"""Career Matching API — Phase 3.6."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models import User
from app.schemas.career_matching_api import CareerMatchingAPIResponse
from app.services.career_matching_pipeline_service import run_career_matching_pipeline
from app.services.embedding_service import EmbeddingServiceError

router = APIRouter(prefix="/career-matching", tags=["Career Matching"])


@router.get("/me", response_model=CareerMatchingAPIResponse)
async def get_my_career_matches(
    include_ai: bool = Query(
        default=True,
        description="Include Gemini reranking and Qwen explanations. If false, returns deterministic fallback Top 5.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CareerMatchingAPIResponse:
    try:
        return await run_career_matching_pipeline(db=db, user=current_user, include_ai=include_ai)
    except EmbeddingServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Career opportunity retrieval is temporarily unavailable: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Career matching is temporarily unavailable.",
        ) from exc
