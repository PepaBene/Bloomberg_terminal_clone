"""Tests for Pillar 3 Phase 2 — Part 7d: Management Quality Analysis Engine."""

from src.engines.management_quality_engine import (
    AccountingRedFlag,
    CompensationAlignment,
    ExecutionTrackRecord,
    ManagementQualityResult,
    assess_compensation_alignment,
    assess_management_quality,
    compute_guidance_accuracy_score,
    compute_management_quality_score,
    compute_margin_stability_score,
    compute_strategic_consistency_score,
    detect_accounting_red_flags,
)


# ── Guidance Accuracy Tests ──────────────────────────────────────────────


class TestGuidanceAccuracy:
    """Tests for compute_guidance_accuracy_score()."""

    def test_high_accuracy(self):
        """Management consistently hits guidance midpoint within 5%."""
        guidance = [
            {"guidance_midpoint": 5.00, "actual": 5.10},
            {"guidance_midpoint": 5.50, "actual": 5.45},
            {"guidance_midpoint": 6.00, "actual": 6.15},
            {"guidance_midpoint": 6.50, "actual": 6.40},
        ]
        score = compute_guidance_accuracy_score(guidance)
        assert score is not None
        assert score >= 80.0

    def test_low_accuracy(self):
        """Guidance consistently missed by 15-25%."""
        guidance = [
            {"guidance_midpoint": 5.00, "actual": 3.75},
            {"guidance_midpoint": 6.00, "actual": 4.80},
            {"guidance_midpoint": 5.50, "actual": 4.40},
        ]
        score = compute_guidance_accuracy_score(guidance)
        assert score is not None
        assert score <= 30.0

    def test_no_history(self):
        """Empty guidance history returns None."""
        assert compute_guidance_accuracy_score([]) is None


# ── Strategic Consistency Tests ──────────────────────────────────────────


class TestStrategicConsistency:
    """Tests for compute_strategic_consistency_score()."""

    def test_consistent_strategy(self):
        """Low description change and no pivots -> high consistency."""
        data = {
            "business_description_change_pct": 5.0,
            "strategy_change_count": 0,
        }
        score = compute_strategic_consistency_score(data)
        assert score is not None
        assert score >= 85.0

    def test_frequent_pivots(self):
        """Major description rewrites + multiple pivots -> low score."""
        data = {
            "business_description_change_pct": 25.0,
            "strategy_change_count": 3,
        }
        score = compute_strategic_consistency_score(data)
        assert score is not None
        assert score <= 25.0


# ── Margin Stability Tests ───────────────────────────────────────────────


class TestMarginStability:
    """Tests for compute_margin_stability_score()."""

    def test_stable_margins(self):
        """Operating margins barely move year-to-year -> high score."""
        margins = [0.22, 0.23, 0.22, 0.24, 0.23, 0.22]
        score = compute_margin_stability_score(margins)
        assert score is not None
        assert score >= 85.0

    def test_volatile_margins(self):
        """Wild margin swings -> low score."""
        margins = [0.25, 0.10, 0.30, 0.05, 0.28, 0.08]
        score = compute_margin_stability_score(margins)
        assert score is not None
        assert score <= 20.0


# ── Accounting Red Flags Tests ───────────────────────────────────────────


class TestAccountingRedFlags:
    """Tests for detect_accounting_red_flags()."""

    def test_beneish_m_score_flag(self):
        """M-Score above -1.78 triggers CRITICAL flag."""
        data = {"beneish_m_score": -1.20}
        flags = detect_accounting_red_flags(data)
        assert len(flags) >= 1
        m_flags = [f for f in flags if f.flag == "HIGH_MANIPULATION_RISK"]
        assert len(m_flags) == 1
        assert m_flags[0].severity == "CRITICAL"
        assert m_flags[0].value == -1.20

    def test_auditor_change(self):
        """Auditor change triggers HIGH flag."""
        data = {"auditor_change": True}
        flags = detect_accounting_red_flags(data)
        audit_flags = [f for f in flags if f.flag == "AUDITOR_CHANGE"]
        assert len(audit_flags) == 1
        assert audit_flags[0].severity == "HIGH"

    def test_no_flags(self):
        """Clean data returns empty flag list."""
        data = {
            "beneish_m_score": -2.50,
            "accruals_quality": 0.03,
            "auditor_change": False,
            "restatement_count": 0,
            "revenue_vs_receivables_divergence": 0.05,
        }
        flags = detect_accounting_red_flags(data)
        assert len(flags) == 0


# ── Compensation Alignment Tests ─────────────────────────────────────────


