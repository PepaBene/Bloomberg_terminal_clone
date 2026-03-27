"""Pillar 4 Phase 1 — Watchlist Monitoring Engine.

Pure computation engine for evaluating watchlist alert conditions.
Watched securities generate alerts for: price thresholds, score changes,
filing events, news events, valuation targets, institutional flow,
and earnings calendar.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta


# ── Alert Type Definitions ────────────────────────────────────────────────

ALERT_TYPES: dict[str, dict] = {
    "PRICE_THRESHOLD": {"severity": "HIGH", "description": "Price crossed user-defined threshold"},
    "VALUATION_TARGET": {"severity": "HIGH", "description": "Security reached target valuation/entry price"},
    "SCORE_CHANGE": {"severity": "MEDIUM", "description": "Quality score changed significantly"},
    "FILING_EVENT": {"severity": "MEDIUM", "description": "New SEC filing detected"},
    "NEWS_ALERT": {"severity": "MEDIUM", "description": "Material news for watched security"},
    "INSTITUTIONAL_FLOW": {"severity": "LOW", "description": "Notable institutional activity"},
    "EARNINGS_CALENDAR": {"severity": "LOW", "description": "Upcoming earnings date"},
}

SCORE_CHANGE_THRESHOLDS: dict[str, object] = {
    "piotroski": 3,                # >=3 point change
    "altman_zone_change": True,    # Zone changed (safe<->gray<->distress)
    "beneish_flag": -1.78,         # Crossed the -1.78 threshold
}

# Severity ordering for filtering
_SEVERITY_ORDER = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

# Priority filing types (higher urgency)
_PRIORITY_FILING_TYPES = {"8-K", "8-K/A", "SC 13D", "SC 13D/A", "4", "4/A"}


# ── Dataclasses ───────────────────────────────────────────────────────────


@dataclass
class WatchlistAlert:
    """A triggered watchlist alert."""

    alert_type: str       # One of ALERT_TYPES keys
    entity_id: str
    ticker: str
    severity: str         # HIGH / MEDIUM / LOW
    title: str            # Human-readable alert title
    message: str          # Detailed alert message
    data: dict = field(default_factory=dict)   # Alert-specific data
    triggered_at: str = ""  # ISO datetime


@dataclass
class PriceAlert:
    """Price threshold crossing."""

    ticker: str
    current_price: float
    threshold_price: float
    direction: str           # ABOVE / BELOW
    pct_from_threshold: float


@dataclass
class ScoreChangeAlert:
    """Quality score significant change."""

    ticker: str
    score_name: str          # piotroski / altman / beneish
    old_value: float
    new_value: float
    change: float
    significance: str        # IMPROVED / DETERIORATED


@dataclass
class ValuationAlert:
    """Valuation target reached."""

    ticker: str
    current_price: float
    target_price: float | None
    current_pe: float | None
    target_pe: float | None
    below_entry: bool


@dataclass
class WatchlistMonitorResult:
    """Aggregated monitoring result for an entity."""

    entity_id: str
    ticker: str
    total_alerts: int
    high_priority: int
    medium_priority: int
    low_priority: int
    alerts: list[WatchlistAlert] = field(default_factory=list)


# ── Altman Zone Helper ────────────────────────────────────────────────────


def _altman_zone(z: float) -> str:
    """Classify Altman Z-Score into zones."""
    if z > 2.99:
        return "SAFE"
    if z >= 1.81:
        return "GREY"
    return "DISTRESS"


# ── Price Alert ───────────────────────────────────────────────────────────


def check_price_alert(
    current_price: float, alert_rules: list[dict]
) -> list[PriceAlert]:
    """Check if current price crosses any user-defined thresholds.

    Parameters
    ----------
    current_price : float
        Current market price.
    alert_rules : list[dict]
        Each rule: {threshold: float, direction: "ABOVE"/"BELOW"}.

    Returns
    -------
    list[PriceAlert]
        Alerts for each crossed threshold.
    """
    alerts: list[PriceAlert] = []

    for rule in alert_rules:
        threshold = rule.get("threshold")
        direction = rule.get("direction", "ABOVE")
        if threshold is None:
            continue

        threshold = float(threshold)
        triggered = False

        if direction == "ABOVE" and current_price >= threshold:
            triggered = True
        elif direction == "BELOW" and current_price <= threshold:
            triggered = True

        if triggered:
            diff = current_price - threshold
            pct = (diff / threshold * 100) if threshold != 0 else 0.0
            alerts.append(PriceAlert(
                ticker="",  # Filled by caller
                current_price=current_price,
                threshold_price=threshold,
                direction=direction,
                pct_from_threshold=round(pct, 2),
            ))

    return alerts


# ── Valuation Alert ───────────────────────────────────────────────────────


def check_valuation_alert(
    current_price: float,
    target_price: float | None,
    current_pe: float | None,
    target_pe: float | None,
) -> ValuationAlert | None:
    """Check if security reached target valuation / entry price.

    Parameters
    ----------
    current_price : float
        Current market price.
    target_price : float | None
        User-defined entry/target price.
    current_pe : float | None
        Current P/E ratio.
    target_pe : float | None
        User-defined target P/E.

    Returns
    -------
    ValuationAlert | None
        Alert if any condition met, else None.
    """
    below_entry = False

    if target_price is not None and current_price <= target_price:
        below_entry = True

    pe_triggered = False
    if current_pe is not None and target_pe is not None and current_pe <= target_pe:
        pe_triggered = True

    if not below_entry and not pe_triggered:
        return None

    return ValuationAlert(
        ticker="",  # Filled by caller
        current_price=current_price,
        target_price=target_price,
        current_pe=current_pe,
        target_pe=target_pe,
        below_entry=below_entry,
    )


# ── Score Change ──────────────────────────────────────────────────────────


def check_score_change(
    current_scores: dict, prior_scores: dict
) -> list[ScoreChangeAlert]:
    """Evaluate quality score changes for watchlist alerting.

    Parameters
    ----------
    current_scores : dict
        {piotroski: int, altman: float, beneish: float}.
    prior_scores : dict
        Previous period values with same keys.

    Returns
    -------
    list[ScoreChangeAlert]
        Alerts for significant changes.
    """
    alerts: list[ScoreChangeAlert] = []

    # Piotroski: alert if |change| >= 3
    pio_cur = current_scores.get("piotroski")
    pio_pri = prior_scores.get("piotroski")
    if pio_cur is not None and pio_pri is not None:
        change = pio_cur - pio_pri
        if abs(change) >= SCORE_CHANGE_THRESHOLDS["piotroski"]:
            alerts.append(ScoreChangeAlert(
                ticker="",
                score_name="piotroski",
                old_value=float(pio_pri),
                new_value=float(pio_cur),
                change=float(change),
                significance="IMPROVED" if change > 0 else "DETERIORATED",
            ))

    # Altman: alert if zone changed
    alt_cur = current_scores.get("altman")
    alt_pri = prior_scores.get("altman")
    if alt_cur is not None and alt_pri is not None:
        cur_zone = _altman_zone(alt_cur)
        pri_zone = _altman_zone(alt_pri)
        if cur_zone != pri_zone:
            change = alt_cur - alt_pri
            # Improvement = moving toward SAFE, deterioration = toward DISTRESS
            significance = "IMPROVED" if alt_cur > alt_pri else "DETERIORATED"
            alerts.append(ScoreChangeAlert(
                ticker="",
                score_name="altman",
                old_value=float(alt_pri),
                new_value=float(alt_cur),
                change=float(change),
                significance=significance,
            ))

    # Beneish: alert if crossed -1.78 threshold in either direction
    ben_cur = current_scores.get("beneish")
    ben_pri = prior_scores.get("beneish")
    if ben_cur is not None and ben_pri is not None:
        threshold = SCORE_CHANGE_THRESHOLDS["beneish_flag"]
        crossed = False
        if ben_pri <= threshold and ben_cur > threshold:
            crossed = True  # Crossed above (potential manipulation)
        elif ben_pri > threshold and ben_cur <= threshold:
            crossed = True  # Crossed below (cleared)

        if crossed:
            change = ben_cur - ben_pri
            # Above -1.78 is worse (manipulation signal)
            significance = "DETERIORATED" if ben_cur > threshold else "IMPROVED"
            alerts.append(ScoreChangeAlert(
                ticker="",
                score_name="beneish",
                old_value=float(ben_pri),
                new_value=float(ben_cur),
                change=float(change),
                significance=significance,
            ))

    return alerts


# ── Filing Alert ──────────────────────────────────────────────────────────


def check_filing_alert(
    recent_filings: list[dict], last_checked: str
) -> list[dict]:
    """Identify new filings since last check.

    Parameters
    ----------
    recent_filings : list[dict]
        Each: {filing_type, filed_date, title, url}.
    last_checked : str
        ISO datetime of last check.

    Returns
    -------
    list[dict]
        New filings sorted with 8-K and insider transactions first.
    """
    new_filings: list[dict] = []

    for filing in recent_filings:
        filed_date = filing.get("filed_date", "")
        if filed_date > last_checked:
            new_filings.append(filing)

    # Sort: priority filing types first, then by date descending
    def _sort_key(f: dict) -> tuple:
        is_priority = f.get("filing_type", "") in _PRIORITY_FILING_TYPES
        return (0 if is_priority else 1, f.get("filed_date", "") * -1 if isinstance(f.get("filed_date"), (int, float)) else f.get("filed_date", ""))

    new_filings.sort(key=lambda f: (
        0 if f.get("filing_type", "") in _PRIORITY_FILING_TYPES else 1,
        f.get("filed_date", ""),
    ), reverse=False)

    # Re-sort: priority first, within priority by date desc
    priority = [f for f in new_filings if f.get("filing_type", "") in _PRIORITY_FILING_TYPES]
    non_priority = [f for f in new_filings if f.get("filing_type", "") not in _PRIORITY_FILING_TYPES]

    # Sort each group by filed_date descending
    priority.sort(key=lambda f: f.get("filed_date", ""), reverse=True)
    non_priority.sort(key=lambda f: f.get("filed_date", ""), reverse=True)

    return priority + non_priority


# ── News Alert ────────────────────────────────────────────────────────────


def check_news_alert(
    recent_news: list[dict], min_relevance: float = 0.5
) -> list[dict]:
    """Filter and rank news by relevance.

    Parameters
    ----------
    recent_news : list[dict]
        Each: {title, source, published_date, relevance_score, sentiment}.
    min_relevance : float
        Minimum relevance_score to include.

    Returns
    -------
    list[dict]
        Filtered news sorted by relevance descending.
    """
    filtered = [
        n for n in recent_news
        if n.get("relevance_score", 0) >= min_relevance
    ]
    filtered.sort(key=lambda n: n.get("relevance_score", 0), reverse=True)
    return filtered


# ── Institutional Flow ────────────────────────────────────────────────────


def check_institutional_flow(flow_data: dict) -> list[dict]:
    """Evaluate institutional flow for watchlist alerting.

    Parameters
    ----------
    flow_data : dict
        {whale_trades: [...], activist_filings: [...], insider_transactions: [...]}.

    Returns
    -------
    list[dict]
        Alerts for whale trades > $10M, activist 13D filings, cluster insider buys.
    """
    alerts: list[dict] = []

    # Whale trades > $10M
    for trade in flow_data.get("whale_trades", []):
        value = trade.get("value_mm", trade.get("value", 0))
        if value >= 10:
            alerts.append({
                "type": "WHALE_TRADE",
                "institution": trade.get("institution", "Unknown"),
                "direction": trade.get("direction", "unknown"),
                "value_mm": value,
                "detail": f"{trade.get('institution', 'Unknown')} {trade.get('direction', '')} ${value:.0f}M",
            })

    # Activist 13D filings
    for filing in flow_data.get("activist_filings", []):
        alerts.append({
            "type": "ACTIVIST_13D",
            "activist": filing.get("activist", "Unknown"),
            "stake_pct": filing.get("stake_pct", 0),
            "detail": f"{filing.get('activist', 'Unknown')} filed 13D with {filing.get('stake_pct', 0):.1f}% stake",
        })

    # Cluster insider buys (3+ insiders buying)
    insider_txns = flow_data.get("insider_transactions", [])
    buy_count = sum(1 for t in insider_txns if t.get("direction") == "BUY")
    if buy_count >= 3:
        alerts.append({
            "type": "CLUSTER_INSIDER_BUY",
            "buy_count": buy_count,
            "detail": f"{buy_count} insiders bought shares in cluster period",
        })

    return alerts


# ── Earnings Calendar ─────────────────────────────────────────────────────


def check_earnings_calendar(
    earnings_dates: list[dict], days_ahead: int = 14
) -> list[dict]:
    """Find upcoming earnings within window.

    Parameters
    ----------
    earnings_dates : list[dict]
        Each: {ticker, earnings_date (ISO str), is_confirmed}.
    days_ahead : int
        Days ahead to look (default 14).

    Returns
    -------
    list[dict]
        Earnings events within the window.
    """
    alerts: list[dict] = []
    now = datetime.utcnow()
    cutoff = now + timedelta(days=days_ahead)

    for entry in earnings_dates:
        date_str = entry.get("earnings_date", "")
        if not date_str:
            continue

        try:
            # Support both date-only and datetime ISO formats
            if "T" in date_str:
                earnings_dt = datetime.fromisoformat(date_str.replace("Z", "+00:00").replace("+00:00", ""))
            else:
                earnings_dt = datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, TypeError):
            continue

        if now <= earnings_dt <= cutoff:
            days_until = (earnings_dt - now).days
            alerts.append({
                "ticker": entry.get("ticker", ""),
                "earnings_date": date_str,
                "is_confirmed": entry.get("is_confirmed", False),
                "days_until": days_until,
            })

    return alerts


# ── Orchestrator ──────────────────────────────────────────────────────────


def evaluate_watchlist_alerts(
    entity_data: dict, alert_config: dict | None = None
) -> WatchlistMonitorResult:
    """Run all watchlist checks for a single entity.

    Parameters
    ----------
    entity_data : dict
        {entity_id, ticker, current_price, target_price, target_pe,
         current_pe, scores, prior_scores, filings, last_checked,
         news, flows, earnings}.
    alert_config : dict | None
        {muted_types: [...], min_severity: "MEDIUM"}.

    Returns
    -------
    WatchlistMonitorResult
        Aggregated result with all collected alerts.
    """
    entity_id = entity_data.get("entity_id", "")
    ticker = entity_data.get("ticker", "")
    now_iso = datetime.utcnow().isoformat()
    all_alerts: list[WatchlistAlert] = []

    # 1. Price threshold alerts
    current_price = entity_data.get("current_price")
    price_rules = entity_data.get("price_rules", [])
    if current_price is not None and price_rules:
        price_alerts = check_price_alert(current_price, price_rules)
        for pa in price_alerts:
            all_alerts.append(WatchlistAlert(
                alert_type="PRICE_THRESHOLD",
                entity_id=entity_id,
                ticker=ticker,
                severity="HIGH",
                title=f"{ticker}: Price {pa.direction} ${pa.threshold_price:.2f}",
                message=f"Current price ${pa.current_price:.2f} is {pa.direction.lower()} threshold ${pa.threshold_price:.2f} ({pa.pct_from_threshold:+.1f}%)",
                data={"current_price": pa.current_price, "threshold": pa.threshold_price, "direction": pa.direction},
                triggered_at=now_iso,
            ))

    # 2. Valuation target alerts
    target_price = entity_data.get("target_price")
    current_pe = entity_data.get("current_pe")
    target_pe = entity_data.get("target_pe")
    if current_price is not None:
        va = check_valuation_alert(current_price, target_price, current_pe, target_pe)
        if va is not None:
            msg_parts = []
            if va.below_entry:
                msg_parts.append(f"below entry price ${target_price:.2f}")
            if current_pe is not None and target_pe is not None and current_pe <= target_pe:
                msg_parts.append(f"P/E {current_pe:.1f}x below target {target_pe:.1f}x")
            all_alerts.append(WatchlistAlert(
                alert_type="VALUATION_TARGET",
                entity_id=entity_id,
                ticker=ticker,
                severity="HIGH",
                title=f"{ticker}: Valuation target reached",
                message=f"${current_price:.2f} — {', '.join(msg_parts)}",
                data={"current_price": current_price, "target_price": target_price, "current_pe": current_pe, "target_pe": target_pe},
                triggered_at=now_iso,
            ))

    # 3. Score change alerts
    scores = entity_data.get("scores", {})
    prior_scores = entity_data.get("prior_scores", {})
    if scores and prior_scores:
        score_alerts = check_score_change(scores, prior_scores)
        for sa in score_alerts:
            all_alerts.append(WatchlistAlert(
                alert_type="SCORE_CHANGE",
                entity_id=entity_id,
                ticker=ticker,
                severity="MEDIUM",
                title=f"{ticker}: {sa.score_name.title()} score {sa.significance.lower()}",
                message=f"{sa.score_name.title()} changed from {sa.old_value:.1f} to {sa.new_value:.1f} ({sa.change:+.1f})",
                data={"score_name": sa.score_name, "old": sa.old_value, "new": sa.new_value, "change": sa.change},
                triggered_at=now_iso,
            ))

    # 4. Filing alerts
    filings = entity_data.get("filings", [])
    last_checked = entity_data.get("last_checked", "")
    if filings and last_checked:
        new_filings = check_filing_alert(filings, last_checked)
        for f in new_filings:
            all_alerts.append(WatchlistAlert(
                alert_type="FILING_EVENT",
                entity_id=entity_id,
                ticker=ticker,
                severity="MEDIUM",
                title=f"{ticker}: New {f.get('filing_type', 'filing')} — {f.get('title', '')}",
                message=f"Filed {f.get('filed_date', '')}",
                data=f,
                triggered_at=now_iso,
            ))

    # 5. News alerts
    news = entity_data.get("news", [])
    if news:
        material_news = check_news_alert(news)
        for n in material_news:
            all_alerts.append(WatchlistAlert(
                alert_type="NEWS_ALERT",
                entity_id=entity_id,
                ticker=ticker,
                severity="MEDIUM",
                title=f"{ticker}: {n.get('title', 'News')}",
                message=f"Source: {n.get('source', 'Unknown')} | Relevance: {n.get('relevance_score', 0):.1f}",
                data=n,
                triggered_at=now_iso,
            ))

    # 6. Institutional flow alerts
    flows = entity_data.get("flows", {})
    if flows:
        flow_alerts = check_institutional_flow(flows)
        for fa in flow_alerts:
            all_alerts.append(WatchlistAlert(
                alert_type="INSTITUTIONAL_FLOW",
                entity_id=entity_id,
                ticker=ticker,
                severity="LOW",
                title=f"{ticker}: {fa.get('type', 'Flow')} — {fa.get('detail', '')}",
                message=fa.get("detail", ""),
                data=fa,
                triggered_at=now_iso,
            ))

    # 7. Earnings calendar alerts
    earnings = entity_data.get("earnings", [])
    if earnings:
        upcoming = check_earnings_calendar(earnings)
        for e in upcoming:
            confirmed = "confirmed" if e.get("is_confirmed") else "estimated"
            all_alerts.append(WatchlistAlert(
                alert_type="EARNINGS_CALENDAR",
                entity_id=entity_id,
                ticker=ticker,
                severity="LOW",
                title=f"{ticker}: Earnings in {e.get('days_until', '?')} days ({confirmed})",
                message=f"Earnings date: {e.get('earnings_date', '')} ({confirmed})",
                data=e,
                triggered_at=now_iso,
            ))

    # Apply config filtering
    if alert_config:
        all_alerts = filter_by_user_preferences(all_alerts, alert_config)

    # Count by severity
    high = sum(1 for a in all_alerts if a.severity == "HIGH")
    medium = sum(1 for a in all_alerts if a.severity == "MEDIUM")
    low = sum(1 for a in all_alerts if a.severity == "LOW")

    return WatchlistMonitorResult(
        entity_id=entity_id,
        ticker=ticker,
        total_alerts=len(all_alerts),
        high_priority=high,
        medium_priority=medium,
        low_priority=low,
        alerts=all_alerts,
    )


# ── User Preference Filtering ────────────────────────────────────────────


def filter_by_user_preferences(
    alerts: list[WatchlistAlert], preferences: dict
) -> list[WatchlistAlert]:
    """Filter alerts based on user preferences.

    Parameters
    ----------
    alerts : list[WatchlistAlert]
        All generated alerts.
    preferences : dict
        {muted_types: [...], min_severity: "MEDIUM", quiet_hours: {start, end}}.

    Returns
    -------
    list[WatchlistAlert]
        Filtered alerts.
    """
    filtered = list(alerts)

    # Remove muted alert types
    muted_types = preferences.get("muted_types", [])
    if muted_types:
        filtered = [a for a in filtered if a.alert_type not in muted_types]

    # Filter below minimum severity
    min_severity = preferences.get("min_severity")
    if min_severity:
        min_order = _SEVERITY_ORDER.get(min_severity, 0)
        filtered = [
            a for a in filtered
            if _SEVERITY_ORDER.get(a.severity, 0) >= min_order
        ]

    # Respect quiet hours (simple string comparison on HH:MM)
    quiet_hours = preferences.get("quiet_hours")
    if quiet_hours:
        start = quiet_hours.get("start", "")
        end = quiet_hours.get("end", "")
        if start and end:
            now_hm = datetime.utcnow().strftime("%H:%M")
            if start <= end:
                in_quiet = start <= now_hm <= end
            else:
                in_quiet = now_hm >= start or now_hm <= end
            if in_quiet:
                # During quiet hours, only allow HIGH severity
                filtered = [a for a in filtered if a.severity == "HIGH"]

    return filtered


# ── Alert Digest ──────────────────────────────────────────────────────────


def format_alert_digest(alerts: list[WatchlistAlert]) -> dict:
    """Format alerts into a digest summary.

    Parameters
    ----------
    alerts : list[WatchlistAlert]
        All alerts.

    Returns
    -------
    dict
        {high_count, medium_count, low_count, by_type: {type: count}, top_alerts: [...]}.
    """
    high_count = sum(1 for a in alerts if a.severity == "HIGH")
    medium_count = sum(1 for a in alerts if a.severity == "MEDIUM")
    low_count = sum(1 for a in alerts if a.severity == "LOW")

    by_type: dict[str, int] = {}
    for a in alerts:
        by_type[a.alert_type] = by_type.get(a.alert_type, 0) + 1

    # Top alerts: HIGH first, then MEDIUM, then LOW — up to 10
    sorted_alerts = sorted(
        alerts,
        key=lambda a: -_SEVERITY_ORDER.get(a.severity, 0),
    )
    top_alerts = [
        {
            "alert_type": a.alert_type,
            "ticker": a.ticker,
            "severity": a.severity,
            "title": a.title,
        }
        for a in sorted_alerts[:10]
    ]

    return {
        "high_count": high_count,
        "medium_count": medium_count,
        "low_count": low_count,
        "by_type": by_type,
        "top_alerts": top_alerts,
    }
