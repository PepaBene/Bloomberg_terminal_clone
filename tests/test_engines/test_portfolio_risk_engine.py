"""Tests for Pillar 4 Phase 3 — Portfolio Risk Engine.

Covers all 12 public functions with realistic portfolio data.
"""

import math

import pytest

from src.engines.portfolio_risk_engine import (
    CONCENTRATION_THRESHOLDS,
    CONFIDENCE_LEVELS,
    FACTORS,
    HISTORICAL_SCENARIOS,
    ConcentrationResult,
    FactorExposureResult,
    StressTestResult,
    VaRResult,
    analyze_concentration,
    calculate_portfolio_var,
    classify_concentration,
    compute_component_var,
    compute_factor_exposures,
    compute_hhi,
    compute_incremental_var,
    compute_marginal_var,
    compute_undiversified_var,
    get_available_scenarios,
    run_hypothetical_stress,
    run_stress_test,
)


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def two_asset_portfolio():
    """Simple 2-asset portfolio for exact VaR math."""
    weights = {"AAPL": 0.60, "MSFT": 0.40}
    individual_vars = {"AAPL": 0.02, "MSFT": 0.015}
    correlation_matrix = {
        "AAPL": {"AAPL": 1.0, "MSFT": 0.5},
        "MSFT": {"MSFT": 1.0, "AAPL": 0.5},
    }
    return weights, individual_vars, correlation_matrix


@pytest.fixture
def five_stock_portfolio():
    """Diversified 5-stock portfolio."""
    weights = {
        "AAPL": 0.25, "MSFT": 0.20, "GOOGL": 0.20,
        "AMZN": 0.20, "META": 0.15,
    }
    individual_vars = {
        "AAPL": 0.020, "MSFT": 0.018, "GOOGL": 0.022,
        "AMZN": 0.025, "META": 0.028,
    }
    # Low-to-moderate correlations
    tickers = sorted(weights.keys())
    corr = {}
    base_corr = {
        ("AAPL", "MSFT"): 0.65, ("AAPL", "GOOGL"): 0.55,
        ("AAPL", "AMZN"): 0.50, ("AAPL", "META"): 0.45,
        ("MSFT", "GOOGL"): 0.60, ("MSFT", "AMZN"): 0.55,
        ("MSFT", "META"): 0.50, ("GOOGL", "AMZN"): 0.50,
        ("GOOGL", "META"): 0.55, ("AMZN", "META"): 0.45,
    }
    for t in tickers:
        corr[t] = {}
        for u in tickers:
            if t == u:
                corr[t][u] = 1.0
            else:
                pair = tuple(sorted([t, u]))
                corr[t][u] = base_corr.get(pair, 0.3)
    return weights, individual_vars, corr


@pytest.fixture
def diversified_20_positions():
    """20-stock diversified portfolio for concentration tests."""
    sectors = [
        "Technology", "Technology", "Technology", "Healthcare", "Healthcare",
        "Financials", "Financials", "Consumer Disc", "Consumer Disc", "Industrials",
        "Industrials", "Energy", "Energy", "Utilities", "Materials",
        "Real Estate", "Comm Services", "Consumer Staples", "Consumer Staples", "Technology",
    ]
    industries = [
        "Software", "Hardware", "Semiconductors", "Pharma", "Biotech",
        "Banks", "Insurance", "Retail", "Auto", "Aerospace",
        "Machinery", "Oil & Gas", "Renewable", "Electric", "Chemicals",
        "REIT", "Media", "Food", "Beverage", "Cloud",
    ]
    countries = [
        "US", "US", "US", "US", "CH",
        "US", "UK", "US", "DE", "US",
        "JP", "US", "DK", "US", "AU",
        "US", "US", "US", "UK", "US",
    ]
    positions = []
    for i in range(20):
        positions.append({
            "ticker": f"STOCK_{i:02d}",
            "weight": 0.05,  # equal weight 5% each
            "sector": sectors[i],
            "industry": industries[i],
            "country": countries[i],
            "market_value": 50000.0,
        })
    return positions


@pytest.fixture
def concentrated_3_positions():
    """Concentrated 3-stock portfolio."""
    return [
        {
            "ticker": "AAPL", "weight": 0.50, "sector": "Technology",
            "industry": "Hardware", "country": "US", "market_value": 500000.0,
        },
        {
            "ticker": "MSFT", "weight": 0.35, "sector": "Technology",
            "industry": "Software", "country": "US", "market_value": 350000.0,
        },
        {
            "ticker": "GOOGL", "weight": 0.15, "sector": "Technology",
            "industry": "Internet", "country": "US", "market_value": 150000.0,
        },
    ]


@pytest.fixture
def equity_positions_for_stress():
    """5-stock equity portfolio for stress testing."""
    return [
        {"ticker": "AAPL", "market_value": 200000, "asset_class": "equity", "beta": 1.1},
        {"ticker": "MSFT", "market_value": 180000, "asset_class": "equity", "beta": 1.0},
        {"ticker": "JPM", "market_value": 150000, "asset_class": "equity", "beta": 1.3},
        {"ticker": "JNJ", "market_value": 120000, "asset_class": "equity", "beta": 0.7},
        {"ticker": "XOM", "market_value": 100000, "asset_class": "equity", "beta": 0.9},
    ]


