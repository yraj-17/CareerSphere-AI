"""Final Career Matching API schemas for Phase 3.6."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel

from app.schemas.career_matching import CareerMatchBreakdown, CareerMatchResult
from app.schemas.gemini_reranking import GeminiConfidence, GeminiStatus


QwenStatus = Literal["success", "unavailable", "skipped"]


class MatchExplanation(BaseModel):
    why_match: Optional[str] = None
    strengths: List[str] = []
    skill_gaps: List[str] = []
    recommendation: Optional[str] = None
    match_summary: Optional[Literal["Strong Match", "Good Match", "Partial Match"]] = None


class CareerMatchingCacheInfo(BaseModel):
    hit: bool
    key: Optional[str] = None


class CareerMatchingFinalResult(BaseModel):
    opportunity_id: str
    title: str
    company: str
    location: Optional[str] = None
    is_remote: bool = False
    opportunity_type: str
    target_role: str
    experience_level: Optional[str] = None
    industry: Optional[str] = None
    deterministic_score: float
    breakdown: CareerMatchBreakdown
    semantic_rank: int
    rerank_reason: Optional[str] = None
    confidence: Optional[GeminiConfidence] = None
    explanation: Optional[MatchExplanation] = None


class CareerMatchingAPIResponse(BaseModel):
    status: Literal["success", "no_profile", "no_target_role"] = "success"
    target_role: Optional[str] = None
    deterministic_results: List[CareerMatchResult] = []
    final_results: List[CareerMatchingFinalResult] = []
    gemini_status: GeminiStatus
    qwen_status: QwenStatus
    used_deterministic_fallback: bool
    used_qwen_fallback: bool
    cache: CareerMatchingCacheInfo
