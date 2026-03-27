"""Tests for Pillar 3 Phase 3A — Industry Economics Engine."""

import pytest

from src.engines.industry_economics import (
    CompanyIndustryPosition,
    IndustryEconomics,
    classify_capital_cycle,
    compare_industries,
    compute_cagr,
    compute_dispersion,
    compute_industry_economics,
    compute_median,
    compute_percentile,
    rank_companies_in_industry,
)


# ── CAGR Tests ───────────────────────────────────────────────────────────


class TestComputeCagr:
    """Tests for compute_cagr()."""

    def test_positive_growth(self):
        """100 -> 200 over 5 years ~ 14.87%."""
        result = compute_cagr(100.0, 200.0, 5.0)
        assert abs(result - 0.1487) < 0.001

    def test_decline(self):
        """200 -> 100 over 5 years ~ -12.94%."""
        result = compute_cagr(200.0, 100.0, 5.0)
        assert result < 0
        assert abs(result - (-0.1294)) < 0.001

    def test_zero_start(self):
        """Zero start value returns 0.0."""
        assert compute_cagr(0.0, 100.0, 5.0) == 0.0

    def test_one_year(self):
        """Single year: (end/start) - 1."""
        result = compute_cagr(100.0, 120.0, 1.0)
        assert abs(result - 0.20) < 0.001


# ── Dispersion Tests ─────────────────────────────────────────────────────


class TestComputeDispersion:
    """Tests for compute_dispersion()."""

    def test_normal_list(self):
        """Known standard deviation."""
        values = [10.0, 12.0, 8.0, 14.0, 6.0]
        result = compute_dispersion(values)
        assert result > 0
        assert abs(result - 3.162) < 0.01  # sample stdev

    def test_single_value(self):
        """Single value returns 0.0."""
        assert compute_dispersion([5.0]) == 0.0

    def test_empty(self):
        """Empty list returns 0.0."""
        assert compute_dispersion([]) == 0.0


# ── Median Tests ─────────────────────────────────────────────────────────


class TestComputeMedian:
    """Tests for compute_median()."""

    def test_odd_list(self):
        """Odd-length list: middle element."""
        assert compute_median([1.0, 3.0, 5.0, 7.0, 9.0]) == 5.0

    def test_even_list(self):
        """Even-length list: average of two middle elements."""
        assert compute_median([1.0, 3.0, 5.0, 7.0]) == 4.0

    def test_single(self):
        """Single element is the median."""
        assert compute_median([42.0]) == 42.0

    def test_empty(self):
        """Empty list returns 0.0."""
        assert compute_median([]) == 0.0


# ── Percentile Tests ─────────────────────────────────────────────────────


class TestComputePercentile:
    """Tests for compute_percentile()."""

    def test_at_bottom(self):
        """Lowest value: 0% below."""
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        assert compute_percentile(10.0, values) == 0.0

    def test_at_top(self):
        """Highest value: 80% below (4 out of 5)."""
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        assert compute_percentile(50.0, values) == 80.0

    def test_in_middle(self):
        """Middle value: 40% below (2 out of 5)."""
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        assert compute_percentile(30.0, values) == 40.0

    def test_empty(self):
        """Empty list returns 0.0."""
        assert compute_percentile(42.0, []) == 0.0


# ── Capital Cycle Tests ──────────────────────────────────────────────────


class TestClassifyCapitalCycle:
    """Tests for classify_capital_cycle()."""

    def test_expanding(self):
        """High capex growth + rising ROIC = EXPANDING."""
        result = classify_capital_cycle([0.08, 0.10, 0.12], roic_trend=0.02)
        assert result == "EXPANDING"

    def test_contracting(self):
        """Declining capex = CONTRACTING."""
        result = classify_capital_cycle([-0.05, -0.08, -0.03], roic_trend=-0.01)
        assert result == "CONTRACTING"

    def test_stable(self):
        """Moderate capex growth, no clear trend = STABLE."""
        result = classify_capital_cycle([0.01, 0.02, 0.03], roic_trend=0.01)
        assert result == "STABLE"

    def test_empty_history(self):
        """No capex data returns STABLE."""
        assert classify_capital_cycle([], roic_trend=0.05) == "STABLE"


# ── Industry Economics Computation Tests ─────────────────────────────────


def _make_company(
    entity_id: str,
    revenue_history: list[float],
    gross_margin: float,
    operating_margin: float,
    capex_to_revenue: float,
    rd_to_revenue: float,
    roic: float,
    wacc: float,
    capex_growth_history: list[float] | None = None,
) -> dict:
    """Helper to build a company dict."""
    return {
        "entity_id": entity_id,
        "revenue_history": revenue_history,
        "gross_margin": gross_margin,
        "operating_margin": operating_margin,
        "capex_to_revenue": capex_to_revenue,
        "rd_to_revenue": rd_to_revenue,
        "roic": roic,
        "wacc": wacc,
        "capex_growth_history": capex_growth_history or [],
    }


