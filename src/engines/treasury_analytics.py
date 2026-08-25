"""Pillar 1 FI Supplement D11: Treasury Analytics Engine.

Pure computation functions (no DB access) for treasury securities analysis.
"""

from __future__ import annotations

from datetime import date


# ── Tenor buckets used for on-the-run identification ─────────────────

TENOR_BUCKETS: dict[str, tuple[float, float]] = {
    "1M": (0.0, 0.125),       # up to ~1.5 months
    "3M": (0.125, 0.375),     # ~1.5 to ~4.5 months
    "6M": (0.375, 0.75),      # ~4.5 to 9 months
    "1Y": (0.75, 1.5),        # 9 months to 1.5 years
    "2Y": (1.5, 2.5),
    "3Y": (2.5, 3.5),
    "5Y": (3.5, 6.0),
    "7Y": (6.0, 8.5),
    "10Y": (8.5, 15.0),
    "20Y": (15.0, 25.0),
    "30Y": (25.0, 100.0),
}


def classify_treasury(
    coupon_rate: float,
    maturity_years: float,
    is_inflation_indexed: bool = False,
) -> str:
    """Classify a treasury security by type.

    Returns one of: BILL, NOTE, BOND, TIPS.
    """
    if is_inflation_indexed:
        return "TIPS"
    if coupon_rate == 0 and maturity_years <= 1.0:
        return "BILL"
    if maturity_years <= 10.0:
        return "NOTE"
    return "BOND"


def compute_treasury_ytm(
    coupon_rate: float,
    face_value: float,
    price: float,
    years_to_maturity: float,
    frequency: int = 2,
) -> float:
    """Compute yield-to-maturity for a treasury security.

    For T-Bills (coupon_rate == 0, years_to_maturity < 1): uses discount yield formula.
    For coupon bonds: uses Newton-Raphson iteration.

    Parameters
    ----------
    coupon_rate : float
        Annual coupon rate as a percentage (e.g. 5.0 for 5%).
    face_value : float
        Face / par value (typically 100).
    price : float
        Current market price.
    years_to_maturity : float
        Years remaining to maturity.
    frequency : int
        Coupon payment frequency per year (2 = semi-annual).

    Returns
    -------
    float
        Annualised yield-to-maturity as a percentage.
    """
    if years_to_maturity <= 0:
        return 0.0

    # T-Bill: discount yield formula.
    # [Bug fix] The bank-discount-yield convention universally used to quote
    # T-Bill discount rates annualizes on an actual/360 basis, NOT a
    # calendar-year (365/365.25) basis: discount_yield = (FV-P)/FV *
    # (360/days_to_maturity). Every caller in this codebase computes
    # years_to_maturity as days/365.25, so `1.0/years_to_maturity` was
    # `365.25/days` -- the wrong basis, overstating the discount yield
    # relative to the market-standard actual/360 quote.
    if coupon_rate == 0 and years_to_maturity < 1.0:
        days_to_maturity = years_to_maturity * 365.25
        discount_yield = ((face_value - price) / face_value) * (360.0 / days_to_maturity) * 100.0
        return round(discount_yield, 6)

    # Coupon bond: Newton-Raphson
    coupon_per_period = (coupon_rate / 100.0) * face_value / frequency
    n_periods = int(round(years_to_maturity * frequency))
    if n_periods < 1:
        n_periods = 1

    # Initial guess
    ytm_guess = coupon_rate / 100.0 if coupon_rate > 0 else 0.05

    for _ in range(200):
        r = ytm_guess / frequency
        if abs(r) < 1e-12:
            # Edge case: near zero yield
            pv = coupon_per_period * n_periods + face_value
            dpv = 0.0
            for t in range(1, n_periods + 1):
                dpv -= t * coupon_per_period / frequency
            dpv -= n_periods * face_value / frequency
        else:
            discount = (1 + r) ** (-n_periods)
            pv = coupon_per_period * (1 - discount) / r + face_value * discount
            # Derivative of PV with respect to ytm (chain rule: dr/dytm = 1/freq)
            dpv_dr = (
                -coupon_per_period * (
                    ((1 - discount) / (r * r))
                    - (n_periods * (1 + r) ** (-(n_periods + 1))) / r
                )
                * (-1)
                + coupon_per_period * (1 - discount) / (r * r) * (-1)
            )
            # Simpler numeric derivative approach for robustness
            dr = 1e-8
            r2 = r + dr
            discount2 = (1 + r2) ** (-n_periods)
            pv2 = coupon_per_period * (1 - discount2) / r2 + face_value * discount2
            dpv = (pv2 - pv) / dr / frequency

        f_val = pv - price
        if abs(dpv) < 1e-15:
            break
        ytm_guess -= f_val / dpv
        if abs(f_val) < 1e-10:
            break

    return round(ytm_guess * 100.0, 6)


