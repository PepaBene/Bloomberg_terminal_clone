"""Pillar 3 Phase 3A — Concentration Risk Engine.

Pure computation engine for customer/supplier/geographic concentration risk.
Evaluates revenue concentration across customers, supply chain dependencies,
and geographic exposure to produce risk classifications.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ── Constants ────────────────────────────────────────────────────────────

CUSTOMER_RISK_THRESHOLDS = {"HIGH": 40, "MODERATE": 20}  # top customer %

SUPPLIER_RISK_THRESHOLDS = {"HIGH": 3, "MODERATE": 1}  # single-source count

GEOGRAPHIC_RISK_THRESHOLDS = {"HIGH": 60, "MODERATE": 40}  # top-country %


# ── Dataclasses ──────────────────────────────────────────────────────────


@dataclass
class ConcentrationResult:
    """Complete concentration risk assessment."""

    customer_risk: str  # LOW_RISK/MODERATE/HIGH
    supplier_risk: str
    geographic_risk: str
    overall_risk: str
    overall_score: float  # 0-100 (higher = more concentrated = riskier)
    customer_top1_pct: float | None
    customer_hhi: float | None
    supplier_single_source_count: int
    geographic_hhi: float | None
    fx_exposure_score: float
    risk_factors: list[str] = field(default_factory=list)


# ── Customer Concentration ───────────────────────────────────────────────


def classify_customer_concentration(
    top1_pct: float | None,
    top5_pct: float | None,
    top10_pct: float | None,
) -> str:
    """Classify customer concentration risk.

    Parameters
    ----------
    top1_pct : float | None
        Revenue % from top customer.
    top5_pct : float | None
        Revenue % from top 5 customers.
    top10_pct : float | None
        Revenue % from top 10 customers.

    Returns
    -------
    str
        HIGH, MODERATE, or LOW_RISK.
    """
    if top1_pct is not None and top1_pct >= CUSTOMER_RISK_THRESHOLDS["HIGH"]:
        return "HIGH"
    if top1_pct is not None and top1_pct >= CUSTOMER_RISK_THRESHOLDS["MODERATE"]:
        return "MODERATE"
    if top5_pct is not None and top5_pct >= 60:
        return "MODERATE"
    if top10_pct is not None and top10_pct >= 80:
        return "MODERATE"
    return "LOW_RISK"


def compute_customer_hhi(customer_pcts: list[float]) -> float:
    """Compute Herfindahl-Hirschman Index for customer concentration.

    Parameters
    ----------
    customer_pcts : list[float]
        Revenue percentage for each customer (should sum to ~100).

    Returns
    -------
    float
        HHI value (sum of squared percentages).
    """
    if not customer_pcts:
        return 0.0
    return round(sum(p ** 2 for p in customer_pcts), 2)


# ── Supplier Concentration ───────────────────────────────────────────────


def classify_supplier_concentration(
    single_source_count: int,
    critical_count: int,
    geographic_spread: int,
) -> str:
    """Classify supplier concentration risk.

    Parameters
    ----------
    single_source_count : int
        Number of inputs sourced from a single supplier.
    critical_count : int
        Number of critical/strategic inputs.
    geographic_spread : int
        Number of distinct supplier countries/regions.

    Returns
    -------
    str
        HIGH, MODERATE, or LOW_RISK.
    """
    if single_source_count >= SUPPLIER_RISK_THRESHOLDS["HIGH"]:
        return "HIGH"

    if single_source_count >= SUPPLIER_RISK_THRESHOLDS["MODERATE"]:
        # Single-sourced inputs are riskier when suppliers are also
        # geographically concentrated (a regional disruption can hit all
        # of them at once); wide geographic spread mitigates that risk.
        if geographic_spread <= 2:
            return "HIGH"
        return "MODERATE"

    if critical_count > 0 and geographic_spread <= 1:
        return "MODERATE"

    return "LOW_RISK"


# ── Geographic Concentration ─────────────────────────────────────────────


def compute_geographic_hhi(revenue_by_region: dict[str, float]) -> float:
    """Compute HHI of geographic revenue distribution.

    Parameters
    ----------
    revenue_by_region : dict[str, float]
        Region name -> revenue percentage (should sum to ~100).

    Returns
    -------
    float
        HHI value.
    """
    if not revenue_by_region:
        return 0.0
    return round(sum(v ** 2 for v in revenue_by_region.values()), 2)


def classify_geographic_concentration(
    top1_pct: float,
    hhi: float,
    high_risk_exposure: float,
) -> str:
    """Classify geographic concentration risk.

    Parameters
    ----------
    top1_pct : float
        Revenue % from the top country/region.
    hhi : float
        Geographic HHI.
    high_risk_exposure : float
        Revenue % from high-risk/sanctioned regions.

    Returns
    -------
    str
        HIGH, MODERATE, or LOW_RISK.
    """
    if top1_pct >= GEOGRAPHIC_RISK_THRESHOLDS["HIGH"]:
        return "HIGH"
    if top1_pct >= GEOGRAPHIC_RISK_THRESHOLDS["MODERATE"]:
        return "MODERATE"
    if hhi > 4000:
        return "HIGH"
    if hhi > 2500:
        return "MODERATE"
    if high_risk_exposure > 20:
        return "MODERATE"
    return "LOW_RISK"


# ── FX Exposure ──────────────────────────────────────────────────────────


def compute_fx_exposure_score(
    domestic_pct: float,
    developed_market_pct: float,
    em_pct: float,
) -> float:
    """Compute FX exposure score 0-100.

    More EM exposure = higher score (riskier).

    Parameters
    ----------
    domestic_pct : float
        Revenue % from domestic market.
    developed_market_pct : float
        Revenue % from developed foreign markets.
    em_pct : float
        Revenue % from emerging markets.

    Returns
    -------
    float
        Score 0-100 (higher = more FX risk).
    """
    # Domestic revenue has no FX risk, developed has moderate, EM has high
    score = (
        domestic_pct * 0.0
        + developed_market_pct * 0.4
        + em_pct * 1.0
    )
    return round(max(0.0, min(100.0, score)), 2)


# ── Overall Concentration ────────────────────────────────────────────────


def compute_overall_concentration(
    customer_risk: str,
    supplier_risk: str,
    geographic_risk: str,
) -> tuple[str, float]:
    """Compute overall concentration risk classification and score.

    Uses worst-of classification + weighted score.

    Parameters
    ----------
    customer_risk : str
        Customer risk level.
    supplier_risk : str
        Supplier risk level.
    geographic_risk : str
        Geographic risk level.

    Returns
    -------
    tuple[str, float]
        (overall_risk, overall_score 0-100).
    """
    risk_levels = {"HIGH": 3, "MODERATE": 2, "LOW_RISK": 1}
    level_to_score = {"HIGH": 85, "MODERATE": 55, "LOW_RISK": 20}

    risks = [customer_risk, supplier_risk, geographic_risk]
    unknown = [r for r in risks if r not in risk_levels]
    if unknown:
        # Silently defaulting an unrecognized level to LOW_RISK/20 would
        # understate risk for a typo'd or new classification string — fail
        # loudly instead so the bad input gets fixed at the source.
        raise ValueError(
            f"Unrecognized risk level(s) {unknown!r}; expected one of "
            f"{sorted(risk_levels)}"
        )

    max_level = max(risks, key=lambda r: risk_levels[r])

    # Weighted score: customer 40%, supplier 30%, geographic 30%
    score = (
        0.40 * level_to_score[customer_risk]
        + 0.30 * level_to_score[supplier_risk]
        + 0.30 * level_to_score[geographic_risk]
    )

    return max_level, round(score, 2)


# ── Risk Factor Identification ───────────────────────────────────────────


def identify_risk_factors(result: ConcentrationResult) -> list[str]:
    """Generate human-readable risk descriptions.

    Parameters
    ----------
    result : ConcentrationResult
        The concentration assessment result.

    Returns
    -------
    list[str]
        List of risk factor descriptions.
    """
    factors: list[str] = []

    if result.customer_risk == "HIGH":
        pct_str = f" ({result.customer_top1_pct:.0f}%)" if result.customer_top1_pct else ""
        factors.append(f"High customer concentration{pct_str}: revenue dependent on few customers")
    elif result.customer_risk == "MODERATE":
        factors.append("Moderate customer concentration: top customers represent significant revenue share")

    if result.supplier_risk == "HIGH":
        factors.append(
            f"High supplier risk: {result.supplier_single_source_count} single-source dependencies"
        )
    elif result.supplier_risk == "MODERATE":
        factors.append("Moderate supplier risk: some single-source dependencies exist")

    if result.geographic_risk == "HIGH":
        factors.append("High geographic concentration: revenue heavily dependent on single region")
    elif result.geographic_risk == "MODERATE":
        factors.append("Moderate geographic concentration: limited regional diversification")

    if result.fx_exposure_score > 50:
        factors.append(f"Elevated FX exposure (score: {result.fx_exposure_score:.0f}/100)")

    if result.customer_hhi is not None and result.customer_hhi > 2000:
        factors.append(f"Customer HHI of {result.customer_hhi:.0f} indicates concentrated customer base")

    return factors


# ── Industry Comparison ──────────────────────────────────────────────────


def compare_to_industry(
    entity_result: ConcentrationResult,
    industry_median: dict,
) -> dict:
    """Compare entity concentration to industry medians.

    Parameters
    ----------
    entity_result : ConcentrationResult
        Entity's concentration result.
    industry_median : dict
        Industry median values:
        - customer_hhi: float
        - geographic_hhi: float
        - overall_score: float

    Returns
    -------
    dict
        Comparison with deltas.
    """
    comparison: dict = {}

    if entity_result.customer_hhi is not None and "customer_hhi" in industry_median:
        comparison["customer_hhi_vs_industry"] = round(
            entity_result.customer_hhi - industry_median["customer_hhi"], 2,
        )

    if entity_result.geographic_hhi is not None and "geographic_hhi" in industry_median:
        comparison["geographic_hhi_vs_industry"] = round(
            entity_result.geographic_hhi - industry_median["geographic_hhi"], 2,
        )

    if "overall_score" in industry_median:
        comparison["overall_score_vs_industry"] = round(
            entity_result.overall_score - industry_median["overall_score"], 2,
        )

    # Summary label
    delta = comparison.get("overall_score_vs_industry", 0)
    if delta > 15:
        comparison["relative_risk"] = "MORE_CONCENTRATED"
    elif delta < -15:
        comparison["relative_risk"] = "LESS_CONCENTRATED"
    else:
        comparison["relative_risk"] = "IN_LINE"

    return comparison


# ── Full Orchestrator ────────────────────────────────────────────────────


def assess_concentration_risk(
    customer_data: dict,
    supplier_data: dict,
    geographic_data: dict,
) -> ConcentrationResult:
    """Full concentration risk assessment orchestrator.

    Parameters
    ----------
    customer_data : dict
        - top1_pct: float | None
        - top5_pct: float | None
        - top10_pct: float | None
        - customer_pcts: list[float] | None
    supplier_data : dict
        - single_source_count: int
        - critical_count: int
        - geographic_spread: int
    geographic_data : dict
        - revenue_by_region: dict[str, float]
        - domestic_pct: float
        - developed_market_pct: float
        - em_pct: float
        - high_risk_exposure: float

    Returns
    -------
    ConcentrationResult
    """
    # Customer
    top1 = customer_data.get("top1_pct")
    top5 = customer_data.get("top5_pct")
    top10 = customer_data.get("top10_pct")
    customer_risk = classify_customer_concentration(top1, top5, top10)

    customer_pcts = customer_data.get("customer_pcts")
    customer_hhi = compute_customer_hhi(customer_pcts) if customer_pcts else None

    # Supplier
    single_source = supplier_data.get("single_source_count", 0)
    critical = supplier_data.get("critical_count", 0)
    geo_spread = supplier_data.get("geographic_spread", 5)
    supplier_risk = classify_supplier_concentration(single_source, critical, geo_spread)

    # Geographic
    rev_by_region = geographic_data.get("revenue_by_region", {})
    geo_hhi = compute_geographic_hhi(rev_by_region) if rev_by_region else None

    top1_geo = max(rev_by_region.values()) if rev_by_region else 0.0
    high_risk_exp = geographic_data.get("high_risk_exposure", 0.0)
    geographic_risk = classify_geographic_concentration(
        top1_geo, geo_hhi or 0.0, high_risk_exp,
    )

    # FX exposure
    fx_score = compute_fx_exposure_score(
        geographic_data.get("domestic_pct", 100.0),
        geographic_data.get("developed_market_pct", 0.0),
        geographic_data.get("em_pct", 0.0),
    )

    # Overall
    overall_risk, overall_score = compute_overall_concentration(
        customer_risk, supplier_risk, geographic_risk,
    )

    result = ConcentrationResult(
        customer_risk=customer_risk,
        supplier_risk=supplier_risk,
        geographic_risk=geographic_risk,
        overall_risk=overall_risk,
        overall_score=overall_score,
        customer_top1_pct=top1,
        customer_hhi=customer_hhi,
        supplier_single_source_count=single_source,
        geographic_hhi=geo_hhi,
        fx_exposure_score=fx_score,
    )

    result.risk_factors = identify_risk_factors(result)

    return result
