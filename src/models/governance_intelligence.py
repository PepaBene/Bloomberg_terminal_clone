"""Pillar 3 Phase 1: Governance Intelligence models (proxy, compensation, board, proposals)."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class ProxyFiling(TimestampMixin, Base):
    """DEF 14A proxy filing tracking."""

    __tablename__ = "proxy_filings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.entity_id"),
        nullable=False,
        index=True,
    )
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    filing_date: Mapped[date] = mapped_column(Date, nullable=False)
    meeting_date: Mapped[date | None] = mapped_column(Date)
    filing_accession_number: Mapped[str | None] = mapped_column(String(25))
    filing_url: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (
        Index("uq_proxy_entity_year", "entity_id", "fiscal_year", unique=True),
    )


class ExecutiveCompensation(TimestampMixin, Base):
    """C-suite compensation from proxy statements."""

    __tablename__ = "executive_compensation"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    proxy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("proxy_filings.id"),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.entity_id"),
        nullable=False,
        index=True,
    )
    person_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    total_compensation: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    base_salary: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    bonus: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    stock_awards: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    option_awards: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    non_equity_incentive: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    other_compensation: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    change_in_pension: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    yoy_change_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    pay_ratio_to_median: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    __table_args__ = (
        Index(
            "uq_exec_comp",
            "entity_id", "person_name", "fiscal_year",
            unique=True,
        ),
    )


class BoardMember(TimestampMixin, Base):
    """Board of directors composition from proxy."""

    __tablename__ = "board_members"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    proxy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("proxy_filings.id"),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.entity_id"),
        nullable=False,
        index=True,
    )
    person_name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_independent: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_chair: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tenure_years: Mapped[int | None] = mapped_column(Integer)
    age: Mapped[int | None] = mapped_column(Integer)
    gender: Mapped[str | None] = mapped_column(String(10))
    committees: Mapped[list | None] = mapped_column(JSONB)
    expertise_areas: Mapped[list | None] = mapped_column(JSONB)
    other_boards: Mapped[list | None] = mapped_column(JSONB)

    __table_args__ = (
        Index("uq_board_member", "entity_id", "person_name", "proxy_id", unique=True),
    )


class ShareholderProposal(TimestampMixin, Base):
    """Shareholder proposals from proxy statements."""

    __tablename__ = "shareholder_proposals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    proxy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("proxy_filings.id"),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.entity_id"),
        nullable=False,
        index=True,
    )
    proposal_number: Mapped[int] = mapped_column(Integer, nullable=False)
    topic: Mapped[str | None] = mapped_column(String(30))
    description: Mapped[str | None] = mapped_column(Text)
    proponent: Mapped[str | None] = mapped_column(String(200))
    management_recommendation: Mapped[str | None] = mapped_column(String(10))
    vote_for_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    vote_against_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    vote_abstain_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    passed: Mapped[bool | None] = mapped_column(Boolean)


class GovernanceAssessment(TimestampMixin, Base):
    """Composite governance score and red flags."""

    __tablename__ = "governance_assessments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.entity_id"),
        nullable=False,
        index=True,
    )
    assessment_date: Mapped[date] = mapped_column(Date, nullable=False)
    governance_score: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    classification: Mapped[str | None] = mapped_column(String(20))
    dual_class: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ceo_is_chair: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    board_independence_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    avg_board_tenure: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    has_poison_pill: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_staggered_board: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_majority_voting: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    related_party_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ceo_pay_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    long_term_incentive_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    board_diversity_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    board_interlock_count: Mapped[int | None] = mapped_column(Integer)
    red_flags: Mapped[list | None] = mapped_column(JSONB)

    __table_args__ = (
        Index("uq_governance_entity_date", "entity_id", "assessment_date", unique=True),
    )
