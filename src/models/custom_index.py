"""Custom index models (Pillar 2 Supplement – Part 4)."""

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class CustomIndex(TimestampMixin, Base):
    """User-created custom index definition."""

    __tablename__ = "custom_indices"

    index_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    weighting_method: Mapped[str | None] = mapped_column(String(20))
    rebalance_frequency: Mapped[str | None] = mapped_column(String(20))
    max_constituents: Mapped[int | None] = mapped_column(Integer)
    min_market_cap: Mapped[float | None] = mapped_column(Numeric(20, 2))
    inception_date: Mapped[date | None] = mapped_column(Date)
    total_return_inception: Mapped[float | None] = mapped_column(Numeric(10, 6))
    annualized_return: Mapped[float | None] = mapped_column(Numeric(10, 6))
    annualized_volatility: Mapped[float | None] = mapped_column(Numeric(8, 6))
    sharpe_ratio: Mapped[float | None] = mapped_column(Numeric(8, 4))
    max_drawdown: Mapped[float | None] = mapped_column(Numeric(8, 6))
    created_by: Mapped[str | None] = mapped_column(String(100))


class IndexConstituent(TimestampMixin, Base):
    """Constituent of a custom index."""

    __tablename__ = "index_constituents"

    constituent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    index_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("custom_indices.index_id"), nullable=False
    )
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id"), nullable=False
    )
    weight: Mapped[float | None] = mapped_column(Numeric(8, 6))
    added_date: Mapped[date] = mapped_column(Date, nullable=False)
    removed_date: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index("idx_ic_index_sec_date", "index_id", "security_id", "added_date", unique=True),
    )


class IndexPerformance(TimestampMixin, Base):
    """Daily performance of a custom index."""

    __tablename__ = "index_performance"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    index_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("custom_indices.index_id"), nullable=False
    )
    perf_date: Mapped[date] = mapped_column(Date, nullable=False)
    index_level: Mapped[float | None] = mapped_column(Numeric(12, 4))
    daily_return: Mapped[float | None] = mapped_column(Numeric(10, 8))
    cumulative_return: Mapped[float | None] = mapped_column(Numeric(10, 6))

    __table_args__ = (
        Index("idx_ip_index_date", "index_id", "perf_date", unique=True),
    )
