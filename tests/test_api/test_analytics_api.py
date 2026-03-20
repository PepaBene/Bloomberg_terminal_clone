"""Tests for the Pillar 2 Analytics API endpoints."""

import uuid
from datetime import date, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.analytics import (
    AnalyticsResult,
    CalculationLineage,
    DuPontDecomposition,
    MultipleTimeSeries,
    WACCResult,
)
from src.models.entity import Entity
from src.models.security import Security


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def seeded_analytics(session: AsyncSession):
    """Seed a security with pre-computed analytics results."""
    entity = Entity(
        entity_id=uuid.uuid4(),
        legal_name="Analytics API Test Corp",
        entity_type="PUBLIC_COMPANY",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
    )
    session.add(entity)
    await session.flush()

    security = Security(
        security_id=uuid.uuid4(),
        name="Analytics API Test Corp Common Stock",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity.entity_id,
    )
    session.add(security)
    await session.flush()

    today = date.today()

    # Seed some E1 ratio results
    ratios = [
        ("gross_margin", "PROFITABILITY", 0.45),
        ("operating_margin", "PROFITABILITY", 0.22),
        ("net_margin", "PROFITABILITY", 0.15),
        ("roe", "PROFITABILITY", 0.18),
        ("debt_to_equity", "LEVERAGE", 0.75),
        ("current_ratio", "LEVERAGE", 1.5),
        ("asset_turnover", "EFFICIENCY", 0.8),
        ("revenue_yoy", "GROWTH", 0.12),
        ("eps_basic", "PER_SHARE", 3.50),
    ]
    for name, category, value in ratios:
        session.add(AnalyticsResult(
            result_id=uuid.uuid4(),
            security_id=security.security_id,
            entity_id=entity.entity_id,
            engine_id="E1",
            metric_name=name,
            metric_category=category,
            value=value,
            period="TTM",
            as_of_date=today,
        ))

    # TTM metrics
    for name, val in [("total_revenue", 400_000_000), ("net_income", 60_000_000)]:
        session.add(AnalyticsResult(
            result_id=uuid.uuid4(),
            security_id=security.security_id,
            entity_id=entity.entity_id,
            engine_id="E1",
            metric_name=name,
            metric_category="INCOME_STATEMENT",
            value=val,
            period="TTM",
            as_of_date=today,
        ))

    # E2 multiples
    for name, val in [("PE_TRAILING", 18.5), ("EV_EBITDA", 12.3), ("DIVIDEND_YIELD", 0.02)]:
        session.add(AnalyticsResult(
            result_id=uuid.uuid4(),
            security_id=security.security_id,
            entity_id=entity.entity_id,
            engine_id="E2",
            metric_name=name,
            metric_category="VALUATION",
            value=val,
            period="TTM",
            as_of_date=today,
        ))

    # DuPont decomposition
    session.add(DuPontDecomposition(
        decomposition_id=uuid.uuid4(),
        entity_id=entity.entity_id,
        security_id=security.security_id,
        period="TTM",
        period_end_date=today,
        model_type="THREE_FACTOR",
        roe=0.18,
        net_profit_margin=0.15,
        asset_turnover=0.80,
        equity_multiplier=1.50,
    ))

    # WACC result
    session.add(WACCResult(
        wacc_id=uuid.uuid4(),
        entity_id=entity.entity_id,
        security_id=security.security_id,
        calculation_date=today,
        risk_free_rate=0.0425,
        equity_risk_premium=0.055,
        beta=1.15,
        cost_of_equity=0.106,
        cost_of_debt_pretax=0.05,
        effective_tax_rate=0.21,
        cost_of_debt_aftertax=0.0395,
        debt_weight=0.30,
        equity_weight=0.70,
        wacc=0.086,
        market_cap=3_500_000_000.0,
        total_debt=1_500_000_000.0,
    ))

    # Lineage entry
    session.add(CalculationLineage(
        lineage_id=uuid.uuid4(),
        security_id=security.security_id,
        entity_id=entity.entity_id,
        engine_id="E1",
        engine_version="1.0.0",
        output_metric="gross_margin",
        output_value=0.45,
        period="TTM",
        calculation_formula="gross_profit / total_revenue",
        inputs=[
            {"name": "gross_profit", "source": "pillar_1.fundamentals", "value": 180000000},
            {"name": "total_revenue", "source": "pillar_1.fundamentals", "value": 400000000},
        ],
    ))

    await session.flush()
    return security


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_all_ratios(client, seeded_analytics):
    """GET /v2/analytics/ratios/{id} returns grouped ratios."""
    resp = await client.get(f"/v2/analytics/ratios/{seeded_analytics.security_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["security_id"] == str(seeded_analytics.security_id)
    assert "profitability" in data
    assert "gross_margin" in data["profitability"]
    assert data["profitability"]["gross_margin"] == pytest.approx(0.45)


@pytest.mark.asyncio
async def test_get_ratios_by_category(client, seeded_analytics):
    """GET /v2/analytics/ratios/{id}/profitability returns category ratios."""
    resp = await client.get(f"/v2/analytics/ratios/{seeded_analytics.security_id}/profitability")
    assert resp.status_code == 200
    data = resp.json()
    assert "gross_margin" in data
    assert data["gross_margin"] == pytest.approx(0.45)


@pytest.mark.asyncio
async def test_get_ratios_404(client):
    """GET /v2/analytics/ratios/{bad_id} returns 404."""
    resp = await client.get(f"/v2/analytics/ratios/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_ttm(client, seeded_analytics):
    """GET /v2/analytics/ttm/{id} returns TTM metrics."""
    resp = await client.get(f"/v2/analytics/ttm/{seeded_analytics.security_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "metrics" in data
    assert "total_revenue" in data["metrics"]


@pytest.mark.asyncio
async def test_get_dupont(client, seeded_analytics):
    """GET /v2/analytics/dupont/{id} returns DuPont decomposition."""
    resp = await client.get(f"/v2/analytics/dupont/{seeded_analytics.security_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["model_type"] == "THREE_FACTOR"
    assert data[0]["roe"] == pytest.approx(0.18)


@pytest.mark.asyncio
async def test_get_multiples(client, seeded_analytics):
    """GET /v2/analytics/multiples/{id} returns valuation multiples."""
    resp = await client.get(f"/v2/analytics/multiples/{seeded_analytics.security_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "multiples" in data
    assert "PE_TRAILING" in data["multiples"]
    assert data["multiples"]["PE_TRAILING"] == pytest.approx(18.5)


@pytest.mark.asyncio
async def test_get_wacc(client, seeded_analytics):
    """GET /v2/analytics/wacc/{id} returns WACC with components."""
    resp = await client.get(f"/v2/analytics/wacc/{seeded_analytics.security_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["wacc"] == pytest.approx(0.086)
    assert data["beta"] == pytest.approx(1.15)
    assert data["cost_of_equity"] == pytest.approx(0.106)


@pytest.mark.asyncio
async def test_get_wacc_components(client, seeded_analytics):
    """GET /v2/analytics/wacc/{id}/components returns detailed breakdown."""
    resp = await client.get(f"/v2/analytics/wacc/{seeded_analytics.security_id}/components")
    assert resp.status_code == 200
    data = resp.json()
    assert "risk_free_rate" in data
    assert "equity_risk_premium" in data
    assert "debt_weight" in data


@pytest.mark.asyncio
async def test_get_wacc_404(client):
    """GET /v2/analytics/wacc/{bad_id} returns 404."""
    resp = await client.get(f"/v2/analytics/wacc/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_lineage(client, seeded_analytics):
    """GET /v2/analytics/audit/{id}/{metric} returns lineage."""
    resp = await client.get(
        f"/v2/analytics/audit/{seeded_analytics.security_id}/gross_margin"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["output_metric"] == "gross_margin"
    assert data["output_value"] == pytest.approx(0.45)
    assert len(data["inputs"]) == 2
    assert data["calculation_formula"] == "gross_profit / total_revenue"


@pytest.mark.asyncio
async def test_get_lineage_404(client, seeded_analytics):
    """GET /v2/analytics/audit/{id}/nonexistent returns 404."""
    resp = await client.get(
        f"/v2/analytics/audit/{seeded_analytics.security_id}/nonexistent_metric"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_bulk_ratios(client, seeded_analytics):
    """POST /v2/analytics/ratios/bulk returns ratios for multiple securities."""
    resp = await client.post(
        "/v2/analytics/ratios/bulk",
        json={
            "security_ids": [str(seeded_analytics.security_id)],
            "categories": ["PROFITABILITY"],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert str(seeded_analytics.security_id) in data


@pytest.mark.asyncio
async def test_dupont_history(client, seeded_analytics):
    """GET /v2/analytics/dupont/{id}/history returns decomposition history."""
    resp = await client.get(
        f"/v2/analytics/dupont/{seeded_analytics.security_id}/history"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "decompositions" in data
