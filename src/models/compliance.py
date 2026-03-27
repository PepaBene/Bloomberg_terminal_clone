"""Pillar 4 Phase 3: Compliance rules, results, and drift monitoring."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class ComplianceRule(Base):
    """User-defined compliance rule for a portfolio."""

    __tablename__ = "compliance_rules"

    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id"),
        nullable=False, index=True,
    )
    rule_name: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(30), nullable=False)
    rule_definition: Mapped[dict] = mapped_column(JSONB, nullable=False)
    threshold: Mapped[Decimal | None] = mapped_column(Numeric(15, 6))
    upper_threshold: Mapped[Decimal | None] = mapped_column(Numeric(15, 6))
    comparison: Mapped[str] = mapped_column(String(10), nullable=False)
    severity: Mapped[str | None] = mapped_column(String(10), server_default="WARNING")
    is_active: Mapped[bool | None] = mapped_column(Boolean, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ComplianceResult(Base):
    """Result of a compliance check against a rule."""

    __tablename__ = "compliance_results"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "rule_id", "check_date", name="uq_compliance_portfolio_rule_date"),
    )

    result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id"),
        nullable=False, index=True,
    )
    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("compliance_rules.rule_id"),
        nullable=False,
    )
    check_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    current_value: Mapped[Decimal | None] = mapped_column(Numeric(15, 6))
    threshold_value: Mapped[Decimal | None] = mapped_column(Numeric(15, 6))
    breach_positions: Mapped[dict | None] = mapped_column(JSONB)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DriftSnapshot(Base):
    """Portfolio drift analysis vs target allocation."""

    __tablename__ = "drift_snapshots"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "snapshot_date", name="uq_drift_portfolio_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id"),
        nullable=False, index=True,
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_drift_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    max_position_drift_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    max_sector_drift_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    drift_classification: Mapped[str | None] = mapped_column(String(15))
    position_drifts: Mapped[dict | None] = mapped_column(JSONB)
    sector_drifts: Mapped[dict | None] = mapped_column(JSONB)
    rebalance_needed: Mapped[bool | None] = mapped_column(Boolean, server_default="0")
    target_allocation: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
