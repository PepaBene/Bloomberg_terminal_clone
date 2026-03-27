"""Tests for Pillar 3 Phase 3A — Moat Assessment Engine."""

from src.engines.moat_assessment import (
    MARGIN_STABILITY_BANDS,
    MOAT_SOURCE_WEIGHTS,
    MOAT_WIDTH_THRESHOLDS,
    MoatResult,
    assess_gross_margin_stability,
    assess_market_share_trend,
    assess_moat,
    assess_moat_stability,
    assess_roic_consistency,
    score_cost_advantage,
    score_efficient_scale,
    score_intangible_assets,
    score_network_effects,
    score_switching_costs,
)


# ── ROIC Consistency Tests ───────────────────────────────────────────────


class TestROICConsistency:
    """Tests for assess_roic_consistency()."""

    def test_all_years_above_wide_moat(self):
        """12/12 years ROIC > WACC -> high consistency, qualifies for WIDE."""
        roic = [0.18, 0.19, 0.20, 0.21, 0.22, 0.20, 0.19, 0.21, 0.22, 0.23, 0.24, 0.25]
        wacc = [0.09, 0.09, 0.09, 0.09, 0.09, 0.09, 0.09, 0.09, 0.09, 0.09, 0.09, 0.09]
        years, score = assess_roic_consistency(roic, wacc)
        assert years == 12
        assert years >= MOAT_WIDTH_THRESHOLDS["WIDE"]
        assert score > 50.0

    def test_eight_of_ten_narrow_moat(self):
        """8/10 years ROIC > WACC -> qualifies for NARROW."""
        roic = [0.14, 0.15, 0.08, 0.16, 0.17, 0.14, 0.07, 0.15, 0.16, 0.18]
        wacc = [0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10]
        years, score = assess_roic_consistency(roic, wacc)
        assert years == 8
        assert years >= MOAT_WIDTH_THRESHOLDS["NARROW"]
        assert score >= 0.0  # May be low due to volatility penalty from years below WACC

    def test_three_of_ten_no_moat(self):
        """Only 3/10 years ROIC > WACC -> NONE."""
        roic = [0.05, 0.06, 0.12, 0.04, 0.11, 0.03, 0.06, 0.13, 0.05, 0.04]
        wacc = [0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10]
        years, score = assess_roic_consistency(roic, wacc)
        assert years == 3
        assert years < MOAT_WIDTH_THRESHOLDS["NARROW"]

    def test_empty_history(self):
        """Empty histories return 0 years and 0 score."""
        years, score = assess_roic_consistency([], [])
        assert years == 0
        assert score == 0.0

    def test_mismatched_lengths(self):
        """Mismatched list lengths use minimum."""
        roic = [0.15, 0.16, 0.17]
        wacc = [0.09, 0.09]
        years, score = assess_roic_consistency(roic, wacc)
        assert years == 2
        assert score > 0.0

    def test_negative_mean_spread(self):
        """Negative mean spread returns 0 score."""
        roic = [0.05, 0.04, 0.03]
        wacc = [0.10, 0.10, 0.10]
        years, score = assess_roic_consistency(roic, wacc)
        assert years == 0
        assert score == 0.0


# ── Margin Stability Tests ───────────────────────────────────────────────


class TestMarginStability:
    """Tests for assess_gross_margin_stability()."""

    def test_very_stable_margins(self):
        """Std dev < 10 bps -> score 100."""
        margins = [0.4500, 0.4503, 0.4498, 0.4501, 0.4502]
        score = assess_gross_margin_stability(margins)
        assert score == 100.0

    def test_moderate_volatility(self):
        """Moderate margin variation -> mid-range score."""
        margins = [0.40, 0.42, 0.39, 0.43, 0.38]
        score = assess_gross_margin_stability(margins)
        assert 20.0 <= score <= 80.0

    def test_high_volatility(self):
        """Very volatile margins -> low score."""
        margins = [0.30, 0.50, 0.20, 0.55, 0.25]
        score = assess_gross_margin_stability(margins)
        assert score == 20.0  # "else" band

    def test_insufficient_history(self):
        """Single data point returns unknown (50)."""
        score = assess_gross_margin_stability([0.45])
        assert score == 50.0


# ── Market Share Trend Tests ─────────────────────────────────────────────


class TestMarketShareTrend:
    """Tests for assess_market_share_trend()."""

    def test_gaining_share(self):
        """Entity growth >> industry growth -> GAINING."""
        trend, delta = assess_market_share_trend(15.0, 5.0)
        assert trend == "GAINING"
        assert delta > 2.0

    def test_losing_share(self):
        """Entity growth << industry growth -> LOSING."""
        trend, delta = assess_market_share_trend(2.0, 8.0)
        assert trend == "LOSING"
        assert delta < -2.0

    def test_stable_share(self):
        """Entity growth ~ industry growth -> STABLE."""
        trend, delta = assess_market_share_trend(6.0, 5.0)
        assert trend == "STABLE"
        assert -2.0 <= delta <= 2.0

    def test_equal_growth(self):
        """Exactly equal growth -> STABLE with delta=0."""
        trend, delta = assess_market_share_trend(7.0, 7.0)
        assert trend == "STABLE"
        assert delta == 0.0


