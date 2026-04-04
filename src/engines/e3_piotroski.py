"""E3 Piotroski F-Score Engine.

Computes the Piotroski F-Score (0-9), a binary scoring system that
evaluates the financial strength of a company across three dimensions:

Profitability (4 points):
    F1: Net Income > 0
    F2: Operating Cash Flow > 0
    F3: ROA improving year-over-year
    F4: Cash Flow > Net Income (earnings quality)

Leverage & Liquidity (3 points):
    F5: Long-term Debt / Total Assets decreased YoY
    F6: Current Ratio increased YoY
    F7: No new equity issued (shares unchanged or decreased)

Operating Efficiency (2 points):
    F8: Gross Margin increased YoY
    F9: Asset Turnover increased YoY

Interpretation:
    8-9: Strong financial position
    5-7: Moderate financial position
    0-4: Weak financial position

Part of Pillar 2 analytics — consumes Pillar 1 fundamentals (income
statement + balance sheet + cash flow statement) and produces
composable EngineOutput metrics.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.engines.base import BaseEngine, EngineOutput, make_input, safe_divide
from src.models.fundamentals import (
    BalanceSheet,
    CashFlowStatement,
    FinancialPeriod,
    IncomeStatement,
)
from src.models.security import Security

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_output(
    security_id: UUID,
    entity_id: UUID,
    metric_name: str,
    value: float | None,
    period_label: str,
    period_end_date: Any,
    inputs: list[dict],
    *,
    data_quality: str = "COMPLETE",
    unit: str = "SCORE",
) -> EngineOutput:
    """Convenience factory for a Piotroski EngineOutput."""
    return EngineOutput(
        security_id=security_id,
        entity_id=entity_id,
        engine_id="E3",
        metric_name=metric_name,
        metric_category="QUALITY",
        value=value,
        unit=unit,
        period=period_label,
        period_end_date=period_end_date,
        data_quality=data_quality,
        inputs=inputs,
    )


def _f(val: Any) -> float | None:
    """Convert a Decimal/numeric value to float, or None."""
    return float(val) if val is not None else None


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class PiotroskiEngine(BaseEngine):
    """Piotroski F-Score engine (E3).

    Reads the two most recent annual financial periods that each have an
    income statement, balance sheet, and cash flow statement, then computes
    the nine binary signals and the aggregate F-Score.

    **Profitability (F1-F4)**
        - ``piotroski_f1_positive_income``  — net_income > 0
        - ``piotroski_f2_positive_ocf``     — cash_from_operations > 0
        - ``piotroski_f3_improving_roa``    — ROA(curr) > ROA(prior)
        - ``piotroski_f4_earnings_quality`` — cash_from_operations > net_income

    **Leverage & Liquidity (F5-F7)**
        - ``piotroski_f5_deleveraging``         — LTD/TA decreased YoY
        - ``piotroski_f6_improving_liquidity``   — current ratio increased YoY
        - ``piotroski_f7_no_dilution``           — shares not increased YoY

    **Operating Efficiency (F8-F9)**
        - ``piotroski_f8_improving_gross_margin``    — gross margin up YoY
        - ``piotroski_f9_improving_asset_turnover``  — asset turnover up YoY

    **Aggregates**
        - ``piotroski_profitability_subscore`` — sum of F1-F4 (0-4)
        - ``piotroski_f_score``                — total score (0-9)
        - ``piotroski_zone``                   — STRONG / MODERATE / WEAK

    Edge cases handled:
        - **Missing prior year**: all outputs have data_quality=INSUFFICIENT_DATA
        - **Missing fields**: that component conservatively scores 0
        - **Negative equity**: computed but flagged
        - **No statements**: returns empty list
    """

    engine_id = "E3"
    engine_name = "Piotroski F-Score"
    engine_version = "1.0.0"

    async def compute(
        self,
        session: AsyncSession,
        security_id: UUID,
        **kwargs: Any,
    ) -> list[EngineOutput]:
        # ------------------------------------------------------------------
        # 1. Resolve security -> entity
        # ------------------------------------------------------------------
        sec_result = await session.execute(
            select(Security).where(Security.security_id == security_id)
        )
        security = sec_result.scalar_one_or_none()
        if security is None or security.issuer_entity_id is None:
            logger.warning("Piotroski: security %s not found or has no issuer", security_id)
            return []

        entity_id: UUID = security.issuer_entity_id

        # ------------------------------------------------------------------
        # 2. Find the two most recent annual periods with IS, BS, and CF
        # ------------------------------------------------------------------
        stmt = (
            select(FinancialPeriod)
            .where(
                FinancialPeriod.entity_id == entity_id,
                FinancialPeriod.period_type == "ANNUAL",
            )
            .options(
                selectinload(FinancialPeriod.income_statement),
                selectinload(FinancialPeriod.balance_sheet),
                selectinload(FinancialPeriod.cash_flow),
            )
            .order_by(FinancialPeriod.period_end_date.desc())
            .limit(5)  # look back a bit in case recent ones lack data
        )
        result = await session.execute(stmt)
        periods: list[FinancialPeriod] = list(result.scalars().all())

        # Filter to periods that have at least IS and BS
        usable: list[FinancialPeriod] = [
            p for p in periods
            if p.income_statement is not None and p.balance_sheet is not None
        ]

        if len(usable) == 0:
            logger.info(
                "Piotroski: no annual period with IS+BS for entity %s", entity_id
            )
            return []

        curr_period = usable[0]
        prior_period = usable[1] if len(usable) >= 2 else None

        period_label = f"FY_{curr_period.fiscal_year}"

        # ------------------------------------------------------------------
        # 3. Extract raw values — current year
        # ------------------------------------------------------------------
        curr_is: IncomeStatement = curr_period.income_statement
        curr_bs: BalanceSheet = curr_period.balance_sheet
        curr_cf: CashFlowStatement | None = curr_period.cash_flow

        net_income_curr = _f(curr_is.net_income)
        total_revenue_curr = _f(curr_is.total_revenue)
        gross_profit_curr = _f(curr_is.gross_profit)
        total_assets_curr = _f(curr_bs.total_assets)
        total_equity_curr = _f(curr_bs.total_equity)
        long_term_debt_curr = _f(curr_bs.long_term_debt)
        total_current_assets_curr = _f(curr_bs.total_current_assets)
        total_current_liabilities_curr = _f(curr_bs.total_current_liabilities)
        shares_curr = _f(curr_is.diluted_shares_outstanding) or _f(curr_is.basic_shares_outstanding)
        ocf_curr = _f(curr_cf.cash_from_operations) if curr_cf is not None else None

        # ------------------------------------------------------------------
        # 4. Extract raw values — prior year
        # ------------------------------------------------------------------
        net_income_prior: float | None = None
        total_revenue_prior: float | None = None
        gross_profit_prior: float | None = None
        total_assets_prior: float | None = None
        long_term_debt_prior: float | None = None
        total_current_assets_prior: float | None = None
        total_current_liabilities_prior: float | None = None
        shares_prior: float | None = None

        prior_is: IncomeStatement | None = None
        prior_bs: BalanceSheet | None = None

        if prior_period is not None:
            prior_is = prior_period.income_statement
            prior_bs = prior_period.balance_sheet
            if prior_is is not None:
                net_income_prior = _f(prior_is.net_income)
                total_revenue_prior = _f(prior_is.total_revenue)
                gross_profit_prior = _f(prior_is.gross_profit)
                shares_prior = _f(prior_is.diluted_shares_outstanding) or _f(prior_is.basic_shares_outstanding)
            if prior_bs is not None:
                total_assets_prior = _f(prior_bs.total_assets)
                long_term_debt_prior = _f(prior_bs.long_term_debt)
                total_current_assets_prior = _f(prior_bs.total_current_assets)
                total_current_liabilities_prior = _f(prior_bs.total_current_liabilities)

        has_prior = prior_period is not None

        # ------------------------------------------------------------------
        # 5. Lineage helper
        # ------------------------------------------------------------------
        def _inp(name: str, value: float | None, period: str = period_label) -> dict:
            return make_input(
                name=name,
                source="financial_periods",
                value=value,
                period=period,
            )

        prior_label = f"FY_{prior_period.fiscal_year}" if prior_period else "N/A"

        # ------------------------------------------------------------------
        # 6. Data quality flags
        # ------------------------------------------------------------------
        quality_flags: list[str] = []
        if not has_prior:
            quality_flags.append("INSUFFICIENT_DATA")
        if total_equity_curr is not None and total_equity_curr < 0:
            quality_flags.append("NEGATIVE_EQUITY")

        base_quality = quality_flags[0] if quality_flags else "COMPLETE"

        # ------------------------------------------------------------------
        # 7. Profitability Signals (F1-F4)
        # ------------------------------------------------------------------
        negative_equity = (total_equity_curr is not None and total_equity_curr < 0)

        # F1: Net Income > 0
        if negative_equity:
            f1 = None
            f1_qual = "NEGATIVE_EQUITY"
        elif net_income_curr is not None:
            f1 = 1 if net_income_curr > 0 else 0
            f1_qual = base_quality
        else:
            f1 = None
            f1_qual = "INSUFFICIENT_DATA"

        # F2: Operating Cash Flow > 0
        if negative_equity:
            f2 = None
            f2_qual = "NEGATIVE_EQUITY"
        elif ocf_curr is not None:
            f2 = 1 if ocf_curr > 0 else 0
            f2_qual = base_quality
        else:
            f2 = None
            f2_qual = "INSUFFICIENT_DATA"

        # F3: ROA improving YoY
        roa_curr = safe_divide(net_income_curr, total_assets_curr)
        roa_prior = safe_divide(net_income_prior, total_assets_prior)
        if negative_equity:
            f3 = None
            f3_qual = "NEGATIVE_EQUITY"
        elif has_prior and roa_curr is not None and roa_prior is not None:
            f3 = 1 if roa_curr > roa_prior else 0
            f3_qual = score_quality
        else:
            f3 = None
            f3_qual = "INSUFFICIENT_DATA"

        # F4: Operating Cash Flow > Net Income (earnings quality)
        if negative_equity:
            f4 = None
            f4_qual = "NEGATIVE_EQUITY"
        elif ocf_curr is not None and net_income_curr is not None:
            f4 = 1 if ocf_curr > net_income_curr else 0
            f4_qual = base_quality
        else:
            f4 = None
            f4_qual = "INSUFFICIENT_DATA"

        # ------------------------------------------------------------------
        # 8. Leverage & Liquidity Signals (F5-F7)
        # ------------------------------------------------------------------

        # F5: Long-term Debt / Total Assets decreased YoY
        leverage_curr = safe_divide(long_term_debt_curr, total_assets_curr)
        leverage_prior = safe_divide(long_term_debt_prior, total_assets_prior)
        if has_prior and leverage_curr is not None and leverage_prior is not None:
            f5 = 1 if leverage_curr < leverage_prior else 0
        elif has_prior and long_term_debt_curr is not None and long_term_debt_curr == 0:
            # No debt at all is always good
            f5 = 1
        else:
            f5 = 0

        # F6: Current Ratio increased YoY
        current_ratio_curr = safe_divide(total_current_assets_curr, total_current_liabilities_curr)
        current_ratio_prior = safe_divide(total_current_assets_prior, total_current_liabilities_prior)
        if has_prior and current_ratio_curr is not None and current_ratio_prior is not None:
            f6 = 1 if current_ratio_curr > current_ratio_prior else 0
        else:
            f6 = 0

        # F7: No new equity issued (shares unchanged or decreased)
        if has_prior and shares_curr is not None and shares_prior is not None:
            f7 = 1 if shares_curr <= shares_prior else 0
            f7_qual = score_quality
        else:
            f7 = None
            f7_qual = "INSUFFICIENT_DATA"

        # ------------------------------------------------------------------
        # 9. Operating Efficiency Signals (F8-F9)
        # ------------------------------------------------------------------

        # F8: Gross Margin increased YoY
        gross_margin_curr = safe_divide(gross_profit_curr, total_revenue_curr)
        gross_margin_prior = safe_divide(gross_profit_prior, total_revenue_prior)
        if has_prior and gross_margin_curr is not None and gross_margin_prior is not None:
            f8 = 1 if gross_margin_curr > gross_margin_prior else 0
        else:
            f8 = 0

        # F9: Asset Turnover increased YoY
        asset_turnover_curr = safe_divide(total_revenue_curr, total_assets_curr)
        asset_turnover_prior = safe_divide(total_revenue_prior, total_assets_prior)
        if has_prior and asset_turnover_curr is not None and asset_turnover_prior is not None:
            f9 = 1 if asset_turnover_curr > asset_turnover_prior else 0
        else:
            f9 = 0

        # ------------------------------------------------------------------
        # 10. Aggregate score and zone
        # ------------------------------------------------------------------
        f_score_components = (f1, f2, f3, f4, f5, f6, f7, f8, f9)
        f_score = sum(x for x in f_score_components if x is not None)

        if f_score >= 8:
            zone = "STRONG"
        elif f_score >= 5:
            zone = "MODERATE"
        else:
            zone = "WEAK"

        # If no prior-year data, flag everything as insufficient
        score_quality = "INSUFFICIENT_DATA" if not has_prior else base_quality

        # ------------------------------------------------------------------
        # 11. Build outputs
        # ------------------------------------------------------------------
        outputs: list[EngineOutput] = []

        # F1: Positive Net Income
        outputs.append(
            _build_output(
                security_id, entity_id,
                "piotroski_f1_positive_income",
                float(f1) if f1 is not None else None,
                period_label, curr_period.period_end_date,
                [_inp("net_income", net_income_curr)],
                data_quality=f1_qual,
            )
        )

        # F2: Positive Operating Cash Flow
        outputs.append(
            _build_output(
                security_id, entity_id,
                "piotroski_f2_positive_ocf",
                float(f2) if f2 is not None else None,
                period_label, curr_period.period_end_date,
                [_inp("cash_from_operations", ocf_curr)],
                data_quality=f2_qual,
            )
        )

        # F3: Improving ROA
        outputs.append(
            _build_output(
                security_id, entity_id,
                "piotroski_f3_improving_roa",
                float(f3) if f3 is not None else None,
                period_label, curr_period.period_end_date,
                [
                    _inp("net_income_curr", net_income_curr),
                    _inp("total_assets_curr", total_assets_curr),
                    _inp("roa_curr", roa_curr),
                    _inp("net_income_prior", net_income_prior, prior_label),
                    _inp("total_assets_prior", total_assets_prior, prior_label),
                    _inp("roa_prior", roa_prior, prior_label),
                ],
                data_quality=f3_qual,
            )
        )

        # F4: Earnings Quality (OCF > NI)
        outputs.append(
            _build_output(
                security_id, entity_id,
                "piotroski_f4_earnings_quality",
                float(f4) if f4 is not None else None,
                period_label, curr_period.period_end_date,
                [
                    _inp("cash_from_operations", ocf_curr),
                    _inp("net_income", net_income_curr),
                ],
                data_quality=f4_qual,
            )
        )

        # F5: Deleveraging
        outputs.append(
            _build_output(
                security_id, entity_id,
                "piotroski_f5_deleveraging",
                float(f5),
                period_label, curr_period.period_end_date,
                [
                    _inp("long_term_debt_curr", long_term_debt_curr),
                    _inp("total_assets_curr", total_assets_curr),
                    _inp("leverage_ratio_curr", leverage_curr),
                    _inp("long_term_debt_prior", long_term_debt_prior, prior_label),
                    _inp("total_assets_prior", total_assets_prior, prior_label),
                    _inp("leverage_ratio_prior", leverage_prior, prior_label),
                ],
                data_quality=score_quality,
            )
        )

        # F6: Improving Liquidity
        outputs.append(
            _build_output(
                security_id, entity_id,
                "piotroski_f6_improving_liquidity",
                float(f6),
                period_label, curr_period.period_end_date,
                [
                    _inp("total_current_assets_curr", total_current_assets_curr),
                    _inp("total_current_liabilities_curr", total_current_liabilities_curr),
                    _inp("current_ratio_curr", current_ratio_curr),
                    _inp("total_current_assets_prior", total_current_assets_prior, prior_label),
                    _inp("total_current_liabilities_prior", total_current_liabilities_prior, prior_label),
                    _inp("current_ratio_prior", current_ratio_prior, prior_label),
                ],
                data_quality=score_quality,
            )
        )

        # F7: No Dilution
        outputs.append(
            _build_output(
                security_id, entity_id,
                "piotroski_f7_no_dilution",
                float(f7) if f7 is not None else None,
                period_label, curr_period.period_end_date,
                [
                    _inp("shares_outstanding_curr", shares_curr),
                    _inp("shares_outstanding_prior", shares_prior, prior_label),
                ],
                data_quality=f7_qual,
            )
        )

        # F8: Improving Gross Margin
        outputs.append(
            _build_output(
                security_id, entity_id,
                "piotroski_f8_improving_gross_margin",
                float(f8),
                period_label, curr_period.period_end_date,
                [
                    _inp("gross_profit_curr", gross_profit_curr),
                    _inp("total_revenue_curr", total_revenue_curr),
                    _inp("gross_margin_curr", gross_margin_curr),
                    _inp("gross_profit_prior", gross_profit_prior, prior_label),
                    _inp("total_revenue_prior", total_revenue_prior, prior_label),
                    _inp("gross_margin_prior", gross_margin_prior, prior_label),
                ],
                data_quality=score_quality,
            )
        )

        # F9: Improving Asset Turnover
        outputs.append(
            _build_output(
                security_id, entity_id,
                "piotroski_f9_improving_asset_turnover",
                float(f9),
                period_label, curr_period.period_end_date,
                [
                    _inp("total_revenue_curr", total_revenue_curr),
                    _inp("total_assets_curr", total_assets_curr),
                    _inp("asset_turnover_curr", asset_turnover_curr),
                    _inp("total_revenue_prior", total_revenue_prior, prior_label),
                    _inp("total_assets_prior", total_assets_prior, prior_label),
                    _inp("asset_turnover_prior", asset_turnover_prior, prior_label),
                ],
                data_quality=score_quality,
            )
        )

        # Profitability Subscore (F1+F2+F3+F4)
        outputs.append(
            _build_output(
                security_id, entity_id,
                "piotroski_profitability_subscore",
                float(profitability_subscore),
                period_label, curr_period.period_end_date,
                [
                    _inp("f1_positive_income", float(f1)),
                    _inp("f2_positive_ocf", float(f2)),
                    _inp("f3_improving_roa", float(f3)),
                    _inp("f4_earnings_quality", float(f4)),
                ],
                data_quality=score_quality,
            )
        )

        # Total F-Score
        outputs.append(
            _build_output(
                security_id, entity_id,
                "piotroski_f_score",
                float(f_score),
                period_label, curr_period.period_end_date,
                [
                    _inp("f1_positive_income", float(f1)),
                    _inp("f2_positive_ocf", float(f2)),
                    _inp("f3_improving_roa", float(f3)),
                    _inp("f4_earnings_quality", float(f4)),
                    _inp("f5_deleveraging", float(f5)),
                    _inp("f6_improving_liquidity", float(f6)),
                    _inp("f7_no_dilution", float(f7)),
                    _inp("f8_improving_gross_margin", float(f8)),
                    _inp("f9_improving_asset_turnover", float(f9)),
                ],
                data_quality=score_quality,
            )
        )

        # Zone Classification
        outputs.append(
            _build_output(
                security_id, entity_id,
                "piotroski_zone",
                None,  # classification, not a numeric value
                period_label, curr_period.period_end_date,
                [_inp("f_score", float(f_score))],
                data_quality=score_quality,
                unit="CLASSIFICATION",
            )
        )
        # Store the zone string in the value field as a convention:
        # downstream consumers read unit=CLASSIFICATION and interpret
        # the inputs to get the label.  We also stash it in inputs.
        outputs[-1].inputs.append(  # type: ignore[union-attr]
            make_input(name="zone", source="derived", value=None, period=zone)
        )

        logger.info(
            "Piotroski: F-Score=%d (%s) for security %s (period %s, %d metrics)",
            f_score, zone, security_id, period_label, len(outputs),
        )
        return outputs
