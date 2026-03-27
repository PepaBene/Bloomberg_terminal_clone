"""Tests for E13 Credit Quality Engine (Pillar 2 FI Supplement – Part 4)."""

import math

import pytest

from src.engines.e13_credit_quality import (
    compute_credit_momentum,
    compute_fallen_angel_probability,
    compute_ohlson_o_score,
    compute_refinancing_risk,
)


# ── Ohlson O-Score ─────────────────────────────────────────────────


class TestOhlsonOScore:
    def test_known_inputs_components(self):
        """Verify O-Score components are computed for known inputs."""
        result = compute_ohlson_o_score(
            total_assets=1_000_000,
            total_liabilities=600_000,
            working_capital=200_000,
            current_liabilities=150_000,
            net_income=80_000,
            funds_from_operations=100_000,
            total_debt=400_000,
            net_income_lag1=70_000,
            total_assets_lag1=950_000,
        )
        assert "o_score" in result
        assert "probability_of_default" in result
        assert "components" in result
        comp = result["components"]
        # All 9 components should be present
        for key in ["size", "leverage", "liquidity", "cl_ratio", "roa",
                     "cash_coverage", "oeneg", "intwo", "ni_change"]:
            assert key in comp

    def test_high_leverage_high_o_score(self):
        """A company with very high leverage should produce a high O-Score."""
        result = compute_ohlson_o_score(
            total_assets=100_000,
            total_liabilities=120_000,  # liabilities exceed assets
            working_capital=-20_000,
            current_liabilities=50_000,
            net_income=-10_000,
            funds_from_operations=-5_000,
            total_debt=100_000,
            net_income_lag1=5_000,
            total_assets_lag1=110_000,
        )
        # High O-Score = high bankruptcy risk
        assert result["o_score"] > 0
        assert result["probability_of_default"] > 0.5

    def test_healthy_company_low_o_score(self):
        """A healthy company should have a relatively low O-Score."""
        result = compute_ohlson_o_score(
            total_assets=10_000_000,
            total_liabilities=2_000_000,
            working_capital=3_000_000,
            current_liabilities=1_000_000,
            net_income=1_500_000,
            funds_from_operations=2_000_000,
            total_debt=1_500_000,
            net_income_lag1=1_400_000,
            total_assets_lag1=9_500_000,
        )
        # Healthy company: low probability of default
        assert result["probability_of_default"] < 0.5

    def test_zero_assets_handling(self):
        """Zero total assets should not crash; returns maximum distress."""
        result = compute_ohlson_o_score(
            total_assets=0,
            total_liabilities=100_000,
            working_capital=-50_000,
            current_liabilities=60_000,
            net_income=-20_000,
            funds_from_operations=-10_000,
            total_debt=80_000,
            net_income_lag1=-15_000,
            total_assets_lag1=50_000,
        )
        assert result["o_score"] == 10.0
        assert result["probability_of_default"] > 0.9

    def test_oeneg_component_when_overleveraged(self):
        """OENEG should be 0.285 when total liabilities exceed total assets."""
        result = compute_ohlson_o_score(
            total_assets=100_000,
            total_liabilities=150_000,  # > total_assets
            working_capital=-20_000,
            current_liabilities=40_000,
            net_income=-5_000,
            funds_from_operations=2_000,
            total_debt=120_000,
            net_income_lag1=-3_000,
            total_assets_lag1=100_000,
        )
        assert result["components"]["oeneg"] == 0.285

    def test_oeneg_component_when_solvent(self):
        """OENEG should be 0 when total liabilities < total assets."""
        result = compute_ohlson_o_score(
            total_assets=200_000,
            total_liabilities=100_000,
            working_capital=50_000,
            current_liabilities=30_000,
            net_income=20_000,
            funds_from_operations=25_000,
            total_debt=70_000,
            net_income_lag1=18_000,
            total_assets_lag1=190_000,
        )
        assert result["components"]["oeneg"] == 0.0

    def test_probability_between_zero_and_one(self):
        """PD should always be between 0 and 1."""
        for ta, tl, wc in [(1_000_000, 200_000, 300_000), (50_000, 80_000, -20_000)]:
            result = compute_ohlson_o_score(
                total_assets=ta,
                total_liabilities=tl,
                working_capital=wc,
                current_liabilities=50_000,
                net_income=10_000,
                funds_from_operations=15_000,
                total_debt=tl * 0.7,
                net_income_lag1=8_000,
                total_assets_lag1=ta * 0.95,
            )
            assert 0.0 <= result["probability_of_default"] <= 1.0


