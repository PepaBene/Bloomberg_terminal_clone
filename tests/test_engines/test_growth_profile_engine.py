"""Tests for the Growth Profile & Operating Leverage Engine."""

import pytest

from src.engines.growth_profile_engine import (
    GROWTH_METRICS,
    GrowthProfileResult,
    GrowthSeries,
    OperatingLeverageDetail,
    analyze_growth_profile,
    analyze_growth_series,
    compute_operating_leverage_detail,
)


# ── Growth Series Tests ──────────────────────────────────────────────────


class TestAnalyzeGrowthSeries:
    """Tests for analyze_growth_series()."""

    def test_steadily_accelerating_revenue_growth(self):
        """5 periods of steadily accelerating revenue growth -> ACCELERATING trend."""
        history = [
            {"period_end_date": "2021-12-31", "revenue": 100.0},
            {"period_end_date": "2022-12-31", "revenue": 110.0},
            {"period_end_date": "2023-12-31", "revenue": 125.0},
            {"period_end_date": "2024-12-31", "revenue": 145.0},
            {"period_end_date": "2025-12-31", "revenue": 175.0},
        ]
        result = analyze_growth_series(history, "revenue")
        assert isinstance(result, GrowthSeries)
        assert result.metric == "revenue"

        # Latest YoY: (175 - 145) / 145 * 100
        expected_yoy = (175.0 - 145.0) / 145.0 * 100.0
        assert result.latest_yoy_growth_pct == pytest.approx(expected_yoy, abs=1e-4)

        # CAGR: ((175/100) ** (1/4) - 1) * 100  (4 periods analyzed, n_periods = 4 intervals)
        expected_cagr = ((175.0 / 100.0) ** (1.0 / 4.0) - 1.0) * 100.0
        assert result.cagr_pct == pytest.approx(expected_cagr, abs=1e-4)

        # Hand-computed consecutive growth rates (%)
        growth_rates = [
            (110.0 - 100.0) / 100.0 * 100.0,
            (125.0 - 110.0) / 110.0 * 100.0,
            (145.0 - 125.0) / 125.0 * 100.0,
            (175.0 - 145.0) / 145.0 * 100.0,
        ]
        mean = sum(growth_rates) / len(growth_rates)
        variance = sum((r - mean) ** 2 for r in growth_rates) / (len(growth_rates) - 1)
        expected_volatility = variance**0.5
        assert result.growth_volatility == pytest.approx(expected_volatility, abs=1e-3)

        assert result.growth_trend == "ACCELERATING"
        assert result.positive_growth_period_pct == 100.0

    def test_loss_making_earliest_period_skips_cagr(self):
        """Net income going from loss to profit -> CAGR undefined, no crash."""
        history = [
            {"period_end_date": "2022-12-31", "net_income": -50.0},
            {"period_end_date": "2023-12-31", "net_income": -20.0},
            {"period_end_date": "2024-12-31", "net_income": 30.0},
            {"period_end_date": "2025-12-31", "net_income": 60.0},
        ]
        result = analyze_growth_series(history, "net_income")
        assert result.cagr_pct is None
        # Latest YoY still computable: (60 - 30) / 30 * 100
        assert result.latest_yoy_growth_pct == pytest.approx(100.0, abs=1e-4)
        # No crash, volatility/trend still computed from valid growth rates.
        assert result.growth_volatility is not None
        assert result.growth_trend in ("ACCELERATING", "DECELERATING", "STABLE", "UNKNOWN")

    def test_two_periods_only_yoy_computable(self):
        """Only 2 periods -> only latest YoY, CAGR None, trend UNKNOWN."""
        history = [
            {"period_end_date": "2024-12-31", "revenue": 100.0},
            {"period_end_date": "2025-12-31", "revenue": 120.0},
        ]
        result = analyze_growth_series(history, "revenue")
        assert result.latest_yoy_growth_pct == pytest.approx(20.0, abs=1e-4)
        assert result.cagr_pct is None
        assert result.growth_trend == "UNKNOWN"
        # A single growth rate -> positive_growth_period_pct computable, volatility not (needs >=2).
        assert result.positive_growth_period_pct == 100.0
        assert result.growth_volatility is None

    def test_missing_key_in_one_period_skipped_gracefully(self):
        """A period missing the target metric key is excluded, not substituted with 0."""
        history = [
            {"period_end_date": "2023-12-31", "revenue": 100.0, "eps": 1.0},
            {"period_end_date": "2024-12-31", "revenue": 110.0},  # no eps key at all
            {"period_end_date": "2025-12-31", "revenue": 125.0, "eps": 1.5},
        ]
        eps_result = analyze_growth_series(history, "eps")
        # Only 2 real eps data points (period 1 and period 3) -> YoY uses those, no crash.
        assert eps_result.latest_yoy_growth_pct == pytest.approx(50.0, abs=1e-4)
        assert eps_result.cagr_pct is None  # only 2 valid points

        # Revenue series is unaffected by eps being missing.
        revenue_result = analyze_growth_series(history, "revenue")
        assert revenue_result.latest_yoy_growth_pct == pytest.approx(
            (125.0 - 110.0) / 110.0 * 100.0, abs=1e-4
        )

    def test_none_value_treated_same_as_missing(self):
        """An explicit None value for the metric is skipped, not fabricated as 0."""
        history = [
            {"period_end_date": "2023-12-31", "fcf": 10.0},
            {"period_end_date": "2024-12-31", "fcf": None},
            {"period_end_date": "2025-12-31", "fcf": 15.0},
        ]
        result = analyze_growth_series(history, "fcf")
        assert result.latest_yoy_growth_pct == pytest.approx(50.0, abs=1e-4)