# 10 realistic tech-like companies
TECH_COMPANIES = [
    _make_company("MSFT", [110, 125, 143, 168, 198, 211], 0.68, 0.42, 0.10, 0.13, 0.30, 0.09, [0.08, 0.06, 0.10]),
    _make_company("AAPL", [230, 260, 274, 294, 365, 383], 0.43, 0.30, 0.04, 0.07, 0.50, 0.09, [0.03, 0.05, 0.04]),
    _make_company("GOOG", [136, 161, 182, 257, 282, 307], 0.56, 0.26, 0.11, 0.15, 0.25, 0.10, [0.12, 0.10, 0.08]),
    _make_company("META", [70, 86, 117, 85, 134, 156], 0.80, 0.35, 0.20, 0.25, 0.20, 0.11, [0.15, 0.20, 0.18]),
    _make_company("AMZN", [233, 280, 386, 469, 514, 575], 0.42, 0.05, 0.08, 0.12, 0.10, 0.10, [0.10, 0.08, 0.12]),
    _make_company("NVDA", [11, 17, 27, 27, 61, 96], 0.65, 0.38, 0.05, 0.27, 0.45, 0.11, [0.10, 0.15, 0.20]),
    _make_company("CRM", [13, 17, 21, 26, 31, 35], 0.73, 0.06, 0.03, 0.14, 0.08, 0.10, [0.05, 0.04, 0.06]),
    _make_company("ORCL", [39, 39, 40, 42, 50, 53], 0.79, 0.30, 0.06, 0.17, 0.15, 0.08, [0.02, 0.03, 0.01]),
    _make_company("ADBE", [11, 13, 15, 17, 18, 20], 0.88, 0.36, 0.04, 0.18, 0.35, 0.09, [0.06, 0.05, 0.07]),
    _make_company("INTC", [71, 72, 78, 79, 63, 54], 0.55, 0.25, 0.22, 0.20, 0.08, 0.10, [-0.05, -0.08, -0.10]),
]


class TestComputeIndustryEconomics:
    """Tests for compute_industry_economics()."""

    def test_full_dataset_10_companies(self):
        """Full dataset of 10 tech companies produces valid industry profile."""
        result = compute_industry_economics(TECH_COMPANIES)
        assert isinstance(result, IndustryEconomics)
        # Should have CAGR values
        assert result.revenue_growth_3y_cagr is not None
        assert result.revenue_growth_5y_cagr is not None
        # Medians should be within realistic ranges
        assert 0.40 < result.median_gross_margin < 0.90
        assert 0.05 < result.median_operating_margin < 0.45
        assert result.median_roic is not None
        assert result.median_wacc is not None
        assert result.roic_wacc_spread is not None
        assert result.roic_wacc_spread > 0  # Tech earns above cost of capital

    def test_quartile_roic_ordering(self):
        """Top quartile ROIC should exceed bottom quartile."""
        result = compute_industry_economics(TECH_COMPANIES)
        assert result.top_quartile_roic is not None
        assert result.bottom_quartile_roic is not None
        assert result.top_quartile_roic >= result.bottom_quartile_roic

    def test_roic_dispersion_positive(self):
        """ROIC dispersion should be positive for diverse companies."""
        result = compute_industry_economics(TECH_COMPANIES)
        assert result.roic_dispersion is not None
        assert result.roic_dispersion > 0

    def test_minimal_data(self):
        """Single company with minimal fields still produces a result."""
        data = [{"gross_margin": 0.50, "operating_margin": 0.20, "roic": 0.12}]
        result = compute_industry_economics(data)
        assert isinstance(result, IndustryEconomics)
        assert result.median_gross_margin == 0.50
        assert result.revenue_growth_3y_cagr is None  # No revenue history

    def test_empty_list(self):
        """Empty company list returns default IndustryEconomics."""
        result = compute_industry_economics([])
        assert isinstance(result, IndustryEconomics)
        assert result.median_gross_margin is None
        assert result.median_roic is None
        assert result.capital_cycle_indicator == "STABLE"


# ── Rank Companies Tests ─────────────────────────────────────────────────


class TestRankCompanies:
    """Tests for rank_companies_in_industry()."""

    def test_rank_five_companies(self):
        """Rank subset of companies, all positions populated."""
        companies = TECH_COMPANIES[:5]
        industry = compute_industry_economics(TECH_COMPANIES)
        positions = rank_companies_in_industry(companies, industry)
        assert len(positions) == 5
        for p in positions:
            assert isinstance(p, CompanyIndustryPosition)
            assert p.entity_id != ""

    def test_leader_identification(self):
        """AAPL (highest ROIC=0.50) should have high ROIC percentile."""
        industry = compute_industry_economics(TECH_COMPANIES)
        positions = rank_companies_in_industry(TECH_COMPANIES, industry)
        aapl = [p for p in positions if p.entity_id == "AAPL"][0]
        assert aapl.roic_percentile is not None
        assert aapl.roic_percentile >= 70.0  # Should be top-tier

    def test_laggard_identification(self):
        """INTC (lowest ROIC=0.08) should have low ROIC percentile."""
        industry = compute_industry_economics(TECH_COMPANIES)
        positions = rank_companies_in_industry(TECH_COMPANIES, industry)
        intc = [p for p in positions if p.entity_id == "INTC"][0]
        assert intc.roic_percentile is not None
        assert intc.roic_percentile <= 20.0  # Bottom tier

    def test_empty_list(self):
        """Empty company list returns empty positions."""
        industry = compute_industry_economics(TECH_COMPANIES)
        positions = rank_companies_in_industry([], industry)
        assert positions == []


