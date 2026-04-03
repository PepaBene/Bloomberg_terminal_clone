"""Domain 3: Company Fundamentals models (Spec Section 5)."""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class Filing(TimestampMixin, Base):
    """SEC/regulatory filings (Spec 5.3)."""

    __tablename__ = "filings"

    filing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    filing_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    accession_number: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    file_number: Mapped[str | None] = mapped_column(String(20))
    filing_date: Mapped[date] = mapped_column(Date, nullable=False)
    acceptance_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    period_end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    fiscal_quarter: Mapped[int | None] = mapped_column(Integer)
    period_type: Mapped[str | None] = mapped_column(String(20))
    processing_status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Amendment tracking
    is_amendment: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    amends_filing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("filings.filing_id")
    )
    amendment_type: Mapped[str | None] = mapped_column(String(100))

    # Restatement tracking
    is_restatement: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    restated_filing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("filings.filing_id")
    )
    restatement_reason: Mapped[str | None] = mapped_column(Text)

    document_url: Mapped[str | None] = mapped_column(String(500))
    source: Mapped[str] = mapped_column(String(50), nullable=False)

    __table_args__ = (
        Index("idx_filings_entity_period", "entity_id", "period_end_date"),
    )


class FinancialPeriod(TimestampMixin, Base):
    """Financial reporting period container (Spec 5.3)."""

    __tablename__ = "financial_periods"

    period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    filing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("filings.filing_id")
    )
    period_start_date: Mapped[date | None] = mapped_column(Date)
    period_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_type: Mapped[str] = mapped_column(String(20), nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    fiscal_quarter: Mapped[int | None] = mapped_column(Integer)
    reporting_currency: Mapped[str | None] = mapped_column(
        String(3), ForeignKey("currencies.currency_code")
    )
    accounting_standard: Mapped[str | None] = mapped_column(String(20))
    data_version: Mapped[str] = mapped_column(String(20), nullable=False, default="AS_REPORTED")
    audit_opinion: Mapped[str | None] = mapped_column(String(30))
    auditor_name: Mapped[str | None] = mapped_column(String(200))

    # Relationships
    income_statement = relationship(
        "IncomeStatement", back_populates="period", uselist=False, lazy="selectin", cascade="all, delete-orphan"
    )
    balance_sheet = relationship(
        "BalanceSheet", back_populates="period", uselist=False, lazy="selectin", cascade="all, delete-orphan"
    )
    cash_flow = relationship(
        "CashFlowStatement", back_populates="period", uselist=False, lazy="selectin", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("uq_financial_period", "entity_id", "period_end_date", "data_version", unique=True),
        CheckConstraint("data_version IN ('AS_REPORTED', 'RESTATED', 'PRELIMINARY')", name="ck_financial_period_data_version"),
    )


class IncomeStatement(Base):
    """Income statement data (Spec 5.3)."""

    __tablename__ = "income_statements"

    statement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("financial_periods.period_id"), nullable=False, unique=True
    )

    # Revenue
    total_revenue: Mapped[float | None] = mapped_column(Numeric(20, 2))
    cost_of_revenue: Mapped[float | None] = mapped_column(Numeric(20, 2))
    gross_profit: Mapped[float | None] = mapped_column(Numeric(20, 2))

    # Operating expenses
    research_development: Mapped[float | None] = mapped_column(Numeric(20, 2))
    selling_general_admin: Mapped[float | None] = mapped_column(Numeric(20, 2))
    depreciation_amortization: Mapped[float | None] = mapped_column(Numeric(20, 2))
    other_operating_expense: Mapped[float | None] = mapped_column(Numeric(20, 2))
    total_operating_expense: Mapped[float | None] = mapped_column(Numeric(20, 2))
    operating_income: Mapped[float | None] = mapped_column(Numeric(20, 2))

    # Non-operating
    interest_income: Mapped[float | None] = mapped_column(Numeric(20, 2))
    interest_expense: Mapped[float | None] = mapped_column(Numeric(20, 2))
    net_interest: Mapped[float | None] = mapped_column(Numeric(20, 2))
    other_income_expense: Mapped[float | None] = mapped_column(Numeric(20, 2))
    pretax_income: Mapped[float | None] = mapped_column(Numeric(20, 2))

    # Tax
    income_tax_expense: Mapped[float | None] = mapped_column(Numeric(20, 2))
    effective_tax_rate: Mapped[float | None] = mapped_column(Numeric(8, 6))

    # Net income
    discontinued_operations: Mapped[float | None] = mapped_column(Numeric(20, 2))
    net_income_continuing: Mapped[float | None] = mapped_column(Numeric(20, 2))
    net_income: Mapped[float | None] = mapped_column(Numeric(20, 2))
    net_income_to_common: Mapped[float | None] = mapped_column(Numeric(20, 2))
    net_income_to_noncontrolling: Mapped[float | None] = mapped_column(Numeric(20, 2))
    preferred_dividends: Mapped[float | None] = mapped_column(Numeric(20, 2))

    # Per share
    basic_shares_outstanding: Mapped[float | None] = mapped_column(Numeric(20, 2))
    diluted_shares_outstanding: Mapped[float | None] = mapped_column(Numeric(20, 2))
    basic_eps: Mapped[float | None] = mapped_column(Numeric(10, 4))
    diluted_eps: Mapped[float | None] = mapped_column(Numeric(10, 4))

    # Non-GAAP adjustments
    stock_based_compensation: Mapped[float | None] = mapped_column(Numeric(20, 2))
    restructuring_charges: Mapped[float | None] = mapped_column(Numeric(20, 2))
    impairment_charges: Mapped[float | None] = mapped_column(Numeric(20, 2))
    acquisition_costs: Mapped[float | None] = mapped_column(Numeric(20, 2))
    litigation_settlements: Mapped[float | None] = mapped_column(Numeric(20, 2))

    # Derived
    ebitda: Mapped[float | None] = mapped_column(Numeric(20, 2))
    adjusted_ebitda: Mapped[float | None] = mapped_column(Numeric(20, 2))

    period = relationship("FinancialPeriod", back_populates="income_statement")


