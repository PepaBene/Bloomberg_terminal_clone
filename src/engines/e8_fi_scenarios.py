"""E8 Extension: Fixed Income Scenario & Sensitivity Analysis.

Provides 1D/2D sensitivity tables and multi-variable scenario shifts
for bond portfolios using the duration-convexity approximation.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Rating migration spread impact (notch → spread change in bps)
# Positive notches = upgrade (spread tightens), negative = downgrade (widens)
# ---------------------------------------------------------------------------

_MIGRATION_SPREAD_PER_NOTCH_BPS: float = 25.0  # ~25bps per notch


# ---------------------------------------------------------------------------
# Sensitivity table
# ---------------------------------------------------------------------------

def fi_sensitivity_table(
    base_price: float,
    modified_duration: float,
    convexity: float,
    var1_name: str,
    var1_range: list[float],
    var2_name: str | None = None,
    var2_range: list[float] | None = None,
) -> dict:
    """Generate a 1D or 2D sensitivity table for a bond.

    Supported variables: ``yield_shift_bps``, ``spread_shift_bps``.

    For a given shift in basis points the price change is computed via the
    duration-convexity approximation:

        ΔP/P = -D * Δy + 0.5 * C * Δy²

    where Δy is the *total* shift from yield and/or spread combined (since
    spread shifts affect yield one-for-one in this model).

    Parameters
    ----------
    base_price : float
        Starting clean price of the bond.
    modified_duration : float
        Bond's modified duration.
    convexity : float
        Bond's convexity.
    var1_name : str
        First variable name (``yield_shift_bps`` or ``spread_shift_bps``).
    var1_range : list[float]
        Values to sweep for var1 (in bps).
    var2_name : str | None
        Optional second variable for 2D table.
    var2_range : list[float] | None
        Values to sweep for var2 (in bps).

    Returns
    -------
    dict
        For 1D: ``{var1_name, results: [{var1_value, price, price_change_pct}]}``
        For 2D: ``{var1_name, var2_name, results: [{var1_value, var2_value, price, price_change_pct}]}``
    """

    def _price_for_shift(total_shift_bps: float) -> tuple[float, float]:
        """Return (price, price_change_pct) for a given total shift in bps."""
        dy = total_shift_bps / 10_000  # decimal
        pct_change = -modified_duration * dy + 0.5 * convexity * dy ** 2
        new_price = base_price * (1 + pct_change)
        return round(new_price, 4), round(pct_change * 100, 4)

    results: list[dict] = []

    if var2_name is not None and var2_range is not None:
        # 2D sensitivity
        for v1 in var1_range:
            for v2 in var2_range:
                total_bps = v1 + v2
                price, pct = _price_for_shift(total_bps)
                results.append({
                    "var1_value": v1,
                    "var2_value": v2,
                    "price": price,
                    "price_change_pct": pct,
                })
        return {
            "var1_name": var1_name,
            "var2_name": var2_name,
            "results": results,
        }
    else:
        # 1D sensitivity
        for v1 in var1_range:
            price, pct = _price_for_shift(v1)
            results.append({
                "var1_value": v1,
                "price": price,
                "price_change_pct": pct,
            })
        return {
            "var1_name": var1_name,
            "var2_name": None,
            "results": results,
        }


# ---------------------------------------------------------------------------
# Multi-variable scenario shift
# ---------------------------------------------------------------------------

def fi_scenario_shift(
    positions: list[dict],
    yield_shift_bps: float = 0.0,
    spread_shift_bps: float = 0.0,
    rating_migration_notches: int = 0,
) -> dict:
    """Apply a multi-variable scenario shift to a bond portfolio.

    Parameters
    ----------
    positions : list[dict]
        Each dict: ``{market_value, modified_duration, convexity, spread_duration, rating_numeric, cusip}``
    yield_shift_bps : float
        Parallel yield shift in basis points (positive = rates up).
    spread_shift_bps : float
        Credit spread shift in basis points (positive = widening).
    rating_migration_notches : int
        Rating migration: positive = downgrade (wider spreads), negative = upgrade.

    Returns
    -------
    dict with total_pnl, components, and per-position detail.

    Notes
    -----
    - Yield impact: MV * (-mod_dur * Δy + 0.5 * cvx * Δy²)
    - Spread impact: MV * (-spread_dur * Δspread)
    - Migration impact: MV * (-spread_dur * notches * 25bps)
    """
    dy = yield_shift_bps / 10_000
    ds = spread_shift_bps / 10_000
    migration_spread = rating_migration_notches * _MIGRATION_SPREAD_PER_NOTCH_BPS / 10_000

    total_yield_impact = 0.0
    total_spread_impact = 0.0
    total_migration_impact = 0.0
    total_mv = 0.0
    by_position: list[dict] = []

    for pos in positions:
        mv = float(pos.get("market_value", 0.0))
        mod_dur = float(pos.get("modified_duration", 0.0))
        cvx = float(pos.get("convexity", 0.0) or 0.0)
        spread_dur = pos.get("spread_duration")
        if spread_dur is None:
            spread_dur = mod_dur
        else:
            spread_dur = float(spread_dur)
        cusip = pos.get("cusip")

        # Yield component
        yield_pnl = mv * (-mod_dur * dy + 0.5 * cvx * dy ** 2)

        # Spread component
        spread_pnl = mv * (-spread_dur * ds)

        # Migration component
        migration_pnl = mv * (-spread_dur * migration_spread)

        pos_total = yield_pnl + spread_pnl + migration_pnl

        total_yield_impact += yield_pnl
        total_spread_impact += spread_pnl
        total_migration_impact += migration_pnl
        total_mv += mv

        by_position.append({
            "cusip": cusip,
            "total_pnl": round(pos_total, 2),
            "components": {
                "yield_impact": round(yield_pnl, 2),
                "spread_impact": round(spread_pnl, 2),
                "migration_impact": round(migration_pnl, 2),
            },
        })

    total_pnl = total_yield_impact + total_spread_impact + total_migration_impact
    total_pnl_pct = (total_pnl / total_mv * 100) if total_mv else 0.0

    return {
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 4),
        "yield_impact": round(total_yield_impact, 2),
        "spread_impact": round(total_spread_impact, 2),
        "migration_impact": round(total_migration_impact, 2),
        "position_count": len(positions),
        "by_position": by_position,
    }
