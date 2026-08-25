"""API tests for the Layer 3 adviser chat endpoints
(src/api/routers/adviser_chat.py, §5.3).

``POST .../messages``'s streaming execution path opens its own session
via ``get_session_factory()`` (same reason as
``tests/test_api/test_research_deep_api.py``'s documented limitation --
FastAPI tears down ``Depends(get_session)`` before a StreamingResponse's
body generator runs, so the generator must open its own session, which
means it always talks to the real configured database). What IS testable
here without a live Postgres: conversation creation, message/
recommendation history reads, and the 503 the endpoint returns
synchronously (before ever constructing an SSE response) when the AI
client is disabled -- which it always is in this test environment (no
ANTHROPIC_API_KEY). The underlying business logic
(run_adviser_turn/save_recommendations) has full unit coverage in
tests/test_ai/test_adviser.py and tests/test_ai/test_adviser_store.py.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.advice_recommendation import AdviceRecommendation
from src.models.conversation import Conversation, ConversationMessage
from src.models.portfolio import Portfolio


async def _seed_portfolio(session: AsyncSession, **kwargs) -> Portfolio:
    defaults = dict(
        id=uuid.uuid4(), user_id="default_user", portfolio_name=f"Adviser Chat API Portfolio {uuid.uuid4().hex}",
        portfolio_type="REAL", inception_date=date(2025, 1, 1),
        initial_cash=Decimal("100000.00"), current_cash=Decimal("20000.00"),
    )
    defaults.update(kwargs)
    p = Portfolio(**defaults)
    session.add(p)
    await session.flush()
    return p


@pytest.mark.asyncio
async def test_start_conversation(client: AsyncClient, session: AsyncSession):
    p = await _seed_portfolio(session)
    await session.commit()

    resp = await client.post(
        "/v5/adviser/conversations",
        json={"user_id": "default_user", "portfolio_id": str(p.id), "title": "Rebalance chat"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Rebalance chat"
    assert body["portfolio_id"] == str(p.id)


@pytest.mark.asyncio
async def test_send_message_404_for_unknown_conversation(client: AsyncClient):
    resp = await client.post(
        f"/v5/adviser/conversations/{uuid.uuid4()}/messages", json={"message": "How am I doing?"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_send_message_400_when_no_portfolio_on_conversation(client: AsyncClient, session: AsyncSession):
    convo_id = uuid.uuid4()
    session.add(Conversation(id=convo_id, user_id="default_user", portfolio_id=None))
    await session.commit()

    resp = await client.post(f"/v5/adviser/conversations/{convo_id}/messages", json={"message": "hi"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_send_message_503_when_ai_disabled(client: AsyncClient, session: AsyncSession):
    p = await _seed_portfolio(session)
    convo_id = uuid.uuid4()
    session.add(Conversation(id=convo_id, user_id="default_user", portfolio_id=p.id))
    await session.commit()

    resp = await client.post(f"/v5/adviser/conversations/{convo_id}/messages", json={"message": "How am I doing?"})
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_get_messages_404_for_unknown_conversation(client: AsyncClient):
    resp = await client.get(f"/v5/adviser/conversations/{uuid.uuid4()}/messages")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_messages_returns_history(client: AsyncClient, session: AsyncSession):
    p = await _seed_portfolio(session)
    convo_id = uuid.uuid4()
    session.add(Conversation(id=convo_id, user_id="default_user", portfolio_id=p.id))
    await session.flush()
    session.add(ConversationMessage(id=uuid.uuid4(), conversation_id=convo_id, role="user", content="Hi"))
    session.add(ConversationMessage(id=uuid.uuid4(), conversation_id=convo_id, role="assistant", content="Hello!"))
    await session.commit()

    resp = await client.get(f"/v5/adviser/conversations/{convo_id}/messages")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert body[0]["role"] == "user"
    assert body[1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_get_recommendations_404_for_unknown_conversation(client: AsyncClient):
    resp = await client.get(f"/v5/adviser/conversations/{uuid.uuid4()}/recommendations")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_recommendations_returns_saved_recommendations(client: AsyncClient, session: AsyncSession):
    p = await _seed_portfolio(session)
    convo_id = uuid.uuid4()
    session.add(Conversation(id=convo_id, user_id="default_user", portfolio_id=p.id))
    session.add(AdviceRecommendation(
        id=uuid.uuid4(), user_id="default_user", portfolio_id=p.id, kind="THESIS",
        rationale="Long-term bullish on the sector.", evidence=["recent_news: strong earnings"],
        confidence=Decimal("0.700"), status="PROPOSED",
    ))
    await session.commit()

    resp = await client.get(f"/v5/adviser/conversations/{convo_id}/recommendations")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["kind"] == "THESIS"
    assert body[0]["status"] == "PROPOSED"
