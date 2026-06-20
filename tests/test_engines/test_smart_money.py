"""Tests for the Smart-Money / Notable-Filer Intelligence Engine."""

from src.engines.smart_money import (
    CATEGORY_SIGNAL_WEIGHTS,
    aggregate_smart_money_flow,
    build_filer_profile,
    classify_political_trade,
    compute_follow_signal,
    compute_position_conviction,
    detect_consensus,
    find_investor,
    load_notable_investors,
)


# ── Registry ─────────────────────────────────────────────────────────────

class TestRegistry:
    def test_registry_loads_known_people(self):
        reg = load_notable_investors()
        names = {e["display_name"] for e in reg}
        assert "Michael Burry" in names
        assert "Jamie Dimon" in names
        assert "Nancy Pelosi" in names

    def test_find_investor_by_key_and_name(self):
        reg = load_notable_investors()
        assert find_investor(reg, "michael_burry")["display_name"] == "Michael Burry"
        assert find_investor(reg, "Nancy Pelosi")["category"] == "POLITICIAN"
        assert find_investor(reg, "burry") is not None  # fuzzy contains

    def test_find_investor_missing(self):
        assert find_investor(load_notable_investors(), "nobody xyz") is None
        assert find_investor([], "") is None


# ── Conviction scoring ───────────────────────────────────────────────────

class TestConviction:
    def test_new_concentrated_position_scores_high(self):
        score = compute_position_conviction(
            {"percent_of_portfolio": 20, "market_value": 1_000_000_000, "is_new_position": True}
        )
        assert score >= 95

    def test_small_position_scores_low(self):
        score = compute_position_conviction(
            {"percent_of_portfolio": 0.5, "market_value": 1_000_000}
        )
        assert score < 10

    def test_accumulation_adds_momentum(self):
        flat = compute_position_conviction({"percent_of_portfolio": 5, "market_value": 0})
        grown = compute_position_conviction(
            {"percent_of_portfolio": 5, "market_value": 0, "shares_change_pct": 1.0}
        )
        assert grown > flat


# ── 13F profile diffing ──────────────────────────────────────────────────

class TestFilerProfile:
    def test_detects_new_and_exited_positions(self):
        prior = [
            {"ticker": "AAPL", "shares": 100, "percent_of_portfolio": 40, "market_value": 100},
            {"ticker": "GOOG", "shares": 50, "percent_of_portfolio": 20, "market_value": 50},
        ]
        current = [
            {"ticker": "AAPL", "shares": 200, "percent_of_portfolio": 50, "market_value": 200},
            {"ticker": "NVDA", "shares": 10, "percent_of_portfolio": 30, "market_value": 150},
        ]
        prof = build_filer_profile("Test Fund", "GURU_13F", current, prior)
        new_tickers = {p["ticker"] for p in prof["new_positions"]}
        exited_tickers = {p["ticker"] for p in prof["exited_positions"]}
        inc_tickers = {p["ticker"] for p in prof["increased_positions"]}
        assert new_tickers == {"NVDA"}
        assert exited_tickers == {"GOOG"}
        assert inc_tickers == {"AAPL"}
        assert prof["num_holdings"] == 2

    def test_concentration_and_turnover(self):
        current = [
            {"ticker": "A", "shares": 1, "percent_of_portfolio": 60, "market_value": 60},
            {"ticker": "B", "shares": 1, "percent_of_portfolio": 40, "market_value": 40},
        ]
        prof = build_filer_profile("F", "GURU_13F", current, [])
        assert prof["top5_concentration_pct"] == 100.0
        assert prof["total_value"] == 100.0
        assert prof["turnover"] == 1.0  # all names are new vs empty prior


# ── Political trade classification ───────────────────────────────────────

