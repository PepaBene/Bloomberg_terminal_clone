"""Tests for scripts/run_portfolio_risk_batch.py.

Regression coverage for the Pillar-4 "zero callers, zero writers" gap
(DEEP_AUDIT_2026-07-16 Dimension 2/3): attribution_engine,
portfolio_risk_engine (VaR/concentration/factor exposure), and
compliance_engine were all correct pure-computation modules that nothing
ever called outside of the on-demand stress-test endpoints, so their
result tables stayed permanently empty. Each test below seeds real
positions/prices/analytics and asserts the batch script persists a REAL
(not zero/None/fabricated) snapshot.
"""

import math
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from scripts.run_portfolio_risk_batch import (
    build_factor_zscore_universe,
    _upsert_attribution,
    _upsert_compliance_results,
    _upsert_concentration,
    _upsert_factor_exposure,
    _upsert_var,
)
from src.api.routers.portfolio_risk import load_position_dicts_with_classification
from src.models.analytics import AnalyticsResult, CompositeScore
from src.models.attribution import AttributionResult
from src.models.compliance import ComplianceResult, ComplianceRule
from src.models.entity import Entity
from src.models.portfolio import Portfolio
from src.models.portfolio_risk import ConcentrationAnalysis, FactorExposureSnapshot, PortfolioVarSnapshot
from src.models.position import Position
from src.models.security import EODPrice, Security

NOW = datetime.now(timezone.utc)


async def _seed_entity_security(session: AsyncSession, *, name: str, gics_sector: str) -> uuid.UUID:
    entity = Entity(
        entity_id=uuid.uuid4(), legal_name=name, entity_type="PUBLIC_COMPANY",
        status="ACTIVE", source="TEST", gics_sector=gics_sector,
        domicile_country="US",
    )
    session.add(entity)
    await session.flush()
    security = Security(
        security_id=uuid.uuid4(), name=f"{name} Stock", security_type="COMMON_STOCK",
        asset_class="EQUITY", status="ACTIVE", issuer_entity_id=entity.entity_id,
    )
    session.add(security)
    await session.flush()
    return security.security_id


async def _seed_prices(session: AsyncSession, security_id: uuid.UUID, *, base: float, amplitude: float, days: int = 260) -> None:
    base_date = date.today() - timedelta(days=days + 5)
    for i in range(days):
        price = base + 0.05 * i + amplitude * math.sin(i * 0.3)
        session.add(EODPrice(
            security_id=security_id, price_date=base_date + timedelta(days=i),
            close=price, close_adjusted=price, source="TEST", created_at=NOW,
        ))
    await session.flush()


async def _seed_portfolio(session: AsyncSession, **kwargs) -> Portfolio:
    defaults = {
        "id": uuid.uuid4(), "user_id": "default_user", "portfolio_name": "Risk Batch Test",
        "portfolio_type": "REAL", "inception_date": date(2025, 1, 1),
        "initial_cash": Decimal("0.00"), "current_cash": Decimal("0.00"),
    }
    defaults.update(kwargs)
    p = Portfolio(**defaults)
    session.add(p)
    await session.flush()
    return p


@pytest_asyncio.fixture
async def two_security_portfolio(session: AsyncSession):
    """Portfolio with two open positions in distinct GICS sectors, each
    with real EOD price history."""
    sec_a = await _seed_entity_security(session, name="Alpha Corp", gics_sector="45")
    sec_b = await _seed_entity_security(session, name="Beta Corp", gics_sector="20")
    await _seed_prices(session, sec_a, base=100.0, amplitude=2.0)
    await _seed_prices(session, sec_b, base=50.0, amplitude=1.0)

    portfolio = await _seed_portfolio(session)
    session.add_all([
        Position(id=uuid.uuid4(), portfolio_id=portfolio.id, ticker="ALPHA", status="OPEN",
                 security_id=sec_a, market_value=Decimal("60000.00")),
        Position(id=uuid.uuid4(), portfolio_id=portfolio.id, ticker="BETA", status="OPEN",
                 security_id=sec_b, market_value=Decimal("40000.00")),
    ])
    await session.flush()
    return portfolio, sec_a, sec_b


@pytest.mark.asyncio
async def test_concentration_persists_real_values(session: AsyncSession, two_security_portfolio):
    portfolio, sec_a, sec_b = two_security_portfolio
    positions = await load_position_dicts_with_classification(session, portfolio.id)
    today = date.today()

    await _upsert_concentration(session, portfolio.id, today, positions, nav=100000.0)
    await session.flush()

    row = (await session.execute(
        select(ConcentrationAnalysis).where(ConcentrationAnalysis.portfolio_id == portfolio.id)
    )).scalar_one()
    # 60/40 split -> HHI = 0.6^2 + 0.4^2 = 0.52, *10000 = 5200.
    assert float(row.hhi_position) == pytest.approx(5200.0, abs=1.0)
    assert row.concentration_classification == "CONCENTRATED"
    assert float(row.largest_position_weight) == pytest.approx(0.6, abs=0.001)
    assert row.sector_detail  # real per-sector breakdown, not empty


