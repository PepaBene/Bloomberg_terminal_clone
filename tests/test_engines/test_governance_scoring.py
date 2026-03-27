"""Tests for Pillar 3 Phase 1 — Part 6: Governance Scoring Engine."""

import pytest

from src.engines.governance_scoring import (
    RED_FLAG_CHECKS,
    SCORE_CLASSIFICATIONS,
    analyze_shareholder_proposals,
    compute_board_diversity,
    compute_governance_score,
    compute_pay_alignment,
    detect_board_interlocks,
    detect_red_flags,
)


# ── Helpers ──────────────────────────────────────────────────────────────

def _clean_governance() -> dict:
    """Return governance data with zero red flags."""
    return {
        "dual_class": False,
        "ceo_is_chair": False,
        "board_independence_pct": 80.0,
        "avg_board_tenure": 7.0,
        "has_poison_pill": False,
        "has_staggered_board": False,
        "ceo_pay_ratio": 150.0,
        "related_party_flag": False,
        "long_term_incentive_pct": 60.0,
        "has_majority_voting": True,
    }


# ── Red Flag Detection Tests ────────────────────────────────────────────


class TestDetectRedFlags:
    """Tests for detect_red_flags()."""

    def test_detect_no_red_flags(self):
        """Clean governance data should produce no red flags."""
        data = _clean_governance()
        flags = detect_red_flags(data)
        assert flags == []

    def test_detect_dual_class_flag(self):
        data = _clean_governance()
        data["dual_class"] = True
        flags = detect_red_flags(data)
        flag_names = [f["flag"] for f in flags]
        assert "dual_class" in flag_names
        dual = next(f for f in flags if f["flag"] == "dual_class")
        assert dual["severity"] == "HIGH"
        assert dual["weight"] == 15

    def test_detect_ceo_is_chair_flag(self):
        data = _clean_governance()
        data["ceo_is_chair"] = True
        flags = detect_red_flags(data)
        flag_names = [f["flag"] for f in flags]
        assert "ceo_is_chair" in flag_names
        flag = next(f for f in flags if f["flag"] == "ceo_is_chair")
        assert flag["severity"] == "MEDIUM"
        assert flag["weight"] == 10

    def test_detect_low_independence(self):
        """65% < 67% threshold → flagged."""
        data = _clean_governance()
        data["board_independence_pct"] = 65.0
        flags = detect_red_flags(data)
        flag_names = [f["flag"] for f in flags]
        assert "low_independence" in flag_names

    def test_detect_independence_ok(self):
        """80% >= 67% threshold → not flagged."""
        data = _clean_governance()
        data["board_independence_pct"] = 80.0
        flags = detect_red_flags(data)
        flag_names = [f["flag"] for f in flags]
        assert "low_independence" not in flag_names

    def test_detect_high_tenure(self):
        """Average 15 years > 12 year threshold → flagged."""
        data = _clean_governance()
        data["avg_board_tenure"] = 15.0
        flags = detect_red_flags(data)
        flag_names = [f["flag"] for f in flags]
        assert "high_tenure" in flag_names

    def test_detect_poison_pill(self):
        data = _clean_governance()
        data["has_poison_pill"] = True
        flags = detect_red_flags(data)
        flag_names = [f["flag"] for f in flags]
        assert "poison_pill" in flag_names
        flag = next(f for f in flags if f["flag"] == "poison_pill")
        assert flag["severity"] == "HIGH"

    def test_detect_staggered_board(self):
        data = _clean_governance()
        data["has_staggered_board"] = True
        flags = detect_red_flags(data)
        flag_names = [f["flag"] for f in flags]
        assert "staggered_board" in flag_names
        flag = next(f for f in flags if f["flag"] == "staggered_board")
        assert flag["severity"] == "MEDIUM"

    def test_detect_high_pay_ratio(self):
        """350x > 300x threshold → flagged."""
        data = _clean_governance()
        data["ceo_pay_ratio"] = 350.0
        flags = detect_red_flags(data)
        flag_names = [f["flag"] for f in flags]
        assert "high_pay_ratio" in flag_names

    def test_detect_pay_ratio_ok(self):
        """200x <= 300x threshold → not flagged."""
        data = _clean_governance()
        data["ceo_pay_ratio"] = 200.0
        flags = detect_red_flags(data)
        flag_names = [f["flag"] for f in flags]
        assert "high_pay_ratio" not in flag_names

    def test_detect_related_party(self):
        data = _clean_governance()
        data["related_party_flag"] = True
        flags = detect_red_flags(data)
        flag_names = [f["flag"] for f in flags]
        assert "related_party" in flag_names
        flag = next(f for f in flags if f["flag"] == "related_party")
        assert flag["severity"] == "HIGH"

    def test_detect_low_ltip(self):
        """30% < 40% threshold → flagged."""
        data = _clean_governance()
        data["long_term_incentive_pct"] = 30.0
        flags = detect_red_flags(data)
        flag_names = [f["flag"] for f in flags]
        assert "low_ltip_pct" in flag_names

    def test_detect_no_majority_voting(self):
        data = _clean_governance()
        data["has_majority_voting"] = False
        flags = detect_red_flags(data)
        flag_names = [f["flag"] for f in flags]
        assert "no_majority_voting" in flag_names

    def test_detect_multiple_red_flags(self):
        """Three flags simultaneously."""
        data = _clean_governance()
        data["dual_class"] = True
        data["ceo_is_chair"] = True
        data["has_poison_pill"] = True
        flags = detect_red_flags(data)
        flag_names = {f["flag"] for f in flags}
        assert flag_names == {"dual_class", "ceo_is_chair", "poison_pill"}
        assert len(flags) == 3


