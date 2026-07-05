"""Pillar 3 Phase 3B — Country Risk Engine.

Pure computation engine for country risk assessment.
Evaluates political, economic, and sanctions risk factors to produce
composite country risk scores and company exposure mappings.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

from dataclasses import dataclass


# ── Constants ────────────────────────────────────────────────────────────

RISK_WEIGHTS = {"political": 0.40, "economic": 0.35, "sanctions": 0.25}

RISK_CLASSIFICATIONS = [
    (20, "LOW_RISK"),
    (40, "MODERATE_RISK"),
    (60, "ELEVATED_RISK"),
    (80, "HIGH_RISK"),
    (101, "EXTREME_RISK"),
]

POLITICAL_WEIGHTS = {
    "regime_stability": 0.25,
    "policy_predictability": 0.20,
    "corruption": 0.20,
    "rule_of_law": 0.20,
    "civil_unrest": 0.15,
}

ECONOMIC_WEIGHTS = {
    "gdp_growth": 0.20,
    "inflation": 0.20,
    "current_account": 0.15,
    "debt_gdp": 0.20,
    "reserves": 0.10,
    "currency_stability": 0.15,
}


# ── Dataclasses ──────────────────────────────────────────────────────────


@dataclass
class PoliticalRisk:
    """Political risk assessment result."""

    score: float  # 0-100
    regime_stability: float
    policy_predictability: float
    corruption: float
    rule_of_law: float
    civil_unrest: float


@dataclass
class EconomicRisk:
    """Economic risk assessment result."""

    score: float  # 0-100
    gdp_growth_score: float
    inflation_score: float
    current_account_score: float
    debt_gdp_score: float
    reserves_score: float
    currency_stability_score: float


@dataclass
class SanctionsRisk:
    """Sanctions risk assessment result."""

    score: float  # 0-100
    active_programs_count: int
    trade_restriction_intensity: float
    trajectory: str  # ESCALATING/STABLE/DE_ESCALATING


@dataclass
class CountryRiskResult:
    """Complete country risk assessment."""

    composite_score: float  # 0-100
    classification: str  # LOW_RISK/MODERATE_RISK/ELEVATED_RISK/HIGH_RISK/EXTREME_RISK
    trend: str  # IMPROVING/STABLE/DETERIORATING
    political: PoliticalRisk
    economic: EconomicRisk
    sanctions: SanctionsRisk


@dataclass
class CompanyExposure:
    """Geographic exposure of a company to a specific country."""

    entity_id: str
    country_code: str
    exposure_type: str  # REVENUE/OPERATIONS/SUPPLY_CHAIN
    exposure_pct: float
    source: str


# ── Political Risk ───────────────────────────────────────────────────────


def compute_political_risk_score(governance_data: dict) -> PoliticalRisk:
    """Compute political risk from governance sub-scores.

    Parameters
    ----------
    governance_data : dict
        Keys matching POLITICAL_WEIGHTS: regime_stability,
        policy_predictability, corruption, rule_of_law, civil_unrest.
        Each value 0-100 where higher = riskier.

    Returns
    -------
    PoliticalRisk
    """
    sub_scores = {}
    for key in POLITICAL_WEIGHTS:
        sub_scores[key] = max(0.0, min(100.0, float(governance_data.get(key, 50.0))))

    weighted_score = sum(
        sub_scores[key] * weight for key, weight in POLITICAL_WEIGHTS.items()
    )

    return PoliticalRisk(
        score=round(weighted_score, 2),
        regime_stability=sub_scores["regime_stability"],
        policy_predictability=sub_scores["policy_predictability"],
        corruption=sub_scores["corruption"],
        rule_of_law=sub_scores["rule_of_law"],
        civil_unrest=sub_scores["civil_unrest"],
    )


# ── Economic Risk ────────────────────────────────────────────────────────


def _score_gdp_growth(gdp_growth: float) -> float:
    """Convert GDP growth % to a risk score (0-100, higher = riskier).

    Negative → 80+, >3% → 20-.
    """
    if gdp_growth < -2.0:
        return min(100.0, 90.0 + abs(gdp_growth) * 2)
    if gdp_growth < 0.0:
        return 80.0 + abs(gdp_growth) * 5
    if gdp_growth < 1.0:
        return 60.0
    if gdp_growth < 2.0:
        return 40.0
    if gdp_growth < 3.0:
        return 30.0
    if gdp_growth < 5.0:
        return 20.0
    return 10.0


def _score_inflation(inflation: float) -> float:
    """Convert inflation % to a risk score (0-100, higher = riskier).

    >10% → 80+, <3% → 20-.
    """
    if inflation > 20.0:
        return 100.0
    if inflation > 10.0:
        return 80.0 + (inflation - 10.0) * 2
    if inflation > 5.0:
        return 50.0 + (inflation - 5.0) * 6
    if inflation > 3.0:
        return 30.0 + (inflation - 3.0) * 10
    if inflation >= 0.0:
        return max(5.0, inflation * 10)
    # Deflation is also risky
    return 40.0 + abs(inflation) * 10


def _score_debt_gdp(debt_gdp: float) -> float:
    """Convert debt/GDP % to a risk score (0-100, higher = riskier).

    >100% → 80+, <40% → 20-.
    """
    if debt_gdp > 150.0:
        return 100.0
    if debt_gdp > 100.0:
        return 80.0 + (debt_gdp - 100.0) * 0.4
    if debt_gdp > 80.0:
        return 60.0 + (debt_gdp - 80.0)
    if debt_gdp > 60.0:
        return 40.0 + (debt_gdp - 60.0)
    if debt_gdp > 40.0:
        return 20.0 + (debt_gdp - 40.0)
    return max(5.0, debt_gdp * 0.5)


def compute_economic_risk_score(macro_data: dict) -> EconomicRisk:
    """Compute economic risk from macro indicators.

    Parameters
    ----------
    macro_data : dict
        Keys: gdp_growth (%), inflation (%), current_account (% of GDP),
        debt_gdp (%), reserves (months of imports), currency_stability (0-100).

    Returns
    -------
    EconomicRisk
    """
    gdp_score = _score_gdp_growth(macro_data.get("gdp_growth", 0.0))
    inf_score = _score_inflation(macro_data.get("inflation", 0.0))

    # Current account: deficit is riskier
    ca = macro_data.get("current_account", 0.0)
    if ca < -5.0:
        ca_score = 80.0
    elif ca < -2.0:
        ca_score = 50.0 + abs(ca + 2.0) * 10
    elif ca < 0.0:
        ca_score = 30.0
    else:
        ca_score = max(10.0, 20.0 - ca * 2)

    debt_score = _score_debt_gdp(macro_data.get("debt_gdp", 0.0))

    # Reserves: fewer months = riskier
    reserves = macro_data.get("reserves", 6.0)
    if reserves < 2.0:
        res_score = 90.0
    elif reserves < 4.0:
        res_score = 60.0
    elif reserves < 6.0:
        res_score = 40.0
    elif reserves < 9.0:
        res_score = 20.0
    else:
        res_score = 10.0

    # Currency stability: passed directly as 0-100 (higher = riskier)
    cur_score = max(0.0, min(100.0, float(macro_data.get("currency_stability", 30.0))))

    weighted_score = (
        gdp_score * ECONOMIC_WEIGHTS["gdp_growth"]
        + inf_score * ECONOMIC_WEIGHTS["inflation"]
        + ca_score * ECONOMIC_WEIGHTS["current_account"]
        + debt_score * ECONOMIC_WEIGHTS["debt_gdp"]
        + res_score * ECONOMIC_WEIGHTS["reserves"]
        + cur_score * ECONOMIC_WEIGHTS["currency_stability"]
    )

    return EconomicRisk(
        score=round(weighted_score, 2),
        gdp_growth_score=round(gdp_score, 2),
        inflation_score=round(inf_score, 2),
        current_account_score=round(ca_score, 2),
        debt_gdp_score=round(debt_score, 2),
        reserves_score=round(res_score, 2),
        currency_stability_score=round(cur_score, 2),
    )


# ── Sanctions Risk ───────────────────────────────────────────────────────


def compute_sanctions_risk_score(sanctions_data: dict) -> SanctionsRisk:
    """Compute sanctions risk from program data.

    Parameters
    ----------
    sanctions_data : dict
        - active_programs_count: int (number of active sanctions programs)
        - trade_restriction_intensity: float (0-100)
        - trajectory: str (ESCALATING/STABLE/DE_ESCALATING)

    Returns
    -------
    SanctionsRisk
    """
    programs = int(sanctions_data.get("active_programs_count", 0))
    intensity = float(sanctions_data.get("trade_restriction_intensity", 0.0))
    trajectory = sanctions_data.get("trajectory", "STABLE")

    # Base score from programs count
    if programs == 0:
        base_score = 0.0
    elif programs <= 2:
        base_score = 20.0 + programs * 10
    elif programs <= 5:
        base_score = 40.0 + (programs - 2) * 8
    else:
        base_score = min(100.0, 64.0 + (programs - 5) * 6)

    # Blend base score with intensity
    score = base_score * 0.5 + intensity * 0.5

    # Trajectory adjustment
    if trajectory == "ESCALATING":
        score = min(100.0, score * 1.15)
    elif trajectory == "DE_ESCALATING":
        score = score * 0.85

    return SanctionsRisk(
        score=round(max(0.0, min(100.0, score)), 2),
        active_programs_count=programs,
        trade_restriction_intensity=intensity,
        trajectory=trajectory,
    )


# ── Composite Risk ───────────────────────────────────────────────────────


def compute_composite_risk(
    political: PoliticalRisk,
    economic: EconomicRisk,
    sanctions: SanctionsRisk,
) -> float:
    """Compute weighted composite risk score.

    Parameters
    ----------
    political : PoliticalRisk
    economic : EconomicRisk
    sanctions : SanctionsRisk

    Returns
    -------
    float
        Composite score 0-100.
    """
    score = (
        political.score * RISK_WEIGHTS["political"]
        + economic.score * RISK_WEIGHTS["economic"]
        + sanctions.score * RISK_WEIGHTS["sanctions"]
    )
    return round(max(0.0, min(100.0, score)), 2)


def classify_risk(score: float) -> str:
    """Classify a risk score into a named classification.

    Parameters
    ----------
    score : float
        Composite score 0-100.

    Returns
    -------
    str
        One of LOW_RISK, MODERATE_RISK, ELEVATED_RISK, HIGH_RISK,
        EXTREME_RISK.
    """
    for threshold, label in RISK_CLASSIFICATIONS:
        if score < threshold:
            return label
    return "EXTREME_RISK"


def assess_risk_trend(
    current_score: float,
    prior_score: float,
    threshold: float = 5.0,
) -> str:
    """Assess the direction of risk change.

    Parameters
    ----------
    current_score : float
        Current composite risk score.
    prior_score : float
        Previous composite risk score.
    threshold : float
        Minimum change to register as a trend (default 5.0).

    Returns
    -------
    str
        IMPROVING if score decreased >threshold (lower risk),
        DETERIORATING if score increased >threshold (higher risk),
        STABLE otherwise.
    """
    delta = current_score - prior_score
    if delta < -threshold:
        return "IMPROVING"
    if delta > threshold:
        return "DETERIORATING"
    return "STABLE"


# ── Full Assessment ──────────────────────────────────────────────────────


def assess_country_risk(
    governance_data: dict,
    macro_data: dict,
    sanctions_data: dict,
    prior_score: float | None = None,
) -> CountryRiskResult:
    """Full country risk assessment orchestrator.

    Parameters
    ----------
    governance_data : dict
        Political governance sub-scores.
    macro_data : dict
        Economic macro indicators.
    sanctions_data : dict
        Sanctions program data.
    prior_score : float | None
        Previous composite score for trend analysis.

    Returns
    -------
    CountryRiskResult
    """
    political = compute_political_risk_score(governance_data)
    economic = compute_economic_risk_score(macro_data)
    sanctions = compute_sanctions_risk_score(sanctions_data)

    composite = compute_composite_risk(political, economic, sanctions)
    classification = classify_risk(composite)
    trend = assess_risk_trend(composite, prior_score) if prior_score is not None else "STABLE"

    return CountryRiskResult(
        composite_score=composite,
        classification=classification,
        trend=trend,
        political=political,
        economic=economic,
        sanctions=sanctions,
    )


# ── Company Exposure Mapping ─────────────────────────────────────────────


def map_company_exposure(
    entity_id: str,
    segment_data: dict,
    relationship_data: dict | None = None,
) -> list[CompanyExposure]:
    """Map geographic segments to country exposures.

    Parameters
    ----------
    entity_id : str
        Company entity identifier.
    segment_data : dict
        Keys: "revenue_segments" — list of
        {country_code, pct, source?}, "operations" — list of
        {country_code, pct, source?}.
    relationship_data : dict | None
        Optional supply chain data: "supply_chain" — list of
        {country_code, pct, source?}.

    Returns
    -------
    list[CompanyExposure]
    """
    exposures: list[CompanyExposure] = []

    # Revenue segments
    for seg in segment_data.get("revenue_segments", []):
        country_code = seg.get("country_code")
        pct = seg.get("pct")
        if not country_code or pct is None:
            continue  # skip malformed segments
        exposures.append(CompanyExposure(
            entity_id=entity_id,
            country_code=country_code,
            exposure_type="REVENUE",
            exposure_pct=float(pct),
            source=seg.get("source", "filing"),
        ))

    # Operations segments
    for seg in segment_data.get("operations", []):
        country_code = seg.get("country_code")
        pct = seg.get("pct")
        if not country_code or pct is None:
            continue  # skip malformed segments
        exposures.append(CompanyExposure(
            entity_id=entity_id,
            country_code=country_code,
            exposure_type="OPERATIONS",
            exposure_pct=float(pct),
            source=seg.get("source", "filing"),
        ))

    # Supply chain from relationship data
    if relationship_data is not None:
        for seg in relationship_data.get("supply_chain", []):
            country_code = seg.get("country_code")
            pct = seg.get("pct")
            if not country_code or pct is None:
                continue  # skip malformed segments
            exposures.append(CompanyExposure(
                entity_id=entity_id,
                country_code=country_code,
                exposure_type="SUPPLY_CHAIN",
                exposure_pct=float(pct),
                source=seg.get("source", "relationship"),
            ))

    return exposures


def find_exposed_companies(
    country_code: str,
    all_exposures: list[CompanyExposure],
    min_pct: float = 10.0,
) -> list[CompanyExposure]:
    """Filter exposures by country and minimum percentage.

    Parameters
    ----------
    country_code : str
        ISO country code to filter on.
    all_exposures : list[CompanyExposure]
        Full list of exposures across companies.
    min_pct : float
        Minimum exposure percentage to include (default 10.0).

    Returns
    -------
    list[CompanyExposure]
        Exposures matching the country and exceeding min_pct,
        sorted by exposure_pct descending.
    """
    matched = [
        e for e in all_exposures
        if e.country_code == country_code and e.exposure_pct >= min_pct
    ]
    matched.sort(key=lambda e: -e.exposure_pct)
    return matched
