"""API tests for Portfolio Management endpoints (Pillar 4 Phase 1)."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.portfolio import Portfolio
from src.models.position import Position
from src.models.transaction import Transaction
from src.models.nav_snapshot import NAVSnapshot, CorporateActionQueue


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_portfolio(
    session: AsyncSession,
    portfolio_name: str = "API Test Portfolio",
    **kwargs,
) -> Portfolio:
    defaults = {
        "id": uuid.uuid4(),
        "user_id": "default_user",
        "portfolio_name": portfolio_name,
        "portfolio_type": "REAL",
        "inception_date": date(2025, 1, 1),
        "initial_cash": Decimal("100000.00"),
        "current_cash": Decimal("100000.00"),
    }
    defaults.update(kwargs)
    p = Portfolio(**defaults)
    session.add(p)
    await session.flush()
    return p


async def _seed_position(
    session: AsyncSession,
    portfolio_id: uuid.UUID,
    ticker: str = "AAPL",
    **kwargs,
) -> Position:
    defaults = {
        "id": uuid.uuid4(),
        "portfolio_id": portfolio_id,
        "ticker": ticker,
        "status": "OPEN",
        "shares": Decimal("100.000000"),
        "cost_basis_per_share": Decimal("150.000000"),
        "cost_basis_total": Decimal("15000.00"),
        "first_acquisition_date": date(2025, 3, 1),
    }
    defaults.update(kwargs)
    pos = Position(**defaults)
    session.add(pos)
    await session.flush()
    return pos


async def _seed_transaction(
    session: AsyncSession,
    portfolio_id: uuid.UUID,
    **kwargs,
) -> Transaction:
    defaults = {
        "id": uuid.uuid4(),
        "portfolio_id": portfolio_id,
        "ticker": "AAPL",
        "transaction_type": "BUY",
        "transaction_date": date(2025, 3, 15),
        "shares": Decimal("100.000000"),
        "price_per_share": Decimal("150.000000"),
        "gross_amount": Decimal("15000.00"),
        "commission": Decimal("9.99"),
        "net_amount": Decimal("15009.99"),
        "cash_impact": Decimal("-15009.99"),
    }
    defaults.update(kwargs)
    txn = Transaction(**defaults)
    session.add(txn)
    await session.flush()
    return txn


async def _seed_nav_snapshot(
    session: AsyncSession,
    portfolio_id: uuid.UUID,
    snapshot_date: date = date(2025, 6, 1),
    **kwargs,
) -> NAVSnapshot:
    defaults = {
        "id": uuid.uuid4(),
        "portfolio_id": portfolio_id,
        "snapshot_date": snapshot_date,
        "nav": Decimal("105000.00"),
        "market_value": Decimal("80000.00"),
        "cash_balance": Decimal("25000.00"),
        "daily_return": Decimal("0.00150000"),
        "cumulative_return": Decimal("0.05000000"),
    }
    defaults.update(kwargs)
    snap = NAVSnapshot(**defaults)
    session.add(snap)
    await session.flush()
    return snap


async def _seed_corporate_action(
    session: AsyncSession,
    portfolio_id: uuid.UUID,
    **kwargs,
) -> CorporateActionQueue:
    defaults = {
        "id": uuid.uuid4(),
        "portfolio_id": portfolio_id,
        "action_type": "DIVIDEND",
        "ticker": "AAPL",
        "status": "PENDING",
    }
    defaults.update(kwargs)
    ca = CorporateActionQueue(**defaults)
    session.add(ca)
    await session.flush()
    return ca


# ══════════════════════════════════════════════════════════════════════
# Portfolio CRUD
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_portfolio(client: AsyncClient, session: AsyncSession):
    """POST /v4/portfolios creates a portfolio."""
    resp = await client.post("/v4/portfolios", json={
        "portfolio_name": "My Growth Portfolio",
        "portfolio_type": "REAL",
        "inception_date": "2025-01-01",
        "initial_cash": 100000.00,
        "benchmark_id": "SPX",
        "tags": {"strategy": "growth"},
        "notes": "Test portfolio",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["portfolio_name"] == "My Growth Portfolio"
    assert data["status"] == "ACTIVE"
    assert data["initial_cash"] == 100000.00


@pytest.mark.asyncio
async def test_create_portfolio_minimal(client: AsyncClient, session: AsyncSession):
    """POST /v4/portfolios with minimal fields."""
    resp = await client.post("/v4/portfolios", json={
        "portfolio_name": "Minimal Portfolio",
        "inception_date": "2025-06-01",
        "initial_cash": 50000.00,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["portfolio_name"] == "Minimal Portfolio"
    assert data["portfolio_type"] == "REAL"


@pytest.mark.asyncio
async def test_create_portfolio_duplicate_name_409(client: AsyncClient, session: AsyncSession):
    """POST /v4/portfolios duplicate name returns 409."""
    await _seed_portfolio(session, portfolio_name="Dup Name API")
    resp = await client.post("/v4/portfolios", json={
        "portfolio_name": "Dup Name API",
        "inception_date": "2025-01-01",
        "initial_cash": 10000.00,
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_portfolios_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios returns empty list."""
    resp = await client.get("/v4/portfolios")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_list_portfolios_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios returns seeded portfolios."""
    await _seed_portfolio(session, portfolio_name="List A")
    await _seed_portfolio(session, portfolio_name="List B")
    resp = await client.get("/v4/portfolios")
    assert resp.status_code == 200
    data = resp.json()
    names = [p["portfolio_name"] for p in data]
    assert "List A" in names
    assert "List B" in names


@pytest.mark.asyncio
async def test_get_portfolio_found(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id} returns portfolio."""
    p = await _seed_portfolio(session, portfolio_name="Get Me")
    resp = await client.get(f"/v4/portfolios/{p.id}")
    assert resp.status_code == 200
    assert resp.json()["portfolio_name"] == "Get Me"


