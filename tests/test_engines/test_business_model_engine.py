"""Tests for Pillar 3 Phase 2 — Part 7a: Business Model Analysis Engine."""

from src.engines.business_model_engine import (
    BusinessModelDurability,
    BusinessModelResult,
    RevenueQuality,
    ScalingBehavior,
    UnitEconomics,
    analyze_business_model,
    assess_business_model_durability,
    assess_revenue_quality,
    compute_scaling_behavior,
    compute_unit_economics,
)


# ── Revenue Quality Tests ────────────────────────────────────────────────


class TestAssessRevenueQuality:
    """Tests for assess_revenue_quality()."""

    def test_high_quality_recurring_diversified_low_cyclicality(self):
        """MSFT-like: high recurring, diversified, stable revenue."""
        financials = {
            "recurring_revenue_pct": 0.78,
            "deferred_revenue_history": [18.0, 19.5, 21.0, 23.5],
            "top_customer_pct": 3.0,
            "geo_segment_count": 5,
            "product_segment_count": 5,
            "revenue_history": [168.0, 176.0, 185.0, 198.0, 211.0],
        }
        result = assess_revenue_quality(financials)
        assert isinstance(result, RevenueQuality)
        assert result.recurring_pct == 0.78
        assert result.deferred_revenue_trend == "GROWING"
        assert result.customer_concentration == 3.0
        assert result.diversification_score >= 80.0
        assert result.cyclicality_score < 30.0  # Low volatility

    def test_low_quality_concentrated_cyclical(self):
        """Single-customer, single-product, cyclical commodity producer."""
        financials = {
            "recurring_revenue_pct": 0.10,
            "deferred_revenue_history": [],
            "top_customer_pct": 55.0,
            "geo_segment_count": 1,
            "product_segment_count": 1,
            "revenue_history": [80.0, 120.0, 60.0, 140.0, 70.0],
        }
        result = assess_revenue_quality(financials)
        assert result.recurring_pct == 0.10
        assert result.customer_concentration == 55.0
        assert result.diversification_score <= 14.0  # 7+7+0 = 14
        assert result.cyclicality_score > 60.0  # Volatile swings

    def test_unknown_missing_data(self):
        """All fields absent should return safe defaults."""
        result = assess_revenue_quality({})
        assert result.recurring_pct is None
        assert result.deferred_revenue_trend == "UNKNOWN"
        assert result.customer_concentration is None
        # geo=1, prod=1, top_customer=None -> 7+7+15 = 29
        assert result.diversification_score == 29.0
        assert result.cyclicality_score == 50.0  # Unknown

    def test_deferred_revenue_declining_trend(self):
        """Declining deferred revenue signals weakening backlog."""
        financials = {
            "deferred_revenue_history": [25.0, 23.0, 20.0, 17.0],
            "revenue_history": [100.0, 105.0, 108.0, 110.0, 112.0],
        }
        result = assess_revenue_quality(financials)
        assert result.deferred_revenue_trend == "DECLINING"


# ── Unit Economics Tests ─────────────────────────────────────────────────


class TestComputeUnitEconomics:
    """Tests for compute_unit_economics()."""

    def test_with_employees_and_segments(self):
        """Tech company with high revenue per employee."""
        financials = {
            "revenue": 50_000.0,
            "employee_count": 200,
            "segments": [
                {"name": "Cloud", "revenue": 30_000.0, "operating_income": 12_000.0},
                {"name": "License", "revenue": 20_000.0, "operating_income": 8_000.0},
            ],
        }
        result = compute_unit_economics(financials)
        assert isinstance(result, UnitEconomics)
        assert result.revenue_per_employee == 250.0  # 50000/200
        assert result.revenue_per_subscriber is None
        assert result.contribution_margin_by_segment["Cloud"] == 0.4
        assert result.contribution_margin_by_segment["License"] == 0.4

    def test_with_subscribers(self):
        """SaaS company with subscriber metrics."""
        financials = {
            "revenue": 2_400.0,
            "subscriber_count": 12_000,
            "segments": [],
        }
        result = compute_unit_economics(financials)
        assert result.revenue_per_subscriber == 0.2  # 2400/12000
        assert result.revenue_per_employee is None

    def test_missing_data(self):
        """No employee/subscriber data returns None for per-unit metrics."""
        result = compute_unit_economics({})
        assert result.revenue_per_employee is None
        assert result.revenue_per_subscriber is None
        assert result.contribution_margin_by_segment == {}


# ── Scaling Behavior Tests ───────────────────────────────────────────────


