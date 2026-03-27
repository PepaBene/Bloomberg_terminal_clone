"""API tests for FI Intelligence endpoints (Pillar 3 Phase 3C)."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entity import Entity
from src.models.fi_intelligence import (
    CrossAssetSignal,
    FIMarketBriefing,
    NewIssuanceEvent,
)


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_entity(session: AsyncSession) -> Entity:
    eid = uuid.uuid4()
    entity = Entity(
        entity_id=eid,
        entity_type="PUBLIC_COMPANY",
        legal_name="FI Intel API Test Corp",
        status="ACTIVE",
        source="TEST",
    )
    session.add(entity)
    await session.flush()
    return entity


async def _seed_briefing(
    session: AsyncSession,
    briefing_type: str | None = "CREDIT",
    briefing_date: date | None = None,
    credit_regime: str | None = "NORMAL",
    fallen_angels: dict | None = None,
    rising_stars: dict | None = None,
) -> FIMarketBriefing:
    bid = uuid.uuid4()
    briefing = FIMarketBriefing(
        id=bid,
        briefing_date=briefing_date or date.today(),
        briefing_type=briefing_type,
        ig_oas_bps=Decimal("95.50"),
        hy_oas_bps=Decimal("350.25"),
        ig_oas_1w_change=Decimal("-5.00"),
        hy_oas_1w_change=Decimal("12.00"),
        credit_regime=credit_regime,
        spread_2s10s_bps=Decimal("45.00"),
        spread_3m10y_bps=Decimal("-20.00"),
        curve_shape="INVERTED",
        narrative="Test briefing.",
        fallen_angels_this_period=fallen_angels,
        rising_stars_this_period=rising_stars,
    )
    session.add(briefing)
    await session.flush()
    return briefing


async def _seed_issuance(
    session: AsyncSession,
    entity_id: uuid.UUID | None = None,
    issue_date: date | None = None,
) -> NewIssuanceEvent:
    iid = uuid.uuid4()
    event = NewIssuanceEvent(
        id=iid,
        entity_id=entity_id,
        issue_date=issue_date or date.today(),
        coupon_rate=Decimal("5.2500"),
        maturity_date=date(2035, 7, 20),
        size_mm=Decimal("750.00"),
        spread_at_issue_bps=Decimal("125.00"),
        rating="BBB+",
        oversubscribed=True,
    )
    session.add(event)
    await session.flush()
    return event


async def _seed_signal(
    session: AsyncSession,
    entity_id: uuid.UUID,
    signal_type: str = "DIVERGENCE",
) -> CrossAssetSignal:
    sid = uuid.uuid4()
    signal = CrossAssetSignal(
        id=sid,
        entity_id=entity_id,
        signal_date=date.today(),
        signal_type=signal_type,
        equity_return_pct=Decimal("3.5000"),
        spread_change_bps=Decimal("-10.00"),
        severity="HIGH",
        narrative="Test signal.",
    )
    session.add(signal)
    await session.flush()
    return signal


# ══════════════════════════════════════════════════════════════════════
# Yield Curve Intelligence
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_yield_curve_briefing_empty(client: AsyncClient, session: AsyncSession):
    """GET /v3/fi/yield-curve/briefing returns 200 with empty list."""
    resp = await client.get("/v3/fi/yield-curve/briefing")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_yield_curve_briefing_seeded(client: AsyncClient, session: AsyncSession):
    """GET /v3/fi/yield-curve/briefing returns seeded briefing."""
    await _seed_briefing(session, briefing_type="YIELD_CURVE")
    resp = await client.get("/v3/fi/yield-curve/briefing")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert "curve_shape" in data[0]


@pytest.mark.asyncio
async def test_yield_curve_history(client: AsyncClient, session: AsyncSession):
    """GET /v3/fi/yield-curve/history returns 200."""
    await _seed_briefing(session, briefing_date=date.today() - timedelta(days=5))
    resp = await client.get("/v3/fi/yield-curve/history?days=30")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_yield_curve_auctions(client: AsyncClient, session: AsyncSession):
    """GET /v3/fi/yield-curve/auctions returns 200."""
    await _seed_briefing(session)
    resp = await client.get("/v3/fi/yield-curve/auctions")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_yield_curve_equity_impact(client: AsyncClient, session: AsyncSession):
    """GET /v3/fi/yield-curve/equity-impact returns 200."""
    entity = await _seed_entity(session)
    await _seed_signal(session, entity.entity_id, signal_type="RATE_SENSITIVITY")
    resp = await client.get("/v3/fi/yield-curve/equity-impact")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


# ══════════════════════════════════════════════════════════════════════
# Credit Market Intelligence
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_credit_briefing_empty(client: AsyncClient, session: AsyncSession):
    """GET /v3/fi/credit/briefing returns 200 with empty list."""
    resp = await client.get("/v3/fi/credit/briefing")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_credit_briefing_seeded(client: AsyncClient, session: AsyncSession):
    """GET /v3/fi/credit/briefing returns seeded data."""
    await _seed_briefing(session, briefing_type="CREDIT")
    resp = await client.get("/v3/fi/credit/briefing")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert "ig_oas_bps" in data[0]


@pytest.mark.asyncio
async def test_credit_regime(client: AsyncClient, session: AsyncSession):
    """GET /v3/fi/credit/regime returns regime or null."""
    await _seed_briefing(session, credit_regime="TIGHT")
    resp = await client.get("/v3/fi/credit/regime")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_credit_fallen_angels(client: AsyncClient, session: AsyncSession):
    """GET /v3/fi/credit/fallen-angels returns fallen angel events."""
    fa = {"entity_name": "FallCo", "old_rating": "BBB-", "new_rating": "BB+"}
    await _seed_briefing(session, fallen_angels=fa)
    resp = await client.get("/v3/fi/credit/fallen-angels")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_credit_rising_stars(client: AsyncClient, session: AsyncSession):
    """GET /v3/fi/credit/rising-stars returns rising star events."""
    rs = {"entity_name": "RiseCo", "old_rating": "BB+", "new_rating": "BBB-"}
    await _seed_briefing(session, rising_stars=rs)
    resp = await client.get("/v3/fi/credit/rising-stars")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


# ══════════════════════════════════════════════════════════════════════
# New Issuance
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_issuance_today_empty(client: AsyncClient, session: AsyncSession):
    """GET /v3/fi/issuance/today returns 200 empty."""
    resp = await client.get("/v3/fi/issuance/today")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_issuance_today_seeded(client: AsyncClient, session: AsyncSession):
    """GET /v3/fi/issuance/today returns today's issues."""
    entity = await _seed_entity(session)
    await _seed_issuance(session, entity.entity_id, issue_date=date.today())
    resp = await client.get("/v3/fi/issuance/today")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["rating"] == "BBB+"