# ── Operating Leverage Detail Tests ──────────────────────────────────────


class TestComputeOperatingLeverageDetail:
    """Tests for compute_operating_leverage_detail()."""

    def test_near_zero_revenue_change_pair_skipped(self):
        """A pair with ~0% revenue change is excluded, not a divide-by-near-zero blowup."""
        history = [
            {"period_end_date": "2023-12-31", "revenue": 1000.0, "ebit": 100.0},
            {"period_end_date": "2024-12-31", "revenue": 1000.5, "ebit": 110.0},  # ~0% rev change
            {"period_end_date": "2025-12-31", "revenue": 1200.0, "ebit": 150.0},
        ]
        result = compute_operating_leverage_detail(history)
        assert isinstance(result, OperatingLeverageDetail)

        # Only the second pair (period 2 -> period 3) produces a valid op-leverage point.
        assert len(result.operating_leverage_trend) == 1
        assert result.operating_leverage_trend[0]["period_end_date"] == "2025-12-31"

        rev_change = (1200.0 - 1000.5) / 1000.5
        ebit_change = (150.0 - 110.0) / 110.0
        expected_op_lev = round(ebit_change / rev_change, 4)
        assert result.operating_leverage_trend[0]["operating_leverage"] == pytest.approx(
            expected_op_lev, abs=1e-3
        )
        assert result.avg_operating_leverage == pytest.approx(expected_op_lev, abs=1e-3)
        # Only 1 valid value -> stdev undefined, stability None.
        assert result.operating_leverage_stability is None

    def test_multi_period_trend_and_stability(self):
        """Multiple valid pairs -> avg and stability (stdev) computed."""
        history = [
            {"period_end_date": "2022-12-31", "revenue": 1000.0, "ebit": 100.0},
            {"period_end_date": "2023-12-31", "revenue": 1100.0, "ebit": 120.0},
            {"period_end_date": "2024-12-31", "revenue": 1210.0, "ebit": 150.0},
            {"period_end_date": "2025-12-31", "revenue": 1331.0, "ebit": 170.0},
        ]
        result = compute_operating_leverage_detail(history)
        assert len(result.operating_leverage_trend) == 3
        assert len(result.incremental_margin_trend) == 3
        assert result.avg_operating_leverage is not None
        assert result.operating_leverage_stability is not None
        # Dates on trend points are the newer period in the pair.
        assert [p["period_end_date"] for p in result.operating_leverage_trend] == [
            "2023-12-31",
            "2024-12-31",
            "2025-12-31",
        ]

    def test_insufficient_history_empty_trends(self):
        """Fewer than 2 periods -> empty trends, no averages."""
        result = compute_operating_leverage_detail([{"revenue": 500.0, "ebit": 50.0}])
        assert result.operating_leverage_trend == []
        assert result.incremental_margin_trend == []
        assert result.avg_operating_leverage is None
        assert result.operating_leverage_stability is None

    def test_missing_ebit_pair_skipped(self):
        """A pair missing ebit on either side is skipped gracefully, not crashed."""
        history = [
            {"period_end_date": "2023-12-31", "revenue": 1000.0, "ebit": 100.0},
            {"period_end_date": "2024-12-31", "revenue": 1100.0},  # no ebit
            {"period_end_date": "2025-12-31", "revenue": 1200.0, "ebit": 150.0},
        ]
        result = compute_operating_leverage_detail(history)
        # Both pairs touch the ebit-less period, so neither produces a trend point.
        assert result.operating_leverage_trend == []
        assert result.incremental_margin_trend == []


