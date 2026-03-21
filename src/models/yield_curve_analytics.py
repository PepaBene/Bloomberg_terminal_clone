"""Yield curve fitted curves and analytics models."""

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, Index, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class YieldCurveFitted(TimestampMixin, Base):
    """Nelson-Siegel or interpolation fitted yield curve."""

    __tablename__ = "yield_curve_fitted"

    fit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    curve_date: Mapped[date] = mapped_column(Date, nullable=False)
    curve_type: Mapped[str] = mapped_column(String(25), nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    beta0: Mapped[float | None] = mapped_column(Numeric(10, 6))
    beta1: Mapped[float | None] = mapped_column(Numeric(10, 6))
    beta2: Mapped[float | None] = mapped_column(Numeric(10, 6))
    tau: Mapped[float | None] = mapped_column(Numeric(10, 6))
    fit_error: Mapped[float | None] = mapped_column(Numeric(10, 8))
    fitted_rates: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        Index(
            "idx_ycf_date_type_method",
            "curve_date", "curve_type", "method",
            unique=True,
        ),
    )


class CurveAnalytics(TimestampMixin, Base):
    """Daily computed yield curve spread and shape metrics."""

    __tablename__ = "curve_analytics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    curve_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    spread_2s10s: Mapped[float | None] = mapped_column(Numeric(8, 4))
    spread_3m10y: Mapped[float | None] = mapped_column(Numeric(8, 4))
    steepness: Mapped[float | None] = mapped_column(Numeric(8, 4))
    curvature: Mapped[float | None] = mapped_column(Numeric(8, 4))
    breakeven_5y: Mapped[float | None] = mapped_column(Numeric(8, 4))
    breakeven_10y: Mapped[float | None] = mapped_column(Numeric(8, 4))
    is_inverted: Mapped[bool | None] = mapped_column(Boolean)