# ── Credit Momentum ────────────────────────────────────────────────


class TestCreditMomentum:
    def test_all_improving(self):
        """All positive inputs should yield IMPROVING signal with score > 0.15."""
        result = compute_credit_momentum(
            rating_momentum=0.5,
            score_momentum=0.5,
            spread_momentum=0.5,
        )
        assert result["momentum_score"] > 0.15
        assert result["signal"] == "IMPROVING"

    def test_all_deteriorating(self):
        """All negative inputs should yield DETERIORATING signal with score < -0.15."""
        result = compute_credit_momentum(
            rating_momentum=-0.5,
            score_momentum=-0.5,
            spread_momentum=-0.5,
        )
        assert result["momentum_score"] < -0.15
        assert result["signal"] == "DETERIORATING"

    def test_mixed_inputs_stable(self):
        """Mixed inputs near zero should yield STABLE signal."""
        result = compute_credit_momentum(
            rating_momentum=0.1,
            score_momentum=-0.1,
            spread_momentum=0.05,
        )
        assert -0.15 <= result["momentum_score"] <= 0.15
        assert result["signal"] == "STABLE"

    def test_boundary_improving(self):
        """Score exactly at 0.15 should be STABLE (not IMPROVING)."""
        # 0.4 * x + 0.35 * x + 0.25 * x = x, so x = 0.15 gives score = 0.15
        result = compute_credit_momentum(
            rating_momentum=0.15,
            score_momentum=0.15,
            spread_momentum=0.15,
        )
        # Score = 0.15, which is NOT > 0.15, so STABLE
        assert result["signal"] == "STABLE"

    def test_boundary_just_above(self):
        """Score just above 0.15 should be IMPROVING."""
        result = compute_credit_momentum(
            rating_momentum=0.16,
            score_momentum=0.16,
            spread_momentum=0.16,
        )
        assert result["momentum_score"] > 0.15
        assert result["signal"] == "IMPROVING"

    def test_components_present(self):
        """All component weights and values should be present."""
        result = compute_credit_momentum(0.3, -0.2, 0.1)
        comp = result["components"]
        assert comp["rating_weight"] == 0.40
        assert comp["score_weight"] == 0.35
        assert comp["spread_weight"] == 0.25
        assert comp["rating_momentum"] == 0.3
        assert comp["score_momentum"] == -0.2
        assert comp["spread_momentum"] == 0.1

    def test_weighted_calculation(self):
        """Verify the weighted formula: 0.4*r + 0.35*s + 0.25*sp."""
        r, s, sp = 0.6, -0.3, 0.2
        expected = 0.4 * r + 0.35 * s + 0.25 * sp
        result = compute_credit_momentum(r, s, sp)
        assert abs(result["momentum_score"] - expected) < 0.0001


# ── Fallen Angel Probability ───────────────────────────────────────


