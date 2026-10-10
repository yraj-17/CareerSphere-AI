from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models import User
from app.schemas.resources import (
    RESOURCE_TYPES,
    ResourceCreateRequest,
    ResourceListResponse,
    ResourceResponse,
    ResourceSaveResponse,
    ResourceUpdateRequest,
)
from app.services import resource_service as svc


router = APIRouter(prefix="/resources", tags=["Resources"])

RESOURCE_LIST_LIMIT_MAX = 50
RESOURCE_SORTS = {"newest", "oldest", "title"}


def _clean_resource_type(value: Optional[str]) -> Optional[str]:
    if not value or value == "all":
        return None
    cleaned = value.strip().upper()
    if cleaned not in RESOURCE_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid resource type.")
    return cleaned


@router.get("", response_model=ResourceListResponse, summary="Discover shared resources")
def list_resources(
    q: Optional[str] = Query(None, description="Search title, description, source, category, or tags"),
    resource_type: Optional[str] = Query(None, description="Resource type filter"),
    category: Optional[str] = Query(None, description="Category filter"),
    tag: Optional[str] = Query(None, description="Tag filter"),
    saved: bool = Query(False, description="Return only resources saved by the authenticated user"),
    sort: str = Query("newest", pattern="^(newest|oldest|title)$"),
    limit: int = Query(20, ge=1, le=RESOURCE_LIST_LIMIT_MAX),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResourceListResponse:
    if sort not in RESOURCE_SORTS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid sort.")
    total, resources = svc.list_resources(
        db=db,
        current_user=current_user,
        q=q,
        resource_type=_clean_resource_type(resource_type),
        category=category,
        tag=tag,
        saved_only=saved,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    return ResourceListResponse(total=total, limit=limit, offset=offset, resources=resources)


@router.post("", response_model=ResourceResponse, status_code=status.HTTP_201_CREATED, summary="Share a resource")
def create_resource(
    payload: ResourceCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResourceResponse:
    return svc.create_resource(db, current_user, payload)


@router.get("/{resource_id}", response_model=ResourceResponse, summary="Get resource detail")
def get_resource(
    resource_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResourceResponse:
    return svc.get_resource(db, current_user, resource_id)


@router.patch("/{resource_id}", response_model=ResourceResponse, summary="Edit an owned resource")
def update_resource(
    resource_id: str,
    payload: ResourceUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResourceResponse:
    return svc.update_resource(db, current_user, resource_id, payload)


@router.delete("/{resource_id}", summary="Delete an owned resource")
def delete_resource(
    resource_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, bool | str]:
    return svc.delete_resource(db, current_user, resource_id)


@router.post("/{resource_id}/save", response_model=ResourceSaveResponse, summary="Save a resource")
def save_resource(
    resource_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResourceSaveResponse:
    return ResourceSaveResponse(**svc.save_resource(db, current_user, resource_id))


@router.delete("/{resource_id}/save", response_model=ResourceSaveResponse, summary="Unsave a resource")
def unsave_resource(
    resource_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResourceSaveResponse:
    return ResourceSaveResponse(**svc.unsave_resource(db, current_user, resource_id))