# ── Orchestrator Tests ───────────────────────────────────────────────────


class TestAnalyzeGrowthProfile:
    """Tests for analyze_growth_profile()."""

    def test_full_multi_period_history(self):
        """A realistic 5-period history produces all four growth series plus op-leverage detail."""
        history = [
            {
                "period_end_date": "2021-12-31",
                "revenue": 100.0,
                "net_income": 10.0,
                "ebit": 15.0,
                "ebitda": 20.0,
                "eps": 1.0,
                "fcf": 8.0,
            },
            {
                "period_end_date": "2022-12-31",
                "revenue": 110.0,
                "net_income": 12.0,
                "ebit": 18.0,
                "ebitda": 24.0,
                "eps": 1.2,
                "fcf": 9.0,
            },
            {
                "period_end_date": "2023-12-31",
                "revenue": 125.0,
                "net_income": 15.0,
                "ebit": 22.0,
                "ebitda": 29.0,
                "eps": 1.5,
                "fcf": 11.0,
            },
            {
                "period_end_date": "2024-12-31",
                "revenue": 145.0,
                "net_income": 19.0,
                "ebit": 27.0,
                "ebitda": 35.0,
                "eps": 1.9,
                "fcf": 14.0,
            },
            {
                "period_end_date": "2025-12-31",
                "revenue": 175.0,
                "net_income": 25.0,
                "ebit": 34.0,
                "ebitda": 44.0,
                "eps": 2.5,
                "fcf": 18.0,
            },
        ]
        result = analyze_growth_profile(history)
        assert isinstance(result, GrowthProfileResult)
        assert result.periods_analyzed == 5
        assert [s.metric for s in result.growth_series] == list(GROWTH_METRICS)
        for series in result.growth_series:
            assert series.latest_yoy_growth_pct is not None
            assert series.cagr_pct is not None

        assert isinstance(result.operating_leverage, OperatingLeverageDetail)
        assert len(result.operating_leverage.operating_leverage_trend) == 4
        assert result.operating_leverage.avg_operating_leverage is not None

    def test_empty_history_returns_graceful_empty_result(self):
        """Empty history -> valid result with all fields gracefully empty/None, no crash."""
        result = analyze_growth_profile([])
        assert isinstance(result, GrowthProfileResult)
        assert result.periods_analyzed == 0
        assert len(result.growth_series) == 4
        for series in result.growth_series:
            assert series.latest_yoy_growth_pct is None
            assert series.cagr_pct is None
            assert series.growth_volatility is None
            assert series.growth_trend == "UNKNOWN"
            assert series.positive_growth_period_pct is None

        assert result.operating_leverage.avg_operating_leverage is None
        assert result.operating_leverage.operating_leverage_stability is None
        assert result.operating_leverage.operating_leverage_trend == []
        assert result.operating_leverage.incremental_margin_trend == []

    def test_two_period_history_orchestrator(self):
        """2-period history end-to-end: only YoY, no CAGR, UNKNOWN trend."""
        history = [
            {"period_end_date": "2024-12-31", "revenue": 100.0, "ebit": 10.0},
            {"period_end_date": "2025-12-31", "revenue": 120.0, "ebit": 15.0},
        ]
        result = analyze_growth_profile(history)
        assert result.periods_analyzed == 2
        revenue_series = result.growth_series[0]
        assert revenue_series.metric == "revenue"
        assert revenue_series.latest_yoy_growth_pct == pytest.approx(20.0, abs=1e-4)
        assert revenue_series.cagr_pct is None
        assert revenue_series.growth_trend == "UNKNOWN"

        # net_income/eps/fcf all missing entirely -> gracefully None, no crash.
        for series in result.growth_series[1:]:
            assert series.latest_yoy_growth_pct is None
            assert series.cagr_pct is None

        assert len(result.operating_leverage.operating_leverage_trend) == 1
