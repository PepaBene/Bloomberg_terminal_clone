"""Pydantic schemas for D3 Company Fundamentals endpoints."""

import uuid
from datetime import date, datetime

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
    total_revenue: float | None = None
    cost_of_revenue: float | None = None
    gross_profit: float | None = None
    # Operating expenses
    research_development: float | None = None
    selling_general_admin: float | None = None
    depreciation_amortization: float | None = None
    other_operating_expense: float | None = None
    total_operating_expense: float | None = None
    operating_income: float | None = None
    # Non-operating
    interest_income: float | None = None
    interest_expense: float | None = None
    net_interest: float | None = None
    other_income_expense: float | None = None
    pretax_income: float | None = None
    # Tax
    income_tax_expense: float | None = None
    effective_tax_rate: float | None = None
    # Net income
    discontinued_operations: float | None = None
    net_income_continuing: float | None = None
    net_income: float | None = None
    net_income_to_common: float | None = None
    net_income_to_noncontrolling: float | None = None
    preferred_dividends: float | None = None
    # Per share
    basic_shares_outstanding: float | None = None
    diluted_shares_outstanding: float | None = None
    basic_eps: float | None = None
    diluted_eps: float | None = None
    # Non-GAAP adjustments
    stock_based_compensation: float | None = None
    restructuring_charges: float | None = None
    impairment_charges: float | None = None
    acquisition_costs: float | None = None
    litigation_settlements: float | None = None
    # Derived
    ebitda: float | None = None
    adjusted_ebitda: float | None = None

    model_config = {"from_attributes": True}


# --- Balance Sheet ---

class BalanceSheetResponse(BaseModel):
    statement_id: uuid.UUID
    period_id: uuid.UUID
    # Current assets
    cash_and_equivalents: float | None = None
    short_term_investments: float | None = None
    cash_and_short_term: float | None = None
    accounts_receivable: float | None = None
    inventory: float | None = None
    prepaid_expenses: float | None = None
    other_current_assets: float | None = None
    total_current_assets: float | None = None
    # Non-current assets
    ppe_gross: float | None = None
    accumulated_depreciation: float | None = None
    ppe_net: float | None = None
    goodwill: float | None = None
    intangible_assets: float | None = None
    long_term_investments: float | None = None
    deferred_tax_assets: float | None = None
    other_non_current_assets: float | None = None
    total_non_current_assets: float | None = None
    total_assets: float | None = None
    # Current liabilities
    accounts_payable: float | None = None
    short_term_debt: float | None = None
    current_portion_ltd: float | None = None
    accrued_liabilities: float | None = None
    deferred_revenue_current: float | None = None
    other_current_liabilities: float | None = None
    total_current_liabilities: float | None = None
    # Non-current liabilities
    long_term_debt: float | None = None
    deferred_tax_liabilities: float | None = None
    deferred_revenue_nc: float | None = None
    pension_liabilities: float | None = None
    other_nc_liabilities: float | None = None
    total_nc_liabilities: float | None = None
    total_liabilities: float | None = None
    # Equity
    common_stock: float | None = None
    additional_paid_in_capital: float | None = None
    retained_earnings: float | None = None
    treasury_stock: float | None = None
    aoci: float | None = None
    total_common_equity: float | None = None
    preferred_equity: float | None = None
    noncontrolling_interest: float | None = None
    total_equity: float | None = None
    total_liabilities_and_equity: float | None = None
    # Derived
    total_debt: float | None = None
    net_debt: float | None = None
    working_capital: float | None = None
    tangible_book_value: float | None = None

    model_config = {"from_attributes": True}


# --- Cash Flow ---

class CashFlowStatementResponse(BaseModel):
    statement_id: uuid.UUID
    period_id: uuid.UUID
    # Operating
    net_income: float | None = None
    depreciation_amortization: float | None = None
    stock_based_comp: float | None = None
    deferred_taxes: float | None = None
    impairment_charges: float | None = None
    other_non_cash: float | None = None
    change_in_receivables: float | None = None
    change_in_inventory: float | None = None
    change_in_payables: float | None = None
    change_in_other_wc: float | None = None
    cash_from_operations: float | None = None
    # Investing
    capital_expenditures: float | None = None
    acquisitions: float | None = None
    divestitures: float | None = None
    investment_purchases: float | None = None
    investment_sales: float | None = None
    other_investing: float | None = None
    cash_from_investing: float | None = None
    # Financing
    debt_issued: float | None = None
    debt_repaid: float | None = None
    stock_issued: float | None = None
    stock_repurchased: float | None = None
    dividends_paid: float | None = None
    other_financing: float | None = None
    cash_from_financing: float | None = None
    # Net
    fx_effect: float | None = None
    net_change_in_cash: float | None = None
    beginning_cash: float | None = None
    ending_cash: float | None = None
    # Derived
    free_cash_flow: float | None = None
    fcf_to_equity: float | None = None

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
    revenue: float | None = None
    operating_income: float | None = None
    operating_margin: float | None = None
    assets: float | None = None
    depreciation: float | None = None
    capex: float | None = None
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
    value: float
    source: str | None = None
    is_reported: bool = True

    model_config = {"from_attributes": True}


# --- Screen Request ---

class FundamentalsScreenRequest(BaseModel):
    min_revenue: float | None = None
    max_revenue: float | None = None
    min_net_income: float | None = None
    min_total_assets: float | None = None
    period_type: str | None = None
    fiscal_year: int | None = None
    country: str | None = None
