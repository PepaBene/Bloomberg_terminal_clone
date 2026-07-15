"""Tests for the ESG controversies connector (configurable feed).

Exercises parsing helpers, transform normalization, mocked HTTP extract, and
the DB load of ESGControversy rows against a seeded entity. No network.
"""

import uuid
from datetime import date
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from src.ingestion.edgar_esg_controversies import (
    EsgControversiesConnector,
    _bump_for_recency,
    _classify_article,
    _gdelt_keyword_query,
    _parse_date,
    _parse_seendate,
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


# --------------------------------------------------------------------------
# GDELT extract path
# --------------------------------------------------------------------------

# Realistic fixture matching GDELT DOC 2.0 API's documented artlist/JSON
# response shape: {"articles": [{"url":..., "title":..., "seendate":...,
# "domain":..., "sourcecountry":...}, ...]}
SAMPLE_GDELT_RESPONSE = {
    "articles": [
        {
            "url": "https://news.example.com/acme-lawsuit-filed",
            "title": "Acme Corp faces class action lawsuit over data breach",
            "seendate": "20260710T120000Z",
            "domain": "news.example.com",
            "sourcecountry": "United States",
        },
        {
            "url": "https://wire.example.com/acme-epa-fine",
            "title": "Acme Corp fined by regulators for emissions violation",
            "seendate": "20260601T090000Z",
            "domain": "wire.example.com",
            "sourcecountry": "United States",
        },
        {
            # Missing title -> dropped in _extract_gdelt
            "url": "https://wire.example.com/no-title",
            "seendate": "20260601T090000Z",
            "domain": "wire.example.com",
        },
    ]
}


def test_gdelt_keyword_query_groups_all_keywords():
    query = _gdelt_keyword_query()
    assert query.startswith("(") and query.endswith(")")
    assert "lawsuit" in query
    assert '"class action"' in query  # multiword keywords are quoted


def test_classify_article_matches_keyword_and_defaults():
    assert _classify_article("Company sued in class action lawsuit") == ("LEGAL", "high")
    assert _classify_article("Regulators issue fine for pollution violation") == (
        "REGULATORY",
        "moderate",
    )
    assert _classify_article("Whistleblower alleges accounting fraud") == (
        "REPUTATIONAL",
        "severe",
    )
    assert _classify_article("Company announces new product line") == ("OTHER", "moderate")


def test_bump_for_recency_bumps_only_within_window():
    today = date(2026, 7, 15)
    # 3 days old -> bumped one rank
    assert _bump_for_recency("moderate", date(2026, 7, 12), today=today) == "high"
    # 30 days old -> no bump
    assert _bump_for_recency("moderate", date(2026, 6, 15), today=today) == "moderate"
    # Capped at "severe" even if already "severe"
    assert _bump_for_recency("severe", date(2026, 7, 14), today=today) == "severe"
    # No seendate -> unchanged
    assert _bump_for_recency("high", None, today=today) is not None


def test_parse_seendate():
    assert _parse_seendate("20260710T120000Z") == date(2026, 7, 10)
    assert _parse_seendate(None) is None
    assert _parse_seendate("garbage") is None


@pytest.mark.asyncio
async def test_extract_gdelt_mocked_http(monkeypatch):
    captured_params: dict = {}

    class _Resp:
        status_code = 200

        def raise_for_status(self):
            pass

        @property
        def text(self):
            import json

            return json.dumps(SAMPLE_GDELT_RESPONSE)

        def json(self):
            return SAMPLE_GDELT_RESPONSE

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def get(self, url, params=None):
            captured_params.update(params or {})
            return _Resp()

        async def aclose(self):
            pass

    monkeypatch.setattr(httpx, "AsyncClient", _Client)

    conn = EsgControversiesConnector(
        entities=[{"cik": "0009000789", "legal_name": "Acme Corp"}],
        gdelt_lookback_days=90,
        max_articles_per_entity=5,
    )
    raw = await conn.extract()
    await conn.close()

    # 2 articles kept (one dropped for missing title)
    assert len(raw) == 2
    assert '"Acme Corp"' in captured_params["query"]
    assert "tone<-2" in captured_params["query"]
    assert captured_params["timespan"] == "90d"

    lawsuit_row = next(r for r in raw if "lawsuit" in r["description"].lower())
    assert lawsuit_row["controversy_type"] == "LEGAL"
    assert lawsuit_row["severity"] in ("high", "severe")  # may be recency-bumped
    assert lawsuit_row["cik"] == "0009000789"
    assert lawsuit_row["source"] == "GDELT"
    assert lawsuit_row["source_url"] == "https://news.example.com/acme-lawsuit-filed"


@pytest.mark.asyncio
async def test_extract_dispatches_to_gdelt_when_no_feed_url(monkeypatch):
    """extract() should use GDELT when no feed_url is set but entities are given."""

    class _Resp:
        status_code = 200

        def raise_for_status(self):
            pass

        @property
        def text(self):
            import json

            return json.dumps({"articles": []})

        def json(self):
            return {"articles": []}

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def get(self, url, params=None):
            return _Resp()

        async def aclose(self):
            pass

    monkeypatch.setattr(httpx, "AsyncClient", _Client)

    conn = EsgControversiesConnector(entities=[{"cik": "123", "legal_name": "Foo Inc"}])
    raw = await conn.extract()
    await conn.close()
    assert raw == []


@pytest.mark.asyncio
async def test_extract_returns_empty_with_no_feed_and_no_entities():
    conn = EsgControversiesConnector()
    raw = await conn.extract()
    assert raw == []


@pytest.mark.asyncio
async def test_gdelt_end_to_end_transform_and_load(monkeypatch, session):
    from src.models.entity import Entity, EntityIdentifier
    from src.models.esg import ESGControversy

    eid = uuid.uuid4()
    session.add(
        Entity(
            entity_id=eid,
            entity_type="PUBLIC_COMPANY",
            legal_name="Acme Corp",
            status="ACTIVE",
            source="TEST",
        )
    )
    session.add(
        EntityIdentifier(
            id=uuid.uuid4(),
            entity_id=eid,
            identifier_type="CIK",
            identifier_value="0009000789",
        )
    )
    await session.flush()

    class _Resp:
        status_code = 200

        def raise_for_status(self):
            pass

        @property
        def text(self):
            import json

            return json.dumps(SAMPLE_GDELT_RESPONSE)

        def json(self):
            return SAMPLE_GDELT_RESPONSE

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def get(self, url, params=None):
            return _Resp()

        async def aclose(self):
            pass

    monkeypatch.setattr(httpx, "AsyncClient", _Client)

    conn = EsgControversiesConnector(
        entities=[{"cik": "0009000789", "legal_name": "Acme Corp"}]
    )
    raw = await conn.extract()
    valid = await conn.validate(raw)
    transformed = await conn.transform(valid)
    stats = await conn.load(transformed, session)
    await conn.close()

    assert stats["inserted"] == 2
    rows = (await session.execute(select(ESGControversy))).scalars().all()
    assert len(rows) == 2
    assert all(r.entity_id == eid for r in rows)
    assert all(r.source == "GDELT" for r in rows)
