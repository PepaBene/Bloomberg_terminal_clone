"""Tests for Technical Studies API endpoints."""

import uuid
from datetime import date

import pytest

from src.models.security import Security
from src.models.technical_studies import TechnicalStudyValue


@pytest.mark.asyncio
async def test_list_technicals_empty(client):
    """Test listing technicals for a non-existent security."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/securities/{fake_id}/technicals")
    assert response.status_code == 200
    assert response.json()["data"] == []


@pytest.mark.asyncio
async def test_list_technicals(client, session):
    """Test listing technicals for a security."""
    sec_id = uuid.uuid4()
    session.add(Security(
        security_id=sec_id, name="Tech Stock",
        security_type="COMMON_STOCK", asset_class="EQUITY", status="ACTIVE",
    ))
    await session.flush()

    for ind, cat in [("RSI", "MOMENTUM"), ("SMA_50", "TREND"), ("ATR", "VOLATILITY")]:
        session.add(TechnicalStudyValue(
            id=uuid.uuid4(), security_id=sec_id,
            study_date=date(2026, 3, 1),
            indicator=ind, value=50.0, category=cat,
        ))
    await session.flush()

    response = await client.get(f"/v1/securities/{sec_id}/technicals")
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 3


@pytest.mark.asyncio
async def test_list_technicals_filter_indicator(client, session):
    """Test filtering technicals by indicator."""
    sec_id = uuid.uuid4()
    session.add(Security(
        security_id=sec_id, name="Filter Stock",
        security_type="COMMON_STOCK", asset_class="EQUITY", status="ACTIVE",
    ))
    await session.flush()

    session.add(TechnicalStudyValue(
        id=uuid.uuid4(), security_id=sec_id,
        study_date=date(2026, 3, 1), indicator="RSI", value=70.0, category="MOMENTUM",
    ))
    session.add(TechnicalStudyValue(
        id=uuid.uuid4(), security_id=sec_id,
        study_date=date(2026, 3, 1), indicator="SMA_50", value=150.0, category="TREND",
    ))
    await session.flush()

    response = await client.get(
        f"/v1/securities/{sec_id}/technicals", params={"indicator": "RSI"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 1


@pytest.mark.asyncio
async def test_list_technicals_filter_category(client, session):
    """Test filtering technicals by category."""
    sec_id = uuid.uuid4()
    session.add(Security(
        security_id=sec_id, name="Cat Stock",
        security_type="COMMON_STOCK", asset_class="EQUITY", status="ACTIVE",
    ))
    await session.flush()

    session.add(TechnicalStudyValue(
        id=uuid.uuid4(), security_id=sec_id,
        study_date=date(2026, 3, 1), indicator="RSI", value=70.0, category="MOMENTUM",
    ))
    session.add(TechnicalStudyValue(
        id=uuid.uuid4(), security_id=sec_id,
        study_date=date(2026, 3, 1), indicator="SMA_50", value=150.0, category="TREND",
    ))
    await session.flush()

    response = await client.get(
        f"/v1/securities/{sec_id}/technicals", params={"category": "MOMENTUM"}
    )
    assert response.status_code == 200
    assert response.json()["meta"]["total_count"] == 1


@pytest.mark.asyncio
async def test_indicator_history_empty(client):
    """Test getting indicator history for non-existent security."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/securities/{fake_id}/technicals/RSI")
    assert response.status_code == 200
    assert response.json()["data"] == []


@pytest.mark.asyncio
async def test_indicator_history(client, session):
    """Test getting history for a specific indicator."""
    sec_id = uuid.uuid4()
    session.add(Security(
        security_id=sec_id, name="History Stock",
        security_type="COMMON_STOCK", asset_class="EQUITY", status="ACTIVE",
    ))
    await session.flush()

    for d in [date(2026, 3, 1), date(2026, 3, 2), date(2026, 3, 3)]:
        session.add(TechnicalStudyValue(
            id=uuid.uuid4(), security_id=sec_id,
            study_date=d, indicator="RSI", value=55.0, category="MOMENTUM",
        ))
    # Also add a different indicator — should not appear
    session.add(TechnicalStudyValue(
        id=uuid.uuid4(), security_id=sec_id,
        study_date=date(2026, 3, 1), indicator="SMA_50", value=100.0, category="TREND",
    ))
    await session.flush()

    response = await client.get(f"/v1/securities/{sec_id}/technicals/RSI")
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 3
