"""Tests for the market movers engine (Pillar 2 Supplement – Part 5)."""

import logging

import pytest

from src.engines.market_movers import (
    MostActiveStatus,
    MoversComputationMeta,
    compute_daily_movers,
)

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
        for category in ("TOP_GAINERS", "TOP_LOSERS", "MOST_ACTIVE"):
            assert len(result[category]) == 0

    def test_change_pct_calculation(self):
        result = compute_daily_movers(SAMPLE_DATA)
        gainer = next(m for m in result["TOP_GAINERS"] if m.ticker == "E")
        assert gainer.change_pct == pytest.approx(20.0, abs=0.01)


# ── Data-quality logging & status tests (P1-E-018 / P1-E-019) ────────────


class TestExclusionLogging:
    """Tests for P1-E-018: dropped rows must be logged, not silently eaten."""

    def test_meta_counts_missing_price_or_prior(self):
        data = [
            {"security_id": "1", "name": "Bad", "price": None, "prior_price": 100, "volume": 100},
            {"security_id": "2", "name": "Bad2", "price": 50, "prior_price": None, "volume": 100},
        ]
        result = compute_daily_movers(data)
        meta = result["meta"]
        assert isinstance(meta, MoversComputationMeta)
        assert meta.total_input == 2
        assert meta.excluded_missing_price_or_prior == 2
        assert meta.valid_count == 0

    def test_meta_counts_low_prior_price_and_low_volume(self):
        data = [
            # Below MIN_PRIOR_PRICE ($1)
            {"security_id": "1", "name": "Penny", "price": 0.6, "prior_price": 0.5, "volume": 5000},
            # Below MIN_VOLUME (1000)
            {"security_id": "2", "name": "Illiquid", "price": 51, "prior_price": 50, "volume": 10},
        ]
        result = compute_daily_movers(data)
        meta = result["meta"]
        assert meta.excluded_low_prior_price == 1
        assert meta.excluded_low_volume == 1
        assert meta.valid_count == 0

    def test_meta_counts_extreme_change(self):
        data = [
            {"security_id": "1", "name": "Bad Split", "price": 10, "prior_price": 100, "volume": 5000},
        ]
        result = compute_daily_movers(data)
        meta = result["meta"]
        assert meta.excluded_extreme_change == 1

    def test_warning_logged_when_rows_excluded(self, caplog):
        data = [{"security_id": "1", "name": "Bad", "price": None, "prior_price": 100, "volume": 100}]
        with caplog.at_level(logging.WARNING, logger="src.engines.market_movers"):
            compute_daily_movers(data)
        assert any("excluded" in rec.message for rec in caplog.records)

    def test_no_warning_when_nothing_excluded(self, caplog):
        with caplog.at_level(logging.WARNING, logger="src.engines.market_movers"):
            compute_daily_movers(SAMPLE_DATA)
        assert not any(rec.levelno == logging.WARNING for rec in caplog.records)


class TestMostActiveStatus:
    """Tests for P1-E-019: distinguish 'quiet day' from 'no data' for MOST_ACTIVE."""

    def test_ok_status_when_volume_present(self):
        result = compute_daily_movers(SAMPLE_DATA)
        assert result["meta"].most_active_status == MostActiveStatus.OK

    def test_no_data_status_when_nothing_valid(self):
        data = [{"security_id": "1", "name": "Bad", "price": None, "prior_price": 100, "volume": 100}]
        result = compute_daily_movers(data)
        assert result["MOST_ACTIVE"] == []
        assert result["meta"].most_active_status == MostActiveStatus.NO_DATA

    def test_quiet_day_status_when_all_volume_none(self):
        data = [
            {"security_id": "1", "name": "A", "ticker": "A", "price": 110, "prior_price": 100, "volume": None},
            {"security_id": "2", "name": "B", "ticker": "B", "price": 95, "prior_price": 100, "volume": None},
        ]
        result = compute_daily_movers(data)
        assert result["MOST_ACTIVE"] == []
        # Valid price data existed (gainers/losers are non-empty) but no
        # volume was reported for anyone -- a quiet day, not "no data".
        assert result["TOP_GAINERS"] != []
        assert result["meta"].most_active_status == MostActiveStatus.QUIET_DAY

    def test_quiet_day_and_no_data_are_distinguishable(self):
        no_data_result = compute_daily_movers(
            [{"security_id": "1", "name": "Bad", "price": None, "prior_price": 100, "volume": 100}]
        )
        quiet_day_result = compute_daily_movers(
            [{"security_id": "1", "name": "A", "ticker": "A", "price": 110, "prior_price": 100, "volume": None}]
        )
        assert (
            no_data_result["meta"].most_active_status
            != quiet_day_result["meta"].most_active_status
        )
