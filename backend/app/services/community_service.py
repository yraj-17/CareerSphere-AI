from __future__ import annotations

import io
import logging
from typing import List

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db.models import (
    Community,
    CommunityMembership,
    CommunityPost,
    CommunityPostComment,
    CommunityPostMedia,
    CommunityPostReaction,
    CommunityPostTag,
    Profile,
    User,
)
from app.schemas.communities import (
    ALLOWED_IMAGE_MIME_TYPES,
    MAX_COMMUNITY_IMAGE_BYTES,
    MAX_POST_IMAGE_BYTES,
    MAX_POST_IMAGES,
    MAX_POST_TAGS,
    CommunityCreateRequest,
    CommunityImageUpdateResponse,
    CommunityMemberResponse,
    CommunityMembershipResponse,
    CommunityPostCommentCreateRequest,
    CommunityPostCommentResponse,
    CommunityPostCreateRequest,
    CommunityPostDeleteResponse,
    CommunityPostMediaResponse,
    CommunityPostResponse,
    CommunityReactionRequest,
    CommunityReactionSummaryResponse,
    CommunityResponse,
    CommunityUserSummary,
    clean_post_tags,
)
from app.services.storage_service import (
    build_object_key,
    delete_file,
    presigned_get_url,
    upload_bytes,
)

logger = logging.getLogger(__name__)

OWNER_ROLE = "owner"
MEMBER_ROLE = "member"
PUBLIC_VISIBILITY = "public"
PRIVATE_VISIBILITY = "private"
REACTION_TYPES = ("LIKE", "LOVE", "CELEBRATE", "SUPPORT", "INSIGHTFUL", "FUNNY")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _profile_photo_url(profile: Profile | None) -> str | None:
    if not profile or not profile.profile_photo:
        return None
    try:
        return presigned_get_url(profile.profile_photo.object_key)
    except Exception:
        return None


def _community_image_url(community: Community) -> str | None:
    if not community.image_key:
        return None
    try:
        return presigned_get_url(community.image_key)
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
        image_url=_community_image_url(community),
        created_at=community.created_at,
        updated_at=community.updated_at,
    )


# ---------------------------------------------------------------------------
# Image validation helper (reused for community photo and post images)
# ---------------------------------------------------------------------------

def _validate_image(payload: bytes, content_type: str, max_bytes: int) -> None:
    """Validate image MIME type and size. Raises HTTPException on failure."""
    ct = (content_type or "").lower().split(";")[0].strip()
    if ct not in ALLOWED_IMAGE_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported image type '{ct}'. Allowed: jpeg, png, webp.",
        )
    if len(payload) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image exceeds the {max_bytes // (1024 * 1024)} MB limit.",
        )
    if not payload:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file.")


# ---------------------------------------------------------------------------
# Community CRUD
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Community photo management
# ---------------------------------------------------------------------------

async def update_community_image(
    db: Session,
    current_user: User,
    community_id: str,
    file: UploadFile | None,
    remove: bool = False,
) -> CommunityImageUpdateResponse:
    """Upload, change, or remove a community profile photo."""
    community = _require_community(db, community_id)
    membership = _membership_for(db, community.id, current_user.id)
    if not _is_community_owner(community, current_user.id, membership):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the community owner can change the community photo.",
        )

    old_key = community.image_key

    if remove:
        # Remove the photo
        community.image_key = None
        db.commit()
        if old_key:
            try:
                delete_file(old_key)
            except Exception:
                logger.warning("Failed to delete old community image from MinIO: %s", old_key)
        return CommunityImageUpdateResponse(
            success=True, community_id=community_id, image_url=None
        )

    if file is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided.",
        )

    payload = await file.read()
    content_type = file.content_type or ""
    _validate_image(payload, content_type, MAX_COMMUNITY_IMAGE_BYTES)

    filename = file.filename or "community_photo.jpg"
    object_key = build_object_key(current_user.id, "community_image", filename)

    try:
        upload_bytes(
            object_key=object_key,
            payload=payload,
            content_type=content_type,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Object storage unavailable. ({exc})",
        )

    community.image_key = object_key
    try:
        db.commit()
    except Exception:
        db.rollback()
        try:
            delete_file(object_key)
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update community image.",
        )

    # Clean up old image after successful DB commit
    if old_key and old_key != object_key:
        try:
            delete_file(old_key)
        except Exception:
            logger.warning("Failed to delete old community image from MinIO: %s", old_key)

    image_url = presigned_get_url(object_key)
    return CommunityImageUpdateResponse(
        success=True, community_id=community_id, image_url=image_url
    )


