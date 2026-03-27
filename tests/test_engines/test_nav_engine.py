"""Tests for Pillar 4 Phase 1 — Daily NAV Calculation Engine."""

import pytest

from src.engines.nav_engine import (
    MissingPriceFlag,
    PortfolioNAV,
    PositionValuation,
    build_nav_snapshot,
    compute_cash_weight,
    compute_cumulative_return,
    compute_daily_return,
    compute_day_change,
    compute_portfolio_nav,
    compute_position_market_value,
    compute_position_valuation,
    compute_position_weights,
    handle_missing_price,
    validate_nav_integrity,
)


# ── Helpers ─────────────────────────────────────────────────────────────


def _make_position(
    ticker: str,
    shares: float,
    cost_per_share: float,
    closing_price: float,
    prior_close: float | None = None,
) -> dict:
    """Helper to build a position dict."""
    return {
        "ticker": ticker,
        "shares": shares,
        "cost_basis_total": shares * cost_per_share,
        "cost_basis_per_share": cost_per_share,
        "closing_price": closing_price,
        "prior_close": prior_close,
    }


# ── TestPositionValuation ──────────────────────────────────────────────


class TestPositionValuation:
    """Tests for compute_position_valuation and compute_position_market_value."""

    def test_basic_valuation(self):
        """100 shares at $150, cost $100/share → MV=15000, PnL=5000."""
        val = compute_position_valuation(
            ticker="AAPL", shares=100, cost_basis_total=10000,
            cost_basis_per_share=100.0, closing_price=150.0, prior_close=148.0,
        )
        assert val.market_value == 15000.0
        assert val.unrealized_pnl == 5000.0
        assert val.unrealized_pnl_pct == pytest.approx(50.0, abs=0.01)
        assert val.day_change_pct is not None
        assert val.day_change_pct == pytest.approx(1.3514, abs=0.01)

    def test_zero_shares(self):
        """Zero shares → market value 0."""
        val = compute_position_valuation(
            ticker="MSFT", shares=0, cost_basis_total=0,
            cost_basis_per_share=0, closing_price=400.0,
        )
        assert val.market_value == 0.0
        assert val.unrealized_pnl == 0.0

    def test_negative_pnl(self):
        """Price dropped below cost basis → negative PnL."""
        val = compute_position_valuation(
            ticker="META", shares=50, cost_basis_total=25000,
            cost_basis_per_share=500.0, closing_price=400.0,
        )
        assert val.market_value == 20000.0
        assert val.unrealized_pnl == -5000.0
        assert val.unrealized_pnl_pct < 0

    def test_no_prior_close(self):
        """No prior close → day_change_pct is None."""
        val = compute_position_valuation(
            ticker="GOOG", shares=10, cost_basis_total=1500,
            cost_basis_per_share=150.0, closing_price=175.0,
        )
        assert val.day_change_pct is None

    def test_market_value_computation(self):
        """Direct market value: 500 shares * $25 = $12500."""
        mv = compute_position_market_value(500, 25.0)
        assert mv == 12500.0


# ── TestPortfolioNAV ───────────────────────────────────────────────────


class TestPortfolioNAV:
    """Tests for compute_portfolio_nav."""

    def test_five_stock_portfolio(self):
        """Realistic 5-stock portfolio with cash."""
        positions = [
            _make_position("AAPL", 100, 150.0, 175.0, 173.0),
            _make_position("MSFT", 80, 300.0, 350.0, 348.0),
            _make_position("JNJ", 120, 160.0, 155.0, 156.0),
            _make_position("JPM", 90, 140.0, 165.0, 163.0),
            _make_position("PG", 110, 130.0, 145.0, 144.0),
        ]
        cash = 25000.0

        nav_result = compute_portfolio_nav(positions, cash)

        # Total MV = 100*175 + 80*350 + 120*155 + 90*165 + 110*145
        # = 17500 + 28000 + 18600 + 14850 + 15950 = 94900
        assert nav_result.market_value == 94900.0
        assert nav_result.nav == 94900.0 + 25000.0  # 119900
        assert nav_result.cash_balance == 25000.0
        assert nav_result.position_count == 5
        assert len(nav_result.positions) == 5

        # Check weights sum to ~1 - cash_weight
        pos_weights = sum(p.weight for p in nav_result.positions)
        assert pos_weights + nav_result.cash_weight == pytest.approx(1.0, abs=0.001)

    def test_single_position(self):
        """Single position portfolio."""
        positions = [_make_position("BRK.B", 50, 350.0, 400.0)]
        cash = 5000.0
        nav_result = compute_portfolio_nav(positions, cash)

        assert nav_result.market_value == 20000.0
        assert nav_result.nav == 25000.0
        assert nav_result.position_count == 1

    def test_cash_only(self):
        """Portfolio with no positions, only cash."""
        nav_result = compute_portfolio_nav([], 100000.0)

        assert nav_result.market_value == 0.0
        assert nav_result.nav == 100000.0
        assert nav_result.cash_weight == pytest.approx(1.0, abs=0.0001)
        assert nav_result.position_count == 0