@pytest.fixture
def mixed_positions_for_stress():
    """Mixed equity + bond portfolio for stress testing."""
    return [
        {"ticker": "AAPL", "market_value": 200000, "asset_class": "equity", "beta": 1.1},
        {"ticker": "MSFT", "market_value": 150000, "asset_class": "equity", "beta": 1.0},
        {
            "ticker": "UST10Y", "market_value": 200000, "asset_class": "bond",
            "beta": 0.0, "duration": 8.5, "spread_duration": 0.0,
        },
        {
            "ticker": "IG_CORP", "market_value": 150000, "asset_class": "bond",
            "beta": 0.0, "duration": 6.0, "spread_duration": 5.0,
        },
        {
            "ticker": "HY_BOND", "market_value": 100000, "asset_class": "bond",
            "beta": 0.0, "duration": 4.0, "spread_duration": 3.5,
        },
    ]


@pytest.fixture
def value_tilt_positions():
    """Portfolio with intentional value tilt for factor tests."""
    return [
        {
            "ticker": "BRK.B", "weight": 0.20,
            "factor_exposures": {
                "value": 1.5, "growth": -0.8, "momentum": 0.2,
                "quality": 1.0, "size": -0.5, "low_vol": 0.3,
            },
        },
        {
            "ticker": "JPM", "weight": 0.20,
            "factor_exposures": {
                "value": 1.2, "growth": -0.5, "momentum": 0.1,
                "quality": 0.8, "size": -0.3, "low_vol": -0.2,
            },
        },
        {
            "ticker": "XOM", "weight": 0.20,
            "factor_exposures": {
                "value": 1.8, "growth": -1.0, "momentum": -0.3,
                "quality": 0.5, "size": -0.2, "low_vol": 0.1,
            },
        },
        {
            "ticker": "PG", "weight": 0.20,
            "factor_exposures": {
                "value": 0.5, "growth": 0.2, "momentum": 0.3,
                "quality": 1.2, "size": -0.4, "low_vol": 1.0,
            },
        },
        {
            "ticker": "JNJ", "weight": 0.20,
            "factor_exposures": {
                "value": 0.8, "growth": -0.3, "momentum": 0.0,
                "quality": 1.1, "size": -0.3, "low_vol": 0.8,
            },
        },
    ]


@pytest.fixture
def neutral_positions():
    """Near-neutral factor exposure portfolio."""
    return [
        {
            "ticker": "SPY", "weight": 1.0,
            "factor_exposures": {
                "value": 0.0, "growth": 0.0, "momentum": 0.0,
                "quality": 0.0, "size": 0.0, "low_vol": 0.0,
            },
        },
    ]


@pytest.fixture
def benchmark_positions():
    """S&P 500 style benchmark."""
    return [
        {
            "ticker": "SP500", "weight": 1.0,
            "factor_exposures": {
                "value": 0.0, "growth": 0.1, "momentum": 0.05,
                "quality": 0.1, "size": 0.0, "low_vol": 0.0,
            },
        },
    ]


# ══════════════════════════════════════════════════════════════════════
# VaR Tests
# ══════════════════════════════════════════════════════════════════════


class TestComputeUndiversifiedVar:
    """Tests for compute_undiversified_var."""

    def test_two_assets(self, two_asset_portfolio):
        weights, ind_vars, _ = two_asset_portfolio
        result = compute_undiversified_var(weights, ind_vars)
        # 0.60 * 0.02 + 0.40 * 0.015 = 0.012 + 0.006 = 0.018
        assert result == pytest.approx(0.018, abs=1e-6)

    def test_single_asset(self):
        weights = {"AAPL": 1.0}
        ind_vars = {"AAPL": 0.03}
        result = compute_undiversified_var(weights, ind_vars)
        assert result == pytest.approx(0.03, abs=1e-6)

    def test_empty_portfolio(self):
        assert compute_undiversified_var({}, {}) == 0.0

    def test_zero_var(self):
        weights = {"AAPL": 0.5, "CASH": 0.5}
        ind_vars = {"AAPL": 0.02, "CASH": 0.0}
        result = compute_undiversified_var(weights, ind_vars)
        assert result == pytest.approx(0.01, abs=1e-6)


