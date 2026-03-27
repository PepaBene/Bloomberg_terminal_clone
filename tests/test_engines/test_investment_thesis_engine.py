"""Tests for Pillar 3 Phase 4B — Investment Thesis Engine."""

import pytest

from src.engines.investment_thesis_engine import (
    CONVICTION_THRESHOLDS,
    SECTOR_TEMPLATES,
    Catalyst,
    InvestmentDriver,
    InvestmentRisk,
    InvestmentThesisResult,
    ThesisQuality,
    ThesisValuation,
    ValuationScenario,
    assemble_thesis_prompt,
    build_investment_thesis,
    build_valuation_scenarios,
    compute_conviction_level,
    compute_thesis_diff,
    compute_thesis_quality,
    generate_elevator_pitch,
    generate_slide_outline,
    identify_catalysts,
    identify_key_drivers,
    identify_primary_risks,
    select_sector_template,
)


# ── Constants ─────────────────────────────────────────────────────────


class TestConstants:
    """Tests for module constants."""

    def test_sector_templates_has_11_sectors(self):
        assert len(SECTOR_TEMPLATES) == 11

    def test_each_template_has_required_keys(self):
        for sector, template in SECTOR_TEMPLATES.items():
            assert "drivers" in template, f"{sector} missing drivers"
            assert "risks" in template, f"{sector} missing risks"
            assert "multiples" in template, f"{sector} missing multiples"
            assert len(template["drivers"]) >= 3
            assert len(template["risks"]) >= 3

    def test_conviction_thresholds(self):
        assert CONVICTION_THRESHOLDS[25] == "low"
        assert CONVICTION_THRESHOLDS[50] == "medium"
        assert CONVICTION_THRESHOLDS[75] == "high"
        assert CONVICTION_THRESHOLDS[90] == "very_high"


# ── select_sector_template ────────────────────────────────────────────


class TestSelectSectorTemplate:
    """Tests for select_sector_template."""

    def test_exact_match(self):
        template = select_sector_template("Information Technology")
        assert "TAM expansion" in template["drivers"]

    def test_partial_match(self):
        template = select_sector_template("Technology")
        assert "drivers" in template
        assert len(template["drivers"]) >= 3

    def test_case_insensitive(self):
        template = select_sector_template("health care")
        assert "drivers" in template

    def test_unknown_sector_returns_default(self):
        template = select_sector_template("Unknown Sector XYZ")
        assert "drivers" in template
        assert "revenue growth" in template["drivers"]

    def test_energy_sector(self):
        template = select_sector_template("Energy")
        assert "commodity prices" in template["drivers"]

    def test_financials_sector(self):
        template = select_sector_template("Financials")
        assert "NIM expansion" in template["drivers"]


# ── identify_key_drivers ──────────────────────────────────────────────


class TestIdentifyKeyDrivers:
    """Tests for identify_key_drivers."""

    def test_identifies_revenue_growth_driver(self):
        financials = {"revenue_growth": 15.0}
        drivers = identify_key_drivers(financials, None, "Technology")
        driver_names = [d.driver for d in drivers]
        assert "Revenue growth trajectory" in driver_names
        rev_driver = [d for d in drivers if d.driver == "Revenue growth trajectory"][0]
        assert rev_driver.current_impact == "positive"

    def test_negative_revenue_growth(self):
        financials = {"revenue_growth": -5.0}
        drivers = identify_key_drivers(financials, None, "Technology")
        rev_driver = [d for d in drivers if d.driver == "Revenue growth trajectory"][0]
        assert rev_driver.current_impact == "negative"

    def test_margin_trend_identified(self):
        financials = {"revenue_growth": 10.0, "margin_trend": 2.5}
        drivers = identify_key_drivers(financials, None, "Technology")
        margin_drivers = [d for d in drivers if "margin" in d.driver.lower()]
        assert len(margin_drivers) >= 1

    def test_roic_quality_driver(self):
        financials = {"roic": 20.0}
        drivers = identify_key_drivers(financials, None, "Technology")
        roic_drivers = [d for d in drivers if "capital" in d.driver.lower()]
        assert len(roic_drivers) >= 1
        assert roic_drivers[0].current_impact == "positive"

    def test_transcript_themes_added(self):
        financials = {"revenue_growth": 8.0}
        transcripts = [{"themes": ["AI adoption momentum", "Cloud migration"], "date": "2024-Q3"}]
        drivers = identify_key_drivers(financials, transcripts, "Technology")
        driver_names = [d.driver for d in drivers]
        assert "AI adoption momentum" in driver_names

    def test_pads_with_template_defaults(self):
        financials = {}
        drivers = identify_key_drivers(financials, None, "Technology")
        assert len(drivers) >= 3

    def test_max_six_drivers(self):
        financials = {"revenue_growth": 10, "margin_trend": 2, "roic": 18, "fcf_growth": 15}
        transcripts = [{"themes": ["Theme1", "Theme2", "Theme3"], "date": "Q1"}]
        drivers = identify_key_drivers(financials, transcripts, "Technology")
        assert len(drivers) <= 6