class TestComputeScalingBehavior:
    """Tests for compute_scaling_behavior()."""

    def test_positive_operating_leverage(self):
        """Revenue up 10%, EBIT up 20% -> op leverage ~2.0."""
        history = [
            {"revenue": 1000.0, "ebit": 100.0, "sga": 300.0},
            {"revenue": 1100.0, "ebit": 120.0, "sga": 315.0},
        ]
        result = compute_scaling_behavior(history)
        assert isinstance(result, ScalingBehavior)
        assert result.operating_leverage is not None
        assert result.operating_leverage > 1.5  # EBIT grew faster than rev
        assert result.incremental_margin is not None
        assert result.incremental_margin > 0.0
        # SGA grew 5% vs revenue 10% -> sga_scalability 0.5
        assert result.sga_scalability is not None
        assert result.sga_scalability < 1.0  # Scalable

    def test_negative_operating_leverage(self):
        """Revenue up but EBIT shrinks -> negative leverage."""
        history = [
            {"revenue": 1000.0, "ebit": 100.0, "sga": 300.0},
            {"revenue": 1100.0, "ebit": 80.0, "sga": 360.0},
        ]
        result = compute_scaling_behavior(history)
        assert result.operating_leverage is not None
        assert result.operating_leverage < 0  # EBIT shrank while rev grew
        assert result.sga_scalability is not None
        assert result.sga_scalability > 1.0  # SGA growing faster = not scalable

    def test_insufficient_history(self):
        """Single period returns empty ScalingBehavior."""
        result = compute_scaling_behavior([{"revenue": 500.0, "ebit": 50.0}])
        assert result.operating_leverage is None
        assert result.incremental_margin is None
        assert result.sga_scalability is None


# ── Business Model Durability Tests ──────────────────────────────────────


class TestAssessBusinessModelDurability:
    """Tests for assess_business_model_durability()."""

    def test_high_switching_costs_and_moat(self):
        """Enterprise SaaS with network effects, long contracts, high R&D, stable margins."""
        data = {
            "contract_length_avg": 4.0,
            "r_and_d_pct": 0.15,
            "gross_margin_history": [0.72, 0.73, 0.72, 0.74, 0.73],
            "roic_history": [0.18, 0.19, 0.20, 0.21, 0.22],
            "business_description": (
                "We operate a leading platform ecosystem with strong network "
                "effects and a marketplace connecting millions of users."
            ),
        }
        result = assess_business_model_durability(data)
        assert isinstance(result, BusinessModelDurability)
        assert result.switching_cost_score >= 80.0
        assert result.moat_type == "NETWORK_EFFECT"
        assert result.disruption_vulnerability < 40.0

    def test_vulnerable_business(self):
        """Low-margin commodity business with no moat signals."""
        data = {
            "contract_length_avg": 0.5,
            "r_and_d_pct": 0.01,
            "gross_margin_history": [0.18, 0.15, 0.22, 0.12, 0.20],
            "roic_history": [0.04, 0.03, 0.05, 0.02, 0.04],
            "business_description": "We sell commodity products through wholesale channels.",
        }
        result = assess_business_model_durability(data)
        assert result.switching_cost_score < 20.0
        assert result.moat_type is None
        assert result.disruption_vulnerability > 60.0

    def test_no_data_returns_defaults(self):
        """Empty dict returns neutral defaults."""
        result = assess_business_model_durability({})
        assert result.switching_cost_score == 0.0
        assert result.moat_type is None
        assert result.disruption_vulnerability == 50.0


# ── Orchestrator Tests ───────────────────────────────────────────────────


class TestAnalyzeBusinessModel:
    """Tests for analyze_business_model() orchestrator."""

    def test_full_data(self):
        """Full data produces all sub-results."""
        financials = {
            "recurring_revenue_pct": 0.65,
            "deferred_revenue_history": [10.0, 12.0, 14.0],
            "top_customer_pct": 8.0,
            "geo_segment_count": 4,
            "product_segment_count": 3,
            "revenue_history": [90.0, 95.0, 100.0, 108.0, 115.0],
            "revenue": 115_000.0,
            "employee_count": 500,
            "segments": [
                {"name": "SaaS", "revenue": 80_000.0, "operating_income": 32_000.0},
                {"name": "Services", "revenue": 35_000.0, "operating_income": 7_000.0},
            ],
            "contract_length_avg": 3.5,
            "r_and_d_pct": 0.12,
            "gross_margin_history": [0.60, 0.61, 0.62, 0.63],
            "roic_history": [0.14, 0.15, 0.16, 0.17],
            "business_description": "We are a premium brand with strong customer loyalty and trust.",
        }
        history = [
            {"revenue": 100_000.0, "ebit": 20_000.0, "sga": 25_000.0},
            {"revenue": 115_000.0, "ebit": 26_000.0, "sga": 27_000.0},
        ]
        result = analyze_business_model(financials, history)
        assert isinstance(result, BusinessModelResult)
        assert result.revenue_quality.recurring_pct == 0.65
        assert result.unit_economics.revenue_per_employee == 230.0
        assert result.scaling.operating_leverage is not None
        assert result.durability.switching_cost_score > 0

    def test_minimal_data(self):
        """Minimal/empty data still returns a valid result without errors."""
        result = analyze_business_model({})
        assert isinstance(result, BusinessModelResult)
        assert result.revenue_quality.recurring_pct is None
        assert result.unit_economics.revenue_per_employee is None
        assert result.scaling.operating_leverage is None
        assert result.durability.switching_cost_score == 0.0
