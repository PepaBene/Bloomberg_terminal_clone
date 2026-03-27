"""E12 FI Risk Engine — Portfolio DV01, Rate/Spread Scenario P&L, Credit VaR, Expected Loss."""

from __future__ import annotations

import math


# Default probability by rating numeric (1Y horizon, simplified)
# 1=AAA ... 10=BBB- ... 22=D
PD_BY_RATING: dict[int, float] = {
    1: 0.0001,   # AAA
    2: 0.0002,   # AA+
    3: 0.0003,   # AA
    4: 0.0005,   # AA-
    5: 0.0008,   # A+
    6: 0.0010,   # A
    7: 0.0015,   # A-
    8: 0.0020,   # BBB+
    9: 0.0030,   # BBB
    10: 0.0050,  # BBB-
    11: 0.0100,  # BB+
    12: 0.0150,  # BB
    13: 0.0250,  # BB-
    14: 0.0400,  # B+
    15: 0.0600,  # B
    16: 0.0900,  # B-
    17: 0.1500,  # CCC+
    18: 0.2000,  # CCC
    19: 0.2500,  # CCC-
    20: 0.3500,  # CC
    21: 0.5000,  # C
    22: 1.0000,  # D
}

# Recovery rates by seniority
RECOVERY_RATES: dict[str, float] = {
    "SENIOR_SECURED": 0.55,
    "SENIOR_UNSECURED": 0.40,
    "SENIOR_SUBORDINATED": 0.30,
    "SUBORDINATED": 0.25,
    "JUNIOR_SUBORDINATED": 0.15,
}

DEFAULT_LGD = 0.60  # 1 - recovery for senior unsecured

# Rating labels for buckets
RATING_LABELS: dict[int, str] = {
    1: "AAA", 2: "AA+", 3: "AA", 4: "AA-",
    5: "A+", 6: "A", 7: "A-",
    8: "BBB+", 9: "BBB", 10: "BBB-",
    11: "BB+", 12: "BB", 13: "BB-",
    14: "B+", 15: "B", 16: "B-",
    17: "CCC+", 18: "CCC", 19: "CCC-",
    20: "CC", 21: "C", 22: "D",
}

# Z-scores for common confidence levels
_Z_SCORES: dict[float, float] = {
    0.90: 1.282,
    0.95: 1.645,
    0.99: 2.326,
    0.999: 3.090,
}


def _get_z_score(confidence: float) -> float:
    """Look up z-score for a given confidence level, or approximate using Abramowitz & Stegun."""
    if confidence in _Z_SCORES:
        return _Z_SCORES[confidence]
    # Rational approximation (Abramowitz & Stegun 26.2.23)
    if confidence <= 0.0 or confidence >= 1.0:
        return 2.326  # fallback to 99%
    p = 1.0 - confidence
    t = math.sqrt(-2.0 * math.log(p))
    c0, c1, c2 = 2.515517, 0.802853, 0.010328
    d1, d2, d3 = 1.432788, 0.189269, 0.001308
    return t - (c0 + c1 * t + c2 * t * t) / (1.0 + d1 * t + d2 * t * t + d3 * t * t * t)


def _get_lgd(seniority: str | None) -> float:
    """Return LGD = 1 - recovery_rate for a given seniority."""
    if seniority and seniority in RECOVERY_RATES:
        return 1.0 - RECOVERY_RATES[seniority]
    return DEFAULT_LGD


def compute_portfolio_dv01(positions: list[dict]) -> float:
    """Portfolio DV01 = sum(market_value * modified_duration * 0.0001).

    Each position should have either:
    - {market_value, modified_duration} — DV01 computed from these
    - {weight, dv01} — pre-computed DV01 weighted
    """
    total = 0.0
    for pos in positions:
        if "dv01" in pos:
            # Pre-computed DV01, possibly weighted
            weight = pos.get("weight", 1.0)
            total += pos["dv01"] * weight
        else:
            mv = pos.get("market_value", 0.0)
            md = pos.get("modified_duration", 0.0)
            total += mv * md * 0.0001
    return total


