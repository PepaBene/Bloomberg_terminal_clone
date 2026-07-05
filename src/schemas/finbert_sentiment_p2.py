"""Pydantic schemas for Pillar 3 Phase 2: FinBERT Sentiment Extensions."""

from datetime import date

from pydantic import BaseModel, Field
from uuid import UUID


class SentimentSummaryResponse(BaseModel):
    entity_id: UUID
    sentiment_7d: float | None = None
    sentiment_30d: float | None = None
    sentiment_90d: float | None = None
    momentum: float | None = None
    momentum_class: str | None = None
    article_count: int = 0


class PeerComparisonResponse(BaseModel):
    entity_id: UUID
    sentiment_30d: float | None = None
    peer_median: float | None = None  # absolute peer-group median sentiment
    peer_rank_pct: float | None = None  # 0-100 percentile rank within peers
    z_score: float | None = None
    is_significant: bool = False


class SentimentAnomalyResponse(BaseModel):
    entity_id: UUID
    combined_score: float | None = None
    volume_anomaly: bool = False
    sentiment_shift_anomaly: bool = False
    price_divergence_anomaly: bool = False
    anomalies: list[dict] = []


class SentimentScreenRequest(BaseModel):
    min_sentiment: float | None = None
    max_sentiment: float | None = None
    momentum_class: str | None = None
    min_anomaly_score: float | None = None
    limit: int = 50


class SentimentScreenResponse(BaseModel):
    results: list[SentimentSummaryResponse] = []
    total_count: int = 0


class BulkNewsRequest(BaseModel):
    """Validated request body for bulk news fetching."""
    entity_ids: list[str] = Field(default_factory=list, description="List of entity UUID strings")
    from_date: date | None = Field(None, description="Start date filter")
    to_date: date | None = Field(None, description="End date filter")
    limit: int = Field(100, ge=1, le=1000, description="Maximum articles to return")
