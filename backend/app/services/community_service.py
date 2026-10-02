from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    Community,
    CommunityMembership,
    CommunityPost,
    CommunityPostComment,
    CommunityPostReaction,
    Profile,
    User,
)
from app.schemas.communities import (
    CommunityCreateRequest,
    CommunityMemberResponse,
    CommunityMembershipResponse,
    CommunityPostCreateRequest,
    CommunityPostCommentCreateRequest,
    CommunityPostCommentResponse,
    CommunityPostDeleteResponse,
    CommunityPostResponse,
    CommunityReactionRequest,
    CommunityReactionSummaryResponse,
    CommunityResponse,
    CommunityUserSummary,
)
from app.services.storage_service import presigned_get_url


OWNER_ROLE = "owner"
MEMBER_ROLE = "member"
PUBLIC_VISIBILITY = "public"
PRIVATE_VISIBILITY = "private"
REACTION_TYPES = ("LIKE", "LOVE", "CELEBRATE", "SUPPORT", "INSIGHTFUL", "FUNNY")


def _profile_photo_url(profile: Profile | None) -> str | None:
    if not profile or not profile.profile_photo:
        return None
    try:
        return presigned_get_url(profile.profile_photo.object_key)
    except Exception:
        return None


def _user_summary(user: User | None) -> CommunityUserSummary | None:
    if user is None:
        return None
    profile = user.profile
    return CommunityUserSummary(
        id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        headline=profile.headline if profile else None,
        location=profile.location if profile else None,
        profile_photo_url=_profile_photo_url(profile),
    )


def _membership_for(db: Session, community_id: str, user_id: str) -> CommunityMembership | None:
    return (
        db.query(CommunityMembership)
        .filter(
            CommunityMembership.community_id == community_id,
            CommunityMembership.user_id == user_id,
        )
        .first()
    )


def _require_community(db: Session, community_id: str) -> Community:
    community = db.query(Community).filter(Community.id == community_id).first()
    if community is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Community not found.")
    return community


def _can_view(community: Community, membership: CommunityMembership | None) -> bool:
    return community.visibility == PUBLIC_VISIBILITY or membership is not None


def _empty_reaction_counts() -> dict[str, int]:
    return {reaction_type: 0 for reaction_type in REACTION_TYPES}


def _is_community_owner(
    community: Community,
    current_user_id: str,
    membership: CommunityMembership | None = None,
) -> bool:
    if community.creator_id == current_user_id:
        return True
    return bool(membership and membership.role == OWNER_ROLE)


def _member_count_subquery(db: Session):
    return (
        db.query(
            CommunityMembership.community_id.label("community_id"),
            func.count(CommunityMembership.id).label("member_count"),
        )
        .group_by(CommunityMembership.community_id)
        .subquery()
    )


def _community_response(
    community: Community,
    current_user_id: str,
    member_count: int = 0,
    membership: CommunityMembership | None = None,
) -> CommunityResponse:
    joined = membership is not None
    is_owner = membership.role == OWNER_ROLE if membership else community.creator_id == current_user_id
    return CommunityResponse(
        id=community.id,
        name=community.name,
        description=community.description,
        category=community.category,
        tags=list(community.tags or []),
        visibility=community.visibility,
        creator_id=community.creator_id,
        creator=_user_summary(community.creator),
        member_count=member_count,
        joined=joined,
        is_joined=joined,
        is_owner=is_owner,
        membership_status="joined" if joined else "none",
        created_at=community.created_at,
        updated_at=community.updated_at,
    )


def create_community(
    db: Session,
    current_user: User,
    payload: CommunityCreateRequest,
) -> CommunityResponse:
    community = Community(
        name=payload.name,
        description=payload.description,
        category=payload.category,
        tags=payload.tags,
        visibility=payload.visibility,
        creator_id=current_user.id,
    )
    db.add(community)
    db.flush()

    membership = CommunityMembership(
        community_id=community.id,
        user_id=current_user.id,
        role=OWNER_ROLE,
    )
    db.add(membership)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Community membership already exists.",
        )

    db.refresh(community)
    db.refresh(membership)
    community.creator = current_user
    return _community_response(
        community=community,
        current_user_id=current_user.id,
        member_count=1,
        membership=membership,
    )


