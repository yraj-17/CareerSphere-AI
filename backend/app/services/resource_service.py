from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import String, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.db.models import Profile, Resource, ResourceType, SavedResource, User
from app.schemas.resources import (
    ResourceAuthorSummary,
    ResourceCreateRequest,
    ResourceResponse,
    ResourceUpdateRequest,
    normalize_resource_tags,
    resource_domain,
)
from app.services.storage_service import presigned_get_url


def _profile_photo_url(profile: Profile | None) -> str | None:
    if not profile or not profile.profile_photo:
        return None
    try:
        return presigned_get_url(profile.profile_photo.object_key)
    except Exception:
        return None


def _author_summary(user: User | None) -> ResourceAuthorSummary | None:
    if user is None:
        return None
    profile = user.profile
    return ResourceAuthorSummary(
        id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        headline=profile.headline if profile else None,
        location=profile.location if profile else None,
        profile_photo_url=_profile_photo_url(profile),
    )


def _require_resource(db: Session, resource_id: str) -> Resource:
    resource = (
        db.query(Resource)
        .options(joinedload(Resource.author).joinedload(User.profile).joinedload(Profile.profile_photo))
        .filter(Resource.id == resource_id)
        .first()
    )
    if resource is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found.")
    return resource


def _saved_ids_for(db: Session, current_user_id: str, resource_ids: list[str]) -> set[str]:
    if not resource_ids:
        return set()
    return {
        row.resource_id
        for row in db.query(SavedResource.resource_id)
        .filter(
            SavedResource.user_id == current_user_id,
            SavedResource.resource_id.in_(resource_ids),
        )
        .all()
    }


def _save_counts_for(db: Session, resource_ids: list[str]) -> dict[str, int]:
    if not resource_ids:
        return {}
    rows = (
        db.query(SavedResource.resource_id, func.count(SavedResource.id).label("save_count"))
        .filter(SavedResource.resource_id.in_(resource_ids))
        .group_by(SavedResource.resource_id)
        .all()
    )
    return {resource_id: int(count or 0) for resource_id, count in rows}


def _resource_response(
    resource: Resource,
    current_user_id: str,
    is_saved: bool = False,
    save_count: int = 0,
) -> ResourceResponse:
    resource_type = resource.resource_type.value if hasattr(resource.resource_type, "value") else str(resource.resource_type)
    return ResourceResponse(
        id=resource.id,
        author_id=resource.author_id,
        author=_author_summary(resource.author),
        title=resource.title,
        description=resource.description,
        url=resource.url,
        source_domain=resource.source_domain,
        resource_type=resource_type,
        category=resource.category,
        tags=list(resource.tags or []),
        thumbnail_url=resource.thumbnail_url,
        is_owner=resource.author_id == current_user_id,
        is_saved=is_saved,
        save_count=save_count,
        created_at=resource.created_at,
        updated_at=resource.updated_at,
    )


def _apply_filters(
    query,
    q: str | None,
    resource_type: str | None,
    category: str | None,
    tag: str | None,
):
    if q and q.strip():
        term = f"%{q.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(Resource.title).like(term),
                func.lower(func.coalesce(Resource.description, "")).like(term),
                func.lower(func.coalesce(Resource.category, "")).like(term),
                func.lower(func.coalesce(Resource.source_domain, "")).like(term),
                func.lower(func.cast(Resource.tags, String)).like(term),
            )
        )

    if resource_type and resource_type != "all":
        query = query.filter(Resource.resource_type == ResourceType(resource_type.strip().upper()))

    if category and category != "all":
        query = query.filter(func.lower(Resource.category) == category.strip().lower())

    if tag and tag.strip():
        normalized = tag.strip().lower()
        query = query.filter(func.lower(func.cast(Resource.normalized_tags, String)).like(f'%"{normalized}"%'))

    return query


def _apply_sort(query, sort: str):
    if sort == "oldest":
        return query.order_by(Resource.created_at.asc(), Resource.title.asc())
    if sort == "title":
        return query.order_by(Resource.title.asc(), Resource.created_at.desc())
    return query.order_by(Resource.created_at.desc(), Resource.title.asc())


