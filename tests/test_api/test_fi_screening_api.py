"""Tests for Pillar 2 FI Supplement -- Part 6: FI Screening & Scenarios API.

Covers all five endpoints:
- POST /v2/analytics/bonds/screen
- GET  /v2/analytics/bonds/rate-scenarios
- POST /v2/analytics/bonds/rate-scenario/{scenario_id}
- POST /v2/analytics/bonds/sensitivity
- POST /v2/analytics/bonds/scenario-analysis
"""

import uuid
from datetime import date

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.corporate_bond import BondEODPrice, CorporateBond
from src.models.entity import Entity


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def seeded_bonds(session: AsyncSession, client: AsyncClient):
    """Seed the database with a few corporate bonds and EOD prices.

    Returns (client, cusips) for convenience.
    """
    # Need an entity for FK
    entity = Entity(
        entity_id=uuid.uuid4(),
        legal_name="FI Screening Test Issuer",
        entity_type="PUBLIC_COMPANY",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
    )
    session.add(entity)
    await session.flush()

    bond1 = CorporateBond(
        cusip="TEST00001",
        name="Test IG Bond 5% 2030",
        issuer_entity_id=entity.entity_id,
        issuer_name="Test IG Corp",
        coupon_rate=5.0,
        coupon_frequency=2,
        maturity_date=date(2030, 6, 15),
        issue_date=date(2020, 6, 15),
        seniority="SENIOR_UNSECURED",
        is_callable=False,
        initial_rating_sp="A",
        is_investment_grade=True,
        outstanding_amount=500_000_000,
    )
    bond2 = CorporateBond(
        cusip="TEST00002",
        name="Test HY Bond 8% 2028",
        issuer_entity_id=entity.entity_id,
        issuer_name="Test HY Corp",
        coupon_rate=8.0,
        coupon_frequency=2,
        maturity_date=date(2028, 3, 1),
        issue_date=date(2021, 3, 1),
        seniority="SENIOR_SECURED",
        is_callable=True,
        initial_rating_sp="BB",
        is_investment_grade=False,
        outstanding_amount=250_000_000,
    )
    session.add(bond1)
    session.add(bond2)
    await session.flush()

    # EOD prices (keyed by bond_id)
    eod1 = BondEODPrice(
        bond_id=bond1.bond_id,
        price_date=date(2025, 1, 15),
        yield_to_maturity=5.25,
        yield_to_worst=5.10,
        g_spread_bps=120,
        liquidity_score=8,
    )
    eod2 = BondEODPrice(
        bond_id=bond2.bond_id,
        price_date=date(2025, 1, 15),
        yield_to_maturity=9.00,
        yield_to_worst=8.75,
        g_spread_bps=400,
        liquidity_score=4,
    )
    session.add(eod1)
    session.add(eod2)
    await session.flush()

    return client, ["TEST00001", "TEST00002"]


