"""Tests for the Revenue Drivers Engine (per-segment growth decomposition)."""

import math

from src.engines.revenue_drivers_engine import (
    RevenueDriver,
    RevenueDriversResult,
    analyze_revenue_drivers,
    compute_revenue_concentration_hhi,
    compute_revenue_drivers,
    compute_total_revenue_growth,
)


def _driver_by_name(drivers: list[RevenueDriver], name: str) -> RevenueDriver:
    for d in drivers:
        if d.segment_name == name:
            return d
    raise AssertionError(f"segment {name!r} not found in drivers: {[d.segment_name for d in drivers]}")


# ── Realistic 3-period, 3-segment fixture ───────────────────────────────
#
# SegA: growing 100 -> 150 -> 225 (50% YoY each step)
# SegB: shrinking 100 -> 70 -> 40 (-30%, then -42.857% YoY)
# SegC: flat 100 -> 102 -> 104 (~2% and ~1.96% YoY)
# total_revenue == sum of the three segments in every period (no other
# segments/geo noise), so contribution-to-growth percentages sum to 100%.

SEGMENT_HISTORY_3P = [
    {
        "period_end_date": "2021-12-31",
        "segments": [
            {"name": "SegA", "type": "BUSINESS", "revenue": 100.0},
            {"name": "SegB", "type": "BUSINESS", "revenue": 100.0},
            {"name": "SegC", "type": "BUSINESS", "revenue": 100.0},
        ],
    },
    {
        "period_end_date": "2022-12-31",
        "segments": [
            {"name": "SegA", "type": "BUSINESS", "revenue": 150.0},
            {"name": "SegB", "type": "BUSINESS", "revenue": 70.0},
            {"name": "SegC", "type": "BUSINESS", "revenue": 102.0},
        ],
    },
    {
        "period_end_date": "2023-12-31",
        "segments": [
            {"name": "SegA", "type": "BUSINESS", "revenue": 225.0},
            {"name": "SegB", "type": "BUSINESS", "revenue": 40.0},
            {"name": "SegC", "type": "BUSINESS", "revenue": 104.0},
        ],
    },
]

TOTAL_REVENUE_3P = [300.0, 322.0, 369.0]  # 100+100+100, 150+70+102, 225+40+104


