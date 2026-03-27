"""Tests for Pillar 3 Phase 3A: Competitive Intelligence models."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from src.models.entity import Entity
from src.models.competitive_intelligence import (
    CompetitiveLandscape,
    ConcentrationRiskAssessment,
    MoatAssessment,
    MoatHistory,
)


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_entity(session, entity_id: uuid.UUID | None = None) -> Entity:
    eid = entity_id or uuid.uuid4()
    entity = Entity(
        entity_id=eid,
        entity_type="PUBLIC_COMPANY",
        legal_name="Competitive Test Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()
    return entity


# ── Moat Assessment Tests ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_moat_assessment(session):
    """Create a moat assessment with all fields and verify."""
    entity = await _seed_entity(session)
    mid = uuid.uuid4()

    moat = MoatAssessment(
        id=mid,
        entity_id=entity.entity_id,
        as_of_date=date(2025, 6, 30),
        roic_above_wacc_years=12,
        roic_consistency_score=Decimal("85.50"),
        gross_margin_stability=Decimal("92.00"),
        gross_margin_10y_std=Decimal("0.0250"),
        market_share_trend="GROWING",
        market_share_5y_delta=Decimal("0.0350"),
        customer_retention_proxy=Decimal("95.00"),
        moat_width="WIDE",
        moat_stability="STABLE",
        moat_score=Decimal("88.00"),
        cost_advantage_score=Decimal("70.00"),
        network_effects_score=Decimal("90.00"),
        switching_costs_score=Decimal("85.00"),
        intangible_assets_score=Decimal("75.00"),
        efficient_scale_score=Decimal("60.00"),
        dominant_moat_source="NETWORK_EFFECTS",
        moat_evidence={"key_evidence": "Platform ecosystem lock-in"},
        ai_summary="Strong network effects with high switching costs.",
        ai_enabled=True,
    )
    session.add(moat)
    await session.flush()

    result = await session.execute(
        select(MoatAssessment).where(MoatAssessment.id == mid)
    )
    fetched = result.scalar_one()
    assert fetched.entity_id == entity.entity_id
    assert fetched.moat_width == "WIDE"
    assert fetched.moat_score == Decimal("88.00")
    assert fetched.roic_above_wacc_years == 12
    assert fetched.network_effects_score == Decimal("90.00")
    assert fetched.dominant_moat_source == "NETWORK_EFFECTS"
    assert fetched.ai_enabled is True


@pytest.mark.asyncio
async def test_moat_width_values(session):
    """Test different moat width classifications."""
    entity = await _seed_entity(session)
    widths = ["WIDE", "NARROW", "NONE"]
    ids = []
    for i, width in enumerate(widths):
        mid = uuid.uuid4()
        ids.append(mid)
        session.add(MoatAssessment(
            id=mid,
            entity_id=entity.entity_id,
            as_of_date=date(2025, 6, i + 1),
            moat_width=width,
        ))
    await session.flush()

    for i, expected_width in enumerate(widths):
        result = await session.execute(
            select(MoatAssessment).where(MoatAssessment.id == ids[i])
        )
        fetched = result.scalar_one()
        assert fetched.moat_width == expected_width


@pytest.mark.asyncio
async def test_moat_evidence_jsonb(session):
    """Round-trip JSONB moat_evidence."""
    entity = await _seed_entity(session)
    mid = uuid.uuid4()
    evidence = {
        "sources": ["brand_loyalty", "patents"],
        "details": {"patents_count": 1500, "brand_rank": 3},
    }
    session.add(MoatAssessment(
        id=mid,
        entity_id=entity.entity_id,
        as_of_date=date(2025, 7, 1),
        moat_width="WIDE",
        moat_evidence=evidence,
    ))
    await session.flush()

    result = await session.execute(
        select(MoatAssessment).where(MoatAssessment.id == mid)
    )
    fetched = result.scalar_one()
    assert fetched.moat_evidence == evidence
    assert fetched.moat_evidence["sources"] == ["brand_loyalty", "patents"]


@pytest.mark.asyncio
async def test_moat_entity_id_required(session):
    """MoatAssessment entity_id column must reference a UUID."""
    entity = await _seed_entity(session)
    mid = uuid.uuid4()
    session.add(MoatAssessment(
        id=mid,
        entity_id=entity.entity_id,
        as_of_date=date(2025, 6, 30),
        moat_width="NARROW",
    ))
    await session.flush()

    result = await session.execute(
        select(MoatAssessment).where(MoatAssessment.id == mid)
    )
    fetched = result.scalar_one()
    assert fetched.entity_id == entity.entity_id


# ── Moat History Tests ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_moat_history(session):
    """Create historical moat data points."""
    entity = await _seed_entity(session)
    hid = uuid.uuid4()

    history = MoatHistory(
        id=hid,
        entity_id=entity.entity_id,
        period_end_date=date(2024, 12, 31),
        moat_width="WIDE",
        moat_score=Decimal("86.00"),
        roic=Decimal("0.2200"),
        wacc=Decimal("0.0900"),
        roic_wacc_spread=Decimal("0.1300"),
        gross_margin=Decimal("0.7400"),
        market_share_est=Decimal("0.1500"),
    )
    session.add(history)
    await session.flush()

    result = await session.execute(
        select(MoatHistory).where(MoatHistory.id == hid)
    )
    fetched = result.scalar_one()
    assert fetched.entity_id == entity.entity_id
    assert fetched.moat_width == "WIDE"
    assert fetched.roic == Decimal("0.2200")
    assert fetched.roic_wacc_spread == Decimal("0.1300")
    assert fetched.market_share_est == Decimal("0.1500")


@pytest.mark.asyncio
async def test_moat_history_multiple_periods(session):
    """Multiple history entries for same entity across periods."""
    entity = await _seed_entity(session)
    ids = []
    for yr in [2022, 2023, 2024]:
        hid = uuid.uuid4()
        ids.append(hid)
        session.add(MoatHistory(
            id=hid,
            entity_id=entity.entity_id,
            period_end_date=date(yr, 12, 31),
            moat_width="WIDE",
            moat_score=Decimal(f"{80 + yr - 2022}.00"),
        ))
    await session.flush()

    result = await session.execute(
        select(MoatHistory)
        .where(MoatHistory.entity_id == entity.entity_id)
        .order_by(MoatHistory.period_end_date.desc())
    )
    rows = result.scalars().all()
    assert len(rows) >= 3
    assert rows[0].period_end_date >= rows[1].period_end_date


# ── Concentration Risk Tests ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_concentration_risk(session):
    """Create a concentration risk assessment with all fields."""
    entity = await _seed_entity(session)
    cid = uuid.uuid4()
    customer_details = {"top_customer": "US Government", "pct": 25.0}
    supplier_details = {"critical": ["TSMC", "Samsung"]}
    geo_breakdown = {"US": 0.55, "Europe": 0.25, "Asia": 0.20}
    supplier_geo = {"Taiwan": 0.40, "South Korea": 0.30, "China": 0.20}

    conc = ConcentrationRiskAssessment(
        id=cid,
        entity_id=entity.entity_id,
        as_of_date=date(2025, 6, 30),
        customer_top1_pct=Decimal("0.2500"),
        customer_top5_pct=Decimal("0.5500"),
        customer_top10_pct=Decimal("0.7000"),
        customer_concentration_risk="HIGH",
        customer_details=customer_details,
        supplier_single_source_count=3,
        supplier_critical_count=5,
        supplier_geographic_concentration=supplier_geo,
        supplier_concentration_risk="MODERATE",
        supplier_details=supplier_details,
        geographic_revenue_breakdown=geo_breakdown,
        geographic_top1_pct=Decimal("0.5500"),
        geographic_hhi=Decimal("3850.00"),
        fx_exposure_score=Decimal("45.00"),
        geographic_concentration_risk="MODERATE",
        overall_concentration_risk="HIGH",
        overall_risk_score=Decimal("72.00"),
    )
    session.add(conc)
    await session.flush()

    result = await session.execute(
        select(ConcentrationRiskAssessment).where(ConcentrationRiskAssessment.id == cid)
    )
    fetched = result.scalar_one()
    assert fetched.entity_id == entity.entity_id
    assert fetched.customer_top1_pct == Decimal("0.2500")
    assert fetched.customer_concentration_risk == "HIGH"
    assert fetched.supplier_single_source_count == 3
    assert fetched.overall_concentration_risk == "HIGH"
    assert fetched.overall_risk_score == Decimal("72.00")


@pytest.mark.asyncio
async def test_concentration_jsonb_fields(session):
    """Round-trip JSONB concentration detail fields."""
    entity = await _seed_entity(session)
    cid = uuid.uuid4()
    customer_details = {"names": ["Customer A", "Customer B"]}
    geo_breakdown = {"US": 0.60, "China": 0.40}

    session.add(ConcentrationRiskAssessment(
        id=cid,
        entity_id=entity.entity_id,
        as_of_date=date(2025, 7, 1),
        customer_details=customer_details,
        geographic_revenue_breakdown=geo_breakdown,
    ))
    await session.flush()

    result = await session.execute(
        select(ConcentrationRiskAssessment).where(ConcentrationRiskAssessment.id == cid)
    )
    fetched = result.scalar_one()
    assert fetched.customer_details == customer_details
    assert fetched.geographic_revenue_breakdown == geo_breakdown


# ── Competitive Landscape Tests ──────────────────────────────────────


@pytest.mark.asyncio
async def test_create_competitive_landscape(session):
    """Create a competitive landscape with all fields."""
    entity = await _seed_entity(session)
    lid = uuid.uuid4()
    peer_group = [
        {"entity_id": str(uuid.uuid4()), "entity_name": "Peer A", "market_share_est_pct": 0.15},
        {"entity_id": str(uuid.uuid4()), "entity_name": "Peer B", "market_share_est_pct": 0.10},
    ]
    advantages = ["brand_loyalty", "scale_economies", "network_effects"]
    threats = ["new_entrant_disruption", "regulation"]
    valuation = {"pe_ratio": 28.5, "ev_ebitda": 18.2}

    landscape = CompetitiveLandscape(
        id=lid,
        entity_id=entity.entity_id,
        gics_code="45102010",
        as_of_date=date(2025, 6, 30),
        peer_group=peer_group,
        market_share_est_pct=Decimal("0.2500"),
        market_share_rank=1,
        revenue_growth_vs_peers=Decimal("0.0500"),
        margin_vs_peers=Decimal("0.0800"),
        roic_vs_peers=Decimal("0.0600"),
        valuation_vs_peers=valuation,
        share_gainer=True,
        value_chain_position="PLATFORM",
        competitive_advantages=advantages,
        competitive_threats=threats,
    )
    session.add(landscape)
    await session.flush()

    result = await session.execute(
        select(CompetitiveLandscape).where(CompetitiveLandscape.id == lid)
    )
    fetched = result.scalar_one()
    assert fetched.entity_id == entity.entity_id
    assert fetched.gics_code == "45102010"
    assert fetched.market_share_est_pct == Decimal("0.2500")
    assert fetched.market_share_rank == 1
    assert fetched.share_gainer is True
    assert fetched.value_chain_position == "PLATFORM"


@pytest.mark.asyncio
async def test_landscape_jsonb_round_trip(session):
    """JSONB fields in CompetitiveLandscape should round-trip."""
    entity = await _seed_entity(session)
    lid = uuid.uuid4()
    peer_group = [{"entity_name": "Rival Corp", "share": 0.12}]
    advantages = ["cost_leadership"]
    threats = ["tech_disruption"]

    session.add(CompetitiveLandscape(
        id=lid,
        entity_id=entity.entity_id,
        gics_code="20301010",
        as_of_date=date(2025, 7, 1),
        peer_group=peer_group,
        competitive_advantages=advantages,
        competitive_threats=threats,
    ))
    await session.flush()

    result = await session.execute(
        select(CompetitiveLandscape).where(CompetitiveLandscape.id == lid)
    )
    fetched = result.scalar_one()
    assert fetched.peer_group == peer_group
    assert fetched.competitive_advantages == advantages
    assert fetched.competitive_threats == threats


@pytest.mark.asyncio
async def test_landscape_entity_id_required(session):
    """CompetitiveLandscape entity_id column must reference a UUID."""
    entity = await _seed_entity(session)
    lid = uuid.uuid4()
    session.add(CompetitiveLandscape(
        id=lid,
        entity_id=entity.entity_id,
        gics_code="45102010",
        as_of_date=date(2025, 6, 30),
    ))
    await session.flush()

    result = await session.execute(
        select(CompetitiveLandscape).where(CompetitiveLandscape.id == lid)
    )
    fetched = result.scalar_one()
    assert fetched.entity_id == entity.entity_id
