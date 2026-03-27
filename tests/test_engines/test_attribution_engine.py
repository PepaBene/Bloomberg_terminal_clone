"""Tests for Pillar 4 Phase 2 — Attribution Engine."""

import pytest

from src.engines.attribution_engine import (
    BrinsonResult,
    FactorAttribution,
    FactorResult,
    SectorAttribution,
    SecurityContribution,
    compute_allocation_effect,
    compute_bottom_contributors,
    compute_brinson_attribution,
    compute_factor_attribution,
    compute_interaction_effect,
    compute_sector_returns,
    compute_sector_weights,
    compute_security_contribution,
    compute_selection_effect,
    compute_stock_specific_return,
    compute_top_contributors,
    link_multi_period_attribution,
)


# ── TestSectorWeights ──────────────────────────────────────────────────


class TestSectorWeights:
    """Tests for compute_sector_weights."""

    def test_basic_weights(self):
        """Three sectors with known values."""
        positions = [
            {"sector": "Tech", "market_value": 50000},
            {"sector": "Tech", "market_value": 30000},
            {"sector": "Health", "market_value": 20000},
        ]
        weights = compute_sector_weights(positions, 100000.0)
        assert weights["Tech"] == pytest.approx(0.80, abs=0.01)
        assert weights["Health"] == pytest.approx(0.20, abs=0.01)

    def test_single_sector(self):
        """One sector → weight = 1.0."""
        positions = [
            {"sector": "Energy", "market_value": 100000},
        ]
        weights = compute_sector_weights(positions, 100000.0)
        assert weights["Energy"] == pytest.approx(1.0, abs=0.001)

    def test_zero_total(self):
        """Zero total value → empty dict."""
        positions = [{"sector": "Tech", "market_value": 1000}]
        assert compute_sector_weights(positions, 0.0) == {}

    def test_multiple_sectors(self):
        """Four sectors sum to ~1.0."""
        positions = [
            {"sector": "Tech", "market_value": 25000},
            {"sector": "Health", "market_value": 25000},
            {"sector": "Finance", "market_value": 25000},
            {"sector": "Energy", "market_value": 25000},
        ]
        weights = compute_sector_weights(positions, 100000.0)
        assert sum(weights.values()) == pytest.approx(1.0, abs=0.001)


# ── TestSectorReturns ──────────────────────────────────────────────────


class TestSectorReturns:
    """Tests for compute_sector_returns."""

    def test_weighted_avg_return(self):
        """Two positions in same sector → weighted average."""
        positions = [
            {"sector": "Tech", "market_value": 60000, "return": 0.10},
            {"sector": "Tech", "market_value": 40000, "return": 0.05},
        ]
        returns = compute_sector_returns(positions)
        # (60000*0.10 + 40000*0.05) / 100000 = 0.08
        assert returns["Tech"] == pytest.approx(0.08, abs=0.001)

    def test_single_position_sector(self):
        """Single position per sector → same return."""
        positions = [
            {"sector": "Health", "market_value": 50000, "return": 0.12},
        ]
        returns = compute_sector_returns(positions)
        assert returns["Health"] == pytest.approx(0.12, abs=0.001)

    def test_multiple_sectors(self):
        """Each sector gets its own return."""
        positions = [
            {"sector": "Tech", "market_value": 50000, "return": 0.10},
            {"sector": "Health", "market_value": 50000, "return": -0.05},
        ]
        returns = compute_sector_returns(positions)
        assert returns["Tech"] > 0
        assert returns["Health"] < 0


# ── TestAllocationEffect ───────────────────────────────────────────────


class TestAllocationEffect:
    """Tests for compute_allocation_effect."""

    def test_overweight_outperforming(self):
        """Overweight in sector that outperforms → positive allocation."""
        # wp=0.30, wb=0.20, rb_s=0.10, rb=0.05
        alloc = compute_allocation_effect(0.30, 0.20, 0.10, 0.05)
        # (0.30 - 0.20) * (0.10 - 0.05) = 0.005
        assert alloc == pytest.approx(0.005, abs=0.001)

    def test_underweight_outperforming(self):
        """Underweight in outperforming sector → negative allocation."""
        alloc = compute_allocation_effect(0.10, 0.20, 0.10, 0.05)
        assert alloc < 0

    def test_equal_weight(self):
        """Equal weight → zero allocation effect."""
        alloc = compute_allocation_effect(0.25, 0.25, 0.10, 0.05)
        assert alloc == pytest.approx(0.0, abs=0.001)


