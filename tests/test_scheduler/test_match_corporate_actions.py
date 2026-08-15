"""Tests for scripts/match_corporate_actions.py.

Regression coverage for the corporate-action-queue "zero writer" gap
(DEEP_AUDIT_2026-07-16 Dimension 2/3): corporate_action_engine
.match_corporate_actions_to_holdings has "no production caller today" per
its own docstring, so CorporateActionQueue never got populated and
GET /v4/portfolios/{id}/corporate-actions returned an empty list forever
even when a portfolio held a security with a real, already-ingested
upcoming dividend.
"""

import uuid
from datetime import date, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from scripts.match_corporate_actions import run
from src.models.corporate_actions import CorporateAction
from src.models.entity import Entity
from src.models.nav_snapshot import CorporateActionQueue
from src.models.portfolio import Portfolio
from src.models.position import Position
from src.models.security import Security, SecurityIdentifier


@pytest_asyncio.fixture
async def held_security_with_dividend(session: AsyncSession):
    # Each test that pulls this fixture drives run() with dry_run=False
    # (a real commit against the shared session-scoped test DB, since
    # get_session_factory is monkeypatched to hand back this same test
    # session) -- unique per-invocation identifiers keep the two tests
    # below from colliding on each other's committed rows.
    ticker = f"DIV{uuid.uuid4().hex[:8].upper()}"

    entity = Entity(
        entity_id=uuid.uuid4(), legal_name="Dividend Corp", entity_type="PUBLIC_COMPANY",
        status="ACTIVE", source="TEST",
    )
    session.add(entity)
    await session.flush()
    security = Security(
        security_id=uuid.uuid4(), name="Dividend Corp Stock", security_type="COMMON_STOCK",
        asset_class="EQUITY", status="ACTIVE", issuer_entity_id=entity.entity_id,
    )
    session.add(security)
    await session.flush()
    session.add(SecurityIdentifier(
        id=uuid.uuid4(), security_id=security.security_id, identifier_type="TICKER",
        identifier_value=ticker, source="TEST",
    ))

    action = CorporateAction(
        action_id=uuid.uuid4(), action_type="CASH_DIVIDEND", security_id=security.security_id,
        entity_id=entity.entity_id, ex_date=date.today() + timedelta(days=5),
        payment_date=date.today() + timedelta(days=20), status="ANNOUNCED", source="TEST",
    )
    session.add(action)

    portfolio = Portfolio(
        id=uuid.uuid4(), user_id="default_user", portfolio_name=f"Corp Action Test {uuid.uuid4()}",
        portfolio_type="REAL", inception_date=date(2025, 1, 1),
        initial_cash=0, current_cash=0,
    )
    session.add(portfolio)
    await session.flush()

    position = Position(
        id=uuid.uuid4(), portfolio_id=portfolio.id, ticker=ticker, status="OPEN",
        security_id=security.security_id, market_value=10000,
    )
    session.add(position)
    await session.flush()

    return portfolio, position, action


@pytest.mark.asyncio
async def test_match_queues_real_pending_action(session: AsyncSession, held_security_with_dividend, monkeypatch):
    portfolio, position, action = held_security_with_dividend

    import scripts.match_corporate_actions as mod
    monkeypatch.setattr(mod, "get_session_factory", lambda: _SingleSessionFactory(session))

    queued = await run(dry_run=False)
    await session.flush()

    assert queued == 1
    row = (await session.execute(
        select(CorporateActionQueue).where(CorporateActionQueue.portfolio_id == portfolio.id)
    )).scalar_one()
    assert row.status == "PENDING"
    assert row.ticker == position.ticker
    assert row.action_type == "CASH_DIVIDEND"
    assert row.position_id == position.id
    assert row.ex_date == action.ex_date


@pytest.mark.asyncio
async def test_match_is_idempotent(session: AsyncSession, held_security_with_dividend, monkeypatch):
    """Running the matcher twice must not create duplicate queue rows for
    the same (portfolio, position, action)."""
    portfolio, position, action = held_security_with_dividend

    import scripts.match_corporate_actions as mod
    monkeypatch.setattr(mod, "get_session_factory", lambda: _SingleSessionFactory(session))

    first = await run(dry_run=False)
    await session.flush()
    second = await run(dry_run=False)
    await session.flush()

    assert first == 1
    assert second == 0
    rows = (await session.execute(
        select(CorporateActionQueue).where(CorporateActionQueue.portfolio_id == portfolio.id)
    )).scalars().all()
    assert len(rows) == 1


class _SingleSessionFactory:
    """Minimal stand-in for get_session_factory() that hands back the
    shared test ``session`` through an async-context-manager interface,
    without committing/closing it (the test's own rollback handles
    cleanup)."""

    def __init__(self, session: AsyncSession):
        self._session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc):
        return False
