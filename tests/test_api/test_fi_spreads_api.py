"""Tests for Fixed Income - Credit Spreads API endpoints (D11 FI Supplement P6)."""

import uuid
from datetime import date

import pytest

from src.models.credit_spread import CreditSpreadIndex, CreditSpreadPercentile


async def _seed_spread(session, series_id, obs_date, rating_category, spread_bps, **kwargs):
    """Helper to seed a credit spread index entry."""
    entry = CreditSpreadIndex(
        series_id=series_id,
        observation_date=obs_date,
        rating_category=rating_category,
        spread_bps=spread_bps,
        **kwargs,
    )
    session.add(entry)
    await session.flush()
    return entry


async def _seed_percentile(session, series_id, as_of_date, lookback_years, **kwargs):
    """Helper to seed a credit spread percentile entry."""
    entry = CreditSpreadPercentile(
        series_id=series_id,
        as_of_date=as_of_date,
        lookback_years=lookback_years,
        **kwargs,
    )
    session.add(entry)
    await session.flush()
    return entry


@pytest.mark.asyncio
async def test_list_spreads(client, session):
    """GET /v1/fixed-income/spreads -> 200, returns seeded items."""
    await _seed_spread(
        session, "BAMLC0A0CM", date(2026, 1, 10), "IG", 125.0000,
        index_name="US Corporate Master OAS", source="FRED",
    )
    await _seed_spread(
        session, "BAMLH0A0HYM2", date(2026, 1, 10), "HY", 420.0000,
        index_name="US High Yield Master OAS", source="FRED",
    )

    response = await client.get("/v1/fixed-income/spreads")
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 2
    assert len(data["data"]) == 2


@pytest.mark.asyncio
async def test_ig_spreads(client, session):
    """GET /v1/fixed-income/spreads/ig -> IG category data."""
    await _seed_spread(
        session, "BAMLC0A0CM", date(2026, 1, 11), "IG", 126.0000,
    )
    await _seed_spread(
        session, "BAMLC0A1CAAA", date(2026, 1, 11), "AAA", 55.0000,
    )
    await _seed_spread(
        session, "BAMLC0A4CBBB", date(2026, 1, 11), "BBB", 175.0000,
    )

    response = await client.get("/v1/fixed-income/spreads/ig")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    categories = {item["rating_category"] for item in data}
    # Should only include IG categories
    assert categories <= {"IG", "AAA", "AA", "A", "BBB"}
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_hy_spreads(client, session):
    """GET /v1/fixed-income/spreads/hy -> HY category data."""
    await _seed_spread(
        session, "BAMLH0A0HYM2", date(2026, 1, 12), "HY", 425.0000,
    )
    await _seed_spread(
        session, "BAMLH0A1HYBB", date(2026, 1, 12), "BB", 310.0000,
    )
    await _seed_spread(
        session, "BAMLH0A3HYC", date(2026, 1, 12), "CCC", 950.0000,
    )

    response = await client.get("/v1/fixed-income/spreads/hy")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    categories = {item["rating_category"] for item in data}
    assert categories <= {"HY", "BB", "B", "CCC"}
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_regime(client, session):
    """GET /v1/fixed-income/spreads/regime -> regime info per category."""
    # Seed multiple observations to build history
    for day in range(1, 11):
        await _seed_spread(
            session, "BAMLC0A0CM", date(2026, 2, day), "IG",
            100.0 + day * 5,
        )

    response = await client.get("/v1/fixed-income/spreads/regime")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if data:
        item = data[0]
        assert "regime" in item
        assert "percentile" in item
        assert "current_oas" in item
        assert "category" in item
        assert item["regime"] in {"TIGHT", "NORMAL", "WIDE", "CRISIS"}


@pytest.mark.asyncio
async def test_history(client, session):
    """GET /v1/fixed-income/spreads/history?series_id=BAMLC0A0CM -> time series."""
    await _seed_spread(
        session, "BAMLC0A0CM", date(2026, 3, 1), "IG", 130.0000,
    )
    await _seed_spread(
        session, "BAMLC0A0CM", date(2026, 3, 2), "IG", 131.0000,
    )

    response = await client.get(
        "/v1/fixed-income/spreads/history",
        params={"series_id": "BAMLC0A0CM"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] >= 2
    # Verify all items belong to the requested series
    for item in data["data"]:
        assert item["series_id"] == "BAMLC0A0CM"


@pytest.mark.asyncio
async def test_single_series(client, session):
    """GET /v1/fixed-income/spreads/{series_id} -> single series history."""
    await _seed_spread(
        session, "BAMLC0A2CAA", date(2026, 3, 10), "AA", 70.0000,
    )
    await _seed_spread(
        session, "BAMLC0A2CAA", date(2026, 3, 11), "AA", 72.0000,
    )

    response = await client.get("/v1/fixed-income/spreads/BAMLC0A2CAA")
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 2
    for item in data["data"]:
        assert item["series_id"] == "BAMLC0A2CAA"


@pytest.mark.asyncio
async def test_percentile(client, session):
    """GET /v1/fixed-income/spreads/{series_id}/percentile -> percentile ranks."""
    await _seed_percentile(
        session, "BAMLC0A3CA", date(2026, 3, 15), 5,
        percentile_rank=60.00, current_oas=110.0000,
        min_oas=70.0000, max_oas=250.0000,
        mean_oas=120.0000, std_dev=35.0000, z_score=-0.2857,
    )
    await _seed_percentile(
        session, "BAMLC0A3CA", date(2026, 3, 15), 10,
        percentile_rank=55.00, current_oas=110.0000,
        min_oas=60.0000, max_oas=300.0000,
        mean_oas=130.0000, std_dev=50.0000, z_score=-0.4000,
    )

    response = await client.get("/v1/fixed-income/spreads/BAMLC0A3CA/percentile")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    lookbacks = {item["lookback_years"] for item in data}
    assert lookbacks == {5, 10}
