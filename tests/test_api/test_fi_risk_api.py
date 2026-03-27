"""API tests for FI Risk Analytics endpoints (Pillar 2 FI Supplement – Part 5)."""

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.corporate_bond import BondEODPrice, CorporateBond
from src.models.entity import Entity


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_entity(session: AsyncSession, entity_id: uuid.UUID) -> Entity:
    entity = Entity(
        entity_id=entity_id,
        entity_type="CORPORATION",
        legal_name="Risk Test Corp",
        short_name="RTEST",
        status="ACTIVE",
        source="TEST",
        confidence_score=0.99,
    )
    session.add(entity)
    await session.commit()
    return entity


async def _seed_bond_with_price(
    session: AsyncSession,
    entity_id: uuid.UUID,
    cusip: str = "RISK00001",
    coupon_rate: float = 5.0,
    maturity_date: date | None = None,
    initial_rating_sp: str | None = "BBB",
    seniority: str = "SENIOR_UNSECURED",
    last_trade_price: float = 98.0,
) -> CorporateBond:
    bond_id = uuid.uuid4()
    mat = maturity_date or date(2035, 6, 15)
    bond = CorporateBond(
        bond_id=bond_id,
        cusip=cusip,
        issuer_entity_id=entity_id,
        issuer_name="Risk Test Corp",
        name=f"Risk Test {coupon_rate}% {mat.year}",
        coupon_rate=coupon_rate,
        coupon_type="FIXED",
        coupon_frequency=2,
        maturity_date=mat,
        seniority=seniority,
        currency="USD",
        is_investment_grade=True,
        initial_rating_sp=initial_rating_sp,
        status="OUTSTANDING",
    )
    session.add(bond)
    await session.flush()

    eod = BondEODPrice(
        bond_id=bond_id,
        price_date=date(2026, 3, 20),
        last_trade_price=last_trade_price,
        yield_to_maturity=0.052,
        g_spread_bps=150,
        has_sufficient_trades=True,
    )
    session.add(eod)
    await session.commit()
    return bond


# ── POST /v2/analytics/bonds/portfolio/risk ──────────────────────────


@pytest.mark.asyncio
async def test_portfolio_risk(client: AsyncClient):
    """Portfolio risk endpoint returns DV01, credit distribution, expected loss."""
    payload = {
        "positions": [
            {
                "cusip": "AAA111",
                "market_value": 1_000_000,
                "modified_duration": 7.0,
                "convexity": 60.0,
                "spread_duration": 6.5,
                "rating_numeric": 6,
                "seniority": "SENIOR_UNSECURED",
                "is_investment_grade": True,
            },
            {
                "cusip": "BBB222",
                "market_value": 500_000,
                "modified_duration": 4.0,
                "convexity": 20.0,
                "spread_duration": 3.8,
                "rating_numeric": 14,
                "seniority": "SENIOR_UNSECURED",
                "is_investment_grade": False,
            },
        ]
    }
    resp = await client.post("/v2/analytics/bonds/portfolio/risk", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["position_count"] == 2
    assert data["total_market_value"] == 1_500_000
    assert data["portfolio_dv01"] > 0
    assert data["expected_loss"] > 0
    assert "credit_distribution" in data
    assert data["credit_distribution"]["ig_pct"] > 0
    assert data["credit_distribution"]["hy_pct"] > 0


# ── POST /v2/analytics/bonds/portfolio/rate-scenario ─────────────────


@pytest.mark.asyncio
async def test_rate_scenario(client: AsyncClient):
    """Rate scenario endpoint returns P&L for given shift."""
    payload = {
        "positions": [
            {
                "cusip": "TEST001",
                "market_value": 1_000_000,
                "modified_duration": 7.0,
                "convexity": 60.0,
            }
        ],
        "rate_shift_bps": 100.0,
    }
    resp = await client.post("/v2/analytics/bonds/portfolio/rate-scenario", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["shift_bps"] == 100.0
    assert data["total_pnl"] < 0  # rates up -> price down
    assert len(data["by_position"]) == 1
    assert data["by_position"][0]["cusip"] == "TEST001"


@pytest.mark.asyncio
async def test_rate_scenario_negative_shift(client: AsyncClient):
    """Negative rate shift should produce positive P&L."""
    payload = {
        "positions": [
            {
                "market_value": 1_000_000,
                "modified_duration": 5.0,
                "convexity": 30.0,
            }
        ],
        "rate_shift_bps": -100.0,
    }
    resp = await client.post("/v2/analytics/bonds/portfolio/rate-scenario", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_pnl"] > 0  # rates down -> price up


# ── POST /v2/analytics/bonds/portfolio/spread-scenario ───────────────


@pytest.mark.asyncio
async def test_spread_scenario_widening(client: AsyncClient):
    """Spread widening should produce negative P&L."""
    payload = {
        "positions": [
            {
                "cusip": "SPR001",
                "market_value": 1_000_000,
                "modified_duration": 5.0,
                "spread_duration": 5.0,
            }
        ],
        "spread_shift_bps": 50.0,
    }
    resp = await client.post("/v2/analytics/bonds/portfolio/spread-scenario", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["shift_bps"] == 50.0
    assert data["total_pnl"] < 0
    assert len(data["by_position"]) == 1


@pytest.mark.asyncio
async def test_spread_scenario_tightening(client: AsyncClient):
    """Spread tightening should produce positive P&L."""
    payload = {
        "positions": [
            {
                "market_value": 1_000_000,
                "modified_duration": 5.0,
                "spread_duration": 5.0,
            }
        ],
        "spread_shift_bps": -50.0,
    }
    resp = await client.post("/v2/analytics/bonds/portfolio/spread-scenario", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_pnl"] > 0


# ── GET /v2/analytics/bonds/{cusip}/risk-metrics ─────────────────────


@pytest.mark.asyncio
async def test_bond_risk_metrics(client: AsyncClient, session: AsyncSession):
    """Risk metrics for a single bond with seeded data."""
    eid = uuid.uuid4()
    await _seed_entity(session, eid)
    await _seed_bond_with_price(
        session, eid,
        cusip="RISKMET01",
        coupon_rate=5.0,
        maturity_date=date(2035, 6, 15),
        initial_rating_sp="BBB",
        seniority="SENIOR_UNSECURED",
        last_trade_price=98.0,
    )

    resp = await client.get("/v2/analytics/bonds/RISKMET01/risk-metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cusip"] == "RISKMET01"
    assert data["dv01"] > 0
    assert data["rate_pnl_100bps"] < 0  # rate rise -> loss
    assert data["spread_pnl_100bps"] < 0  # spread widening -> loss
    assert data["rating_numeric"] == 9  # BBB
    assert data["pd_1y"] is not None
    assert data["lgd"] is not None


@pytest.mark.asyncio
async def test_bond_risk_metrics_not_found(client: AsyncClient):
    """Requesting risk metrics for unknown CUSIP returns 404."""
    resp = await client.get("/v2/analytics/bonds/ZZZZZZZZZ/risk-metrics")
    assert resp.status_code == 404
