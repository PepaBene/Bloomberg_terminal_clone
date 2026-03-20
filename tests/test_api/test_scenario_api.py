"""Tests for the Scenario & Sensitivity API endpoints (E8)."""

import uuid
from datetime import date, datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.analytics import WACCResult
from src.models.entity import Entity
from src.models.fundamentals import (
    BalanceSheet,
    CashFlowStatement,
    FinancialPeriod,
    IncomeStatement,
)
from src.models.security import EODPrice, EquityDetails, Security


# ---------------------------------------------------------------------------
# Fixtures — entity with financials + WACC + price
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def scenario_data(session: AsyncSession):
    now = datetime.now(timezone.utc)
    entity = Entity(
        entity_id=uuid.uuid4(),
        entity_type="PUBLIC_COMPANY",
        legal_name="Scenario API Corp",
        status="ACTIVE",
        source="TEST",
        created_at=now,
        updated_at=now,
    )
    session.add(entity)
    await session.flush()

    security = Security(
        security_id=uuid.uuid4(),
        name="Scenario API Corp Stock",
        short_name="SCNA",
        security_type="COMMON_STOCK",
        asset_class="EQUITY",
        status="ACTIVE",
        issuer_entity_id=entity.entity_id,
        created_at=now,
        updated_at=now,
    )
    session.add(security)
    await session.flush()

    eq = EquityDetails(
        security_id=security.security_id,
        shares_outstanding=50_000_000.0,
    )
    session.add(eq)
    await session.flush()

    # 3 annual periods
    for year, rev, opinc, pretax, ni, tax_exp, eff_tax, da, \
        ta, ca, cl, debt, cash, wc, cfo, capex, cf_da in [
        (2022, 400e6, 60e6, 52e6, 40e6, 12e6, 0.23, 18e6,
         700e6, 200e6, 120e6, 180e6, 50e6, 80e6, 55e6, -25e6, 18e6),
        (2023, 500e6, 80e6, 70e6, 56e6, 14e6, 0.20, 20e6,
         800e6, 250e6, 150e6, 200e6, 60e6, 100e6, 70e6, -30e6, 20e6),
        (2024, 600e6, 110e6, 100e6, 80e6, 20e6, 0.20, 22e6,
         900e6, 300e6, 140e6, 180e6, 80e6, 160e6, 95e6, -35e6, 22e6),
    ]:
        fp = FinancialPeriod(
            period_id=uuid.uuid4(),
            entity_id=entity.entity_id,
            period_end_date=date(year, 12, 31),
            period_type="ANNUAL",
            fiscal_year=year,
        )
        session.add(fp)
        await session.flush()

        session.add(IncomeStatement(
            statement_id=uuid.uuid4(),
            period_id=fp.period_id,
            total_revenue=rev,
            operating_income=opinc,
            pretax_income=pretax,
            net_income=ni,
            income_tax_expense=tax_exp,
            effective_tax_rate=eff_tax,
            depreciation_amortization=da,
        ))
        session.add(BalanceSheet(
            statement_id=uuid.uuid4(),
            period_id=fp.period_id,
            total_assets=ta,
            total_current_assets=ca,
            total_current_liabilities=cl,
            total_debt=debt,
            cash_and_equivalents=cash,
            working_capital=wc,
        ))
        session.add(CashFlowStatement(
            statement_id=uuid.uuid4(),
            period_id=fp.period_id,
            cash_from_operations=cfo,
            capital_expenditures=capex,
            depreciation_amortization=cf_da,
        ))
        await session.flush()

    # WACC
    session.add(WACCResult(
        entity_id=entity.entity_id,
        security_id=security.security_id,
        calculation_date=date(2025, 1, 15),
        wacc=0.10,
        cost_of_equity=0.12,
        risk_free_rate=0.04,
        equity_risk_premium=0.06,
        beta=1.1,
        cost_of_debt_pretax=0.05,
        effective_tax_rate=0.20,
        cost_of_debt_aftertax=0.04,
        debt_weight=0.30,
        equity_weight=0.70,
        market_cap=5e9,
        total_debt=180e6,
        data_quality="COMPLETE",
    ))
    await session.flush()

    # Price
    session.add(EODPrice(
        security_id=security.security_id,
        price_date=date(2025, 3, 14),
        open=99.0,
        high=101.0,
        low=98.5,
        close=100.0,
        close_adjusted=100.0,
        volume=1_000_000,
    ))
    await session.flush()

    return {
        "security_id": security.security_id,
        "entity_id": entity.entity_id,
    }