class TestPortfolioVarFromWeights:
    """Tests for the internal _portfolio_var_from_weights via calculate_portfolio_var."""

    def test_two_asset_exact(self, two_asset_portfolio):
        """Verify 2-asset VaR against closed-form solution."""
        weights, ind_vars, corr = two_asset_portfolio
        # Variance = w_a^2*v_a^2 + w_b^2*v_b^2 + 2*w_a*w_b*v_a*v_b*rho
        # = 0.36*0.0004 + 0.16*0.000225 + 2*0.6*0.4*0.02*0.015*0.5
        # = 0.000144 + 0.000036 + 0.000072 = 0.000252
        # VaR = sqrt(0.000252) ≈ 0.015875
        expected = math.sqrt(0.36 * 0.0004 + 0.16 * 0.000225 + 2 * 0.6 * 0.4 * 0.02 * 0.015 * 0.5)
        result = calculate_portfolio_var(weights, ind_vars, corr, 1_000_000)
        assert result.var_1d_95 == pytest.approx(expected, abs=1e-6)

    def test_perfect_correlation_equals_undiversified(self):
        """With rho=1 everywhere, diversified VaR == undiversified VaR."""
        weights = {"A": 0.5, "B": 0.5}
        ind_vars = {"A": 0.02, "B": 0.03}
        corr = {"A": {"A": 1.0, "B": 1.0}, "B": {"B": 1.0, "A": 1.0}}
        result = calculate_portfolio_var(weights, ind_vars, corr, 1_000_000)
        undiverse = compute_undiversified_var(weights, ind_vars)
        assert result.var_1d_95 == pytest.approx(undiverse, abs=1e-6)

    def test_zero_correlation_reduces_var(self):
        """With rho=0, diversified VaR < undiversified VaR."""
        weights = {"A": 0.5, "B": 0.5}
        ind_vars = {"A": 0.02, "B": 0.02}
        corr = {"A": {"A": 1.0, "B": 0.0}, "B": {"B": 1.0, "A": 0.0}}
        result = calculate_portfolio_var(weights, ind_vars, corr, 1_000_000)
        undiverse = compute_undiversified_var(weights, ind_vars)
        assert result.var_1d_95 < undiverse

    def test_diversification_ratio_less_than_one(self, five_stock_portfolio):
        """Diversification ratio should be < 1 for imperfectly correlated assets."""
        weights, ind_vars, corr = five_stock_portfolio
        result = calculate_portfolio_var(weights, ind_vars, corr, 1_000_000)
        assert result.diversification_ratio < 1.0
        assert result.diversification_ratio > 0.0


class TestCalculatePortfolioVar:
    """Tests for calculate_portfolio_var (full VaR result)."""

    def test_scaling_99_from_95(self, two_asset_portfolio):
        """99% VaR is scaled from 95% by z-score ratio."""
        weights, ind_vars, corr = two_asset_portfolio
        result = calculate_portfolio_var(weights, ind_vars, corr, 1_000_000)
        expected_ratio = CONFIDENCE_LEVELS["99"] / CONFIDENCE_LEVELS["95"]
        assert result.var_1d_99 == pytest.approx(
            result.var_1d_95 * expected_ratio, abs=1e-6,
        )

    def test_scaling_10d_from_1d(self, two_asset_portfolio):
        """10-day VaR is scaled from 1-day by sqrt(10)."""
        weights, ind_vars, corr = two_asset_portfolio
        result = calculate_portfolio_var(weights, ind_vars, corr, 1_000_000)
        assert result.var_10d_95 == pytest.approx(
            result.var_1d_95 * math.sqrt(10), abs=1e-6,
        )
        assert result.var_10d_99 == pytest.approx(
            result.var_1d_99 * math.sqrt(10), abs=1e-6,
        )

    def test_nav_stored(self, two_asset_portfolio):
        weights, ind_vars, corr = two_asset_portfolio
        result = calculate_portfolio_var(weights, ind_vars, corr, 2_500_000)
        assert result.portfolio_nav == 2_500_000

    def test_result_type(self, two_asset_portfolio):
        weights, ind_vars, corr = two_asset_portfolio
        result = calculate_portfolio_var(weights, ind_vars, corr, 1_000_000)
        assert isinstance(result, VaRResult)

    def test_all_fields_populated(self, five_stock_portfolio):
        weights, ind_vars, corr = five_stock_portfolio
        result = calculate_portfolio_var(weights, ind_vars, corr, 1_000_000)
        assert result.var_1d_95 > 0
        assert result.var_1d_99 > result.var_1d_95
        assert result.var_10d_95 > result.var_1d_95
        assert len(result.marginal_var) == 5
        assert len(result.component_var) == 5
        assert len(result.incremental_var) == 5


