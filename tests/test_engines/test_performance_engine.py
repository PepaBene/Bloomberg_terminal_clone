"""Tests for Pillar 4 Phase 2 — Performance Engine."""

import math

import pytest

from src.engines.performance_engine import (
    DrawdownAnalysis,
    PerformanceSummary,
    RiskMetrics,
    annualize_return,
    build_performance_summary,
    compute_alpha,
    compute_batting_average,
    compute_beta,
    compute_calmar_ratio,
    compute_calendar_year_returns,
    compute_downside_deviation,
    compute_information_ratio,
    compute_max_drawdown,
    compute_mwr,
    compute_rolling_returns,
    compute_sharpe_ratio,
    compute_sortino_ratio,
    compute_standard_periods,
    compute_tracking_error,
    compute_twr,
    compute_up_down_capture,
    compute_volatility,
)


# ── TestTWR ────────────────────────────────────────────────────────────


class TestTWR:
    """Tests for compute_twr (time-weighted return)."""

    def test_basic_positive(self):
        """Five days of 1% each → geometric > 5%."""
        returns = [0.01, 0.01, 0.01, 0.01, 0.01]
        twr = compute_twr(returns)
        assert twr == pytest.approx(0.05101, abs=0.001)

    def test_mixed_returns(self):
        """Mixed positive/negative returns."""
        returns = [0.02, -0.01, 0.015, -0.005, 0.01]
        twr = compute_twr(returns)
        expected = 1.02 * 0.99 * 1.015 * 0.995 * 1.01 - 1.0
        assert twr == pytest.approx(expected, abs=0.0001)

    def test_empty(self):
        """Empty returns → 0."""
        assert compute_twr([]) == 0.0

    def test_single_day(self):
        """Single return."""
        assert compute_twr([0.05]) == pytest.approx(0.05, abs=0.0001)

    def test_all_negative(self):
        """All negative daily returns."""
        returns = [-0.01, -0.02, -0.015, -0.005, -0.01]
        twr = compute_twr(returns)
        assert twr < 0

    def test_zero_returns(self):
        """All zero returns → 0."""
        assert compute_twr([0.0, 0.0, 0.0]) == 0.0

    def test_large_single_gain(self):
        """Single large gain."""
        assert compute_twr([0.5]) == pytest.approx(0.5, abs=0.0001)


# ── TestMWR ────────────────────────────────────────────────────────────


class TestMWR:
    """Tests for compute_mwr (money-weighted return / IRR)."""

    def test_simple_irr(self):
        """Invest 100 at t=0, get back 110 at t=365 → ~10% IRR."""
        cash_flows = [{"date_offset": 0, "amount": -100.0}]
        mwr = compute_mwr(cash_flows, final_value=110.0)
        assert mwr == pytest.approx(0.10, abs=0.02)

    def test_multiple_flows(self):
        """Multiple cash flows should converge."""
        cash_flows = [
            {"date_offset": 0, "amount": -1000.0},
            {"date_offset": 180, "amount": -500.0},
        ]
        mwr = compute_mwr(cash_flows, final_value=1600.0)
        assert -1.0 < mwr < 1.0  # reasonable range

    def test_empty_flows(self):
        """No cash flows → 0."""
        assert compute_mwr([], final_value=100.0) == 0.0

    def test_negative_return(self):
        """Invest 1000, get back 900 → negative IRR."""
        cash_flows = [{"date_offset": 0, "amount": -1000.0}]
        mwr = compute_mwr(cash_flows, final_value=900.0)
        assert mwr < 0


# ── TestAnnualizeReturn ────────────────────────────────────────────────


class TestAnnualizeReturn:
    """Tests for annualize_return."""

    def test_one_year(self):
        """10% over 365 days → 10% annualized."""
        ann = annualize_return(0.10, 365)
        assert ann == pytest.approx(0.10, abs=0.001)

    def test_half_year(self):
        """5% over 182 days → annualized > 10%."""
        ann = annualize_return(0.05, 182)
        assert ann > 0.10

    def test_two_years(self):
        """21% over 730 days → annualized ~10%."""
        ann = annualize_return(0.21, 730)
        assert ann == pytest.approx(0.10, abs=0.01)

    def test_zero_days(self):
        """Zero days → 0."""
        assert annualize_return(0.10, 0) == 0.0

    def test_total_loss(self):
        """-100% → clamped to -1."""
        assert annualize_return(-1.0, 365) == -1.0


