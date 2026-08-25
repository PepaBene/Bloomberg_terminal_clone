"""Smoke test for the Conversation/ConversationMessage models (Layer 3
§5.3: adviser chat)."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from src.models.conversation import Conversation, ConversationMessage
from src.models.portfolio import Portfolio


async def _seed_portfolio(session, **kwargs) -> Portfolio:
    defaults = dict(
        id=uuid.uuid4(), user_id="default_user", portfolio_name=f"Conversation Model Test {uuid.uuid4().hex}",
        portfolio_type="REAL", inception_date=date(2025, 1, 1),
        initial_cash=Decimal("100000.00"), current_cash=Decimal("20000.00"),
    )
    defaults.update(kwargs)
    p = Portfolio(**defaults)
    session.add(p)
    await session.flush()
    return p


async def test_create_conversation(session):
    p = await _seed_portfolio(session)
    convo = Conversation(id=uuid.uuid4(), user_id="default_user", portfolio_id=p.id, title="Rebalance discussion")
    session.add(convo)
    await session.flush()

    fetched = (await session.execute(select(Conversation).where(Conversation.id == convo.id))).scalar_one()
    assert fetched.title == "Rebalance discussion"
    assert fetched.portfolio_id == p.id


async def test_conversation_without_portfolio(session):
    convo = Conversation(id=uuid.uuid4(), user_id="default_user", portfolio_id=None)
    session.add(convo)
    await session.flush()

    fetched = (await session.execute(select(Conversation).where(Conversation.id == convo.id))).scalar_one()
    assert fetched.portfolio_id is None


async def test_append_messages_with_tool_calls_and_citations(session):
    p = await _seed_portfolio(session)
    convo = Conversation(id=uuid.uuid4(), user_id="default_user", portfolio_id=p.id)
    session.add(convo)
    await session.flush()

    session.add(ConversationMessage(id=uuid.uuid4(), conversation_id=convo.id, role="user", content="Should I trim AAPL?"))
    session.add(ConversationMessage(
        id=uuid.uuid4(), conversation_id=convo.id, role="assistant",
        content="Yes, consider trimming.",
        tool_calls=[{"name": "portfolio_snapshot", "input": {}}],
        citations=["portfolio_snapshot: AAPL 50% of NAV"],
        tokens=128,
    ))
    await session.flush()

    rows = (
        await session.execute(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == convo.id)
            .order_by(ConversationMessage.created_at.asc())
        )
    ).scalars().all()
    assert len(rows) == 2
    assert rows[1].tool_calls[0]["name"] == "portfolio_snapshot"
    assert rows[1].tokens == 128
