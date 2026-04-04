"""E2 WACC Engine — Weighted Average Cost of Capital.

Computes WACC using CAPM for the cost of equity and an implied cost of
debt from financial statements.  Every sub-component is returned as a
separate EngineOutput with full lineage, and the complete result is stored
in the WACCResult table.

Formula
-------
WACC = E/(E+D) * Ke  +  D/(E+D) * Kd * (1 - t)

Cost of Equity (Ke) via CAPM:
    Ke = Rf + beta * ERP + size_premium + country_premium

Beta:
    Raw beta from OLS regression of security daily returns against a
    market benchmark (SPY).  Blume-adjusted:
        adjusted_beta = w * raw_beta + (1 - w) * 1.0

Cost of Debt (Kd):
    Kd_pretax = interest_expense_ttm / avg_total_debt
    Kd_aftertax = Kd_pretax * (1 - effective_tax_rate)
"""

from __future__ import annotations

import logging
import math
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.engines.base import BaseEngine, EngineOutput, safe_divide, make_input
from src.models.analytics import AnalyticsResult, WACCResult
from src.models.macro import MacroIndicator, MacroValue
from src.models.security import EODPrice, Security, SecurityIdentifier

logger = logging.getLogger(__name__)

# Try numpy for fast OLS; fall back to pure-Python implementation
try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:  # pragma: no cover
    _HAS_NUMPY = False


# ---------------------------------------------------------------------------
# Pure-Python simple OLS (fallback when numpy is unavailable)
# ---------------------------------------------------------------------------

def _ols_pure_python(
    x: list[float],
    y: list[float],
) -> tuple[float, float, float]:
    """Ordinary least-squares: y = alpha + beta * x.

    Returns (alpha, beta, r_squared).
    """
    n = len(x)
    if n < 2:
        raise ValueError("Need at least 2 observations for OLS")

    sum_x = sum(x)
    sum_y = sum(y)
    sum_xy = sum(xi * yi for xi, yi in zip(x, y))
    sum_x2 = sum(xi * xi for xi in x)
    sum_y2 = sum(yi * yi for yi in y)

    mean_x = sum_x / n
    mean_y = sum_y / n

    denom = sum_x2 - n * mean_x * mean_x
    if denom == 0:
        raise ValueError("Zero variance in x — cannot compute beta")

    beta = (sum_xy - n * mean_x * mean_y) / denom
    alpha = mean_y - beta * mean_x

    # R-squared
    ss_res = sum((yi - (alpha + beta * xi)) ** 2 for xi, yi in zip(x, y))
    ss_tot = sum_y2 - n * mean_y * mean_y
    r_squared = 1.0 - (ss_res / ss_tot) if ss_tot != 0 else 0.0

    return alpha, beta, r_squared


def _ols_numpy(
    x: list[float],
    y: list[float],
) -> tuple[float, float, float]:
    """OLS using numpy for speed."""
    xa = np.array(x, dtype=np.float64)
    ya = np.array(y, dtype=np.float64)

    n = len(xa)
    if n < 2:
        raise ValueError("Need at least 2 observations for OLS")

    # Add constant column for intercept: X = [ones, x]
    X = np.column_stack([np.ones(n), xa])
    # Normal equation: coeffs = (X'X)^-1 X'y
    XtX = X.T @ X
    Xty = X.T @ ya
    coeffs = np.linalg.solve(XtX, Xty)
    alpha, beta = float(coeffs[0]), float(coeffs[1])

    # R-squared
    y_pred = X @ coeffs
    ss_res = float(np.sum((ya - y_pred) ** 2))
    ss_tot = float(np.sum((ya - np.mean(ya)) ** 2))
    r_squared = 1.0 - (ss_res / ss_tot) if ss_tot != 0 else 0.0

    return alpha, beta, r_squared


def run_ols(x: list[float], y: list[float]) -> tuple[float, float, float]:
    """Run OLS regression, preferring numpy when available."""
    if _HAS_NUMPY:
        return _ols_numpy(x, y)
    return _ols_pure_python(x, y)


# ---------------------------------------------------------------------------
# Market Cost of Debt helpers (FI Supplement)
# ---------------------------------------------------------------------------

