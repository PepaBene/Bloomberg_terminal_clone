"""Tests for Pillar 3 Phase 3A — Concentration Risk Engine."""

from src.engines.concentration_risk import (
    CUSTOMER_RISK_THRESHOLDS,
    GEOGRAPHIC_RISK_THRESHOLDS,
    SUPPLIER_RISK_THRESHOLDS,
    ConcentrationResult,
    assess_concentration_risk,
    classify_customer_concentration,
    classify_geographic_concentration,
    classify_supplier_concentration,
    compare_to_industry,
    compute_customer_hhi,
    compute_fx_exposure_score,
    compute_geographic_hhi,
    compute_overall_concentration,
    identify_risk_factors,
)


# ── Customer Concentration Tests ─────────────────────────────────────────


class TestCustomerConcentration:
    """Tests for classify_customer_concentration()."""

    def test_high_lockheed_govt(self):
        """Lockheed-like: 50% from government -> HIGH."""
        result = classify_customer_concentration(50.0, 75.0, 90.0)
        assert result == "HIGH"

    def test_moderate_apple_like(self):
        """Apple-like: 25% from top customer -> MODERATE."""
        result = classify_customer_concentration(25.0, 50.0, 65.0)
        assert result == "MODERATE"

    def test_low_diversified(self):
        """Well-diversified: 5% top customer -> LOW_RISK."""
        result = classify_customer_concentration(5.0, 20.0, 35.0)
        assert result == "LOW_RISK"

    def test_no_data(self):
        """No data available -> LOW_RISK."""
        result = classify_customer_concentration(None, None, None)
        assert result == "LOW_RISK"


# ── Customer HHI Tests ───────────────────────────────────────────────────


class TestCustomerHHI:
    """Tests for compute_customer_hhi()."""

    def test_concentrated(self):
        """Single customer 100% -> HHI = 10000."""
        hhi = compute_customer_hhi([100.0])
        assert hhi == 10000.0

    def test_diversified(self):
        """10 customers at 10% each -> HHI = 1000."""
        hhi = compute_customer_hhi([10.0] * 10)
        assert hhi == 1000.0

    def test_empty(self):
        """Empty list -> HHI = 0."""
        hhi = compute_customer_hhi([])
        assert hhi == 0.0


# ── Supplier Concentration Tests ─────────────────────────────────────────


class TestSupplierConcentration:
    """Tests for classify_supplier_concentration()."""

    def test_high_many_single_source(self):
        """3+ single-source inputs -> HIGH."""
        result = classify_supplier_concentration(4, 5, 2)
        assert result == "HIGH"

    def test_moderate(self):
        """1-2 single-source inputs -> MODERATE."""
        result = classify_supplier_concentration(2, 3, 3)
        assert result == "MODERATE"

    def test_low(self):
        """No single-source inputs, good spread -> LOW_RISK."""
        result = classify_supplier_concentration(0, 2, 8)
        assert result == "LOW_RISK"


# ── Geographic HHI Tests ─────────────────────────────────────────────────


class TestGeographicHHI:
    """Tests for compute_geographic_hhi()."""

    def test_us_only(self):
        """100% US -> HHI = 10000."""
        hhi = compute_geographic_hhi({"US": 100.0})
        assert hhi == 10000.0

    def test_diversified(self):
        """5 regions at 20% each -> HHI = 2000."""
        hhi = compute_geographic_hhi({
            "US": 20.0, "Europe": 20.0, "Asia": 20.0,
            "LatAm": 20.0, "Africa": 20.0,
        })
        assert hhi == 2000.0

    def test_emerging_heavy(self):
        """60% China, 20% India, 20% Brazil."""
        hhi = compute_geographic_hhi({
            "China": 60.0, "India": 20.0, "Brazil": 20.0,
        })
        assert hhi > 4000.0  # 3600 + 400 + 400 = 4400


# ── Geographic Concentration Tests ───────────────────────────────────────