@pytest.mark.asyncio
async def test_var_persists_real_values(session: AsyncSession, two_security_portfolio):
    portfolio, sec_a, sec_b = two_security_portfolio
    for sec_id in (sec_a, sec_b):
        session.add(AnalyticsResult(
            security_id=sec_id, entity_id=uuid.uuid4(), engine_id="E5",
            metric_name="var_historical_95_1d", metric_category="RISK",
            value=0.025, unit="RATIO", period="LATEST", as_of_date=date.today(),
            data_quality="COMPLETE",
        ))
    await session.flush()

    positions = await load_position_dicts_with_classification(session, portfolio.id)
    today = date.today()
    result = await _upsert_var(session, portfolio.id, today, positions, nav=100000.0, return_cache={})
    await session.flush()

    assert result is not None
    row = (await session.execute(
        select(PortfolioVarSnapshot).where(PortfolioVarSnapshot.portfolio_id == portfolio.id)
    )).scalar_one()
    # VaR is stored as a P&L impact -- negative (a loss), and nonzero given
    # both holdings carry a real 2.5% individual VaR.
    assert float(row.var_1d_95) < 0
    assert float(row.portfolio_nav) == pytest.approx(100000.0)
    assert row.component_var  # per-ticker decomposition persisted


@pytest.mark.asyncio
async def test_factor_exposure_uses_real_relative_scores(session: AsyncSession, two_security_portfolio):
    portfolio, sec_a, sec_b = two_security_portfolio
    # Alpha scores far higher on momentum than Beta -- a real cross-sectional
    # z-score must put Alpha's momentum exposure above Beta's, not both at 0.
    session.add_all([
        AnalyticsResult(security_id=sec_a, entity_id=uuid.uuid4(), engine_id="E5",
                         metric_name="factor_momentum", metric_category="MOMENTUM", value=2.0,
                         unit="SCORE", period="LATEST", as_of_date=date.today(), data_quality="COMPLETE"),
        AnalyticsResult(security_id=sec_b, entity_id=uuid.uuid4(), engine_id="E5",
                         metric_name="factor_momentum", metric_category="MOMENTUM", value=-2.0,
                         unit="SCORE", period="LATEST", as_of_date=date.today(), data_quality="COMPLETE"),
    ])
    await session.flush()

    positions = await load_position_dicts_with_classification(session, portfolio.id)
    today = date.today()
    zscores = await build_factor_zscore_universe(session, [sec_a, sec_b])
    await _upsert_factor_exposure(session, portfolio.id, today, positions, nav=100000.0, factor_zscores=zscores)
    await session.flush()

    row = (await session.execute(
        select(FactorExposureSnapshot).where(FactorExposureSnapshot.portfolio_id == portfolio.id)
    )).scalar_one()
    # Alpha (z=+1.0, 60% weight) and Beta (z=-1.0, 40% weight) -> weighted
    # portfolio momentum exposure = 0.6*1.0 + 0.4*-1.0 = 0.2, not the
    # hardcoded zero the audit found.
    assert float(row.momentum_exposure) == pytest.approx(0.2, abs=0.01)


@pytest.mark.asyncio
async def test_attribution_computes_real_security_contribution(session: AsyncSession, two_security_portfolio):
    portfolio, sec_a, sec_b = two_security_portfolio
    today = date.today()

    await _upsert_attribution(session, portfolio, today, await load_position_dicts_with_classification(session, portfolio.id), nav=100000.0)
    await session.flush()

    row = (await session.execute(
        select(AttributionResult).where(AttributionResult.portfolio_id == portfolio.id)
    )).scalar_one()
    assert row.attribution_type == "SECURITY"
    assert row.total_portfolio_return is not None
    assert row.security_detail
    tickers = {d["ticker"] for d in row.security_detail}
    assert tickers == {"ALPHA", "BETA"}
    # No benchmark configured on this portfolio -> honest gap, not a
    # fabricated Brinson split.
    assert row.total_benchmark_return is None
    assert row.sector_detail is None


@pytest.mark.asyncio
async def test_compliance_results_flags_real_breach(session: AsyncSession, two_security_portfolio):
    portfolio, sec_a, sec_b = two_security_portfolio
    # ALPHA is 60% of NAV; a 50% position limit must BREACH for real.
    session.add(ComplianceRule(
        rule_id=uuid.uuid4(), portfolio_id=portfolio.id, rule_name="Max Position 50%",
        rule_type="POSITION_LIMIT", rule_definition={"max_weight": 50.0},
        comparison="LTE", threshold=Decimal("50.0"), severity="BREACH", is_active=True,
    ))
    await session.flush()

    positions = await load_position_dicts_with_classification(session, portfolio.id)
    today = date.today()
    await _upsert_compliance_results(session, portfolio.id, today, positions, nav=100000.0, var_result=None)
    await session.flush()

    row = (await session.execute(
        select(ComplianceResult).where(ComplianceResult.portfolio_id == portfolio.id)
    )).scalar_one()
    assert row.status == "BREACH"
    assert float(row.current_value) == pytest.approx(60.0)
    assert row.breach_positions is not None
