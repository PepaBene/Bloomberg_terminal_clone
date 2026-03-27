"""Tests for Pillar 4 Phase 3: Portfolio risk, compliance, and drift models."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.models.portfolio import Portfolio
from src.models.portfolio_risk import (
    ConcentrationAnalysis,
    FactorExposureSnapshot,
    PortfolioVarSnapshot,
    PortfolioStressTestResult,
)
from src.models.compliance import ComplianceRule, ComplianceResult, DriftSnapshot


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_portfolio(
    session,
    user_id: str = "test-user",
    portfolio_name: str = "Risk Test Portfolio",
    **kwargs,
) -> Portfolio:
    defaults = {
        "id": uuid.uuid4(),
        "user_id": user_id,
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
    session,
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
    session,
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
        "hhi_industry": Decimal("0.0950"),
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
    session,
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
        "benchmark_momentum": Decimal("0.0500"),
        "benchmark_quality": Decimal("0.1200"),
        "benchmark_size": Decimal("0.0000"),
        "benchmark_low_vol": Decimal("0.0200"),
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
    session,
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
    session,
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
    session,
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
        "breach_positions": None,
        "notes": "All positions within limits",
    }
    defaults.update(kwargs)
    result = ComplianceResult(**defaults)
    session.add(result)
    await session.flush()
    return result


async def _seed_drift_snapshot(
    session,
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
# PortfolioVarSnapshot
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_var_snapshot(session):
    """Create a PortfolioVarSnapshot with all fields."""
    p = await _seed_portfolio(session, portfolio_name="VaR Create")
    snap = await _seed_var_snapshot(session, p.id)
    result = await session.execute(
        select(PortfolioVarSnapshot).where(PortfolioVarSnapshot.id == snap.id)
    )
    fetched = result.scalar_one()
    assert fetched.portfolio_id == p.id
    assert fetched.var_1d_95 == Decimal("-12500.0000")
    assert fetched.var_1d_99 == Decimal("-18750.0000")
    assert fetched.method == "HISTORICAL"


@pytest.mark.asyncio
async def test_var_snapshot_unique_constraint(session):
    """Duplicate (portfolio_id, snapshot_date) raises IntegrityError."""
    p = await _seed_portfolio(session, portfolio_name="VaR Unique")
    await _seed_var_snapshot(session, p.id, snapshot_date=date(2025, 7, 1))
    session.add(PortfolioVarSnapshot(
        id=uuid.uuid4(),
        portfolio_id=p.id,
        snapshot_date=date(2025, 7, 1),
    ))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_var_snapshot_jsonb_round_trip(session):
    """JSONB fields round-trip correctly."""
    p = await _seed_portfolio(session, portfolio_name="VaR JSONB")
    snap = await _seed_var_snapshot(session, p.id, snapshot_date=date(2025, 8, 1))
    result = await session.execute(
        select(PortfolioVarSnapshot).where(PortfolioVarSnapshot.id == snap.id)
    )
    fetched = result.scalar_one()
    assert fetched.marginal_var["AAPL"] == -2500
    assert fetched.component_var["MSFT"] == -3500
    assert fetched.incremental_var["AAPL"] == -1500


# ══════════════════════════════════════════════════════════════════════
# ConcentrationAnalysis
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_concentration(session):
    """Create a ConcentrationAnalysis with all fields."""
    p = await _seed_portfolio(session, portfolio_name="Conc Create")
    snap = await _seed_concentration(session, p.id)
    result = await session.execute(
        select(ConcentrationAnalysis).where(ConcentrationAnalysis.id == snap.id)
    )
    fetched = result.scalar_one()
    assert fetched.hhi_position == Decimal("0.0850")
    assert fetched.concentration_classification == "MODERATE"


@pytest.mark.asyncio
async def test_concentration_unique_constraint(session):
    """Duplicate (portfolio_id, snapshot_date) raises IntegrityError."""
    p = await _seed_portfolio(session, portfolio_name="Conc Unique")
    await _seed_concentration(session, p.id, snapshot_date=date(2025, 7, 1))
    session.add(ConcentrationAnalysis(
        id=uuid.uuid4(),
        portfolio_id=p.id,
        snapshot_date=date(2025, 7, 1),
    ))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_concentration_jsonb_sector_detail(session):
    """sector_detail JSONB round-trips correctly."""
    p = await _seed_portfolio(session, portfolio_name="Conc JSONB")
    snap = await _seed_concentration(session, p.id, snapshot_date=date(2025, 9, 1))
    result = await session.execute(
        select(ConcentrationAnalysis).where(ConcentrationAnalysis.id == snap.id)
    )
    fetched = result.scalar_one()
    assert len(fetched.sector_detail) == 2
    assert fetched.sector_detail[0]["sector"] == "Technology"


# ══════════════════════════════════════════════════════════════════════
# FactorExposureSnapshot
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_factor_exposure(session):
    """Create a FactorExposureSnapshot with all fields."""
    p = await _seed_portfolio(session, portfolio_name="Factor Create")
    snap = await _seed_factor_exposure(session, p.id)
    result = await session.execute(
        select(FactorExposureSnapshot).where(FactorExposureSnapshot.id == snap.id)
    )
    fetched = result.scalar_one()
    assert fetched.value_exposure == Decimal("0.1200")
    assert fetched.growth_exposure == Decimal("0.2500")


@pytest.mark.asyncio
async def test_factor_exposure_unique_constraint(session):
    """Duplicate (portfolio_id, snapshot_date) raises IntegrityError."""
    p = await _seed_portfolio(session, portfolio_name="Factor Unique")
    await _seed_factor_exposure(session, p.id, snapshot_date=date(2025, 7, 1))
    session.add(FactorExposureSnapshot(
        id=uuid.uuid4(),
        portfolio_id=p.id,
        snapshot_date=date(2025, 7, 1),
    ))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_factor_exposure_unintended_flags(session):
    """unintended_flags JSONB round-trips correctly."""
    p = await _seed_portfolio(session, portfolio_name="Factor Flags")
    snap = await _seed_factor_exposure(session, p.id, snapshot_date=date(2025, 10, 1))
    result = await session.execute(
        select(FactorExposureSnapshot).where(FactorExposureSnapshot.id == snap.id)
    )
    fetched = result.scalar_one()
    assert fetched.unintended_flags["size"] is True


# ══════════════════════════════════════════════════════════════════════
# PortfolioStressTestResult
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_stress_test(session):
    """Create a PortfolioStressTestResult with all fields."""
    p = await _seed_portfolio(session, portfolio_name="Stress Create")
    snap = await _seed_stress_test(session, p.id)
    result = await session.execute(
        select(PortfolioStressTestResult).where(PortfolioStressTestResult.id == snap.id)
    )
    fetched = result.scalar_one()
    assert fetched.scenario_name == "2008_GFC"
    assert fetched.scenario_type == "HISTORICAL"
    assert fetched.total_pnl_dollar == Decimal("-15000.00")


@pytest.mark.asyncio
async def test_stress_test_unique_constraint(session):
    """Duplicate (portfolio_id, snapshot_date, scenario_name) raises IntegrityError."""
    p = await _seed_portfolio(session, portfolio_name="Stress Unique")
    await _seed_stress_test(session, p.id, snapshot_date=date(2025, 7, 1), scenario_name="2008_GFC")
    session.add(PortfolioStressTestResult(
        id=uuid.uuid4(),
        portfolio_id=p.id,
        snapshot_date=date(2025, 7, 1),
        scenario_name="2008_GFC",
        scenario_type="HISTORICAL",
    ))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_stress_test_decimal_precision(session):
    """Verify Decimal precision for pnl fields."""
    p = await _seed_portfolio(session, portfolio_name="Stress Precision")
    snap = await _seed_stress_test(
        session, p.id,
        snapshot_date=date(2025, 11, 1),
        scenario_name="CUSTOM_TEST",
        total_pnl_percent=Decimal("-0.123456"),
    )
    result = await session.execute(
        select(PortfolioStressTestResult).where(PortfolioStressTestResult.id == snap.id)
    )
    fetched = result.scalar_one()
    assert fetched.total_pnl_percent == Decimal("-0.123456")


# ══════════════════════════════════════════════════════════════════════
# ComplianceRule
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_compliance_rule(session):
    """Create a ComplianceRule with all fields."""
    p = await _seed_portfolio(session, portfolio_name="Rule Create")
    rule = await _seed_compliance_rule(session, p.id)
    result = await session.execute(
        select(ComplianceRule).where(ComplianceRule.rule_id == rule.rule_id)
    )
    fetched = result.scalar_one()
    assert fetched.rule_name == "Max Position Weight"
    assert fetched.rule_type == "POSITION_LIMIT"
    assert fetched.threshold == Decimal("0.100000")


@pytest.mark.asyncio
async def test_compliance_rule_jsonb_definition(session):
    """rule_definition JSONB round-trips correctly."""
    p = await _seed_portfolio(session, portfolio_name="Rule JSONB")
    rule = await _seed_compliance_rule(
        session, p.id,
        rule_definition={"field": "sector_weight", "sector": "Technology", "max": 0.35},
    )
    result = await session.execute(
        select(ComplianceRule).where(ComplianceRule.rule_id == rule.rule_id)
    )
    fetched = result.scalar_one()
    assert fetched.rule_definition["sector"] == "Technology"
    assert fetched.rule_definition["max"] == 0.35


@pytest.mark.asyncio
async def test_compliance_rule_update(session):
    """Update a compliance rule threshold."""
    p = await _seed_portfolio(session, portfolio_name="Rule Update")
    rule = await _seed_compliance_rule(session, p.id)
    rule.threshold = Decimal("0.150000")
    rule.severity = "CRITICAL"
    await session.flush()

    result = await session.execute(
        select(ComplianceRule).where(ComplianceRule.rule_id == rule.rule_id)
    )
    fetched = result.scalar_one()
    assert fetched.threshold == Decimal("0.150000")
    assert fetched.severity == "CRITICAL"


# ══════════════════════════════════════════════════════════════════════
# ComplianceResult
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_compliance_result(session):
    """Create a ComplianceResult linked to a rule."""
    p = await _seed_portfolio(session, portfolio_name="Result Create")
    rule = await _seed_compliance_rule(session, p.id)
    cr = await _seed_compliance_result(session, p.id, rule.rule_id)
    result = await session.execute(
        select(ComplianceResult).where(ComplianceResult.result_id == cr.result_id)
    )
    fetched = result.scalar_one()
    assert fetched.status == "PASS"
    assert fetched.current_value == Decimal("0.085000")


@pytest.mark.asyncio
async def test_compliance_result_unique_constraint(session):
    """Duplicate (portfolio_id, rule_id, check_date) raises IntegrityError."""
    p = await _seed_portfolio(session, portfolio_name="Result Unique")
    rule = await _seed_compliance_rule(session, p.id)
    await _seed_compliance_result(session, p.id, rule.rule_id, check_date=date(2025, 7, 1))
    session.add(ComplianceResult(
        result_id=uuid.uuid4(),
        portfolio_id=p.id,
        rule_id=rule.rule_id,
        check_date=date(2025, 7, 1),
        status="BREACH",
    ))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


# ══════════════════════════════════════════════════════════════════════
# DriftSnapshot
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_drift_snapshot(session):
    """Create a DriftSnapshot with all fields."""
    p = await _seed_portfolio(session, portfolio_name="Drift Create")
    snap = await _seed_drift_snapshot(session, p.id)
    result = await session.execute(
        select(DriftSnapshot).where(DriftSnapshot.id == snap.id)
    )
    fetched = result.scalar_one()
    assert fetched.total_drift_pct == Decimal("0.0350")
    assert fetched.drift_classification == "LOW"
    assert fetched.rebalance_needed is False


@pytest.mark.asyncio
async def test_drift_snapshot_unique_constraint(session):
    """Duplicate (portfolio_id, snapshot_date) raises IntegrityError."""
    p = await _seed_portfolio(session, portfolio_name="Drift Unique")
    await _seed_drift_snapshot(session, p.id, snapshot_date=date(2025, 7, 1))
    session.add(DriftSnapshot(
        id=uuid.uuid4(),
        portfolio_id=p.id,
        snapshot_date=date(2025, 7, 1),
    ))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_drift_snapshot_jsonb_round_trip(session):
    """JSONB fields (position_drifts, sector_drifts, target_allocation) round-trip."""
    p = await _seed_portfolio(session, portfolio_name="Drift JSONB")
    snap = await _seed_drift_snapshot(session, p.id, snapshot_date=date(2025, 12, 1))
    result = await session.execute(
        select(DriftSnapshot).where(DriftSnapshot.id == snap.id)
    )
    fetched = result.scalar_one()
    assert len(fetched.position_drifts) == 1
    assert fetched.position_drifts[0]["ticker"] == "AAPL"
    assert fetched.target_allocation["AAPL"] == 0.10


@pytest.mark.asyncio
async def test_drift_snapshot_decimal_precision(session):
    """Verify Numeric(8,4) precision for drift fields."""
    p = await _seed_portfolio(session, portfolio_name="Drift Precision")
    snap = await _seed_drift_snapshot(
        session, p.id,
        snapshot_date=date(2026, 1, 1),
        total_drift_pct=Decimal("0.1234"),
        max_position_drift_pct=Decimal("0.5678"),
    )
    result = await session.execute(
        select(DriftSnapshot).where(DriftSnapshot.id == snap.id)
    )
    fetched = result.scalar_one()
    assert fetched.total_drift_pct == Decimal("0.1234")
    assert fetched.max_position_drift_pct == Decimal("0.5678")
