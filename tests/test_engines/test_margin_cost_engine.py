"""Tests for margin trend and cost-structure analysis (margin_cost_engine.py)."""

from src.engines.margin_cost_engine import (
    CostLineItem,
    CostStructureResult,
    MarginAnalysisResult,
    MarginMetric,
    analyze_cost_structure,
    analyze_margin_trends,
)


class TestAnalyzeMarginTrends:
    def test_expanding_margins_multi_period(self):
        history = [
            {"revenue": 100.0, "cogs": 60.0, "operating_income": 10.0, "net_income": 7.0},
            {"revenue": 120.0, "cogs": 66.0, "operating_income": 15.0, "net_income": 10.0},
            {"revenue": 140.0, "cogs": 70.0, "operating_income": 22.0, "net_income": 16.0},
            {"revenue": 160.0, "cogs": 76.8, "operating_income": 30.0, "net_income": 22.0},
        ]
        result = analyze_margin_trends(history)
        assert isinstance(result, MarginAnalysisResult)
        assert result.periods_analyzed == 4
        by_metric = {m.metric: m for m in result.margins}

        gm = by_metric["gross_margin"]
        assert gm.current_pct == round((160.0 - 76.8) / 160.0 * 100, 2)
        assert gm.prior_pct == round((140.0 - 70.0) / 140.0 * 100, 2)
        assert gm.five_year_avg_pct is not None  # 4 periods meets the min
        assert gm.trend in ("EXPANDING", "STABLE")

        om = by_metric["operating_margin"]
        assert om.current_pct == round(30.0 / 160.0 * 100, 2)
        assert om.trend == "EXPANDING"

        nm = by_metric["net_margin"]
        assert nm.current_pct == round(22.0 / 160.0 * 100, 2)

    def test_uses_precomputed_gross_margin_field_when_present(self):
        history = [
            {"revenue": 100.0, "gross_margin": 45.0, "operating_income": 10.0},
            {"revenue": 110.0, "gross_margin": 47.5, "operating_income": 12.0},
        ]
        result = analyze_margin_trends(history)
        gm = next(m for m in result.margins if m.metric == "gross_margin")
        assert gm.current_pct == 47.5
        assert gm.prior_pct == 45.0

    def test_five_year_avg_none_below_minimum_periods(self):
        history = [
            {"revenue": 100.0, "cogs": 60.0},
            {"revenue": 110.0, "cogs": 64.0},
        ]
        result = analyze_margin_trends(history)
        gm = next(m for m in result.margins if m.metric == "gross_margin")
        assert gm.five_year_avg_pct is None

    def test_missing_fields_skip_that_margin_only(self):
        history = [
            {"revenue": 100.0, "cogs": 60.0},  # no operating_income/net_income
            {"revenue": 110.0, "cogs": 64.0},
        ]
        result = analyze_margin_trends(history)
        by_metric = {m.metric: m for m in result.margins}
        assert by_metric["gross_margin"].current_pct is not None
        assert by_metric["operating_margin"].current_pct is None
        assert by_metric["operating_margin"].trend == "UNKNOWN"
        assert by_metric["net_margin"].current_pct is None

    def test_empty_history(self):
        result = analyze_margin_trends([])
        assert result == MarginAnalysisResult(margins=[], periods_analyzed=0)

    def test_zero_revenue_period_skipped_not_treated_as_zero(self):
        history = [
            {"revenue": 0.0, "cogs": 5.0},
            {"revenue": 100.0, "cogs": 60.0},
        ]
        result = analyze_margin_trends(history)
        gm = next(m for m in result.margins if m.metric == "gross_margin")
        # Only 1 usable period -> no prior_pct.
        assert gm.prior_pct is None
        assert gm.current_pct == 40.0


class TestAnalyzeCostStructure:
    def test_rising_and_falling_cost_lines(self):
        history = [
            {"revenue": 100.0, "cogs": 60.0, "sga": 20.0, "rd": 5.0},
            {"revenue": 120.0, "cogs": 78.0, "sga": 18.0, "rd": 9.6},
        ]
        result = analyze_cost_structure(history)
        assert isinstance(result, CostStructureResult)
        assert result.periods_analyzed == 2
        by_cat = {i.category: i for i in result.items}

        cogs = by_cat["COGS"]
        assert cogs.pct_of_revenue == 65.0
        assert cogs.prior_pct_of_revenue == 60.0
        assert cogs.trend == "RISING"

        sga = by_cat["SG&A"]
        assert sga.pct_of_revenue == 15.0
        assert sga.prior_pct_of_revenue == 20.0
        assert sga.trend == "FALLING"

        rd = by_cat["R&D"]
        assert rd.pct_of_revenue == 8.0
        assert rd.trend == "RISING"

    def test_stable_within_half_point_band(self):
        history = [
            {"revenue": 100.0, "cogs": 60.0},
            {"revenue": 100.0, "cogs": 60.3},
        ]
        result = analyze_cost_structure(history)
        cogs = next(i for i in result.items if i.category == "COGS")
        assert cogs.trend == "STABLE"

    def test_missing_rd_field_yields_unknown_for_that_line_only(self):
        history = [
            {"revenue": 100.0, "cogs": 60.0, "sga": 20.0},
            {"revenue": 110.0, "cogs": 64.0, "sga": 21.0},
        ]
        result = analyze_cost_structure(history)
        rd = next(i for i in result.items if i.category == "R&D")
        assert rd.pct_of_revenue is None
        assert rd.trend == "UNKNOWN"
        cogs = next(i for i in result.items if i.category == "COGS")
        assert cogs.pct_of_revenue is not None

    def test_empty_history(self):
        result = analyze_cost_structure([])
        assert result == CostStructureResult(items=[], periods_analyzed=0)

    def test_single_period_no_prior(self):
        history = [{"revenue": 100.0, "cogs": 60.0, "sga": 20.0, "rd": 5.0}]
        result = analyze_cost_structure(history)
        cogs = next(i for i in result.items if i.category == "COGS")
        assert cogs.pct_of_revenue == 60.0
        assert cogs.prior_pct_of_revenue is None
        assert cogs.trend == "UNKNOWN"


class TestDataclassDefaults:
    def test_margin_metric_defaults(self):
        m = MarginMetric(metric="gross_margin")
        assert m.current_pct is None
        assert m.trend == "UNKNOWN"

    def test_cost_line_item_defaults(self):
        c = CostLineItem(category="COGS")
        assert c.pct_of_revenue is None
        assert c.trend == "UNKNOWN"
