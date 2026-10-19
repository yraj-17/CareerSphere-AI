from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db.models import (
    GlobalPost,
    GlobalPostComment,
    GlobalPostLike,
    GlobalPostMedia,
    MediaObject,
    Profile,
    Resource,
    User,
)
from app.schemas.posts import (
    CommentCreateRequest,
    CommentResponse,
    LikeResponse,
    PostAuthorResponse,
    PostCreateRequest,
    PostMediaResponse,
    PostResourceResponse,
    PostResponse,
    PostUpdateRequest,
)
from app.services.storage_service import delete_file, presigned_get_url


def _profile_photo_url(profile: Profile | None) -> str | None:
    if not profile or not profile.profile_photo:
        return None
    try:
        return presigned_get_url(profile.profile_photo.object_key)
    except Exception:
        return None


def _author(user: User) -> PostAuthorResponse:
    profile = user.profile
    return PostAuthorResponse(
        id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        headline=profile.headline if profile else None,
        profile_photo_url=_profile_photo_url(profile),
    )


def _post_query(db: Session):
    return db.query(GlobalPost).options(
        joinedload(GlobalPost.author).joinedload(User.profile).joinedload(Profile.profile_photo),
        joinedload(GlobalPost.resource),
        selectinload(GlobalPost.media).joinedload(GlobalPostMedia.media_object),
    )


def _comment_query(db: Session):
    return db.query(GlobalPostComment).options(
        joinedload(GlobalPostComment.author).joinedload(User.profile).joinedload(Profile.profile_photo),
    )


def _post_or_404(db: Session, post_id: str) -> GlobalPost:
    post = _post_query(db).filter(GlobalPost.id == post_id).first()
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")
    return post


def _resource_or_404(db: Session, resource_id: str | None) -> Resource | None:
    if not resource_id:
        return None
    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if resource is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found.")
    return resource


def _media_for_post(db: Session, current_user: User, media_ids: list[str]) -> list[MediaObject]:
    unique_ids = list(dict.fromkeys(media_ids or []))
    if len(unique_ids) > 4:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You can attach up to 4 images.")
    if not unique_ids:
        return []
    media = db.query(MediaObject).filter(
        MediaObject.id.in_(unique_ids),
        MediaObject.user_id == current_user.id,
        MediaObject.purpose == "post_image",
    ).all()
    if len(media) != len(unique_ids) or any(not (item.content_type or "").lower().startswith("image/") for item in media):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more image attachments are invalid.")
    by_id = {item.id: item for item in media}
    return [by_id[item_id] for item_id in unique_ids]


def _resource_response(resource: Resource | None) -> PostResourceResponse | None:
    if resource is None:
        return None
    resource_type = resource.resource_type.value if hasattr(resource.resource_type, "value") else str(resource.resource_type)
    return PostResourceResponse(
        id=resource.id,
        title=resource.title,
        description=resource.description,
        url=resource.url,
        source_domain=resource.source_domain,
        resource_type=resource_type,
    )


def _post_response(db: Session, post: GlobalPost, current_user: User) -> PostResponse:
    like_count = db.query(func.count(GlobalPostLike.id)).filter(GlobalPostLike.post_id == post.id).scalar() or 0
    comment_count = db.query(func.count(GlobalPostComment.id)).filter(GlobalPostComment.post_id == post.id).scalar() or 0
    liked = db.query(GlobalPostLike.id).filter(
        GlobalPostLike.post_id == post.id,
        GlobalPostLike.user_id == current_user.id,
    ).first() is not None
    media_items = []
    for item in post.media:
        try:
            url = presigned_get_url(item.media_object.object_key) if item.media_object else None
        except Exception:
            url = None
        media_items.append(PostMediaResponse(
            id=item.id,
            url=url,
            content_type=item.media_object.content_type if item.media_object else "image/*",
        ))
    return PostResponse(
        id=post.id,
        content=post.content,
        created_at=post.created_at,
        updated_at=post.updated_at,
        author=_author(post.author),
        media=media_items,
        resource=_resource_response(post.resource),
        like_count=int(like_count),
        comment_count=int(comment_count),
        liked_by_me=liked,
        is_owner=post.author_id == current_user.id,
    )


