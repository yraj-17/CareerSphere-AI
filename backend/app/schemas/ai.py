from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AIRequest(BaseModel):
    prompt: str
    think: bool = False
    use_profile: bool = False


class AIResponse(BaseModel):
    response: str


class ConversationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    role: str
    content: str
    used_profile_context: bool = False
    created_at: datetime


class ConversationDetail(ConversationSummary):
    messages: List[ChatMessageOut] = Field(default_factory=list)


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=8000)
    use_profile: bool = False

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise ValueError("Message cannot be empty.")
        return cleaned


class SendMessageResponse(BaseModel):
    conversation: ConversationSummary
    user_message: ChatMessageOut
    assistant_message: Optional[ChatMessageOut] = None
    error: Optional[str] = None


class GrammarCheckRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=8000)

    @field_validator("text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise ValueError("Text cannot be empty.")
        return cleaned


class GrammarMatchOut(BaseModel):
    offset: int
    length: int
    message: str
    short_message: str
    original: str
    replacements: List[str]
    rule_id: str
    category: str


class GrammarCheckResponse(BaseModel):
    original_text: str
    corrected_text: str
    matches: List[GrammarMatchOut] = Field(default_factory=list)


class ProfileOptimizationSection(BaseModel):
    section: str
    score: int = Field(..., ge=0, le=100)
    status: str
    current: Optional[str] = None
    suggestion: str
    reason: str


class ProfileOptimizationResponse(BaseModel):
    overall_score: int = Field(..., ge=0, le=100)
    summary: str
    sections: List[ProfileOptimizationSection] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    recommended_improvements: List[str] = Field(default_factory=list)
    existing_skills: List[str] = Field(default_factory=list)
    suggested_skills_to_learn: List[str] = Field(default_factory=list)