# ── Governance Score Tests ───────────────────────────────────────────────


class TestComputeGovernanceScore:
    """Tests for compute_governance_score()."""

    def test_governance_score_perfect(self):
        """No flags → score 100, STRONG."""
        data = _clean_governance()
        result = compute_governance_score(data)
        assert result["score"] == 100
        assert result["classification"] == "STRONG"
        assert result["red_flags"] == []
        assert result["total_deductions"] == 0

    def test_governance_score_one_flag(self):
        """dual_class (weight 15) → score 85, STRONG."""
        data = _clean_governance()
        data["dual_class"] = True
        result = compute_governance_score(data)
        assert result["score"] == 85
        assert result["classification"] == "STRONG"
        assert result["total_deductions"] == 15

    def test_governance_score_many_flags(self):
        """All flags triggered → low score, SIGNIFICANT_RISK."""
        data = {
            "dual_class": True,
            "ceo_is_chair": True,
            "board_independence_pct": 40.0,
            "avg_board_tenure": 18.0,
            "has_poison_pill": True,
            "has_staggered_board": True,
            "ceo_pay_ratio": 500.0,
            "related_party_flag": True,
            "long_term_incentive_pct": 20.0,
            "has_majority_voting": False,
        }
        result = compute_governance_score(data)
        total_weight = sum(v["weight"] for v in RED_FLAG_CHECKS.values())
        assert result["score"] == max(0, 100 - total_weight)
        assert result["classification"] == "SIGNIFICANT_RISK"
        assert len(result["red_flags"]) == 10

    def test_governance_score_classification_boundaries(self):
        """Test exact classification boundaries."""
        # Helper to build data that yields exactly N deduction points
        def _score_for(deduction: int) -> dict:
            # Build clean, then manually set score via mock approach
            # Instead, test _classify_score indirectly via known deduction combos
            pass

        # Score 80 → STRONG
        # dual_class (15) + ceo_is_chair (10) = 25 deduction → score 75
        # We need score=80 exactly → deduction=20 → dual_class(15) + no_majority(7)=22
        # Actually let's test via compute_governance_score results:

        # Score = 80: 100 - 20 = 80 → need deductions of exactly 20
        # ceo_is_chair(10) + poison_pill(10) = 20
        data = _clean_governance()
        data["ceo_is_chair"] = True
        data["has_poison_pill"] = True
        result = compute_governance_score(data)
        assert result["score"] == 80
        assert result["classification"] == "STRONG"  # 80 is in [80, 101)

        # Score = 79: deduction=21 → dual_class(15) + no_majority(7)=22 → 78
        # Or: ceo_is_chair(10) + low_independence(12)=22 → 78
        # Try: staggered_board(8) + low_ltip(8) + no_majority(7)=23 → 77
        # For exactly 79: not easy with integer weights. Test 78 instead.
        data2 = _clean_governance()
        data2["ceo_is_chair"] = True
        data2["board_independence_pct"] = 50.0  # low_independence: 12
        result2 = compute_governance_score(data2)
        assert result2["score"] == 78  # 100 - 10 - 12 = 78
        assert result2["classification"] == "ADEQUATE"  # [60, 80)

        # Score in ADEQUATE range: 60 → [60, 80)
        # deduction=40: dual_class(15)+low_independence(12)+ceo_is_chair(10) = 37 → 63
        data3 = _clean_governance()
        data3["dual_class"] = True
        data3["board_independence_pct"] = 50.0
        data3["ceo_is_chair"] = True
        result3 = compute_governance_score(data3)
        assert result3["score"] == 63
        assert result3["classification"] == "ADEQUATE"

        # Score in CONCERNS range: [40, 60)
        # deduction=42: dual_class(15)+low_independence(12)+poison_pill(10)+ceo_is_chair(10)=47 → 53
        data4 = _clean_governance()
        data4["dual_class"] = True
        data4["board_independence_pct"] = 50.0
        data4["has_poison_pill"] = True
        data4["ceo_is_chair"] = True
        result4 = compute_governance_score(data4)
        assert result4["score"] == 53  # 100 - 15 - 12 - 10 - 10 = 53
        assert result4["classification"] == "CONCERNS"

        # Score in SIGNIFICANT_RISK: [0, 40)
        # deduction >= 61
        data5 = _clean_governance()
        data5["dual_class"] = True  # 15
        data5["board_independence_pct"] = 50.0  # 12
        data5["has_poison_pill"] = True  # 10
        data5["ceo_is_chair"] = True  # 10
        data5["related_party_flag"] = True  # 12
        data5["ceo_pay_ratio"] = 400.0  # 10
        # total deduction: 15+12+10+10+12+10 = 69 → score 31
        result5 = compute_governance_score(data5)
        assert result5["score"] == 31
        assert result5["classification"] == "SIGNIFICANT_RISK"


