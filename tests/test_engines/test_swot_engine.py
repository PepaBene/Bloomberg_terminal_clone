"""Tests for the SWOT synthesis engine (deterministic rules over real signals)."""

from src.engines.swot_engine import (
    KNOWN_SIGNAL_KEYS,
    SWOTItem,
    SWOTResult,
    derive_swot,
)


def _metrics(items: list[SWOTItem]) -> set[str]:
    return {i.metric for i in items}


def _texts(items: list[SWOTItem]) -> list[str]:
    return [i.text for i in items]


# ── Empty input ───────────────────────────────────────────────────────────


class TestEmptySignals:
    def test_empty_dict_all_buckets_empty(self):
        result = derive_swot({})
        assert isinstance(result, SWOTResult)
        assert result.strengths == []
        assert result.weaknesses == []
        assert result.opportunities == []
        assert result.threats == []
        assert result.signals_available == 0

    def test_all_known_keys_present_but_none(self):
        """Explicit None for every key must behave identically to omission."""
        signals = {k: None for k in KNOWN_SIGNAL_KEYS}
        result = derive_swot(signals)
        assert result.strengths == []
        assert result.weaknesses == []
        assert result.opportunities == []
        assert result.threats == []
        assert result.signals_available == 0


# ── Composite scenarios ──────────────────────────────────────────────────


class TestStrongCompanyProfile:
    """A company that is strong across the board."""

    STRONG_SIGNALS = {
        "moat_width": "WIDE",
        "moat_score": 88.0,
        "dominant_moat_source": "network_effects",
        "market_share_trend": "GAINING",
        "diversification_score": 85.0,
        "cyclicality_score": 15.0,
        "disruption_vulnerability": 10.0,
        "switching_cost_score": 75.0,
        "operating_leverage": 1.2,
        "net_debt_ebitda": 0.4,
        "z_score": 5.5,
        "refinancing_risk_score": 5.0,
        "liquidity_ratio": 2.5,
        "overall_score": 90.0,
        "roic_vs_wacc_spread": 0.12,
        "overall_quality_score": 92.0,
        "governance_score": 88.0,
        "beneish_m_score": -2.5,
        "customer_top1_pct": 4.0,
        "overall_concentration_risk": "LOW",
        "overall_risk_score": 8.0,
    }

    def test_multiple_strengths_fire(self):
        result = derive_swot(self.STRONG_SIGNALS)
        assert len(result.strengths) >= 6
        metrics = _metrics(result.strengths)
        assert "moat_score" in metrics
        assert "overall_score" in metrics
        assert "z_score" in metrics
        assert "net_debt_ebitda" in metrics

    def test_no_weaknesses_or_threats(self):
        result = derive_swot(self.STRONG_SIGNALS)
        assert result.weaknesses == []
        assert result.threats == []

    def test_signals_available_full(self):
        result = derive_swot(self.STRONG_SIGNALS)
        assert result.signals_available == len(KNOWN_SIGNAL_KEYS)

    def test_specific_strength_texts(self):
        result = derive_swot(self.STRONG_SIGNALS)
        texts = " ".join(_texts(result.strengths))
        assert "moat" in texts.lower()
        assert "capital allocation" in texts.lower()


class TestWeakRiskyCompanyProfile:
    """A company that is weak/risky across the board."""

    WEAK_SIGNALS = {
        "moat_width": "NONE",
        "moat_score": 15.0,
        "dominant_moat_source": None,
        "market_share_trend": "LOSING",
        "diversification_score": 12.0,
        "cyclicality_score": 85.0,
        "disruption_vulnerability": 80.0,
        "switching_cost_score": 10.0,
        "operating_leverage": -2.0,
        "net_debt_ebitda": 6.5,
        "z_score": 1.1,
        "refinancing_risk_score": 78.0,
        "liquidity_ratio": 0.8,
        "overall_score": 22.0,
        "roic_vs_wacc_spread": -0.05,
        "overall_quality_score": 30.0,
        "governance_score": 25.0,
        "beneish_m_score": -1.2,
        "customer_top1_pct": 55.0,
        "overall_concentration_risk": "HIGH",
        "overall_risk_score": 82.0,
    }

    def test_multiple_weaknesses_fire(self):
        result = derive_swot(self.WEAK_SIGNALS)
        assert len(result.weaknesses) >= 4
        metrics = _metrics(result.weaknesses)
        assert "moat_score" in metrics
        assert "net_debt_ebitda" in metrics
        assert "customer_top1_pct" in metrics

    def test_multiple_threats_fire(self):
        result = derive_swot(self.WEAK_SIGNALS)
        assert len(result.threats) >= 4
        metrics = _metrics(result.threats)
        assert "cyclicality_score" in metrics
        assert "disruption_vulnerability" in metrics
        assert "beneish_m_score" in metrics
        assert "refinancing_risk_score" in metrics

    def test_specific_weakness_values(self):
        result = derive_swot(self.WEAK_SIGNALS)
        leverage_item = next(i for i in result.weaknesses if i.metric == "net_debt_ebitda")
        assert leverage_item.value == 6.5
        assert leverage_item.severity in ("LOW", "MODERATE", "HIGH")

        conc_item = next(i for i in result.weaknesses if i.metric == "customer_top1_pct")
        assert conc_item.value == 55.0

    def test_no_strengths(self):
        result = derive_swot(self.WEAK_SIGNALS)
        assert result.strengths == []