class BalanceSheet(Base):
    """Balance sheet data (Spec 5.3)."""

    __tablename__ = "balance_sheets"

    statement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("financial_periods.period_id"), nullable=False, unique=True
    )

    # Current assets
    cash_and_equivalents: Mapped[float | None] = mapped_column(Numeric(20, 2))
    short_term_investments: Mapped[float | None] = mapped_column(Numeric(20, 2))
    cash_and_short_term: Mapped[float | None] = mapped_column(Numeric(20, 2))
    accounts_receivable: Mapped[float | None] = mapped_column(Numeric(20, 2))
    inventory: Mapped[float | None] = mapped_column(Numeric(20, 2))
    prepaid_expenses: Mapped[float | None] = mapped_column(Numeric(20, 2))
    other_current_assets: Mapped[float | None] = mapped_column(Numeric(20, 2))
    total_current_assets: Mapped[float | None] = mapped_column(Numeric(20, 2))

    # Non-current assets
    ppe_gross: Mapped[float | None] = mapped_column(Numeric(20, 2))
    accumulated_depreciation: Mapped[float | None] = mapped_column(Numeric(20, 2))
    ppe_net: Mapped[float | None] = mapped_column(Numeric(20, 2))
    goodwill: Mapped[float | None] = mapped_column(Numeric(20, 2))
    intangible_assets: Mapped[float | None] = mapped_column(Numeric(20, 2))
    long_term_investments: Mapped[float | None] = mapped_column(Numeric(20, 2))
    deferred_tax_assets: Mapped[float | None] = mapped_column(Numeric(20, 2))
    other_non_current_assets: Mapped[float | None] = mapped_column(Numeric(20, 2))
    total_non_current_assets: Mapped[float | None] = mapped_column(Numeric(20, 2))
    total_assets: Mapped[float | None] = mapped_column(Numeric(20, 2))

    # Current liabilities
    accounts_payable: Mapped[float | None] = mapped_column(Numeric(20, 2))
    short_term_debt: Mapped[float | None] = mapped_column(Numeric(20, 2))
    current_portion_ltd: Mapped[float | None] = mapped_column(Numeric(20, 2))
    accrued_liabilities: Mapped[float | None] = mapped_column(Numeric(20, 2))
    deferred_revenue_current: Mapped[float | None] = mapped_column(Numeric(20, 2))
    other_current_liabilities: Mapped[float | None] = mapped_column(Numeric(20, 2))
    total_current_liabilities: Mapped[float | None] = mapped_column(Numeric(20, 2))

    # Non-current liabilities
    long_term_debt: Mapped[float | None] = mapped_column(Numeric(20, 2))
    deferred_tax_liabilities: Mapped[float | None] = mapped_column(Numeric(20, 2))
    deferred_revenue_nc: Mapped[float | None] = mapped_column(Numeric(20, 2))
    pension_liabilities: Mapped[float | None] = mapped_column(Numeric(20, 2))
    other_nc_liabilities: Mapped[float | None] = mapped_column(Numeric(20, 2))
    total_nc_liabilities: Mapped[float | None] = mapped_column(Numeric(20, 2))
    total_liabilities: Mapped[float | None] = mapped_column(Numeric(20, 2))

    # Equity
    common_stock: Mapped[float | None] = mapped_column(Numeric(20, 2))
    additional_paid_in_capital: Mapped[float | None] = mapped_column(Numeric(20, 2))
    retained_earnings: Mapped[float | None] = mapped_column(Numeric(20, 2))
    treasury_stock: Mapped[float | None] = mapped_column(Numeric(20, 2))
    aoci: Mapped[float | None] = mapped_column(Numeric(20, 2))
    total_common_equity: Mapped[float | None] = mapped_column(Numeric(20, 2))
    preferred_equity: Mapped[float | None] = mapped_column(Numeric(20, 2))
    noncontrolling_interest: Mapped[float | None] = mapped_column(Numeric(20, 2))
    total_equity: Mapped[float | None] = mapped_column(Numeric(20, 2))
    total_liabilities_and_equity: Mapped[float | None] = mapped_column(Numeric(20, 2))

    # Derived
    total_debt: Mapped[float | None] = mapped_column(Numeric(20, 2))
    net_debt: Mapped[float | None] = mapped_column(Numeric(20, 2))
    working_capital: Mapped[float | None] = mapped_column(Numeric(20, 2))
    tangible_book_value: Mapped[float | None] = mapped_column(Numeric(20, 2))

    period = relationship("FinancialPeriod", back_populates="balance_sheet")


