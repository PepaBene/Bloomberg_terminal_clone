"""Tests for Pillar 4 Phase 1 — Portfolio-Level Analytics Engine."""

import pytest

from src.engines.portfolio_analytics import (
    classify_concentration,
    compute_cash_utilization,
    compute_concentration_hhi,
    compute_effective_positions,
    compute_portfolio_age,
    compute_portfolio_summary,
    compute_sector_allocation,
    compute_top_holdings,
    compute_unrealized_pnl_summary,
    enrich_position_with_p2,
)


# ── Helpers ─────────────────────────────────────────────────────────────


def _ten_stock_portfolio() -> list[dict]:
    """Realistic 10-stock Buffett-style portfolio."""
    return [
        {"ticker": "AAPL", "market_value": 120000, "weight": 0.12, "sector": "Technology", "unrealized_pnl": 25000},
        {"ticker": "BRK.B", "market_value": 95000, "weight": 0.095, "sector": "Financials", "unrealized_pnl": 15000},
        {"ticker": "KO", "market_value": 85000, "weight": 0.085, "sector": "Consumer Staples", "unrealized_pnl": 10000},
        {"ticker": "AXP", "market_value": 78000, "weight": 0.078, "sector": "Financials", "unrealized_pnl": 18000},
        {"ticker": "BAC", "market_value": 72000, "weight": 0.072, "sector": "Financials", "unrealized_pnl": 8000},
        {"ticker": "CVX", "market_value": 68000, "weight": 0.068, "sector": "Energy", "unrealized_pnl": 5000},
        {"ticker": "OXY", "market_value": 55000, "weight": 0.055, "sector": "Energy", "unrealized_pnl": -3000},
        {"ticker": "KHC", "market_value": 48000, "weight": 0.048, "sector": "Consumer Staples", "unrealized_pnl": -7000},
        {"ticker": "MCO", "market_value": 42000, "weight": 0.042, "sector": "Financials", "unrealized_pnl": 12000},
        {"ticker": "DVA", "market_value": 37000, "weight": 0.037, "sector": "Healthcare", "unrealized_pnl": 5000},
    ]


# ── TestSummary ───────────────────────────────────────────────────────


class TestSummary:
    """Tests for compute_portfolio_summary."""

    def test_ten_stock_portfolio(self):
        """10-stock portfolio summary."""
        positions = _ten_stock_portfolio()
        total_mv = sum(p["market_value"] for p in positions)
        cash = 50000.0
        nav = total_mv + cash

        summary = compute_portfolio_summary(positions, cash, nav)
        assert summary["total_positions"] == 10
        assert summary["market_value"] == total_mv
        assert summary["cash_pct"] > 0
        assert summary["invested_pct"] > 0
        assert summary["cash_pct"] + summary["invested_pct"] == pytest.approx(100.0, abs=0.01)

    def test_single_stock(self):
        """Single stock portfolio."""
        positions = [{"ticker": "AAPL", "market_value": 50000}]
        summary = compute_portfolio_summary(positions, 10000.0, 60000.0)
        assert summary["total_positions"] == 1
        assert summary["avg_position_size"] == 50000.0

    def test_cash_only(self):
        """Cash-only portfolio."""
        summary = compute_portfolio_summary([], 100000.0, 100000.0)
        assert summary["total_positions"] == 0
        assert summary["cash_pct"] == 100.0
        assert summary["invested_pct"] == 0.0
        assert summary["avg_position_size"] == 0.0


# ── TestSectorAllocation ─────────────────────────────────────────────


class TestSectorAllocation:
    """Tests for compute_sector_allocation."""

    def test_three_sectors(self):
        """3 sectors: Financials dominant."""
        positions = _ten_stock_portfolio()
        sectors = compute_sector_allocation(positions)

        assert len(sectors) >= 3
        # Financials should be highest (BRK.B + AXP + BAC + MCO)
        assert sectors[0]["sector"] == "Financials"
        # Weights should sum to ~100%
        total_weight = sum(s["weight"] for s in sectors)
        assert total_weight == pytest.approx(100.0, abs=0.1)

    def test_single_sector(self):
        """All positions in one sector."""
        positions = [
            {"ticker": "AAPL", "market_value": 50000, "sector": "Technology"},
            {"ticker": "MSFT", "market_value": 30000, "sector": "Technology"},
        ]
        sectors = compute_sector_allocation(positions)
        assert len(sectors) == 1
        assert sectors[0]["sector"] == "Technology"
        assert sectors[0]["weight"] == pytest.approx(100.0, abs=0.01)


# ── TestTopHoldings ───────────────────────────────────────────────────


