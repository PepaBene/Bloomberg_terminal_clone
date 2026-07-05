"""Pillar 1 Supplement: Debt Maturity Profile models (DDIS)."""

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, Numeric
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class DebtMaturityProfile(TimestampMixin, Base):
    """Aggregate debt maturity risk metrics for an entity."""

    __tablename__ = "debt_maturity_profiles"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    # The filings table is named ``filings`` in fundamentals.py.
    filing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("filings.filing_id")
    )

    # Refinancing risk indicators
    debt_maturing_1yr: Mapped[float | None] = mapped_column(Numeric(20, 2))
    debt_maturing_2yr: Mapped[float | None] = mapped_column(Numeric(20, 2))
    debt_maturing_3yr: Mapped[float | None] = mapped_column(Numeric(20, 2))
    pct_debt_maturing_1yr: Mapped[float | None] = mapped_column(Numeric(8, 4))
    pct_debt_maturing_3yr: Mapped[float | None] = mapped_column(Numeric(8, 4))

    # Weighted averages
    weighted_avg_maturity_years: Mapped[float | None] = mapped_column(Numeric(8, 2))
    weighted_avg_coupon: Mapped[float | None] = mapped_column(Numeric(8, 4))

    # Coverage ratios
    cash_to_1yr_maturities: Mapped[float | None] = mapped_column(Numeric(8, 4))
    fcf_to_1yr_maturities: Mapped[float | None] = mapped_column(Numeric(8, 4))

    # Alerts
    maturity_wall_alert: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    near_term_stress: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    buckets = relationship("MaturityBucket", back_populates="profile", lazy="selectin")

    __table_args__ = (
        Index("idx_maturity_entity_date", "entity_id", "as_of_date"),
    )


class MaturityBucket(TimestampMixin, Base):
    """Annual maturity bucket within a debt maturity profile."""

    __tablename__ = "maturity_buckets"

    bucket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("debt_maturity_profiles.profile_id"),
        nullable=False,
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    total_amount: Mapped[float | None] = mapped_column(Numeric(20, 2))
    breakdown: Mapped[dict | None] = mapped_column(JSONB)

    # Relationships
    profile = relationship("DebtMaturityProfile", back_populates="buckets")

    __table_args__ = (
        Index("idx_bucket_profile_year", "profile_id", "year"),
    )