def compute_rate_scenario_pnl(
    positions: list[dict],
    rate_shift_bps: float,
) -> dict:
    """Compute P&L from a parallel rate shift using duration-convexity approximation.

    positions: list of {market_value, modified_duration, convexity, cusip}
    For each position:  delta_P = -D * delta_y * MV + 0.5 * C * delta_y^2 * MV
    Returns {total_pnl, total_pnl_pct, by_position: [{cusip, pnl, pnl_pct}]}
    """
    delta_y = rate_shift_bps / 10000.0
    total_pnl = 0.0
    total_mv = 0.0
    by_position: list[dict] = []

    for pos in positions:
        mv = pos.get("market_value", 0.0)
        md = pos.get("modified_duration", 0.0)
        conv = pos.get("convexity", 0.0)
        cusip = pos.get("cusip")

        # Duration-convexity approximation: %change = -D*dy + 0.5*C*dy^2
        pct_change = -md * delta_y + 0.5 * conv * delta_y ** 2
        pnl = pct_change * mv

        total_pnl += pnl
        total_mv += mv
        by_position.append({
            "cusip": cusip,
            "pnl": pnl,
            "pnl_pct": pct_change,
        })

    total_pnl_pct = total_pnl / total_mv if total_mv != 0 else 0.0

    return {
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct,
        "by_position": by_position,
    }


def compute_spread_scenario_pnl(
    positions: list[dict],
    spread_shift_bps: float,
) -> dict:
    """Compute P&L from a spread widening/tightening.

    positions: list of {market_value, spread_duration, cusip}
    For each position:  delta_P approx= -spread_duration * delta_s * market_value
    Returns {total_pnl, total_pnl_pct, by_position: [{cusip, pnl, pnl_pct}]}
    """
    delta_s = spread_shift_bps / 10000.0
    total_pnl = 0.0
    total_mv = 0.0
    by_position: list[dict] = []

    for pos in positions:
        mv = pos.get("market_value", 0.0)
        sd = pos.get("spread_duration", 0.0) or 0.0
        cusip = pos.get("cusip")

        pnl = -sd * delta_s * mv
        pnl_pct = -sd * delta_s if sd else 0.0

        total_pnl += pnl
        total_mv += mv
        by_position.append({
            "cusip": cusip,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
        })

    total_pnl_pct = total_pnl / total_mv if total_mv != 0 else 0.0

    return {
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct,
        "by_position": by_position,
    }


def compute_credit_distribution(positions: list[dict]) -> dict:
    """Compute credit quality distribution of portfolio.

    positions: list of {market_value, rating_numeric, is_investment_grade}
    Returns {
        ig_pct, hy_pct, nr_pct,
        by_rating: {rating_bucket: {count, weight_pct, total_mv}},
        avg_rating_numeric, weighted_avg_spread
    }
    """
    total_mv = sum(pos.get("market_value", 0.0) for pos in positions)
    if total_mv == 0:
        return {
            "ig_pct": 0.0,
            "hy_pct": 0.0,
            "nr_pct": 0.0,
            "by_rating": {},
            "avg_rating_numeric": None,
            "weighted_avg_spread": None,
        }

    ig_mv = 0.0
    hy_mv = 0.0
    nr_mv = 0.0
    rating_buckets: dict[str, dict] = {}
    weighted_rating_sum = 0.0
    rated_mv = 0.0
    weighted_spread_sum = 0.0
    spread_mv = 0.0

    for pos in positions:
        mv = pos.get("market_value", 0.0)
        rating = pos.get("rating_numeric")
        ig = pos.get("is_investment_grade")
        spread = pos.get("spread_bps")

        if rating is None:
            nr_mv += mv
        else:
            # Investment grade: rating_numeric <= 10 (BBB- and above)
            if ig is True or (ig is None and rating <= 10):
                ig_mv += mv
            else:
                hy_mv += mv

            label = RATING_LABELS.get(rating, f"Rating_{rating}")
            if label not in rating_buckets:
                rating_buckets[label] = {"count": 0, "weight_pct": 0.0, "total_mv": 0.0}
            rating_buckets[label]["count"] += 1
            rating_buckets[label]["total_mv"] += mv

            weighted_rating_sum += rating * mv
            rated_mv += mv

        if spread is not None:
            weighted_spread_sum += spread * mv
            spread_mv += mv

    # Compute weight percentages for buckets
    for bucket in rating_buckets.values():
        bucket["weight_pct"] = bucket["total_mv"] / total_mv * 100.0 if total_mv else 0.0

    avg_rating = weighted_rating_sum / rated_mv if rated_mv > 0 else None
    weighted_avg_spread = weighted_spread_sum / spread_mv if spread_mv > 0 else None

    return {
        "ig_pct": ig_mv / total_mv * 100.0,
        "hy_pct": hy_mv / total_mv * 100.0,
        "nr_pct": nr_mv / total_mv * 100.0,
        "by_rating": rating_buckets,
        "avg_rating_numeric": avg_rating,
        "weighted_avg_spread": weighted_avg_spread,
    }


