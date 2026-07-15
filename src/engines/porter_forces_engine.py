"""Pillar 3 Phase 3 — Porter's Five Forces Engine.

Pure computation engine that produces a DETERMINISTIC, QUANTITATIVE PROXY
scoring for Porter's Five Forces (supplier power, buyer power, competitive
rivalry, threat of substitutes, threat of new entrants).

IMPORTANT — proxy scoring, not genuine industry-structure research
---------------------------------------------------------------------------
A full Porter's Five Forces analysis is a qualitative industry-structure
judgment (regulatory dynamics, switching frictions, capital intensity,
distribution control, etc.) that no algorithm can fully replicate from
financial-statement-derived signals alone. This engine does NOT attempt
that. Instead it derives five 0-100 *proxy* scores from signals this
codebase already computes and persists elsewhere (moat assessment,
concentration risk, business-model analysis, competitive landscape). Each
proxy score is traceable to the specific input metric(s) that drove it via
named threshold/weight constants below — there is no hidden judgment and no
fabricated fallback value. A force with no supporting inputs available
scores `None` (UNKNOWN), never a fabricated midpoint. Callers/UI should
present these as "quantitative proxy" scores, not as a substitute for a
human analyst's Five Forces write-up.

Score convention: for every force, 0-100 where HIGHER means the force
represents a BIGGER competitive challenge/threat to the company's
profitability (i.e. high supplier_power_score = suppliers have a lot of
leverage over the company; high new_entrant_threat_score = entry barriers
are weak).

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ── Constants ────────────────────────────────────────────────────────────

# Generic force-score -> qualitative level classification, reused across all
# five forces so "HIGH"/"MODERATE"/"LOW" mean the same magnitude everywhere.
PORTER_FORCE_LEVEL_THRESHOLDS = {"HIGH": 65.0, "MODERATE": 40.0}

# -- Supplier power -----------------------------------------------------
# Mirrors the single-source-count banding already used by
# concentration_risk.SUPPLIER_RISK_THRESHOLDS, reused here for both the
# single-source and critical-input counts.
SUPPLIER_POWER_THRESHOLDS = {"HIGH": 3, "MODERATE": 1}  # count of relationships
SUPPLIER_POWER_LEVEL_SCORES = {"HIGH": 85.0, "MODERATE": 55.0, "LOW": 15.0}
# Maps the pre-classified supplier_concentration_risk label straight to a
# score contribution using the same HIGH/MODERATE/LOW banding.
SUPPLIER_POWER_RISK_LABEL_SCORES = {"HIGH": 85.0, "MODERATE": 55.0, "LOW": 15.0}
# Relative contribution of each present input to the blended score.
SUPPLIER_POWER_WEIGHTS = {
    "single_source_count": 0.4,
    "critical_count": 0.3,
    "concentration_risk_label": 0.3,
}

# -- Buyer (customer) power ----------------------------------------------
# top1_pct (0-100 scale) * SCALE, capped at 100 -- a single customer at 50%+
# of revenue is treated as maximal buyer leverage.
BUYER_POWER_TOP1_SCALE = 2.0
# customer_hhi (0-10000 scale) / DIVISOR, capped at 100.
BUYER_POWER_HHI_DIVISOR = 100.0
BUYER_POWER_WEIGHTS = {"top1_pct": 0.6, "hhi": 0.4}

# -- Competitive rivalry ---------------------------------------------------
# 10-year gross-margin std-dev (decimal, e.g. 0.08 = 8pts) at/above this cap
# maps to the maximum rivalry contribution from margin volatility.
RIVALRY_MARGIN_STD_CAP = 0.08
RIVALRY_TREND_SCORES = {"LOSING": 80.0, "STABLE": 45.0, "GAINING": 15.0}
# margin_vs_peers is a decimal delta (e.g. 0.05 = 5pts above peer median).
# score = 50 - (margin_vs_peers * SCALE), i.e. being meaningfully above peers
# pulls the rivalry-pressure score down, below peers pushes it up.
RIVALRY_MARGIN_VS_PEERS_SCALE = 500.0
RIVALRY_WEIGHTS = {"margin_std": 0.35, "trend": 0.35, "margin_vs_peers": 0.30}

# -- Threat of substitutes -------------------------------------------------
# disruption_vulnerability is used near-directly (it already IS a 0-100
# substitute-threat-shaped signal). switching_cost_score enters INVERTED
# (100 - switching_cost_score) since high switching costs make it harder
# for customers to defect to a substitute.
SUBSTITUTE_THREAT_WEIGHTS = {
    "disruption_vulnerability": 0.7,
    "switching_cost_inverse": 0.3,
}

# -- Threat of new entrants -------------------------------------------------
# This force is the INVERSE of entry barriers: new_entrant_threat_score =
# 100 - weighted_avg(moat_score, efficient_scale_score, cost_advantage_score).
# moat_score is weighted heaviest since it is itself a synthesis of all five
# moat sources; efficient_scale/cost_advantage are the two moat sources most
# directly tied to entry-barrier economics (capital intensity, minimum
# efficient scale, structural cost position) so they get secondary weight.
NEW_ENTRANT_BARRIER_WEIGHTS = {
    "moat_score": 0.5,
    "efficient_scale_score": 0.25,
    "cost_advantage_score": 0.25,
}

# All possible input signal keys, used to compute data_completeness.
ALL_SIGNAL_KEYS = [
    "supplier_single_source_count",
    "supplier_critical_count",
    "supplier_concentration_risk",
    "customer_top1_pct",
    "customer_hhi",
    "gross_margin_10y_std",
    "market_share_trend",
    "margin_vs_peers",
    "disruption_vulnerability",
    "switching_cost_score",
    "moat_score",
    "efficient_scale_score",
    "cost_advantage_score",
]

FORCE_NAMES = [
    "supplier_power",
    "buyer_power",
    "competitive_rivalry",
    "substitute_threat",
    "new_entrant_threat",
]


# ── Dataclasses ──────────────────────────────────────────────────────────


@dataclass
class PorterForce:
    """A single Porter's-Five-Forces proxy score."""

    name: str  # supplier_power/buyer_power/competitive_rivalry/substitute_threat/new_entrant_threat
    score: float | None  # 0-100, higher = bigger competitive challenge; None if no inputs
    level: str  # HIGH/MODERATE/LOW/UNKNOWN


