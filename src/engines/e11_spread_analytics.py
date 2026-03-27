"""E11 Spread Analytics Engine — G-spread, Z-spread, OAS, relative value, breakeven."""

from __future__ import annotations

import math
import statistics


def interpolate_treasury_yield(maturity_years: float, treasury_curve: list[dict]) -> float:
    """Interpolate treasury yield at exact maturity from curve points.

    Parameters
    ----------
    maturity_years : float
        Target maturity in years.
    treasury_curve : list[dict]
        Each dict has ``tenor_years`` (float) and ``yield_rate`` (float, decimal form).
        Must contain at least one point.

    Returns
    -------
    float
        Interpolated yield (decimal form, e.g. 0.045 for 4.5%).
        Extrapolates flat beyond endpoints.
    """
    if not treasury_curve:
        return 0.0

    # Sort by tenor
    sorted_curve = sorted(treasury_curve, key=lambda p: p["tenor_years"])

    # Flat extrapolation below first point
    if maturity_years <= sorted_curve[0]["tenor_years"]:
        return sorted_curve[0]["yield_rate"]

    # Flat extrapolation above last point
    if maturity_years >= sorted_curve[-1]["tenor_years"]:
        return sorted_curve[-1]["yield_rate"]

    # Find bracketing points and linearly interpolate
    for i in range(len(sorted_curve) - 1):
        t0 = sorted_curve[i]["tenor_years"]
        t1 = sorted_curve[i + 1]["tenor_years"]
        y0 = sorted_curve[i]["yield_rate"]
        y1 = sorted_curve[i + 1]["yield_rate"]

        if t0 <= maturity_years <= t1:
            if abs(t1 - t0) < 1e-12:
                return y0
            fraction = (maturity_years - t0) / (t1 - t0)
            return y0 + fraction * (y1 - y0)

    # Fallback (should not reach here)
    return sorted_curve[-1]["yield_rate"]


def compute_g_spread_interpolated(
    bond_ytm: float,
    maturity_years: float,
    treasury_curve: list[dict],
) -> int:
    """G-spread in bps using interpolated treasury yield at exact bond maturity.

    Parameters
    ----------
    bond_ytm : float
        Bond yield to maturity (decimal, e.g. 0.055).
    maturity_years : float
        Years to maturity.
    treasury_curve : list[dict]
        Treasury curve points with ``tenor_years`` and ``yield_rate``.

    Returns
    -------
    int
        G-spread = bond_ytm - interpolated_treasury_yield, in basis points.
    """
    benchmark_yield = interpolate_treasury_yield(maturity_years, treasury_curve)
    spread = bond_ytm - benchmark_yield
    return round(spread * 10_000)


def _interpolate_zero_rate(t: float, zero_curve: list[dict]) -> float:
    """Interpolate a zero rate from the zero curve at time *t* (years).

    Uses the same logic as ``interpolate_treasury_yield`` but with
    ``zero_rate`` key.
    """
    if not zero_curve:
        return 0.0

    sorted_curve = sorted(zero_curve, key=lambda p: p["tenor_years"])

    if t <= sorted_curve[0]["tenor_years"]:
        return sorted_curve[0]["zero_rate"]
    if t >= sorted_curve[-1]["tenor_years"]:
        return sorted_curve[-1]["zero_rate"]

    for i in range(len(sorted_curve) - 1):
        t0 = sorted_curve[i]["tenor_years"]
        t1 = sorted_curve[i + 1]["tenor_years"]
        z0 = sorted_curve[i]["zero_rate"]
        z1 = sorted_curve[i + 1]["zero_rate"]

        if t0 <= t <= t1:
            if abs(t1 - t0) < 1e-12:
                return z0
            frac = (t - t0) / (t1 - t0)
            return z0 + frac * (z1 - z0)

    return sorted_curve[-1]["zero_rate"]


def compute_z_spread(
    cash_flows: list[dict],
    price: float,
    zero_curve: list[dict],
    face_value: float = 100.0,
    max_iterations: int = 100,
    tolerance: float = 0.01,
) -> int:
    """Z-spread (Zero-Volatility Spread) via Newton-Raphson.

    Find constant spread *s* such that:
        Price = sum( CF_i / (1 + z_i + s)^t_i )
    where z_i is the interpolated zero rate for time t_i.

    Parameters
    ----------
    cash_flows : list[dict]
        Each dict has ``years`` (float) and ``amount`` (float).
    price : float
        Clean price as percentage of par (e.g. 98.5).
    zero_curve : list[dict]
        Each dict has ``tenor_years`` (float) and ``zero_rate`` (float, decimal).
    face_value : float
        Par value (default 100).
    max_iterations : int
        Newton-Raphson iteration cap.
    tolerance : float
        Convergence threshold for price difference.

    Returns
    -------
    int
        Z-spread in basis points.
    """
    if not cash_flows or not zero_curve:
        return 0

    # Scale price to dollar amount (price is % of par)
    target_price = price

    # Initial guess: 100 bps = 0.01
    s = 0.01

    for _ in range(max_iterations):
        pv = 0.0
        dpv_ds = 0.0  # derivative of PV w.r.t. s

        for cf in cash_flows:
            t = cf["years"]
            amount = cf["amount"]
            if t <= 0:
                pv += amount
                continue

            z = _interpolate_zero_rate(t, zero_curve)
            discount_rate = 1 + z + s

            if discount_rate <= 0:
                discount_rate = 0.0001

            df = discount_rate ** (-t)
            pv += amount * df
            # d/ds [ amount * (1+z+s)^(-t) ] = amount * (-t) * (1+z+s)^(-t-1)
            dpv_ds += amount * (-t) * (discount_rate ** (-t - 1))

        diff = pv - target_price
        if abs(diff) < tolerance:
            return round(s * 10_000)

        if abs(dpv_ds) < 1e-15:
            break

        s -= diff / dpv_ds

    return round(s * 10_000)