class TestPoliticalTrade:
    def test_size_bucket_and_midpoint(self):
        out = classify_political_trade(
            {"amount_range_low": 1_000_001, "amount_range_high": 5_000_000,
             "transaction_type": "BUY"}
        )
        assert out["midpoint_amount"] == 3_000_000.5
        assert out["size_bucket"] == "JUMBO"

    def test_late_disclosure_flag(self):
        out = classify_political_trade(
            {"transaction_date": "2025-01-01", "disclosure_date": "2025-04-01",
             "amount_range_low": 1000, "amount_range_high": 15000}
        )
        assert out["disclosure_lag_days"] == 90
        assert out["is_late_disclosure"] is True

    def test_committee_conflict_detection(self):
        out = classify_political_trade(
            {"amount_range_low": 1000, "amount_range_high": 15000, "sector": "FINANCIALS"},
            committees=["Financial Services"],
        )
        assert out["committee_conflict"] is True
        assert out["conflict_committee"] == "Financial Services"

    def test_no_conflict_when_sector_unrelated(self):
        out = classify_political_trade(
            {"amount_range_low": 1000, "amount_range_high": 15000, "sector": "ENERGY"},
            committees=["Financial Services"],
        )
        assert out["committee_conflict"] is False


# ── Follow signals ───────────────────────────────────────────────────────

class TestFollowSignal:
    def test_insider_open_market_buy_is_strong_bullish(self):
        sig = compute_follow_signal(
            {"category": "INSIDER_FORM4", "action": "BUY", "conviction": 80, "is_open_market": True}
        )
        assert sig["direction"] == "BULLISH"
        assert sig["strength"] > 80

    def test_non_open_market_insider_is_discounted(self):
        full = compute_follow_signal(
            {"category": "INSIDER_FORM4", "action": "BUY", "conviction": 80, "is_open_market": True}
        )
        grant = compute_follow_signal(
            {"category": "INSIDER_FORM4", "action": "BUY", "conviction": 80, "is_open_market": False}
        )
        assert grant["strength"] < full["strength"]

    def test_exit_is_bearish(self):
        sig = compute_follow_signal({"category": "GURU_13F", "action": "EXIT", "conviction": 60})
        assert sig["direction"] == "BEARISH"

    def test_category_weights_ordering(self):
        assert CATEGORY_SIGNAL_WEIGHTS["INSIDER_FORM4"] > CATEGORY_SIGNAL_WEIGHTS["GURU_13F"]
        assert CATEGORY_SIGNAL_WEIGHTS["GURU_13F"] > CATEGORY_SIGNAL_WEIGHTS["POLITICIAN"]

    def test_politician_committee_conflict_boosts_strength(self):
        plain = compute_follow_signal(
            {"category": "POLITICIAN", "action": "BUY", "conviction": 50}
        )
        conflicted = compute_follow_signal(
            {"category": "POLITICIAN", "action": "BUY", "conviction": 50, "committee_conflict": True}
        )
        assert conflicted["strength"] > plain["strength"]


# ── Consensus & flow ─────────────────────────────────────────────────────

class TestConsensusAndFlow:
    def _profile(self, name, new=(), exited=()):
        return {
            "display_name": name,
            "new_positions": [{"ticker": t} for t in new],
            "increased_positions": [],
            "exited_positions": [{"ticker": t} for t in exited],
            "decreased_positions": [],
        }

    def test_detect_consensus_requires_min_participants(self):
        profiles = [
            self._profile("A", new=["NVDA"]),
            self._profile("B", new=["NVDA"]),
            self._profile("C", new=["TSLA"]),
        ]
        rows = detect_consensus(profiles, min_participants=2)
        tickers = {r["ticker"] for r in rows}
        assert "NVDA" in tickers
        assert "TSLA" not in tickers  # only 1 participant
        nvda = next(r for r in rows if r["ticker"] == "NVDA")
        assert nvda["signal"] == "BULLISH"
        assert nvda["net_score"] == 2

    def test_aggregate_flow_net_pressure(self):
        events = [
            {"ticker": "AAPL", "display_name": "X", "direction": "BULLISH", "strength": 70},
            {"ticker": "AAPL", "display_name": "Y", "direction": "BEARISH", "strength": 20},
        ]
        flow = aggregate_smart_money_flow(events)
        row = next(r for r in flow if r["ticker"] == "AAPL")
        assert row["net_pressure"] == 50.0
        assert row["signal"] == "BULLISH"
        assert row["events"] == 2