# ---------------------------------------------------------------------------
# Posts
# ---------------------------------------------------------------------------

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
        .options(
            joinedload(CommunityPost.author).joinedload(User.profile).joinedload(Profile.profile_photo),
            selectinload(CommunityPost.media),
            selectinload(CommunityPost.post_tags),
        )
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


async def create_post(
    db: Session,
    current_user: User,
    community_id: str,
    content: str,
    tags: list[str],
    images: list[UploadFile],
) -> CommunityPostResponse:
    """Create a community post with optional images and topic tags."""
    community = _require_community(db, community_id)
    membership = _membership_for(db, community.id, current_user.id)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only community members can create posts.",
        )

    # Validate: at least content or at least one image
    content = (content or "").strip()
    if not content and not images:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A post must have content text or at least one image.",
        )

    # Validate image count
    if len(images) > MAX_POST_IMAGES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"A post may have at most {MAX_POST_IMAGES} images.",
        )

    # Validate and read images upfront before touching the DB
    validated_images: list[tuple[bytes, str, str]] = []  # (payload, content_type, filename)
    for img in images:
        payload = await img.read()
        ct = img.content_type or ""
        _validate_image(payload, ct, MAX_POST_IMAGE_BYTES)
        validated_images.append((payload, ct, img.filename or "post_image.jpg"))

    # Validate tags (raises HTTPException on invalid input)
    try:
        cleaned_tags = clean_post_tags(tags)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    if len(cleaned_tags) > MAX_POST_TAGS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"A post may have at most {MAX_POST_TAGS} topic tags.",
        )

    # Create the post record
    post = CommunityPost(
        community_id=community.id,
        author_id=current_user.id,
        content=content,
    )
    db.add(post)
    db.flush()  # Get post.id without committing

    # ── Phase 1: Upload all images to MinIO ──────────────────────────────────
    # We upload first so we have the object_keys, then do all DB inserts in one
    # pass.  This means any MinIO failure aborts before we touch the DB further.
    # Keys collected here are the ONLY ones eligible for cleanup if a later step
    # fails — we never touch pre-existing community or post images.
    uploaded_keys: list[str] = []          # MinIO keys created this request
    upload_results: list[tuple[str, str]]  # (object_key, presigned_url)
    upload_results = []

    if validated_images:
        try:
            for payload, ct, filename in validated_images:
                object_key = build_object_key(current_user.id, "post_image", filename)
                upload_bytes(object_key=object_key, payload=payload, content_type=ct)
                uploaded_keys.append(object_key)
                upload_results.append((object_key, presigned_get_url(object_key)))
        except Exception as exc:
            # MinIO / storage failure — roll back the post flush and clean up
            # any objects that were successfully uploaded before the failure.
            db.rollback()
            for key in uploaded_keys:
                try:
                    delete_file(key)
                except Exception:
                    logger.warning("Failed to clean up MinIO object after upload error: %s", key)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Image upload failed: object storage is unavailable.",
            )

    # ── Phase 2: Insert media metadata rows with integer sort_order ──────────
    # sort_order is always assigned by the backend from the upload index —
    # the frontend never sends it and it is always a Python int.
    media_responses: list[CommunityPostMediaResponse] = []
    try:
        for sort_order, (object_key, url) in enumerate(upload_results):
            media_obj = CommunityPostMedia(
                post_id=post.id,
                object_key=object_key,
                media_type="image",
                sort_order=sort_order,   # int — matches INTEGER column in PostgreSQL
            )
            db.add(media_obj)
            db.flush()
            media_responses.append(
                CommunityPostMediaResponse(
                    id=media_obj.id,
                    url=url,
                    media_type="image",
                    sort_order=sort_order,
                )
            )
    except Exception as exc:
        # DB failure after successful MinIO uploads — roll back and clean up
        # only the objects we just uploaded (never touch anything pre-existing).
        db.rollback()
        for key in uploaded_keys:
            try:
                delete_file(key)
            except Exception:
                logger.warning("Failed to clean up MinIO object after DB error: %s", key)
        logger.error("Failed to persist post media metadata: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save post media. The post was not created.",
        )

    # ── Phase 3: Insert tag rows ──────────────────────────────────────────────
    for tag in cleaned_tags:
        db.add(CommunityPostTag(
            post_id=post.id,
            tag=tag,
            tag_normalized=tag.lower(),
        ))

    # ── Phase 4: Commit ───────────────────────────────────────────────────────
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        for key in uploaded_keys:
            try:
                delete_file(key)
            except Exception:
                logger.warning("Failed to clean up MinIO object after commit error: %s", key)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate tag detected. Each tag must be unique per post.",
        )

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
        media_items=media_responses,
        tag_names=cleaned_tags,
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

    # Collect MinIO object keys before deleting DB records
    media_objects = (
        db.query(CommunityPostMedia)
        .filter(CommunityPostMedia.post_id == post.id)
        .all()
    )
    object_keys = [m.object_key for m in media_objects]

    # Delete child records (cascade handles reactions/comments/media/tags,
    # but we delete reactions and comments explicitly for clarity)
    db.query(CommunityPostReaction).filter(CommunityPostReaction.post_id == post.id).delete(synchronize_session=False)
    db.query(CommunityPostComment).filter(CommunityPostComment.post_id == post.id).delete(synchronize_session=False)
    db.query(CommunityPostMedia).filter(CommunityPostMedia.post_id == post.id).delete(synchronize_session=False)
    db.query(CommunityPostTag).filter(CommunityPostTag.post_id == post.id).delete(synchronize_session=False)
    db.delete(post)
    db.commit()

    # Clean up MinIO objects after successful DB commit
    for key in object_keys:
        try:
            delete_file(key)
        except Exception:
            logger.warning("Failed to delete post image from MinIO: %s", key)

    return CommunityPostDeleteResponse(success=True, post_id=post_id)


