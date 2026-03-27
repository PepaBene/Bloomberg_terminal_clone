"""E15 Cross-Asset Divergence Signals Engine.

Detects divergences between equity and fixed income markets for the same issuer.
All functions are pure computation — no database access.
"""

from __future__ import annotations

import math


# Signal types
SIGNAL_TYPES = [
    "EQUITY_RALLY_BOND_DETERIORATION",
    "BOND_DISTRESS_BEFORE_EQUITY",
    "FALLEN_ANGEL_OVERHANG",
    "CHEAP_BONDS_CHEAP_EQUITY",
    "YIELD_CURVE_INVERSION_SIGNAL",
]


def detect_divergence_signals(
    equity_data: dict,
    bond_data: dict,
    rating_data: dict | None = None,
    curve_data: dict | None = None,
) -> list[dict]:
    """Detect cross-asset divergence signals.

    equity_data: {
        return_3m: float,       # 3-month equity return (decimal, e.g. 0.15 = 15%)
        return_6m: float,       # 6-month equity return
        pe_ratio: float | None,
        pe_percentile: float | None,   # vs own history (0-100)
        volatility: float | None,      # annualized equity vol (decimal, e.g. 0.25)
    }

    bond_data: {
        spread_bps: float,
        spread_change_3m_bps: float,  # positive = widening
        spread_percentile: float,     # vs own history (0-100)
        ytw: float | None,
    }

    rating_data: {
        rating_numeric: int | None,
        outlook: str | None,
        watch_status: str | None,
    }

    curve_data: {
        slope_2s10s: float | None,
        is_inverted: bool | None,
    }

    Returns list of {
        signal_type: str,
        description: str,
        severity: str (LOW, MEDIUM, HIGH),
        actionability: str (description of potential action),
        confidence: float (0-1),
    }
    """
    signals: list[dict] = []
    rating_data = rating_data or {}
    curve_data = curve_data or {}

    eq_return_3m = equity_data.get("return_3m", 0.0)
    eq_return_6m = equity_data.get("return_6m", 0.0)
    eq_pe_percentile = equity_data.get("pe_percentile")
    eq_volatility = equity_data.get("volatility")

    spread_bps = bond_data.get("spread_bps", 0.0)
    spread_change_3m = bond_data.get("spread_change_3m_bps", 0.0)
    spread_percentile = bond_data.get("spread_percentile", 50.0)

    rating_numeric = rating_data.get("rating_numeric")
    outlook = rating_data.get("outlook")
    watch_status = rating_data.get("watch_status")

    slope_2s10s = curve_data.get("slope_2s10s")
    is_inverted = curve_data.get("is_inverted")

    # ── Signal 1: EQUITY_RALLY_BOND_DETERIORATION ──────────────────────
    # Equity up >15% over 3-6 months BUT spreads widening >50bps
    eq_rallying = eq_return_3m > 0.15 or eq_return_6m > 0.15
    spreads_widening = spread_change_3m > 50.0
    if eq_rallying and spreads_widening:
        # Severity based on magnitude of divergence
        if spread_change_3m > 150.0:
            severity = "HIGH"
            confidence = 0.85
        elif spread_change_3m > 100.0:
            severity = "MEDIUM"
            confidence = 0.70
        else:
            severity = "LOW"
            confidence = 0.55

        signals.append({
            "signal_type": "EQUITY_RALLY_BOND_DETERIORATION",
            "description": (
                f"Equity rallied ({max(eq_return_3m, eq_return_6m)*100:.1f}% return) "
                f"while credit spreads widened by {spread_change_3m:.0f}bps. "
                "Bond market may be pricing in risks that equities have not yet reflected."
            ),
            "severity": severity,
            "actionability": (
                "Consider reducing equity exposure or hedging with credit protection. "
                "Bond market often leads equity in recognizing deterioration."
            ),
            "confidence": confidence,
        })

    # ── Signal 2: BOND_DISTRESS_BEFORE_EQUITY ─────────────────────────
    # Spreads >500bps or widened >200bps BUT equity hasn't repriced (return > -5%)
    bond_distressed = spread_bps > 500.0 or spread_change_3m > 200.0
    equity_not_repriced = eq_return_3m > -0.05
    if bond_distressed and equity_not_repriced:
        if spread_bps > 800.0:
            severity = "HIGH"
            confidence = 0.90
        elif spread_bps > 500.0:
            severity = "HIGH"
            confidence = 0.80
        else:
            severity = "MEDIUM"
            confidence = 0.70

        signals.append({
            "signal_type": "BOND_DISTRESS_BEFORE_EQUITY",
            "description": (
                f"Credit spreads at {spread_bps:.0f}bps (change: +{spread_change_3m:.0f}bps) "
                f"signal distress, but equity returned {eq_return_3m*100:+.1f}% over 3 months. "
                "Historically, equity tends to catch down to credit signals."
            ),
            "severity": severity,
            "actionability": (
                "Credit markets are pricing significant default risk. "
                "Equity may be next to reprice. Consider selling equity or buying puts."
            ),
            "confidence": confidence,
        })

    # ── Signal 3: FALLEN_ANGEL_OVERHANG ────────────────────────────────
    # BBB rating (numeric 8-10) + negative outlook/watch + equity vol elevated (>30%)
    is_bbb = rating_numeric is not None and 8 <= rating_numeric <= 10
    negative_credit = (
        (outlook is not None and outlook.upper() == "NEGATIVE")
        or (watch_status is not None and watch_status.upper() == "WATCH_NEGATIVE")
    )
    vol_elevated = eq_volatility is not None and eq_volatility > 0.30
    if is_bbb and negative_credit and vol_elevated:
        if watch_status and watch_status.upper() == "WATCH_NEGATIVE":
            severity = "HIGH"
            confidence = 0.80
        else:
            severity = "MEDIUM"
            confidence = 0.65

        signals.append({
            "signal_type": "FALLEN_ANGEL_OVERHANG",
            "description": (
                f"BBB-rated issuer (numeric {rating_numeric}) with negative credit outlook "
                f"and elevated equity volatility ({eq_volatility*100:.0f}%). "
                "Fallen angel risk creates forced selling pressure from IG mandates."
            ),
            "severity": severity,
            "actionability": (
                "Monitor for rating downgrade. If downgrade occurs, IG-mandated holders "
                "will be forced sellers, creating technical pressure. Position accordingly."
            ),
            "confidence": confidence,
        })

    # ── Signal 4: CHEAP_BONDS_CHEAP_EQUITY ─────────────────────────────
    # Both PE below 25th percentile AND spread above 75th percentile
    pe_cheap = eq_pe_percentile is not None and eq_pe_percentile < 25.0
    spread_wide = spread_percentile > 75.0
    if pe_cheap and spread_wide:
        if eq_pe_percentile < 10.0 and spread_percentile > 90.0:
            severity = "HIGH"
            confidence = 0.75
        else:
            severity = "MEDIUM"
            confidence = 0.60

        signals.append({
            "signal_type": "CHEAP_BONDS_CHEAP_EQUITY",
            "description": (
                f"Both equity (PE at {eq_pe_percentile:.0f}th percentile) and bonds "
                f"(spread at {spread_percentile:.0f}th percentile, i.e. wide) are cheap. "
                "Potential deep value opportunity if fundamental thesis intact."
            ),
            "severity": severity,
            "actionability": (
                "Both debt and equity are attractively priced. "
                "Consider adding exposure in both if credit quality is stable and "
                "the cheapness is driven by sentiment rather than fundamentals."
            ),
            "confidence": confidence,
        })

    # ── Signal 5: YIELD_CURVE_INVERSION_SIGNAL ─────────────────────────
    # Curve inverted + spreads widening > 30bps over 3m
    curve_inverted = is_inverted is True or (slope_2s10s is not None and slope_2s10s < 0)
    spreads_widening_moderate = spread_change_3m > 30.0
    if curve_inverted and spreads_widening_moderate:
        if spread_change_3m > 100.0:
            severity = "HIGH"
            confidence = 0.75
        elif spread_change_3m > 60.0:
            severity = "MEDIUM"
            confidence = 0.60
        else:
            severity = "LOW"
            confidence = 0.50

        signals.append({
            "signal_type": "YIELD_CURVE_INVERSION_SIGNAL",
            "description": (
                f"Yield curve inverted (2s10s slope: {slope_2s10s*100:.0f}bps) "
                f"with credit spreads widening {spread_change_3m:.0f}bps. "
                "Combination historically precedes economic contraction."
            ) if slope_2s10s is not None else (
                f"Inverted yield curve with credit spreads widening {spread_change_3m:.0f}bps. "
                "Combination historically precedes economic contraction."
            ),
            "severity": severity,
            "actionability": (
                "Recessionary signal. Consider shortening credit duration, "
                "upgrading quality (move up in capital structure), and reducing "
                "cyclical exposure."
            ),
            "confidence": confidence,
        })

    return signals