# ── TestDailyReturn ────────────────────────────────────────────────────


class TestDailyReturn:
    """Tests for compute_daily_return."""

    def test_positive_return(self):
        """NAV went from 100000 to 101000 → 1%."""
        ret = compute_daily_return(101000.0, 100000.0)
        assert ret == pytest.approx(0.01, abs=0.0001)

    def test_negative_return(self):
        """NAV went from 100000 to 98000 → -2%."""
        ret = compute_daily_return(98000.0, 100000.0)
        assert ret == pytest.approx(-0.02, abs=0.0001)

    def test_with_cash_flows(self):
        """Modified Dietz with cash inflow."""
        # NAV yesterday = 100000, today = 110000, cash flow = 5000
        # return = (110000 - 100000 - 5000) / (100000 + 0.5*5000)
        # = 5000 / 102500 ≈ 0.04878
        ret = compute_daily_return(110000.0, 100000.0, 5000.0)
        assert ret == pytest.approx(0.04878, abs=0.001)

    def test_zero_nav_yesterday(self):
        """Zero starting NAV → return 0."""
        ret = compute_daily_return(100.0, 0.0, 0.0)
        assert ret == 0.0


# ── TestCumulativeReturn ───────────────────────────────────────────────


class TestCumulativeReturn:
    """Tests for compute_cumulative_return."""

    def test_five_days_positive(self):
        """5 days of 1% each → geometric > 5%."""
        returns = [0.01, 0.01, 0.01, 0.01, 0.01]
        cum = compute_cumulative_return(returns)
        # (1.01)^5 - 1 = 0.05101
        assert cum == pytest.approx(0.05101, abs=0.001)

    def test_mixed_returns(self):
        """Mixed positive and negative returns."""
        returns = [0.02, -0.01, 0.015, -0.005, 0.01]
        cum = compute_cumulative_return(returns)
        expected = 1.02 * 0.99 * 1.015 * 0.995 * 1.01 - 1.0
        assert cum == pytest.approx(expected, abs=0.0001)

    def test_empty_list(self):
        """Empty list → 0 return."""
        assert compute_cumulative_return([]) == 0.0

    def test_single_day(self):
        """Single day return."""
        assert compute_cumulative_return([0.05]) == pytest.approx(0.05, abs=0.0001)


# ── TestPositionWeights ────────────────────────────────────────────────


class TestPositionWeights:
    """Tests for compute_position_weights."""

    def test_equal_weight(self):
        """4 positions of $25000 each, NAV=100000."""
        weights = compute_position_weights(
            [25000, 25000, 25000, 25000], 100000,
        )
        assert all(w == pytest.approx(0.25, abs=0.001) for w in weights)

    def test_concentrated(self):
        """One position dominates."""
        weights = compute_position_weights(
            [80000, 10000, 5000, 5000], 100000,
        )
        assert weights[0] == pytest.approx(0.80, abs=0.001)
        assert sum(weights) == pytest.approx(1.0, abs=0.001)

    def test_zero_nav(self):
        """Zero NAV → all weights zero."""
        weights = compute_position_weights([100, 200, 300], 0.0)
        assert all(w == 0.0 for w in weights)


# ── TestDayChange ──────────────────────────────────────────────────────


