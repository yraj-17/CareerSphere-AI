"""
Networking v1 — REST API router.

Architecture:
    JWT → authenticated current_user → this router → connection_service → PostgreSQL

All endpoints require authentication. The current authenticated user's identity
is derived exclusively from the JWT — the frontend cannot supply or override it.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload, selectinload

from app.api.deps import get_current_user, get_db
from app.db.models import Connection, Profile, ProfileProject, User
from app.schemas.networking import (
    ConnectionResponse,
    ConnectionStatusResponse,
    EnrichedConnectionResponse,
    ConnectionUserSummary,
    NetworkingUserResponse,
    PaginatedUsersResponse,
    PublicProfileResponse,
    PublicUserSummary,
    PublicSkillResponse,
    PublicEducationResponse,
    PublicExperienceResponse,
    PublicProjectResponse,
    PublicCertificationResponse,
)
from app.services import connection_service as svc
from app.services.storage_service import presigned_get_url

router = APIRouter(prefix="/networking", tags=["Networking"])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _connection_response(conn: Connection) -> ConnectionResponse:
    return ConnectionResponse(
        id=conn.id,
        requester_id=conn.requester_id,
        receiver_id=conn.receiver_id,
        status=conn.status.value,
        created_at=conn.created_at,
        updated_at=conn.updated_at,
    )


def _get_connection_or_404(db: Session, connection_id: str) -> Connection:
    conn = db.query(Connection).filter(Connection.id == connection_id).first()
    if conn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found.",
        )
    return conn


def _get_user_or_404(db: Session, user_id: str) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    return user


def _profile_photo_url(profile: Optional[Profile]) -> Optional[str]:
    """Return a presigned MinIO URL for the profile photo, or None."""
    if not profile or not profile.profile_photo:
        return None
    try:
        return presigned_get_url(profile.profile_photo.object_key)
    except Exception:
        return None


def _build_user_response(
    user: User,
    connection_status: str,
    profile: Optional[Profile] = None,
) -> NetworkingUserResponse:
    headline = profile.headline if profile else None
    location = profile.location if profile else None
    photo_url = _profile_photo_url(profile)
    return NetworkingUserResponse(
        id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        headline=headline,
        location=location,
        profile_photo_url=photo_url,
        connection_status=connection_status,
    )


# ---------------------------------------------------------------------------
# POST /networking/connections/{user_id}
# Send a connection request
# ---------------------------------------------------------------------------


@router.post(
    "/connections/{user_id}",
    response_model=ConnectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send a connection request to another user",
)
def send_connection_request(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConnectionResponse:
    """
    Send a connection request from the authenticated user to ``user_id``.

    - 400 if the target is the authenticated user themselves.
    - 404 if the target user does not exist.
    - 409 if a connection already exists (any status).
    """
    receiver = _get_user_or_404(db, user_id)
    conn = svc.send_connection_request(db, current_user, receiver)
    return _connection_response(conn)


# ---------------------------------------------------------------------------
# GET /networking/connections
# List accepted connections
# ---------------------------------------------------------------------------


@router.get(
    "/connections",
    response_model=list[ConnectionResponse],
    summary="Get the authenticated user's accepted connections",
)
def get_my_connections(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ConnectionResponse]:
    """Return all accepted connections where the current user is either party."""
    connections = svc.get_accepted_connections(db, current_user)
    return [_connection_response(c) for c in connections]


# ---------------------------------------------------------------------------
# GET /networking/requests/incoming
# Incoming pending requests
# ---------------------------------------------------------------------------


@router.get(
    "/requests/incoming",
    response_model=list[ConnectionResponse],
    summary="Get incoming pending connection requests",
)
def get_incoming_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ConnectionResponse]:
    """Return pending requests where the authenticated user is the receiver."""
    requests = svc.get_pending_requests_for_user(db, current_user)
    return [_connection_response(r) for r in requests]


# ---------------------------------------------------------------------------
# GET /networking/requests/outgoing
# Outgoing pending requests
# ---------------------------------------------------------------------------


@router.get(
    "/requests/outgoing",
    response_model=list[ConnectionResponse],
    summary="Get outgoing pending connection requests",
)
def get_outgoing_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ConnectionResponse]:
    """Return pending requests that the authenticated user has sent."""
    requests = svc.get_sent_pending_requests(db, current_user)
    return [_connection_response(r) for r in requests]


# ---------------------------------------------------------------------------
# POST /networking/requests/{connection_id}/accept
# Accept a pending request
# ---------------------------------------------------------------------------


@router.post(
    "/requests/{connection_id}/accept",
    response_model=ConnectionResponse,
    summary="Accept a pending connection request",
)
def accept_request(
    connection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConnectionResponse:
    """
    Accept a pending connection request.

    - 403 if the authenticated user is not the receiver.
    - 404 if the connection does not exist.
    - 422 if the connection is not pending.
    """
    conn = _get_connection_or_404(db, connection_id)
    updated = svc.accept_connection_request(db, conn, current_user)
    return _connection_response(updated)


# ---------------------------------------------------------------------------
# POST /networking/requests/{connection_id}/reject
# Reject a pending request
# ---------------------------------------------------------------------------


@router.post(
    "/requests/{connection_id}/reject",
    response_model=ConnectionResponse,
    summary="Reject a pending connection request",
)
def reject_request(
    connection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConnectionResponse:
    """
    Reject a pending connection request.

    - 403 if the authenticated user is not the receiver.
    - 404 if the connection does not exist.
    - 422 if the connection is not pending.
    """
    conn = _get_connection_or_404(db, connection_id)
    updated = svc.reject_connection_request(db, conn, current_user)
    return _connection_response(updated)


# ---------------------------------------------------------------------------
# POST /networking/requests/{connection_id}/cancel
# Cancel an outgoing pending request
# ---------------------------------------------------------------------------


@router.post(
    "/requests/{connection_id}/cancel",
    response_model=ConnectionResponse,
    summary="Cancel a pending connection request you sent",
)
def cancel_request(
    connection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConnectionResponse:
    """
    Cancel a pending connection request.

    - 403 if the authenticated user is not the original requester.
    - 404 if the connection does not exist.
    - 422 if the connection is not pending.
    """
    conn = _get_connection_or_404(db, connection_id)
    updated = svc.cancel_connection_request(db, conn, current_user)
    return _connection_response(updated)


# ---------------------------------------------------------------------------
# DELETE /networking/connections/{connection_id}
# Remove an accepted connection
# ---------------------------------------------------------------------------


@router.delete(
    "/connections/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove an accepted connection",
)
def remove_connection(
    connection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """
    Permanently delete an accepted connection.

    Either party may remove the connection.

    - 403 if the authenticated user is not a participant.
    - 404 if the connection does not exist.
    - 422 if the connection is not accepted.
    """
    conn = _get_connection_or_404(db, connection_id)
    svc.remove_connection(db, conn, current_user)


# ---------------------------------------------------------------------------
# GET /networking/users/{user_id}/connection
# Direction-independent relationship check
# ---------------------------------------------------------------------------


@router.get(
    "/users/{user_id}/connection",
    response_model=ConnectionStatusResponse,
    summary="Check the connection status between the current user and another user",
)
def get_connection_status(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConnectionStatusResponse:
    """
    Return the current relationship between the authenticated user and ``user_id``.

    - When no relationship exists, ``status`` is ``"none"``.
    - The result is the same regardless of who sent the original request.
    - Looking up your own ID returns ``status: "none"`` (no self-connections exist).
    """
    # Ensure target user exists (returns 404 on unknown ID)
    _get_user_or_404(db, user_id)

    conn = svc.get_connection_between_users(db, current_user.id, user_id)
    if conn is None:
        return ConnectionStatusResponse(status="none")

    return ConnectionStatusResponse(
        status=conn.status.value,
        connection_id=conn.id,
        requester_id=conn.requester_id,
        receiver_id=conn.receiver_id,
        created_at=conn.created_at,
        updated_at=conn.updated_at,
    )


# ---------------------------------------------------------------------------
# GET /networking/users
# People discovery
# ---------------------------------------------------------------------------

_DISCOVERY_LIMIT_MAX = 50


@router.get(
    "/users",
    response_model=PaginatedUsersResponse,
    summary="Discover other users (people search)",
)
def discover_users(
    q: Optional[str] = Query(None, description="Search by username or full name"),
    limit: int = Query(20, ge=1, le=_DISCOVERY_LIMIT_MAX, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedUsersResponse:
    """
    Simple people discovery.

    - Excludes the authenticated user from results.
    - Optionally filters by ``?q=`` (case-insensitive username or full-name match).
    - Returns profile basics + connection status for each user.
    - No AI, no vector search, no recommendations.
    """
    # Base query: all users except the current user, with their profile eagerly loaded
    query = (
        db.query(User)
        .outerjoin(Profile, Profile.user_id == User.id)
        .options(
            joinedload(User.profile).joinedload(Profile.profile_photo)
        )
        .filter(User.id != current_user.id)
    )

    if q and q.strip():
        term = f"%{q.strip().lower()}%"
        query = query.filter(
            (User.username.ilike(term))
            | (User.first_name.ilike(term))
            | (User.last_name.ilike(term))
        )

    total = query.count()
    users = query.order_by(User.username.asc()).offset(offset).limit(limit).all()

    # Build connection-status map for the returned users in one pass
    # (avoids N+1: one query per returned user)
    user_ids = [u.id for u in users]
    conn_map: dict[str, str] = {}
    if user_ids:
        ca_vals, cb_vals = zip(
            *[Connection.canonical_pair(current_user.id, uid) for uid in user_ids]
        )
        rows = (
            db.query(Connection)
            .filter(
                Connection.canonical_a.in_(ca_vals),
                Connection.canonical_b.in_(cb_vals),
            )
            .all()
        )
        # Index by canonical pair so we can look up per-user
        pair_to_status: dict[tuple[str, str], str] = {
            (c.canonical_a, c.canonical_b): c.status.value for c in rows
        }
        for uid in user_ids:
            ca, cb = Connection.canonical_pair(current_user.id, uid)
            conn_map[uid] = pair_to_status.get((ca, cb), "none")

    result_users = []
    for user in users:
        profile: Optional[Profile] = user.profile  # loaded via joinedload
        result_users.append(
            _build_user_response(
                user=user,
                connection_status=conn_map.get(user.id, "none"),
                profile=profile,
            )
        )

    return PaginatedUsersResponse(
        total=total,
        limit=limit,
        offset=offset,
        users=result_users,
    )


# ---------------------------------------------------------------------------
# Enrichment helper — builds EnrichedConnectionResponse
# ---------------------------------------------------------------------------


def _build_other_user_summary(
    conn: Connection,
    current_user_id: str,
    db: Session,
) -> EnrichedConnectionResponse:
    """
    Determine the 'other' user for a connection row (the one who is NOT
    the current user), load their profile, and return the enriched schema.
    """
    other_id = conn.receiver_id if conn.requester_id == current_user_id else conn.requester_id
    other_user = db.query(User).filter(User.id == other_id).first()

    if other_user is None:
        # Defensive: user deleted after connection was formed
        summary = ConnectionUserSummary(
            id=other_id,
            username="unknown",
            first_name="Deleted",
            last_name="User",
        )
    else:
        profile = other_user.profile
        summary = ConnectionUserSummary(
            id=other_user.id,
            username=other_user.username,
            first_name=other_user.first_name,
            last_name=other_user.last_name,
            headline=profile.headline if profile else None,
            location=profile.location if profile else None,
            profile_photo_url=_profile_photo_url(profile) if profile else None,
        )

    return EnrichedConnectionResponse(
        id=conn.id,
        requester_id=conn.requester_id,
        receiver_id=conn.receiver_id,
        status=conn.status.value,
        created_at=conn.created_at,
        updated_at=conn.updated_at,
        other_user=summary,
    )


# ---------------------------------------------------------------------------
# GET /networking/my-network/connections
# Enriched accepted connections (My Network page)
# ---------------------------------------------------------------------------


@router.get(
    "/my-network/connections",
    response_model=list[EnrichedConnectionResponse],
    summary="Get accepted connections with user details (My Network page)",
)
def get_my_network_connections(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[EnrichedConnectionResponse]:
    """
    Returns accepted connections enriched with the other user's public profile
    details so the My Network page can render cards without extra requests.
    """
    connections = svc.get_accepted_connections(db, current_user)
    return [
        _build_other_user_summary(c, current_user.id, db)
        for c in connections
    ]


# ---------------------------------------------------------------------------
# GET /networking/my-network/requests/incoming
# Enriched incoming pending requests (My Network page)
# ---------------------------------------------------------------------------


@router.get(
    "/my-network/requests/incoming",
    response_model=list[EnrichedConnectionResponse],
    summary="Get incoming pending requests with user details (My Network page)",
)
def get_my_network_incoming(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[EnrichedConnectionResponse]:
    """Returns incoming pending requests enriched with the requester's profile details."""
    requests = svc.get_pending_requests_for_user(db, current_user)
    return [
        _build_other_user_summary(r, current_user.id, db)
        for r in requests
    ]


