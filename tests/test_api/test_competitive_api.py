"""API tests for Competitive Intelligence endpoints (Pillar 3 Phase 3A)."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entity import Entity
from src.models.competitive_intelligence import (
    CompetitiveLandscape,
    ConcentrationRiskAssessment,
    MoatAssessment,
    MoatHistory,
)


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_entity(session, entity_id=None):
    eid = entity_id or uuid.uuid4()
    entity = Entity(
        entity_id=eid,
        entity_type="PUBLIC_COMPANY",
        legal_name="Competitive API Test Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()
    return entity


async def _seed_moat(session, entity_id):
    mid = uuid.uuid4()
    moat = MoatAssessment(
        id=mid,
        entity_id=entity_id,
        as_of_date=date(2025, 6, 30),
        moat_width="WIDE",
        moat_stability="STABLE",
        moat_score=Decimal("88.00"),
        roic_above_wacc_years=12,
        dominant_moat_source="NETWORK_EFFECTS",
        moat_evidence={"key": "Platform lock-in"},
        cost_advantage_score=Decimal("70.00"),
        network_effects_score=Decimal("90.00"),
        switching_costs_score=Decimal("85.00"),
        intangible_assets_score=Decimal("75.00"),
        efficient_scale_score=Decimal("60.00"),
    )
    session.add(moat)
    await session.flush()
    return moat


async def _seed_moat_history(session, entity_id):
    entries = []
    for yr in [2022, 2023, 2024]:
        hid = uuid.uuid4()
        entry = MoatHistory(
            id=hid,
            entity_id=entity_id,
            period_end_date=date(yr, 12, 31),
            moat_width="WIDE",
            moat_score=Decimal(f"{80 + yr - 2022}.00"),
            roic=Decimal("0.2200"),
            wacc=Decimal("0.0900"),
            roic_wacc_spread=Decimal("0.1300"),
        )
        session.add(entry)
        entries.append(entry)
    await session.flush()
    return entries


async def _seed_concentration(session, entity_id):
    cid = uuid.uuid4()
    conc = ConcentrationRiskAssessment(
        id=cid,
        entity_id=entity_id,
        as_of_date=date(2025, 6, 30),
        customer_top1_pct=Decimal("0.2500"),
        customer_top5_pct=Decimal("0.5500"),
        customer_top10_pct=Decimal("0.7000"),
        customer_concentration_risk="HIGH",
        customer_details={"top_customer": "US Government"},
        supplier_single_source_count=3,
        supplier_critical_count=5,
        supplier_geographic_concentration={"Taiwan": 0.40},
        supplier_concentration_risk="MODERATE",
        supplier_details={"critical": ["TSMC"]},
        geographic_revenue_breakdown={"US": 0.55, "Europe": 0.25},
        geographic_top1_pct=Decimal("0.5500"),
        geographic_hhi=Decimal("3850.00"),
        fx_exposure_score=Decimal("45.00"),
        geographic_concentration_risk="MODERATE",
        overall_concentration_risk="HIGH",
        overall_risk_score=Decimal("72.00"),
    )
    session.add(conc)
    await session.flush()
    return conc


async def _seed_landscape(session, entity_id):
    lid = uuid.uuid4()
    landscape = CompetitiveLandscape(
        id=lid,
        entity_id=entity_id,
        gics_code="45102010",
        as_of_date=date(2025, 6, 30),
        peer_group=[
            {"entity_id": str(uuid.uuid4()), "entity_name": "Peer A", "market_share_est_pct": 0.15},
        ],
        market_share_est_pct=Decimal("0.2500"),
        market_share_rank=1,
        revenue_growth_vs_peers=Decimal("0.0500"),
        margin_vs_peers=Decimal("0.0800"),
        roic_vs_peers=Decimal("0.0600"),
        share_gainer=True,
        value_chain_position="PLATFORM",
        competitive_advantages=["brand_loyalty", "scale"],
        competitive_threats=["disruption"],
    )
    session.add(landscape)
    await session.flush()
    return landscape


# ── Moat endpoint tests ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_moat_entity_not_found(client: AsyncClient, session: AsyncSession):
    """GET /v3/competitive/{entity_id}/moat returns 404 for missing entity."""
    resp = await client.get(f"/v3/competitive/{uuid.uuid4()}/moat")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_moat_no_assessment(client: AsyncClient, session: AsyncSession):
    """GET /v3/competitive/{entity_id}/moat returns 404 when entity exists but no moat."""
    entity = await _seed_entity(session)
    resp = await client.get(f"/v3/competitive/{entity.entity_id}/moat")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_moat_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v3/competitive/{entity_id}/moat returns moat assessment."""
    entity = await _seed_entity(session)
    await _seed_moat(session, entity.entity_id)
    resp = await client.get(f"/v3/competitive/{entity.entity_id}/moat")
    assert resp.status_code == 200
    data = resp.json()
    assert data["moat_width"] == "WIDE"
    assert data["moat_stability"] == "STABLE"
    assert data["dominant_moat_source"] == "NETWORK_EFFECTS"


