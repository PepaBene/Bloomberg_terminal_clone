"""Tests for the Institutional Flows API endpoints (E6).

Covers institution profiles, security-level flow analysis,
market-level aggregations, and flow alerts.
"""

import uuid
from datetime import date, datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entity import Entity
from src.models.flows import FlowAlert, InstitutionalFlowSignal
from src.models.ownership import InstitutionalHolding, InstitutionProfile, ShortInterest
from src.models.security import Security


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def flows_data(session: AsyncSession):
    """Seed entity + security + institution + holdings + flow signal + alert."""
    entity = Entity(
        entity_id=uuid.uuid4(),
        legal_name="Flow Test Corp",
        entity_type="PUBLIC_COMPANY",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
        gics_sector="45",
    )
    session.add(entity)
    await session.flush()

    security = Security(
        security_id=uuid.uuid4(),
        name="Flow Test Corp Stock",
        short_name="FLOW",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity.entity_id,
    )
    session.add(security)
    await session.flush()

    institution = InstitutionProfile(
        institution_id=uuid.uuid4(),
        institution_name="Test Whale Capital",
        institution_type="HEDGE_FUND",
        tier="WHALE",
        aum=50_000_000_000.0,
        number_of_holdings=100,
    )
    session.add(institution)

    institution2 = InstitutionProfile(
        institution_id=uuid.uuid4(),
        institution_name="Test Major Fund",
        institution_type="MUTUAL_FUND",
        tier="MAJOR",
        aum=5_000_000_000.0,
        number_of_holdings=200,
    )
    session.add(institution2)
    await session.flush()

    now = datetime.now(timezone.utc)

    # Prior quarter holdings (Q4 2025)
    session.add(InstitutionalHolding(
        institution_id=institution.institution_id,
        security_id=security.security_id,
        report_date=date(2025, 12, 31),
        shares_held=90_000.0,
        market_value=9_000_000.0,
        percent_of_portfolio=0.018,
        percent_of_outstanding=0.045,
        created_at=now,
    ))
    session.add(InstitutionalHolding(
        institution_id=institution2.institution_id,
        security_id=security.security_id,
        report_date=date(2025, 12, 31),
        shares_held=50_000.0,
        market_value=5_000_000.0,
        percent_of_portfolio=0.01,
        percent_of_outstanding=0.025,
        created_at=now,
    ))

    # Current quarter holdings (Q1 2026)
    session.add(InstitutionalHolding(
        institution_id=institution.institution_id,
        security_id=security.security_id,
        report_date=date(2026, 3, 31),
        shares_held=100_000.0,
        market_value=10_000_000.0,
        percent_of_portfolio=0.02,
        percent_of_outstanding=0.05,
        shares_change=10_000.0,
        created_at=now,
    ))
    session.add(InstitutionalHolding(
        institution_id=institution2.institution_id,
        security_id=security.security_id,
        report_date=date(2026, 3, 31),
        shares_held=60_000.0,
        market_value=6_000_000.0,
        percent_of_portfolio=0.012,
        percent_of_outstanding=0.03,
        shares_change=10_000.0,
        created_at=now,
    ))

    # Flow signal
    signal = InstitutionalFlowSignal(
        signal_id=uuid.uuid4(),
        security_id=security.security_id,
        report_date=date(2026, 3, 31),
        new_positions_count=2,
        closed_positions_count=1,
        increased_positions_count=5,
        decreased_positions_count=2,
        net_shares_change=50_000.0,
        net_value_change=5_000_000.0,
        breadth_score=0.30,
        conviction_score=0.65,
        smart_money_flow=0.50,
        whale_net_shares=10_000.0,
        whale_net_value=1_000_000.0,
        flow_trend_3q="ACCUMULATION",
        data_quality="COMPLETE",
    )
    session.add(signal)

    # Short interest
    short = ShortInterest(
        security_id=security.security_id,
        settlement_date=date(2026, 3, 15),
        shares_short=500_000.0,
        short_percent_float=0.08,
        days_to_cover=3.5,
    )
    session.add(short)

    # Flow alert
    alert = FlowAlert(
        alert_id=uuid.uuid4(),
        alert_type="WHALE_MOVE",
        security_id=security.security_id,
        institution_id=institution.institution_id,
        report_date=date(2026, 3, 31),
        headline="Test Whale Capital increased position by 2.5%",
        shares_involved=50_000.0,
        value_involved=5_000_000.0,
        percent_of_outstanding=0.025,
        details={"prior_pct": 0.025, "current_pct": 0.05},
        severity="HIGH",
    )
    session.add(alert)
    await session.flush()

    return entity, security, institution, institution2, signal, alert


