"""Tests for the portfolio parser engine (Pillar 2 Supplement – Part 4)."""

import pytest

from src.engines.portfolio_parser import (
    MatchResult,
    ParsedHolding,
    match_holdings_to_securities,
    parse_csv,
)


class TestParseCSV:
    def test_basic_csv(self):
        csv_content = "Ticker,Name,Quantity,Weight\nAAPL,Apple Inc,100,0.10\nMSFT,Microsoft,200,0.15\n"
        result = parse_csv(csv_content)
        assert len(result) == 2
        assert result[0].identifier == "AAPL"
        assert result[0].name == "Apple Inc"
        assert result[0].quantity == 100.0
        assert result[0].weight == 0.10

    def test_alternative_column_names(self):
        csv_content = "Symbol,Security_Name,Shares,Allocation\nGOOG,Alphabet,50,0.05\n"
        result = parse_csv(csv_content)
        assert len(result) == 1
        assert result[0].identifier == "GOOG"
        assert result[0].name == "Alphabet"
        assert result[0].quantity == 50.0
        assert result[0].weight == 0.05

    def test_empty_csv(self):
        result = parse_csv("")
        assert result == []

    def test_header_only(self):
        result = parse_csv("Ticker,Name,Quantity\n")
        assert result == []

    def test_percentage_sign_in_weight(self):
        csv_content = "Ticker,Weight\nAAPL,10%\nMSFT,15%\n"
        result = parse_csv(csv_content)
        assert len(result) == 2
        assert result[0].weight == 10.0
        assert result[1].weight == 15.0

    def test_commas_in_quantity(self):
        csv_content = "Ticker,Quantity\nAAPL,\"1,000\"\n"
        result = parse_csv(csv_content)
        assert len(result) == 1
        assert result[0].quantity == 1000.0

    def test_skip_empty_rows(self):
        csv_content = "Ticker,Name\nAAPL,Apple\n,,\nMSFT,Microsoft\n"
        result = parse_csv(csv_content)
        assert len(result) == 2


class TestMatchHoldings:
    def test_ticker_match(self):
        holdings = [ParsedHolding(row_number=1, identifier="AAPL", name="Apple")]
        tickers = {"AAPL": "sec-001"}
        result = match_holdings_to_securities(holdings, known_tickers=tickers)
        assert len(result) == 1
        assert result[0].status == "MATCHED"
        assert result[0].matched_security_id == "sec-001"
        assert result[0].confidence == 1.0

    def test_name_match(self):
        holdings = [ParsedHolding(row_number=1, name="apple inc")]
        names = {"apple inc": "sec-001"}
        result = match_holdings_to_securities(holdings, known_names=names)
        assert len(result) == 1
        assert result[0].status == "MATCHED"
        assert result[0].confidence == 0.8

    def test_no_match(self):
        holdings = [ParsedHolding(row_number=1, identifier="XYZ")]
        result = match_holdings_to_securities(holdings)
        assert len(result) == 1
        assert result[0].status == "NOT_FOUND"
        assert result[0].matched_security_id is None

    def test_case_insensitive_ticker(self):
        holdings = [ParsedHolding(row_number=1, identifier="aapl")]
        tickers = {"AAPL": "sec-001"}
        result = match_holdings_to_securities(holdings, known_tickers=tickers)
        assert result[0].status == "MATCHED"

    def test_multiple_holdings(self):
        holdings = [
            ParsedHolding(row_number=1, identifier="AAPL"),
            ParsedHolding(row_number=2, identifier="MSFT"),
            ParsedHolding(row_number=3, identifier="UNKNOWN"),
        ]
        tickers = {"AAPL": "s1", "MSFT": "s2"}
        result = match_holdings_to_securities(holdings, known_tickers=tickers)
        assert result[0].status == "MATCHED"
        assert result[1].status == "MATCHED"
        assert result[2].status == "NOT_FOUND"
