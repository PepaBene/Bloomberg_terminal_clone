"""API tests for Portfolio Risk Management endpoints (Pillar 4 Phase 3)."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entity import Entity
from src.models.portfolio import Portfolio
from src.models.portfolio_risk import (
    ConcentrationAnalysis,
    FactorExposureSnapshot,
    PortfolioVarSnapshot,
    PortfolioStressTestResult,
)
from src.models.compliance import ComplianceRule, ComplianceResult, DriftSnapshot
from src.models.position import Position
from src.models.security import EODPrice, Security


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_portfolio(
    session: AsyncSession,
    portfolio_name: str = "Risk API Portfolio",
    **kwargs,
) -> Portfolio:
    defaults = {
        "id": uuid.uuid4(),
        "user_id": "default_user",
        "portfolio_name": portfolio_name,
        "portfolio_type": "REAL",
        "inception_date": date(2025, 1, 1),
        "initial_cash": Decimal("100000.00"),
        "current_cash": Decimal("100000.00"),
    }
    defaults.update(kwargs)
    p = Portfolio(**defaults)
    session.add(p)
    await session.flush()
    return p


async def _seed_var_snapshot(
    session: AsyncSession,
    portfolio_id: uuid.UUID,
    snapshot_date: date = date(2025, 6, 1),
    **kwargs,
) -> PortfolioVarSnapshot:
    defaults = {
        "id": uuid.uuid4(),
        "portfolio_id": portfolio_id,
        "snapshot_date": snapshot_date,
        "var_1d_95": Decimal("-12500.0000"),
        "var_1d_99": Decimal("-18750.0000"),
        "var_10d_95": Decimal("-39528.4000"),
        "var_10d_99": Decimal("-59292.6000"),
        "undiversified_var": Decimal("-15000.0000"),
        "diversification_ratio": Decimal("0.8333"),
        "marginal_var": {"AAPL": -2500, "MSFT": -2000},
        "component_var": {"AAPL": -4000, "MSFT": -3500},
        "incremental_var": {"AAPL": -1500, "MSFT": -1200},
        "portfolio_nav": Decimal("100000.00"),
        "method": "HISTORICAL",
    }
    defaults.update(kwargs)
    snap = PortfolioVarSnapshot(**defaults)
    session.add(snap)
    await session.flush()
    return snap


async def _seed_concentration(
    session: AsyncSession,
    portfolio_id: uuid.UUID,
    snapshot_date: date = date(2025, 6, 1),
    **kwargs,
) -> ConcentrationAnalysis:
    defaults = {
        "id": uuid.uuid4(),
        "portfolio_id": portfolio_id,
        "snapshot_date": snapshot_date,
        "hhi_position": Decimal("0.0850"),
        "hhi_sector": Decimal("0.1200"),
        "largest_position_weight": Decimal("0.1500"),
        "top_5_weight": Decimal("0.4500"),
        "top_10_weight": Decimal("0.6500"),
        "effective_num_positions": Decimal("11.76"),
        "concentration_classification": "MODERATE",
        "sector_detail": [
            {"sector": "Technology", "weight": 0.35, "benchmark_weight": 0.30},
            {"sector": "Healthcare", "weight": 0.15, "benchmark_weight": 0.18},
        ],
        "geographic_detail": [
            {"region": "North America", "weight": 0.75},
            {"region": "Europe", "weight": 0.15},
        ],
        "flags": {"single_name_risk": True},
    }
    defaults.update(kwargs)
    snap = ConcentrationAnalysis(**defaults)
    session.add(snap)
    await session.flush()
    return snap


async def _seed_factor_exposure(
    session: AsyncSession,
    portfolio_id: uuid.UUID,
    snapshot_date: date = date(2025, 6, 1),
    **kwargs,
) -> FactorExposureSnapshot:
    defaults = {
        "id": uuid.uuid4(),
        "portfolio_id": portfolio_id,
        "snapshot_date": snapshot_date,
        "value_exposure": Decimal("0.1200"),
        "growth_exposure": Decimal("0.2500"),
        "momentum_exposure": Decimal("0.0800"),
        "quality_exposure": Decimal("0.1500"),
        "size_exposure": Decimal("-0.0500"),
        "low_vol_exposure": Decimal("0.0300"),
        "benchmark_value": Decimal("0.1000"),
        "benchmark_growth": Decimal("0.2000"),
        "active_exposures": {"value": 0.02, "growth": 0.05},
        "factor_contributions": {"value": 0.003, "growth": 0.005},
        "unintended_flags": {"size": True},
    }
    defaults.update(kwargs)
    snap = FactorExposureSnapshot(**defaults)
    session.add(snap)
    await session.flush()
    return snap


async def _seed_stress_test(
    session: AsyncSession,
    portfolio_id: uuid.UUID,
    snapshot_date: date = date(2025, 6, 1),
    scenario_name: str = "2008_GFC",
    **kwargs,
) -> PortfolioStressTestResult:
    defaults = {
        "id": uuid.uuid4(),
        "portfolio_id": portfolio_id,
        "snapshot_date": snapshot_date,
        "scenario_name": scenario_name,
        "scenario_type": "HISTORICAL",
        "total_pnl_dollar": Decimal("-15000.00"),
        "total_pnl_percent": Decimal("-0.150000"),
        "max_drawdown_pct": Decimal("-0.250000"),
        "recovery_time_months": Decimal("18.0"),
        "per_position_pnl": {"AAPL": -5000, "MSFT": -4000},
        "worst_positions": {"worst": [{"ticker": "AAPL", "pnl": -5000}]},
        "scenario_params": {"equity_shock": -0.40},
    }
    defaults.update(kwargs)
    snap = PortfolioStressTestResult(**defaults)
    session.add(snap)
    await session.flush()
    return snap


async def _seed_compliance_rule(
    session: AsyncSession,
    portfolio_id: uuid.UUID,
    **kwargs,
) -> ComplianceRule:
    defaults = {
        "rule_id": uuid.uuid4(),
        "portfolio_id": portfolio_id,
        "rule_name": "Max Position Weight",
        "rule_type": "POSITION_LIMIT",
        "rule_definition": {"field": "weight", "max": 0.10},
        "threshold": Decimal("0.100000"),
        "comparison": "LTE",
        "severity": "WARNING",
        "is_active": True,
    }
    defaults.update(kwargs)
    rule = ComplianceRule(**defaults)
    session.add(rule)
    await session.flush()
    return rule


async def _seed_compliance_result(
    session: AsyncSession,
    portfolio_id: uuid.UUID,
    rule_id: uuid.UUID,
    check_date: date = date(2025, 6, 1),
    **kwargs,
) -> ComplianceResult:
    defaults = {
        "result_id": uuid.uuid4(),
        "portfolio_id": portfolio_id,
        "rule_id": rule_id,
        "check_date": check_date,
        "status": "PASS",
        "current_value": Decimal("0.085000"),
        "threshold_value": Decimal("0.100000"),
    }
    defaults.update(kwargs)
    cr = ComplianceResult(**defaults)
    session.add(cr)
    await session.flush()
    return cr


async def _seed_drift_snapshot(
    session: AsyncSession,
    portfolio_id: uuid.UUID,
    snapshot_date: date = date(2025, 6, 1),
    **kwargs,
) -> DriftSnapshot:
    defaults = {
        "id": uuid.uuid4(),
        "portfolio_id": portfolio_id,
        "snapshot_date": snapshot_date,
        "total_drift_pct": Decimal("0.0350"),
        "max_position_drift_pct": Decimal("0.0250"),
        "max_sector_drift_pct": Decimal("0.0150"),
        "drift_classification": "LOW",
        "rebalance_needed": False,
        "position_drifts": [
            {"ticker": "AAPL", "target_weight": 0.10, "current_weight": 0.125, "drift_pct": 0.025},
        ],
        "sector_drifts": [
            {"sector": "Technology", "target_weight": 0.30, "current_weight": 0.315, "drift_pct": 0.015},
        ],
        "target_allocation": {"AAPL": 0.10, "MSFT": 0.08},
    }
    defaults.update(kwargs)
    snap = DriftSnapshot(**defaults)
    session.add(snap)
    await session.flush()
    return snap


# ══════════════════════════════════════════════════════════════════════
# Stress Scenarios (static route)
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_list_stress_scenarios(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/risk/scenarios returns available scenarios."""
    resp = await client.get("/v4/portfolios/risk/scenarios")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 4
    names = [s["scenario_name"] for s in data]
    assert "2008_GFC" in names
    assert "2020_COVID" in names


