"""Pillar 3 Phase 3C — Part 16: Cross-Asset Signal Narrative Engine.

Pure computation engine for generating cross-asset divergence narratives,
detecting fallen angel overhang, cheap-on-both-sides signals, and
bond-equity comparisons.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations


# ── Divergence Narrative ──────────────────────────────────────────────────


def generate_divergence_narrative(
    signal_type: str,
    entity_name: str,
    equity_return: float,
    spread_change: float,
    sector: str | None = None,
) -> str:
    """Generate a human-readable narrative for a cross-asset divergence signal.

    Parameters
    ----------
    signal_type : str
        E.g. EQUITY_LEADS_CREDIT, CREDIT_LEADS_EQUITY, SIMULTANEOUS_STRESS.
    entity_name : str
        Company or issuer name.
    equity_return : float
        Equity return percentage (positive = up).
    spread_change : float
        Credit spread change in bps (positive = widening).
    sector : str | None
        GICS sector name for context.

    Returns
    -------
    str
        Narrative paragraph describing the divergence.
    """
    sector_ctx = f" ({sector})" if sector else ""

    if signal_type == "EQUITY_LEADS_CREDIT":
        direction = "declined" if equity_return < 0 else "rallied"
        spread_dir = "tightened" if spread_change < 0 else "widened"
        narrative = (
            f"{entity_name}{sector_ctx} equity {direction} {abs(equity_return):.1f}% "
            f"while credit spreads {spread_dir} {abs(spread_change):.0f}bps. "
            f"Equity is leading credit — historically, credit follows within 1-3 months. "
            f"Monitor for spread adjustment."
        )
    elif signal_type == "CREDIT_LEADS_EQUITY":
        spread_dir = "widened" if spread_change > 0 else "tightened"
        equity_dir = "has not yet reacted" if abs(equity_return) < 2 else (
            f"moved only {abs(equity_return):.1f}%"
        )
        narrative = (
            f"{entity_name}{sector_ctx} credit spreads {spread_dir} {abs(spread_change):.0f}bps "
            f"but equity {equity_dir}. "
            f"Credit markets often lead equity — watch for equity repricing."
        )
    elif signal_type == "SIMULTANEOUS_STRESS":
        narrative = (
            f"{entity_name}{sector_ctx} is under simultaneous stress: "
            f"equity down {abs(equity_return):.1f}% and spreads widened {abs(spread_change):.0f}bps. "
            f"Both markets signal deterioration — elevated default/restructuring risk."
        )
    else:
        narrative = (
            f"{entity_name}{sector_ctx}: equity moved {equity_return:+.1f}% "
            f"and spreads changed {spread_change:+.0f}bps. Signal type: {signal_type}."
        )

    return narrative


# ── Fallen Angel Overhang ─────────────────────────────────────────────────


def detect_fallen_angel_overhang(
    rating: str,
    momentum: str,
    ig_holders_pct: float | None = None,
) -> dict | None:
    """Detect fallen angel overhang risk for a BBB-rated issuer.

    A fallen angel is an issuer downgraded from investment grade to high yield.
    Overhang occurs when a BBB issuer with deteriorating credit momentum has
    a high percentage of IG-only holders who would be forced sellers.

    Parameters
    ----------
    rating : str
        Current credit rating (e.g. "BBB", "BBB-").
    momentum : str
        Credit momentum: IMPROVING, STABLE, DETERIORATING.
    ig_holders_pct : float | None
        Percentage of bondholders restricted to IG-only mandates.

    Returns
    -------
    dict | None
        {risk_level, forced_selling_pct, narrative} or None if no risk.
    """
    bbb_ratings = {"BBB+", "BBB", "BBB-"}
    if rating not in bbb_ratings:
        return None
    if momentum != "DETERIORATING":
        return None

    forced_selling = ig_holders_pct if ig_holders_pct is not None else 0.0

    if rating == "BBB-" and forced_selling >= 50:
        risk_level = "HIGH"
    elif rating == "BBB-" and forced_selling >= 30:
        risk_level = "MEDIUM"
    elif rating in ("BBB", "BBB+") and momentum == "DETERIORATING":
        risk_level = "LOW"
    else:
        risk_level = "LOW"

    narrative = (
        f"Fallen angel overhang risk: {rating} rated with {momentum} momentum. "
        f"Estimated {forced_selling:.0f}% of holders are IG-only mandates. "
        f"Downgrade to HY could trigger forced selling."
    )

    return {
        "risk_level": risk_level,
        "forced_selling_pct": forced_selling,
        "narrative": narrative,
    }


# ── Cheap-on-Both-Sides Signal ───────────────────────────────────────────


def detect_cheap_both_signal(
    pe: float | None = None,
    fcf_yield: float | None = None,
    spread_percentile: float | None = None,
    z_score: float | None = None,
) -> dict | None:
    """Detect issuers that appear cheap on both equity and credit metrics.

    Parameters
    ----------
    pe : float | None
        Price-to-earnings ratio.
    fcf_yield : float | None
        Free cash flow yield (percentage).
    spread_percentile : float | None
        Current spread percentile vs 1-year history (0-100).
    z_score : float | None
        Altman Z-score.

    Returns
    -------
    dict | None
        {equity_cheap, credit_cheap, combined_signal, supporting_metrics}
        or None if data is insufficient.
    """
    equity_cheap = False
    credit_cheap = False
    supporting: list[str] = []

    # Equity cheapness
    if pe is not None and 0 < pe < 12:
        equity_cheap = True
        supporting.append(f"P/E of {pe:.1f} below 12x threshold")
    if fcf_yield is not None and fcf_yield > 8.0:
        equity_cheap = True
        supporting.append(f"FCF yield of {fcf_yield:.1f}% above 8% threshold")

    # Credit cheapness (wide spreads = cheap credit)
    if spread_percentile is not None and spread_percentile >= 75:
        credit_cheap = True
        supporting.append(f"Spread at {spread_percentile:.0f}th percentile (wide)")

    # Safety check
    if z_score is not None and z_score < 1.8:
        # Distress zone — not a cheap signal, it's risky
        return {
            "equity_cheap": equity_cheap,
            "credit_cheap": credit_cheap,
            "combined_signal": False,
            "supporting_metrics": supporting + [f"Z-score {z_score:.2f} in distress zone — caution"],
        }

    if not equity_cheap and not credit_cheap:
        return None

    return {
        "equity_cheap": equity_cheap,
        "credit_cheap": credit_cheap,
        "combined_signal": equity_cheap and credit_cheap,
        "supporting_metrics": supporting,
    }


# ── Bond-Equity Comparison ───────────────────────────────────────────────


def generate_bond_equity_comparison(entity_data: dict) -> str:
    """Generate a narrative comparing bond and equity investment theses.

    Parameters
    ----------
    entity_data : dict
        Keys: entity_name, equity_yield_pct (earnings or dividend yield),
              bond_yield_pct, spread_bps, credit_rating, equity_beta,
              leverage_ratio.

    Returns
    -------
    str
        Narrative comparing the two investment approaches.
    """
    name = entity_data.get("entity_name", "Unknown")
    eq_yield = entity_data.get("equity_yield_pct")
    bond_yield = entity_data.get("bond_yield_pct")
    spread = entity_data.get("spread_bps")
    rating = entity_data.get("credit_rating", "NR")
    beta = entity_data.get("equity_beta")
    leverage = entity_data.get("leverage_ratio")

    parts: list[str] = [f"{name} cross-asset view:"]

    if eq_yield is not None and bond_yield is not None:
        gap = round(eq_yield - bond_yield, 2)
        if gap > 2:
            parts.append(
                f"Equity yield ({eq_yield:.1f}%) significantly exceeds bond yield "
                f"({bond_yield:.1f}%) by {gap:.1f}pp — equity appears relatively cheap"
            )
        elif gap < -2:
            parts.append(
                f"Bond yield ({bond_yield:.1f}%) exceeds equity yield "
                f"({eq_yield:.1f}%) by {abs(gap):.1f}pp — bonds may offer better risk-adjusted return"
            )
        else:
            parts.append(
                f"Equity yield ({eq_yield:.1f}%) and bond yield ({bond_yield:.1f}%) "
                f"are similar — choice depends on risk preference"
            )

    if spread is not None:
        parts.append(f"Credit spread: {spread:.0f}bps ({rating})")

    if leverage is not None:
        if leverage > 4.0:
            parts.append(f"High leverage ({leverage:.1f}x) favors bond seniority")
        elif leverage < 2.0:
            parts.append(f"Low leverage ({leverage:.1f}x) supports equity upside")

    if beta is not None:
        if beta > 1.3:
            parts.append(f"High beta ({beta:.2f}) — bonds provide downside protection")
        elif beta < 0.7:
            parts.append(f"Low beta ({beta:.2f}) — equity behaves bond-like")

    return ". ".join(parts) + "."


# ── Signal Severity Classification ───────────────────────────────────────


def classify_signal_severity(
    signal_type: str, spread_magnitude: float, equity_magnitude: float
) -> str:
    """Classify the severity of a cross-asset divergence signal.

    Parameters
    ----------
    signal_type : str
        Type of signal (e.g. SIMULTANEOUS_STRESS).
    spread_magnitude : float
        Absolute spread change in bps.
    equity_magnitude : float
        Absolute equity return percentage.

    Returns
    -------
    str
        CRITICAL, HIGH, MEDIUM, or LOW.
    """
    if signal_type == "SIMULTANEOUS_STRESS":
        if spread_magnitude > 100 or equity_magnitude > 10:
            return "CRITICAL"
        if spread_magnitude > 50 or equity_magnitude > 5:
            return "HIGH"
        return "MEDIUM"

    # Divergence signals
    combined = spread_magnitude + equity_magnitude * 10  # normalize
    if combined > 200:
        return "CRITICAL"
    if combined > 100:
        return "HIGH"
    if combined > 50:
        return "MEDIUM"
    return "LOW"


# ── Historical Divergence Outcomes ───────────────────────────────────────


def compute_historical_divergence_outcome(
    signal_type: str, sector: str | None = None
) -> dict:
    """Return stylized historical outcome statistics for divergence signals.

    This provides base-rate guidance for how divergence signals have
    historically resolved. Values are representative of academic research
    on credit-equity lead/lag relationships.

    Parameters
    ----------
    signal_type : str
        Type of divergence signal.
    sector : str | None
        GICS sector for sector-specific adjustments.

    Returns
    -------
    dict
        {equity_followed_credit_pct, avg_lag_months, sample_size}
    """
    # Base rates from stylized research
    base_rates = {
        "CREDIT_LEADS_EQUITY": {
            "equity_followed_credit_pct": 68.0,
            "avg_lag_months": 2.5,
            "sample_size": 450,
        },
        "EQUITY_LEADS_CREDIT": {
            "equity_followed_credit_pct": 55.0,
            "avg_lag_months": 1.8,
            "sample_size": 380,
        },
        "SIMULTANEOUS_STRESS": {
            "equity_followed_credit_pct": 82.0,
            "avg_lag_months": 0.5,
            "sample_size": 120,
        },
    }

    result = base_rates.get(signal_type, {
        "equity_followed_credit_pct": 50.0,
        "avg_lag_months": 3.0,
        "sample_size": 100,
    }).copy()

    # Sector adjustments
    if sector == "Financials":
        result["equity_followed_credit_pct"] = min(
            100.0, result["equity_followed_credit_pct"] + 5.0
        )
        result["avg_lag_months"] = max(0.5, result["avg_lag_months"] - 0.5)
    elif sector == "Energy":
        result["equity_followed_credit_pct"] = min(
            100.0, result["equity_followed_credit_pct"] + 3.0
        )

    return result