class TestGeographicConcentration:
    """Tests for classify_geographic_concentration()."""

    def test_domestic_heavy(self):
        """80% domestic -> HIGH."""
        result = classify_geographic_concentration(80.0, 6800.0, 0.0)
        assert result == "HIGH"

    def test_global_diversified(self):
        """25% top country, low HHI -> LOW_RISK."""
        result = classify_geographic_concentration(25.0, 1800.0, 5.0)
        assert result == "LOW_RISK"

    def test_high_risk_exposure(self):
        """30% high-risk exposure -> MODERATE."""
        result = classify_geographic_concentration(35.0, 2000.0, 25.0)
        assert result == "MODERATE"


# ── FX Exposure Tests ────────────────────────────────────────────────────


class TestFXExposure:
    """Tests for compute_fx_exposure_score()."""

    def test_pure_domestic(self):
        """100% domestic -> 0 FX risk."""
        score = compute_fx_exposure_score(100.0, 0.0, 0.0)
        assert score == 0.0

    def test_fifty_fifty(self):
        """50% domestic, 50% developed -> moderate."""
        score = compute_fx_exposure_score(50.0, 50.0, 0.0)
        assert 15.0 <= score <= 25.0

    def test_heavy_em(self):
        """20% domestic, 30% developed, 50% EM -> high."""
        score = compute_fx_exposure_score(20.0, 30.0, 50.0)
        assert score >= 50.0


# ── Overall Concentration Tests ──────────────────────────────────────────


class TestOverallConcentration:
    """Tests for compute_overall_concentration()."""

    def test_all_high(self):
        """All high risk -> HIGH overall."""
        risk, score = compute_overall_concentration("HIGH", "HIGH", "HIGH")
        assert risk == "HIGH"
        assert score >= 80.0

    def test_all_low(self):
        """All low risk -> LOW_RISK overall."""
        risk, score = compute_overall_concentration("LOW_RISK", "LOW_RISK", "LOW_RISK")
        assert risk == "LOW_RISK"
        assert score <= 25.0

    def test_mixed(self):
        """Mixed risks -> worst-of."""
        risk, score = compute_overall_concentration("LOW_RISK", "HIGH", "LOW_RISK")
        assert risk == "HIGH"
        assert 30.0 <= score <= 60.0


# ── Full Assessment Tests ────────────────────────────────────────────────


class TestAssessConcentrationRisk:
    """Tests for assess_concentration_risk() orchestrator."""

    def test_defense_contractor_high_customer(self):
        """Defense contractor: 60% government customer -> HIGH customer risk."""
        result = assess_concentration_risk(
            customer_data={
                "top1_pct": 60.0,
                "top5_pct": 85.0,
                "top10_pct": 95.0,
                "customer_pcts": [60.0, 10.0, 8.0, 5.0, 2.0, 15.0],
            },
            supplier_data={
                "single_source_count": 4,
                "critical_count": 6,
                "geographic_spread": 2,
            },
            geographic_data={
                "revenue_by_region": {"US": 90.0, "Europe": 8.0, "Asia": 2.0},
                "domestic_pct": 90.0,
                "developed_market_pct": 8.0,
                "em_pct": 2.0,
                "high_risk_exposure": 0.0,
            },
        )
        assert isinstance(result, ConcentrationResult)
        assert result.customer_risk == "HIGH"
        assert result.supplier_risk == "HIGH"
        assert result.geographic_risk == "HIGH"
        assert result.overall_risk == "HIGH"
        assert result.overall_score >= 70.0
        assert len(result.risk_factors) >= 2

    def test_global_consumer_low_risk(self):
        """Global consumer company: diversified everywhere -> LOW_RISK."""
        result = assess_concentration_risk(
            customer_data={
                "top1_pct": 5.0,
                "top5_pct": 15.0,
                "top10_pct": 25.0,
                "customer_pcts": [5.0, 4.0, 3.0, 2.5, 2.0] + [1.0] * 83 + [0.5],
            },
            supplier_data={
                "single_source_count": 0,
                "critical_count": 2,
                "geographic_spread": 12,
            },
            geographic_data={
                "revenue_by_region": {
                    "US": 30.0, "Europe": 25.0, "Asia": 20.0,
                    "LatAm": 15.0, "Africa": 10.0,
                },
                "domestic_pct": 30.0,
                "developed_market_pct": 45.0,
                "em_pct": 25.0,
                "high_risk_exposure": 5.0,
            },
        )
        assert result.customer_risk == "LOW_RISK"
        assert result.supplier_risk == "LOW_RISK"
        assert result.geographic_risk == "LOW_RISK"
        assert result.overall_risk == "LOW_RISK"
        assert result.overall_score <= 25.0

    def test_partial_data_no_crash(self):
        """Minimal/empty data should not crash."""
        result = assess_concentration_risk(
            customer_data={},
            supplier_data={},
            geographic_data={},
        )
        assert isinstance(result, ConcentrationResult)
        assert result.customer_risk == "LOW_RISK"
        assert result.overall_score >= 0.0