# ── identify_primary_risks ────────────────────────────────────────────


class TestIdentifyPrimaryRisks:
    """Tests for identify_primary_risks."""

    def test_processes_risk_factors(self):
        risk_factors = [
            {"description": "Competition from large players", "severity": "high", "mitigation": "Innovate"},
        ]
        risks = identify_primary_risks(risk_factors, None, "Technology")
        assert len(risks) >= 1
        assert risks[0].severity == "high"
        assert risks[0].probability == 0.6

    def test_credit_risk_added_high_leverage(self):
        risks = identify_primary_risks([], {"leverage_ratio": 6.0, "interest_coverage": 1.5}, "Industrials")
        leverage_risks = [r for r in risks if "leverage" in r.risk.lower()]
        assert len(leverage_risks) >= 1
        assert leverage_risks[0].severity == "high"

    def test_credit_risk_moderate_leverage(self):
        risks = identify_primary_risks([], {"leverage_ratio": 4.5, "interest_coverage": 2.5}, "Industrials")
        leverage_risks = [r for r in risks if "leverage" in r.risk.lower()]
        assert len(leverage_risks) >= 1
        assert leverage_risks[0].severity == "medium"

    def test_pads_with_defaults(self):
        risks = identify_primary_risks([], None, "Technology")
        assert len(risks) >= 3

    def test_max_six_risks(self):
        many_risks = [{"description": f"Risk {i}", "severity": "medium"} for i in range(10)]
        risks = identify_primary_risks(many_risks, {"leverage_ratio": 5.0, "interest_coverage": 1.0}, "Tech")
        assert len(risks) <= 6


# ── build_valuation_scenarios ─────────────────────────────────────────


class TestBuildValuationScenarios:
    """Tests for build_valuation_scenarios."""

    def test_basic_valuation(self):
        financials = {"current_price": 100.0, "eps": 5.0, "ebitda": 1000.0}
        consensus = {"target_price": 120.0}
        val = build_valuation_scenarios(financials, consensus, None)
        assert isinstance(val, ThesisValuation)
        assert val.current_price == 100.0

    def test_bull_above_base(self):
        financials = {"current_price": 100.0, "eps": 5.0, "ebitda": 1000.0}
        consensus = {"target_price": 110.0}
        val = build_valuation_scenarios(financials, consensus, None)
        assert val.bull.target_price > val.base.target_price
        assert val.base.target_price > val.bear.target_price

    def test_implied_returns_calculated(self):
        financials = {"current_price": 100.0, "eps": 5.0, "ebitda": 1000.0}
        consensus = {"target_price": 120.0}
        val = build_valuation_scenarios(financials, consensus, None)
        assert val.base.implied_return == pytest.approx(20.0, abs=0.1)
        assert val.bear.implied_return < 0

    def test_no_consensus_uses_default(self):
        financials = {"current_price": 100.0, "eps": 5.0, "ebitda": 1000.0}
        val = build_valuation_scenarios(financials, None, None)
        assert val.base.target_price > 0

    def test_sector_multiples_used(self):
        financials = {"current_price": 100.0, "eps": 5.0, "ebitda": 1000.0}
        multiples = {"pe_ratio": 25.0}
        val = build_valuation_scenarios(financials, {"target_price": 120.0}, multiples)
        assert val.bull.assumptions["pe_multiple"] > 25.0


# ── identify_catalysts ────────────────────────────────────────────────


