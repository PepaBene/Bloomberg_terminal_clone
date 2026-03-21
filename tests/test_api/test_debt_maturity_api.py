"""Tests for Debt Maturity Profile API endpoints."""

import uuid
from datetime import date

import pytest

from src.models.debt_maturity import DebtMaturityProfile, MaturityBucket
from src.models.entity import Entity


@pytest.mark.asyncio
async def test_get_debt_maturity_not_found(client):
    """Test 404 when no debt maturity profile exists."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/entities/{fake_id}/debt-maturity")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_debt_maturity(client, session):
    """Test fetching debt maturity profile with buckets."""
    entity_id = uuid.uuid4()
    entity = Entity(
        entity_id=entity_id,
        entity_type="PUBLIC_COMPANY",
        legal_name="Maturity API Corp",
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
        weighted_avg_maturity_years=4.50,
        maturity_wall_alert=False,
        near_term_stress=False,
    )
    session.add(profile)
    await session.flush()

    session.add(MaturityBucket(
        bucket_id=uuid.uuid4(),
        profile_id=profile_id,
        year=2026,
        total_amount=500000000.00,
    ))
    await session.flush()

    response = await client.get(f"/v1/entities/{entity_id}/debt-maturity")
    assert response.status_code == 200
    data = response.json()
    assert data["entity_id"] == str(entity_id)
    assert data["debt_maturing_1yr"] == 500000000.00
    assert len(data["buckets"]) == 1
    assert data["buckets"][0]["year"] == 2026


@pytest.mark.asyncio
async def test_get_debt_maturity_metrics_not_found(client):
    """Test 404 for metrics when no data exists."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/entities/{fake_id}/debt-maturity/metrics")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_debt_maturity_metrics(client, session):
    """Test fetching derived maturity metrics."""
    entity_id = uuid.uuid4()
    entity = Entity(
        entity_id=entity_id,
        entity_type="PUBLIC_COMPANY",
        legal_name="Metrics Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()

    session.add(DebtMaturityProfile(
        profile_id=uuid.uuid4(),
        entity_id=entity_id,
        as_of_date=date(2025, 12, 31),
        debt_maturing_1yr=800000000.00,
        pct_debt_maturing_1yr=0.16,
        weighted_avg_maturity_years=5.20,
        weighted_avg_coupon=0.0475,
    ))
    await session.flush()

    response = await client.get(f"/v1/entities/{entity_id}/debt-maturity/metrics")
    assert response.status_code == 200
    data = response.json()
    assert data["pct_debt_maturing_1yr"] == pytest.approx(0.16, abs=0.01)
    assert data["weighted_avg_maturity_years"] == pytest.approx(5.20, abs=0.01)


@pytest.mark.asyncio
async def test_get_debt_maturity_alerts_not_found(client):
    """Test 404 for alerts when no data exists."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/entities/{fake_id}/debt-maturity/alerts")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_debt_maturity_alerts(client, session):
    """Test fetching refinancing risk alerts."""
    entity_id = uuid.uuid4()
    entity = Entity(
        entity_id=entity_id,
        entity_type="PUBLIC_COMPANY",
        legal_name="Alert Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()

    session.add(DebtMaturityProfile(
        profile_id=uuid.uuid4(),
        entity_id=entity_id,
        as_of_date=date(2025, 12, 31),
        debt_maturing_1yr=3000000000.00,
        pct_debt_maturing_1yr=0.60,
        cash_to_1yr_maturities=0.30,
        maturity_wall_alert=True,
        near_term_stress=True,
    ))
    await session.flush()

    response = await client.get(f"/v1/entities/{entity_id}/debt-maturity/alerts")
    assert response.status_code == 200
    data = response.json()
    assert data["maturity_wall_alert"] is True
    assert data["near_term_stress"] is True