# ── Moat evidence endpoint ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_moat_evidence_not_found(client: AsyncClient, session: AsyncSession):
    """GET /v3/competitive/{entity_id}/moat/evidence returns 404 for missing entity."""
    resp = await client.get(f"/v3/competitive/{uuid.uuid4()}/moat/evidence")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_moat_evidence_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v3/competitive/{entity_id}/moat/evidence returns evidence details."""
    entity = await _seed_entity(session)
    await _seed_moat(session, entity.entity_id)
    resp = await client.get(f"/v3/competitive/{entity.entity_id}/moat/evidence")
    assert resp.status_code == 200
    data = resp.json()
    assert data["moat_width"] == "WIDE"
    assert "moat_evidence" in data
    assert data["network_effects_score"] is not None


# ── Moat history endpoint ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_moat_history_not_found(client: AsyncClient, session: AsyncSession):
    """GET /v3/competitive/{entity_id}/moat/history returns 404 for missing entity."""
    resp = await client.get(f"/v3/competitive/{uuid.uuid4()}/moat/history")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_moat_history_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v3/competitive/{entity_id}/moat/history returns history list."""
    entity = await _seed_entity(session)
    await _seed_moat_history(session, entity.entity_id)
    resp = await client.get(f"/v3/competitive/{entity.entity_id}/moat/history")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["history"]) == 3


# ── Concentration endpoint ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_concentration_not_found(client: AsyncClient, session: AsyncSession):
    """GET /v3/competitive/{entity_id}/concentration returns 404 for missing entity."""
    resp = await client.get(f"/v3/competitive/{uuid.uuid4()}/concentration")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_concentration_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v3/competitive/{entity_id}/concentration returns concentration data."""
    entity = await _seed_entity(session)
    await _seed_concentration(session, entity.entity_id)
    resp = await client.get(f"/v3/competitive/{entity.entity_id}/concentration")
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall_concentration_risk"] == "HIGH"
    assert data["customer_concentration_risk"] == "HIGH"


# ── Concentration sub-endpoints ──────────────────────────────────────


@pytest.mark.asyncio
async def test_get_customer_concentration(client: AsyncClient, session: AsyncSession):
    """GET /v3/competitive/{entity_id}/concentration/customers returns customer data."""
    entity = await _seed_entity(session)
    await _seed_concentration(session, entity.entity_id)
    resp = await client.get(f"/v3/competitive/{entity.entity_id}/concentration/customers")
    assert resp.status_code == 200
    data = resp.json()
    assert data["customer_concentration_risk"] == "HIGH"
    assert "customer_details" in data


@pytest.mark.asyncio
async def test_get_supplier_concentration(client: AsyncClient, session: AsyncSession):
    """GET /v3/competitive/{entity_id}/concentration/suppliers returns supplier data."""
    entity = await _seed_entity(session)
    await _seed_concentration(session, entity.entity_id)
    resp = await client.get(f"/v3/competitive/{entity.entity_id}/concentration/suppliers")
    assert resp.status_code == 200
    data = resp.json()
    assert data["supplier_concentration_risk"] == "MODERATE"
    assert data["supplier_single_source_count"] == 3


@pytest.mark.asyncio
async def test_get_geographic_concentration(client: AsyncClient, session: AsyncSession):
    """GET /v3/competitive/{entity_id}/concentration/geographic returns geo data."""
    entity = await _seed_entity(session)
    await _seed_concentration(session, entity.entity_id)
    resp = await client.get(f"/v3/competitive/{entity.entity_id}/concentration/geographic")
    assert resp.status_code == 200
    data = resp.json()
    assert data["geographic_concentration_risk"] == "MODERATE"
    assert "geographic_revenue_breakdown" in data


# ── Landscape endpoint ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_landscape_not_found(client: AsyncClient, session: AsyncSession):
    """GET /v3/competitive/{entity_id}/landscape returns 404 for missing entity."""
    resp = await client.get(f"/v3/competitive/{uuid.uuid4()}/landscape")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_landscape_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v3/competitive/{entity_id}/landscape returns landscape data."""
    entity = await _seed_entity(session)
    await _seed_landscape(session, entity.entity_id)
    resp = await client.get(f"/v3/competitive/{entity.entity_id}/landscape")
    assert resp.status_code == 200
    data = resp.json()
    assert data["gics_code"] == "45102010"
    assert data["share_gainer"] is True
    assert data["value_chain_position"] == "PLATFORM"


# ── Peers endpoint ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_peers_empty(client: AsyncClient, session: AsyncSession):
    """GET /v3/competitive/{entity_id}/peers returns empty for entity with no landscape."""
    entity = await _seed_entity(session)
    resp = await client.get(f"/v3/competitive/{entity.entity_id}/peers")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_peers_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v3/competitive/{entity_id}/peers returns peer comparison entries."""
    entity = await _seed_entity(session)
    await _seed_landscape(session, entity.entity_id)
    resp = await client.get(f"/v3/competitive/{entity.entity_id}/peers")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["entity_name"] == "Peer A"


# ── Market share endpoint ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_market_share_not_found(client: AsyncClient, session: AsyncSession):
    """GET /v3/competitive/{entity_id}/market-share returns 404."""
    resp = await client.get(f"/v3/competitive/{uuid.uuid4()}/market-share")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_market_share_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v3/competitive/{entity_id}/market-share returns share data."""
    entity = await _seed_entity(session)
    await _seed_landscape(session, entity.entity_id)
    resp = await client.get(f"/v3/competitive/{entity.entity_id}/market-share")
    assert resp.status_code == 200
    data = resp.json()
    assert data["market_share_rank"] == 1
    assert data["share_gainer"] is True


# ── Relationships endpoint ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_relationships_not_found(client: AsyncClient, session: AsyncSession):
    """GET /v3/competitive/{entity_id}/relationships returns 404."""
    resp = await client.get(f"/v3/competitive/{uuid.uuid4()}/relationships")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_relationships_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v3/competitive/{entity_id}/relationships returns advantages/threats."""
    entity = await _seed_entity(session)
    await _seed_landscape(session, entity.entity_id)
    resp = await client.get(f"/v3/competitive/{entity.entity_id}/relationships")
    assert resp.status_code == 200
    data = resp.json()
    assert "competitive_advantages" in data
    assert "competitive_threats" in data


# ── Value chain endpoint ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_value_chain_not_found(client: AsyncClient, session: AsyncSession):
    """GET /v3/competitive/{entity_id}/value-chain returns 404."""
    resp = await client.get(f"/v3/competitive/{uuid.uuid4()}/value-chain")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_value_chain_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v3/competitive/{entity_id}/value-chain returns chain position."""
    entity = await _seed_entity(session)
    await _seed_landscape(session, entity.entity_id)
    resp = await client.get(f"/v3/competitive/{entity.entity_id}/value-chain")
    assert resp.status_code == 200
    data = resp.json()
    assert data["value_chain_position"] == "PLATFORM"
    assert data["gics_code"] == "45102010"


# ── Computed-from-fundamentals test (on-demand producer) ─────────────


async def _seed_competitive_universe(session: AsyncSession, gics="45102010", n=3):
    from src.models.fundamentals import (
        BalanceSheet, CashFlowStatement, FinancialPeriod, IncomeStatement,
    )
    from src.models.relationships import BusinessRelationship
    entities = []
    for i in range(n):
        e = Entity(
            entity_id=uuid.uuid4(), entity_type="PUBLIC_COMPANY",
            legal_name=f"Compete Co {i}", status="ACTIVE", source="TEST",
            gics_sub_industry=gics, gics_industry=gics[:6],
            gics_industry_group=gics[:4], gics_sector=gics[:2],
        )
        session.add(e)
        await session.flush()
        entities.append(e)
        for year, rev in [(2022, 100e6 * (i + 1)), (2023, 125e6 * (i + 1)), (2024, 150e6 * (i + 1))]:
            fp = FinancialPeriod(
                period_id=uuid.uuid4(), entity_id=e.entity_id,
                period_end_date=date(year, 12, 31), period_type="ANNUAL", fiscal_year=year,
            )
            session.add(fp)
            await session.flush()
            session.add(IncomeStatement(
                statement_id=uuid.uuid4(), period_id=fp.period_id,
                total_revenue=rev, cost_of_revenue=rev * 0.5, gross_profit=rev * 0.5,
                operating_income=rev * 0.22, net_income=rev * 0.15, ebitda=rev * 0.3,
            ))
            session.add(BalanceSheet(
                statement_id=uuid.uuid4(), period_id=fp.period_id,
                total_assets=rev * 1.4, total_debt=rev * 0.25, cash_and_equivalents=rev * 0.12,
                total_equity=rev * 0.9,
            ))
            session.add(CashFlowStatement(
                statement_id=uuid.uuid4(), period_id=fp.period_id,
                capital_expenditures=-rev * 0.05, free_cash_flow=rev * 0.17,
            ))
            await session.flush()
    # A customer concentration relationship for the first entity.
    session.add(BusinessRelationship(
        relationship_id=uuid.uuid4(), source_entity_id=entities[0].entity_id,
        target_entity_id=entities[1].entity_id, relationship_type="CUSTOMER",
        direction="OUTBOUND", revenue_percentage=35.0, is_single_source=False, is_active=True,
    ))
    await session.commit()
    return entities


@pytest.mark.asyncio
async def test_competitive_computed_from_fundamentals(client: AsyncClient, session: AsyncSession):
    """moat / landscape / concentration compute on-demand from fundamentals +
    industry aggregates + business relationships (were 404 forever)."""
    entities = await _seed_competitive_universe(session, n=3)
    eid = entities[0].entity_id

    moat = await client.get(f"/v3/competitive/{eid}/moat")
    assert moat.status_code == 200
    assert moat.json()["moat_score"] is not None

    land = await client.get(f"/v3/competitive/{eid}/landscape")
    assert land.status_code == 200
    assert land.json()["market_share_est_pct"] is not None

    conc = await client.get(f"/v3/competitive/{eid}/concentration")
    assert conc.status_code == 200
    # The seeded 35% customer relationship is reflected.
    assert conc.json()["customer_top1_pct"] == 35.0
