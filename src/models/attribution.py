"""Pillar 4 Phase 2: Attribution results and report request models."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:  # avoid circular imports at runtime
    from src.models.portfolio import Portfolio


class AttributionResult(Base):
    """Brinson or factor attribution result for a period."""

    __tablename__ = "attribution_results"
    __table_args__ = (
        # P4-M-015: the audit's originally-shipped constraint covered
        # (portfolio_id, attribution_type, period_end), which allows two
        # rows for the *same* period with different period_start values to
        # coexist under the same attribution_type/period_end pair, and
        # (worse) silently treats a genuine re-run of the same period with
        # a different attribution_type as non-duplicate. The period itself
        # -- (portfolio_id, period_start, period_end) -- is what uniquely
        # identifies "the result for this period"; attribution_type is a
        # dimension of the row's content, not a new key.
        UniqueConstraint("portfolio_id", "period_start", "period_end", name="uq_attr_portfolio_period"),
        # P4-M-023: date-order sanity check.
        CheckConstraint("period_start <= period_end", name="ck_attr_period_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # P4-M-009: cascade-delete with parent portfolio so ``session.delete
    # (portfolio)`` doesn't fail with a bare FK violation against history
    # tables.
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # P4-M-010: ORM-level back-reference so Portfolio.attribution_results
    # can eager-load without a separate query.
    portfolio: Mapped["Portfolio"] = relationship(
        "Portfolio", back_populates="attribution_results"
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
    __table_args__ = (
        # P4-M-023: date-order sanity check. Both columns are nullable
        # (not every report is period-scoped), so the check only fires
        # once both are populated.
        CheckConstraint(
            "period_start IS NULL OR period_end IS NULL OR period_start <= period_end",
            name="ck_report_period_order",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # P4-M-009: cascade-delete with parent portfolio, matching this
    # module's other portfolio_id FK.
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False,
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
