"""Tests for Pillar 3 Phase 3 — Porter's Five Forces Engine."""

from src.engines.porter_forces_engine import (
    PorterForce,
    PorterForcesResult,
    assess_porter_forces,
    score_new_entrant_threat,
    score_supplier_power,
)


def _force(result: PorterForcesResult, name: str) -> PorterForce:
    for f in result.forces:
        if f.name == name:
            return f
    raise AssertionError(f"force {name!r} not found in result")


# ── Highly competitive, unattractive industry ────────────────────────────


class TestHighlyCompetitiveIndustry:
    """All five forces should read HIGH/MODERATE-HIGH, low attractiveness."""

    SIGNALS = {
        # Supplier power: many single-source/critical deps, HIGH label
        "supplier_single_source_count": 5,
        "supplier_critical_count": 4,
        "supplier_concentration_risk": "HIGH",
        # Buyer power: concentrated customer base
        "customer_top1_pct": 45.0,
        "customer_hhi": 3500.0,
        # Competitive rivalry: volatile margins, losing share, below peers
        "gross_margin_10y_std": 0.10,
        "market_share_trend": "LOSING",
        "margin_vs_peers": -0.05,
        # Substitute threat: highly vulnerable, low switching costs
        "disruption_vulnerability": 85.0,
        "switching_cost_score": 10.0,
        # New entrant threat: weak moat/scale/cost-advantage -> low barriers
        "moat_score": 15.0,
        "efficient_scale_score": 20.0,
        "cost_advantage_score": 10.0,
    }

    def test_all_forces_high_or_moderate_high(self):
        result = assess_porter_forces(self.SIGNALS)
        assert isinstance(result, PorterForcesResult)
        for f in result.forces:
            assert f.score is not None
            assert f.score >= 60.0, f"{f.name} expected high score, got {f.score}"
            assert f.level in ("HIGH", "MODERATE")

    def test_low_industry_attractiveness(self):
        result = assess_porter_forces(self.SIGNALS)
        assert result.overall_industry_attractiveness_score is not None
        assert result.overall_industry_attractiveness_score < 30.0

    def test_dominant_force_is_highest_scoring(self):
        result = assess_porter_forces(self.SIGNALS)
        assert result.dominant_force is not None
        dominant = _force(result, result.dominant_force)
        for f in result.forces:
            assert dominant.score >= f.score

    def test_data_completeness_full(self):
        result = assess_porter_forces(self.SIGNALS)
        assert result.data_completeness == 1.0


# ── Protected, attractive industry ───────────────────────────────────────


class TestProtectedAttractiveIndustry:
    """Wide moat, low concentration, stable margins -> attractive industry."""

    SIGNALS = {
        "supplier_single_source_count": 0,
        "supplier_critical_count": 0,
        "supplier_concentration_risk": "LOW",
        "customer_top1_pct": 5.0,
        "customer_hhi": 800.0,
        "gross_margin_10y_std": 0.01,
        "market_share_trend": "GAINING",
        "margin_vs_peers": 0.05,
        "disruption_vulnerability": 10.0,
        "switching_cost_score": 90.0,
        "moat_score": 90.0,
        "efficient_scale_score": 85.0,
        "cost_advantage_score": 88.0,
    }

    def test_all_forces_low(self):
        result = assess_porter_forces(self.SIGNALS)
        for f in result.forces:
            assert f.score is not None
            assert f.score < 40.0, f"{f.name} expected low score, got {f.score}"
            assert f.level == "LOW"

    def test_high_industry_attractiveness(self):
        result = assess_porter_forces(self.SIGNALS)
        assert result.overall_industry_attractiveness_score is not None
        assert result.overall_industry_attractiveness_score > 70.0


# ── Partial signals ───────────────────────────────────────────────────────