def compute_cross_asset_regime(
    equity_vol: float,        # annualized equity volatility (decimal, e.g. 0.20)
    credit_spread: float,     # credit spread in bps
    rate_level: float,        # 10Y yield (decimal, e.g. 0.045)
    curve_slope: float,       # 2s10s spread (decimal, e.g. -0.005 for inverted)
) -> dict:
    """Classify the current cross-asset regime.

    RISK_ON: low vol (<15%), tight spreads (<200bps), positive slope
    RISK_OFF: high vol (>25%), wide spreads (>400bps), inverted curve
    TRANSITION: mixed signals
    STRESS: very high vol (>35%), very wide spreads (>600bps)

    Returns {regime: str, confidence: float, factors: {vol_signal, credit_signal, rate_signal, curve_signal}}
    """
    # Classify individual factors
    # Volatility signal
    if equity_vol > 0.35:
        vol_signal = "STRESS"
        vol_score = 3
    elif equity_vol > 0.25:
        vol_signal = "RISK_OFF"
        vol_score = 2
    elif equity_vol > 0.15:
        vol_signal = "NEUTRAL"
        vol_score = 1
    else:
        vol_signal = "RISK_ON"
        vol_score = 0

    # Credit signal
    if credit_spread > 600:
        credit_signal = "STRESS"
        credit_score = 3
    elif credit_spread > 400:
        credit_signal = "RISK_OFF"
        credit_score = 2
    elif credit_spread > 200:
        credit_signal = "NEUTRAL"
        credit_score = 1
    else:
        credit_signal = "RISK_ON"
        credit_score = 0

    # Rate signal — high rates are mildly risk-off
    if rate_level > 0.06:
        rate_signal = "RESTRICTIVE"
        rate_score = 2
    elif rate_level > 0.04:
        rate_signal = "NEUTRAL"
        rate_score = 1
    elif rate_level > 0.02:
        rate_signal = "ACCOMMODATIVE"
        rate_score = 0
    else:
        rate_signal = "VERY_ACCOMMODATIVE"
        rate_score = 0

    # Curve signal
    if curve_slope < -0.005:
        curve_signal = "INVERTED"
        curve_score = 2
    elif curve_slope < 0.005:
        curve_signal = "FLAT"
        curve_score = 1
    else:
        curve_signal = "NORMAL"
        curve_score = 0

    # Determine composite regime
    avg_score = (vol_score + credit_score + rate_score + curve_score) / 4.0

    if vol_score >= 3 or credit_score >= 3:
        # Any single factor at STRESS overrides
        regime = "STRESS"
        confidence = 0.85
    elif avg_score >= 2.0:
        regime = "RISK_OFF"
        confidence = 0.75
    elif avg_score <= 0.5:
        regime = "RISK_ON"
        confidence = 0.75
    else:
        regime = "TRANSITION"
        confidence = 0.55

    # Boost confidence if signals agree
    scores = [vol_score, credit_score, rate_score, curve_score]
    if all(s <= 1 for s in scores):
        confidence = min(confidence + 0.10, 0.95)
    elif all(s >= 2 for s in scores):
        confidence = min(confidence + 0.10, 0.95)

    return {
        "regime": regime,
        "confidence": round(confidence, 2),
        "factors": {
            "vol_signal": vol_signal,
            "credit_signal": credit_signal,
            "rate_signal": rate_signal,
            "curve_signal": curve_signal,
        },
    }


