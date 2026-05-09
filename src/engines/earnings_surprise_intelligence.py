"""Pillar 3 Phase 4C — Engine 4: Earnings Surprise Intelligence.

Pure computation engine for post-earnings analysis: surprise metrics,
margin decomposition, guidance implications, stock reaction analysis,
and revision implications.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ── Dataclasses ────────────────────────────────────────────────────────────


@dataclass
class EPSAnalysis:
    """EPS surprise analysis."""

    consensus: float
    actual: float
    surprise_pct: float
    beat: bool
    magnitude: str  # "inline", "small", "large", "blowout"


@dataclass
class RevenueAnalysis:
    """Revenue surprise analysis."""

    consensus: float
    actual: float
    surprise_pct: float
    beat: bool
    magnitude: str


@dataclass
class MarginAnalysis:
    """Margin performance analysis."""

    gross_margin: float | None = None
    operating_margin: float | None = None
    gross_margin_yoy_change: float | None = None
    operating_margin_yoy_change: float | None = None
    margin_trend: str = "stable"  # expanding, contracting, stable


@dataclass
class GuidanceImplications:
    """Forward guidance assessment."""

    guidance_direction: str = "maintained"  # raised, lowered, maintained, withdrawn
    eps_guidance_range: tuple[float, float] | None = None
    revenue_guidance_range: tuple[float, float] | None = None
    confidence_level: str = "neutral"  # positive, neutral, cautious


@dataclass
class StockReaction:
    """Post-earnings stock price reaction."""

    price_change_pct: float = 0.0
    volume_vs_avg: float = 1.0
    reaction_type: str = "neutral"  # positive, negative, neutral, muted, volatile


@dataclass
class RevisionImplication:
    """Estimate revision implications."""

    direction: str = "maintain"  # upgrade, downgrade, maintain
    magnitude: str = "none"  # small, moderate, large, none
    affected_periods: list[str] = field(default_factory=list)


@dataclass
class EarningsSurpriseResult:
    """Complete earnings surprise analysis result."""

    eps_analysis: EPSAnalysis
    revenue_analysis: RevenueAnalysis
    margin_analysis: MarginAnalysis
    guidance: GuidanceImplications
    stock_reaction: StockReaction
    revision_implication: RevisionImplication
    recommendation: str
    key_takeaways: list[str]
    narrative: str


# ── Analysis Functions ─────────────────────────────────────────────────────


def analyze_eps_surprise(consensus: float, actual: float) -> EPSAnalysis:
    """Analyze EPS surprise.

    Parameters
    ----------
    consensus : float
        Consensus EPS estimate.
    actual : float
        Actual reported EPS.

    Returns
    -------
    EPSAnalysis
    """
    if consensus == 0:
        surprise_pct = 0.0 if actual == 0 else 100.0
    else:
        surprise_pct = round(((actual - consensus) / abs(consensus)) * 100, 4)

    beat = actual >= consensus

    abs_surprise = abs(surprise_pct)
    if abs_surprise <= 2.0:
        magnitude = "inline"
    elif abs_surprise <= 10.0:
        magnitude = "small"
    elif abs_surprise <= 25.0:
        magnitude = "large"
    else:
        magnitude = "blowout"

    return EPSAnalysis(
        consensus=consensus,
        actual=actual,
        surprise_pct=surprise_pct,
        beat=beat,
        magnitude=magnitude,
    )


def analyze_revenue_surprise(consensus: float, actual: float) -> RevenueAnalysis:
    """Analyze revenue surprise.

    Parameters
    ----------
    consensus : float
        Consensus revenue estimate.
    actual : float
        Actual reported revenue.

    Returns
    -------
    RevenueAnalysis
    """
    if consensus == 0:
        surprise_pct = 0.0 if actual == 0 else 100.0
    else:
        surprise_pct = round(((actual - consensus) / abs(consensus)) * 100, 4)

    beat = actual >= consensus

    abs_surprise = abs(surprise_pct)
    if abs_surprise <= 1.0:
        magnitude = "inline"
    elif abs_surprise <= 5.0:
        magnitude = "small"
    elif abs_surprise <= 15.0:
        magnitude = "large"
    else:
        magnitude = "blowout"

    return RevenueAnalysis(
        consensus=consensus,
        actual=actual,
        surprise_pct=surprise_pct,
        beat=beat,
        magnitude=magnitude,
    )


def analyze_margin_performance(
    gross_margin: float | None = None,
    operating_margin: float | None = None,
    prior_gross_margin: float | None = None,
    prior_operating_margin: float | None = None,
) -> MarginAnalysis:
    """Analyze margin performance vs prior period.

    Parameters
    ----------
    gross_margin : float | None
        Current gross margin (%).
    operating_margin : float | None
        Current operating margin (%).
    prior_gross_margin : float | None
    prior_operating_margin : float | None

    Returns
    -------
    MarginAnalysis
    """
    gm_change = None
    om_change = None

    if gross_margin is not None and prior_gross_margin is not None:
        gm_change = round(gross_margin - prior_gross_margin, 2)

    if operating_margin is not None and prior_operating_margin is not None:
        om_change = round(operating_margin - prior_operating_margin, 2)

    # Determine trend from operating margin change, fall back to gross margin
    change = om_change if om_change is not None else gm_change
    if change is not None:
        if change >= 0.5:
            trend = "expanding"
        elif change <= -0.5:
            trend = "contracting"
        else:
            trend = "stable"
    else:
        trend = "stable"

    return MarginAnalysis(
        gross_margin=gross_margin,
        operating_margin=operating_margin,
        gross_margin_yoy_change=gm_change,
        operating_margin_yoy_change=om_change,
        margin_trend=trend,
    )


def assess_guidance_implications(
    guidance_direction: str = "maintained",
    eps_low: float | None = None,
    eps_high: float | None = None,
    rev_low: float | None = None,
    rev_high: float | None = None,
    prior_eps_consensus: float | None = None,
) -> GuidanceImplications:
    """Assess forward guidance implications.

    Parameters
    ----------
    guidance_direction : str
        "raised", "lowered", "maintained", "withdrawn"
    eps_low, eps_high : float | None
        EPS guidance range.
    rev_low, rev_high : float | None
        Revenue guidance range.
    prior_eps_consensus : float | None
        Prior consensus for comparison.

    Returns
    -------
    GuidanceImplications
    """
    eps_range = (eps_low, eps_high) if eps_low is not None and eps_high is not None else None
    rev_range = (rev_low, rev_high) if rev_low is not None and rev_high is not None else None

    # Assess confidence level
    if guidance_direction == "raised":
        confidence = "positive"
    elif guidance_direction == "lowered":
        confidence = "cautious"
    elif guidance_direction == "withdrawn":
        confidence = "cautious"
    else:
        # Check if guidance midpoint vs consensus suggests direction
        if eps_range and prior_eps_consensus:
            midpoint = (eps_range[0] + eps_range[1]) / 2
            if midpoint > prior_eps_consensus * 1.02:
                confidence = "positive"
            elif midpoint < prior_eps_consensus * 0.98:
                confidence = "cautious"
            else:
                confidence = "neutral"
        else:
            confidence = "neutral"

    return GuidanceImplications(
        guidance_direction=guidance_direction,
        eps_guidance_range=eps_range,
        revenue_guidance_range=rev_range,
        confidence_level=confidence,
    )


def analyze_stock_reaction(
    price_change_pct: float,
    volume_vs_avg: float = 1.0,
) -> StockReaction:
    """Analyze post-earnings stock price reaction.

    Parameters
    ----------
    price_change_pct : float
        Post-earnings price change (%).
    volume_vs_avg : float
        Volume relative to average (e.g. 2.0 = 2x average).

    Returns
    -------
    StockReaction
    """
    abs_change = abs(price_change_pct)

    if abs_change <= 1.0:
        if volume_vs_avg >= 2.0:
            reaction_type = "muted"
        else:
            reaction_type = "neutral"
    elif abs_change <= 3.0:
        reaction_type = "positive" if price_change_pct > 0 else "negative"
    else:
        if volume_vs_avg >= 3.0 and abs_change >= 8.0:
            reaction_type = "volatile"
        elif price_change_pct > 0:
            reaction_type = "positive"
        else:
            reaction_type = "negative"

    return StockReaction(
        price_change_pct=price_change_pct,
        volume_vs_avg=volume_vs_avg,
        reaction_type=reaction_type,
    )


def compute_revision_implications(
    eps_surprise_pct: float,
    revenue_surprise_pct: float,
    guidance_direction: str = "maintained",
) -> RevisionImplication:
    """Compute estimate revision implications.

    Parameters
    ----------
    eps_surprise_pct : float
    revenue_surprise_pct : float
    guidance_direction : str

    Returns
    -------
    RevisionImplication
    """
    # Combined signal strength
    combined = abs(eps_surprise_pct) + abs(revenue_surprise_pct)
    positive_signal = eps_surprise_pct > 0 and revenue_surprise_pct >= 0

    # Guidance amplifies/dampens
    if guidance_direction == "raised":
        combined *= 1.3
    elif guidance_direction == "lowered":
        combined *= 1.3
        positive_signal = False
    elif guidance_direction == "withdrawn":
        positive_signal = False

    # Determine direction and magnitude
    if combined < 3.0:
        return RevisionImplication(direction="maintain", magnitude="none", affected_periods=[])

    if positive_signal:
        direction = "upgrade"
    else:
        direction = "downgrade"

    if combined >= 20.0:
        magnitude = "large"
        periods = ["current_quarter", "next_quarter", "full_year"]
    elif combined >= 10.0:
        magnitude = "moderate"
        periods = ["current_quarter", "next_quarter"]
    else:
        magnitude = "small"
        periods = ["current_quarter"]

    return RevisionImplication(
        direction=direction,
        magnitude=magnitude,
        affected_periods=periods,
    )


def generate_recommendation(
    eps_analysis: EPSAnalysis,
    revenue_analysis: RevenueAnalysis,
    guidance: GuidanceImplications,
    revision: RevisionImplication,
) -> str:
    """Generate an overall recommendation.

    Returns one of: STRONG_POSITIVE, POSITIVE, NEUTRAL, NEGATIVE, STRONG_NEGATIVE.
    """
    score = 0

    # EPS surprise
    if eps_analysis.beat:
        if eps_analysis.magnitude in ("large", "blowout"):
            score += 3
        else:
            score += 1
    else:
        if eps_analysis.magnitude in ("large", "blowout"):
            score -= 3
        else:
            score -= 1

    # Revenue surprise
    if revenue_analysis.beat:
        if revenue_analysis.magnitude in ("large", "blowout"):
            score += 2
        else:
            score += 1
    else:
        if revenue_analysis.magnitude in ("large", "blowout"):
            score -= 2
        else:
            score -= 1

    # Guidance
    if guidance.guidance_direction == "raised":
        score += 2
    elif guidance.guidance_direction == "lowered":
        score -= 2
    elif guidance.guidance_direction == "withdrawn":
        score -= 3

    # Revision implication
    if revision.direction == "upgrade":
        score += 1
    elif revision.direction == "downgrade":
        score -= 1

    if score >= 5:
        return "STRONG_POSITIVE"
    elif score >= 2:
        return "POSITIVE"
    elif score <= -5:
        return "STRONG_NEGATIVE"
    elif score <= -2:
        return "NEGATIVE"
    return "NEUTRAL"


def generate_key_takeaways(
    eps_analysis: EPSAnalysis,
    revenue_analysis: RevenueAnalysis,
    margin_analysis: MarginAnalysis,
    guidance: GuidanceImplications,
    stock_reaction: StockReaction,
) -> list[str]:
    """Generate a list of key takeaways from the earnings report.

    Returns up to 5 bullet-point takeaways.
    """
    takeaways = []

    # EPS — surprise_pct is None when consensus is missing or zero; format
    # accordingly instead of crashing with TypeError on abs(None).
    verb = "beat" if eps_analysis.beat else "missed"
    if eps_analysis.surprise_pct is None:
        takeaways.append(
            f"EPS {verb} consensus "
            f"(${eps_analysis.actual:.2f} vs ${eps_analysis.consensus:.2f})"
        )
    else:
        takeaways.append(
            f"EPS {verb} consensus by {abs(eps_analysis.surprise_pct):.1f}% "
            f"(${eps_analysis.actual:.2f} vs ${eps_analysis.consensus:.2f})"
        )

    # Revenue
    verb = "exceeded" if revenue_analysis.beat else "fell short of"
    if revenue_analysis.surprise_pct is None:
        takeaways.append(f"Revenue {verb} expectations")
    else:
        takeaways.append(
            f"Revenue {verb} expectations by {abs(revenue_analysis.surprise_pct):.1f}%"
        )

    # Margins
    if margin_analysis.margin_trend != "stable":
        takeaways.append(
            f"Operating margins {margin_analysis.margin_trend} "
            f"({margin_analysis.operating_margin_yoy_change:+.1f} pp YoY)"
            if margin_analysis.operating_margin_yoy_change is not None
            else f"Margins {margin_analysis.margin_trend}"
        )

    # Guidance
    if guidance.guidance_direction != "maintained":
        takeaways.append(f"Management {guidance.guidance_direction} forward guidance")

    # Stock reaction
    if stock_reaction.reaction_type != "neutral":
        takeaways.append(
            f"Stock reacted {stock_reaction.reaction_type} "
            f"({stock_reaction.price_change_pct:+.1f}%) on "
            f"{stock_reaction.volume_vs_avg:.1f}x average volume"
        )

    return takeaways[:5]


def generate_narrative_template(
    eps_analysis: EPSAnalysis,
    revenue_analysis: RevenueAnalysis,
    recommendation: str,
) -> str:
    """Generate a narrative template for the earnings event.

    Parameters
    ----------
    eps_analysis : EPSAnalysis
    revenue_analysis : RevenueAnalysis
    recommendation : str

    Returns
    -------
    str
        Narrative text.
    """
    eps_verb = "beat" if eps_analysis.beat else "missed"
    rev_verb = "exceeded" if revenue_analysis.beat else "fell short of"

    eps_pct_phrase = (
        f"by {abs(eps_analysis.surprise_pct):.1f}%"
        if eps_analysis.surprise_pct is not None
        else ""
    )
    rev_pct_phrase = (
        f"by {abs(revenue_analysis.surprise_pct):.1f}%"
        if revenue_analysis.surprise_pct is not None
        else ""
    )
    narrative = (
        f"The company reported EPS of ${eps_analysis.actual:.2f}, "
        f"which {eps_verb} the consensus estimate of ${eps_analysis.consensus:.2f} "
        f"{eps_pct_phrase} (a {eps_analysis.magnitude} "
        f"{'beat' if eps_analysis.beat else 'miss'}). "
        f"Revenue {rev_verb} expectations {rev_pct_phrase}. "
        f"Overall assessment: {recommendation}."
    )

    return narrative


# ── End-to-End Analysis ─────────────────────────────────────────────────


def analyze_earnings_event(
    eps_consensus: float,
    eps_actual: float,
    revenue_consensus: float,
    revenue_actual: float,
    gross_margin: float | None = None,
    operating_margin: float | None = None,
    prior_gross_margin: float | None = None,
    prior_operating_margin: float | None = None,
    guidance_direction: str = "maintained",
    eps_guidance_low: float | None = None,
    eps_guidance_high: float | None = None,
    rev_guidance_low: float | None = None,
    rev_guidance_high: float | None = None,
    prior_eps_consensus: float | None = None,
    price_change_pct: float = 0.0,
    volume_vs_avg: float = 1.0,
) -> EarningsSurpriseResult:
    """Run full earnings surprise analysis.

    Returns
    -------
    EarningsSurpriseResult
        Complete analysis result.
    """
    eps = analyze_eps_surprise(eps_consensus, eps_actual)
    revenue = analyze_revenue_surprise(revenue_consensus, revenue_actual)
    margins = analyze_margin_performance(
        gross_margin, operating_margin, prior_gross_margin, prior_operating_margin,
    )
    guidance = assess_guidance_implications(
        guidance_direction, eps_guidance_low, eps_guidance_high,
        rev_guidance_low, rev_guidance_high, prior_eps_consensus,
    )
    stock = analyze_stock_reaction(price_change_pct, volume_vs_avg)
    revision = compute_revision_implications(
        eps.surprise_pct, revenue.surprise_pct, guidance_direction,
    )
    rec = generate_recommendation(eps, revenue, guidance, revision)
    takeaways = generate_key_takeaways(eps, revenue, margins, guidance, stock)
    narrative = generate_narrative_template(eps, revenue, rec)

    return EarningsSurpriseResult(
        eps_analysis=eps,
        revenue_analysis=revenue,
        margin_analysis=margins,
        guidance=guidance,
        stock_reaction=stock,
        revision_implication=revision,
        recommendation=rec,
        key_takeaways=takeaways,
        narrative=narrative,
    )