class TestDayChange:
    """Tests for compute_day_change."""

    def test_up_five_pct(self):
        """Price from $100 to $105 → +5%."""
        change = compute_day_change(105.0, 100.0)
        assert change["dollar_change"] == pytest.approx(5.0, abs=0.01)
        assert change["pct_change"] == pytest.approx(5.0, abs=0.01)

    def test_down_ten_pct(self):
        """Price from $200 to $180 → -10%."""
        change = compute_day_change(180.0, 200.0)
        assert change["dollar_change"] == pytest.approx(-20.0, abs=0.01)
        assert change["pct_change"] == pytest.approx(-10.0, abs=0.01)

    def test_flat(self):
        """No price change → 0%."""
        change = compute_day_change(150.0, 150.0)
        assert change["dollar_change"] == pytest.approx(0.0, abs=0.01)
        assert change["pct_change"] == pytest.approx(0.0, abs=0.01)


# ── TestMissingPrice ──────────────────────────────────────────────────


class TestMissingPrice:
    """Tests for handle_missing_price."""

    def test_stale_price(self):
        flag = handle_missing_price("XYZ", "STALE", 45.0, "2025-12-01")
        assert flag.ticker == "XYZ"
        assert flag.reason == "STALE"
        assert flag.last_price == 45.0
        assert flag.last_price_date == "2025-12-01"

    def test_delisted(self):
        flag = handle_missing_price("DEAD", "DELISTED", 0.01, "2024-06-15")
        assert flag.reason == "DELISTED"
        assert flag.last_price == 0.01

    def test_ipo(self):
        flag = handle_missing_price("NEWCO", "IPO", None, None)
        assert flag.reason == "IPO"
        assert flag.last_price is None
        assert flag.last_price_date is None


# ── TestNavIntegrity ──────────────────────────────────────────────────


class TestNavIntegrity:
    """Tests for validate_nav_integrity."""

    def test_valid_nav(self):
        """NAV matches positions + cash → no warnings."""
        warnings = validate_nav_integrity(100000.0, 85000.0, 15000.0)
        assert warnings == []

    def test_discrepancy(self):
        """Small mismatch triggers warning."""
        warnings = validate_nav_integrity(100000.0, 84990.0, 15000.0)
        assert len(warnings) >= 1
        assert "mismatch" in warnings[0].lower()

    def test_large_mismatch(self):
        """Large mismatch clearly flagged."""
        warnings = validate_nav_integrity(100000.0, 70000.0, 15000.0)
        assert len(warnings) >= 1


# ── TestCashWeight ────────────────────────────────────────────────────


class TestCashWeight:
    """Tests for compute_cash_weight."""

    def test_normal(self):
        """$15000 cash, $100000 NAV → 15%."""
        w = compute_cash_weight(15000.0, 100000.0)
        assert w == pytest.approx(0.15, abs=0.001)

    def test_zero_nav(self):
        """Zero NAV → 0."""
        assert compute_cash_weight(1000.0, 0.0) == 0.0

    def test_hundred_pct_cash(self):
        """All cash → weight = 1.0."""
        w = compute_cash_weight(50000.0, 50000.0)
        assert w == pytest.approx(1.0, abs=0.0001)


# ── TestBuildSnapshot ─────────────────────────────────────────────────


class TestBuildSnapshot:
    """Tests for build_nav_snapshot."""

    def test_full_snapshot(self):
        """Build snapshot with all fields populated."""
        nav_data = PortfolioNAV(
            nav=100000.0, market_value=90000.0, cash_balance=10000.0,
            unrealized_pnl=5000.0, cash_weight=0.1, position_count=5,
        )
        snap = build_nav_snapshot(
            portfolio_id="PORT-001",
            snapshot_date="2025-06-15",
            nav_data=nav_data,
            daily_return=0.0085,
            cumulative_return=0.12,
            benchmark_daily=0.005,
            benchmark_cumulative=0.08,
        )
        assert snap["portfolio_id"] == "PORT-001"
        assert snap["snapshot_date"] == "2025-06-15"
        assert snap["nav"] == 100000.0
        assert snap["daily_return"] == pytest.approx(0.0085, abs=0.0001)
        assert snap["active_return_daily"] == pytest.approx(0.0035, abs=0.0001)
        assert snap["active_return_cumulative"] == pytest.approx(0.04, abs=0.0001)

    def test_snapshot_no_benchmark(self):
        """Build snapshot without benchmark data."""
        nav_data = PortfolioNAV(
            nav=50000.0, market_value=45000.0, cash_balance=5000.0,
            unrealized_pnl=2000.0, cash_weight=0.1, position_count=3,
        )
        snap = build_nav_snapshot(
            portfolio_id="PORT-002",
            snapshot_date="2025-06-15",
            nav_data=nav_data,
            daily_return=0.005,
            cumulative_return=0.06,
            benchmark_daily=None,
            benchmark_cumulative=None,
        )
        assert snap["benchmark_daily_return"] is None
        assert snap["benchmark_cumulative_return"] is None
        assert snap["active_return_daily"] is None
        assert snap["active_return_cumulative"] is None