class TestFallenAngelProbability:
    def test_bbb_minus_watch_negative(self):
        """BBB- on WATCH_NEGATIVE should have high probability (~60+%)."""
        prob = compute_fallen_angel_probability(
            current_rating_numeric=10,  # BBB-
            outlook="NEGATIVE",
            watch_status="WATCH_NEGATIVE",
        )
        assert prob >= 60.0  # 20 + 15 + 25 = 60%

    def test_bbb_stable_outlook(self):
        """BBB with STABLE outlook should have ~10% probability."""
        prob = compute_fallen_angel_probability(
            current_rating_numeric=9,  # BBB
            outlook="STABLE",
        )
        assert prob == 10.0  # base rate = 10%, STABLE adds nothing

    def test_aa_rated_zero(self):
        """AA rated entity (numeric 3) should return 0."""
        prob = compute_fallen_angel_probability(
            current_rating_numeric=3,  # AA
            outlook="NEGATIVE",
        )
        assert prob == 0.0

    def test_non_ig_zero(self):
        """Non-IG (BB+ = 11) rated entity should return 0."""
        prob = compute_fallen_angel_probability(
            current_rating_numeric=11,  # BB+
            outlook="NEGATIVE",
            watch_status="WATCH_NEGATIVE",
        )
        assert prob == 0.0

    def test_bbb_plus_base_rate(self):
        """BBB+ base rate should be 5%."""
        prob = compute_fallen_angel_probability(
            current_rating_numeric=8,  # BBB+
        )
        assert prob == 5.0

    def test_positive_outlook_reduces(self):
        """POSITIVE outlook should reduce probability."""
        prob_stable = compute_fallen_angel_probability(
            current_rating_numeric=9,
            outlook="STABLE",
        )
        prob_positive = compute_fallen_angel_probability(
            current_rating_numeric=9,
            outlook="POSITIVE",
        )
        assert prob_positive < prob_stable

    def test_spread_widening_increases(self):
        """Spread widening (negative spread_trend) should increase probability."""
        prob_flat = compute_fallen_angel_probability(
            current_rating_numeric=10,
            spread_trend=0.0,
        )
        prob_wide = compute_fallen_angel_probability(
            current_rating_numeric=10,
            spread_trend=-2.0,  # 2 std devs of widening
        )
        assert prob_wide > prob_flat
        assert prob_wide == pytest.approx(prob_flat + 20.0, abs=0.01)  # 2 * 10%

    def test_score_deterioration_increases(self):
        """Score deterioration should increase probability."""
        prob_flat = compute_fallen_angel_probability(
            current_rating_numeric=9,
            score_trend=0.0,
        )
        prob_bad = compute_fallen_angel_probability(
            current_rating_numeric=9,
            score_trend=-0.5,  # 0.5 / 0.1 * 5% = 25%
        )
        assert prob_bad > prob_flat

    def test_clamped_to_95(self):
        """Probability should never exceed 95."""
        prob = compute_fallen_angel_probability(
            current_rating_numeric=10,
            outlook="NEGATIVE",
            watch_status="WATCH_NEGATIVE",
            spread_trend=-5.0,
            score_trend=-1.0,
        )
        assert prob <= 95.0


# ── Refinancing Risk ───────────────────────────────────────────────


class TestRefinancingRisk:
    def test_high_risk_scenario(self):
        """High maturity wall + wide spreads + low FCF should yield HIGH."""
        result = compute_refinancing_risk(
            maturity_wall_pct=90.0,
            current_spread_bps=800.0,
            fcf_to_debt=0.02,
            credit_direction=-0.8,
        )
        assert result["score"] >= 75.0
        assert result["assessment"] == "HIGH"

    def test_low_risk_scenario(self):
        """Low maturity wall + tight spreads + high FCF should yield LOW."""
        result = compute_refinancing_risk(
            maturity_wall_pct=5.0,
            current_spread_bps=50.0,
            fcf_to_debt=0.60,
            credit_direction=0.8,
        )
        assert result["score"] < 25.0
        assert result["assessment"] == "LOW"

    def test_moderate_scenario(self):
        """Middle-ground inputs should yield MODERATE."""
        result = compute_refinancing_risk(
            maturity_wall_pct=40.0,
            current_spread_bps=250.0,
            fcf_to_debt=0.20,
            credit_direction=0.0,
        )
        assert 25.0 <= result["score"] < 50.0
        assert result["assessment"] == "MODERATE"

    def test_elevated_scenario(self):
        """Somewhat high inputs should yield ELEVATED."""
        result = compute_refinancing_risk(
            maturity_wall_pct=60.0,
            current_spread_bps=500.0,
            fcf_to_debt=0.05,
            credit_direction=-0.5,
        )
        assert 50.0 <= result["score"] < 75.0
        assert result["assessment"] == "ELEVATED"

    def test_components_present(self):
        """All component scores should be in the result."""
        result = compute_refinancing_risk(
            maturity_wall_pct=50.0,
            current_spread_bps=300.0,
            fcf_to_debt=0.15,
            credit_direction=0.2,
        )
        comp = result["components"]
        for key in ["maturity_wall_score", "spread_stress_score",
                     "fcf_coverage_score", "credit_direction_score"]:
            assert key in comp
            assert 0.0 <= comp[key] <= 100.0

    def test_score_clamped_to_100(self):
        """Score should never exceed 100."""
        result = compute_refinancing_risk(
            maturity_wall_pct=100.0,
            current_spread_bps=5000.0,
            fcf_to_debt=0.0,
            credit_direction=-1.0,
        )
        assert result["score"] <= 100.0

    def test_score_at_least_zero(self):
        """Score should never go below 0."""
        result = compute_refinancing_risk(
            maturity_wall_pct=0.0,
            current_spread_bps=0.0,
            fcf_to_debt=1.0,
            credit_direction=1.0,
        )
        assert result["score"] >= 0.0
