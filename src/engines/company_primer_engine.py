"""Pillar 3 Phase 4A — Company Primer Engine.

Pure computation engine for assembling company research primers.
Extracts business model profiles, competitive landscape, financial health,
strategic initiatives, risk factors, and catalyst calendars from raw data,
then builds structured LLM prompts for primer generation.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field


# ── Dataclasses ───────────────────────────────────────────────────────────


@dataclass
class BusinessModelProfile:
    """Core business model characteristics."""

    revenue_streams: list[str] = field(default_factory=list)
    customer_segments: list[str] = field(default_factory=list)
    geographic_exposure: list[str] = field(default_factory=list)
    key_partnerships: list[str] = field(default_factory=list)


@dataclass
class CompetitiveLandscapeProfile:
    """Competitive positioning among peers."""

    direct_competitors: list[str] = field(default_factory=list)
    competitive_advantages: list[str] = field(default_factory=list)
    market_position: str = "niche"  # leader / challenger / niche


@dataclass
class FinancialHealthSnapshot:
    """Point-in-time financial health metrics."""

    revenue_ttm: float = 0.0
    gross_margin: float = 0.0
    operating_margin: float = 0.0
    net_margin: float | None = None
    net_debt_to_ebitda: float | None = None
    fcf_margin: float | None = None


@dataclass
class StrategicInitiative:
    """A strategic initiative extracted from filings / guidance."""

    name: str = ""
    description: str = ""
    timeline: str = ""
    potential_impact: str = "medium"  # high / medium / low


@dataclass
class RiskFactor:
    """A categorized risk factor."""

    category: str = "operational"  # regulatory / competitive / operational / market
    description: str = ""
    severity: str = "medium"  # critical / high / medium / low
    mitigation_status: str = ""


@dataclass
class CatalystEvent:
    """An upcoming or recent catalyst event."""

    date: str = ""
    event: str = ""
    market_reaction_pct: float | None = None
    strategic_significance: str = "medium"  # high / medium / low


@dataclass
class PromptContext:
    """Structured LLM prompt context for primer generation."""

    entity_name: str = ""
    system_prompt: str = ""
    user_prompt: str = ""
    data_context: dict = field(default_factory=dict)


@dataclass
class CompanyPrimerResult:
    """Complete company primer assembly result."""

    entity_name: str = ""
    business_model: BusinessModelProfile = field(default_factory=BusinessModelProfile)
    competitive: CompetitiveLandscapeProfile = field(
        default_factory=CompetitiveLandscapeProfile,
    )
    financial_health: FinancialHealthSnapshot = field(
        default_factory=FinancialHealthSnapshot,
    )
    initiatives: list[StrategicInitiative] = field(default_factory=list)
    risks: list[RiskFactor] = field(default_factory=list)
    catalysts: list[CatalystEvent] = field(default_factory=list)
    data_completeness: float = 0.0
    prompt_context: PromptContext | None = None


# ── Constants ─────────────────────────────────────────────────────────────

_RISK_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "regulatory": [
        "regulat", "compliance", "legislation", "government", "legal",
        "antitrust", "sanction", "tax", "policy",
    ],
    "competitive": [
        "compet", "market share", "pricing pressure", "disruption",
        "substitute", "new entrant",
    ],
    "operational": [
        "supply chain", "cyber", "talent", "execution", "technology",
        "infrastructure", "operational",
    ],
    "market": [
        "macroeconomic", "interest rate", "currency", "inflation",
        "recession", "geopolit", "trade war",
    ],
}

_SEVERITY_KEYWORDS: dict[str, list[str]] = {
    "critical": ["material", "significant adverse", "critical", "existential"],
    "high": ["substantial", "major", "significant", "adverse"],
    "medium": ["moderate", "may", "could", "potential"],
    "low": ["minor", "limited", "unlikely", "immaterial"],
}

_IMPACT_KEYWORDS: dict[str, list[str]] = {
    "high": [
        "transform", "significant", "major", "strategic shift",
        "acquisition", "restructur",
    ],
    "medium": ["expansion", "launch", "partnership", "initiative"],
    "low": ["minor", "incremental", "routine", "update"],
}


# ── 1. Extract Business Model ────────────────────────────────────────────


def extract_business_model(
    filing_data: dict,
    segment_data: dict | None,
) -> BusinessModelProfile:
    """Extract business model profile from filing and segment data.

    Parameters
    ----------
    filing_data : dict
        Keys: revenue_streams (list[str]), customer_segments (list[str]),
        key_partnerships (list[str]), business_description (str).
    segment_data : dict | None
        Keys: geographic (list[str]), product_segments (list[str]).
    """
    revenue_streams = list(filing_data.get("revenue_streams", []))
    customer_segments = list(filing_data.get("customer_segments", []))
    key_partnerships = list(filing_data.get("key_partnerships", []))
    geographic_exposure: list[str] = []

    if segment_data:
        geographic_exposure = list(segment_data.get("geographic", []))
        # Supplement revenue streams from product segments if available
        for seg in segment_data.get("product_segments", []):
            if seg and seg not in revenue_streams:
                revenue_streams.append(seg)

    return BusinessModelProfile(
        revenue_streams=revenue_streams,
        customer_segments=customer_segments,
        geographic_exposure=geographic_exposure,
        key_partnerships=key_partnerships,
    )


# ── 2. Extract Competitive Landscape ─────────────────────────────────────


def extract_competitive_landscape(
    company_data: dict,
    peer_data: list[dict],
) -> CompetitiveLandscapeProfile:
    """Derive competitive positioning by comparing to peers.

    Parameters
    ----------
    company_data : dict
        Keys: market_cap (float), revenue (float), revenue_growth_pct (float),
        operating_margin (float), competitive_advantages (list[str]).
    peer_data : list[dict]
        Each peer: name (str), market_cap (float), revenue (float),
        revenue_growth_pct (float), operating_margin (float).
    """
    direct_competitors = [p.get("name", "") for p in peer_data if p.get("name")]
    competitive_advantages = list(company_data.get("competitive_advantages", []))

    # Classify market position based on market cap rank among peers
    company_mcap = company_data.get("market_cap", 0.0)
    company_rev = company_data.get("revenue", 0.0)
    company_margin = company_data.get("operating_margin", 0.0)

    if not peer_data:
        position = "niche"
    else:
        peer_mcaps = [p.get("market_cap", 0.0) for p in peer_data]
        peer_revs = [p.get("revenue", 0.0) for p in peer_data]

        # Leader: largest market cap AND above-median revenue
        larger_mcap_count = sum(1 for mc in peer_mcaps if mc > company_mcap)

        total_peers = len(peer_data)
        if larger_mcap_count == 0:
            position = "leader"
        elif larger_mcap_count <= total_peers * 0.35:
            position = "leader"
        elif larger_mcap_count < total_peers:
            position = "challenger"
        else:
            position = "niche"

        # Margin-based advantages
        if peer_revs:
            avg_peer_margin = sum(
                p.get("operating_margin", 0.0) for p in peer_data
            ) / len(peer_data)
            if company_margin > avg_peer_margin + 5.0:
                if "Superior margins" not in competitive_advantages:
                    competitive_advantages.append("Superior margins")

        # Growth-based advantages
        company_growth = company_data.get("revenue_growth_pct", 0.0)
        if peer_data:
            avg_peer_growth = sum(
                p.get("revenue_growth_pct", 0.0) for p in peer_data
            ) / len(peer_data)
            if company_growth > avg_peer_growth + 5.0:
                if "Above-peer growth" not in competitive_advantages:
                    competitive_advantages.append("Above-peer growth")

    return CompetitiveLandscapeProfile(
        direct_competitors=direct_competitors,
        competitive_advantages=competitive_advantages,
        market_position=position,
    )


# ── 3. Compute Financial Health ──────────────────────────────────────────


def compute_financial_health(financials: dict) -> FinancialHealthSnapshot:
    """Calculate financial health snapshot from raw financial data.

    Parameters
    ----------
    financials : dict
        Keys: revenue_ttm (float), cost_of_revenue (float),
        operating_income (float), net_income (float | None),
        total_debt (float | None), cash (float | None),
        ebitda (float | None), free_cash_flow (float | None).
    """
    revenue_ttm = financials.get("revenue_ttm", 0.0)

    # Gross margin
    cost_of_revenue = financials.get("cost_of_revenue", 0.0)
    gross_margin = 0.0
    if revenue_ttm > 0:
        gross_margin = round((revenue_ttm - cost_of_revenue) / revenue_ttm, 4)

    # Operating margin
    operating_income = financials.get("operating_income", 0.0)
    operating_margin = 0.0
    if revenue_ttm > 0:
        operating_margin = round(operating_income / revenue_ttm, 4)

    # Net margin
    net_income = financials.get("net_income")
    net_margin = None
    if net_income is not None and revenue_ttm > 0:
        net_margin = round(net_income / revenue_ttm, 4)

    # Net debt / EBITDA
    net_debt_to_ebitda = None
    total_debt = financials.get("total_debt")
    cash = financials.get("cash", 0.0)
    ebitda = financials.get("ebitda")
    if total_debt is not None and ebitda and ebitda > 0:
        net_debt = total_debt - (cash or 0.0)
        net_debt_to_ebitda = round(net_debt / ebitda, 2)

    # FCF margin
    fcf = financials.get("free_cash_flow")
    fcf_margin = None
    if fcf is not None and revenue_ttm > 0:
        fcf_margin = round(fcf / revenue_ttm, 4)

    return FinancialHealthSnapshot(
        revenue_ttm=revenue_ttm,
        gross_margin=gross_margin,
        operating_margin=operating_margin,
        net_margin=net_margin,
        net_debt_to_ebitda=net_debt_to_ebitda,
        fcf_margin=fcf_margin,
    )


# ── 4. Extract Strategic Initiatives ─────────────────────────────────────


def _classify_impact(text: str) -> str:
    """Classify potential impact from text keywords."""
    text_lower = text.lower()
    for level in ("high", "medium", "low"):
        for kw in _IMPACT_KEYWORDS[level]:
            if kw in text_lower:
                return level
    return "medium"


def extract_strategic_initiatives(
    eight_k_events: list[dict],
    guidance: dict | None,
) -> list[StrategicInitiative]:
    """Extract strategic initiatives from 8-K events and guidance.

    Parameters
    ----------
    eight_k_events : list[dict]
        Each event: title (str), description (str), date (str),
        event_type (str).
    guidance : dict | None
        Keys: initiatives (list[dict]) where each has name, description,
        timeline, potential_impact.
    """
    initiatives: list[StrategicInitiative] = []

    # From 8-K events: filter for strategic events
    strategic_types = {
        "acquisition", "divestiture", "restructuring", "new_product",
        "partnership", "leadership_change", "strategic",
    }
    for event in eight_k_events:
        event_type = event.get("event_type", "").lower()
        title = event.get("title", "")
        desc = event.get("description", "")

        if event_type in strategic_types or _classify_impact(title + " " + desc) == "high":
            initiatives.append(StrategicInitiative(
                name=title,
                description=desc,
                timeline=event.get("date", ""),
                potential_impact=_classify_impact(title + " " + desc),
            ))

    # From guidance
    if guidance:
        for item in guidance.get("initiatives", []):
            initiatives.append(StrategicInitiative(
                name=item.get("name", ""),
                description=item.get("description", ""),
                timeline=item.get("timeline", ""),
                potential_impact=item.get("potential_impact", "medium"),
            ))

    return initiatives


# ── 5. Extract Risk Factors ──────────────────────────────────────────────


def _classify_risk_category(text: str) -> str:
    """Classify a risk factor into a category based on keywords."""
    text_lower = text.lower()
    best_category = "operational"
    best_hits = 0
    for category, keywords in _RISK_CATEGORY_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in text_lower)
        if hits > best_hits:
            best_hits = hits
            best_category = category
    return best_category


def _classify_severity(text: str) -> str:
    """Classify severity from risk description text."""
    text_lower = text.lower()
    for level in ("critical", "high", "medium", "low"):
        for kw in _SEVERITY_KEYWORDS[level]:
            if kw in text_lower:
                return level
    return "medium"


def extract_risk_factors(
    filing_risks: list[dict],
    credit_data: dict | None,
) -> list[RiskFactor]:
    """Categorize and rank risk factors by severity.

    Parameters
    ----------
    filing_risks : list[dict]
        Each risk: description (str), category (str | None),
        severity (str | None), mitigation (str | None).
    credit_data : dict | None
        Keys: credit_rating (str), outlook (str), watchlist (bool),
        credit_risks (list[dict]).
    """
    risks: list[RiskFactor] = []

    for risk in filing_risks:
        desc = risk.get("description", "")
        category = risk.get("category") or _classify_risk_category(desc)
        severity = risk.get("severity") or _classify_severity(desc)
        mitigation = risk.get("mitigation", "")

        risks.append(RiskFactor(
            category=category,
            description=desc,
            severity=severity,
            mitigation_status=mitigation,
        ))

    # Augment with credit risks
    if credit_data:
        for cr in credit_data.get("credit_risks", []):
            risks.append(RiskFactor(
                category="market",
                description=cr.get("description", ""),
                severity=cr.get("severity", "medium"),
                mitigation_status=cr.get("mitigation", ""),
            ))

        # Watchlist adds a special risk
        if credit_data.get("watchlist"):
            risks.append(RiskFactor(
                category="market",
                description=(
                    f"Credit watchlist: rating {credit_data.get('credit_rating', 'N/A')}, "
                    f"outlook {credit_data.get('outlook', 'N/A')}"
                ),
                severity="high",
                mitigation_status="monitoring",
            ))

    # Sort by severity: critical > high > medium > low
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    risks.sort(key=lambda r: severity_order.get(r.severity, 2))

    return risks


# ── 6. Build Catalyst Calendar ───────────────────────────────────────────


def build_catalyst_calendar(
    events: list[dict],
    earnings_dates: list[str],
) -> list[CatalystEvent]:
    """Build upcoming catalyst timeline from events and earnings dates.

    Parameters
    ----------
    events : list[dict]
        Each event: date (str), event (str), market_reaction_pct (float | None),
        strategic_significance (str | None).
    earnings_dates : list[str]
        Upcoming earnings dates as strings.
    """
    catalysts: list[CatalystEvent] = []

    for evt in events:
        catalysts.append(CatalystEvent(
            date=evt.get("date", ""),
            event=evt.get("event", ""),
            market_reaction_pct=evt.get("market_reaction_pct"),
            strategic_significance=evt.get("strategic_significance", "medium"),
        ))

    # Add earnings dates as high-significance catalysts
    for ed in earnings_dates:
        catalysts.append(CatalystEvent(
            date=ed,
            event="Earnings Release",
            market_reaction_pct=None,
            strategic_significance="high",
        ))

    # Sort by date string (ISO format expected)
    catalysts.sort(key=lambda c: c.date)

    return catalysts


# ── 7. Compute Data Completeness ─────────────────────────────────────────


def compute_data_completeness(primer_data: dict) -> float:
    """Compute data completeness score (0-100).

    Each major section is worth 20 points:
    - business_model (20): revenue_streams, customer_segments, geographic
    - financial (20): revenue_ttm, margins, leverage
    - competitive (20): competitors, advantages, position
    - risks (20): at least one risk factor
    - catalysts (20): at least one catalyst event
    """
    score = 0.0

    # Business model section (20 pts)
    bm = primer_data.get("business_model", {})
    if bm.get("revenue_streams"):
        score += 7.0
    if bm.get("customer_segments"):
        score += 5.0
    if bm.get("geographic_exposure"):
        score += 5.0
    if bm.get("key_partnerships"):
        score += 3.0

    # Financial section (20 pts)
    fin = primer_data.get("financial_health", {})
    if fin.get("revenue_ttm", 0) > 0:
        score += 5.0
    if fin.get("gross_margin", 0) > 0:
        score += 4.0
    if fin.get("operating_margin", 0) != 0:
        score += 4.0
    if fin.get("net_margin") is not None:
        score += 3.0
    if fin.get("net_debt_to_ebitda") is not None:
        score += 2.0
    if fin.get("fcf_margin") is not None:
        score += 2.0

    # Competitive section (20 pts)
    comp = primer_data.get("competitive", {})
    if comp.get("direct_competitors"):
        score += 8.0
    if comp.get("competitive_advantages"):
        score += 7.0
    if comp.get("market_position") and comp["market_position"] != "niche":
        score += 5.0
    elif comp.get("market_position"):
        score += 3.0

    # Risks section (20 pts)
    risks = primer_data.get("risks", [])
    if risks:
        score += min(len(risks) * 4.0, 20.0)

    # Catalysts section (20 pts)
    catalysts = primer_data.get("catalysts", [])
    if catalysts:
        score += min(len(catalysts) * 5.0, 20.0)

    return min(round(score, 1), 100.0)


# ── 8. Assemble Primer Prompt ────────────────────────────────────────────


def assemble_primer_prompt(
    entity_name: str,
    filing_text: str,
    transcript: str | None,
    news: list[dict],
    peer_data: list[dict],
) -> PromptContext:
    """Build a structured LLM prompt with all data context.

    Parameters
    ----------
    entity_name : str
        Company name or ticker.
    filing_text : str
        Raw filing text (10-K, 10-Q excerpt).
    transcript : str | None
        Earnings call transcript excerpt.
    news : list[dict]
        Recent news items: headline, date, source.
    peer_data : list[dict]
        Peer comparison data.
    """
    system_prompt = (
        "You are a senior equity research analyst. Generate a comprehensive "
        "company research primer that covers business model, competitive "
        "positioning, financial health, strategic initiatives, key risks, "
        "and upcoming catalysts. Be concise, data-driven, and actionable."
    )

    # Build data context
    news_summary = []
    for n in news[:10]:  # Limit to 10 most recent
        news_summary.append({
            "headline": n.get("headline", ""),
            "date": n.get("date", ""),
            "source": n.get("source", ""),
        })

    peer_summary = []
    for p in peer_data[:10]:
        peer_summary.append({
            "name": p.get("name", ""),
            "market_cap": p.get("market_cap"),
            "revenue": p.get("revenue"),
        })

    data_context = {
        "filing_excerpt": filing_text[:5000] if filing_text else "",
        "transcript_excerpt": (transcript[:3000] if transcript else ""),
        "recent_news": news_summary,
        "peer_comparison": peer_summary,
    }

    user_prompt = (
        f"Generate a research primer for {entity_name}. "
        f"Use the provided filing data, "
        f"{'earnings transcript, ' if transcript else ''}"
        f"recent news, and peer comparison data. "
        f"Structure your analysis into: "
        f"1) Business Model Overview, "
        f"2) Competitive Positioning, "
        f"3) Financial Health Assessment, "
        f"4) Strategic Initiatives, "
        f"5) Key Risk Factors, "
        f"6) Catalyst Calendar."
    )

    return PromptContext(
        entity_name=entity_name,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        data_context=data_context,
    )


# ── 9. Parse Primer Response ─────────────────────────────────────────────


def parse_primer_response(llm_response: str) -> dict:
    """Parse a JSON or structured text LLM response into a primer dict.

    Handles common LLM output quirks: markdown code blocks, trailing
    commas, unquoted keys (best-effort).

    Parameters
    ----------
    llm_response : str
        Raw LLM output text.

    Returns
    -------
    dict
        Parsed primer data, or {"raw_text": llm_response, "parse_error": ...}
        on failure.
    """
    text = llm_response.strip()

    # Strip markdown code blocks
    if text.startswith("```"):
        # Remove opening ```json or ```
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)

    # Try direct JSON parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try removing trailing commas before } or ]
    cleaned = re.sub(r",\s*([}\]])", r"\1", text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in the text
    json_match = re.search(r"\{[\s\S]*\}", text)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

        # Last resort: clean trailing commas in extracted block
        cleaned_block = re.sub(r",\s*([}\]])", r"\1", json_match.group())
        try:
            return json.loads(cleaned_block)
        except json.JSONDecodeError:
            pass

    return {"raw_text": llm_response, "parse_error": "Could not parse LLM response as JSON"}


# ── 10. Build Company Primer (Orchestrator) ──────────────────────────────


def build_company_primer(
    entity_data: dict,
    filings: dict,
    transcripts: list[dict] | None,
    news: list[dict],
    peers: list[dict],
) -> CompanyPrimerResult:
    """Full orchestrator: assemble a complete company primer.

    Parameters
    ----------
    entity_data : dict
        Company-level data: name (str), market_cap (float), revenue (float),
        revenue_growth_pct (float), operating_margin (float),
        competitive_advantages (list[str]).
    filings : dict
        Filing data: revenue_streams, customer_segments, key_partnerships,
        segment_data (dict with geographic, product_segments),
        financial_data (dict for compute_financial_health),
        risks (list[dict]), eight_k_events (list[dict]),
        guidance (dict | None), filing_text (str).
    transcripts : list[dict] | None
        Earnings transcripts: text (str), date (str).
    news : list[dict]
        News items: headline, date, source, impact, affected_tickers.
    peers : list[dict]
        Peer data for competitive analysis.
    """
    entity_name = entity_data.get("name", "Unknown")

    # 1. Business model
    business_model = extract_business_model(
        filing_data=filings,
        segment_data=filings.get("segment_data"),
    )

    # 2. Competitive landscape
    competitive = extract_competitive_landscape(
        company_data=entity_data,
        peer_data=peers,
    )

    # 3. Financial health
    financial_health = compute_financial_health(
        filings.get("financial_data", {}),
    )

    # 4. Strategic initiatives
    initiatives = extract_strategic_initiatives(
        eight_k_events=filings.get("eight_k_events", []),
        guidance=filings.get("guidance"),
    )

    # 5. Risk factors
    risks = extract_risk_factors(
        filing_risks=filings.get("risks", []),
        credit_data=filings.get("credit_data"),
    )

    # 6. Catalyst calendar
    catalysts = build_catalyst_calendar(
        events=filings.get("catalyst_events", []),
        earnings_dates=filings.get("earnings_dates", []),
    )

    # 7. Data completeness
    primer_dict = {
        "business_model": {
            "revenue_streams": business_model.revenue_streams,
            "customer_segments": business_model.customer_segments,
            "geographic_exposure": business_model.geographic_exposure,
            "key_partnerships": business_model.key_partnerships,
        },
        "financial_health": {
            "revenue_ttm": financial_health.revenue_ttm,
            "gross_margin": financial_health.gross_margin,
            "operating_margin": financial_health.operating_margin,
            "net_margin": financial_health.net_margin,
            "net_debt_to_ebitda": financial_health.net_debt_to_ebitda,
            "fcf_margin": financial_health.fcf_margin,
        },
        "competitive": {
            "direct_competitors": competitive.direct_competitors,
            "competitive_advantages": competitive.competitive_advantages,
            "market_position": competitive.market_position,
        },
        "risks": [{"description": r.description, "severity": r.severity} for r in risks],
        "catalysts": [{"date": c.date, "event": c.event} for c in catalysts],
    }
    data_completeness = compute_data_completeness(primer_dict)

    # 8. Prompt context
    transcript_text = None
    if transcripts:
        transcript_text = transcripts[0].get("text", "")

    prompt_context = assemble_primer_prompt(
        entity_name=entity_name,
        filing_text=filings.get("filing_text", ""),
        transcript=transcript_text,
        news=news,
        peer_data=peers,
    )

    return CompanyPrimerResult(
        entity_name=entity_name,
        business_model=business_model,
        competitive=competitive,
        financial_health=financial_health,
        initiatives=initiatives,
        risks=risks,
        catalysts=catalysts,
        data_completeness=data_completeness,
        prompt_context=prompt_context,
    )
