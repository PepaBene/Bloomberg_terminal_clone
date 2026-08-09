"""Pydantic schemas for Pillar 3 News Articles."""

from pydantic import BaseModel
from uuid import UUID
from datetime import date


class ArticleEntityLinkResponse(BaseModel):
    entity_id: UUID
    relevance_score: float | None = None
    confidence: float | None = None
    is_primary: bool = False
    mention_text: str | None = None


class NewsArticleResponse(BaseModel):
    id: UUID
    title: str
    summary: str | None = None
    source_name: str
    publish_date: date
    ingest_date: date
    news_type: str | None = None
    topics: list | None = None
    materiality: str | None = None
    sentiment_score: float | None = None
    sentiment_label: str | None = None
    source_url: str | None = None
    entities: list[ArticleEntityLinkResponse] = []
    # Layer 2 §4.2/§4.5: trust/corroboration, for the deterministic
    # no-AI ranked view -- lets the frontend show "why this is ranked
    # here" (trust tier, corroborating source count) without an LLM call.
    source_trust: float | None = None
    credibility_score: float | None = None
    is_non_consensus: bool = False
    corroboration_count: int = 1

    model_config = {"from_attributes": True}


class ArticleAnalysisResponse(BaseModel):
    """Layer 2 §4.4: per-article AI analysis (trust-weighted summary,
    interpretation, non-consensus angle, connections)."""

    article_id: UUID
    summary: str
    interpretation: str
    non_consensus_angle: str | None = None
    connections: list[str] = []
    confidence: float


class NewsSearchRequest(BaseModel):
    query: str
    entities: list[UUID] | None = None
    topics: list[str] | None = None
    date_from: date | None = None
    date_to: date | None = None
    news_types: list[str] | None = None
    materiality_min: str | None = None
    limit: int = 50
    offset: int = 0


class NewsSearchResponse(BaseModel):
    articles: list[NewsArticleResponse] = []
    total_count: int = 0


class NewsStatsResponse(BaseModel):
    total_articles: int = 0
    articles_today: int = 0
    by_source: dict = {}
    by_type: dict = {}
    by_materiality: dict = {}
