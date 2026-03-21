"""Tests for the company intelligence engine (Pillar 2 Supplement – Part 7)."""

import pytest

from src.engines.company_intelligence import (
    KeySignal,
    ValuationContext,
    BriefingData,
    extract_key_signals,
    compute_valuation_context,
    generate_briefing,
)


class TestExtractKeySignals:
    def test_no_data(self):
        signals = extract_key_signals({})
        assert signals == []

    def test_strong_price_up(self):
        signals = extract_key_signals({"price_change_pct": 15.0})
        assert len(signals) == 1
        assert signals[0].severity == "HIGH"
        assert "momentum" in signals[0].signal.lower()

    def test_strong_price_down(self):
        signals = extract_key_signals({"price_change_pct": -12.0})
        assert len(signals) == 1
        assert "decline" in signals[0].signal.lower()

    def test_moderate_price_change_no_signal(self):
        signals = extract_key_signals({"price_change_pct": 5.0})
        assert signals == []

    def test_unusual_volume(self):
        signals = extract_key_signals({"volume_ratio": 4.0})
        assert len(signals) == 1
        assert "volume" in signals[0].signal.lower()

    def test_normal_volume_no_signal(self):
        signals = extract_key_signals({"volume_ratio": 1.5})
        assert signals == []

    def test_earnings_beat(self):
        signals = extract_key_signals({"earnings_surprise_pct": 15.0})
        assert len(signals) == 1
        assert "beat" in signals[0].signal.lower()

    def test_earnings_miss(self):
        signals = extract_key_signals({"earnings_surprise_pct": -12.0})
        assert len(signals) == 1
        assert "miss" in signals[0].signal.lower()

    def test_insider_buying(self):
        signals = extract_key_signals({"insider_net_shares": 50000})
        assert len(signals) == 1
        assert "insider buying" in signals[0].signal.lower()

    def test_insider_selling(self):
        signals = extract_key_signals({"insider_net_shares": -200000})
        assert len(signals) == 1
        assert "insider selling" in signals[0].signal.lower()

    def test_high_leverage(self):
        signals = extract_key_signals({"debt_to_equity": 4.0})
        assert len(signals) == 1
        assert "leverage" in signals[0].signal.lower()

    def test_low_interest_coverage(self):
        signals = extract_key_signals({"interest_coverage": 1.0})
        assert len(signals) == 1
        assert "coverage" in signals[0].signal.lower()

    def test_guidance_up(self):
        signals = extract_key_signals({"guidance_revision": "UP"})
        assert len(signals) == 1
        assert "raised" in signals[0].signal.lower()

    def test_guidance_down(self):
        signals = extract_key_signals({"guidance_revision": "DOWN"})
        assert len(signals) == 1
        assert "lowered" in signals[0].signal.lower()

    def test_positive_analyst_revisions(self):
        signals = extract_key_signals({"analyst_revision_pct": 8.0})
        assert len(signals) == 1
        assert "positive" in signals[0].signal.lower()

    def test_negative_analyst_revisions(self):
        signals = extract_key_signals({"analyst_revision_pct": -7.0})
        assert len(signals) == 1
        assert "negative" in signals[0].signal.lower()

    def test_multiple_signals(self):
        data = {
            "price_change_pct": 15.0,
            "volume_ratio": 5.0,
            "earnings_surprise_pct": 20.0,
        }
        signals = extract_key_signals(data)
        assert len(signals) == 3


class TestComputeValuationContext:
    def test_full_data(self):
        data = {
            "price": 150.0,
            "eps": 6.0,
            "pe_5y_avg": 22.0,
            "peer_pe_avg": 20.0,
            "ev": 2500.0,
            "ebitda": 250.0,
            "book_value_per_share": 50.0,
            "dividend_per_share": 3.0,
        }
        vc = compute_valuation_context(data)
        assert vc.pe_current == pytest.approx(25.0)
        assert vc.pe_5y_avg == 22.0
        assert vc.pe_vs_peers == pytest.approx(1.25)
        assert vc.ev_ebitda == pytest.approx(10.0)
        assert vc.pb_ratio == pytest.approx(3.0)
        assert vc.dividend_yield == pytest.approx(2.0)

    def test_empty_data(self):
        vc = compute_valuation_context({})
        assert vc.pe_current is None
        assert vc.ev_ebitda is None
        assert vc.pb_ratio is None

    def test_zero_eps(self):
        vc = compute_valuation_context({"price": 100.0, "eps": 0.0})
        assert vc.pe_current is None

    def test_negative_eps(self):
        vc = compute_valuation_context({"price": 100.0, "eps": -5.0})
        assert vc.pe_current is None


class TestGenerateBriefing:
    def test_without_ai(self):
        briefing = generate_briefing(
            entity_id="test-id",
            entity_name="Test Corp",
            signal_data={"price_change_pct": 15.0},
            valuation_data={"price": 100.0, "eps": 5.0},
        )
        assert isinstance(briefing, BriefingData)
        assert briefing.ai_enabled is False
        assert briefing.summary_text is None
        assert len(briefing.key_signals) >= 1
        assert briefing.valuation_context is not None
        assert briefing.valuation_context.pe_current == pytest.approx(20.0)

    def test_with_ai_summary(self):
        briefing = generate_briefing(
            entity_id="test-id",
            entity_name="Test Corp",
            signal_data={},
            valuation_data={},
            ai_summary="AI-generated summary text.",
        )
        assert briefing.ai_enabled is True
        assert briefing.summary_text == "AI-generated summary text."

    def test_entity_id_preserved(self):
        briefing = generate_briefing(
            entity_id="abc-123",
            entity_name="ABC Corp",
            signal_data={},
            valuation_data={},
        )
        assert briefing.entity_id == "abc-123"
        assert briefing.entity_name == "ABC Corp"