def list_communities(
    db: Session,
    current_user: User,
    q: str | None = None,
    category: str | None = None,
    membership: str = "discover",
    limit: int = 20,
    offset: int = 0,
) -> tuple[int, list[CommunityResponse]]:
    count_sq = _member_count_subquery(db)
    my_membership_sq = (
        db.query(
            CommunityMembership.community_id.label("community_id"),
            CommunityMembership.role.label("role"),
        )
        .filter(CommunityMembership.user_id == current_user.id)
        .subquery()
    )

    query = (
        db.query(
            Community,
            func.coalesce(count_sq.c.member_count, 0).label("member_count"),
            my_membership_sq.c.role.label("my_role"),
        )
        .outerjoin(count_sq, count_sq.c.community_id == Community.id)
        .outerjoin(my_membership_sq, my_membership_sq.c.community_id == Community.id)
        .options(joinedload(Community.creator).joinedload(User.profile).joinedload(Profile.profile_photo))
    )

    if membership == "joined":
        query = query.filter(my_membership_sq.c.community_id.isnot(None))
    else:
        query = query.filter(Community.visibility == PUBLIC_VISIBILITY)

    if q and q.strip():
        term = f"%{q.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(Community.name).like(term),
                func.lower(Community.description).like(term),
            )
        )

    if category and category != "all":
        query = query.filter(Community.category == category)

    total = query.count()
    rows = (
        query.order_by(Community.created_at.desc(), Community.name.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    responses: list[CommunityResponse] = []
    for community, member_count, my_role in rows:
        membership_obj = None
        if my_role:
            membership_obj = CommunityMembership(
                community_id=community.id,
                user_id=current_user.id,
                role=my_role,
            )
        responses.append(
            _community_response(
                community=community,
                current_user_id=current_user.id,
                member_count=int(member_count or 0),
                membership=membership_obj,
            )
        )
    return total, responses


def get_community(db: Session, current_user: User, community_id: str) -> CommunityResponse:
    community = (
        db.query(Community)
        .options(joinedload(Community.creator).joinedload(User.profile).joinedload(Profile.profile_photo))
        .filter(Community.id == community_id)
        .first()
    )
    if community is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Community not found.")

    membership = _membership_for(db, community.id, current_user.id)
    if not _can_view(community, membership):
        # Avoid confirming private community existence to non-members.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Community not found.")

    member_count = (
        db.query(func.count(CommunityMembership.id))
        .filter(CommunityMembership.community_id == community.id)
        .scalar()
        or 0
    )
    return _community_response(community, current_user.id, int(member_count), membership)


def join_community(db: Session, current_user: User, community_id: str) -> CommunityMembershipResponse:
    community = _require_community(db, community_id)

    if community.visibility == PRIVATE_VISIBILITY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Private communities are not open to direct joins.",
        )

    existing = _membership_for(db, community.id, current_user.id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You are already a member of this community.",
        )

    membership = CommunityMembership(
        community_id=community.id,
        user_id=current_user.id,
        role=MEMBER_ROLE,
    )
    db.add(membership)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You are already a member of this community.",
        )

    return CommunityMembershipResponse(success=True, community_id=community.id, joined=True)


def leave_community(db: Session, current_user: User, community_id: str) -> CommunityMembershipResponse:
    community = _require_community(db, community_id)
    membership = _membership_for(db, community.id, current_user.id)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Community membership not found.",
        )
    if membership.role == OWNER_ROLE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Community owners cannot leave their community in V1.",
        )

    db.delete(membership)
    db.commit()
    return CommunityMembershipResponse(success=True, community_id=community.id, joined=False)


def _require_view_access(db: Session, community_id: str, current_user: User) -> tuple[Community, CommunityMembership | None]:
    community = _require_community(db, community_id)
    membership = _membership_for(db, community.id, current_user.id)
    if not _can_view(community, membership):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot access this private community.")
    return community, membership


