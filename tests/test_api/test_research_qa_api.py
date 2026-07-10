"""API tests for Analyst Q&A endpoints (Pillar 3 Phase 4B)."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entity import Entity
from src.models.analyst_qa import QASession, QAFeedback


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_entity(session, entity_id=None):
    eid = entity_id or uuid.uuid4()
    entity = Entity(
        entity_id=eid,
        entity_type="PUBLIC_COMPANY",
        legal_name="QA API Test Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()
    return entity


async def _seed_qa_session(session, user_id="default_user", entity_id=None,
                           question="What is the revenue trend?"):
    sid = uuid.uuid4()
    qa = QASession(
        id=sid,
        user_id=user_id,
        entity_id=entity_id,
        question=question,
        answer_text="AI-generated answer for testing.",
        answer_type="AI_GENERATED",
        follow_up_suggestions={"suggestions": ["What about margins?", "Compare with peers"]},
        execution_time_ms=100,
    )
    session.add(qa)
    await session.flush()
    return qa


# ── POST /research/qa/ask ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ask_question(client: AsyncClient, session: AsyncSession):
    """POST /v4/research/qa/ask creates a new Q&A session."""
    resp = await client.post("/v4/research/qa/ask", json={
        "question": "What are the key growth drivers?",
        "user_id": "analyst_001",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["question"] == "What are the key growth drivers?"
    assert data["user_id"] == "analyst_001"
    # No ANTHROPIC_API_KEY in the test environment — answer_text must be
    # None (honest "AI unavailable"), not a fabricated placeholder string.
    assert data["answer_text"] is None
    assert data["answer_type"] == "AI_DISABLED"


@pytest.mark.asyncio
async def test_ask_question_with_entity(client: AsyncClient, session: AsyncSession):
    """POST /v4/research/qa/ask with entity_id context."""
    entity = await _seed_entity(session)
    resp = await client.post("/v4/research/qa/ask", json={
        "question": "What are the risks?",
        "entity_id": str(entity.entity_id),
        "user_id": "analyst_002",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["entity_id"] == str(entity.entity_id)


@pytest.mark.asyncio
async def test_ask_question_with_context(client: AsyncClient, session: AsyncSession):
    """POST /v4/research/qa/ask with context dict."""
    resp = await client.post("/v4/research/qa/ask", json={
        "question": "What about the competitive landscape?",
        "context": {"sector": "Technology", "market_cap": "LARGE"},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["sources"] == {"sector": "Technology", "market_cap": "LARGE"}


@pytest.mark.asyncio
async def test_ask_question_default_user(client: AsyncClient, session: AsyncSession):
    """POST /v4/research/qa/ask uses default_user when none provided."""
    resp = await client.post("/v4/research/qa/ask", json={
        "question": "Simple question?",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == "default_user"


# ── GET /research/qa/history ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_qa_history_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/qa/history returns empty list when no sessions."""
    resp = await client.get("/v4/research/qa/history", params={"user_id": "nonexistent_user"})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_qa_history_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/qa/history returns session history."""
    await _seed_qa_session(session, user_id="hist_user", question="Q1?")
    await _seed_qa_session(session, user_id="hist_user", question="Q2?")
    resp = await client.get("/v4/research/qa/history", params={"user_id": "hist_user"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2


@pytest.mark.asyncio
async def test_qa_history_limit(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/qa/history respects limit parameter."""
    await _seed_qa_session(session, user_id="limit_user", question="Q1?")
    await _seed_qa_session(session, user_id="limit_user", question="Q2?")
    resp = await client.get("/v4/research/qa/history", params={"user_id": "limit_user", "limit": 1})
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ── GET /research/qa/popular ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_popular_questions_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/qa/popular returns empty list when no data."""
    resp = await client.get("/v4/research/qa/popular")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_popular_questions_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/qa/popular returns aggregated popular questions."""
    await _seed_qa_session(session, question="Popular question?")
    await _seed_qa_session(session, question="Popular question?")
    await _seed_qa_session(session, question="Other question?")
    resp = await client.get("/v4/research/qa/popular")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


# ── GET /research/qa/stats ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_qa_stats(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/qa/stats returns usage statistics."""
    resp = await client.get("/v4/research/qa/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_questions" in data
    assert "total_with_feedback" in data
    assert isinstance(data["answer_type_counts"], dict)


# ── GET /research/qa/by-entity/{entity_id} ───────────────────────────


@pytest.mark.asyncio
async def test_qa_by_entity_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/qa/by-entity/{entity_id} returns empty for entity with no Q&A."""
    resp = await client.get(f"/v4/research/qa/by-entity/{uuid.uuid4()}")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_qa_by_entity_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/qa/by-entity/{entity_id} returns entity Q&A sessions."""
    entity = await _seed_entity(session)
    await _seed_qa_session(session, entity_id=entity.entity_id, question="Entity Q?")
    resp = await client.get(f"/v4/research/qa/by-entity/{entity.entity_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["entity_id"] == str(entity.entity_id)


# ── GET /research/qa/{session_id} ────────────────────────────────────


@pytest.mark.asyncio
async def test_get_qa_session_not_found(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/qa/{session_id} returns 404 for unknown session."""
    resp = await client.get(f"/v4/research/qa/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_qa_session_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/qa/{session_id} returns session details."""
    qa = await _seed_qa_session(session)
    resp = await client.get(f"/v4/research/qa/{qa.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["question"] == "What is the revenue trend?"
    assert data["answer_text"] is not None


# ── POST /research/qa/{session_id}/feedback ──────────────────────────


@pytest.mark.asyncio
async def test_feedback_not_found(client: AsyncClient, session: AsyncSession):
    """POST /v4/research/qa/{session_id}/feedback returns 404 for unknown session."""
    resp = await client.post(f"/v4/research/qa/{uuid.uuid4()}/feedback", json={
        "rating": 5,
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_feedback_success(client: AsyncClient, session: AsyncSession):
    """POST /v4/research/qa/{session_id}/feedback creates feedback."""
    qa = await _seed_qa_session(session)
    resp = await client.post(f"/v4/research/qa/{qa.id}/feedback", json={
        "rating": 4,
        "feedback_text": "Good answer.",
        "is_accurate": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["rating"] == 4
    assert data["feedback_text"] == "Good answer."
    assert data["is_accurate"] is True


@pytest.mark.asyncio
async def test_feedback_rating_only(client: AsyncClient, session: AsyncSession):
    """POST /v4/research/qa/{session_id}/feedback works with rating only."""
    qa = await _seed_qa_session(session)
    resp = await client.post(f"/v4/research/qa/{qa.id}/feedback", json={
        "rating": 2,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["rating"] == 2
    assert data["feedback_text"] is None


# ── GET /research/qa/{session_id}/follow-ups ─────────────────────────


@pytest.mark.asyncio
async def test_follow_ups_not_found(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/qa/{session_id}/follow-ups returns 404 for unknown session."""
    resp = await client.get(f"/v4/research/qa/{uuid.uuid4()}/follow-ups")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_follow_ups_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/qa/{session_id}/follow-ups returns suggestions."""
    qa = await _seed_qa_session(session)
    resp = await client.get(f"/v4/research/qa/{qa.id}/follow-ups")
    assert resp.status_code == 200
    data = resp.json()
    assert "follow_up_suggestions" in data
    assert data["follow_up_suggestions"]["suggestions"] == ["What about margins?", "Compare with peers"]