@dataclass
class PorterForcesResult:
    """Complete Porter's Five Forces proxy assessment."""

    forces: list[PorterForce] = field(default_factory=list)  # all 5, fixed order
    overall_industry_attractiveness_score: float | None = None  # 0-100, higher = more attractive
    dominant_force: str | None = None  # name of the highest-scoring non-None force
    data_completeness: float = 0.0  # fraction of ALL_SIGNAL_KEYS that were non-None


# ── Shared helpers ───────────────────────────────────────────────────────


def _clamp(value: float) -> float:
    """Clamp a score to the 0-100 range."""
    return max(0.0, min(100.0, value))


def _weighted_average(components: list[tuple[float | None, float]]) -> float | None:
    """Weighted average over (value, weight) pairs, renormalizing weights
    over only the components whose value is not None.

    Returns None if every component is None (i.e. no supporting inputs).
    """
    present = [(value, weight) for value, weight in components if value is not None]
    if not present:
        return None
    total_weight = sum(weight for _, weight in present)
    if total_weight <= 0:
        return None
    return sum(value * weight for value, weight in present) / total_weight


def _classify_level(score: float | None) -> str:
    """Classify a 0-100 force score into HIGH/MODERATE/LOW/UNKNOWN."""
    if score is None:
        return "UNKNOWN"
    if score >= PORTER_FORCE_LEVEL_THRESHOLDS["HIGH"]:
        return "HIGH"
    if score >= PORTER_FORCE_LEVEL_THRESHOLDS["MODERATE"]:
        return "MODERATE"
    return "LOW"


def _count_to_level(count: int, thresholds: dict) -> str:
    """Classify a relationship count into HIGH/MODERATE/LOW using count thresholds."""
    if count >= thresholds["HIGH"]:
        return "HIGH"
    if count >= thresholds["MODERATE"]:
        return "MODERATE"
    return "LOW"


