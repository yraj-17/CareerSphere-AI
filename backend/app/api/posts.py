from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models import User
from app.schemas.posts import (
    CommentCreateRequest,
    CommentListResponse,
    CommentResponse,
    LikeResponse,
    PostCreateRequest,
    PostListResponse,
    PostResponse,
    PostUpdateRequest,
)
from app.services import post_service as svc

router = APIRouter(prefix="/posts", tags=["Posts"])


@router.get("", response_model=PostListResponse, summary="List the authenticated user's Home feed")
def list_posts(
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PostListResponse:
    total, posts = svc.list_posts(db, current_user, limit, offset)
    return PostListResponse(total=total, limit=limit, offset=offset, posts=posts)


@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED, summary="Create a global post")
def create_post(
    payload: PostCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PostResponse:
    return svc.create_post(db, current_user, payload)


@router.patch("/{post_id}", response_model=PostResponse, summary="Edit your global post")
def update_post(
    post_id: str,
    payload: PostUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PostResponse:
    return svc.update_post(db, current_user, post_id, payload)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete your global post")
def delete_post(
    post_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    svc.delete_post(db, current_user, post_id)


@router.post("/{post_id}/like", response_model=LikeResponse, summary="Like a global post")
def like_post(
    post_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LikeResponse:
    return svc.like_post(db, current_user, post_id, True)


@router.delete("/{post_id}/like", response_model=LikeResponse, summary="Unlike a global post")
def unlike_post(
    post_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LikeResponse:
    return svc.like_post(db, current_user, post_id, False)


@router.get("/{post_id}/comments", response_model=CommentListResponse, summary="List comments for a global post")
def list_comments(
    post_id: str,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CommentListResponse:
    total, comments = svc.list_comments(db, current_user, post_id, limit, offset)
    return CommentListResponse(total=total, limit=limit, offset=offset, comments=comments)


@router.post("/{post_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED, summary="Comment on a global post")
def create_comment(
    post_id: str,
    payload: CommentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CommentResponse:
    return svc.create_comment(db, current_user, post_id, payload)


@router.patch("/comments/{comment_id}", response_model=CommentResponse, summary="Edit your comment")
def update_comment(
    comment_id: str,
    payload: CommentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CommentResponse:
    return svc.update_comment(db, current_user, comment_id, payload)


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a comment")
def delete_comment(
    comment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    svc.delete_comment(db, current_user, comment_id)
