"""Tests for the agency (GSE) bonds connector.

Covers the FHLB Office of Finance extract() path for both CSV and JSON
response shapes (mocked httpx, content-type driven branching + body
sniffing), the pre-existing configurable JSON feed fallback, and the
existing transform()/load() against parsed rows. No network access.
"""

import uuid
from datetime import date
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from src.ingestion.agency_bonds import AgencyBondsConnector

# A small synthetic CSV matching the documented _CSV_COLUMN_MAP column names.
SAMPLE_CSV = (
    "CUSIP,Issuer,Coupon Rate,Coupon Type,Maturity Date,Issue Date,"
    "Issue Amount ($MM),Amount Outstanding ($MM),First Call Date,Callable\n"
    "3130ABCD1,Federal Home Loan Banks,4.375,FIXED,2030-06-15,2025-06-15,"
    "1000,1000,,N\n"
    "3130EFGH2,Federal Home Loan Banks,3.875,FIXED,2032-09-01,2025-09-01,"
    "500,500,2029-09-01,Y\n"
    "3130IJKL3,Federal Home Loan Banks,0,FLOATING,2027-03-01,2025-03-01,"
    "750,750,,N\n"
)

SAMPLE_JSON_ROWS = [
    {
        "CUSIP": "3130MNOP4",
        "Issuer": "Federal Home Loan Banks",
        "Coupon Rate": "5.125",
        "Coupon Type": "FIXED",
        "Maturity Date": "2031-01-15",
        "Issue Date": "2025-01-15",
        "Issue Amount ($MM)": "2000",
        "Amount Outstanding ($MM)": "2000",
        "First Call Date": None,
        "Callable": "N",
    }
]


def test_normalize_row_csv_dict_reader_style():
    conn = AgencyBondsConnector()
    row = {
        "CUSIP": "3130ABCD1",
        "Issuer": "Federal Home Loan Banks",
        "Coupon Rate": "4.375",
        "Coupon Type": "FIXED",
        "Maturity Date": "2030-06-15",
        "Issue Date": "2025-06-15",
        "Issue Amount ($MM)": "1000",
        "Amount Outstanding ($MM)": "1000",
        "First Call Date": "",
        "Callable": "N",
    }
    mapped = conn._normalize_row(row)
    assert mapped["cusip"] == "3130ABCD1"
    assert mapped["issuer_name"] == "Federal Home Loan Banks"
    assert mapped["coupon_rate"] == "4.375"
    assert mapped["maturity_date"] == "2030-06-15"
    assert mapped["agency_type"] == "FHLB"


@pytest.mark.asyncio
async def test_extract_fhlb_csv_mocked_http(monkeypatch):
    class _Resp:
        headers = {"content-type": "text/csv"}
        text = SAMPLE_CSV

        def raise_for_status(self):
            pass

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, headers=None):
            return _Resp()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)

    conn = AgencyBondsConnector(fhlb_url="https://fhlb-of.com/fake/debt.csv")
    raw = await conn.extract()
    assert len(raw) == 3
    assert raw[0]["cusip"] == "3130ABCD1"
    assert raw[0]["agency_type"] == "FHLB"

    valid = await conn.validate(raw)
    transformed = await conn.transform(valid)
    assert len(transformed) == 3
    by_cusip = {r["cusip"]: r for r in transformed}

    fixed = by_cusip["3130ABCD1"]
    assert fixed["agency_type"] == "FHLB"
    assert fixed["backing_type"] == "IMPLICIT_SUPPORT"
    assert fixed["coupon_rate"] == Decimal("4.375")
    assert fixed["maturity_date"] == date(2030, 6, 15)
    assert fixed["is_callable"] is False

    callable_bond = by_cusip["3130EFGH2"]
    assert callable_bond["is_callable"] is True
    assert callable_bond["first_call_date"] == date(2029, 9, 1)

    floater = by_cusip["3130IJKL3"]
    assert floater["coupon_type"] == "FLOATING"


@pytest.mark.asyncio
async def test_extract_fhlb_json_mocked_http(monkeypatch):
    import json as _json

    class _Resp:
        headers = {"content-type": "application/json"}
        text = _json.dumps(SAMPLE_JSON_ROWS)

        def raise_for_status(self):
            pass

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, headers=None):
            return _Resp()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)

    conn = AgencyBondsConnector(fhlb_url="https://fhlb-of.com/fake/debt.json")
    raw = await conn.extract()
    assert len(raw) == 1
    assert raw[0]["cusip"] == "3130MNOP4"

    transformed = await conn.transform(await conn.validate(raw))
    assert len(transformed) == 1
    assert transformed[0]["coupon_rate"] == Decimal("5.125")
    assert transformed[0]["maturity_date"] == date(2031, 1, 15)


@pytest.mark.asyncio
async def test_extract_fhlb_content_type_sniffing_csv_served_as_text_plain(monkeypatch):
    """Some static-file hosts serve CSV under a generic content-type; body sniffing must catch it."""

    class _Resp:
        headers = {"content-type": "text/plain"}
        text = SAMPLE_CSV

        def raise_for_status(self):
            pass

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, headers=None):
            return _Resp()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)

    conn = AgencyBondsConnector(fhlb_url="https://fhlb-of.com/fake/debt")
    raw = await conn.extract()
    assert len(raw) == 3


@pytest.mark.asyncio
async def test_extract_no_fhlb_url_and_no_feed_url_noop():
    conn = AgencyBondsConnector(feed_url="", fhlb_url="")
    raw = await conn.extract()
    assert raw == []


@pytest.mark.asyncio
async def test_extract_legacy_feed_url_wins_over_fhlb(monkeypatch):
    feed_payload = [
        {
            "cusip": "3130ZZZZ9",
            "issuer_name": "Federal Farm Credit Banks",
            "agency_type": "FFCB",
            "coupon_rate": "4.500",
            "maturity_date": "2033-05-01",
        }
    ]

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return feed_payload

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, headers=None):
            return _Resp()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)

    conn = AgencyBondsConnector(
        feed_url="http://example.com/feed", fhlb_url="https://fhlb-of.com/fake/debt.csv"
    )
    raw = await conn.extract()
    assert raw == feed_payload


@pytest.mark.asyncio
async def test_load_inserts_and_upserts_from_fhlb_shaped_rows(session):
    from src.models.agency_bond import AgencyBond

    conn = AgencyBondsConnector()
    raw = [
        {
            "cusip": "3130TEST1",
            "issuer_name": "Federal Home Loan Banks",
            "agency_type": "FHLB",
            "coupon_rate": "4.000",
            "coupon_type": "FIXED",
            "maturity_date": "2029-04-01",
            "issue_date": "2024-04-01",
            "original_amount_mm": "1500",
            "outstanding_amount_mm": "1500",
            "is_callable": "N",
        }
    ]
    transformed = await conn.transform(await conn.validate(raw))
    stats = await conn.load(transformed, session)
    assert stats["inserted"] == 1
    await session.flush()

    rows = (await session.execute(select(AgencyBond).where(AgencyBond.cusip == "3130TEST1"))).scalars().all()
    assert len(rows) == 1
    assert rows[0].agency_type == "FHLB"
    assert rows[0].backing_type == "IMPLICIT_SUPPORT"
    assert rows[0].coupon_rate == Decimal("4.000")

    # Re-loading upserts rather than duplicating.
    stats2 = await conn.load(transformed, session)
    assert stats2["updated"] == 1
    assert stats2["inserted"] == 0
