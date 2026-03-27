"""Pillar 3 Phase 4C — Engine 3: Intelligent Alert Engine.

Pure computation engine for alert deduplication, consolidation,
priority scoring, fatigue reduction, and routing.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

from datetime import datetime, timezone


# ── Constants ──────────────────────────────────────────────────────────────

DEDUP_WINDOW_HOURS = 2
MAX_ALERTS_PER_ENTITY = 5

PRIORITY_SCORES: dict[str, int] = {
    "earnings_miss": 95,
    "guidance_cut": 90,
    "rating_downgrade": 88,
    "ceo_departure": 85,
    "sec_investigation": 92,
    "dividend_cut": 80,
    "ma_announcement": 85,
    "insider_selling": 70,
    "analyst_downgrade": 65,
    "price_target_cut": 60,
    "news_negative": 50,
    "news_positive": 40,
    "filing_10k": 45,
    "filing_8k": 55,
    "volume_spike": 35,
    "price_move": 30,
}

ALERT_CATEGORIES = {
    "earnings_miss": "EARNINGS",
    "guidance_cut": "EARNINGS",
    "rating_downgrade": "RATING",
    "ceo_departure": "MANAGEMENT",
    "sec_investigation": "REGULATORY",
    "dividend_cut": "CORPORATE_ACTION",
    "ma_announcement": "CORPORATE_ACTION",
    "insider_selling": "INSIDER",
    "analyst_downgrade": "RATING",
    "price_target_cut": "RATING",
    "news_negative": "NEWS",
    "news_positive": "NEWS",
    "filing_10k": "FILING",
    "filing_8k": "FILING",
    "volume_spike": "MARKET",
    "price_move": "MARKET",
}

ACTION_THRESHOLDS = {
    "REVIEW_IMMEDIATELY": 85,
    "REVIEW_TODAY": 65,
    "MONITOR": 40,
    "INFORMATIONAL": 0,
}


# ── Classification & Priority ─────────────────────────────────────────────


def classify_alert_category(alert_type: str) -> str:
    """Classify an alert into a category.

    Parameters
    ----------
    alert_type : str
        One of the known alert types.

    Returns
    -------
    str
        Category label (e.g. EARNINGS, RATING, MANAGEMENT, etc.).
    """
    return ALERT_CATEGORIES.get(alert_type, "OTHER")


def compute_alert_priority(
    alert_type: str,
    magnitude: float | None = None,
    entity_in_portfolio: bool = False,
    market_hours: bool = True,
) -> int:
    """Compute priority score for an alert.

    Parameters
    ----------
    alert_type : str
        Alert type key.
    magnitude : float | None
        Magnitude of the event (e.g. EPS miss %, price move %).
    entity_in_portfolio : bool
        Whether the entity is in the user's portfolio.
    market_hours : bool
        Whether the alert arrived during market hours.

    Returns
    -------
    int
        Priority score 0-100.
    """
    base = PRIORITY_SCORES.get(alert_type, 25)

    adjustments = 0

    # Magnitude boost
    if magnitude is not None:
        if abs(magnitude) >= 20:
            adjustments += 10
        elif abs(magnitude) >= 10:
            adjustments += 5

    # Portfolio boost
    if entity_in_portfolio:
        adjustments += 10

    # Market hours boost
    if market_hours:
        adjustments += 5

    return min(100, max(0, base + adjustments))


# ── Deduplication ──────────────────────────────────────────────────────────


def deduplicate_alerts(alerts: list[dict]) -> list[dict]:
    """Remove duplicate alerts within the dedup window.

    Alerts are considered duplicates if they share the same entity_id,
    alert_type, and arrive within DEDUP_WINDOW_HOURS of each other.

    Parameters
    ----------
    alerts : list[dict]
        Each alert has: entity_id, alert_type, timestamp (ISO string or datetime),
        headline, and optionally alert_id.

    Returns
    -------
    list[dict]
        Deduplicated alerts (keeps earliest occurrence).
    """
    if not alerts:
        return []

    # Sort by timestamp
    def _parse_ts(a):
        ts = a.get("timestamp")
        if isinstance(ts, str):
            return datetime.fromisoformat(ts)
        return ts if ts else datetime.min.replace(tzinfo=timezone.utc)

    sorted_alerts = sorted(alerts, key=_parse_ts)

    seen: dict[tuple, datetime] = {}
    deduped: list[dict] = []

    for alert in sorted_alerts:
        key = (alert.get("entity_id"), alert.get("alert_type"))
        ts = _parse_ts(alert)

        if key in seen:
            delta_hours = (ts - seen[key]).total_seconds() / 3600
            if delta_hours < DEDUP_WINDOW_HOURS:
                continue  # duplicate within window

        seen[key] = ts
        deduped.append(alert)

    return deduped


# ── Consolidation ──────────────────────────────────────────────────────────


def consolidate_alerts(alerts: list[dict]) -> list[dict]:
    """Consolidate alerts per entity: pick highest-priority as primary,
    rest become secondary.

    Parameters
    ----------
    alerts : list[dict]
        Each alert has entity_id, alert_type, headline, priority (int).

    Returns
    -------
    list[dict]
        One consolidated alert per entity with primary + secondary alerts.
    """
    if not alerts:
        return []

    by_entity: dict[str, list[dict]] = {}
    for a in alerts:
        eid = a.get("entity_id", "unknown")
        by_entity.setdefault(eid, []).append(a)

    consolidated = []
    for entity_id, entity_alerts in by_entity.items():
        # Sort by priority descending
        entity_alerts.sort(key=lambda x: x.get("priority", 0), reverse=True)

        primary = entity_alerts[0]
        secondary = entity_alerts[1:MAX_ALERTS_PER_ENTITY]

        categories = list({classify_alert_category(a.get("alert_type", "")) for a in entity_alerts})

        consolidated.append({
            "entity_id": entity_id,
            "alert_priority": primary.get("priority", 0),
            "alert_categories": categories,
            "primary_headline": primary.get("headline", ""),
            "primary_type": primary.get("alert_type", ""),
            "source_alert_ids": [a.get("alert_id") for a in entity_alerts if a.get("alert_id")],
            "secondary_alerts": [
                {"headline": s.get("headline", ""), "alert_type": s.get("alert_type", ""), "priority": s.get("priority", 0)}
                for s in secondary
            ],
        })

    # Sort by priority descending
    consolidated.sort(key=lambda x: x["alert_priority"], reverse=True)
    return consolidated


# ── Filtering & Fatigue Reduction ──────────────────────────────────────────


def filter_low_signal(alerts: list[dict], min_priority: int = 30) -> list[dict]:
    """Filter out low-signal alerts below a minimum priority threshold.

    Parameters
    ----------
    alerts : list[dict]
    min_priority : int

    Returns
    -------
    list[dict]
    """
    return [a for a in alerts if a.get("priority", a.get("alert_priority", 0)) >= min_priority]


def apply_fatigue_reduction(
    alerts: list[dict],
    max_per_entity: int = MAX_ALERTS_PER_ENTITY,
    max_total: int = 20,
) -> list[dict]:
    """Reduce alert volume to prevent fatigue.

    Parameters
    ----------
    alerts : list[dict]
        Alerts sorted by priority descending.
    max_per_entity : int
        Maximum alerts per entity.
    max_total : int
        Maximum total alerts returned.

    Returns
    -------
    list[dict]
    """
    entity_counts: dict[str, int] = {}
    reduced: list[dict] = []

    for alert in alerts:
        if len(reduced) >= max_total:
            break

        entity_id = alert.get("entity_id", "unknown")
        count = entity_counts.get(entity_id, 0)

        if count >= max_per_entity:
            continue

        reduced.append(alert)
        entity_counts[entity_id] = count + 1

    return reduced


# ── Synthesis & Action ─────────────────────────────────────────────────────


def generate_alert_synthesis_template(consolidated: dict) -> str:
    """Generate an AI synthesis template for a consolidated alert.

    Parameters
    ----------
    consolidated : dict
        Output of consolidate_alerts (single entity).

    Returns
    -------
    str
        Synthesis text.
    """
    headline = consolidated.get("primary_headline", "")
    primary_type = consolidated.get("primary_type", "")
    secondary = consolidated.get("secondary_alerts", [])
    categories = consolidated.get("alert_categories", [])
    priority = consolidated.get("alert_priority", 0)

    parts = [f"Primary alert: {headline} (type: {primary_type}, priority: {priority})."]

    if secondary:
        secondary_summary = "; ".join(
            f"{s.get('headline', '')} ({s.get('alert_type', '')})"
            for s in secondary[:3]
        )
        parts.append(f"Related alerts: {secondary_summary}.")

    if categories:
        parts.append(f"Categories: {', '.join(categories)}.")

    return " ".join(parts)


def recommend_action(priority: int) -> str:
    """Recommend an action based on alert priority.

    Parameters
    ----------
    priority : int
        Alert priority score.

    Returns
    -------
    str
        Recommended action label.
    """
    for action, threshold in ACTION_THRESHOLDS.items():
        if priority >= threshold:
            return action
    return "INFORMATIONAL"


def route_alert(
    alert: dict,
    routing_rules: dict | None = None,
) -> dict:
    """Determine routing destination for an alert.

    Parameters
    ----------
    alert : dict
        Alert with priority, alert_type, entity_id.
    routing_rules : dict | None
        Custom routing rules. If None, uses default.

    Returns
    -------
    dict
        {destination, channel, escalate}
    """
    priority = alert.get("priority", alert.get("alert_priority", 0))
    alert_type = alert.get("alert_type", alert.get("primary_type", ""))

    if routing_rules:
        custom = routing_rules.get(alert_type)
        if custom:
            return {
                "destination": custom.get("destination", "default"),
                "channel": custom.get("channel", "email"),
                "escalate": priority >= 85,
            }

    # Default routing
    if priority >= 85:
        return {"destination": "portfolio_manager", "channel": "push", "escalate": True}
    elif priority >= 65:
        return {"destination": "research_analyst", "channel": "push", "escalate": False}
    elif priority >= 40:
        return {"destination": "research_analyst", "channel": "email", "escalate": False}
    else:
        return {"destination": "digest", "channel": "email", "escalate": False}


# ── Batch Processing ──────────────────────────────────────────────────────


def process_alert_batch(
    raw_alerts: list[dict],
    portfolio_entity_ids: set[str] | None = None,
    min_priority: int = 30,
    max_total: int = 20,
) -> list[dict]:
    """End-to-end alert processing pipeline.

    Steps: classify -> compute priority -> deduplicate -> consolidate ->
    filter low signal -> reduce fatigue -> add action + routing.

    Parameters
    ----------
    raw_alerts : list[dict]
        Raw incoming alerts with entity_id, alert_type, headline, timestamp.
    portfolio_entity_ids : set[str] | None
        Entity IDs in the user's portfolio.
    min_priority : int
    max_total : int

    Returns
    -------
    list[dict]
        Processed, consolidated alerts.
    """
    portfolio = portfolio_entity_ids or set()

    # Step 1: Enrich with priority
    for alert in raw_alerts:
        alert["priority"] = compute_alert_priority(
            alert.get("alert_type", ""),
            magnitude=alert.get("magnitude"),
            entity_in_portfolio=alert.get("entity_id", "") in portfolio,
        )

    # Step 2: Deduplicate
    deduped = deduplicate_alerts(raw_alerts)

    # Step 3: Filter low signal
    filtered = filter_low_signal(deduped, min_priority=min_priority)

    # Step 4: Consolidate
    consolidated = consolidate_alerts(filtered)

    # Step 5: Fatigue reduction
    reduced = apply_fatigue_reduction(consolidated, max_total=max_total)

    # Step 6: Add action and routing
    for alert in reduced:
        alert["recommended_action"] = recommend_action(alert["alert_priority"])
        alert["routing"] = route_alert(alert)
        alert["ai_synthesis"] = generate_alert_synthesis_template(alert)

    return reduced