class TestComponentVar:
    """Tests for compute_component_var."""

    def test_components_sum_to_portfolio_var(self, five_stock_portfolio):
        """Component VaRs should sum to total portfolio VaR."""
        weights, ind_vars, corr = five_stock_portfolio
        result = calculate_portfolio_var(weights, ind_vars, corr, 1_000_000)
        comp_sum = sum(result.component_var.values())
        assert comp_sum == pytest.approx(result.var_1d_95, abs=1e-6)

    def test_two_asset_component(self, two_asset_portfolio):
        weights, ind_vars, corr = two_asset_portfolio
        result = calculate_portfolio_var(weights, ind_vars, corr, 1_000_000)
        comp_sum = sum(result.component_var.values())
        assert comp_sum == pytest.approx(result.var_1d_95, abs=1e-6)

    def test_zero_var_asset(self):
        """Zero-VaR asset has zero component VaR."""
        weights = {"A": 0.5, "B": 0.5}
        ind_vars = {"A": 0.02, "B": 0.0}
        corr = {"A": {"A": 1.0, "B": 0.0}, "B": {"B": 1.0, "A": 0.0}}
        pvar = 0.01  # approximate
        from src.engines.portfolio_risk_engine import _portfolio_var_from_weights
        pvar = _portfolio_var_from_weights(weights, ind_vars, corr)
        comp = compute_component_var(weights, ind_vars, corr, pvar)
        assert comp["B"] == pytest.approx(0.0, abs=1e-8)


class TestMarginalVar:
    """Tests for compute_marginal_var."""

    def test_positive_marginal_for_risky_asset(self, five_stock_portfolio):
        """Increasing weight in a risky asset should increase VaR."""
        weights, ind_vars, corr = five_stock_portfolio
        result = calculate_portfolio_var(weights, ind_vars, corr, 1_000_000)
        # All marginal VaRs should be positive for long-only risky portfolio
        for t, mvar in result.marginal_var.items():
            assert mvar > 0, f"Marginal VaR for {t} should be positive"

    def test_higher_var_asset_has_higher_marginal(self, two_asset_portfolio):
        """Asset with higher individual VaR should have higher marginal VaR."""
        weights, ind_vars, corr = two_asset_portfolio
        result = calculate_portfolio_var(weights, ind_vars, corr, 1_000_000)
        # AAPL has VaR=0.02, MSFT has VaR=0.015
        assert result.marginal_var["AAPL"] > result.marginal_var["MSFT"]


class TestIncrementalVar:
    """Tests for compute_incremental_var."""

    def test_positive_incremental_for_correlated_assets(self, five_stock_portfolio):
        """Removing a correlated asset should reduce VaR (positive incremental)."""
        weights, ind_vars, corr = five_stock_portfolio
        result = calculate_portfolio_var(weights, ind_vars, corr, 1_000_000)
        # Most positions in a correlated portfolio add risk
        positive_count = sum(1 for v in result.incremental_var.values() if v > 0)
        assert positive_count >= 3, "Most positions should add risk"

    def test_single_asset_incremental(self):
        """Single-asset portfolio: incremental VaR = full VaR."""
        weights = {"AAPL": 1.0}
        ind_vars = {"AAPL": 0.02}
        corr = {"AAPL": {"AAPL": 1.0}}
        result = compute_incremental_var(weights, ind_vars, corr)
        from src.engines.portfolio_risk_engine import _portfolio_var_from_weights
        full_var = _portfolio_var_from_weights(weights, ind_vars, corr)
        assert result["AAPL"] == pytest.approx(full_var, abs=1e-6)


# ══════════════════════════════════════════════════════════════════════
# Concentration Tests
# ══════════════════════════════════════════════════════════════════════


class TestComputeHHI:
    """Tests for compute_hhi."""

    def test_equal_weight_20(self):
        """20 equal-weight positions → HHI = 20 * (0.05)^2 * 10000 = 500."""
        weights = [0.05] * 20
        assert compute_hhi(weights) == pytest.approx(500.0, abs=0.1)

    def test_single_position(self):
        """One position at 100% → HHI = 10000."""
        assert compute_hhi([1.0]) == pytest.approx(10000.0, abs=0.1)

    def test_two_equal(self):
        """Two equal positions → HHI = 2 * 0.25 * 10000 = 5000."""
        assert compute_hhi([0.5, 0.5]) == pytest.approx(5000.0, abs=0.1)

    def test_empty(self):
        assert compute_hhi([]) == 0.0

    def test_three_unequal(self):
        """60/30/10 → HHI = (0.36 + 0.09 + 0.01) * 10000 = 4600."""
        assert compute_hhi([0.6, 0.3, 0.1]) == pytest.approx(4600.0, abs=0.1)

    def test_ten_equal(self):
        """10 equal → HHI = 10 * 0.01 * 10000 = 1000."""
        assert compute_hhi([0.1] * 10) == pytest.approx(1000.0, abs=0.1)


class TestClassifyConcentration:
    """Tests for classify_concentration."""

    def test_diversified(self):
        assert classify_concentration(400) == "DIVERSIFIED"

    def test_moderate(self):
        assert classify_concentration(800) == "MODERATE"

    def test_concentrated(self):
        assert classify_concentration(2000) == "CONCENTRATED"

    def test_boundary_diversified(self):
        assert classify_concentration(499) == "DIVERSIFIED"

    def test_boundary_moderate_low(self):
        assert classify_concentration(500) == "MODERATE"

    def test_boundary_moderate_high(self):
        assert classify_concentration(1500) == "MODERATE"

    def test_boundary_concentrated(self):
        assert classify_concentration(1501) == "CONCENTRATED"


