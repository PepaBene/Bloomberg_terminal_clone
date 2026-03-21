"""Pillar 1 Supplement: M&A Deal Database models (Part 3)."""

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class MandADeal(TimestampMixin, Base):
    """Rich M&A deal record with valuation multiples and advisory details."""

    __tablename__ = "ma_deals"

    deal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    acquirer_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), index=True
    )
    target_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), index=True
    )

    # Denormalized names for search
    acquirer_name: Mapped[str | None] = mapped_column(String(200))
    target_name: Mapped[str | None] = mapped_column(String(200))

    # Deal classification
    deal_type: Mapped[str | None] = mapped_column(String(25))
    deal_status: Mapped[str | None] = mapped_column(String(15), index=True)
    is_hostile: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Valuation
    total_value: Mapped[float | None] = mapped_column(Numeric(20, 2))
    equity_value: Mapped[float | None] = mapped_column(Numeric(20, 2))
    price_per_share: Mapped[float | None] = mapped_column(Numeric(12, 4))
    premium_to_undisturbed: Mapped[float | None] = mapped_column(Numeric(8, 4))

    # Consideration
    payment_type: Mapped[str | None] = mapped_column(String(10))
    cash_component: Mapped[float | None] = mapped_column(Numeric(20, 2))
    stock_exchange_ratio: Mapped[float | None] = mapped_column(Numeric(10, 6))

    # Multiples
    ev_to_revenue: Mapped[float | None] = mapped_column(Numeric(10, 4))
    ev_to_ebitda: Mapped[float | None] = mapped_column(Numeric(10, 4))
    pe_ratio: Mapped[float | None] = mapped_column(Numeric(10, 4))

    # Target financials (LTM)
    target_revenue_ltm: Mapped[float | None] = mapped_column(Numeric(20, 2))
    target_ebitda_ltm: Mapped[float | None] = mapped_column(Numeric(20, 2))
    target_net_income_ltm: Mapped[float | None] = mapped_column(Numeric(20, 2))

    # Key dates
    announcement_date: Mapped[date | None] = mapped_column(Date, index=True)
    completion_date: Mapped[date | None] = mapped_column(Date)
    termination_date: Mapped[date | None] = mapped_column(Date)
    expected_completion: Mapped[date | None] = mapped_column(Date)

    # Advisors (JSONB lists)
    acquirer_financial_advisors: Mapped[dict | None] = mapped_column(JSONB)
    target_financial_advisors: Mapped[dict | None] = mapped_column(JSONB)
    acquirer_legal_counsel: Mapped[dict | None] = mapped_column(JSONB)
    target_legal_counsel: Mapped[dict | None] = mapped_column(JSONB)

    # Regulatory
    regulatory_approvals_required: Mapped[dict | None] = mapped_column(JSONB)
    regulatory_status: Mapped[str | None] = mapped_column(String(30))

    # Sector
    target_gics_sector: Mapped[str | None] = mapped_column(String(100))
    target_gics_industry: Mapped[str | None] = mapped_column(String(100))

    # Source
    source_filings: Mapped[dict | None] = mapped_column(JSONB)
    primary_source: Mapped[str | None] = mapped_column(String(20))
    corporate_action_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("corporate_actions.action_id")
    )

    __table_args__ = (
        Index("idx_deal_announcement", "announcement_date"),
        Index("idx_deal_sector", "target_gics_sector"),
    )
