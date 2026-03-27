"""Pillar 3 Phase 4B — Investment Thesis Engine.

Pure computation engine for generating structured investment theses,
valuation scenarios, conviction scoring, and presentation outlines.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean


# ── Constants ─────────────────────────────────────────────────────────

SECTOR_TEMPLATES: dict[str, dict] = {
    "Information Technology": {
        "drivers": ["TAM expansion", "product cycle", "recurring revenue mix", "AI adoption"],
        "risks": ["regulatory scrutiny", "competition", "talent retention", "valuation compression"],
        "multiples": ["EV/Revenue", "EV/EBITDA", "P/E"],
    },
    "Health Care": {
        "drivers": ["pipeline progression", "patent cliff exposure", "pricing power", "M&A optionality"],
        "risks": ["clinical trial failure", "generic competition", "regulatory changes", "reimbursement cuts"],
        "multiples": ["EV/EBITDA", "P/E", "EV/Revenue"],
    },
    "Financials": {
        "drivers": ["NIM expansion", "fee income growth", "credit quality", "capital return"],
        "risks": ["credit cycle", "rate sensitivity", "regulatory capital", "fintech disruption"],
        "multiples": ["P/E", "P/TBV", "ROE"],
    },
    "Consumer Discretionary": {
        "drivers": ["brand strength", "e-commerce penetration", "same-store growth", "pricing power"],
        "risks": ["consumer sentiment", "input costs", "competition", "inventory risk"],
        "multiples": ["EV/EBITDA", "P/E", "EV/Revenue"],
    },
    "Consumer Staples": {
        "drivers": ["pricing power", "volume growth", "market share", "margin expansion"],
        "risks": ["commodity costs", "private label competition", "FX exposure", "demand elasticity"],
        "multiples": ["EV/EBITDA", "P/E", "dividend yield"],
    },
    "Energy": {
        "drivers": ["commodity prices", "production growth", "capital discipline", "energy transition"],
        "risks": ["oil price volatility", "regulatory/ESG pressure", "reserve depletion", "capex overruns"],
        "multiples": ["EV/EBITDA", "P/CF", "EV/BOE"],
    },
    "Industrials": {
        "drivers": ["infrastructure spending", "order backlog", "pricing power", "automation"],
        "risks": ["cyclicality", "supply chain disruption", "raw material costs", "geopolitical"],
        "multiples": ["EV/EBITDA", "P/E", "FCF yield"],
    },
    "Materials": {
        "drivers": ["commodity prices", "volume growth", "cost optimization", "specialty mix"],
        "risks": ["commodity cycle", "environmental liability", "energy costs", "demand slowdown"],
        "multiples": ["EV/EBITDA", "P/E", "EV/ton"],
    },
    "Real Estate": {
        "drivers": ["occupancy rates", "rent growth", "development pipeline", "cap rate compression"],
        "risks": ["interest rate sensitivity", "tenant concentration", "oversupply", "remote work impact"],
        "multiples": ["P/FFO", "P/NAV", "cap rate"],
    },
    "Utilities": {
        "drivers": ["rate base growth", "renewable transition", "regulatory outcomes", "demand growth"],
        "risks": ["regulatory risk", "weather events", "capex execution", "interest rate sensitivity"],
        "multiples": ["P/E", "EV/EBITDA", "dividend yield"],
    },
    "Communication Services": {
        "drivers": ["subscriber growth", "ARPU expansion", "content investment", "advertising trends"],
        "risks": ["cord-cutting", "regulatory", "content costs", "competition"],
        "multiples": ["EV/EBITDA", "P/E", "EV/subscriber"],
    },
}

CONVICTION_THRESHOLDS: dict[int, str] = {
    25: "low",
    50: "medium",
    75: "high",
    90: "very_high",
}


# ── Dataclasses ───────────────────────────────────────────────────────


@dataclass
class InvestmentDriver:
    """A key driver for the investment thesis."""

    driver: str
    current_impact: str  # positive / negative / neutral
    timeline: str  # near_term / medium_term / long_term
    supporting_evidence: str
    key_metrics: list[str] = field(default_factory=list)


@dataclass
class InvestmentRisk:
    """A primary risk to the thesis."""

    risk: str
    severity: str  # low / medium / high / critical
    probability: float  # 0-1
    potential_impact_pct: float
    mitigation: str


@dataclass
class ValuationScenario:
    """A valuation scenario (bull / base / bear)."""

    target_price: float
    implied_return: float
    assumptions: dict
    scenarios: list[str] = field(default_factory=list)


@dataclass
class ThesisValuation:
    """Three-scenario valuation framework."""

    current_price: float
    bull: ValuationScenario
    base: ValuationScenario
    bear: ValuationScenario


@dataclass
class Catalyst:
    """A potential catalyst for the stock."""

    catalyst_type: str  # earnings / regulatory / M&A / product / macro
    description: str
    timing: str
    probability: float  # 0-1
    expected_impact: str  # positive / negative / mixed
    price_impact_pct: float | None = None


@dataclass
class ThesisQuality:
    """Quality metrics for the thesis."""

    completeness_score: float  # 0-100
    data_quality_score: float  # 0-100
    coherence_score: float  # 0-100


@dataclass
class InvestmentThesisResult:
    """Complete investment thesis output."""

    title: str
    horizon: str
    conviction: str
    summary_template: str
    drivers: list[InvestmentDriver]
    risks: list[InvestmentRisk]
    valuation: ThesisValuation
    catalysts: list[Catalyst]
    quality: ThesisQuality
    elevator_pitch: str
    slide_outline: list[dict]


# ── 1. Sector Template Selection ─────────────────────────────────────


def select_sector_template(gics_sector: str) -> dict:
    """Select the sector-specific template for thesis generation.

    Parameters
    ----------
    gics_sector : str
        GICS sector name.

    Returns
    -------
    dict
        Template with default drivers, risks, and multiples.
    """
    # Try exact match first
    if gics_sector in SECTOR_TEMPLATES:
        return SECTOR_TEMPLATES[gics_sector]

    # Try case-insensitive partial match
    sector_lower = gics_sector.lower()
    for key, template in SECTOR_TEMPLATES.items():
        if sector_lower in key.lower() or key.lower() in sector_lower:
            return template

    # Default template
    return {
        "drivers": ["revenue growth", "margin expansion", "market share", "innovation"],
        "risks": ["competition", "macro slowdown", "execution risk", "valuation"],
        "multiples": ["EV/EBITDA", "P/E"],
    }


# ── 2. Key Driver Identification ─────────────────────────────────────


def identify_key_drivers(
    financials: dict,
    transcripts: list[dict] | None,
    sector: str,
) -> list[InvestmentDriver]:
    """Identify key investment drivers from financial data and transcripts.

    Parameters
    ----------
    financials : dict
        Financial data with keys: revenue_growth, margin_trend,
        roic, fcf_growth, etc.
    transcripts : list[dict] | None
        Earnings call transcripts with 'themes' list.
    sector : str
        GICS sector for template defaults.

    Returns
    -------
    list[InvestmentDriver]
    """
    drivers: list[InvestmentDriver] = []
    template = select_sector_template(sector)

    # Revenue growth driver
    rev_growth = financials.get("revenue_growth")
    if rev_growth is not None:
        impact = "positive" if rev_growth > 5 else ("negative" if rev_growth < -2 else "neutral")
        drivers.append(InvestmentDriver(
            driver="Revenue growth trajectory",
            current_impact=impact,
            timeline="near_term",
            supporting_evidence=f"Revenue growth at {rev_growth:.1f}%",
            key_metrics=["revenue_growth", "revenue_cagr_3y"],
        ))

    # Margin trend
    margin_trend = financials.get("margin_trend")
    if margin_trend is not None:
        impact = "positive" if margin_trend > 0 else ("negative" if margin_trend < -1 else "neutral")
        drivers.append(InvestmentDriver(
            driver="Operating margin expansion",
            current_impact=impact,
            timeline="medium_term",
            supporting_evidence=f"Margin trend: {margin_trend:+.1f}pp",
            key_metrics=["operating_margin", "ebitda_margin"],
        ))

    # ROIC quality
    roic = financials.get("roic")
    if roic is not None:
        impact = "positive" if roic > 15 else ("neutral" if roic > 8 else "negative")
        drivers.append(InvestmentDriver(
            driver="Capital allocation efficiency",
            current_impact=impact,
            timeline="long_term",
            supporting_evidence=f"ROIC at {roic:.1f}%",
            key_metrics=["roic", "invested_capital"],
        ))

    # FCF generation
    fcf_growth = financials.get("fcf_growth")
    if fcf_growth is not None:
        impact = "positive" if fcf_growth > 10 else ("neutral" if fcf_growth > 0 else "negative")
        drivers.append(InvestmentDriver(
            driver="Free cash flow generation",
            current_impact=impact,
            timeline="near_term",
            supporting_evidence=f"FCF growth at {fcf_growth:.1f}%",
            key_metrics=["fcf", "fcf_margin"],
        ))

    # Add transcript-sourced drivers
    if transcripts:
        for t in transcripts[:2]:
            themes = t.get("themes", [])
            for theme in themes[:2]:
                if isinstance(theme, str) and theme not in [d.driver for d in drivers]:
                    drivers.append(InvestmentDriver(
                        driver=theme,
                        current_impact="positive",
                        timeline="medium_term",
                        supporting_evidence=f"Management commentary from {t.get('date', 'recent')} call",
                        key_metrics=[],
                    ))

    # Pad with template defaults if needed
    if len(drivers) < 3:
        for default_driver in template.get("drivers", []):
            if len(drivers) >= 4:
                break
            if default_driver not in [d.driver for d in drivers]:
                drivers.append(InvestmentDriver(
                    driver=default_driver,
                    current_impact="neutral",
                    timeline="medium_term",
                    supporting_evidence="Sector-typical driver (requires further analysis)",
                    key_metrics=[],
                ))

    return drivers[:6]


# ── 3. Risk Identification ───────────────────────────────────────────


def identify_primary_risks(
    risk_factors: list[dict],
    credit_data: dict | None,
    sector: str,
) -> list[InvestmentRisk]:
    """Identify primary risks from risk factors and credit data.

    Parameters
    ----------
    risk_factors : list[dict]
        Each has 'description', 'category', 'severity'.
    credit_data : dict | None
        Credit metrics: leverage_ratio, interest_coverage, etc.
    sector : str
        GICS sector for template defaults.

    Returns
    -------
    list[InvestmentRisk]
    """
    risks: list[InvestmentRisk] = []
    template = select_sector_template(sector)

    # Process explicit risk factors
    for rf in risk_factors[:4]:
        severity = rf.get("severity", "medium").lower()
        probability = {"low": 0.2, "medium": 0.4, "high": 0.6, "critical": 0.8}.get(severity, 0.4)
        impact = {"low": -5.0, "medium": -10.0, "high": -20.0, "critical": -30.0}.get(severity, -10.0)

        risks.append(InvestmentRisk(
            risk=rf.get("description", "Unspecified risk"),
            severity=severity,
            probability=probability,
            potential_impact_pct=impact,
            mitigation=rf.get("mitigation", "Monitor closely"),
        ))

    # Credit-specific risk
    if credit_data:
        leverage = credit_data.get("leverage_ratio", 0)
        coverage = credit_data.get("interest_coverage", 999)
        if leverage > 4.0 or coverage < 3.0:
            severity = "high" if leverage > 5.0 or coverage < 2.0 else "medium"
            risks.append(InvestmentRisk(
                risk="Elevated leverage and balance sheet risk",
                severity=severity,
                probability=0.5,
                potential_impact_pct=-15.0,
                mitigation="Debt reduction plan and refinancing strategy",
            ))

    # Pad with template defaults if too few
    if len(risks) < 3:
        for default_risk in template.get("risks", []):
            if len(risks) >= 4:
                break
            if default_risk not in [r.risk for r in risks]:
                risks.append(InvestmentRisk(
                    risk=default_risk,
                    severity="medium",
                    probability=0.3,
                    potential_impact_pct=-10.0,
                    mitigation="Standard sector risk — monitor developments",
                ))

    return risks[:6]


# ── 4. Valuation Scenarios ───────────────────────────────────────────


def build_valuation_scenarios(
    financials: dict,
    consensus: dict | None,
    sector_multiples: dict | None,
) -> ThesisValuation:
    """Build bull/base/bear valuation scenarios.

    Parameters
    ----------
    financials : dict
        Must have 'current_price', 'eps', 'ebitda'.
    consensus : dict | None
        Consensus target_price, eps_estimate.
    sector_multiples : dict | None
        Sector median pe_ratio, ev_ebitda.

    Returns
    -------
    ThesisValuation
    """
    current_price = financials.get("current_price", 100.0)
    eps = financials.get("eps", 5.0)
    ebitda = financials.get("ebitda", 1000.0)

    # Get multiples
    pe = (sector_multiples or {}).get("pe_ratio", 18.0)
    consensus_target = (consensus or {}).get("target_price", current_price * 1.1)

    # Bull case: 20% above consensus
    bull_target = round(consensus_target * 1.2, 2)
    bull_return = round((bull_target / current_price - 1) * 100, 1)

    # Base case: consensus target
    base_target = round(consensus_target, 2)
    base_return = round((base_target / current_price - 1) * 100, 1)

    # Bear case: 20% below current
    bear_target = round(current_price * 0.8, 2)
    bear_return = round((bear_target / current_price - 1) * 100, 1)

    bull = ValuationScenario(
        target_price=bull_target,
        implied_return=bull_return,
        assumptions={"pe_multiple": round(pe * 1.3, 1), "eps_growth": "above consensus"},
        scenarios=["Accelerating growth", "Multiple expansion", "Positive catalysts"],
    )

    base = ValuationScenario(
        target_price=base_target,
        implied_return=base_return,
        assumptions={"pe_multiple": pe, "eps_growth": "in line with consensus"},
        scenarios=["Steady execution", "Consensus estimates met", "Status quo"],
    )

    bear = ValuationScenario(
        target_price=bear_target,
        implied_return=bear_return,
        assumptions={"pe_multiple": round(pe * 0.7, 1), "eps_growth": "below consensus"},
        scenarios=["Earnings miss", "Multiple compression", "Macro headwinds"],
    )

    return ThesisValuation(
        current_price=current_price,
        bull=bull,
        base=base,
        bear=bear,
    )


# ── 5. Catalyst Identification ───────────────────────────────────────


def identify_catalysts(
    events: list[dict],
    earnings_dates: list[str],
    sector_events: list[dict] | None,
) -> list[Catalyst]:
    """Identify potential stock catalysts from events.

    Parameters
    ----------
    events : list[dict]
        Company events: {type, description, timing, probability}.
    earnings_dates : list[str]
        Upcoming earnings dates.
    sector_events : list[dict] | None
        Sector-wide events.

    Returns
    -------
    list[Catalyst]
    """
    catalysts: list[Catalyst] = []

    # Process company-specific events
    for ev in events[:5]:
        catalysts.append(Catalyst(
            catalyst_type=ev.get("type", "event"),
            description=ev.get("description", ""),
            timing=ev.get("timing", "TBD"),
            probability=ev.get("probability", 0.5),
            expected_impact=ev.get("impact", "positive"),
            price_impact_pct=ev.get("price_impact_pct"),
        ))

    # Add earnings dates as catalysts
    for ed in earnings_dates[:2]:
        catalysts.append(Catalyst(
            catalyst_type="earnings",
            description=f"Earnings report on {ed}",
            timing=ed,
            probability=1.0,
            expected_impact="mixed",
            price_impact_pct=None,
        ))

    # Add sector events
    if sector_events:
        for se in sector_events[:2]:
            catalysts.append(Catalyst(
                catalyst_type=se.get("type", "sector"),
                description=se.get("description", ""),
                timing=se.get("timing", "TBD"),
                probability=se.get("probability", 0.4),
                expected_impact=se.get("impact", "mixed"),
                price_impact_pct=se.get("price_impact_pct"),
            ))

    return catalysts[:8]


# ── 6. Conviction Level Computation ──────────────────────────────────


def compute_conviction_level(
    drivers: list[InvestmentDriver],
    risks: list[InvestmentRisk],
    valuation: ThesisValuation,
) -> str:
    """Compute conviction level from drivers, risks, and valuation.

    Parameters
    ----------
    drivers : list[InvestmentDriver]
    risks : list[InvestmentRisk]
    valuation : ThesisValuation

    Returns
    -------
    str
        One of: low, medium, high, very_high.
    """
    score = 50.0  # neutral start

    # Driver strength: count positive drivers
    positive_drivers = sum(1 for d in drivers if d.current_impact == "positive")
    negative_drivers = sum(1 for d in drivers if d.current_impact == "negative")
    score += positive_drivers * 8
    score -= negative_drivers * 6

    # Risk assessment: high-severity risks reduce conviction
    high_risks = sum(1 for r in risks if r.severity in ("high", "critical"))
    medium_risks = sum(1 for r in risks if r.severity == "medium")
    score -= high_risks * 10
    score -= medium_risks * 3

    # Valuation upside: base case return
    base_return = valuation.base.implied_return
    if base_return > 20:
        score += 15
    elif base_return > 10:
        score += 10
    elif base_return > 0:
        score += 5
    elif base_return < -10:
        score -= 15
    elif base_return < 0:
        score -= 5

    # Clamp 0-100
    score = max(0, min(100, score))

    # Map to conviction level
    for threshold in sorted(CONVICTION_THRESHOLDS.keys(), reverse=True):
        if score >= threshold:
            return CONVICTION_THRESHOLDS[threshold]

    return "low"


# ── 7. Thesis Quality Computation ────────────────────────────────────


def compute_thesis_quality(thesis_data: dict) -> ThesisQuality:
    """Assess the quality and completeness of thesis inputs.

    Parameters
    ----------
    thesis_data : dict
        Keys: has_financials, has_transcripts, has_filings,
        has_consensus, has_credit, driver_count, risk_count.

    Returns
    -------
    ThesisQuality
    """
    # Completeness: what data sources are available
    data_sources = [
        "has_financials", "has_transcripts", "has_filings",
        "has_consensus", "has_credit",
    ]
    available = sum(1 for s in data_sources if thesis_data.get(s))
    completeness = round((available / len(data_sources)) * 100, 1)

    # Data quality: how many drivers and risks were identified
    driver_count = thesis_data.get("driver_count", 0)
    risk_count = thesis_data.get("risk_count", 0)
    quality_inputs = []
    if driver_count >= 3:
        quality_inputs.append(100)
    elif driver_count >= 2:
        quality_inputs.append(70)
    else:
        quality_inputs.append(40)

    if risk_count >= 3:
        quality_inputs.append(100)
    elif risk_count >= 2:
        quality_inputs.append(70)
    else:
        quality_inputs.append(40)

    data_quality = round(mean(quality_inputs), 1) if quality_inputs else 50.0

    # Coherence: drivers and risks should be balanced
    if driver_count > 0 and risk_count > 0:
        ratio = min(driver_count, risk_count) / max(driver_count, risk_count)
        coherence = round(ratio * 100, 1)
    else:
        coherence = 30.0

    return ThesisQuality(
        completeness_score=completeness,
        data_quality_score=data_quality,
        coherence_score=coherence,
    )


# ── 8. Elevator Pitch Generation ─────────────────────────────────────


def generate_elevator_pitch(
    entity_name: str,
    thesis_title: str,
    drivers: list[InvestmentDriver],
    valuation: ThesisValuation,
) -> str:
    """Generate a concise elevator pitch for the thesis.

    Parameters
    ----------
    entity_name : str
    thesis_title : str
    drivers : list[InvestmentDriver]
    valuation : ThesisValuation

    Returns
    -------
    str
        Elevator pitch (max ~500 chars).
    """
    positive_drivers = [d.driver for d in drivers if d.current_impact == "positive"]
    driver_text = ", ".join(positive_drivers[:3]) if positive_drivers else "improving fundamentals"

    base_return = valuation.base.implied_return
    direction = "upside" if base_return > 0 else "downside risk"

    pitch = (
        f"{entity_name}: {thesis_title}. "
        f"Key drivers include {driver_text}. "
        f"Base case implies {abs(base_return):.0f}% {direction} "
        f"to ${valuation.base.target_price:.0f}, "
        f"with bull case at ${valuation.bull.target_price:.0f} "
        f"({valuation.bull.implied_return:+.0f}%)."
    )
    return pitch[:500]


# ── 9. Slide Outline Generation ──────────────────────────────────────


def generate_slide_outline(thesis: InvestmentThesisResult) -> list[dict]:
    """Generate a presentation slide outline from the thesis.

    Parameters
    ----------
    thesis : InvestmentThesisResult

    Returns
    -------
    list[dict]
        Each dict has 'slide_number', 'title', 'bullet_points'.
    """
    slides = [
        {
            "slide_number": 1,
            "title": f"Investment Thesis: {thesis.title}",
            "bullet_points": [
                f"Conviction: {thesis.conviction}",
                f"Horizon: {thesis.horizon}",
                thesis.elevator_pitch[:200] if thesis.elevator_pitch else "",
            ],
        },
        {
            "slide_number": 2,
            "title": "Key Investment Drivers",
            "bullet_points": [
                f"{d.driver} ({d.current_impact})" for d in thesis.drivers[:4]
            ],
        },
        {
            "slide_number": 3,
            "title": "Valuation Framework",
            "bullet_points": [
                f"Current: ${thesis.valuation.current_price:.0f}",
                f"Bull: ${thesis.valuation.bull.target_price:.0f} ({thesis.valuation.bull.implied_return:+.0f}%)",
                f"Base: ${thesis.valuation.base.target_price:.0f} ({thesis.valuation.base.implied_return:+.0f}%)",
                f"Bear: ${thesis.valuation.bear.target_price:.0f} ({thesis.valuation.bear.implied_return:+.0f}%)",
            ],
        },
        {
            "slide_number": 4,
            "title": "Primary Risks",
            "bullet_points": [
                f"{r.risk} (severity: {r.severity})" for r in thesis.risks[:4]
            ],
        },
        {
            "slide_number": 5,
            "title": "Catalysts & Timeline",
            "bullet_points": [
                f"{c.description} — {c.timing}" for c in thesis.catalysts[:4]
            ],
        },
    ]
    return slides


# ── 10. Thesis Prompt Assembly ───────────────────────────────────────


def assemble_thesis_prompt(
    entity_name: str,
    data_context: dict,
    template: dict,
) -> dict:
    """Build an LLM prompt for thesis generation.

    Parameters
    ----------
    entity_name : str
    data_context : dict
        Available data: financials, filings, transcripts summary.
    template : dict
        Sector template.

    Returns
    -------
    dict
        {system_message, user_message, template_drivers, template_risks}
    """
    system_message = (
        "You are a senior equity research analyst at Bloomberg. "
        "Generate a structured investment thesis for the given company "
        "using the provided financial data and sector template. "
        "Be specific with numbers and cite data sources."
    )

    user_message = (
        f"Company: {entity_name}\n"
        f"Sector template drivers: {template.get('drivers', [])}\n"
        f"Sector template risks: {template.get('risks', [])}\n"
        f"Financial highlights: {data_context.get('financials_summary', 'N/A')}\n"
        f"Recent filings: {data_context.get('filings_summary', 'N/A')}\n"
        f"Transcript themes: {data_context.get('transcript_themes', 'N/A')}\n"
    )

    return {
        "system_message": system_message,
        "user_message": user_message,
        "template_drivers": template.get("drivers", []),
        "template_risks": template.get("risks", []),
    }


# ── 11. Thesis Diff Computation ──────────────────────────────────────


def compute_thesis_diff(current: dict, previous: dict) -> dict:
    """Compute differences between two thesis versions.

    Parameters
    ----------
    current : dict
        Current thesis data.
    previous : dict
        Previous thesis data.

    Returns
    -------
    dict
        {changed_fields: list, conviction_change, new_drivers, removed_drivers,
         valuation_changes}
    """
    changed_fields: list[str] = []

    # Check conviction change
    cur_conviction = current.get("conviction_level", "")
    prev_conviction = previous.get("conviction_level", "")
    conviction_change = None
    if cur_conviction != prev_conviction:
        changed_fields.append("conviction_level")
        conviction_change = f"{prev_conviction} -> {cur_conviction}"

    # Check driver changes
    cur_drivers = set(d.get("driver", "") for d in current.get("drivers", []))
    prev_drivers = set(d.get("driver", "") for d in previous.get("drivers", []))
    new_drivers = sorted(cur_drivers - prev_drivers)
    removed_drivers = sorted(prev_drivers - cur_drivers)
    if new_drivers or removed_drivers:
        changed_fields.append("drivers")

    # Check valuation changes
    valuation_changes = {}
    for scenario in ("bull", "base", "bear"):
        cur_price = current.get("valuation", {}).get(scenario, {}).get("target_price")
        prev_price = previous.get("valuation", {}).get(scenario, {}).get("target_price")
        if cur_price is not None and prev_price is not None and cur_price != prev_price:
            valuation_changes[scenario] = {
                "previous": prev_price,
                "current": cur_price,
                "change_pct": round((cur_price / prev_price - 1) * 100, 1) if prev_price else 0,
            }
            if "valuation" not in changed_fields:
                changed_fields.append("valuation")

    # Check other fields
    for field in ("thesis_title", "investment_horizon", "executive_summary"):
        if current.get(field) != previous.get(field):
            changed_fields.append(field)

    return {
        "changed_fields": changed_fields,
        "conviction_change": conviction_change,
        "new_drivers": new_drivers,
        "removed_drivers": removed_drivers,
        "valuation_changes": valuation_changes,
    }


# ── 12. Full Thesis Builder ──────────────────────────────────────────


def build_investment_thesis(
    entity_data: dict,
    financials: dict,
    filings: dict,
    transcripts: list[dict] | None,
    consensus: dict | None,
) -> InvestmentThesisResult:
    """Build a complete investment thesis from all available data.

    Parameters
    ----------
    entity_data : dict
        Entity info: name, sector, industry.
    financials : dict
        Financial data.
    filings : dict
        Filing data with risk_factors list.
    transcripts : list[dict] | None
        Earnings call transcripts.
    consensus : dict | None
        Consensus estimates.

    Returns
    -------
    InvestmentThesisResult
    """
    entity_name = entity_data.get("name", "Unknown")
    sector = entity_data.get("sector", "")
    template = select_sector_template(sector)

    # Identify drivers
    drivers = identify_key_drivers(financials, transcripts, sector)

    # Identify risks
    risk_factors = filings.get("risk_factors", [])
    credit_data = financials.get("credit_data")
    risks = identify_primary_risks(risk_factors, credit_data, sector)

    # Build valuation
    sector_multiples = entity_data.get("sector_multiples")
    valuation = build_valuation_scenarios(financials, consensus, sector_multiples)

    # Identify catalysts
    events = entity_data.get("events", [])
    earnings_dates = entity_data.get("earnings_dates", [])
    sector_events = entity_data.get("sector_events")
    catalysts = identify_catalysts(events, earnings_dates, sector_events)

    # Compute conviction
    conviction = compute_conviction_level(drivers, risks, valuation)

    # Compute quality
    quality = compute_thesis_quality({
        "has_financials": bool(financials),
        "has_transcripts": bool(transcripts),
        "has_filings": bool(filings.get("risk_factors")),
        "has_consensus": bool(consensus),
        "has_credit": bool(credit_data),
        "driver_count": len(drivers),
        "risk_count": len(risks),
    })

    # Determine horizon
    horizon = entity_data.get("investment_horizon", "12M")

    # Title
    thesis_title = f"{entity_name} — {conviction.replace('_', ' ').title()} Conviction {horizon} Thesis"

    # Summary template
    summary_template = (
        f"Investment thesis for {entity_name} in the {sector or 'market'} sector. "
        f"{len(drivers)} key drivers identified with {conviction} conviction. "
        f"Base case target implies {valuation.base.implied_return:+.1f}% return."
    )

    # Elevator pitch
    elevator_pitch = generate_elevator_pitch(entity_name, thesis_title, drivers, valuation)

    thesis = InvestmentThesisResult(
        title=thesis_title,
        horizon=horizon,
        conviction=conviction,
        summary_template=summary_template,
        drivers=drivers,
        risks=risks,
        valuation=valuation,
        catalysts=catalysts,
        quality=quality,
        elevator_pitch=elevator_pitch,
        slide_outline=[],
    )

    # Generate slide outline
    thesis.slide_outline = generate_slide_outline(thesis)

    return thesis