def create_resource(db: Session, current_user: User, payload: ResourceCreateRequest) -> ResourceResponse:
    tags, normalized_tags = normalize_resource_tags(payload.tags)
    resource = Resource(
        author_id=current_user.id,
        title=payload.title,
        description=payload.description,
        url=payload.url,
        source_domain=resource_domain(payload.url),
        resource_type=ResourceType(payload.resource_type),
        category=payload.category.strip().lower() if payload.category else None,
        tags=tags,
        normalized_tags=normalized_tags,
        thumbnail_url=payload.thumbnail_url,
    )
    db.add(resource)
    db.commit()
    db.refresh(resource)
    resource.author = current_user
    return _resource_response(resource, current_user.id, is_saved=False, save_count=0)


def list_resources(
    db: Session,
    current_user: User,
    q: str | None = None,
    resource_type: str | None = None,
    category: str | None = None,
    tag: str | None = None,
    saved_only: bool = False,
    sort: str = "newest",
    limit: int = 20,
    offset: int = 0,
) -> tuple[int, list[ResourceResponse]]:
    query = (
        db.query(Resource)
        .options(joinedload(Resource.author).joinedload(User.profile).joinedload(Profile.profile_photo))
    )

    if saved_only:
        query = query.join(
            SavedResource,
            (SavedResource.resource_id == Resource.id) & (SavedResource.user_id == current_user.id),
        )

    query = _apply_filters(query, q, resource_type, category, tag)

    total = query.count()
    resources = _apply_sort(query, sort).offset(offset).limit(limit).all()
    ids = [resource.id for resource in resources]
    saved_ids = _saved_ids_for(db, current_user.id, ids)
    save_counts = _save_counts_for(db, ids)
    return total, [
        _resource_response(
            resource,
            current_user.id,
            is_saved=resource.id in saved_ids,
            save_count=save_counts.get(resource.id, 0),
        )
        for resource in resources
    ]


def get_resource(db: Session, current_user: User, resource_id: str) -> ResourceResponse:
    resource = _require_resource(db, resource_id)
    saved = (
        db.query(SavedResource.id)
        .filter(SavedResource.user_id == current_user.id, SavedResource.resource_id == resource_id)
        .first()
        is not None
    )
    save_count = (
        db.query(func.count(SavedResource.id))
        .filter(SavedResource.resource_id == resource_id)
        .scalar()
        or 0
    )
    return _resource_response(resource, current_user.id, is_saved=saved, save_count=int(save_count))


def update_resource(
    db: Session,
    current_user: User,
    resource_id: str,
    payload: ResourceUpdateRequest,
) -> ResourceResponse:
    resource = _require_resource(db, resource_id)
    if resource.author_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the resource owner can edit it.")

    update_data = payload.model_dump(exclude_unset=True)
    if "title" in update_data:
        resource.title = payload.title
    if "description" in update_data:
        resource.description = payload.description
    if "url" in update_data and payload.url:
        resource.url = payload.url
        resource.source_domain = resource_domain(payload.url)
    if "resource_type" in update_data and payload.resource_type:
        resource.resource_type = ResourceType(payload.resource_type)
    if "category" in update_data:
        resource.category = payload.category.strip().lower() if payload.category else None
    if "tags" in update_data:
        tags, normalized_tags = normalize_resource_tags(payload.tags or [])
        resource.tags = tags
        resource.normalized_tags = normalized_tags
    if "thumbnail_url" in update_data:
        resource.thumbnail_url = payload.thumbnail_url

    db.commit()
    db.refresh(resource)
    return get_resource(db, current_user, resource_id)


def delete_resource(db: Session, current_user: User, resource_id: str) -> dict[str, bool | str]:
    resource = _require_resource(db, resource_id)
    if resource.author_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the resource owner can delete it.")
    db.delete(resource)
    db.commit()
    return {"success": True, "resource_id": resource_id}


def save_resource(db: Session, current_user: User, resource_id: str) -> dict[str, bool | str]:
    _require_resource(db, resource_id)
    existing = (
        db.query(SavedResource)
        .filter(SavedResource.user_id == current_user.id, SavedResource.resource_id == resource_id)
        .first()
    )
    if existing is None:
        db.add(SavedResource(user_id=current_user.id, resource_id=resource_id))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
    return {"success": True, "resource_id": resource_id, "is_saved": True}


def unsave_resource(db: Session, current_user: User, resource_id: str) -> dict[str, bool | str]:
    _require_resource(db, resource_id)
    db.query(SavedResource).filter(
        SavedResource.user_id == current_user.id,
        SavedResource.resource_id == resource_id,
    ).delete(synchronize_session=False)
    db.commit()
    return {"success": True, "resource_id": resource_id, "is_saved": False}
