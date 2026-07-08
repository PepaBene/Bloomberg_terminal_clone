"""Tests for the ESG controversies connector (configurable feed).

Exercises parsing helpers, transform normalization, mocked HTTP extract, and
the DB load of ESGControversy rows against a seeded entity. No network.
"""

import uuid
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from src.ingestion.edgar_esg_controversies import (
    EsgControversiesConnector,
    _parse_date,
    _to_decimal,
)

SAMPLE_FEED = [
    {
        "cik": "9000789",
        "controversy_type": "environmental",
        "severity": "major",
        "description": "Alleged emissions violation",
        "start_date": "2024-03-01",
        "status": "ongoing",
        "estimated_financial_impact": "5000000",
        "source": "ExampleFeed",
        "url": "https://example.com/story",
    },
    {  # missing controversy_type → dropped in validate
        "cik": "9000789",
        "severity": "low",
    },
]


def test_parse_helpers():
    assert _parse_date("2024-03-01").isoformat() == "2024-03-01"
    assert _parse_date("03/01/2024").isoformat() == "2024-03-01"
    assert _parse_date("") is None
    assert _to_decimal("5000000") == Decimal("5000000")
    assert _to_decimal("N/A") is None


@pytest.mark.asyncio
async def test_validate_and_transform():
    conn = EsgControversiesConnector(feed_url="http://x")
    valid = await conn.validate(SAMPLE_FEED)
    assert len(valid) == 1
    out = await conn.transform(valid)
    row = out[0]
    assert row["cik"] == "0009000789"
    assert row["controversy_type"] == "ENVIRONMENTAL"
    assert row["severity"] == "HIGH"  # "major" → HIGH
    assert row["status"] == "ONGOING"
    assert row["estimated_financial_impact"] == Decimal("5000000")


@pytest.mark.asyncio
async def test_extract_mocked_http(monkeypatch):
    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return SAMPLE_FEED

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
    conn = EsgControversiesConnector(feed_url="http://feed")
    raw = await conn.extract()
    assert len(raw) == 2


@pytest.mark.asyncio
async def test_load_resolves_cik_and_dedupes(session):
    from src.models.entity import Entity, EntityIdentifier

    eid = uuid.uuid4()
    session.add(Entity(entity_id=eid, entity_type="PUBLIC_COMPANY", legal_name="Apple Inc.", status="ACTIVE", source="TEST"))
    session.add(EntityIdentifier(id=uuid.uuid4(), entity_id=eid, identifier_type="CIK", identifier_value="0009000789"))
    await session.flush()

    conn = EsgControversiesConnector(feed_url="http://x")
    recs = await conn.transform(await conn.validate(SAMPLE_FEED))
    stats = await conn.load(recs, session)
    assert stats["inserted"] == 1
    await session.flush()

    from src.models.esg import ESGControversy

    rows = (await session.execute(select(ESGControversy))).scalars().all()
    assert len(rows) == 1
    assert rows[0].entity_id == eid
    assert rows[0].controversy_type == "ENVIRONMENTAL"
    assert rows[0].estimated_financial_impact == Decimal("5000000")

    stats2 = await conn.load(recs, session)
    assert stats2["inserted"] == 0
    assert stats2["skipped"] == 1


@pytest.mark.asyncio
async def test_load_skips_unresolved_cik(session):
    conn = EsgControversiesConnector(feed_url="http://x")
    feed = [
        {
            "cik": "9999999",  # never seeded → unresolved
            "controversy_type": "governance",
            "description": "Unresolved-CIK row",
            "start_date": "2024-01-01",
        }
    ]
    recs = await conn.transform(await conn.validate(feed))
    stats = await conn.load(recs, session)
    assert stats["skipped"] == 1
    assert stats["inserted"] == 0
