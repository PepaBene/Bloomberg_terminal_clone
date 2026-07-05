"""Sentiment analysis models (Pillar 2 Supplement – Part 8)."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func
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
        UUID(as_uuid=True), ForeignKey("entities.entity_id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(500))
    source_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sentiment: Mapped[str] = mapped_column(String(10), nullable=False)
    sentiment_score: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.5)
    relevance: Mapped[float | None] = mapped_column(Numeric(5, 4))
    topics: Mapped[dict | None] = mapped_column(JSONB)  # List of topic tags for this sentiment score
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("idx_sentiment_entity_date", "entity_id", "source_date"),
        UniqueConstraint("entity_id", "source_type", "source_reference", name="uq_sentiment_entity_source"),
    )


class SentimentAggregate(TimestampMixin, Base):
    """Company-level rolling sentiment aggregate."""

    __tablename__ = "sentiment_aggregates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id", ondelete="CASCADE"),
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

    # Phase 2: Extended anomaly and momentum fields
    sentiment_momentum_class: Mapped[str | None] = mapped_column(
        String(25)
    )  # STRONGLY_IMPROVING etc
    peer_z_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    volume_anomaly: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sentiment_shift_anomaly: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    price_divergence_anomaly: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    combined_anomaly_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    __table_args__ = (
        Index("idx_sent_agg_entity_date_tf", "entity_id", "as_of_date", "timeframe", unique=True),
        Index("ix_sentiment_agg_entity_date", "entity_id", "as_of_date", postgresql_ops={"as_of_date": "DESC"}),
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


# ── Pillar 3 Phase 2: Paragraph & Entity-Level Sentiment ───────────────


class ParagraphSentiment(TimestampMixin, Base):
    """Per-paragraph sentiment within a news article."""

    __tablename__ = "paragraph_sentiments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("news_articles.id"),
        nullable=False,
        index=True,
    )
    paragraph_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text_snippet: Mapped[str | None] = mapped_column(String(500))  # First 500 chars
    sentiment: Mapped[str | None] = mapped_column(
        String(10)
    )  # POSITIVE/NEGATIVE/NEUTRAL
    positive_prob: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    negative_prob: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    neutral_prob: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    composite_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4)
    )  # positive - negative
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    method: Mapped[str | None] = mapped_column(String(15))  # FINBERT / KEYWORD

    __table_args__ = (
        Index(
            "uq_paragraph_article_idx",
            "article_id",
            "paragraph_index",
            unique=True,
        ),
    )


class EntitySentiment(TimestampMixin, Base):
    """Per-entity sentiment within a news article."""

    __tablename__ = "entity_sentiments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("news_articles.id"),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.entity_id"),
        nullable=False,
    )
    sentence_count: Mapped[int | None] = mapped_column(Integer)
    avg_sentiment: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    method: Mapped[str | None] = mapped_column(String(15))

    __table_args__ = (
        Index(
            "uq_entity_sent_article_entity",
            "article_id",
            "entity_id",
            unique=True,
        ),
    )


# ── Pillar 3 Phase 1: Watchlist & Alerting ─────────────────────────────


class Watchlist(TimestampMixin, Base):
    """User's entity watchlist for alerts and digests."""

    __tablename__ = "watchlists"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # TODO: Add ForeignKey("users.id") once the users table is created.
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.entity_id"),
        nullable=False,
        index=True,
    )
    added_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("uq_watchlist_user_entity", "user_id", "entity_id", unique=True),
    )


class AlertRule(TimestampMixin, Base):
    """User-configurable alert rules."""

    __tablename__ = "alert_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # TODO: Add ForeignKey("users.id") once the users table is created.
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_scope: Mapped[dict | None] = mapped_column(JSONB)  # {entity_ids: [uuid], sectors: [str], ...}
    conditions: Mapped[dict | None] = mapped_column(JSONB)  # {threshold: float, direction: str, metric: str, ...}
    priority_threshold: Mapped[str | None] = mapped_column(String(10))
    delivery_preference: Mapped[str] = mapped_column(
        String(20), nullable=False, default="DAILY_DIGEST"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    quiet_hours_start: Mapped[str | None] = mapped_column(String(5))
    quiet_hours_end: Mapped[str | None] = mapped_column(String(5))

    __table_args__ = (
        Index("idx_alert_rule_user_type", "user_id", "alert_type"),
    )


class AlertEvent(TimestampMixin, Base):
    """Triggered alert events."""

    __tablename__ = "alert_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alert_rules.id"),
    )
    # TODO: Add ForeignKey("users.id") once the users table is created.
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.entity_id"),
        nullable=False,
        index=True,
    )
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="MEDIUM")
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    detail: Mapped[dict | None] = mapped_column(JSONB)  # Alert-specific detail payload (metrics, context, etc.)
    is_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("idx_alert_user_ack", "user_id", "is_acknowledged", "created_at"),
        Index("idx_alert_entity_date", "entity_id", "created_at"),
    )
