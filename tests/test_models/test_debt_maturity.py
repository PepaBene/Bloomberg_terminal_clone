"""Tests for debt maturity profile models."""

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from src.models.debt_maturity import DebtMaturityProfile, MaturityBucket
from src.models.entity import Entity


@pytest.mark.asyncio
async def test_create_debt_maturity_profile(session):
    """Test creating a debt maturity profile."""
    entity_id = uuid.uuid4()
    entity = Entity(
        entity_id=entity_id,
        entity_type="PUBLIC_COMPANY",
        legal_name="Maturity Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()

    profile_id = uuid.uuid4()
    profile = DebtMaturityProfile(
        profile_id=profile_id,
        entity_id=entity_id,
        as_of_date=date(2025, 12, 31),
        debt_maturing_1yr=500000000.00,
        debt_maturing_2yr=1200000000.00,
        debt_maturing_3yr=2000000000.00,
        pct_debt_maturing_1yr=0.10,
        pct_debt_maturing_3yr=0.40,
        weighted_avg_maturity_years=4.50,
        weighted_avg_coupon=0.0525,
        cash_to_1yr_maturities=2.50,
        fcf_to_1yr_maturities=1.80,
        maturity_wall_alert=False,
        near_term_stress=False,
    )
    session.add(profile)
    await session.flush()

    result = await session.execute(
        select(DebtMaturityProfile).where(DebtMaturityProfile.profile_id == profile_id)
    )
    fetched = result.scalar_one()
    assert fetched.entity_id == entity_id
    assert float(fetched.debt_maturing_1yr) == 500000000.00
    assert float(fetched.weighted_avg_maturity_years) == 4.50
    assert fetched.maturity_wall_alert is False


@pytest.mark.asyncio
async def test_create_maturity_bucket(session):
    """Test creating maturity buckets linked to a profile."""
    entity_id = uuid.uuid4()
    entity = Entity(
        entity_id=entity_id,
        entity_type="PUBLIC_COMPANY",
        legal_name="Bucket Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()

    profile_id = uuid.uuid4()
    profile = DebtMaturityProfile(
        profile_id=profile_id,
        entity_id=entity_id,
        as_of_date=date(2025, 12, 31),
    )
    session.add(profile)
    await session.flush()

    for year in [2026, 2027, 2028]:
        session.add(MaturityBucket(
            bucket_id=uuid.uuid4(),
            profile_id=profile_id,
            year=year,
            total_amount=500000000.00 * (year - 2025),
            breakdown=[{"instrument_name": f"Notes due {year}", "amount": 500000000.00 * (year - 2025)}],
        ))
    await session.flush()

    result = await session.execute(
        select(MaturityBucket).where(MaturityBucket.profile_id == profile_id)
    )
    buckets = result.scalars().all()
    assert len(buckets) == 3
    years = {b.year for b in buckets}
    assert years == {2026, 2027, 2028}


@pytest.mark.asyncio
async def test_profile_bucket_relationship(session):
    """Test that buckets are loaded via the profile relationship."""
    entity_id = uuid.uuid4()
    entity = Entity(
        entity_id=entity_id,
        entity_type="PUBLIC_COMPANY",
        legal_name="Rel Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()

    profile_id = uuid.uuid4()
    profile = DebtMaturityProfile(
        profile_id=profile_id,
        entity_id=entity_id,
        as_of_date=date(2025, 12, 31),
        maturity_wall_alert=True,
    )
    session.add(profile)
    await session.flush()

    session.add(MaturityBucket(
        bucket_id=uuid.uuid4(),
        profile_id=profile_id,
        year=2027,
        total_amount=2000000000.00,
    ))
    await session.flush()

    result = await session.execute(
        select(DebtMaturityProfile).where(DebtMaturityProfile.profile_id == profile_id)
    )
    fetched = result.scalar_one()
    assert fetched.maturity_wall_alert is True
    assert len(fetched.buckets) == 1
    assert fetched.buckets[0].year == 2027


@pytest.mark.asyncio
async def test_maturity_profile_alerts(session):
    """Test alert flags on a stressed maturity profile."""
    entity_id = uuid.uuid4()
    entity = Entity(
        entity_id=entity_id,
        entity_type="PUBLIC_COMPANY",
        legal_name="Stress Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()

    profile = DebtMaturityProfile(
        profile_id=uuid.uuid4(),
        entity_id=entity_id,
        as_of_date=date(2025, 12, 31),
        debt_maturing_1yr=3000000000.00,
        pct_debt_maturing_1yr=0.60,
        cash_to_1yr_maturities=0.30,
        maturity_wall_alert=True,
        near_term_stress=True,
    )
    session.add(profile)
    await session.flush()

    result = await session.execute(
        select(DebtMaturityProfile).where(DebtMaturityProfile.entity_id == entity_id)
    )
    fetched = result.scalar_one()
    assert fetched.maturity_wall_alert is True
    assert fetched.near_term_stress is True
    assert float(fetched.cash_to_1yr_maturities) == pytest.approx(0.30, abs=0.01)
