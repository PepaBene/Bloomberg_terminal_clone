"""Tests for Pillar 3 Phase 3C — Part 16: Cross-Asset Signal Narrative Engine."""

import pytest

from src.engines.cross_asset_narrative import (
    classify_signal_severity,
    compute_historical_divergence_outcome,
    detect_cheap_both_signal,
    detect_fallen_angel_overhang,
    generate_bond_equity_comparison,
    generate_divergence_narrative,
)


# ── generate_divergence_narrative ─────────────────────────────────────────


class TestGenerateDivergenceNarrative:
    def test_equity_leads_credit_decline(self):
        result = generate_divergence_narrative(
            "EQUITY_LEADS_CREDIT", "TestCorp", -5.0, 2.0, "Financials"
        )
        assert "TestCorp" in result
        assert "Financials" in result
        assert "declined" in result
        assert "credit follows" in result.lower() or "equity is leading" in result.lower()

    def test_equity_leads_credit_rally(self):
        result = generate_divergence_narrative(
            "EQUITY_LEADS_CREDIT", "TestCorp", 8.0, -5.0
        )
        assert "rallied" in result

    def test_credit_leads_equity(self):
        result = generate_divergence_narrative(
            "CREDIT_LEADS_EQUITY", "BondCo", 0.5, 30.0, "Energy"
        )
        assert "BondCo" in result
        assert "widened" in result
        assert "credit markets often lead" in result.lower()

    def test_credit_leads_equity_small_move(self):
        result = generate_divergence_narrative(
            "CREDIT_LEADS_EQUITY", "SmallCo", 1.0, 20.0
        )
        assert "not yet reacted" in result

    def test_simultaneous_stress(self):
        result = generate_divergence_narrative(
            "SIMULTANEOUS_STRESS", "StressCo", -10.0, 80.0
        )
        assert "simultaneous stress" in result.lower()
        assert "default" in result.lower() or "deterioration" in result.lower()

    def test_unknown_signal_type(self):
        result = generate_divergence_narrative(
            "CUSTOM_SIGNAL", "TestCorp", 3.0, -5.0
        )
        assert "TestCorp" in result
        assert "CUSTOM_SIGNAL" in result

    def test_no_sector(self):
        result = generate_divergence_narrative(
            "EQUITY_LEADS_CREDIT", "NoSectorCo", -3.0, 5.0, None
        )
        assert "NoSectorCo" in result
        assert "(" not in result.split("NoSectorCo")[1][:3]  # no sector parenthetical


# ── detect_fallen_angel_overhang ──────────────────────────────────────────


class TestDetectFallenAngelOverhang:
    def test_high_risk(self):
        result = detect_fallen_angel_overhang("BBB-", "DETERIORATING", 60.0)
        assert result is not None
        assert result["risk_level"] == "HIGH"
        assert result["forced_selling_pct"] == 60.0

    def test_medium_risk(self):
        result = detect_fallen_angel_overhang("BBB-", "DETERIORATING", 35.0)
        assert result is not None
        assert result["risk_level"] == "MEDIUM"

    def test_low_risk_bbb(self):
        result = detect_fallen_angel_overhang("BBB", "DETERIORATING", 20.0)
        assert result is not None
        assert result["risk_level"] == "LOW"

    def test_no_risk_stable(self):
        result = detect_fallen_angel_overhang("BBB-", "STABLE", 60.0)
        assert result is None

    def test_no_risk_high_rating(self):
        result = detect_fallen_angel_overhang("A", "DETERIORATING", 60.0)
        assert result is None

    def test_no_risk_hy(self):
        result = detect_fallen_angel_overhang("BB+", "DETERIORATING", 60.0)
        assert result is None


# ── detect_cheap_both_signal ──────────────────────────────────────────────


class TestDetectCheapBothSignal:
    def test_combined_signal(self):
        result = detect_cheap_both_signal(pe=8.0, fcf_yield=10.0, spread_percentile=80.0, z_score=3.5)
        assert result is not None
        assert result["combined_signal"] is True
        assert result["equity_cheap"] is True
        assert result["credit_cheap"] is True

    def test_equity_cheap_only(self):
        result = detect_cheap_both_signal(pe=7.0, spread_percentile=40.0)
        assert result is not None
        assert result["equity_cheap"] is True
        assert result["credit_cheap"] is False
        assert result["combined_signal"] is False

    def test_credit_cheap_only(self):
        result = detect_cheap_both_signal(pe=20.0, spread_percentile=85.0)
        assert result is not None
        assert result["equity_cheap"] is False
        assert result["credit_cheap"] is True

    def test_distress_override(self):
        result = detect_cheap_both_signal(pe=5.0, spread_percentile=90.0, z_score=1.2)
        assert result is not None
        assert result["combined_signal"] is False
        assert any("distress" in s.lower() for s in result["supporting_metrics"])

    def test_no_signal(self):
        result = detect_cheap_both_signal(pe=25.0, spread_percentile=30.0)
        assert result is None

    def test_fcf_yield_trigger(self):
        result = detect_cheap_both_signal(pe=20.0, fcf_yield=12.0, spread_percentile=50.0)
        assert result is not None
        assert result["equity_cheap"] is True


