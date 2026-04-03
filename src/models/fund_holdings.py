"""Pillar 1 Supplement: Fund Holdings (N-PORT) models (Part 4)."""

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class Fund(TimestampMixin, Base):
    """Investment fund (ETF, mutual fund, etc.)."""

    __tablename__ = "funds"

    fund_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id")
    )
    fund_name: Mapped[str] = mapped_column(String(300), nullable=False)
    fund_ticker: Mapped[str | None] = mapped_column(String(20), index=True)
    series_id: Mapped[str | None] = mapped_column(String(30))
    class_id: Mapped[str | None] = mapped_column(String(30))
    cik: Mapped[str | None] = mapped_column(String(10), index=True)
    fund_type: Mapped[str | None] = mapped_column(String(20), index=True)
    strategy: Mapped[str | None] = mapped_column(String(100))
    category: Mapped[str | None] = mapped_column(String(100))
    total_net_assets: Mapped[float | None] = mapped_column(Numeric(20, 2))
    number_of_holdings: Mapped[int | None] = mapped_column(Integer)
    top_10_concentration: Mapped[float | None] = mapped_column(Numeric(8, 4))
    expense_ratio: Mapped[float | None] = mapped_column(Numeric(8, 4))

    holdings = relationship("FundHolding", back_populates="fund", lazy="selectin")


class FundHolding(TimestampMixin, Base):
    """Individual security holding within a fund."""

    __tablename__ = "fund_holdings"

    holding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    fund_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("funds.fund_id"), nullable=False, index=True
    )
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    security_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id")
    )
    security_name: Mapped[str | None] = mapped_column(String(300))
    cusip: Mapped[str | None] = mapped_column(String(9))
    isin: Mapped[str | None] = mapped_column(String(12))
    quantity: Mapped[float | None] = mapped_column(Numeric(20, 4))
    market_value: Mapped[float | None] = mapped_column(Numeric(20, 2))
    pct_of_nav: Mapped[float | None] = mapped_column(Numeric(8, 4))
    asset_type: Mapped[str | None] = mapped_column(String(20))
    issuer_category: Mapped[str | None] = mapped_column(String(20))
    nport_accession: Mapped[str | None] = mapped_column(String(25))

    fund = relationship("Fund", back_populates="holdings")

    __table_args__ = (
        Index("idx_holding_fund_date", "fund_id", "report_date"),
        Index("idx_holding_security_date", "security_id", "report_date"),
    )
