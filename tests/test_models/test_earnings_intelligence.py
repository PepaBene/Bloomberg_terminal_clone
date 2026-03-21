"""Tests for earnings intelligence models."""

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from src.models.earnings_intelligence import EarningsSurprise, GuidanceTracking
from src.models.entity import Entity


@pytest.mark.asyncio
async def test_create_earnings_surprise(session):
    """Test creating an earnings surprise record."""
    entity_id = uuid.uuid4()
    entity = Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name="Earnings Corp", status="ACTIVE", source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()

    surprise_id = uuid.uuid4()
    surprise = EarningsSurprise(
        surprise_id=surprise_id,
        entity_id=entity_id,
        fiscal_year=2026,
        fiscal_quarter=1,
        actual_eps=2.15,
        consensus_eps=2.05,
        eps_surprise=0.10,
        eps_surprise_pct=0.0488,
        price_reaction_pct=0.035,
        announcement_date=date(2026, 1, 25),
    )
    session.add(surprise)
    await session.flush()

    result = await session.execute(
        select(EarningsSurprise).where(EarningsSurprise.surprise_id == surprise_id)
    )
    fetched = result.scalar_one()
    assert float(fetched.actual_eps) == pytest.approx(2.15, abs=0.01)
    assert float(fetched.eps_surprise) == pytest.approx(0.10, abs=0.01)


@pytest.mark.asyncio
async def test_list_surprises_by_entity(session):
    """Test querying surprises for an entity across quarters."""
    entity_id = uuid.uuid4()
    entity = Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name="Quarterly Corp", status="ACTIVE", source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()

    for q in range(1, 5):
        session.add(EarningsSurprise(
            surprise_id=uuid.uuid4(),
            entity_id=entity_id,
            fiscal_year=2025,
            fiscal_quarter=q,
            actual_eps=1.50 + q * 0.1,
        ))
    await session.flush()

    result = await session.execute(
        select(EarningsSurprise).where(EarningsSurprise.entity_id == entity_id)
    )
    surprises = result.scalars().all()
    assert len(surprises) == 4


@pytest.mark.asyncio
async def test_create_guidance(session):
    """Test creating a guidance tracking record."""
    entity_id = uuid.uuid4()
    entity = Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name="Guidance Corp", status="ACTIVE", source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()

    guidance_id = uuid.uuid4()
    guidance = GuidanceTracking(
        guidance_id=guidance_id,
        entity_id=entity_id,
        guidance_fiscal_year=2026,
        metric="EPS",
        guidance_low=8.50,
        guidance_high=9.00,
        guidance_midpoint=8.75,
        guidance_date=date(2026, 1, 25),
        guidance_type="INITIAL",
        guidance_vs_consensus="ABOVE",
    )
    session.add(guidance)
    await session.flush()

    result = await session.execute(
        select(GuidanceTracking).where(GuidanceTracking.guidance_id == guidance_id)
    )
    fetched = result.scalar_one()
    assert fetched.metric == "EPS"
    assert float(fetched.guidance_midpoint) == pytest.approx(8.75, abs=0.01)
    assert fetched.guidance_vs_consensus == "ABOVE"


@pytest.mark.asyncio
async def test_guidance_revision(session):
    """Test guidance raised scenario."""
    entity_id = uuid.uuid4()
    entity = Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name="Revised Corp", status="ACTIVE", source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()

    session.add(GuidanceTracking(
        guidance_id=uuid.uuid4(),
        entity_id=entity_id,
        guidance_fiscal_year=2026,
        metric="REVENUE",
        guidance_low=10000.0,
        guidance_high=10500.0,
        guidance_midpoint=10250.0,
        guidance_date=date(2026, 1, 25),
        guidance_type="INITIAL",
    ))
    session.add(GuidanceTracking(
        guidance_id=uuid.uuid4(),
        entity_id=entity_id,
        guidance_fiscal_year=2026,
        metric="REVENUE",
        guidance_low=10500.0,
        guidance_high=11000.0,
        guidance_midpoint=10750.0,
        guidance_date=date(2026, 4, 25),
        guidance_type="RAISED",
        prior_guidance_low=10000.0,
        prior_guidance_high=10500.0,
    ))
    await session.flush()

    result = await session.execute(
        select(GuidanceTracking)
        .where(GuidanceTracking.entity_id == entity_id)
        .order_by(GuidanceTracking.guidance_date.asc())
    )
    records = result.scalars().all()
    assert len(records) == 2
    assert records[1].guidance_type == "RAISED"
