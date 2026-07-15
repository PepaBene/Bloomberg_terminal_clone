"""SWOT synthesis engine — deterministic rules over real, already-computed signals.

`GET /v3/competitive/{entity_id}/swot` has no backend implementation anywhere
in this codebase today (no SWOT schema, model, or engine exists). A genuine
analyst-quality SWOT requires qualitative judgment ("management is
disciplined about capital allocation because...") that an algorithm cannot
honestly replicate — so this module does NOT attempt to write analyst prose.

Instead it is a deterministic RULES ENGINE: it consumes a flat dict of
signals that are themselves real, already-persisted quantitative outputs of
other engines/assessments (moat score, business-model durability, balance
sheet risk, capital allocation quality, management quality, concentration
risk — see the `derive_swot` docstring for the exact key list and their
source tables). Each rule is a single documented threshold on a single named
metric; every bullet this module emits carries the metric name and the value
that triggered it, so a human can immediately verify (or dispute) the
classification against the source data. Nothing here is fabricated judgment
— it is the same "honest heuristic, not invented content" discipline used
elsewhere in this codebase, e.g. the GDELT severity classifier in
``src/ingestion/edgar_esg_controversies.py``: a rule fires only when a real
number crosses a documented line, and the module is explicit that a bullet
is a mechanical derivation, not equivalent to human analyst judgment.

Design: a single flat RULE TABLE (list of `_Rule` entries) rather than nested
if/else. Each rule declares its bucket (strengths/weaknesses/opportunities/
threats), a `condition(signals) -> bool` predicate, a text template, the
metric name(s) it is grounded in, a value extractor, and a severity/
confidence rule. `derive_swot` iterates the table once, evaluates every rule
against the input signals, and buckets the ones that fire. This makes it
trivial to unit-test each rule in isolation and to extend the table without
touching control flow.

A missing/None signal key means "no rule keyed to that signal can fire" —
never "the underlying condition is false" or "assume zero/worst-case".
Rules that need a value are written so a None short-circuits to False before
any comparison is attempted.

No database access, no network access — all functions accept and return
plain data (dicts/dataclasses).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ── Dataclasses ───────────────────────────────────────────────────────────


@dataclass
class SWOTItem:
    """A single, auditable SWOT bullet.

    `metric` + `value` let a human trace the bullet back to the exact real
    number that triggered it. `severity` bands how far past its threshold
    the triggering value sits (see `_band_severity` for the general rule;
    individual rules may use a bespoke banding when noted).
    """

    text: str
    metric: str
    value: float | str
    severity: str  # HIGH / MODERATE / LOW


@dataclass
class SWOTResult:
    """Complete SWOT synthesis: four buckets of `SWOTItem` plus a coverage disclosure."""

    strengths: list[SWOTItem] = field(default_factory=list)
    weaknesses: list[SWOTItem] = field(default_factory=list)
    opportunities: list[SWOTItem] = field(default_factory=list)
    threats: list[SWOTItem] = field(default_factory=list)
    signals_available: int = 0  # count of non-None input signals, out of ~20 possible


# ── Signal inventory (for the completeness disclosure) ──────────────────────

# The full set of keys `derive_swot` knows how to consume. Used only to
# compute `signals_available` honestly (count of these keys present in the
# input dict with a non-None value) -- NOT used to gate rule evaluation,
# since `signals.get(...)` on an absent key already returns None safely.
KNOWN_SIGNAL_KEYS: tuple[str, ...] = (
    "moat_width",
    "moat_score",
    "dominant_moat_source",
    "market_share_trend",
    "diversification_score",
    "cyclicality_score",
    "disruption_vulnerability",
    "switching_cost_score",
    "operating_leverage",
    "net_debt_ebitda",
    "z_score",
    "refinancing_risk_score",
    "liquidity_ratio",
    "overall_score",
    "roic_vs_wacc_spread",
    "overall_quality_score",
    "governance_score",
    "beneish_m_score",
    "customer_top1_pct",
    "overall_concentration_risk",
    "overall_risk_score",
)


# ── Rule table plumbing ──────────────────────────────────────────────────


@dataclass(frozen=True)
class _Rule:
    """One row of the rule table.

    `condition` and `build` both receive the raw `signals` dict and must
    treat every key as possibly absent/None -- a KeyError/TypeError inside
    either is treated as "rule does not fire" (see `derive_swot`), never
    propagated, so one malformed/missing signal cannot break the rest.
    """

    bucket: str  # "strengths" / "weaknesses" / "opportunities" / "threats"
    rule_id: str
    condition: Callable[[dict[str, Any]], bool]
    build: Callable[[dict[str, Any]], SWOTItem]


def _severity_band(value: float, low: float, high: float, higher_is_worse: bool = True) -> str:
    """Generic severity banding: LOW up to `low` past threshold, HIGH beyond `high`.

    `value` is expected to already be the "distance past threshold" measure
    the caller computed (e.g. `net_debt_ebitda - 4.0`), always >= 0 by
    construction of the caller. `higher_is_worse` is documentation only here
    (banding is symmetric); kept for readability at call sites.
    """
    if value >= high:
        return "HIGH"
    if value >= low:
        return "MODERATE"
    return "LOW"


# ── Strengths ─────────────────────────────────────────────────────────────


def _r_wide_moat(s: dict[str, Any]) -> bool:
    return s.get("moat_width") == "WIDE"


def _b_wide_moat(s: dict[str, Any]) -> SWOTItem:
    score = s.get("moat_score")
    source = s.get("dominant_moat_source")
    detail = f" (source: {source})" if source else ""
    score_txt = f", moat score {score:.0f}/100" if isinstance(score, (int, float)) else ""
    return SWOTItem(
        text=f"Wide economic moat{detail}{score_txt} -- durable competitive advantage.",
        metric="moat_width" if score is None else "moat_score",
        value=score if isinstance(score, (int, float)) else "WIDE",
        severity="HIGH",
    )


def _r_high_capital_allocation(s: dict[str, Any]) -> bool:
    v = s.get("overall_score")
    return isinstance(v, (int, float)) and v >= 70


def _b_high_capital_allocation(s: dict[str, Any]) -> SWOTItem:
    v = s["overall_score"]
    return SWOTItem(
        text=f"Strong capital allocation track record (score {v:.0f}/100).",
        metric="overall_score",
        value=v,
        severity=_severity_band(v - 70, low=0, high=20),
    )


def _r_positive_roic_spread(s: dict[str, Any]) -> bool:
    v = s.get("roic_vs_wacc_spread")
    return isinstance(v, (int, float)) and v > 0.02


def _b_positive_roic_spread(s: dict[str, Any]) -> SWOTItem:
    v = s["roic_vs_wacc_spread"]
    return SWOTItem(
        text=f"Earns returns well above its cost of capital (ROIC-WACC spread {v * 100:.1f}pts).",
        metric="roic_vs_wacc_spread",
        value=v,
        severity=_severity_band(v - 0.02, low=0.0, high=0.08),
    )


def _r_strong_balance_sheet(s: dict[str, Any]) -> bool:
    v = s.get("z_score")
    return isinstance(v, (int, float)) and v > 2.99


def _b_strong_balance_sheet(s: dict[str, Any]) -> SWOTItem:
    v = s["z_score"]
    return SWOTItem(
        text=f"Balance sheet sits in Altman Z-Score 'safe zone' (Z={v:.2f}), low bankruptcy risk.",
        metric="z_score",
        value=v,
        severity=_severity_band(v - 2.99, low=0.0, high=2.0),
    )


def _r_low_leverage(s: dict[str, Any]) -> bool:
    v = s.get("net_debt_ebitda")
    return isinstance(v, (int, float)) and v < 1.0


def _b_low_leverage(s: dict[str, Any]) -> SWOTItem:
    v = s["net_debt_ebitda"]
    return SWOTItem(
        text=f"Low leverage (net debt/EBITDA {v:.2f}x) provides balance-sheet flexibility.",
        metric="net_debt_ebitda",
        value=v,
        severity=_severity_band(1.0 - v, low=0.0, high=1.0),
    )


def _r_high_diversification(s: dict[str, Any]) -> bool:
    v = s.get("diversification_score")
    return isinstance(v, (int, float)) and v >= 70


def _b_high_diversification(s: dict[str, Any]) -> SWOTItem:
    v = s["diversification_score"]
    return SWOTItem(
        text=f"Highly diversified revenue base (diversification score {v:.0f}/100) limits single-point-of-failure risk.",
        metric="diversification_score",
        value=v,
        severity=_severity_band(v - 70, low=0, high=20),
    )


def _r_high_management_quality(s: dict[str, Any]) -> bool:
    v = s.get("overall_quality_score")
    return isinstance(v, (int, float)) and v >= 75


def _b_high_management_quality(s: dict[str, Any]) -> SWOTItem:
    v = s["overall_quality_score"]
    return SWOTItem(
        text=f"High-quality management team (overall quality score {v:.0f}/100).",
        metric="overall_quality_score",
        value=v,
        severity=_severity_band(v - 75, low=0, high=15),
    )


def _r_gaining_share(s: dict[str, Any]) -> bool:
    return s.get("market_share_trend") == "GAINING"


def _b_gaining_share(s: dict[str, Any]) -> SWOTItem:
    return SWOTItem(
        text="Gaining market share relative to competitors.",
        metric="market_share_trend",
        value="GAINING",
        severity="MODERATE",
    )


# ── Weaknesses ────────────────────────────────────────────────────────────


def _r_no_narrow_moat(s: dict[str, Any]) -> bool:
    width = s.get("moat_width")
    score = s.get("moat_score")
    return width in ("NONE", "NARROW") and isinstance(score, (int, float)) and score < 40


def _b_no_narrow_moat(s: dict[str, Any]) -> SWOTItem:
    width = s["moat_width"]
    score = s["moat_score"]
    return SWOTItem(
        text=f"Weak competitive moat (width={width}, moat score {score:.0f}/100) -- limited pricing power protection.",
        metric="moat_score",
        value=score,
        severity=_severity_band(40 - score, low=0, high=20),
    )


def _r_elevated_leverage(s: dict[str, Any]) -> bool:
    v = s.get("net_debt_ebitda")
    return isinstance(v, (int, float)) and v > 4.0


def _b_elevated_leverage(s: dict[str, Any]) -> SWOTItem:
    v = s["net_debt_ebitda"]
    return SWOTItem(
        text=f"Elevated leverage (net debt/EBITDA {v:.2f}x) constrains financial flexibility.",
        metric="net_debt_ebitda",
        value=v,
        severity=_severity_band(v - 4.0, low=0.0, high=2.0),
    )


def _r_weak_capital_allocation(s: dict[str, Any]) -> bool:
    v = s.get("overall_score")
    return isinstance(v, (int, float)) and v < 40


def _b_weak_capital_allocation(s: dict[str, Any]) -> SWOTItem:
    v = s["overall_score"]
    return SWOTItem(
        text=f"Weak capital allocation track record (score {v:.0f}/100).",
        metric="overall_score",
        value=v,
        severity=_severity_band(40 - v, low=0, high=20),
    )


def _r_high_customer_concentration(s: dict[str, Any]) -> bool:
    v = s.get("customer_top1_pct")
    return isinstance(v, (int, float)) and v > 30


def _b_high_customer_concentration(s: dict[str, Any]) -> SWOTItem:
    v = s["customer_top1_pct"]
    return SWOTItem(
        text=f"High customer concentration ({v:.0f}% of revenue from top customer).",
        metric="customer_top1_pct",
        value=v,
        severity=_severity_band(v - 30, low=0, high=30),
    )


def _r_losing_share(s: dict[str, Any]) -> bool:
    return s.get("market_share_trend") == "LOSING"


def _b_losing_share(s: dict[str, Any]) -> SWOTItem:
    return SWOTItem(
        text="Losing market share relative to competitors.",
        metric="market_share_trend",
        value="LOSING",
        severity="MODERATE",
    )


def _r_low_diversification(s: dict[str, Any]) -> bool:
    v = s.get("diversification_score")
    return isinstance(v, (int, float)) and v < 30


def _b_low_diversification(s: dict[str, Any]) -> SWOTItem:
    v = s["diversification_score"]
    return SWOTItem(
        text=f"Low revenue diversification (score {v:.0f}/100) -- concentrated exposure.",
        metric="diversification_score",
        value=v,
        severity=_severity_band(30 - v, low=0, high=20),
    )


# ── Opportunities ─────────────────────────────────────────────────────────


def _r_underappreciated_switching_costs(s: dict[str, Any]) -> bool:
    v = s.get("switching_cost_score")
    return isinstance(v, (int, float)) and v >= 60 and s.get("moat_width") != "WIDE"


def _b_underappreciated_switching_costs(s: dict[str, Any]) -> SWOTItem:
    v = s["switching_cost_score"]
    return SWOTItem(
        text=(
            f"High switching-cost score ({v:.0f}/100) not yet reflected in a wide moat rating -- "
            "underappreciated switching-cost advantage could widen the moat."
        ),
        metric="switching_cost_score",
        value=v,
        severity=_severity_band(v - 60, low=0, high=20),
    )


def _r_balance_sheet_capacity(s: dict[str, Any]) -> bool:
    nd = s.get("net_debt_ebitda")
    liq = s.get("liquidity_ratio")
    return isinstance(nd, (int, float)) and nd < 1.5 and isinstance(liq, (int, float)) and liq > 1.5


def _b_balance_sheet_capacity(s: dict[str, Any]) -> SWOTItem:
    nd = s["net_debt_ebitda"]
    liq = s["liquidity_ratio"]
    return SWOTItem(
        text=(
            f"Low leverage (net debt/EBITDA {nd:.2f}x) and healthy liquidity (ratio {liq:.2f}) "
            "provide balance sheet capacity for M&A or buybacks."
        ),
        metric="net_debt_ebitda",
        value=nd,
        severity="MODERATE",
    )


def _r_op_leverage_headroom(s: dict[str, Any]) -> bool:
    v = s.get("operating_leverage")
    return isinstance(v, (int, float)) and 0 < v < 1.5


def _b_op_leverage_headroom(s: dict[str, Any]) -> SWOTItem:
    v = s["operating_leverage"]
    return SWOTItem(
        text=(
            f"Positive operating leverage ({v:.2f}x) suggests further margin expansion "
            "as revenue scales, assuming the ratio holds."
        ),
        metric="operating_leverage",
        value=v,
        severity="LOW",
    )


# ── Threats ───────────────────────────────────────────────────────────────


def _r_high_cyclicality(s: dict[str, Any]) -> bool:
    v = s.get("cyclicality_score")
    return isinstance(v, (int, float)) and v >= 70


def _b_high_cyclicality(s: dict[str, Any]) -> SWOTItem:
    v = s["cyclicality_score"]
    return SWOTItem(
        text=f"Highly cyclical revenue base (cyclicality score {v:.0f}/100) -- exposed to macro downturns.",
        metric="cyclicality_score",
        value=v,
        severity=_severity_band(v - 70, low=0, high=20),
    )


def _r_high_disruption_vulnerability(s: dict[str, Any]) -> bool:
    v = s.get("disruption_vulnerability")
    return isinstance(v, (int, float)) and v >= 65


def _b_high_disruption_vulnerability(s: dict[str, Any]) -> SWOTItem:
    v = s["disruption_vulnerability"]
    return SWOTItem(
        text=f"Elevated disruption vulnerability (score {v:.0f}/100) -- business model exposed to substitution risk.",
        metric="disruption_vulnerability",
        value=v,
        severity=_severity_band(v - 65, low=0, high=25),
    )


def _r_elevated_beneish(s: dict[str, Any]) -> bool:
    v = s.get("beneish_m_score")
    return isinstance(v, (int, float)) and v > -1.78


def _b_elevated_beneish(s: dict[str, Any]) -> SWOTItem:
    v = s["beneish_m_score"]
    return SWOTItem(
        text=(
            f"Beneish M-Score of {v:.2f} is above the -1.78 threshold, indicating an elevated "
            "statistical earnings-manipulation risk score -- not an accusation, a screening flag "
            "worth independent diligence."
        ),
        metric="beneish_m_score",
        value=v,
        severity=_severity_band(v - (-1.78), low=0.0, high=1.0),
    )


def _r_high_concentration_risk(s: dict[str, Any]) -> bool:
    label = s.get("overall_concentration_risk")
    score = s.get("overall_risk_score")
    return label == "HIGH" or (isinstance(score, (int, float)) and score > 70)


def _b_high_concentration_risk(s: dict[str, Any]) -> SWOTItem:
    score = s.get("overall_risk_score")
    label = s.get("overall_concentration_risk")
    if isinstance(score, (int, float)):
        text = f"High overall concentration risk (score {score:.0f}/100)."
        metric, value = "overall_risk_score", score
        severity = _severity_band(score - 70, low=0, high=15)
    else:
        text = f"High overall concentration risk (rated {label})."
        metric, value = "overall_concentration_risk", label
        severity = "HIGH"
    return SWOTItem(text=text, metric=metric, value=value, severity=severity)


def _r_refinancing_risk(s: dict[str, Any]) -> bool:
    v = s.get("refinancing_risk_score")
    return isinstance(v, (int, float)) and v > 60


def _b_refinancing_risk(s: dict[str, Any]) -> SWOTItem:
    v = s["refinancing_risk_score"]
    return SWOTItem(
        text=f"Elevated refinancing risk (score {v:.0f}/100) -- upcoming debt maturities face unfavorable conditions.",
        metric="refinancing_risk_score",
        value=v,
        severity=_severity_band(v - 60, low=0, high=20),
    )


# ── Rule table ────────────────────────────────────────────────────────────
#
# rule_id -> bucket -> threshold summary (kept in sync with the docstring
# below and with the task's rule spec):
#
#   wide_moat                          strengths     moat_width == "WIDE"
#   high_capital_allocation            strengths     overall_score >= 70
#   positive_roic_spread               strengths     roic_vs_wacc_spread > 0.02
#   strong_balance_sheet                strengths     z_score > 2.99
#   low_leverage                       strengths     net_debt_ebitda < 1.0
#   high_diversification               strengths     diversification_score >= 70
#   high_management_quality            strengths     overall_quality_score >= 75
#   gaining_share                      strengths     market_share_trend == "GAINING"
#   no_narrow_moat                     weaknesses    moat_width in (NONE,NARROW) and moat_score < 40
#   elevated_leverage                  weaknesses    net_debt_ebitda > 4.0
#   weak_capital_allocation            weaknesses    overall_score < 40
#   high_customer_concentration        weaknesses    customer_top1_pct > 30
#   losing_share                       weaknesses    market_share_trend == "LOSING"
#   low_diversification                weaknesses    diversification_score < 30
#   underappreciated_switching_costs   opportunities switching_cost_score >= 60 and moat_width != WIDE
#   balance_sheet_capacity             opportunities net_debt_ebitda < 1.5 and liquidity_ratio > 1.5
#   op_leverage_headroom               opportunities 0 < operating_leverage < 1.5
#   high_cyclicality                   threats       cyclicality_score >= 70
#   high_disruption_vulnerability      threats       disruption_vulnerability >= 65
#   elevated_beneish                   threats       beneish_m_score > -1.78
#   high_concentration_risk            threats       overall_concentration_risk == HIGH or overall_risk_score > 70
#   refinancing_risk                   threats       refinancing_risk_score > 60
#
_RULES: tuple[_Rule, ...] = (
    # Strengths
    _Rule("strengths", "wide_moat", _r_wide_moat, _b_wide_moat),
    _Rule("strengths", "high_capital_allocation", _r_high_capital_allocation, _b_high_capital_allocation),
    _Rule("strengths", "positive_roic_spread", _r_positive_roic_spread, _b_positive_roic_spread),
    _Rule("strengths", "strong_balance_sheet", _r_strong_balance_sheet, _b_strong_balance_sheet),
    _Rule("strengths", "low_leverage", _r_low_leverage, _b_low_leverage),
    _Rule("strengths", "high_diversification", _r_high_diversification, _b_high_diversification),
    _Rule("strengths", "high_management_quality", _r_high_management_quality, _b_high_management_quality),
    _Rule("strengths", "gaining_share", _r_gaining_share, _b_gaining_share),
    # Weaknesses
    _Rule("weaknesses", "no_narrow_moat", _r_no_narrow_moat, _b_no_narrow_moat),
    _Rule("weaknesses", "elevated_leverage", _r_elevated_leverage, _b_elevated_leverage),
    _Rule("weaknesses", "weak_capital_allocation", _r_weak_capital_allocation, _b_weak_capital_allocation),
    _Rule(
        "weaknesses",
        "high_customer_concentration",
        _r_high_customer_concentration,
        _b_high_customer_concentration,
    ),
    _Rule("weaknesses", "losing_share", _r_losing_share, _b_losing_share),
    _Rule("weaknesses", "low_diversification", _r_low_diversification, _b_low_diversification),
    # Opportunities
    _Rule(
        "opportunities",
        "underappreciated_switching_costs",
        _r_underappreciated_switching_costs,
        _b_underappreciated_switching_costs,
    ),
    _Rule("opportunities", "balance_sheet_capacity", _r_balance_sheet_capacity, _b_balance_sheet_capacity),
    _Rule("opportunities", "op_leverage_headroom", _r_op_leverage_headroom, _b_op_leverage_headroom),
    # Threats
    _Rule("threats", "high_cyclicality", _r_high_cyclicality, _b_high_cyclicality),
    _Rule(
        "threats",
        "high_disruption_vulnerability",
        _r_high_disruption_vulnerability,
        _b_high_disruption_vulnerability,
    ),
    _Rule("threats", "elevated_beneish", _r_elevated_beneish, _b_elevated_beneish),
    _Rule("threats", "high_concentration_risk", _r_high_concentration_risk, _b_high_concentration_risk),
    _Rule("threats", "refinancing_risk", _r_refinancing_risk, _b_refinancing_risk),
)


# ── Orchestrator ──────────────────────────────────────────────────────────


def derive_swot(signals: dict[str, Any]) -> SWOTResult:
    """Evaluate every rule in `_RULES` against `signals` and bucket the ones that fire.

    Parameters
    ----------
    signals : dict
        Flat dict of real, already-computed quantitative signals sourced
        from `MoatAssessment`, `BusinessModelAnalysis`,
        `BalanceSheetRiskAssessment`, `CapitalAllocationAssessment`,
        `ManagementQualityAssessment`, and `ConcentrationRiskAssessment`.
        See `KNOWN_SIGNAL_KEYS` for the full accepted key list. Every key is
        optional; a missing or None value simply means no rule keyed to it
        can fire -- it is never treated as 0 or as a negative judgment.

    Returns
    -------
    SWOTResult
        Four buckets of `SWOTItem`, each traceable to a real metric/value,
        plus `signals_available` -- an honest count of how many of the
        known input signals were actually present (non-None), so a caller
        can gauge how complete a picture this SWOT is built on.
    """
    result = SWOTResult()
    buckets: dict[str, list[SWOTItem]] = {
        "strengths": result.strengths,
        "weaknesses": result.weaknesses,
        "opportunities": result.opportunities,
        "threats": result.threats,
    }

    for rule in _RULES:
        try:
            fires = rule.condition(signals)
        except Exception:
            logger.warning("SWOT rule %r condition raised; skipping", rule.rule_id, exc_info=True)
            continue
        if not fires:
            continue
        try:
            item = rule.build(signals)
        except Exception:
            logger.warning("SWOT rule %r build raised after firing; skipping", rule.rule_id, exc_info=True)
            continue
        buckets[rule.bucket].append(item)

    result.signals_available = sum(1 for k in KNOWN_SIGNAL_KEYS if signals.get(k) is not None)
    return result