# ══════════════════════════════════════════════════════════════════════
# Risk Dashboard
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_risk_dashboard_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/risk returns empty dashboard when no data."""
    p = await _seed_portfolio(session, portfolio_name="Dashboard Empty")
    resp = await client.get(f"/v4/portfolios/{p.id}/risk")
    assert resp.status_code == 200
    data = resp.json()
    assert data["var_summary"] is None
    assert data["concentration_summary"] is None
    assert data["factor_summary"] is None


@pytest.mark.asyncio
async def test_get_risk_dashboard_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/risk returns full dashboard."""
    p = await _seed_portfolio(session, portfolio_name="Dashboard Full")
    await _seed_var_snapshot(session, p.id)
    await _seed_concentration(session, p.id)
    await _seed_factor_exposure(session, p.id)
    resp = await client.get(f"/v4/portfolios/{p.id}/risk")
    assert resp.status_code == 200
    data = resp.json()
    assert data["var_summary"] is not None
    assert data["concentration_summary"] is not None
    assert data["factor_summary"] is not None


@pytest.mark.asyncio
async def test_risk_dashboard_404(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/risk returns 404 for missing portfolio."""
    resp = await client.get(f"/v4/portfolios/{uuid.uuid4()}/risk")
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════
# VaR
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_var_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/risk/var returns null when no data."""
    p = await _seed_portfolio(session, portfolio_name="VaR Empty")
    resp = await client.get(f"/v4/portfolios/{p.id}/risk/var")
    assert resp.status_code == 200
    assert resp.json() is None


@pytest.mark.asyncio
async def test_get_var_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/risk/var returns VaR snapshot."""
    p = await _seed_portfolio(session, portfolio_name="VaR Data")
    await _seed_var_snapshot(session, p.id, snapshot_date=date(2025, 7, 1))
    resp = await client.get(f"/v4/portfolios/{p.id}/risk/var")
    assert resp.status_code == 200
    data = resp.json()
    assert data["var_1d_95"] is not None
    assert data["var_1d_99"] is not None
    assert data["method"] == "HISTORICAL"


@pytest.mark.asyncio
async def test_get_var_decomposition(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/risk/var/decomposition returns decomposition."""
    p = await _seed_portfolio(session, portfolio_name="VaR Decomp")
    await _seed_var_snapshot(session, p.id, snapshot_date=date(2025, 8, 1))
    resp = await client.get(f"/v4/portfolios/{p.id}/risk/var/decomposition")
    assert resp.status_code == 200
    data = resp.json()
    assert data["marginal_var"] is not None
    assert data["component_var"] is not None


@pytest.mark.asyncio
async def test_get_var_404(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/risk/var returns 404 for missing portfolio."""
    resp = await client.get(f"/v4/portfolios/{uuid.uuid4()}/risk/var")
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════
# Concentration
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_concentration_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/risk/concentration returns null when no data."""
    p = await _seed_portfolio(session, portfolio_name="Conc Empty")
    resp = await client.get(f"/v4/portfolios/{p.id}/risk/concentration")
    assert resp.status_code == 200
    assert resp.json() is None


@pytest.mark.asyncio
async def test_get_concentration_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/risk/concentration returns analysis."""
    p = await _seed_portfolio(session, portfolio_name="Conc Data")
    await _seed_concentration(session, p.id, snapshot_date=date(2025, 9, 1))
    resp = await client.get(f"/v4/portfolios/{p.id}/risk/concentration")
    assert resp.status_code == 200
    data = resp.json()
    assert data["hhi_position"] is not None
    assert data["concentration_classification"] == "MODERATE"


@pytest.mark.asyncio
async def test_get_concentration_sectors(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/risk/concentration/sectors returns sectors."""
    p = await _seed_portfolio(session, portfolio_name="Conc Sectors")
    await _seed_concentration(session, p.id, snapshot_date=date(2025, 10, 1))
    resp = await client.get(f"/v4/portfolios/{p.id}/risk/concentration/sectors")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["sector"] == "Technology"


@pytest.mark.asyncio
async def test_get_concentration_geographic(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/risk/concentration/geographic returns regions."""
    p = await _seed_portfolio(session, portfolio_name="Conc Geo")
    await _seed_concentration(session, p.id, snapshot_date=date(2025, 11, 1))
    resp = await client.get(f"/v4/portfolios/{p.id}/risk/concentration/geographic")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


# ══════════════════════════════════════════════════════════════════════
# Factor Exposure
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_factors_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/risk/factors returns null when no data."""
    p = await _seed_portfolio(session, portfolio_name="Factor Empty")
    resp = await client.get(f"/v4/portfolios/{p.id}/risk/factors")
    assert resp.status_code == 200
    assert resp.json() is None


@pytest.mark.asyncio
async def test_get_factors_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/risk/factors returns factor snapshot."""
    p = await _seed_portfolio(session, portfolio_name="Factor Data")
    await _seed_factor_exposure(session, p.id, snapshot_date=date(2025, 7, 1))
    resp = await client.get(f"/v4/portfolios/{p.id}/risk/factors")
    assert resp.status_code == 200
    data = resp.json()
    assert data["value_exposure"] is not None
    assert data["growth_exposure"] is not None


@pytest.mark.asyncio
async def test_get_factor_history(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/risk/factors/history returns time series."""
    p = await _seed_portfolio(session, portfolio_name="Factor History")
    await _seed_factor_exposure(session, p.id, snapshot_date=date(2025, 8, 1))
    await _seed_factor_exposure(session, p.id, snapshot_date=date(2025, 9, 1))
    resp = await client.get(f"/v4/portfolios/{p.id}/risk/factors/history")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 2


@pytest.mark.asyncio
async def test_get_unintended_factors(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/risk/factors/unintended returns flags."""
    p = await _seed_portfolio(session, portfolio_name="Factor Unintended")
    await _seed_factor_exposure(session, p.id, snapshot_date=date(2025, 10, 1))
    resp = await client.get(f"/v4/portfolios/{p.id}/risk/factors/unintended")
    assert resp.status_code == 200
    data = resp.json()
    assert data["size"] is True


# ══════════════════════════════════════════════════════════════════════
# Stress Testing
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_run_historical_stress_test(client: AsyncClient, session: AsyncSession):
    """POST /v4/portfolios/{id}/risk/stress/historical creates result."""
    p = await _seed_portfolio(session, portfolio_name="Stress Historical")
    resp = await client.post(
        f"/v4/portfolios/{p.id}/risk/stress/historical",
        json={"scenario_name": "2008_GFC"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["scenario_name"] == "2008_GFC"
    assert data["scenario_type"] == "HISTORICAL"
    assert data["total_pnl_dollar"] is not None


@pytest.mark.asyncio
async def test_run_hypothetical_stress_test(client: AsyncClient, session: AsyncSession):
    """POST /v4/portfolios/{id}/risk/stress/hypothetical creates result."""
    p = await _seed_portfolio(session, portfolio_name="Stress Hypothetical")
    resp = await client.post(
        f"/v4/portfolios/{p.id}/risk/stress/hypothetical",
        json={"scenario_name": "CUSTOM_SHOCK", "shocks": {"equity": -0.20}},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["scenario_name"] == "CUSTOM_SHOCK"
    assert data["scenario_type"] == "HYPOTHETICAL"


@pytest.mark.asyncio
async def test_what_if_market_drop_computes_real_projection(client: AsyncClient, session: AsyncSession):
    """POST /v4/portfolios/{id}/what-if -- regression test for the "no
    route exists" gap: the frontend's What-If panel already POSTs
    {scenario} and reads back {projectedNavChange, projectedPnl} (see
    PortfolioDetail.tsx), which always errored. A beta=1.0 equity position
    under "market_drop_10" (-10% equity shock) must show a real -10% NAV
    projection, not null/zero.
    """
    p = await _seed_portfolio(session, portfolio_name="What-If Drop", current_cash=Decimal("0.00"))
    session.add(Position(
        id=uuid.uuid4(), portfolio_id=p.id, ticker="AAPL", status="OPEN",
        market_value=Decimal("15000.00"),
    ))
    await session.flush()

    resp = await client.post(f"/v4/portfolios/{p.id}/what-if", json={"scenario": "market_drop_10"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["projectedNavChange"] == pytest.approx(-0.10, abs=0.001)
    assert data["projectedPnl"] == pytest.approx(-1500.0, abs=1.0)


@pytest.mark.asyncio
async def test_what_if_unmapped_scenario_returns_honest_null(client: AsyncClient, session: AsyncSession):
    """"sector_rotation" has no real per-sector shock model anywhere in
    this codebase -- must return null projections, not a fabricated
    number."""
    p = await _seed_portfolio(session, portfolio_name="What-If Sector")
    session.add(Position(
        id=uuid.uuid4(), portfolio_id=p.id, ticker="AAPL", status="OPEN",
        market_value=Decimal("15000.00"),
    ))
    await session.flush()

    resp = await client.post(f"/v4/portfolios/{p.id}/what-if", json={"scenario": "sector_rotation"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["projectedNavChange"] is None
    assert data["projectedPnl"] is None


@pytest.mark.asyncio
async def test_get_stress_results(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/risk/stress/results returns past results."""
    p = await _seed_portfolio(session, portfolio_name="Stress Results")
    await _seed_stress_test(session, p.id, snapshot_date=date(2025, 7, 1))
    resp = await client.get(f"/v4/portfolios/{p.id}/risk/stress/results")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_stress_test_404(client: AsyncClient, session: AsyncSession):
    """POST /v4/portfolios/{id}/risk/stress/historical returns 404."""
    resp = await client.post(
        f"/v4/portfolios/{uuid.uuid4()}/risk/stress/historical",
        json={"scenario_name": "2008_GFC"},
    )
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════
# Compliance
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_compliance_summary_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/compliance returns empty summary."""
    p = await _seed_portfolio(session, portfolio_name="Compliance Empty")
    resp = await client.get(f"/v4/portfolios/{p.id}/compliance")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_rules"] == 0


@pytest.mark.asyncio
async def test_get_compliance_summary_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/compliance returns summary with rules."""
    p = await _seed_portfolio(session, portfolio_name="Compliance Data")
    rule = await _seed_compliance_rule(session, p.id)
    await _seed_compliance_result(session, p.id, rule.rule_id)
    resp = await client.get(f"/v4/portfolios/{p.id}/compliance")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_rules"] == 1
    assert data["passing"] == 1


@pytest.mark.asyncio
async def test_list_compliance_rules(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/compliance/rules returns rules."""
    p = await _seed_portfolio(session, portfolio_name="Compliance Rules")
    await _seed_compliance_rule(session, p.id)
    resp = await client.get(f"/v4/portfolios/{p.id}/compliance/rules")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1


@pytest.mark.asyncio
async def test_create_compliance_rule(client: AsyncClient, session: AsyncSession):
    """POST /v4/portfolios/{id}/compliance/rules creates a rule."""
    p = await _seed_portfolio(session, portfolio_name="Compliance Create")
    resp = await client.post(
        f"/v4/portfolios/{p.id}/compliance/rules",
        json={
            "rule_name": "Max Sector Weight",
            "rule_type": "SECTOR_LIMIT",
            "rule_definition": {"field": "sector_weight", "sector": "Technology", "max": 0.35},
            "threshold": 0.35,
            "comparison": "LTE",
            "severity": "CRITICAL",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["rule_name"] == "Max Sector Weight"
    assert data["rule_type"] == "SECTOR_LIMIT"
    assert data["threshold"] == 0.35


@pytest.mark.asyncio
async def test_update_compliance_rule(client: AsyncClient, session: AsyncSession):
    """PUT /v4/portfolios/{id}/compliance/rules/{rule_id} updates rule."""
    p = await _seed_portfolio(session, portfolio_name="Compliance Update")
    rule = await _seed_compliance_rule(session, p.id)
    resp = await client.put(
        f"/v4/portfolios/{p.id}/compliance/rules/{rule.rule_id}",
        json={"rule_name": "Updated Name", "severity": "CRITICAL"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["rule_name"] == "Updated Name"
    assert data["severity"] == "CRITICAL"


@pytest.mark.asyncio
async def test_delete_compliance_rule(client: AsyncClient, session: AsyncSession):
    """DELETE /v4/portfolios/{id}/compliance/rules/{rule_id} deletes rule."""
    p = await _seed_portfolio(session, portfolio_name="Compliance Delete")
    rule = await _seed_compliance_rule(session, p.id)
    resp = await client.delete(
        f"/v4/portfolios/{p.id}/compliance/rules/{rule.rule_id}"
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_compliance_rule_404(client: AsyncClient, session: AsyncSession):
    """DELETE /v4/portfolios/{id}/compliance/rules/{rule_id} returns 404."""
    p = await _seed_portfolio(session, portfolio_name="Compliance Del 404")
    resp = await client.delete(
        f"/v4/portfolios/{p.id}/compliance/rules/{uuid.uuid4()}"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_compliance_results(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/compliance/results returns history."""
    p = await _seed_portfolio(session, portfolio_name="Compliance Results")
    rule = await _seed_compliance_rule(session, p.id)
    await _seed_compliance_result(session, p.id, rule.rule_id, check_date=date(2025, 7, 1))
    resp = await client.get(f"/v4/portfolios/{p.id}/compliance/results")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_pre_trade_check_approved(client: AsyncClient, session: AsyncSession):
    """POST /v4/portfolios/{id}/compliance/pre-trade-check returns approved."""
    p = await _seed_portfolio(session, portfolio_name="Pre-trade Approved")
    resp = await client.post(
        f"/v4/portfolios/{p.id}/compliance/pre-trade-check",
        json={"ticker": "AAPL", "action": "BUY", "shares": 10, "price": 150.0},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["approved"] is True
    assert data["violations"] == []


@pytest.mark.asyncio
async def test_pre_trade_check_violation(client: AsyncClient, session: AsyncSession):
    """POST /v4/portfolios/{id}/compliance/pre-trade-check returns violation."""
    p = await _seed_portfolio(session, portfolio_name="Pre-trade Violation")
    await _seed_compliance_rule(
        session, p.id,
        rule_type="POSITION_LIMIT",
        threshold=Decimal("1000.000000"),
    )
    resp = await client.post(
        f"/v4/portfolios/{p.id}/compliance/pre-trade-check",
        json={"ticker": "AAPL", "action": "BUY", "shares": 100, "price": 150.0},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["approved"] is False
    assert len(data["violations"]) >= 1


@pytest.mark.asyncio
async def test_compliance_404(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/compliance returns 404 for missing portfolio."""
    resp = await client.get(f"/v4/portfolios/{uuid.uuid4()}/compliance")
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════
# Drift
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_drift_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/drift returns null when no data."""
    p = await _seed_portfolio(session, portfolio_name="Drift Empty")
    resp = await client.get(f"/v4/portfolios/{p.id}/drift")
    assert resp.status_code == 200
    assert resp.json() is None


@pytest.mark.asyncio
async def test_get_drift_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/drift returns drift analysis."""
    p = await _seed_portfolio(session, portfolio_name="Drift Data")
    await _seed_drift_snapshot(session, p.id, snapshot_date=date(2025, 7, 1))
    resp = await client.get(f"/v4/portfolios/{p.id}/drift")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_drift_pct"] is not None
    assert data["drift_classification"] == "LOW"
    assert len(data["position_drifts"]) >= 1


@pytest.mark.asyncio
async def test_get_drift_history(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/drift/history returns time series."""
    p = await _seed_portfolio(session, portfolio_name="Drift History")
    await _seed_drift_snapshot(session, p.id, snapshot_date=date(2025, 8, 1))
    await _seed_drift_snapshot(session, p.id, snapshot_date=date(2025, 9, 1))
    resp = await client.get(f"/v4/portfolios/{p.id}/drift/history")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 2


@pytest.mark.asyncio
async def test_get_rebalance_suggestions_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/drift/rebalance returns empty when no drift."""
    p = await _seed_portfolio(session, portfolio_name="Rebalance Empty")
    resp = await client.get(f"/v4/portfolios/{p.id}/drift/rebalance")
    assert resp.status_code == 200
    data = resp.json()
    assert data["rebalance_needed"] is False


@pytest.mark.asyncio
async def test_get_rebalance_suggestions_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/drift/rebalance returns suggestions."""
    p = await _seed_portfolio(session, portfolio_name="Rebalance Data")
    await _seed_drift_snapshot(
        session, p.id,
        snapshot_date=date(2025, 10, 1),
        rebalance_needed=True,
        position_drifts=[
            {"ticker": "AAPL", "target_weight": 0.10, "current_weight": 0.15, "drift_pct": 0.05},
            {"ticker": "MSFT", "target_weight": 0.08, "current_weight": 0.06, "drift_pct": -0.03},
        ],
    )
    resp = await client.get(f"/v4/portfolios/{p.id}/drift/rebalance")
    assert resp.status_code == 200
    data = resp.json()
    assert data["rebalance_needed"] is True
    assert len(data["suggestions"]) >= 1


@pytest.mark.asyncio
async def test_set_target_allocation(client: AsyncClient, session: AsyncSession):
    """POST /v4/portfolios/{id}/drift/target sets target allocation and
    computes REAL drift against current holdings.

    Regression test for the "fabricates zeros" bug (DEEP_AUDIT_2026-07-16
    Dimension 3): this endpoint used to hardcode every drift metric to
    0.0/"NONE" no matter what the portfolio actually held. AAPL/MSFT are
    seeded far above their targets (60%/40% of NAV vs. 10%/8% targets) and
    GOOG isn't held at all vs. a 7% target, so a real computation must show
    large SELL/BUY drift, not a fabricated "no drift" result.
    """
    p = await _seed_portfolio(session, portfolio_name="Drift Target", current_cash=Decimal("0.00"))
    session.add_all([
        Position(id=uuid.uuid4(), portfolio_id=p.id, ticker="AAPL", status="OPEN", market_value=Decimal("12000.00")),
        Position(id=uuid.uuid4(), portfolio_id=p.id, ticker="MSFT", status="OPEN", market_value=Decimal("8000.00")),
    ])
    await session.flush()

    resp = await client.post(
        f"/v4/portfolios/{p.id}/drift/target",
        json={"AAPL": 0.10, "MSFT": 0.08, "GOOG": 0.07},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["target_allocation"]["AAPL"] == 0.10
    assert data["drift_classification"] == "CRITICAL"
    assert data["rebalance_needed"] is True
    assert data["total_drift_pct"] == pytest.approx(44.5, abs=0.01)
    by_ticker = {d["ticker"]: d for d in data["position_drifts"]}
    assert by_ticker["AAPL"]["current_weight"] == pytest.approx(60.0)
    assert by_ticker["GOOG"]["current_weight"] == pytest.approx(0.0)
    assert by_ticker["GOOG"]["target_weight"] == pytest.approx(7.0)


@pytest.mark.asyncio
async def test_drift_404(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/drift returns 404 for missing portfolio."""
    resp = await client.get(f"/v4/portfolios/{uuid.uuid4()}/drift")
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════
# Trade List
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_trade_list_no_target_is_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/trade-list with no target allocation set
    returns an honest empty list, not a fabricated one."""
    p = await _seed_portfolio(session, portfolio_name="Trade List No Target")
    resp = await client.get(f"/v4/portfolios/{p.id}/trade-list")
    assert resp.status_code == 200
    data = resp.json()
    assert data["orders"] == []
    assert data["summary"]["total_orders"] == 0


@pytest.mark.asyncio
async def test_trade_list_generates_real_sell_order(client: AsyncClient, session: AsyncSession):
    """GET /v4/portfolios/{id}/trade-list computes a real sized order from
    drift_engine's rebalance suggestion + a real EOD price.

    AAPL is 100% of NAV but the target is 50% -> a real SELL of half the
    position, sized in whole shares against today's $150 close.
    """
    entity = Entity(
        entity_id=uuid.uuid4(), legal_name="Apple Inc", entity_type="PUBLIC_COMPANY",
        status="ACTIVE", source="TEST",
    )
    session.add(entity)
    await session.flush()
    security = Security(
        security_id=uuid.uuid4(), name="Apple Inc Stock", security_type="COMMON_STOCK",
        asset_class="EQUITY", status="ACTIVE", issuer_entity_id=entity.entity_id,
    )
    session.add(security)
    session.add(EODPrice(
        security_id=security.security_id, price_date=date.today(), close=Decimal("150.00"), source="TEST",
    ))
    await session.flush()

    p = await _seed_portfolio(session, portfolio_name="Trade List Sell", current_cash=Decimal("0.00"))
    session.add(Position(
        id=uuid.uuid4(), portfolio_id=p.id, ticker="AAPL", status="OPEN",
        security_id=security.security_id, market_value=Decimal("15000.00"),
    ))
    await _seed_drift_snapshot(session, p.id, target_allocation={"AAPL": 0.50})
    await session.flush()

    resp = await client.get(f"/v4/portfolios/{p.id}/trade-list")
    assert resp.status_code == 200
    data = resp.json()

    assert data["summary"]["total_orders"] == 1
    order = data["orders"][0]
    assert order["ticker"] == "AAPL"
    assert order["action"] == "SELL"
    assert order["shares"] == 50
    assert order["notional_amount"] == pytest.approx(7500.0)


@pytest.mark.asyncio
async def test_trade_list_csv_format(client: AsyncClient, session: AsyncSession):
    """GET .../trade-list?format=csv returns broker-compatible CSV."""
    p = await _seed_portfolio(session, portfolio_name="Trade List CSV")
    resp = await client.get(f"/v4/portfolios/{p.id}/trade-list?format=csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "ticker,side,quantity" in resp.text
