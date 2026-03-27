"""D11 FI Supplement P6: Credit Spread Indices."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class CreditSpreadIndex(TimestampMixin, Base):
    __tablename__ = "credit_spread_indices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    series_id: Mapped[str] = mapped_column(String(30), nullable=False)
    observation_date: Mapped[date] = mapped_column(Date, nullable=False)
    index_name: Mapped[str | None] = mapped_column(String(200))
    rating_category: Mapped[str | None] = mapped_column(String(10))
    spread_bps: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    total_return_index: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    source: Mapped[str | None] = mapped_column(String(30))

    __table_args__ = (
        UniqueConstraint("series_id", "observation_date", name="uq_spread_series_date"),
        Index("idx_spread_series_id", "series_id"),
        Index("idx_spread_observation_date", "observation_date"),
    )


class CreditSpreadPercentile(TimestampMixin, Base):
    __tablename__ = "credit_spread_percentiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    series_id: Mapped[str] = mapped_column(String(30), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    lookback_years: Mapped[int] = mapped_column(Integer, nullable=False)
    percentile_rank: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    current_oas: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    min_oas: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    max_oas: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    mean_oas: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    std_dev: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    z_score: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))

    __table_args__ = (
        UniqueConstraint(
            "series_id", "as_of_date", "lookback_years",
            name="uq_percentile_series_date_lookback",
        ),
    )