# ── TestSelectionEffect ────────────────────────────────────────────────


class TestSelectionEffect:
    """Tests for compute_selection_effect."""

    def test_positive_selection(self):
        """Portfolio sector beats benchmark sector → positive selection."""
        # wb=0.25, rp_s=0.12, rb_s=0.08
        select = compute_selection_effect(0.25, 0.12, 0.08)
        # 0.25 * (0.12 - 0.08) = 0.01
        assert select == pytest.approx(0.01, abs=0.001)

    def test_negative_selection(self):
        """Portfolio sector underperforms → negative selection."""
        select = compute_selection_effect(0.25, 0.05, 0.08)
        assert select < 0

    def test_zero_weight(self):
        """Zero benchmark weight → zero selection."""
        assert compute_selection_effect(0.0, 0.12, 0.08) == 0.0


# ── TestInteractionEffect ─────────────────────────────────────────────


class TestInteractionEffect:
    """Tests for compute_interaction_effect."""

    def test_overweight_outperform(self):
        """Overweight + outperform → positive interaction."""
        interact = compute_interaction_effect(0.30, 0.20, 0.12, 0.08)
        # (0.30 - 0.20) * (0.12 - 0.08) = 0.004
        assert interact == pytest.approx(0.004, abs=0.001)

    def test_overweight_underperform(self):
        """Overweight + underperform → negative interaction."""
        interact = compute_interaction_effect(0.30, 0.20, 0.05, 0.08)
        assert interact < 0

    def test_equal_weight(self):
        """Equal weights → zero interaction."""
        interact = compute_interaction_effect(0.25, 0.25, 0.12, 0.08)
        assert interact == pytest.approx(0.0, abs=0.001)


# ── TestBrinsonAttribution ─────────────────────────────────────────────


class TestBrinsonAttribution:
    """Tests for compute_brinson_attribution."""

    def _standard_sectors(self):
        """Standard 3-sector test case."""
        port = [
            {"sector": "Tech", "weight": 0.40, "return": 0.12},
            {"sector": "Health", "weight": 0.35, "return": 0.08},
            {"sector": "Finance", "weight": 0.25, "return": 0.05},
        ]
        bench = [
            {"sector": "Tech", "weight": 0.30, "return": 0.10},
            {"sector": "Health", "weight": 0.40, "return": 0.06},
            {"sector": "Finance", "weight": 0.30, "return": 0.04},
        ]
        total_bench = sum(s["weight"] * s["return"] for s in bench)
        return port, bench, total_bench

    def test_basic_attribution(self):
        """Full Brinson returns valid result."""
        port, bench, total_bench = self._standard_sectors()
        result = compute_brinson_attribution(port, bench, total_bench)
        assert isinstance(result, BrinsonResult)
        assert len(result.sector_detail) == 3

    def test_active_return_decomposition(self):
        """Active return ≈ allocation + selection + interaction + residual."""
        port, bench, total_bench = self._standard_sectors()
        result = compute_brinson_attribution(port, bench, total_bench)
        decomposed = (
            result.total_allocation
            + result.total_selection
            + result.total_interaction
            + result.residual
        )
        assert decomposed == pytest.approx(result.total_active_return, abs=0.0001)

    def test_zero_active(self):
        """Same portfolio and benchmark → zero active."""
        sectors = [
            {"sector": "Tech", "weight": 0.50, "return": 0.10},
            {"sector": "Health", "weight": 0.50, "return": 0.05},
        ]
        total = 0.50 * 0.10 + 0.50 * 0.05
        result = compute_brinson_attribution(sectors, sectors, total)
        assert result.total_active_return == pytest.approx(0.0, abs=0.0001)
        assert result.total_allocation == pytest.approx(0.0, abs=0.0001)
        assert result.total_selection == pytest.approx(0.0, abs=0.0001)

    def test_sector_only_in_portfolio(self):
        """Sector present in portfolio but not benchmark."""
        port = [
            {"sector": "Tech", "weight": 0.50, "return": 0.10},
            {"sector": "Crypto", "weight": 0.50, "return": 0.20},
        ]
        bench = [
            {"sector": "Tech", "weight": 1.00, "return": 0.10},
        ]
        total_bench = 0.10
        result = compute_brinson_attribution(port, bench, total_bench)
        sectors = {s.sector for s in result.sector_detail}
        assert "Crypto" in sectors

    def test_sector_detail_weights(self):
        """Sector details carry correct weights."""
        port, bench, total_bench = self._standard_sectors()
        result = compute_brinson_attribution(port, bench, total_bench)
        tech = next(s for s in result.sector_detail if s.sector == "Tech")
        assert tech.portfolio_weight == 0.40
        assert tech.benchmark_weight == 0.30


