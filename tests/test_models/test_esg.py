"""Tests for ESG & Sustainability models."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from src.models.esg import ESGControversy, ESGMetric, ESGScore


@pytest.mark.asyncio
async def test_create_esg_score(session):
    """Test creating an ESG score record."""
    entity_id = uuid.uuid4()
    score = ESGScore(
        score_id=uuid.uuid4(),
        entity_id=entity_id,
        provider="MSCI",
        as_of_date=date(2025, 12, 31),
        esg_score=Decimal("72.50"),
        esg_percentile=Decimal("85.00"),
        esg_rating="AA",
        environmental_score=Decimal("78.30"),
        social_score=Decimal("65.10"),
        governance_score=Decimal("74.00"),
        controversy_score=Decimal("3.00"),
        controversy_level="LOW",
        score_trend="IMPROVING",
    )
    session.add(score)
    await session.flush()

    result = await session.execute(
        select(ESGScore).where(ESGScore.entity_id == entity_id)
    )
    fetched = result.scalar_one()
    assert float(fetched.esg_score) == 72.50
    assert fetched.esg_rating == "AA"
    assert fetched.provider == "MSCI"
    assert float(fetched.environmental_score) == 78.30


@pytest.mark.asyncio
async def test_create_esg_metric(session):
    """Test creating an ESG metric record."""
    entity_id = uuid.uuid4()
    metric = ESGMetric(
        metric_id=uuid.uuid4(),
        entity_id=entity_id,
        metric_type="CARBON_EMISSIONS",
        metric_category="ENVIRONMENTAL",
        period_end_date=date(2025, 12, 31),
        period_type="ANNUAL",
        value=Decimal("1250000.500000"),
        unit="tonnes CO2e",
        is_reported=True,
        source="CDP",
    )
    session.add(metric)
    await session.flush()

    result = await session.execute(
        select(ESGMetric).where(ESGMetric.entity_id == entity_id)
    )
    fetched = result.scalar_one()
    assert fetched.metric_type == "CARBON_EMISSIONS"
    assert fetched.metric_category == "ENVIRONMENTAL"
    assert fetched.unit == "tonnes CO2e"
    assert fetched.is_reported is True


@pytest.mark.asyncio
async def test_create_esg_controversy(session):
    """Test creating an ESG controversy record."""
    entity_id = uuid.uuid4()
    controversy = ESGControversy(
        controversy_id=uuid.uuid4(),
        entity_id=entity_id,
        controversy_type="ENVIRONMENTAL_SPILL",
        severity="HIGH",
        description="Major oil spill in coastal waters.",
        start_date=date(2025, 6, 15),
        status="ONGOING",
        estimated_financial_impact=Decimal("500000000.00"),
        source="NEWS",
        source_url="https://example.com/article",
    )
    session.add(controversy)
    await session.flush()

    result = await session.execute(
        select(ESGControversy).where(ESGControversy.entity_id == entity_id)
    )
    fetched = result.scalar_one()
    assert fetched.controversy_type == "ENVIRONMENTAL_SPILL"
    assert fetched.severity == "HIGH"
    assert fetched.status == "ONGOING"
    assert float(fetched.estimated_financial_impact) == 500000000.00


@pytest.mark.asyncio
async def test_query_esg_scores_by_provider(session):
    """Test querying ESG scores filtered by provider."""
    entity_id = uuid.uuid4()

    # Create scores from two providers
    for provider, score_val, rating in [
        ("MSCI", Decimal("72.50"), "AA"),
        ("SUSTAINALYTICS", Decimal("25.30"), "LOW_RISK"),
    ]:
        score = ESGScore(
            score_id=uuid.uuid4(),
            entity_id=entity_id,
            provider=provider,
            as_of_date=date(2025, 12, 31),
            esg_score=score_val,
            esg_rating=rating,
        )
        session.add(score)
    await session.flush()

    # Query by provider
    result = await session.execute(
        select(ESGScore).where(
            ESGScore.entity_id == entity_id,
            ESGScore.provider == "MSCI",
        )
    )
    scores = result.scalars().all()
    assert len(scores) == 1
    assert scores[0].esg_rating == "AA"

    # Query all for entity
    result_all = await session.execute(
        select(ESGScore).where(ESGScore.entity_id == entity_id)
    )
    all_scores = result_all.scalars().all()
    assert len(all_scores) == 2
