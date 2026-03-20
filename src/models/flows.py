"""Pillar 2: Institutional Flow Analytics models (E6)."""

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class InstitutionalFlowSignal(TimestampMixin, Base):
    """Aggregated institutional flow signals per security per quarter.

    Computed by E6 from raw ``InstitutionalHolding`` rows.  Each row
    summarises position-change counts, net flow, breadth, conviction,
    smart-money signals, trend detection, and short-interest integration.
    """

    __tablename__ = "institutional_flow_signals"

    signal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id"), nullable=False
    )
    report_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Position change counts
    new_positions_count: Mapped[int | None] = mapped_column(Integer)
    closed_positions_count: Mapped[int | None] = mapped_column(Integer)
    increased_positions_count: Mapped[int | None] = mapped_column(Integer)
    decreased_positions_count: Mapped[int | None] = mapped_column(Integer)
    unchanged_positions_count: Mapped[int | None] = mapped_column(Integer)

    # Net flow
    net_shares_change: Mapped[float | None] = mapped_column(Numeric(20, 2))
    net_value_change: Mapped[float | None] = mapped_column(Numeric(20, 2))

    # Breadth & conviction
    buy_sell_ratio: Mapped[float | None] = mapped_column(Numeric(8, 4))
    breadth_score: Mapped[float | None] = mapped_column(Numeric(8, 4))  # -1 to +1
    conviction_score: Mapped[float | None] = mapped_column(Numeric(8, 4))

    # Smart money (whale-tier)
    whale_net_shares: Mapped[float | None] = mapped_column(Numeric(20, 2))
    whale_net_value: Mapped[float | None] = mapped_column(Numeric(20, 2))
    smart_money_flow: Mapped[float | None] = mapped_column(Numeric(8, 4))  # -1 to +1

    # Multi-quarter trend
    flow_trend_3q: Mapped[str | None] = mapped_column(String(20))  # ACCUMULATION/DISTRIBUTION/NEUTRAL
    flow_trend_4q: Mapped[str | None] = mapped_column(String(20))

    # Short interest integration
    short_interest_ratio: Mapped[float | None] = mapped_column(Numeric(8, 4))
    days_to_cover: Mapped[float | None] = mapped_column(Numeric(8, 2))
    squeeze_potential: Mapped[str | None] = mapped_column(String(20))  # HIGH/MODERATE/LOW

    data_quality: Mapped[str] = mapped_column(
        String(20), nullable=False, default="COMPLETE"
    )
    inputs: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        Index("idx_flow_signals_security_date", "security_id", "report_date"),
        Index("idx_flow_signals_date", "report_date"),
    )


class InstitutionAnalytics(TimestampMixin, Base):
    """Derived analytics for an institutional investor.

    Computed by E6 from ``InstitutionalHolding`` history: investment
    style classification, concentration, turnover, sector allocation.
    """

    __tablename__ = "institution_analytics"

    analytics_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("institution_profiles.institution_id"),
        nullable=False,
    )
    report_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Derived classification
    investment_style: Mapped[str | None] = mapped_column(String(30))
    concentration_score: Mapped[float | None] = mapped_column(Numeric(8, 4))
    turnover_rate: Mapped[float | None] = mapped_column(Numeric(8, 4))

    # Position summary
    total_positions: Mapped[int | None] = mapped_column(Integer)
    new_positions: Mapped[int | None] = mapped_column(Integer)
    closed_positions: Mapped[int | None] = mapped_column(Integer)
    total_value: Mapped[float | None] = mapped_column(Numeric(20, 2))

    # Detailed breakdowns
    top_holdings: Mapped[dict | None] = mapped_column(JSONB)
    sector_allocation: Mapped[dict | None] = mapped_column(JSONB)

    data_quality: Mapped[str] = mapped_column(
        String(20), nullable=False, default="COMPLETE"
    )

    __table_args__ = (
        Index("idx_inst_analytics_institution_date", "institution_id", "report_date"),
    )


class FlowAlert(TimestampMixin, Base):
    """Notable institutional flow events (whale moves, activist filings, etc.)."""

    __tablename__ = "flow_alerts"

    alert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    alert_type: Mapped[str] = mapped_column(String(30), nullable=False)
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.security_id"), nullable=False
    )
    institution_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("institution_profiles.institution_id"),
        nullable=True,
    )
    report_date: Mapped[date] = mapped_column(Date, nullable=False)

    headline: Mapped[str] = mapped_column(String(500), nullable=False)
    shares_involved: Mapped[float | None] = mapped_column(Numeric(20, 2))
    value_involved: Mapped[float | None] = mapped_column(Numeric(20, 2))
    percent_of_outstanding: Mapped[float | None] = mapped_column(Numeric(8, 4))

    details: Mapped[dict | None] = mapped_column(JSONB)
    severity: Mapped[str] = mapped_column(String(10), nullable=False, default="INFO")

    __table_args__ = (
        Index("idx_flow_alerts_type_date", "alert_type", "report_date"),
        Index("idx_flow_alerts_security", "security_id"),
    )
