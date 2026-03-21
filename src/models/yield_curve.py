"""Pillar 1 Supplement: Yield Curve models (Part 2)."""

import uuid
from datetime import date

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
    rate_1m: Mapped[float | None] = mapped_column(Numeric(8, 4))
    rate_3m: Mapped[float | None] = mapped_column(Numeric(8, 4))
    rate_6m: Mapped[float | None] = mapped_column(Numeric(8, 4))
    rate_1y: Mapped[float | None] = mapped_column(Numeric(8, 4))
    rate_2y: Mapped[float | None] = mapped_column(Numeric(8, 4))
    rate_3y: Mapped[float | None] = mapped_column(Numeric(8, 4))
    rate_5y: Mapped[float | None] = mapped_column(Numeric(8, 4))
    rate_7y: Mapped[float | None] = mapped_column(Numeric(8, 4))
    rate_10y: Mapped[float | None] = mapped_column(Numeric(8, 4))
    rate_20y: Mapped[float | None] = mapped_column(Numeric(8, 4))
    rate_30y: Mapped[float | None] = mapped_column(Numeric(8, 4))

    # Derived spreads
    spread_2s10s: Mapped[float | None] = mapped_column(Numeric(8, 4))
    spread_3m10y: Mapped[float | None] = mapped_column(Numeric(8, 4))
    curve_slope: Mapped[float | None] = mapped_column(Numeric(8, 4))
    is_inverted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Source
    source: Mapped[str | None] = mapped_column(String(20))

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
    tenor_years: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    zero_rate: Mapped[float | None] = mapped_column(Numeric(8, 6))
    discount_factor: Mapped[float | None] = mapped_column(Numeric(12, 8))
    forward_rate: Mapped[float | None] = mapped_column(Numeric(8, 6))

    __table_args__ = (
        Index("idx_zc_date_tenor", "curve_date", "tenor_years", unique=True),
    )