# ---------------------------------------------------------------------------
# POST /bonds/screen
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_screen_bonds_no_filters(seeded_bonds):
    """Screening with no filters returns all bonds."""
    client, cusips = seeded_bonds
    resp = await client.post(
        "/v2/analytics/bonds/screen",
        json={"filters": [], "sort_by": "spread_bps", "ascending": False, "limit": 50},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_screen_bonds_with_spread_filter(seeded_bonds):
    """Filtering spread >= 200 should return only the HY bond."""
    client, _ = seeded_bonds
    resp = await client.post(
        "/v2/analytics/bonds/screen",
        json={
            "filters": [{"field": "spread_bps", "op": "GTE", "value": 200}],
            "sort_by": "spread_bps",
            "ascending": False,
            "limit": 50,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["results"][0]["cusip"] == "TEST00002"


@pytest.mark.asyncio
async def test_screen_bonds_ig_only(seeded_bonds):
    """Filtering investment-grade only should return TEST00001."""
    client, _ = seeded_bonds
    resp = await client.post(
        "/v2/analytics/bonds/screen",
        json={
            "filters": [{"field": "is_investment_grade", "op": "EQ", "value": True}],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["results"][0]["cusip"] == "TEST00001"


# ---------------------------------------------------------------------------
# GET /bonds/rate-scenarios
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_rate_scenarios(client: AsyncClient):
    """Should return all four FI rate scenarios."""
    resp = await client.get("/v2/analytics/bonds/rate-scenarios")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["scenarios"]) == 4
    ids = {s["scenario_id"] for s in data["scenarios"]}
    assert "BOND_MASSACRE_1994" in ids
    assert "BULL_RALLY_2019" in ids


# ---------------------------------------------------------------------------
# POST /bonds/rate-scenario/{scenario_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_rate_scenario(client: AsyncClient):
    """Apply 1994 Bond Massacre to a simple portfolio."""
    resp = await client.post(
        "/v2/analytics/bonds/rate-scenario/BOND_MASSACRE_1994",
        json={
            "positions": [
                {
                    "cusip": "BOND_A",
                    "market_value": 1_000_000,
                    "modified_duration": 5.0,
                    "convexity": 30.0,
                    "spread_duration": 5.0,
                    "is_investment_grade": True,
                },
            ],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["scenario_id"] == "BOND_MASSACRE_1994"
    assert data["total_pnl"] < 0
    assert len(data["by_position"]) == 1


@pytest.mark.asyncio
async def test_apply_unknown_scenario_404(client: AsyncClient):
    """Unknown scenario should return 404."""
    resp = await client.post(
        "/v2/analytics/bonds/rate-scenario/NONEXISTENT",
        json={
            "positions": [
                {"market_value": 1_000_000, "modified_duration": 5.0},
            ],
        },
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /bonds/sensitivity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sensitivity_1d(client: AsyncClient):
    """1D sensitivity table for yield shifts."""
    resp = await client.post(
        "/v2/analytics/bonds/sensitivity",
        json={
            "base_price": 100.0,
            "modified_duration": 5.0,
            "convexity": 30.0,
            "var1_name": "yield_shift_bps",
            "var1_range": [-100, 0, 100],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["var1_name"] == "yield_shift_bps"
    assert data["var2_name"] is None
    assert len(data["results"]) == 3
    # Zero shift should be close to base price
    zero_cell = [r for r in data["results"] if r["var1_value"] == 0][0]
    assert abs(zero_cell["price"] - 100.0) < 0.01


@pytest.mark.asyncio
async def test_sensitivity_2d(client: AsyncClient):
    """2D sensitivity table (yield x spread)."""
    resp = await client.post(
        "/v2/analytics/bonds/sensitivity",
        json={
            "base_price": 100.0,
            "modified_duration": 5.0,
            "convexity": 30.0,
            "var1_name": "yield_shift_bps",
            "var1_range": [-50, 0, 50],
            "var2_name": "spread_shift_bps",
            "var2_range": [-25, 0, 25],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["var2_name"] == "spread_shift_bps"
    assert len(data["results"]) == 9  # 3 x 3


# ---------------------------------------------------------------------------
# POST /bonds/scenario-analysis
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_analysis(client: AsyncClient):
    """Multi-variable scenario shift endpoint."""
    resp = await client.post(
        "/v2/analytics/bonds/scenario-analysis",
        json={
            "positions": [
                {
                    "cusip": "BOND_X",
                    "market_value": 2_000_000,
                    "modified_duration": 6.0,
                    "convexity": 40.0,
                    "spread_duration": 5.0,
                },
            ],
            "yield_shift_bps": 100,
            "spread_shift_bps": 50,
            "rating_migration_notches": 1,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["position_count"] == 1
    assert data["total_pnl"] < 0  # rates up + spreads wider + downgrade -> loss
    assert data["yield_impact"] < 0
    assert data["spread_impact"] < 0
    assert data["migration_impact"] < 0
