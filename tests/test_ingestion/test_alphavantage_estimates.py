"""Tests for the Alpha Vantage consensus estimates connector.

Exercises the pure EARNINGS-response flattening, validate/transform
filtering, security_id resolution via SecurityIdentifier, and the DB load of
ConsensusEstimate rows against a seeded security. No live network calls —
extract() is exercised against a mocked httpx response matching Alpha
Vantage's documented EARNINGS response shape.
"""

import uuid
from datetime import date

import httpx
import pytest
from sqlalchemy import select

from src.config import settings
from src.ingestion.alphavantage_estimates import AlphaVantageEstimatesConnector

SAMPLE_EARNINGS_RESPONSE = {
    "symbol": "IBM",
    "annualEarnings": [
        {"fiscalDateEnding": "2023-12-31", "reportedEPS": "9.62"},
    ],
    "quarterlyEarnings": [
        {
            "fiscalDateEnding": "2024-03-31",
            "reportedDate": "2024-04-24",
            "reportedEPS": "1.68",
            "estimatedEPS": "1.61",
            "surprise": "0.07",
            "surprisePercentage": "4.3478",
        },
        {
            "fiscalDateEnding": "2024-06-30",
            "reportedDate": "2024-07-24",
            "reportedEPS": "2.43",
            "estimatedEPS": "2.35",
            "surprise": "0.08",
            "surprisePercentage": "3.4043",
        },
        {
            # Alpha Vantage's literal missing-value sentinel — should be dropped.
            "fiscalDateEnding": "2024-09-30",
            "reportedDate": None,
            "reportedEPS": "None",
            "estimatedEPS": "None",
            "surprise": "None",
            "surprisePercentage": "None",
        },
    ],
}


def test_extract_quarterly_rows_pure():
    conn = AlphaVantageEstimatesConnector()
    rows = conn._extract_quarterly_rows(SAMPLE_EARNINGS_RESPONSE, "IBM")
    assert len(rows) == 3
    assert rows[0]["symbol"] == "IBM"
    assert rows[0]["fiscalDateEnding"] == "2024-03-31"
    assert rows[0]["estimatedEPS"] == "1.61"
    assert rows[2]["estimatedEPS"] == "None"


def test_extract_quarterly_rows_handles_api_notices():
    conn = AlphaVantageEstimatesConnector()
    assert conn._extract_quarterly_rows({"Note": "rate limited"}, "IBM") == []
    assert conn._extract_quarterly_rows({"Error Message": "bad symbol"}, "BADTICKER") == []
    assert conn._extract_quarterly_rows({}, "IBM") == []


@pytest.mark.asyncio
async def test_validate_drops_missing_estimated_eps():
    conn = AlphaVantageEstimatesConnector()
    rows = conn._extract_quarterly_rows(SAMPLE_EARNINGS_RESPONSE, "IBM")
    valid = await conn.validate(rows)
    # The "None"-sentinel row is dropped; the other two survive.
    assert len(valid) == 2
    assert all(r["estimatedEPS"] != "None" for r in valid)


@pytest.mark.asyncio
async def test_transform_maps_period_and_mean():
    conn = AlphaVantageEstimatesConnector()
    rows = conn._extract_quarterly_rows(SAMPLE_EARNINGS_RESPONSE, "IBM")
    valid = await conn.validate(rows)
    out = await conn.transform(valid)

    assert len(out) == 2
    by_period = {r["period_end_date"]: r for r in out}

    q1 = by_period[date(2024, 3, 31)]
    assert q1["ticker"] == "IBM"
    assert q1["metric"] == "EPS"
    assert q1["period_type"] == "QUARTERLY"
    assert q1["fiscal_year"] == 2024
    assert q1["fiscal_quarter"] == 1
    assert q1["mean"] == pytest.approx(1.61)
    # Honest about the single-figure limitation of this endpoint.
    assert q1["high"] is None
    assert q1["low"] is None
    assert q1["median"] is None
    assert q1["as_of_date"] == date.today()

    q2 = by_period[date(2024, 6, 30)]
    assert q2["fiscal_quarter"] == 2
    assert q2["mean"] == pytest.approx(2.35)


@pytest.mark.asyncio
async def test_extract_mocked_http(monkeypatch):
    """Extract path against a mocked httpx response, rate-limited per-ticker."""

    class _Resp:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return SAMPLE_EARNINGS_RESPONSE

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def get(self, url, params=None):
            assert params["function"] == "EARNINGS"
            return _Resp()

        async def aclose(self):
            pass

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    monkeypatch.setattr(settings, "ALPHA_VANTAGE_API_KEY", "test-key")

    conn = AlphaVantageEstimatesConnector(tickers=["IBM"])
    raw = await conn.extract()
    assert len(raw) == 3
    await conn.close()


@pytest.mark.asyncio
async def test_extract_noops_without_api_key():
    conn = AlphaVantageEstimatesConnector(api_key="", tickers=["IBM"])
    assert await conn.extract() == []


@pytest.mark.asyncio
async def test_extract_noops_without_tickers():
    conn = AlphaVantageEstimatesConnector(api_key="test-key", tickers=[])
    assert await conn.extract() == []


@pytest.mark.asyncio
async def test_load_resolves_ticker_and_upserts(session):
    from src.models.security import Security, SecurityIdentifier

    sec_id = uuid.uuid4()
    session.add(
        Security(
            security_id=sec_id,
            security_type="EQUITY",
            name="International Business Machines",
            status="ACTIVE",
            asset_class="EQUITY",
        )
    )
    session.add(
        SecurityIdentifier(
            id=uuid.uuid4(), security_id=sec_id, identifier_type="TICKER", identifier_value="IBM"
        )
    )
    await session.flush()

    conn = AlphaVantageEstimatesConnector()
    rows = conn._extract_quarterly_rows(SAMPLE_EARNINGS_RESPONSE, "IBM")
    recs = await conn.transform(await conn.validate(rows))
    stats = await conn.load(recs, session)
    assert stats["inserted"] == 2
    assert stats["skipped"] == 0
    await session.flush()

    from src.models.estimates import ConsensusEstimate

    rows_db = (await session.execute(select(ConsensusEstimate))).scalars().all()
    assert len(rows_db) == 2
    assert all(r.security_id == sec_id for r in rows_db)
    assert all(r.metric == "EPS" for r in rows_db)

    # Re-loading upserts rather than duplicating.
    stats2 = await conn.load(recs, session)
    assert stats2["inserted"] == 0
    assert stats2["updated"] == 2


@pytest.mark.asyncio
async def test_load_skips_unresolvable_ticker(session):
    """No Security exists for UNKNOWN — must be skipped, not fabricated."""
    conn = AlphaVantageEstimatesConnector()
    unresolvable = {
        "symbol": "UNKNOWN",
        "annualEarnings": [],
        "quarterlyEarnings": SAMPLE_EARNINGS_RESPONSE["quarterlyEarnings"],
    }
    rows = conn._extract_quarterly_rows(unresolvable, "UNKNOWN")
    recs = await conn.transform(await conn.validate(rows))
    stats = await conn.load(recs, session)
    assert stats["inserted"] == 0
    assert stats["skipped"] == 2

    from src.models.estimates import ConsensusEstimate

    rows_db = (await session.execute(select(ConsensusEstimate))).scalars().all()
    assert len(rows_db) == 0
