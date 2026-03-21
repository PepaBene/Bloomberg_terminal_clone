"""Tests for Money Market Rates API endpoints."""

import uuid
from datetime import date

import pytest

from src.models.fed_meeting import MoneyMarketRate


@pytest.mark.asyncio
async def test_list_money_market_rates_empty(client):
    """Test listing money market rates when DB is empty."""
    response = await client.get("/v1/macro/money-markets")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []
    assert data["meta"]["total_count"] == 0


@pytest.mark.asyncio
async def test_list_money_market_rates(client, session):
    """Test listing money market rates."""
    for rtype in ["SOFR", "FED_FUNDS_EFFECTIVE", "PRIME"]:
        session.add(MoneyMarketRate(
            id=uuid.uuid4(),
            rate_date=date(2026, 3, 19),
            rate_type=rtype,
            rate_value=0.053,
        ))
    await session.flush()

    response = await client.get("/v1/macro/money-markets")
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 3


@pytest.mark.asyncio
async def test_filter_by_rate_type(client, session):
    """Test filtering money market rates by type."""
    session.add(MoneyMarketRate(
        id=uuid.uuid4(),
        rate_date=date(2026, 3, 19),
        rate_type="SOFR",
        rate_value=0.0533,
    ))
    session.add(MoneyMarketRate(
        id=uuid.uuid4(),
        rate_date=date(2026, 3, 19),
        rate_type="PRIME",
        rate_value=0.0850,
    ))
    await session.flush()

    response = await client.get(
        "/v1/macro/money-markets",
        params={"rate_type": "SOFR"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 1
    assert data["data"][0]["rate_type"] == "SOFR"


@pytest.mark.asyncio
async def test_filter_by_date(client, session):
    """Test filtering money market rates by specific date."""
    session.add(MoneyMarketRate(
        id=uuid.uuid4(),
        rate_date=date(2026, 3, 18),
        rate_type="SOFR",
        rate_value=0.0530,
    ))
    session.add(MoneyMarketRate(
        id=uuid.uuid4(),
        rate_date=date(2026, 3, 19),
        rate_type="SOFR",
        rate_value=0.0533,
    ))
    await session.flush()

    response = await client.get(
        "/v1/macro/money-markets",
        params={"rate_date": "2026-03-19"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_count"] == 1
