"""Pillar 4 Phase 2: Attribution results and report request models."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class AttributionResult(Base):
    """Brinson or factor attribution result for a period."""

    __tablename__ = "attribution_results"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "attribution_type", "period_end", name="uq_attr_portfolio_type_end"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id"),
        nullable=False, index=True,
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    attribution_type: Mapped[str] = mapped_column(String(10), nullable=False)
    total_portfolio_return: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    total_benchmark_return: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    total_active_return: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    total_allocation: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    total_selection: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    total_interaction: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    residual: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    sector_detail: Mapped[dict | None] = mapped_column(JSONB)
    security_detail: Mapped[dict | None] = mapped_column(JSONB)
    factor_detail: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ReportRequest(Base):
    """Report generation request and cached result."""

    __tablename__ = "report_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id"), nullable=False,
    )
    report_type: Mapped[str] = mapped_column(String(20), nullable=False)
    format: Mapped[str] = mapped_column(String(10), nullable=False)
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    parameters: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(15), default="COMPLETED")
    result_data: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
