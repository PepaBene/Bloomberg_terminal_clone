"""Pillar 3 Phase 4B: Semantic search models."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin

# gemini-embedding-002's default output dimensionality (DEFAULT_DIMENSIONS
# in src/services/ai/embedding_client.py) — must stay in sync.
EMBEDDING_DIMENSIONS = 3072


class SearchDocument(Base):
    """A chunked document indexed for semantic search."""

    __tablename__ = "search_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Wider VARCHAR for source/anomaly type strings — earnings_call_*
    # variants regularly exceed 25 chars (M-002).
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(100))
    title: Mapped[str | None] = mapped_column(String(500))
    author: Mapped[str | None] = mapped_column(String(200))
    publish_date: Mapped[date | None] = mapped_column(Date)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=True, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_token_count: Mapped[int | None] = mapped_column(Integer)
    embedding_model: Mapped[str | None] = mapped_column(String(50))
    # M-001 (legacy): pre-pgvector storage, still written alongside
    # `embedding` for backward compatibility with any other JSONB
    # consumer. Real ANN ranking in semantic_search() uses `embedding`.
    embedding_vector: Mapped[dict | None] = mapped_column(JSONB)
    # M-001: real pgvector column with an HNSW cosine index (see migration
    # 087) — replaces the JSONB + pure-Python cosine_similarity() loop.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Audit M-007: re-indexing should bump the timestamp; without it we
    # cannot answer "what was reindexed today?".
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        # M-010: chunk retrieval most often filters on (source_type, source_id).
        Index("idx_search_documents_source", "source_type", "source_id"),
    )


class SearchQuery(Base):
    """A recorded semantic search query."""

    __tablename__ = "search_queries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # TODO: Add ForeignKey("users.id") once the users table is created.
    user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    result_count: Mapped[int | None] = mapped_column(Integer)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer)
    top_result_relevance: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    ai_synthesis: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # M-007: track recompute time so we can answer "queries refreshed
    # today" without it always equalling created_at.
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