class TestAnalyzeConcentration:
    """Tests for analyze_concentration."""

    def test_diversified_portfolio(self, diversified_20_positions):
        result = analyze_concentration(diversified_20_positions)
        assert isinstance(result, ConcentrationResult)
        assert result.hhi_position == pytest.approx(500.0, abs=1.0)
        assert result.classification == "MODERATE"  # 500 is boundary
        assert result.largest_position_weight == pytest.approx(0.05, abs=0.001)
        assert result.top_5_weight == pytest.approx(0.25, abs=0.001)
        assert result.top_10_weight == pytest.approx(0.50, abs=0.001)
        assert result.effective_num_positions == pytest.approx(20.0, abs=0.5)

    def test_concentrated_portfolio(self, concentrated_3_positions):
        result = analyze_concentration(concentrated_3_positions)
        assert result.classification == "CONCENTRATED"
        assert result.hhi_position > 1500
        assert result.largest_position_weight == pytest.approx(0.50, abs=0.001)
        assert "Single position exceeds 20%" in result.flags[0]
        assert any("Very few positions" in f for f in result.flags)

    def test_sector_concentration(self, concentrated_3_positions):
        """All 3 positions in Technology → sector HHI = 10000."""
        result = analyze_concentration(concentrated_3_positions)
        assert result.hhi_sector == pytest.approx(10000.0, abs=1.0)
        assert any("Sector HHI" in f for f in result.flags)
        assert any("Sector(s) over 40%" in f for f in result.flags)

    def test_sector_detail_sorted(self, diversified_20_positions):
        result = analyze_concentration(diversified_20_positions)
        # Sector detail should be sorted by weight descending
        for i in range(len(result.sector_detail) - 1):
            assert result.sector_detail[i]["weight"] >= result.sector_detail[i + 1]["weight"]

    def test_geographic_detail(self, diversified_20_positions):
        result = analyze_concentration(diversified_20_positions)
        assert len(result.geographic_detail) > 0
        # US should be the largest
        assert result.geographic_detail[0]["country"] == "US"

    def test_empty_portfolio(self):
        result = analyze_concentration([])
        assert result.hhi_position == 0.0
        assert result.classification == "DIVERSIFIED"
        assert result.effective_num_positions == 0.0

    def test_flags_top_5_concentration(self):
        """Portfolio where top 5 exceed 60%."""
        positions = [
            {"ticker": f"S{i}", "weight": w, "sector": "Tech", "industry": "SW", "country": "US"}
            for i, w in enumerate([0.25, 0.20, 0.15, 0.10, 0.10, 0.05, 0.05, 0.05, 0.05])
        ]
        result = analyze_concentration(positions)
        assert result.top_5_weight == pytest.approx(0.80, abs=0.001)
        assert any("Top 5" in f for f in result.flags)

    def test_industry_detail(self, diversified_20_positions):
        result = analyze_concentration(diversified_20_positions)
        assert len(result.industry_detail) == 20  # all unique industries


# ══════════════════════════════════════════════════════════════════════
# Factor Exposure Tests
# ══════════════════════════════════════════════════════════════════════


class TestComputeFactorExposures:
    """Tests for compute_factor_exposures."""

    def test_value_tilt_detected(self, value_tilt_positions, benchmark_positions):
        result = compute_factor_exposures(value_tilt_positions, benchmark_positions)
        assert isinstance(result, FactorExposureResult)
        # Portfolio should have strong value exposure
        assert result.portfolio_exposures["value"] > 0.5
        # Active value exposure should be positive
        assert result.active_exposures["value"] > 0.5
        # Should flag value as unintended if threshold exceeded
        factor_flags = [f["factor"] for f in result.unintended_flags]
        assert "value" in factor_flags

    def test_neutral_portfolio(self, neutral_positions, benchmark_positions):
        """Near-neutral portfolio should have small active exposures."""
        result = compute_factor_exposures(neutral_positions, benchmark_positions)
        for factor in FACTORS:
            assert abs(result.active_exposures[factor]) < 0.2

    def test_no_benchmark(self, value_tilt_positions):
        """Without benchmark, active exposures equal portfolio exposures."""
        result = compute_factor_exposures(value_tilt_positions)
        for factor in FACTORS:
            assert result.active_exposures[factor] == pytest.approx(
                result.portfolio_exposures[factor], abs=1e-6,
            )
            assert result.benchmark_exposures[factor] == 0.0

    def test_all_factors_present(self, value_tilt_positions):
        result = compute_factor_exposures(value_tilt_positions)
        for factor in FACTORS:
            assert factor in result.portfolio_exposures
            assert factor in result.benchmark_exposures
            assert factor in result.active_exposures
            assert factor in result.factor_contributions

    def test_weighted_average_correct(self, value_tilt_positions):
        """Verify factor exposures are weighted averages."""
        result = compute_factor_exposures(value_tilt_positions)
        expected_value = sum(
            p["weight"] * p["factor_exposures"]["value"]
            for p in value_tilt_positions
        )
        assert result.portfolio_exposures["value"] == pytest.approx(
            expected_value, abs=1e-6,
        )

    def test_unintended_flag_severity(self, value_tilt_positions, benchmark_positions):
        """Large active exposures should be flagged with correct severity."""
        result = compute_factor_exposures(value_tilt_positions, benchmark_positions)
        for flag in result.unintended_flags:
            if abs(flag["active_exposure"]) > 1.0:
                assert flag["severity"] == "HIGH"
            elif abs(flag["active_exposure"]) > 0.5:
                assert flag["severity"] in ("MEDIUM", "HIGH")

    def test_historical_drift_detection(self, value_tilt_positions):
        """Detect drift from historical mean."""
        # Historical exposures with low value tilt
        historical = [
            {"date": "2024-01-01", "exposures": {"value": 0.2, "growth": 0.0, "momentum": 0.0, "quality": 0.0, "size": 0.0, "low_vol": 0.0}},
            {"date": "2024-02-01", "exposures": {"value": 0.3, "growth": 0.0, "momentum": 0.0, "quality": 0.0, "size": 0.0, "low_vol": 0.0}},
            {"date": "2024-03-01", "exposures": {"value": 0.25, "growth": 0.0, "momentum": 0.0, "quality": 0.0, "size": 0.0, "low_vol": 0.0}},
        ]
        result = compute_factor_exposures(value_tilt_positions, historical_exposures=historical)
        # Current value exposure ~1.16 vs historical mean ~0.25 → should drift
        drift_flags = [f for f in result.unintended_flags if f["severity"] == "DRIFT"]
        assert len(drift_flags) > 0
        drift_factors = [f["factor"] for f in drift_flags]
        assert "value" in drift_factors