# ── Per-rule isolation tests ─────────────────────────────────────────────


class TestStrengthRulesIsolated:
    def test_wide_moat(self):
        result = derive_swot({"moat_width": "WIDE", "moat_score": 80.0})
        assert len(result.strengths) == 1
        assert result.strengths[0].metric == "moat_score"
        assert result.strengths[0].value == 80.0
        assert result.weaknesses == result.opportunities == result.threats == []

    def test_high_capital_allocation(self):
        result = derive_swot({"overall_score": 75.0})
        assert len(result.strengths) == 1
        assert result.strengths[0].metric == "overall_score"
        assert result.strengths[0].value == 75.0

    def test_positive_roic_spread(self):
        result = derive_swot({"roic_vs_wacc_spread": 0.05})
        assert len(result.strengths) == 1
        assert result.strengths[0].metric == "roic_vs_wacc_spread"
        assert result.strengths[0].value == 0.05

    def test_strong_balance_sheet(self):
        result = derive_swot({"z_score": 3.5})
        assert len(result.strengths) == 1
        assert result.strengths[0].metric == "z_score"

    def test_low_leverage(self):
        result = derive_swot({"net_debt_ebitda": 0.5})
        assert len(result.strengths) == 1
        assert result.strengths[0].metric == "net_debt_ebitda"
        assert result.strengths[0].value == 0.5

    def test_high_diversification(self):
        result = derive_swot({"diversification_score": 71.0})
        assert len(result.strengths) == 1
        assert result.strengths[0].metric == "diversification_score"

    def test_high_management_quality(self):
        result = derive_swot({"overall_quality_score": 80.0})
        assert len(result.strengths) == 1
        assert result.strengths[0].metric == "overall_quality_score"

    def test_gaining_share(self):
        result = derive_swot({"market_share_trend": "GAINING"})
        assert len(result.strengths) == 1
        assert result.strengths[0].metric == "market_share_trend"
        assert result.strengths[0].value == "GAINING"


class TestWeaknessRulesIsolated:
    def test_no_narrow_moat(self):
        result = derive_swot({"moat_width": "NARROW", "moat_score": 25.0})
        assert len(result.weaknesses) == 1
        assert result.weaknesses[0].metric == "moat_score"
        assert result.weaknesses[0].value == 25.0

    def test_no_narrow_moat_requires_low_score(self):
        """NARROW width alone (score missing) must not fire -- avoid false negatives on missing data."""
        result = derive_swot({"moat_width": "NARROW"})
        assert result.weaknesses == []

    def test_elevated_leverage(self):
        result = derive_swot({"net_debt_ebitda": 5.0})
        assert len(result.weaknesses) == 1
        assert result.weaknesses[0].metric == "net_debt_ebitda"
        assert result.weaknesses[0].value == 5.0

    def test_weak_capital_allocation(self):
        result = derive_swot({"overall_score": 35.0})
        assert len(result.weaknesses) == 1
        assert result.weaknesses[0].metric == "overall_score"

    def test_high_customer_concentration(self):
        result = derive_swot({"customer_top1_pct": 40.0})
        assert len(result.weaknesses) == 1
        assert result.weaknesses[0].metric == "customer_top1_pct"
        assert result.weaknesses[0].value == 40.0

    def test_losing_share(self):
        result = derive_swot({"market_share_trend": "LOSING"})
        assert len(result.weaknesses) == 1
        assert result.weaknesses[0].metric == "market_share_trend"
        assert result.weaknesses[0].value == "LOSING"

    def test_low_diversification(self):
        result = derive_swot({"diversification_score": 20.0})
        assert len(result.weaknesses) == 1
        assert result.weaknesses[0].metric == "diversification_score"


class TestOpportunityRulesIsolated:
    def test_underappreciated_switching_costs(self):
        result = derive_swot({"switching_cost_score": 65.0, "moat_width": "NARROW"})
        assert len(result.opportunities) == 1
        assert result.opportunities[0].metric == "switching_cost_score"

    def test_underappreciated_switching_costs_suppressed_if_already_wide(self):
        """If the moat is already WIDE, the opportunity is moot -- only the strength should fire."""
        result = derive_swot({"switching_cost_score": 65.0, "moat_width": "WIDE"})
        assert result.opportunities == []

    def test_balance_sheet_capacity(self):
        result = derive_swot({"net_debt_ebitda": 1.0, "liquidity_ratio": 2.0})
        assert len(result.opportunities) == 1
        assert result.opportunities[0].metric == "net_debt_ebitda"

    def test_op_leverage_headroom(self):
        result = derive_swot({"operating_leverage": 0.8})
        assert len(result.opportunities) == 1
        assert result.opportunities[0].metric == "operating_leverage"
        assert result.opportunities[0].value == 0.8

    def test_op_leverage_headroom_excludes_negative(self):
        result = derive_swot({"operating_leverage": -0.5})
        assert result.opportunities == []


