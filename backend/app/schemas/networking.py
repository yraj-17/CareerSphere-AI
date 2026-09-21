"""
Networking v1 — Pydantic response schemas.

These schemas define the API contract for all networking endpoints.
No SQLAlchemy objects are returned directly from the router — all
responses go through one of these models.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# User summary — safe public subset, no sensitive fields
# ---------------------------------------------------------------------------


class NetworkingUserSummary(BaseModel):
    """Minimal public user info returned as part of connection responses."""

    id: str
    username: str
    first_name: str
    last_name: str

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Connection response
# ---------------------------------------------------------------------------


class ConnectionResponse(BaseModel):
    """
    A single connection row as returned by the API.

    Fields:
        id              — connection row UUID
        requester       — user who sent the request
        receiver        — user who received the request
        status          — pending / accepted / rejected / cancelled
        created_at      — when the request was sent
        updated_at      — when the status last changed
    """

    id: str
    requester_id: str
    receiver_id: str
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Connection status check — GET /users/{user_id}/connection
# ---------------------------------------------------------------------------


class ConnectionStatusResponse(BaseModel):
    """
    Response for the direction-independent relationship check endpoint.

    When no relationship exists, ``status`` is ``"none"`` and all
    other fields are ``None``.
    """

    status: str  # "none" | "pending" | "accepted" | "rejected" | "cancelled"
    connection_id: Optional[str] = None
    requester_id: Optional[str] = None
    receiver_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# People discovery — GET /users
# ---------------------------------------------------------------------------


class NetworkingUserResponse(BaseModel):
    """
    A discovered user returned by the people-discovery endpoint.

    Includes enough info for the frontend to render a people card:
    profile basics + current connection status with the authenticated user.
    Never exposes passwords, hashes, or internal auth fields.
    """

    id: str
    username: str
    first_name: str
    last_name: str
    headline: Optional[str] = None
    location: Optional[str] = None
    profile_photo_url: Optional[str] = None
    connection_status: str  # "none" | "pending" | "accepted" | "rejected" | "cancelled"


class PaginatedUsersResponse(BaseModel):
    """Paginated wrapper for the people-discovery endpoint."""

    total: int
    limit: int
    offset: int
    users: list[NetworkingUserResponse]


# ---------------------------------------------------------------------------
# Enriched connection response — includes user details for My Network page
# ---------------------------------------------------------------------------


class ConnectionUserSummary(BaseModel):
    """Public user details embedded in an enriched connection response."""

    id: str
    username: str
    first_name: str
    last_name: str
    headline: Optional[str] = None
    location: Optional[str] = None
    profile_photo_url: Optional[str] = None

    model_config = {"from_attributes": True}


class EnrichedConnectionResponse(BaseModel):
    """
    Connection row enriched with public details of the *other* user.

    Used by the My Network page so the frontend doesn't need per-user
    secondary requests to display names, headlines, and avatars.
    """

    id: str
    requester_id: str
    receiver_id: str
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    other_user: ConnectionUserSummary


# ---------------------------------------------------------------------------
# Public profile view — GET /networking/users/{user_id}/profile
# ---------------------------------------------------------------------------


class PublicUserSummary(BaseModel):
    """Safe public user identity — no email, no auth fields."""

    id: str
    username: str
    first_name: str
    last_name: str

    model_config = {"from_attributes": True}


class PublicSkillResponse(BaseModel):
    id: str
    name: str

    model_config = {"from_attributes": True}


class PublicEducationResponse(BaseModel):
    id: str
    institution: str
    degree: str
    field_of_study: Optional[str] = None
    start_date: Optional[str] = None   # ISO date string
    end_date: Optional[str] = None
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class PublicExperienceResponse(BaseModel):
    id: str
    company: str
    job_title: str
    employment_type: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    currently_working: bool = False
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class PublicProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    technologies: list[str] = []
    github_url: Optional[str] = None
    live_url: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None

    model_config = {"from_attributes": True}


class PublicCertificationResponse(BaseModel):
    id: str
    name: str
    issuing_organization: str
    issue_date: Optional[str] = None
    expiration_date: Optional[str] = None
    credential_url: Optional[str] = None

    model_config = {"from_attributes": True}


class PublicProfileResponse(BaseModel):
    """
    Safe public professional profile.

    Intentionally excludes:
      - email / password_hash / any auth fields
      - career_preferences (private intent data)
      - completeness metrics (internal)
      - profile_photo_media_id (internal FK)
    """

    user: PublicUserSummary
    headline: Optional[str] = None
    location: Optional[str] = None
    about: Optional[str] = None
    profile_photo_url: Optional[str] = None
    skills: list[PublicSkillResponse] = []
    experience: list[PublicExperienceResponse] = []
    education: list[PublicEducationResponse] = []
    projects: list[PublicProjectResponse] = []
    certifications: list[PublicCertificationResponse] = []