# ══════════════════════════════════════════════════════════════════════
# Stress Test Tests
# ══════════════════════════════════════════════════════════════════════


class TestRunStressTest:
    """Tests for run_stress_test."""

    def test_gfc_2008(self, equity_positions_for_stress):
        nav = sum(p["market_value"] for p in equity_positions_for_stress)
        result = run_stress_test(equity_positions_for_stress, "GFC_2008", nav)
        assert isinstance(result, StressTestResult)
        assert result.scenario_name == "GFC_2008"
        assert result.scenario_type == "historical"
        assert result.total_pnl_dollar < 0  # should lose money
        assert result.total_pnl_percent < 0
        assert result.recovery_time_months == 48

    def test_covid_2020(self, equity_positions_for_stress):
        nav = sum(p["market_value"] for p in equity_positions_for_stress)
        result = run_stress_test(equity_positions_for_stress, "COVID_2020", nav)
        assert result.total_pnl_dollar < 0
        assert result.recovery_time_months == 5

    def test_rate_shock_2022(self, mixed_positions_for_stress):
        nav = sum(p["market_value"] for p in mixed_positions_for_stress)
        result = run_stress_test(mixed_positions_for_stress, "RATE_SHOCK_2022", nav)
        assert result.total_pnl_dollar < 0
        # Bonds should lose in a rate shock
        assert result.per_position_pnl["UST10Y"]["pnl_dollar"] < 0

    def test_dotcom_2000(self, equity_positions_for_stress):
        nav = sum(p["market_value"] for p in equity_positions_for_stress)
        result = run_stress_test(equity_positions_for_stress, "DOTCOM_2000", nav)
        assert result.total_pnl_dollar < 0
        assert result.recovery_time_months == 30

    def test_all_four_scenarios(self, equity_positions_for_stress):
        """All 4 historical scenarios should run without error."""
        nav = sum(p["market_value"] for p in equity_positions_for_stress)
        for scenario in HISTORICAL_SCENARIOS:
            result = run_stress_test(equity_positions_for_stress, scenario, nav)
            assert result.total_pnl_dollar < 0
            assert len(result.worst_positions) <= 5

    def test_unknown_scenario_raises(self, equity_positions_for_stress):
        with pytest.raises(ValueError, match="Unknown scenario"):
            run_stress_test(equity_positions_for_stress, "FAKE_SCENARIO", 1_000_000)

    def test_worst_positions_ordering(self, equity_positions_for_stress):
        """Worst positions should be sorted by PnL ascending (most negative first)."""
        nav = sum(p["market_value"] for p in equity_positions_for_stress)
        result = run_stress_test(equity_positions_for_stress, "GFC_2008", nav)
        for i in range(len(result.worst_positions) - 1):
            assert (
                result.worst_positions[i]["pnl_dollar"]
                <= result.worst_positions[i + 1]["pnl_dollar"]
            )

    def test_per_position_pnl_all_tickers(self, equity_positions_for_stress):
        nav = sum(p["market_value"] for p in equity_positions_for_stress)
        result = run_stress_test(equity_positions_for_stress, "GFC_2008", nav)
        for p in equity_positions_for_stress:
            assert p["ticker"] in result.per_position_pnl

    def test_custom_params_override(self, equity_positions_for_stress):
        """Custom params should override scenario defaults."""
        nav = sum(p["market_value"] for p in equity_positions_for_stress)
        # GFC with milder equity shock
        result = run_stress_test(
            equity_positions_for_stress, "GFC_2008", nav,
            custom_params={"equity_shock": -0.10},
        )
        # Should lose less than default -55%
        assert result.total_pnl_percent > -0.15

    def test_beta_sensitivity(self, equity_positions_for_stress):
        """Higher beta positions should lose more in equity crash."""
        nav = sum(p["market_value"] for p in equity_positions_for_stress)
        result = run_stress_test(equity_positions_for_stress, "GFC_2008", nav)
        # JPM (beta=1.3) should lose more % than JNJ (beta=0.7)
        assert (
            result.per_position_pnl["JPM"]["pnl_pct"]
            < result.per_position_pnl["JNJ"]["pnl_pct"]
        )

    def test_mixed_portfolio_bond_rate_impact(self, mixed_positions_for_stress):
        """Bonds should react to rate shocks based on duration."""
        nav = sum(p["market_value"] for p in mixed_positions_for_stress)
        result = run_stress_test(mixed_positions_for_stress, "RATE_SHOCK_2022", nav)
        # UST10Y (duration=8.5) should lose more than HY_BOND (duration=4.0)
        # in rate shock scenario (+300 bps)
        # UST10Y pnl = -8.5 * 0.03 = -25.5%
        ust_pnl = result.per_position_pnl["UST10Y"]["pnl_pct"]
        assert ust_pnl == pytest.approx(-8.5 * 300 / 10000, abs=0.01)

    def test_mixed_portfolio_spread_impact(self, mixed_positions_for_stress):
        """Credit bonds should be affected by spread widening."""
        nav = sum(p["market_value"] for p in mixed_positions_for_stress)
        # COVID had +350bp spread widening
        result = run_stress_test(mixed_positions_for_stress, "COVID_2020", nav)
        # IG_CORP: -6.0*(-0.015) - 5.0*(0.035) = 0.09 - 0.175 = -0.085
        ig_pnl = result.per_position_pnl["IG_CORP"]["pnl_pct"]
        expected = -6.0 * (-150 / 10000) - 5.0 * (350 / 10000)
        assert ig_pnl == pytest.approx(expected, abs=0.01)