class CashFlowStatement(Base):
    """Cash flow statement data (Spec 5.3)."""

    __tablename__ = "cash_flow_statements"

    statement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("financial_periods.period_id"), nullable=False, unique=True
    )

    # Operating
    net_income: Mapped[float | None] = mapped_column(Numeric(20, 2))
    depreciation_amortization: Mapped[float | None] = mapped_column(Numeric(20, 2))
    stock_based_comp: Mapped[float | None] = mapped_column(Numeric(20, 2))
    deferred_taxes: Mapped[float | None] = mapped_column(Numeric(20, 2))
    impairment_charges: Mapped[float | None] = mapped_column(Numeric(20, 2))
    other_non_cash: Mapped[float | None] = mapped_column(Numeric(20, 2))
    change_in_receivables: Mapped[float | None] = mapped_column(Numeric(20, 2))
    change_in_inventory: Mapped[float | None] = mapped_column(Numeric(20, 2))
    change_in_payables: Mapped[float | None] = mapped_column(Numeric(20, 2))
    change_in_other_wc: Mapped[float | None] = mapped_column(Numeric(20, 2))
    cash_from_operations: Mapped[float | None] = mapped_column(Numeric(20, 2))

    # Investing
    capital_expenditures: Mapped[float | None] = mapped_column(Numeric(20, 2))
    acquisitions: Mapped[float | None] = mapped_column(Numeric(20, 2))
    divestitures: Mapped[float | None] = mapped_column(Numeric(20, 2))
    investment_purchases: Mapped[float | None] = mapped_column(Numeric(20, 2))
    investment_sales: Mapped[float | None] = mapped_column(Numeric(20, 2))
    other_investing: Mapped[float | None] = mapped_column(Numeric(20, 2))
    cash_from_investing: Mapped[float | None] = mapped_column(Numeric(20, 2))

    # Financing
    debt_issued: Mapped[float | None] = mapped_column(Numeric(20, 2))
    debt_repaid: Mapped[float | None] = mapped_column(Numeric(20, 2))
    stock_issued: Mapped[float | None] = mapped_column(Numeric(20, 2))
    stock_repurchased: Mapped[float | None] = mapped_column(Numeric(20, 2))
    dividends_paid: Mapped[float | None] = mapped_column(Numeric(20, 2))
    other_financing: Mapped[float | None] = mapped_column(Numeric(20, 2))
    cash_from_financing: Mapped[float | None] = mapped_column(Numeric(20, 2))

    # Net
    fx_effect: Mapped[float | None] = mapped_column(Numeric(20, 2))
    net_change_in_cash: Mapped[float | None] = mapped_column(Numeric(20, 2))
    beginning_cash: Mapped[float | None] = mapped_column(Numeric(20, 2))
    ending_cash: Mapped[float | None] = mapped_column(Numeric(20, 2))

    # Derived
    free_cash_flow: Mapped[float | None] = mapped_column(Numeric(20, 2))
    fcf_to_equity: Mapped[float | None] = mapped_column(Numeric(20, 2))

    period = relationship("FinancialPeriod", back_populates="cash_flow")


