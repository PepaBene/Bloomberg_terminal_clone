"""Pillar 1 FI Supplement D11.1: Treasury Securities Reference."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, Integer, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class TreasurySecurity(TimestampMixin, Base):
    __tablename__ = "treasury_securities"

    treasury_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cusip: Mapped[str] = mapped_column(String(9), nullable=False, unique=True, index=True)
    treasury_type: Mapped[str] = mapped_column(String(25), nullable=False, index=True)

    # Terms
    coupon_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    coupon_frequency: Mapped[int | None] = mapped_column(Integer)  # 2=semi-annual, 0=bills
    issue_date: Mapped[date | None] = mapped_column(Date)
    maturity_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Outstanding
    original_issue_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    outstanding_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))

    # Auction data
    auction_date: Mapped[date | None] = mapped_column(Date)
    auction_high_yield: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    auction_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    auction_bid_to_cover: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    auction_median_yield: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    auction_low_yield: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))

    # TIPS
    is_inflation_indexed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    index_ratio: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    ref_cpi_date: Mapped[date | None] = mapped_column(Date)
    ref_cpi_value: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))

    # STRIPS
    is_stripped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    stripped_from_cusip: Mapped[str | None] = mapped_column(String(9))
    strip_type: Mapped[str | None] = mapped_column(String(15))

    # Status
    is_outstanding: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str | None] = mapped_column(String(20))

    # Linkage
    security_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    __table_args__ = (
        Index("idx_treas_maturity", "maturity_date"),
        Index("idx_treas_type_outstanding", "treasury_type", "is_outstanding"),
    )