# ---------------------------------------------------------------------------
# Internal helpers (post access / meta / response builders)
# ---------------------------------------------------------------------------

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
            "media_items": [],
            "tag_names": [],
        }
        for post_id in post_ids
    }

    # Reactions
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

    # Comments count
    comment_rows = (
        db.query(CommunityPostComment.post_id, func.count(CommunityPostComment.id))
        .filter(CommunityPostComment.post_id.in_(post_ids))
        .group_by(CommunityPostComment.post_id)
        .all()
    )
    for post_id, count in comment_rows:
        meta[post_id]["comment_count"] = int(count or 0)

    # Delete permission
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

    # Media — batch load
    media_rows = (
        db.query(CommunityPostMedia)
        .filter(CommunityPostMedia.post_id.in_(post_ids))
        .order_by(CommunityPostMedia.post_id, CommunityPostMedia.sort_order)
        .all()
    )
    for m in media_rows:
        try:
            url = presigned_get_url(m.object_key)
        except Exception:
            url = ""
        meta[m.post_id]["media_items"].append(
            CommunityPostMediaResponse(
                id=m.id,
                url=url,
                media_type=m.media_type or "image",
                sort_order=m.sort_order,  # Integer column — no cast needed
            )
        )

    # Tags — batch load
    tag_rows = (
        db.query(CommunityPostTag)
        .filter(CommunityPostTag.post_id.in_(post_ids))
        .order_by(CommunityPostTag.post_id, CommunityPostTag.created_at)
        .all()
    )
    for t in tag_rows:
        meta[t.post_id]["tag_names"].append(t.tag)

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
    media_items: list[CommunityPostMediaResponse] | None = None,
    tag_names: list[str] | None = None,
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
        media=media_items or [],
        tags=tag_names or [],
        created_at=post.created_at,
        updated_at=post.updated_at,
    )
