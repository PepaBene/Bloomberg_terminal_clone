"""API tests for Global Intelligence endpoints (Pillar 3 Phase 3B)."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

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


async def _seed_entity(session: AsyncSession) -> Entity:
    eid = uuid.uuid4()
    entity = Entity(
        entity_id=eid,
        entity_type="PUBLIC_COMPANY",
        legal_name="Global Intel API Test Corp",
        status="ACTIVE",
        source="TEST",
    )
    session.add(entity)
    await session.flush()
    return entity


async def _seed_country(session: AsyncSession, code: str = "USA") -> CountryProfile:
    cid = uuid.uuid4()
    profile = CountryProfile(
        id=cid,
        country_code=code,
        country_name="United States" if code == "USA" else f"Country {code}",
        region="NORTH_AMERICA",
        is_g20=True,
        is_eu=False,
        gdp_usd=Decimal("25000000000000.00"),
    )
    session.add(profile)
    await session.flush()
    return profile


async def _seed_risk_score(session: AsyncSession, code: str = "USA") -> CountryRiskScore:
    rid = uuid.uuid4()
    score = CountryRiskScore(
        id=rid,
        country_code=code,
        as_of_date=date(2025, 7, 1),
        composite_risk_score=Decimal("45.00"),
        risk_classification="MODERATE",
        political_risk_score=Decimal("30.00"),
        economic_risk_score=Decimal("25.00"),
    )
    session.add(score)
    await session.flush()
    return score


async def _seed_geopolitical_event(session: AsyncSession) -> GeopoliticalEvent:
    gid = uuid.uuid4()
    event = GeopoliticalEvent(
        id=gid,
        event_type="TRADE_WAR",
        title="Test Trade Tensions",
        severity="HIGH",
        status="ACTIVE",
        countries_involved=["USA", "CHN"],
        start_date=date(2025, 5, 1),
        commodity_impact={"oil": "NEGATIVE"},
        sector_impact={"Tech": -3.0},
    )
    session.add(event)
    await session.flush()
    return event


async def _seed_central_bank(session: AsyncSession, code: str = "FED") -> CentralBankProfile:
    bid = uuid.uuid4()
    bank = CentralBankProfile(
        id=bid,
        bank_code=code,
        bank_name="Federal Reserve" if code == "FED" else f"Bank {code}",
        country_code="USA",
        current_rate=Decimal("5.2500"),
        policy_stance="HAWKISH",
        next_meeting_date=date(2025, 9, 17),
    )
    session.add(bank)
    await session.flush()
    return bank


async def _seed_cb_decision(session: AsyncSession, code: str = "FED") -> CentralBankDecision:
    did = uuid.uuid4()
    decision = CentralBankDecision(
        id=did,
        bank_code=code,
        decision_date=date(2025, 7, 30),
        rate_before=Decimal("5.2500"),
        rate_after=Decimal("5.0000"),
        rate_change_bps=-25,
        decision_type="CUT",
        was_surprise=False,
    )
    session.add(decision)
    await session.flush()
    return decision


async def _seed_macro_indicator(session: AsyncSession, country: str = "USA", itype: str = "CPI") -> GlobalMacroIndicator:
    mid = uuid.uuid4()
    indicator = GlobalMacroIndicator(
        id=mid,
        country_code=country,
        indicator_type=itype,
        period_label="2025-Q2",
        value=Decimal("3.2000"),
        prior_value=Decimal("3.5000"),
        release_date=date(2025, 7, 10),
    )
    session.add(indicator)
    await session.flush()
    return indicator


async def _seed_commodity(session: AsyncSession, code: str = "CL") -> CommodityProfile:
    cid = uuid.uuid4()
    profile = CommodityProfile(
        id=cid,
        commodity_code=code,
        commodity_name="WTI Crude Oil" if code == "CL" else f"Commodity {code}",
        category="ENERGY",
        unit="USD/barrel",
    )
    session.add(profile)
    await session.flush()
    return profile


async def _seed_commodity_price(session: AsyncSession, code: str = "CL") -> CommodityPrice:
    pid = uuid.uuid4()
    price = CommodityPrice(
        id=pid,
        commodity_code=code,
        price_date=date(2025, 7, 15),
        close_price=Decimal("78.4500"),
        open_price=Decimal("77.2000"),
        high_price=Decimal("79.1000"),
        low_price=Decimal("76.8000"),
    )
    session.add(price)
    await session.flush()
    return price


async def _seed_bill(session: AsyncSession, bill_id: str = "HR-1234") -> LegislativeBill:
    lid = uuid.uuid4()
    bill = LegislativeBill(
        id=lid,
        bill_id=bill_id,
        title="Test Bill",
        status="IN_COMMITTEE",
        passage_probability=Decimal("35.00"),
        introduced_date=date(2025, 3, 1),
        last_action_date=date(2025, 7, 10),
    )
    session.add(bill)
    await session.flush()
    return bill


async def _seed_regulatory_action(session: AsyncSession) -> RegulatoryAction:
    rid = uuid.uuid4()
    action = RegulatoryAction(
        id=rid,
        agency="SEC",
        action_type="ENFORCEMENT",
        title="Test Enforcement Action",
        severity="HIGH",
        financial_impact=Decimal("15000000.00"),
        action_date=date(2025, 6, 20),
    )
    session.add(action)
    await session.flush()
    return action


async def _seed_sanctions(session: AsyncSession, country: str = "RUS") -> SanctionsEntry:
    sid = uuid.uuid4()
    entry = SanctionsEntry(
        id=sid,
        program="OFAC_SDN",
        country_code=country,
        target_name="Test Entity",
        target_type="ENTITY",
        status="ACTIVE",
        effective_date=date(2022, 4, 6),
        affected_sectors=["Energy"],
    )
    session.add(entry)
    await session.flush()
    return entry


# ══════════════════════════════════════════════════════════════════════
# Country Risk API Tests
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_list_countries_empty(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/countries returns 200 with empty list."""
    resp = await client.get("/v3/global/countries")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_list_countries_seeded(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/countries returns seeded country."""
    await _seed_country(session, "GBR")
    resp = await client.get("/v3/global/countries")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert any(c["country_code"] == "GBR" for c in data)


@pytest.mark.asyncio
async def test_get_country_risk_ranking_empty(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/countries/risk-ranking returns 200 empty."""
    resp = await client.get("/v3/global/countries/risk-ranking")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_country_risk_ranking_seeded(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/countries/risk-ranking returns ranked countries."""
    await _seed_country(session, "BRA")
    await _seed_risk_score(session, "BRA")
    resp = await client.get("/v3/global/countries/risk-ranking")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["rank"] == 1


@pytest.mark.asyncio
async def test_get_country_profile_404(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/countries/ZZZ returns 404."""
    resp = await client.get("/v3/global/countries/ZZZ")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_country_profile_seeded(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/countries/{code} returns seeded country."""
    await _seed_country(session, "FRA")
    resp = await client.get("/v3/global/countries/FRA")
    assert resp.status_code == 200
    assert resp.json()["country_code"] == "FRA"


@pytest.mark.asyncio
async def test_get_country_risk_empty(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/countries/{code}/risk returns 200 empty."""
    resp = await client.get("/v3/global/countries/XYZ/risk")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_country_risk_seeded(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/countries/{code}/risk returns risk scores."""
    await _seed_risk_score(session, "JPN")
    resp = await client.get("/v3/global/countries/JPN/risk")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["country_code"] == "JPN"


@pytest.mark.asyncio
async def test_get_country_exposed_companies(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/countries/{code}/exposed-companies returns 200."""
    entity = await _seed_entity(session)
    session.add(CompanyCountryExposure(
        entity_id=entity.entity_id,
        country_code="CHN",
        exposure_type="REVENUE",
        exposure_pct=Decimal("20.0000"),
    ))
    await session.flush()
    resp = await client.get("/v3/global/countries/CHN/exposed-companies")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_get_country_events(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/countries/{code}/events returns filtered events."""
    await _seed_geopolitical_event(session)
    resp = await client.get("/v3/global/countries/USA/events")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


# ══════════════════════════════════════════════════════════════════════
# Geopolitical Events API Tests
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_list_geopolitical_events_empty(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/events/geopolitical returns 200 empty."""
    resp = await client.get("/v3/global/events/geopolitical")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_list_geopolitical_events_seeded(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/events/geopolitical returns seeded events."""
    await _seed_geopolitical_event(session)
    resp = await client.get("/v3/global/events/geopolitical")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_get_geopolitical_event_404(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/events/geopolitical/{id} returns 404."""
    resp = await client.get(f"/v3/global/events/geopolitical/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_geopolitical_event_seeded(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/events/geopolitical/{id} returns event."""
    event = await _seed_geopolitical_event(session)
    resp = await client.get(f"/v3/global/events/geopolitical/{event.id}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Test Trade Tensions"


@pytest.mark.asyncio
async def test_list_scenarios(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/scenarios returns 200."""
    await _seed_geopolitical_event(session)
    resp = await client.get("/v3/global/scenarios")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_run_scenario_impact_404(client: AsyncClient, session: AsyncSession):
    """POST /v3/global/scenarios/{id}/impact returns 404."""
    resp = await client.post(f"/v3/global/scenarios/{uuid.uuid4()}/impact")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_run_scenario_impact_seeded(client: AsyncClient, session: AsyncSession):
    """POST /v3/global/scenarios/{id}/impact returns impact."""
    event = await _seed_geopolitical_event(session)
    resp = await client.post(f"/v3/global/scenarios/{event.id}/impact")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scenario_id"] == str(event.id)


# ══════════════════════════════════════════════════════════════════════
# Global Macro API Tests
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_macro_dashboard(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/macro/dashboard returns 200."""
    resp = await client.get("/v3/global/macro/dashboard")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_list_central_banks_empty(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/macro/central-banks returns 200 empty."""
    resp = await client.get("/v3/global/macro/central-banks")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_list_central_banks_seeded(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/macro/central-banks returns seeded banks."""
    await _seed_central_bank(session, "BOJ")
    resp = await client.get("/v3/global/macro/central-banks")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_get_inflation_comparison(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/macro/inflation returns 200."""
    await _seed_macro_indicator(session, "DEU", "CPI")
    resp = await client.get("/v3/global/macro/inflation")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_get_growth_ranking(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/macro/growth returns 200."""
    await _seed_macro_indicator(session, "IND", "GDP_GROWTH")
    resp = await client.get("/v3/global/macro/growth")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_recession_probability(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/macro/recession-probability returns 200."""
    await _seed_macro_indicator(session, "USA", "RECESSION_PROB")
    resp = await client.get("/v3/global/macro/recession-probability")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_country_indicators(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/macro/{code}/indicators returns 200."""
    await _seed_macro_indicator(session, "GBR", "CPI")
    resp = await client.get("/v3/global/macro/GBR/indicators")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_get_central_bank_404(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/macro/central-banks/ZZZ returns 404."""
    resp = await client.get("/v3/global/macro/central-banks/ZZZ")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_central_bank_seeded(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/macro/central-banks/{code} returns bank."""
    await _seed_central_bank(session, "ECB")
    resp = await client.get("/v3/global/macro/central-banks/ECB")
    assert resp.status_code == 200
    assert resp.json()["bank_code"] == "ECB"


@pytest.mark.asyncio
async def test_get_central_bank_meetings(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/macro/central-banks/{code}/meetings returns 200."""
    await _seed_cb_decision(session, "BOE")
    resp = await client.get("/v3/global/macro/central-banks/BOE/meetings")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


# ══════════════════════════════════════════════════════════════════════
# Commodities API Tests
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_list_commodities_empty(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/commodities returns 200 empty."""
    resp = await client.get("/v3/global/commodities")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_list_commodities_seeded(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/commodities returns seeded commodities."""
    await _seed_commodity(session, "NG")
    resp = await client.get("/v3/global/commodities")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_get_commodity_dashboard(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/commodities/dashboard returns 200."""
    await _seed_commodity(session, "SI")
    await _seed_commodity_price(session, "SI")
    resp = await client.get("/v3/global/commodities/dashboard")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_commodity_profile_404(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/commodities/ZZZ returns 404."""
    resp = await client.get("/v3/global/commodities/ZZZ")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_commodity_profile_seeded(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/commodities/{code} returns commodity."""
    await _seed_commodity(session, "HG")
    resp = await client.get("/v3/global/commodities/HG")
    assert resp.status_code == 200
    assert resp.json()["commodity_code"] == "HG"


@pytest.mark.asyncio
async def test_get_commodity_history(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/commodities/{code}/history returns 200."""
    await _seed_commodity_price(session, "GC")
    resp = await client.get("/v3/global/commodities/GC/history")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_commodity_companies(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/commodities/{code}/companies returns 200."""
    entity = await _seed_entity(session)
    session.add(CommodityCompanyExposure(
        commodity_code="CL",
        entity_id=entity.entity_id,
        exposure_type="INPUT_COST",
        sensitivity_score=Decimal("75.00"),
    ))
    await session.flush()
    resp = await client.get("/v3/global/commodities/CL/companies")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_get_commodity_supply_demand_404(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/commodities/{code}/supply-demand returns 404 when no data."""
    resp = await client.get("/v3/global/commodities/NODATA/supply-demand")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_commodity_supply_demand_seeded(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/commodities/{code}/supply-demand returns balance."""
    await _seed_commodity_price(session, "PL")
    resp = await client.get("/v3/global/commodities/PL/supply-demand")
    assert resp.status_code == 200
    data = resp.json()
    assert "supply_demand_indicator" in data


@pytest.mark.asyncio
async def test_run_commodity_scenario(client: AsyncClient, session: AsyncSession):
    """POST /v3/global/commodities/{code}/scenario returns impact."""
    entity = await _seed_entity(session)
    session.add(CommodityCompanyExposure(
        commodity_code="BZ",
        entity_id=entity.entity_id,
        exposure_type="INPUT_COST",
        sensitivity_score=Decimal("80.00"),
    ))
    await session.flush()
    resp = await client.post(
        "/v3/global/commodities/BZ/scenario",
        json={"price_change_pct": 25.0, "description": "Oil price spike"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["commodity_code"] == "BZ"
    assert data["scenario_price_change_pct"] == 25.0


# ══════════════════════════════════════════════════════════════════════
# Political & Policy API Tests
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_list_us_bills_empty(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/political/us/bills returns 200 empty."""
    resp = await client.get("/v3/global/political/us/bills")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_list_us_bills_seeded(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/political/us/bills returns seeded bills."""
    await _seed_bill(session, "HR-9999")
    resp = await client.get("/v3/global/political/us/bills")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_get_us_bill_404(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/political/us/bills/{id} returns 404."""
    resp = await client.get("/v3/global/political/us/bills/NONEXISTENT")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_us_bill_seeded(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/political/us/bills/{id} returns bill."""
    await _seed_bill(session, "S-4321")
    resp = await client.get("/v3/global/political/us/bills/S-4321")
    assert resp.status_code == 200
    assert resp.json()["bill_id"] == "S-4321"


@pytest.mark.asyncio
async def test_list_regulatory_actions(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/political/us/regulations returns 200."""
    await _seed_regulatory_action(session)
    resp = await client.get("/v3/global/political/us/regulations")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_list_enforcement_actions(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/political/us/enforcement returns 200."""
    await _seed_regulatory_action(session)
    resp = await client.get("/v3/global/political/us/enforcement")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_elections(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/political/elections returns 200."""
    gid = uuid.uuid4()
    session.add(GeopoliticalEvent(
        id=gid,
        event_type="ELECTION",
        title="US Presidential Election",
        severity="HIGH",
        status="UPCOMING",
        start_date=date(2028, 11, 3),
        countries_involved=["USA"],
    ))
    await session.flush()
    resp = await client.get("/v3/global/political/elections")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_list_sanctions_empty(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/political/sanctions returns 200 empty."""
    resp = await client.get("/v3/global/political/sanctions")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_list_sanctions_seeded(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/political/sanctions returns seeded entries."""
    await _seed_sanctions(session, "IRN")
    resp = await client.get("/v3/global/political/sanctions")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_get_sanctions_by_country(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/political/sanctions/{code} returns filtered sanctions."""
    await _seed_sanctions(session, "CUB")
    resp = await client.get("/v3/global/political/sanctions/CUB")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert all(s["country_code"] == "CUB" for s in data)


@pytest.mark.asyncio
async def test_get_sanctions_by_country_empty(client: AsyncClient, session: AsyncSession):
    """GET /v3/global/political/sanctions/{code} returns empty for unknown country."""
    resp = await client.get("/v3/global/political/sanctions/XXX")
    assert resp.status_code == 200
    assert resp.json() == []


# ── FRED-backed US macro indicators (on-demand producer) ─────────────


async def _seed_fred(session: AsyncSession, code, *, value, yoy_pct=None, qoq=None, yoy=None):
    from src.models.macro import MacroIndicator, MacroValue
    ind = MacroIndicator(
        indicator_id=uuid.uuid4(), indicator_code=code, name=code,
        category="MACRO", frequency="MONTHLY",
    )
    session.add(ind)
    await session.flush()
    session.add(MacroValue(
        indicator_id=ind.indicator_id, observation_date=date(2025, 6, 1),
        vintage_date=date(2025, 6, 15), value=value,
        value_yoy_percent=yoy_pct, value_qoq_annualized=qoq, value_yoy=yoy,
    ))
    await session.flush()


@pytest.mark.asyncio
async def test_global_macro_computed_from_fred(client: AsyncClient, session: AsyncSession):
    """/global/macro/* endpoints populate US GlobalMacroIndicator rows on-demand
    from real FRED macro_values (was empty forever)."""
    await _seed_fred(session, "CPIAUCSL", value=310.0, yoy_pct=3.2)
    await _seed_fred(session, "GDPC1", value=22000.0, qoq=2.5)
    await _seed_fred(session, "T10Y2Y", value=-0.6)  # inverted curve
    await _seed_fred(session, "UNRATE", value=4.1, yoy=0.3)
    await session.commit()

    infl = await client.get("/v3/global/macro/inflation")
    assert infl.status_code == 200
    us_cpi = [r for r in infl.json() if r.get("country_code") == "US"]
    assert us_cpi and us_cpi[0]["value"] == 3.2

    rec = await client.get("/v3/global/macro/recession-probability")
    assert rec.status_code == 200
    us_rec = [r for r in rec.json() if r.get("country_code") == "US"]
    # Inverted yield curve => elevated recession probability computed by engine.
    assert us_rec and us_rec[0]["value"] is not None and us_rec[0]["value"] > 50
