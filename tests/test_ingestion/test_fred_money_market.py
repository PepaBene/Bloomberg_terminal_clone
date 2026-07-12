"""Tests for the FRED money market rates connector.

``extract()`` was previously a stub that always returned ``[]``; this
exercises the now-real validate/transform/load pipeline against
representative FRED ``series/observations`` payloads. No network.
"""

from datetime import date

import pytest
from sqlalchemy import select

from src.ingestion.fred_money_market import FredMoneyMarketConnector


@pytest.mark.asyncio
async def test_validate_drops_missing_value_sentinel():
    conn = FredMoneyMarketConnector()
    records = [
        {"rate_date": "2026-03-19", "rate_type": "SOFR", "rate_value": "5.31"},
        {"rate_date": "2026-03-20", "rate_type": "SOFR", "rate_value": "."},  # FRED missing-value sentinel
        {"rate_date": None, "rate_type": "SOFR", "rate_value": "5.31"},
    ]
    valid = await conn.validate(records)
    assert len(valid) == 1
    assert valid[0]["rate_date"] == "2026-03-19"


@pytest.mark.asyncio
async def test_transform_converts_percent_to_decimal():
    conn = FredMoneyMarketConnector()
    out = await conn.transform([
        {"rate_date": "2026-03-19", "rate_type": "SOFR", "rate_value": "5.31"},
    ])
    assert len(out) == 1
    assert out[0]["rate_date"] == date(2026, 3, 19)
    assert out[0]["rate_type"] == "SOFR"
    assert abs(out[0]["rate_value"] - 0.0531) < 1e-9
    assert out[0]["source"] == "FRED"


@pytest.mark.asyncio
async def test_load_inserts_and_updates(session):
    from src.models.fed_meeting import MoneyMarketRate

    conn = FredMoneyMarketConnector()
    records = [{"rate_date": date(2026, 3, 19), "rate_type": "SOFR", "rate_value": 0.0531, "source": "FRED"}]
    stats = await conn.load(records, session)
    assert stats["inserted"] == 1
    await session.flush()

    rows = (await session.execute(select(MoneyMarketRate))).scalars().all()
    assert len(rows) == 1
    assert float(rows[0].rate_value) == pytest.approx(0.0531)

    # Re-loading the same (rate_date, rate_type) updates rather than duplicates.
    updated = [{"rate_date": date(2026, 3, 19), "rate_type": "SOFR", "rate_value": 0.0540, "source": "FRED"}]
    stats2 = await conn.load(updated, session)
    assert stats2["updated"] == 1
    assert stats2["inserted"] == 0
    await session.flush()

    rows = (await session.execute(select(MoneyMarketRate))).scalars().all()
    assert len(rows) == 1
    assert float(rows[0].rate_value) == pytest.approx(0.0540)


@pytest.mark.asyncio
async def test_extract_without_api_key_returns_empty():
    conn = FredMoneyMarketConnector(api_key="")
    records = await conn.extract()
    assert records == []