# ---------------------------------------------------------------------------
# 2D Sensitivity
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sensitivity_2d_200(client, scenario_data):
    resp = await client.post("/v2/analytics/scenario/sensitivity", json={
        "security_id": str(scenario_data["security_id"]),
        "row_variable": "discount_rate",
        "col_variable": "terminal_growth",
        "steps": 5,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["row_variable"] == "discount_rate"
    assert len(data["grid"]) == 5


@pytest.mark.asyncio
async def test_sensitivity_2d_404(client):
    resp = await client.post("/v2/analytics/scenario/sensitivity", json={
        "security_id": str(uuid.uuid4()),
        "row_variable": "discount_rate",
        "col_variable": "terminal_growth",
    })
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 3D Sensitivity
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sensitivity_3d_200(client, scenario_data):
    resp = await client.post("/v2/analytics/scenario/sensitivity/3d", json={
        "security_id": str(scenario_data["security_id"]),
        "fixed_variable": "tax_rate",
        "fixed_values": [0.15, 0.25],
        "row_variable": "discount_rate",
        "col_variable": "terminal_growth",
        "steps": 3,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["tables"]) == 2


# ---------------------------------------------------------------------------
# Tornado
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tornado_200(client, scenario_data):
    resp = await client.post("/v2/analytics/scenario/tornado", json={
        "security_id": str(scenario_data["security_id"]),
        "variables": ["discount_rate", "ebit_margin"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["bars"]) == 2
    assert data["base_case_value"] is not None


# ---------------------------------------------------------------------------
# Shock
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_shock_200(client, scenario_data):
    resp = await client.post("/v2/analytics/scenario/shock", json={
        "security_id": str(scenario_data["security_id"]),
        "shock_vector": {"discount_rate": 0.02},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["shocked_value"] < data["base_case_value"]


# ---------------------------------------------------------------------------
# Pre-built list
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prebuilt_list(client):
    resp = await client.get("/v2/analytics/scenario/shock/prebuilt")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 5
    names = [s["name"] for s in data]
    assert "STAGFLATION" in names
    assert "PANDEMIC_SHOCK" in names


# ---------------------------------------------------------------------------
# Custom Shock
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_custom_shock_200(client, scenario_data):
    resp = await client.post("/v2/analytics/scenario/shock/custom", json={
        "security_id": str(scenario_data["security_id"]),
        "name": "My Scenario",
        "shock_vector": {"discount_rate": 0.01, "ebit_margin": -0.02},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["base_case_value"] is not None
    assert len(data["individual_impacts"]) == 2


# ---------------------------------------------------------------------------
# Breakeven
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_breakeven_200(client, scenario_data):
    # Get base case first to set a reasonable target
    shock_resp = await client.post("/v2/analytics/scenario/shock", json={
        "security_id": str(scenario_data["security_id"]),
        "shock_vector": {},
    })
    base = shock_resp.json()["base_case_value"]

    resp = await client.post("/v2/analytics/scenario/breakeven", json={
        "security_id": str(scenario_data["security_id"]),
        "variable": "discount_rate",
        "target_price": base * 0.90,
        "search_min": 0.06,
        "search_max": 0.20,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "converged" in data
    assert "breakeven_value" in data


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_portfolio_200(client, scenario_data):
    resp = await client.post("/v2/analytics/scenario/portfolio", json={
        "positions": [
            {"security_id": str(scenario_data["security_id"]), "weight": 1.0},
        ],
        "shock_vector": {"discount_rate": 0.02},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_impact"] < 0  # higher discount rate → lower price
    assert len(data["positions"]) == 1


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sensitivity_invalid_steps(client, scenario_data):
    resp = await client.post("/v2/analytics/scenario/sensitivity", json={
        "security_id": str(scenario_data["security_id"]),
        "row_variable": "discount_rate",
        "col_variable": "terminal_growth",
        "steps": 1,  # Below minimum (3)
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_tornado_invalid_swing(client, scenario_data):
    resp = await client.post("/v2/analytics/scenario/tornado", json={
        "security_id": str(scenario_data["security_id"]),
        "swing_pct": 5.0,  # Above maximum (1.0)
    })
    assert resp.status_code == 422