class TestComputeRevenueDrivers:
    """Tests for compute_revenue_drivers() with the 3-segment fixture."""

    def test_yoy_growth_rates(self):
        drivers = compute_revenue_drivers(SEGMENT_HISTORY_3P, TOTAL_REVENUE_3P)
        seg_a = _driver_by_name(drivers, "SegA")
        seg_b = _driver_by_name(drivers, "SegB")
        seg_c = _driver_by_name(drivers, "SegC")

        assert seg_a.yoy_growth_pct == round((225.0 - 150.0) / 150.0 * 100.0, 4)
        assert seg_a.yoy_growth_pct == 50.0

        assert seg_b.yoy_growth_pct == round((40.0 - 70.0) / 70.0 * 100.0, 4)
        assert math.isclose(seg_b.yoy_growth_pct, -42.857143, abs_tol=1e-4)

        assert seg_c.yoy_growth_pct == round((104.0 - 102.0) / 102.0 * 100.0, 4)
        assert math.isclose(seg_c.yoy_growth_pct, 1.960784, abs_tol=1e-4)

    def test_revenue_share_pct(self):
        drivers = compute_revenue_drivers(SEGMENT_HISTORY_3P, TOTAL_REVENUE_3P)
        seg_a = _driver_by_name(drivers, "SegA")
        seg_b = _driver_by_name(drivers, "SegB")
        seg_c = _driver_by_name(drivers, "SegC")

        assert seg_a.latest_revenue == 225.0
        assert seg_a.revenue_share_pct == round(225.0 / 369.0 * 100.0, 4)
        assert seg_b.revenue_share_pct == round(40.0 / 369.0 * 100.0, 4)
        assert seg_c.revenue_share_pct == round(104.0 / 369.0 * 100.0, 4)

        # Shares should sum to ~100% since total == sum of segments.
        total_share = seg_a.revenue_share_pct + seg_b.revenue_share_pct + seg_c.revenue_share_pct
        assert math.isclose(total_share, 100.0, abs_tol=1e-3)

    def test_contribution_to_growth(self):
        drivers = compute_revenue_drivers(SEGMENT_HISTORY_3P, TOTAL_REVENUE_3P)
        seg_a = _driver_by_name(drivers, "SegA")
        seg_b = _driver_by_name(drivers, "SegB")
        seg_c = _driver_by_name(drivers, "SegC")

        # denom = total_latest(369) - total_prior(322) = 47
        denom = 369.0 - 322.0
        assert denom == 47.0

        expected_a = round((225.0 - 150.0) / denom * 100.0, 4)
        expected_b = round((40.0 - 70.0) / denom * 100.0, 4)
        expected_c = round((104.0 - 102.0) / denom * 100.0, 4)

        assert seg_a.contribution_to_growth_pct == expected_a
        assert math.isclose(expected_a, 159.5745, abs_tol=1e-3)

        assert seg_b.contribution_to_growth_pct == expected_b
        assert math.isclose(expected_b, -63.8298, abs_tol=1e-3)

        assert seg_c.contribution_to_growth_pct == expected_c
        assert math.isclose(expected_c, 4.2553, abs_tol=1e-3)

        # Contributions should sum to ~100% (segments == entire total revenue).
        total_contribution = (
            seg_a.contribution_to_growth_pct
            + seg_b.contribution_to_growth_pct
            + seg_c.contribution_to_growth_pct
        )
        assert math.isclose(total_contribution, 100.0, abs_tol=1e-2)

    def test_cagr(self):
        drivers = compute_revenue_drivers(SEGMENT_HISTORY_3P, TOTAL_REVENUE_3P)
        seg_a = _driver_by_name(drivers, "SegA")
        seg_b = _driver_by_name(drivers, "SegB")
        seg_c = _driver_by_name(drivers, "SegC")

        # 3 periods spanning 2 year-over-year intervals -> CAGR computable.
        assert seg_a.cagr_pct == round(((225.0 / 100.0) ** (1 / 2) - 1) * 100.0, 4)
        assert seg_a.cagr_pct == 50.0  # sqrt(2.25) - 1 == 0.5 exactly

        assert seg_b.cagr_pct == round(((40.0 / 100.0) ** (1 / 2) - 1) * 100.0, 4)
        assert math.isclose(seg_b.cagr_pct, -36.7544, abs_tol=1e-3)

        assert seg_c.cagr_pct == round(((104.0 / 100.0) ** (1 / 2) - 1) * 100.0, 4)
        assert math.isclose(seg_c.cagr_pct, 1.9804, abs_tol=1e-3)

    def test_classification(self):
        drivers = compute_revenue_drivers(SEGMENT_HISTORY_3P, TOTAL_REVENUE_3P)
        seg_a = _driver_by_name(drivers, "SegA")
        seg_b = _driver_by_name(drivers, "SegB")
        seg_c = _driver_by_name(drivers, "SegC")

        assert seg_a.classification == "GROWTH_DRIVER"  # yoy 50% > 5%, positive contribution
        assert seg_b.classification == "DRAG"  # yoy -42.9% < -5%
        assert seg_c.classification == "STABLE"  # yoy ~2%, small positive contribution

    def test_ranked_by_absolute_contribution_descending(self):
        drivers = compute_revenue_drivers(SEGMENT_HISTORY_3P, TOTAL_REVENUE_3P)
        names_in_order = [d.segment_name for d in drivers]
        # |159.57| > |63.83| > |4.26|
        assert names_in_order == ["SegA", "SegB", "SegC"]

    def test_hhi(self):
        hhi = compute_revenue_concentration_hhi(SEGMENT_HISTORY_3P, TOTAL_REVENUE_3P)
        share_a = 225.0 / 369.0 * 100.0
        share_b = 40.0 / 369.0 * 100.0
        share_c = 104.0 / 369.0 * 100.0
        expected = round(share_a**2 + share_b**2 + share_c**2, 4)
        assert hhi == expected
        # Sanity: HHI on 0-10000 scale, dominated by SegA's ~61% share.
        assert 4000.0 < hhi < 5000.0

    def test_total_revenue_growth(self):
        growth = compute_total_revenue_growth(TOTAL_REVENUE_3P)
        expected = round((369.0 - 322.0) / 322.0 * 100.0, 4)
        assert growth == expected
        assert math.isclose(growth, 14.5963, abs_tol=1e-3)


class TestSegmentPresentInOnlyOnePeriod:
    """A segment appearing in only 1 of 3 periods must not get fabricated growth."""

    def test_insufficient_data_no_fabricated_growth(self):
        history = [
            {
                "period_end_date": "2021-12-31",
                "segments": [
                    {"name": "SegA", "type": "BUSINESS", "revenue": 100.0},
                ],
            },
            {
                "period_end_date": "2022-12-31",
                "segments": [
                    {"name": "SegA", "type": "BUSINESS", "revenue": 110.0},
                ],
            },
            {
                "period_end_date": "2023-12-31",
                "segments": [
                    {"name": "SegA", "type": "BUSINESS", "revenue": 120.0},
                    {"name": "NewSegment", "type": "BUSINESS", "revenue": 30.0},
                ],
            },
        ]
        total_revenue = [100.0, 110.0, 150.0]

        drivers = compute_revenue_drivers(history, total_revenue)
        new_seg = _driver_by_name(drivers, "NewSegment")

        assert new_seg.classification == "INSUFFICIENT_DATA"
        assert new_seg.yoy_growth_pct is None
        assert new_seg.cagr_pct is None
        assert new_seg.contribution_to_growth_pct is None
        # Latest revenue and share are still knowable even without growth.
        assert new_seg.latest_revenue == 30.0
        assert new_seg.revenue_share_pct == round(30.0 / 150.0 * 100.0, 4)

        # SegA has 3 populated periods -> growth IS computable.
        seg_a = _driver_by_name(drivers, "SegA")
        assert seg_a.yoy_growth_pct is not None
        assert seg_a.classification != "INSUFFICIENT_DATA"


