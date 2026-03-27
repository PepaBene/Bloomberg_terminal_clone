"""Pillar 4 Phase 1 — Daily NAV Calculation Engine.

Pure computation engine for Net Asset Value calculations, position
valuations, daily/cumulative returns, and portfolio snapshots.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import reduce


# ── Dataclasses ─────────────────────────────────────────────────────────


@dataclass
class PositionValuation:
    """Valuation result for a single position."""
    ticker: str
    shares: float
    cost_basis_total: float
    cost_basis_per_share: float
    closing_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    weight: float
    day_change_pct: float | None
    price_status: str  # CURRENT / STALE / DELISTED / IPO


@dataclass
class PortfolioNAV:
    """Aggregated NAV for a portfolio."""
    nav: float
    market_value: float
    cash_balance: float
    unrealized_pnl: float
    cash_weight: float
    position_count: int
    positions: list[PositionValuation] = field(default_factory=list)


@dataclass
class MissingPriceFlag:
    """Flag raised when a price is missing or stale."""
    ticker: str
    reason: str  # STALE / DELISTED / IPO
    last_price: float | None
    last_price_date: str | None


# ── Position-Level Functions ────────────────────────────────────────────


def compute_position_market_value(shares: float, closing_price: float) -> float:
    """Compute market value: shares * closing price."""
    return shares * closing_price


def compute_position_valuation(
    ticker: str,
    shares: float,
    cost_basis_total: float,
    cost_basis_per_share: float,
    closing_price: float,
    prior_close: float | None = None,
) -> PositionValuation:
    """Compute full valuation for a single position."""
    market_value = compute_position_market_value(shares, closing_price)
    unrealized_pnl = market_value - cost_basis_total
    unrealized_pnl_pct = (
        (unrealized_pnl / cost_basis_total) * 100.0
        if cost_basis_total != 0.0
        else 0.0
    )

    day_change_pct: float | None = None
    if prior_close is not None and prior_close != 0.0:
        day_change_pct = ((closing_price - prior_close) / prior_close) * 100.0

    return PositionValuation(
        ticker=ticker,
        shares=shares,
        cost_basis_total=cost_basis_total,
        cost_basis_per_share=cost_basis_per_share,
        closing_price=closing_price,
        market_value=market_value,
        unrealized_pnl=unrealized_pnl,
        unrealized_pnl_pct=round(unrealized_pnl_pct, 4),
        weight=0.0,  # set at portfolio level
        day_change_pct=(
            round(day_change_pct, 4) if day_change_pct is not None else None
        ),
        price_status="CURRENT",
    )


# ── Portfolio-Level Functions ───────────────────────────────────────────


def compute_portfolio_nav(
    positions: list[dict],
    cash_balance: float,
) -> PortfolioNAV:
    """Aggregate all positions + cash into a portfolio NAV."""
    valuations: list[PositionValuation] = []
    total_market_value = 0.0
    total_cost = 0.0

    for pos in positions:
        val = compute_position_valuation(
            ticker=pos["ticker"],
            shares=pos["shares"],
            cost_basis_total=pos["cost_basis_total"],
            cost_basis_per_share=pos["cost_basis_per_share"],
            closing_price=pos["closing_price"],
            prior_close=pos.get("prior_close"),
        )
        valuations.append(val)
        total_market_value += val.market_value
        total_cost += val.cost_basis_total

    nav = total_market_value + cash_balance
    unrealized_pnl = total_market_value - total_cost

    # Compute weights
    if nav > 0:
        for val in valuations:
            val.weight = round(val.market_value / nav, 6)

    cash_weight = compute_cash_weight(cash_balance, nav)

    return PortfolioNAV(
        nav=round(nav, 2),
        market_value=round(total_market_value, 2),
        cash_balance=round(cash_balance, 2),
        unrealized_pnl=round(unrealized_pnl, 2),
        cash_weight=cash_weight,
        position_count=len(valuations),
        positions=valuations,
    )


# ── Return Calculations ────────────────────────────────────────────────


def compute_daily_return(
    nav_today: float,
    nav_yesterday: float,
    cash_flows_today: float = 0.0,
) -> float:
    """Compute daily return using Modified Dietz method.

    Formula: (NAV_today - NAV_yesterday - cash_flows) /
             (NAV_yesterday + 0.5 * cash_flows)
    """
    denominator = nav_yesterday + 0.5 * cash_flows_today
    if denominator == 0.0:
        return 0.0
    return (nav_today - nav_yesterday - cash_flows_today) / denominator


def compute_cumulative_return(daily_returns: list[float]) -> float:
    """Compute cumulative return via geometric linking: prod(1 + r) - 1."""
    if not daily_returns:
        return 0.0
    return reduce(lambda acc, r: acc * (1.0 + r), daily_returns, 1.0) - 1.0


# ── Weight / Change Functions ───────────────────────────────────────────


def compute_position_weights(
    market_values: list[float],
    total_nav: float,
) -> list[float]:
    """Compute weight of each position as market_value / total_nav."""
    if total_nav == 0.0:
        return [0.0] * len(market_values)
    return [mv / total_nav for mv in market_values]


def compute_day_change(
    current_price: float,
    prior_price: float,
) -> dict:
    """Compute dollar and percentage day change."""
    dollar_change = current_price - prior_price
    pct_change = (
        (dollar_change / prior_price) * 100.0 if prior_price != 0.0 else 0.0
    )
    return {
        "dollar_change": round(dollar_change, 4),
        "pct_change": round(pct_change, 4),
    }


# ── Missing Price Handling ──────────────────────────────────────────────


def handle_missing_price(
    ticker: str,
    reason: str,
    last_known_price: float | None,
    last_date: str | None,
) -> MissingPriceFlag:
    """Create a missing-price flag for a security."""
    return MissingPriceFlag(
        ticker=ticker,
        reason=reason,
        last_price=last_known_price,
        last_price_date=last_date,
    )


# ── NAV Integrity ──────────────────────────────────────────────────────


def validate_nav_integrity(
    computed_nav: float,
    sum_positions: float,
    cash: float,
    tolerance: float = 0.01,
) -> list[str]:
    """Validate that computed NAV equals sum of positions + cash.

    Returns a list of discrepancy warnings (empty if valid).
    """
    warnings: list[str] = []
    expected = sum_positions + cash
    diff = abs(computed_nav - expected)
    if diff > tolerance:
        warnings.append(
            f"NAV mismatch: computed={computed_nav:.2f}, "
            f"expected (positions+cash)={expected:.2f}, "
            f"diff={diff:.2f}"
        )

    if computed_nav > 0 and sum_positions + cash > 0:
        weight_sum = sum_positions / computed_nav
        cash_w = cash / computed_nav
        total_w = weight_sum + cash_w
        if abs(total_w - 1.0) > tolerance:
            warnings.append(
                f"Weight sum mismatch: {total_w:.4f} (expected ~1.0)"
            )

    return warnings


def compute_cash_weight(cash_balance: float, nav: float) -> float:
    """Compute cash weight as cash / NAV. Returns 0.0 if NAV is zero."""
    if nav == 0.0:
        return 0.0
    return round(cash_balance / nav, 6)


# ── NAV Snapshot Builder ───────────────────────────────────────────────


def build_nav_snapshot(
    portfolio_id: str,
    snapshot_date: str,
    nav_data: PortfolioNAV,
    daily_return: float,
    cumulative_return: float,
    benchmark_daily: float | None,
    benchmark_cumulative: float | None,
) -> dict:
    """Build a full NAV snapshot dictionary."""
    return {
        "portfolio_id": portfolio_id,
        "snapshot_date": snapshot_date,
        "nav": nav_data.nav,
        "market_value": nav_data.market_value,
        "cash_balance": nav_data.cash_balance,
        "unrealized_pnl": nav_data.unrealized_pnl,
        "cash_weight": nav_data.cash_weight,
        "position_count": nav_data.position_count,
        "daily_return": round(daily_return, 6),
        "cumulative_return": round(cumulative_return, 6),
        "benchmark_daily_return": (
            round(benchmark_daily, 6) if benchmark_daily is not None else None
        ),
        "benchmark_cumulative_return": (
            round(benchmark_cumulative, 6)
            if benchmark_cumulative is not None
            else None
        ),
        "active_return_daily": (
            round(daily_return - benchmark_daily, 6)
            if benchmark_daily is not None
            else None
        ),
        "active_return_cumulative": (
            round(cumulative_return - benchmark_cumulative, 6)
            if benchmark_cumulative is not None
            else None
        ),
    }
