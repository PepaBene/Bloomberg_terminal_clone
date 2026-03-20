"""Tests for estimates models."""

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from src.models.estimates import CompanyGuidance, ConsensusEstimate, EstimateSurprise
from src.models.security import Security
from src.models.entity import Entity


@pytest.mark.asyncio
async def test_create_consensus_estimate(session):
    """Test creating a consensus estimate record."""
    security = Security(
        security_id=uuid.uuid4(),
        security_type="COMMON_STOCK",
        name="Test Corp Common Stock",
        short_name="TEST",
        status="ACTIVE",
        asset_class="EQUITY",
        primary_currency="USD",
    )
    session.add(security)
    await session.flush()

    estimate = ConsensusEstimate(
        security_id=security.security_id,
        metric="EPS",
        period_end_date=date(2025, 12, 31),
        as_of_date=date(2025, 10, 15),
        fiscal_year=2025,
        fiscal_quarter=4,
        period_type="QUARTERLY",
        mean=3.45,
        median=3.42,
        high=4.00,
        low=3.00,
        standard_deviation=0.25,
        num_estimates=25,
        num_revisions_up=10,
        num_revisions_down=3,
    )
    session.add(estimate)
    await session.flush()

    result = await session.execute(
        select(ConsensusEstimate).where(
            ConsensusEstimate.security_id == security.security_id,
            ConsensusEstimate.metric == "EPS",
        )
    )
    fetched = result.scalar_one()
    assert float(fetched.mean) == 3.45
    assert fetched.num_estimates == 25
    assert fetched.fiscal_year == 2025


@pytest.mark.asyncio
async def test_create_estimate_surprise(session):
    """Test creating an estimate surprise record."""
    security = Security(
        security_id=uuid.uuid4(),
        security_type="COMMON_STOCK",
        name="Surprise Corp",
        short_name="SURP",
        status="ACTIVE",
        asset_class="EQUITY",
        primary_currency="USD",
    )
    session.add(security)
    await session.flush()

    surprise = EstimateSurprise(
        surprise_id=uuid.uuid4(),
        security_id=security.security_id,
        fiscal_year=2025,
        fiscal_quarter=3,
        period_type="QUARTERLY",
        metric="EPS",
        consensus_estimate=2.50,
        actual_value=2.75,
        surprise=0.25,
        surprise_percent=10.0,
        announcement_date=date(2025, 10, 25),
    )
    session.add(surprise)
    await session.flush()

    result = await session.execute(
        select(EstimateSurprise).where(
            EstimateSurprise.surprise_id == surprise.surprise_id
        )
    )
    fetched = result.scalar_one()
    assert float(fetched.surprise_percent) == 10.0
    assert float(fetched.actual_value) == 2.75


@pytest.mark.asyncio
async def test_create_company_guidance(session):
    """Test creating a company guidance record."""
    entity = Entity(
        entity_id=uuid.uuid4(),
        entity_type="PUBLIC_COMPANY",
        legal_name="Guidance Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()

    guidance = CompanyGuidance(
        guidance_id=uuid.uuid4(),
        entity_id=entity.entity_id,
        fiscal_year=2025,
        period_type="ANNUAL",
        metric="REVENUE",
        guidance_type="RANGE",
        low_estimate=50000.0,
        high_estimate=55000.0,
        guidance_date=date(2025, 7, 15),
        source_event="Q2 2025 Earnings Call",
    )
    session.add(guidance)
    await session.flush()

    result = await session.execute(
        select(CompanyGuidance).where(
            CompanyGuidance.guidance_id == guidance.guidance_id
        )
    )
    fetched = result.scalar_one()
    assert float(fetched.low_estimate) == 50000.0
    assert fetched.guidance_type == "RANGE"
    assert fetched.source_event == "Q2 2025 Earnings Call"


@pytest.mark.asyncio
async def test_query_consensus_by_metric(session):
    """Test querying consensus estimates filtered by metric."""
    security = Security(
        security_id=uuid.uuid4(),
        security_type="COMMON_STOCK",
        name="Multi Metric Corp",
        short_name="MMC",
        status="ACTIVE",
        asset_class="EQUITY",
        primary_currency="USD",
    )
    session.add(security)
    await session.flush()

    # Create estimates for two different metrics
    for metric in ("EPS", "REVENUE"):
        estimate = ConsensusEstimate(
            security_id=security.security_id,
            metric=metric,
            period_end_date=date(2025, 12, 31),
            as_of_date=date(2025, 11, 1),
            fiscal_year=2025,
            mean=100.0 if metric == "REVENUE" else 3.50,
            num_estimates=20,
        )
        session.add(estimate)
    await session.flush()

    # Query only EPS
    result = await session.execute(
        select(ConsensusEstimate).where(
            ConsensusEstimate.security_id == security.security_id,
            ConsensusEstimate.metric == "EPS",
        )
    )
    eps_estimates = result.scalars().all()
    assert len(eps_estimates) == 1
    assert float(eps_estimates[0].mean) == 3.50

    # Query only REVENUE
    result = await session.execute(
        select(ConsensusEstimate).where(
            ConsensusEstimate.security_id == security.security_id,
            ConsensusEstimate.metric == "REVENUE",
        )
    )
    rev_estimates = result.scalars().all()
    assert len(rev_estimates) == 1
    assert float(rev_estimates[0].mean) == 100.0
