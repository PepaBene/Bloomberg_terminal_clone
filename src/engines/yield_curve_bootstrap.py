"""Yield Curve Bootstrapping Engine (Part 2).

Computes zero-coupon rates, discount factors, and forward rates from
par yield curve data using the standard bootstrapping method.
"""

import math


def bootstrap_zero_curve(
    tenors: list[float],
    par_rates: list[float],
) -> list[dict]:
    """Bootstrap zero-coupon rates from par rates.

    Parameters
    ----------
    tenors : list[float]
        Tenor in years (e.g. [0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]).
    par_rates : list[float]
        Par coupon rates at each tenor (as decimals, e.g. 0.05 = 5%).

    Returns
    -------
    list[dict]
        Each dict has: tenor_years, zero_rate, discount_factor, forward_rate.
    """
    if len(tenors) != len(par_rates):
        raise ValueError("tenors and par_rates must have same length")
    if not tenors:
        return []

    results: list[dict] = []
    discount_factors: list[float] = []

    for i, (t, c) in enumerate(zip(tenors, par_rates)):
        if t <= 1.0:
            # For short tenors (≤ 1 year), zero rate equals par rate
            z = c
            df = 1.0 / (1.0 + z * t) if t > 0 else 1.0
        else:
            # Bootstrap: solve for discount factor at tenor t
            # Par bond: c * sum(df_j) + (1 + c) * df_t = 1
            coupon_sum = sum(
                discount_factors[j] * c
                for j in range(len(discount_factors))
                if tenors[j] < t  # only use shorter tenor DFs  # noqa: B023
            )
            df = (1.0 - coupon_sum) / (1.0 + c)
            # Convert DF to continuously compounded zero rate
            z = -math.log(df) / t if df > 0 and t > 0 else 0.0

        discount_factors.append(df)

        # Forward rate: implied rate between this tenor and previous
        if i == 0:
            fwd = z
        else:
            prev_t = tenors[i - 1]
            prev_df = discount_factors[i - 1]
            dt = t - prev_t
            if dt > 0 and df > 0 and prev_df > 0:
                fwd = math.log(prev_df / df) / dt
            else:
                fwd = z

        results.append({
            "tenor_years": t,
            "zero_rate": round(z, 6),
            "discount_factor": round(df, 8),
            "forward_rate": round(fwd, 6),
        })

    return results


def compute_spread(rate_short: float | None, rate_long: float | None) -> float | None:
    """Compute spread between two rates (long minus short)."""
    if rate_short is None or rate_long is None:
        return None
    return rate_long - rate_short


def enhanced_bootstrap(par_rates: dict[str, float]) -> dict:
    """Full FI bootstrap: par → zero → discount factors → forward rates.

    Args:
        par_rates: dict mapping tenor strings to par rates, e.g. {"1M": 0.05, "3M": 0.052, ...}

    Returns:
        dict with keys: "par", "zero", "discount_factors", "forwards"
    """
    # Map tenor strings to years
    TENOR_TO_YEARS = {
        "1M": 1/12, "3M": 0.25, "6M": 0.5, "1Y": 1.0, "2Y": 2.0,
        "3Y": 3.0, "5Y": 5.0, "7Y": 7.0, "10Y": 10.0, "20Y": 20.0, "30Y": 30.0,
    }

    tenors = []
    rates = []
    for t_str in ["1M", "3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y"]:
        if t_str in par_rates and par_rates[t_str] is not None:
            tenors.append(TENOR_TO_YEARS[t_str])
            rates.append(par_rates[t_str])

    if not tenors:
        return {"par": {}, "zero": {}, "discount_factors": {}, "forwards": {}}

    # Use existing bootstrap
    results = bootstrap_zero_curve(tenors, rates)

    par_out = {}
    zero_out = {}
    df_out = {}
    fwd_out = {}

    for r in results:
        t = r["tenor_years"]
        # Find tenor string
        for ts, ty in TENOR_TO_YEARS.items():
            if abs(ty - t) < 0.001:
                par_out[ts] = par_rates.get(ts)
                zero_out[ts] = r.get("zero_rate")
                df_out[ts] = r.get("discount_factor")
                fwd_out[ts] = r.get("forward_rate")
                break

    return {"par": par_out, "zero": zero_out, "discount_factors": df_out, "forwards": fwd_out}
