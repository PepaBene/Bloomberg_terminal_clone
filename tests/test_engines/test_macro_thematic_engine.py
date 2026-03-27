"""Tests for Pillar 3 Phase 4C — Engine 1: Macro Thematic Exposure Engine."""

import pytest

from src.engines.macro_thematic_engine import (
    MACRO_THEMES,
    SECTOR_THEME_SENSITIVITY,
    compute_commodity_exposure,
    compute_energy_transition_exposure,
    compute_fx_exposure,
    compute_growth_exposure,
    compute_inflation_exposure,
    compute_rates_exposure,
    score_all_themes,
    screen_by_theme,
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _base_company(sector: str = "Information Technology") -> dict:
    """Return a minimal company dict for testing."""
    return {
        "entity_id": "test-001",
        "ticker": "TEST",
        "sector": sector,
        "gross_margin": 50.0,
        "international_revenue_pct": 40.0,
    }


# ── Constants Tests ──────────────────────────────────────────────────────


class TestConstants:
    def test_macro_themes_has_seven_entries(self):
        assert len(MACRO_THEMES) == 7

    def test_macro_themes_known_values(self):
        for theme in ["inflation", "deflation", "growth", "rates", "fx", "commodities", "energy_transition"]:
            assert theme in MACRO_THEMES

    def test_sector_sensitivity_has_eleven_sectors(self):
        assert len(SECTOR_THEME_SENSITIVITY) == 11

    def test_each_sector_has_all_themes(self):
        for sector, sensitivities in SECTOR_THEME_SENSITIVITY.items():
            for theme in MACRO_THEMES:
                assert theme in sensitivities, f"{sector} missing theme {theme}"


# ── Inflation Exposure Tests ─────────────────────────────────────────────


class TestInflationExposure:
    def test_basic_inflation_score(self):
        company = _base_company("Energy")
        result = compute_inflation_exposure(company)
        assert "score" in result
        assert "direction" in result
        assert "evidence" in result

    def test_energy_sector_benefits_from_inflation(self):
        company = _base_company("Energy")
        result = compute_inflation_exposure(company)
        assert result["score"] > 0
        assert result["direction"] == "positive"

    def test_consumer_discretionary_hurt_by_inflation(self):
        company = _base_company("Consumer Discretionary")
        result = compute_inflation_exposure(company)
        assert result["score"] < 0
        assert result["direction"] == "negative"

    def test_strong_pricing_power_mitigates(self):
        company = _base_company("Consumer Discretionary")
        company["pricing_power_score"] = 80.0
        result = compute_inflation_exposure(company)
        # Should be less negative than without pricing power
        company_no_pp = _base_company("Consumer Discretionary")
        result_no_pp = compute_inflation_exposure(company_no_pp)
        assert result["score"] > result_no_pp["score"]

    def test_weak_pricing_power_amplifies(self):
        company = _base_company("Consumer Discretionary")
        company["pricing_power_score"] = 20.0
        result = compute_inflation_exposure(company)
        company_no_pp = _base_company("Consumer Discretionary")
        result_no_pp = compute_inflation_exposure(company_no_pp)
        assert result["score"] < result_no_pp["score"]

    def test_high_variable_costs_worsen_inflation(self):
        company = _base_company("Energy")
        company["cost_structure_pct_variable"] = 80.0
        result = compute_inflation_exposure(company)
        assert any("variable cost" in e.lower() for e in result["evidence"])

    def test_high_gross_margin_cushion(self):
        company = _base_company("Consumer Staples")
        company["gross_margin"] = 70.0
        result = compute_inflation_exposure(company)
        assert any("gross margin" in e.lower() for e in result["evidence"])

    def test_score_clamped_to_range(self):
        company = _base_company("Energy")
        company["pricing_power_score"] = 90.0
        company["cost_structure_pct_variable"] = 5.0
        company["gross_margin"] = 80.0
        result = compute_inflation_exposure(company)
        assert -100.0 <= result["score"] <= 100.0


# ── Rates Exposure Tests ─────────────────────────────────────────────────


class TestRatesExposure:
    def test_basic_rates_score(self):
        company = _base_company("Financials")
        company["debt_to_equity"] = 1.0
        result = compute_rates_exposure(company)
        assert "score" in result

    def test_financials_benefit_from_rates(self):
        company = _base_company("Financials")
        company["debt_to_equity"] = 0.5
        result = compute_rates_exposure(company)
        assert result["score"] > 0

    def test_high_leverage_amplifies_rate_sensitivity(self):
        company = _base_company("Information Technology")
        company["debt_to_equity"] = 3.0
        result = compute_rates_exposure(company)
        assert any("leverage" in e.lower() for e in result["evidence"])

    def test_floating_rate_debt_increases_exposure(self):
        company = _base_company("Industrials")
        company["debt_to_equity"] = 1.0
        company["pct_floating_rate_debt"] = 60.0
        result = compute_rates_exposure(company)
        assert any("floating" in e.lower() for e in result["evidence"])

    def test_short_duration_financials(self):
        company = _base_company("Financials")
        company["debt_to_equity"] = 1.0
        company["duration_years"] = 1.5
        result = compute_rates_exposure(company)
        assert any("short duration" in e.lower() for e in result["evidence"])


# ── FX Exposure Tests ────────────────────────────────────────────────────


class TestFXExposure:
    def test_basic_fx_score(self):
        company = _base_company("Information Technology")
        result = compute_fx_exposure(company)
        assert "score" in result

    def test_high_international_revenue_increases_fx_exposure(self):
        company = _base_company("Information Technology")
        company["international_revenue_pct"] = 70.0
        result = compute_fx_exposure(company)
        assert any("international" in e.lower() for e in result["evidence"])

    def test_domestic_focus_limits_fx(self):
        company = _base_company("Utilities")
        company["international_revenue_pct"] = 5.0
        result = compute_fx_exposure(company)
        assert any("domestic" in e.lower() for e in result["evidence"])

    def test_hedging_mitigates_fx(self):
        company = _base_company("Information Technology")
        company["international_revenue_pct"] = 60.0
        company["hedging_ratio"] = 80.0
        result = compute_fx_exposure(company)
        assert any("hedging" in e.lower() for e in result["evidence"])


# ── Commodity Exposure Tests ─────────────────────────────────────────────


class TestCommodityExposure:
    def test_commodity_producer_benefits(self):
        company = _base_company("Energy")
        company["is_commodity_producer"] = True
        result = compute_commodity_exposure(company)
        assert result["score"] > 0

    def test_high_commodity_input_negative(self):
        company = _base_company("Consumer Staples")
        company["commodity_input_pct"] = 60.0
        result = compute_commodity_exposure(company)
        assert any("commodity input" in e.lower() for e in result["evidence"])

    def test_hedging_months_reduces_risk(self):
        company = _base_company("Materials")
        company["hedging_months"] = 18
        result = compute_commodity_exposure(company)
        assert any("hedging" in e.lower() for e in result["evidence"])


# ── Growth Exposure Tests ────────────────────────────────────────────────


class TestGrowthExposure:
    def test_cyclical_sector_high_growth_sensitivity(self):
        company = _base_company("Consumer Discretionary")
        company["earnings_cyclicality"] = 80.0
        result = compute_growth_exposure(company)
        assert result["score"] > 0

    def test_strong_revenue_growth_signals_leverage(self):
        company = _base_company("Information Technology")
        company["revenue_growth_yoy"] = 25.0
        result = compute_growth_exposure(company)
        assert any("revenue growth" in e.lower() for e in result["evidence"])

    def test_deep_backlog_provides_visibility(self):
        company = _base_company("Industrials")
        company["backlog_months"] = 15.0
        result = compute_growth_exposure(company)
        assert any("backlog" in e.lower() for e in result["evidence"])


# ── Energy Transition Exposure Tests ─────────────────────────────────────


class TestEnergyTransitionExposure:
    def test_green_revenue_benefits(self):
        company = _base_company("Utilities")
        company["green_revenue_pct"] = 60.0
        result = compute_energy_transition_exposure(company)
        assert result["score"] > 0

    def test_high_carbon_intensity_risk(self):
        company = _base_company("Energy")
        company["carbon_intensity"] = 600.0
        result = compute_energy_transition_exposure(company)
        assert any("carbon intensity" in e.lower() for e in result["evidence"])

    def test_green_capex_signals_readiness(self):
        company = _base_company("Industrials")
        company["capex_green_pct"] = 50.0
        result = compute_energy_transition_exposure(company)
        assert any("green capex" in e.lower() for e in result["evidence"])


# ── score_all_themes Tests ───────────────────────────────────────────────


class TestScoreAllThemes:
    def test_returns_all_seven_themes(self):
        company = _base_company("Financials")
        company["debt_to_equity"] = 1.0
        results = score_all_themes(company)
        assert len(results) == 7
        for theme in MACRO_THEMES:
            assert theme in results

    def test_each_theme_has_required_keys(self):
        company = _base_company("Energy")
        results = score_all_themes(company)
        for theme, data in results.items():
            assert "score" in data
            assert "direction" in data
            assert "evidence" in data

    def test_deflation_inversely_correlated_to_inflation(self):
        company = _base_company("Energy")
        results = score_all_themes(company)
        # Deflation score should be opposite sign to inflation
        assert results["inflation"]["score"] * results["deflation"]["score"] <= 0


# ── screen_by_theme Tests ───────────────────────────────────────────────


class TestScreenByTheme:
    def test_screen_returns_matching_companies(self):
        companies = [
            {**_base_company("Energy"), "entity_id": "e1"},
            {**_base_company("Information Technology"), "entity_id": "e2"},
            {**_base_company("Utilities"), "entity_id": "e3"},
        ]
        results = screen_by_theme(companies, "inflation")
        assert len(results) > 0
        for r in results:
            assert "company" in r
            assert "exposure" in r

    def test_screen_filter_by_direction(self):
        companies = [
            {**_base_company("Energy"), "entity_id": "e1"},
            {**_base_company("Consumer Discretionary"), "entity_id": "e2"},
        ]
        positive = screen_by_theme(companies, "inflation", direction="positive")
        for r in positive:
            assert r["exposure"]["direction"] == "positive"

    def test_screen_filter_by_min_score(self):
        companies = [
            {**_base_company("Energy"), "entity_id": "e1"},
            {**_base_company("Consumer Staples"), "entity_id": "e2"},
        ]
        results = screen_by_theme(companies, "commodities", min_score=30.0)
        for r in results:
            assert r["exposure"]["score"] >= 30.0

    def test_screen_filter_by_max_score(self):
        companies = [
            {**_base_company("Energy"), "entity_id": "e1"},
            {**_base_company("Consumer Staples"), "entity_id": "e2"},
        ]
        results = screen_by_theme(companies, "commodities", max_score=0.0)
        for r in results:
            assert r["exposure"]["score"] <= 0.0

    def test_screen_invalid_theme_raises(self):
        with pytest.raises(ValueError, match="Unknown theme"):
            screen_by_theme([_base_company()], "invalid_theme")

    def test_screen_sorted_by_absolute_score(self):
        companies = [
            {**_base_company("Consumer Staples"), "entity_id": "e1"},
            {**_base_company("Energy"), "entity_id": "e2"},
            {**_base_company("Financials"), "entity_id": "e3"},
        ]
        results = screen_by_theme(companies, "commodities")
        scores = [abs(r["exposure"]["score"]) for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_screen_empty_list(self):
        results = screen_by_theme([], "inflation")
        assert results == []
