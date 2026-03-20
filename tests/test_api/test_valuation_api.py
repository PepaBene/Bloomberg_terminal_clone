"""Tests for Part 2 valuation & quality API endpoints."""

import uuid
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.analytics import CompositeScore, CompsResult, DCFResult
from src.models.entity import Entity
from src.models.security import Security


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def valuation_security(session: AsyncSession):
    """Seed an entity + security with DCF, Comps, and Composite data."""
    entity = Entity(
        entity_id=uuid.uuid4(),
        legal_name="Valuation Test Corp",
        entity_type="PUBLIC_COMPANY",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
    )
    session.add(entity)
    await session.flush()

    security = Security(
        security_id=uuid.uuid4(),
        name="Valuation Test Corp Common Stock",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity.entity_id,
    )
    session.add(security)
    await session.flush()

    today = date.today()

    # DCF result
    session.add(DCFResult(
        dcf_id=uuid.uuid4(),
        entity_id=entity.entity_id,
        security_id=security.security_id,
        calculation_date=today,
        method="FCFF",
        assumptions={"revenue_growth": [0.10, 0.08], "terminal_growth": 0.025},
        wacc_used=0.0950,
        cost_of_equity=0.1100,
        projected_cashflows=[
            {"year": 2026, "fcff": 85_000_000, "pv": 78_000_000},
            {"year": 2027, "fcff": 90_000_000, "pv": 75_000_000},
        ],
        terminal_value=2_500_000_000.0,
        terminal_method="GORDON_GROWTH",
        terminal_growth_rate=0.0250,
        pv_terminal=1_800_000_000.0,
        terminal_pct_of_ev=0.7500,
        pv_of_fcf=600_000_000.0,
        enterprise_value=2_400_000_000.0,
        net_debt=500_000_000.0,
        equity_value=1_900_000_000.0,
        shares_outstanding=100_000_000.0,
        implied_price=19.00,
        current_price=15.50,
        upside_downside_pct=0.2258,
        sensitivity_grid={"wacc": [0.08, 0.09, 0.10], "growth": [0.02, 0.025, 0.03]},
        data_quality="COMPLETE",
        currency="USD",
    ))

    # Comps result
    session.add(CompsResult(
        comps_id=uuid.uuid4(),
        security_id=security.security_id,
        calculation_date=today,
        peer_security_ids=[str(uuid.uuid4()) for _ in range(5)],
        peer_count=5,
        peer_selection_method="GICS_SECTOR",
        multiples_comparison=[
            {"multiple_name": "PE_TRAILING", "subject_value": 18.5, "peer_median": 22.0, "implied_price": 18.40},
            {"multiple_name": "EV_EBITDA", "subject_value": 12.0, "peer_median": 14.0, "implied_price": 18.10},
        ],
        primary_multiple="PE_TRAILING",
        composite_implied_price=18.25,
        current_price=15.50,
        data_quality="COMPLETE",
    ))

    # Composite scores
    for score_type, score_value, classification in [
        ("EARNINGS_QUALITY", 72.5, "GOOD"),
        ("FINANCIAL_STRENGTH", 81.0, "STRONG"),
        ("DIVIDEND_SAFETY", None, "SAFE"),
        ("VALUE_TRAP", None, "LOW_RISK"),
    ]:
        session.add(CompositeScore(
            score_id=uuid.uuid4(),
            security_id=security.security_id,
            entity_id=entity.entity_id,
            calculation_date=today,
            score_type=score_type,
            score_value=score_value,
            classification=classification,
            components=[
                {"name": "component_1", "raw_value": 0.5, "score": 65.0, "weight": 0.5},
                {"name": "component_2", "raw_value": 0.3, "score": 80.0, "weight": 0.5},
            ],
            data_quality="COMPLETE",
        ))

    await session.flush()
    return security


# ---------------------------------------------------------------------------
# DCF Endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dcf_default_returns_result(client, valuation_security):
    """GET /v2/analytics/dcf/{id}/default returns seeded DCF."""
    resp = await client.get(f"/v2/analytics/dcf/{valuation_security.security_id}/default")
    assert resp.status_code == 200
    data = resp.json()
    assert data["method"] == "FCFF"
    assert data["implied_price"] == pytest.approx(19.0, abs=0.01)
    assert data["enterprise_value"] == pytest.approx(2_400_000_000.0, rel=0.01)