class TestIdentifyCatalysts:
    """Tests for identify_catalysts."""

    def test_processes_company_events(self):
        events = [{"type": "M&A", "description": "Potential acquisition", "timing": "Q2 2025", "probability": 0.3}]
        catalysts = identify_catalysts(events, [], None)
        assert len(catalysts) >= 1
        assert catalysts[0].catalyst_type == "M&A"

    def test_earnings_dates_added(self):
        catalysts = identify_catalysts([], ["2025-04-15", "2025-07-20"], None)
        assert len(catalysts) == 2
        assert all(c.catalyst_type == "earnings" for c in catalysts)
        assert catalysts[0].probability == 1.0

    def test_sector_events_added(self):
        sector = [{"type": "regulatory", "description": "FDA ruling", "timing": "H2 2025", "probability": 0.6}]
        catalysts = identify_catalysts([], [], sector)
        assert len(catalysts) >= 1

    def test_max_eight_catalysts(self):
        events = [{"type": "event", "description": f"Event {i}", "timing": "TBD"} for i in range(10)]
        dates = ["2025-01-01", "2025-04-01", "2025-07-01"]
        catalysts = identify_catalysts(events, dates, None)
        assert len(catalysts) <= 8

    def test_empty_inputs(self):
        catalysts = identify_catalysts([], [], None)
        assert catalysts == []


# ── compute_conviction_level ──────────────────────────────────────────


class TestComputeConvictionLevel:
    """Tests for compute_conviction_level."""

    def _make_valuation(self, base_return: float) -> ThesisValuation:
        return ThesisValuation(
            current_price=100.0,
            bull=ValuationScenario(130.0, 30.0, {}, []),
            base=ValuationScenario(100 + base_return, base_return, {}, []),
            bear=ValuationScenario(80.0, -20.0, {}, []),
        )

    def test_high_conviction_many_positive_drivers(self):
        drivers = [InvestmentDriver("D1", "positive", "near_term", "evidence", []),
                    InvestmentDriver("D2", "positive", "near_term", "evidence", []),
                    InvestmentDriver("D3", "positive", "medium_term", "evidence", [])]
        risks = [InvestmentRisk("R1", "low", 0.2, -5.0, "monitor")]
        val = self._make_valuation(25.0)
        level = compute_conviction_level(drivers, risks, val)
        assert level in ("high", "very_high")

    def test_low_conviction_many_risks(self):
        drivers = [InvestmentDriver("D1", "negative", "near_term", "evidence", [])]
        risks = [InvestmentRisk("R1", "high", 0.7, -20.0, "monitor"),
                 InvestmentRisk("R2", "critical", 0.8, -30.0, "monitor"),
                 InvestmentRisk("R3", "high", 0.6, -15.0, "monitor")]
        val = self._make_valuation(-10.0)
        level = compute_conviction_level(drivers, risks, val)
        assert level == "low"

    def test_medium_conviction_balanced(self):
        drivers = [InvestmentDriver("D1", "positive", "near_term", "ev", []),
                    InvestmentDriver("D2", "neutral", "medium_term", "ev", [])]
        risks = [InvestmentRisk("R1", "medium", 0.4, -10.0, "monitor")]
        val = self._make_valuation(10.0)
        level = compute_conviction_level(drivers, risks, val)
        assert level in ("medium", "high")


# ── compute_thesis_quality ────────────────────────────────────────────


class TestComputeThesisQuality:
    """Tests for compute_thesis_quality."""

    def test_full_data_high_quality(self):
        data = {
            "has_financials": True, "has_transcripts": True, "has_filings": True,
            "has_consensus": True, "has_credit": True,
            "driver_count": 4, "risk_count": 4,
        }
        quality = compute_thesis_quality(data)
        assert quality.completeness_score == 100.0
        assert quality.data_quality_score >= 80

    def test_no_data_low_quality(self):
        data = {
            "has_financials": False, "has_transcripts": False, "has_filings": False,
            "has_consensus": False, "has_credit": False,
            "driver_count": 1, "risk_count": 0,
        }
        quality = compute_thesis_quality(data)
        assert quality.completeness_score == 0.0
        assert quality.coherence_score <= 30

    def test_partial_data(self):
        data = {
            "has_financials": True, "has_transcripts": False, "has_filings": True,
            "has_consensus": False, "has_credit": False,
            "driver_count": 3, "risk_count": 2,
        }
        quality = compute_thesis_quality(data)
        assert 30 < quality.completeness_score < 70


# ── generate_elevator_pitch ───────────────────────────────────────────


