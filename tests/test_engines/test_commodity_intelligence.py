"""Tests for Pillar 3 Phase 3B — Commodity Intelligence Engine."""

import pytest

from src.engines.commodity_intelligence import (
    COMMODITY_CATEGORIES,
    EXPOSURE_TYPES,
    CommodityImpact,
    CommoditySnapshot,
    ScenarioResult,
    build_commodity_snapshot,
    classify_company_exposure,
    compute_historical_correlation,
    compute_price_percentile,
    compute_returns,
    compute_sensitivity_score,
    compute_supply_demand_balance,
    detect_price_anomaly,
    get_commodity_category,
    run_commodity_scenario,
)


# ── Helpers ────────────────────────────────────────────────────────────

def _make_prices(values: list[float]) -> list[dict]:
    """Build a list of price dicts from a simple list of floats."""
    return [
        {"date": f"2025-01-{i + 1:02d}", "close_price": v}
        for i, v in enumerate(values)
    ]


# ── TestReturns ────────────────────────────────────────────────────────


class TestReturns:
    """Tests for compute_returns()."""

    def test_positive_returns(self):
        """Price goes from 100 to 110 over 2 days → positive 1d return."""
        prices = _make_prices([100.0, 105.0, 110.0])
        result = compute_returns(prices, periods={"1d": 1})
        assert "1d" in result
        assert result["1d"] > 0

    def test_negative_returns(self):
        """Price drops from 100 to 90 → negative return."""
        prices = _make_prices([100.0, 95.0, 90.0])
        result = compute_returns(prices, periods={"1d": 1})
        assert "1d" in result
        assert result["1d"] < 0

    def test_mixed_timeframes(self):
        """Return different periods from a longer history."""
        vals = list(range(50, 100))  # 50 prices
        prices = _make_prices([float(v) for v in vals])
        result = compute_returns(prices, periods={"1d": 1, "1w": 7, "1m": 30})
        assert "1d" in result
        assert "1w" in result
        assert "1m" in result

    def test_insufficient_data(self):
        """Fewer than 2 prices → empty dict."""
        prices = _make_prices([100.0])
        result = compute_returns(prices)
        assert result == {}


# ── TestPercentile ─────────────────────────────────────────────────────


class TestPercentile:
    """Tests for compute_price_percentile()."""

    def test_at_bottom(self):
        """Current price lower than all history → 0."""
        assert compute_price_percentile(1.0, [10.0, 20.0, 30.0]) == 0.0

    def test_at_top(self):
        """Current price higher than all history → 100."""
        assert compute_price_percentile(100.0, [10.0, 20.0, 30.0]) == 100.0

    def test_middle(self):
        """Current price in the middle → approximately 50%."""
        history = [float(i) for i in range(1, 101)]  # 1..100
        pct = compute_price_percentile(50.0, history)
        assert 45.0 <= pct <= 55.0

    def test_small_history(self):
        """Works correctly with a 2-element history."""
        pct = compute_price_percentile(5.0, [3.0, 10.0])
        assert pct == 50.0  # 1 of 2 below


# ── TestSnapshot ──────────────────────────────────────────────────────


class TestSnapshot:
    """Tests for build_commodity_snapshot()."""

    def test_full_snapshot(self):
        """Build from a 2-year-ish daily history."""
        vals = [50.0 + i * 0.05 for i in range(500)]
        prices = _make_prices(vals)
        snap = build_commodity_snapshot("WTI", prices)
        assert isinstance(snap, CommoditySnapshot)
        assert snap.commodity_code == "WTI"
        assert snap.current_price == vals[-1]
        assert snap.percentile_1y is not None
        assert snap.percentile_5y is not None

    def test_minimal_data(self):
        """Empty prices → zeroed-out snapshot."""
        snap = build_commodity_snapshot("GOLD", [])
        assert snap.current_price == 0.0
        assert snap.price_change_1d_pct is None


# ── TestSupplyDemand ──────────────────────────────────────────────────


class TestSupplyDemand:
    """Tests for compute_supply_demand_balance()."""

    def test_surplus(self):
        result = compute_supply_demand_balance(
            {"total": 110.0}, {"total": 100.0},
        )
        assert result == "SURPLUS"

    def test_deficit(self):
        result = compute_supply_demand_balance(
            {"total": 90.0}, {"total": 100.0},
        )
        assert result == "DEFICIT"

    def test_balanced(self):
        result = compute_supply_demand_balance(
            {"total": 100.0}, {"total": 100.0},
        )
        assert result == "BALANCED"

    def test_edge_at_threshold(self):
        """Exactly at 1.05 boundary → BALANCED (not strictly greater)."""
        result = compute_supply_demand_balance(
            {"total": 105.0}, {"total": 100.0},
        )
        assert result == "BALANCED"