def list_members(
    db: Session,
    current_user: User,
    community_id: str,
    limit: int = 50,
    offset: int = 0,
) -> tuple[int, list[CommunityMemberResponse]]:
    community, _ = _require_view_access(db, community_id, current_user)
    base = (
        db.query(CommunityMembership)
        .join(User, User.id == CommunityMembership.user_id)
        .outerjoin(Profile, Profile.user_id == User.id)
        .options(joinedload(CommunityMembership.user).joinedload(User.profile).joinedload(Profile.profile_photo))
        .filter(CommunityMembership.community_id == community.id)
    )
    total = base.count()
    rows = (
        base.order_by(CommunityMembership.created_at.asc(), User.username.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    members = []
    for membership in rows:
        user = membership.user
        profile = user.profile
        members.append(
            CommunityMemberResponse(
                id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                headline=profile.headline if profile else None,
                location=profile.location if profile else None,
                profile_photo_url=_profile_photo_url(profile),
                role=membership.role,
                joined_at=membership.created_at,
            )
        )
    return total, members


def list_posts(
    db: Session,
    current_user: User,
    community_id: str,
    limit: int = 20,
    offset: int = 0,
) -> tuple[int, list[CommunityPostResponse]]:
    community, _ = _require_view_access(db, community_id, current_user)
    base = (
        db.query(CommunityPost)
        .options(joinedload(CommunityPost.author).joinedload(User.profile).joinedload(Profile.profile_photo))
        .filter(CommunityPost.community_id == community.id)
    )
    total = base.count()
    posts = (
        base.order_by(CommunityPost.created_at.desc(), CommunityPost.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    post_meta = _post_meta_for_posts(db, posts, current_user.id, community)
    return total, [_post_response(post, **post_meta.get(post.id, {})) for post in posts]


def create_post(
    db: Session,
    current_user: User,
    community_id: str,
    payload: CommunityPostCreateRequest,
) -> CommunityPostResponse:
    community = _require_community(db, community_id)
    membership = _membership_for(db, community.id, current_user.id)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only community members can create posts.",
        )

    post = CommunityPost(
        community_id=community.id,
        author_id=current_user.id,
        content=payload.content,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    post.author = current_user
    post.community = community
    return _post_response(
        post,
        reaction_counts=_empty_reaction_counts(),
        total_reactions=0,
        my_reaction=None,
        comment_count=0,
        can_delete=True,
    )


def set_post_reaction(
    db: Session,
    current_user: User,
    post_id: str,
    payload: CommunityReactionRequest,
) -> CommunityReactionSummaryResponse:
    post, _community, _membership = _require_post_access(db, post_id, current_user)
    existing = (
        db.query(CommunityPostReaction)
        .filter(
            CommunityPostReaction.post_id == post.id,
            CommunityPostReaction.user_id == current_user.id,
        )
        .first()
    )

    try:
        if existing is None:
            db.add(
                CommunityPostReaction(
                    post_id=post.id,
                    user_id=current_user.id,
                    reaction_type=payload.reaction_type,
                )
            )
        elif existing.reaction_type == payload.reaction_type:
            db.delete(existing)
        else:
            existing.reaction_type = payload.reaction_type
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(CommunityPostReaction)
            .filter(
                CommunityPostReaction.post_id == post.id,
                CommunityPostReaction.user_id == current_user.id,
            )
            .first()
        )
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Unable to update reaction. Please try again.",
            )
        if existing.reaction_type == payload.reaction_type:
            db.delete(existing)
        else:
            existing.reaction_type = payload.reaction_type
        db.commit()

    return _reaction_summary(db, post.id, current_user.id)


def list_comments(
    db: Session,
    current_user: User,
    post_id: str,
    limit: int = 20,
    offset: int = 0,
) -> tuple[int, list[CommunityPostCommentResponse]]:
    post, _community, _membership = _require_post_access(db, post_id, current_user)
    base = (
        db.query(CommunityPostComment)
        .options(joinedload(CommunityPostComment.author).joinedload(User.profile).joinedload(Profile.profile_photo))
        .filter(CommunityPostComment.post_id == post.id)
    )
    total = base.count()
    comments = (
        base.order_by(CommunityPostComment.created_at.asc(), CommunityPostComment.id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return total, [_comment_response(comment) for comment in comments]


def create_comment(
    db: Session,
    current_user: User,
    post_id: str,
    payload: CommunityPostCommentCreateRequest,
) -> CommunityPostCommentResponse:
    post, _community, _membership = _require_post_access(db, post_id, current_user)
    comment = CommunityPostComment(
        post_id=post.id,
        author_id=current_user.id,
        content=payload.content,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    comment.author = current_user
    return _comment_response(comment)


def delete_post(db: Session, current_user: User, post_id: str) -> CommunityPostDeleteResponse:
    post, community, membership = _require_post_access(db, post_id, current_user)
    if post.author_id != current_user.id and not _is_community_owner(community, current_user.id, membership):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot delete this post.")

    db.query(CommunityPostReaction).filter(CommunityPostReaction.post_id == post.id).delete(synchronize_session=False)
    db.query(CommunityPostComment).filter(CommunityPostComment.post_id == post.id).delete(synchronize_session=False)
    db.delete(post)
    db.commit()
    return CommunityPostDeleteResponse(success=True, post_id=post_id)


def _require_post_access(
    db: Session,
    post_id: str,
    current_user: User,
) -> tuple[CommunityPost, Community, CommunityMembership | None]:
    post = (
        db.query(CommunityPost)
        .options(
            joinedload(CommunityPost.community),
            joinedload(CommunityPost.author).joinedload(User.profile).joinedload(Profile.profile_photo),
        )
        .filter(CommunityPost.id == post_id)
        .first()
    )
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")

    community = post.community
    membership = _membership_for(db, community.id, current_user.id)
    if not _can_view(community, membership):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")
    return post, community, membership


def _post_meta_for_posts(
    db: Session,
    posts: list[CommunityPost],
    current_user_id: str,
    community: Community | None = None,
) -> dict[str, dict]:
    post_ids = [post.id for post in posts]
    if not post_ids:
        return {}

    meta = {
        post_id: {
            "reaction_counts": _empty_reaction_counts(),
            "total_reactions": 0,
            "my_reaction": None,
            "comment_count": 0,
            "can_delete": False,
        }
        for post_id in post_ids
    }

    reaction_rows = (
        db.query(
            CommunityPostReaction.post_id,
            CommunityPostReaction.reaction_type,
            func.count(CommunityPostReaction.id),
        )
        .filter(CommunityPostReaction.post_id.in_(post_ids))
        .group_by(CommunityPostReaction.post_id, CommunityPostReaction.reaction_type)
        .all()
    )
    for post_id, reaction_type, count in reaction_rows:
        if reaction_type in meta[post_id]["reaction_counts"]:
            meta[post_id]["reaction_counts"][reaction_type] = int(count or 0)
            meta[post_id]["total_reactions"] += int(count or 0)

    my_reactions = (
        db.query(CommunityPostReaction.post_id, CommunityPostReaction.reaction_type)
        .filter(
            CommunityPostReaction.post_id.in_(post_ids),
            CommunityPostReaction.user_id == current_user_id,
        )
        .all()
    )
    for post_id, reaction_type in my_reactions:
        meta[post_id]["my_reaction"] = reaction_type

    comment_rows = (
        db.query(CommunityPostComment.post_id, func.count(CommunityPostComment.id))
        .filter(CommunityPostComment.post_id.in_(post_ids))
        .group_by(CommunityPostComment.post_id)
        .all()
    )
    for post_id, count in comment_rows:
        meta[post_id]["comment_count"] = int(count or 0)

    community_owner_ids: dict[str, str] = {}
    if community is not None:
        community_owner_ids[community.id] = community.creator_id
    else:
        community_ids = {post.community_id for post in posts}
        for community_id, creator_id in (
            db.query(Community.id, Community.creator_id)
            .filter(Community.id.in_(community_ids))
            .all()
        ):
            community_owner_ids[community_id] = creator_id

    for post in posts:
        meta[post.id]["can_delete"] = (
            post.author_id == current_user_id
            or community_owner_ids.get(post.community_id) == current_user_id
        )

    return meta


def _reaction_summary(db: Session, post_id: str, current_user_id: str) -> CommunityReactionSummaryResponse:
    counts = _empty_reaction_counts()
    rows = (
        db.query(CommunityPostReaction.reaction_type, func.count(CommunityPostReaction.id))
        .filter(CommunityPostReaction.post_id == post_id)
        .group_by(CommunityPostReaction.reaction_type)
        .all()
    )
    for reaction_type, count in rows:
        if reaction_type in counts:
            counts[reaction_type] = int(count or 0)

    my_reaction = (
        db.query(CommunityPostReaction.reaction_type)
        .filter(
            CommunityPostReaction.post_id == post_id,
            CommunityPostReaction.user_id == current_user_id,
        )
        .scalar()
    )
    return CommunityReactionSummaryResponse(
        post_id=post_id,
        my_reaction=my_reaction,
        counts=counts,
        total=sum(counts.values()),
    )


def _comment_response(comment: CommunityPostComment) -> CommunityPostCommentResponse:
    return CommunityPostCommentResponse(
        id=comment.id,
        post_id=comment.post_id,
        author_id=comment.author_id,
        author=_user_summary(comment.author),
        content=comment.content,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


def _post_response(
    post: CommunityPost,
    reaction_counts: dict[str, int] | None = None,
    total_reactions: int = 0,
    my_reaction: str | None = None,
    comment_count: int = 0,
    can_delete: bool = False,
) -> CommunityPostResponse:
    reaction_counts = reaction_counts or _empty_reaction_counts()
    return CommunityPostResponse(
        id=post.id,
        community_id=post.community_id,
        author_id=post.author_id,
        author=_user_summary(post.author),
        content=post.content,
        like_count=reaction_counts.get("LIKE", 0),
        reaction_counts=reaction_counts,
        total_reactions=total_reactions,
        my_reaction=my_reaction,
        comment_count=comment_count,
        can_delete=can_delete,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )
