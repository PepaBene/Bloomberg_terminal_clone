"""Tests for the congressional trades connector (pure transform path)."""

import pytest

from src.ingestion.congress_trades import (
    CongressTradesConnector,
    _parse_amount,
    _parse_date,
)


def test_parse_amount_known_range():
    assert _parse_amount("$1,001 - $15,000") == (1_001, 15_000)
    assert _parse_amount("$1,000,001 - $5,000,000") == (1_000_001, 5_000_000)


def test_parse_amount_unknown():
    assert _parse_amount("free text") == (None, None)
    assert _parse_amount(None) == (None, None)


def test_parse_date_formats():
    assert _parse_date("2025-01-15").isoformat() == "2025-01-15"
    assert _parse_date("01/15/2025").isoformat() == "2025-01-15"
    assert _parse_date("") is None


@pytest.mark.asyncio
async def test_transform_house_feed_row():
    conn = CongressTradesConnector(chamber="HOUSE")
    raw = [
        {
            "representative": "Nancy Pelosi",
            "transaction_date": "2025-01-01",
            "disclosure_date": "2025-03-01",
            "ticker": "nvda",
            "type": "purchase",
            "amount": "$1,000,001 - $5,000,000",
            "owner": "spouse",
            "asset_description": "NVIDIA Corp",
        }
    ]
    out = await conn.transform(raw)
    assert len(out) == 1
    row = out[0]
    assert row["politician_name"] == "Nancy Pelosi"
    assert row["ticker"] == "NVDA"
    assert row["transaction_type"] == "BUY"
    assert row["amount_range_low"] == 1_000_001
    assert row["chamber"] == "HOUSE"
    assert row["disclosure_lag_days"] == 59
    assert row["is_late_disclosure"] is True  # 59 > 45


@pytest.mark.asyncio
async def test_transform_skips_invalid_rows():
    conn = CongressTradesConnector(chamber="HOUSE")
    raw = [{"ticker": "AAPL"}, {"representative": "X"}]  # no date / no name+date
    out = await conn.transform(raw)
    assert out == []


@pytest.mark.asyncio
async def test_transform_normalizes_dashes_to_none_ticker():
    conn = CongressTradesConnector(chamber="SENATE")
    raw = [{"senator": "Jane Doe", "transaction_date": "2025-02-02", "ticker": "--", "type": "sale"}]
    out = await conn.transform(raw)
    assert out[0]["ticker"] is None
    assert out[0]["transaction_type"] == "SELL"
    assert out[0]["chamber"] == "SENATE"
