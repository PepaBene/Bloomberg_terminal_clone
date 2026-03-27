"""Tests for Fixed Income - Treasuries API endpoints (D11 FI Supplement P2)."""

import uuid
from datetime import date, timedelta

import pytest

from src.models.treasury import TreasurySecurity


async def _seed_treasury(session, cusip, treasury_type, coupon_rate, maturity_date, issue_date, **kwargs):
    """Helper to seed a treasury security."""
    t = TreasurySecurity(
        cusip=cusip,
        treasury_type=treasury_type,
        coupon_rate=coupon_rate,
        maturity_date=maturity_date,
        issue_date=issue_date,
        **kwargs,
    )
    session.add(t)
    await session.flush()
    return t


@pytest.mark.asyncio
async def test_list_treasuries(client, session):
    """Seed 2 treasuries, GET /v1/fixed-income/treasuries -> 200, items count=2."""
    await _seed_treasury(
        session, "91282CFA1", "NOTE", 4.0,
        date(2034, 1, 15), date(2024, 1, 15),
    )
    await _seed_treasury(
        session, "91282CFB2", "NOTE", 4.5,
        date(2034, 7, 15), date(2024, 7, 15),
    )

    response = await client.get("/v1/fixed-income/treasuries")
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 2
    assert len(data["data"]) == 2


@pytest.mark.asyncio
async def test_list_filter_by_type(client, session):
    """Seed NOTE+BILL, filter ?type=NOTE -> 1 result."""
    await _seed_treasury(
        session, "91282CGA1", "NOTE", 3.5,
        date(2033, 2, 15), date(2023, 2, 15),
    )
    await _seed_treasury(
        session, "91282CGB2", "BILL", 0,
        date(2026, 5, 15), date(2026, 2, 15),
    )

    response = await client.get("/v1/fixed-income/treasuries", params={"type": "NOTE"})
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 1
    assert data["data"][0]["treasury_type"] == "NOTE"


@pytest.mark.asyncio
async def test_get_by_cusip(client, session):
    """Seed 1, GET /{cusip} -> 200, verify fields."""
    t = await _seed_treasury(
        session, "91282CHA1", "NOTE", 4.25,
        date(2035, 3, 15), date(2025, 3, 15),
        coupon_frequency=2,
    )

    response = await client.get(f"/v1/fixed-income/treasuries/{t.cusip}")
    assert response.status_code == 200
    data = response.json()
    assert data["cusip"] == "91282CHA1"
    assert data["treasury_type"] == "NOTE"
    assert float(data["coupon_rate"]) == 4.25


@pytest.mark.asyncio
async def test_get_by_cusip_404(client):
    """GET /nonexistent -> 404."""
    response = await client.get("/v1/fixed-income/treasuries/XXXXXXXXX")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_on_the_run(client, session):
    """Seed 2 notes with different issue_dates, GET /on-the-run -> returns latest."""
    today = date.today()
    mat = today + timedelta(days=int(10 * 365.25))

    await _seed_treasury(
        session, "91282CIA1", "NOTE", 4.0,
        mat, today - timedelta(days=180),
    )
    await _seed_treasury(
        session, "91282CIB2", "NOTE", 4.25,
        mat - timedelta(days=30), today - timedelta(days=30),
    )

    response = await client.get("/v1/fixed-income/treasuries/on-the-run")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # The newer one should be on-the-run for its tenor bucket
    if data:
        cusips = [item["cusip"] for item in data]
        assert "91282CIB2" in cusips


@pytest.mark.asyncio
async def test_auction_results(client, session):
    """Seed treasury with auction data, GET /auction-results -> has auction fields."""
    await _seed_treasury(
        session, "91282CJA1", "NOTE", 4.5,
        date(2035, 4, 15), date(2025, 4, 15),
        auction_date=date(2025, 4, 10),
        auction_high_yield=4.520000,
        auction_price=99.850000,
        auction_bid_to_cover=2.450,
    )

    response = await client.get("/v1/fixed-income/treasuries/auction-results")
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] >= 1
    item = data["data"][0]
    assert item["auction_date"] is not None
    assert item["auction_high_yield"] is not None


@pytest.mark.asyncio
async def test_analytics(client, session):
    """Seed 1, GET /{cusip}/analytics?price=100 -> has ytm, duration, convexity."""
    await _seed_treasury(
        session, "91282CKA1", "NOTE", 5.0,
        date.today() + timedelta(days=int(10 * 365.25)),
        date.today() - timedelta(days=30),
        coupon_frequency=2,
    )

    response = await client.get(
        "/v1/fixed-income/treasuries/91282CKA1/analytics",
        params={"price": 100.0},
    )
    assert response.status_code == 200
    data = response.json()
    assert "ytm" in data
    assert "modified_duration" in data
    assert "macaulay_duration" in data
    assert "convexity" in data
    # At par, YTM should be close to coupon
    assert abs(data["ytm"] - 5.0) < 0.5


@pytest.mark.asyncio
async def test_list_filter_outstanding(client, session):
    """Seed outstanding + matured, filter -> only outstanding returned."""
    await _seed_treasury(
        session, "91282CLA1", "NOTE", 3.0,
        date(2032, 5, 15), date(2022, 5, 15),
        is_outstanding=True,
    )
    await _seed_treasury(
        session, "91282CLB2", "NOTE", 2.5,
        date(2022, 5, 15), date(2012, 5, 15),
        is_outstanding=False,
    )

    # Default is_outstanding=True
    response = await client.get("/v1/fixed-income/treasuries")
    assert response.status_code == 200
    data = response.json()
    cusips = [item["cusip"] for item in data["data"]]
    assert "91282CLA1" in cusips
    assert "91282CLB2" not in cusips


@pytest.mark.asyncio
async def test_pagination(client, session):
    """Seed 3, GET ?limit=2 -> 2 items returned with pagination."""
    for i, cusip in enumerate(["91282CMA1", "91282CMB2", "91282CMC3"]):
        await _seed_treasury(
            session, cusip, "NOTE", 4.0 + i * 0.25,
            date(2034, 6 + i, 15), date(2024, 6 + i, 15),
        )

    response = await client.get(
        "/v1/fixed-income/treasuries",
        params={"page_size": 2},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 2
    assert data["meta"]["total_count"] == 3
    assert data["meta"]["total_pages"] == 2