def list_posts(db: Session, current_user: User, limit: int, offset: int) -> tuple[int, list[PostResponse]]:
    total = db.query(func.count(GlobalPost.id)).scalar() or 0
    posts = (
        _post_query(db)
        .order_by(GlobalPost.created_at.desc(), GlobalPost.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return int(total), [_post_response(db, post, current_user) for post in posts]


def create_post(db: Session, current_user: User, payload: PostCreateRequest) -> PostResponse:
    _resource_or_404(db, payload.resource_id)
    media = _media_for_post(db, current_user, payload.image_media_ids)
    post = GlobalPost(author_id=current_user.id, content=payload.content, resource_id=payload.resource_id)
    db.add(post)
    try:
        db.flush()
        for index, media_object in enumerate(media):
            db.add(GlobalPostMedia(post_id=post.id, media_id=media_object.id, sort_order=index))
        db.commit()
    except Exception:
        db.rollback()
        # Image media is uploaded immediately before post creation. If the
        # relational write fails, remove those unattached objects and metadata
        # so a failed publish cannot leak storage.
        for media_object in media:
            try:
                delete_file(media_object.object_key)
            except Exception:
                pass
        if media:
            try:
                db.query(MediaObject).filter(MediaObject.id.in_([item.id for item in media])).delete(synchronize_session=False)
                db.commit()
            except Exception:
                db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to publish the post.")
    return _post_response(db, _post_or_404(db, post.id), current_user)


def update_post(db: Session, current_user: User, post_id: str, payload: PostUpdateRequest) -> PostResponse:
    post = _post_or_404(db, post_id)
    if post.author_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only edit your own posts.")
    _resource_or_404(db, payload.resource_id)
    post.content = payload.content
    post.resource_id = payload.resource_id
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to update the post.")
    return _post_response(db, _post_or_404(db, post_id), current_user)


def delete_post(db: Session, current_user: User, post_id: str) -> None:
    post = _post_or_404(db, post_id)
    if post.author_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only delete your own posts.")
    media_to_delete = [(item.media_id, item.media_object.object_key if item.media_object else None) for item in post.media]
    media_ids = [media_id for media_id, _ in media_to_delete]
    db.delete(post)
    if media_ids:
        db.query(MediaObject).filter(MediaObject.id.in_(media_ids)).delete(synchronize_session=False)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to delete the post.")
    for _, object_key in media_to_delete:
        if object_key:
            try:
                delete_file(object_key)
            except Exception:
                pass


def like_post(db: Session, current_user: User, post_id: str, liked: bool) -> LikeResponse:
    _post_or_404(db, post_id)
    existing = db.query(GlobalPostLike).filter(
        GlobalPostLike.post_id == post_id,
        GlobalPostLike.user_id == current_user.id,
    ).first()
    if liked and existing is None:
        db.add(GlobalPostLike(post_id=post_id, user_id=current_user.id))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
    elif not liked and existing is not None:
        db.delete(existing)
        db.commit()
    count = db.query(func.count(GlobalPostLike.id)).filter(GlobalPostLike.post_id == post_id).scalar() or 0
    return LikeResponse(post_id=post_id, like_count=int(count), liked_by_me=liked)


def list_comments(db: Session, current_user: User, post_id: str, limit: int, offset: int) -> tuple[int, list[CommentResponse]]:
    _post_or_404(db, post_id)
    total = db.query(func.count(GlobalPostComment.id)).filter(GlobalPostComment.post_id == post_id).scalar() or 0
    comments = (
        _comment_query(db)
        .filter(GlobalPostComment.post_id == post_id)
        .order_by(GlobalPostComment.created_at.asc(), GlobalPostComment.id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return int(total), [CommentResponse(
        id=comment.id,
        post_id=comment.post_id,
        content=comment.content,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        author=_author(comment.author),
        is_owner=comment.author_id == current_user.id,
    ) for comment in comments]


def create_comment(db: Session, current_user: User, post_id: str, payload: CommentCreateRequest) -> CommentResponse:
    _post_or_404(db, post_id)
    comment = GlobalPostComment(post_id=post_id, author_id=current_user.id, content=payload.content)
    db.add(comment)
    try:
        db.commit()
        db.refresh(comment)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to add the comment.")
    comment = _comment_query(db).filter(GlobalPostComment.id == comment.id).first()
    return CommentResponse(
        id=comment.id,
        post_id=comment.post_id,
        content=comment.content,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        author=_author(comment.author),
        is_owner=True,
    )


def update_comment(db: Session, current_user: User, comment_id: str, payload: CommentCreateRequest) -> CommentResponse:
    comment = _comment_query(db).filter(GlobalPostComment.id == comment_id).first()
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found.")
    if comment.author_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only edit your own comments.")
    comment.content = payload.content
    db.commit()
    return CommentResponse(id=comment.id, post_id=comment.post_id, content=comment.content, created_at=comment.created_at, updated_at=comment.updated_at, author=_author(comment.author), is_owner=True)


def delete_comment(db: Session, current_user: User, comment_id: str) -> None:
    comment = db.query(GlobalPostComment).filter(GlobalPostComment.id == comment_id).first()
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found.")
    post = db.query(GlobalPost.author_id).filter(GlobalPost.id == comment.post_id).first()
    if comment.author_id != current_user.id and (not post or post[0] != current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot delete this comment.")
    db.delete(comment)
    db.commit()