class TestTopHoldings:
    """Tests for compute_top_holdings."""

    def test_top_five_from_twenty(self):
        """Top 5 from 20 positions."""
        positions = [
            {"ticker": f"STK{i}", "weight": 0.05 * (20 - i)}
            for i in range(20)
        ]
        top = compute_top_holdings(positions, n=5)
        assert len(top) == 5
        assert top[0]["weight"] >= top[4]["weight"]

    def test_top_three_from_three(self):
        """Top 3 from exactly 3."""
        positions = [
            {"ticker": "A", "weight": 0.5},
            {"ticker": "B", "weight": 0.3},
            {"ticker": "C", "weight": 0.2},
        ]
        top = compute_top_holdings(positions, n=3)
        assert len(top) == 3
        assert top[0]["ticker"] == "A"


# ── TestHHI ───────────────────────────────────────────────────────────


class TestHHI:
    """Tests for compute_concentration_hhi."""

    def test_equal_weight_twenty(self):
        """20 equal-weight positions → HHI=500."""
        weights = [1.0 / 20] * 20
        hhi = compute_concentration_hhi(weights)
        assert hhi == pytest.approx(500.0, abs=1.0)

    def test_concentrated_five(self):
        """5 positions with unequal weights → HHI > 2000."""
        weights = [0.50, 0.20, 0.15, 0.10, 0.05]
        hhi = compute_concentration_hhi(weights)
        # 0.25 + 0.04 + 0.0225 + 0.01 + 0.0025 = 0.325 * 10000 = 3250
        assert hhi == pytest.approx(3250.0, abs=1.0)
        assert hhi > 2000

    def test_single_stock(self):
        """Single stock → HHI=10000."""
        hhi = compute_concentration_hhi([1.0])
        assert hhi == pytest.approx(10000.0, abs=0.01)


# ── TestConcentration ─────────────────────────────────────────────────


class TestConcentration:
    """Tests for classify_concentration."""

    def test_diversified(self):
        assert classify_concentration(400) == "DIVERSIFIED"

    def test_moderate(self):
        assert classify_concentration(800) == "MODERATE"

    def test_concentrated(self):
        assert classify_concentration(2000) == "CONCENTRATED"


# ── TestEffectivePositions ────────────────────────────────────────────


class TestEffectivePositions:
    """Tests for compute_effective_positions."""

    def test_hhi_500(self):
        """HHI=500 → 20 effective positions."""
        assert compute_effective_positions(500) == pytest.approx(20.0, abs=0.1)

    def test_hhi_2000(self):
        """HHI=2000 → 5 effective positions."""
        assert compute_effective_positions(2000) == pytest.approx(5.0, abs=0.1)


# ── TestPnLSummary ────────────────────────────────────────────────────


class TestPnLSummary:
    """Tests for compute_unrealized_pnl_summary."""

    def test_seven_winners_three_losers(self):
        """7 winners, 3 losers."""
        positions = _ten_stock_portfolio()
        summary = compute_unrealized_pnl_summary(positions)

        # Count from test data: positive PnL = AAPL, BRK.B, KO, AXP, BAC, CVX, MCO, DVA = 8
        # Negative PnL = OXY, KHC = 2
        assert summary["winners_count"] == 8
        assert summary["losers_count"] == 2
        assert summary["total_gain"] > 0
        assert summary["total_loss"] < 0
        assert summary["net_pnl"] == summary["total_gain"] + summary["total_loss"]
        assert summary["win_rate"] == pytest.approx(80.0, abs=0.1)

    def test_all_winners(self):
        """All positions have gains."""
        positions = [
            {"ticker": "A", "unrealized_pnl": 1000},
            {"ticker": "B", "unrealized_pnl": 2000},
        ]
        summary = compute_unrealized_pnl_summary(positions)
        assert summary["winners_count"] == 2
        assert summary["losers_count"] == 0
        assert summary["win_rate"] == 100.0

    def test_all_losers(self):
        """All positions have losses."""
        positions = [
            {"ticker": "A", "unrealized_pnl": -500},
            {"ticker": "B", "unrealized_pnl": -1500},
        ]
        summary = compute_unrealized_pnl_summary(positions)
        assert summary["winners_count"] == 0
        assert summary["losers_count"] == 2
        assert summary["win_rate"] == 0.0


# ── TestCashUtil ──────────────────────────────────────────────────────


