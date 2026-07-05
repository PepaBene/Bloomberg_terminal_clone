"""Tests for the Automatic Model Builder Engine."""

import pytest

from src.engines.auto_model_builder import (
    SCOPES,
    build_company_model,
    build_corporate_model,
    build_economic_model,
    build_industry_model,
    build_market_model,
    build_model,
)


class TestDispatcher:
    def test_all_scopes_dispatch(self):
        for scope in SCOPES:
            model = build_model(scope, {}, subject="X")
            assert model.scope == scope
            assert 0 <= model.composite_score <= 100
            assert model.to_dict()["scope"] == scope

    def test_unknown_scope_raises(self):
        with pytest.raises(ValueError):
            build_model("GALACTIC", {})

    def test_case_insensitive(self):
        assert build_model("company", {}).scope == "COMPANY"


class TestEconomic:
    def test_inverted_curve_raises_recession_probability(self):
        flat = build_economic_model({"yield_curve_spread": 1.0, "pmi": 55})
        inverted = build_economic_model({"yield_curve_spread": -1.0, "pmi": 45, "leading_index_change": -1})
        assert inverted.scores["recession_probability_pct"] > flat.scores["recession_probability_pct"]

    def test_expansion_regime(self):
        m = build_economic_model({"gdp_growth": 3.0, "inflation": 2.0, "policy_rate": 2.0})
        assert m.rating == "EXPANSION"

    def test_restrictive_policy_stance(self):
        m = build_economic_model({"policy_rate": 5.0, "inflation": 2.0})
        section = next(s for s in m.sections if s.title == "Inflation & Policy")
        assert section.metrics["policy_stance"] == "RESTRICTIVE"


class TestMarket:
    def test_cheap_market_scores_higher_than_expensive(self):
        cheap = build_market_model({"pe_percentile": 10, "earnings_growth": 10, "vix": 14})
        rich = build_market_model({"pe_percentile": 95, "earnings_growth": 0, "vix": 30})
        assert cheap.composite_score > rich.composite_score

    def test_risk_off_regime_on_high_vix(self):
        m = build_market_model({"vix": 35})
        section = next(s for s in m.sections if s.title == "Risk Conditions")
        assert section.metrics["risk_regime"] == "RISK_OFF"


class TestIndustry:
    def test_expansion_cycle_detected(self):
        m = build_industry_model({"revenue_growth": 15, "margin_trend": 0.5})
        assert "EXPANSION" in m.summary

    def test_concentration_band(self):
        m = build_industry_model({"hhi": 3000})
        section = next(s for s in m.sections if s.title == "Structure")
        assert section.metrics["concentration"] == "CONCENTRATED"


class TestCorporate:
    def test_high_leverage_lowers_score_and_flags_credit(self):
        strong = build_corporate_model({"net_debt_to_ebitda": 1.0, "interest_coverage": 12})
        weak = build_corporate_model({"net_debt_to_ebitda": 6.0, "interest_coverage": 1.5, "altman_z": 1.2})
        assert strong.composite_score > weak.composite_score
        assert weak.rating == "DISTRESSED"

    def test_maturity_wall_driver(self):
        m = build_corporate_model({"net_debt_to_ebitda": 3, "near_term_maturities_pct": 40})
        assert any("maturity" in d.lower() for d in m.drivers)


class TestCompany:
    def test_strong_company_rates_buy(self):
        m = build_company_model(
            {
                "revenue_growth": 20, "ebitda_margin": 35, "roe": 25,
                "dcf_upside_pct": 40, "pe_vs_peers": -0.5, "piotroski": 8,
                "altman_z": 6, "smart_money_signal": "BULLISH", "insider_buy_ratio": 0.9,
            }
        )
        assert m.rating in ("BUY", "STRONG_BUY")
        assert set(m.scores) >= {"growth", "quality", "value", "safety", "sentiment"}

    def test_weak_company_rates_sell(self):
        m = build_company_model(
            {
                "revenue_growth": -15, "ebitda_margin": 2, "roe": -5,
                "dcf_upside_pct": -40, "pe_vs_peers": 0.8, "piotroski": 1,
                "altman_z": 1.0, "smart_money_signal": "BEARISH", "insider_buy_ratio": 0.1,
            }
        )
        assert m.rating in ("SELL", "STRONG_SELL")

    def test_distress_driver_surfaced(self):
        m = build_company_model({"altman_z": 1.0})
        assert any("distress" in d.lower() for d in m.drivers)