# ── Force 1: Supplier power ─────────────────────────────────────────────


def score_supplier_power(signals: dict) -> float | None:
    """Supplier power proxy from single-source count, critical-input count,
    and the pre-classified supplier concentration risk label.

    More single-source / critical dependencies, or a HIGH concentration
    label, mean suppliers hold more leverage over the company -> higher
    score.
    """
    single_source = signals.get("supplier_single_source_count")
    critical = signals.get("supplier_critical_count")
    risk_label = signals.get("supplier_concentration_risk")

    components: list[tuple[float | None, float]] = []

    if single_source is not None:
        level = _count_to_level(single_source, SUPPLIER_POWER_THRESHOLDS)
        components.append(
            (SUPPLIER_POWER_LEVEL_SCORES[level], SUPPLIER_POWER_WEIGHTS["single_source_count"])
        )

    if critical is not None:
        level = _count_to_level(critical, SUPPLIER_POWER_THRESHOLDS)
        components.append(
            (SUPPLIER_POWER_LEVEL_SCORES[level], SUPPLIER_POWER_WEIGHTS["critical_count"])
        )

    if risk_label is not None and risk_label in SUPPLIER_POWER_RISK_LABEL_SCORES:
        components.append(
            (
                SUPPLIER_POWER_RISK_LABEL_SCORES[risk_label],
                SUPPLIER_POWER_WEIGHTS["concentration_risk_label"],
            )
        )

    score = _weighted_average(components)
    return None if score is None else round(_clamp(score), 2)


# ── Force 2: Buyer (customer) power ─────────────────────────────────────


def score_buyer_power(signals: dict) -> float | None:
    """Buyer power proxy from top-customer revenue % and customer HHI.

    Higher concentration in either metric means the company's customers
    hold more leverage over pricing/terms -> higher score.
    """
    top1_pct = signals.get("customer_top1_pct")
    hhi = signals.get("customer_hhi")

    components: list[tuple[float | None, float]] = []

    if top1_pct is not None:
        components.append(
            (_clamp(top1_pct * BUYER_POWER_TOP1_SCALE), BUYER_POWER_WEIGHTS["top1_pct"])
        )

    if hhi is not None:
        components.append((_clamp(hhi / BUYER_POWER_HHI_DIVISOR), BUYER_POWER_WEIGHTS["hhi"]))

    score = _weighted_average(components)
    return None if score is None else round(_clamp(score), 2)


# ── Force 3: Competitive rivalry ────────────────────────────────────────


def score_competitive_rivalry(signals: dict) -> float | None:
    """Competitive rivalry proxy from margin volatility, market share trend,
    and margin vs. peers.

    Higher 10y gross-margin volatility (weaker pricing power), a LOSING
    share trend, and a below-peer margin all raise rivalry pressure.
    """
    margin_std = signals.get("gross_margin_10y_std")
    trend = signals.get("market_share_trend")
    margin_vs_peers = signals.get("margin_vs_peers")

    components: list[tuple[float | None, float]] = []

    if margin_std is not None:
        std_score = _clamp(margin_std / RIVALRY_MARGIN_STD_CAP * 100.0)
        components.append((std_score, RIVALRY_WEIGHTS["margin_std"]))

    if trend is not None and trend in RIVALRY_TREND_SCORES:
        components.append((RIVALRY_TREND_SCORES[trend], RIVALRY_WEIGHTS["trend"]))

    if margin_vs_peers is not None:
        peers_score = _clamp(50.0 - margin_vs_peers * RIVALRY_MARGIN_VS_PEERS_SCALE)
        components.append((peers_score, RIVALRY_WEIGHTS["margin_vs_peers"]))

    score = _weighted_average(components)
    return None if score is None else round(_clamp(score), 2)


# ── Force 4: Threat of substitutes ──────────────────────────────────────


