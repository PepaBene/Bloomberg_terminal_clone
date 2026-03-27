"""Tests for Pillar 3 Phase 3B — Country Risk Engine."""

import pytest

from src.engines.country_risk import (
    RISK_CLASSIFICATIONS,
    RISK_WEIGHTS,
    POLITICAL_WEIGHTS,
    ECONOMIC_WEIGHTS,
    CompanyExposure,
    CountryRiskResult,
    EconomicRisk,
    PoliticalRisk,
    SanctionsRisk,
    assess_country_risk,
    assess_risk_trend,
    classify_risk,
    compute_composite_risk,
    compute_economic_risk_score,
    compute_political_risk_score,
    compute_sanctions_risk_score,
    find_exposed_companies,
    map_company_exposure,
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _switzerland_governance() -> dict:
    """Low-risk political data (Switzerland-like)."""
    return {
        "regime_stability": 5,
        "policy_predictability": 10,
        "corruption": 8,
        "rule_of_law": 5,
        "civil_unrest": 5,
    }


def _authoritarian_governance() -> dict:
    """High-risk political data (authoritarian regime)."""
    return {
        "regime_stability": 85,
        "policy_predictability": 90,
        "corruption": 80,
        "rule_of_law": 85,
        "civil_unrest": 70,
    }


def _strong_economy() -> dict:
    """Low-risk macro data (US-like)."""
    return {
        "gdp_growth": 3.5,
        "inflation": 2.5,
        "current_account": -2.0,
        "debt_gdp": 35.0,
        "reserves": 10.0,
        "currency_stability": 10.0,
    }


def _crisis_economy() -> dict:
    """High-risk macro data (Argentina-like)."""
    return {
        "gdp_growth": -4.0,
        "inflation": 25.0,
        "current_account": -6.0,
        "debt_gdp": 120.0,
        "reserves": 1.5,
        "currency_stability": 90.0,
    }


def _no_sanctions() -> dict:
    """Zero sanctions data."""
    return {
        "active_programs_count": 0,
        "trade_restriction_intensity": 0.0,
        "trajectory": "STABLE",
    }


def _heavy_sanctions() -> dict:
    """Heavy sanctions (Russia-like)."""
    return {
        "active_programs_count": 8,
        "trade_restriction_intensity": 95.0,
        "trajectory": "ESCALATING",
    }


# ── TestPoliticalRisk ────────────────────────────────────────────────────


class TestPoliticalRisk:
    """Tests for compute_political_risk_score()."""

    def test_stable_democracy(self):
        """Switzerland-like governance → low score (~15)."""
        result = compute_political_risk_score(_switzerland_governance())
        assert isinstance(result, PoliticalRisk)
        assert result.score < 20
        assert result.regime_stability == 5.0

    def test_authoritarian_regime(self):
        """Authoritarian governance → high score (~80+)."""
        result = compute_political_risk_score(_authoritarian_governance())
        assert result.score > 75
        assert result.regime_stability == 85.0
        assert result.corruption == 80.0

    def test_mixed_governance_moderate(self):
        """Mixed governance scores → moderate output."""
        data = {
            "regime_stability": 30,
            "policy_predictability": 40,
            "corruption": 50,
            "rule_of_law": 35,
            "civil_unrest": 25,
        }
        result = compute_political_risk_score(data)
        assert 30 < result.score < 50

    def test_mixed_governance_leaning_high(self):
        """Mostly high sub-scores with one low → still high."""
        data = {
            "regime_stability": 70,
            "policy_predictability": 75,
            "corruption": 80,
            "rule_of_law": 70,
            "civil_unrest": 20,
        }
        result = compute_political_risk_score(data)
        assert result.score > 60

    def test_missing_keys_default(self):
        """Missing keys default to 50 (moderate risk)."""
        result = compute_political_risk_score({})
        assert result.score == pytest.approx(50.0, abs=0.1)

    def test_clamps_to_range(self):
        """Values outside 0-100 get clamped."""
        data = {
            "regime_stability": -10,
            "policy_predictability": 150,
            "corruption": 50,
            "rule_of_law": 50,
            "civil_unrest": 50,
        }
        result = compute_political_risk_score(data)
        assert result.regime_stability == 0.0
        assert result.policy_predictability == 100.0


# ── TestEconomicRisk ─────────────────────────────────────────────────────


class TestEconomicRisk:
    """Tests for compute_economic_risk_score()."""

    def test_strong_economy(self):
        """US-like economy → low score (~25)."""
        result = compute_economic_risk_score(_strong_economy())
        assert isinstance(result, EconomicRisk)
        assert result.score < 30
        assert result.gdp_growth_score <= 20

    def test_crisis_economy(self):
        """Argentina-like crisis → high score (~85+)."""
        result = compute_economic_risk_score(_crisis_economy())
        assert result.score > 80
        assert result.inflation_score > 80
        assert result.debt_gdp_score > 80

    def test_emerging_stable_moderate(self):
        """Emerging but stable economy → moderate score."""
        data = {
            "gdp_growth": 2.0,
            "inflation": 5.5,
            "current_account": -3.0,
            "debt_gdp": 55.0,
            "reserves": 5.0,
            "currency_stability": 40.0,
        }
        result = compute_economic_risk_score(data)
        assert 30 < result.score < 60

    def test_emerging_with_reserves(self):
        """Good reserves offset some other risks."""
        data = {
            "gdp_growth": 1.5,
            "inflation": 4.0,
            "current_account": -1.0,
            "debt_gdp": 45.0,
            "reserves": 12.0,
            "currency_stability": 25.0,
        }
        result = compute_economic_risk_score(data)
        assert result.reserves_score <= 10
        assert result.score < 40

    def test_deflation_risky(self):
        """Negative inflation (deflation) → moderate risk score."""
        data = {
            "gdp_growth": 1.0,
            "inflation": -1.0,
            "current_account": 2.0,
            "debt_gdp": 50.0,
            "reserves": 8.0,
            "currency_stability": 20.0,
        }
        result = compute_economic_risk_score(data)
        assert result.inflation_score > 40  # deflation is risky


# ── TestSanctionsRisk ────────────────────────────────────────────────────


class TestSanctionsRisk:
    """Tests for compute_sanctions_risk_score()."""

    def test_no_sanctions(self):
        """No sanctions → score 0."""
        result = compute_sanctions_risk_score(_no_sanctions())
        assert isinstance(result, SanctionsRisk)
        assert result.score == 0.0
        assert result.active_programs_count == 0

    def test_heavy_sanctions(self):
        """Russia-like heavy sanctions → score ~90+."""
        result = compute_sanctions_risk_score(_heavy_sanctions())
        assert result.score > 85
        assert result.trajectory == "ESCALATING"

    def test_moderate_sanctions(self):
        """Moderate sanctions → mid-range score."""
        data = {
            "active_programs_count": 3,
            "trade_restriction_intensity": 40.0,
            "trajectory": "STABLE",
        }
        result = compute_sanctions_risk_score(data)
        assert 25 < result.score < 55

    def test_de_escalating_trajectory(self):
        """DE_ESCALATING trajectory reduces score."""
        base = {
            "active_programs_count": 3,
            "trade_restriction_intensity": 40.0,
            "trajectory": "STABLE",
        }
        stable_result = compute_sanctions_risk_score(base)

        de_esc = dict(base, trajectory="DE_ESCALATING")
        de_esc_result = compute_sanctions_risk_score(de_esc)
        assert de_esc_result.score < stable_result.score

    def test_escalating_trajectory(self):
        """ESCALATING trajectory increases score."""
        base = {
            "active_programs_count": 3,
            "trade_restriction_intensity": 40.0,
            "trajectory": "STABLE",
        }
        stable_result = compute_sanctions_risk_score(base)

        esc = dict(base, trajectory="ESCALATING")
        esc_result = compute_sanctions_risk_score(esc)
        assert esc_result.score > stable_result.score


# ── TestCompositeRisk ────────────────────────────────────────────────────


class TestCompositeRisk:
    """Tests for compute_composite_risk()."""

    def test_all_low(self):
        """All low risks → LOW_RISK."""
        pol = PoliticalRisk(score=10, regime_stability=5, policy_predictability=10,
                            corruption=8, rule_of_law=5, civil_unrest=5)
        eco = EconomicRisk(score=15, gdp_growth_score=10, inflation_score=15,
                           current_account_score=10, debt_gdp_score=15,
                           reserves_score=10, currency_stability_score=10)
        san = SanctionsRisk(score=0, active_programs_count=0,
                            trade_restriction_intensity=0, trajectory="STABLE")
        composite = compute_composite_risk(pol, eco, san)
        assert composite < 20
        assert classify_risk(composite) == "LOW_RISK"

    def test_mixed_moderate(self):
        """Mixed risks → MODERATE or ELEVATED."""
        pol = PoliticalRisk(score=45, regime_stability=40, policy_predictability=50,
                            corruption=45, rule_of_law=45, civil_unrest=40)
        eco = EconomicRisk(score=35, gdp_growth_score=30, inflation_score=40,
                           current_account_score=30, debt_gdp_score=35,
                           reserves_score=30, currency_stability_score=35)
        san = SanctionsRisk(score=25, active_programs_count=2,
                            trade_restriction_intensity=20, trajectory="STABLE")
        composite = compute_composite_risk(pol, eco, san)
        assert 25 < composite < 50
        classification = classify_risk(composite)
        assert classification in ("MODERATE_RISK", "ELEVATED_RISK")

    def test_all_high(self):
        """All high risks → HIGH_RISK or EXTREME_RISK."""
        pol = PoliticalRisk(score=85, regime_stability=90, policy_predictability=85,
                            corruption=80, rule_of_law=85, civil_unrest=80)
        eco = EconomicRisk(score=90, gdp_growth_score=85, inflation_score=95,
                           current_account_score=80, debt_gdp_score=90,
                           reserves_score=90, currency_stability_score=90)
        san = SanctionsRisk(score=90, active_programs_count=8,
                            trade_restriction_intensity=95, trajectory="ESCALATING")
        composite = compute_composite_risk(pol, eco, san)
        assert composite > 80
        classification = classify_risk(composite)
        assert classification in ("HIGH_RISK", "EXTREME_RISK")


# ── TestClassifyRisk ─────────────────────────────────────────────────────


class TestClassifyRisk:
    """Tests for classify_risk() at each boundary."""

    def test_low_risk(self):
        assert classify_risk(0.0) == "LOW_RISK"
        assert classify_risk(19.9) == "LOW_RISK"

    def test_moderate_risk(self):
        assert classify_risk(20.0) == "MODERATE_RISK"
        assert classify_risk(39.9) == "MODERATE_RISK"

    def test_elevated_risk(self):
        assert classify_risk(40.0) == "ELEVATED_RISK"
        assert classify_risk(59.9) == "ELEVATED_RISK"

    def test_high_risk(self):
        assert classify_risk(60.0) == "HIGH_RISK"
        assert classify_risk(79.9) == "HIGH_RISK"

    def test_extreme_risk(self):
        assert classify_risk(80.0) == "EXTREME_RISK"
        assert classify_risk(100.0) == "EXTREME_RISK"


# ── TestRiskTrend ────────────────────────────────────────────────────────


class TestRiskTrend:
    """Tests for assess_risk_trend()."""

    def test_improving(self):
        """Score decreased by >5 → IMPROVING."""
        assert assess_risk_trend(30.0, 40.0) == "IMPROVING"

    def test_deteriorating(self):
        """Score increased by >5 → DETERIORATING."""
        assert assess_risk_trend(50.0, 40.0) == "DETERIORATING"

    def test_stable(self):
        """Score changed by <5 → STABLE."""
        assert assess_risk_trend(42.0, 40.0) == "STABLE"

    def test_exact_threshold(self):
        """Score changed by exactly 5 → STABLE (not strictly >5)."""
        assert assess_risk_trend(45.0, 40.0) == "STABLE"


# ── TestAssessCountryRisk ────────────────────────────────────────────────


class TestAssessCountryRisk:
    """Tests for assess_country_risk() full orchestrator."""

    def test_switzerland_full(self):
        """Switzerland-like data → LOW_RISK."""
        result = assess_country_risk(
            governance_data=_switzerland_governance(),
            macro_data=_strong_economy(),
            sanctions_data=_no_sanctions(),
        )
        assert isinstance(result, CountryRiskResult)
        assert result.composite_score < 20
        assert result.classification == "LOW_RISK"
        assert result.trend == "STABLE"  # no prior

    def test_venezuela_full(self):
        """Venezuela-like data → HIGH_RISK or EXTREME_RISK."""
        result = assess_country_risk(
            governance_data=_authoritarian_governance(),
            macro_data=_crisis_economy(),
            sanctions_data=_heavy_sanctions(),
        )
        assert result.composite_score > 75
        assert result.classification in ("HIGH_RISK", "EXTREME_RISK")

    def test_with_prior_score(self):
        """Prior score provided → trend computed."""
        result = assess_country_risk(
            governance_data=_switzerland_governance(),
            macro_data=_strong_economy(),
            sanctions_data=_no_sanctions(),
            prior_score=50.0,
        )
        # Low current score vs high prior → IMPROVING
        assert result.trend == "IMPROVING"


# ── TestMapExposure ──────────────────────────────────────────────────────


class TestMapExposure:
    """Tests for map_company_exposure()."""

    def test_company_three_regions(self):
        """Company with revenue in 3 countries."""
        segments = {
            "revenue_segments": [
                {"country_code": "US", "pct": 50.0},
                {"country_code": "DE", "pct": 30.0},
                {"country_code": "CN", "pct": 20.0},
            ],
        }
        result = map_company_exposure("ENT001", segments)
        assert len(result) == 3
        assert all(isinstance(e, CompanyExposure) for e in result)
        us = [e for e in result if e.country_code == "US"]
        assert len(us) == 1
        assert us[0].exposure_pct == 50.0
        assert us[0].exposure_type == "REVENUE"

    def test_no_segments(self):
        """Empty segment data → empty list."""
        result = map_company_exposure("ENT002", {})
        assert result == []

    def test_relationship_based(self):
        """Supply chain from relationship data."""
        segments = {
            "revenue_segments": [
                {"country_code": "US", "pct": 70.0},
            ],
        }
        rels = {
            "supply_chain": [
                {"country_code": "CN", "pct": 40.0, "source": "supply_analysis"},
                {"country_code": "TW", "pct": 25.0, "source": "supply_analysis"},
            ],
        }
        result = map_company_exposure("ENT003", segments, rels)
        assert len(result) == 3
        supply = [e for e in result if e.exposure_type == "SUPPLY_CHAIN"]
        assert len(supply) == 2
        assert supply[0].source == "supply_analysis"


# ── TestFindExposed ──────────────────────────────────────────────────────


class TestFindExposed:
    """Tests for find_exposed_companies()."""

    def test_find_over_threshold(self):
        """Find companies with >10% exposure to RU."""
        exposures = [
            CompanyExposure("ENT001", "RU", "REVENUE", 25.0, "filing"),
            CompanyExposure("ENT002", "RU", "REVENUE", 5.0, "filing"),
            CompanyExposure("ENT003", "RU", "OPERATIONS", 15.0, "filing"),
            CompanyExposure("ENT004", "US", "REVENUE", 50.0, "filing"),
        ]
        result = find_exposed_companies("RU", exposures)
        assert len(result) == 2
        assert result[0].entity_id == "ENT001"  # highest first
        assert result[1].entity_id == "ENT003"

    def test_none_qualify(self):
        """No exposures meet threshold → empty list."""
        exposures = [
            CompanyExposure("ENT001", "RU", "REVENUE", 5.0, "filing"),
            CompanyExposure("ENT002", "RU", "REVENUE", 8.0, "filing"),
        ]
        result = find_exposed_companies("RU", exposures, min_pct=10.0)
        assert result == []

    def test_exact_threshold(self):
        """Exposure exactly at threshold → included."""
        exposures = [
            CompanyExposure("ENT001", "CN", "REVENUE", 10.0, "filing"),
            CompanyExposure("ENT002", "CN", "REVENUE", 9.9, "filing"),
        ]
        result = find_exposed_companies("CN", exposures, min_pct=10.0)
        assert len(result) == 1
        assert result[0].entity_id == "ENT001"


# ── Integration Tests ────────────────────────────────────────────────────


class TestIntegration:
    """Full pipeline integration tests with realistic data."""

    def test_g7_country_assessment(self):
        """Assess a typical G7 country (Germany-like)."""
        gov = {
            "regime_stability": 10,
            "policy_predictability": 12,
            "corruption": 15,
            "rule_of_law": 10,
            "civil_unrest": 8,
        }
        macro = {
            "gdp_growth": 1.5,
            "inflation": 3.2,
            "current_account": 5.0,
            "debt_gdp": 65.0,
            "reserves": 8.0,
            "currency_stability": 15.0,
        }
        sanctions = _no_sanctions()

        result = assess_country_risk(gov, macro, sanctions)
        assert result.classification in ("LOW_RISK", "MODERATE_RISK")
        assert result.political.score < 20

    def test_emerging_market_assessment(self):
        """Assess an emerging market (Turkey-like)."""
        gov = {
            "regime_stability": 55,
            "policy_predictability": 65,
            "corruption": 50,
            "rule_of_law": 55,
            "civil_unrest": 45,
        }
        macro = {
            "gdp_growth": 2.0,
            "inflation": 15.0,
            "current_account": -5.5,
            "debt_gdp": 70.0,
            "reserves": 3.5,
            "currency_stability": 70.0,
        }
        sanctions = {
            "active_programs_count": 1,
            "trade_restriction_intensity": 15.0,
            "trajectory": "STABLE",
        }
        result = assess_country_risk(gov, macro, sanctions)
        assert result.classification in ("ELEVATED_RISK", "HIGH_RISK")
        assert result.economic.inflation_score > 60

    def test_company_exposure_pipeline(self):
        """Map exposure → assess country → find affected companies."""
        # Map exposures for several companies
        all_exposures: list[CompanyExposure] = []

        # Company A: 40% Russia revenue
        segs_a = {"revenue_segments": [
            {"country_code": "RU", "pct": 40.0},
            {"country_code": "US", "pct": 60.0},
        ]}
        all_exposures.extend(map_company_exposure("A", segs_a))

        # Company B: 5% Russia
        segs_b = {"revenue_segments": [
            {"country_code": "RU", "pct": 5.0},
            {"country_code": "DE", "pct": 95.0},
        ]}
        all_exposures.extend(map_company_exposure("B", segs_b))

        # Company C: 20% Russia supply chain
        segs_c = {"revenue_segments": [{"country_code": "US", "pct": 100.0}]}
        rels_c = {"supply_chain": [{"country_code": "RU", "pct": 20.0}]}
        all_exposures.extend(map_company_exposure("C", segs_c, rels_c))

        # Find companies with significant RU exposure
        ru_exposed = find_exposed_companies("RU", all_exposures, min_pct=10.0)
        assert len(ru_exposed) == 2
        entity_ids = [e.entity_id for e in ru_exposed]
        assert "A" in entity_ids
        assert "C" in entity_ids

    def test_risk_trend_over_time(self):
        """Simulate deteriorating conditions and verify trend."""
        gov_stable = _switzerland_governance()
        macro_stable = _strong_economy()
        sanctions_none = _no_sanctions()

        result_t0 = assess_country_risk(gov_stable, macro_stable, sanctions_none)

        # Conditions deteriorate
        gov_worse = {
            "regime_stability": 50,
            "policy_predictability": 55,
            "corruption": 45,
            "rule_of_law": 50,
            "civil_unrest": 40,
        }
        macro_worse = {
            "gdp_growth": -1.0,
            "inflation": 8.0,
            "current_account": -4.0,
            "debt_gdp": 80.0,
            "reserves": 4.0,
            "currency_stability": 55.0,
        }
        sanctions_new = {
            "active_programs_count": 2,
            "trade_restriction_intensity": 30.0,
            "trajectory": "ESCALATING",
        }

        result_t1 = assess_country_risk(
            gov_worse, macro_worse, sanctions_new,
            prior_score=result_t0.composite_score,
        )
        assert result_t1.composite_score > result_t0.composite_score
        assert result_t1.trend == "DETERIORATING"