class TestRunHypotheticalStress:
    """Tests for run_hypothetical_stress."""

    def test_basic_hypothetical(self, equity_positions_for_stress):
        nav = sum(p["market_value"] for p in equity_positions_for_stress)
        result = run_hypothetical_stress(
            equity_positions_for_stress,
            equity_shock=-0.30,
            rate_shock_bps=200,
            spread_shock_bps=150,
            portfolio_nav=nav,
        )
        assert isinstance(result, StressTestResult)
        assert result.scenario_name == "HYPOTHETICAL"
        assert result.scenario_type == "hypothetical"
        assert result.total_pnl_dollar < 0

    def test_zero_shock(self, equity_positions_for_stress):
        """Zero shocks → no PnL impact."""
        nav = sum(p["market_value"] for p in equity_positions_for_stress)
        result = run_hypothetical_stress(
            equity_positions_for_stress, 0.0, 0.0, 0.0, nav,
        )
        assert result.total_pnl_dollar == pytest.approx(0.0, abs=0.01)
        assert result.total_pnl_percent == pytest.approx(0.0, abs=0.0001)

    def test_recovery_estimate_proportional(self, equity_positions_for_stress):
        """Larger shocks should estimate longer recovery."""
        nav = sum(p["market_value"] for p in equity_positions_for_stress)
        mild = run_hypothetical_stress(
            equity_positions_for_stress, -0.10, 0, 0, nav,
        )
        severe = run_hypothetical_stress(
            equity_positions_for_stress, -0.50, 0, 0, nav,
        )
        assert severe.recovery_time_months > mild.recovery_time_months

    def test_positive_shock(self, equity_positions_for_stress):
        """Positive equity shock should generate gains."""
        nav = sum(p["market_value"] for p in equity_positions_for_stress)
        result = run_hypothetical_stress(
            equity_positions_for_stress, 0.10, 0, 0, nav,
        )
        assert result.total_pnl_dollar > 0


class TestGetAvailableScenarios:
    """Tests for get_available_scenarios."""

    def test_returns_all_four(self):
        scenarios = get_available_scenarios()
        assert len(scenarios) == 4

    def test_scenario_structure(self):
        scenarios = get_available_scenarios()
        for s in scenarios:
            assert "name" in s
            assert "label" in s
            assert "equity_shock" in s
            assert "rate_shock_bps" in s
            assert "spread_shock_bps" in s
            assert "recovery_months" in s

    def test_known_names(self):
        scenarios = get_available_scenarios()
        names = {s["name"] for s in scenarios}
        assert names == {"GFC_2008", "COVID_2020", "RATE_SHOCK_2022", "DOTCOM_2000"}

    def test_all_shocks_negative(self):
        """All historical scenarios should have negative equity shocks."""
        for s in get_available_scenarios():
            assert s["equity_shock"] < 0