def compute_oas_simplified(z_spread_bps: int, option_cost_bps: int = 0) -> int:
    """Option-Adjusted Spread (simplified).

    OAS = Z-spread - option cost.
    For non-callable bonds, option_cost = 0 so OAS = Z-spread.

    Parameters
    ----------
    z_spread_bps : int
        Z-spread in basis points.
    option_cost_bps : int
        Estimated option cost in basis points (default 0).

    Returns
    -------
    int
        OAS in basis points.
    """
    return z_spread_bps - option_cost_bps


def compute_relative_value(
    current_spread_bps: float,
    historical_spreads: list[float],
    peer_spreads: list[float] | None = None,
    sector_spread_bps: float | None = None,
) -> dict:
    """Relative value analysis.

    Parameters
    ----------
    current_spread_bps : float
        Current spread of the bond in bps.
    historical_spreads : list[float]
        Historical spread observations for the same bond.
    peer_spreads : list[float] | None
        Spread observations for peer bonds (same sector/rating).
    sector_spread_bps : float | None
        Sector-level index spread in bps.

    Returns
    -------
    dict
        Keys:
        - own_percentile: float (0-100)
        - own_z_score: float
        - vs_peers_percentile: float | None (where current bond ranks among peers)
        - vs_sector_diff_bps: int | None (current - sector)
        - rich_cheap_score: float (-100 to +100, negative=rich, positive=cheap)
    """
    # Own history analysis
    if historical_spreads:
        count_le = sum(1 for v in historical_spreads if v <= current_spread_bps)
        own_percentile = round((count_le / len(historical_spreads)) * 100.0, 2)
        mean_val = statistics.mean(historical_spreads)
        std_dev = statistics.pstdev(historical_spreads) if len(historical_spreads) > 1 else 0.0
        own_z_score = round((current_spread_bps - mean_val) / std_dev, 4) if std_dev > 0 else 0.0
    else:
        own_percentile = 50.0
        own_z_score = 0.0

    # Peers analysis
    vs_peers_percentile: float | None = None
    if peer_spreads:
        all_spreads = peer_spreads + [current_spread_bps]
        count_le_peers = sum(1 for v in all_spreads if v <= current_spread_bps)
        vs_peers_percentile = round((count_le_peers / len(all_spreads)) * 100.0, 2)

    # Sector difference
    vs_sector_diff_bps: int | None = None
    if sector_spread_bps is not None:
        vs_sector_diff_bps = round(current_spread_bps - sector_spread_bps)

    # Rich/cheap score: -100 (very rich) to +100 (very cheap)
    # Based on own_percentile: 50th = neutral (0), 0th = rich (-100), 100th = cheap (+100)
    rich_cheap_score = round((own_percentile - 50.0) * 2.0, 2)
    # Clamp to [-100, 100]
    rich_cheap_score = max(-100.0, min(100.0, rich_cheap_score))

    return {
        "own_percentile": own_percentile,
        "own_z_score": own_z_score,
        "vs_peers_percentile": vs_peers_percentile,
        "vs_sector_diff_bps": vs_sector_diff_bps,
        "rich_cheap_score": rich_cheap_score,
    }


def compute_breakeven_spread(
    spread_bps: float,
    modified_duration: float,
    horizon_years: float = 1.0,
) -> dict:
    """Breakeven spread analysis.

    Breakeven widening = carry / spread_duration.
    Carry (bps per year) ~ spread_bps (simplified -- assumes no roll-down).
    Breakeven widening = spread / duration (the spread can widen by this much
    before you lose carry over the horizon).

    Parameters
    ----------
    spread_bps : float
        Current spread in basis points.
    modified_duration : float
        Bond's modified duration (years).
    horizon_years : float
        Investment horizon (default 1 year).

    Returns
    -------
    dict
        Keys: carry_bps, breakeven_widening_bps, horizon_years.
    """
    carry_bps = spread_bps * horizon_years
    if modified_duration > 0:
        breakeven_widening_bps = round(carry_bps / modified_duration, 2)
    else:
        breakeven_widening_bps = float("inf") if carry_bps > 0 else 0.0

    return {
        "carry_bps": round(carry_bps, 2),
        "breakeven_widening_bps": breakeven_widening_bps,
        "horizon_years": horizon_years,
    }


def compute_spread_duration(modified_duration: float) -> float:
    """Spread duration ~ modified duration for fixed-rate bonds.

    For floating-rate bonds, spread duration would differ (typically
    much shorter, equal to time to next coupon reset).

    Parameters
    ----------
    modified_duration : float
        Bond's modified duration.

    Returns
    -------
    float
        Spread duration.
    """
    return modified_duration