def compute_equity_exposure_adjustment(
    regime: str,
    signals: list[dict],
    current_equity_weight: float = 0.60,
) -> dict:
    """Suggest equity exposure adjustment based on credit signals.

    Returns {
        suggested_weight: float,
        adjustment_pct: float (negative = reduce),
        reason: str,
        confidence: float,
    }
    """
    adjustment = 0.0
    reasons: list[str] = []
    confidence = 0.50

    # Regime-based adjustment
    if regime == "STRESS":
        adjustment -= 0.15
        reasons.append("STRESS regime: significant de-risking warranted")
        confidence = 0.80
    elif regime == "RISK_OFF":
        adjustment -= 0.08
        reasons.append("RISK_OFF regime: moderate de-risking suggested")
        confidence = 0.70
    elif regime == "RISK_ON":
        adjustment += 0.05
        reasons.append("RISK_ON regime: conditions support equity exposure")
        confidence = 0.65
    else:
        # TRANSITION — no regime adjustment, rely on signals
        reasons.append("TRANSITION regime: mixed signals, relying on specific indicators")
        confidence = 0.55

    # Signal-based adjustments
    for signal in signals:
        sig_type = signal.get("signal_type", "")
        severity = signal.get("severity", "LOW")

        if sig_type == "BOND_DISTRESS_BEFORE_EQUITY":
            if severity == "HIGH":
                adjustment -= 0.10
            elif severity == "MEDIUM":
                adjustment -= 0.05
            reasons.append(f"Bond distress signal ({severity}): reduce equity")

        elif sig_type == "EQUITY_RALLY_BOND_DETERIORATION":
            if severity == "HIGH":
                adjustment -= 0.07
            elif severity == "MEDIUM":
                adjustment -= 0.04
            reasons.append(f"Equity/bond divergence ({severity}): caution on equity")

        elif sig_type == "FALLEN_ANGEL_OVERHANG":
            if severity == "HIGH":
                adjustment -= 0.05
            elif severity == "MEDIUM":
                adjustment -= 0.03
            reasons.append(f"Fallen angel risk ({severity}): reduce exposure")

        elif sig_type == "CHEAP_BONDS_CHEAP_EQUITY":
            if severity == "HIGH":
                adjustment += 0.05
            elif severity == "MEDIUM":
                adjustment += 0.03
            reasons.append(f"Cheap assets signal ({severity}): potential value opportunity")

        elif sig_type == "YIELD_CURVE_INVERSION_SIGNAL":
            if severity == "HIGH":
                adjustment -= 0.06
            elif severity == "MEDIUM":
                adjustment -= 0.03
            reasons.append(f"Curve inversion ({severity}): defensive positioning")

    # Clamp the suggested weight to [0.10, 0.90]
    suggested = max(0.10, min(0.90, current_equity_weight + adjustment))
    actual_adjustment = suggested - current_equity_weight

    reason_text = "; ".join(reasons) if reasons else "No specific signals detected"

    return {
        "suggested_weight": round(suggested, 4),
        "adjustment_pct": round(actual_adjustment, 4),
        "reason": reason_text,
        "confidence": round(confidence, 2),
    }
