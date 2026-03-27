"""D11 FI Supplement P8: Agency Bond Reference."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class AgencyBond(TimestampMixin, Base):
    __tablename__ = "agency_bonds"

    bond_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cusip: Mapped[str] = mapped_column(String(9), nullable=False, unique=True, index=True)
    issuer_name: Mapped[str | None] = mapped_column(String(200))
    agency_type: Mapped[str | None] = mapped_column(String(20))  # FNMA, FHLMC, FHLB, FFCB, TVA, SBA, GNMA
    backing_type: Mapped[str | None] = mapped_column(String(25))  # EXPLICIT_GUARANTEE, CONSERVATORSHIP, IMPLICIT_SUPPORT

    # Coupon
    coupon_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    coupon_type: Mapped[str | None] = mapped_column(String(20))  # FIXED, FLOATING, ZERO
    coupon_frequency: Mapped[int | None] = mapped_column(Integer)

    # Dates
    maturity_date: Mapped[date] = mapped_column(Date, nullable=False)
    issue_date: Mapped[date | None] = mapped_column(Date)

    # Amounts
    original_amount_mm: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    outstanding_amount_mm: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str | None] = mapped_column(String(3))

    # Call features
    is_callable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    first_call_date: Mapped[date | None] = mapped_column(Date)

    # Status
    is_outstanding: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str | None] = mapped_column(String(20))

    # Linkage
    security_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    __table_args__ = (
        Index("idx_agency_type_maturity", "agency_type", "maturity_date"),
    )
