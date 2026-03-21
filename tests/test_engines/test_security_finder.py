"""Tests for the security finder engine (Pillar 2 Supplement – Part 5)."""

import pytest

from src.engines.security_finder import search_securities, suggest_securities

SAMPLE_SECURITIES = [
    {"security_id": "1", "name": "Apple Inc. Common Stock", "short_name": "AAPL", "security_type": "COMMON_STOCK", "asset_class": "EQUITY", "status": "ACTIVE"},
    {"security_id": "2", "name": "Microsoft Corporation", "short_name": "MSFT", "security_type": "COMMON_STOCK", "asset_class": "EQUITY", "status": "ACTIVE"},
    {"security_id": "3", "name": "Alphabet Inc Class A", "short_name": "GOOGL", "security_type": "COMMON_STOCK", "asset_class": "EQUITY", "status": "ACTIVE"},
    {"security_id": "4", "name": "Apple Credit Corp Bond", "short_name": None, "security_type": "BOND", "asset_class": "FIXED_INCOME", "status": "ACTIVE"},
    {"security_id": "5", "name": "Inactive Corp", "short_name": "INAC", "security_type": "COMMON_STOCK", "asset_class": "EQUITY", "status": "INACTIVE"},
]


class TestSearchSecurities:
    def test_exact_ticker_match(self):
        results = search_securities("AAPL", SAMPLE_SECURITIES)
        assert len(results) >= 1
        assert results[0].short_name == "AAPL"

    def test_name_search(self):
        results = search_securities("apple", SAMPLE_SECURITIES)
        assert len(results) >= 1
        assert any("Apple" in r.name for r in results)

    def test_partial_match(self):
        results = search_securities("micro", SAMPLE_SECURITIES)
        assert len(results) >= 1
        assert results[0].name == "Microsoft Corporation"

    def test_filter_by_type(self):
        results = search_securities("apple", SAMPLE_SECURITIES, security_type="BOND")
        assert len(results) == 1
        assert results[0].security_type == "BOND"

    def test_filter_by_asset_class(self):
        results = search_securities("apple", SAMPLE_SECURITIES, asset_class="EQUITY")
        assert len(results) == 1
        assert results[0].asset_class == "EQUITY"

    def test_no_match(self):
        results = search_securities("xyz_nonexistent", SAMPLE_SECURITIES)
        assert len(results) == 0

    def test_empty_query(self):
        results = search_securities("", SAMPLE_SECURITIES)
        assert len(results) == 0

    def test_max_results(self):
        results = search_securities("a", SAMPLE_SECURITIES, max_results=2)
        assert len(results) <= 2

    def test_relevance_ordering(self):
        results = search_securities("apple", SAMPLE_SECURITIES)
        if len(results) >= 2:
            assert results[0].relevance_score >= results[1].relevance_score


class TestSuggestSecurities:
    def test_basic_suggest(self):
        results = suggest_securities("aa", SAMPLE_SECURITIES)
        assert len(results) >= 1
        assert any("AAPL" in r["display"] for r in results)

    def test_empty_query(self):
        results = suggest_securities("", SAMPLE_SECURITIES)
        assert results == []

    def test_max_suggestions(self):
        results = suggest_securities("a", SAMPLE_SECURITIES, max_suggestions=1)
        assert len(results) <= 1