# ── TestVolatility ─────────────────────────────────────────────────────


class TestVolatility:
    """Tests for compute_volatility."""

    def test_basic_volatility(self):
        """Known returns → positive vol."""
        returns = [0.01, -0.02, 0.015, -0.005, 0.008, 0.01, -0.01]
        vol = compute_volatility(returns, annualize=True)
        assert vol > 0

    def test_zero_returns(self):
        """All zero returns → zero vol."""
        assert compute_volatility([0.0, 0.0, 0.0, 0.0]) == 0.0

    def test_annualized_vs_daily(self):
        """Annualized vol > daily vol for typical data."""
        returns = [0.01, -0.005, 0.008, -0.003, 0.006]
        vol_ann = compute_volatility(returns, annualize=True)
        vol_daily = compute_volatility(returns, annualize=False)
        assert vol_ann > vol_daily

    def test_single_return(self):
        """Single return → 0."""
        assert compute_volatility([0.01]) == 0.0

    def test_empty(self):
        """Empty → 0."""
        assert compute_volatility([]) == 0.0


# ── TestDownsideDeviation ──────────────────────────────────────────────


class TestDownsideDeviation:
    """Tests for compute_downside_deviation."""

    def test_all_positive(self):
        """All positive returns with MAR=0 → 0 downside deviation."""
        returns = [0.01, 0.02, 0.015, 0.005]
        dd = compute_downside_deviation(returns, mar=0.0)
        assert dd == 0.0

    def test_mixed_returns(self):
        """Mixed returns → positive downside deviation."""
        returns = [0.01, -0.02, 0.015, -0.03, 0.005]
        dd = compute_downside_deviation(returns, mar=0.0)
        assert dd > 0

    def test_custom_mar(self):
        """Non-zero MAR threshold."""
        returns = [0.01, 0.005, -0.01, 0.002]
        dd_zero = compute_downside_deviation(returns, mar=0.0)
        dd_high = compute_downside_deviation(returns, mar=0.01)
        assert dd_high > dd_zero

    def test_empty(self):
        """Empty → 0."""
        assert compute_downside_deviation([]) == 0.0


# ── TestSharpeRatio ────────────────────────────────────────────────────


class TestSharpeRatio:
    """Tests for compute_sharpe_ratio."""

    def test_positive_sharpe(self):
        """Return > risk-free → positive Sharpe."""
        sharpe = compute_sharpe_ratio(0.12, 0.04, 0.15)
        assert sharpe == pytest.approx(0.5333, abs=0.01)

    def test_negative_sharpe(self):
        """Return < risk-free → negative Sharpe."""
        sharpe = compute_sharpe_ratio(0.02, 0.04, 0.15)
        assert sharpe < 0

    def test_zero_vol(self):
        """Zero volatility → 0."""
        assert compute_sharpe_ratio(0.10, 0.04, 0.0) == 0.0


# ── TestSortinoRatio ───────────────────────────────────────────────────


class TestSortinoRatio:
    """Tests for compute_sortino_ratio."""

    def test_positive_sortino(self):
        """Return > risk-free with positive downside dev."""
        sortino = compute_sortino_ratio(0.12, 0.04, 0.10)
        assert sortino == pytest.approx(0.80, abs=0.01)

    def test_zero_downside(self):
        """Zero downside deviation → 0."""
        assert compute_sortino_ratio(0.10, 0.04, 0.0) == 0.0


# ── TestInformationRatio ───────────────────────────────────────────────


class TestInformationRatio:
    """Tests for compute_information_ratio."""

    def test_positive_ir(self):
        """Positive active return with tracking error."""
        ir = compute_information_ratio(0.03, 0.05)
        assert ir == pytest.approx(0.60, abs=0.01)

    def test_negative_ir(self):
        """Negative active return."""
        ir = compute_information_ratio(-0.02, 0.05)
        assert ir < 0

    def test_zero_te(self):
        """Zero tracking error → 0."""
        assert compute_information_ratio(0.03, 0.0) == 0.0


# ── TestTrackingError ──────────────────────────────────────────────────


