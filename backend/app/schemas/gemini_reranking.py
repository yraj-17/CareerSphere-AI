"""Schemas for Phase 3.5 Gemini semantic reranking."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.career_matching import CareerMatchResult


GeminiStatus = Literal["success", "unavailable", "invalid_response", "not_configured"]
GeminiConfidence = Literal["high", "medium", "low"]


class GeminiRerankItem(BaseModel):
    opportunity_id: str
    semantic_rank: int = Field(..., ge=1, le=5)
    rerank_reason: str = Field(..., min_length=1, max_length=500)
    confidence: GeminiConfidence


class GeminiRerankResponse(BaseModel):
    ranked_opportunities: List[GeminiRerankItem] = Field(default_factory=list, max_length=5)


class CareerMatchRerankedResult(CareerMatchResult):
    semantic_rank: int
    rerank_reason: Optional[str] = None
    confidence: Optional[GeminiConfidence] = None


class CareerMatchingWithRerankResponse(BaseModel):
    deterministic_results: List[CareerMatchResult]
    final_results: List[CareerMatchRerankedResult]
    gemini_status: GeminiStatus
    used_deterministic_fallback: bool
