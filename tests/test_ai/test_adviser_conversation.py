"""Tests for src/ai/adviser/conversation.py (Layer 3 §5.3: chat
persistence + conversational recall)."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from src.ai.adviser.conversation import (
    append_message,
    create_conversation,
    get_conversation,
    load_history,
    render_history_for_prompt,
)
from src.models.conversation import ConversationMessage
from src.models.portfolio import Portfolio


async def _seed_portfolio(session, **kwargs) -> Portfolio:
    defaults = dict(
        id=uuid.uuid4(), user_id="default_user", portfolio_name="Conversation Test Portfolio",
        portfolio_type="REAL", inception_date=date(2025, 1, 1),
        initial_cash=Decimal("100000.00"), current_cash=Decimal("20000.00"),
    )
    defaults.update(kwargs)
    p = Portfolio(**defaults)
    session.add(p)
    await session.flush()
    return p


class TestRenderHistoryForPrompt:

    def test_empty_history(self):
        assert render_history_for_prompt([]) == ""

    def test_renders_user_and_assistant_turns(self):
        messages = [
            ConversationMessage(id=uuid.uuid4(), conversation_id=uuid.uuid4(), role="user", content="How am I doing?"),
            ConversationMessage(id=uuid.uuid4(), conversation_id=uuid.uuid4(), role="assistant", content="Your NAV is 100k."),
        ]
        result = render_history_for_prompt(messages)
        assert "User: How am I doing?" in result
        assert "Adviser: Your NAV is 100k." in result


@pytest.mark.asyncio
class TestConversationPersistence:

    async def test_create_and_get_conversation(self, session):
        p = await _seed_portfolio(session)
        convo = await create_conversation(session, user_id="default_user", portfolio_id=p.id, title="Rebalance discussion")

        fetched = await get_conversation(session, convo.id)
        assert fetched is not None
        assert fetched.title == "Rebalance discussion"
        assert fetched.portfolio_id == p.id

    async def test_get_conversation_returns_none_for_unknown_id(self, session):
        result = await get_conversation(session, uuid.uuid4())
        assert result is None

    async def test_append_and_load_history(self, session):
        p = await _seed_portfolio(session)
        convo = await create_conversation(session, user_id="default_user", portfolio_id=p.id)

        await append_message(session, convo.id, role="user", content="Should I trim AAPL?")
        await append_message(session, convo.id, role="assistant", content="Yes, consider trimming.", tokens=42)

        history = await load_history(session, convo.id)
        assert len(history) == 2
        assert history[0].role == "user"
        assert history[1].role == "assistant"
        assert history[1].tokens == 42

    async def test_load_history_respects_limit_and_chronological_order(self, session):
        p = await _seed_portfolio(session)
        convo = await create_conversation(session, user_id="default_user", portfolio_id=p.id)
        for i in range(5):
            await append_message(session, convo.id, role="user", content=f"message {i}")

        history = await load_history(session, convo.id, limit=3)
        assert len(history) == 3
        assert [m.content for m in history] == ["message 2", "message 3", "message 4"]