# ---------------------------------------------------------------------------
# Institution Profile Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_institution(client, flows_data):
    """GET /v2/analytics/institutions/{id} returns the institution profile."""
    _entity, _security, institution, _inst2, _signal, _alert = flows_data

    response = await client.get(
        f"/v2/analytics/institutions/{institution.institution_id}"
    )
    assert response.status_code == 200

    data = response.json()
    assert data["institution_id"] == str(institution.institution_id)
    assert data["institution_name"] == "Test Whale Capital"
    assert data["institution_type"] == "HEDGE_FUND"
    assert data["tier"] == "WHALE"
    assert data["aum"] == 50_000_000_000.0
    assert data["number_of_holdings"] == 100


@pytest.mark.asyncio
async def test_get_institution_not_found(client):
    """GET /v2/analytics/institutions/{random_uuid} returns 404."""
    fake_id = uuid.uuid4()
    response = await client.get(f"/v2/analytics/institutions/{fake_id}")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Institution Holdings Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_institution_holdings(client, flows_data):
    """GET /v2/analytics/institutions/{id}/holdings returns holdings list."""
    _entity, security, institution, _inst2, _signal, _alert = flows_data

    response = await client.get(
        f"/v2/analytics/institutions/{institution.institution_id}/holdings"
    )
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1

    holding = data[0]
    assert holding["institution_id"] == str(institution.institution_id)
    assert holding["security_id"] == str(security.security_id)
    assert holding["report_date"] == "2026-03-31"
    assert holding["shares_held"] == 100_000.0
    assert holding["market_value"] == 10_000_000.0


# ---------------------------------------------------------------------------
# Security-Level Flow Analysis Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_flow_summary(client, flows_data):
    """GET /v2/analytics/flows/{security_id} returns flow summary."""
    _entity, security, _institution, _inst2, signal, _alert = flows_data

    response = await client.get(
        f"/v2/analytics/flows/{security.security_id}"
    )
    assert response.status_code == 200

    data = response.json()
    assert data["security_id"] == str(security.security_id)
    assert data["report_date"] == "2026-03-31"
    assert data["new_positions"] == 2
    assert data["closed_positions"] == 1
    assert data["increased_positions"] == 5
    assert data["decreased_positions"] == 2
    assert data["net_shares_change"] == 50_000.0
    assert data["breadth_score"] == pytest.approx(0.30, abs=1e-3)
    assert data["smart_money_flow"] == pytest.approx(0.50, abs=1e-3)
    assert data["flow_trend_3q"] == "ACCUMULATION"
    assert data["data_quality"] == "COMPLETE"


@pytest.mark.asyncio
async def test_get_flow_holders(client, flows_data):
    """GET /v2/analytics/flows/{security_id}/holders returns holder list."""
    _entity, security, institution, _inst2, _signal, _alert = flows_data

    response = await client.get(
        f"/v2/analytics/flows/{security.security_id}/holders"
    )
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2  # Two institutions hold this security

    # Results ordered by market_value DESC => whale (10M) first, then major (6M)
    holder = data[0]
    assert holder["institution_id"] == str(institution.institution_id)
    assert holder["institution_name"] == "Test Whale Capital"
    assert holder["institution_type"] == "HEDGE_FUND"
    assert holder["tier"] == "WHALE"
    assert holder["shares_held"] == 100_000.0
    assert holder["market_value"] == 10_000_000.0


@pytest.mark.asyncio
async def test_get_short_interest(client, flows_data):
    """GET /v2/analytics/flows/{security_id}/short-interest returns data."""
    _entity, security, _institution, _inst2, _signal, _alert = flows_data

    response = await client.get(
        f"/v2/analytics/flows/{security.security_id}/short-interest"
    )
    assert response.status_code == 200

    data = response.json()
    assert data["security_id"] == str(security.security_id)
    assert data["settlement_date"] == "2026-03-15"
    assert data["shares_short"] == 500_000.0
    assert data["short_percent_float"] == pytest.approx(0.08, abs=1e-3)
    assert data["days_to_cover"] == pytest.approx(3.5, abs=1e-2)
    assert data["squeeze_potential"] == "LOW"  # 0.08 < 0.10


@pytest.mark.asyncio
async def test_get_flow_history(client, flows_data):
    """GET /v2/analytics/flows/{security_id}/history returns history."""
    _entity, security, _institution, _inst2, signal, _alert = flows_data

    response = await client.get(
        f"/v2/analytics/flows/{security.security_id}/history"
    )
    assert response.status_code == 200

    data = response.json()
    assert data["security_id"] == str(security.security_id)
    assert isinstance(data["data_points"], list)
    assert len(data["data_points"]) >= 1

    point = data["data_points"][0]
    assert point["report_date"] == "2026-03-31"
    assert point["net_shares_change"] == 50_000.0
    assert point["breadth_score"] == pytest.approx(0.30, abs=1e-3)
    assert point["smart_money_flow"] == pytest.approx(0.50, abs=1e-3)
    # holders_count = new(2) + increased(5) + decreased(2) + unchanged(0)
    assert point["holders_count"] == 9