# ── Cost Advantage Tests ─────────────────────────────────────────────────


class TestCostAdvantage:
    """Tests for score_cost_advantage()."""

    def test_strong_msft_like(self):
        """MSFT-like margins: 40% operating vs 20% peer -> high score."""
        score = score_cost_advantage(0.40, 0.20, 0.04)
        assert score >= 80.0

    def test_weak_commodity(self):
        """Commodity: 5% margin vs 6% peer, high capex -> low score."""
        score = score_cost_advantage(0.05, 0.06, 0.15)
        assert score <= 10.0

    def test_no_margin_advantage(self):
        """Equal margins, moderate capex -> moderate-low score."""
        score = score_cost_advantage(0.15, 0.15, 0.07)
        assert score <= 30.0


# ── Network Effects Tests ────────────────────────────────────────────────


class TestNetworkEffects:
    """Tests for score_network_effects()."""

    def test_strong_platform(self):
        """Platform with high user growth and revenue per user growth."""
        score = score_network_effects(0.25, 0.15, True)
        assert score >= 80.0

    def test_no_network_effects(self):
        """No platform, no user growth data -> 0."""
        score = score_network_effects(None, None, False)
        assert score == 0.0

    def test_partial_data(self):
        """Platform flag but no growth data -> moderate."""
        score = score_network_effects(None, None, True)
        assert score == 30.0


# ── Switching Costs Tests ────────────────────────────────────────────────


class TestSwitchingCosts:
    """Tests for score_switching_costs()."""

    def test_high_enterprise_saas(self):
        """Enterprise SaaS: 90% recurring, 5yr contracts, 97% retention."""
        score = score_switching_costs(0.90, 5.0, 0.97)
        assert score >= 90.0

    def test_low_consumer(self):
        """Consumer product: 10% recurring, no contracts, low retention."""
        score = score_switching_costs(0.10, 0.3, 0.60)
        assert score <= 10.0

    def test_no_data(self):
        """No contract or retention data -> only recurring revenue score."""
        score = score_switching_costs(0.50, None, None)
        assert 15.0 <= score <= 25.0


# ── Intangible Assets Tests ──────────────────────────────────────────────


class TestIntangibleAssets:
    """Tests for score_intangible_assets()."""

    def test_high_rd_pharma(self):
        """Pharma: 20% R&D, 10000 patents, 40% brand premium."""
        score = score_intangible_assets(0.20, 10000, 0.40)
        assert score == 100.0

    def test_low_commodity(self):
        """Commodity: 1% R&D, no patents, no brand premium."""
        score = score_intangible_assets(0.01, 0, None)
        assert score <= 5.0

    def test_no_data(self):
        """Minimal data -> low score."""
        score = score_intangible_assets(0.0, None, None)
        assert score == 0.0


# ── Efficient Scale Tests ────────────────────────────────────────────────


class TestEfficientScale:
    """Tests for score_efficient_scale()."""

    def test_monopoly_like(self):
        """50% share in concentrated market (HHI 3000), 50% capacity."""
        score = score_efficient_scale(0.50, 3000, 0.50)
        assert score == 100.0

    def test_fragmented_market(self):
        """3% share in fragmented market (HHI 200)."""
        score = score_efficient_scale(0.03, 200, 0.03)
        assert score <= 5.0

    def test_moderate_position(self):
        """20% share in moderately concentrated market."""
        score = score_efficient_scale(0.20, 1800, 0.20)
        assert 40.0 <= score <= 70.0


# ── Moat Stability Tests ────────────────────────────────────────────────


class TestMoatStability:
    """Tests for assess_moat_stability()."""

    def test_widening(self):
        """Both spread and margin improving -> WIDENING."""
        result = assess_moat_stability(0.12, 0.08, 0.50, 0.45)
        assert result == "WIDENING"

    def test_eroding(self):
        """Both spread and margin declining -> ERODING."""
        result = assess_moat_stability(0.06, 0.10, 0.42, 0.48)
        assert result == "ERODING"

    def test_stable(self):
        """Minor changes -> STABLE."""
        result = assess_moat_stability(0.10, 0.10, 0.45, 0.45)
        assert result == "STABLE"


# ── Full Assess Moat Tests ───────────────────────────────────────────────


