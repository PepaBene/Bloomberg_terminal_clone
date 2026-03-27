"""Tests for Pillar 3 Phase 3B: Global Intelligence models."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.models.entity import Entity
from src.models.country_risk import (
    CompanyCountryExposure,
    CountryProfile,
    CountryRiskScore,
    GeopoliticalEvent,
)
from src.models.global_macro import (
    CentralBankDecision,
    CentralBankProfile,
    GlobalMacroIndicator,
)
from src.models.commodity_intelligence import (
    CommodityCompanyExposure,
    CommodityPrice,
    CommodityProfile,
)
from src.models.political_intelligence import (
    LegislativeBill,
    RegulatoryAction,
    SanctionsEntry,
)


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_entity(session, entity_id: uuid.UUID | None = None) -> Entity:
    eid = entity_id or uuid.uuid4()
    entity = Entity(
        entity_id=eid,
        entity_type="PUBLIC_COMPANY",
        legal_name="Global Intel Test Corp",
        status="ACTIVE",
        source="TEST",
    )
    session.add(entity)
    await session.flush()
    return entity


# ══════════════════════════════════════════════════════════════════════
# Country Risk
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_country_profile(session):
    """Create a country profile with all fields."""
    cid = uuid.uuid4()
    profile = CountryProfile(
        id=cid,
        country_code="USA",
        country_name="United States",
        region="NORTH_AMERICA",
        income_group="HIGH",
        is_g20=True,
        is_eu=False,
        population=Decimal("331000000"),
        gdp_usd=Decimal("25462700000000.00"),
    )
    session.add(profile)
    await session.flush()

    result = await session.execute(
        select(CountryProfile).where(CountryProfile.id == cid)
    )
    fetched = result.scalar_one()
    assert fetched.country_code == "USA"
    assert fetched.country_name == "United States"
    assert fetched.is_g20 is True
    assert fetched.is_eu is False
    assert fetched.population == Decimal("331000000")
    assert fetched.gdp_usd == Decimal("25462700000000.00")


@pytest.mark.asyncio
async def test_country_profile_unique_country_code(session):
    """country_code should be unique."""
    session.add(CountryProfile(
        country_code="DEU",
        country_name="Germany",
    ))
    await session.flush()

    session.add(CountryProfile(
        country_code="DEU",
        country_name="Germany Duplicate",
    ))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_create_country_risk_score(session):
    """Create a country risk score with JSONB components."""
    rid = uuid.uuid4()
    score = CountryRiskScore(
        id=rid,
        country_code="RUS",
        as_of_date=date(2025, 6, 1),
        political_risk_score=Decimal("85.50"),
        economic_risk_score=Decimal("72.30"),
        sanctions_risk_score=Decimal("95.00"),
        composite_risk_score=Decimal("84.27"),
        risk_classification="HIGH",
        risk_trend="WORSENING",
        political_components={"stability": 20, "conflict": 90},
        economic_components={"inflation": 75, "gdp_growth": -2.1},
        sanctions_components={"ofac": True, "eu_sanctions": True},
    )
    session.add(score)
    await session.flush()

    result = await session.execute(
        select(CountryRiskScore).where(CountryRiskScore.id == rid)
    )
    fetched = result.scalar_one()
    assert fetched.country_code == "RUS"
    assert fetched.composite_risk_score == Decimal("84.27")
    assert fetched.risk_classification == "HIGH"
    assert fetched.political_components["conflict"] == 90
    assert fetched.sanctions_components["ofac"] is True


@pytest.mark.asyncio
async def test_country_risk_score_jsonb_roundtrip(session):
    """Verify JSONB round-trip for component breakdowns."""
    rid = uuid.uuid4()
    components = {"debt_to_gdp": 120.5, "current_account": -3.2, "reserves": 450}
    session.add(CountryRiskScore(
        id=rid,
        country_code="ARG",
        as_of_date=date(2025, 7, 1),
        economic_components=components,
    ))
    await session.flush()

    result = await session.execute(
        select(CountryRiskScore).where(CountryRiskScore.id == rid)
    )
    fetched = result.scalar_one()
    assert fetched.economic_components == components
    assert fetched.economic_components["debt_to_gdp"] == 120.5


@pytest.mark.asyncio
async def test_create_company_country_exposure(session):
    """Create a company country exposure record."""
    entity = await _seed_entity(session)
    eid = uuid.uuid4()
    exposure = CompanyCountryExposure(
        id=eid,
        entity_id=entity.entity_id,
        country_code="CHN",
        exposure_type="REVENUE",
        exposure_pct=Decimal("18.5000"),
        source="10K_FILING",
        as_of_date=date(2025, 3, 31),
    )
    session.add(exposure)
    await session.flush()

    result = await session.execute(
        select(CompanyCountryExposure).where(CompanyCountryExposure.id == eid)
    )
    fetched = result.scalar_one()
    assert fetched.entity_id == entity.entity_id
    assert fetched.country_code == "CHN"
    assert fetched.exposure_pct == Decimal("18.5000")


@pytest.mark.asyncio
async def test_create_geopolitical_event(session):
    """Create a geopolitical event with JSONB impact fields."""
    gid = uuid.uuid4()
    event = GeopoliticalEvent(
        id=gid,
        event_type="TRADE_WAR",
        title="US-China Trade Tensions Escalate",
        description="New tariffs announced on semiconductor exports.",
        countries_involved=["USA", "CHN"],
        severity="HIGH",
        status="ACTIVE",
        start_date=date(2025, 5, 15),
        commodity_impact={"semiconductors": "NEGATIVE", "rare_earths": "NEGATIVE"},
        sector_impact={"Technology": -5.2, "Manufacturing": -3.1},
        affected_entity_ids=["entity-1", "entity-2"],
    )
    session.add(event)
    await session.flush()

    result = await session.execute(
        select(GeopoliticalEvent).where(GeopoliticalEvent.id == gid)
    )
    fetched = result.scalar_one()
    assert fetched.title == "US-China Trade Tensions Escalate"
    assert fetched.severity == "HIGH"
    assert "USA" in fetched.countries_involved
    assert fetched.commodity_impact["semiconductors"] == "NEGATIVE"
    assert fetched.sector_impact["Technology"] == -5.2


# ══════════════════════════════════════════════════════════════════════
# Global Macro
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_central_bank_profile(session):
    """Create a central bank profile."""
    bid = uuid.uuid4()
    bank = CentralBankProfile(
        id=bid,
        bank_code="FED",
        bank_name="Federal Reserve",
        country_code="USA",
        current_rate=Decimal("5.2500"),
        policy_stance="HAWKISH",
        next_meeting_date=date(2025, 9, 17),
        forward_guidance_summary="Rates to remain elevated until inflation reaches 2%.",
    )
    session.add(bank)
    await session.flush()

    result = await session.execute(
        select(CentralBankProfile).where(CentralBankProfile.id == bid)
    )
    fetched = result.scalar_one()
    assert fetched.bank_code == "FED"
    assert fetched.current_rate == Decimal("5.2500")
    assert fetched.policy_stance == "HAWKISH"


@pytest.mark.asyncio
async def test_central_bank_unique_bank_code(session):
    """bank_code should be unique."""
    session.add(CentralBankProfile(
        bank_code="ECB",
        bank_name="European Central Bank",
    ))
    await session.flush()

    session.add(CentralBankProfile(
        bank_code="ECB",
        bank_name="ECB Duplicate",
    ))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_create_central_bank_decision(session):
    """Create a central bank decision record."""
    did = uuid.uuid4()
    decision = CentralBankDecision(
        id=did,
        bank_code="FED",
        decision_date=date(2025, 7, 30),
        rate_before=Decimal("5.2500"),
        rate_after=Decimal("5.0000"),
        rate_change_bps=-25,
        decision_type="CUT",
        was_surprise=True,
        vote_split="7-4",
        statement_summary="Fed cuts rates by 25bp citing slowing labor market.",
    )
    session.add(decision)
    await session.flush()

    result = await session.execute(
        select(CentralBankDecision).where(CentralBankDecision.id == did)
    )
    fetched = result.scalar_one()
    assert fetched.bank_code == "FED"
    assert fetched.rate_change_bps == -25
    assert fetched.was_surprise is True
    assert fetched.vote_split == "7-4"


@pytest.mark.asyncio
async def test_create_global_macro_indicator(session):
    """Create a global macro indicator."""
    mid = uuid.uuid4()
    indicator = GlobalMacroIndicator(
        id=mid,
        country_code="USA",
        indicator_type="CPI",
        period_label="2025-Q2",
        value=Decimal("3.2000"),
        prior_value=Decimal("3.5000"),
        forecast_value=Decimal("3.1000"),
        source="BLS",
        release_date=date(2025, 7, 10),
    )
    session.add(indicator)
    await session.flush()

    result = await session.execute(
        select(GlobalMacroIndicator).where(GlobalMacroIndicator.id == mid)
    )
    fetched = result.scalar_one()
    assert fetched.country_code == "USA"
    assert fetched.indicator_type == "CPI"
    assert fetched.value == Decimal("3.2000")
    assert fetched.prior_value == Decimal("3.5000")


# ══════════════════════════════════════════════════════════════════════
# Commodities
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_commodity_profile(session):
    """Create a commodity profile."""
    cid = uuid.uuid4()
    profile = CommodityProfile(
        id=cid,
        commodity_code="CL",
        commodity_name="WTI Crude Oil",
        category="ENERGY",
        unit="USD/barrel",
        primary_source="NYMEX",
    )
    session.add(profile)
    await session.flush()

    result = await session.execute(
        select(CommodityProfile).where(CommodityProfile.id == cid)
    )
    fetched = result.scalar_one()
    assert fetched.commodity_code == "CL"
    assert fetched.commodity_name == "WTI Crude Oil"
    assert fetched.category == "ENERGY"


@pytest.mark.asyncio
async def test_commodity_profile_unique_code(session):
    """commodity_code should be unique."""
    session.add(CommodityProfile(
        commodity_code="GC",
        commodity_name="Gold",
    ))
    await session.flush()

    session.add(CommodityProfile(
        commodity_code="GC",
        commodity_name="Gold Duplicate",
    ))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_create_commodity_price(session):
    """Create a commodity price record with Decimal precision."""
    pid = uuid.uuid4()
    price = CommodityPrice(
        id=pid,
        commodity_code="CL",
        price_date=date(2025, 7, 15),
        close_price=Decimal("78.4500"),
        open_price=Decimal("77.2000"),
        high_price=Decimal("79.1000"),
        low_price=Decimal("76.8000"),
        volume=Decimal("1250000.00"),
        source="NYMEX",
    )
    session.add(price)
    await session.flush()

    result = await session.execute(
        select(CommodityPrice).where(CommodityPrice.id == pid)
    )
    fetched = result.scalar_one()
    assert fetched.commodity_code == "CL"
    assert fetched.close_price == Decimal("78.4500")
    assert fetched.high_price == Decimal("79.1000")
    assert fetched.volume == Decimal("1250000.00")


@pytest.mark.asyncio
async def test_create_commodity_company_exposure(session):
    """Create a commodity company exposure record."""
    entity = await _seed_entity(session)
    eid = uuid.uuid4()
    exposure = CommodityCompanyExposure(
        id=eid,
        commodity_code="CL",
        entity_id=entity.entity_id,
        exposure_type="INPUT_COST",
        exposure_description="Crude oil is key input for petrochemical operations.",
        sensitivity_score=Decimal("85.50"),
        historical_correlation=Decimal("0.7200"),
        source="ANALYST",
    )
    session.add(exposure)
    await session.flush()

    result = await session.execute(
        select(CommodityCompanyExposure).where(CommodityCompanyExposure.id == eid)
    )
    fetched = result.scalar_one()
    assert fetched.commodity_code == "CL"
    assert fetched.sensitivity_score == Decimal("85.50")
    assert fetched.historical_correlation == Decimal("0.7200")


# ══════════════════════════════════════════════════════════════════════
# Political & Policy
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_legislative_bill(session):
    """Create a legislative bill with JSONB sector impact."""
    lid = uuid.uuid4()
    bill = LegislativeBill(
        id=lid,
        bill_id="HR-1234",
        title="Clean Energy Investment Act",
        summary="Tax credits for renewable energy investments.",
        bill_type="HOUSE",
        status="IN_COMMITTEE",
        sponsor_count=45,
        passage_probability=Decimal("35.00"),
        affected_sectors=["Energy", "Utilities"],
        introduced_date=date(2025, 3, 1),
        last_action_date=date(2025, 7, 10),
        source_url="https://congress.gov/bill/hr-1234",
    )
    session.add(bill)
    await session.flush()

    result = await session.execute(
        select(LegislativeBill).where(LegislativeBill.id == lid)
    )
    fetched = result.scalar_one()
    assert fetched.bill_id == "HR-1234"
    assert fetched.passage_probability == Decimal("35.00")
    assert "Energy" in fetched.affected_sectors


@pytest.mark.asyncio
async def test_legislative_bill_unique_bill_id(session):
    """bill_id should be unique."""
    session.add(LegislativeBill(
        bill_id="S-5678",
        title="Test Bill",
    ))
    await session.flush()

    session.add(LegislativeBill(
        bill_id="S-5678",
        title="Test Bill Duplicate",
    ))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_create_regulatory_action(session):
    """Create a regulatory action with financial impact."""
    rid = uuid.uuid4()
    action = RegulatoryAction(
        id=rid,
        agency="SEC",
        action_type="ENFORCEMENT",
        title="SEC fines broker-dealer for compliance failures",
        description="Civil penalty for failure to maintain adequate AML controls.",
        affected_sectors=["Financials"],
        severity="HIGH",
        financial_impact=Decimal("15000000.00"),
        action_date=date(2025, 6, 20),
        source_url="https://sec.gov/enforcement/example",
    )
    session.add(action)
    await session.flush()

    result = await session.execute(
        select(RegulatoryAction).where(RegulatoryAction.id == rid)
    )
    fetched = result.scalar_one()
    assert fetched.agency == "SEC"
    assert fetched.financial_impact == Decimal("15000000.00")
    assert fetched.severity == "HIGH"


@pytest.mark.asyncio
async def test_create_sanctions_entry(session):
    """Create a sanctions entry with JSONB affected sectors."""
    sid = uuid.uuid4()
    entry = SanctionsEntry(
        id=sid,
        program="OFAC_SDN",
        country_code="RUS",
        target_name="Rosneft Oil Company",
        target_type="ENTITY",
        status="ACTIVE",
        effective_date=date(2022, 4, 6),
        description="Full blocking sanctions on Russian energy entity.",
        affected_sectors=["Energy", "Financials"],
        source_url="https://ofac.treasury.gov/example",
    )
    session.add(entry)
    await session.flush()

    result = await session.execute(
        select(SanctionsEntry).where(SanctionsEntry.id == sid)
    )
    fetched = result.scalar_one()
    assert fetched.program == "OFAC_SDN"
    assert fetched.country_code == "RUS"
    assert fetched.target_name == "Rosneft Oil Company"
    assert "Energy" in fetched.affected_sectors


@pytest.mark.asyncio
async def test_sanctions_entry_jsonb_roundtrip(session):
    """Round-trip JSONB affected_sectors list."""
    sid = uuid.uuid4()
    sectors = ["Energy", "Technology", "Financials", "Defense"]
    session.add(SanctionsEntry(
        id=sid,
        program="OFAC_SDN",
        country_code="IRN",
        target_name="Test Entity",
        target_type="ENTITY",
        status="ACTIVE",
        affected_sectors=sectors,
    ))
    await session.flush()

    result = await session.execute(
        select(SanctionsEntry).where(SanctionsEntry.id == sid)
    )
    fetched = result.scalar_one()
    assert fetched.affected_sectors == sectors
    assert len(fetched.affected_sectors) == 4
