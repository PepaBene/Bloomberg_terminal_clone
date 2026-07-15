"""Commodity profile, price, and company exposure models (Pillar 3 Phase 3B – Part 8)."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class CommodityProfile(TimestampMixin, Base):
    """Reference profile for a tracked commodity."""

    __tablename__ = "commodity_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    commodity_code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    commodity_name: Mapped[str | None] = mapped_column(String(100))
    category: Mapped[str | None] = mapped_column(String(20))
    unit: Mapped[str | None] = mapped_column(String(30))
    primary_source: Mapped[str | None] = mapped_column(String(20))


class CommodityPrice(TimestampMixin, Base):
    """Daily commodity price OHLCV record."""

    __tablename__ = "commodity_prices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    commodity_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    price_date: Mapped[date] = mapped_column(Date, nullable=False)

    # OHLCV
    close_price: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))
    open_price: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))
    high_price: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))
    low_price: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))
    volume: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    source: Mapped[str | None] = mapped_column(String(20))

    __table_args__ = (
        {"comment": "Daily commodity OHLCV price data"},
    )


class CommodityInventory(TimestampMixin, Base):
    """Periodic physical supply/inventory (stocks-in-storage) report for a
    commodity, e.g. EIA weekly petroleum/natural-gas/gasoline stocks.

    This is the real data source the ``/global/commodities/{code}/supply-demand``
    endpoint (src/api/routers/global_intelligence.py) needs to compute an actual
    supply/demand signal instead of inferring one from price movement alone.
    One row per (commodity_code, as_of_date): the total reported stock level
    for that reporting period.
    """

    __tablename__ = "commodity_inventories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    commodity_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    stock_level: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    stock_unit: Mapped[str | None] = mapped_column(String(30))
    metric_name: Mapped[str | None] = mapped_column(String(100))
    source: Mapped[str | None] = mapped_column(String(20))

    __table_args__ = (
        Index(
            "uq_commodity_inventory_code_date", "commodity_code", "as_of_date", unique=True
        ),
        {"comment": "Periodic commodity stock/inventory levels (supply-side reports)"},
    )


class CommodityCompanyExposure(TimestampMixin, Base):
    """Company-level commodity exposure and sensitivity mapping."""

    __tablename__ = "commodity_company_exposures"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    commodity_code: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.entity_id"),
        nullable=False,
    )
    exposure_type: Mapped[str | None] = mapped_column(String(20))
    exposure_description: Mapped[str | None] = mapped_column(String(500))
    sensitivity_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    historical_correlation: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    source: Mapped[str | None] = mapped_column(String(20))
