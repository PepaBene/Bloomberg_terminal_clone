"""Pillar 3 Phase 2: Earnings Call Transcript models."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class EarningsCallTranscript(TimestampMixin, Base):
    """Full earnings call transcript with NLP-derived tone and topic analysis."""

    __tablename__ = "earnings_call_transcripts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.entity_id"),
        nullable=False,
        index=True,
    )

    # Period identification
    call_date: Mapped[date] = mapped_column(Date, nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    fiscal_quarter: Mapped[int] = mapped_column(Integer, nullable=False)
    call_type: Mapped[str | None] = mapped_column(
        String(20), default="EARNINGS"
    )  # EARNINGS, SPECIAL, GUIDANCE

    # Raw transcript sections
    raw_text: Mapped[str | None] = mapped_column(Text)
    prepared_remarks: Mapped[str | None] = mapped_column(Text)
    qa_section: Mapped[str | None] = mapped_column(Text)
    ceo_section: Mapped[str | None] = mapped_column(Text)
    cfo_section: Mapped[str | None] = mapped_column(Text)

    # Participants metadata
    participants: Mapped[dict | None] = mapped_column(JSONB)  # [{name, title, firm}]

    # Tone analysis (-1.0 to +1.0)
    overall_tone: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    prepared_tone: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    qa_tone: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    ceo_tone: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    cfo_tone: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    tone_divergence: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4)
    )  # prepared - qa
    tone_vs_prior_qtr: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    tone_vs_prior_year: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))

    # Language quality metrics
    hedging_ratio: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    confidence_ratio: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    forward_looking_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    buzzword_counts: Mapped[dict | None] = mapped_column(JSONB)  # {term: count}

    # Topic analysis
    mgmt_topics: Mapped[dict | None] = mapped_column(JSONB)  # Top 5
    qa_topics: Mapped[dict | None] = mapped_column(JSONB)
    absent_topics: Mapped[dict | None] = mapped_column(JSONB)
    new_topics: Mapped[dict | None] = mapped_column(JSONB)

    # AI-generated insights
    ai_summary: Mapped[str | None] = mapped_column(Text)
    key_takeaways: Mapped[dict | None] = mapped_column(JSONB)
    management_outlook: Mapped[str | None] = mapped_column(
        String(20)
    )  # BULLISH/CAUTIOUS/MIXED
    analyst_concerns: Mapped[dict | None] = mapped_column(JSONB)

    # Source and flags
    source_url: Mapped[str | None] = mapped_column(String(1000))
    source_type: Mapped[str | None] = mapped_column(String(30))
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index(
            "uq_transcript_entity_period",
            "entity_id",
            "fiscal_year",
            "fiscal_quarter",
            unique=True,
        ),
        Index("idx_transcript_call_date", "call_date"),
    )
