"""Legislative, regulatory, and sanctions models (Pillar 3 Phase 3B – Part 8)."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class LegislativeBill(TimestampMixin, Base):
    """Tracked legislative bill with passage probability and sector impact."""

    __tablename__ = "legislative_bills"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    bill_id: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    bill_type: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str | None] = mapped_column(String(30))
    sponsor_count: Mapped[int | None] = mapped_column(Integer)
    passage_probability: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    affected_sectors: Mapped[dict | None] = mapped_column(JSONB)
    affected_entity_ids: Mapped[dict | None] = mapped_column(JSONB)
    introduced_date: Mapped[date | None] = mapped_column(Date)
    last_action_date: Mapped[date | None] = mapped_column(Date)
    source_url: Mapped[str | None] = mapped_column(String(500))


class RegulatoryAction(TimestampMixin, Base):
    """Regulatory agency action with entity and sector impact assessment."""

    __tablename__ = "regulatory_actions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agency: Mapped[str | None] = mapped_column(String(10))
    action_type: Mapped[str | None] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    affected_entity_ids: Mapped[dict | None] = mapped_column(JSONB)
    affected_sectors: Mapped[dict | None] = mapped_column(JSONB)
    severity: Mapped[str | None] = mapped_column(String(10))
    financial_impact: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    action_date: Mapped[date | None] = mapped_column(Date)
    source_url: Mapped[str | None] = mapped_column(String(500))


class SanctionsEntry(TimestampMixin, Base):
    """Sanctions program entry with target and sector details."""

    __tablename__ = "sanctions_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    program: Mapped[str | None] = mapped_column(String(20))
    country_code: Mapped[str | None] = mapped_column(String(3))
    target_name: Mapped[str | None] = mapped_column(String(200))
    target_type: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str | None] = mapped_column(String(20))
    effective_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    affected_sectors: Mapped[dict | None] = mapped_column(JSONB)
    source_url: Mapped[str | None] = mapped_column(String(500))
