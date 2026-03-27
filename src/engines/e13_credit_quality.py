"""E13 Credit Quality Engine — Ohlson O-Score, Credit Momentum, Fallen Angel Probability, Refinancing Risk.

All functions are pure computation — no database access.
"""

from __future__ import annotations

import math


def compute_ohlson_o_score(
    total_assets: float,
    total_liabilities: float,
    working_capital: float,
    current_liabilities: float,
    net_income: float,
    funds_from_operations: float,
    total_debt: float,
    net_income_lag1: float,
    total_assets_lag1: float,
    consecutive_loss_years: int = 0,
) -> dict:
    """Ohlson O-Score (1980) — logistic regression model for bankruptcy prediction.

    Based on Ohlson (1980) "Financial Ratios and the Probabilistic Prediction
    of Bankruptcy", Journal of Accounting Research, Vol. 18, No. 1.

    9 components with original Model 1 coefficients:
    T1 = -1.32 - 0.407*log(TA)                  (SIZE)
    T2 = +6.03 * (TL/TA)                        (LEVERAGE)
    T3 = -1.43 * (WC/TA)                        (LIQUIDITY)
    T4 = +0.0757 * (CL/CA)                      (CL ratio — CA = CL + WC)
    T5 = -2.37 * (NI/TA)                        (ROA)
    T6 = -1.83 * (FFO/TL)                       (cash flow coverage)
    T7 = +0.285 * OENEG                         (1 if TL>TA else 0)
    T8 = +0.285 * INTWO                         (1 if NI<0 for last 2 years else 0)
    T9 = -0.521 * CHIN                          (change in NI: (NI-NI_lag)/(|NI|+|NI_lag|))

    O-Score = T1+T2+T3+T4+T5+T6+T7+T8+T9
    P(bankruptcy) = 1/(1+exp(-O-Score))

    Parameters
    ----------
    consecutive_loss_years : int
        Number of consecutive years with negative net income (default 0).
        If >= 2, INTWO indicator is set to 1.

    Returns dict with keys: o_score, probability_of_default, components.
    """
    if total_assets <= 0:
        # Avoid log(0) and division by zero; return maximally distressed score
        return {
            "o_score": 10.0,
            "probability_of_default": 1.0 / (1.0 + math.exp(-10.0)),
            "components": {
                "size": 0.0,
                "leverage": 0.0,
                "liquidity": 0.0,
                "cl_ratio": 0.0,
                "roa": 0.0,
                "cash_coverage": 0.0,
                "oeneg": 0.0,
                "intwo": 0.0,
                "ni_change": 0.0,
            },
        }

    ta = total_assets
    tl = total_liabilities
    wc = working_capital
    cl = current_liabilities
    ni = net_income
    ffo = funds_from_operations
    d = total_debt
    ni_lag = net_income_lag1

    # T1: SIZE
    t1 = -1.32 - 0.407 * math.log(max(ta, 1.0))

    # T2: LEVERAGE (TL/TA)
    t2 = 6.03 * (tl / ta)

    # T3: LIQUIDITY (WC/TA)
    t3 = -1.43 * (wc / ta)

    # T4: CL ratio (CL / CA) where CA = CL + WC
    current_assets = cl + wc
    if current_assets > 0:
        t4 = 0.0757 * (cl / current_assets)
    else:
        t4 = 0.0757 * 1.0  # assume worst case: CL = CA

    # T5: ROA (NI/TA)
    t5 = -2.37 * (ni / ta)

    # T6: Cash flow coverage (FFO/TL)
    if tl > 0:
        t6 = -1.83 * (ffo / tl)
    else:
        t6 = -1.83 * 1.0  # assume good coverage if no liabilities

    # T7: OENEG (1 if TL > TA, else 0)
    oeneg_val = 1.0 if tl > ta else 0.0
    t7 = 0.285 * oeneg_val

    # T8: INTWO (1 if NI was negative for both of last 2 years, else 0)
    intwo_val = 1.0 if consecutive_loss_years >= 2 else 0.0
    t8 = 0.285 * intwo_val

    # T9: Change in NI: CHIN = (NI - NI_lag) / (|NI| + |NI_lag|)
    denom_ni = abs(ni) + abs(ni_lag)
    if denom_ni > 0:
        chin = (ni - ni_lag) / denom_ni
    else:
        chin = 0.0
    t9 = -0.521 * chin

    o_score = t1 + t2 + t3 + t4 + t5 + t6 + t7 + t8 + t9

    # Probability of default via logistic function
    probability_of_default = 1.0 / (1.0 + math.exp(-o_score))

    return {
        "o_score": round(o_score, 4),
        "probability_of_default": round(probability_of_default, 6),
        "components": {
            "size": round(t1, 4),
            "leverage": round(t2, 4),
            "liquidity": round(t3, 4),
            "cl_ratio": round(t4, 4),
            "roa": round(t5, 4),
            "cash_coverage": round(t6, 4),
            "oeneg": round(t7, 4),
            "intwo": round(t8, 4),
            "ni_change": round(t9, 4),
        },
    }