# ── Compare Industries Tests ─────────────────────────────────────────────


class TestCompareIndustries:
    """Tests for compare_industries()."""

    def test_tech_vs_utilities(self):
        """Tech should have higher margins and ROIC than utilities."""
        tech = IndustryEconomics(
            revenue_growth_3y_cagr=0.12,
            revenue_growth_5y_cagr=0.10,
            revenue_dispersion=0.05,
            median_gross_margin=0.65,
            median_operating_margin=0.30,
            median_capex_to_revenue=0.08,
            median_rd_to_revenue=0.15,
            median_roic=0.20,
            median_wacc=0.09,
            roic_wacc_spread=0.11,
            roic_dispersion=0.12,
            capital_cycle_indicator="EXPANDING",
            top_quartile_roic=0.35,
            bottom_quartile_roic=0.10,
        )
        utilities = IndustryEconomics(
            revenue_growth_3y_cagr=0.03,
            revenue_growth_5y_cagr=0.02,
            revenue_dispersion=0.01,
            median_gross_margin=0.35,
            median_operating_margin=0.18,
            median_capex_to_revenue=0.20,
            median_rd_to_revenue=0.01,
            median_roic=0.06,
            median_wacc=0.07,
            roic_wacc_spread=-0.01,
            roic_dispersion=0.03,
            capital_cycle_indicator="STABLE",
            top_quartile_roic=0.09,
            bottom_quartile_roic=0.04,
        )
        deltas = compare_industries(tech, utilities)
        assert deltas["median_gross_margin"] > 0  # Tech higher
        assert deltas["median_roic"] > 0  # Tech higher
        assert deltas["median_capex_to_revenue"] < 0  # Utilities higher capex
        assert deltas["capital_cycle_indicator"]["a"] == "EXPANDING"
        assert deltas["capital_cycle_indicator"]["b"] == "STABLE"

    def test_same_industry(self):
        """Comparing same industry should produce zero deltas."""
        industry = IndustryEconomics(
            revenue_growth_3y_cagr=0.08,
            median_gross_margin=0.50,
            median_operating_margin=0.20,
            median_roic=0.15,
            median_wacc=0.09,
            roic_wacc_spread=0.06,
        )
        deltas = compare_industries(industry, industry)
        assert deltas["median_gross_margin"] == 0.0
        assert deltas["median_roic"] == 0.0
        assert deltas["roic_wacc_spread"] == 0.0

    def test_missing_values_produce_none(self):
        """Missing values on either side produce None delta."""
        a = IndustryEconomics(median_gross_margin=0.50)
        b = IndustryEconomics()  # All None
        deltas = compare_industries(a, b)
        # median_gross_margin: a=0.50, b=None -> None
        assert deltas["median_gross_margin"] is None
        assert deltas["median_roic"] is None


# ── Integration Tests ────────────────────────────────────────────────────


class TestIntegration:
    """End-to-end integration tests with realistic sector data."""

    def test_full_pipeline(self):
        """Full pipeline: economics -> rank -> top performer check."""
        economics = compute_industry_economics(TECH_COMPANIES)
        positions = rank_companies_in_industry(TECH_COMPANIES, economics)
        assert len(positions) == 10
        # The spread should exist and be meaningful
        assert economics.roic_wacc_spread is not None

    def test_economics_then_compare(self):
        """Compute two industries then compare."""
        tech = compute_industry_economics(TECH_COMPANIES)
        # Create simplified utility-like companies
        util_companies = [
            _make_company("NEE", [18, 19, 20, 21, 22, 23], 0.38, 0.20, 0.25, 0.01, 0.07, 0.07),
            _make_company("DUK", [24, 24, 25, 25, 26, 27], 0.35, 0.18, 0.22, 0.00, 0.05, 0.06),
            _make_company("SO", [20, 21, 22, 22, 23, 24], 0.33, 0.16, 0.20, 0.00, 0.06, 0.06),
        ]
        util = compute_industry_economics(util_companies)
        deltas = compare_industries(tech, util)
        # Tech should beat utilities on margins
        assert deltas["median_gross_margin"] is not None
        assert deltas["median_gross_margin"] > 0

    def test_single_company_industry(self):
        """Single-company industry still works end-to-end."""
        solo = [TECH_COMPANIES[0]]
        economics = compute_industry_economics(solo)
        positions = rank_companies_in_industry(solo, economics)
        assert len(positions) == 1
        assert positions[0].entity_id == "MSFT"

    def test_revenue_growth_dispersion_meaningful(self):
        """Revenue dispersion should reflect company diversity."""
        economics = compute_industry_economics(TECH_COMPANIES)
        assert economics.revenue_dispersion is not None
        assert economics.revenue_dispersion > 0  # Companies grow at different rates