# ── Pay Alignment Tests ──────────────────────────────────────────────────


class TestComputePayAlignment:
    """Tests for compute_pay_alignment()."""

    def test_pay_alignment_good(self):
        """Comp grew roughly with TSR → high alignment score."""
        ceo_comp = {"total_compensation": 15_000_000, "yoy_change_pct": 12.0}
        perf = {"tsr_1y": 15.0, "revenue_growth_pct": 10.0, "roic": 18.0}
        result = compute_pay_alignment(ceo_comp, perf)
        assert result["alignment_score"] >= 70
        assert result["pay_vs_performance"] == "WELL_ALIGNED"
        assert result["peer_comparison"] is None

    def test_pay_alignment_bad(self):
        """Comp grew while TSR declined → low alignment score."""
        ceo_comp = {"total_compensation": 20_000_000, "yoy_change_pct": 25.0}
        perf = {"tsr_1y": -10.0, "revenue_growth_pct": -5.0, "roic": 5.0}
        result = compute_pay_alignment(ceo_comp, perf)
        assert result["alignment_score"] < 45
        assert result["pay_vs_performance"] == "MISALIGNED"

    def test_pay_alignment_with_peers(self):
        """Peer comparison present → peer_comparison dict populated."""
        ceo_comp = {"total_compensation": 18_000_000, "yoy_change_pct": 8.0}
        perf = {"tsr_1y": 10.0, "revenue_growth_pct": 12.0, "roic": 14.0}
        peers = [
            {"total_compensation": 12_000_000},
            {"total_compensation": 14_000_000},
            {"total_compensation": 16_000_000},
            {"total_compensation": 20_000_000},
        ]
        result = compute_pay_alignment(ceo_comp, perf, peer_comp=peers)
        assert result["peer_comparison"] is not None
        pc = result["peer_comparison"]
        assert pc["ceo_total_compensation"] == 18_000_000
        assert pc["peer_count"] == 4
        assert pc["peer_median"] == 15_000_000  # median of [12M, 14M, 16M, 20M]
        assert pc["ratio_to_peer_median"] == 1.2  # 18M / 15M

    def test_pay_alignment_no_peers(self):
        """None peer_comp → peer_comparison is None."""
        ceo_comp = {"total_compensation": 10_000_000, "yoy_change_pct": 5.0}
        perf = {"tsr_1y": 8.0, "revenue_growth_pct": 6.0, "roic": 12.0}
        result = compute_pay_alignment(ceo_comp, perf, peer_comp=None)
        assert result["peer_comparison"] is None
        assert "alignment_score" in result


# ── Board Diversity Tests ────────────────────────────────────────────────


