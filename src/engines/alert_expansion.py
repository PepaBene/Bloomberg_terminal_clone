"""Pillar 3 Phase 3C — Part 17: Alert Expansion Engine.

Pure computation engine for FI alerts, quality score alerts, and
institutional flow alerts. Covers rating changes, spread thresholds,
curve inversions, regime changes, Piotroski/Altman/Beneish score alerts,
and whale/activist/cluster flow detection.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations


# ── Alert Type Definitions ────────────────────────────────────────────────

FI_ALERT_TYPES: dict[str, dict] = {
    "RATING_UPGRADE": {"severity": "HIGH", "description": "Credit rating upgrade"},
    "RATING_DOWNGRADE": {"severity": "HIGH", "description": "Credit rating downgrade"},
    "FALLEN_ANGEL": {"severity": "CRITICAL", "description": "Downgrade from IG to HY (fallen angel)"},
    "RISING_STAR": {"severity": "HIGH", "description": "Upgrade from HY to IG (rising star)"},
    "SPREAD_WIDENING": {"severity": "MEDIUM", "description": "Significant credit spread widening"},
    "SPREAD_TIGHTENING": {"severity": "LOW", "description": "Notable credit spread tightening"},
    "DISTRESS_THRESHOLD": {"severity": "CRITICAL", "description": "Spread exceeds distress threshold"},
    "CURVE_INVERSION": {"severity": "HIGH", "description": "Yield curve inversion detected"},
    "CURVE_STEEPENING": {"severity": "MEDIUM", "description": "Significant curve steepening"},
    "REGIME_CHANGE": {"severity": "HIGH", "description": "Credit regime transition"},
    "NEW_ISSUE_LARGE": {"severity": "MEDIUM", "description": "Large new bond issuance"},
    "MATURITY_WALL": {"severity": "HIGH", "description": "Significant near-term maturities"},
    "COVENANT_BREACH": {"severity": "CRITICAL", "description": "Potential covenant breach detected"},
}

QUALITY_ALERT_TYPES: dict[str, dict] = {
    "PIOTROSKI_CHANGE": {"severity": "HIGH", "description": "Significant Piotroski F-Score change"},
    "ALTMAN_ZONE_CHANGE": {"severity": "HIGH", "description": "Altman Z-Score zone transition"},
    "BENEISH_FLAG": {"severity": "CRITICAL", "description": "Beneish M-Score exceeds manipulation threshold"},
    "VALUE_TRAP": {"severity": "HIGH", "description": "Value trap signal detected"},
    "GOVERNANCE_DETERIORATION": {"severity": "MEDIUM", "description": "Governance score deterioration"},
}

FLOW_ALERT_TYPES: dict[str, dict] = {
    "WHALE_MOVE": {"severity": "HIGH", "description": "Large institutional position change (>$100M)"},
    "ACTIVIST_13D": {"severity": "CRITICAL", "description": "Activist investor 13D filing"},
    "CLUSTER_BUY": {"severity": "HIGH", "description": "Cluster of institutional buying"},
    "CLUSTER_SELL": {"severity": "HIGH", "description": "Cluster of institutional selling"},
    "SHORT_SPIKE": {"severity": "HIGH", "description": "Significant short interest increase"},
    "INSIDER_CLUSTER": {"severity": "MEDIUM", "description": "Cluster of insider transactions"},
}

# IG ratings for fallen angel / rising star detection
_IG_RATINGS = {"AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-"}
_HY_RATINGS = {"BB+", "BB", "BB-", "B+", "B", "B-", "CCC+", "CCC", "CCC-", "CC", "C", "D"}


# ── FI Alert Checks ──────────────────────────────────────────────────────


def check_rating_change(current_rating: str, prior_rating: str) -> dict | None:
    """Check for credit rating change.

    Returns
    -------
    dict | None
        Alert dict with {alert_type, severity, detail} or None.
    """
    if current_rating == prior_rating:
        return None

    # Determine direction
    all_ratings = [
        "AAA", "AA+", "AA", "AA-", "A+", "A", "A-",
        "BBB+", "BBB", "BBB-", "BB+", "BB", "BB-",
        "B+", "B", "B-", "CCC+", "CCC", "CCC-", "CC", "C", "D",
    ]

    cur_idx = all_ratings.index(current_rating) if current_rating in all_ratings else -1
    pri_idx = all_ratings.index(prior_rating) if prior_rating in all_ratings else -1

    if cur_idx < 0 or pri_idx < 0:
        return None

    # Check for fallen angel / rising star
    if prior_rating in _IG_RATINGS and current_rating in _HY_RATINGS:
        return {
            "alert_type": "FALLEN_ANGEL",
            "severity": "CRITICAL",
            "detail": f"Downgraded from {prior_rating} (IG) to {current_rating} (HY) — fallen angel",
        }
    if prior_rating in _HY_RATINGS and current_rating in _IG_RATINGS:
        return {
            "alert_type": "RISING_STAR",
            "severity": "HIGH",
            "detail": f"Upgraded from {prior_rating} (HY) to {current_rating} (IG) — rising star",
        }

    if cur_idx < pri_idx:
        # Lower index = higher rating → upgrade
        return {
            "alert_type": "RATING_UPGRADE",
            "severity": "HIGH",
            "detail": f"Upgraded from {prior_rating} to {current_rating}",
        }
    else:
        return {
            "alert_type": "RATING_DOWNGRADE",
            "severity": "HIGH",
            "detail": f"Downgraded from {prior_rating} to {current_rating}",
        }


def check_fallen_angel(current_rating: str, momentum: str) -> dict | None:
    """Check for fallen angel risk (BBB- with deteriorating momentum).

    Returns
    -------
    dict | None
        Alert dict or None.
    """
    LOWEST_IG_RATINGS = {"BBB-", "Baa3"}
    if current_rating not in LOWEST_IG_RATINGS or momentum != "DETERIORATING":
        return None

    return {
        "alert_type": "FALLEN_ANGEL",
        "severity": "CRITICAL",
        "detail": f"{current_rating} rated with DETERIORATING momentum — fallen angel risk elevated",
    }


def check_spread_widening(
    spread_change_bps: float, threshold: float = 20.0
) -> dict | None:
    """Check for significant spread widening.

    Returns
    -------
    dict | None
        Alert dict or None.
    """
    if spread_change_bps < threshold:
        return None

    return {
        "alert_type": "SPREAD_WIDENING",
        "severity": "MEDIUM" if spread_change_bps < 50 else "HIGH",
        "detail": f"Spread widened {spread_change_bps:.0f}bps (threshold: {threshold:.0f}bps)",
    }


def check_distress_threshold(
    spread_bps: float, threshold: float = 500.0
) -> dict | None:
    """Check if spread exceeds distress threshold.

    Returns
    -------
    dict | None
        Alert dict or None.
    """
    if spread_bps < threshold:
        return None

    return {
        "alert_type": "DISTRESS_THRESHOLD",
        "severity": "CRITICAL",
        "detail": f"Spread at {spread_bps:.0f}bps exceeds distress threshold of {threshold:.0f}bps",
    }


def check_curve_inversion(spread_2s10s: float, prior: float) -> dict | None:
    """Check if yield curve crossed zero (inversion/un-inversion).

    Returns
    -------
    dict | None
        Alert dict or None.
    """
    if prior >= 0 and spread_2s10s < 0:
        return {
            "alert_type": "CURVE_INVERSION",
            "severity": "HIGH",
            "detail": f"Yield curve inverted: 2s10s moved from {prior:.0f}bps to {spread_2s10s:.0f}bps",
        }
    if prior < 0 and spread_2s10s >= 0:
        return {
            "alert_type": "CURVE_STEEPENING",
            "severity": "MEDIUM",
            "detail": f"Yield curve un-inverted: 2s10s moved from {prior:.0f}bps to {spread_2s10s:.0f}bps",
        }
    return None


def check_regime_change(current_regime: str, prior_regime: str) -> dict | None:
    """Check for credit regime transition.

    Returns
    -------
    dict | None
        Alert dict or None.
    """
    if current_regime == prior_regime:
        return None

    severity_map = {
        "STRESS": "CRITICAL",
        "RISK_OFF": "HIGH",
        "NORMAL": "MEDIUM",
        "RISK_ON": "LOW",
    }

    severity = severity_map.get(current_regime, "MEDIUM")

    return {
        "alert_type": "REGIME_CHANGE",
        "severity": severity,
        "detail": f"Credit regime changed from {prior_regime} to {current_regime}",
    }


def evaluate_fi_alerts(
    entity_data: dict, fi_config: dict | None = None
) -> list[dict]:
    """Run all FI alert checks against entity data.

    Parameters
    ----------
    entity_data : dict
        Keys: current_rating, prior_rating, momentum, spread_change_bps,
              spread_bps, spread_2s10s, prior_2s10s, current_regime,
              prior_regime.
    fi_config : dict | None
        User alert configuration: {spread_threshold, distress_threshold}.

    Returns
    -------
    list[dict]
        List of triggered alerts.
    """
    alerts: list[dict] = []

    # Rating change
    current_rating = entity_data.get("current_rating", "")
    prior_rating = entity_data.get("prior_rating", "")
    if current_rating and prior_rating:
        alert = check_rating_change(current_rating, prior_rating)
        if alert:
            alerts.append(alert)

    # Fallen angel risk
    momentum = entity_data.get("momentum", "")
    if current_rating and momentum:
        alert = check_fallen_angel(current_rating, momentum)
        if alert:
            # Avoid duplicate if already triggered by rating change
            existing_types = {a["alert_type"] for a in alerts}
            if "FALLEN_ANGEL" not in existing_types:
                alerts.append(alert)

    # Spread widening
    spread_change = entity_data.get("spread_change_bps")
    if spread_change is not None:
        threshold = 20.0
        if fi_config:
            threshold = fi_config.get("spread_threshold", 20.0)
        alert = check_spread_widening(spread_change, threshold)
        if alert:
            alerts.append(alert)

    # Distress threshold
    spread_bps = entity_data.get("spread_bps")
    if spread_bps is not None:
        dist_threshold = 500.0
        if fi_config:
            dist_threshold = fi_config.get("distress_threshold", 500.0)
        alert = check_distress_threshold(spread_bps, dist_threshold)
        if alert:
            alerts.append(alert)

    # Curve inversion
    s2s10s = entity_data.get("spread_2s10s")
    prior_2s10s = entity_data.get("prior_2s10s")
    if s2s10s is not None and prior_2s10s is not None:
        alert = check_curve_inversion(s2s10s, prior_2s10s)
        if alert:
            alerts.append(alert)

    # Regime change
    current_regime = entity_data.get("current_regime", "")
    prior_regime = entity_data.get("prior_regime", "")
    if current_regime and prior_regime:
        alert = check_regime_change(current_regime, prior_regime)
        if alert:
            alerts.append(alert)

    return alerts


# ── Quality Alert Checks ─────────────────────────────────────────────────


def check_score_change(
    current: float, prior: float, score_name: str, threshold: float
) -> dict | None:
    """Check if a score changed by more than the threshold.

    Parameters
    ----------
    current : float
        Current score value.
    prior : float
        Prior score value.
    score_name : str
        Name of the score for the alert detail.
    threshold : float
        Minimum absolute change to trigger alert.

    Returns
    -------
    dict | None
        Alert dict or None.
    """
    change = current - prior
    if abs(change) < threshold:
        return None

    direction = "increased" if change > 0 else "decreased"
    return {
        "alert_type": f"{score_name.upper()}_CHANGE",
        "severity": "HIGH",
        "detail": f"{score_name} {direction} by {abs(change):.1f} (from {prior:.1f} to {current:.1f})",
    }


def evaluate_quality_alerts(
    scores_current: dict, scores_prior: dict
) -> list[dict]:
    """Evaluate quality-related alerts across Piotroski, Altman, Beneish.

    Parameters
    ----------
    scores_current : dict
        {piotroski, altman_z, beneish_m, governance_score}.
    scores_prior : dict
        Previous period values with same keys.

    Returns
    -------
    list[dict]
        Triggered alerts.
    """
    alerts: list[dict] = []

    # Piotroski F-Score (0-9): >=3 point change is significant
    piotroski_cur = scores_current.get("piotroski")
    piotroski_pri = scores_prior.get("piotroski")
    if piotroski_cur is not None and piotroski_pri is not None:
        alert = check_score_change(piotroski_cur, piotroski_pri, "PIOTROSKI", 3.0)
        if alert:
            alerts.append(alert)

    # Altman Z-Score zone transitions
    altman_cur = scores_current.get("altman_z")
    altman_pri = scores_prior.get("altman_z")
    if altman_cur is not None and altman_pri is not None:
        cur_zone = _altman_zone(altman_cur)
        pri_zone = _altman_zone(altman_pri)
        if cur_zone != pri_zone:
            alerts.append({
                "alert_type": "ALTMAN_ZONE_CHANGE",
                "severity": "CRITICAL" if cur_zone == "DISTRESS" else "HIGH",
                "detail": (
                    f"Altman Z-Score moved from {pri_zone} zone ({altman_pri:.2f}) "
                    f"to {cur_zone} zone ({altman_cur:.2f})"
                ),
            })

    # Beneish M-Score: exceeds -1.78 → manipulation flag
    beneish_cur = scores_current.get("beneish_m")
    if beneish_cur is not None and beneish_cur > -1.78:
        alerts.append({
            "alert_type": "BENEISH_FLAG",
            "severity": "CRITICAL",
            "detail": f"Beneish M-Score of {beneish_cur:.2f} exceeds -1.78 threshold — potential earnings manipulation",
        })

    # Governance score deterioration
    gov_cur = scores_current.get("governance_score")
    gov_pri = scores_prior.get("governance_score")
    if gov_cur is not None and gov_pri is not None:
        change = gov_cur - gov_pri
        if change < -10:
            alerts.append({
                "alert_type": "GOVERNANCE_DETERIORATION",
                "severity": "MEDIUM",
                "detail": f"Governance score declined {abs(change):.0f} points (from {gov_pri:.0f} to {gov_cur:.0f})",
            })

    return alerts


def _altman_zone(z: float) -> str:
    """Classify Altman Z-Score into zones."""
    if z > 2.99:
        return "SAFE"
    if z > 1.81:
        return "GREY"
    return "DISTRESS"


# ── Flow Alert Checks ────────────────────────────────────────────────────


def evaluate_flow_alerts(flow_data: dict) -> list[dict]:
    """Evaluate institutional flow alerts.

    Parameters
    ----------
    flow_data : dict
        Keys: whale_moves (list[dict]), activist_filings (list[dict]),
              cluster_buys (int), cluster_sells (int),
              short_interest_change_pct (float),
              insider_transactions (list[dict]).

    Returns
    -------
    list[dict]
        Triggered alerts.
    """
    alerts: list[dict] = []

    # Whale moves (>$100M position changes)
    for whale in flow_data.get("whale_moves", []):
        size_mm = whale.get("size_mm", 0.0)
        if size_mm >= 100:
            direction = whale.get("direction", "unknown")
            institution = whale.get("institution", "Unknown")
            alerts.append({
                "alert_type": "WHALE_MOVE",
                "severity": "HIGH",
                "detail": f"{institution} {direction} ${size_mm:.0f}M position",
            })

    # Activist 13D filings
    for filing in flow_data.get("activist_filings", []):
        activist = filing.get("activist", "Unknown")
        stake_pct = filing.get("stake_pct", 0.0)
        alerts.append({
            "alert_type": "ACTIVIST_13D",
            "severity": "CRITICAL",
            "detail": f"{activist} filed 13D with {stake_pct:.1f}% stake",
        })

    # Cluster buy/sell
    cluster_buys = flow_data.get("cluster_buys", 0)
    if cluster_buys >= 3:
        alerts.append({
            "alert_type": "CLUSTER_BUY",
            "severity": "HIGH",
            "detail": f"{cluster_buys} institutional buyers in cluster period",
        })

    cluster_sells = flow_data.get("cluster_sells", 0)
    if cluster_sells >= 3:
        alerts.append({
            "alert_type": "CLUSTER_SELL",
            "severity": "HIGH",
            "detail": f"{cluster_sells} institutional sellers in cluster period",
        })

    # Short interest spike — scale threshold based on base short interest level
    short_change = flow_data.get("short_interest_change_pct")
    if short_change is not None:
        base_short = flow_data.get("short_interest_pct", 0.0)
        # Higher base short interest → lower threshold for spike detection
        if base_short >= 20.0:
            spike_threshold = 10.0  # Already heavily shorted; small increases matter
        elif base_short >= 10.0:
            spike_threshold = 15.0
        else:
            spike_threshold = 25.0  # Default threshold for low base
        if short_change > spike_threshold:
            alerts.append({
                "alert_type": "SHORT_SPIKE",
                "severity": "HIGH",
                "detail": f"Short interest increased {short_change:.1f}% (base: {base_short:.1f}%, threshold: {spike_threshold:.0f}%)",
            })

    # Insider cluster — count unique insiders, not transactions
    insider_txns = flow_data.get("insider_transactions", [])
    if len(insider_txns) >= 3:
        buy_insiders = set(
            t.get("insider_name") or t.get("insider_id") for t in insider_txns if t.get("direction") == "BUY"
        )
        sell_insiders = set(
            t.get("insider_name") or t.get("insider_id") for t in insider_txns if t.get("direction") == "SELL"
        )
        # Discard None entries from missing identifiers
        buy_insiders.discard(None)
        sell_insiders.discard(None)
        unique_buyers = len(buy_insiders)
        unique_sellers = len(sell_insiders)
        if unique_buyers >= 3 or unique_sellers >= 3:
            direction = "buying" if unique_buyers >= unique_sellers else "selling"
            unique_count = max(unique_buyers, unique_sellers)
            alerts.append({
                "alert_type": "INSIDER_CLUSTER",
                "severity": "MEDIUM",
                "detail": f"Cluster of insider {direction}: {unique_count} unique insiders",
            })

    return alerts


# ── Alert Prioritization ─────────────────────────────────────────────────

_SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def prioritize_alerts(alerts: list[dict]) -> list[dict]:
    """Sort alerts by severity: CRITICAL > HIGH > MEDIUM > LOW.

    Parameters
    ----------
    alerts : list[dict]
        Each dict has at minimum {alert_type, severity, detail}.

    Returns
    -------
    list[dict]
        Sorted list (highest severity first).
    """
    return sorted(
        alerts,
        key=lambda a: _SEVERITY_ORDER.get(a.get("severity", "LOW"), 99),
    )
