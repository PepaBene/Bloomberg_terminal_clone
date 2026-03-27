"""Pydantic schemas for Pillar 3 Phase 2: Earnings Transcripts, Surprises, Guidance."""

from pydantic import BaseModel
from uuid import UUID
from datetime import date


class TranscriptResponse(BaseModel):
    id: UUID
    entity_id: UUID
    call_date: date
    fiscal_year: int
    fiscal_quarter: int
    call_type: str | None = None
    participants: list[dict] | None = None
    overall_tone: float | None = None
    prepared_tone: float | None = None
    qa_tone: float | None = None
    tone_divergence: float | None = None
    hedging_ratio: float | None = None
    confidence_ratio: float | None = None
    forward_looking_pct: float | None = None
    management_outlook: str | None = None
    source_url: str | None = None
    ai_enabled: bool = False

    model_config = {"from_attributes": True}


class TranscriptSummaryResponse(BaseModel):
    entity_id: UUID
    call_date: date
    ai_summary: str | None = None
    key_takeaways: list[str] | None = None
    management_outlook: str | None = None
    analyst_concerns: list[str] | None = None
    ai_enabled: bool = False


class TranscriptSentimentResponse(BaseModel):
    entity_id: UUID
    call_date: date
    overall_tone: float
    prepared_tone: float | None
    qa_tone: float | None
    ceo_tone: float | None
    cfo_tone: float | None
    tone_divergence: float | None
    hedging_ratio: float | None
    confidence_ratio: float | None


class TranscriptTopicsResponse(BaseModel):
    entity_id: UUID
    call_date: date
    mgmt_topics: list[str] = []
    qa_topics: list[str] = []
    absent_topics: list[str] = []
    new_topics: list[str] = []
    buzzword_counts: dict[str, int] = {}


class SentimentHistoryPoint(BaseModel):
    call_date: date
    fiscal_year: int
    fiscal_quarter: int
    overall_tone: float
    prepared_tone: float | None = None
    qa_tone: float | None = None


class CallSentimentHistoryResponse(BaseModel):
    entity_id: UUID
    history: list[SentimentHistoryPoint] = []


class SurpriseResponse(BaseModel):
    id: UUID
    entity_id: UUID
    fiscal_year: int
    fiscal_quarter: int
    actual_eps: float | None = None
    consensus_eps: float | None = None
    eps_surprise_pct: float | None = None
    actual_revenue: float | None = None
    revenue_surprise_pct: float | None = None
    ebitda_surprise_pct: float | None = None
    beat_and_fell: bool = False
    consecutive_beats: int | None = None
    price_reaction_pct: float | None = None
    price_reaction_5d_pct: float | None = None

    model_config = {"from_attributes": True}


class GuidanceResponse(BaseModel):
    id: UUID
    entity_id: UUID
    metric: str | None = None
    guidance_low: float | None
    guidance_high: float | None
    guidance_midpoint: float | None
    guidance_type: str | None
    guidance_vs_consensus: str | None
    credibility_score: float | None

    model_config = {"from_attributes": True}


class GuidanceCredibilityResponse(BaseModel):
    entity_id: UUID
    credibility_score: float
    historical_accuracy: float | None
    consistency_score: float | None


class EarningsCalendarResponse(BaseModel):
    events: list[dict] = []
    total_count: int = 0
