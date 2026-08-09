"""API tests for the Layer 3 portfolio advisor tools endpoints
(src/api/routers/portfolio_advisor.py, §5.1)."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.compliance import DriftSnapshot
from src.models.portfolio import Portfolio
from src.models.position import Position


async def _seed_portfolio(session: AsyncSession, **kwargs) -> Portfolio:
    defaults = dict(
        id=uuid.uuid4(), user_id="default_user", portfolio_name="Advisor API Portfolio",
        portfolio_type="REAL", inception_date=date(2025, 1, 1),
        initial_cash=Decimal("100000.00"), current_cash=Decimal("20000.00"),
    )
    defaults.update(kwargs)
    p = Portfolio(**defaults)
    session.add(p)
    await session.flush()
    return p


async def _seed_position(session: AsyncSession, portfolio_id, **kwargs) -> Position:
    defaults = dict(
        id=uuid.uuid4(), portfolio_id=portfolio_id, ticker="AAPL", status="OPEN",
        shares=Decimal("100"), market_value=Decimal("40000.00"), weight=Decimal("0.5"),
        closing_price=Decimal("400.00"),
    )
    defaults.update(kwargs)
    pos = Position(**defaults)
    session.add(pos)
    await session.flush()
    return pos


@pytest.mark.asyncio
async def test_whatif_404_for_unknown_portfolio(client: AsyncClient):
    resp = await client.post(f"/v5/portfolios/{uuid.uuid4()}/whatif", json=[])
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_whatif_returns_position_impacts(client: AsyncClient, session: AsyncSession):
    p = await _seed_portfolio(session)
    await _seed_position(session, p.id)

    resp = await client.post(
        f"/v5/portfolios/{p.id}/whatif",
        json=[{"ticker": "AAPL", "action": "SELL", "shares": 50, "price_per_share": 400.0}],
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["portfolio_id"] == str(p.id)
    assert any(pi["ticker"] == "AAPL" for pi in body["position_impacts"])
    assert "risk_impact" in body
    assert "transaction_cost" in body


@pytest.mark.asyncio
async def test_drift_analysis_404_for_unknown_portfolio(client: AsyncClient):
    resp = await client.post(f"/v5/portfolios/{uuid.uuid4()}/drift-analysis")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_drift_analysis_no_target_set(client: AsyncClient, session: AsyncSession):
    p = await _seed_portfolio(session)
    await _seed_position(session, p.id)

    resp = await client.post(f"/v5/portfolios/{p.id}/drift-analysis")
    assert resp.status_code == 200
    body = resp.json()
    assert body["target_allocation_set"] is False


@pytest.mark.asyncio
async def test_drift_analysis_with_target_set(client: AsyncClient, session: AsyncSession):
    p = await _seed_portfolio(session)
    await _seed_position(session, p.id, ticker="AAPL", weight=Decimal("0.80"), market_value=Decimal("80000"))
    session.add(DriftSnapshot(
        id=uuid.uuid4(), portfolio_id=p.id, snapshot_date=date(2026, 1, 1),
        target_allocation={"AAPL": 50.0},
    ))
    await session.flush()

    resp = await client.post(f"/v5/portfolios/{p.id}/drift-analysis")
    assert resp.status_code == 200
    body = resp.json()
    assert body["target_allocation_set"] is True
    assert body["result"]["rebalance_needed"] is True
    assert len(body["rebalance_trades"]) >= 1


@pytest.mark.asyncio
async def test_trade_list_400_without_rebalance_trades_or_target(client: AsyncClient, session: AsyncSession):
    p = await _seed_portfolio(session)
    await _seed_position(session, p.id)

    resp = await client.post(f"/v5/portfolios/{p.id}/trade-list")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_trade_list_with_explicit_rebalance_trades(client: AsyncClient, session: AsyncSession):
    p = await _seed_portfolio(session)
    await _seed_position(session, p.id, ticker="AAPL", shares=Decimal("100"), closing_price=Decimal("400.00"))

    resp = await client.post(
        f"/v5/portfolios/{p.id}/trade-list",
        json=[{"ticker": "AAPL", "action": "SELL", "weight_delta": 10.0, "notional_amount": 12000.0}],
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["portfolio_id"] == str(p.id)
    assert len(body["orders"]) >= 1


@pytest.mark.asyncio
async def test_trade_list_csv_export(client: AsyncClient, session: AsyncSession):
    p = await _seed_portfolio(session)
    await _seed_position(session, p.id, ticker="AAPL", shares=Decimal("100"), closing_price=Decimal("400.00"))

    resp = await client.post(
        f"/v5/portfolios/{p.id}/trade-list",
        params={"export_format": "csv"},
        json=[{"ticker": "AAPL", "action": "SELL", "weight_delta": 10.0, "notional_amount": 12000.0}],
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "AAPL" in resp.text


@pytest.mark.asyncio
async def test_trade_list_derives_from_drift_when_no_body(client: AsyncClient, session: AsyncSession):
    p = await _seed_portfolio(session)
    await _seed_position(session, p.id, ticker="AAPL", weight=Decimal("0.80"), market_value=Decimal("80000"), closing_price=Decimal("400.00"))
    session.add(DriftSnapshot(
        id=uuid.uuid4(), portfolio_id=p.id, snapshot_date=date(2026, 1, 1),
        target_allocation={"AAPL": 50.0},
    ))
    await session.flush()

    resp = await client.post(f"/v5/portfolios/{p.id}/trade-list")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["orders"]) >= 1
