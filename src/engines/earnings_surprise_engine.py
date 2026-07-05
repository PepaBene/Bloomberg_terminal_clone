"""Pillar 3 Phase 2 -- Part 3: Earnings Surprise Engine.

Pure computation engine for earnings surprise analysis, market reaction
classification, historical pattern detection, guidance tracking, and
guidance credibility scoring.

No database access -- all functions accept and return plain data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class SurpriseResult:
    """Surprise metrics for a single earnings report."""

    eps_surprise_pct: float | None = None
    revenue_surprise_pct: float | None = None
    ebitda_surprise_pct: float | None = None
    is_beat: bool = False
    is_miss: bool = False


@dataclass
class MarketReactionAnalysis:
    """Market reaction classification relative to earnings surprise."""

    price_reaction_1d_pct: float = 0.0
    price_reaction_5d_pct: float = 0.0
    reaction_vs_surprise: str = "PROPORTIONAL"  # PROPORTIONAL / MUTED / OVERREACTION
    beat_and_fell: bool = False


@dataclass
class HistoricalPattern:
    """Historical earnings surprise patterns."""

    consecutive_beats: int = 0
    consecutive_misses: int = 0
    avg_surprise_magnitude_4q: float = 0.0
    sandbagging_flag: bool = False
    guidance_accuracy: float = 0.0


@dataclass
class GuidanceAnalysis:
    """Classification of company guidance relative to prior and consensus."""

    guidance_type: str = "INITIAL"  # INITIAL/RAISED/LOWERED/MAINTAINED/NARROWED/WITHDRAWN
    guidance_vs_consensus: str = "INLINE"  # ABOVE/INLINE/BELOW
    width_pct: float = 0.0


@dataclass
class GuidanceCredibility:
    """Credibility assessment of company guidance based on historical accuracy."""

    credibility_score: float = 0.0  # 0-100
    historical_accuracy: float = 0.0
    consistency_score: float = 0.0
    avg_width_pct: float = 0.0


# ---------------------------------------------------------------------------
# Core Functions
# ---------------------------------------------------------------------------


def compute_surprise(actual: float | None, consensus: float | None) -> float | None:
    """Compute surprise percentage: (actual - consensus) / |consensus|.

    Parameters
    ----------
    actual : float | None
        Actual reported value.
    consensus : float | None
        Consensus estimate.

    Returns
    -------
    float | None
        Surprise as percentage, or None if inputs are invalid.
    """
    if actual is None or consensus is None:
        return None
    if consensus == 0.0:
        return None

    return round((actual - consensus) / abs(consensus) * 100, 4)


def compute_all_surprises(
    actual_eps: float | None = None,
    consensus_eps: float | None = None,
    actual_revenue: float | None = None,
    consensus_revenue: float | None = None,
    actual_ebitda: float | None = None,
    consensus_ebitda: float | None = None,
) -> SurpriseResult:
    """Compute surprise metrics for EPS, revenue, and EBITDA.

    Parameters
    ----------
    actual_eps, consensus_eps : EPS values.
    actual_revenue, consensus_revenue : Revenue values.
    actual_ebitda, consensus_ebitda : EBITDA values.

    Returns
    -------
    SurpriseResult with surprise percentages and beat/miss flags.
    """
    eps_surprise = compute_surprise(actual_eps, consensus_eps)
    revenue_surprise = compute_surprise(actual_revenue, consensus_revenue)
    ebitda_surprise = compute_surprise(actual_ebitda, consensus_ebitda)

    # Determine beat/miss based on available surprises with weighted voting.
    # EPS gets double weight because it is the most material metric.
    metric_results: list[tuple[str, float]] = []
    if eps_surprise is not None:
        metric_results.append(("eps", eps_surprise))
    if revenue_surprise is not None:
        metric_results.append(("revenue", revenue_surprise))
    if ebitda_surprise is not None:
        metric_results.append(("ebitda", ebitda_surprise))

    is_beat = False
    is_miss = False
    if metric_results:
        # EPS gets double weight in beat/miss determination
        weighted_beat = sum(
            2 if metric == "eps" else 1
            for metric, surprise in metric_results if surprise > 0
        )
        weighted_miss = sum(
            2 if metric == "eps" else 1
            for metric, surprise in metric_results if surprise < 0
        )
        is_beat = weighted_beat > weighted_miss
        is_miss = weighted_miss > weighted_beat

    return SurpriseResult(
        eps_surprise_pct=eps_surprise,
        revenue_surprise_pct=revenue_surprise,
        ebitda_surprise_pct=ebitda_surprise,
        is_beat=is_beat,
        is_miss=is_miss,
    )


def analyze_market_reaction(
    surprise_pct: float | None,
    price_change_1d: float | None,
    price_change_5d: float | None,
) -> MarketReactionAnalysis:
    """Classify market reaction relative to earnings surprise.

    Parameters
    ----------
    surprise_pct : float | None
        Earnings surprise percentage.
    price_change_1d : float | None
        One-day price change percentage.
    price_change_5d : float | None
        Five-day price change percentage.

    Returns
    -------
    MarketReactionAnalysis with classification and beat_and_fell flag.
    """
    safe_1d = price_change_1d if price_change_1d is not None else 0.0
    safe_5d = price_change_5d if price_change_5d is not None else 0.0
    safe_surprise = surprise_pct if surprise_pct is not None else 0.0

    # Beat and fell: positive surprise but stock fell more than 1%
    beat_and_fell = safe_surprise > 0.0 and safe_1d < -1.0

    # Classify reaction vs surprise
    reaction_type = "PROPORTIONAL"

    if surprise_pct is None or price_change_1d is None:
        reaction_type = "PROPORTIONAL"
    else:
        abs_surprise = abs(safe_surprise)
        abs_price_change = abs(safe_1d)

        if abs_surprise < 0.5:
            # Small surprise -- any reaction classification is fine
            reaction_type = "PROPORTIONAL"
        elif abs_price_change < 0.5 and abs_surprise >= 2.0:
            # Stock barely moved despite significant surprise
            reaction_type = "MUTED"
        elif abs_surprise > 0.0 and abs_price_change / max(abs_surprise, 0.01) > 3.0:
            # Price moved disproportionately more than surprise
            reaction_type = "OVERREACTION"
        else:
            reaction_type = "PROPORTIONAL"

    return MarketReactionAnalysis(
        price_reaction_1d_pct=safe_1d,
        price_reaction_5d_pct=safe_5d,
        reaction_vs_surprise=reaction_type,
        beat_and_fell=beat_and_fell,
    )


def compute_historical_pattern(
    surprises: list[dict],
) -> HistoricalPattern:
    """Analyze historical earnings surprise patterns.

    Parameters
    ----------
    surprises : list[dict]
        List of quarterly surprise dicts, most recent first.
        Each dict has: {surprise_pct, guidance_midpoint, actual}

    Returns
    -------
    HistoricalPattern with consecutive beats/misses, average magnitude,
    sandbagging flag, and guidance accuracy.
    """
    if not surprises:
        return HistoricalPattern()

    # Count consecutive beats/misses from most recent backward
    consecutive_beats = 0
    consecutive_misses = 0

    for entry in surprises:
        pct = entry.get("surprise_pct")
        if pct is None:
            break
        if pct > 0:
            if consecutive_misses > 0:
                break
            consecutive_beats += 1
        elif pct < 0:
            if consecutive_beats > 0:
                break
            consecutive_misses += 1
        else:
            break  # Exact match breaks the streak

    # Average surprise magnitude over last 4 quarters
    recent_4 = surprises[:4]
    magnitudes = [
        abs(e.get("surprise_pct", 0.0))
        for e in recent_4
        if e.get("surprise_pct") is not None
    ]
    avg_magnitude_4q = round(sum(magnitudes) / len(magnitudes), 4) if magnitudes else 0.0

    # Sandbagging flag: avg surprise > 5% for 4+ consecutive quarters
    sandbagging = False
    if consecutive_beats >= 4 and avg_magnitude_4q > 5.0:
        sandbagging = True

    # Guidance accuracy: 1 - mean(|guidance - actual| / |actual|)
    guidance_errors: list[float] = []
    for entry in surprises:
        guidance_mid = entry.get("guidance_midpoint")
        actual = entry.get("actual")
        if guidance_mid is not None and actual is not None and actual != 0:
            error = abs(guidance_mid - actual) / abs(actual)
            guidance_errors.append(error)

    guidance_accuracy = 0.0
    if guidance_errors:
        mean_error = sum(guidance_errors) / len(guidance_errors)
        guidance_accuracy = round(max(1.0 - mean_error, 0.0), 4)

    return HistoricalPattern(
        consecutive_beats=consecutive_beats,
        consecutive_misses=consecutive_misses,
        avg_surprise_magnitude_4q=avg_magnitude_4q,
        sandbagging_flag=sandbagging,
        guidance_accuracy=guidance_accuracy,
    )


def classify_guidance(
    guidance_low: float | None,
    guidance_high: float | None,
    prior_low: float | None,
    prior_high: float | None,
    consensus: float | None,
) -> GuidanceAnalysis:
    """Classify guidance type and positioning vs consensus.

    Parameters
    ----------
    guidance_low, guidance_high : Current guidance range.
    prior_low, prior_high : Prior guidance range.
    consensus : Consensus estimate.

    Returns
    -------
    GuidanceAnalysis with type, consensus comparison, and width.
    """
    # Determine guidance type
    if guidance_low is None and guidance_high is None:
        if prior_low is not None:
            return GuidanceAnalysis(
                guidance_type="WITHDRAWN",
                guidance_vs_consensus="INLINE",
                width_pct=0.0,
            )
        return GuidanceAnalysis(
            guidance_type="INITIAL",
            guidance_vs_consensus="INLINE",
            width_pct=0.0,
        )

    # If we have current guidance but no prior
    if prior_low is None and prior_high is None:
        guidance_type = "INITIAL"
    else:
        # Compare current vs prior
        safe_prior_low = prior_low if prior_low is not None else 0.0
        safe_prior_high = prior_high if prior_high is not None else 0.0
        safe_curr_low = guidance_low if guidance_low is not None else 0.0
        safe_curr_high = guidance_high if guidance_high is not None else 0.0

        low_change_pct = _pct_change(safe_curr_low, safe_prior_low)
        high_change_pct = _pct_change(safe_curr_high, safe_prior_high)

        prior_width = safe_prior_high - safe_prior_low
        curr_width = safe_curr_high - safe_curr_low

        if low_change_pct > 1.0 and high_change_pct > 1.0:
            guidance_type = "RAISED"
        elif low_change_pct < -1.0 and high_change_pct < -1.0:
            guidance_type = "LOWERED"
        elif curr_width < prior_width * 0.8:
            guidance_type = "NARROWED"
        elif abs(low_change_pct) <= 1.0 and abs(high_change_pct) <= 1.0:
            guidance_type = "MAINTAINED"
        elif low_change_pct > 1.0 or high_change_pct > 1.0:
            guidance_type = "RAISED"
        elif low_change_pct < -1.0 or high_change_pct < -1.0:
            guidance_type = "LOWERED"
        else:
            guidance_type = "MAINTAINED"

    # Compute midpoint and width
    safe_low = guidance_low if guidance_low is not None else 0.0
    safe_high = guidance_high if guidance_high is not None else safe_low
    midpoint = (safe_low + safe_high) / 2.0

    width_pct = 0.0
    if midpoint != 0.0:
        width_pct = round(abs(safe_high - safe_low) / abs(midpoint) * 100, 4)

    # Compare vs consensus
    vs_consensus = "INLINE"
    if consensus is not None and consensus != 0.0:
        if midpoint > consensus * 1.02:
            vs_consensus = "ABOVE"
        elif midpoint < consensus * 0.98:
            vs_consensus = "BELOW"

    return GuidanceAnalysis(
        guidance_type=guidance_type,
        guidance_vs_consensus=vs_consensus,
        width_pct=width_pct,
    )


def _pct_change(current: float, prior: float) -> float:
    """Helper: percentage change from prior to current."""
    if prior == 0.0:
        return 0.0 if current == 0.0 else 100.0
    return (current - prior) / abs(prior) * 100


def compute_guidance_credibility(
    history: list[dict],
) -> GuidanceCredibility:
    """Assess credibility of company guidance based on track record.

    Parameters
    ----------
    history : list[dict]
        Historical quarters, each with: {guidance_midpoint, actual}
        Optionally: {guidance_low, guidance_high}

    Returns
    -------
    GuidanceCredibility with score (0-100), accuracy, consistency, width.
    """
    if not history:
        return GuidanceCredibility()

    # Compute errors: |guidance - actual| / |actual|
    errors: list[float] = []
    widths: list[float] = []

    for entry in history:
        guidance_mid = entry.get("guidance_midpoint")
        actual = entry.get("actual")

        if guidance_mid is not None and actual is not None and actual != 0:
            error = abs(guidance_mid - actual) / abs(actual)
            errors.append(error)

        # Width calculation
        g_low = entry.get("guidance_low")
        g_high = entry.get("guidance_high")
        if g_low is not None and g_high is not None:
            mid = (g_low + g_high) / 2.0
            if mid != 0.0:
                widths.append(abs(g_high - g_low) / abs(mid) * 100)

    if not errors:
        return GuidanceCredibility()

    # Accuracy: 1 - mean(errors)
    mean_error = sum(errors) / len(errors)
    accuracy = max(1.0 - mean_error, 0.0)

    # Consistency: 1 - std(errors)
    if len(errors) >= 2:
        mean_e = sum(errors) / len(errors)
        variance = sum((e - mean_e) ** 2 for e in errors) / len(errors)
        std = math.sqrt(variance)
        consistency = max(1.0 - std, 0.0)
    else:
        # Single quarter -- assume moderate consistency
        consistency = 0.5

    # Average guidance width
    avg_width = sum(widths) / len(widths) if widths else 0.0

    # Normalize width penalty: wider ranges = less credible
    # Cap at 20% width as "maximum penalty"
    width_factor = 1.0 - min(avg_width / 20.0, 1.0)

    # Composite score: 40% accuracy + 30% consistency + 30% width factor
    score = (40 * accuracy) + (30 * consistency) + (30 * width_factor)
    score = round(min(max(score, 0.0), 100.0), 2)

    return GuidanceCredibility(
        credibility_score=score,
        historical_accuracy=round(accuracy, 4),
        consistency_score=round(consistency, 4),
        avg_width_pct=round(avg_width, 4),
    )
