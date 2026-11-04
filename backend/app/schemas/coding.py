"""
Coding assessment API schemas.

Requests carry only what a candidate controls: language, source code, optional
custom input, and an idempotency key. Limits, tests, expected outputs and checkers
come exclusively from the backend problem configuration; unknown fields are
rejected so nothing else can be smuggled in.

Responses never contain hidden test inputs, expected outputs, or the candidate's
output on hidden tests — hidden results have their own type with none of those fields.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import settings

LanguageKey = Literal["CPP", "JAVA", "PYTHON", "JAVASCRIPT", "BASH", "SQLITE"]
IDEMPOTENCY_PATTERN = r"^[A-Za-z0-9_-]{8,64}$"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _bounded_source(value: str) -> str:
    if not value or not value.strip():
        raise ValueError("Source code cannot be empty.")
    if len(value.encode("utf-8")) > settings.CODING_MAX_SOURCE_BYTES:
        raise ValueError(f"Source code is larger than {settings.CODING_MAX_SOURCE_BYTES // 1024} KB.")
    return value


class RunCodeRequest(_Strict):
    language: LanguageKey
    source_code: str
    custom_input: Optional[str] = None
    idempotency_key: Optional[str] = Field(None, pattern=IDEMPOTENCY_PATTERN)

    @field_validator("source_code")
    @classmethod
    def bounded_source(cls, value: str) -> str:
        return _bounded_source(value)

    @field_validator("custom_input")
    @classmethod
    def bounded_input(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and len(value.encode("utf-8")) > settings.CODING_MAX_CUSTOM_INPUT_BYTES:
            raise ValueError(f"Custom input is larger than {settings.CODING_MAX_CUSTOM_INPUT_BYTES // 1024} KB.")
        return value


class SubmitSolutionRequest(_Strict):
    language: LanguageKey
    source_code: str
    idempotency_key: str = Field(..., pattern=IDEMPOTENCY_PATTERN)

    @field_validator("source_code")
    @classmethod
    def bounded_source(cls, value: str) -> str:
        return _bounded_source(value)


class LanguageOut(BaseModel):
    key: str
    label: str  # exactly as reported by the Judge0 server
    monaco_language: str
    notes: str = ""


class LanguagesResponse(BaseModel):
    execution_available: bool
    languages: list[LanguageOut]


class ExampleOut(BaseModel):
    input: str
    output: str
    explanation: Optional[str] = None


class ProblemOut(BaseModel):
    id: str
    slug: str
    title: str
    difficulty: str
    category: str = "dsa"  # dsa | frontend | backend | sql | bash
    statement: str
    input_format: str
    output_format: str
    constraints: str
    examples: list[ExampleOut]
    instructions: Optional[str] = None
    languages: list[LanguageOut]
    starter_code: dict[str, str]
    time_limit_seconds: float
    memory_limit_kb: int
    estimated_minutes: int
    sample_test_count: int
    hidden_test_count: int


class VisibleTestResult(BaseModel):
    """Sample tests and custom input: full detail."""

    ordinal: int
    kind: Literal["sample", "custom"]
    verdict: str
    verdict_label: str
    passed: Optional[bool] = None  # None for custom input (nothing to compare against)
    time: Optional[float] = None
    memory: Optional[int] = None
    judge0_status: str
    input: str
    expected_output: Optional[str] = None
    stdout: str = ""
    stderr: str = ""
    reason: str = ""


class HiddenTestResult(BaseModel):
    """Hidden tests: outcome and metrics only — no input, expected output, or program output."""

    ordinal: int
    kind: Literal["hidden"] = "hidden"
    verdict: str
    verdict_label: str
    passed: bool
    time: Optional[float] = None
    memory: Optional[int] = None
    judge0_status: str


class SubmissionOut(BaseModel):
    id: str
    question_id: str
    submission_type: Literal["RUN", "SUBMIT"]
    language: str
    language_label: str
    status: Literal["QUEUED", "RUNNING", "COMPLETED", "FAILED"]
    verdict: Optional[str] = None
    verdict_label: Optional[str] = None
    tests_passed: Optional[int] = None
    tests_total: Optional[int] = None
    correctness_score: Optional[float] = None  # weighted test correctness, 0-100 (execution only)
    max_time_seconds: Optional[float] = None
    max_memory_kb: Optional[int] = None
    compile_output: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    results: list[Union[VisibleTestResult, HiddenTestResult]] = Field(default_factory=list)


class SubmissionListResponse(BaseModel):
    submissions: list[SubmissionOut]
