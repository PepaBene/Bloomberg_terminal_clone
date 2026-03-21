"""Tests for technical study value models."""

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from src.models.security import Security
from src.models.technical_studies import TechnicalStudyValue


@pytest.mark.asyncio
async def test_create_technical_study_value(session):
    """Test creating a technical study value."""
    sec_id = uuid.uuid4()
    session.add(Security(
        security_id=sec_id, name="AAPL", security_type="COMMON_STOCK", asset_class="EQUITY", status="ACTIVE",
    ))
    await session.flush()

    val_id = uuid.uuid4()
    session.add(TechnicalStudyValue(
        id=val_id, security_id=sec_id,
        study_date=date(2026, 3, 1),
        indicator="RSI", value=65.4321,
        category="MOMENTUM",
    ))
    await session.flush()

    result = await session.execute(
        select(TechnicalStudyValue).where(TechnicalStudyValue.id == val_id)
    )
    fetched = result.scalar_one()
    assert fetched.indicator == "RSI"
    assert float(fetched.value) == pytest.approx(65.4321, abs=0.001)


@pytest.mark.asyncio
async def test_list_by_security(session):
    """Test querying study values by security."""
    sec_id = uuid.uuid4()
    session.add(Security(
        security_id=sec_id, name="MSFT", security_type="COMMON_STOCK", asset_class="EQUITY", status="ACTIVE",
    ))
    await session.flush()

    for ind, cat in [("RSI", "MOMENTUM"), ("SMA_50", "TREND"), ("ATR", "VOLATILITY")]:
        session.add(TechnicalStudyValue(
            id=uuid.uuid4(), security_id=sec_id,
            study_date=date(2026, 3, 1),
            indicator=ind, value=50.0, category=cat,
        ))
    await session.flush()

    result = await session.execute(
        select(TechnicalStudyValue).where(TechnicalStudyValue.security_id == sec_id)
    )
    vals = result.scalars().all()
    assert len(vals) == 3


@pytest.mark.asyncio
async def test_filter_by_category(session):
    """Test filtering study values by category."""
    sec_id = uuid.uuid4()
    session.add(Security(
        security_id=sec_id, name="GOOG", security_type="COMMON_STOCK", asset_class="EQUITY", status="ACTIVE",
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

    result = await session.execute(
        select(TechnicalStudyValue)
        .where(TechnicalStudyValue.security_id == sec_id)
        .where(TechnicalStudyValue.category == "MOMENTUM")
    )
    vals = result.scalars().all()
    assert len(vals) == 1
    assert vals[0].indicator == "RSI"


@pytest.mark.asyncio
async def test_multiple_dates(session):
    """Test values across multiple dates."""
    sec_id = uuid.uuid4()
    session.add(Security(
        security_id=sec_id, name="TSLA", security_type="COMMON_STOCK", asset_class="EQUITY", status="ACTIVE",
    ))
    await session.flush()

    for d in [date(2026, 3, 1), date(2026, 3, 2), date(2026, 3, 3)]:
        session.add(TechnicalStudyValue(
            id=uuid.uuid4(), security_id=sec_id,
            study_date=d, indicator="RSI", value=55.0, category="MOMENTUM",
        ))
    await session.flush()

    result = await session.execute(
        select(TechnicalStudyValue)
        .where(TechnicalStudyValue.security_id == sec_id)
        .where(TechnicalStudyValue.indicator == "RSI")
    )
    vals = result.scalars().all()
    assert len(vals) == 3
