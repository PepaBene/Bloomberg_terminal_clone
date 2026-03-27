"""Tests for Pillar 3 Phase 4C — Engine 2: Macro Scenario Analysis Engine."""

import pytest

from src.engines.macro_scenario_engine import (
    PREBUILT_SCENARIOS,
    SECTOR_SENSITIVITIES,
    build_custom_scenario,
    classify_rating_implication,
    compare_scenarios,
    compute_scenario_price_target,
    estimate_eps_impact,
    estimate_margin_impact,
    generate_scenario_narrative_template,
    get_prebuilt_scenarios,
    run_company_scenario,
    run_portfolio_scenario,
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _base_company(sector: str = "Information Technology") -> dict:
    return {
        "entity_id": "test-001",
        "sector": sector,
        "base_eps": 5.00,
        "current_price": 150.0,
        "base_margin_bps": 2000.0,
    }


def _recession_assumptions() -> dict:
    return PREBUILT_SCENARIOS["recession"]["assumptions"].copy()


def _soft_landing_assumptions() -> dict:
    return PREBUILT_SCENARIOS["soft_landing"]["assumptions"].copy()


# ── Constants Tests ──────────────────────────────────────────────────────


class TestConstants:
    def test_prebuilt_scenarios_count(self):
        assert len(PREBUILT_SCENARIOS) == 4

    def test_prebuilt_scenario_keys(self):
        expected = {"soft_landing", "recession", "stagflation", "deflation"}
        assert set(PREBUILT_SCENARIOS.keys()) == expected

    def test_each_scenario_has_assumptions(self):
        for name, scenario in PREBUILT_SCENARIOS.items():
            assert "assumptions" in scenario, f"{name} missing assumptions"
            assert "gdp_growth_pct" in scenario["assumptions"]

    def test_sector_sensitivities_count(self):
        assert len(SECTOR_SENSITIVITIES) == 11

    def test_sector_sensitivity_keys(self):
        for sector, sens in SECTOR_SENSITIVITIES.items():
            assert "gdp" in sens
            assert "inflation" in sens
            assert "rates" in sens
            assert "oil" in sens


# ── get_prebuilt_scenarios Tests ─────────────────────────────────────────


class TestGetPrebuiltScenarios:
    def test_returns_deep_copy(self):
        s1 = get_prebuilt_scenarios()
        s2 = get_prebuilt_scenarios()
        s1["recession"]["assumptions"]["gdp_growth_pct"] = 999
        assert s2["recession"]["assumptions"]["gdp_growth_pct"] != 999

    def test_returns_all_four(self):
        scenarios = get_prebuilt_scenarios()
        assert len(scenarios) == 4


# ── build_custom_scenario Tests ──────────────────────────────────────────


class TestBuildCustomScenario:
    def test_valid_custom_scenario(self):
        result = build_custom_scenario(
            "Test Scenario",
            {"gdp_growth_pct": 3.0, "inflation_pct": 2.0},
            description="A test",
        )
        assert result["scenario_name"] == "Test Scenario"
        assert result["scenario_type"] == "custom"
        assert result["assumptions"]["gdp_growth_pct"] == 3.0

    def test_missing_required_raises(self):
        with pytest.raises(ValueError, match="Missing required"):
            build_custom_scenario("Bad", {"oil_price_usd": 50})

    def test_custom_with_created_by(self):
        result = build_custom_scenario(
            "My Scenario",
            {"gdp_growth_pct": 1.0, "inflation_pct": 3.0},
            created_by="john",
        )
        assert result["created_by"] == "john"


# ── estimate_eps_impact Tests ────────────────────────────────────────────


class TestEstimateEpsImpact:
    def test_recession_lowers_eps(self):
        result = estimate_eps_impact(5.0, _recession_assumptions(), "Consumer Discretionary")
        assert result["scenario_eps"] < 5.0
        assert result["eps_change_pct"] < 0

    def test_soft_landing_moderate_impact(self):
        result = estimate_eps_impact(5.0, _soft_landing_assumptions(), "Consumer Staples")
        # Soft landing should have relatively mild impact
        assert abs(result["eps_change_pct"]) < 30

    def test_financials_benefit_from_rates(self):
        # In soft landing, rates are below baseline (4% vs 5% baseline) -> negative for financials
        result_recession = estimate_eps_impact(5.0, _recession_assumptions(), "Financials")
        # Recession has lower rates (2.5%) which hurts financials more
        assert result_recession["eps_change_pct"] < 0

    def test_energy_sensitive_to_oil(self):
        low_oil = {"gdp_growth_pct": 2.5, "inflation_pct": 3.0, "fed_funds_rate_pct": 5.0, "oil_price_usd": 40}
        high_oil = {"gdp_growth_pct": 2.5, "inflation_pct": 3.0, "fed_funds_rate_pct": 5.0, "oil_price_usd": 120}
        low_result = estimate_eps_impact(5.0, low_oil, "Energy")
        high_result = estimate_eps_impact(5.0, high_oil, "Energy")
        assert high_result["scenario_eps"] > low_result["scenario_eps"]

    def test_returns_required_keys(self):
        result = estimate_eps_impact(5.0, _recession_assumptions(), "Industrials")
        assert "scenario_eps" in result
        assert "eps_change_pct" in result

    def test_unknown_sector_uses_defaults(self):
        result = estimate_eps_impact(5.0, _recession_assumptions(), "Unknown Sector")
        assert "scenario_eps" in result


# ── estimate_margin_impact Tests ─────────────────────────────────────────


class TestEstimateMarginImpact:
    def test_recession_compresses_margins(self):
        result = estimate_margin_impact(2000.0, _recession_assumptions(), "Consumer Discretionary")
        assert result["margin_change_bps"] < 0

    def test_returns_required_keys(self):
        result = estimate_margin_impact(1500.0, _soft_landing_assumptions(), "Industrials")
        assert "scenario_margin_bps" in result
        assert "margin_change_bps" in result

    def test_energy_inflation_impact(self):
        stagflation = PREBUILT_SCENARIOS["stagflation"]["assumptions"].copy()
        result = estimate_margin_impact(2000.0, stagflation, "Energy")
        assert "margin_change_bps" in result


# ── classify_rating_implication Tests ────────────────────────────────────


class TestClassifyRatingImplication:
    def test_upgrade_on_large_positive(self):
        assert classify_rating_implication(15.0) == "UPGRADE"

    def test_downgrade_on_large_negative(self):
        assert classify_rating_implication(-12.0) == "DOWNGRADE"

    def test_maintain_on_moderate_change(self):
        assert classify_rating_implication(5.0) == "MAINTAIN"
        assert classify_rating_implication(-5.0) == "MAINTAIN"

    def test_boundary_at_10(self):
        assert classify_rating_implication(10.0) == "UPGRADE"
        assert classify_rating_implication(-10.0) == "DOWNGRADE"

    def test_zero_change(self):
        assert classify_rating_implication(0.0) == "MAINTAIN"


# ── compute_scenario_price_target Tests ──────────────────────────────────


class TestComputeScenarioPriceTarget:
    def test_lower_eps_lowers_target(self):
        target = compute_scenario_price_target(150.0, 5.0, 4.0)
        assert target < 150.0

    def test_higher_eps_raises_target(self):
        target = compute_scenario_price_target(150.0, 5.0, 6.0)
        assert target > 150.0

    def test_same_eps_same_target(self):
        target = compute_scenario_price_target(150.0, 5.0, 5.0)
        assert target == 150.0

    def test_zero_base_eps_returns_current_price(self):
        target = compute_scenario_price_target(150.0, 0.0, 3.0)
        assert target == 150.0

    def test_custom_pe_used(self):
        target = compute_scenario_price_target(150.0, 5.0, 5.0, current_pe=25.0)
        assert target == 125.0  # 25 * 5 = 125


# ── run_company_scenario Tests ───────────────────────────────────────────


class TestRunCompanyScenario:
    def test_returns_all_fields(self):
        company = _base_company("Consumer Discretionary")
        scenario = PREBUILT_SCENARIOS["recession"]
        result = run_company_scenario(company, scenario)
        assert "entity_id" in result
        assert "scenario_name" in result
        assert "base_eps" in result
        assert "scenario_eps" in result
        assert "eps_change_pct" in result
        assert "margin_impact_bps" in result
        assert "rating_implication" in result
        assert "price_target_scenario" in result

    def test_recession_hurts_cyclicals(self):
        company = _base_company("Consumer Discretionary")
        scenario = PREBUILT_SCENARIOS["recession"]
        result = run_company_scenario(company, scenario)
        assert result["eps_change_pct"] < 0
        assert result["scenario_eps"] < result["base_eps"]

    def test_preserves_entity_id(self):
        company = _base_company()
        company["entity_id"] = "my-entity-123"
        scenario = PREBUILT_SCENARIOS["soft_landing"]
        result = run_company_scenario(company, scenario)
        assert result["entity_id"] == "my-entity-123"


# ── run_portfolio_scenario Tests ─────────────────────────────────────────


class TestRunPortfolioScenario:
    def test_returns_results_for_all_companies(self):
        companies = [
            {**_base_company("Energy"), "entity_id": "e1"},
            {**_base_company("Financials"), "entity_id": "e2"},
            {**_base_company("Utilities"), "entity_id": "e3"},
        ]
        scenario = PREBUILT_SCENARIOS["recession"]
        results = run_portfolio_scenario(companies, scenario)
        assert len(results) == 3

    def test_sorted_by_eps_change_ascending(self):
        companies = [
            {**_base_company("Energy"), "entity_id": "e1"},
            {**_base_company("Consumer Discretionary"), "entity_id": "e2"},
            {**_base_company("Consumer Staples"), "entity_id": "e3"},
        ]
        scenario = PREBUILT_SCENARIOS["recession"]
        results = run_portfolio_scenario(companies, scenario)
        changes = [r["eps_change_pct"] for r in results]
        assert changes == sorted(changes)

    def test_empty_portfolio(self):
        results = run_portfolio_scenario([], PREBUILT_SCENARIOS["recession"])
        assert results == []


# ── compare_scenarios Tests ──────────────────────────────────────────────


class TestCompareScenarios:
    def test_compares_all_scenarios(self):
        company = _base_company("Information Technology")
        scenarios = list(PREBUILT_SCENARIOS.values())
        results = compare_scenarios(company, scenarios)
        assert len(results) == 4

    def test_sorted_worst_first(self):
        company = _base_company("Consumer Discretionary")
        scenarios = list(PREBUILT_SCENARIOS.values())
        results = compare_scenarios(company, scenarios)
        changes = [r["eps_change_pct"] for r in results]
        assert changes == sorted(changes)

    def test_single_scenario(self):
        company = _base_company()
        results = compare_scenarios(company, [PREBUILT_SCENARIOS["soft_landing"]])
        assert len(results) == 1


# ── generate_scenario_narrative_template Tests ───────────────────────────


class TestGenerateScenarioNarrative:
    def test_contains_scenario_name(self):
        impact = {
            "scenario_name": "Recession",
            "eps_change_pct": -18.5,
            "margin_impact_bps": -150,
            "rating_implication": "DOWNGRADE",
            "price_target_scenario": 95.0,
        }
        narrative = generate_scenario_narrative_template(impact)
        assert "Recession" in narrative

    def test_negative_eps_shows_decrease(self):
        impact = {
            "scenario_name": "Test",
            "eps_change_pct": -10.0,
            "margin_impact_bps": -50,
            "rating_implication": "MAINTAIN",
            "price_target_scenario": 120.0,
        }
        narrative = generate_scenario_narrative_template(impact)
        assert "decrease" in narrative

    def test_positive_eps_shows_increase(self):
        impact = {
            "scenario_name": "Boom",
            "eps_change_pct": 12.0,
            "margin_impact_bps": 80,
            "rating_implication": "UPGRADE",
            "price_target_scenario": 180.0,
        }
        narrative = generate_scenario_narrative_template(impact)
        assert "increase" in narrative

    def test_large_impact_shows_significantly(self):
        impact = {
            "scenario_name": "Crisis",
            "eps_change_pct": -20.0,
            "margin_impact_bps": -200,
            "rating_implication": "DOWNGRADE",
            "price_target_scenario": 80.0,
        }
        narrative = generate_scenario_narrative_template(impact)
        assert "significantly" in narrative

    def test_price_target_included(self):
        impact = {
            "scenario_name": "Test",
            "eps_change_pct": 5.0,
            "margin_impact_bps": 30,
            "rating_implication": "MAINTAIN",
            "price_target_scenario": 155.50,
        }
        narrative = generate_scenario_narrative_template(impact)
        assert "155.50" in narrative
