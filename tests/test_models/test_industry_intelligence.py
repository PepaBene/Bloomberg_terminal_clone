"""Tests for Pillar 3 Phase 3A: Industry Intelligence models."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.models.industry_intelligence import (
    IndustryCompetitiveStructure,
    IndustryCyclePosition,
    IndustryProfile,
)


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_profile(
    session,
    gics_code: str = "45102010",
    gics_name: str = "Application Software",
    profile_id: uuid.UUID | None = None,
) -> IndustryProfile:
    pid = profile_id or uuid.uuid4()
    profile = IndustryProfile(
        id=pid,
        gics_code=gics_code,
        gics_level="SUB_INDUSTRY",
        gics_name=gics_name,
        as_of_date=date(2025, 6, 30),
        company_count=150,
        total_market_cap=Decimal("5500000000000.00"),
        median_market_cap=Decimal("12000000000.00"),
        revenue_growth_3y_cagr=Decimal("0.1520"),
        revenue_growth_5y_cagr=Decimal("0.1340"),
        median_gross_margin=Decimal("0.7200"),
        median_operating_margin=Decimal("0.2500"),
        median_roic=Decimal("0.1800"),
        median_wacc=Decimal("0.0950"),
        roic_wacc_spread=Decimal("0.0850"),
    )
    session.add(profile)
    await session.flush()
    return profile


# ── Tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_industry_profile(session):
    """Create an industry profile with all fields and verify."""
    pid = uuid.uuid4()
    profile = IndustryProfile(
        id=pid,
        gics_code="45102010",
        gics_level="SUB_INDUSTRY",
        gics_name="Application Software",
        as_of_date=date(2025, 6, 30),
        company_count=150,
        total_market_cap=Decimal("5500000000000.00"),
        median_market_cap=Decimal("12000000000.00"),
        revenue_growth_3y_cagr=Decimal("0.1520"),
        revenue_growth_5y_cagr=Decimal("0.1340"),
        revenue_dispersion=Decimal("0.0800"),
        median_gross_margin=Decimal("0.7200"),
        median_operating_margin=Decimal("0.2500"),
        median_capex_to_revenue=Decimal("0.0450"),
        median_rd_to_revenue=Decimal("0.1500"),
        median_roic=Decimal("0.1800"),
        median_wacc=Decimal("0.0950"),
        roic_wacc_spread=Decimal("0.0850"),
        roic_dispersion=Decimal("0.1200"),
        capital_cycle_indicator="EXPANSION",
    )
    session.add(profile)
    await session.flush()

    result = await session.execute(
        select(IndustryProfile).where(IndustryProfile.id == pid)
    )
    fetched = result.scalar_one()
    assert fetched.gics_code == "45102010"
    assert fetched.gics_name == "Application Software"
    assert fetched.company_count == 150
    assert fetched.total_market_cap == Decimal("5500000000000.00")
    assert fetched.revenue_growth_3y_cagr == Decimal("0.1520")
    assert fetched.median_gross_margin == Decimal("0.7200")
    assert fetched.median_roic == Decimal("0.1800")
    assert fetched.capital_cycle_indicator == "EXPANSION"


@pytest.mark.asyncio
async def test_industry_profile_decimal_precision(session):
    """Verify Decimal precision is preserved through round-trip."""
    pid = uuid.uuid4()
    session.add(IndustryProfile(
        id=pid,
        gics_code="40101010",
        gics_level="SUB_INDUSTRY",
        gics_name="Diversified Banks",
        as_of_date=date(2025, 6, 30),
        median_roic=Decimal("0.1234"),
        median_wacc=Decimal("0.0876"),
        roic_wacc_spread=Decimal("0.0358"),
    ))
    await session.flush()

    result = await session.execute(
        select(IndustryProfile).where(IndustryProfile.id == pid)
    )
    fetched = result.scalar_one()
    assert fetched.median_roic == Decimal("0.1234")
    assert fetched.median_wacc == Decimal("0.0876")
    assert fetched.roic_wacc_spread == Decimal("0.0358")


@pytest.mark.asyncio
async def test_industry_profile_nullable_fields(session):
    """Nullable fields default to None."""
    pid = uuid.uuid4()
    session.add(IndustryProfile(
        id=pid,
        gics_code="10101010",
        gics_level="SUB_INDUSTRY",
        gics_name="Oil & Gas Exploration",
        as_of_date=date(2025, 6, 30),
    ))
    await session.flush()

    result = await session.execute(
        select(IndustryProfile).where(IndustryProfile.id == pid)
    )
    fetched = result.scalar_one()
    assert fetched.company_count is None
    assert fetched.total_market_cap is None
    assert fetched.median_roic is None
    assert fetched.capital_cycle_indicator is None


@pytest.mark.asyncio
async def test_create_industry_cycle_position(session):
    """Create an industry cycle position with all fields."""
    cid = uuid.uuid4()
    cycle = IndustryCyclePosition(
        id=cid,
        gics_code="45102010",
        as_of_date=date(2025, 6, 30),
        revenue_growth_acceleration=Decimal("0.0250"),
        capacity_utilization_proxy=Decimal("0.8500"),
        inventory_dynamics="BUILDING",
        inventory_to_sales_trend=Decimal("0.0100"),
        margin_cycle_direction="EXPANDING",
        operating_margin_momentum=Decimal("0.0150"),
        cycle_position="EXPANSION",
        cycle_confidence=Decimal("75.50"),
        prior_cycle_position="RECOVERY",
        cycle_duration_quarters=6,
    )
    session.add(cycle)
    await session.flush()

    result = await session.execute(
        select(IndustryCyclePosition).where(IndustryCyclePosition.id == cid)
    )
    fetched = result.scalar_one()
    assert fetched.gics_code == "45102010"
    assert fetched.cycle_position == "EXPANSION"
    assert fetched.cycle_confidence == Decimal("75.50")
    assert fetched.prior_cycle_position == "RECOVERY"
    assert fetched.cycle_duration_quarters == 6
    assert fetched.inventory_dynamics == "BUILDING"


@pytest.mark.asyncio
async def test_cycle_position_values(session):
    """Test various cycle position values."""
    positions = ["EXPANSION", "PEAK", "CONTRACTION", "TROUGH", "RECOVERY"]
    ids = []
    for i, pos in enumerate(positions):
        cid = uuid.uuid4()
        ids.append(cid)
        session.add(IndustryCyclePosition(
            id=cid,
            gics_code=f"4510{i:04d}",
            as_of_date=date(2025, 6, i + 1),
            cycle_position=pos,
        ))
    await session.flush()

    for i, expected_pos in enumerate(positions):
        result = await session.execute(
            select(IndustryCyclePosition).where(IndustryCyclePosition.id == ids[i])
        )
        fetched = result.scalar_one()
        assert fetched.cycle_position == expected_pos


@pytest.mark.asyncio
async def test_create_industry_competitive_structure(session):
    """Create a competitive structure with all fields including JSONB."""
    sid = uuid.uuid4()
    barrier_factors = {"capital_requirements": "HIGH", "regulation": "MODERATE", "technology": "HIGH"}
    pricing_evidence = {"margin_stability": True, "price_over_cost_index": 1.15}
    market_share = [
        {"company": "Company A", "share": 0.25},
        {"company": "Company B", "share": 0.18},
    ]

    structure = IndustryCompetitiveStructure(
        id=sid,
        gics_code="45102010",
        as_of_date=date(2025, 6, 30),
        hhi_index=Decimal("1250.50"),
        hhi_classification="MODERATE",
        top3_market_share=Decimal("0.5500"),
        top5_market_share=Decimal("0.7200"),
        top10_market_share=Decimal("0.8800"),
        consolidation_trend="INCREASING",
        consolidation_5y_delta=Decimal("0.0500"),
        barrier_to_entry="HIGH",
        barrier_factors=barrier_factors,
        pricing_power="STRONG",
        pricing_power_evidence=pricing_evidence,
        competitive_dynamics="OLIGOPOLY",
        market_share_data=market_share,
    )
    session.add(structure)
    await session.flush()

    result = await session.execute(
        select(IndustryCompetitiveStructure).where(IndustryCompetitiveStructure.id == sid)
    )
    fetched = result.scalar_one()
    assert fetched.gics_code == "45102010"
    assert fetched.hhi_index == Decimal("1250.50")
    assert fetched.hhi_classification == "MODERATE"
    assert fetched.top3_market_share == Decimal("0.5500")
    assert fetched.barrier_to_entry == "HIGH"
    assert fetched.pricing_power == "STRONG"
    assert fetched.competitive_dynamics == "OLIGOPOLY"


@pytest.mark.asyncio
async def test_competitive_structure_jsonb_round_trip(session):
    """JSONB fields should round-trip correctly."""
    sid = uuid.uuid4()
    barrier_factors = {"capital": "HIGH", "ip": "VERY_HIGH", "regulatory": "MODERATE"}
    market_data = [{"name": "Alpha Corp", "share": 0.35}]

    session.add(IndustryCompetitiveStructure(
        id=sid,
        gics_code="20101010",
        as_of_date=date(2025, 7, 1),
        barrier_factors=barrier_factors,
        market_share_data=market_data,
    ))
    await session.flush()

    result = await session.execute(
        select(IndustryCompetitiveStructure).where(IndustryCompetitiveStructure.id == sid)
    )
    fetched = result.scalar_one()
    assert fetched.barrier_factors == barrier_factors
    assert fetched.market_share_data == market_data
    assert fetched.market_share_data[0]["name"] == "Alpha Corp"


@pytest.mark.asyncio
async def test_competitive_structure_hhi_classifications(session):
    """Test different HHI classification values."""
    classifications = [
        (Decimal("800.00"), "LOW"),
        (Decimal("1500.00"), "MODERATE"),
        (Decimal("2800.00"), "HIGH"),
    ]
    ids = []
    for i, (hhi, cls) in enumerate(classifications):
        sid = uuid.uuid4()
        ids.append(sid)
        session.add(IndustryCompetitiveStructure(
            id=sid,
            gics_code=f"3010{i:04d}",
            as_of_date=date(2025, 7, i + 1),
            hhi_index=hhi,
            hhi_classification=cls,
        ))
    await session.flush()

    for i, (expected_hhi, expected_cls) in enumerate(classifications):
        result = await session.execute(
            select(IndustryCompetitiveStructure).where(IndustryCompetitiveStructure.id == ids[i])
        )
        fetched = result.scalar_one()
        assert fetched.hhi_index == expected_hhi
        assert fetched.hhi_classification == expected_cls


@pytest.mark.asyncio
async def test_multiple_profiles_same_gics(session):
    """Multiple profiles for same GICS code with different dates."""
    gics = "45102010"
    ids = []
    for month in [1, 3, 6]:
        pid = uuid.uuid4()
        ids.append(pid)
        session.add(IndustryProfile(
            id=pid,
            gics_code=gics,
            gics_level="SUB_INDUSTRY",
            gics_name="Application Software",
            as_of_date=date(2025, month, 30 if month != 1 else 31),
            company_count=140 + month * 5,
        ))
    await session.flush()

    result = await session.execute(
        select(IndustryProfile)
        .where(IndustryProfile.gics_code == gics)
        .order_by(IndustryProfile.as_of_date.desc())
    )
    rows = result.scalars().all()
    assert len(rows) >= 3
    # Most recent date should come first
    assert rows[0].as_of_date >= rows[1].as_of_date


@pytest.mark.asyncio
async def test_industry_profile_gics_levels(session):
    """Test different GICS hierarchy levels."""
    levels = [
        ("45", "SECTOR", "Information Technology"),
        ("4510", "INDUSTRY_GROUP", "Software & Services"),
        ("451020", "INDUSTRY", "IT Services"),
        ("45102010", "SUB_INDUSTRY", "IT Consulting"),
    ]
    ids = []
    for code, level, name in levels:
        pid = uuid.uuid4()
        ids.append(pid)
        session.add(IndustryProfile(
            id=pid,
            gics_code=code,
            gics_level=level,
            gics_name=name,
            as_of_date=date(2025, 6, 30),
        ))
    await session.flush()

    for i, (expected_code, expected_level, expected_name) in enumerate(levels):
        result = await session.execute(
            select(IndustryProfile).where(IndustryProfile.id == ids[i])
        )
        fetched = result.scalar_one()
        assert fetched.gics_code == expected_code
        assert fetched.gics_level == expected_level
        assert fetched.gics_name == expected_name


@pytest.mark.asyncio
async def test_cycle_position_nullable_indicators(session):
    """Cycle position with minimal required fields."""
    cid = uuid.uuid4()
    session.add(IndustryCyclePosition(
        id=cid,
        gics_code="25201010",
        as_of_date=date(2025, 6, 30),
        cycle_position="TROUGH",
    ))
    await session.flush()

    result = await session.execute(
        select(IndustryCyclePosition).where(IndustryCyclePosition.id == cid)
    )
    fetched = result.scalar_one()
    assert fetched.cycle_position == "TROUGH"
    assert fetched.revenue_growth_acceleration is None
    assert fetched.capacity_utilization_proxy is None
    assert fetched.inventory_dynamics is None
    assert fetched.prior_cycle_position is None
    assert fetched.cycle_duration_quarters is None
