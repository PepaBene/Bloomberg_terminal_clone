"""Pillar 3 Phase 1: News Article models (articles, entity links)."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class NewsArticle(TimestampMixin, Base):
    """Ingested news article with enrichment metadata."""

    __tablename__ = "news_articles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    body_text: Mapped[str | None] = mapped_column(Text)
    source_name: Mapped[str] = mapped_column(String(100), nullable=False)
    publish_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    ingest_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    news_type: Mapped[str | None] = mapped_column(String(30))
    topics: Mapped[list | None] = mapped_column(JSONB)  # [str] list of topic tags
    materiality: Mapped[str | None] = mapped_column(String(10))
    sentiment_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    sentiment_confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    sentiment_label: Mapped[str | None] = mapped_column(String(10))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    is_propagated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    propagation_source: Mapped[str | None] = mapped_column(String(30))

    # ── Layer 2 (AI_THREE_LAYER_REBUILD_PLAN.md §4.2): trust & corroboration ──
    source_trust: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    credibility_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    # Self-referential: points at the cluster's representative article (the
    # first one seen). A representative's cluster_id points at itself, so
    # "every article has a cluster_id" holds uniformly -- no NULL-means-
    # singleton special case for callers to handle.
    cluster_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("news_articles.id"), index=True
    )
    is_non_consensus: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    corroboration_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # ── Layer 2 §4.4: per-article AI analysis ──────────────────────────
    # One JSONB blob rather than five+ ai_* columns -- matches how
    # Interpretation.drivers/consequences/connections already store
    # structured LLM output in this codebase. Shape:
    # {summary, interpretation, non_consensus_angle, connections: [str],
    #  confidence, model, prompt_id, prompt_version, analyzed_at}.
    # NULL means "not yet analyzed" -- the compute-on-miss cache-miss
    # state (src/ai/news/store.py); articles are immutable post-
    # enrichment, so there's no separate freshness/version check the way
    # Layer 1's interpretations need for changing analytics.
    ai_analysis: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        Index("idx_news_type_date", "news_type", "publish_date"),
        Index("idx_news_materiality_date", "materiality", "publish_date"),
    )


class NewsSource(TimestampMixin, Base):
    """Trust/credibility registry for news sources (§4.2).

    A reference/lookup table like ``Currency``/``Exchange`` in
    ``src/models/reference.py`` -- natural-key primary key, no surrogate
    UUID, seeded from static JSON via ``reference_loader.py`` rather than
    an ingestion connector. ``source_name`` is the free-form label
    ingestion connectors already write onto ``NewsArticle.source_name``
    (e.g. Finnhub passes through whatever the underlying feed calls
    itself), so it's the natural key here too; ``domain`` is a secondary,
    nullable-unique lookup for connectors that only have a URL.
    """

    __tablename__ = "news_sources"

    source_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    domain: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    tier: Mapped[str] = mapped_column(String(10), nullable=False)  # WIRE|TIER1|TIER2|BLOG|SOCIAL|PR
    reliability_weight: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)
    region: Mapped[str | None] = mapped_column(String(50))
    is_paywalled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class ArticleEntityLink(TimestampMixin, Base):
    """Many-to-many link between news articles and entities."""

    __tablename__ = "article_entity_links"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("news_articles.id"),
        nullable=False,
        index=True,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.entity_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relevance_score: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mention_text: Mapped[str | None] = mapped_column(String(200))
    mention_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    __table_args__ = (
        Index("uq_article_entity", "article_id", "entity_id", unique=True),
    )


# ── Pillar 3 Phase 2: News Propagation ────────────────────────────────


class PropagationRule(TimestampMixin, Base):
    """Rules governing how news events propagate across entity relationships."""

    __tablename__ = "propagation_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    rule_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # SUPPLY_CHAIN, CUSTOMER, COMPETITIVE, SECTOR, GEOGRAPHIC, MACRO
    event_category: Mapped[str | None] = mapped_column(String(30))
    severity: Mapped[str | None] = mapped_column(String(10))
    relevance_decay_hop1: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 3), default=0.3
    )
    relevance_decay_hop2: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 3), default=0.1
    )
    max_hops: Mapped[int | None] = mapped_column(Integer, default=2)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PropagationEvent(TimestampMixin, Base):
    """Tracked event propagation from source to target entity."""

    __tablename__ = "propagation_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_article_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("news_articles.id"),
    )
    source_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.entity_id"),
        nullable=False,
    )
    target_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.entity_id"),
        nullable=False,
        index=True,
    )
    rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("propagation_rules.id"),
    )
    propagation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    hop_number: Mapped[int] = mapped_column(Integer, nullable=False)
    relevance_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    event_summary: Mapped[str | None] = mapped_column(String(500))
    severity: Mapped[str | None] = mapped_column(String(10))

    __table_args__ = (
        Index("idx_prop_event_target_created", "target_entity_id", "created_at"),
        Index("idx_prop_event_source_created", "source_entity_id", "created_at"),
    )


class PropagationPreference(TimestampMixin, Base):
    """User preferences for propagation event types."""

    __tablename__ = "propagation_preferences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    propagation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index(
            "uq_prop_pref_user_type",
            "user_id",
            "propagation_type",
            unique=True,
        ),
    )
