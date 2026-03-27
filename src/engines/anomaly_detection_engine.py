"""Pillar 3 Phase 4A -- Anomaly Detection Engine.

Pure computation engine for detecting statistical anomalies across
price momentum, volume, earnings, fundamentals, sentiment, supply chain,
and peer divergence dimensions.

No database access -- all functions accept and return plain data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import mean, stdev


# -- Anomaly Type Definitions ------------------------------------------------

ANOMALY_TYPES: dict[str, str] = {
    "price_momentum": "Unusual price move relative to historical distribution",
    "volume_spike": "Abnormal trading volume relative to historical average",
    "earnings_surprise": "Unusual earnings surprise vs consensus estimates",
    "fundamental_shift": "Changes in profitability, leverage, or growth metrics",
    "sentiment": "Unusual sentiment shift in news or social media",
    "supply_chain": "Supply chain disruption signals from supplier/customer news",
    "peer_divergence": "Divergence from peer group performance",
}

SEVERITY_THRESHOLDS: dict[int, str] = {
    50: "MEDIUM",
    70: "HIGH",
    85: "CRITICAL",
}

ALERT_ROUTING: dict[int, str] = {
    85: "REAL_TIME",
    70: "DAILY_BATCH",
    50: "WEEKLY",
    0: "HISTORICAL",
}


# -- Dataclasses --------------------------------------------------------------


@dataclass
class StatisticalEvidence:
    """Statistical backing for an anomaly detection."""

    observed_value: float
    expected_value: float
    z_score: float
    percentile_rank: float


@dataclass
class ContextualAnalysis:
    """Qualitative context around an anomaly."""

    peer_comparison: str | None
    historical_precedent: str | None
    potential_catalysts: list[str]
    estimated_impact: str  # high/medium/low


@dataclass
class RelatedData:
    """Supplementary market data associated with an anomaly."""

    price_change_pct: float | None
    volume_change_pct: float | None
    iv_change: float | None
    news_count: int | None
    insider_activity: str | None  # null/buying/selling


@dataclass
class RecommendedAction:
    """A recommended follow-up action for a detected anomaly."""

    action: str
    urgency: str  # immediate/near_term/ongoing_monitoring
    resource_required: str  # analyst/quant_research/trader


@dataclass
class AnomalyResult:
    """Full anomaly detection result for a single anomaly."""

    anomaly_type: str
    severity_score: float  # 0-100
    evidence: StatisticalEvidence
    context: ContextualAnalysis
    related_data: RelatedData | None
    narrative_template: str
    actions: list[RecommendedAction]
    confidence: float  # 0-1


# -- Core Statistical Helpers ------------------------------------------------


def compute_z_score(values: list[float], current: float) -> float:
    """Compute z-score of *current* relative to *values*.

    Returns 0.0 for empty or single-element lists where standard
    deviation is undefined.
    """
    if len(values) < 2:
        return 0.0
    m = mean(values)
    sd = stdev(values)
    if sd == 0.0:
        return 0.0
    return (current - m) / sd


def compute_percentile(values: list[float], current: float) -> float:
    """Compute percentile rank (0-100) of *current* in *values*.

    Percentile = proportion of historical values that are strictly
    below *current*, expressed as 0-100.  Returns 0.0 for empty lists.
    """
    if not values:
        return 0.0
    below = sum(1 for v in values if v < current)
    return (below / len(values)) * 100.0


# -- Severity Classification -------------------------------------------------


def classify_severity(z_score: float, anomaly_type: str) -> float:
    """Convert a z-score into a 0-100 severity score.

    Base score = |z_score| * 20.
    Type multipliers: earnings_surprise and fundamental_shift get 1.2x,
    supply_chain gets 1.1x.  Capped at 100.
    """
    base = abs(z_score) * 20.0
    multiplier = 1.0
    if anomaly_type in ("earnings_surprise", "fundamental_shift"):
        multiplier = 1.2
    elif anomaly_type == "supply_chain":
        multiplier = 1.1
    return min(base * multiplier, 100.0)


def _severity_label(score: float) -> str:
    """Return CRITICAL / HIGH / MEDIUM / LOW label for a severity score."""
    if score >= 85:
        return "CRITICAL"
    if score >= 70:
        return "HIGH"
    if score >= 50:
        return "MEDIUM"
    return "LOW"


def _alert_route(score: float) -> str:
    """Return alert routing category for a severity score."""
    if score >= 85:
        return "REAL_TIME"
    if score >= 70:
        return "DAILY_BATCH"
    if score >= 50:
        return "WEEKLY"
    return "HISTORICAL"


def _default_actions(anomaly_type: str, severity: float) -> list[RecommendedAction]:
    """Generate default recommended actions based on anomaly type and severity."""
    actions: list[RecommendedAction] = []

    if severity >= 85:
        urgency = "immediate"
    elif severity >= 70:
        urgency = "near_term"
    else:
        urgency = "ongoing_monitoring"

    resource_map = {
        "price_momentum": "trader",
        "volume_spike": "trader",
        "earnings_surprise": "analyst",
        "fundamental_shift": "analyst",
        "sentiment": "analyst",
        "supply_chain": "analyst",
        "peer_divergence": "quant_research",
    }
    resource = resource_map.get(anomaly_type, "analyst")

    actions.append(RecommendedAction(
        action=f"Review {anomaly_type.replace('_', ' ')} anomaly",
        urgency=urgency,
        resource_required=resource,
    ))

    if severity >= 70:
        actions.append(RecommendedAction(
            action="Escalate to senior analyst",
            urgency=urgency,
            resource_required="analyst",
        ))

    return actions


# -- Anomaly Detectors -------------------------------------------------------


def detect_price_momentum_anomaly(
    returns: list[float],
    current_return: float,
    beta: float | None = None,
    market_return: float | None = None,
) -> AnomalyResult | None:
    """Detect unusual price momentum.

    If *beta* and *market_return* are provided the expected return is
    ``beta * market_return`` and the excess return is used for z-scoring.
    Otherwise the raw return is scored against the historical distribution.

    Returns ``None`` when ``|z_score| < 2``.
    """
    if beta is not None and market_return is not None:
        expected = beta * market_return
        excess = current_return - expected
        # Build an excess-return series for z-scoring
        excess_series = [r - expected for r in returns]
        z = compute_z_score(excess_series, excess)
        observed = excess
    else:
        z = compute_z_score(returns, current_return)
        expected = mean(returns) if returns else 0.0
        observed = current_return

    if abs(z) < 2:
        return None

    severity = min(abs(z) * 20.0, 100.0)
    percentile = compute_percentile(returns, current_return)
    direction = "positive" if current_return > 0 else "negative"

    evidence = StatisticalEvidence(
        observed_value=observed,
        expected_value=expected,
        z_score=z,
        percentile_rank=percentile,
    )
    context = ContextualAnalysis(
        peer_comparison=None,
        historical_precedent=f"{direction} {abs(z):.1f}-sigma move",
        potential_catalysts=[],
        estimated_impact="high" if severity >= 70 else "medium",
    )
    actions = _default_actions("price_momentum", severity)

    return AnomalyResult(
        anomaly_type="price_momentum",
        severity_score=severity,
        evidence=evidence,
        context=context,
        related_data=None,
        narrative_template=(
            f"Price momentum anomaly detected: {direction} "
            f"{abs(z):.1f}-sigma move (severity {severity:.0f})"
        ),
        actions=actions,
        confidence=min(abs(z) / 5.0, 1.0),
    )


def detect_volume_spike(
    volumes: list[float],
    current_volume: float,
) -> AnomalyResult | None:
    """Detect abnormal trading volume spikes.

    Only triggers on *positive* spikes (current > mean).
    Returns ``None`` when ``z_score < 2``.
    """
    if not volumes or len(volumes) < 2:
        return None

    m = mean(volumes)
    if current_volume <= m:
        return None

    z = compute_z_score(volumes, current_volume)
    if z < 2:
        return None

    severity = min(z * 25.0, 100.0)
    percentile = compute_percentile(volumes, current_volume)
    vol_ratio = current_volume / m if m > 0 else 0.0

    evidence = StatisticalEvidence(
        observed_value=current_volume,
        expected_value=m,
        z_score=z,
        percentile_rank=percentile,
    )
    context = ContextualAnalysis(
        peer_comparison=None,
        historical_precedent=f"{vol_ratio:.1f}x average volume",
        potential_catalysts=[],
        estimated_impact="high" if severity >= 70 else "medium",
    )
    actions = _default_actions("volume_spike", severity)

    return AnomalyResult(
        anomaly_type="volume_spike",
        severity_score=severity,
        evidence=evidence,
        context=context,
        related_data=None,
        narrative_template=(
            f"Volume spike detected: {vol_ratio:.1f}x average "
            f"(z-score {z:.1f}, severity {severity:.0f})"
        ),
        actions=actions,
        confidence=min(z / 5.0, 1.0),
    )


def detect_earnings_surprise_anomaly(
    actual_eps: float,
    consensus_eps: float,
    historical_surprises: list[float],
) -> AnomalyResult | None:
    """Detect unusual earnings surprise relative to historical distribution.

    Surprise % = ``(actual - consensus) / |consensus| * 100`` when
    consensus != 0.  Returns ``None`` when ``|z_score| < 1.5``.
    """
    if consensus_eps == 0:
        return None

    surprise_pct = (actual_eps - consensus_eps) / abs(consensus_eps) * 100.0
    z = compute_z_score(historical_surprises, surprise_pct)

    if abs(z) < 1.5:
        return None

    severity = min(abs(z) * 22.0, 100.0)
    direction = "beat" if surprise_pct > 0 else "miss"
    percentile = compute_percentile(historical_surprises, surprise_pct)

    evidence = StatisticalEvidence(
        observed_value=surprise_pct,
        expected_value=mean(historical_surprises) if historical_surprises else 0.0,
        z_score=z,
        percentile_rank=percentile,
    )
    context = ContextualAnalysis(
        peer_comparison=None,
        historical_precedent=f"Earnings {direction} of {abs(surprise_pct):.1f}%",
        potential_catalysts=[],
        estimated_impact="high" if severity >= 70 else "medium",
    )
    actions = _default_actions("earnings_surprise", severity)

    return AnomalyResult(
        anomaly_type="earnings_surprise",
        severity_score=severity,
        evidence=evidence,
        context=context,
        related_data=None,
        narrative_template=(
            f"Earnings surprise anomaly: {direction} by {abs(surprise_pct):.1f}% "
            f"(z-score {z:.1f}, severity {severity:.0f})"
        ),
        actions=actions,
        confidence=min(abs(z) / 4.0, 1.0),
    )


def detect_fundamental_shift(
    current_metrics: dict,
    prior_metrics: dict,
    peer_metrics: list[dict] | None = None,
) -> AnomalyResult | None:
    """Detect significant changes in fundamental metrics.

    Compares ``operating_margin``, ``roe``, ``debt_to_equity``, and
    ``revenue_growth`` between *current_metrics* and *prior_metrics*.

    A metric is flagged if it changed by more than 2 standard deviations
    relative to the peer distribution (if available) or >30% absolute
    change otherwise.

    Returns the most significant shift, or ``None`` if no shift detected.
    """
    keys = ["operating_margin", "roe", "debt_to_equity", "revenue_growth"]
    best_z = 0.0
    best_key: str | None = None
    best_current = 0.0
    best_prior = 0.0

    for key in keys:
        cur = current_metrics.get(key)
        pri = prior_metrics.get(key)
        if cur is None or pri is None:
            continue

        if peer_metrics:
            peer_values = [p[key] for p in peer_metrics if key in p]
            if len(peer_values) >= 2:
                change = cur - pri
                z = compute_z_score(peer_values, cur)
                if abs(z) > abs(best_z) and abs(z) > 2:
                    best_z = z
                    best_key = key
                    best_current = cur
                    best_prior = pri
                continue

        # Fallback: >30% absolute change
        if pri != 0:
            pct_change = abs(cur - pri) / abs(pri) * 100.0
        else:
            pct_change = abs(cur - pri) * 100.0

        if pct_change > 30:
            # Convert to synthetic z-score for severity
            synthetic_z = pct_change / 15.0  # 30% => 2.0
            if abs(synthetic_z) > abs(best_z):
                best_z = synthetic_z
                best_key = key
                best_current = cur
                best_prior = pri

    if best_key is None:
        return None

    severity = classify_severity(best_z, "fundamental_shift")
    percentile = 0.0  # No historical distribution available in this path

    evidence = StatisticalEvidence(
        observed_value=best_current,
        expected_value=best_prior,
        z_score=best_z,
        percentile_rank=percentile,
    )
    context = ContextualAnalysis(
        peer_comparison=(
            f"{best_key} diverges from peers" if peer_metrics else None
        ),
        historical_precedent=f"{best_key} changed from {best_prior:.2f} to {best_current:.2f}",
        potential_catalysts=[],
        estimated_impact="high" if severity >= 70 else "medium",
    )
    actions = _default_actions("fundamental_shift", severity)

    return AnomalyResult(
        anomaly_type="fundamental_shift",
        severity_score=severity,
        evidence=evidence,
        context=context,
        related_data=None,
        narrative_template=(
            f"Fundamental shift in {best_key}: "
            f"{best_prior:.2f} -> {best_current:.2f} "
            f"(z-score {best_z:.1f}, severity {severity:.0f})"
        ),
        actions=actions,
        confidence=min(abs(best_z) / 5.0, 1.0),
    )


def detect_sentiment_anomaly(
    current_score: float,
    historical_scores: list[float],
    news_volume: int,
    avg_volume: float,
) -> AnomalyResult | None:
    """Detect unusual sentiment shifts.

    Z-score of *current_score* vs *historical_scores*.  If news volume
    exceeds 2x average, severity is amplified by 1.3x.
    Returns ``None`` when ``|z_score| < 2``.
    """
    z = compute_z_score(historical_scores, current_score)
    if abs(z) < 2:
        return None

    severity = min(abs(z) * 20.0, 100.0)

    # Amplify if news volume is elevated
    if avg_volume > 0 and news_volume > 2 * avg_volume:
        severity = min(severity * 1.3, 100.0)

    percentile = compute_percentile(historical_scores, current_score)
    direction = "negative" if current_score < 0 else "positive"

    evidence = StatisticalEvidence(
        observed_value=current_score,
        expected_value=mean(historical_scores) if historical_scores else 0.0,
        z_score=z,
        percentile_rank=percentile,
    )
    context = ContextualAnalysis(
        peer_comparison=None,
        historical_precedent=f"Sentiment {direction} shift, {abs(z):.1f}-sigma",
        potential_catalysts=[],
        estimated_impact="high" if severity >= 70 else "medium",
    )
    actions = _default_actions("sentiment", severity)

    return AnomalyResult(
        anomaly_type="sentiment",
        severity_score=severity,
        evidence=evidence,
        context=context,
        related_data=None,
        narrative_template=(
            f"Sentiment anomaly: {direction} shift "
            f"(z-score {z:.1f}, severity {severity:.0f})"
        ),
        actions=actions,
        confidence=min(abs(z) / 5.0, 1.0),
    )


def detect_supply_chain_anomaly(
    supplier_news: list[dict],
    customer_news: list[dict],
) -> AnomalyResult | None:
    """Detect supply chain disruption signals.

    Counts negative-sentiment news items for suppliers and customers.
    Triggers if combined negative count exceeds 3.

    Each news dict is expected to have at least ``{"sentiment": "negative"|...}``.
    """
    neg_supplier = sum(
        1 for n in supplier_news if n.get("sentiment") == "negative"
    )
    neg_customer = sum(
        1 for n in customer_news if n.get("sentiment") == "negative"
    )
    total_neg = neg_supplier + neg_customer

    if total_neg <= 3:
        return None

    # Severity: scale by count — 4 negatives ~ base, more is worse
    raw_z = total_neg / 2.0  # 4 neg => z=2, 6 neg => z=3, etc.
    severity = classify_severity(raw_z, "supply_chain")

    source = "supplier" if neg_supplier >= neg_customer else "customer"

    evidence = StatisticalEvidence(
        observed_value=float(total_neg),
        expected_value=0.0,
        z_score=raw_z,
        percentile_rank=0.0,
    )
    context = ContextualAnalysis(
        peer_comparison=None,
        historical_precedent=None,
        potential_catalysts=[
            f"{neg_supplier} negative supplier news",
            f"{neg_customer} negative customer news",
        ],
        estimated_impact="high" if severity >= 70 else "medium",
    )
    actions = _default_actions("supply_chain", severity)

    return AnomalyResult(
        anomaly_type="supply_chain",
        severity_score=severity,
        evidence=evidence,
        context=context,
        related_data=None,
        narrative_template=(
            f"Supply chain anomaly: {total_neg} negative news items "
            f"(primarily {source}, severity {severity:.0f})"
        ),
        actions=actions,
        confidence=min(raw_z / 5.0, 1.0),
    )


def detect_peer_divergence(
    entity_return: float,
    peer_returns: list[float],
    lookback_days: int = 30,
) -> AnomalyResult | None:
    """Detect significant divergence from peer group.

    Z-score of *entity_return* vs *peer_returns* distribution.
    Returns ``None`` when ``|z_score| < 2``.
    """
    z = compute_z_score(peer_returns, entity_return)
    if abs(z) < 2:
        return None

    severity = min(abs(z) * 20.0, 100.0)
    percentile = compute_percentile(peer_returns, entity_return)
    direction = "outperformance" if entity_return > mean(peer_returns) else "underperformance"

    evidence = StatisticalEvidence(
        observed_value=entity_return,
        expected_value=mean(peer_returns),
        z_score=z,
        percentile_rank=percentile,
    )
    context = ContextualAnalysis(
        peer_comparison=f"{direction} vs peer group over {lookback_days} days",
        historical_precedent=None,
        potential_catalysts=[],
        estimated_impact="high" if severity >= 70 else "medium",
    )
    actions = _default_actions("peer_divergence", severity)

    return AnomalyResult(
        anomaly_type="peer_divergence",
        severity_score=severity,
        evidence=evidence,
        context=context,
        related_data=None,
        narrative_template=(
            f"Peer divergence: {direction} by {abs(z):.1f} sigma "
            f"over {lookback_days} days (severity {severity:.0f})"
        ),
        actions=actions,
        confidence=min(abs(z) / 5.0, 1.0),
    )


# -- Narrative Generation ----------------------------------------------------


def generate_anomaly_narrative_template(
    anomaly: AnomalyResult,
    entity_name: str,
) -> str:
    """Generate a human-readable narrative for an anomaly.

    Template: ``"{entity_name} shows {anomaly_type} anomaly (severity {severity}).
    Observed {observed} vs expected {expected} (z-score: {z_score}).
    Recommended: {actions}."``
    """
    ev = anomaly.evidence
    action_text = "; ".join(a.action for a in anomaly.actions) if anomaly.actions else "No actions"
    severity_label = _severity_label(anomaly.severity_score)

    return (
        f"{entity_name} shows {anomaly.anomaly_type.replace('_', ' ')} anomaly "
        f"(severity {anomaly.severity_score:.0f}, {severity_label}). "
        f"Observed {ev.observed_value:.4f} vs expected {ev.expected_value:.4f} "
        f"(z-score: {ev.z_score:.2f}). "
        f"Recommended: {action_text}."
    )


# -- Full Scan ---------------------------------------------------------------


def run_full_anomaly_scan(
    entity_data: dict,
    market_data: dict,
    peer_data: list[dict] | None = None,
) -> list[AnomalyResult]:
    """Run all 7 anomaly detectors and return results sorted by severity.

    Parameters
    ----------
    entity_data : dict
        Keys: returns, volumes, current_return, current_volume,
        eps_actual, eps_consensus, historical_surprises,
        sentiment_score, historical_sentiments, news_volume,
        avg_news_volume, fundamentals_current, fundamentals_prior,
        supplier_news, customer_news
    market_data : dict
        Keys: market_return, beta
    peer_data : list[dict] | None
        Each dict has at least ``return_pct``.

    Returns
    -------
    list[AnomalyResult]
        All detected anomalies sorted by severity_score descending.
    """
    results: list[AnomalyResult] = []

    # 1. Price momentum
    pm = detect_price_momentum_anomaly(
        returns=entity_data.get("returns", []),
        current_return=entity_data.get("current_return", 0.0),
        beta=market_data.get("beta"),
        market_return=market_data.get("market_return"),
    )
    if pm is not None:
        results.append(pm)

    # 2. Volume spike
    vs = detect_volume_spike(
        volumes=entity_data.get("volumes", []),
        current_volume=entity_data.get("current_volume", 0.0),
    )
    if vs is not None:
        results.append(vs)

    # 3. Earnings surprise
    eps_actual = entity_data.get("eps_actual")
    eps_consensus = entity_data.get("eps_consensus")
    if eps_actual is not None and eps_consensus is not None:
        es = detect_earnings_surprise_anomaly(
            actual_eps=eps_actual,
            consensus_eps=eps_consensus,
            historical_surprises=entity_data.get("historical_surprises", []),
        )
        if es is not None:
            results.append(es)

    # 4. Fundamental shift
    fc = entity_data.get("fundamentals_current")
    fp = entity_data.get("fundamentals_prior")
    if fc is not None and fp is not None:
        peer_fund = None
        if peer_data:
            peer_fund = [p for p in peer_data if "operating_margin" in p]
        fs = detect_fundamental_shift(
            current_metrics=fc,
            prior_metrics=fp,
            peer_metrics=peer_fund if peer_fund else None,
        )
        if fs is not None:
            results.append(fs)

    # 5. Sentiment
    sent_score = entity_data.get("sentiment_score")
    if sent_score is not None:
        sa = detect_sentiment_anomaly(
            current_score=sent_score,
            historical_scores=entity_data.get("historical_sentiments", []),
            news_volume=entity_data.get("news_volume", 0),
            avg_volume=entity_data.get("avg_news_volume", 0.0),
        )
        if sa is not None:
            results.append(sa)

    # 6. Supply chain
    sc = detect_supply_chain_anomaly(
        supplier_news=entity_data.get("supplier_news", []),
        customer_news=entity_data.get("customer_news", []),
    )
    if sc is not None:
        results.append(sc)

    # 7. Peer divergence
    if peer_data:
        peer_returns = [p["return_pct"] for p in peer_data if "return_pct" in p]
        if peer_returns:
            pd_result = detect_peer_divergence(
                entity_return=entity_data.get("current_return", 0.0),
                peer_returns=peer_returns,
            )
            if pd_result is not None:
                results.append(pd_result)

    # Sort by severity descending
    results.sort(key=lambda r: r.severity_score, reverse=True)
    return results