# ══════════════════════════════════════════════════════════════════════
# Integration: Full Risk Dashboard
# ══════════════════════════════════════════════════════════════════════


class TestIntegrationRiskDashboard:
    """Integration test combining VaR + concentration + factor + stress."""

    def test_full_risk_dashboard(self):
        """Run a complete risk assessment on a realistic portfolio."""
        # 7-stock portfolio
        positions = [
            {"ticker": "AAPL", "weight": 0.20, "market_value": 200000, "sector": "Technology", "industry": "Hardware", "country": "US", "asset_class": "equity", "beta": 1.1,
             "factor_exposures": {"value": -0.3, "growth": 1.2, "momentum": 0.5, "quality": 0.8, "size": -0.2, "low_vol": -0.5}},
            {"ticker": "MSFT", "weight": 0.15, "market_value": 150000, "sector": "Technology", "industry": "Software", "country": "US", "asset_class": "equity", "beta": 1.0,
             "factor_exposures": {"value": -0.1, "growth": 0.9, "momentum": 0.3, "quality": 1.0, "size": -0.3, "low_vol": -0.3}},
            {"ticker": "JPM", "weight": 0.15, "market_value": 150000, "sector": "Financials", "industry": "Banks", "country": "US", "asset_class": "equity", "beta": 1.3,
             "factor_exposures": {"value": 1.0, "growth": -0.5, "momentum": 0.1, "quality": 0.6, "size": -0.1, "low_vol": -0.8}},
            {"ticker": "JNJ", "weight": 0.15, "market_value": 150000, "sector": "Healthcare", "industry": "Pharma", "country": "US", "asset_class": "equity", "beta": 0.7,
             "factor_exposures": {"value": 0.3, "growth": -0.2, "momentum": -0.1, "quality": 1.1, "size": -0.2, "low_vol": 1.0}},
            {"ticker": "XOM", "weight": 0.10, "market_value": 100000, "sector": "Energy", "industry": "Oil & Gas", "country": "US", "asset_class": "equity", "beta": 0.9,
             "factor_exposures": {"value": 1.5, "growth": -1.0, "momentum": -0.3, "quality": 0.5, "size": -0.1, "low_vol": 0.2}},
            {"ticker": "NESN", "weight": 0.10, "market_value": 100000, "sector": "Consumer Staples", "industry": "Food", "country": "CH", "asset_class": "equity", "beta": 0.6,
             "factor_exposures": {"value": 0.2, "growth": 0.1, "momentum": 0.2, "quality": 0.9, "size": -0.3, "low_vol": 0.8}},
            {"ticker": "TSLA", "weight": 0.15, "market_value": 150000, "sector": "Consumer Disc", "industry": "Auto", "country": "US", "asset_class": "equity", "beta": 1.8,
             "factor_exposures": {"value": -1.5, "growth": 2.0, "momentum": 1.0, "quality": -0.5, "size": 0.1, "low_vol": -1.5}},
        ]

        nav = 1_000_000
        weights = {p["ticker"]: p["weight"] for p in positions}
        individual_vars = {
            "AAPL": 0.020, "MSFT": 0.018, "JPM": 0.025,
            "JNJ": 0.012, "XOM": 0.022, "NESN": 0.010, "TSLA": 0.040,
        }
        corr_base = 0.4
        corr = {}
        for t in weights:
            corr[t] = {}
            for u in weights:
                corr[t][u] = 1.0 if t == u else corr_base

        # 1. VaR
        var_result = calculate_portfolio_var(weights, individual_vars, corr, nav)
        assert var_result.var_1d_95 > 0
        assert var_result.diversification_ratio < 1.0
        comp_sum = sum(var_result.component_var.values())
        assert comp_sum == pytest.approx(var_result.var_1d_95, abs=1e-5)

        # 2. Concentration
        conc = analyze_concentration(positions)
        assert conc.classification in ("DIVERSIFIED", "MODERATE", "CONCENTRATED")
        assert conc.effective_num_positions > 5
        assert len(conc.sector_detail) > 1

        # 3. Factor exposures
        benchmark = [
            {"ticker": "SP500", "weight": 1.0,
             "factor_exposures": {"value": 0.0, "growth": 0.1, "momentum": 0.0, "quality": 0.1, "size": 0.0, "low_vol": 0.0}},
        ]
        factors = compute_factor_exposures(positions, benchmark)
        assert len(factors.portfolio_exposures) == 6

        # 4. Stress test all scenarios
        for scenario in HISTORICAL_SCENARIOS:
            stress = run_stress_test(positions, scenario, nav)
            assert stress.total_pnl_dollar < 0
            assert len(stress.worst_positions) <= 5

        # 5. Hypothetical stress
        hypo = run_hypothetical_stress(positions, -0.20, 100, 50, nav)
        assert hypo.scenario_type == "hypothetical"
        assert hypo.total_pnl_dollar < 0
