"""Pillar 3 Phase 3B — Global Intelligence: Political Intelligence Engine.

Pure computation engine for political and policy analysis.
Assesses bill passage probability, sector impact, regulatory severity,
sanctions exposure, policy momentum, and regulatory pipeline tracking.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ── Constants ──────────────────────────────────────────────────────────

BILL_TYPE_SECTOR_MAP: dict[str, list[str]] = {
    "TAX": ["ALL"],
    "TRADE": ["INDUSTRIALS", "MATERIALS", "CONSUMER_STAPLES"],
    "HEALTHCARE_REGULATION": ["HEALTH_CARE"],
    "TECH_REGULATION": ["INFORMATION_TECHNOLOGY", "COMMUNICATION_SERVICES"],
    "ENERGY_POLICY": ["ENERGY", "UTILITIES"],
    "FINANCIAL_REGULATION": ["FINANCIALS"],
    "DEFENSE": ["INDUSTRIALS"],
}

SEVERITY_SCORES: dict[str, int] = {
    "INQUIRY": 10,
    "INVESTIGATION": 30,
    "ENFORCEMENT": 60,
    "SETTLEMENT": 50,
    "FINE": 70,
    "RULEMAKING": 40,
}

STATUS_WEIGHTS: dict[str, float] = {
    "INTRODUCED": 0.1,
    "COMMITTEE": 0.2,
    "PASSED_HOUSE": 0.4,
    "PASSED_SENATE": 0.5,
    "SIGNED": 1.0,
    "VETOED": 0.0,
}

# Keyword to sector mapping used for title/summary scanning
_KEYWORD_SECTOR_MAP: dict[str, str] = {
    "health": "HEALTH_CARE",
    "pharma": "HEALTH_CARE",
    "drug": "HEALTH_CARE",
    "hospital": "HEALTH_CARE",
    "medicare": "HEALTH_CARE",
    "medicaid": "HEALTH_CARE",
    "tech": "INFORMATION_TECHNOLOGY",
    "data privacy": "INFORMATION_TECHNOLOGY",
    "artificial intelligence": "INFORMATION_TECHNOLOGY",
    "ai regulation": "INFORMATION_TECHNOLOGY",
    "social media": "COMMUNICATION_SERVICES",
    "telecom": "COMMUNICATION_SERVICES",
    "bank": "FINANCIALS",
    "insurance": "FINANCIALS",
    "crypto": "FINANCIALS",
    "oil": "ENERGY",
    "gas": "ENERGY",
    "renewable": "ENERGY",
    "solar": "ENERGY",
    "wind": "ENERGY",
    "electric vehicle": "ENERGY",
    "carbon": "ENERGY",
    "emission": "ENERGY",
    "utility": "UTILITIES",
    "grid": "UTILITIES",
    "defense": "INDUSTRIALS",
    "military": "INDUSTRIALS",
    "trade": "INDUSTRIALS",
    "tariff": "INDUSTRIALS",
    "agriculture": "CONSUMER_STAPLES",
    "food": "CONSUMER_STAPLES",
}


# ── Dataclasses ────────────────────────────────────────────────────────

@dataclass
class BillAssessment:
    """Full assessment of a legislative bill."""
    bill_id: str
    title: str
    passage_probability: float  # 0-100
    affected_sectors: list[dict]  # [{gics_code, sector_name, direction, magnitude}]
    status_stage: str
    market_relevance: str  # HIGH / MEDIUM / LOW


@dataclass
class RegulatoryImpact:
    """Assessment of a single regulatory action."""
    agency: str
    action_type: str
    severity_score: float  # 0-100
    affected_sectors: list[str]
    financial_impact_estimate: float | None
    precedent_assessment: str  # NOVEL / ROUTINE / ESCALATION


@dataclass
class SanctionsAssessment:
    """Assessment of sanctions exposure for a country."""
    country_code: str
    program_count: int
    total_companies_affected: int
    most_exposed_sectors: list[str]
    trajectory: str  # ESCALATING / STABLE / DE_ESCALATING
    enforcement_intensity: str  # STRICT / MODERATE / LENIENT


# ── 1. Assess bill passage probability ───────────────────────────────

def assess_bill_passage_probability(
    sponsor_count: int,
    committee_status: str,
    bipartisan: bool,
    historical_rate: float | None = None,
) -> float:
    """Estimate probability (0-100) that a bill passes.

    Scoring
    -------
    - Base from ``STATUS_WEIGHTS`` mapped to 0-100.
    - Each sponsor adds ~0.5 percentage point (capped at +25).
    - Bipartisan bonus: +15 points.
    - If *historical_rate* is given, blend with computed score (30% weight).
    """
    base_weight = STATUS_WEIGHTS.get(committee_status.upper(), 0.1)
    score = base_weight * 100.0

    # Sponsor boost — each sponsor adds 0.5%, capped at +25
    sponsor_boost = min(25.0, sponsor_count * 0.5)
    score += sponsor_boost

    # Bipartisan bonus
    if bipartisan:
        score += 15.0

    # Blend with historical rate if available
    if historical_rate is not None:
        score = score * 0.7 + historical_rate * 0.3

    return round(min(100.0, max(0.0, score)), 2)


# ── 2. Classify bill sector impact ──────────────────────────────────

def classify_bill_sector_impact(
    bill_type: str,
    title: str,
    summary: str | None = None,
) -> list[dict]:
    """Map a bill to affected GICS sectors.

    Uses ``BILL_TYPE_SECTOR_MAP`` for the primary mapping, then scans
    *title* and *summary* for additional keyword-based sector matches.

    Returns
    -------
    list[dict]  — each: {sector_name, direction, magnitude}.
    """
    sectors_seen: set[str] = set()
    results: list[dict] = []

    # Primary mapping from bill type
    mapped = BILL_TYPE_SECTOR_MAP.get(bill_type.upper(), [])
    for sector in mapped:
        if sector not in sectors_seen:
            sectors_seen.add(sector)
            results.append({
                "sector_name": sector,
                "direction": "MIXED",
                "magnitude": "MEDIUM",
            })

    # Keyword scan on title + summary
    text = (title or "").lower()
    if summary:
        text += " " + summary.lower()

    for keyword, sector in _KEYWORD_SECTOR_MAP.items():
        if keyword in text and sector not in sectors_seen:
            sectors_seen.add(sector)
            results.append({
                "sector_name": sector,
                "direction": "MIXED",
                "magnitude": "LOW",
            })

    return results


# ── 3. Assess bill market relevance ─────────────────────────────────

def assess_bill_market_relevance(
    passage_probability: float,
    affected_sector_count: int,
) -> str:
    """Classify market relevance of a bill.

    - **HIGH** — probability > 40% AND affects > 2 sectors.
    - **LOW** — probability < 15%.
    - **MEDIUM** — everything else.
    """
    if passage_probability < 15.0:
        return "LOW"
    if passage_probability > 40.0 and affected_sector_count > 2:
        return "HIGH"
    return "MEDIUM"


# ── 4. Assess bill (orchestrator) ────────────────────────────────────

def assess_bill(
    bill_id: str,
    title: str,
    bill_type: str,
    sponsor_count: int,
    status: str,
    bipartisan: bool,
    summary: str | None = None,
) -> BillAssessment:
    """Full bill assessment combining probability, sector impact, relevance."""
    probability = assess_bill_passage_probability(
        sponsor_count=sponsor_count,
        committee_status=status,
        bipartisan=bipartisan,
    )
    affected = classify_bill_sector_impact(bill_type, title, summary)
    relevance = assess_bill_market_relevance(probability, len(affected))

    return BillAssessment(
        bill_id=bill_id,
        title=title,
        passage_probability=probability,
        affected_sectors=affected,
        status_stage=status,
        market_relevance=relevance,
    )


# ── 5. Classify regulatory severity ─────────────────────────────────

def classify_regulatory_severity(
    action_type: str,
    financial_impact: float | None = None,
) -> float:
    """Return a 0-100 severity score for a regulatory action.

    Base score from ``SEVERITY_SCORES``.  Financial impact adds up to +20:
    - >= $1B → +20
    - >= $100M → +15
    - >= $10M → +10
    - >= $1M → +5
    """
    base = SEVERITY_SCORES.get(action_type.upper(), 20)
    boost = 0.0

    if financial_impact is not None:
        if financial_impact >= 1_000_000_000:
            boost = 20.0
        elif financial_impact >= 100_000_000:
            boost = 15.0
        elif financial_impact >= 10_000_000:
            boost = 10.0
        elif financial_impact >= 1_000_000:
            boost = 5.0

    return round(min(100.0, base + boost), 2)


# ── 6. Assess regulatory precedent ──────────────────────────────────

def assess_regulatory_precedent(
    agency: str,
    action_type: str,
    prior_actions: list[dict] | None = None,
) -> str:
    """Classify a regulatory action as NOVEL, ESCALATION, or ROUTINE.

    Parameters
    ----------
    agency : str
    action_type : str
    prior_actions : list[dict] | None
        Each: {agency, action_type, severity_score, ...}.

    Logic
    -----
    - **NOVEL** — no prior actions from this agency of this type.
    - **ESCALATION** — current severity exceeds the max prior severity.
    - **ROUTINE** — otherwise.
    """
    if not prior_actions:
        return "NOVEL"

    # Filter priors to same agency
    same_agency = [a for a in prior_actions if a.get("agency") == agency]
    if not same_agency:
        return "NOVEL"

    # Check if this action type has been seen before
    same_type = [a for a in same_agency if a.get("action_type") == action_type]
    if not same_type:
        return "NOVEL"

    # Compare severity
    current_severity = SEVERITY_SCORES.get(action_type.upper(), 20)
    max_prior = max(
        (a.get("severity_score", 0) for a in same_type),
        default=0,
    )

    if current_severity > max_prior:
        return "ESCALATION"
    return "ROUTINE"


# ── 7. Assess regulatory impact (orchestrator) ──────────────────────

def assess_regulatory_impact(
    agency: str,
    action_type: str,
    title: str,
    financial_impact: float | None,
    prior_actions: list[dict] | None,
) -> RegulatoryImpact:
    """Full assessment of a regulatory action."""
    severity = classify_regulatory_severity(action_type, financial_impact)
    precedent = assess_regulatory_precedent(agency, action_type, prior_actions)

    # Derive affected sectors from title keywords
    affected: list[str] = []
    title_lower = (title or "").lower()
    for keyword, sector in _KEYWORD_SECTOR_MAP.items():
        if keyword in title_lower and sector not in affected:
            affected.append(sector)

    # Fallback — use agency heuristic
    if not affected:
        agency_sector_map = {
            "SEC": "FINANCIALS",
            "CFTC": "FINANCIALS",
            "FDA": "HEALTH_CARE",
            "EPA": "ENERGY",
            "FTC": "INFORMATION_TECHNOLOGY",
            "FCC": "COMMUNICATION_SERVICES",
            "DOJ": "ALL",
        }
        fallback = agency_sector_map.get(agency.upper())
        if fallback:
            affected.append(fallback)

    return RegulatoryImpact(
        agency=agency,
        action_type=action_type,
        severity_score=severity,
        affected_sectors=affected,
        financial_impact_estimate=financial_impact,
        precedent_assessment=precedent,
    )


# ── 8. Assess sanctions impact ──────────────────────────────────────

def assess_sanctions_impact(
    country_code: str,
    active_sanctions: list[dict],
    company_exposures: list[dict],
) -> SanctionsAssessment:
    """Evaluate sanctions exposure for a given country.

    Parameters
    ----------
    country_code : str
    active_sanctions : list[dict]
        Each: {program_name, severity, date_imposed, ...}.
    company_exposures : list[dict]
        Each: {entity_id, entity_name, sector, revenue_exposure_pct, ...}.
    """
    program_count = len(active_sanctions)

    # Count affected companies (those with any revenue exposure)
    affected = [
        c for c in company_exposures
        if (c.get("revenue_exposure_pct") or 0) > 0
    ]
    total_affected = len(affected)

    # Most exposed sectors
    sector_counts: dict[str, int] = {}
    for c in affected:
        sector = c.get("sector", "UNKNOWN")
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
    sorted_sectors = sorted(sector_counts.items(), key=lambda x: -x[1])
    most_exposed = [s[0] for s in sorted_sectors[:5]]

    # Trajectory — based on sanction dates if available
    trajectory = _compute_sanctions_trajectory(active_sanctions)

    # Enforcement intensity — based on severity distribution
    enforcement = _compute_enforcement_intensity(active_sanctions)

    return SanctionsAssessment(
        country_code=country_code,
        program_count=program_count,
        total_companies_affected=total_affected,
        most_exposed_sectors=most_exposed,
        trajectory=trajectory,
        enforcement_intensity=enforcement,
    )


def _compute_sanctions_trajectory(sanctions: list[dict]) -> str:
    """Determine trajectory from sanctions list."""
    if len(sanctions) <= 1:
        return "STABLE"

    # Sort by date if available
    dated = [s for s in sanctions if s.get("date_imposed")]
    if len(dated) < 2:
        return "STABLE"

    dated.sort(key=lambda s: s.get("date_imposed", "1900-01-01"))

    # Simple heuristic: compare count in first half vs second half
    mid = len(dated) // 2
    first_half = dated[:mid]
    second_half = dated[mid:]

    if len(second_half) > len(first_half) * 1.3:
        return "ESCALATING"
    if len(second_half) < len(first_half) * 0.7:
        return "DE_ESCALATING"
    return "STABLE"


def _compute_enforcement_intensity(sanctions: list[dict]) -> str:
    """Classify enforcement intensity from severity levels."""
    if not sanctions:
        return "LENIENT"

    severities = [s.get("severity", "MODERATE") for s in sanctions]
    strict_count = sum(1 for s in severities if s.upper() == "HIGH")
    lenient_count = sum(1 for s in severities if s.upper() == "LOW")

    ratio = strict_count / len(severities) if severities else 0
    if ratio >= 0.5:
        return "STRICT"
    if lenient_count / len(severities) >= 0.5 if severities else False:
        return "LENIENT"
    return "MODERATE"


# ── 9. Detect policy momentum ───────────────────────────────────────

def detect_policy_momentum(
    bills: list[dict],
    topic: str,
) -> str:
    """Classify policy momentum on a topic as ACCELERATING, DECELERATING, or STABLE.

    Parameters
    ----------
    bills : list[dict]
        Each: {topic, date_introduced, ...}.
    topic : str
        Topic to filter on.

    Logic
    -----
    Filter bills matching *topic*, sort by date, split at the temporal
    midpoint (average of first and last date ordinals).
    - ACCELERATING if second-half count > first-half count * 1.3.
    - DECELERATING if second-half count < first-half count * 0.7.
    - STABLE otherwise.
    """
    from datetime import date as _date

    topic_lower = topic.lower()
    relevant = [
        b for b in bills
        if topic_lower in (b.get("topic", "") or "").lower()
    ]

    if len(relevant) < 2:
        return "STABLE"

    # Sort by date
    dated = sorted(relevant, key=lambda b: b.get("date_introduced", ""))

    # Compute temporal midpoint
    try:
        first_d = _date.fromisoformat(dated[0]["date_introduced"])
        last_d = _date.fromisoformat(dated[-1]["date_introduced"])
        mid_ordinal = (first_d.toordinal() + last_d.toordinal()) // 2
        mid_date = _date.fromordinal(mid_ordinal).isoformat()
    except (ValueError, KeyError):
        # Fallback to index-based split
        mid_idx = len(dated) // 2
        first_half_count = max(mid_idx, 1)
        second_half_count = len(dated) - mid_idx
        if second_half_count > first_half_count * 1.3:
            return "ACCELERATING"
        if second_half_count < first_half_count * 0.7:
            return "DECELERATING"
        return "STABLE"

    first_half_count = sum(
        1 for b in dated if b.get("date_introduced", "") <= mid_date
    )
    second_half_count = len(dated) - first_half_count
    first_half_count = max(first_half_count, 1)
    second_half_count = max(second_half_count, 0)

    if second_half_count > first_half_count * 1.3:
        return "ACCELERATING"
    if second_half_count < first_half_count * 0.7:
        return "DECELERATING"
    return "STABLE"


# ── 10. Track regulatory pipeline ───────────────────────────────────

def track_regulatory_pipeline(actions: list[dict]) -> dict:
    """Summarize a set of regulatory actions into a pipeline overview.

    Parameters
    ----------
    actions : list[dict]
        Each: {agency, action_type, date, title, ...}.

    Returns
    -------
    dict with keys:
        - by_agency: {agency: {count, action_types: {type: count}}}
        - by_type: {action_type: count}
        - total: int
        - most_active_agency: str | None
        - trend: INCREASING / DECREASING / STABLE
    """
    if not actions:
        return {
            "by_agency": {},
            "by_type": {},
            "total": 0,
            "most_active_agency": None,
            "trend": "STABLE",
        }

    by_agency: dict[str, dict] = {}
    by_type: dict[str, int] = {}

    for action in actions:
        agency = action.get("agency", "UNKNOWN")
        a_type = action.get("action_type", "UNKNOWN")

        if agency not in by_agency:
            by_agency[agency] = {"count": 0, "action_types": {}}
        by_agency[agency]["count"] += 1
        by_agency[agency]["action_types"][a_type] = (
            by_agency[agency]["action_types"].get(a_type, 0) + 1
        )

        by_type[a_type] = by_type.get(a_type, 0) + 1

    total = len(actions)
    most_active = max(by_agency.items(), key=lambda x: x[1]["count"])[0]

    # Trend — split chronologically
    dated = sorted(actions, key=lambda a: a.get("date", ""))
    mid = len(dated) // 2
    first_count = max(mid, 1)
    second_count = len(dated) - mid

    if second_count > first_count * 1.3:
        trend = "INCREASING"
    elif second_count < first_count * 0.7:
        trend = "DECREASING"
    else:
        trend = "STABLE"

    return {
        "by_agency": by_agency,
        "by_type": by_type,
        "total": total,
        "most_active_agency": most_active,
        "trend": trend,
    }