class TestGenerateElevatorPitch:
    """Tests for generate_elevator_pitch."""

    def test_includes_entity_name(self):
        drivers = [InvestmentDriver("Growth", "positive", "near_term", "", [])]
        val = ThesisValuation(
            100.0,
            ValuationScenario(140.0, 40.0, {}, []),
            ValuationScenario(120.0, 20.0, {}, []),
            ValuationScenario(80.0, -20.0, {}, []),
        )
        pitch = generate_elevator_pitch("Apple Inc.", "Growth Thesis", drivers, val)
        assert "Apple Inc." in pitch

    def test_max_length_500(self):
        drivers = [InvestmentDriver(f"Driver {i}", "positive", "near_term", "", []) for i in range(10)]
        val = ThesisValuation(100.0,
                              ValuationScenario(200.0, 100.0, {}, []),
                              ValuationScenario(150.0, 50.0, {}, []),
                              ValuationScenario(50.0, -50.0, {}, []))
        pitch = generate_elevator_pitch("Company", "Thesis", drivers, val)
        assert len(pitch) <= 500

    def test_includes_return_info(self):
        drivers = [InvestmentDriver("Growth", "positive", "near_term", "", [])]
        val = ThesisValuation(100.0,
                              ValuationScenario(130.0, 30.0, {}, []),
                              ValuationScenario(115.0, 15.0, {}, []),
                              ValuationScenario(85.0, -15.0, {}, []))
        pitch = generate_elevator_pitch("Test Co", "Test", drivers, val)
        assert "upside" in pitch or "downside" in pitch


# ── generate_slide_outline ────────────────────────────────────────────


class TestGenerateSlideOutline:
    """Tests for generate_slide_outline."""

    def test_generates_five_slides(self):
        thesis = InvestmentThesisResult(
            title="Test Thesis", horizon="12M", conviction="high",
            summary_template="summary", elevator_pitch="pitch",
            drivers=[InvestmentDriver("D1", "positive", "near_term", "", [])],
            risks=[InvestmentRisk("R1", "medium", 0.3, -10.0, "monitor")],
            valuation=ThesisValuation(100.0,
                                      ValuationScenario(130.0, 30.0, {}, []),
                                      ValuationScenario(115.0, 15.0, {}, []),
                                      ValuationScenario(85.0, -15.0, {}, [])),
            catalysts=[Catalyst("earnings", "Q4 report", "2025-01", 1.0, "mixed")],
            quality=ThesisQuality(80.0, 80.0, 80.0),
            slide_outline=[],
        )
        slides = generate_slide_outline(thesis)
        assert len(slides) == 5
        assert slides[0]["slide_number"] == 1
        assert "Investment Thesis" in slides[0]["title"]

    def test_slide_has_bullet_points(self):
        thesis = InvestmentThesisResult(
            title="Test", horizon="12M", conviction="medium",
            summary_template="", elevator_pitch="pitch",
            drivers=[InvestmentDriver("D1", "positive", "near_term", "", [])],
            risks=[InvestmentRisk("R1", "low", 0.2, -5.0, "ok")],
            valuation=ThesisValuation(100.0,
                                      ValuationScenario(120.0, 20.0, {}, []),
                                      ValuationScenario(110.0, 10.0, {}, []),
                                      ValuationScenario(90.0, -10.0, {}, [])),
            catalysts=[], quality=ThesisQuality(50, 50, 50),
            slide_outline=[],
        )
        slides = generate_slide_outline(thesis)
        for slide in slides:
            assert "bullet_points" in slide


# ── assemble_thesis_prompt ────────────────────────────────────────────


class TestAssembleThesisPrompt:
    """Tests for assemble_thesis_prompt."""

    def test_basic_prompt(self):
        template = {"drivers": ["growth"], "risks": ["competition"]}
        data_context = {"financials_summary": "Revenue: $100B"}
        prompt = assemble_thesis_prompt("Apple Inc.", data_context, template)
        assert "system_message" in prompt
        assert "user_message" in prompt
        assert "Apple Inc." in prompt["user_message"]

    def test_template_included(self):
        template = {"drivers": ["TAM", "AI"], "risks": ["regulation"]}
        prompt = assemble_thesis_prompt("TestCo", {}, template)
        assert prompt["template_drivers"] == ["TAM", "AI"]
        assert prompt["template_risks"] == ["regulation"]


# ── compute_thesis_diff ───────────────────────────────────────────────


