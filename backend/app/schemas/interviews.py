"""
AI Interviewer V1 schemas.

Two groups live here:
* API request/response models (validated input, serialized output).
* Model-output models — the JSON shapes Qwen must return. These are passed to
  Ollama as a JSON schema and every response is validated against them before
  anything is persisted.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


INTERVIEW_TYPES = ("TECHNICAL", "BEHAVIORAL", "MIXED")
INTERACTION_MODES = ("TEXT", "VOICE")
DIFFICULTIES = ("BEGINNER", "INTERMEDIATE", "ADVANCED")
DEFAULT_DURATION_MINUTES = 15
# Supported durations mapped to the question budget for that duration (~2.5 min/question).
DURATION_QUESTION_LIMITS = {10: 4, 15: 6, 20: 8, 30: 12}

MAX_ROLE_LENGTH = 120
MAX_FOCUS_AREAS = 8
MAX_FOCUS_AREA_LENGTH = 60
MAX_INSTRUCTIONS_LENGTH = 500
MAX_ANSWER_LENGTH = 5000

SCORE_SCALE_EXPLANATION = (
    "Scores are 0-100 AI-generated practice feedback: 85+ strong, 70-84 solid, "
    "50-69 developing, below 50 needs significant work. They are not a hiring decision "
    "and do not predict real interview outcomes."
)


def _clean_text_list(values, max_items: int, max_len: int) -> list[str]:
    """Lenient list cleaning: strip, drop empties, truncate, de-duplicate, cap count."""
    if not isinstance(values, list):
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in values:
        if not isinstance(raw, str):
            continue
        item = " ".join(raw.split())[:max_len].strip()
        key = item.lower()
        if not item or key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
        if len(cleaned) >= max_items:
            break
    return cleaned


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class InterviewCreateRequest(BaseModel):
    target_role: str = Field(..., min_length=2, max_length=MAX_ROLE_LENGTH)
    interview_type: Literal["TECHNICAL", "BEHAVIORAL", "MIXED"]
    interaction_mode: Literal["TEXT", "VOICE"] = "TEXT"
    difficulty: Literal["BEGINNER", "INTERMEDIATE", "ADVANCED"] = "INTERMEDIATE"
    duration_minutes: int = DEFAULT_DURATION_MINUTES
    focus_areas: list[str] = Field(default_factory=list)
    instructions: Optional[str] = Field(None, max_length=MAX_INSTRUCTIONS_LENGTH)

    @field_validator("target_role")
    @classmethod
    def clean_role(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 2:
            raise ValueError("Target role must be at least 2 characters.")
        return cleaned

    @field_validator("duration_minutes")
    @classmethod
    def supported_duration(cls, value: int) -> int:
        if value not in DURATION_QUESTION_LIMITS:
            allowed = ", ".join(str(v) for v in DURATION_QUESTION_LIMITS)
            raise ValueError(f"Duration must be one of: {allowed} minutes.")
        return value

    @field_validator("focus_areas", mode="before")
    @classmethod
    def clean_focus_areas(cls, value) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("Focus areas must be a list.")
        if len(value) > MAX_FOCUS_AREAS * 2:
            raise ValueError(f"Choose at most {MAX_FOCUS_AREAS} focus areas.")
        cleaned = _clean_text_list(value, max_items=MAX_FOCUS_AREAS + 1, max_len=MAX_FOCUS_AREA_LENGTH + 1)
        if len(cleaned) > MAX_FOCUS_AREAS:
            raise ValueError(f"Choose at most {MAX_FOCUS_AREAS} focus areas.")
        if any(len(item) > MAX_FOCUS_AREA_LENGTH for item in cleaned):
            raise ValueError(f"Each focus area must be at most {MAX_FOCUS_AREA_LENGTH} characters.")
        return cleaned

    @field_validator("instructions")
    @classmethod
    def clean_instructions(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class InterviewAnswerSubmitRequest(BaseModel):
    question_id: str = Field(..., min_length=1, max_length=36)
    answer_text: str = Field(..., max_length=MAX_ANSWER_LENGTH)
    answer_source: Literal["TEXT", "VOICE"] = "TEXT"

    @field_validator("answer_text")
    @classmethod
    def non_empty_answer(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Answer cannot be empty.")
        return cleaned


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class DimensionScores(BaseModel):
    relevance: Optional[int] = None
    clarity: Optional[int] = None
    accuracy: Optional[int] = None
    reasoning: Optional[int] = None
    structure: Optional[int] = None
    reflection: Optional[int] = None


class AnswerEvaluationOut(BaseModel):
    score: int
    dimensions: DimensionScores
    strengths: list[str]
    improvements: list[str]
    feedback: str
    key_points: list[str]


class InterviewAnswerOut(BaseModel):
    id: str
    question_id: str
    answer_text: str
    answer_source: str
    submitted_at: datetime
    evaluation_status: str
    score: Optional[int] = None
    evaluation: Optional[AnswerEvaluationOut] = None
    can_retry_evaluation: bool = False


class InterviewQuestionOut(BaseModel):
    id: str
    question_order: int
    question_text: str
    category: str
    competency: str
    difficulty: str
    interviewer_context: Optional[str] = None
    created_at: datetime
    answer: Optional[InterviewAnswerOut] = None


class InterviewSessionSummary(BaseModel):
    id: str
    target_role: str
    interview_type: str
    interaction_mode: str
    difficulty: str
    duration_minutes: int
    status: str
    started_at: datetime
    deadline_at: datetime
    completed_at: Optional[datetime] = None
    final_score: Optional[int] = None
    question_count: int
    answered_count: int
    report_status: Optional[str] = None


class InterviewSessionOut(InterviewSessionSummary):
    focus_areas: list[str]
    instructions: Optional[str] = None
    max_questions: int
    server_time: datetime
    remaining_seconds: int
    current_question: Optional[InterviewQuestionOut] = None
    can_request_next_question: bool
    questions: list[InterviewQuestionOut]


class InterviewListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    interviews: list[InterviewSessionSummary]


class AnswerSubmitResponse(BaseModel):
    answer: InterviewAnswerOut
    interview: InterviewSessionOut


class ReportNarrativeOut(BaseModel):
    summary: str
    strengths: list[str]
    weaknesses: list[str]
    repeated_gaps: list[str]
    improvement_plan: list[str]
    topics_to_revise: list[str]


class ReportQuestionRef(BaseModel):
    question_id: str
    question_order: int
    competency: str
    category: str
    score: int


class ReportAggregatesOut(BaseModel):
    question_count: int
    answered_count: int
    evaluated_count: int
    dimension_scores: DimensionScores
    category_scores: dict[str, Optional[int]]
    strongest: list[ReportQuestionRef]
    weakest: list[ReportQuestionRef]
    methodology: str


class InterviewReportOut(BaseModel):
    interview_id: str
    status: str
    overall_score: Optional[int] = None
    aggregates: Optional[ReportAggregatesOut] = None
    narrative: Optional[ReportNarrativeOut] = None
    generated_at: Optional[datetime] = None
    can_retry: bool
    score_scale: str = SCORE_SCALE_EXPLANATION


class InterviewCompleteResponse(BaseModel):
    interview: InterviewSessionOut
    report: Optional[InterviewReportOut] = None


class InterviewOptionsResponse(BaseModel):
    interview_types: list[str]
    interaction_modes: list[str]
    difficulties: list[str]
    durations: list[int]
    default_duration_minutes: int
    max_answer_length: int
    max_focus_areas: int
    transcription_available: bool
    max_audio_seconds: int
    max_audio_bytes: int
    score_scale: str = SCORE_SCALE_EXPLANATION


class InterviewSuggestionsResponse(BaseModel):
    target_role: Optional[str] = None
    skills: list[str]
    has_profile: bool


class TranscriptionResponse(BaseModel):
    transcript: str
    duration_seconds: Optional[float] = None


# ---------------------------------------------------------------------------
# Model output (validated before persisting)
# ---------------------------------------------------------------------------


class GeneratedQuestion(BaseModel):
    question_text: str = Field(..., min_length=15, max_length=700)
    competency: str = Field(..., min_length=2, max_length=120)
    interviewer_context: Optional[str] = Field(None, max_length=400)

    @field_validator("question_text", "competency")
    @classmethod
    def collapse_whitespace(cls, value: str) -> str:
        return " ".join(value.split())


_Score = Field(..., ge=0, le=100)


class _EvaluationBase(BaseModel):
    relevance: int = _Score
    clarity: int = _Score
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    feedback: str = Field(..., min_length=10, max_length=1200)
    key_points: list[str] = Field(default_factory=list)

    @field_validator("strengths", "improvements", mode="before")
    @classmethod
    def clean_feedback_lists(cls, value) -> list[str]:
        return _clean_text_list(value, max_items=4, max_len=300)

    @field_validator("key_points", mode="before")
    @classmethod
    def clean_key_points(cls, value) -> list[str]:
        return _clean_text_list(value, max_items=5, max_len=300)


class TechnicalEvaluation(_EvaluationBase):
    accuracy: int = _Score
    reasoning: int = _Score


class BehavioralEvaluation(_EvaluationBase):
    structure: int = _Score
    reflection: int = _Score


class GeneratedNarrative(BaseModel):
    summary: str = Field(..., min_length=20, max_length=1500)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    repeated_gaps: list[str] = Field(default_factory=list)
    improvement_plan: list[str] = Field(default_factory=list)
    topics_to_revise: list[str] = Field(default_factory=list)

    @field_validator("strengths", "weaknesses", "repeated_gaps", "improvement_plan", "topics_to_revise", mode="before")
    @classmethod
    def clean_lists(cls, value) -> list[str]:
        return _clean_text_list(value, max_items=6, max_len=300)