# ── Risk Factor Identification Tests ─────────────────────────────────────


class TestIdentifyRiskFactors:
    """Tests for identify_risk_factors()."""

    def test_multiple_risks(self):
        """Multiple risk dimensions flagged."""
        result = ConcentrationResult(
            customer_risk="HIGH",
            supplier_risk="HIGH",
            geographic_risk="MODERATE",
            overall_risk="HIGH",
            overall_score=80.0,
            customer_top1_pct=55.0,
            customer_hhi=3500.0,
            supplier_single_source_count=5,
            geographic_hhi=5000.0,
            fx_exposure_score=60.0,
        )
        factors = identify_risk_factors(result)
        assert len(factors) >= 3
        assert any("customer" in f.lower() for f in factors)
        assert any("supplier" in f.lower() for f in factors)
        assert any("fx" in f.lower() or "geographic" in f.lower() for f in factors)

    def test_no_risks(self):
        """Clean result should have no risk factors."""
        result = ConcentrationResult(
            customer_risk="LOW_RISK",
            supplier_risk="LOW_RISK",
            geographic_risk="LOW_RISK",
            overall_risk="LOW_RISK",
            overall_score=15.0,
            customer_top1_pct=5.0,
            customer_hhi=500.0,
            supplier_single_source_count=0,
            geographic_hhi=2000.0,
            fx_exposure_score=10.0,
        )
        factors = identify_risk_factors(result)
        assert len(factors) == 0


# ── Industry Comparison Tests ────────────────────────────────────────────


class TestCompareToIndustry:
    """Tests for compare_to_industry()."""

    def test_more_concentrated(self):
        """Entity more concentrated than industry."""
        result = ConcentrationResult(
            customer_risk="HIGH",
            supplier_risk="MODERATE",
            geographic_risk="HIGH",
            overall_risk="HIGH",
            overall_score=75.0,
            customer_top1_pct=50.0,
            customer_hhi=4000.0,
            supplier_single_source_count=3,
            geographic_hhi=6000.0,
            fx_exposure_score=20.0,
        )
        comparison = compare_to_industry(result, {
            "customer_hhi": 1500.0,
            "geographic_hhi": 3000.0,
            "overall_score": 40.0,
        })
        assert comparison["relative_risk"] == "MORE_CONCENTRATED"
        assert comparison["customer_hhi_vs_industry"] > 0

    def test_less_concentrated(self):
        """Entity less concentrated than industry."""
        result = ConcentrationResult(
            customer_risk="LOW_RISK",
            supplier_risk="LOW_RISK",
            geographic_risk="LOW_RISK",
            overall_risk="LOW_RISK",
            overall_score=20.0,
            customer_top1_pct=5.0,
            customer_hhi=800.0,
            supplier_single_source_count=0,
            geographic_hhi=2000.0,
            fx_exposure_score=10.0,
        )
        comparison = compare_to_industry(result, {
            "customer_hhi": 2500.0,
            "geographic_hhi": 4000.0,
            "overall_score": 55.0,
        })
        assert comparison["relative_risk"] == "LESS_CONCENTRATED"
