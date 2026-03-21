"""Sentiment analysis models (Pillar 2 Supplement – Part 8)."""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class SentimentScore(TimestampMixin, Base):
    """Per-article/document sentiment score."""

    __tablename__ = "sentiment_scores"

    score_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"),
        nullable=False, index=True,
    )
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(500))
    source_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sentiment: Mapped[str] = mapped_column(String(10), nullable=False)
    sentiment_score: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.5)
    relevance: Mapped[float | None] = mapped_column(Numeric(5, 4))
    topics: Mapped[dict | None] = mapped_column(JSONB)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("idx_sentiment_entity_date", "entity_id", "source_date"),
    )


class SentimentAggregate(TimestampMixin, Base):
    """Company-level rolling sentiment aggregate."""

    __tablename__ = "sentiment_aggregates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"),
        nullable=False, index=True,
    )
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    timeframe: Mapped[str] = mapped_column(String(15), nullable=False)
    avg_sentiment: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    sentiment_momentum: Mapped[float | None] = mapped_column(Numeric(5, 4))
    article_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    positive_pct: Mapped[float | None] = mapped_column(Numeric(5, 4))
    negative_pct: Mapped[float | None] = mapped_column(Numeric(5, 4))
    anomaly_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    peer_rank_pct: Mapped[float | None] = mapped_column(Numeric(5, 4))

    __table_args__ = (
        Index("idx_sent_agg_entity_date_tf", "entity_id", "as_of_date", "timeframe", unique=True),
    )


class EarningsCallSentiment(TimestampMixin, Base):
    """Structured earnings call sentiment analysis."""

    __tablename__ = "earnings_call_sentiment"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"),
        nullable=False, index=True,
    )
    call_date: Mapped[date] = mapped_column(Date, nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    fiscal_quarter: Mapped[int] = mapped_column(Integer, nullable=False)
    overall_tone: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    management_tone: Mapped[float | None] = mapped_column(Numeric(5, 4))
    qa_tone: Mapped[float | None] = mapped_column(Numeric(5, 4))
    tone_vs_prior: Mapped[float | None] = mapped_column(Numeric(5, 4))
    hedging_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    confidence_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    topic_sentiments: Mapped[dict | None] = mapped_column(JSONB)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("idx_ecall_entity_fy_fq", "entity_id", "fiscal_year", "fiscal_quarter", unique=True),
    )