# ── TestExposure ─────────────────────────────────────────────────────


class TestExposure:
    """Tests for classify_company_exposure()."""

    def test_energy_company_is_producer(self):
        result = classify_company_exposure("ENERGY", None, "WTI")
        assert result == "PRODUCER"

    def test_airline_is_consumer(self):
        result = classify_company_exposure("AIRLINES", None, "WTI")
        assert result == "CONSUMER"

    def test_tech_is_indirect(self):
        result = classify_company_exposure(
            "INFORMATION_TECHNOLOGY", None, "GOLD",
        )
        assert result == "INDIRECT"


# ── TestSensitivity ──────────────────────────────────────────────────


class TestSensitivity:
    """Tests for compute_sensitivity_score()."""

    def test_high_sensitivity_producer(self):
        """Oil producer with 80% revenue exposure + 0.9 corr → high."""
        score = compute_sensitivity_score("PRODUCER", 80.0, 0.9)
        assert score >= 75.0

    def test_low_sensitivity_indirect(self):
        """Indirect exposure, no data → base score only."""
        score = compute_sensitivity_score("INDIRECT", None, None)
        assert score == 15.0

    def test_no_data_defaults(self):
        """Unknown exposure type with no data → minimal score."""
        score = compute_sensitivity_score("UNKNOWN", None, None)
        assert score == 15.0


# ── TestCorrelation ──────────────────────────────────────────────────


class TestCorrelation:
    """Tests for compute_historical_correlation()."""

    def test_positive_correlation(self):
        """Perfectly correlated series → correlation near 1.0."""
        eq = [1.0, 2.0, 3.0, 4.0, 5.0]
        co = [2.0, 4.0, 6.0, 8.0, 10.0]
        corr = compute_historical_correlation(eq, co)
        assert corr == pytest.approx(1.0, abs=0.01)

    def test_negative_correlation(self):
        """Inversely correlated → near -1.0."""
        eq = [1.0, 2.0, 3.0, 4.0, 5.0]
        co = [10.0, 8.0, 6.0, 4.0, 2.0]
        corr = compute_historical_correlation(eq, co)
        assert corr == pytest.approx(-1.0, abs=0.01)

    def test_zero_correlation(self):
        """Uncorrelated data → near 0."""
        eq = [1.0, -1.0, 1.0, -1.0, 1.0, -1.0]
        co = [1.0, 1.0, -1.0, -1.0, 1.0, 1.0]
        corr = compute_historical_correlation(eq, co)
        assert -0.5 <= corr <= 0.5

    def test_unequal_lengths(self):
        """Different length series → truncated and still works."""
        eq = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
        co = [2.0, 4.0, 6.0, 8.0, 10.0]
        corr = compute_historical_correlation(eq, co)
        assert corr == pytest.approx(1.0, abs=0.01)


# ── TestScenario ─────────────────────────────────────────────────────


class TestScenario:
    """Tests for run_commodity_scenario()."""

    def _companies(self) -> list[dict]:
        return [
            {
                "entity_id": "E1", "entity_name": "OilCo",
                "exposure_type": "PRODUCER", "sensitivity_score": 90.0,
                "revenue_exposure_pct": 70.0, "commodity_code": "WTI",
            },
            {
                "entity_id": "E2", "entity_name": "AirlineA",
                "exposure_type": "CONSUMER", "sensitivity_score": 75.0,
                "revenue_exposure_pct": 30.0, "commodity_code": "WTI",
            },
            {
                "entity_id": "E3", "entity_name": "TechCo",
                "exposure_type": "INDIRECT", "sensitivity_score": 20.0,
                "revenue_exposure_pct": 5.0, "commodity_code": "WTI",
            },
            {
                "entity_id": "E4", "entity_name": "MinerB",
                "exposure_type": "PRODUCER", "sensitivity_score": 85.0,
                "revenue_exposure_pct": 60.0, "commodity_code": "WTI",
            },
            {
                "entity_id": "E5", "entity_name": "RefinerC",
                "exposure_type": "CONSUMER", "sensitivity_score": 70.0,
                "revenue_exposure_pct": 40.0, "commodity_code": "WTI",
            },
        ]

    def test_oil_to_100(self):
        """Oil price moves from $75 to $100 → price increase scenario."""
        result = run_commodity_scenario(75.0, 100.0, self._companies())
        assert isinstance(result, ScenarioResult)
        assert result.price_change_pct > 0
        assert result.total_affected == 5
        assert len(result.most_impacted) == 5
        # Producers should have POSITIVE direction on price increase
        oil_co = next(
            c for c in result.affected_companies if c.entity_id == "E1"
        )
        assert oil_co.direction == "POSITIVE"

    def test_price_drop(self):
        """Oil drops from $80 to $50 → producers hurt."""
        result = run_commodity_scenario(80.0, 50.0, self._companies())
        assert result.price_change_pct < 0
        oil_co = next(
            c for c in result.affected_companies if c.entity_id == "E1"
        )
        assert oil_co.direction == "NEGATIVE"
        # Consumers benefit from price drop
        airline = next(
            c for c in result.affected_companies if c.entity_id == "E2"
        )
        assert airline.direction == "POSITIVE"

    def test_no_companies(self):
        """Empty company list → zero affected."""
        result = run_commodity_scenario(80.0, 100.0, [])
        assert result.total_affected == 0
        assert result.most_impacted == []


