"""E1 DuPont Decomposition Engine.

Performs both 3-factor and 5-factor DuPont analysis to decompose Return
on Equity (ROE) into its underlying drivers.  This lets analysts pinpoint
whether ROE changes are driven by profitability, efficiency, or leverage.

3-factor:
    ROE = Net Profit Margin x Asset Turnover x Equity Multiplier

5-factor:
    ROE = Tax Burden x Interest Burden x Operating Margin
          x Asset Turnover x Equity Multiplier

Part of Pillar 2 analytics — consumes Pillar 1 fundamentals (income
statement + balance sheet) and produces composable EngineOutput metrics.
"""

from __future__ import annotations

import logging
import math
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.engines.base import BaseEngine, EngineOutput, make_input, safe_divide
from src.models.analytics import AnalyticsResult
from src.models.fundamentals import (
    BalanceSheet,
    FinancialPeriod,
    IncomeStatement,
)
from src.models.security import Security

logger = logging.getLogger(__name__)

# Tolerance for the cross-check: product of factors vs. direct ROE
_CROSS_CHECK_TOL = 0.001


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
    unit: str = "RATIO",
) -> EngineOutput:
    """Convenience factory for a DuPont EngineOutput."""
    return EngineOutput(
        security_id=security_id,
        entity_id=entity_id,
        engine_id="E1",
        metric_name=metric_name,
        metric_category="DUPONT",
        value=value,
        unit=unit,
        period=period_label,
        period_end_date=period_end_date,
        data_quality=data_quality,
        inputs=inputs,
    )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class DuPontEngine(BaseEngine):
    """DuPont decomposition engine (E1).

    Reads the most recent quarterly financial period that has both an
    income statement and a balance sheet, then computes:

    **3-factor decomposition**
        - ``dupont_net_profit_margin`` = net_income / total_revenue
        - ``dupont_asset_turnover``    = total_revenue / total_assets
        - ``dupont_equity_multiplier`` = total_assets / total_equity
        - ``dupont_roe_3f``            = product of the above three

    **5-factor decomposition**
        - ``dupont_tax_burden``        = net_income / pretax_income
        - ``dupont_interest_burden``   = pretax_income / operating_income
        - ``dupont_operating_margin``  = operating_income / total_revenue
        - ``dupont_asset_turnover``    (shared with 3-factor)
        - ``dupont_equity_multiplier`` (shared with 3-factor)
        - ``dupont_roe_5f``            = product of the above five

    Edge cases handled:
        - **Negative equity**: equity multiplier flagged ``NEGATIVE_EQUITY``
        - **Zero revenue**: margin metrics are None
        - **Zero operating / pretax income**: burden ratios are None
        - **Missing statements**: returns empty list
    """

    engine_id = "E1"
    engine_name = "DuPont Decomposition Engine"
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
            logger.warning("DuPont: security %s not found or has no issuer", security_id)
            return []

        entity_id: UUID = security.issuer_entity_id

        # ------------------------------------------------------------------
        # 2. Find the latest quarterly period with both IS and BS
        # ------------------------------------------------------------------
        stmt = (
            select(FinancialPeriod)
            .where(
                FinancialPeriod.entity_id == entity_id,
                FinancialPeriod.period_type == "QUARTERLY",
            )
            .order_by(FinancialPeriod.period_end_date.desc())
            .limit(8)  # look a bit further back in case recent ones lack data
        )
        result = await session.execute(stmt)
        periods: list[FinancialPeriod] = list(result.scalars().all())

        period: FinancialPeriod | None = None
        inc: IncomeStatement | None = None
        bs: BalanceSheet | None = None

        for p in periods:
            if p.income_statement is not None and p.balance_sheet is not None:
                period = p
                inc = p.income_statement
                bs = p.balance_sheet
                break

        if period is None or inc is None or bs is None:
            logger.info(
                "DuPont: no period with both IS and BS for entity %s — attempting TTM fallback",
                entity_id,
            )
            return await self._ttm_fallback(session, security_id, entity_id)

        period_label = (
            f"Q{period.fiscal_quarter}_{period.fiscal_year}"
            if period.fiscal_quarter
            else str(period.period_end_date)
        )

        # ------------------------------------------------------------------
        # 3. Extract raw values (convert Decimal -> float where not None)
        # ------------------------------------------------------------------
        net_income = float(inc.net_income) if inc.net_income is not None else None
        total_revenue = float(inc.total_revenue) if inc.total_revenue is not None else None
        operating_income = float(inc.operating_income) if inc.operating_income is not None else None
        pretax_income = float(inc.pretax_income) if inc.pretax_income is not None else None
        total_assets = float(bs.total_assets) if bs.total_assets is not None else None
        total_equity = float(bs.total_equity) if bs.total_equity is not None else None

        outputs: list[EngineOutput] = []

        # Common lineage inputs
        def _inp(name: str, value: float | None) -> dict:
            return make_input(
                name=name,
                source="financial_periods",
                value=value,
                period=period_label,
            )

        # ------------------------------------------------------------------
        # 4. 3-Factor DuPont
        # ------------------------------------------------------------------

        # Net Profit Margin = net_income / total_revenue
        net_profit_margin = safe_divide(net_income, total_revenue)
        npm_quality = "COMPLETE"
        if total_revenue is not None and total_revenue == 0:
            npm_quality = "ZERO_REVENUE"
        outputs.append(
            _build_output(
                security_id, entity_id,
                "dupont_net_profit_margin",
                net_profit_margin,
                period_label, period.period_end_date,
                [_inp("net_income", net_income), _inp("total_revenue", total_revenue)],
                data_quality=npm_quality,
            )
        )

        # Asset Turnover = total_revenue / total_assets
        asset_turnover = safe_divide(total_revenue, total_assets)
        outputs.append(
            _build_output(
                security_id, entity_id,
                "dupont_asset_turnover",
                asset_turnover,
                period_label, period.period_end_date,
                [_inp("total_revenue", total_revenue), _inp("total_assets", total_assets)],
            )
        )

        # Equity Multiplier = total_assets / total_equity
        eq_mult_quality = "COMPLETE"
        if total_equity is not None and total_equity < 0:
            eq_mult_quality = "NEGATIVE_EQUITY"
        equity_multiplier = safe_divide(total_assets, total_equity)
        outputs.append(
            _build_output(
                security_id, entity_id,
                "dupont_equity_multiplier",
                equity_multiplier,
                period_label, period.period_end_date,
                [_inp("total_assets", total_assets), _inp("total_equity", total_equity)],
                data_quality=eq_mult_quality,
            )
        )

        # ROE (3-factor) = product
        roe_3f: float | None = None
        if all(v is not None for v in (net_profit_margin, asset_turnover, equity_multiplier)):
            roe_3f = net_profit_margin * asset_turnover * equity_multiplier  # type: ignore[operator]

        # Direct ROE for cross-check
        direct_roe = safe_divide(net_income, total_equity)
        roe_3f_quality = "COMPLETE"
        # [Bug 6 fix] propagate NEGATIVE_EQUITY to composite 3F ROE
        if eq_mult_quality == "NEGATIVE_EQUITY":
            roe_3f_quality = "NEGATIVE_EQUITY"
        if roe_3f is not None and direct_roe is not None:
            # [Bug 7 fix] use both relative and absolute tolerance
            if not math.isclose(roe_3f, direct_roe, rel_tol=0.005, abs_tol=_CROSS_CHECK_TOL):
                roe_3f_quality = "CROSS_CHECK_MISMATCH"
                logger.warning(
                    "DuPont 3F cross-check: product=%.6f vs direct=%.6f for %s",
                    roe_3f, direct_roe, security_id,
                )

        outputs.append(
            _build_output(
                security_id, entity_id,
                "dupont_roe_3f",
                roe_3f,
                period_label, period.period_end_date,
                [
                    _inp("net_profit_margin", net_profit_margin),
                    _inp("asset_turnover", asset_turnover),
                    _inp("equity_multiplier", equity_multiplier),
                ],
                data_quality=roe_3f_quality,
            )
        )

        # Also store direct ROE for reference
        outputs.append(
            _build_output(
                security_id, entity_id,
                "dupont_roe_direct",
                direct_roe,
                period_label, period.period_end_date,
                [_inp("net_income", net_income), _inp("total_equity", total_equity)],
                data_quality="NEGATIVE_EQUITY" if (total_equity is not None and total_equity < 0) else "COMPLETE",
            )
        )

        # ------------------------------------------------------------------
        # 5. 5-Factor DuPont
        # ------------------------------------------------------------------

        # Tax Burden = net_income / pretax_income
        tax_burden = safe_divide(net_income, pretax_income)
        outputs.append(
            _build_output(
                security_id, entity_id,
                "dupont_tax_burden",
                tax_burden,
                period_label, period.period_end_date,
                [_inp("net_income", net_income), _inp("pretax_income", pretax_income)],
            )
        )

        # Interest Burden = pretax_income / operating_income
        interest_burden = safe_divide(pretax_income, operating_income)
        outputs.append(
            _build_output(
                security_id, entity_id,
                "dupont_interest_burden",
                interest_burden,
                period_label, period.period_end_date,
                [_inp("pretax_income", pretax_income), _inp("operating_income", operating_income)],
            )
        )

        # Operating Margin = operating_income / total_revenue
        operating_margin = safe_divide(operating_income, total_revenue)
        om_quality = "COMPLETE"
        if total_revenue is not None and total_revenue == 0:
            om_quality = "ZERO_REVENUE"
        outputs.append(
            _build_output(
                security_id, entity_id,
                "dupont_operating_margin",
                operating_margin,
                period_label, period.period_end_date,
                [_inp("operating_income", operating_income), _inp("total_revenue", total_revenue)],
                data_quality=om_quality,
            )
        )

        # Asset Turnover and Equity Multiplier are shared with 3-factor
        # (already emitted above — no duplicate).

        # ROE (5-factor) = product
        roe_5f: float | None = None
        factors_5 = [tax_burden, interest_burden, operating_margin, asset_turnover, equity_multiplier]
        if all(v is not None for v in factors_5):
            roe_5f = 1.0
            for f in factors_5:
                roe_5f *= f  # type: ignore[operator]

        roe_5f_quality = "COMPLETE"
        # [Bug 6 fix] propagate NEGATIVE_EQUITY to composite 5F ROE
        if eq_mult_quality == "NEGATIVE_EQUITY":
            roe_5f_quality = "NEGATIVE_EQUITY"
        if roe_5f is not None and direct_roe is not None:
            # [Bug 7 fix] use both relative and absolute tolerance
            if not math.isclose(roe_5f, direct_roe, rel_tol=0.005, abs_tol=_CROSS_CHECK_TOL):
                roe_5f_quality = "CROSS_CHECK_MISMATCH"
                logger.warning(
                    "DuPont 5F cross-check: product=%.6f vs direct=%.6f for %s",
                    roe_5f, direct_roe, security_id,
                )

        outputs.append(
            _build_output(
                security_id, entity_id,
                "dupont_roe_5f",
                roe_5f,
                period_label, period.period_end_date,
                [
                    _inp("tax_burden", tax_burden),
                    _inp("interest_burden", interest_burden),
                    _inp("operating_margin", operating_margin),
                    _inp("asset_turnover", asset_turnover),
                    _inp("equity_multiplier", equity_multiplier),
                ],
                data_quality=roe_5f_quality,
            )
        )

        logger.info(
            "DuPont: computed %d metrics for security %s (period %s)",
            len(outputs), security_id, period_label,
        )
        return outputs

    # ------------------------------------------------------------------
    # TTM fallback (Bug 8 fix)
    # ------------------------------------------------------------------

    async def _ttm_fallback(
        self,
        session: AsyncSession,
        security_id: UUID,
        entity_id: UUID,
    ) -> list[EngineOutput]:
        """Build approximate 3-factor DuPont from TTM analytics results.

        Called when no quarterly period has both an income statement and a
        balance sheet.  Queries previously computed TTM metrics from
        ``AnalyticsResult`` and derives profit margin, asset turnover, and
        equity multiplier.  All outputs are marked ``ESTIMATED``.
        """
        ttm_rows = await session.execute(
            select(AnalyticsResult).where(
                AnalyticsResult.security_id == security_id,
                AnalyticsResult.engine_id == "E1",
                AnalyticsResult.metric_name.in_([
                    "ttm_net_income",
                    "ttm_total_revenue",
                    "ttm_total_assets",
                    "ttm_total_equity",
                ]),
            )
        )
        ttm_map: dict[str, float] = {
            row.metric_name: float(row.value)
            for row in ttm_rows.scalars().all()
            if row.value is not None
        }

        needed = {"ttm_net_income", "ttm_total_revenue", "ttm_total_assets", "ttm_total_equity"}
        if not needed.issubset(ttm_map):
            logger.warning(
                "DuPont TTM fallback: insufficient TTM data for security %s (have %s)",
                security_id,
                sorted(ttm_map.keys()),
            )
            return []

        net_income = ttm_map["ttm_net_income"]
        total_revenue = ttm_map["ttm_total_revenue"]
        total_assets = ttm_map["ttm_total_assets"]
        total_equity = ttm_map["ttm_total_equity"]

        period_label = "TTM"
        quality = "ESTIMATED"

        def _inp(name: str, value: float) -> dict:
            return make_input(
                name=name,
                source="analytics_results_ttm",
                value=value,
                period=period_label,
            )

        outputs: list[EngineOutput] = []

        # Net Profit Margin
        net_profit_margin = safe_divide(net_income, total_revenue)
        outputs.append(
            _build_output(
                security_id, entity_id,
                "dupont_net_profit_margin",
                net_profit_margin,
                period_label, None,
                [_inp("ttm_net_income", net_income), _inp("ttm_total_revenue", total_revenue)],
                data_quality=quality,
            )
        )

        # Asset Turnover
        asset_turnover = safe_divide(total_revenue, total_assets)
        outputs.append(
            _build_output(
                security_id, entity_id,
                "dupont_asset_turnover",
                asset_turnover,
                period_label, None,
                [_inp("ttm_total_revenue", total_revenue), _inp("ttm_total_assets", total_assets)],
                data_quality=quality,
            )
        )

        # Equity Multiplier
        equity_multiplier = safe_divide(total_assets, total_equity)
        eq_quality = quality if total_equity >= 0 else "ESTIMATED_NEGATIVE_EQUITY"
        outputs.append(
            _build_output(
                security_id, entity_id,
                "dupont_equity_multiplier",
                equity_multiplier,
                period_label, None,
                [_inp("ttm_total_assets", total_assets), _inp("ttm_total_equity", total_equity)],
                data_quality=eq_quality,
            )
        )

        # ROE (3-factor)
        roe_3f: float | None = None
        if all(v is not None for v in (net_profit_margin, asset_turnover, equity_multiplier)):
            roe_3f = net_profit_margin * asset_turnover * equity_multiplier  # type: ignore[operator]
        outputs.append(
            _build_output(
                security_id, entity_id,
                "dupont_roe_3f",
                roe_3f,
                period_label, None,
                [
                    _inp("net_profit_margin", net_profit_margin or 0.0),
                    _inp("asset_turnover", asset_turnover or 0.0),
                    _inp("equity_multiplier", equity_multiplier or 0.0),
                ],
                data_quality=quality,
            )
        )

        # Direct ROE for reference
        direct_roe = safe_divide(net_income, total_equity)
        outputs.append(
            _build_output(
                security_id, entity_id,
                "dupont_roe_direct",
                direct_roe,
                period_label, None,
                [_inp("ttm_net_income", net_income), _inp("ttm_total_equity", total_equity)],
                data_quality=quality,
            )
        )

        logger.info(
            "DuPont TTM fallback: computed %d estimated metrics for security %s",
            len(outputs), security_id,
        )
        return outputs
