"""Congressional trading models (US STOCK Act periodic transaction reports).

Source: free public disclosures filed by members of the US House
(House Clerk) and Senate (Senate eFD) under the STOCK Act. Used to follow
politician trading activity such as Nancy Pelosi.
"""

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class CongressionalTrade(TimestampMixin, Base):
    """A single STOCK Act periodic transaction report (PTR) line item."""

    __tablename__ = "congressional_trades"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Politician identity
    politician_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    bioguide_id: Mapped[str | None] = mapped_column(String(20), index=True)
    chamber: Mapped[str | None] = mapped_column(String(10))  # HOUSE / SENATE
    party: Mapped[str | None] = mapped_column(String(4))
    state: Mapped[str | None] = mapped_column(String(2))

    # Security (resolved where possible)
    ticker: Mapped[str | None] = mapped_column(String(20), index=True)
    security_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id")
    )
    asset_description: Mapped[str | None] = mapped_column(String(400))
    asset_type: Mapped[str | None] = mapped_column(String(40))  # STOCK / OPTION / BOND / FUND

    # Transaction
    transaction_type: Mapped[str] = mapped_column(String(12), nullable=False)  # BUY/SELL/EXCHANGE
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    disclosure_date: Mapped[date | None] = mapped_column(Date)
    amount_range_low: Mapped[float | None] = mapped_column(Numeric(18, 2))
    amount_range_high: Mapped[float | None] = mapped_column(Numeric(18, 2))
    owner: Mapped[str | None] = mapped_column(String(20))  # SELF / SPOUSE / JOINT / DEPENDENT

    # Derived / context
    disclosure_lag_days: Mapped[int | None] = mapped_column(Integer)
    is_late_disclosure: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    committees: Mapped[list | None] = mapped_column(JSONB)
    source_url: Mapped[str | None] = mapped_column(String(600))

    __table_args__ = (
        Index("idx_congress_trade_person_date", "politician_name", "transaction_date"),
        Index("idx_congress_trade_ticker_date", "ticker", "transaction_date"),
    )