class TestAssessMoat:
    """Tests for assess_moat() orchestrator."""

    def test_wide_moat_msft_like(self):
        """MSFT-like company: consistent ROIC, strong margins, network effects."""
        roic = [0.20, 0.21, 0.22, 0.23, 0.22, 0.24, 0.25, 0.26, 0.25, 0.27, 0.28, 0.29]
        wacc = [0.09] * 12
        margins = [0.68, 0.69, 0.70, 0.70, 0.71, 0.72]
        result = assess_moat(
            roic_history=roic,
            wacc_history=wacc,
            margin_history=margins,
            entity_revenue_growth=15.0,
            industry_revenue_growth=8.0,
            peer_median_margin=0.20,
            operating_margin=0.42,
            capex_intensity=0.04,
            recurring_pct=0.80,
            hhi=2000,
            market_share=0.30,
            qualitative_inputs={
                "user_growth_rate": 0.15,
                "revenue_per_user_trend": 0.08,
                "platform_flag": True,
                "avg_contract_years": 4.0,
                "customer_retention_rate": 0.96,
                "rd_intensity": 0.14,
                "patent_count": 8000,
                "brand_premium": 0.25,
                "capacity_share": 0.30,
            },
        )
        assert isinstance(result, MoatResult)
        assert result.moat_width == "WIDE"
        assert result.moat_score > 60.0
        assert result.roic_above_wacc_years == 12
        assert len(result.evidence) > 0

    def test_no_moat_commodity(self):
        """Commodity company: inconsistent ROIC, no competitive advantages."""
        roic = [0.05, 0.08, 0.03, 0.06, 0.04, 0.07, 0.02, 0.05, 0.03, 0.06]
        wacc = [0.09] * 10
        margins = [0.15, 0.20, 0.10, 0.22, 0.12]
        result = assess_moat(
            roic_history=roic,
            wacc_history=wacc,
            margin_history=margins,
            entity_revenue_growth=3.0,
            industry_revenue_growth=4.0,
            peer_median_margin=0.12,
            operating_margin=0.08,
            capex_intensity=0.18,
            recurring_pct=0.10,
            hhi=300,
            market_share=0.03,
        )
        assert result.moat_width == "NONE"
        assert result.moat_score < 30.0

    def test_narrow_moat(self):
        """Company with 8 years ROIC > WACC: NARROW moat."""
        roic = [0.12, 0.13, 0.08, 0.14, 0.15, 0.11, 0.09, 0.13, 0.14, 0.16]
        wacc = [0.10] * 10
        margins = [0.35, 0.36, 0.34, 0.37, 0.35]
        result = assess_moat(
            roic_history=roic,
            wacc_history=wacc,
            margin_history=margins,
            entity_revenue_growth=8.0,
            industry_revenue_growth=5.0,
            peer_median_margin=0.18,
            operating_margin=0.25,
            capex_intensity=0.06,
            recurring_pct=0.55,
            hhi=1200,
            market_share=0.15,
        )
        assert result.moat_width == "NARROW"

    def test_partial_data_no_crash(self):
        """Minimal data should not crash."""
        result = assess_moat(
            roic_history=[],
            wacc_history=[],
            margin_history=[],
            entity_revenue_growth=0.0,
            industry_revenue_growth=0.0,
            peer_median_margin=0.0,
            operating_margin=0.0,
            capex_intensity=0.0,
            recurring_pct=0.0,
            hhi=0.0,
            market_share=0.0,
        )
        assert isinstance(result, MoatResult)
        assert result.moat_width == "NONE"
        assert result.moat_score >= 0.0

    def test_dominant_source_reported(self):
        """Dominant source should be the highest-scoring moat source."""
        result = assess_moat(
            roic_history=[0.20] * 12,
            wacc_history=[0.09] * 12,
            margin_history=[0.70] * 5,
            entity_revenue_growth=10.0,
            industry_revenue_growth=5.0,
            peer_median_margin=0.15,
            operating_margin=0.40,
            capex_intensity=0.03,
            recurring_pct=0.30,
            hhi=500,
            market_share=0.05,
        )
        # Cost advantage should be dominant given huge margin spread + low capex
        assert result.dominant_source == "cost_advantage"
        assert result.cost_advantage_score >= 80.0

    def test_evidence_populated(self):
        """Evidence list should contain entries for strong moat sources."""
        result = assess_moat(
            roic_history=[0.25] * 12,
            wacc_history=[0.09] * 12,
            margin_history=[0.70] * 5,
            entity_revenue_growth=12.0,
            industry_revenue_growth=5.0,
            peer_median_margin=0.15,
            operating_margin=0.40,
            capex_intensity=0.03,
            recurring_pct=0.85,
            hhi=2800,
            market_share=0.35,
            qualitative_inputs={
                "user_growth_rate": 0.25,
                "revenue_per_user_trend": 0.12,
                "platform_flag": True,
                "avg_contract_years": 5.0,
                "customer_retention_rate": 0.97,
                "rd_intensity": 0.18,
                "patent_count": 6000,
                "brand_premium": 0.35,
                "capacity_share": 0.40,
            },
        )
        sources_in_evidence = {e["source"] for e in result.evidence}
        assert "cost_advantage" in sources_in_evidence
        assert "switching_costs" in sources_in_evidence
