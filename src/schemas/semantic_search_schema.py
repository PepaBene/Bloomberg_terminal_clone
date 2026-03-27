"""Pydantic schemas for Pillar 3 Phase 4B: Semantic Search."""

from pydantic import BaseModel
from uuid import UUID
from datetime import date, datetime


class SearchRequest(BaseModel):
    query: str
    limit: int = 20
    document_types: list[str] | None = None
    companies: list[str] | None = None
    date_range: dict | None = None


class SearchChunkResponse(BaseModel):
    document_id: UUID
    source_type: str
    source_id: str | None = None
    title: str | None = None
    author: str | None = None
    publish_date: date | None = None
    entity_id: UUID | None = None
    chunk_index: int
    chunk_text: str
    relevance_score: float | None = None

    model_config = {"from_attributes": True}


class SearchResultResponse(BaseModel):
    query: str
    total_results: int
    results: list[SearchChunkResponse] = []
    execution_time_ms: int | None = None


class SearchSynthesisResponse(BaseModel):
    query: str
    synthesis: str | None = None
    total_results: int
    results: list[SearchChunkResponse] = []
    execution_time_ms: int | None = None


class SearchHistoryResponse(BaseModel):
    id: UUID
    user_id: str
    query_text: str
    result_count: int | None = None
    execution_time_ms: int | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class SuggestedQueryResponse(BaseModel):
    query: str
    category: str | None = None
    relevance_score: float | None = None


class DocumentStatsResponse(BaseModel):
    total_documents: int
    total_chunks: int
    source_type_counts: dict
    last_indexed_at: datetime | None = None


class IndexDocumentRequest(BaseModel):
    source_type: str
    source_id: str | None = None
    title: str | None = None
    author: str | None = None
    publish_date: date | None = None
    entity_id: UUID | None = None
    chunks: list[dict]


class IndexDocumentResponse(BaseModel):
    document_count: int
    chunk_count: int
    source_type: str
    status: str


class TrendingTopicResponse(BaseModel):
    topic: str
    query_count: int
    trend_direction: str | None = None