class TestComputeBoardDiversity:
    """Tests for compute_board_diversity()."""

    def test_board_diversity_all_independent(self):
        members = [
            {
                "is_independent": True, "is_chair": False,
                "tenure_years": 5, "age": 55, "gender": "M",
                "expertise_areas": ["finance"], "other_boards": [],
            },
            {
                "is_independent": True, "is_chair": True,
                "tenure_years": 8, "age": 62, "gender": "F",
                "expertise_areas": ["finance", "tech"], "other_boards": [],
            },
        ]
        result = compute_board_diversity(members)
        assert result["total_directors"] == 2
        assert result["independent_count"] == 2
        assert result["independent_pct"] == 100.0

    def test_board_diversity_mixed(self):
        members = [
            {
                "is_independent": True, "is_chair": False,
                "tenure_years": 3, "age": 50, "gender": "M",
                "expertise_areas": ["finance"], "other_boards": [],
            },
            {
                "is_independent": False, "is_chair": True,
                "tenure_years": 10, "age": 65, "gender": "M",
                "expertise_areas": ["operations"], "other_boards": ["ACME Inc"],
            },
            {
                "is_independent": True, "is_chair": False,
                "tenure_years": 5, "age": 48, "gender": "F",
                "expertise_areas": ["legal"], "other_boards": [],
            },
        ]
        result = compute_board_diversity(members)
        assert result["total_directors"] == 3
        assert result["independent_count"] == 2
        assert result["independent_pct"] == pytest.approx(66.7, abs=0.1)

    def test_board_diversity_gender(self):
        members = [
            {
                "is_independent": True, "is_chair": False,
                "tenure_years": 5, "age": 55, "gender": "M",
                "expertise_areas": [], "other_boards": [],
            },
            {
                "is_independent": True, "is_chair": False,
                "tenure_years": 3, "age": 45, "gender": "F",
                "expertise_areas": [], "other_boards": [],
            },
            {
                "is_independent": True, "is_chair": False,
                "tenure_years": 4, "age": 50, "gender": "F",
                "expertise_areas": [], "other_boards": [],
            },
            {
                "is_independent": True, "is_chair": False,
                "tenure_years": 6, "age": 60, "gender": "NB",
                "expertise_areas": [], "other_boards": [],
            },
        ]
        result = compute_board_diversity(members)
        # 3 non-male out of 4
        assert result["gender_diversity_pct"] == 75.0

    def test_board_diversity_expertise_mix(self):
        members = [
            {
                "is_independent": True, "is_chair": False,
                "tenure_years": 5, "age": 55, "gender": "M",
                "expertise_areas": ["finance", "risk"], "other_boards": [],
            },
            {
                "is_independent": True, "is_chair": False,
                "tenure_years": 3, "age": 48, "gender": "F",
                "expertise_areas": ["finance", "tech"], "other_boards": [],
            },
            {
                "is_independent": True, "is_chair": False,
                "tenure_years": 7, "age": 60, "gender": "M",
                "expertise_areas": ["legal"], "other_boards": [],
            },
        ]
        result = compute_board_diversity(members)
        mix = result["expertise_mix"]
        assert mix["finance"] == 2
        assert mix["risk"] == 1
        assert mix["tech"] == 1
        assert mix["legal"] == 1


# ── Board Interlocks Tests ───────────────────────────────────────────────


class TestDetectBoardInterlocks:
    """Tests for detect_board_interlocks()."""

    def test_detect_interlocks(self):
        """Director on 3 other boards → flagged."""
        members = [
            {
                "name": "Alice Smith",
                "other_boards": ["Corp A", "Corp B", "Corp C"],
            },
            {
                "name": "Bob Jones",
                "other_boards": ["Corp D"],
            },
        ]
        result = detect_board_interlocks(members)
        assert len(result) == 1
        assert result[0]["person_name"] == "Alice Smith"
        assert result[0]["interlock_count"] == 3
        assert result[0]["boards"] == ["Corp A", "Corp B", "Corp C"]

    def test_detect_no_interlocks(self):
        """No other_boards → no interlocks detected."""
        members = [
            {"name": "Alice Smith", "other_boards": []},
            {"name": "Bob Jones", "other_boards": ["Corp A"]},
        ]
        result = detect_board_interlocks(members)
        assert result == []


# ── Shareholder Proposals Tests ──────────────────────────────────────────


class TestAnalyzeShareholderProposals:
    """Tests for analyze_shareholder_proposals()."""

    def test_analyze_proposals_mixed(self):
        """Some passed, some failed — various metrics calculated."""
        proposals = [
            {
                "topic": "ESG",
                "vote_for_pct": 55.0,
                "management_recommendation": "AGAINST",
                "passed": True,
            },
            {
                "topic": "ESG",
                "vote_for_pct": 42.0,
                "management_recommendation": "AGAINST",
                "passed": False,
            },
            {
                "topic": "Compensation",
                "vote_for_pct": 65.0,
                "management_recommendation": "FOR",
                "passed": True,
            },
            {
                "topic": "Governance",
                "vote_for_pct": 30.0,
                "management_recommendation": "FOR",
                "passed": False,
            },
        ]
        result = analyze_shareholder_proposals(proposals)
        assert result["total_proposals"] == 4
        assert result["proposals_over_50pct"] == 2  # 55% and 65%
        # ESG proposal passed against management rec → 1 override
        # Governance proposal failed with management FOR → 1 override
        assert result["management_overrides"] == 2
        assert "ESG" in result["by_topic"]
        assert result["by_topic"]["ESG"]["count"] == 2
        assert result["avg_support_pct"] == pytest.approx(48.0, abs=0.1)

    def test_analyze_proposals_empty(self):
        """Empty proposal list → zero metrics."""
        result = analyze_shareholder_proposals([])
        assert result["total_proposals"] == 0
        assert result["by_topic"] == {}
        assert result["avg_support_pct"] == 0.0
        assert result["proposals_over_50pct"] == 0
        assert result["management_overrides"] == 0
