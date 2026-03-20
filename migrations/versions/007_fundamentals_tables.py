"""Create company fundamentals tables.

Revision ID: 007
Revises: 006
Create Date: 2026-03-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- filings ---
    op.create_table(
        "filings",
        sa.Column("filing_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), nullable=False),
        sa.Column("filing_type", sa.String(20), nullable=False),
        sa.Column("accession_number", sa.String(30), nullable=False, unique=True),
        sa.Column("file_number", sa.String(20)),
        sa.Column("filing_date", sa.Date(), nullable=False),
        sa.Column("acceptance_datetime", sa.DateTime(timezone=True)),
        sa.Column("period_end_date", sa.Date(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("fiscal_quarter", sa.Integer()),
        sa.Column("period_type", sa.String(20)),
        sa.Column("processing_status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("is_amendment", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("amends_filing_id", UUID(as_uuid=True), sa.ForeignKey("filings.filing_id")),
        sa.Column("amendment_type", sa.String(100)),
        sa.Column("is_restatement", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("restated_filing_id", UUID(as_uuid=True), sa.ForeignKey("filings.filing_id")),
        sa.Column("restatement_reason", sa.Text()),
        sa.Column("document_url", sa.String(500)),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_filings_entity", "filings", ["entity_id"])
    op.create_index("idx_filings_type", "filings", ["filing_type"])
    op.create_index("idx_filings_period", "filings", ["period_end_date"])
    op.create_index("idx_filings_entity_period", "filings", ["entity_id", "period_end_date"])

    # --- financial_periods ---
    op.create_table(
        "financial_periods",
        sa.Column("period_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), nullable=False),
        sa.Column("filing_id", UUID(as_uuid=True), sa.ForeignKey("filings.filing_id")),
        sa.Column("period_start_date", sa.Date()),
        sa.Column("period_end_date", sa.Date(), nullable=False),
        sa.Column("period_type", sa.String(20), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("fiscal_quarter", sa.Integer()),
        sa.Column("reporting_currency", sa.String(3), sa.ForeignKey("currencies.currency_code")),
        sa.Column("accounting_standard", sa.String(20)),
        sa.Column("data_version", sa.String(20), nullable=False, server_default="AS_REPORTED"),
        sa.Column("audit_opinion", sa.String(30)),
        sa.Column("auditor_name", sa.String(200)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_fp_entity", "financial_periods", ["entity_id"])
    op.create_index("uq_financial_period", "financial_periods", ["entity_id", "period_end_date", "data_version"], unique=True)

    # --- income_statements ---
    op.create_table(
        "income_statements",
        sa.Column("statement_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("period_id", UUID(as_uuid=True), sa.ForeignKey("financial_periods.period_id"), nullable=False, unique=True),
        sa.Column("total_revenue", sa.Numeric(20, 2)),
        sa.Column("cost_of_revenue", sa.Numeric(20, 2)),
        sa.Column("gross_profit", sa.Numeric(20, 2)),
        sa.Column("research_development", sa.Numeric(20, 2)),
        sa.Column("selling_general_admin", sa.Numeric(20, 2)),
        sa.Column("depreciation_amortization", sa.Numeric(20, 2)),
        sa.Column("other_operating_expense", sa.Numeric(20, 2)),
        sa.Column("total_operating_expense", sa.Numeric(20, 2)),
        sa.Column("operating_income", sa.Numeric(20, 2)),
        sa.Column("interest_income", sa.Numeric(20, 2)),
        sa.Column("interest_expense", sa.Numeric(20, 2)),
        sa.Column("net_interest", sa.Numeric(20, 2)),
        sa.Column("other_income_expense", sa.Numeric(20, 2)),
        sa.Column("pretax_income", sa.Numeric(20, 2)),
        sa.Column("income_tax_expense", sa.Numeric(20, 2)),
        sa.Column("effective_tax_rate", sa.Numeric(8, 6)),
        sa.Column("discontinued_operations", sa.Numeric(20, 2)),
        sa.Column("net_income_continuing", sa.Numeric(20, 2)),
        sa.Column("net_income", sa.Numeric(20, 2)),
        sa.Column("net_income_to_common", sa.Numeric(20, 2)),
        sa.Column("net_income_to_noncontrolling", sa.Numeric(20, 2)),
        sa.Column("preferred_dividends", sa.Numeric(20, 2)),
        sa.Column("basic_shares_outstanding", sa.Numeric(20, 2)),
        sa.Column("diluted_shares_outstanding", sa.Numeric(20, 2)),
        sa.Column("basic_eps", sa.Numeric(10, 4)),
        sa.Column("diluted_eps", sa.Numeric(10, 4)),
        sa.Column("stock_based_compensation", sa.Numeric(20, 2)),
        sa.Column("restructuring_charges", sa.Numeric(20, 2)),
        sa.Column("impairment_charges", sa.Numeric(20, 2)),
        sa.Column("acquisition_costs", sa.Numeric(20, 2)),
        sa.Column("litigation_settlements", sa.Numeric(20, 2)),
        sa.Column("ebitda", sa.Numeric(20, 2)),
        sa.Column("adjusted_ebitda", sa.Numeric(20, 2)),
    )

    # --- balance_sheets ---
    op.create_table(
        "balance_sheets",
        sa.Column("statement_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("period_id", UUID(as_uuid=True), sa.ForeignKey("financial_periods.period_id"), nullable=False, unique=True),
        sa.Column("cash_and_equivalents", sa.Numeric(20, 2)),
        sa.Column("short_term_investments", sa.Numeric(20, 2)),
        sa.Column("cash_and_short_term", sa.Numeric(20, 2)),
        sa.Column("accounts_receivable", sa.Numeric(20, 2)),
        sa.Column("inventory", sa.Numeric(20, 2)),
        sa.Column("prepaid_expenses", sa.Numeric(20, 2)),
        sa.Column("other_current_assets", sa.Numeric(20, 2)),
        sa.Column("total_current_assets", sa.Numeric(20, 2)),
        sa.Column("ppe_gross", sa.Numeric(20, 2)),
        sa.Column("accumulated_depreciation", sa.Numeric(20, 2)),
        sa.Column("ppe_net", sa.Numeric(20, 2)),
        sa.Column("goodwill", sa.Numeric(20, 2)),
        sa.Column("intangible_assets", sa.Numeric(20, 2)),
        sa.Column("long_term_investments", sa.Numeric(20, 2)),
        sa.Column("deferred_tax_assets", sa.Numeric(20, 2)),
        sa.Column("other_non_current_assets", sa.Numeric(20, 2)),
        sa.Column("total_non_current_assets", sa.Numeric(20, 2)),
        sa.Column("total_assets", sa.Numeric(20, 2)),
        sa.Column("accounts_payable", sa.Numeric(20, 2)),
        sa.Column("short_term_debt", sa.Numeric(20, 2)),
        sa.Column("current_portion_ltd", sa.Numeric(20, 2)),
        sa.Column("accrued_liabilities", sa.Numeric(20, 2)),
        sa.Column("deferred_revenue_current", sa.Numeric(20, 2)),
        sa.Column("other_current_liabilities", sa.Numeric(20, 2)),
        sa.Column("total_current_liabilities", sa.Numeric(20, 2)),
        sa.Column("long_term_debt", sa.Numeric(20, 2)),
        sa.Column("deferred_tax_liabilities", sa.Numeric(20, 2)),
        sa.Column("deferred_revenue_nc", sa.Numeric(20, 2)),
        sa.Column("pension_liabilities", sa.Numeric(20, 2)),
        sa.Column("other_nc_liabilities", sa.Numeric(20, 2)),
        sa.Column("total_nc_liabilities", sa.Numeric(20, 2)),
        sa.Column("total_liabilities", sa.Numeric(20, 2)),
        sa.Column("common_stock", sa.Numeric(20, 2)),
        sa.Column("additional_paid_in_capital", sa.Numeric(20, 2)),
        sa.Column("retained_earnings", sa.Numeric(20, 2)),
        sa.Column("treasury_stock", sa.Numeric(20, 2)),
        sa.Column("aoci", sa.Numeric(20, 2)),
        sa.Column("total_common_equity", sa.Numeric(20, 2)),
        sa.Column("preferred_equity", sa.Numeric(20, 2)),
        sa.Column("noncontrolling_interest", sa.Numeric(20, 2)),
        sa.Column("total_equity", sa.Numeric(20, 2)),
        sa.Column("total_liabilities_and_equity", sa.Numeric(20, 2)),
        sa.Column("total_debt", sa.Numeric(20, 2)),
        sa.Column("net_debt", sa.Numeric(20, 2)),
        sa.Column("working_capital", sa.Numeric(20, 2)),
        sa.Column("tangible_book_value", sa.Numeric(20, 2)),
    )

    # --- cash_flow_statements ---
    op.create_table(
        "cash_flow_statements",
        sa.Column("statement_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("period_id", UUID(as_uuid=True), sa.ForeignKey("financial_periods.period_id"), nullable=False, unique=True),
        sa.Column("net_income", sa.Numeric(20, 2)),
        sa.Column("depreciation_amortization", sa.Numeric(20, 2)),
        sa.Column("stock_based_comp", sa.Numeric(20, 2)),
        sa.Column("deferred_taxes", sa.Numeric(20, 2)),
        sa.Column("impairment_charges", sa.Numeric(20, 2)),
        sa.Column("other_non_cash", sa.Numeric(20, 2)),
        sa.Column("change_in_receivables", sa.Numeric(20, 2)),
        sa.Column("change_in_inventory", sa.Numeric(20, 2)),
        sa.Column("change_in_payables", sa.Numeric(20, 2)),
        sa.Column("change_in_other_wc", sa.Numeric(20, 2)),
        sa.Column("cash_from_operations", sa.Numeric(20, 2)),
        sa.Column("capital_expenditures", sa.Numeric(20, 2)),
        sa.Column("acquisitions", sa.Numeric(20, 2)),
        sa.Column("divestitures", sa.Numeric(20, 2)),
        sa.Column("investment_purchases", sa.Numeric(20, 2)),
        sa.Column("investment_sales", sa.Numeric(20, 2)),
        sa.Column("other_investing", sa.Numeric(20, 2)),
        sa.Column("cash_from_investing", sa.Numeric(20, 2)),
        sa.Column("debt_issued", sa.Numeric(20, 2)),
        sa.Column("debt_repaid", sa.Numeric(20, 2)),
        sa.Column("stock_issued", sa.Numeric(20, 2)),
        sa.Column("stock_repurchased", sa.Numeric(20, 2)),
        sa.Column("dividends_paid", sa.Numeric(20, 2)),
        sa.Column("other_financing", sa.Numeric(20, 2)),
        sa.Column("cash_from_financing", sa.Numeric(20, 2)),
        sa.Column("fx_effect", sa.Numeric(20, 2)),
        sa.Column("net_change_in_cash", sa.Numeric(20, 2)),
        sa.Column("beginning_cash", sa.Numeric(20, 2)),
        sa.Column("ending_cash", sa.Numeric(20, 2)),
        sa.Column("free_cash_flow", sa.Numeric(20, 2)),
        sa.Column("fcf_to_equity", sa.Numeric(20, 2)),
    )

    # --- segment_data ---
    op.create_table(
        "segment_data",
        sa.Column("segment_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("period_id", UUID(as_uuid=True), sa.ForeignKey("financial_periods.period_id"), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), nullable=False),
        sa.Column("segment_type", sa.String(20), nullable=False),
        sa.Column("segment_name", sa.String(200), nullable=False),
        sa.Column("segment_name_normalized", sa.String(200)),
        sa.Column("revenue", sa.Numeric(20, 2)),
        sa.Column("operating_income", sa.Numeric(20, 2)),
        sa.Column("operating_margin", sa.Numeric(8, 4)),
        sa.Column("assets", sa.Numeric(20, 2)),
        sa.Column("depreciation", sa.Numeric(20, 2)),
        sa.Column("capex", sa.Numeric(20, 2)),
        sa.Column("custom_metrics", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_segment_entity", "segment_data", ["entity_id"])

    # --- kpi_definitions ---
    op.create_table(
        "kpi_definitions",
        sa.Column("kpi_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("kpi_code", sa.String(50), nullable=False, unique=True),
        sa.Column("kpi_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("applicable_industries", JSONB),
        sa.Column("data_type", sa.String(20)),
        sa.Column("unit", sa.String(50)),
        sa.Column("calculation_formula", sa.Text()),
    )

    # --- kpi_values ---
    op.create_table(
        "kpi_values",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.entity_id"), nullable=False),
        sa.Column("period_id", UUID(as_uuid=True), sa.ForeignKey("financial_periods.period_id"), nullable=False),
        sa.Column("kpi_id", UUID(as_uuid=True), sa.ForeignKey("kpi_definitions.kpi_id"), nullable=False),
        sa.Column("value", sa.Numeric(20, 6), nullable=False),
        sa.Column("source", sa.String(50)),
        sa.Column("is_reported", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_kpi_values_entity_period", "kpi_values", ["entity_id", "period_id"])


def downgrade() -> None:
    op.drop_table("kpi_values")
    op.drop_table("kpi_definitions")
    op.drop_table("segment_data")
    op.drop_table("cash_flow_statements")
    op.drop_table("balance_sheets")
    op.drop_table("income_statements")
    op.drop_table("financial_periods")
    op.drop_table("filings")
