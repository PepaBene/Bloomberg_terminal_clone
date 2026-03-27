"""Pillar 4 Phase 1: Portfolio management model."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class Portfolio(TimestampMixin, Base):
    """User portfolio with benchmark, cash, and configuration."""

    __tablename__ = "portfolios"
    __table_args__ = (
        UniqueConstraint("user_id", "portfolio_name", name="uq_portfolio_user_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    portfolio_name: Mapped[str] = mapped_column(String(200), nullable=False)
    portfolio_type: Mapped[str] = mapped_column(
        String(10), nullable=False, default="REAL"
    )
    benchmark_id: Mapped[str | None] = mapped_column(String(20))
    inception_date: Mapped[date] = mapped_column(Date, nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), default="USD")
    initial_cash: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    current_cash: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(10), default="ACTIVE")
    tags: Mapped[dict | None] = mapped_column(JSONB)
    notes: Mapped[str | None] = mapped_column(Text)