@pytest.mark.asyncio
async def test_get_portfolio_not_found(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id} returns 404."""
    resp = await client.get(f"/v4/portfolios/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_portfolio_name(client: AsyncClient, session: AsyncSession):
    """PUT /v4/portfolios/{id} updates name."""
    p = await _seed_portfolio(session, portfolio_name="Old Name")
    resp = await client.put(f"/v4/portfolios/{p.id}", json={
        "portfolio_name": "New Name",
    })
    assert resp.status_code == 200
    assert resp.json()["portfolio_name"] == "New Name"


@pytest.mark.asyncio
async def test_update_portfolio_status(client: AsyncClient, session: AsyncSession):
    """PUT /v4/portfolios/{id} updates status."""
    p = await _seed_portfolio(session, portfolio_name="Status Update")
    resp = await client.put(f"/v4/portfolios/{p.id}", json={
        "status": "PAUSED",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "PAUSED"


@pytest.mark.asyncio
async def test_delete_portfolio_soft(client: AsyncClient, session: AsyncSession):
    """DELETE /v4/portfolios/{id} sets status to ARCHIVED."""
    p = await _seed_portfolio(session, portfolio_name="Delete Me")
    resp = await client.delete(f"/v4/portfolios/{p.id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ARCHIVED"


@pytest.mark.asyncio
async def test_clone_portfolio(client: AsyncClient, session: AsyncSession):
    """POST /v4/portfolios/{id}/clone clones portfolio."""
    p = await _seed_portfolio(session, portfolio_name="Original")
    await _seed_position(session, p.id, ticker="AAPL")
    resp = await client.post(f"/v4/portfolios/{p.id}/clone")
    assert resp.status_code == 201
    data = resp.json()
    assert "Clone" in data["portfolio_name"]


# ══════════════════════════════════════════════════════════════════════
# Positions
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_list_positions_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/positions returns empty list."""
    p = await _seed_portfolio(session, portfolio_name="Empty Positions")
    resp = await client.get(f"/v4/portfolios/{p.id}/positions")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_add_position(client: AsyncClient, session: AsyncSession):
    """POST /v4/portfolios/{id}/positions adds a position."""
    p = await _seed_portfolio(session, portfolio_name="Add Pos")
    resp = await client.post(f"/v4/portfolios/{p.id}/positions", json={
        "ticker": "MSFT",
        "shares": 50,
        "cost_basis_per_share": 300.00,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["ticker"] == "MSFT"
    assert data["shares"] == 50.0
    assert data["status"] == "OPEN"


@pytest.mark.asyncio
async def test_update_position(client: AsyncClient, session: AsyncSession):
    """PUT /v4/portfolios/{id}/positions/{pos_id} updates position."""
    p = await _seed_portfolio(session, portfolio_name="Update Pos")
    pos = await _seed_position(session, p.id, ticker="GOOG")
    resp = await client.put(
        f"/v4/portfolios/{p.id}/positions/{pos.id}",
        json={"shares": 200, "notes": "Doubled down"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["shares"] == 200.0
    assert data["notes"] == "Doubled down"


@pytest.mark.asyncio
async def test_delete_position(client: AsyncClient, session: AsyncSession):
    """DELETE /v4/portfolios/{id}/positions/{pos_id} closes position."""
    p = await _seed_portfolio(session, portfolio_name="Del Pos")
    pos = await _seed_position(session, p.id, ticker="TSLA")
    resp = await client.delete(f"/v4/portfolios/{p.id}/positions/{pos.id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "CLOSED"


# ══════════════════════════════════════════════════════════════════════
# Transactions
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_buy_transaction(client: AsyncClient, session: AsyncSession):
    """POST /v4/portfolios/{id}/transactions records a BUY."""
    p = await _seed_portfolio(session, portfolio_name="Buy Txn")
    resp = await client.post(f"/v4/portfolios/{p.id}/transactions", json={
        "ticker": "AAPL",
        "transaction_type": "BUY",
        "transaction_date": "2025-03-15",
        "shares": 10,
        "price_per_share": 150.00,
        "commission": 9.99,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["transaction_type"] == "BUY"
    assert data["ticker"] == "AAPL"
    assert data["cash_impact"] < 0


@pytest.mark.asyncio
async def test_create_sell_transaction(client: AsyncClient, session: AsyncSession):
    """POST /v4/portfolios/{id}/transactions records a SELL."""
    p = await _seed_portfolio(session, portfolio_name="Sell Txn")
    await _seed_position(session, p.id, ticker="MSFT", shares=Decimal("100.000000"))
    resp = await client.post(f"/v4/portfolios/{p.id}/transactions", json={
        "ticker": "MSFT",
        "transaction_type": "SELL",
        "transaction_date": "2025-04-01",
        "shares": 50,
        "price_per_share": 300.00,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["transaction_type"] == "SELL"
    assert data["cash_impact"] > 0


@pytest.mark.asyncio
async def test_sell_insufficient_shares_400(client: AsyncClient, session: AsyncSession):
    """POST /v4/portfolios/{id}/transactions SELL too many returns 400."""
    p = await _seed_portfolio(session, portfolio_name="Oversell")
    await _seed_position(session, p.id, ticker="NFLX", shares=Decimal("10.000000"))
    resp = await client.post(f"/v4/portfolios/{p.id}/transactions", json={
        "ticker": "NFLX",
        "transaction_type": "SELL",
        "transaction_date": "2025-04-01",
        "shares": 100,
        "price_per_share": 500.00,
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_transactions(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/transactions returns history."""
    p = await _seed_portfolio(session, portfolio_name="Txn History")
    await _seed_transaction(session, p.id, transaction_type="BUY")
    resp = await client.get(f"/v4/portfolios/{p.id}/transactions")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_list_transactions_filtered(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/transactions?type=BUY filters by type."""
    p = await _seed_portfolio(session, portfolio_name="Filtered Txns")
    await _seed_transaction(session, p.id, transaction_type="BUY")
    await _seed_transaction(session, p.id, transaction_type="SELL",
                            cash_impact=Decimal("14990.01"),
                            net_amount=Decimal("14990.01"))
    resp = await client.get(f"/v4/portfolios/{p.id}/transactions?type=BUY")
    assert resp.status_code == 200
    data = resp.json()
    for txn in data:
        assert txn["transaction_type"] == "BUY"


# ══════════════════════════════════════════════════════════════════════
# NAV
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_nav_current(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/nav returns NAV summary."""
    p = await _seed_portfolio(session, portfolio_name="NAV Current")
    resp = await client.get(f"/v4/portfolios/{p.id}/nav")
    assert resp.status_code == 200
    data = resp.json()
    assert "nav" in data
    assert data["cash_balance"] == 100000.00
    assert data["position_count"] == 0


@pytest.mark.asyncio
async def test_get_nav_history(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/nav/history returns history."""
    p = await _seed_portfolio(session, portfolio_name="NAV History")
    await _seed_nav_snapshot(session, p.id, snapshot_date=date(2025, 6, 1))
    await _seed_nav_snapshot(session, p.id, snapshot_date=date(2025, 6, 2))
    resp = await client.get(f"/v4/portfolios/{p.id}/nav/history")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["history"]) >= 2


@pytest.mark.asyncio
async def test_get_nav_snapshot_by_date(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/nav/snapshot?date=... returns snapshot."""
    p = await _seed_portfolio(session, portfolio_name="NAV Snapshot")
    await _seed_nav_snapshot(session, p.id, snapshot_date=date(2025, 7, 1))
    resp = await client.get(f"/v4/portfolios/{p.id}/nav/snapshot?date=2025-07-01")
    assert resp.status_code == 200
    data = resp.json()
    assert data["snapshot_date"] == "2025-07-01"


@pytest.mark.asyncio
async def test_get_nav_snapshot_none(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/nav/snapshot returns null when no data."""
    p = await _seed_portfolio(session, portfolio_name="NAV No Snap")
    resp = await client.get(f"/v4/portfolios/{p.id}/nav/snapshot")
    assert resp.status_code == 200
    assert resp.json() is None


# ══════════════════════════════════════════════════════════════════════
# Corporate Actions
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_list_corporate_actions_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/corporate-actions returns empty list."""
    p = await _seed_portfolio(session, portfolio_name="Corp Actions Empty")
    resp = await client.get(f"/v4/portfolios/{p.id}/corporate-actions")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_apply_corporate_action(client: AsyncClient, session: AsyncSession):
    """POST /v4/portfolios/{id}/corporate-actions/{id}/apply applies action."""
    p = await _seed_portfolio(session, portfolio_name="Apply CA")
    ca = await _seed_corporate_action(session, p.id)
    resp = await client.post(f"/v4/portfolios/{p.id}/corporate-actions/{ca.id}/apply")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "APPLIED"
    assert data["applied_at"] is not None


@pytest.mark.asyncio
async def test_dismiss_corporate_action(client: AsyncClient, session: AsyncSession):
    """POST /v4/portfolios/{id}/corporate-actions/{id}/dismiss dismisses action."""
    p = await _seed_portfolio(session, portfolio_name="Dismiss CA")
    ca = await _seed_corporate_action(session, p.id)
    resp = await client.post(f"/v4/portfolios/{p.id}/corporate-actions/{ca.id}/dismiss")
    assert resp.status_code == 200
    assert resp.json()["status"] == "DISMISSED"


# ══════════════════════════════════════════════════════════════════════
# Upload
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_upload_preview(client: AsyncClient, session: AsyncSession):
    """POST /v4/portfolios/upload/preview returns preview."""
    csv_content = "ticker,shares,cost_basis\nAAPL,100,150.00\nMSFT,50,300.00\n"
    resp = await client.post(
        "/v4/portfolios/upload/preview",
        json={"csv_content": csv_content},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "total_rows" in data
    assert data["total_rows"] == 2
    assert "preview_positions" in data


@pytest.mark.asyncio
async def test_upload_commit(client: AsyncClient, session: AsyncSession):
    """POST /v4/portfolios/upload/commit returns commit response."""
    csv_content = "ticker,shares,cost_basis\nAAPL,100,150.00\nMSFT,50,300.00\n"
    resp = await client.post(
        "/v4/portfolios/upload/commit",
        json={"csv_content": csv_content, "portfolio_name": "Upload Test Portfolio"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "portfolio_id" in data
    assert data["status"] == "COMMITTED"
    assert data["positions_created"] == 2
