"""
Communities V1 REST API.

JWT identity is always derived from the existing authentication dependency.
V1 intentionally excludes chat, comments, likes, recommendations, invitations,
events, media, Redis, WebSockets, and AI features.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models import User
from app.schemas.communities import (
    CommunityCreateRequest,
    CommunityListResponse,
    CommunityMembersResponse,
    CommunityMembershipResponse,
    CommunityPostCreateRequest,
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
    summary="Create a community post",
)
def create_post(
    community_id: str,
    payload: CommunityPostCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CommunityPostResponse:
    return svc.create_post(db, current_user, community_id, payload)


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
