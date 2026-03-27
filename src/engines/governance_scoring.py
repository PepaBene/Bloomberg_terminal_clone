"""Pillar 3 Phase 1 — Part 6: Governance Scoring Engine.

Pure computation engine for governance assessment and red flag detection.
Evaluates board composition, pay alignment, shareholder proposals, and
structural governance risks.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

from statistics import mean, median


# ── Red Flag Definitions ────────────────────────────────────────────────

RED_FLAG_CHECKS = {
    "dual_class": {
        "weight": 15,
        "severity": "HIGH",
        "desc": "Dual-class share structure (unequal voting rights)",
    },
    "ceo_is_chair": {
        "weight": 10,
        "severity": "MEDIUM",
        "desc": "CEO and Chairman are same person",
    },
    "low_independence": {
        "weight": 12,
        "severity": "HIGH",
        "desc": "Board independence below 67%",
    },
    "high_tenure": {
        "weight": 8,
        "severity": "MEDIUM",
        "desc": "Average board tenure exceeds 12 years",
    },
    "poison_pill": {
        "weight": 10,
        "severity": "HIGH",
        "desc": "Poison pill / shareholder rights plan in effect",
    },
    "staggered_board": {
        "weight": 8,
        "severity": "MEDIUM",
        "desc": "Staggered board (limits accountability)",
    },
    "high_pay_ratio": {
        "weight": 10,
        "severity": "HIGH",
        "desc": "CEO pay / median employee ratio exceeds 300x",
    },
    "related_party": {
        "weight": 12,
        "severity": "HIGH",
        "desc": "Excessive related-party transactions",
    },
    "low_ltip_pct": {
        "weight": 8,
        "severity": "MEDIUM",
        "desc": "Long-term incentive < 40% of CEO total comp",
    },
    "no_majority_voting": {
        "weight": 7,
        "severity": "MEDIUM",
        "desc": "No majority voting requirement for directors",
    },
}

SCORE_CLASSIFICATIONS = {
    (80, 101): "STRONG",
    (60, 80): "ADEQUATE",
    (40, 60): "CONCERNS",
    (0, 40): "SIGNIFICANT_RISK",
}


# ── Red Flag Detection ──────────────────────────────────────────────────


def detect_red_flags(governance_data: dict) -> list[dict]:
    """Check all 10 red flag conditions against supplied governance data.

    Parameters
    ----------
    governance_data : dict
        Keys matching the flag names:
        - dual_class: bool
        - ceo_is_chair: bool
        - board_independence_pct: float  (0-100)
        - avg_board_tenure: float  (years)
        - has_poison_pill: bool
        - has_staggered_board: bool
        - ceo_pay_ratio: float | None
        - related_party_flag: bool
        - long_term_incentive_pct: float | None  (0-100)
        - has_majority_voting: bool

    Returns
    -------
    list[dict]
        Each dict has {flag, severity, detail, weight}.
    """
    flags: list[dict] = []

    # dual_class
    if governance_data.get("dual_class"):
        flags.append({
            "flag": "dual_class",
            "severity": RED_FLAG_CHECKS["dual_class"]["severity"],
            "detail": RED_FLAG_CHECKS["dual_class"]["desc"],
            "weight": RED_FLAG_CHECKS["dual_class"]["weight"],
        })

    # ceo_is_chair
    if governance_data.get("ceo_is_chair"):
        flags.append({
            "flag": "ceo_is_chair",
            "severity": RED_FLAG_CHECKS["ceo_is_chair"]["severity"],
            "detail": RED_FLAG_CHECKS["ceo_is_chair"]["desc"],
            "weight": RED_FLAG_CHECKS["ceo_is_chair"]["weight"],
        })

    # low_independence — board independence below 67%
    independence = governance_data.get("board_independence_pct")
    if independence is not None and independence < 67.0:
        flags.append({
            "flag": "low_independence",
            "severity": RED_FLAG_CHECKS["low_independence"]["severity"],
            "detail": (
                f"{RED_FLAG_CHECKS['low_independence']['desc']} "
                f"(actual: {independence:.1f}%)"
            ),
            "weight": RED_FLAG_CHECKS["low_independence"]["weight"],
        })

    # high_tenure — average board tenure exceeds 12 years
    tenure = governance_data.get("avg_board_tenure")
    if tenure is not None and tenure > 12.0:
        flags.append({
            "flag": "high_tenure",
            "severity": RED_FLAG_CHECKS["high_tenure"]["severity"],
            "detail": (
                f"{RED_FLAG_CHECKS['high_tenure']['desc']} "
                f"(actual: {tenure:.1f} years)"
            ),
            "weight": RED_FLAG_CHECKS["high_tenure"]["weight"],
        })

    # poison_pill
    if governance_data.get("has_poison_pill"):
        flags.append({
            "flag": "poison_pill",
            "severity": RED_FLAG_CHECKS["poison_pill"]["severity"],
            "detail": RED_FLAG_CHECKS["poison_pill"]["desc"],
            "weight": RED_FLAG_CHECKS["poison_pill"]["weight"],
        })

    # staggered_board
    if governance_data.get("has_staggered_board"):
        flags.append({
            "flag": "staggered_board",
            "severity": RED_FLAG_CHECKS["staggered_board"]["severity"],
            "detail": RED_FLAG_CHECKS["staggered_board"]["desc"],
            "weight": RED_FLAG_CHECKS["staggered_board"]["weight"],
        })

    # high_pay_ratio — CEO pay / median employee ratio exceeds 300x
    pay_ratio = governance_data.get("ceo_pay_ratio")
    if pay_ratio is not None and pay_ratio > 300.0:
        flags.append({
            "flag": "high_pay_ratio",
            "severity": RED_FLAG_CHECKS["high_pay_ratio"]["severity"],
            "detail": (
                f"{RED_FLAG_CHECKS['high_pay_ratio']['desc']} "
                f"(actual: {pay_ratio:.0f}x)"
            ),
            "weight": RED_FLAG_CHECKS["high_pay_ratio"]["weight"],
        })

    # related_party
    if governance_data.get("related_party_flag"):
        flags.append({
            "flag": "related_party",
            "severity": RED_FLAG_CHECKS["related_party"]["severity"],
            "detail": RED_FLAG_CHECKS["related_party"]["desc"],
            "weight": RED_FLAG_CHECKS["related_party"]["weight"],
        })

    # low_ltip_pct — long-term incentive < 40% of CEO total comp
    ltip = governance_data.get("long_term_incentive_pct")
    if ltip is not None and ltip < 40.0:
        flags.append({
            "flag": "low_ltip_pct",
            "severity": RED_FLAG_CHECKS["low_ltip_pct"]["severity"],
            "detail": (
                f"{RED_FLAG_CHECKS['low_ltip_pct']['desc']} "
                f"(actual: {ltip:.1f}%)"
            ),
            "weight": RED_FLAG_CHECKS["low_ltip_pct"]["weight"],
        })

    # no_majority_voting
    if not governance_data.get("has_majority_voting", True):
        flags.append({
            "flag": "no_majority_voting",
            "severity": RED_FLAG_CHECKS["no_majority_voting"]["severity"],
            "detail": RED_FLAG_CHECKS["no_majority_voting"]["desc"],
            "weight": RED_FLAG_CHECKS["no_majority_voting"]["weight"],
        })

    return flags


# ── Governance Score Computation ─────────────────────────────────────────


def _classify_score(score: int) -> str:
    """Map a numeric governance score to a classification label."""
    for (low, high), label in SCORE_CLASSIFICATIONS.items():
        if low <= score < high:
            return label
    return "SIGNIFICANT_RISK"


def compute_governance_score(governance_data: dict) -> dict:
    """Compute overall governance score (100 = perfect, deductions per flag).

    Parameters
    ----------
    governance_data : dict
        Same keys as :func:`detect_red_flags`.

    Returns
    -------
    dict
        {score, classification, red_flags, total_deductions}
    """
    red_flags = detect_red_flags(governance_data)
    total_deductions = sum(f["weight"] for f in red_flags)
    score = max(0, 100 - total_deductions)
    classification = _classify_score(score)

    return {
        "score": score,
        "classification": classification,
        "red_flags": red_flags,
        "total_deductions": total_deductions,
    }


# ── Pay Alignment ────────────────────────────────────────────────────────


def compute_pay_alignment(
    ceo_comp: dict,
    company_performance: dict,
    peer_comp: list[dict] | None = None,
) -> dict:
    """Assess CEO pay-for-performance alignment.

    Parameters
    ----------
    ceo_comp : dict
        - total_compensation: float
        - yoy_change_pct: float  (year-over-year change in comp, %)
    company_performance : dict
        - tsr_1y: float  (total shareholder return, %)
        - revenue_growth_pct: float
        - roic: float  (return on invested capital, %)
    peer_comp : list[dict] | None
        List of {total_compensation: float} for peer companies.

    Returns
    -------
    dict
        {alignment_score (0-100), pay_vs_performance, metrics, peer_comparison}
    """
    comp_change = ceo_comp.get("yoy_change_pct", 0.0)
    tsr = company_performance.get("tsr_1y", 0.0)
    revenue_growth = company_performance.get("revenue_growth_pct", 0.0)
    roic = company_performance.get("roic", 0.0)

    # --- Alignment scoring ---
    # Core idea: pay growth should track performance growth.
    # If TSR and revenue are positive but pay grew much faster, alignment is poor.
    # If TSR is negative but pay grew, alignment is very poor.

    alignment_score = 50  # neutral start

    # TSR alignment (biggest weight): +/- 30 points
    tsr_gap = comp_change - tsr
    if tsr < 0 and comp_change > 0:
        # Pay rose while shareholders lost money
        alignment_score -= 30
    elif tsr_gap > 20:
        # Pay growth greatly exceeded TSR
        alignment_score -= 20
    elif tsr_gap > 10:
        alignment_score -= 10
    elif abs(tsr_gap) <= 10:
        # Pay growth roughly tracks TSR — good
        alignment_score += 20
    elif tsr_gap < -10:
        # Pay grew less than performance — conservative, reward
        alignment_score += 25

    # Revenue alignment: +/- 10 points
    rev_gap = comp_change - revenue_growth
    if revenue_growth < 0 and comp_change > 5:
        alignment_score -= 10
    elif abs(rev_gap) <= 15:
        alignment_score += 10

    # ROIC bonus: above 15% is strong capital allocation
    if roic >= 15:
        alignment_score += 10
    elif roic >= 10:
        alignment_score += 5

    # Clamp to 0-100
    alignment_score = max(0, min(100, alignment_score))

    # Label
    if alignment_score >= 70:
        pay_vs_performance = "WELL_ALIGNED"
    elif alignment_score >= 45:
        pay_vs_performance = "MODERATE"
    else:
        pay_vs_performance = "MISALIGNED"

    metrics = {
        "comp_yoy_change_pct": comp_change,
        "tsr_1y": tsr,
        "revenue_growth_pct": revenue_growth,
        "roic": roic,
    }

    # Peer comparison
    peer_comparison: dict | None = None
    if peer_comp is not None and len(peer_comp) > 0:
        peer_totals = [p["total_compensation"] for p in peer_comp]
        ceo_total = ceo_comp.get("total_compensation", 0.0)
        peer_med = median(peer_totals)
        peer_avg = mean(peer_totals)
        ratio_to_median = (
            round(ceo_total / peer_med, 2) if peer_med else None
        )
        peer_comparison = {
            "ceo_total_compensation": ceo_total,
            "peer_median": peer_med,
            "peer_average": round(peer_avg, 2),
            "ratio_to_peer_median": ratio_to_median,
            "peer_count": len(peer_totals),
        }

    return {
        "alignment_score": alignment_score,
        "pay_vs_performance": pay_vs_performance,
        "metrics": metrics,
        "peer_comparison": peer_comparison,
    }


# ── Board Diversity ──────────────────────────────────────────────────────


def compute_board_diversity(board_members: list[dict]) -> dict:
    """Compute board composition and diversity metrics.

    Parameters
    ----------
    board_members : list[dict]
        Each member dict has:
        - is_independent: bool
        - is_chair: bool
        - tenure_years: float
        - age: int
        - gender: str  ("M", "F", "NB", etc.)
        - expertise_areas: list[str]
        - other_boards: list[str]

    Returns
    -------
    dict
        {total_directors, independent_count, independent_pct,
         gender_diversity_pct, avg_tenure, avg_age,
         expertise_mix: dict, interlock_count}
    """
    total = len(board_members)
    if total == 0:
        return {
            "total_directors": 0,
            "independent_count": 0,
            "independent_pct": 0.0,
            "gender_diversity_pct": 0.0,
            "avg_tenure": 0.0,
            "avg_age": 0.0,
            "expertise_mix": {},
            "interlock_count": 0,
        }

    independent_count = sum(1 for m in board_members if m.get("is_independent"))
    independent_pct = round((independent_count / total) * 100, 1)

    # Gender diversity: percentage of non-male directors
    non_male = sum(1 for m in board_members if m.get("gender", "M") != "M")
    gender_diversity_pct = round((non_male / total) * 100, 1)

    tenures = [m.get("tenure_years", 0) for m in board_members]
    ages = [m.get("age", 0) for m in board_members]
    avg_tenure = round(mean(tenures), 1) if tenures else 0.0
    avg_age = round(mean(ages), 1) if ages else 0.0

    # Expertise mix: count directors per expertise area
    expertise_mix: dict[str, int] = {}
    for m in board_members:
        for area in m.get("expertise_areas", []):
            expertise_mix[area] = expertise_mix.get(area, 0) + 1

    # Interlock count: directors serving on 3+ other boards
    interlock_count = sum(
        1 for m in board_members if len(m.get("other_boards", [])) >= 3
    )

    return {
        "total_directors": total,
        "independent_count": independent_count,
        "independent_pct": independent_pct,
        "gender_diversity_pct": gender_diversity_pct,
        "avg_tenure": avg_tenure,
        "avg_age": avg_age,
        "expertise_mix": expertise_mix,
        "interlock_count": interlock_count,
    }


# ── Board Interlocks ─────────────────────────────────────────────────────


def detect_board_interlocks(board_members: list[dict]) -> list[dict]:
    """Find directors serving on multiple external boards.

    Parameters
    ----------
    board_members : list[dict]
        Each member has at minimum:
        - name: str  (or person_name)
        - other_boards: list[str]

    Returns
    -------
    list[dict]
        [{person_name, boards, interlock_count}] for directors on 2+ other boards.
    """
    interlocks: list[dict] = []
    for m in board_members:
        other = m.get("other_boards", [])
        if len(other) >= 2:
            name = m.get("person_name") or m.get("name", "Unknown")
            interlocks.append({
                "person_name": name,
                "boards": other,
                "interlock_count": len(other),
            })

    # Sort by interlock count descending
    interlocks.sort(key=lambda x: -x["interlock_count"])
    return interlocks


# ── Shareholder Proposal Analysis ────────────────────────────────────────


def analyze_shareholder_proposals(proposals: list[dict]) -> dict:
    """Analyze shareholder proposal voting results.

    Parameters
    ----------
    proposals : list[dict]
        Each proposal has:
        - topic: str
        - vote_for_pct: float  (0-100)
        - management_recommendation: str  ("FOR" or "AGAINST")
        - passed: bool

    Returns
    -------
    dict
        {total_proposals, by_topic, avg_support_pct,
         proposals_over_50pct, management_overrides}
    """
    total = len(proposals)
    if total == 0:
        return {
            "total_proposals": 0,
            "by_topic": {},
            "avg_support_pct": 0.0,
            "proposals_over_50pct": 0,
            "management_overrides": 0,
        }

    # By topic
    by_topic: dict[str, dict] = {}
    for p in proposals:
        topic = p.get("topic", "Other")
        if topic not in by_topic:
            by_topic[topic] = {"count": 0, "total_support": 0.0, "passed": 0}
        by_topic[topic]["count"] += 1
        by_topic[topic]["total_support"] += p.get("vote_for_pct", 0.0)
        if p.get("passed"):
            by_topic[topic]["passed"] += 1

    # Compute average support per topic
    for topic_data in by_topic.values():
        cnt = topic_data["count"]
        topic_data["avg_support_pct"] = round(
            topic_data["total_support"] / cnt, 1,
        ) if cnt else 0.0

    support_values = [p.get("vote_for_pct", 0.0) for p in proposals]
    avg_support_pct = round(mean(support_values), 1)

    proposals_over_50 = sum(
        1 for p in proposals if p.get("vote_for_pct", 0.0) > 50.0
    )

    # Management overrides: proposals that passed but management recommended
    # AGAINST, or proposals that failed but management recommended FOR
    management_overrides = sum(
        1
        for p in proposals
        if (
            (p.get("passed") and p.get("management_recommendation") == "AGAINST")
            or (
                not p.get("passed")
                and p.get("management_recommendation") == "FOR"
            )
        )
    )

    return {
        "total_proposals": total,
        "by_topic": by_topic,
        "avg_support_pct": avg_support_pct,
        "proposals_over_50pct": proposals_over_50,
        "management_overrides": management_overrides,
    }
