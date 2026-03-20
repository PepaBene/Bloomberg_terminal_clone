"""Tests for Part 3 screening and flow models."""

import uuid
from datetime import date, datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.flows import FlowAlert, InstitutionalFlowSignal, InstitutionAnalytics
from src.models.screening import SavedScreen
from src.models.entity import Entity
from src.models.security import Security
from src.models.ownership import InstitutionProfile


@pytest_asyncio.fixture
async def base_data(session: AsyncSession):
    """Create entity + security + institution for FK refs."""
    entity = Entity(
        entity_id=uuid.uuid4(),
        legal_name="Model Test Corp",
        entity_type="PUBLIC_COMPANY",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
    )
    session.add(entity)
    await session.flush()

    security = Security(
        security_id=uuid.uuid4(),
        name="Model Test Corp Stock",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity.entity_id,
    )
    session.add(security)

    institution = InstitutionProfile(
        institution_id=uuid.uuid4(),
        institution_name="Test Capital Management",
        institution_type="HEDGE_FUND",
        tier="WHALE",
        aum=50_000_000_000.0,
    )
    session.add(institution)
    await session.flush()
    return entity, security, institution


@pytest.mark.asyncio
async def test_saved_screen_create(session: AsyncSession):
    """SavedScreen round-trips with JSONB definition."""
    screen = SavedScreen(
        name="Test Screen",
        screen_type="CUSTOM",
        definition={
            "filters": {"logic": "AND", "filters": [{"field": "pe_trailing", "op": "LT", "value": 15}]},
        },
        tags=["value", "test"],
    )
    session.add(screen)
    await session.flush()
    assert screen.screen_id is not None
    assert screen.definition["filters"]["logic"] == "AND"
    assert screen.tags == ["value", "test"]


@pytest.mark.asyncio
async def test_flow_signal_create(session: AsyncSession, base_data):
    """InstitutionalFlowSignal persists all fields."""
    _, security, _ = base_data
    signal = InstitutionalFlowSignal(
        security_id=security.security_id,
        report_date=date(2026, 3, 31),
        new_positions_count=5,
        closed_positions_count=2,
        increased_positions_count=10,
        decreased_positions_count=3,
        net_shares_change=500_000.0,
        breadth_score=0.35,
        smart_money_flow=0.60,
        flow_trend_3q="ACCUMULATION",
        data_quality="COMPLETE",
    )
    session.add(signal)
    await session.flush()
    assert signal.signal_id is not None
    assert signal.new_positions_count == 5
    assert signal.flow_trend_3q == "ACCUMULATION"


@pytest.mark.asyncio
async def test_institution_analytics_create(session: AsyncSession, base_data):
    """InstitutionAnalytics persists derived classification."""
    _, _, institution = base_data
    analytics = InstitutionAnalytics(
        institution_id=institution.institution_id,
        report_date=date(2026, 3, 31),
        investment_style="VALUE",
        concentration_score=0.45,
        total_positions=35,
        total_value=12_000_000_000.0,
        top_holdings=[{"security_id": str(uuid.uuid4()), "weight": 0.08}],
        sector_allocation={"45": 0.35, "35": 0.25, "20": 0.20},
    )
    session.add(analytics)
    await session.flush()
    assert analytics.analytics_id is not None
    assert analytics.investment_style == "VALUE"
    assert analytics.sector_allocation["45"] == 0.35


@pytest.mark.asyncio
async def test_flow_alert_create(session: AsyncSession, base_data):
    """FlowAlert persists headline and details JSONB."""
    _, security, institution = base_data
    alert = FlowAlert(
        alert_type="WHALE_MOVE",
        security_id=security.security_id,
        institution_id=institution.institution_id,
        report_date=date(2026, 3, 31),
        headline="Test Capital increased position by 2.5%",
        shares_involved=1_000_000.0,
        value_involved=50_000_000.0,
        percent_of_outstanding=0.025,
        details={"prior_pct": 0.03, "current_pct": 0.055},
        severity="WARNING",
    )
    session.add(alert)
    await session.flush()
    assert alert.alert_id is not None
    assert alert.severity == "WARNING"
    assert alert.details["prior_pct"] == 0.03


@pytest.mark.asyncio
async def test_saved_screen_definition_jsonb(session: AsyncSession):
    """JSONB definition field stores and retrieves nested structure."""
    defn = {
        "universe": "US_EQUITIES",
        "filters": {
            "logic": "AND",
            "filters": [
                {"field": "roe", "op": "GT", "value": 0.15},
                {
                    "logic": "OR",
                    "filters": [
                        {"field": "pe_trailing", "op": "LT", "value": 15},
                        {"field": "ev_ebitda", "op": "LT", "value": 10},
                    ],
                },
            ],
        },
        "ranking": [{"field": "roic", "weight": 0.6}, {"field": "fcf_yield", "weight": 0.4}],
    }
    screen = SavedScreen(
        name="Nested Test",
        screen_type="CUSTOM",
        definition=defn,
    )
    session.add(screen)
    await session.flush()

    # Verify nested structure preserved
    assert screen.definition["filters"]["filters"][1]["logic"] == "OR"
    assert len(screen.definition["ranking"]) == 2