class SegmentData(TimestampMixin, Base):
    """Business/geographic segment data (Spec 5.3)."""

    __tablename__ = "segment_data"

    segment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("financial_periods.period_id"), nullable=False
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    segment_type: Mapped[str] = mapped_column(String(20), nullable=False)
    segment_name: Mapped[str] = mapped_column(String(200), nullable=False)
    segment_name_normalized: Mapped[str | None] = mapped_column(String(200))
    revenue: Mapped[float | None] = mapped_column(Numeric(20, 2))
    operating_income: Mapped[float | None] = mapped_column(Numeric(20, 2))
    operating_margin: Mapped[float | None] = mapped_column(Numeric(8, 4))
    assets: Mapped[float | None] = mapped_column(Numeric(20, 2))
    depreciation: Mapped[float | None] = mapped_column(Numeric(20, 2))
    capex: Mapped[float | None] = mapped_column(Numeric(20, 2))
    custom_metrics: Mapped[dict | None] = mapped_column(JSONB)


class KPIDefinition(Base):
    """Industry KPI definitions (Spec 5.3)."""

    __tablename__ = "kpi_definitions"

    kpi_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kpi_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    kpi_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    applicable_industries: Mapped[dict | None] = mapped_column(JSONB)
    data_type: Mapped[str | None] = mapped_column(String(20))
    unit: Mapped[str | None] = mapped_column(String(50))
    calculation_formula: Mapped[str | None] = mapped_column(Text)


class KPIValue(TimestampMixin, Base):
    """KPI values per entity per period (Spec 5.3)."""

    __tablename__ = "kpi_values"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("financial_periods.period_id"), nullable=False
    )
    kpi_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kpi_definitions.kpi_id"), nullable=False
    )
    value: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)
    source: Mapped[str | None] = mapped_column(String(50))
    is_reported: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index("idx_kpi_values_entity_period", "entity_id", "period_id"),
        Index("idx_kpi_values_kpi_period", "kpi_id", "period_id"),
    )