# ── TestSecurityContribution ──────────────────────────────────────────


class TestSecurityContribution:
    """Tests for compute_security_contribution."""

    def test_basic_contributions(self):
        """Contribution = weight * return."""
        positions = [
            {"ticker": "AAPL", "weight": 0.20, "return": 0.05},
            {"ticker": "MSFT", "weight": 0.15, "return": -0.02},
            {"ticker": "JNJ", "weight": 0.10, "return": 0.03},
        ]
        contribs = compute_security_contribution(positions)
        assert len(contribs) == 3
        assert contribs[0].contribution == pytest.approx(0.01, abs=0.001)
        assert contribs[1].contribution == pytest.approx(-0.003, abs=0.001)

    def test_zero_weight(self):
        """Zero weight → zero contribution."""
        positions = [{"ticker": "XYZ", "weight": 0.0, "return": 0.10}]
        contribs = compute_security_contribution(positions)
        assert contribs[0].contribution == 0.0

    def test_empty(self):
        """Empty positions → empty list."""
        assert compute_security_contribution([]) == []


# ── TestTopBottomContributors ──────────────────────────────────────────


class TestTopBottomContributors:
    """Tests for compute_top_contributors and compute_bottom_contributors."""

    def _make_contributions(self) -> list[SecurityContribution]:
        positions = [
            {"ticker": "AAPL", "weight": 0.20, "return": 0.05},
            {"ticker": "MSFT", "weight": 0.15, "return": 0.08},
            {"ticker": "JNJ", "weight": 0.10, "return": -0.03},
            {"ticker": "JPM", "weight": 0.12, "return": 0.02},
            {"ticker": "META", "weight": 0.18, "return": -0.04},
            {"ticker": "GOOG", "weight": 0.25, "return": 0.06},
        ]
        return compute_security_contribution(positions)

    def test_top_5(self):
        """Top 5 sorted by contribution descending."""
        contribs = self._make_contributions()
        top = compute_top_contributors(contribs, n=5)
        assert len(top) == 5
        # First should have highest contribution
        assert top[0].contribution >= top[1].contribution

    def test_bottom_5(self):
        """Bottom 5 sorted by contribution ascending."""
        contribs = self._make_contributions()
        bottom = compute_bottom_contributors(contribs, n=5)
        assert len(bottom) == 5
        assert bottom[0].contribution <= bottom[1].contribution

    def test_top_3(self):
        """Top 3 limits correctly."""
        contribs = self._make_contributions()
        top = compute_top_contributors(contribs, n=3)
        assert len(top) == 3

    def test_n_larger_than_list(self):
        """N > list size returns all."""
        contribs = self._make_contributions()
        top = compute_top_contributors(contribs, n=20)
        assert len(top) == 6


# ── TestFactorAttribution ─────────────────────────────────────────────


class TestFactorAttribution:
    """Tests for compute_factor_attribution."""

    def test_basic_factors(self):
        """Standard factor attribution."""
        port_exp = {"value": 0.5, "momentum": 0.3, "quality": 0.2}
        bench_exp = {"value": 0.3, "momentum": 0.4, "quality": 0.3}
        factor_ret = {"value": 0.05, "momentum": 0.03, "quality": 0.02}
        result = compute_factor_attribution(port_exp, bench_exp, factor_ret)
        assert isinstance(result, FactorResult)
        assert len(result.factors) == 3

    def test_factor_contribution(self):
        """Factor contribution = active_exposure * factor_return."""
        port_exp = {"value": 0.5}
        bench_exp = {"value": 0.3}
        factor_ret = {"value": 0.05}
        result = compute_factor_attribution(port_exp, bench_exp, factor_ret)
        # active_exp = 0.2, factor_ret = 0.05, contrib = 0.01
        assert result.factors[0].contribution == pytest.approx(0.01, abs=0.001)
        assert result.total_factor_return == pytest.approx(0.01, abs=0.001)

    def test_zero_exposure(self):
        """Zero active exposure → zero contribution."""
        port_exp = {"value": 0.3}
        bench_exp = {"value": 0.3}
        factor_ret = {"value": 0.10}
        result = compute_factor_attribution(port_exp, bench_exp, factor_ret)
        assert result.factors[0].contribution == pytest.approx(0.0, abs=0.001)

    def test_negative_active(self):
        """Negative active exposure with positive factor return → negative."""
        port_exp = {"momentum": 0.1}
        bench_exp = {"momentum": 0.4}
        factor_ret = {"momentum": 0.05}
        result = compute_factor_attribution(port_exp, bench_exp, factor_ret)
        assert result.factors[0].contribution < 0

    def test_missing_factor_return(self):
        """Factor with no return is excluded."""
        port_exp = {"value": 0.5, "growth": 0.3}
        bench_exp = {"value": 0.3, "growth": 0.2}
        factor_ret = {"value": 0.05}  # no growth return
        result = compute_factor_attribution(port_exp, bench_exp, factor_ret)
        factor_names = [f.factor for f in result.factors]
        assert "growth" not in factor_names