class TestComputeThesisDiff:
    """Tests for compute_thesis_diff."""

    def test_no_changes(self):
        data = {"conviction_level": "high", "drivers": [], "valuation": {}}
        diff = compute_thesis_diff(data, data)
        assert diff["changed_fields"] == []
        assert diff["conviction_change"] is None

    def test_conviction_change_detected(self):
        current = {"conviction_level": "high", "drivers": [], "valuation": {}}
        previous = {"conviction_level": "medium", "drivers": [], "valuation": {}}
        diff = compute_thesis_diff(current, previous)
        assert "conviction_level" in diff["changed_fields"]
        assert diff["conviction_change"] == "medium -> high"

    def test_driver_changes_detected(self):
        current = {"conviction_level": "high",
                    "drivers": [{"driver": "A"}, {"driver": "C"}],
                    "valuation": {}}
        previous = {"conviction_level": "high",
                     "drivers": [{"driver": "A"}, {"driver": "B"}],
                     "valuation": {}}
        diff = compute_thesis_diff(current, previous)
        assert "C" in diff["new_drivers"]
        assert "B" in diff["removed_drivers"]

    def test_valuation_changes_detected(self):
        current = {"conviction_level": "high", "drivers": [],
                    "valuation": {"base": {"target_price": 120}}}
        previous = {"conviction_level": "high", "drivers": [],
                     "valuation": {"base": {"target_price": 100}}}
        diff = compute_thesis_diff(current, previous)
        assert "base" in diff["valuation_changes"]
        assert diff["valuation_changes"]["base"]["change_pct"] == 20.0

    def test_title_change_detected(self):
        current = {"conviction_level": "high", "drivers": [], "valuation": {},
                    "thesis_title": "New Title"}
        previous = {"conviction_level": "high", "drivers": [], "valuation": {},
                     "thesis_title": "Old Title"}
        diff = compute_thesis_diff(current, previous)
        assert "thesis_title" in diff["changed_fields"]


# ── build_investment_thesis ───────────────────────────────────────────


class TestBuildInvestmentThesis:
    """Tests for build_investment_thesis."""

    @pytest.fixture
    def sample_entity_data(self):
        return {
            "name": "Apple Inc.",
            "sector": "Information Technology",
            "events": [{"type": "product", "description": "iPhone launch", "timing": "Q4 2025"}],
            "earnings_dates": ["2025-04-25"],
        }

    @pytest.fixture
    def sample_financials(self):
        return {
            "current_price": 195.0,
            "eps": 6.5,
            "ebitda": 130000.0,
            "revenue_growth": 8.5,
            "margin_trend": 1.2,
            "roic": 25.0,
            "fcf_growth": 12.0,
        }

    @pytest.fixture
    def sample_filings(self):
        return {
            "risk_factors": [
                {"description": "Supply chain concentration risk", "severity": "high"},
                {"description": "Regulatory scrutiny in EU", "severity": "medium"},
            ]
        }

    def test_full_thesis_generation(self, sample_entity_data, sample_financials, sample_filings):
        consensus = {"target_price": 220.0, "eps_estimate": 7.0}
        thesis = build_investment_thesis(
            sample_entity_data, sample_financials, sample_filings,
            transcripts=None, consensus=consensus,
        )
        assert isinstance(thesis, InvestmentThesisResult)
        assert "Apple Inc." in thesis.title
        assert thesis.conviction in ("low", "medium", "high", "very_high")
        assert len(thesis.drivers) >= 3
        assert len(thesis.risks) >= 2
        assert thesis.valuation.current_price == 195.0
        assert len(thesis.slide_outline) == 5

    def test_thesis_without_optional_data(self, sample_entity_data, sample_financials, sample_filings):
        thesis = build_investment_thesis(
            sample_entity_data, sample_financials, sample_filings,
            transcripts=None, consensus=None,
        )
        assert isinstance(thesis, InvestmentThesisResult)
        assert thesis.valuation.base.target_price > 0

    def test_thesis_elevator_pitch_populated(self, sample_entity_data, sample_financials, sample_filings):
        thesis = build_investment_thesis(
            sample_entity_data, sample_financials, sample_filings, None, None,
        )
        assert len(thesis.elevator_pitch) > 0
        assert "Apple Inc." in thesis.elevator_pitch

    def test_thesis_quality_computed(self, sample_entity_data, sample_financials, sample_filings):
        thesis = build_investment_thesis(
            sample_entity_data, sample_financials, sample_filings, None, None,
        )
        assert thesis.quality.completeness_score > 0
        assert thesis.quality.data_quality_score > 0