class TestTrackingError:
    """Tests for compute_tracking_error."""

    def test_basic(self):
        """Active returns have positive tracking error."""
        active = [0.005, -0.003, 0.008, -0.002, 0.004]
        te = compute_tracking_error(active)
        assert te > 0

    def test_zero_active(self):
        """All zero active returns → 0."""
        assert compute_tracking_error([0.0, 0.0, 0.0]) == 0.0

    def test_single(self):
        """Single active return → 0."""
        assert compute_tracking_error([0.01]) == 0.0


# ── TestMaxDrawdown ────────────────────────────────────────────────────


class TestMaxDrawdown:
    """Tests for compute_max_drawdown."""

    def test_simple_drawdown(self):
        """NAV: 100 → 110 → 90 → 105 → max dd from 110 to 90."""
        dd = compute_max_drawdown([100, 110, 90, 105])
        assert dd.max_drawdown == pytest.approx(-0.1818, abs=0.01)
        assert dd.peak_value == 110
        assert dd.trough_value == 90
        assert dd.peak_index == 1
        assert dd.trough_index == 2

    def test_recovery(self):
        """Full recovery detected."""
        dd = compute_max_drawdown([100, 110, 90, 100, 115])
        assert dd.recovery_index is not None
        assert dd.recovery_index == 4

    def test_no_recovery(self):
        """No recovery when stays below peak."""
        dd = compute_max_drawdown([100, 110, 90, 100])
        assert dd.recovery_index is None

    def test_monotonic_up(self):
        """Monotonically increasing → 0 drawdown."""
        dd = compute_max_drawdown([100, 105, 110, 115, 120])
        assert dd.max_drawdown == 0.0

    def test_single_value(self):
        """Single value → 0 drawdown."""
        dd = compute_max_drawdown([100])
        assert dd.max_drawdown == 0.0

    def test_duration(self):
        """Drawdown duration tracking."""
        dd = compute_max_drawdown([100, 110, 105, 95, 90, 100, 112])
        assert dd.duration_to_trough > 0


# ── TestCalmarRatio ────────────────────────────────────────────────────


class TestCalmarRatio:
    """Tests for compute_calmar_ratio."""

    def test_positive_calmar(self):
        """10% return, -20% drawdown → 0.5."""
        calmar = compute_calmar_ratio(0.10, -0.20)
        assert calmar == pytest.approx(0.50, abs=0.01)

    def test_zero_drawdown(self):
        """Zero drawdown → 0."""
        assert compute_calmar_ratio(0.10, 0.0) == 0.0


# ── TestUpDownCapture ──────────────────────────────────────────────────


class TestUpDownCapture:
    """Tests for compute_up_down_capture."""

    def test_basic_capture(self):
        """Portfolio captures benchmark up and down moves."""
        port = [0.02, -0.015, 0.01, -0.008, 0.005]
        bench = [0.015, -0.01, 0.012, -0.005, 0.008]
        result = compute_up_down_capture(port, bench)
        assert result["up_capture"] is not None
        assert result["down_capture"] is not None

    def test_all_up_market(self):
        """All positive benchmark → down_capture is None."""
        port = [0.01, 0.02, 0.015]
        bench = [0.008, 0.015, 0.012]
        result = compute_up_down_capture(port, bench)
        assert result["up_capture"] is not None
        assert result["down_capture"] is None

    def test_length_mismatch(self):
        """Mismatched lengths → ValueError."""
        with pytest.raises(ValueError):
            compute_up_down_capture([0.01], [0.01, 0.02])


# ── TestBattingAverage ─────────────────────────────────────────────────


class TestBattingAverage:
    """Tests for compute_batting_average."""

    def test_all_outperform(self):
        """Always beat benchmark → 1.0."""
        port = [0.02, 0.03, 0.01, 0.025]
        bench = [0.01, 0.02, 0.005, 0.02]
        assert compute_batting_average(port, bench) == 1.0

    def test_never_outperform(self):
        """Never beat benchmark → 0.0."""
        port = [0.005, 0.01, 0.002]
        bench = [0.01, 0.02, 0.005]
        assert compute_batting_average(port, bench) == 0.0

    def test_half(self):
        """Win half the time."""
        port = [0.02, 0.005, 0.015, 0.002]
        bench = [0.01, 0.01, 0.01, 0.01]
        ba = compute_batting_average(port, bench)
        assert ba == pytest.approx(0.50, abs=0.01)

    def test_empty(self):
        """Empty lists → 0."""
        assert compute_batting_average([], []) == 0.0


# ── TestBeta ───────────────────────────────────────────────────────────