class TestCompensationAlignment:
    """Tests for assess_compensation_alignment()."""

    def test_aligned_pay_tracks_performance(self):
        """CEO comp growth tracks TSR and revenue, high ROIC, high LTIP, insider ownership."""
        result = assess_compensation_alignment(
            ceo_comp_growth=0.12,
            tsr=0.15,
            revenue_growth=0.10,
            roic=0.20,
            ltip_pct=0.70,
            insider_ownership_pct=8.0,
        )
        assert isinstance(result, CompensationAlignment)
        assert result.pay_vs_tsr == "ALIGNED"
        assert result.pay_vs_revenue_growth == "ALIGNED"
        assert result.pay_vs_roic == "ALIGNED"
        assert result.alignment_score >= 75.0

    def test_misaligned_pay_exceeds_performance(self):
        """CEO comp growth far outpaces TSR and revenue, low ROIC, no skin in game."""
        result = assess_compensation_alignment(
            ceo_comp_growth=0.35,
            tsr=0.02,
            revenue_growth=0.05,
            roic=0.03,
            ltip_pct=0.20,
            insider_ownership_pct=0.1,
        )
        assert result.pay_vs_tsr == "MISALIGNED"
        assert result.pay_vs_revenue_growth == "MISALIGNED"
        assert result.pay_vs_roic == "MISALIGNED"
        assert result.alignment_score <= 25.0


# ── Overall Quality Score + Orchestrator Tests ───────────────────────────


class TestManagementQuality:
    """Tests for compute_management_quality_score() and assess_management_quality()."""

    def test_high_quality_management(self):
        """Strong execution, clean accounting, aligned compensation."""
        data = {
            "beneish_m_score": -2.80,
            "accruals_quality": 0.03,
            "auditor_change": False,
            "restatement_count": 0,
            "ceo_comp_growth": 0.10,
            "tsr": 0.14,
            "revenue_growth": 0.12,
            "roic": 0.18,
            "ltip_pct": 0.65,
            "insider_ownership_pct": 6.0,
            "governance_score": 75.0,
        }
        guidance = [
            {"guidance_midpoint": 5.00, "actual": 5.05},
            {"guidance_midpoint": 5.50, "actual": 5.55},
            {"guidance_midpoint": 6.00, "actual": 6.10},
        ]
        filing_diff = {
            "business_description_change_pct": 3.0,
            "strategy_change_count": 0,
        }
        margins = [0.21, 0.22, 0.22, 0.23, 0.22]
        ccc = [45.0, 43.0, 40.0, 38.0]

        result = assess_management_quality(
            data,
            guidance_history=guidance,
            filing_diff_data=filing_diff,
            margin_history=margins,
            ccc_history=ccc,
        )
        assert isinstance(result, ManagementQualityResult)
        assert result.execution.composite_execution_score is not None
        assert result.execution.composite_execution_score >= 70.0
        assert len(result.accounting_flags) == 0
        assert result.compensation.alignment_score >= 70.0
        assert result.overall_quality_score >= 65.0
        assert len(result.red_flags) == 0

    def test_low_quality_with_multiple_flags(self):
        """Poor execution, accounting red flags, misaligned pay."""
        data = {
            "beneish_m_score": -1.10,
            "accruals_quality": 0.15,
            "auditor_change": True,
            "restatement_count": 2,
            "revenue_vs_receivables_divergence": 0.25,
            "ceo_comp_growth": 0.40,
            "tsr": -0.05,
            "revenue_growth": 0.02,
            "roic": 0.03,
            "ltip_pct": 0.15,
            "insider_ownership_pct": 0.1,
            "governance_score": 25.0,
        }
        guidance = [
            {"guidance_midpoint": 5.00, "actual": 3.50},
            {"guidance_midpoint": 4.00, "actual": 2.80},
        ]
        filing_diff = {
            "business_description_change_pct": 30.0,
            "strategy_change_count": 4,
        }
        margins = [0.25, 0.10, 0.30, 0.05, 0.22]
        ccc = [30.0, 35.0, 42.0, 50.0]

        result = assess_management_quality(
            data,
            guidance_history=guidance,
            filing_diff_data=filing_diff,
            margin_history=margins,
            ccc_history=ccc,
        )
        assert isinstance(result, ManagementQualityResult)
        # Multiple CRITICAL/HIGH accounting flags expected
        assert len(result.accounting_flags) >= 3
        severities = [f.severity for f in result.accounting_flags]
        assert "CRITICAL" in severities
        assert result.compensation.pay_vs_tsr == "MISALIGNED"
        assert result.overall_quality_score <= 25.0
        assert len(result.red_flags) >= 3
