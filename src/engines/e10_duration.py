"""E10 Duration & Convexity Engine — DV01, Key Rate Durations, Effective Duration, Portfolio Duration."""

from __future__ import annotations

from src.engines.bond_analytics import (
    compute_convexity,
    compute_macaulay_duration,
    compute_modified_duration,
)

# Standard key rate tenor points
KEY_RATE_TENORS = ["1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y"]
KEY_RATE_YEARS = [1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 20.0, 30.0]


def compute_dv01(modified_duration: float, price: float, face_value: float = 100.0) -> float:
    """Dollar Value of a Basis Point (DV01/PVBP).

    DV01 = modified_duration * price * 0.0001
    Returns the dollar change in price for a 1bp yield change.
    """
    return modified_duration * price * 0.0001


def _price_from_zero_curve(
    coupon_rate: float,
    face_value: float,
    years_to_maturity: float,
    frequency: int,
    zero_rates: dict[float, float],
) -> float:
    """Reprice a bond using a set of zero rates (tenor_years -> zero_rate).

    Each cash flow is discounted at the interpolated zero rate for its tenor.
    Linear interpolation is used between known tenor points.
    """
    if frequency <= 0 or years_to_maturity <= 0:
        return face_value

    coupon = coupon_rate * face_value / frequency
    n_periods = int(round(years_to_maturity * frequency))
    if n_periods < 1:
        n_periods = 1

    # Sort tenor points for interpolation
    sorted_tenors = sorted(zero_rates.keys())
    sorted_rates = [zero_rates[t] for t in sorted_tenors]

    def _interp_rate(t: float) -> float:
        """Linearly interpolate the zero rate at time t."""
        if not sorted_tenors:
            return 0.0
        if t <= sorted_tenors[0]:
            return sorted_rates[0]
        if t >= sorted_tenors[-1]:
            return sorted_rates[-1]
        for i in range(len(sorted_tenors) - 1):
            if sorted_tenors[i] <= t <= sorted_tenors[i + 1]:
                denom = sorted_tenors[i + 1] - sorted_tenors[i]
                if abs(denom) < 1e-12:
                    return sorted_rates[i]
                frac = (t - sorted_tenors[i]) / denom
                return sorted_rates[i] + frac * (sorted_rates[i + 1] - sorted_rates[i])
        return sorted_rates[-1]

    price = 0.0
    for k in range(1, n_periods + 1):
        t = k / frequency
        r = _interp_rate(t)
        df = (1 + r) ** (-t)
        if k < n_periods:
            price += coupon * df
        else:
            price += (coupon + face_value) * df

    return price


def compute_key_rate_durations(
    price: float,
    coupon_rate: float,
    face_value: float,
    years_to_maturity: float,
    frequency: int,
    zero_curve: list[dict],  # [{tenor_years, zero_rate}]
    bump_bps: float = 1.0,
) -> dict[str, float]:
    """Key Rate Durations at 8 standard tenors.

    For each tenor, bump the zero rate at that point by bump_bps,
    reprice the bond, compute partial duration.
    KRD_i = -(P_up - P_down) / (2 * P * delta_y)
    Returns dict like {"1Y": 0.02, "2Y": 0.05, ...}
    """
    # Build base zero rate map: tenor_years -> zero_rate
    base_rates: dict[float, float] = {}
    for point in zero_curve:
        tenor = point.get("tenor_years", 0.0)
        rate = point.get("zero_rate", 0.0)
        base_rates[tenor] = rate

    delta_y = bump_bps / 10000.0
    if abs(delta_y) < 1e-15:
        return {t: 0.0 for t in KEY_RATE_TENORS}
    result: dict[str, float] = {}

    for tenor_label, tenor_years in zip(KEY_RATE_TENORS, KEY_RATE_YEARS):
        # Bump up
        rates_up = dict(base_rates)
        rates_up[tenor_years] = rates_up.get(tenor_years, 0.0) + delta_y

        # Bump down
        rates_down = dict(base_rates)
        rates_down[tenor_years] = rates_down.get(tenor_years, 0.0) - delta_y

        p_up = _price_from_zero_curve(
            coupon_rate, face_value, years_to_maturity, frequency, rates_up
        )
        p_down = _price_from_zero_curve(
            coupon_rate, face_value, years_to_maturity, frequency, rates_down
        )

        if price > 0:
            krd = -(p_up - p_down) / (2.0 * price * delta_y)
        else:
            krd = 0.0

        result[tenor_label] = round(krd, 6)

    return result