class TestBeta:
    """Tests for compute_beta."""

    def test_perfect_correlation(self):
        """Same returns → beta = 1.0."""
        returns = [0.01, -0.02, 0.015, -0.005, 0.008]
        beta = compute_beta(returns, returns)
        assert beta == pytest.approx(1.0, abs=0.01)

    def test_double_sensitivity(self):
        """Portfolio = 2x benchmark → beta ~ 2."""
        bench = [0.01, -0.02, 0.015, -0.005, 0.008]
        port = [r * 2 for r in bench]
        beta = compute_beta(port, bench)
        assert beta == pytest.approx(2.0, abs=0.01)

    def test_zero_bench_variance(self):
        """Zero benchmark variance → 0."""
        assert compute_beta([0.01, 0.02], [0.0, 0.0]) == 0.0

    def test_short_series(self):
        """Single return → 0."""
        assert compute_beta([0.01], [0.01]) == 0.0


# ── TestAlpha ──────────────────────────────────────────────────────────


class TestAlpha:
    """Tests for compute_alpha."""

    def test_positive_alpha(self):
        """Portfolio outperforms expected return → positive alpha."""
        alpha = compute_alpha(0.15, 0.10, 1.0, 0.04)
        # alpha = 0.15 - (0.04 + 1.0 * (0.10 - 0.04)) = 0.15 - 0.10 = 0.05
        assert alpha == pytest.approx(0.05, abs=0.001)

    def test_zero_alpha(self):
        """Portfolio matches CAPM → zero alpha."""
        alpha = compute_alpha(0.10, 0.10, 1.0, 0.04)
        assert alpha == pytest.approx(0.0, abs=0.001)

    def test_high_beta_negative_alpha(self):
        """High beta but underperforming → negative alpha."""
        alpha = compute_alpha(0.12, 0.10, 1.5, 0.04)
        # alpha = 0.12 - (0.04 + 1.5 * (0.10 - 0.04)) = 0.12 - 0.13 = -0.01
        assert alpha == pytest.approx(-0.01, abs=0.001)


# ── TestRollingReturns ─────────────────────────────────────────────────


class TestRollingReturns:
    """Tests for compute_rolling_returns."""

    def test_window_3(self):
        """Window of 3 on 5 returns → 3 rolling values."""
        returns = [0.01, 0.02, -0.01, 0.015, 0.005]
        rolling = compute_rolling_returns(returns, 3)
        assert len(rolling) == 3

    def test_window_equals_length(self):
        """Window = full length → single value = TWR."""
        returns = [0.01, 0.02, -0.01]
        rolling = compute_rolling_returns(returns, 3)
        assert len(rolling) == 1
        assert rolling[0] == pytest.approx(compute_twr(returns), abs=0.0001)

    def test_window_too_large(self):
        """Window > length → empty."""
        assert compute_rolling_returns([0.01, 0.02], 5) == []

    def test_window_zero(self):
        """Window 0 → empty."""
        assert compute_rolling_returns([0.01], 0) == []

    def test_each_value_is_geometric(self):
        """Each rolling value is a geometric product."""
        returns = [0.01, 0.02, 0.03, 0.04]
        rolling = compute_rolling_returns(returns, 2)
        assert rolling[0] == pytest.approx(1.01 * 1.02 - 1.0, abs=0.0001)
        assert rolling[1] == pytest.approx(1.02 * 1.03 - 1.0, abs=0.0001)
        assert rolling[2] == pytest.approx(1.03 * 1.04 - 1.0, abs=0.0001)


# ── TestCalendarYearReturns ────────────────────────────────────────────


class TestCalendarYearReturns:
    """Tests for compute_calendar_year_returns."""

    def test_single_year(self):
        """All data in one year."""
        data = [
            {"date": "2025-01-02", "return": 0.01},
            {"date": "2025-01-03", "return": 0.02},
            {"date": "2025-01-06", "return": -0.005},
        ]
        result = compute_calendar_year_returns(data)
        assert len(result) == 1
        assert result[0]["year"] == 2025

    def test_two_years(self):
        """Data spanning two years."""
        data = [
            {"date": "2024-12-30", "return": 0.01},
            {"date": "2024-12-31", "return": 0.005},
            {"date": "2025-01-02", "return": 0.02},
            {"date": "2025-01-03", "return": -0.01},
        ]
        result = compute_calendar_year_returns(data)
        assert len(result) == 2
        assert result[0]["year"] == 2024
        assert result[1]["year"] == 2025

    def test_empty(self):
        """Empty data → empty result."""
        assert compute_calendar_year_returns([]) == []


