"""
Communities V1 REST API.

JWT identity is always derived from the existing authentication dependency.
V1 media/content enhancements:
- Community profile photo (PATCH /{community_id}/image, DELETE /{community_id}/image)
- Post images (multipart/form-data create)
- Post topic tags (#hashtags)

All existing endpoints (create/list/detail/join/leave/members/posts/reactions/comments/delete) preserved.
"""
from __future__ import annotations

import json
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models import User
from app.schemas.communities import (
    CommunityCreateRequest,
    CommunityImageUpdateResponse,
    CommunityListResponse,
    CommunityMembersResponse,
    CommunityMembershipResponse,
    CommunityPostCommentCreateRequest,
    CommunityPostCommentResponse,
    CommunityPostCommentsResponse,
    CommunityPostDeleteResponse,
    CommunityPostResponse,
    CommunityPostsResponse,
    CommunityReactionRequest,
    CommunityReactionSummaryResponse,
    CommunityResponse,
)
from app.services import community_service as svc

router = APIRouter(prefix="/communities", tags=["Communities"])

COMMUNITY_LIST_LIMIT_MAX = 50
COMMUNITY_POST_LIMIT_MAX = 50
COMMUNITY_MEMBER_LIMIT_MAX = 100
COMMUNITY_COMMENT_LIMIT_MAX = 50


# ─────────────────────────────────────────────────────────────────────────────
# Community discovery / CRUD
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=CommunityListResponse,
    summary="Discover communities",
)
def list_communities(
    q: Optional[str] = Query(None, description="Search communities by name or description"),
    category: Optional[str] = Query(None, description="Community category filter"),
    membership: str = Query("discover", pattern="^(discover|joined)$"),
    limit: int = Query(20, ge=1, le=COMMUNITY_LIST_LIMIT_MAX),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CommunityListResponse:
    total, communities = svc.list_communities(
        db=db,
        current_user=current_user,
        q=q,
        category=category,
        membership=membership,
        limit=limit,
        offset=offset,
    )
    return CommunityListResponse(total=total, limit=limit, offset=offset, communities=communities)


@router.post(
    "",
    response_model=CommunityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a community",
)
def create_community(
    payload: CommunityCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CommunityResponse:
    return svc.create_community(db, current_user, payload)


@router.get(
    "/{community_id}",
    response_model=CommunityResponse,
    summary="Get community detail",
)
def get_community(
    community_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CommunityResponse:
    return svc.get_community(db, current_user, community_id)


@router.post(
    "/{community_id}/join",
    response_model=CommunityMembershipResponse,
    summary="Join a public community",
)
def join_community(
    community_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CommunityMembershipResponse:
    return svc.join_community(db, current_user, community_id)


@router.post(
    "/{community_id}/leave",
    response_model=CommunityMembershipResponse,
    summary="Leave a community",
)
def leave_community(
    community_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CommunityMembershipResponse:
    return svc.leave_community(db, current_user, community_id)


@router.get(
    "/{community_id}/members",
    response_model=CommunityMembersResponse,
    summary="List community members",
)
def list_members(
    community_id: str,
    limit: int = Query(50, ge=1, le=COMMUNITY_MEMBER_LIMIT_MAX),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CommunityMembersResponse:
    total, members = svc.list_members(db, current_user, community_id, limit=limit, offset=offset)
    return CommunityMembersResponse(total=total, limit=limit, offset=offset, members=members)


# ─────────────────────────────────────────────────────────────────────────────
# Community profile photo
# ─────────────────────────────────────────────────────────────────────────────

@router.patch(
    "/{community_id}/image",
    response_model=CommunityImageUpdateResponse,
    summary="Upload or replace the community profile photo (owner only)",
)
async def update_community_image(
    community_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CommunityImageUpdateResponse:
    return await svc.update_community_image(
        db=db,
        current_user=current_user,
        community_id=community_id,
        file=file,
        remove=False,
    )


@router.delete(
    "/{community_id}/image",
    response_model=CommunityImageUpdateResponse,
    summary="Remove the community profile photo (owner only)",
)
async def remove_community_image(
    community_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CommunityImageUpdateResponse:
    return await svc.update_community_image(
        db=db,
        current_user=current_user,
        community_id=community_id,
        file=None,
        remove=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Posts
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/{community_id}/posts",
    response_model=CommunityPostsResponse,
    summary="List community posts",
)
def list_posts(
    community_id: str,
    limit: int = Query(20, ge=1, le=COMMUNITY_POST_LIMIT_MAX),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CommunityPostsResponse:
    total, posts = svc.list_posts(db, current_user, community_id, limit=limit, offset=offset)
    return CommunityPostsResponse(total=total, limit=limit, offset=offset, posts=posts)


@router.post(
    "/{community_id}/posts",
    response_model=CommunityPostResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a community post (text, images, and/or topic tags)",
)
async def create_post(
    community_id: str,
    content: str = Form(default=""),
    tags: str = Form(default="[]"),
    images: List[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CommunityPostResponse:
    # Parse tags from JSON string
    try:
        parsed_tags: list[str] = json.loads(tags) if tags else []
    except (json.JSONDecodeError, ValueError):
        # Fall back to comma-separated format for simple clients
        parsed_tags = [t.strip() for t in tags.split(",") if t.strip()]

    # Enforce content length limit at API layer (Form fields bypass Pydantic validators)
    if len(content) > 2000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Post content must be 2000 characters or fewer.",
        )

    # Filter out empty upload placeholders that some clients send
    real_images = [img for img in images if img.filename and img.filename != ""]

    return await svc.create_post(
        db=db,
        current_user=current_user,
        community_id=community_id,
        content=content,
        tags=parsed_tags,
        images=real_images,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Reactions, Comments, Delete — unchanged from V1
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/posts/{post_id}/reaction",
    response_model=CommunityReactionSummaryResponse,
    summary="Toggle or change the authenticated user's reaction on a community post",
)
def set_post_reaction(
    post_id: str,
    payload: CommunityReactionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CommunityReactionSummaryResponse:
    return svc.set_post_reaction(db, current_user, post_id, payload)


@router.get(
    "/posts/{post_id}/comments",
    response_model=CommunityPostCommentsResponse,
    summary="List comments for a community post",
)
def list_post_comments(
    post_id: str,
    limit: int = Query(20, ge=1, le=COMMUNITY_COMMENT_LIMIT_MAX),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CommunityPostCommentsResponse:
    total, comments = svc.list_comments(db, current_user, post_id, limit=limit, offset=offset)
    return CommunityPostCommentsResponse(total=total, limit=limit, offset=offset, comments=comments)


@router.post(
    "/posts/{post_id}/comments",
    response_model=CommunityPostCommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a comment on a community post",
)
def create_post_comment(
    post_id: str,
    payload: CommunityPostCommentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CommunityPostCommentResponse:
    return svc.create_comment(db, current_user, post_id, payload)


@router.delete(
    "/posts/{post_id}",
    response_model=CommunityPostDeleteResponse,
    summary="Delete a community post",
)
def delete_post(
    post_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CommunityPostDeleteResponse:
    return svc.delete_post(db, current_user, post_id)
