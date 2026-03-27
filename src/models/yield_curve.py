"""Pillar 1 Supplement: Yield Curve models (Part 2)."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class YieldCurveSnapshot(TimestampMixin, Base):
    """Daily yield curve snapshot with rates at standard tenors."""

    __tablename__ = "yield_curve_snapshots"

    curve_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    curve_date: Mapped[date] = mapped_column(Date, nullable=False)
    curve_type: Mapped[str] = mapped_column(String(25), nullable=False)

    # Rates at standard tenors
    rate_1m: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    rate_3m: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    rate_6m: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    rate_1y: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    rate_2y: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    rate_3y: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    rate_5y: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    rate_7y: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    rate_10y: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    rate_20y: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    rate_30y: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))

    # Derived spreads
    spread_2s10s: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    spread_3m10y: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    curve_slope: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    is_inverted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Source
    source: Mapped[str | None] = mapped_column(String(20))

    # D11 FI Supplement: Zero-coupon rates (bootstrapped from par yields)
    zero_1m: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    zero_3m: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    zero_6m: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    zero_1y: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    zero_2y: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    zero_3y: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    zero_5y: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    zero_7y: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    zero_10y: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    zero_20y: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    zero_30y: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))

    # D11 FI Supplement: Discount factors
    df_1y: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    df_2y: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    df_5y: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    df_10y: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    df_20y: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    df_30y: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))

    # D11 FI Supplement: Forward rates
    fwd_0to1y: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    fwd_1to2y: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    fwd_2to5y: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    fwd_5to10y: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    fwd_10to30y: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))

    # D11 FI Supplement: Nelson-Siegel-Svensson parameters
    nsv_beta0: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    nsv_beta1: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    nsv_beta2: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    nsv_beta3: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    nsv_lambda1: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    nsv_lambda2: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    nsv_fit_error: Mapped[Decimal | None] = mapped_column(Numeric(10, 8))

    # D11 FI Supplement: Additional spread metrics
    butterfly_spread: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    spread_5s30s: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))

    __table_args__ = (
        Index("idx_yc_date_type", "curve_date", "curve_type", unique=True),
    )


class ZeroCouponCurve(TimestampMixin, Base):
    """Bootstrapped zero-coupon curve point."""

    __tablename__ = "zero_coupon_curves"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    curve_date: Mapped[date] = mapped_column(Date, nullable=False)
    tenor_years: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    zero_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    discount_factor: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    forward_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))

    __table_args__ = (
        Index("idx_zc_date_tenor", "curve_date", "tenor_years", unique=True),
    )
