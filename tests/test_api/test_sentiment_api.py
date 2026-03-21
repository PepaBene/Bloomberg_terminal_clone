"""API tests for sentiment analysis endpoints (Pillar 2 Supplement – Part 8)."""

import uuid
from datetime import date, datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entity import Entity
from src.models.sentiment import SentimentScore, SentimentAggregate, EarningsCallSentiment


async def _seed_entity(session: AsyncSession, name: str = "Sentiment Test Corp") -> uuid.UUID:
    eid = uuid.uuid4()
    session.add(Entity(
        entity_id=eid,
        entity_type="PUBLIC_COMPANY",
        legal_name=name,
        status="ACTIVE",
        source="TEST",
        confidence_score=0.99,
    ))
    await session.commit()
    return eid


@pytest.mark.asyncio
async def test_score_text(client: AsyncClient):
    resp = await client.post("/v1/analytics/sentiment/score", json={
        "text": "The company reported strong growth and beat expectations.",
        "source_type": "NEWS_ARTICLE",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["sentiment"] == "POSITIVE"
    assert data["sentiment_score"] > 0
    assert data["ai_enabled"] is False


@pytest.mark.asyncio
async def test_score_negative_text(client: AsyncClient):
    resp = await client.post("/v1/analytics/sentiment/score", json={
        "text": "Revenue decline and significant loss led to a downgrade warning.",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["sentiment"] == "NEGATIVE"
    assert data["sentiment_score"] < 0


@pytest.mark.asyncio
async def test_get_aggregate_empty(client: AsyncClient, session: AsyncSession):
    eid = await _seed_entity(session)
    resp = await client.get(f"/v1/analytics/sentiment/{eid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["entity_id"] == str(eid)
    assert data["avg_sentiment"] == 0.0
    assert data["article_count"] == 0


@pytest.mark.asyncio
async def test_get_aggregate_with_data(client: AsyncClient, session: AsyncSession):
    eid = await _seed_entity(session)
    agg = SentimentAggregate(
        id=uuid.uuid4(),
        entity_id=eid,
        as_of_date=date(2024, 8, 1),
        timeframe="ROLLING_30D",
        avg_sentiment=0.35,
        article_count=10,
        positive_pct=0.6,
        negative_pct=0.2,
        anomaly_flag=False,
    )
    session.add(agg)
    await session.commit()

    resp = await client.get(
        f"/v1/analytics/sentiment/{eid}",
        params={"timeframe": "ROLLING_30D"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["avg_sentiment"] == pytest.approx(0.35, abs=0.01)
    assert data["article_count"] == 10


@pytest.mark.asyncio
async def test_get_history(client: AsyncClient, session: AsyncSession):
    eid = await _seed_entity(session)
    for i in range(3):
        session.add(SentimentScore(
            score_id=uuid.uuid4(),
            entity_id=eid,
            source_type="NEWS_ARTICLE",
            source_date=datetime(2024, 8, 1 + i, tzinfo=timezone.utc),
            sentiment="POSITIVE",
            sentiment_score=0.5,
            confidence=0.8,
        ))
    await session.commit()

    resp = await client.get(f"/v1/analytics/sentiment/{eid}/history")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] == 3
    assert len(data["history"]) == 3


@pytest.mark.asyncio
async def test_get_earnings_calls(client: AsyncClient, session: AsyncSession):
    eid = await _seed_entity(session)
    session.add(EarningsCallSentiment(
        id=uuid.uuid4(),
        entity_id=eid,
        call_date=date(2024, 7, 25),
        fiscal_year=2024,
        fiscal_quarter=3,
        overall_tone=0.3,
        management_tone=0.5,
        qa_tone=0.1,
        hedging_count=5,
        confidence_count=10,
    ))
    await session.commit()

    resp = await client.get(f"/v1/analytics/sentiment/{eid}/earnings-calls")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["fiscal_quarter"] == 3
    assert data[0]["overall_tone"] == pytest.approx(0.3, abs=0.01)


@pytest.mark.asyncio
async def test_get_anomalies_empty(client: AsyncClient):
    resp = await client.get("/v1/analytics/sentiment/anomalies")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_entity_not_found(client: AsyncClient):
    fake_id = uuid.uuid4()
    resp = await client.get(f"/v1/analytics/sentiment/{fake_id}")
    assert resp.status_code == 404
