"""Pillar 3 Phase 1 — Part 8: Alert Engine.

Pure computation engine for evaluating alert conditions and generating alerts.
Handles filing alerts, price alerts, insider alerts, and governance alerts.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


# ── Alert Type Definitions ────────────────────────────────────────────────

FILING_ALERT_TYPES = {
    "FILING_8K": {"priority": "HIGH", "desc": "New 8-K material event"},
    "FILING_ANNUAL": {"priority": "MEDIUM", "desc": "New 10-K/10-Q filed"},
    "RISK_FACTOR_CHANGE": {"priority": "HIGH", "desc": "Substantive change in Item 1A Risk Factors"},
    "AUDITOR_CHANGE": {"priority": "CRITICAL", "desc": "8-K Item 4.01: Auditor change"},
    "RESTATEMENT": {"priority": "CRITICAL", "desc": "8-K Item 4.02: Non-reliance on prior financial statements"},
    "MANAGEMENT_CHANGE": {"priority": "HIGH", "desc": "8-K Item 5.02: CEO/CFO departure or appointment"},
    "INSIDER_CLUSTER_BUY": {"priority": "MEDIUM", "desc": "3+ insiders purchased open-market in 30 days"},
    "INSIDER_CEO_PURCHASE": {"priority": "MEDIUM", "desc": "CEO open-market share purchase"},
    "GOVERNANCE_RED_FLAG": {"priority": "LOW", "desc": "New governance red flag detected"},
}

PRICE_ALERT_TYPES = {
    "PRICE_THRESHOLD": {"priority": "MEDIUM", "desc": "Price crossed user-defined threshold"},
    "PRICE_52W_HIGH": {"priority": "LOW", "desc": "New 52-week high"},
    "PRICE_52W_LOW": {"priority": "LOW", "desc": "New 52-week low"},
}

ALL_ALERT_TYPES = {**FILING_ALERT_TYPES, **PRICE_ALERT_TYPES}

# Priority ordering for sorting
PRIORITY_ORDER = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}


# ── Alert Dataclass ───────────────────────────────────────────────────────


@dataclass
class AlertResult:
    """A triggered alert."""

    alert_type: str
    priority: str  # CRITICAL, HIGH, MEDIUM, LOW
    entity_id: str
    entity_name: str = ""
    title: str = ""
    detail: dict = field(default_factory=dict)
    source_type: str = ""  # "8K", "FILING_DIFF", "INSIDER", "PRICE", "GOVERNANCE"
    source_id: str = ""


# ── Filing Alert Evaluation ───────────────────────────────────────────────


def evaluate_filing_alerts(
    events: list[dict],
    rules: list[dict],
) -> list[AlertResult]:
    """Match new filing events against active alert rules.

    Parameters
    ----------
    events : list[dict]
        New events, each with: entity_id, alert_type, priority (from event processor),
        entity_name, detail (dict), source_type, source_id.
    rules : list[dict]
        Active alert rules, each with: alert_type, entity_scope ({type, entity_ids}),
        priority_threshold, is_active.

    Returns
    -------
    list[AlertResult]
        Triggered alerts.
    """
    alerts: list[AlertResult] = []

    for event in events:
        event_type = event.get("alert_type", "")
        event_entity = event.get("entity_id", "")
        event_priority = event.get("priority", "MEDIUM")

        for rule in rules:
            if not rule.get("is_active", True):
                continue

            # Check if alert type matches
            rule_type = rule.get("alert_type", "")
            if rule_type != event_type and rule_type != "*":
                continue

            # Check entity scope
            scope = rule.get("entity_scope", {})
            scope_type = scope.get("type", "UNIVERSE")
            if scope_type == "SPECIFIC":
                entity_ids = scope.get("entity_ids", [])
                if event_entity not in entity_ids:
                    continue
            elif scope_type == "WATCHLIST":
                watchlist_ids = scope.get("entity_ids", [])
                if event_entity not in watchlist_ids:
                    continue
            # UNIVERSE matches all

            # Check priority threshold
            threshold = rule.get("priority_threshold", "LOW")
            if PRIORITY_ORDER.get(event_priority, 0) < PRIORITY_ORDER.get(threshold, 0):
                continue

            # Create alert
            alerts.append(AlertResult(
                alert_type=event_type,
                priority=event_priority,
                entity_id=event_entity,
                entity_name=event.get("entity_name", ""),
                title=event.get("title", format_alert_title(event_type, event.get("entity_name", ""), event.get("detail", {}))),
                detail=event.get("detail", {}),
                source_type=event.get("source_type", ""),
                source_id=event.get("source_id", ""),
            ))
            break  # One alert per event (don't duplicate for multiple matching rules)

    return alerts


# ── Price Alert Evaluation ────────────────────────────────────────────────


def evaluate_price_alerts(
    current_prices: dict[str, float],
    rules: list[dict],
    historical_highs: dict[str, float] | None = None,
    historical_lows: dict[str, float] | None = None,
) -> list[AlertResult]:
    """Check price alert conditions.

    Parameters
    ----------
    current_prices : dict[str, float]
        Mapping of entity_id → current price.
    rules : list[dict]
        Price alert rules with: alert_type (PRICE_THRESHOLD/PRICE_52W_HIGH/PRICE_52W_LOW),
        entity_scope, conditions ({operator, value}).
    historical_highs : dict[str, float] | None
        52-week highs by entity_id.
    historical_lows : dict[str, float] | None
        52-week lows by entity_id.

    Returns
    -------
    list[AlertResult]
        Triggered price alerts.
    """
    alerts: list[AlertResult] = []
    hist_highs = historical_highs or {}
    hist_lows = historical_lows or {}

    for rule in rules:
        if not rule.get("is_active", True):
            continue

        alert_type = rule.get("alert_type", "")
        scope = rule.get("entity_scope", {})
        entity_ids = scope.get("entity_ids", list(current_prices.keys()))

        for entity_id in entity_ids:
            price = current_prices.get(entity_id)
            if price is None:
                continue

            if alert_type == "PRICE_THRESHOLD":
                conditions = rule.get("conditions", {})
                operator = conditions.get("operator", "GT")
                threshold_value = conditions.get("value")
                if threshold_value is None:
                    continue

                triggered = False
                if operator == "GT" and price > float(threshold_value):
                    triggered = True
                elif operator == "LT" and price < float(threshold_value):
                    triggered = True
                elif operator == "GTE" and price >= float(threshold_value):
                    triggered = True
                elif operator == "LTE" and price <= float(threshold_value):
                    triggered = True

                if triggered:
                    alerts.append(AlertResult(
                        alert_type="PRICE_THRESHOLD",
                        priority="MEDIUM",
                        entity_id=entity_id,
                        title=f"Price {operator} ${threshold_value} (current: ${price:.2f})",
                        detail={"price": price, "threshold": float(threshold_value), "operator": operator},
                        source_type="PRICE",
                    ))

            elif alert_type == "PRICE_52W_HIGH":
                high = hist_highs.get(entity_id)
                if high is not None and price >= high:
                    alerts.append(AlertResult(
                        alert_type="PRICE_52W_HIGH",
                        priority="LOW",
                        entity_id=entity_id,
                        title=f"New 52-week high (${price:.2f})",
                        detail={"price": price, "previous_high": high},
                        source_type="PRICE",
                    ))

            elif alert_type == "PRICE_52W_LOW":
                low = hist_lows.get(entity_id)
                if low is not None and price <= low:
                    alerts.append(AlertResult(
                        alert_type="PRICE_52W_LOW",
                        priority="LOW",
                        entity_id=entity_id,
                        title=f"New 52-week low (${price:.2f})",
                        detail={"price": price, "previous_low": low},
                        source_type="PRICE",
                    ))

    return alerts


# ── Insider Alert Evaluation ──────────────────────────────────────────────


def evaluate_insider_alerts(
    signals: list[dict],
    rules: list[dict],
) -> list[AlertResult]:
    """Match insider signals against alert rules.

    Parameters
    ----------
    signals : list[dict]
        Insider signals with: entity_id, signal_type, signal_strength, detail.
    rules : list[dict]
        Insider alert rules.

    Returns
    -------
    list[AlertResult]
        Triggered insider alerts.
    """
    alerts: list[AlertResult] = []

    for signal in signals:
        signal_type = signal.get("signal_type", "")
        entity_id = signal.get("entity_id", "")

        # Map signal types to alert types
        alert_type = None
        if signal_type == "CLUSTER_BUY":
            alert_type = "INSIDER_CLUSTER_BUY"
        elif signal_type in ("CEO_PURCHASE", "CFO_PURCHASE"):
            alert_type = "INSIDER_CEO_PURCHASE"

        if not alert_type:
            continue

        # Check rules
        for rule in rules:
            if not rule.get("is_active", True):
                continue
            if rule.get("alert_type") not in (alert_type, "*"):
                continue

            scope = rule.get("entity_scope", {})
            scope_type = scope.get("type", "UNIVERSE")
            if scope_type in ("SPECIFIC", "WATCHLIST"):
                if entity_id not in scope.get("entity_ids", []):
                    continue

            priority = FILING_ALERT_TYPES.get(alert_type, {}).get("priority", "MEDIUM")
            alerts.append(AlertResult(
                alert_type=alert_type,
                priority=priority,
                entity_id=entity_id,
                entity_name=signal.get("entity_name", ""),
                title=format_alert_title(alert_type, signal.get("entity_name", ""), signal.get("detail", {})),
                detail=signal.get("detail", {}),
                source_type="INSIDER",
            ))
            break

    return alerts


# ── Governance Alert Evaluation ───────────────────────────────────────────


def evaluate_governance_alerts(
    assessments: list[dict],
    rules: list[dict],
) -> list[AlertResult]:
    """Match governance red flag detections against alert rules.

    Parameters
    ----------
    assessments : list[dict]
        Governance assessments with: entity_id, entity_name, red_flags (list),
        governance_score, classification.
    rules : list[dict]
        Governance alert rules.

    Returns
    -------
    list[AlertResult]
        Triggered governance alerts.
    """
    alerts: list[AlertResult] = []

    for assessment in assessments:
        red_flags = assessment.get("red_flags", [])
        if not red_flags:
            continue

        entity_id = assessment.get("entity_id", "")

        for rule in rules:
            if not rule.get("is_active", True):
                continue
            if rule.get("alert_type") not in ("GOVERNANCE_RED_FLAG", "*"):
                continue

            scope = rule.get("entity_scope", {})
            scope_type = scope.get("type", "UNIVERSE")
            if scope_type in ("SPECIFIC", "WATCHLIST"):
                if entity_id not in scope.get("entity_ids", []):
                    continue

            flag_names = [f.get("flag", "") for f in red_flags]
            alerts.append(AlertResult(
                alert_type="GOVERNANCE_RED_FLAG",
                priority="LOW",
                entity_id=entity_id,
                entity_name=assessment.get("entity_name", ""),
                title=f"Governance red flags detected: {', '.join(flag_names[:3])}",
                detail={
                    "governance_score": assessment.get("governance_score"),
                    "classification": assessment.get("classification"),
                    "red_flags": red_flags,
                },
                source_type="GOVERNANCE",
            ))
            break

    return alerts


# ── Alert Prioritization ──────────────────────────────────────────────────


def prioritize_alerts(
    alerts: list[AlertResult],
    max_per_entity: int = 10,
) -> list[AlertResult]:
    """Sort alerts by priority and deduplicate.

    1. Sort by priority (CRITICAL > HIGH > MEDIUM > LOW)
    2. Dedup: same alert_type + entity_id → keep highest priority
    3. Rate limit: max N alerts per entity per batch

    Parameters
    ----------
    alerts : list[AlertResult]
        Raw triggered alerts.
    max_per_entity : int
        Maximum alerts per entity (default 10).

    Returns
    -------
    list[AlertResult]
        Sorted, deduplicated, rate-limited alerts.
    """
    # Sort by priority descending
    sorted_alerts = sorted(
        alerts,
        key=lambda a: -PRIORITY_ORDER.get(a.priority, 0),
    )

    # Dedup: same type + entity → keep first (highest priority due to sort)
    seen: set[tuple[str, str]] = set()
    deduped: list[AlertResult] = []
    for alert in sorted_alerts:
        key = (alert.alert_type, alert.entity_id)
        if key not in seen:
            seen.add(key)
            deduped.append(alert)

    # Rate limit per entity
    entity_counts: dict[str, int] = {}
    limited: list[AlertResult] = []
    for alert in deduped:
        count = entity_counts.get(alert.entity_id, 0)
        if count < max_per_entity:
            limited.append(alert)
            entity_counts[alert.entity_id] = count + 1

    return limited


# ── Alert Title Formatting ────────────────────────────────────────────────


def format_alert_title(
    alert_type: str,
    entity_name: str,
    detail: dict,
) -> str:
    """Generate human-readable alert title.

    Parameters
    ----------
    alert_type : str
        Alert type key.
    entity_name : str
        Company name.
    detail : dict
        Event detail dictionary.

    Returns
    -------
    str
        Formatted alert title.
    """
    name = entity_name or "Company"

    if alert_type == "RESTATEMENT":
        return f"CRITICAL: {name} disclosed non-reliance on prior financial statements"
    elif alert_type == "AUDITOR_CHANGE":
        return f"CRITICAL: {name} changed its certifying accountant"
    elif alert_type == "MANAGEMENT_CHANGE":
        people = detail.get("key_people", [])
        if people:
            person = people[0]
            return f"{name}: {person.get('name', 'Executive')} {person.get('action', 'change')} as {person.get('role', 'officer')}"
        return f"{name}: Management change announced"
    elif alert_type == "FILING_8K":
        item = detail.get("item_number", "")
        item_desc = detail.get("item_description", "")
        return f"{name} filed 8-K: {item} {item_desc}"
    elif alert_type == "FILING_ANNUAL":
        filing_type = detail.get("filing_type", "10-K")
        return f"{name} filed {filing_type}"
    elif alert_type == "RISK_FACTOR_CHANGE":
        materiality = detail.get("materiality", "")
        return f"{name}: Substantive risk factor changes detected ({materiality})"
    elif alert_type == "INSIDER_CLUSTER_BUY":
        count = detail.get("insider_count", 3)
        return f"{name}: {count}+ insiders purchased shares in open market"
    elif alert_type == "INSIDER_CEO_PURCHASE":
        shares = detail.get("shares", "")
        return f"CEO of {name} purchased {shares} shares on open market"
    elif alert_type == "GOVERNANCE_RED_FLAG":
        flags = detail.get("red_flags", [])
        flag_names = [f.get("flag", "") for f in flags[:2]]
        return f"{name}: Governance concerns — {', '.join(flag_names)}"
    elif alert_type == "PRICE_THRESHOLD":
        price = detail.get("price", 0)
        return f"{name}: Price alert triggered (${price:.2f})"
    elif alert_type == "PRICE_52W_HIGH":
        price = detail.get("price", 0)
        return f"New 52-week high for {name} (${price:.2f})"
    elif alert_type == "PRICE_52W_LOW":
        price = detail.get("price", 0)
        return f"New 52-week low for {name} (${price:.2f})"

    return f"{name}: {ALL_ALERT_TYPES.get(alert_type, {}).get('desc', alert_type)}"