# ── TestStandardPeriods ────────────────────────────────────────────────


class TestStandardPeriods:
    """Tests for compute_standard_periods."""

    def test_basic_periods(self):
        """All standard periods are returned."""
        data = [
            {"date": f"2025-{m:02d}-15", "return": 0.005}
            for m in range(1, 13)
        ]
        result = compute_standard_periods(data, "2025-12-31")
        assert "mtd" in result
        assert "qtd" in result
        assert "ytd" in result
        assert "1m" in result
        assert "3m" in result
        assert "6m" in result
        assert "1y" in result
        assert "si" in result

    def test_si_covers_all(self):
        """Since-inception = full geometric link."""
        data = [
            {"date": "2025-01-02", "return": 0.01},
            {"date": "2025-01-03", "return": 0.02},
            {"date": "2025-01-06", "return": -0.005},
        ]
        result = compute_standard_periods(data, "2025-01-06")
        expected_si = 1.01 * 1.02 * 0.995 - 1.0
        assert result["si"] == pytest.approx(expected_si, abs=0.0001)

    def test_empty(self):
        """Empty data → all zeros."""
        result = compute_standard_periods([], "2025-06-15")
        assert result["si"] == 0.0
        assert result["ytd"] == 0.0


# ── TestBuildPerformanceSummary ────────────────────────────────────────


class TestBuildPerformanceSummary:
    """Tests for build_performance_summary orchestrator."""

    def _make_nav_history(self, n_days: int = 252) -> list[dict]:
        """Generate synthetic NAV history."""
        import random
        random.seed(42)
        nav = 100000.0
        history = [{"date": "2024-01-02", "nav": nav}]
        for i in range(1, n_days):
            day_num = i
            month = (day_num // 21) + 1
            day = (day_num % 21) + 2
            if month > 12:
                month = 12
                day = min(day, 28)
            ret = random.gauss(0.0004, 0.01)
            nav *= (1 + ret)
            history.append({
                "date": f"2024-{month:02d}-{day:02d}",
                "nav": nav,
            })
        return history

    def test_basic_summary(self):
        """Build summary without benchmark."""
        nav_history = self._make_nav_history(100)
        summary = build_performance_summary(nav_history)
        assert isinstance(summary, PerformanceSummary)
        assert isinstance(summary.risk_metrics, RiskMetrics)
        assert isinstance(summary.drawdown, DrawdownAnalysis)
        assert summary.positive_days + summary.negative_days <= 99

    def test_with_benchmark(self):
        """Build summary with benchmark populates benchmark metrics."""
        nav_history = self._make_nav_history(50)
        bench_history = self._make_nav_history(50)
        summary = build_performance_summary(nav_history, bench_history)
        assert summary.benchmark_return is not None
        assert summary.active_return is not None
        assert summary.risk_metrics.beta is not None
        assert summary.risk_metrics.alpha is not None
        assert summary.risk_metrics.information_ratio is not None
        assert summary.risk_metrics.tracking_error is not None
        assert summary.risk_metrics.up_capture is not None or summary.risk_metrics.down_capture is not None
        assert summary.risk_metrics.batting_average is not None

    def test_with_cash_flows(self):
        """Build summary with cash flows → MWR populated."""
        nav_history = self._make_nav_history(50)
        cash_flows = [
            {"date_offset": 0, "amount": -100000.0},
            {"date_offset": 25, "amount": -10000.0},
        ]
        summary = build_performance_summary(
            nav_history, cash_flows=cash_flows,
        )
        assert summary.mwr_return is not None

    def test_day_stats(self):
        """Positive/negative day counts and best/worst day."""
        nav_history = self._make_nav_history(50)
        summary = build_performance_summary(nav_history)
        assert summary.positive_days >= 0
        assert summary.negative_days >= 0
        assert summary.best_day >= summary.worst_day

    def test_short_history(self):
        """Very short history (2 days) doesn't crash."""
        nav_history = [
            {"date": "2025-01-02", "nav": 100000.0},
            {"date": "2025-01-03", "nav": 101000.0},
        ]
        summary = build_performance_summary(nav_history)
        assert summary.twr_return == pytest.approx(0.01, abs=0.001)
