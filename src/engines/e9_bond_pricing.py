"""E9 Bond Pricing Engine -- cash flow generation, day count, accrued interest, price<->yield."""

from __future__ import annotations

import calendar
import math
from datetime import date, timedelta

from src.engines.bond_analytics import compute_ytm

# Day count conventions
DAY_COUNT_CONVENTIONS = {
    "30/360": "30_360",
    "ACT/ACT": "ACT_ACT",
    "ACT/360": "ACT_360",
    "ACT/365": "ACT_365",
}


def day_count_fraction(start: date, end: date, convention: str = "30/360") -> float:
    """Compute year fraction between two dates using specified convention.

    Supported conventions:
    - 30/360: each month = 30 days, year = 360 (US 30/360)
    - ACT/ACT: actual days / actual days in year (365 or 366)
    - ACT/360: actual days / 360
    - ACT/365: actual days / 365
    """
    if end <= start:
        return 0.0

    if convention == "30/360":
        d1 = min(start.day, 30)
        # US 30/360: cap d2 to 30 only when d1 is already capped to 30
        d2 = min(end.day, 30) if d1 == 30 else end.day
        numerator = (
            360 * (end.year - start.year)
            + 30 * (end.month - start.month)
            + (d2 - d1)
        )
        return numerator / 360.0

    elif convention == "ACT/ACT":
        actual_days = (end - start).days
        # Determine if we span a leap year -- use the midpoint year to
        # decide the denominator for simplicity (standard ISDA approach
        # for single-period calculations).
        mid = start + timedelta(days=actual_days // 2)
        year_days = 366.0 if calendar.isleap(mid.year) else 365.0
        return actual_days / year_days

    elif convention == "ACT/360":
        actual_days = (end - start).days
        return actual_days / 360.0

    elif convention == "ACT/365":
        actual_days = (end - start).days
        return actual_days / 365.0

    else:
        # Default to 30/360 for unknown conventions
        return day_count_fraction(start, end, "30/360")


def _find_last_coupon_date(
    settlement_date: date,
    maturity_date: date,
    frequency: int,
) -> date:
    """Find the most recent coupon date on or before settlement_date.

    Works backward from the maturity date using the coupon frequency.
    """
    if frequency <= 0:
        return settlement_date

    months_per_period = 12 // frequency
    # Generate coupon dates backward from maturity
    coupon = maturity_date
    prev_coupon = coupon

    # Go back far enough to find coupon before settlement
    while coupon > settlement_date:
        prev_coupon = coupon
        m = coupon.month - months_per_period
        y = coupon.year
        while m <= 0:
            m += 12
            y -= 1
        # Clamp day to valid day in target month
        max_day = calendar.monthrange(y, m)[1]
        d = min(coupon.day, max_day)
        coupon = date(y, m, d)

    return coupon


def _next_coupon_date(coupon: date, frequency: int) -> date:
    """Advance a coupon date by one period."""
    if frequency <= 0:
        return coupon
    months_per_period = 12 // frequency
    m = coupon.month + months_per_period
    y = coupon.year
    while m > 12:
        m -= 12
        y += 1
    max_day = calendar.monthrange(y, m)[1]
    d = min(coupon.day, max_day)
    return date(y, m, d)


def compute_accrued_interest(
    coupon_rate: float,
    face_value: float,
    frequency: int,
    last_coupon_date: date,
    settlement_date: date,
    day_count: str = "30/360",
) -> float:
    """Compute accrued interest from last coupon to settlement.

    AI = (coupon_rate * face_value / frequency) * dcf(last_coupon, settlement) / dcf(last_coupon, next_coupon)
    Simplified: AI = (coupon_rate * face_value / frequency) * dcf(last_coupon, settlement) * frequency
    because dcf for a full period = 1/frequency.

    For practical purposes:
    AI = coupon_per_period * (days_accrued / days_in_period)
    """
    if frequency <= 0 or coupon_rate == 0.0:
        return 0.0

    if settlement_date <= last_coupon_date:
        return 0.0

    coupon_per_period = coupon_rate * face_value / frequency

    # Compute fraction of period elapsed
    next_coupon = _next_coupon_date(last_coupon_date, frequency)
    dcf_accrued = day_count_fraction(last_coupon_date, settlement_date, day_count)
    dcf_full = day_count_fraction(last_coupon_date, next_coupon, day_count)

    if dcf_full <= 0:
        return 0.0

    fraction = dcf_accrued / dcf_full
    return coupon_per_period * fraction


def generate_cash_flow_schedule(
    coupon_rate: float,
    face_value: float,
    frequency: int,
    maturity_date: date,
    settlement_date: date,
    call_schedule: list[dict] | None = None,
) -> list[dict]:
    """Generate complete cash flow schedule for a bond.

    Returns list of {date, amount, type} where type is COUPON, PRINCIPAL, or CALL.
    Only includes cash flows after the settlement date.
    """
    flows: list[dict] = []

    if frequency <= 0:
        # Zero coupon bond -- only principal at maturity
        if maturity_date > settlement_date:
            flows.append({
                "date": maturity_date,
                "amount": face_value,
                "type": "PRINCIPAL",
            })
    else:
        # Generate coupon dates from first coupon after settlement to maturity
        coupon_per_period = coupon_rate * face_value / frequency

        # Find first coupon date after settlement
        last_coupon = _find_last_coupon_date(settlement_date, maturity_date, frequency)
        current = _next_coupon_date(last_coupon, frequency)

        while current < maturity_date:
            flows.append({
                "date": current,
                "amount": round(coupon_per_period, 6),
                "type": "COUPON",
            })
            current = _next_coupon_date(current, frequency)

        # Final coupon + principal at maturity
        if maturity_date > settlement_date:
            flows.append({
                "date": maturity_date,
                "amount": round(coupon_per_period, 6),
                "type": "COUPON",
            })
            flows.append({
                "date": maturity_date,
                "amount": face_value,
                "type": "PRINCIPAL",
            })

    # Add call schedule entries if provided
    if call_schedule:
        for call in call_schedule:
            call_date = call.get("date") or call.get("call_date")
            call_price = call.get("call_price", face_value)
            if call_date and call_date > settlement_date:
                if isinstance(call_date, str):
                    call_date = date.fromisoformat(call_date)
                flows.append({
                    "date": call_date,
                    "amount": float(call_price),
                    "type": "CALL",
                })

    # Sort by date, then by type (COUPON before PRINCIPAL before CALL)
    type_order = {"COUPON": 0, "PRINCIPAL": 1, "CALL": 2}
    flows.sort(key=lambda f: (f["date"], type_order.get(f["type"], 9)))

    return flows


def price_from_yield(
    ytm: float,
    coupon_rate: float,
    face_value: float,
    settlement_date: date,
    maturity_date: date,
    frequency: int = 2,
    day_count: str = "30/360",
) -> dict:
    """Compute clean price, dirty price, accrued interest from yield.

    Returns {clean_price, dirty_price, accrued_interest}.
    """
    if maturity_date <= settlement_date:
        return {
            "clean_price": face_value,
            "dirty_price": face_value,
            "accrued_interest": 0.0,
        }

    years_to_maturity = (maturity_date - settlement_date).days / 365.25

    if frequency <= 0:
        # Zero coupon
        dirty_price = face_value / ((1 + ytm) ** years_to_maturity) if ytm > -1 else face_value
        return {
            "clean_price": round(dirty_price, 6),
            "dirty_price": round(dirty_price, 6),
            "accrued_interest": 0.0,
        }

    coupon_per_period = coupon_rate * face_value / frequency
    n_periods = int(round(years_to_maturity * frequency))
    if n_periods < 1:
        n_periods = 1

    y = ytm / frequency
    if y <= -1.0:
        y = 0.001

    # Compute fractional first period
    last_coupon = _find_last_coupon_date(settlement_date, maturity_date, frequency)
    next_coupon = _next_coupon_date(last_coupon, frequency)

    dcf_accrued = day_count_fraction(last_coupon, settlement_date, day_count)
    dcf_full = day_count_fraction(last_coupon, next_coupon, day_count)

    if dcf_full > 0:
        w = dcf_accrued / dcf_full  # fraction of period elapsed
    else:
        w = 0.0

    # PV of cash flows (dirty price)
    # First coupon is (1-w) periods away, subsequent coupons are t-w periods away
    dirty_price = 0.0
    for t in range(1, n_periods + 1):
        df = (1 + y) ** (-(t - w))
        dirty_price += coupon_per_period * df
    # Principal at maturity
    dirty_price += face_value * (1 + y) ** (-(n_periods - w))

    # Accrued interest
    accrued = compute_accrued_interest(
        coupon_rate, face_value, frequency, last_coupon, settlement_date, day_count
    )

    clean_price = dirty_price - accrued

    return {
        "clean_price": round(clean_price, 6),
        "dirty_price": round(dirty_price, 6),
        "accrued_interest": round(accrued, 6),
    }


def yield_from_price(
    clean_price: float,
    coupon_rate: float,
    face_value: float,
    settlement_date: date,
    maturity_date: date,
    frequency: int = 2,
    day_count: str = "30/360",
) -> float:
    """Solve for yield given clean price. Delegates to compute_ytm.

    Computes the dirty price from clean + accrued, then uses Newton-Raphson.
    """
    if maturity_date <= settlement_date:
        return 0.0

    years_to_maturity = (maturity_date - settlement_date).days / 365.25

    if frequency <= 0:
        # Zero coupon
        return compute_ytm(clean_price, 0.0, face_value, years_to_maturity, 0)

    # For compute_ytm, we need the dirty price (full price).
    # First compute accrued interest with approximate YTM to get last coupon
    last_coupon = _find_last_coupon_date(settlement_date, maturity_date, frequency)
    accrued = compute_accrued_interest(
        coupon_rate, face_value, frequency, last_coupon, settlement_date, day_count
    )
    dirty_price = clean_price + accrued

    return compute_ytm(dirty_price, coupon_rate, face_value, years_to_maturity, frequency)


def compute_ytw_full(
    clean_price: float,
    coupon_rate: float,
    face_value: float,
    settlement_date: date,
    maturity_date: date,
    call_schedule: list[dict] | None = None,
    frequency: int = 2,
    day_count: str = "30/360",
) -> dict:
    """Compute yield-to-worst with full detail.

    Returns:
        {
            ytw: float,
            yield_to: str (MATURITY or CALL),
            exercise_date: date | None,
            ytm: float,
            call_yields: [{date, yield}] | None,
        }
    """
    # Compute yield to maturity
    ytm = yield_from_price(
        clean_price, coupon_rate, face_value,
        settlement_date, maturity_date, frequency, day_count,
    )

    if not call_schedule:
        return {
            "ytw": ytm,
            "yield_to": "MATURITY",
            "exercise_date": None,
            "ytm": ytm,
            "call_yields": None,
        }

    # Compute yield to each call date
    call_yields: list[dict] = []
    worst_yield = ytm
    worst_type = "MATURITY"
    worst_date = None

    for call in call_schedule:
        call_date = call.get("date") or call.get("call_date")
        call_price_val = call.get("call_price", face_value)

        if isinstance(call_date, str):
            call_date = date.fromisoformat(call_date)

        if call_date is None or call_date <= settlement_date:
            continue

        # For yield-to-call, the bond is redeemed at call_price on call_date
        years_to_call = (call_date - settlement_date).days / 365.25
        if years_to_call <= 0:
            continue

        # Compute accrued interest
        last_coupon = _find_last_coupon_date(settlement_date, call_date, frequency)
        accrued = compute_accrued_interest(
            coupon_rate, face_value, frequency, last_coupon, settlement_date, day_count,
        )
        dirty_price = clean_price + accrued

        ytc = compute_ytm(
            dirty_price, coupon_rate, float(call_price_val),
            years_to_call, frequency,
        )

        call_yields.append({
            "date": call_date,
            "yield": round(ytc, 8),
        })

        if ytc < worst_yield:
            worst_yield = ytc
            worst_type = "CALL"
            worst_date = call_date

    return {
        "ytw": round(worst_yield, 8),
        "yield_to": worst_type,
        "exercise_date": worst_date,
        "ytm": round(ytm, 8),
        "call_yields": call_yields if call_yields else None,
    }
