"""E2 Valuation Multiples Engine.

Computes 11 trading multiples (P/E, EV/EBITDA, P/B, etc.) by combining
Pillar 1 price data, E1 TTM fundamentals, and consensus forward estimates.

Every multiple is returned as an EngineOutput with full lineage and is
additionally stored in the MultipleTimeSeries table for historical tracking.

Multiples:
    1. pe_trailing       6. ev_fcf        11. dividend_yield
    2. pe_forward        7. pb
    3. ev_ebitda         8. p_tbv
    4. ev_ebit           9. peg
    5. ev_sales         10. ps
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.engines.base import BaseEngine, EngineOutput, safe_divide, make_input
from src.models.analytics import AnalyticsResult, MultipleTimeSeries
from src.models.estimates import ConsensusEstimate
from src.models.security import EODPrice, Security

logger = logging.getLogger(__name__)

# Metric names expected from the E1 TTM engine stored in AnalyticsResult
_TTM_METRICS = (
    "ttm_total_revenue",
    "ttm_ebitda",
    "ttm_operating_income",     # EBIT proxy
    "ttm_net_income",
    "ttm_free_cash_flow",
    "ttm_dividends_paid",
    "ttm_diluted_eps",
    "ttm_interest_expense",
    "ttm_diluted_shares_outstanding",
    "ttm_total_equity",
    "ttm_total_debt",
    "ttm_cash_and_equivalents",
    "ttm_tangible_book_value",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _load_ttm_metrics(
    session: AsyncSession,
    security_id: UUID,
    entity_id: UUID,
) -> dict[str, float | None]:
    """Load the latest TTM AnalyticsResult rows produced by E1.

    Returns a dict keyed by metric_name -> value (float or None).
    """
    stmt = (
        select(AnalyticsResult.metric_name, AnalyticsResult.value)
        .where(
            AnalyticsResult.security_id == security_id,
            AnalyticsResult.entity_id == entity_id,
            AnalyticsResult.engine_id == "E1",
            AnalyticsResult.metric_name.in_(_TTM_METRICS),
        )
        .order_by(AnalyticsResult.as_of_date.desc())
    )
    result = await session.execute(stmt)
    rows = result.all()

    # Keep only the most recent value per metric
    metrics: dict[str, float | None] = {}
    for name, value in rows:
        if name not in metrics:
            metrics[name] = float(value) if value is not None else None
    return metrics


async def _load_latest_price(
    session: AsyncSession,
    security_id: UUID,
) -> tuple[float | None, date | None]:
    """Return (close_adjusted, price_date) for the most recent EOD price."""
    stmt = (
        select(EODPrice.close_adjusted, EODPrice.price_date)
        .where(EODPrice.security_id == security_id)
        .order_by(EODPrice.price_date.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.first()
    if row is None:
        return None, None
    price = float(row.close_adjusted) if row.close_adjusted is not None else None
    return price, row.price_date


async def _load_forward_eps(
    session: AsyncSession,
    security_id: UUID,
) -> tuple[float | None, int | None]:
    """Return (forward_eps_mean, fiscal_year) for the nearest FY1 EPS estimate.

    Picks the consensus estimate for metric='EPS' whose period_end_date is
    in the future and closest to today.
    """
    today = date.today()
    stmt = (
        select(ConsensusEstimate.mean, ConsensusEstimate.fiscal_year)
        .where(
            ConsensusEstimate.security_id == security_id,
            ConsensusEstimate.metric == "EPS",
            ConsensusEstimate.period_end_date >= today,
        )
        .order_by(
            ConsensusEstimate.period_end_date.asc(),
            ConsensusEstimate.as_of_date.desc(),
        )
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.first()
    if row is None:
        return None, None
    fwd_eps = float(row.mean) if row.mean is not None else None
    return fwd_eps, row.fiscal_year


async def _load_prior_year_eps(
    session: AsyncSession,
    security_id: UUID,
    entity_id: UUID,
) -> float | None:
    """Fetch the prior-year diluted EPS from E1 analytics for growth calc.

    Looks for a TTM diluted EPS with as_of_date roughly one year ago.
    """
    one_year_ago = date.today() - timedelta(days=365)
    stmt = (
        select(AnalyticsResult.value)
        .where(
            AnalyticsResult.security_id == security_id,
            AnalyticsResult.entity_id == entity_id,
            AnalyticsResult.engine_id == "E1",
            AnalyticsResult.metric_name == "ttm_diluted_eps",
            AnalyticsResult.as_of_date <= one_year_ago,
        )
        .order_by(AnalyticsResult.as_of_date.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return float(row)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class MultiplesEngine(BaseEngine):
    """Valuation multiples engine (E2).

    Computes 11 trading multiples per security by combining:
    - Latest EOD price
    - E1 TTM fundamental metrics (revenue, EBITDA, net income, FCF, etc.)
    - Consensus forward EPS estimate
    - Balance-sheet items (equity, debt, cash, tangible book value)

    Each multiple is stored as both an EngineOutput and a row in the
    MultipleTimeSeries table.
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
            logger.warning("Multiples: security %s not found or no issuer", security_id)
            return []

        entity_id: UUID = security.issuer_entity_id

        # ------------------------------------------------------------------
        # 2. Load inputs
        # ------------------------------------------------------------------
        ttm = await _load_ttm_metrics(session, security_id, entity_id)
        price, price_date = await _load_latest_price(session, security_id)
        forward_eps, fwd_fy = await _load_forward_eps(session, security_id)
        prior_eps = await _load_prior_year_eps(session, security_id, entity_id)

        if price is None or price <= 0:
            logger.info("Multiples: no valid price for security %s", security_id)
            return []

        # ------------------------------------------------------------------
        # 3. Derived building blocks
        # ------------------------------------------------------------------
        shares = ttm.get("ttm_diluted_shares_outstanding")
        revenue = ttm.get("ttm_total_revenue")
        ebitda = ttm.get("ttm_ebitda")
        ebit = ttm.get("ttm_operating_income")  # operating_income = EBIT
        net_income = ttm.get("ttm_net_income")
        fcf = ttm.get("ttm_free_cash_flow")
        dividends_paid = ttm.get("ttm_dividends_paid")
        total_equity = ttm.get("ttm_total_equity")
        total_debt = ttm.get("ttm_total_debt")
        cash = ttm.get("ttm_cash_and_equivalents")
        tangible_bv = ttm.get("ttm_tangible_book_value")
        diluted_eps = ttm.get("ttm_diluted_eps")

        # Market cap and enterprise value
        market_cap: float | None = None
        if shares is not None and shares > 0:
            market_cap = price * shares

        enterprise_value: float | None = None
        if market_cap is not None:
            ev_debt = total_debt if total_debt is not None else 0.0
            ev_cash = cash if cash is not None else 0.0
            enterprise_value = market_cap + ev_debt - ev_cash

        # Per-share metrics
        bvps = safe_divide(total_equity, shares)
        tangible_bvps = safe_divide(tangible_bv, shares)
        revenue_per_share = safe_divide(revenue, shares)

        # Dividends per share (dividends_paid is usually negative in CF)
        dps: float | None = None
        if dividends_paid is not None and shares is not None and shares > 0:
            dps = abs(dividends_paid) / shares

        # EPS growth rate for PEG (trailing vs prior year)
        eps_growth: float | None = None
        if diluted_eps is not None and prior_eps is not None and prior_eps > 0:
            eps_growth = (diluted_eps - prior_eps) / abs(prior_eps)

        today = date.today()

        # ------------------------------------------------------------------
        # 4. Compute 11 multiples
        # ------------------------------------------------------------------
        multiples: list[tuple[str, float | None, float | None, float | None, bool, str | None]] = []
        # Each tuple: (name, value, numerator, denominator, is_forward, forward_period)

        # 1. P/E trailing — NULL if EPS <= 0
        pe_trailing = safe_divide(
            price, diluted_eps, allow_negative_denominator=False,
        )
        multiples.append(("pe_trailing", pe_trailing, price, diluted_eps, False, None))

        # 2. P/E forward — NULL if no estimate or EPS <= 0
        pe_forward = safe_divide(
            price, forward_eps, allow_negative_denominator=False,
        )
        fwd_period_str = f"FY{fwd_fy}" if fwd_fy is not None else None
        multiples.append(("pe_forward", pe_forward, price, forward_eps, True, fwd_period_str))

        # 3. EV/EBITDA — NULL if EBITDA <= 0
        ev_ebitda = safe_divide(
            enterprise_value, ebitda, allow_negative_denominator=False,
        )
        multiples.append(("ev_ebitda", ev_ebitda, enterprise_value, ebitda, False, None))

        # 4. EV/EBIT — NULL if EBIT <= 0
        ev_ebit = safe_divide(
            enterprise_value, ebit, allow_negative_denominator=False,
        )
        multiples.append(("ev_ebit", ev_ebit, enterprise_value, ebit, False, None))

        # 5. EV/Sales
        ev_sales = safe_divide(enterprise_value, revenue)
        multiples.append(("ev_sales", ev_sales, enterprise_value, revenue, False, None))

        # 6. EV/FCF — NULL if FCF <= 0
        ev_fcf = safe_divide(
            enterprise_value, fcf, allow_negative_denominator=False,
        )
        multiples.append(("ev_fcf", ev_fcf, enterprise_value, fcf, False, None))

        # 7. P/B — NULL if negative book value
        pb = safe_divide(price, bvps, allow_negative_denominator=False)
        multiples.append(("pb", pb, price, bvps, False, None))

        # 8. P/TBV — NULL if TBV <= 0
        p_tbv = safe_divide(price, tangible_bvps, allow_negative_denominator=False)
        multiples.append(("p_tbv", p_tbv, price, tangible_bvps, False, None))

        # 9. PEG — NULL if growth <= 0 or no forward P/E
        peg: float | None = None
        if pe_forward is not None and eps_growth is not None and eps_growth > 0:
            # PEG = P/E / (growth * 100)  — growth in percentage points
            peg = pe_forward / (eps_growth * 100.0) if eps_growth * 100.0 != 0 else None
        multiples.append(("peg", peg, pe_forward, eps_growth, True, fwd_period_str))

        # 10. P/S (price to sales per share)
        ps = safe_divide(price, revenue_per_share)
        multiples.append(("ps", ps, price, revenue_per_share, False, None))

        # 11. Dividend yield = DPS / price
        dividend_yield = safe_divide(dps, price)
        multiples.append(("dividend_yield", dividend_yield, dps, price, False, None))

        # ------------------------------------------------------------------
        # 5. Build outputs and persist to MultipleTimeSeries
        # ------------------------------------------------------------------
        outputs: list[EngineOutput] = []

        for name, value, numerator, denominator, is_fwd, fwd_period in multiples:
            # Determine unit: dividend_yield is a percentage, rest are multiples
            unit = "PERCENT" if name == "dividend_yield" else "MULTIPLE"

            inputs = [
                make_input("price", "eod_prices", price, str(price_date) if price_date else ""),
            ]
            if numerator is not None and name not in ("pe_trailing", "pe_forward", "pb", "p_tbv", "ps", "dividend_yield"):
                inputs.append(make_input("numerator", "computed", numerator))
            if denominator is not None:
                inputs.append(make_input("denominator", "analytics_results / estimates", denominator))
            if shares is not None:
                inputs.append(make_input("diluted_shares", "analytics_results", shares))

            data_quality = "COMPLETE" if value is not None else "INSUFFICIENT_DATA"

            outputs.append(
                EngineOutput(
                    security_id=security_id,
                    entity_id=entity_id,
                    engine_id=self.engine_id,
                    metric_name=name,
                    metric_category="VALUATION",
                    value=value,
                    unit=unit,
                    period="TTM" if not is_fwd else f"FWD_{fwd_period or 'FY1'}",
                    period_end_date=price_date,
                    as_of_date=today,
                    data_quality=data_quality,
                    inputs=inputs,
                )
            )

            # Persist to time-series table
            ts_row = MultipleTimeSeries(
                security_id=security_id,
                multiple_type=name,
                calculation_date=today,
                value=value,
                numerator_value=numerator,
                denominator_value=denominator,
                is_forward=is_fwd,
                forward_period=fwd_period,
            )
            await session.merge(ts_row)

        logger.info(
            "Multiples: computed %d multiples for security %s (price=%.2f, mkt_cap=%s)",
            len(outputs),
            security_id,
            price,
            f"{market_cap:,.0f}" if market_cap is not None else "N/A",
        )
        return outputs
