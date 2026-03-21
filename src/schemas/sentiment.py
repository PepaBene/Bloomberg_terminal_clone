"""Pydantic schemas for sentiment analysis."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class SentimentScoreResponse(BaseModel):
    """Response for a single sentiment score."""
    score_id: uuid.UUID | None = None
    entity_id: uuid.UUID | None = None
    source_type: str | None = None
    source_reference: str | None = None
    source_date: datetime | None = None
    sentiment: str
    sentiment_score: float
    confidence: float
    relevance: float | None = None
    topics: list[str] | None = None
    ai_enabled: bool = False

    model_config = {"from_attributes": True}


class SentimentAggregateResponse(BaseModel):
    """Aggregated sentiment for a company."""
    entity_id: uuid.UUID
    as_of_date: date | None = None
    timeframe: str = "ROLLING_30D"
    avg_sentiment: float
    sentiment_momentum: float | None = None
    article_count: int = 0
    positive_pct: float = 0.0
    negative_pct: float = 0.0
    anomaly_flag: bool = False
    ai_enabled: bool = False


class EarningsCallSentimentResponse(BaseModel):
    """Earnings call sentiment analysis."""
    entity_id: uuid.UUID
    call_date: date | None = None
    fiscal_year: int | None = None
    fiscal_quarter: int | None = None
    overall_tone: float
    management_tone: float | None = None
    qa_tone: float | None = None
    tone_vs_prior: float | None = None
    hedging_count: int = 0
    confidence_count: int = 0
    topic_sentiments: dict[str, float] | None = None
    ai_enabled: bool = False

    model_config = {"from_attributes": True}


class ScoreTextRequest(BaseModel):
    """Request to score arbitrary text."""
    text: str
    source_type: str = "NEWS_ARTICLE"


class SentimentHistoryPoint(BaseModel):
    """Single point in sentiment history."""
    date: datetime | None = None
    sentiment: str
    score: float
    source_type: str | None = None


class SentimentHistoryResponse(BaseModel):
    """Sentiment score time series."""
    entity_id: uuid.UUID
    history: list[SentimentHistoryPoint] = []
    total_count: int = 0


class SentimentAnomalyResponse(BaseModel):
    """Company with sentiment anomaly."""
    entity_id: uuid.UUID
    entity_name: str | None = None
    avg_sentiment: float
    anomaly_flag: bool = True
    timeframe: str = "ROLLING_30D"