class TestThreatRulesIsolated:
    def test_high_cyclicality(self):
        result = derive_swot({"cyclicality_score": 75.0})
        assert len(result.threats) == 1
        assert result.threats[0].metric == "cyclicality_score"

    def test_high_disruption_vulnerability(self):
        result = derive_swot({"disruption_vulnerability": 70.0})
        assert len(result.threats) == 1
        assert result.threats[0].metric == "disruption_vulnerability"

    def test_elevated_beneish(self):
        result = derive_swot({"beneish_m_score": -1.0})
        assert len(result.threats) == 1
        assert result.threats[0].metric == "beneish_m_score"
        assert result.threats[0].value == -1.0

    def test_high_concentration_risk_via_label(self):
        result = derive_swot({"overall_concentration_risk": "HIGH"})
        assert len(result.threats) == 1
        assert result.threats[0].metric == "overall_concentration_risk"

    def test_high_concentration_risk_via_score(self):
        result = derive_swot({"overall_risk_score": 75.0})
        assert len(result.threats) == 1
        assert result.threats[0].metric == "overall_risk_score"
        assert result.threats[0].value == 75.0

    def test_moderate_concentration_does_not_fire(self):
        result = derive_swot({"overall_concentration_risk": "MODERATE", "overall_risk_score": 50.0})
        assert result.threats == []

    def test_refinancing_risk(self):
        result = derive_swot({"refinancing_risk_score": 65.0})
        assert len(result.threats) == 1
        assert result.threats[0].metric == "refinancing_risk_score"
        assert result.threats[0].value == 65.0


# ── Threshold boundary cases ──────────────────────────────────────────────


class TestThresholdBoundaries:
    """Document and lock in which side of > vs >= each rule uses."""

    def test_net_debt_ebitda_elevated_leverage_boundary(self):
        """Weakness rule uses strict '>' -- exactly 4.0 must NOT fire."""
        result = derive_swot({"net_debt_ebitda": 4.0})
        assert result.weaknesses == []

        result_above = derive_swot({"net_debt_ebitda": 4.01})
        assert len(result_above.weaknesses) == 1

    def test_net_debt_ebitda_low_leverage_boundary(self):
        """Strength rule uses strict '<' -- exactly 1.0 must NOT fire."""
        result = derive_swot({"net_debt_ebitda": 1.0})
        assert result.strengths == []

        result_below = derive_swot({"net_debt_ebitda": 0.99})
        assert len(result_below.strengths) == 1

    def test_z_score_safe_zone_boundary(self):
        """Strict '>' -- exactly 2.99 must NOT fire, 3.0 must."""
        result_at = derive_swot({"z_score": 2.99})
        assert result_at.strengths == []

        result_above = derive_swot({"z_score": 3.0})
        assert len(result_above.strengths) == 1

    def test_capital_allocation_strength_boundary(self):
        """Strength rule uses '>=' -- exactly 70 must fire."""
        result = derive_swot({"overall_score": 70.0})
        assert len(result.strengths) == 1

    def test_capital_allocation_weakness_boundary(self):
        """Weakness rule uses strict '<' -- exactly 40 must NOT fire."""
        result = derive_swot({"overall_score": 40.0})
        assert result.weaknesses == []

        result_below = derive_swot({"overall_score": 39.9})
        assert len(result_below.weaknesses) == 1

    def test_beneish_m_score_boundary(self):
        """Strict '>' -- exactly -1.78 must NOT fire."""
        result = derive_swot({"beneish_m_score": -1.78})
        assert result.threats == []

        result_above = derive_swot({"beneish_m_score": -1.77})
        assert len(result_above.threats) == 1


# ── Robustness / no-crash on unexpected input ────────────────────────────


class TestRobustness:
    def test_unknown_extra_keys_ignored(self):
        result = derive_swot({"some_future_signal": 42, "moat_width": "WIDE", "moat_score": 90.0})
        assert len(result.strengths) == 1

    def test_wrong_type_values_do_not_crash(self):
        """A malformed value (wrong type) should be skipped, not raise."""
        signals = {
            "net_debt_ebitda": "not_a_number",
            "z_score": None,
            "overall_score": [1, 2, 3],
        }
        result = derive_swot(signals)
        assert isinstance(result, SWOTResult)
        assert result.strengths == []
        assert result.weaknesses == []