# ── TestStockSpecificReturn ────────────────────────────────────────────


class TestStockSpecificReturn:
    """Tests for compute_stock_specific_return."""

    def test_positive_stock_specific(self):
        """Active > factor → positive stock-specific."""
        ss = compute_stock_specific_return(0.05, 0.02)
        assert ss == pytest.approx(0.03, abs=0.001)

    def test_negative_stock_specific(self):
        """Active < factor → negative stock-specific."""
        ss = compute_stock_specific_return(0.01, 0.03)
        assert ss == pytest.approx(-0.02, abs=0.001)

    def test_zero(self):
        """Equal → zero."""
        assert compute_stock_specific_return(0.05, 0.05) == pytest.approx(0.0, abs=0.001)


# ── TestMultiPeriodLinking ─────────────────────────────────────────────


class TestMultiPeriodLinking:
    """Tests for link_multi_period_attribution."""

    def _make_period_result(
        self, port_ret: float, bench_ret: float,
        alloc: float, select: float, interact: float,
    ) -> BrinsonResult:
        return BrinsonResult(
            total_portfolio_return=port_ret,
            total_benchmark_return=bench_ret,
            total_active_return=port_ret - bench_ret,
            total_allocation=alloc,
            total_selection=select,
            total_interaction=interact,
            residual=(port_ret - bench_ret) - (alloc + select + interact),
            sector_detail=[
                SectorAttribution(
                    sector="Tech", portfolio_weight=0.40, benchmark_weight=0.30,
                    portfolio_return=port_ret * 1.2, benchmark_return=bench_ret * 1.1,
                    allocation_effect=alloc * 0.6, selection_effect=select * 0.6,
                    interaction_effect=interact * 0.6,
                    total_effect=(alloc + select + interact) * 0.6,
                ),
            ],
        )

    def test_two_periods(self):
        """Link two periods summing effects."""
        p1 = self._make_period_result(0.05, 0.04, 0.005, 0.003, 0.002)
        p2 = self._make_period_result(0.03, 0.025, 0.003, 0.001, 0.001)
        result = link_multi_period_attribution([p1, p2])
        assert result.total_portfolio_return == pytest.approx(0.08, abs=0.001)
        assert result.total_benchmark_return == pytest.approx(0.065, abs=0.001)
        assert result.total_allocation == pytest.approx(0.008, abs=0.001)

    def test_empty(self):
        """Empty list → zero result."""
        result = link_multi_period_attribution([])
        assert result.total_portfolio_return == 0.0
        assert result.total_active_return == 0.0

    def test_single_period(self):
        """Single period passes through."""
        p1 = self._make_period_result(0.05, 0.04, 0.005, 0.003, 0.002)
        result = link_multi_period_attribution([p1])
        assert result.total_portfolio_return == pytest.approx(0.05, abs=0.001)

    def test_sector_aggregation(self):
        """Sector details aggregated across periods."""
        p1 = self._make_period_result(0.05, 0.04, 0.005, 0.003, 0.002)
        p2 = self._make_period_result(0.03, 0.025, 0.003, 0.001, 0.001)
        result = link_multi_period_attribution([p1, p2])
        assert len(result.sector_detail) >= 1
        tech = next(s for s in result.sector_detail if s.sector == "Tech")
        assert tech.allocation_effect == pytest.approx(
            0.005 * 0.6 + 0.003 * 0.6, abs=0.001
        )
