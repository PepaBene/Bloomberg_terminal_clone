"""Tests for src/ai/tools/portfolio.py (Layer 3 §5.1/§5.2 portfolio-action
tools)."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from src.ai.tools.portfolio import (
    DriftAnalysisTool,
    PortfolioSnapshotTool,
    PreTradeComplianceTool,
    WhatIfTool,
)
from src.models.compliance import ComplianceRule, DriftSnapshot
from src.models.portfolio import Portfolio
from src.models.position import Position


async def _seed_portfolio(session, **kwargs) -> Portfolio:
    defaults = dict(
        id=uuid.uuid4(), user_id="default_user", portfolio_name="Tool Test Portfolio",
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


@pytest.mark.asyncio
class TestPortfolioSnapshotTool:

    async def test_invalid_portfolio_id(self, session):
        tool = PortfolioSnapshotTool(session)
        result = await tool.run(portfolio_id="not-a-uuid")
        assert result.is_error is True

    async def test_unknown_portfolio(self, session):
        tool = PortfolioSnapshotTool(session)
        result = await tool.run(portfolio_id=str(uuid.uuid4()))
        assert result.is_error is True

    async def test_returns_positions_and_nav(self, session):
        p = await _seed_portfolio(session)
        await _seed_position(session, p.id, ticker="AAPL", market_value=Decimal("40000"), weight=Decimal("0.5"))
        tool = PortfolioSnapshotTool(session)

        result = await tool.run(portfolio_id=str(p.id))
        assert result.is_error is False
        assert "AAPL" in result.content
        assert "NAV" in result.content

    async def test_no_positions(self, session):
        p = await _seed_portfolio(session)
        tool = PortfolioSnapshotTool(session)
        result = await tool.run(portfolio_id=str(p.id))
        assert "No open positions" in result.content


@pytest.mark.asyncio
class TestWhatIfTool:

    async def test_unknown_portfolio(self, session):
        tool = WhatIfTool(session)
        result = await tool.run(portfolio_id=str(uuid.uuid4()), trades=[])
        assert result.is_error is True

    async def test_simulates_trade_impact(self, session):
        p = await _seed_portfolio(session)
        await _seed_position(session, p.id, ticker="AAPL", weight=Decimal("0.5"), market_value=Decimal("40000"))
        tool = WhatIfTool(session)

        result = await tool.run(
            portfolio_id=str(p.id),
            trades=[{"ticker": "AAPL", "action": "SELL", "shares": 50, "price_per_share": 400.0}],
        )
        assert result.is_error is False
        assert "AAPL" in result.content
        assert "Estimated transaction cost" in result.content

    async def test_flags_compliance_breach(self, session):
        p = await _seed_portfolio(session)
        await _seed_position(session, p.id, ticker="AAPL", weight=Decimal("0.05"), market_value=Decimal("4000"))
        session.add(ComplianceRule(
            rule_id=uuid.uuid4(), portfolio_id=p.id, rule_name="Max Position Weight",
            rule_type="POSITION_LIMIT", rule_definition={}, threshold=Decimal("0.100000"),
            comparison="LTE", severity="WARNING", is_active=True,
        ))
        await session.flush()
        tool = WhatIfTool(session)

        result = await tool.run(
            portfolio_id=str(p.id),
            trades=[{"ticker": "AAPL", "action": "BUY", "shares": 500, "price_per_share": 100.0}],
        )
        assert "Compliance" in result.content


@pytest.mark.asyncio
class TestDriftAnalysisTool:

    async def test_no_target_allocation_set(self, session):
        p = await _seed_portfolio(session)
        await _seed_position(session, p.id)
        tool = DriftAnalysisTool(session)

        result = await tool.run(portfolio_id=str(p.id))
        assert result.is_error is False
        assert "No target allocation" in result.content

    async def test_reports_drift_and_rebalance_trades(self, session):
        p = await _seed_portfolio(session)
        await _seed_position(session, p.id, ticker="AAPL", weight=Decimal("0.80"), market_value=Decimal("80000"))
        session.add(DriftSnapshot(
            id=uuid.uuid4(), portfolio_id=p.id, snapshot_date=date(2026, 1, 1),
            target_allocation={"AAPL": 50.0},
        ))
        await session.flush()
        tool = DriftAnalysisTool(session)

        result = await tool.run(portfolio_id=str(p.id))
        assert "rebalance needed: True" in result.content
        assert "AAPL" in result.content


@pytest.mark.asyncio
class TestPreTradeComplianceTool:

    async def test_approved_trade(self, session):
        p = await _seed_portfolio(session)
        tool = PreTradeComplianceTool(session)
        result = await tool.run(portfolio_id=str(p.id), ticker="AAPL", action="BUY", shares=10, price=150.0)
        assert "APPROVED" in result.content

    async def test_rejected_trade(self, session):
        p = await _seed_portfolio(session)
        session.add(ComplianceRule(
            rule_id=uuid.uuid4(), portfolio_id=p.id, rule_name="Position Cap",
            rule_type="POSITION_LIMIT", rule_definition={}, threshold=Decimal("1000.000000"),
            comparison="LTE", severity="CRITICAL", is_active=True,
        ))
        await session.flush()
        tool = PreTradeComplianceTool(session)

        result = await tool.run(portfolio_id=str(p.id), ticker="AAPL", action="BUY", shares=100, price=150.0)
        assert "REJECTED" in result.content
        assert "Position Cap" in result.content