def compute_duration_convexity(
    ytm: float,
    coupon_rate: float,
    years_to_maturity: float,
    frequency: int = 2,
) -> dict:
    """Compute modified duration, Macaulay duration, and convexity.

    Parameters
    ----------
    ytm : float
        Yield-to-maturity as a percentage (e.g. 5.0 for 5%).
    coupon_rate : float
        Annual coupon rate as a percentage.
    years_to_maturity : float
        Years remaining to maturity.
    frequency : int
        Coupon payment frequency per year (2 = semi-annual).

    Returns
    -------
    dict
        Keys: modified_duration, macaulay_duration, convexity.
    """
    if years_to_maturity <= 0:
        return {
            "modified_duration": 0.0,
            "macaulay_duration": 0.0,
            "convexity": 0.0,
        }

    y = ytm / 100.0
    c = coupon_rate / 100.0
    n_periods = int(round(years_to_maturity * frequency))
    if n_periods < 1:
        n_periods = 1

    coupon_per_period = c * 100.0 / frequency  # per $100 face
    r = y / frequency

    # Zero coupon special case
    if coupon_rate == 0 or c == 0:
        macaulay = years_to_maturity
        modified = macaulay / (1 + r) if (1 + r) != 0 else macaulay
        convexity = years_to_maturity * (years_to_maturity + 1.0 / frequency) / ((1 + r) ** 2)
        return {
            "modified_duration": round(modified, 6),
            "macaulay_duration": round(macaulay, 6),
            "convexity": round(convexity, 6),
        }

    # Price
    price = 0.0
    weighted_cf = 0.0
    conv_sum = 0.0

    for t in range(1, n_periods + 1):
        cf = coupon_per_period
        if t == n_periods:
            cf += 100.0  # face value at maturity
        discount = (1 + r) ** (-t)
        pv_cf = cf * discount
        price += pv_cf
        time_in_years = t / frequency
        weighted_cf += time_in_years * pv_cf
        conv_sum += (t * (t + 1)) * cf * discount

    if price == 0:
        return {
            "modified_duration": 0.0,
            "macaulay_duration": 0.0,
            "convexity": 0.0,
        }

    macaulay_duration = weighted_cf / price
    modified_duration = macaulay_duration / (1 + r)
    convexity = conv_sum / (price * frequency * frequency * (1 + r) ** 2)

    return {
        "modified_duration": round(modified_duration, 6),
        "macaulay_duration": round(macaulay_duration, 6),
        "convexity": round(convexity, 6),
    }


def identify_on_the_run(
    securities_list: list[dict],
) -> dict[str, dict]:
    """Identify on-the-run (most recently issued) treasury per tenor bucket.

    Parameters
    ----------
    securities_list : list[dict]
        Each dict must have keys: cusip, issue_date (date), maturity_date (date).
        Optional: coupon_rate, auction_high_yield.

    Returns
    -------
    dict[str, dict]
        Mapping of tenor bucket name to the most recently issued security info.
    """
    if not securities_list:
        return {}

    result: dict[str, dict] = {}
    today = date.today()

    for sec in securities_list:
        maturity = sec.get("maturity_date")
        issue = sec.get("issue_date")
        if maturity is None:
            continue

        years_to_maturity = (maturity - today).days / 365.25

        if years_to_maturity <= 0:
            continue  # already matured

        # Find matching tenor bucket
        for tenor, (lo, hi) in TENOR_BUCKETS.items():
            if lo < years_to_maturity <= hi:
                # Check if this security is more recently issued
                existing = result.get(tenor)
                if existing is None:
                    result[tenor] = sec
                else:
                    existing_issue = existing.get("issue_date")
                    if issue is not None and (existing_issue is None or issue > existing_issue):
                        result[tenor] = sec
                break

    return result
