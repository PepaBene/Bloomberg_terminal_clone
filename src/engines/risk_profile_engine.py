"""Composite Risk Profile Engine.

Pure computation engine backing ``GET /v3/company/{entity_id}/risk-profile``.

This engine does not derive anything from raw financials. Its whole job is
to COMBINE several already-real, already-computed signals -- Altman
Z-Score, Piotroski F-Score, Beneish M-Score, accruals quality, leverage
(net debt/EBITDA), refinancing risk score, beta, and return volatility --
into one composite risk view with sub-scores and an auditable, rules-based
list of risk factors. The caller (router) is responsible for fetching each
signal from wherever it is already persisted in this codebase and handing
this engine a plain dict.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

# ── Dataclasses ───────────────────────────────────────────────────────────


@dataclass
class RiskFactor:
    """A single auditable, rules-triggered risk factor."""

    factor: str
    severity: str  # LOW/MODERATE/HIGH
    metric: str
    value: float


@dataclass
class RiskProfileResult:
    """Complete composite risk profile."""

    credit_risk_score: float | None = None
    earnings_quality_risk_score: float | None = None
    market_risk_score: float | None = None
    overall_risk_score: float | None = None
    overall_risk_tier: str = "UNKNOWN"  # LOW/MODERATE/ELEVATED/HIGH/UNKNOWN
    data_completeness: float = 0.0
    risk_factors: list[RiskFactor] = field(default_factory=list)


# ── Weight constants ─────────────────────────────────────────────────────
#
# All sub-score and overall-score weights are named constants (mirroring
# MOAT_SOURCE_WEIGHTS in moat_assessment.py) rather than magic numbers
# buried inline. Every weighted average in this module is computed only
# over the inputs that are actually present (non-None) and the remaining
# weights are renormalized to sum to 1.0 -- see `_weighted_average()`.
# This means the *meaning* of a sub-score or the overall score shifts
# depending on which signals were available for a given entity; that is
# intentional (a partially-observed risk view is still useful) but callers
# must consult `data_completeness` to know how grounded the number is.

CREDIT_RISK_WEIGHTS: dict[str, float] = {
    "z_score": 0.40,
    "net_debt_ebitda": 0.30,
    "refinancing_risk_score": 0.30,
}

EARNINGS_QUALITY_RISK_WEIGHTS: dict[str, float] = {
    "piotroski_f_score": 0.40,
    "beneish_m_score": 0.35,
    "accruals_quality": 0.25,
}

MARKET_RISK_WEIGHTS: dict[str, float] = {
    "beta": 0.45,
    "annualized_volatility": 0.55,
}

OVERALL_RISK_WEIGHTS: dict[str, float] = {
    "credit_risk_score": 0.40,
    "earnings_quality_risk_score": 0.30,
    "market_risk_score": 0.30,
}

# Overall risk tier cutoffs (on the 0-100 overall_risk_score scale).
OVERALL_RISK_TIER_THRESHOLDS: dict[str, float] = {
    "LOW": 25.0,       # score < 25          -> LOW
    "MODERATE": 50.0,  # 25 <= score < 50    -> MODERATE
    "ELEVATED": 75.0,  # 50 <= score < 75    -> ELEVATED
    # score >= 75                            -> HIGH
}

# The 8 possible input signals used to compute data_completeness.
ALL_SIGNAL_KEYS: tuple[str, ...] = (
    "z_score",
    "piotroski_f_score",
    "beneish_m_score",
    "accruals_quality",
    "net_debt_ebitda",
    "refinancing_risk_score",
    "beta",
    "annualized_volatility",
)


# ── Weighted-average helper ──────────────────────────────────────────────


def _weighted_average(components: dict[str, float], weights: dict[str, float]) -> float | None:
    """Weighted average over whatever components are present, renormalized.

    Only keys present in ``components`` contribute; their weights (looked
    up from ``weights``) are renormalized to sum to 1.0 so the result stays
    on the original 0-100 scale regardless of how many inputs are missing.
    Returns None if ``components`` is empty.
    """
    if not components:
        return None
    total_weight = sum(weights[k] for k in components if k in weights)
    if total_weight <= 0:
        return None
    score = sum(components[k] * weights[k] for k in components if k in weights) / total_weight
    return round(max(0.0, min(100.0, score)), 2)


# ── Credit risk components ───────────────────────────────────────────────
#
# Banding style mirrors balance_sheet_risk_engine.py's compute_refinancing_risk:
# bucketed points per conventional threshold zone rather than a continuous
# formula, scaled onto a common 0-100 "riskiness" axis.


def _z_score_risk_component(z_score: float | None) -> float | None:
    """Invert Altman Z-Score into a 0-100 risk reading.

    Conventional bands: > 2.99 SAFE, 1.81-2.99 GREY_ZONE, < 1.81 DISTRESS.
    """
    if z_score is None:
        return None
    if z_score < 1.81:
        return 100.0  # DISTRESS
    elif z_score < 2.99:
        return 60.0  # GREY_ZONE
    return 0.0  # SAFE


def _net_debt_ebitda_risk_component(net_debt_ebitda: float | None) -> float | None:
    """Score leverage 0-100. > 4.0x elevated, > 6.0x high (per spec)."""
    if net_debt_ebitda is None:
        return None
    if net_debt_ebitda > 6.0:
        return 100.0
    elif net_debt_ebitda > 4.0:
        return 65.0
    elif net_debt_ebitda > 2.0:
        return 30.0
    return 10.0


def compute_credit_risk_score(signals: dict) -> float | None:
    """Combine z_score, net_debt_ebitda, refinancing_risk_score into 0-100.

    None if all three inputs are missing.
    """
    components: dict[str, float] = {}

    z_component = _z_score_risk_component(signals.get("z_score"))
    if z_component is not None:
        components["z_score"] = z_component

    nde_component = _net_debt_ebitda_risk_component(signals.get("net_debt_ebitda"))
    if nde_component is not None:
        components["net_debt_ebitda"] = nde_component

    refi = signals.get("refinancing_risk_score")
    if refi is not None:
        # Already 0-100 scaled elsewhere (higher = riskier) -- use as-is.
        components["refinancing_risk_score"] = max(0.0, min(100.0, float(refi)))

    return _weighted_average(components, CREDIT_RISK_WEIGHTS)


# ── Earnings quality risk components ─────────────────────────────────────


def _piotroski_risk_component(f_score: float | None) -> float | None:
    """Invert Piotroski F-Score (0-9) into a 0-100 risk reading.

    Zone boundaries mirror src/engines/e3_piotroski.py's own banding
    (f_score >= 8 -> STRONG, >= 5 -> MODERATE, else WEAK) so this engine
    doesn't invent a competing convention.
    """
    if f_score is None:
        return None
    if f_score >= 8:
        return 15.0  # STRONG -> low risk
    elif f_score >= 5:
        return 50.0  # MODERATE
    return 90.0  # WEAK -> high risk


def _beneish_risk_component(m_score: float | None) -> float | None:
    """Score Beneish M-Score 0-100. > -1.78 is the standard academic
    threshold flagging elevated earnings-manipulation probability
    (higher M-score = more suspicious)."""
    if m_score is None:
        return None
    if m_score > -1.78:
        return 90.0  # Above threshold -- likely manipulator
    elif m_score > -2.50:
        return 50.0  # Grey zone, moderately elevated
    return 15.0  # Comfortably below threshold


def _accruals_risk_component(accruals_quality: float | None) -> float | None:
    """Score accruals-based earnings risk 0-100.

    `accruals_quality` is consumed exactly as given (0-1 or similar scale,
    NOT rescaled) per spec. We assume -- since we're inferring convention
    rather than verifying it against the upstream source -- that a HIGHER
    accruals_quality value means LOWER earnings quality (more
    accrual-driven, less cash-backed earnings), i.e. higher = riskier.
    We map it directly onto the 0-100 risk axis (clamped) since it is
    already stated to be on a roughly 0-1 scale.
    """
    if accruals_quality is None:
        return None
    return max(0.0, min(100.0, float(accruals_quality) * 100.0))


def compute_earnings_quality_risk_score(signals: dict) -> float | None:
    """Combine piotroski_f_score, beneish_m_score, accruals_quality into 0-100.

    None if all three inputs are missing.
    """
    components: dict[str, float] = {}

    piotroski_component = _piotroski_risk_component(signals.get("piotroski_f_score"))
    if piotroski_component is not None:
        components["piotroski_f_score"] = piotroski_component

    beneish_component = _beneish_risk_component(signals.get("beneish_m_score"))
    if beneish_component is not None:
        components["beneish_m_score"] = beneish_component

    accruals_component = _accruals_risk_component(signals.get("accruals_quality"))
    if accruals_component is not None:
        components["accruals_quality"] = accruals_component

    return _weighted_average(components, EARNINGS_QUALITY_RISK_WEIGHTS)


# ── Market risk components ───────────────────────────────────────────────


def _beta_risk_component(beta: float | None) -> float | None:
    """Score market beta 0-100. > 1.3 elevated, < 0.7 low (per spec)."""
    if beta is None:
        return None
    if beta < 0.7:
        return 15.0
    elif beta <= 1.3:
        return 40.0
    elif beta <= 2.0:
        return 75.0
    return 100.0


def _volatility_risk_component(annualized_volatility: float | None) -> float | None:
    """Score annualized return volatility 0-100.

    Standard equity-vol heuristic bands: < 0.20 low, > 0.40 elevated.
    """
    if annualized_volatility is None:
        return None
    if annualized_volatility < 0.20:
        return 15.0
    elif annualized_volatility <= 0.40:
        return 45.0
    elif annualized_volatility <= 0.60:
        return 75.0
    return 100.0


def compute_market_risk_score(signals: dict) -> float | None:
    """Combine beta and annualized_volatility into 0-100.

    None if both inputs are missing.
    """
    components: dict[str, float] = {}

    beta_component = _beta_risk_component(signals.get("beta"))
    if beta_component is not None:
        components["beta"] = beta_component

    vol_component = _volatility_risk_component(signals.get("annualized_volatility"))
    if vol_component is not None:
        components["annualized_volatility"] = vol_component

    return _weighted_average(components, MARKET_RISK_WEIGHTS)


# ── Overall score / tier ─────────────────────────────────────────────────


def compute_overall_risk_score(
    credit_risk_score: float | None,
    earnings_quality_risk_score: float | None,
    market_risk_score: float | None,
) -> float | None:
    """Weighted average of whichever sub-scores are available, renormalized.

    None only when all three sub-scores are None.
    """
    components: dict[str, float] = {}
    if credit_risk_score is not None:
        components["credit_risk_score"] = credit_risk_score
    if earnings_quality_risk_score is not None:
        components["earnings_quality_risk_score"] = earnings_quality_risk_score
    if market_risk_score is not None:
        components["market_risk_score"] = market_risk_score

    return _weighted_average(components, OVERALL_RISK_WEIGHTS)


def classify_overall_risk_tier(overall_risk_score: float | None) -> str:
    """Bucket overall_risk_score into LOW/MODERATE/ELEVATED/HIGH/UNKNOWN."""
    if overall_risk_score is None:
        return "UNKNOWN"
    if overall_risk_score < OVERALL_RISK_TIER_THRESHOLDS["LOW"]:
        return "LOW"
    elif overall_risk_score < OVERALL_RISK_TIER_THRESHOLDS["MODERATE"]:
        return "MODERATE"
    elif overall_risk_score < OVERALL_RISK_TIER_THRESHOLDS["ELEVATED"]:
        return "ELEVATED"
    return "HIGH"


# ── Data completeness ─────────────────────────────────────────────────────


def compute_data_completeness(signals: dict) -> float:
    """Fraction (0.0-1.0) of the 8 possible input signals that are non-None."""
    provided = sum(1 for key in ALL_SIGNAL_KEYS if signals.get(key) is not None)
    return round(provided / len(ALL_SIGNAL_KEYS), 4)


# ── Risk factor rule table ───────────────────────────────────────────────
#
# Each rule is (metric, condition, severity, template). `metric` is looked
# up directly in the `signals` dict; if that value is None the rule is
# skipped (never fabricated). If present and `condition(value)` is True, a
# RiskFactor is emitted with the real value substituted into `template`.
# Band edges within the same metric are mutually exclusive by construction
# so at most one rule per metric/band fires.

RiskRule = tuple[str, Callable[[float], bool], str, str]

RISK_FACTOR_RULES: list[RiskRule] = [
    (
        "z_score",
        lambda v: v < 1.81,
        "HIGH",
        "Altman Z-Score of {value:.2f} is in the distress zone (< 1.81)",
    ),
    (
        "z_score",
        lambda v: 1.81 <= v < 2.99,
        "MODERATE",
        "Altman Z-Score of {value:.2f} is in the grey zone (1.81-2.99)",
    ),
    (
        "piotroski_f_score",
        lambda v: v < 5,
        "HIGH",
        "Piotroski F-Score of {value:.0f} indicates weak fundamental quality (WEAK zone, < 5)",
    ),
    (
        "piotroski_f_score",
        lambda v: 5 <= v < 8,
        "MODERATE",
        "Piotroski F-Score of {value:.0f} indicates moderate fundamental quality (MODERATE zone, 5-7)",
    ),
    (
        "beneish_m_score",
        lambda v: v > -1.78,
        "HIGH",
        "Beneish M-Score of {value:.2f} exceeds the -1.78 earnings-manipulation threshold",
    ),
    (
        "accruals_quality",
        lambda v: v > 0.70,
        "HIGH",
        "Accruals quality reading of {value:.2f} indicates high accrual-driven earnings risk",
    ),
    (
        "accruals_quality",
        lambda v: 0.40 < v <= 0.70,
        "MODERATE",
        "Accruals quality reading of {value:.2f} indicates elevated accrual-driven earnings risk",
    ),
    (
        "net_debt_ebitda",
        lambda v: v > 6.0,
        "HIGH",
        "Net debt/EBITDA of {value:.2f}x is high (> 6.0x)",
    ),
    (
        "net_debt_ebitda",
        lambda v: 4.0 < v <= 6.0,
        "MODERATE",
        "Net debt/EBITDA of {value:.2f}x is elevated (> 4.0x)",
    ),
    (
        "refinancing_risk_score",
        lambda v: v >= 75,
        "HIGH",
        "Refinancing risk score of {value:.1f} is in the high-risk band (>= 75)",
    ),
    (
        "refinancing_risk_score",
        lambda v: 50 <= v < 75,
        "MODERATE",
        "Refinancing risk score of {value:.1f} is in the elevated-risk band (50-74)",
    ),
    (
        "beta",
        lambda v: v > 2.0,
        "HIGH",
        "Beta of {value:.2f} indicates very high market-risk sensitivity (> 2.0)",
    ),
    (
        "beta",
        lambda v: 1.3 < v <= 2.0,
        "MODERATE",
        "Beta of {value:.2f} indicates elevated market-risk sensitivity (> 1.3)",
    ),
    (
        "annualized_volatility",
        lambda v: v > 0.60,
        "HIGH",
        "Annualized volatility of {value:.1%} is very high (> 60%)",
    ),
    (
        "annualized_volatility",
        lambda v: 0.40 < v <= 0.60,
        "MODERATE",
        "Annualized volatility of {value:.1%} is elevated (> 40%)",
    ),
]


def _build_risk_factors(signals: dict) -> list[RiskFactor]:
    """Evaluate RISK_FACTOR_RULES against `signals`, emitting one RiskFactor
    per triggered rule. Rules on metrics whose value is None never fire."""
    factors: list[RiskFactor] = []
    for metric, condition, severity, template in RISK_FACTOR_RULES:
        value = signals.get(metric)
        if value is None:
            continue
        if condition(value):
            factors.append(
                RiskFactor(
                    factor=template.format(value=value),
                    severity=severity,
                    metric=metric,
                    value=float(value),
                )
            )
    return factors


# ── Orchestrator ──────────────────────────────────────────────────────────


def assess_risk_profile(signals: dict) -> RiskProfileResult:
    """Combine credit, earnings-quality, and market risk signals into one
    composite RiskProfileResult.

    Parameters
    ----------
    signals : dict
        All keys optional. See module docstring / RISK_FACTOR_RULES for the
        full list of recognized keys and their conventions:
        z_score, piotroski_f_score, beneish_m_score, accruals_quality,
        net_debt_ebitda, refinancing_risk_score, beta, annualized_volatility.
        A missing key is always treated as "signal unavailable", never as 0.
    """
    credit_risk_score = compute_credit_risk_score(signals)
    earnings_quality_risk_score = compute_earnings_quality_risk_score(signals)
    market_risk_score = compute_market_risk_score(signals)

    overall_risk_score = compute_overall_risk_score(
        credit_risk_score, earnings_quality_risk_score, market_risk_score
    )
    overall_risk_tier = classify_overall_risk_tier(overall_risk_score)
    data_completeness = compute_data_completeness(signals)
    risk_factors = _build_risk_factors(signals)

    return RiskProfileResult(
        credit_risk_score=credit_risk_score,
        earnings_quality_risk_score=earnings_quality_risk_score,
        market_risk_score=market_risk_score,
        overall_risk_score=overall_risk_score,
        overall_risk_tier=overall_risk_tier,
        data_completeness=data_completeness,
        risk_factors=risk_factors,
    )
