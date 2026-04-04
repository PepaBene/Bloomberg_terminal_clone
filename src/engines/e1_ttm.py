"""E1 TTM (Trailing Twelve Months) Engine.

Computes TTM values by summing the last 4 quarterly periods for flow
metrics (income statement, cash flow statement) and using the latest
quarter snapshot for stock metrics (balance sheet).

Part of Pillar 2 analytics — derives standardised TTM metrics from
Pillar 1 fundamental data so that downstream engines (valuation, ratios,
screening) always work with comparable annualised figures.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.engines.base import BaseEngine, EngineOutput, make_input
from src.models.fundamentals import (
    BalanceSheet,
    CashFlowStatement,
    FinancialPeriod,
    IncomeStatement,
)
from src.models.security import Security

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Field registries
# ---------------------------------------------------------------------------
# Each entry maps a canonical metric name to (model_class, attribute_name).
# Flow fields are summed across quarters; stock fields use latest quarter.

TTM_FLOW_FIELDS: dict[str, tuple[type, str]] = {
    # Income Statement — flow items
    "total_revenue":              (IncomeStatement, "total_revenue"),
    "cost_of_revenue":            (IncomeStatement, "cost_of_revenue"),
    "gross_profit":               (IncomeStatement, "gross_profit"),
    "operating_income":           (IncomeStatement, "operating_income"),
    "ebitda":                     (IncomeStatement, "ebitda"),
    "net_income":                 (IncomeStatement, "net_income"),
    "net_income_to_common":       (IncomeStatement, "net_income_to_common"),
    "interest_expense":           (IncomeStatement, "interest_expense"),
    "income_tax_expense":         (IncomeStatement, "income_tax_expense"),
    "pretax_income":              (IncomeStatement, "pretax_income"),
    "depreciation_amortization":  (IncomeStatement, "depreciation_amortization"),
    "research_development":       (IncomeStatement, "research_development"),
    "selling_general_admin":      (IncomeStatement, "selling_general_admin"),
    "stock_based_compensation":   (IncomeStatement, "stock_based_compensation"),
    "basic_eps":                  (IncomeStatement, "basic_eps"),
    "diluted_eps":                (IncomeStatement, "diluted_eps"),
    # Cash Flow Statement — flow items
    "cash_from_operations":       (CashFlowStatement, "cash_from_operations"),
    "capital_expenditures":       (CashFlowStatement, "capital_expenditures"),
    "free_cash_flow":             (CashFlowStatement, "free_cash_flow"),
    "dividends_paid":             (CashFlowStatement, "dividends_paid"),
    "stock_repurchased":          (CashFlowStatement, "stock_repurchased"),
    "cf_depreciation_amortization": (CashFlowStatement, "depreciation_amortization"),
    "net_change_in_cash":         (CashFlowStatement, "net_change_in_cash"),
}

TTM_STOCK_FIELDS: dict[str, tuple[type, str]] = {
    # Balance Sheet — point-in-time snapshot items
    "total_assets":               (BalanceSheet, "total_assets"),
    "total_current_assets":       (BalanceSheet, "total_current_assets"),
    "total_equity":               (BalanceSheet, "total_equity"),
    "total_common_equity":        (BalanceSheet, "total_common_equity"),
    "total_liabilities":          (BalanceSheet, "total_liabilities"),
    "total_current_liabilities":  (BalanceSheet, "total_current_liabilities"),
    "total_debt":                 (BalanceSheet, "total_debt"),
    "net_debt":                   (BalanceSheet, "net_debt"),
    "cash_and_equivalents":       (BalanceSheet, "cash_and_equivalents"),
    "cash_and_short_term":        (BalanceSheet, "cash_and_short_term"),
    "accounts_receivable":        (BalanceSheet, "accounts_receivable"),
    "inventory":                  (BalanceSheet, "inventory"),
    "accounts_payable":           (BalanceSheet, "accounts_payable"),
    "working_capital":            (BalanceSheet, "working_capital"),
    "tangible_book_value":        (BalanceSheet, "tangible_book_value"),
    "ppe_net":                    (BalanceSheet, "ppe_net"),
    "goodwill":                   (BalanceSheet, "goodwill"),
    "intangible_assets":          (BalanceSheet, "intangible_assets"),
    "long_term_debt":             (BalanceSheet, "long_term_debt"),
    "retained_earnings":          (BalanceSheet, "retained_earnings"),
    # Shares outstanding are point-in-time stock metrics
    "basic_shares_outstanding":   (IncomeStatement, "basic_shares_outstanding"),
    "diluted_shares_outstanding": (IncomeStatement, "diluted_shares_outstanding"),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_statement(period: FinancialPeriod, model_cls: type) -> Any | None:
    """Return the related statement object for a period, or None."""
    if model_cls is IncomeStatement:
        return period.income_statement
    if model_cls is BalanceSheet:
        return period.balance_sheet
    if model_cls is CashFlowStatement:
        return period.cash_flow
    return None


def _metric_category_for(model_cls: type) -> str:
    """Map a model class to the EngineOutput metric_category string."""
    if model_cls is IncomeStatement:
        return "INCOME_STATEMENT"
    if model_cls is BalanceSheet:
        return "BALANCE_SHEET"
    if model_cls is CashFlowStatement:
        return "CASH_FLOW"
    return "OTHER"


def _has_quarter_gap(periods: list[FinancialPeriod]) -> bool:
    """Detect if there is a gap between consecutive quarters.

    Quarters should be roughly 90 days apart.  If any adjacent pair is
    separated by more than 120 days the data has a gap.
    """
    if len(periods) < 2:
        return False
    for i in range(len(periods) - 1):
        newer = periods[i].period_end_date
        older = periods[i + 1].period_end_date
        delta = (newer - older).days
        if delta > 120:
            return True
    return False


def _months_covered(periods: list[FinancialPeriod]) -> int:
    """Estimate the number of months covered by the available quarters.

    [Bug 9 fix] Count actual quarters × 3 months instead of date arithmetic
    with an off-by-one constant.  This is correct for both Q1-only data
    (3 months, not the erroneous 6) and any partial-year coverage.
    """
    if not periods:
        return 0
    return len(periods) * 3


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class TTMEngine(BaseEngine):
    """Trailing Twelve Months computation engine (E1).

    Produces TTM values for all registered flow and stock metrics given a
    security.  Uses the security's issuer_entity_id to locate quarterly
    financial periods and then:

    * **Flow metrics** (IS/CF): sums the values from the last 4 quarters.
    * **Stock metrics** (BS): takes the value from the most recent quarter.

    When fewer than 4 quarters are available (but at least 1), flow metrics
    are annualised using ``sum * 12 / months_covered`` and the output is
    flagged with ``data_quality="ESTIMATED"``.

    If a gap is detected between quarters the engine sets
    ``data_quality="INSUFFICIENT_DATA"`` and returns ``value=None``.
    """

    engine_id = "E1"
    engine_name = "TTM Engine"
    engine_version = "1.0.0"

    async def compute(
        self,
        session: AsyncSession,
        security_id: UUID,
        **kwargs: Any,
    ) -> list[EngineOutput]:
        # ------------------------------------------------------------------
        # 1. Resolve the issuer entity behind this security
        # ------------------------------------------------------------------
        sec_result = await session.execute(
            select(Security).where(Security.security_id == security_id)
        )
        security = sec_result.scalar_one_or_none()
        if security is None or security.issuer_entity_id is None:
            logger.warning("TTM: security %s not found or has no issuer", security_id)
            return []

        entity_id: UUID = security.issuer_entity_id

        # ------------------------------------------------------------------
        # 2. Fetch up to 4 most recent quarterly periods (with statements)
        # ------------------------------------------------------------------
        stmt = (
            select(FinancialPeriod)
            .where(
                FinancialPeriod.entity_id == entity_id,
                FinancialPeriod.period_type == "QUARTERLY",
            )
            .order_by(FinancialPeriod.period_end_date.desc())
            .limit(4)
        )
        result = await session.execute(stmt)
        periods: list[FinancialPeriod] = list(result.scalars().all())

        if not periods:
            logger.info("TTM: no quarterly periods for entity %s", entity_id)
            return []

        # ------------------------------------------------------------------
        # 3. Determine data quality flags
        # ------------------------------------------------------------------
        quarter_count = len(periods)
        gap_detected = _has_quarter_gap(periods)
        months = _months_covered(periods)
        latest_period = periods[0]
        period_label = f"TTM_{latest_period.period_end_date.isoformat()}"

        outputs: list[EngineOutput] = []

        # ------------------------------------------------------------------
        # 4. Flow metrics — sum across quarters
        # ------------------------------------------------------------------
        for metric_name, (model_cls, field_name) in TTM_FLOW_FIELDS.items():
            if gap_detected:
                outputs.append(
                    EngineOutput(
                        security_id=security_id,
                        entity_id=entity_id,
                        engine_id=self.engine_id,
                        metric_name=f"ttm_{metric_name}",
                        metric_category=_metric_category_for(model_cls),
                        value=None,
                        unit="CURRENCY",
                        period=period_label,
                        period_end_date=latest_period.period_end_date,
                        data_quality="INSUFFICIENT_DATA",
                        inputs=[
                            make_input(
                                name=field_name,
                                source="financial_periods",
                                value=None,
                                period=period_label,
                            )
                        ],
                    )
                )
                continue

            # Accumulate values across available quarters
            total: float | None = None
            input_entries: list[dict] = []
            all_none = True

            for p in periods:
                stmt_obj = _get_statement(p, model_cls)
                if stmt_obj is None:
                    continue
                val = getattr(stmt_obj, field_name, None)
                if val is not None:
                    all_none = False
                    val_float = float(val)
                    total = (total or 0.0) + val_float
                    input_entries.append(
                        make_input(
                            name=field_name,
                            source="financial_periods",
                            value=val_float,
                            period=f"Q{p.fiscal_quarter}_{p.fiscal_year}" if p.fiscal_quarter else str(p.period_end_date),
                        )
                    )

            if all_none:
                # [Bug 11 fix] Still emit metric with None value so downstream
                # screener queries see a consistent schema across securities
                outputs.append(
                    EngineOutput(
                        security_id=security_id,
                        entity_id=entity_id,
                        engine_id=self.engine_id,
                        metric_name=f"ttm_{metric_name}",
                        metric_category=_metric_category_for(model_cls),
                        value=None,
                        unit="CURRENCY",
                        period=period_label,
                        period_end_date=latest_period.period_end_date,
                        data_quality="INSUFFICIENT_DATA",
                        inputs=[],
                    )
                )
                continue

            # Annualise if fewer than 4 quarters
            data_quality = "COMPLETE"
            if quarter_count < 4 and total is not None and months > 0:
                total = total * 12.0 / months
                data_quality = "ESTIMATED"

            outputs.append(
                EngineOutput(
                    security_id=security_id,
                    entity_id=entity_id,
                    engine_id=self.engine_id,
                    metric_name=f"ttm_{metric_name}",
                    metric_category=_metric_category_for(model_cls),
                    value=total,
                    unit="CURRENCY",
                    period=period_label,
                    period_end_date=latest_period.period_end_date,
                    data_quality=data_quality,
                    inputs=input_entries,
                )
            )

        # ------------------------------------------------------------------
        # 5. Stock metrics — latest quarter only
        # ------------------------------------------------------------------
        for metric_name, (model_cls, field_name) in TTM_STOCK_FIELDS.items():
            stmt_obj = _get_statement(latest_period, model_cls)
            if stmt_obj is None:
                # [Bug 11 fix] emit with None value for consistent schema
                outputs.append(
                    EngineOutput(
                        security_id=security_id,
                        entity_id=entity_id,
                        engine_id=self.engine_id,
                        metric_name=f"ttm_{metric_name}",
                        metric_category=_metric_category_for(model_cls),
                        value=None,
                        unit="CURRENCY",
                        period=period_label,
                        period_end_date=latest_period.period_end_date,
                        data_quality="INSUFFICIENT_DATA",
                        inputs=[],
                    )
                )
                continue
            val = getattr(stmt_obj, field_name, None)
            if val is None:
                # [Bug 11 fix] emit with None value for consistent schema
                outputs.append(
                    EngineOutput(
                        security_id=security_id,
                        entity_id=entity_id,
                        engine_id=self.engine_id,
                        metric_name=f"ttm_{metric_name}",
                        metric_category=_metric_category_for(model_cls),
                        value=None,
                        unit="CURRENCY",
                        period=period_label,
                        period_end_date=latest_period.period_end_date,
                        data_quality="INSUFFICIENT_DATA",
                        inputs=[],
                    )
                )
                continue

            val_float = float(val)
            outputs.append(
                EngineOutput(
                    security_id=security_id,
                    entity_id=entity_id,
                    engine_id=self.engine_id,
                    metric_name=f"ttm_{metric_name}",
                    metric_category=_metric_category_for(model_cls),
                    value=val_float,
                    unit="CURRENCY",
                    period=period_label,
                    period_end_date=latest_period.period_end_date,
                    data_quality="COMPLETE",
                    inputs=[
                        make_input(
                            name=field_name,
                            source="financial_periods",
                            value=val_float,
                            period=f"Q{latest_period.fiscal_quarter}_{latest_period.fiscal_year}"
                            if latest_period.fiscal_quarter
                            else str(latest_period.period_end_date),
                        )
                    ],
                )
            )

        logger.info(
            "TTM: computed %d metrics for security %s (%d quarters, quality=%s)",
            len(outputs),
            security_id,
            quarter_count,
            "GAP" if gap_detected else ("ESTIMATED" if quarter_count < 4 else "COMPLETE"),
        )
        return outputs