def compute_market_cost_of_debt(
    risk_free_rate: float,
    credit_spread_bps: float,
) -> dict[str, float]:
    """Compute market-implied cost of debt from risk-free rate + credit spread.

    Parameters
    ----------
    risk_free_rate : float
        Risk-free rate as a decimal (e.g. 0.04 for 4%).
    credit_spread_bps : float
        Credit spread in basis points (e.g. 200.0 for 200 bps).

    Returns
    -------
    dict with keys: cost_of_debt_market, risk_free_rate, credit_spread_bps.
    """
    cost_of_debt_market = risk_free_rate + credit_spread_bps / 10_000.0
    return {
        "cost_of_debt_market": cost_of_debt_market,
        "risk_free_rate": risk_free_rate,
        "credit_spread_bps": credit_spread_bps,
    }


def compute_wacc_with_market_debt_cost(
    cost_of_equity: float,
    cost_of_debt_market: float,
    equity_weight: float,
    debt_weight: float,
    tax_rate: float = 0.21,
) -> dict[str, float]:
    """Compute WACC using a market-derived (pre-tax) cost of debt.

    Parameters
    ----------
    cost_of_equity : float
        Cost of equity (decimal).
    cost_of_debt_market : float
        Pre-tax market cost of debt (decimal).
    equity_weight : float
        Equity weight in capital structure (0-1).
    debt_weight : float
        Debt weight in capital structure (0-1).
    tax_rate : float
        Marginal tax rate for the tax shield (default 0.21 = US statutory).

    Returns
    -------
    dict with keys: wacc_market, cost_of_equity, cost_of_debt_market_pretax,
    cost_of_debt_market_aftertax, equity_weight, debt_weight, tax_rate.
    """
    cost_of_debt_market_aftertax = cost_of_debt_market * (1.0 - tax_rate)
    wacc_market = (
        equity_weight * cost_of_equity
        + debt_weight * cost_of_debt_market * (1.0 - tax_rate)
    )
    return {
        "wacc_market": wacc_market,
        "cost_of_equity": cost_of_equity,
        "cost_of_debt_market_pretax": cost_of_debt_market,
        "cost_of_debt_market_aftertax": cost_of_debt_market_aftertax,
        "equity_weight": equity_weight,
        "debt_weight": debt_weight,
        "tax_rate": tax_rate,
    }


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

