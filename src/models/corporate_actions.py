"""Domain 5: Corporate Actions models (Spec Section 7)."""

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class CorporateAction(TimestampMixin, Base):
    """Canonical corporate action event (Spec 7.3)."""

    __tablename__ = "corporate_actions"

    # Primary identification
    action_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    action_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    action_subtype: Mapped[str | None] = mapped_column(String(50))

    # Links
    security_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id"), index=True
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), index=True
    )

    # Key dates
    announcement_date: Mapped[date | None] = mapped_column(Date)
    ex_date: Mapped[date | None] = mapped_column(Date, index=True)
    record_date: Mapped[date | None] = mapped_column(Date)
    payment_date: Mapped[date | None] = mapped_column(Date)

    # Status & metadata
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(50), nullable=False)

    # Relationships
    dividend_action = relationship(
        "DividendAction", back_populates="corporate_action", uselist=False, lazy="selectin"
    )
    split_action = relationship(
        "SplitAction", back_populates="corporate_action", uselist=False, lazy="selectin"
    )
    ma_action = relationship(
        "MergerAcquisitionAction", back_populates="corporate_action", uselist=False, lazy="selectin"
    )

    __table_args__ = (
        Index("idx_ca_security_date", "security_id", "ex_date"),
        Index("idx_ca_entity", "entity_id"),
        Index("idx_ca_type_status", "action_type", "status"),
    )


class DividendAction(Base):
    """Dividend-specific details (Spec 7.3)."""

    __tablename__ = "dividend_actions"

    action_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("corporate_actions.action_id"), primary_key=True
    )
    dividend_type: Mapped[str] = mapped_column(String(30), nullable=False)
    frequency: Mapped[str | None] = mapped_column(String(20))
    gross_amount: Mapped[float | None] = mapped_column(Numeric(10, 6))
    currency: Mapped[str | None] = mapped_column(
        String(3), ForeignKey("currencies.currency_code")
    )
    tax_rate: Mapped[float | None] = mapped_column(Numeric(5, 4))
    qualified: Mapped[bool | None] = mapped_column(Boolean)
    stock_dividend_ratio: Mapped[float | None] = mapped_column(Numeric(10, 6))

    corporate_action = relationship("CorporateAction", back_populates="dividend_action")


class SplitAction(Base):
    """Stock split / reverse split details (Spec 7.3)."""

    __tablename__ = "split_actions"

    action_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("corporate_actions.action_id"), primary_key=True
    )
    split_ratio_from: Mapped[int] = mapped_column(Integer, nullable=False)
    split_ratio_to: Mapped[int] = mapped_column(Integer, nullable=False)
    split_factor: Mapped[float | None] = mapped_column(Numeric(10, 6))
    adjustment_factor: Mapped[float | None] = mapped_column(Numeric(18, 10))

    corporate_action = relationship("CorporateAction", back_populates="split_action")


class MergerAcquisitionAction(Base):
    """M&A-specific details (Spec 7.3)."""

    __tablename__ = "ma_actions"

    action_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("corporate_actions.action_id"), primary_key=True
    )
    transaction_type: Mapped[str] = mapped_column(String(30), nullable=False)

    # Parties
    acquirer_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id")
    )
    target_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id")
    )

    # Financials
    deal_value: Mapped[float | None] = mapped_column(Numeric(20, 2))
    deal_currency: Mapped[str | None] = mapped_column(
        String(3), ForeignKey("currencies.currency_code")
    )
    price_per_share: Mapped[float | None] = mapped_column(Numeric(18, 6))
    cash_component: Mapped[float | None] = mapped_column(Numeric(18, 6))
    stock_component: Mapped[float | None] = mapped_column(Numeric(18, 6))
    consideration_type: Mapped[str | None] = mapped_column(String(20))

    # Premium metrics
    premium_1day: Mapped[float | None] = mapped_column(Numeric(8, 4))
    premium_30day: Mapped[float | None] = mapped_column(Numeric(8, 4))

    # Deal terms
    conditions: Mapped[dict | None] = mapped_column(JSONB)
    termination_fee: Mapped[float | None] = mapped_column(Numeric(20, 2))

    corporate_action = relationship("CorporateAction", back_populates="ma_action")
