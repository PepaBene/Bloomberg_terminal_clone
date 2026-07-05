"""Tests for the Complex Financial Structure Analysis Engine."""

from src.engines.complex_structure import (
    analyze_complex_structure,
    analyze_debt_waterfall,
    analyze_off_balance_sheet,
    analyze_share_classes,
    analyze_subsidiary_tree,
    compute_complexity_score,
)


class TestSubsidiaryTree:
    def test_offshore_detection(self):
        subs = [
            {"name": "A", "jurisdiction": "Delaware"},
            {"name": "B", "jurisdiction": "Cayman Islands"},
            {"name": "C", "jurisdiction": "Ireland"},
            {"name": "D", "jurisdiction": "Germany"},
        ]
        out = analyze_subsidiary_tree(subs)
        assert out["total_subsidiaries"] == 4
        assert out["offshore_count"] == 3  # Delaware, Cayman, Ireland
        assert out["distinct_jurisdictions"] == 4

    def test_depth_from_parent_links(self):
        subs = [
            {"name": "Mid", "parent": "Parent"},
            {"name": "Leaf", "parent": "Mid"},
        ]
        out = analyze_subsidiary_tree(subs, parent_name="Parent")
        assert out["max_depth"] >= 2

    def test_empty(self):
        out = analyze_subsidiary_tree([])
        assert out["total_subsidiaries"] == 0
        assert out["complexity_flag"] is False


class TestShareClasses:
    def test_single_class_no_wedge(self):
        out = analyze_share_classes([{"class_name": "Common", "shares_outstanding": 100, "votes_per_share": 1}])
        assert out["is_dual_class"] is False
        assert out["control_wedge"] == 0.0

    def test_dual_class_control_wedge(self):
        out = analyze_share_classes([
            {"class_name": "A", "shares_outstanding": 90, "votes_per_share": 1},
            {"class_name": "B", "shares_outstanding": 10, "votes_per_share": 10},
        ])
        assert out["is_dual_class"] is True
        # Class B: 10 shares * 10 votes = 100 votes of 190 total ≈ 52.6% voting on 10% economic.
        assert out["control_wedge"] > 30
        assert "control" in out["assessment"].lower()

    def test_empty(self):
        out = analyze_share_classes([])
        assert out["num_classes"] == 0


class TestOffBalanceSheet:
    def test_materiality_high(self):
        out = analyze_off_balance_sheet(
            {"operating_lease_commitments": 60, "vie_assets": 40}, total_assets=100
        )
        assert out["total_off_balance_sheet"] == 100
        assert out["obs_to_assets_pct"] == 100.0
        assert out["materiality"] == "HIGH"
        assert out["has_vie"] is True

    def test_unknown_without_assets(self):
        out = analyze_off_balance_sheet({"guarantees": 10})
        assert out["materiality"] == "UNKNOWN"


class TestDebtWaterfall:
    def test_priority_ordering_and_debt_ahead(self):
        tranches = [
            {"instrument_name": "Sub Notes", "principal_amount": 100, "seniority_rank": 3},
            {"instrument_name": "Senior Secured", "principal_amount": 200, "seniority_rank": 1, "is_secured": True},
            {"instrument_name": "Senior Unsecured", "principal_amount": 150, "seniority_rank": 2},
        ]
        out = analyze_debt_waterfall(tranches)
        assert out["total_debt"] == 450
        # Most senior first, with zero debt ahead.
        assert out["layers"][0]["instrument_name"] == "Senior Secured"
        assert out["layers"][0]["debt_ahead"] == 0.0
        assert out["layers"][-1]["debt_ahead"] == 350.0

    def test_structural_subordination(self):
        tranches = [
            {"instrument_name": "OpCo Loan", "principal_amount": 100, "seniority_rank": 1, "issuer_level": "OPCO"},
            {"instrument_name": "HoldCo Notes", "principal_amount": 50, "seniority_rank": 2, "issuer_level": "HOLDCO"},
        ]
        out = analyze_debt_waterfall(tranches)
        assert out["structural_subordination"] is True

    def test_empty(self):
        out = analyze_debt_waterfall([])
        assert out["total_debt"] == 0.0


class TestOrchestrator:
    def test_complex_company_scores_high(self):
        payload = {
            "subsidiaries": [{"name": f"S{i}", "jurisdiction": "Cayman Islands"} for i in range(10)]
            + [{"name": "Onshore", "jurisdiction": "Delaware"}],
            "share_classes": [
                {"class_name": "A", "shares_outstanding": 90, "votes_per_share": 1},
                {"class_name": "B", "shares_outstanding": 10, "votes_per_share": 10},
            ],
            "off_balance_sheet": {"vie_assets": 80},
            "total_assets": 100,
            "debt_tranches": [
                {"instrument_name": "OpCo", "principal_amount": 100, "seniority_rank": 1, "issuer_level": "OPCO"},
                {"instrument_name": "HoldCo", "principal_amount": 50, "seniority_rank": 2, "issuer_level": "HOLDCO"},
            ],
        }
        report = analyze_complex_structure(payload, subject="MegaCorp")
        assert report.complexity_rating in ("COMPLEX", "VERY_COMPLEX")
        assert report.complexity_score >= 45
        assert len(report.flags) >= 3

    def test_simple_company_scores_low(self):
        payload = {
            "subsidiaries": [{"name": "Sub1", "jurisdiction": "Germany"}],
            "share_classes": [{"class_name": "Common", "shares_outstanding": 100, "votes_per_share": 1}],
            "off_balance_sheet": {},
            "total_assets": 1000,
            "debt_tranches": [{"instrument_name": "Term Loan", "principal_amount": 100, "seniority_rank": 1}],
        }
        report = analyze_complex_structure(payload, subject="SimpleCo")
        assert report.complexity_rating == "SIMPLE"
        assert report.flags == []

    def test_compute_complexity_score_bounds(self):
        score = compute_complexity_score({}, {}, {}, {})
        assert 0 <= score <= 100