def compute_credit_momentum(
    rating_momentum: float,   # positive = upgrades, negative = downgrades, scale -1 to +1
    score_momentum: float,    # positive = improving scores, scale -1 to +1
    spread_momentum: float,   # positive = tightening (improving), scale -1 to +1
) -> dict:
    """Credit Momentum Score.

    Formula: 0.4 * rating_momentum + 0.35 * score_momentum + 0.25 * spread_momentum
    Signal: IMPROVING (>0.15), DETERIORATING (<-0.15), STABLE

    Returns dict with keys: momentum_score, signal, components.
    """
    w_rating = 0.40
    w_score = 0.35
    w_spread = 0.25

    momentum_score = (
        w_rating * rating_momentum
        + w_score * score_momentum
        + w_spread * spread_momentum
    )

    if momentum_score > 0.15:
        signal = "IMPROVING"
    elif momentum_score < -0.15:
        signal = "DETERIORATING"
    else:
        signal = "STABLE"

    return {
        "momentum_score": round(momentum_score, 4),
        "signal": signal,
        "components": {
            "rating_momentum": round(rating_momentum, 4),
            "rating_weight": w_rating,
            "score_momentum": round(score_momentum, 4),
            "score_weight": w_score,
            "spread_momentum": round(spread_momentum, 4),
            "spread_weight": w_spread,
        },
    }


def compute_fallen_angel_probability(
    current_rating_numeric: int,  # 1=AAA to 22=D, BBB-=10
    outlook: str | None = None,   # POSITIVE, STABLE, NEGATIVE
    watch_status: str | None = None,  # WATCH_POSITIVE, WATCH_NEGATIVE, None
    spread_trend: float = 0.0,    # negative = widening (bad), in std devs
    score_trend: float = 0.0,     # negative = deteriorating, scale -1 to +1
) -> float:
    """Estimate probability (0-100) of falling from IG to HY.

    Only meaningful for BBB+/BBB/BBB- rated entities (numeric 8-10).
    For non-BBB entities, returns 0.

    Factors:
    - Base rate by rating: BBB+=5%, BBB=10%, BBB-=20%
    - Outlook: NEGATIVE adds +15%, POSITIVE subtracts -5%
    - Watch: WATCH_NEGATIVE adds +25%
    - Spread trend: each std dev of widening adds +10%
    - Score trend: each 0.1 deterioration adds +5%

    Clamped to [0, 95].
    """
    # Only meaningful for BBB+/BBB/BBB- (numeric 8, 9, 10)
    if current_rating_numeric < 8 or current_rating_numeric > 10:
        return 0.0

    # Base rate by rating
    base_rates = {8: 5.0, 9: 10.0, 10: 20.0}
    prob = base_rates[current_rating_numeric]

    # Outlook adjustment
    if outlook is not None:
        outlook_upper = outlook.upper()
        if outlook_upper == "NEGATIVE":
            prob += 15.0
        elif outlook_upper == "POSITIVE":
            prob -= 5.0
        # STABLE: no change

    # Watch status adjustment
    if watch_status is not None:
        watch_upper = watch_status.upper()
        if watch_upper == "WATCH_NEGATIVE":
            prob += 25.0

    # Spread trend: negative = widening = bad
    # Each std dev of widening (negative spread_trend) adds +10%
    if spread_trend < 0:
        prob += abs(spread_trend) * 10.0

    # Score trend: negative = deteriorating
    # Each 0.1 deterioration adds +5%
    if score_trend < 0:
        prob += abs(score_trend) / 0.1 * 5.0

    # Clamp to [0, 95]
    return round(max(0.0, min(95.0, prob)), 2)


def compute_refinancing_risk(
    maturity_wall_pct: float,   # % of debt maturing in next 2 years (0-100)
    current_spread_bps: float,  # current credit spread in bps
    fcf_to_debt: float,         # FCF / total debt ratio (0.0 to 1.0+)
    credit_direction: float,    # -1 (deteriorating) to +1 (improving)
) -> dict:
    """Refinancing Risk Score (0-100, higher = more risk).

    Components (each normalized to 0-100):
    - Maturity wall (35%): maturity_wall_pct directly
    - Spread stress (30%): min(current_spread_bps / 10, 100)
    - FCF coverage (20%): 100 - min(fcf_to_debt * 200, 100)  (higher FCF = lower risk)
    - Credit direction (15%): (1 - credit_direction) * 50  (deteriorating = higher risk)

    Returns dict with keys: score, assessment, components.
    """
    # Component scores (each 0-100)
    maturity_wall_score = max(0.0, min(100.0, maturity_wall_pct))
    spread_stress_score = min(current_spread_bps / 10.0, 100.0)
    fcf_coverage_score = 100.0 - min(fcf_to_debt * 200.0, 100.0)
    credit_direction_score = (1.0 - credit_direction) * 50.0

    # Clamp individual scores
    spread_stress_score = max(0.0, min(100.0, spread_stress_score))
    fcf_coverage_score = max(0.0, min(100.0, fcf_coverage_score))
    credit_direction_score = max(0.0, min(100.0, credit_direction_score))

    # Weighted composite
    w_maturity = 0.35
    w_spread = 0.30
    w_fcf = 0.20
    w_direction = 0.15

    score = (
        w_maturity * maturity_wall_score
        + w_spread * spread_stress_score
        + w_fcf * fcf_coverage_score
        + w_direction * credit_direction_score
    )
    score = max(0.0, min(100.0, score))

    # Assessment thresholds
    if score >= 75:
        assessment = "HIGH"
    elif score >= 50:
        assessment = "ELEVATED"
    elif score >= 25:
        assessment = "MODERATE"
    else:
        assessment = "LOW"

    return {
        "score": round(score, 2),
        "assessment": assessment,
        "components": {
            "maturity_wall_score": round(maturity_wall_score, 2),
            "spread_stress_score": round(spread_stress_score, 2),
            "fcf_coverage_score": round(fcf_coverage_score, 2),
            "credit_direction_score": round(credit_direction_score, 2),
        },
    }
