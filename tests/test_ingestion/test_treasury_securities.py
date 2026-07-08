"""Tests for the Treasury securities connector (Fiscal Data API).

Uses a representative ``auctions_query`` sample payload and mocks HTTP so no
network access is required. The Fiscal Data API is keyless, so the extract path
is also exercised against a mocked ``httpx`` response.
"""

import uuid
from decimal import Decimal

import httpx
import pytest

from src.ingestion.treasury_securities import (
    TreasurySecuritiesConnector,
    _parse_date,
    _parse_decimal,
    _clean,
)

# A representative Fiscal Data auctions_query payload (values are strings; the
# API returns the literal "null" for empties — mirrored here).
SAMPLE_PAYLOAD = {
    "data": [
        {
            "cusip": "912797abc",
            "security_type": "Bill",
            "security_term": "26-Week",
            "int_rate": "null",
            "issue_date": "2025-01-09",
            "maturity_date": "2025-07-10",
            "auction_date": "2025-01-06",
            "high_yield": "4.250000",
            "low_yield": "4.200000",
            "avg_med_yield": "4.230000",
            "price_per100": "97.850000",
            "bid_to_cover_ratio": "2.750000",
            "total_accepted": "70000000000.000000",
            "currently_outstanding": "70000000000.000000",
            "inflation_index_security": "No",
            "floating_rate": "No",
        },
        {
            "cusip": "912810UU0",
            "security_type": "Bond",
            "security_term": "30-Year",
            "int_rate": "4.625000",
            "issue_date": "2025-02-18",
            "maturity_date": "2055-02-15",
            "auction_date": "2025-02-13",
            "high_yield": "4.700000",
            "low_yield": "null",
            "avg_med_yield": "4.680000",
            "price_per100": "null",
            "bid_to_cover_ratio": "2.400000",
            "total_accepted": "25000000000.000000",
            "currently_outstanding": "25000000000.000000",
            "inflation_index_security": "No",
            "floating_rate": "No",
        },
        {
            "cusip": "91282CXX1",
            "security_type": "Note",
            "security_term": "10-Year",
            "int_rate": "2.125000",
            "issue_date": "2025-01-15",
            "maturity_date": "2035-01-15",
            "auction_date": "2025-01-08",
            "high_yield": "2.180000",
            "avg_med_yield": "2.150000",
            "inflation_index_security": "Yes",
            "index_ratio_on_issue_date": "1.05000000",
            "ref_cpi_on_issue_date": "310.2500",
            "floating_rate": "No",
        },
        # Reopening of the 30Y bond (same CUSIP) — must be de-duped.
        {
            "cusip": "912810UU0",
            "security_type": "Bond",
            "maturity_date": "2055-02-15",
            "auction_date": "2025-03-13",
            "inflation_index_security": "No",
            "floating_rate": "No",
        },
        # Invalid — no CUSIP.
        {"cusip": "null", "maturity_date": "2030-01-01"},
    ],
    "meta": {"total-pages": 1},
}


def test_clean_handles_literal_null():
    assert _clean("null") is None
    assert _clean("  ") is None
    assert _clean("912810UU0") == "912810UU0"


def test_parse_decimal_and_date():
    assert _parse_decimal("4.625000") == Decimal("4.625000")
    assert _parse_decimal("null") is None
    assert _parse_date("2025-02-15").isoformat() == "2025-02-15"
    assert _parse_date("null") is None


@pytest.mark.asyncio
async def test_validate_filters_bad_rows():
    conn = TreasurySecuritiesConnector()
    valid = await conn.validate(SAMPLE_PAYLOAD["data"])
    # 5 raw rows → the "null"-cusip row is dropped.
    assert len(valid) == 4


@pytest.mark.asyncio
async def test_transform_maps_types_and_dedupes():
    conn = TreasurySecuritiesConnector()
    valid = await conn.validate(SAMPLE_PAYLOAD["data"])
    out = await conn.transform(valid)

    by_cusip = {r["cusip"]: r for r in out}
    # De-dup: the 30Y bond appears once despite the reopening row.
    assert len(out) == 3

    bill = by_cusip["912797ABC".lower()[:9]] if False else by_cusip["912797abc"]
    assert bill["treasury_type"] == "BILL"
    assert bill["coupon_frequency"] == 0
    assert bill["coupon_rate"] is None
    assert bill["auction_bid_to_cover"] == Decimal("2.750000")

    bond = by_cusip["912810UU0"]
    assert bond["treasury_type"] == "BOND"
    assert bond["coupon_frequency"] == 2
    assert bond["coupon_rate"] == Decimal("4.625000")
    assert bond["maturity_date"].isoformat() == "2055-02-15"

    tips = by_cusip["91282CXX1"]
    assert tips["treasury_type"] == "TIPS"
    assert tips["is_inflation_indexed"] is True
    assert tips["index_ratio"] == Decimal("1.05000000")


@pytest.mark.asyncio
async def test_extract_mocked_http(monkeypatch):
    """Keyless extract path against a mocked httpx response."""

    class _Resp:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return SAMPLE_PAYLOAD

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, params=None):
            return _Resp()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    conn = TreasurySecuritiesConnector(max_pages=1)
    raw = await conn.extract()
    assert len(raw) == 5


@pytest.mark.asyncio
async def test_load_inserts_and_upserts(session):
    conn = TreasurySecuritiesConnector()
    valid = await conn.validate(SAMPLE_PAYLOAD["data"])
    recs = await conn.transform(valid)

    stats = await conn.load(recs, session)
    assert stats["inserted"] == 3
    await session.flush()

    from src.models.treasury import TreasurySecurity
    from sqlalchemy import select

    rows = (await session.execute(select(TreasurySecurity))).scalars().all()
    assert len(rows) == 3

    # Re-loading upserts (updates) rather than duplicating.
    stats2 = await conn.load(recs, session)
    assert stats2["updated"] == 3
    assert stats2["inserted"] == 0