# ── TestAnomaly ──────────────────────────────────────────────────────


class TestAnomaly:
    """Tests for detect_price_anomaly()."""

    def test_3_sigma_spike(self):
        """A massive spike at the end should be flagged."""
        prices = [50.0] * 50 + [200.0]  # last value is a huge outlier
        is_anomaly, z = detect_price_anomaly(prices, threshold_sigma=2.0)
        assert is_anomaly is True
        assert z is not None
        assert z > 2.0

    def test_normal_not_flagged(self):
        """Normal price movement → not an anomaly."""
        prices = [50.0, 51.0, 49.5, 50.5, 50.2]
        is_anomaly, z = detect_price_anomaly(prices, threshold_sigma=2.0)
        assert is_anomaly is False

    def test_empty_list(self):
        """Too few prices → not anomaly, z is None."""
        is_anomaly, z = detect_price_anomaly([], threshold_sigma=2.0)
        assert is_anomaly is False
        assert z is None


# ── TestCategory ─────────────────────────────────────────────────────


class TestCategory:
    """Tests for get_commodity_category()."""

    def test_known_commodity(self):
        assert get_commodity_category("WTI") == "ENERGY"
        assert get_commodity_category("GOLD") == "PRECIOUS_METALS"
        assert get_commodity_category("COPPER") == "INDUSTRIAL_METALS"
        assert get_commodity_category("CORN") == "AGRICULTURE"
        assert get_commodity_category("CATTLE") == "LIVESTOCK"

    def test_unknown_commodity(self):
        assert get_commodity_category("UNOBTANIUM") is None


# ── Integration Tests ────────────────────────────────────────────────


class TestIntegration:
    """End-to-end commodity intelligence pipeline tests."""

    def test_full_energy_pipeline(self):
        """Simulate a complete analysis for WTI crude oil."""
        # Build price history (upward trend over ~400 days)
        prices = _make_prices([60.0 + i * 0.05 for i in range(400)])

        # Snapshot
        snap = build_commodity_snapshot("WTI", prices)
        assert snap.commodity_code == "WTI"
        assert snap.current_price > 60.0

        # Category lookup
        cat = get_commodity_category("WTI")
        assert cat == "ENERGY"

        # Company classification
        exp = classify_company_exposure("ENERGY", None, "WTI")
        assert exp == "PRODUCER"

        # Sensitivity
        score = compute_sensitivity_score("PRODUCER", 70.0, 0.8)
        assert score > 70.0

    def test_supply_demand_with_scenario(self):
        """Combine supply/demand with a price scenario."""
        balance = compute_supply_demand_balance(
            {"total": 90.0}, {"total": 100.0},
        )
        assert balance == "DEFICIT"

        # With a deficit, simulate price increase
        companies = [
            {
                "entity_id": "E1", "entity_name": "OilCo",
                "exposure_type": "PRODUCER", "sensitivity_score": 85.0,
                "revenue_exposure_pct": 60.0, "commodity_code": "WTI",
            },
        ]
        result = run_commodity_scenario(75.0, 95.0, companies)
        assert result.price_change_pct > 0
        assert result.total_affected == 1

    def test_anomaly_detection_integration(self):
        """Price spike triggers anomaly in a realistic time series."""
        # Stable prices then a spike
        stable = [70.0 + (i % 5) * 0.1 for i in range(100)]
        stable.append(120.0)  # big spike
        is_anomaly, z = detect_price_anomaly(stable)
        assert is_anomaly is True
        assert z is not None and z > 2.0