def compute_expected_loss(positions: list[dict]) -> dict:
    """Expected loss = sum(EAD x PD x LGD) for each position.

    positions: list of {market_value, rating_numeric, seniority, cusip}
    Returns {total_expected_loss, total_expected_loss_pct, by_position: [{cusip, expected_loss, pd, lgd}]}
    """
    total_el = 0.0
    total_mv = 0.0
    by_position: list[dict] = []

    for pos in positions:
        mv = pos.get("market_value", 0.0)
        rating = pos.get("rating_numeric")
        seniority = pos.get("seniority")
        cusip = pos.get("cusip")

        pd = PD_BY_RATING.get(rating, 0.0) if rating is not None else 0.0
        lgd = _get_lgd(seniority)

        el = mv * pd * lgd

        total_el += el
        total_mv += mv
        by_position.append({
            "cusip": cusip,
            "expected_loss": el,
            "pd": pd,
            "lgd": lgd,
        })

    total_el_pct = total_el / total_mv if total_mv > 0 else 0.0

    return {
        "total_expected_loss": total_el,
        "total_expected_loss_pct": total_el_pct,
        "by_position": by_position,
    }


def compute_credit_var(
    positions: list[dict],
    confidence: float = 0.99,
    horizon_days: int = 250,
) -> dict:
    """Credit VaR using simplified parametric approach.

    Uses expected loss + unexpected loss at confidence level.
    UL = z_score * sqrt(sum(EAD^2 * PD * (1-PD) * LGD^2))
    Scale to horizon: multiply by sqrt(horizon_days / 250)

    Returns {expected_loss, unexpected_loss, credit_var, confidence, horizon_days}
    """
    z = _get_z_score(confidence)

    total_el = 0.0
    variance_sum = 0.0

    for pos in positions:
        mv = pos.get("market_value", 0.0)
        rating = pos.get("rating_numeric")
        seniority = pos.get("seniority")

        pd = PD_BY_RATING.get(rating, 0.0) if rating is not None else 0.0
        lgd = _get_lgd(seniority)

        # Expected loss for this position
        el = mv * pd * lgd
        total_el += el

        # Variance contribution: EAD^2 * PD * (1 - PD) * LGD^2
        variance_sum += (mv ** 2) * pd * (1.0 - pd) * (lgd ** 2)

    # Unexpected loss at confidence level
    ul = z * math.sqrt(variance_sum) if variance_sum > 0 else 0.0

    # Scale to horizon (annualise relative to 250 trading days)
    horizon_scale = math.sqrt(horizon_days / 250.0) if horizon_days != 250 else 1.0
    ul_scaled = ul * horizon_scale
    el_scaled = total_el * (horizon_days / 250.0) if horizon_days != 250 else total_el

    # Credit VaR = EL + UL
    credit_var = el_scaled + ul_scaled

    return {
        "expected_loss": el_scaled,
        "unexpected_loss": ul_scaled,
        "credit_var": credit_var,
        "confidence": confidence,
        "horizon_days": horizon_days,
    }


def compute_single_bond_risk(
    market_value: float,
    modified_duration: float,
    convexity: float,
    spread_duration: float,
    rating_numeric: int,
    seniority: str = "SENIOR_UNSECURED",
) -> dict:
    """Full risk metrics for a single bond.

    Returns {dv01, rate_pnl_100bps, spread_pnl_100bps, expected_loss, pd_1y, lgd}
    """
    # DV01
    dv01 = market_value * modified_duration * 0.0001

    # Rate P&L for +100 bps
    delta_y = 100.0 / 10000.0  # 0.01
    rate_pct = -modified_duration * delta_y + 0.5 * convexity * delta_y ** 2
    rate_pnl_100bps = rate_pct * market_value

    # Spread P&L for +100 bps
    delta_s = 100.0 / 10000.0
    spread_pnl_100bps = -spread_duration * delta_s * market_value

    # Credit risk
    pd = PD_BY_RATING.get(rating_numeric, 0.0)
    lgd = _get_lgd(seniority)
    expected_loss = market_value * pd * lgd

    return {
        "dv01": dv01,
        "rate_pnl_100bps": rate_pnl_100bps,
        "spread_pnl_100bps": spread_pnl_100bps,
        "expected_loss": expected_loss,
        "pd_1y": pd,
        "lgd": lgd,
    }