class TestCashUtil:
    """Tests for compute_cash_utilization."""

    def test_optimal(self):
        """5% cash → OPTIMAL."""
        result = compute_cash_utilization(5000, 100000)
        assert result["status"] == "OPTIMAL"
        assert result["cash_pct"] == pytest.approx(5.0, abs=0.01)

    def test_under_invested(self):
        """0.5% cash → UNDER_INVESTED."""
        result = compute_cash_utilization(500, 100000)
        assert result["status"] == "UNDER_INVESTED"
        assert result["cash_pct"] == pytest.approx(0.5, abs=0.01)

    def test_over_cash(self):
        """20% cash → OVER_CASH."""
        result = compute_cash_utilization(20000, 100000)
        assert result["status"] == "OVER_CASH"
        assert result["cash_pct"] == pytest.approx(20.0, abs=0.01)


# ── TestEnrich ────────────────────────────────────────────────────────


class TestEnrich:
    """Tests for enrich_position_with_p2."""

    def test_with_ratios(self):
        """Enrich with full ratios."""
        pos = {"ticker": "AAPL", "market_value": 100000}
        ratios = {
            "pe_ratio": 28.5,
            "roe": 0.45,
            "piotroski_score": 8,
            "debt_to_equity": 1.5,
            "dividend_yield": 0.006,
        }
        enriched = enrich_position_with_p2(pos, ratios)
        assert enriched["pe_ratio"] == 28.5
        assert enriched["roe"] == 0.45
        assert enriched["piotroski_score"] == 8
        assert enriched["ticker"] == "AAPL"

    def test_without_ratios(self):
        """Enrich without ratios (None)."""
        pos = {"ticker": "MSFT", "market_value": 50000}
        enriched = enrich_position_with_p2(pos, None)
        assert enriched["ticker"] == "MSFT"
        assert "pe_ratio" not in enriched

    def test_partial_ratios(self):
        """Enrich with partial ratios."""
        pos = {"ticker": "JNJ", "market_value": 30000}
        ratios = {"pe_ratio": 15.0, "roe": 0.22}
        enriched = enrich_position_with_p2(pos, ratios)
        assert enriched["pe_ratio"] == 15.0
        assert enriched["roe"] == 0.22
        assert enriched["piotroski_score"] is None


# ── TestAge ───────────────────────────────────────────────────────────


class TestAge:
    """Tests for compute_portfolio_age."""

    def test_one_year(self):
        """365 days ≈ 1 year."""
        age = compute_portfolio_age("2024-01-01", "2025-01-01")
        assert age["days"] == 366  # 2024 is a leap year
        assert age["years"] == pytest.approx(1.0, abs=0.05)

    def test_thirty_days(self):
        """30 days ≈ 1 month."""
        age = compute_portfolio_age("2025-01-01", "2025-01-31")
        assert age["days"] == 30
        assert age["months"] == pytest.approx(1.0, abs=0.1)

    def test_five_years(self):
        """~5 years."""
        age = compute_portfolio_age("2020-03-01", "2025-03-01")
        assert age["years"] == pytest.approx(5.0, abs=0.1)


# ── TestIntegration ───────────────────────────────────────────────────


class TestIntegration:
    """Integration: full analytics for Buffett-style portfolio."""

    def test_full_analytics_pipeline(self):
        """Run all analytics on a realistic portfolio."""
        positions = _ten_stock_portfolio()
        total_mv = sum(p["market_value"] for p in positions)
        cash = 50000.0
        nav = total_mv + cash

        # Summary
        summary = compute_portfolio_summary(positions, cash, nav)
        assert summary["total_positions"] == 10

        # Sector allocation
        sectors = compute_sector_allocation(positions)
        assert len(sectors) >= 3

        # Top holdings
        top = compute_top_holdings(positions, n=5)
        assert len(top) == 5

        # Concentration
        weights = [p["market_value"] / total_mv for p in positions]
        hhi = compute_concentration_hhi(weights)
        classification = classify_concentration(hhi)
        eff = compute_effective_positions(hhi)
        assert eff > 0

    def test_pnl_and_cash_analysis(self):
        """PnL summary and cash utilization."""
        positions = _ten_stock_portfolio()
        total_mv = sum(p["market_value"] for p in positions)
        cash = 50000.0
        nav = total_mv + cash

        pnl = compute_unrealized_pnl_summary(positions)
        assert pnl["net_pnl"] > 0  # net positive

        cash_util = compute_cash_utilization(cash, nav)
        assert cash_util["status"] in ("OPTIMAL", "UNDER_INVESTED", "OVER_CASH")

    def test_enrichment_and_age(self):
        """Enrich positions and compute portfolio age."""
        pos = _ten_stock_portfolio()[0]
        ratios = {"pe_ratio": 30.0, "roe": 0.40, "piotroski_score": 7}
        enriched = enrich_position_with_p2(pos, ratios)
        assert enriched["pe_ratio"] == 30.0

        age = compute_portfolio_age("2020-01-15", "2025-06-15")
        assert age["years"] > 5
