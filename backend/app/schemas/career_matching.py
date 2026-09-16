"""Schemas for deterministic career opportunity matching."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class SkillMatchSummary(BaseModel):
    matched: List[str] = []
    missing: List[str] = []


class TargetRoleMatch(BaseModel):
    user_target_roles: List[str] = []
    opportunity_target_role: str
    relationship: str
    score: float


class ExperienceMatch(BaseModel):
    user_level: str
    opportunity_level: Optional[str] = None
    relationship: str
    score: float


class LocationMatch(BaseModel):
    profile_location: Optional[str] = None
    preferred_locations: List[str] = []
    preferred_work_type: Optional[str] = None
    opportunity_location: Optional[str] = None
    opportunity_is_remote: bool
    relationship: str
    score: float


class PreferenceMatchItem(BaseModel):
    dimension: str
    expected: str
    actual: str
    matched: bool
    score: float


class CareerMatchBreakdown(BaseModel):
    required_skill_score: float
    preferred_skill_score: float
    target_role_score: float
    experience_score: float
    location_remote_score: float
    career_preference_score: float
    matched_required_skills: List[str]
    missing_required_skills: List[str]
    matched_preferred_skills: List[str]
    missing_preferred_skills: List[str]
    target_role_match: TargetRoleMatch
    experience_match: ExperienceMatch
    location_match: LocationMatch
    preference_matches: List[PreferenceMatchItem]


class CareerMatchResult(BaseModel):
    opportunity_id: str
    title: str
    company: str
    final_score: float
    breakdown: CareerMatchBreakdown


class CareerMatchingResponse(BaseModel):
    profile_id: str
    candidates_considered: int
    candidates_after_filters: int
    results: List[CareerMatchResult]