# ── TestIntegration ───────────────────────────────────────────────────


class TestIntegration:
    """Integration tests: full NAV calc for realistic 10-stock value portfolio."""

    def _build_value_portfolio(self) -> tuple[list[dict], float]:
        """Buffett-style $1M value portfolio."""
        return [
            _make_position("AAPL", 200, 130.0, 175.0, 173.0),
            _make_position("BRK.B", 150, 300.0, 380.0, 377.0),
            _make_position("KO", 500, 55.0, 62.0, 61.5),
            _make_position("AXP", 180, 160.0, 210.0, 208.0),
            _make_position("BAC", 600, 32.0, 38.0, 37.5),
            _make_position("CVX", 120, 145.0, 155.0, 154.0),
            _make_position("OXY", 300, 58.0, 52.0, 53.0),
            _make_position("KHC", 400, 35.0, 33.0, 32.5),
            _make_position("MCO", 50, 350.0, 420.0, 418.0),
            _make_position("DVA", 100, 95.0, 110.0, 108.0),
        ], 50000.0

    def test_full_nav_calculation(self):
        """Complete NAV calculation for 10-stock portfolio."""
        positions, cash = self._build_value_portfolio()
        nav_result = compute_portfolio_nav(positions, cash)

        assert nav_result.position_count == 10
        assert nav_result.nav > 0
        assert nav_result.cash_balance == 50000.0
        assert len(nav_result.positions) == 10

    def test_daily_return_calculation(self):
        """Daily return from two consecutive NAVs."""
        positions, cash = self._build_value_portfolio()
        nav_today = compute_portfolio_nav(positions, cash)

        # Simulate yesterday's NAV (slightly lower)
        nav_yesterday = nav_today.nav * 0.995
        ret = compute_daily_return(nav_today.nav, nav_yesterday)
        assert ret == pytest.approx(0.005025, abs=0.001)

    def test_cumulative_return_from_daily(self):
        """Build cumulative return from daily series."""
        daily = [0.005, -0.002, 0.008, 0.001, -0.003]
        cum = compute_cumulative_return(daily)
        assert cum > 0  # net positive

    def test_nav_integrity_check(self):
        """NAV integrity on computed portfolio."""
        positions, cash = self._build_value_portfolio()
        nav_result = compute_portfolio_nav(positions, cash)
        warnings = validate_nav_integrity(
            nav_result.nav, nav_result.market_value, nav_result.cash_balance,
        )
        assert warnings == []


# ── TestEdgeCases ─────────────────────────────────────────────────────


class TestEdgeCases:
    """Edge case tests."""

    def test_fractional_shares(self):
        """Fractional shares (e.g., DRIP)."""
        val = compute_position_valuation(
            ticker="AAPL", shares=10.5432, cost_basis_total=1580.0,
            cost_basis_per_share=149.86, closing_price=175.0,
        )
        assert val.market_value == pytest.approx(10.5432 * 175.0, abs=0.01)

    def test_penny_stock(self):
        """Very low-priced stock."""
        val = compute_position_valuation(
            ticker="PNNY", shares=100000, cost_basis_total=5000.0,
            cost_basis_per_share=0.05, closing_price=0.03,
        )
        assert val.market_value == pytest.approx(3000.0, abs=0.01)
        assert val.unrealized_pnl < 0

    def test_very_large_position(self):
        """Institutional-size position."""
        val = compute_position_valuation(
            ticker="AAPL", shares=1_000_000, cost_basis_total=150_000_000,
            cost_basis_per_share=150.0, closing_price=175.0,
        )
        assert val.market_value == 175_000_000.0
        assert val.unrealized_pnl == 25_000_000.0

    def test_cumulative_return_all_negative(self):
        """All negative daily returns."""
        returns = [-0.01, -0.02, -0.015, -0.005, -0.01]
        cum = compute_cumulative_return(returns)
        assert cum < 0
        # Product: 0.99 * 0.98 * 0.985 * 0.995 * 0.99 ≈ 0.9411 → -5.89%
        assert cum == pytest.approx(-0.0589, abs=0.01)