async def _load_risk_free_rate(session: AsyncSession) -> float | None:
    """Fetch latest US 10-Year Treasury yield from MacroValue.

    The indicator_code is taken from settings.ANALYTICS_RISK_FREE_INDICATOR
    (default "DGS10").  The value stored in macro_values is already in
    percentage terms (e.g. 4.25 for 4.25%), so we divide by 100.
    """
    indicator_code = settings.ANALYTICS_RISK_FREE_INDICATOR

    stmt = (
        select(MacroValue.value)
        .join(MacroIndicator, MacroValue.indicator_id == MacroIndicator.indicator_id)
        .where(MacroIndicator.indicator_code == indicator_code)
        .order_by(MacroValue.observation_date.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return float(row) / 100.0  # convert percentage to decimal


async def _find_benchmark_security_id(
    session: AsyncSession,
) -> UUID | None:
    """Resolve the market benchmark ticker (SPY) to a security_id.

    Looks up SecurityIdentifier with type='TICKER' matching the configured
    benchmark ticker.
    """
    ticker = settings.ANALYTICS_MARKET_BENCHMARK_TICKER
    stmt = (
        select(SecurityIdentifier.security_id)
        .where(
            SecurityIdentifier.identifier_type == "TICKER",
            SecurityIdentifier.identifier_value == ticker,
        )
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _load_daily_prices(
    session: AsyncSession,
    security_id: UUID,
    lookback_days: int,
) -> list[tuple[date, float]]:
    """Load daily adjusted close prices for the lookback window.

    Returns list of (price_date, close_adjusted) ordered by date ascending.
    """
    cutoff = date.today() - timedelta(days=lookback_days)
    stmt = (
        select(EODPrice.price_date, EODPrice.close_adjusted)
        .where(
            EODPrice.security_id == security_id,
            EODPrice.price_date >= cutoff,
            EODPrice.close_adjusted.isnot(None),
        )
        .order_by(EODPrice.price_date.asc())
    )
    result = await session.execute(stmt)
    return [(row.price_date, float(row.close_adjusted)) for row in result.all()]


def _compute_daily_returns(
    prices: list[tuple[date, float]],
) -> dict[date, float]:
    """Compute simple daily returns: r_t = (P_t - P_{t-1}) / P_{t-1}.

    Returns dict mapping date -> return for each day with a prior day.
    """
    returns: dict[date, float] = {}
    for i in range(1, len(prices)):
        prev_price = prices[i - 1][1]
        curr_price = prices[i][1]
        if prev_price != 0:
            returns[prices[i][0]] = (curr_price - prev_price) / prev_price
    return returns


async def _compute_beta(
    session: AsyncSession,
    security_id: UUID,
) -> tuple[float | None, float | None, int]:
    """Compute Blume-adjusted beta for the security vs market benchmark.

    Returns (adjusted_beta, r_squared, num_observations).
    """
    lookback = settings.ANALYTICS_BETA_LOOKBACK_DAYS
    blume_w = settings.ANALYTICS_BETA_BLUME_WEIGHT

    # Load benchmark
    benchmark_id = await _find_benchmark_security_id(session)
    if benchmark_id is None:
        logger.warning("WACC: benchmark security '%s' not found", settings.ANALYTICS_MARKET_BENCHMARK_TICKER)
        return None, None, 0

    # Load prices for both
    sec_prices = await _load_daily_prices(session, security_id, lookback)
    bench_prices = await _load_daily_prices(session, benchmark_id, lookback)

    if len(sec_prices) < 30 or len(bench_prices) < 30:
        logger.info("WACC: insufficient price history for beta (sec=%d, bench=%d)", len(sec_prices), len(bench_prices))
        return None, None, 0

    # Compute returns
    sec_returns = _compute_daily_returns(sec_prices)
    bench_returns = _compute_daily_returns(bench_prices)

    # Align on common dates
    common_dates = sorted(set(sec_returns.keys()) & set(bench_returns.keys()))
    if len(common_dates) < 30:
        logger.info("WACC: only %d common return dates, need >= 30", len(common_dates))
        return None, None, len(common_dates)

    x_market = [bench_returns[d] for d in common_dates]
    y_security = [sec_returns[d] for d in common_dates]

    try:
        _alpha, raw_beta, r_squared = run_ols(x_market, y_security)
    except (ValueError, Exception) as exc:
        logger.warning("WACC: OLS regression failed: %s", exc)
        return None, None, len(common_dates)

    # Blume adjustment: adj_beta = w * raw + (1 - w) * 1.0
    adjusted_beta = blume_w * raw_beta + (1.0 - blume_w) * 1.0

    return adjusted_beta, r_squared, len(common_dates)


async def _load_ttm_value(
    session: AsyncSession,
    security_id: UUID,
    entity_id: UUID,
    metric_name: str,
) -> float | None:
    """Load a single latest TTM metric from AnalyticsResult."""
    stmt = (
        select(AnalyticsResult.value)
        .where(
            AnalyticsResult.security_id == security_id,
            AnalyticsResult.entity_id == entity_id,
            AnalyticsResult.engine_id == "E1",
            AnalyticsResult.metric_name == metric_name,
        )
        .order_by(AnalyticsResult.as_of_date.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    val = result.scalar_one_or_none()
    return float(val) if val is not None else None


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class WACCEngine(BaseEngine):
    """Weighted Average Cost of Capital engine (E2).

    Computes WACC using:
    - Risk-free rate from macro data (10Y Treasury)
    - Blume-adjusted beta from OLS regression vs market benchmark
    - Configurable equity risk premium, size premium, country premium
    - Implied cost of debt from interest expense / total debt
    - Capital structure weights from market cap and total debt

    All individual components are returned as EngineOutput and the
    aggregate is persisted to WACCResult.
    """

    engine_id = "E2"
    engine_name = "Valuation"
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
            logger.warning("WACC: security %s not found or no issuer", security_id)
            return []

        entity_id: UUID = security.issuer_entity_id
        today = date.today()

        # ------------------------------------------------------------------
        # 2. Risk-free rate
        # ------------------------------------------------------------------
        rf = await _load_risk_free_rate(session)
        if rf is None:
            logger.warning("WACC: risk-free rate not available")
            return []

        # ------------------------------------------------------------------
        # 3. Beta (CAPM)
        # ------------------------------------------------------------------
        beta, beta_r2, beta_obs = await _compute_beta(session, security_id)
        if beta is None:
            logger.warning("WACC: beta computation failed for %s", security_id)
            # Continue with beta = 1.0 as fallback
            beta = 1.0
            beta_r2 = 0.0
            beta_quality = "ESTIMATED"
        else:
            beta_quality = "COMPLETE"

        # ------------------------------------------------------------------
        # 4. CAPM parameters
        # ------------------------------------------------------------------
        erp = settings.ANALYTICS_DEFAULT_ERP
        size_premium = 0.0  # TODO: implement market cap decile lookup
        country_premium = 0.0  # TODO: implement country risk premium lookup

        cost_of_equity = rf + beta * erp + size_premium + country_premium

        # ------------------------------------------------------------------
        # 5. Cost of debt
        # ------------------------------------------------------------------
        interest_expense = await _load_ttm_value(session, security_id, entity_id, "ttm_interest_expense")
        total_debt = await _load_ttm_value(session, security_id, entity_id, "ttm_total_debt")
        pretax_income = await _load_ttm_value(session, security_id, entity_id, "ttm_pretax_income")
        income_tax = await _load_ttm_value(session, security_id, entity_id, "ttm_income_tax_expense")

        # Implied cost of debt (pre-tax)
        cost_of_debt_pretax = safe_divide(interest_expense, total_debt)

        # Effective tax rate
        effective_tax_rate: float | None = None
        if pretax_income is not None and pretax_income > 0 and income_tax is not None:
            effective_tax_rate = income_tax / pretax_income
            # Clamp to reasonable range [0, 0.50]
            effective_tax_rate = max(0.0, min(effective_tax_rate, 0.50))

        # After-tax cost of debt
        cost_of_debt_aftertax: float | None = None
        if cost_of_debt_pretax is not None:
            # [Bug 24 fix] Use 0% for companies with zero or negative pretax
            # income (pre-revenue, loss-carry-forward, tax-exempt).  Only
            # apply 21% statutory when pretax income is positive but no tax
            # data is available.
            if effective_tax_rate is not None:
                tax_mult = 1.0 - effective_tax_rate
            elif pretax_income is not None and pretax_income > 0:
                tax_mult = 1.0 - 0.21  # positive pretax, missing tax detail
            else:
                tax_mult = 1.0  # zero/negative pretax → no tax shield
            cost_of_debt_aftertax = cost_of_debt_pretax * tax_mult

        # ------------------------------------------------------------------
        # 6. Capital structure weights
        # ------------------------------------------------------------------
        # Market cap from latest price * diluted shares
        latest_price_stmt = (
            select(EODPrice.close_adjusted)
            .where(EODPrice.security_id == security_id)
            .order_by(EODPrice.price_date.desc())
            .limit(1)
        )
        price_result = await session.execute(latest_price_stmt)
        price_val = price_result.scalar_one_or_none()
        price = float(price_val) if price_val is not None else None

        shares = await _load_ttm_value(session, security_id, entity_id, "ttm_diluted_shares_outstanding")

        market_cap: float | None = None
        if price is not None and shares is not None and price > 0 and shares > 0:
            market_cap = price * shares

        # Weights
        equity_weight: float | None = None
        debt_weight: float | None = None
        if market_cap is not None and total_debt is not None:
            total_capital = market_cap + total_debt
            if total_capital > 0:
                equity_weight = market_cap / total_capital
                debt_weight = total_debt / total_capital
        elif market_cap is not None:
            # No debt — 100% equity
            equity_weight = 1.0
            debt_weight = 0.0

        # ------------------------------------------------------------------
        # 7. WACC calculation
        # ------------------------------------------------------------------
        wacc: float | None = None
        if equity_weight is not None and debt_weight is not None and cost_of_equity is not None:
            equity_component = equity_weight * cost_of_equity
            debt_component = 0.0
            if cost_of_debt_aftertax is not None:
                debt_component = debt_weight * cost_of_debt_aftertax
            wacc = equity_component + debt_component

        # Determine overall data quality
        data_quality = "COMPLETE"
        if beta_quality == "ESTIMATED":
            data_quality = "ESTIMATED"
        if equity_weight is None or wacc is None:
            data_quality = "INSUFFICIENT_DATA"

        # ------------------------------------------------------------------
        # 8. Persist WACCResult
        # ------------------------------------------------------------------
        wacc_row = WACCResult(
            entity_id=entity_id,
            security_id=security_id,
            calculation_date=today,
            risk_free_rate=rf,
            equity_risk_premium=erp,
            beta=beta,
            size_premium=size_premium,
            country_premium=country_premium,
            cost_of_equity=cost_of_equity,
            cost_of_debt_pretax=cost_of_debt_pretax,
            effective_tax_rate=effective_tax_rate,
            cost_of_debt_aftertax=cost_of_debt_aftertax,
            debt_weight=debt_weight,
            equity_weight=equity_weight,
            wacc=wacc,
            market_cap=market_cap,
            total_debt=total_debt,
            assumptions={
                "erp": erp,
                "beta_blume_weight": settings.ANALYTICS_BETA_BLUME_WEIGHT,
                "beta_lookback_days": settings.ANALYTICS_BETA_LOOKBACK_DAYS,
                "beta_observations": beta_obs,
                "beta_r_squared": beta_r2,
                "beta_quality": beta_quality,
                "benchmark": settings.ANALYTICS_MARKET_BENCHMARK_TICKER,
                "risk_free_indicator": settings.ANALYTICS_RISK_FREE_INDICATOR,
                "size_premium": size_premium,
                "country_premium": country_premium,
                "statutory_tax_rate_fallback": 0.21,
            },
            data_quality=data_quality,
        )
        session.add(wacc_row)

        # ------------------------------------------------------------------
        # 9. Build EngineOutput list
        # ------------------------------------------------------------------
        outputs: list[EngineOutput] = []

        def _out(
            metric_name: str,
            value: float | None,
            unit: str = "PERCENT",
            inputs: list[dict] | None = None,
        ) -> EngineOutput:
            return EngineOutput(
                security_id=security_id,
                entity_id=entity_id,
                engine_id=self.engine_id,
                metric_name=metric_name,
                metric_category="VALUATION",
                value=value,
                unit=unit,
                period="LATEST",
                period_end_date=today,
                as_of_date=today,
                data_quality=data_quality,
                inputs=inputs or [],
            )

        outputs.append(
            _out(
                "risk_free_rate", rf,
                inputs=[make_input("rf", "macro_values", rf, period=settings.ANALYTICS_RISK_FREE_INDICATOR)],
            )
        )
        outputs.append(
            _out(
                "beta", beta, unit="RATIO",
                inputs=[
                    make_input("raw_beta", "ols_regression", beta),
                    make_input("observations", "eod_prices", float(beta_obs)),
                    make_input("r_squared", "ols_regression", beta_r2),
                ],
            )
        )
        outputs.append(
            _out(
                "equity_risk_premium", erp,
                inputs=[make_input("erp", "config", erp)],
            )
        )
        outputs.append(
            _out(
                "size_premium", size_premium,
                inputs=[make_input("size_premium", "config", size_premium)],
            )
        )
        outputs.append(
            _out(
                "country_premium", country_premium,
                inputs=[make_input("country_premium", "config", country_premium)],
            )
        )
        outputs.append(
            _out(
                "cost_of_equity", cost_of_equity,
                inputs=[
                    make_input("rf", "macro_values", rf),
                    make_input("beta", "computed", beta),
                    make_input("erp", "config", erp),
                ],
            )
        )
        outputs.append(
            _out(
                "cost_of_debt_pretax", cost_of_debt_pretax,
                inputs=[
                    make_input("interest_expense", "analytics_results", interest_expense),
                    make_input("total_debt", "analytics_results", total_debt),
                ],
            )
        )
        outputs.append(
            _out(
                "effective_tax_rate", effective_tax_rate,
                inputs=[
                    make_input("pretax_income", "analytics_results", pretax_income),
                    make_input("income_tax_expense", "analytics_results", income_tax),
                ],
            )
        )
        outputs.append(
            _out(
                "cost_of_debt_aftertax", cost_of_debt_aftertax,
                inputs=[
                    make_input("cost_of_debt_pretax", "computed", cost_of_debt_pretax),
                    make_input("effective_tax_rate", "computed", effective_tax_rate),
                ],
            )
        )
        outputs.append(
            _out(
                "equity_weight", equity_weight, unit="RATIO",
                inputs=[
                    make_input("market_cap", "computed", market_cap),
                    make_input("total_debt", "analytics_results", total_debt),
                ],
            )
        )
        outputs.append(
            _out(
                "debt_weight", debt_weight, unit="RATIO",
                inputs=[
                    make_input("market_cap", "computed", market_cap),
                    make_input("total_debt", "analytics_results", total_debt),
                ],
            )
        )
        outputs.append(
            _out(
                "wacc", wacc,
                inputs=[
                    make_input("cost_of_equity", "computed", cost_of_equity),
                    make_input("cost_of_debt_aftertax", "computed", cost_of_debt_aftertax),
                    make_input("equity_weight", "computed", equity_weight),
                    make_input("debt_weight", "computed", debt_weight),
                ],
            )
        )

        logger.info(
            "WACC: computed for security %s — WACC=%.4f, Ke=%.4f, beta=%.3f, Rf=%.4f (quality=%s)",
            security_id,
            wacc if wacc is not None else 0.0,
            cost_of_equity if cost_of_equity is not None else 0.0,
            beta if beta is not None else 0.0,
            rf,
            data_quality,
        )
        return outputs