class TestNoneRevenueSkipped:
    """None revenue entries must be skipped, not treated as 0."""

    def test_none_revenue_skipped_not_zero(self):
        history = [
            {
                "period_end_date": "2021-12-31",
                "segments": [
                    {"name": "SegA", "type": "BUSINESS", "revenue": 100.0},
                ],
            },
            {
                "period_end_date": "2022-12-31",
                "segments": [
                    # Reported but revenue not populated this period.
                    {"name": "SegA", "type": "BUSINESS", "revenue": None},
                ],
            },
            {
                "period_end_date": "2023-12-31",
                "segments": [
                    {"name": "SegA", "type": "BUSINESS", "revenue": 225.0},
                ],
            },
        ]
        total_revenue = [100.0, 110.0, 369.0]

        drivers = compute_revenue_drivers(history, total_revenue)
        seg_a = _driver_by_name(drivers, "SegA")

        # YoY growth should skip the None period and compare period0 vs period2,
        # NOT treat the None as 0 (which would show an enormous fake growth
        # from a near-zero denominator, or a negative-then-positive swing).
        expected_yoy = round((225.0 - 100.0) / 100.0 * 100.0, 4)
        assert seg_a.yoy_growth_pct == expected_yoy
        assert seg_a.yoy_growth_pct == 125.0

        # Contribution should use the SAME two populated periods (0 and 2),
        # with total_revenue at those same indices: 369 - 100 = 269.
        expected_contribution = round((225.0 - 100.0) / (369.0 - 100.0) * 100.0, 4)
        assert seg_a.contribution_to_growth_pct == expected_contribution


class TestGeographicSegmentsExcluded:
    """GEOGRAPHIC segments must never appear in drivers, even if present in input."""

    def test_geographic_excluded_from_drivers(self):
        history = [
            {
                "period_end_date": "2022-12-31",
                "segments": [
                    {"name": "iPhone", "type": "BUSINESS", "revenue": 200.0},
                    {"name": "Americas", "type": "GEOGRAPHIC", "revenue": 150.0},
                    {"name": "Europe", "type": "GEOGRAPHIC", "revenue": 100.0},
                ],
            },
            {
                "period_end_date": "2023-12-31",
                "segments": [
                    {"name": "iPhone", "type": "BUSINESS", "revenue": 220.0},
                    {"name": "Americas", "type": "GEOGRAPHIC", "revenue": 160.0},
                    {"name": "Europe", "type": "GEOGRAPHIC", "revenue": 110.0},
                ],
            },
        ]
        total_revenue = [250.0, 270.0]

        drivers = compute_revenue_drivers(history, total_revenue)
        names = [d.segment_name for d in drivers]

        assert "Americas" not in names
        assert "Europe" not in names
        assert names == ["iPhone"]

        # HHI is also computed only from BUSINESS segments.
        hhi = compute_revenue_concentration_hhi(history, total_revenue)
        # Only one BUSINESS segment -> fewer than 2 shares -> None.
        assert hhi is None


class TestAnalyzeRevenueDriversOrchestrator:
    """Tests for the analyze_revenue_drivers() orchestrator."""

    def test_full_fixture(self):
        result = analyze_revenue_drivers(SEGMENT_HISTORY_3P, TOTAL_REVENUE_3P)
        assert isinstance(result, RevenueDriversResult)
        assert len(result.drivers) == 3
        assert result.periods_analyzed == 3
        assert result.revenue_concentration_hhi is not None
        assert result.total_revenue_yoy_growth_pct is not None
        assert result.drivers[0].segment_name == "SegA"  # biggest mover first

    def test_empty_segment_history(self):
        result = analyze_revenue_drivers([], [])
        assert isinstance(result, RevenueDriversResult)
        assert result.drivers == []
        assert result.revenue_concentration_hhi is None
        assert result.total_revenue_yoy_growth_pct is None
        assert result.periods_analyzed == 0

    def test_empty_segment_history_default_total_revenue(self):
        """Orchestrator must not crash when total_revenue_history is omitted."""
        result = analyze_revenue_drivers([])
        assert isinstance(result, RevenueDriversResult)
        assert result.drivers == []

    def test_single_period_all_insufficient_data(self):
        history = [
            {
                "period_end_date": "2023-12-31",
                "segments": [
                    {"name": "SegA", "type": "BUSINESS", "revenue": 100.0},
                    {"name": "SegB", "type": "BUSINESS", "revenue": 50.0},
                ],
            },
        ]
        total_revenue = [150.0]

        result = analyze_revenue_drivers(history, total_revenue)
        assert isinstance(result, RevenueDriversResult)
        assert result.periods_analyzed == 1
        assert len(result.drivers) == 2
        for driver in result.drivers:
            assert driver.classification == "INSUFFICIENT_DATA"
            assert driver.yoy_growth_pct is None
            assert driver.cagr_pct is None
            assert driver.contribution_to_growth_pct is None
            # Latest revenue/share still known from the single period.
            assert driver.latest_revenue is not None
            assert driver.revenue_share_pct is not None

        # No prior period -> no company-wide growth figure either.
        assert result.total_revenue_yoy_growth_pct is None
