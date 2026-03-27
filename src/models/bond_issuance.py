"""D11 FI Supplement P7: Bond Issuance Database."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class BondIssuance(TimestampMixin, Base):
    __tablename__ = "bond_issuances"

    issuance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    issuer_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.entity_id"),
        nullable=False,
        index=True,
    )
    bond_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    # Dates
    pricing_date: Mapped[date | None] = mapped_column(Date)
    settlement_date: Mapped[date | None] = mapped_column(Date)
    announcement_date: Mapped[date | None] = mapped_column(Date)

    # Terms
    coupon_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    maturity_date: Mapped[date | None] = mapped_column(Date)
    seniority: Mapped[str | None] = mapped_column(String(30))
    issue_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    issue_yield: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))

    # Spread dynamics
    initial_talk_low_bps: Mapped[int | None] = mapped_column(Integer)
    initial_talk_high_bps: Mapped[int | None] = mapped_column(Integer)
    final_spread_bps: Mapped[int | None] = mapped_column(Integer)
    tightening_bps: Mapped[int | None] = mapped_column(Integer)

    # Size
    announced_size_mm: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    issued_size_mm: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))

    # Bookrunners
    lead_left_bookrunner: Mapped[str | None] = mapped_column(String(200))
    all_bookrunners: Mapped[list | None] = mapped_column(JSONB)

    # Classification
    use_of_proceeds: Mapped[str | None] = mapped_column(String(30))
    currency: Mapped[str | None] = mapped_column(String(3))
    is_benchmark: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_144a: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_registered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("idx_issuance_entity", "issuer_entity_id"),
        Index("idx_issuance_pricing_date", "pricing_date"),
    )
