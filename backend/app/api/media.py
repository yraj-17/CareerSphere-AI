"""Media upload/download endpoints backed by MinIO + PostgreSQL metadata."""
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models import MediaObject, User
from app.schemas.media import MediaListResponse, MediaUploadResponse, MediaUrlResponse
from app.services import storage_service

router = APIRouter(prefix="/media", tags=["Media"])

ALLOWED_PURPOSES = {"general", "resume", "profile_image", "document"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post(
    "/upload",
    response_model=MediaUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file to MinIO and store metadata in PostgreSQL",
)
async def upload_media(
    purpose: str = Form(default="general"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    purpose = (purpose or "general").strip().lower()
    if purpose not in ALLOWED_PURPOSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid purpose. Allowed: {', '.join(sorted(ALLOWED_PURPOSES))}",
        )

    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file.")
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds the 10 MB upload limit.",
        )

    filename = file.filename or "upload.bin"
    content_type = file.content_type or "application/octet-stream"
    object_key = storage_service.build_object_key(current_user.id, purpose, filename)

    try:
        storage_service.upload_bytes(
            object_key=object_key,
            payload=payload,
            content_type=content_type,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Object storage unavailable. ({exc})",
        )

    media = MediaObject(
        user_id=current_user.id,
        object_key=object_key,
        filename=filename,
        content_type=content_type,
        size_bytes=len(payload),
        purpose=purpose,
    )
    try:
        db.add(media)
        db.commit()
        db.refresh(media)
    except Exception:
        db.rollback()
        try:
            storage_service.delete_file(object_key)
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store file metadata.",
        )

    url = storage_service.presigned_get_url(object_key)
    return MediaUploadResponse(
        id=media.id,
        object_key=media.object_key,
        filename=media.filename,
        content_type=media.content_type,
        size_bytes=media.size_bytes,
        purpose=media.purpose,
        created_at=media.created_at,
        url=url,
    )


@router.get("", response_model=MediaListResponse, summary="List current user's uploaded media")
def list_media(
    purpose: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(MediaObject).filter(MediaObject.user_id == current_user.id)
    if purpose:
        query = query.filter(MediaObject.purpose == purpose.strip().lower())
    items = query.order_by(MediaObject.created_at.desc()).all()
    return MediaListResponse(
        items=[
            MediaUploadResponse(
                id=m.id,
                object_key=m.object_key,
                filename=m.filename,
                content_type=m.content_type,
                size_bytes=m.size_bytes,
                purpose=m.purpose,
                created_at=m.created_at,
                url=storage_service.presigned_get_url(m.object_key),
            )
            for m in items
        ]
    )


@router.get("/{media_id}/url", response_model=MediaUrlResponse, summary="Get a presigned download URL")
def get_media_url(
    media_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    media = (
        db.query(MediaObject)
        .filter(MediaObject.id == media_id, MediaObject.user_id == current_user.id)
        .first()
    )
    if not media:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found.")
    return MediaUrlResponse(
        id=media.id,
        url=storage_service.presigned_get_url(media.object_key),
        expires_in_hours=1,
    )


@router.get("/{media_id}/download", summary="Download media bytes (authenticated)")
def download_media(
    media_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    media = (
        db.query(MediaObject)
        .filter(MediaObject.id == media_id, MediaObject.user_id == current_user.id)
        .first()
    )
    if not media:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found.")
    try:
        data, content_type = storage_service.download_file(media.object_key)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Object storage unavailable. ({exc})",
        )
    return Response(
        content=data,
        media_type=content_type or media.content_type,
        headers={"Content-Disposition": f'attachment; filename="{media.filename}"'},
    )


@router.delete("/{media_id}", status_code=status.HTTP_200_OK, summary="Delete media from MinIO and DB")
def delete_media(
    media_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    media = (
        db.query(MediaObject)
        .filter(MediaObject.id == media_id, MediaObject.user_id == current_user.id)
        .first()
    )
    if not media:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found.")

    object_key = media.object_key
    try:
        db.delete(media)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete media metadata.",
        )

    try:
        storage_service.delete_file(object_key)
    except Exception:
        # Metadata already removed; object cleanup can be retried later
        pass

    return {"message": "Media deleted successfully."}