@pytest.mark.asyncio
async def test_issuance_this_week(client: AsyncClient, session: AsyncSession):
    """GET /v3/fi/issuance/this-week returns 200."""
    entity = await _seed_entity(session)
    await _seed_issuance(session, entity.entity_id, issue_date=date.today())
    resp = await client.get("/v3/fi/issuance/this-week")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_issuance_pipeline(client: AsyncClient, session: AsyncSession):
    """GET /v3/fi/issuance/pipeline returns future issuances."""
    entity = await _seed_entity(session)
    future_date = date.today() + timedelta(days=30)
    await _seed_issuance(session, entity.entity_id, issue_date=future_date)
    resp = await client.get("/v3/fi/issuance/pipeline")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_issuance_entity_404(client: AsyncClient, session: AsyncSession):
    """GET /v3/fi/issuance/{entity_id} returns 404 for unknown entity."""
    resp = await client.get(f"/v3/fi/issuance/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_issuance_entity_seeded(client: AsyncClient, session: AsyncSession):
    """GET /v3/fi/issuance/{entity_id} returns issuer issuance history."""
    entity = await _seed_entity(session)
    await _seed_issuance(session, entity.entity_id)
    resp = await client.get(f"/v3/fi/issuance/{entity.entity_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


# ══════════════════════════════════════════════════════════════════════
# Cross-Asset Signals
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_cross_asset_signals_empty(client: AsyncClient, session: AsyncSession):
    """GET /v3/fi/cross-asset/signals returns 200 empty."""
    resp = await client.get("/v3/fi/cross-asset/signals")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_cross_asset_signals_seeded(client: AsyncClient, session: AsyncSession):
    """GET /v3/fi/cross-asset/signals returns seeded signals."""
    entity = await _seed_entity(session)
    await _seed_signal(session, entity.entity_id)
    resp = await client.get("/v3/fi/cross-asset/signals")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["severity"] == "HIGH"


@pytest.mark.asyncio
async def test_cross_asset_signals_entity_404(client: AsyncClient, session: AsyncSession):
    """GET /v3/fi/cross-asset/signals/{entity_id} returns 404."""
    resp = await client.get(f"/v3/fi/cross-asset/signals/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cross_asset_signals_entity_seeded(client: AsyncClient, session: AsyncSession):
    """GET /v3/fi/cross-asset/signals/{entity_id} returns entity signals."""
    entity = await _seed_entity(session)
    await _seed_signal(session, entity.entity_id)
    resp = await client.get(f"/v3/fi/cross-asset/signals/{entity.entity_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


# ══════════════════════════════════════════════════════════════════════
# Issuer-Level Intelligence
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_issuer_credit_intelligence_404(client: AsyncClient, session: AsyncSession):
    """GET /v3/fi/issuers/{entity_id}/credit-intelligence returns 404."""
    resp = await client.get(f"/v3/fi/issuers/{uuid.uuid4()}/credit-intelligence")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_issuer_credit_intelligence_seeded(client: AsyncClient, session: AsyncSession):
    """GET /v3/fi/issuers/{entity_id}/credit-intelligence returns profile."""
    entity = await _seed_entity(session)
    await _seed_issuance(session, entity.entity_id)
    resp = await client.get(f"/v3/fi/issuers/{entity.entity_id}/credit-intelligence")
    assert resp.status_code == 200
    data = resp.json()
    assert data["entity_id"] == str(entity.entity_id)
    assert data["outstanding_bonds"] >= 1


@pytest.mark.asyncio
async def test_bond_equity_divergence_404(client: AsyncClient, session: AsyncSession):
    """GET /v3/fi/issuers/{entity_id}/bond-equity-divergence returns 404."""
    resp = await client.get(f"/v3/fi/issuers/{uuid.uuid4()}/bond-equity-divergence")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_bond_equity_divergence_seeded(client: AsyncClient, session: AsyncSession):
    """GET /v3/fi/issuers/{entity_id}/bond-equity-divergence returns signals."""
    entity = await _seed_entity(session)
    await _seed_signal(session, entity.entity_id, signal_type="DIVERGENCE")
    resp = await client.get(f"/v3/fi/issuers/{entity.entity_id}/bond-equity-divergence")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_issuer_rating_narrative_404(client: AsyncClient, session: AsyncSession):
    """GET /v3/fi/issuers/{entity_id}/rating-narrative returns 404."""
    resp = await client.get(f"/v3/fi/issuers/{uuid.uuid4()}/rating-narrative")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_issuer_rating_narrative_seeded(client: AsyncClient, session: AsyncSession):
    """GET /v3/fi/issuers/{entity_id}/rating-narrative returns narrative."""
    entity = await _seed_entity(session)
    await _seed_issuance(session, entity.entity_id)
    resp = await client.get(f"/v3/fi/issuers/{entity.entity_id}/rating-narrative")
    assert resp.status_code == 200
    data = resp.json()
    assert data["entity_id"] == str(entity.entity_id)
    assert "BBB+" in data["rating_narrative"]


@pytest.mark.asyncio
async def test_issuer_debt_outlook_404(client: AsyncClient, session: AsyncSession):
    """GET /v3/fi/issuers/{entity_id}/debt-outlook returns 404."""
    resp = await client.get(f"/v3/fi/issuers/{uuid.uuid4()}/debt-outlook")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_issuer_debt_outlook_seeded(client: AsyncClient, session: AsyncSession):
    """GET /v3/fi/issuers/{entity_id}/debt-outlook returns outlook."""
    entity = await _seed_entity(session)
    await _seed_issuance(session, entity.entity_id)
    resp = await client.get(f"/v3/fi/issuers/{entity.entity_id}/debt-outlook")
    assert resp.status_code == 200
    data = resp.json()
    assert data["entity_id"] == str(entity.entity_id)
    assert data["debt_outlook"] is not None