def score_substitute_threat(signals: dict) -> float | None:
    """Substitute-threat proxy from disruption vulnerability (primary
    driver, used near-directly) and switching cost (inverse driver: higher
    switching costs make substitution harder, so they LOWER this score).
    """
    disruption = signals.get("disruption_vulnerability")
    switching_cost = signals.get("switching_cost_score")

    components: list[tuple[float | None, float]] = []

    if disruption is not None:
        components.append(
            (_clamp(disruption), SUBSTITUTE_THREAT_WEIGHTS["disruption_vulnerability"])
        )

    if switching_cost is not None:
        components.append(
            (_clamp(100.0 - switching_cost), SUBSTITUTE_THREAT_WEIGHTS["switching_cost_inverse"])
        )

    score = _weighted_average(components)
    return None if score is None else round(_clamp(score), 2)


# ── Force 5: Threat of new entrants ─────────────────────────────────────


def score_new_entrant_threat(signals: dict) -> float | None:
    """New-entrant-threat proxy: the INVERSE of entry barrier strength.

    barrier_score = weighted_avg(moat_score, efficient_scale_score,
    cost_advantage_score) over whichever of those are present.
    new_entrant_threat_score = 100 - barrier_score -- i.e. a wide moat with
    strong scale/cost-advantage economics means entry is HARD, so this
    force's score (the *threat*) is LOW.
    """
    moat_score = signals.get("moat_score")
    efficient_scale_score = signals.get("efficient_scale_score")
    cost_advantage_score = signals.get("cost_advantage_score")

    components: list[tuple[float | None, float]] = [
        (moat_score, NEW_ENTRANT_BARRIER_WEIGHTS["moat_score"]),
        (efficient_scale_score, NEW_ENTRANT_BARRIER_WEIGHTS["efficient_scale_score"]),
        (cost_advantage_score, NEW_ENTRANT_BARRIER_WEIGHTS["cost_advantage_score"]),
    ]

    barrier_score = _weighted_average(components)
    if barrier_score is None:
        return None
    return round(_clamp(100.0 - barrier_score), 2)


# ── Orchestrator ─────────────────────────────────────────────────────────

_FORCE_SCORERS = {
    "supplier_power": score_supplier_power,
    "buyer_power": score_buyer_power,
    "competitive_rivalry": score_competitive_rivalry,
    "substitute_threat": score_substitute_threat,
    "new_entrant_threat": score_new_entrant_threat,
}


def _compute_data_completeness(signals: dict) -> float:
    """Fraction of ALL_SIGNAL_KEYS present (non-None) in signals."""
    present = sum(1 for key in ALL_SIGNAL_KEYS if signals.get(key) is not None)
    return round(present / len(ALL_SIGNAL_KEYS), 4)


def assess_porter_forces(signals: dict) -> PorterForcesResult:
    """Compute the five Porter's-Forces proxy scores plus a synthesis.

    Parameters
    ----------
    signals : dict
        See module docstring for the full key list. Every key is optional;
        a missing/None key simply means the force(s) that depend on it are
        built from fewer inputs (or are None if ALL their inputs are
        missing). Nothing is ever defaulted to a fabricated midpoint value.

    Returns
    -------
    PorterForcesResult
    """
    signals = signals or {}

    forces: list[PorterForce] = []
    for name in FORCE_NAMES:
        score = _FORCE_SCORERS[name](signals)
        forces.append(PorterForce(name=name, score=score, level=_classify_level(score)))

    present_scores = [f.score for f in forces if f.score is not None]

    overall: float | None = None
    if present_scores:
        # Overall industry attractiveness is the inverse of the average
        # force-pressure score, renormalized over only the forces that have
        # a real (non-None) score -- same "average over available signals
        # only" pattern used elsewhere in this codebase's risk scoring.
        avg_pressure = sum(present_scores) / len(present_scores)
        overall = round(_clamp(100.0 - avg_pressure), 2)

    dominant: str | None = None
    if present_scores:
        dominant_obj = max((f for f in forces if f.score is not None), key=lambda f: f.score)
        dominant = dominant_obj.name

    return PorterForcesResult(
        forces=forces,
        overall_industry_attractiveness_score=overall,
        dominant_force=dominant,
        data_completeness=_compute_data_completeness(signals),
    )
