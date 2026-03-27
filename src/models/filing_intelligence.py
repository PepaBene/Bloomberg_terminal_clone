"""Pillar 3 Phase 1: Filing Intelligence models (sections, diffs, 8-K events)."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class FilingSection(TimestampMixin, Base):
    """Extracted section from a 10-K/10-Q for diffing."""

    __tablename__ = "filing_sections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.entity_id"),
        nullable=False,
        index=True,
    )
    filing_type: Mapped[str] = mapped_column(String(10), nullable=False)
    filing_date: Mapped[date] = mapped_column(Date, nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    fiscal_quarter: Mapped[int | None] = mapped_column(Integer)
    section_key: Mapped[str] = mapped_column(String(20), nullable=False)
    section_text: Mapped[str] = mapped_column(Text, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    filing_accession_number: Mapped[str | None] = mapped_column(String(25))
    filing_url: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (
        Index(
            "uq_filing_section",
            "entity_id", "filing_type", "fiscal_year", "section_key",
            unique=True,
        ),
        Index("idx_filing_section_entity_year", "entity_id", "fiscal_year"),
    )


class FilingDiff(TimestampMixin, Base):
    """Paragraph-level diff between two filing versions."""

    __tablename__ = "filing_diffs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.entity_id"),
        nullable=False,
        index=True,
    )
    section_key: Mapped[str] = mapped_column(String(20), nullable=False)
    year_old: Mapped[int] = mapped_column(Integer, nullable=False)
    year_new: Mapped[int] = mapped_column(Integer, nullable=False)
    change_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    change_classification: Mapped[str | None] = mapped_column(String(20))
    substantive_change_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    boilerplate_change_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    numerical_change_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    structural_change_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    added_paragraphs: Mapped[list | None] = mapped_column(JSONB)
    removed_paragraphs: Mapped[list | None] = mapped_column(JSONB)
    modified_paragraphs: Mapped[list | None] = mapped_column(JSONB)
    ai_summary: Mapped[str | None] = mapped_column(Text)
    materiality: Mapped[str | None] = mapped_column(String(10))

    __table_args__ = (
        Index(
            "uq_filing_diff",
            "entity_id", "section_key", "year_old", "year_new",
            unique=True,
        ),
        Index("idx_filing_diff_entity_year", "entity_id", "year_new"),
    )


class EightKEvent(TimestampMixin, Base):
    """Parsed 8-K material event with extracted intelligence."""

    __tablename__ = "eight_k_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.entity_id"),
        nullable=False,
        index=True,
    )
    filing_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    item_number: Mapped[str] = mapped_column(String(10), nullable=False)
    item_description: Mapped[str | None] = mapped_column(String(200))
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    raw_text: Mapped[str | None] = mapped_column(Text)
    monetary_figures: Mapped[list | None] = mapped_column(JSONB)
    key_dates: Mapped[list | None] = mapped_column(JSONB)
    key_people: Mapped[list | None] = mapped_column(JSONB)
    ai_summary: Mapped[str | None] = mapped_column(Text)
    materiality: Mapped[str | None] = mapped_column(String(10))
    filing_accession_number: Mapped[str | None] = mapped_column(String(25))
    filing_url: Mapped[str | None] = mapped_column(String(500))
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("idx_8k_entity_date", "entity_id", "filing_date"),
        Index("idx_8k_priority_date", "priority", "filing_date"),
        Index("idx_8k_item_date", "item_number", "filing_date"),
    )
