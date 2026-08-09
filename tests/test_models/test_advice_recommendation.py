"""Smoke test for the AdviceRecommendation model (Layer 3 §5.4)."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from src.models.advice_recommendation import AdviceRecommendation
from src.models.portfolio import Portfolio


async def _seed_portfolio(session, **kwargs) -> Portfolio:
    defaults = dict(
        id=uuid.uuid4(), user_id="default_user", portfolio_name="Advice Model Test Portfolio",
        portfolio_type="REAL", inception_date=date(2025, 1, 1),
        initial_cash=Decimal("100000.00"), current_cash=Decimal("20000.00"),
    )
    defaults.update(kwargs)
    p = Portfolio(**defaults)
    session.add(p)
    await session.flush()
    return p


async def test_create_recommendation_defaults_to_proposed(session):
    p = await _seed_portfolio(session)
    row = AdviceRecommendation(
        id=uuid.uuid4(), user_id="default_user", portfolio_id=p.id,
        kind="REBALANCE", rationale="Trim overweight AAPL position.",
        evidence=["portfolio_snapshot: AAPL 50% of NAV"], confidence=Decimal("0.750"),
    )
    session.add(row)
    await session.flush()

    fetched = (
        await session.execute(select(AdviceRecommendation).where(AdviceRecommendation.id == row.id))
    ).scalar_one()
    assert fetched.status == "PROPOSED"
    assert fetched.kind == "REBALANCE"
    assert fetched.evidence == ["portfolio_snapshot: AAPL 50% of NAV"]


async def test_round_trips_whatif_and_compliance_jsonb(session):
    p = await _seed_portfolio(session)
    row = AdviceRecommendation(
        id=uuid.uuid4(), user_id="default_user", portfolio_id=p.id,
        kind="OPPORTUNITY", action={"ticker": "MSFT", "action": "BUY", "shares": 10, "price_per_share": 400.0},
        rationale="Attractive valuation.", evidence=["data_query: P/E below sector median"],
        whatif_impact={"risk_impact": {"var_change": 100.0}},
        compliance={"approved": True, "violations": [], "warnings": []},
        confidence=Decimal("0.600"),
    )
    session.add(row)
    await session.flush()

    fetched = (
        await session.execute(select(AdviceRecommendation).where(AdviceRecommendation.id == row.id))
    ).scalar_one()
    assert fetched.action["ticker"] == "MSFT"
    assert fetched.whatif_impact["risk_impact"]["var_change"] == 100.0
    assert fetched.compliance["approved"] is True
