"""Default risk scoring models (Pillar 2 Supplement – Part 2)."""

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class DefaultRiskScore(TimestampMixin, Base):
    """Composite default risk score combining Altman Z and Merton DD."""

    __tablename__ = "default_risk_scores"

    score_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False
    )
    security_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id")
    )
    calculation_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Altman Z-Score
    altman_z_score: Mapped[float | None] = mapped_column(Numeric(8, 4))
    altman_zone: Mapped[str | None] = mapped_column(String(20))

    # Merton Distance-to-Default
    merton_dd: Mapped[float | None] = mapped_column(Numeric(8, 4))
    merton_pd: Mapped[float | None] = mapped_column(Numeric(10, 8))
    merton_asset_value: Mapped[float | None] = mapped_column(Numeric(20, 2))
    merton_asset_vol: Mapped[float | None] = mapped_column(Numeric(8, 6))
    equity_volatility: Mapped[float | None] = mapped_column(Numeric(8, 6))

    # Composite score
    composite_score: Mapped[float | None] = mapped_column(Numeric(5, 1))
    implied_rating: Mapped[str | None] = mapped_column(String(5))
    credit_zone: Mapped[str | None] = mapped_column(String(20))
    key_drivers: Mapped[dict | None] = mapped_column(JSONB)

    # Trend
    prior_score: Mapped[float | None] = mapped_column(Numeric(5, 1))
    score_change: Mapped[float | None] = mapped_column(Numeric(5, 1))
    trend: Mapped[str | None] = mapped_column(String(20))

    # Data quality
    data_quality: Mapped[str | None] = mapped_column(String(20))
    inputs: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        Index("idx_drs_entity_date", "entity_id", "calculation_date"),
        Index("idx_drs_composite", "composite_score"),
    )
