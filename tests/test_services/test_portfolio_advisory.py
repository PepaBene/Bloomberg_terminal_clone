"""Tests for src/services/portfolio_advisory.py (Layer 3 §5.1: wiring the
previously-dormant whatif_engine/drift_engine/trade_list_engine to real
portfolio data)."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from src.models.compliance import ComplianceRule, DriftSnapshot
from src.models.portfolio import Portfolio
from src.models.portfolio_risk import PortfolioVarSnapshot
from src.models.position import Position
from src.services import portfolio_advisory


async def _seed_portfolio(session, **kwargs) -> Portfolio:
    defaults = dict(
        id=uuid.uuid4(), user_id="default_user", portfolio_name="Advisory Test Portfolio",
        portfolio_type="REAL", inception_date=date(2025, 1, 1),
        initial_cash=Decimal("100000.00"), current_cash=Decimal("20000.00"),
    )
    defaults.update(kwargs)
    p = Portfolio(**defaults)
    session.add(p)
    await session.flush()
    return p


async def _seed_position(session, portfolio_id, **kwargs) -> Position:
    defaults = dict(
        id=uuid.uuid4(), portfolio_id=portfolio_id, ticker="AAPL", status="OPEN",
        shares=Decimal("100"), market_value=Decimal("40000.00"), weight=Decimal("0.5"),
        closing_price=Decimal("400.00"),
    )
    defaults.update(kwargs)
    p = Position(**defaults)
    session.add(p)
    await session.flush()
    return p


async def _seed_compliance_rule(session, portfolio_id, **kwargs) -> ComplianceRule:
    defaults = dict(
        rule_id=uuid.uuid4(), portfolio_id=portfolio_id, rule_name="Max Position",
        rule_type="POSITION_LIMIT", rule_definition={}, threshold=Decimal("0.100000"),
        comparison="LTE", severity="WARNING", is_active=True,
    )
    defaults.update(kwargs)
    rule = ComplianceRule(**defaults)
    session.add(rule)
    await session.flush()
    return rule


class TestPositionDicts:

    def test_converts_fraction_weight_to_percentage(self):
        pos = Position(
            id=uuid.uuid4(), portfolio_id=uuid.uuid4(), ticker="MSFT", status="OPEN",
            shares=Decimal("10"), market_value=Decimal("5000"), weight=Decimal("0.25"),
        )
        result = portfolio_advisory.position_dicts([pos])
        assert result == [{"ticker": "MSFT", "shares": 10.0, "market_value": 5000.0, "weight": 25.0}]

    def test_handles_null_fields(self):
        pos = Position(id=uuid.uuid4(), portfolio_id=uuid.uuid4(), ticker="ZZZ", status="OPEN")
        result = portfolio_advisory.position_dicts([pos])
        assert result == [{"ticker": "ZZZ", "shares": 0.0, "market_value": 0.0, "weight": 0.0}]


@pytest.mark.asyncio
class TestComputeWhatif:

    async def test_returns_none_for_missing_portfolio(self, session):
        result = await portfolio_advisory.compute_whatif(session, uuid.uuid4(), [])
        assert result is None

    async def test_computes_position_impact_from_real_positions(self, session):
        p = await _seed_portfolio(session)
        await _seed_position(session, p.id, ticker="AAPL", shares=Decimal("100"), market_value=Decimal("40000"), weight=Decimal("0.5"))

        result = await portfolio_advisory.compute_whatif(
            session, p.id,
            [{"ticker": "AAPL", "action": "SELL", "shares": 50, "price_per_share": 400.0}],
        )
        assert result is not None
        assert any(pi.ticker == "AAPL" for pi in result.position_impacts)

    async def test_uses_real_var_snapshot_when_present(self, session):
        p = await _seed_portfolio(session)
        await _seed_position(session, p.id)
        session.add(PortfolioVarSnapshot(
            id=uuid.uuid4(), portfolio_id=p.id, snapshot_date=date(2026, 1, 1),
            var_1d_95=Decimal("-5000.0000"),
        ))
        await session.flush()

        result = await portfolio_advisory.compute_whatif(session, p.id, [])
        assert result.risk_impact.current_var_95 == -5000.0

    async def test_degrades_gracefully_with_no_var_snapshot(self, session):
        p = await _seed_portfolio(session)
        await _seed_position(session, p.id)
        result = await portfolio_advisory.compute_whatif(session, p.id, [])
        assert result is not None
        assert result.risk_impact.current_var_95 == 0.0

    async def test_maps_active_position_limit_rule(self, session):
        p = await _seed_portfolio(session)
        await _seed_position(session, p.id, weight=Decimal("0.5"))
        await _seed_compliance_rule(session, p.id, rule_type="POSITION_LIMIT", threshold=Decimal("0.100000"))

        result = await portfolio_advisory.compute_whatif(session, p.id, [])
        assert any(ci.rule_name == "Max Position" for ci in result.compliance_impacts)

    async def test_inactive_rule_excluded(self, session):
        p = await _seed_portfolio(session)
        await _seed_position(session, p.id)
        await _seed_compliance_rule(session, p.id, is_active=False)

        result = await portfolio_advisory.compute_whatif(session, p.id, [])
        assert result.compliance_impacts == []


@pytest.mark.asyncio
class TestComputeDrift:

    async def test_returns_none_for_missing_portfolio(self, session):
        result = await portfolio_advisory.compute_drift(session, uuid.uuid4())
        assert result is None

    async def test_returns_none_when_no_target_allocation_set(self, session):
        p = await _seed_portfolio(session)
        await _seed_position(session, p.id)
        result = await portfolio_advisory.compute_drift(session, p.id)
        assert result is None

    async def test_computes_drift_against_target_allocation(self, session):
        p = await _seed_portfolio(session)
        await _seed_position(session, p.id, ticker="AAPL", weight=Decimal("0.80"), market_value=Decimal("80000"))
        session.add(DriftSnapshot(
            id=uuid.uuid4(), portfolio_id=p.id, snapshot_date=date(2026, 1, 1),
            target_allocation={"AAPL": 50.0},
        ))
        await session.flush()

        analysis = await portfolio_advisory.compute_drift(session, p.id)
        assert analysis is not None
        assert analysis.result.rebalance_needed is True
        assert any(t["ticker"] == "AAPL" for t in analysis.rebalance_trades)

    async def test_uses_most_recent_target_allocation(self, session):
        p = await _seed_portfolio(session)
        await _seed_position(session, p.id, ticker="AAPL", weight=Decimal("0.50"), market_value=Decimal("50000"))
        session.add(DriftSnapshot(
            id=uuid.uuid4(), portfolio_id=p.id, snapshot_date=date(2026, 1, 1),
            target_allocation={"AAPL": 20.0},
        ))
        session.add(DriftSnapshot(
            id=uuid.uuid4(), portfolio_id=p.id, snapshot_date=date(2026, 2, 1),
            target_allocation={"AAPL": 50.0},
        ))
        await session.flush()

        analysis = await portfolio_advisory.compute_drift(session, p.id)
        assert analysis.target_allocation == {"AAPL": 50.0}
        assert analysis.result.rebalance_needed is False


@pytest.mark.asyncio
class TestBuildTradeList:

    async def test_returns_none_for_missing_portfolio(self, session):
        result = await portfolio_advisory.build_trade_list(session, uuid.uuid4(), [])
        assert result is None

    async def test_generates_trade_list_from_rebalance_trades(self, session):
        p = await _seed_portfolio(session)
        await _seed_position(session, p.id, ticker="AAPL", shares=Decimal("100"), closing_price=Decimal("400.00"))

        trade_list = await portfolio_advisory.build_trade_list(
            session, p.id, [{"ticker": "AAPL", "action": "SELL", "weight_delta": 10.0, "notional_amount": 12000.0}],
        )
        assert trade_list is not None
        assert len(trade_list.orders) >= 1


@pytest.mark.asyncio
class TestCheckPretradeCompliance:

    async def test_returns_none_for_missing_portfolio(self, session):
        result = await portfolio_advisory.check_pretrade_compliance(
            session, uuid.uuid4(), ticker="AAPL", action="BUY", shares=10, price=100.0,
        )
        assert result is None

    async def test_approved_with_no_rules(self, session):
        p = await _seed_portfolio(session)
        result = await portfolio_advisory.check_pretrade_compliance(
            session, p.id, ticker="AAPL", action="BUY", shares=10, price=150.0,
        )
        assert result.approved is True
        assert result.violations == []

    async def test_violation_when_over_position_limit(self, session):
        p = await _seed_portfolio(session)
        await _seed_compliance_rule(session, p.id, rule_type="POSITION_LIMIT", threshold=Decimal("1000.000000"))
        result = await portfolio_advisory.check_pretrade_compliance(
            session, p.id, ticker="AAPL", action="BUY", shares=100, price=150.0,
        )
        assert result.approved is False
        assert len(result.violations) >= 1
