"""Career Matching API schemas (real job listings)."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel

from app.schemas.career_matching import CareerMatchBreakdown
from app.schemas.gemini_reranking import GeminiConfidence, GeminiStatus


QwenStatus = Literal["success", "unavailable", "skipped"]

CareerMatchingStatus = Literal[
    "success",               # matches found
    "no_profile",            # the user has no profile yet
    "incomplete_profile",    # neither a target role nor any skills
    "no_jobs_available",     # providers configured/OK, but no active listings stored
    "provider_error",        # no active listings and the latest provider sync failed
    "no_relevant_matches",   # listings exist, none relevant for this profile/filters
]


class MatchExplanation(BaseModel):
    why_match: Optional[str] = None
    strengths: List[str] = []
    skill_gaps: List[str] = []
    recommendation: Optional[str] = None
    match_summary: Optional[Literal["Strong Match", "Good Match", "Partial Match"]] = None


class CareerMatchingCacheInfo(BaseModel):
    hit: bool
    key: Optional[str] = None


class JobMatchResult(BaseModel):
    opportunity_id: str
    title: str
    company: str
    location: Optional[str] = None
    country: Optional[str] = None
    work_mode: Optional[str] = None
    is_remote: bool = False
    employment_type: Optional[str] = None
    opportunity_type: str
    target_role: Optional[str] = None
    experience_level: Optional[str] = None
    experience_min_years: Optional[int] = None
    experience_max_years: Optional[int] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: Optional[str] = None
    salary_period: Optional[str] = None
    salary_text: Optional[str] = None
    posted_at: Optional[datetime] = None
    source: str
    source_label: str
    source_board: Optional[str] = None
    attribution: Optional[str] = None
    job_url: Optional[str] = None
    application_url: Optional[str] = None
    match_score: float
    match_label: Literal["Strong match", "Good match", "Partial match"]
    matched_skills: List[str] = []
    missing_skills: List[str] = []
    match_reasons: List[str] = []
    explanation: str
    breakdown: CareerMatchBreakdown
    # Optional AI annotations (never change the deterministic score or order).
    rerank_reason: Optional[str] = None
    confidence: Optional[GeminiConfidence] = None
    ai_explanation: Optional[MatchExplanation] = None


class ListingAvailability(BaseModel):
    active_listings: int
    configured_providers: List[str]
    providers_with_errors: List[str]
    last_successful_sync_at: Optional[datetime] = None
    sync_running: bool = False


class ProfileMatchSummary(BaseModel):
    target_roles: List[str] = []
    skills_count: int = 0
    experience_level: Optional[str] = None
    experience_years: Optional[float] = None
    preferred_work_type: Optional[str] = None
    preferred_locations: List[str] = []


class AppliedFilters(BaseModel):
    location: Optional[str] = None
    work_mode: Optional[str] = None
    employment_type: Optional[str] = None
    experience: Optional[str] = None
    source: Optional[str] = None


class FilterOptions(BaseModel):
    locations: List[str] = []
    work_modes: List[str] = []
    employment_types: List[str] = []
    sources: List[str] = []


class CareerMatchingAPIResponse(BaseModel):
    status: CareerMatchingStatus = "success"
    message: Optional[str] = None
    target_role: Optional[str] = None
    profile_summary: Optional[ProfileMatchSummary] = None
    missing_profile_fields: List[str] = []
    results: List[JobMatchResult] = []
    total_matches: int = 0
    page: int = 1
    page_size: int = 10
    total_pages: int = 0
    candidates_considered: int = 0
    excluded_counts: Dict[str, int] = {}
    suggestions: List[str] = []
    availability: Optional[ListingAvailability] = None
    applied_filters: AppliedFilters = AppliedFilters()
    filter_options: FilterOptions = FilterOptions()
    gemini_status: GeminiStatus = "not_configured"
    qwen_status: QwenStatus = "skipped"
    used_deterministic_fallback: bool = True
    used_qwen_fallback: bool = True
    cache: CareerMatchingCacheInfo = CareerMatchingCacheInfo(hit=False)


class ProviderStatusItem(BaseModel):
    provider: str
    enabled: bool
    sources: List[str]
    attribution: str
    note: Optional[str] = None
    active_listings: int
    last_run_at: Optional[datetime] = None
    last_run_status: Optional[str] = None
    last_successful_sync_at: Optional[datetime] = None
    last_error_at: Optional[datetime] = None
    last_error: Optional[str] = None
    failing_sources: List[str] = []


class ProviderStatusResponse(BaseModel):
    sync_enabled: bool
    sync_interval_minutes: int
    sync_running: bool
    total_active_listings: int
    providers: List[ProviderStatusItem]


class SyncTriggerResponse(BaseModel):
    status: Literal["started", "already_running"]
    message: str
