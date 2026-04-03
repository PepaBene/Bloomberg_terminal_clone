"""Pydantic schemas for D3 Company Fundamentals endpoints."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


# --- Filing ---

class FilingResponse(BaseModel):
    filing_id: uuid.UUID
    entity_id: uuid.UUID
    filing_type: str
    accession_number: str
    filing_date: date
    period_end_date: date
    fiscal_year: int
    fiscal_quarter: int | None = None
    period_type: str | None = None
    processing_status: str = "PENDING"
    is_amendment: bool = False
    is_restatement: bool = False
    document_url: str | None = None
    file_number: str | None = None
    acceptance_datetime: datetime | None = None
    source: str
    processed_at: datetime | None = None
    amends_filing_id: uuid.UUID | None = None
    amendment_type: str | None = None
    restated_filing_id: uuid.UUID | None = None
    restatement_reason: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


# --- Income Statement ---

class IncomeStatementResponse(BaseModel):
    statement_id: uuid.UUID
    period_id: uuid.UUID
    # Revenue
    total_revenue: Decimal | None = None
    cost_of_revenue: Decimal | None = None
    gross_profit: Decimal | None = None
    # Operating expenses
    research_development: Decimal | None = None
    selling_general_admin: Decimal | None = None
    depreciation_amortization: Decimal | None = None
    other_operating_expense: Decimal | None = None
    total_operating_expense: Decimal | None = None
    operating_income: Decimal | None = None
    # Non-operating
    interest_income: Decimal | None = None
    interest_expense: Decimal | None = None
    net_interest: Decimal | None = None
    other_income_expense: Decimal | None = None
    pretax_income: Decimal | None = None
    # Tax
    income_tax_expense: Decimal | None = None
    effective_tax_rate: Decimal | None = None
    # Net income
    discontinued_operations: Decimal | None = None
    net_income_continuing: Decimal | None = None
    net_income: Decimal | None = None
    net_income_to_common: Decimal | None = None
    net_income_to_noncontrolling: Decimal | None = None
    preferred_dividends: Decimal | None = None
    # Per share
    basic_shares_outstanding: Decimal | None = None
    diluted_shares_outstanding: Decimal | None = None
    basic_eps: Decimal | None = None
    diluted_eps: Decimal | None = None
    # Non-GAAP adjustments
    stock_based_compensation: Decimal | None = None
    restructuring_charges: Decimal | None = None
    impairment_charges: Decimal | None = None
    acquisition_costs: Decimal | None = None
    litigation_settlements: Decimal | None = None
    # Derived
    ebitda: Decimal | None = None
    adjusted_ebitda: Decimal | None = None

    model_config = {"from_attributes": True}


# --- Balance Sheet ---

class BalanceSheetResponse(BaseModel):
    statement_id: uuid.UUID
    period_id: uuid.UUID
    # Current assets
    cash_and_equivalents: Decimal | None = None
    short_term_investments: Decimal | None = None
    cash_and_short_term: Decimal | None = None
    accounts_receivable: Decimal | None = None
    inventory: Decimal | None = None
    prepaid_expenses: Decimal | None = None
    other_current_assets: Decimal | None = None
    total_current_assets: Decimal | None = None
    # Non-current assets
    ppe_gross: Decimal | None = None
    accumulated_depreciation: Decimal | None = None
    ppe_net: Decimal | None = None
    goodwill: Decimal | None = None
    intangible_assets: Decimal | None = None
    long_term_investments: Decimal | None = None
    deferred_tax_assets: Decimal | None = None
    other_non_current_assets: Decimal | None = None
    total_non_current_assets: Decimal | None = None
    total_assets: Decimal | None = None
    # Current liabilities
    accounts_payable: Decimal | None = None
    short_term_debt: Decimal | None = None
    current_portion_ltd: Decimal | None = None
    accrued_liabilities: Decimal | None = None
    deferred_revenue_current: Decimal | None = None
    other_current_liabilities: Decimal | None = None
    total_current_liabilities: Decimal | None = None
    # Non-current liabilities
    long_term_debt: Decimal | None = None
    deferred_tax_liabilities: Decimal | None = None
    deferred_revenue_nc: Decimal | None = None
    pension_liabilities: Decimal | None = None
    other_nc_liabilities: Decimal | None = None
    total_nc_liabilities: Decimal | None = None
    total_liabilities: Decimal | None = None
    # Equity
    common_stock: Decimal | None = None
    additional_paid_in_capital: Decimal | None = None
    retained_earnings: Decimal | None = None
    treasury_stock: Decimal | None = None
    aoci: Decimal | None = None
    total_common_equity: Decimal | None = None
    preferred_equity: Decimal | None = None
    noncontrolling_interest: Decimal | None = None
    total_equity: Decimal | None = None
    total_liabilities_and_equity: Decimal | None = None
    # Derived
    total_debt: Decimal | None = None
    net_debt: Decimal | None = None
    working_capital: Decimal | None = None
    tangible_book_value: Decimal | None = None

    model_config = {"from_attributes": True}


# --- Cash Flow ---

class CashFlowStatementResponse(BaseModel):
    statement_id: uuid.UUID
    period_id: uuid.UUID
    # Operating
    net_income: Decimal | None = None
    depreciation_amortization: Decimal | None = None
    stock_based_comp: Decimal | None = None
    deferred_taxes: Decimal | None = None
    impairment_charges: Decimal | None = None
    other_non_cash: Decimal | None = None
    change_in_receivables: Decimal | None = None
    change_in_inventory: Decimal | None = None
    change_in_payables: Decimal | None = None
    change_in_other_wc: Decimal | None = None
    cash_from_operations: Decimal | None = None
    # Investing
    capital_expenditures: Decimal | None = None
    acquisitions: Decimal | None = None
    divestitures: Decimal | None = None
    investment_purchases: Decimal | None = None
    investment_sales: Decimal | None = None
    other_investing: Decimal | None = None
    cash_from_investing: Decimal | None = None
    # Financing
    debt_issued: Decimal | None = None
    debt_repaid: Decimal | None = None
    stock_issued: Decimal | None = None
    stock_repurchased: Decimal | None = None
    dividends_paid: Decimal | None = None
    other_financing: Decimal | None = None
    cash_from_financing: Decimal | None = None
    # Net
    fx_effect: Decimal | None = None
    net_change_in_cash: Decimal | None = None
    beginning_cash: Decimal | None = None
    ending_cash: Decimal | None = None
    # Derived
    free_cash_flow: Decimal | None = None
    fcf_to_equity: Decimal | None = None

    model_config = {"from_attributes": True}


# --- Financial Period (combined) ---

class FinancialPeriodResponse(BaseModel):
    period_id: uuid.UUID
    entity_id: uuid.UUID
    filing_id: uuid.UUID | None = None
    period_start_date: date | None = None
    period_end_date: date
    period_type: str
    fiscal_year: int
    fiscal_quarter: int | None = None
    reporting_currency: str | None = None
    accounting_standard: str | None = None
    data_version: str = "AS_REPORTED"
    audit_opinion: str | None = None
    auditor_name: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class FundamentalsResponse(BaseModel):
    """Combined fundamentals: period + all 3 statements."""
    period: FinancialPeriodResponse
    income_statement: IncomeStatementResponse | None = None
    balance_sheet: BalanceSheetResponse | None = None
    cash_flow: CashFlowStatementResponse | None = None


# --- Segment ---

class SegmentDataResponse(BaseModel):
    segment_id: uuid.UUID
    period_id: uuid.UUID | None = None
    entity_id: uuid.UUID | None = None
    segment_type: str
    segment_name: str
    segment_name_normalized: str | None = None
    revenue: Decimal | None = None
    operating_income: Decimal | None = None
    operating_margin: Decimal | None = None
    assets: Decimal | None = None
    depreciation: Decimal | None = None
    capex: Decimal | None = None
    custom_metrics: dict | None = None

    model_config = {"from_attributes": True}


# --- KPI ---

class KPIValueResponse(BaseModel):
    id: uuid.UUID
    entity_id: uuid.UUID
    period_id: uuid.UUID
    kpi_id: uuid.UUID
    kpi_code: str | None = None
    kpi_name: str | None = None
    value: Decimal
    source: str | None = None
    is_reported: bool = True

    model_config = {"from_attributes": True}


# --- Screen Request ---

class FundamentalsScreenRequest(BaseModel):
    min_revenue: Decimal | None = None
    max_revenue: Decimal | None = None
    min_net_income: Decimal | None = None
    min_total_assets: Decimal | None = None
    period_type: str | None = None
    fiscal_year: int | None = None
    country: str | None = None
