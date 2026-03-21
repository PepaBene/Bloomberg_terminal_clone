"""Tests for the market movers engine (Pillar 2 Supplement – Part 5)."""

import pytest

from src.engines.market_movers import compute_daily_movers

SAMPLE_DATA = [
    {"security_id": "1", "name": "Stock A", "ticker": "A", "price": 110, "prior_price": 100, "volume": 5000},
    {"security_id": "2", "name": "Stock B", "ticker": "B", "price": 95, "prior_price": 100, "volume": 3000},
    {"security_id": "3", "name": "Stock C", "ticker": "C", "price": 105, "prior_price": 100, "volume": 10000},
    {"security_id": "4", "name": "Stock D", "ticker": "D", "price": 80, "prior_price": 100, "volume": 8000},
    {"security_id": "5", "name": "Stock E", "ticker": "E", "price": 120, "prior_price": 100, "volume": 1000},
]


class TestComputeDailyMovers:
    def test_returns_all_categories(self):
        result = compute_daily_movers(SAMPLE_DATA)
        assert "TOP_GAINERS" in result
        assert "TOP_LOSERS" in result
        assert "MOST_ACTIVE" in result

    def test_top_gainer(self):
        result = compute_daily_movers(SAMPLE_DATA, top_n=1)
        assert len(result["TOP_GAINERS"]) == 1
        assert result["TOP_GAINERS"][0].ticker == "E"  # +20%

    def test_top_loser(self):
        result = compute_daily_movers(SAMPLE_DATA, top_n=1)
        assert len(result["TOP_LOSERS"]) == 1
        assert result["TOP_LOSERS"][0].ticker == "D"  # -20%

    def test_most_active(self):
        result = compute_daily_movers(SAMPLE_DATA, top_n=1)
        assert len(result["MOST_ACTIVE"]) == 1
        assert result["MOST_ACTIVE"][0].ticker == "C"  # volume 10000

    def test_rank_ordering(self):
        result = compute_daily_movers(SAMPLE_DATA, top_n=3)
        gainers = result["TOP_GAINERS"]
        assert gainers[0].change_pct >= gainers[1].change_pct

    def test_empty_input(self):
        result = compute_daily_movers([])
        assert result["TOP_GAINERS"] == []
        assert result["TOP_LOSERS"] == []
        assert result["MOST_ACTIVE"] == []

    def test_skip_invalid_prices(self):
        data = [{"security_id": "1", "name": "Bad", "price": None, "prior_price": 100, "volume": 100}]
        result = compute_daily_movers(data)
        assert all(len(v) == 0 for v in result.values())

    def test_change_pct_calculation(self):
        result = compute_daily_movers(SAMPLE_DATA)
        gainer = next(m for m in result["TOP_GAINERS"] if m.ticker == "E")
        assert gainer.change_pct == pytest.approx(20.0, abs=0.01)
