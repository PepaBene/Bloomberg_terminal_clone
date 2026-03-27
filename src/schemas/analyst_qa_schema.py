"""Pydantic schemas for Pillar 3 Phase 4B: Analyst Q&A."""

from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class QARequest(BaseModel):
    question: str
    context: dict | None = None
    entity_id: UUID | None = None
    user_id: str = "default_user"


class QAResponse(BaseModel):
    id: UUID
    user_id: str
    entity_id: UUID | None = None
    question: str
    answer_text: str | None = None
    answer_type: str | None = None
    confidence_level: float | None = None
    confidence_narrative: str | None = None
    sources: dict | None = None
    supporting_data: dict | None = None
    follow_up_suggestions: dict | None = None
    data_completeness: dict | None = None
    execution_time_ms: int | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class QAFeedbackRequest(BaseModel):
    rating: int | None = None
    feedback_text: str | None = None
    is_accurate: bool | None = None


class QAFeedbackResponse(BaseModel):
    id: UUID
    session_id: UUID
    rating: int | None = None
    feedback_text: str | None = None
    is_accurate: bool | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class QAHistoryResponse(BaseModel):
    id: UUID
    user_id: str
    entity_id: UUID | None = None
    question: str
    answer_type: str | None = None
    confidence_level: float | None = None
    user_rating: int | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class QAPopularResponse(BaseModel):
    question: str
    ask_count: int
    avg_confidence: float | None = None


class QAStatsResponse(BaseModel):
    total_questions: int
    total_with_feedback: int
    avg_confidence: float | None = None
    avg_rating: float | None = None
    answer_type_counts: dict