class TestPartialSignals:
    """Only supplier-power inputs present -- everything else None."""

    SIGNALS = {
        "supplier_single_source_count": 4,
        "supplier_critical_count": 3,
        "supplier_concentration_risk": "HIGH",
    }

    def test_only_supplier_power_scored(self):
        result = assess_porter_forces(self.SIGNALS)
        supplier = _force(result, "supplier_power")
        assert supplier.score is not None
        assert supplier.level != "UNKNOWN"

        for name in (
            "buyer_power",
            "competitive_rivalry",
            "substitute_threat",
            "new_entrant_threat",
        ):
            f = _force(result, name)
            assert f.score is None
            assert f.level == "UNKNOWN"

    def test_overall_score_renormalized_to_single_force(self):
        result = assess_porter_forces(self.SIGNALS)
        supplier = _force(result, "supplier_power")
        # With only one force present, overall attractiveness is exactly
        # 100 - that force's score (renormalized over the single value).
        assert result.overall_industry_attractiveness_score == round(
            100.0 - supplier.score, 2
        )

    def test_dominant_force_is_supplier_power(self):
        result = assess_porter_forces(self.SIGNALS)
        assert result.dominant_force == "supplier_power"

    def test_data_completeness_partial(self):
        result = assess_porter_forces(self.SIGNALS)
        assert 0.0 < result.data_completeness < 1.0


# ── Empty signals ─────────────────────────────────────────────────────────


class TestEmptySignals:
    """Empty dict should not crash and should return all-None/UNKNOWN."""

    def test_empty_dict(self):
        result = assess_porter_forces({})
        assert isinstance(result, PorterForcesResult)
        assert len(result.forces) == 5
        for f in result.forces:
            assert f.score is None
            assert f.level == "UNKNOWN"
        assert result.overall_industry_attractiveness_score is None
        assert result.dominant_force is None
        assert result.data_completeness == 0.0

    def test_none_like_signals_all_none(self):
        signals = {key: None for key in [
            "supplier_single_source_count",
            "customer_top1_pct",
            "gross_margin_10y_std",
            "disruption_vulnerability",
            "moat_score",
        ]}
        result = assess_porter_forces(signals)
        for f in result.forces:
            assert f.score is None
            assert f.level == "UNKNOWN"
        assert result.data_completeness == 0.0


# ── New entrant threat inversion ─────────────────────────────────────────


class TestNewEntrantThreatInversion:
    """High moat/scale/cost-advantage inputs must produce a LOW threat score."""

    def test_hand_computed_inversion(self):
        signals = {
            "moat_score": 90.0,
            "efficient_scale_score": 90.0,
            "cost_advantage_score": 90.0,
        }
        # barrier_score = 0.5*90 + 0.25*90 + 0.25*90 = 90
        # new_entrant_threat_score = 100 - 90 = 10
        score = score_new_entrant_threat(signals)
        assert score == 10.0

    def test_weighted_inversion_with_partial_inputs(self):
        # Only moat_score (weight 0.5) and cost_advantage_score (weight 0.25)
        # present; weights renormalize to moat=2/3, cost_advantage=1/3.
        signals = {"moat_score": 80.0, "cost_advantage_score": 20.0}
        barrier = (0.5 * 80.0 + 0.25 * 20.0) / (0.5 + 0.25)
        expected = round(100.0 - barrier, 2)
        assert score_new_entrant_threat(signals) == expected

    def test_low_barriers_produce_high_threat(self):
        signals = {
            "moat_score": 10.0,
            "efficient_scale_score": 10.0,
            "cost_advantage_score": 10.0,
        }
        assert score_new_entrant_threat(signals) == 90.0

    def test_no_inputs_returns_none(self):
        assert score_new_entrant_threat({}) is None


# ── Supplier power scoring sanity ────────────────────────────────────────


class TestSupplierPowerScoring:
    def test_zero_and_low_risk_gives_low_score(self):
        score = score_supplier_power(
            {
                "supplier_single_source_count": 0,
                "supplier_critical_count": 0,
                "supplier_concentration_risk": "LOW",
            }
        )
        assert score == 15.0

    def test_high_counts_and_high_risk_gives_high_score(self):
        score = score_supplier_power(
            {
                "supplier_single_source_count": 3,
                "supplier_critical_count": 3,
                "supplier_concentration_risk": "HIGH",
            }
        )
        assert score == 85.0

    def test_single_input_only(self):
        score = score_supplier_power({"supplier_single_source_count": 3})
        assert score == 85.0

    def test_no_inputs_returns_none(self):
        assert score_supplier_power({}) is None
