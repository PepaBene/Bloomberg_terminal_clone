"""Tests for the EIA commodity inventory connector (R-023 real supply/demand data).

Covers parse_eia_response() against a synthetic EIA v2 /seriesid/ payload,
extract() dispatch across the 3 mapped series (mocked httpx, no network),
the no-API-key no-op path, and load() insert/upsert against the
CommodityInventory model.
"""

import uuid
from datetime import date
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from src.ingestion.eia_commodity_inventory import (
    EIA_SERIES,
    EIACommodityInventoryConnector,
    parse_eia_response,
)

# Synthetic payload matching EIA API v2's documented envelope shape.
SAMPLE_EIA_PAYLOAD = {
    "response": {
        "total": "3",
        "dateFormat": "YYYY-MM-DD",
        "data": [
            {"period": "2024-05-10", "value": 459200, "units": "MBBL"},
            {"period": "2024-05-03", "value": 462800, "units": "MBBL"},
            {"period": "2023-05-05", "value": 470100, "units": "MBBL"},
        ],
    },
    "request": {},
}


def test_parse_eia_response_maps_rows():
    spec = EIA_SERIES[0]  # WTI / PET.WCESTUS1.W
    rows = parse_eia_response(spec, SAMPLE_EIA_PAYLOAD)
    assert len(rows) == 3
    latest = rows[0]
    assert latest["commodity_code"] == "WTI"
    assert latest["as_of_date"] == date(2024, 5, 10)
    assert latest["stock_level"] == Decimal("459200")
    assert latest["stock_unit"] == "MBBL"
    assert latest["metric_name"] == spec.metric_name
    assert latest["source"] == "EIA"


def test_parse_eia_response_drops_rows_missing_period_or_value():
    spec = EIA_SERIES[0]
    payload = {
        "response": {
            "data": [
                {"period": "2024-05-10", "value": 459200, "units": "MBBL"},
                {"period": None, "value": 100, "units": "MBBL"},
                {"period": "2024-04-01", "value": None, "units": "MBBL"},
            ]
        }
    }
    rows = parse_eia_response(spec, payload)
    assert len(rows) == 1
    assert rows[0]["as_of_date"] == date(2024, 5, 10)


def test_parse_eia_response_empty_payload():
    spec = EIA_SERIES[0]
    assert parse_eia_response(spec, {}) == []
    assert parse_eia_response(spec, {"response": {}}) == []


@pytest.mark.asyncio
async def test_extract_no_api_key_noop():
    conn = EIACommodityInventoryConnector(api_key="")
    raw = await conn.extract()
    assert raw == []


@pytest.mark.asyncio
async def test_extract_fetches_all_three_series_mocked_http(monkeypatch):
    calls = []

    class _Resp:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            pass

        def json(self):
            return self._payload

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, params=None):
            calls.append(url)
            return _Resp(SAMPLE_EIA_PAYLOAD)

    monkeypatch.setattr(httpx, "AsyncClient", _Client)

    conn = EIACommodityInventoryConnector(api_key="fake-key")
    raw = await conn.extract()

    # 3 series x 3 rows each in the fixture payload.
    assert len(raw) == 9
    assert len(calls) == 3
    for spec in EIA_SERIES:
        assert any(spec.series_id in url for url in calls)

    codes = {r["commodity_code"] for r in raw}
    assert codes == {"WTI", "GASOLINE", "NATGAS"}


@pytest.mark.asyncio
async def test_extract_handles_per_series_fetch_failure_gracefully(monkeypatch):
    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, params=None):
            raise httpx.ConnectError("blocked")

    monkeypatch.setattr(httpx, "AsyncClient", _Client)

    conn = EIACommodityInventoryConnector(api_key="fake-key")
    raw = await conn.extract()
    assert raw == []


@pytest.mark.asyncio
async def test_validate_drops_incomplete_rows():
    conn = EIACommodityInventoryConnector(api_key="fake-key")
    raw = [
        {"commodity_code": "WTI", "as_of_date": date(2024, 5, 10), "stock_level": Decimal("100")},
        {"commodity_code": "WTI", "as_of_date": None, "stock_level": Decimal("100")},
        {"commodity_code": "", "as_of_date": date(2024, 5, 10), "stock_level": Decimal("100")},
    ]
    valid = await conn.validate(raw)
    assert len(valid) == 1


@pytest.mark.asyncio
async def test_load_inserts_and_upserts(session):
    from src.models.commodity_intelligence import CommodityInventory

    conn = EIACommodityInventoryConnector(api_key="fake-key")
    records = [
        {
            "commodity_code": "WTI",
            "as_of_date": date(2024, 5, 10),
            "stock_level": Decimal("459200"),
            "stock_unit": "MBBL",
            "metric_name": "US Commercial Crude Oil Stocks (excl. SPR)",
            "source": "EIA",
        }
    ]
    stats = await conn.load(records, session)
    assert stats["inserted"] == 1
    await session.flush()

    rows = (
        await session.execute(
            select(CommodityInventory).where(CommodityInventory.commodity_code == "WTI")
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].stock_level == Decimal("459200")

    # Re-loading the same (commodity_code, as_of_date) upserts, not duplicates.
    updated_records = [{**records[0], "stock_level": Decimal("460000")}]
    stats2 = await conn.load(updated_records, session)
    assert stats2["updated"] == 1
    assert stats2["inserted"] == 0

    rows2 = (
        await session.execute(
            select(CommodityInventory).where(CommodityInventory.commodity_code == "WTI")
        )
    ).scalars().all()
    assert len(rows2) == 1
    assert rows2[0].stock_level == Decimal("460000")