# ── generate_bond_equity_comparison ───────────────────────────────────────


class TestGenerateBondEquityComparison:
    def test_equity_cheap(self):
        data = {
            "entity_name": "TestCorp",
            "equity_yield_pct": 8.0,
            "bond_yield_pct": 5.0,
            "spread_bps": 200,
            "credit_rating": "BBB",
            "leverage_ratio": 1.5,
        }
        result = generate_bond_equity_comparison(data)
        assert "TestCorp" in result
        assert "equity appears relatively cheap" in result.lower()

    def test_bond_better(self):
        data = {
            "entity_name": "BondCo",
            "equity_yield_pct": 3.0,
            "bond_yield_pct": 6.5,
            "spread_bps": 300,
            "credit_rating": "BB",
        }
        result = generate_bond_equity_comparison(data)
        assert "bond" in result.lower() and "better" in result.lower()

    def test_high_leverage(self):
        data = {
            "entity_name": "LevCo",
            "equity_yield_pct": 5.0,
            "bond_yield_pct": 5.0,
            "leverage_ratio": 5.0,
        }
        result = generate_bond_equity_comparison(data)
        assert "seniority" in result.lower()

    def test_high_beta(self):
        data = {
            "entity_name": "VolCo",
            "equity_yield_pct": 5.0,
            "bond_yield_pct": 5.0,
            "equity_beta": 1.5,
        }
        result = generate_bond_equity_comparison(data)
        assert "downside protection" in result.lower()


# ── classify_signal_severity ──────────────────────────────────────────────


class TestClassifySignalSeverity:
    def test_simultaneous_stress_critical(self):
        assert classify_signal_severity("SIMULTANEOUS_STRESS", 120.0, 12.0) == "CRITICAL"

    def test_simultaneous_stress_high(self):
        assert classify_signal_severity("SIMULTANEOUS_STRESS", 60.0, 6.0) == "HIGH"

    def test_simultaneous_stress_medium(self):
        assert classify_signal_severity("SIMULTANEOUS_STRESS", 30.0, 3.0) == "MEDIUM"

    def test_divergence_critical(self):
        assert classify_signal_severity("EQUITY_LEADS_CREDIT", 150.0, 15.0) == "CRITICAL"

    def test_divergence_low(self):
        assert classify_signal_severity("EQUITY_LEADS_CREDIT", 10.0, 1.0) == "LOW"

    def test_divergence_medium(self):
        assert classify_signal_severity("CREDIT_LEADS_EQUITY", 40.0, 2.0) == "MEDIUM"


# ── compute_historical_divergence_outcome ─────────────────────────────────


class TestComputeHistoricalDivergenceOutcome:
    def test_credit_leads(self):
        result = compute_historical_divergence_outcome("CREDIT_LEADS_EQUITY")
        assert result["equity_followed_credit_pct"] == 68.0
        assert result["avg_lag_months"] == 2.5
        assert result["sample_size"] == 450

    def test_equity_leads(self):
        result = compute_historical_divergence_outcome("EQUITY_LEADS_CREDIT")
        assert result["equity_followed_credit_pct"] == 55.0

    def test_simultaneous_stress(self):
        result = compute_historical_divergence_outcome("SIMULTANEOUS_STRESS")
        assert result["equity_followed_credit_pct"] == 82.0

    def test_unknown_type(self):
        result = compute_historical_divergence_outcome("UNKNOWN_SIGNAL")
        assert result["equity_followed_credit_pct"] == 50.0

    def test_financials_sector_adjustment(self):
        result = compute_historical_divergence_outcome("CREDIT_LEADS_EQUITY", "Financials")
        assert result["equity_followed_credit_pct"] == 73.0
        assert result["avg_lag_months"] == 2.0

    def test_energy_sector_adjustment(self):
        result = compute_historical_divergence_outcome("CREDIT_LEADS_EQUITY", "Energy")
        assert result["equity_followed_credit_pct"] == 71.0
