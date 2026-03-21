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