# ---------------------------------------------------------------------------
# GET /networking/my-network/requests/outgoing
# Enriched outgoing pending requests (My Network page)
# ---------------------------------------------------------------------------


@router.get(
    "/my-network/requests/outgoing",
    response_model=list[EnrichedConnectionResponse],
    summary="Get outgoing pending requests with user details (My Network page)",
)
def get_my_network_outgoing(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[EnrichedConnectionResponse]:
    """Returns outgoing pending requests enriched with the receiver's profile details."""
    requests = svc.get_sent_pending_requests(db, current_user)
    return [
        _build_other_user_summary(r, current_user.id, db)
        for r in requests
    ]

# ---------------------------------------------------------------------------
# GET /networking/users/{user_id}/profile
# Public professional profile view
# ---------------------------------------------------------------------------


def _public_project_response(project: ProfileProject) -> PublicProjectResponse:
    return PublicProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        technologies=[t.name for t in project.technologies],
        github_url=str(project.github_url) if project.github_url else None,
        live_url=str(project.live_url) if project.live_url else None,
        start_date=project.start_date.isoformat() if project.start_date else None,
        end_date=project.end_date.isoformat() if project.end_date else None,
    )


def _public_profile_response(user: User, profile: Optional[Profile]) -> PublicProfileResponse:
    """
    Build a PublicProfileResponse from user + optional profile.

    Intentionally omits: email, password_hash, career_preferences,
    completeness, profile_photo_media_id, and any auth/session fields.
    """
    public_user = PublicUserSummary(
        id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )

    if profile is None:
        return PublicProfileResponse(user=public_user)

    photo_url = _profile_photo_url(profile)

    skills = [
        PublicSkillResponse(id=s.id, name=s.name)
        for s in (profile.skills or [])
    ]
    education = [
        PublicEducationResponse(
            id=e.id,
            institution=e.institution,
            degree=e.degree,
            field_of_study=e.field_of_study,
            start_date=e.start_date.isoformat() if e.start_date else None,
            end_date=e.end_date.isoformat() if e.end_date else None,
            description=e.description,
        )
        for e in (profile.education or [])
    ]
    experience = [
        PublicExperienceResponse(
            id=ex.id,
            company=ex.company,
            job_title=ex.job_title,
            employment_type=ex.employment_type,
            location=ex.location,
            start_date=ex.start_date.isoformat() if ex.start_date else None,
            end_date=ex.end_date.isoformat() if ex.end_date else None,
            currently_working=ex.currently_working,
            description=ex.description,
        )
        for ex in (profile.experience or [])
    ]
    projects = [_public_project_response(p) for p in (profile.projects or [])]
    certifications = [
        PublicCertificationResponse(
            id=c.id,
            name=c.name,
            issuing_organization=c.issuing_organization,
            issue_date=c.issue_date.isoformat() if c.issue_date else None,
            expiration_date=c.expiration_date.isoformat() if c.expiration_date else None,
            credential_url=str(c.credential_url) if c.credential_url else None,
        )
        for c in (profile.certifications or [])
    ]

    return PublicProfileResponse(
        user=public_user,
        headline=profile.headline,
        location=profile.location,
        about=profile.about,
        profile_photo_url=photo_url,
        skills=skills,
        experience=experience,
        education=education,
        projects=projects,
        certifications=certifications,
    )


@router.get(
    "/users/{user_id}/profile",
    response_model=PublicProfileResponse,
    summary="View another user's public professional profile",
)
def get_user_public_profile(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PublicProfileResponse:
    """
    Return the public professional profile of the user identified by ``user_id``.

    - Requires authentication (JWT). The viewer's identity comes from the token.
    - Returns 404 if the user does not exist.
    - If the user exists but has no profile, returns the user basics with empty sections.
    - Never exposes email, password_hash, career_preferences, or internal fields.
    """
    # Resolve the target user
    target_user = db.query(User).filter(User.id == user_id).first()
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    # Load profile with all relationships eagerly — returns None if no profile yet
    profile = (
        db.query(Profile)
        .options(
            selectinload(Profile.profile_photo),
            selectinload(Profile.skills),
            selectinload(Profile.education),
            selectinload(Profile.experience),
            selectinload(Profile.projects).selectinload(ProfileProject.technologies),
            selectinload(Profile.certifications),
        )
        .filter(Profile.user_id == user_id)
        .first()
    )

    return _public_profile_response(target_user, profile)
