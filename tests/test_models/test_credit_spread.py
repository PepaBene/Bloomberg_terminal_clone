"""Tests for Credit Spread Index models (D11 FI Supplement P6)."""

import uuid
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.models.credit_spread import CreditSpreadIndex, CreditSpreadPercentile


@pytest.mark.asyncio
async def test_create_credit_spread_index(session):
    """Create a credit spread index entry and verify retrieval."""
    sid = uuid.uuid4()
    entry = CreditSpreadIndex(
        id=sid,
        series_id="BAMLC0A0CM",
        observation_date=date(2026, 3, 1),
        index_name="US Corporate Master OAS",
        rating_category="IG",
        spread_bps=120.5000,
        total_return_index=1500.2500,
        source="FRED",
    )
    session.add(entry)
    await session.flush()

    result = await session.execute(
        select(CreditSpreadIndex).where(CreditSpreadIndex.id == sid)
    )
    fetched = result.scalar_one()
    assert fetched.series_id == "BAMLC0A0CM"
    assert fetched.observation_date == date(2026, 3, 1)
    assert fetched.index_name == "US Corporate Master OAS"
    assert fetched.rating_category == "IG"
    assert float(fetched.spread_bps) == pytest.approx(120.5, abs=0.01)
    assert float(fetched.total_return_index) == pytest.approx(1500.25, abs=0.01)
    assert fetched.source == "FRED"


@pytest.mark.asyncio
async def test_unique_series_date(session):
    """Duplicate (series_id, observation_date) should raise IntegrityError."""
    session.add(CreditSpreadIndex(
        series_id="BAMLC0A0CM",
        observation_date=date(2026, 3, 2),
        rating_category="IG",
        spread_bps=121.0000,
    ))
    await session.flush()

    session.add(CreditSpreadIndex(
        series_id="BAMLC0A0CM",
        observation_date=date(2026, 3, 2),
        rating_category="IG",
        spread_bps=122.0000,
    ))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_create_percentile(session):
    """Create a percentile entry with z-score."""
    pid = uuid.uuid4()
    entry = CreditSpreadPercentile(
        id=pid,
        series_id="BAMLC0A0CM",
        as_of_date=date(2026, 3, 3),
        lookback_years=5,
        percentile_rank=65.50,
        current_oas=130.0000,
        min_oas=80.0000,
        max_oas=350.0000,
        mean_oas=140.0000,
        std_dev=45.0000,
        z_score=-0.2222,
    )
    session.add(entry)
    await session.flush()

    result = await session.execute(
        select(CreditSpreadPercentile).where(CreditSpreadPercentile.id == pid)
    )
    fetched = result.scalar_one()
    assert fetched.series_id == "BAMLC0A0CM"
    assert fetched.lookback_years == 5
    assert float(fetched.percentile_rank) == pytest.approx(65.5, abs=0.1)
    assert float(fetched.z_score) == pytest.approx(-0.2222, abs=0.001)


@pytest.mark.asyncio
async def test_unique_percentile(session):
    """Duplicate (series_id, as_of_date, lookback_years) should raise IntegrityError."""
    session.add(CreditSpreadPercentile(
        series_id="BAMLH0A0HYM2",
        as_of_date=date(2026, 3, 4),
        lookback_years=10,
        percentile_rank=50.00,
    ))
    await session.flush()

    session.add(CreditSpreadPercentile(
        series_id="BAMLH0A0HYM2",
        as_of_date=date(2026, 3, 4),
        lookback_years=10,
        percentile_rank=55.00,
    ))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_multiple_series(session):
    """Create entries for different series and verify both exist."""
    session.add(CreditSpreadIndex(
        series_id="BAMLC0A1CAAA",
        observation_date=date(2026, 3, 5),
        rating_category="AAA",
        spread_bps=50.0000,
    ))
    session.add(CreditSpreadIndex(
        series_id="BAMLH0A3HYC",
        observation_date=date(2026, 3, 5),
        rating_category="CCC",
        spread_bps=900.0000,
    ))
    await session.flush()

    result = await session.execute(
        select(CreditSpreadIndex).where(
            CreditSpreadIndex.observation_date == date(2026, 3, 5)
        )
    )
    items = result.scalars().all()
    series_ids = {i.series_id for i in items}
    assert "BAMLC0A1CAAA" in series_ids
    assert "BAMLH0A3HYC" in series_ids


@pytest.mark.asyncio
async def test_nullable_fields(session):
    """Verify optional fields can be null."""
    sid = uuid.uuid4()
    entry = CreditSpreadIndex(
        id=sid,
        series_id="BAMLC0A0CM",
        observation_date=date(2026, 3, 6),
    )
    session.add(entry)
    await session.flush()

    result = await session.execute(
        select(CreditSpreadIndex).where(CreditSpreadIndex.id == sid)
    )
    fetched = result.scalar_one()
    assert fetched.index_name is None
    assert fetched.rating_category is None
    assert fetched.spread_bps is None
    assert fetched.total_return_index is None
    assert fetched.source is None


@pytest.mark.asyncio
async def test_spread_index_filter(session):
    """Filter by rating_category."""
    session.add(CreditSpreadIndex(
        series_id="BAMLC0A4CBBB",
        observation_date=date(2026, 3, 7),
        rating_category="BBB",
        spread_bps=175.0000,
    ))
    session.add(CreditSpreadIndex(
        series_id="BAMLH0A1HYBB",
        observation_date=date(2026, 3, 7),
        rating_category="BB",
        spread_bps=300.0000,
    ))
    await session.flush()

    result = await session.execute(
        select(CreditSpreadIndex).where(
            CreditSpreadIndex.rating_category == "BBB"
        )
    )
    items = result.scalars().all()
    assert all(i.rating_category == "BBB" for i in items)
    assert any(i.series_id == "BAMLC0A4CBBB" for i in items)


@pytest.mark.asyncio
async def test_percentile_lookback(session):
    """Multiple lookback periods for the same series and date."""
    for lb in [1, 3, 5, 10]:
        session.add(CreditSpreadPercentile(
            series_id="BAMLC0A0CM",
            as_of_date=date(2026, 3, 8),
            lookback_years=lb,
            percentile_rank=50.00 + lb,
        ))
    await session.flush()

    result = await session.execute(
        select(CreditSpreadPercentile).where(
            CreditSpreadPercentile.series_id == "BAMLC0A0CM",
            CreditSpreadPercentile.as_of_date == date(2026, 3, 8),
        )
    )
    items = result.scalars().all()
    assert len(items) == 4
    lookbacks = {i.lookback_years for i in items}
    assert lookbacks == {1, 3, 5, 10}
