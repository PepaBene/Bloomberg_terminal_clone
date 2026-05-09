"""Pillar 3 Phase 2 — Part 7d: Management Quality Analysis Engine.

Pure computation engine for assessing management and governance quality:
execution track record, accounting red flags, compensation alignment.

No database access — all functions accept and return plain data.
Reuses compute_pay_alignment() and detect_red_flags() from governance_scoring.py.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field


# ── Dataclasses ───────────────────────────────────────────────────────────


@dataclass
class ExecutionTrackRecord:
    """Management execution quality metrics."""

    guidance_accuracy_score: float | None = None  # 0-100
    strategic_consistency_score: float | None = None  # 0-100
    margin_stability_score: float | None = None  # 0-100
    wc_management_score: float | None = None  # 0-100
    composite_execution_score: float | None = None  # 0-100


@dataclass
class AccountingRedFlag:
    """Individual accounting red flag."""

    flag: str
    severity: str  # CRITICAL/HIGH/MEDIUM
    detail: str
    value: float | None = None


@dataclass
class CompensationAlignment:
    """CEO compensation alignment assessment."""

    pay_vs_tsr: str = "UNKNOWN"  # ALIGNED/MISALIGNED/NEUTRAL
    pay_vs_revenue_growth: str = "UNKNOWN"
    pay_vs_roic: str = "UNKNOWN"
    ltip_pct: float | None = None
    insider_ownership_pct: float | None = None
    alignment_score: float = 50.0  # 0-100


@dataclass
class ManagementQualityResult:
    """Complete management quality assessment."""

    execution: ExecutionTrackRecord = field(default_factory=ExecutionTrackRecord)
    accounting_flags: list[AccountingRedFlag] = field(default_factory=list)
    compensation: CompensationAlignment = field(default_factory=CompensationAlignment)
    governance_score: float | None = None
    overall_quality_score: float = 50.0  # 0-100
    red_flags: list[dict] = field(default_factory=list)


# ── Execution Track Record ────────────────────────────────────────────────


def compute_guidance_accuracy_score(
    guidance_history: list[dict],
) -> float | None:
    """Score guidance accuracy from 0-100.

    Parameters
    ----------
    guidance_history : list[dict]
        Each: {guidance_midpoint, actual}
    """
    if not guidance_history:
        return None

    errors = []
    for g in guidance_history:
        mid = g.get("guidance_midpoint")
        actual = g.get("actual")
        if mid is not None and actual is not None and actual != 0:
            error = abs(mid - actual) / abs(actual)
            errors.append(error)

    if not errors:
        return None

    avg_error = statistics.mean(errors)
    # 0% error → 100 score, 20%+ error → 0 score
    score = max(0.0, (1.0 - avg_error / 0.20) * 100.0)
    return round(min(score, 100.0), 2)


def compute_strategic_consistency_score(
    filing_diff_data: dict | None,
) -> float | None:
    """Score strategic consistency from filing diff analysis.

    Parameters
    ----------
    filing_diff_data : dict | None
        Expected keys: business_description_change_pct, strategy_change_count (over 3 years)
    """
    if not filing_diff_data:
        return None

    change_pct = filing_diff_data.get("business_description_change_pct", 0)
    strategy_pivots = filing_diff_data.get("strategy_change_count", 0)

    # Lower change = higher consistency
    score = 100.0
    score -= min(change_pct * 2, 40.0)  # 20% change → -40 pts
    score -= min(strategy_pivots * 15.0, 40.0)  # 3+ pivots → -45 pts

    return round(max(0.0, min(100.0, score)), 2)


def compute_margin_stability_score(
    margin_history: list[float],
) -> float | None:
    """Score margin stability through cycles.

    Low volatility = high score. Consistent margins indicate operational discipline.
    """
    if len(margin_history) < 3:
        return None

    vol = statistics.stdev(margin_history)

    # 0% volatility → 100, 10%+ → 0
    score = max(0.0, (1.0 - vol / 0.10) * 100.0)
    return round(min(score, 100.0), 2)


def compute_wc_management_score(
    ccc_history: list[float],
) -> float | None:
    """Score working capital management from CCC trend.

    Improving (declining CCC) = high score. Deteriorating = low score.
    """
    if len(ccc_history) < 2:
        return None

    first = statistics.mean(ccc_history[: len(ccc_history) // 2])
    second = statistics.mean(ccc_history[len(ccc_history) // 2 :])

    if first == 0:
        return 50.0

    improvement = (first - second) / abs(first)  # Positive = CCC decreased = good

    # Map improvement to score: -20% improvement → 0, 0% → 50, +20% → 100
    score = 50.0 + improvement * 250.0
    return round(max(0.0, min(100.0, score)), 2)


def assess_execution_track_record(
    guidance_history: list[dict] | None = None,
    filing_diff_data: dict | None = None,
    margin_history: list[float] | None = None,
    ccc_history: list[float] | None = None,
) -> ExecutionTrackRecord:
    """Compute composite execution track record."""
    ga = compute_guidance_accuracy_score(guidance_history or [])
    sc = compute_strategic_consistency_score(filing_diff_data)
    ms = compute_margin_stability_score(margin_history or [])
    wc = compute_wc_management_score(ccc_history or [])

    # Composite: weighted average of available scores
    scores = [(ga, 0.30), (sc, 0.25), (ms, 0.25), (wc, 0.20)]
    available = [(s, w) for s, w in scores if s is not None]

    composite = None
    if available:
        total_weight = sum(w for _, w in available)
        composite = sum(s * w for s, w in available) / total_weight
        composite = round(composite, 2)

    return ExecutionTrackRecord(
        guidance_accuracy_score=ga,
        strategic_consistency_score=sc,
        margin_stability_score=ms,
        wc_management_score=wc,
        composite_execution_score=composite,
    )


# ── Accounting Red Flags ──────────────────────────────────────────────────


def detect_accounting_red_flags(data: dict) -> list[AccountingRedFlag]:
    """Detect accounting quality red flags.

    Parameters
    ----------
    data : dict
        Expected keys: beneish_m_score, accruals_quality, auditor_change,
        restatement_history, revenue_vs_receivables_divergence
    """
    flags: list[AccountingRedFlag] = []

    # Beneish M-Score
    m_score = data.get("beneish_m_score")
    if m_score is not None and m_score > -1.78:
        flags.append(AccountingRedFlag(
            flag="HIGH_MANIPULATION_RISK",
            severity="CRITICAL",
            detail=f"Beneish M-Score {m_score:.2f} exceeds -1.78 threshold",
            value=m_score,
        ))

    # Accruals quality
    accruals = data.get("accruals_quality")
    if accruals is not None and accruals > 0.10:
        flags.append(AccountingRedFlag(
            flag="HIGH_ACCRUALS",
            severity="HIGH",
            detail=f"Accruals quality {accruals:.2%} indicates potential earnings management",
            value=accruals,
        ))

    # Auditor change
    if data.get("auditor_change"):
        flags.append(AccountingRedFlag(
            flag="AUDITOR_CHANGE",
            severity="HIGH",
            detail="Company changed auditor — investigate reason",
        ))

    # Restatement history
    restatements = data.get("restatement_count", 0)
    if restatements > 0:
        flags.append(AccountingRedFlag(
            flag="RESTATEMENT_HISTORY",
            severity="CRITICAL",
            detail=f"Company has {restatements} restatement(s) in history",
            value=float(restatements),
        ))

    # Revenue vs receivables divergence
    rev_recv = data.get("revenue_vs_receivables_divergence")
    if rev_recv is not None and rev_recv > 0.15:
        flags.append(AccountingRedFlag(
            flag="REVENUE_RECEIVABLES_DIVERGENCE",
            severity="MEDIUM",
            detail=f"Receivables growing {rev_recv:.0%} faster than revenue",
            value=rev_recv,
        ))

    return flags


# ── Compensation Alignment ────────────────────────────────────────────────


def assess_compensation_alignment(
    ceo_comp_growth: float | None,
    tsr: float | None,
    revenue_growth: float | None,
    roic: float | None,
    ltip_pct: float | None = None,
    insider_ownership_pct: float | None = None,
) -> CompensationAlignment:
    """Assess CEO compensation alignment with company performance."""
    score = 50.0
    pay_vs_tsr = "UNKNOWN"
    pay_vs_rev = "UNKNOWN"
    pay_vs_roic = "UNKNOWN"

    if ceo_comp_growth is not None and tsr is not None:
        if ceo_comp_growth > tsr + 0.10:
            pay_vs_tsr = "MISALIGNED"
            score -= 15.0
        elif abs(ceo_comp_growth - tsr) < 0.10:
            pay_vs_tsr = "ALIGNED"
            score += 10.0
        else:
            pay_vs_tsr = "NEUTRAL"

    if ceo_comp_growth is not None and revenue_growth is not None:
        if ceo_comp_growth > revenue_growth + 0.15:
            pay_vs_rev = "MISALIGNED"
            score -= 10.0
        elif abs(ceo_comp_growth - revenue_growth) < 0.15:
            pay_vs_rev = "ALIGNED"
            score += 5.0
        else:
            pay_vs_rev = "NEUTRAL"

    if roic is not None:
        if roic > 0.15:
            pay_vs_roic = "ALIGNED"
            score += 10.0
        elif roic < 0.05:
            pay_vs_roic = "MISALIGNED"
            score -= 10.0
        else:
            pay_vs_roic = "NEUTRAL"

    # LTIP bonus
    if ltip_pct is not None:
        if ltip_pct > 0.60:
            score += 10.0
        elif ltip_pct < 0.30:
            score -= 10.0

    # Insider ownership bonus
    if insider_ownership_pct is not None:
        if insider_ownership_pct > 5.0:
            score += 10.0
        elif insider_ownership_pct > 1.0:
            score += 5.0

    score = max(0.0, min(100.0, round(score, 2)))

    return CompensationAlignment(
        pay_vs_tsr=pay_vs_tsr,
        pay_vs_revenue_growth=pay_vs_rev,
        pay_vs_roic=pay_vs_roic,
        ltip_pct=ltip_pct,
        insider_ownership_pct=insider_ownership_pct,
        alignment_score=score,
    )


# ── Overall Quality Score ─────────────────────────────────────────────────


def compute_management_quality_score(
    execution: ExecutionTrackRecord,
    accounting_flags: list[AccountingRedFlag],
    governance_score: float | None,
    compensation: CompensationAlignment,
) -> float:
    """Compute overall management quality score (0-100).

    Components (weights sum to 1.00):
    - Execution track record  (0.35)
    - Accounting quality      (0.25 — applied as deductions for flags)
    - Governance              (0.20)
    - Compensation alignment  (0.20)
    """
    score = 50.0  # Baseline

    # Execution: scale a 0-100 sub-score by its weight relative to baseline.
    if execution.composite_execution_score is not None:
        score += (execution.composite_execution_score - 50) * 0.35

    # Accounting deductions
    for flag in accounting_flags:
        if flag.severity == "CRITICAL":
            score -= 15.0
        elif flag.severity == "HIGH":
            score -= 8.0
        elif flag.severity == "MEDIUM":
            score -= 4.0

    # Governance
    if governance_score is not None:
        score += (governance_score - 50) * 0.20

    # Compensation alignment
    score += (compensation.alignment_score - 50) * 0.20

    return max(0.0, min(100.0, round(score, 2)))


# ── Orchestrator ──────────────────────────────────────────────────────────


def assess_management_quality(
    data: dict,
    guidance_history: list[dict] | None = None,
    filing_diff_data: dict | None = None,
    margin_history: list[float] | None = None,
    ccc_history: list[float] | None = None,
) -> ManagementQualityResult:
    """Complete management quality assessment.

    Parameters
    ----------
    data : dict
        Expected keys: beneish_m_score, accruals_quality, auditor_change,
        restatement_count, ceo_comp_growth, tsr, revenue_growth, roic,
        ltip_pct, insider_ownership_pct, governance_score
    """
    execution = assess_execution_track_record(
        guidance_history, filing_diff_data, margin_history, ccc_history,
    )
    acct_flags = detect_accounting_red_flags(data)
    comp = assess_compensation_alignment(
        data.get("ceo_comp_growth"),
        data.get("tsr"),
        data.get("revenue_growth"),
        data.get("roic"),
        data.get("ltip_pct"),
        data.get("insider_ownership_pct"),
    )

    gov_score = data.get("governance_score")

    overall = compute_management_quality_score(execution, acct_flags, gov_score, comp)

    # Compile all red flags
    all_flags = [{"flag": f.flag, "severity": f.severity, "detail": f.detail} for f in acct_flags]

    return ManagementQualityResult(
        execution=execution,
        accounting_flags=acct_flags,
        compensation=comp,
        governance_score=gov_score,
        overall_quality_score=overall,
        red_flags=all_flags,
    )