@pytest.mark.asyncio
async def test_dcf_default_404(client):
    """GET /v2/analytics/dcf/{bad_id}/default returns 404."""
    resp = await client.get(f"/v2/analytics/dcf/{uuid.uuid4()}/default")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_dcf_response_has_sensitivity(client, valuation_security):
    """DCF response includes sensitivity_grid."""
    resp = await client.get(f"/v2/analytics/dcf/{valuation_security.security_id}/default")
    data = resp.json()
    assert data["sensitivity_grid"] is not None
    assert "wacc" in data["sensitivity_grid"]


@pytest.mark.asyncio
async def test_dcf_response_has_cashflows(client, valuation_security):
    """DCF response includes projected_cashflows."""
    resp = await client.get(f"/v2/analytics/dcf/{valuation_security.security_id}/default")
    data = resp.json()
    assert isinstance(data["projected_cashflows"], list)
    assert len(data["projected_cashflows"]) == 2


# ---------------------------------------------------------------------------
# Comps Endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_comps_returns_result(client, valuation_security):
    """GET /v2/analytics/comps/{id} returns seeded comps."""
    resp = await client.get(f"/v2/analytics/comps/{valuation_security.security_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["peer_count"] == 5
    assert data["composite_implied_price"] == pytest.approx(18.25, abs=0.01)


@pytest.mark.asyncio
async def test_comps_404(client):
    """GET /v2/analytics/comps/{bad_id} returns 404."""
    resp = await client.get(f"/v2/analytics/comps/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_comps_summary(client, valuation_security):
    """GET /v2/analytics/comps/{id}/summary returns quick view."""
    resp = await client.get(f"/v2/analytics/comps/{valuation_security.security_id}/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["composite_implied_price"] == pytest.approx(18.25, abs=0.01)
    assert data["peer_count"] == 5


# ---------------------------------------------------------------------------
# Composite Scores Endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_composites_all(client, valuation_security):
    """GET /v2/analytics/scores/{id}/composites returns all 4 types."""
    resp = await client.get(f"/v2/analytics/scores/{valuation_security.security_id}/composites")
    assert resp.status_code == 200
    data = resp.json()
    assert data["earnings_quality"] is not None
    assert data["financial_strength"] is not None
    assert data["dividend_safety"] is not None
    assert data["value_trap"] is not None


@pytest.mark.asyncio
async def test_earnings_quality_endpoint(client, valuation_security):
    """GET /v2/analytics/scores/{id}/earnings-quality returns score."""
    resp = await client.get(f"/v2/analytics/scores/{valuation_security.security_id}/earnings-quality")
    assert resp.status_code == 200
    data = resp.json()
    assert data["score_type"] == "EARNINGS_QUALITY"
    assert data["score_value"] == pytest.approx(72.5, abs=0.1)
    assert data["classification"] == "GOOD"
    assert len(data["components"]) == 2


@pytest.mark.asyncio
async def test_financial_strength_endpoint(client, valuation_security):
    """GET /v2/analytics/scores/{id}/financial-strength returns score."""
    resp = await client.get(f"/v2/analytics/scores/{valuation_security.security_id}/financial-strength")
    assert resp.status_code == 200
    data = resp.json()
    assert data["score_type"] == "FINANCIAL_STRENGTH"
    assert data["score_value"] == pytest.approx(81.0, abs=0.1)


@pytest.mark.asyncio
async def test_dividend_safety_endpoint(client, valuation_security):
    """GET /v2/analytics/scores/{id}/dividend-safety returns classification."""
    resp = await client.get(f"/v2/analytics/scores/{valuation_security.security_id}/dividend-safety")
    assert resp.status_code == 200
    data = resp.json()
    assert data["score_type"] == "DIVIDEND_SAFETY"
    assert data["classification"] == "SAFE"


@pytest.mark.asyncio
async def test_value_trap_endpoint(client, valuation_security):
    """GET /v2/analytics/scores/{id}/value-trap returns risk level."""
    resp = await client.get(f"/v2/analytics/scores/{valuation_security.security_id}/value-trap")
    assert resp.status_code == 200
    data = resp.json()
    assert data["score_type"] == "VALUE_TRAP"
    assert data["classification"] == "LOW_RISK"


@pytest.mark.asyncio
async def test_composite_score_404(client):
    """GET /v2/analytics/scores/{bad_id}/earnings-quality returns 404."""
    resp = await client.get(f"/v2/analytics/scores/{uuid.uuid4()}/earnings-quality")
    assert resp.status_code == 404
