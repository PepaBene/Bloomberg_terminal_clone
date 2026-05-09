"""Pydantic schemas for Pillar 3 Phase 2: FinBERT Sentiment Extensions."""

from pydantic import BaseModel
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