def compute_effective_duration(
    price_up: float,
    price_down: float,
    price_base: float,
    shock_bps: float = 100.0,
) -> float:
    """Effective duration for bonds with embedded options (callables).

    ED = (P_down - P_up) / (2 * P_base * delta_y)
    where delta_y = shock_bps / 10000
    """
    delta_y = shock_bps / 10000.0
    if price_base <= 0 or delta_y == 0:
        return 0.0
    return (price_down - price_up) / (2.0 * price_base * delta_y)


def compute_effective_convexity(
    price_up: float,
    price_down: float,
    price_base: float,
    shock_bps: float = 100.0,
) -> float:
    """Effective convexity for bonds with embedded options.

    EC = (P_up + P_down - 2*P_base) / (P_base * delta_y^2)
    """
    delta_y = shock_bps / 10000.0
    if price_base <= 0 or delta_y == 0:
        return 0.0
    return (price_up + price_down - 2.0 * price_base) / (price_base * delta_y ** 2)


def compute_portfolio_duration(
    positions: list[dict],
) -> dict:
    """Portfolio-level duration analytics.

    positions: list of {weight, modified_duration, dv01, convexity, key_rate_durations}
    Returns {
        weighted_avg_duration, portfolio_dv01, weighted_avg_convexity,
        portfolio_key_rate_durations: {tenor: weighted_krd}
    }
    """
    if not positions:
        return {
            "weighted_avg_duration": 0.0,
            "portfolio_dv01": 0.0,
            "weighted_avg_convexity": 0.0,
            "portfolio_key_rate_durations": None,
        }

    total_weight = sum(p.get("weight", 0.0) for p in positions)
    if total_weight == 0:
        total_weight = 1.0  # avoid division by zero

    weighted_duration = 0.0
    portfolio_dv01 = 0.0
    weighted_convexity = 0.0
    has_krds = False
    krd_accum: dict[str, float] = {}

    for pos in positions:
        w = pos.get("weight", 0.0)
        norm_w = w / total_weight
        weighted_duration += norm_w * pos.get("modified_duration", 0.0)
        portfolio_dv01 += pos.get("dv01", 0.0) * w
        weighted_convexity += norm_w * pos.get("convexity", 0.0)

        krds = pos.get("key_rate_durations")
        if krds:
            has_krds = True
            for tenor, krd_val in krds.items():
                krd_accum[tenor] = krd_accum.get(tenor, 0.0) + norm_w * krd_val

    return {
        "weighted_avg_duration": round(weighted_duration, 6),
        "portfolio_dv01": round(portfolio_dv01, 6),
        "weighted_avg_convexity": round(weighted_convexity, 6),
        "portfolio_key_rate_durations": krd_accum if has_krds else None,
    }


def estimate_price_change(
    modified_duration: float,
    convexity: float,
    yield_change_bps: float,
) -> float:
    """Estimate percentage price change using duration-convexity approximation.

    delta_P/P ~ -D * delta_y + 0.5 * C * delta_y^2
    where delta_y = yield_change_bps / 10000
    Returns percentage change (e.g., -0.05 for 5% decrease).
    """
    delta_y = yield_change_bps / 10000.0
    return -modified_duration * delta_y + 0.5 * convexity * delta_y ** 2


def generate_rate_sensitivity_table(
    modified_duration: float,
    convexity: float,
    base_price: float,
    shifts_bps: list[int] | None = None,
) -> list[dict]:
    """Generate price impact table for various yield shifts.

    Default shifts: [-300, -200, -100, -50, -25, +25, +50, +100, +200, +300]
    Returns list of {shift_bps, price_change_pct, estimated_new_price}.
    """
    if shifts_bps is None:
        shifts_bps = [-300, -200, -100, -50, -25, 25, 50, 100, 200, 300]

    table: list[dict] = []
    for shift in shifts_bps:
        pct_change = estimate_price_change(modified_duration, convexity, float(shift))
        new_price = base_price * (1.0 + pct_change)
        table.append({
            "shift_bps": shift,
            "price_change_pct": round(pct_change, 8),
            "estimated_new_price": round(new_price, 4),
        })

    return table