# ---------------------------------------------------------------------------
# Market-Level Aggregation Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_market_flows(client, flows_data):
    """GET /v2/analytics/flows/market returns market-wide summary."""
    _entity, _security, _institution, _inst2, signal, _alert = flows_data

    response = await client.get("/v2/analytics/flows/market")
    assert response.status_code == 200

    data = response.json()
    assert data["report_date"] == "2026-03-31"
    # Our seeded signal: new=2, closed=1
    assert data["total_new_positions"] == 2
    assert data["total_closed_positions"] == 1
    assert data["breadth_score"] == pytest.approx(0.30, abs=1e-3)


# ---------------------------------------------------------------------------
# Institution Filter Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_institutions_by_tier(client, flows_data):
    """GET /v2/analytics/institutions/tiers/WHALE returns matching institutions."""
    _entity, _security, institution, _inst2, _signal, _alert = flows_data

    response = await client.get("/v2/analytics/institutions/tiers/WHALE")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1

    names = [inst["institution_name"] for inst in data]
    assert "Test Whale Capital" in names

    whale = next(i for i in data if i["institution_name"] == "Test Whale Capital")
    assert whale["institution_id"] == str(institution.institution_id)
    assert whale["tier"] == "WHALE"
    assert whale["aum"] == 50_000_000_000.0


# ---------------------------------------------------------------------------
# Alert Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_whale_alerts(client, flows_data):
    """GET /v2/analytics/flows/alerts/whale-moves returns whale alerts."""
    _entity, security, institution, _inst2, _signal, alert = flows_data

    response = await client.get("/v2/analytics/flows/alerts/whale-moves")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1

    whale_alert = next(
        (a for a in data if a["alert_id"] == str(alert.alert_id)), None
    )
    assert whale_alert is not None
    assert whale_alert["alert_type"] == "WHALE_MOVE"
    assert whale_alert["security_id"] == str(security.security_id)
    assert whale_alert["headline"] == "Test Whale Capital increased position by 2.5%"
    assert whale_alert["severity"] == "HIGH"
    assert whale_alert["shares_involved"] == 50_000.0
    assert whale_alert["value_involved"] == 5_000_000.0


# ---------------------------------------------------------------------------
# Flow 404 / Edge Case Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_flow_summary_not_found(client):
    """GET /v2/analytics/flows/{nonexistent_uuid} returns 404."""
    fake_id = uuid.uuid4()
    response = await client.get(f"/v2/analytics/flows/{fake_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_short_interest_not_found(client):
    """GET /v2/analytics/flows/{nonexistent}/short-interest returns 404."""
    fake_id = uuid.uuid4()
    response = await client.get(f"/v2/analytics/flows/{fake_id}/short-interest")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Security Changes Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_security_changes(client, flows_data):
    """GET /v2/analytics/flows/{security_id}/changes returns position changes.

    Two quarters are seeded so the endpoint should detect the increase for
    both institutions between Q4-2025 and Q1-2026.
    """
    _entity, security, institution, institution2, _signal, _alert = flows_data

    response = await client.get(
        f"/v2/analytics/flows/{security.security_id}/changes"
    )
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2  # Both institutions have changes

    # Find institution1's change: 90k -> 100k = +10k (~11.1%)
    inst1_change = next(
        (c for c in data if c["institution_id"] == str(institution.institution_id)),
        None,
    )
    assert inst1_change is not None
    assert inst1_change["change_type"] == "INCREASED"
    assert inst1_change["current_shares"] == 100_000.0
    assert inst1_change["prior_shares"] == 90_000.0

    # Find institution2's change: 50k -> 60k = +10k (20%)
    inst2_change = next(
        (c for c in data if c["institution_id"] == str(institution2.institution_id)),
        None,
    )
    assert inst2_change is not None
    assert inst2_change["change_type"] == "INCREASED"
    assert inst2_change["current_shares"] == 60_000.0
    assert inst2_change["prior_shares"] == 50_000.0


# ---------------------------------------------------------------------------
# Smart Money Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_smart_money(client, flows_data):
    """GET /v2/analytics/flows/smart-money returns top smart money signals."""
    _entity, security, _institution, _inst2, signal, _alert = flows_data

    response = await client.get("/v2/analytics/flows/smart-money")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1

    entry = next(
        (e for e in data if e["security_id"] == str(security.security_id)),
        None,
    )
    assert entry is not None
    assert entry["whale_net_shares"] == 10_000.0
    assert entry["whale_net_value"] == 1_000_000.0
    # smart_money_flow=0.50 > 0.2 => BULLISH
    assert entry["smart_money_signal"] == "BULLISH"


# ---------------------------------------------------------------------------
# Institutions by Type Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_institutions_by_type(client, flows_data):
    """GET /v2/analytics/institutions/types/HEDGE_FUND returns matching institutions."""
    _entity, _security, institution, _inst2, _signal, _alert = flows_data

    response = await client.get("/v2/analytics/institutions/types/HEDGE_FUND")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1

    names = [i["institution_name"] for i in data]
    assert "Test Whale Capital" in names
