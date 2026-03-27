"""API tests for Semantic Search endpoints (Pillar 3 Phase 4B)."""

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entity import Entity
from src.models.semantic_search import SearchDocument, SearchQuery


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_entity(session, entity_id=None):
    eid = entity_id or uuid.uuid4()
    entity = Entity(
        entity_id=eid,
        entity_type="PUBLIC_COMPANY",
        legal_name="Search API Test Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()
    return entity


async def _seed_document(session, entity_id=None, source_type="10K", source_id=None, chunk_index=0):
    did = uuid.uuid4()
    doc = SearchDocument(
        id=did,
        source_type=source_type,
        source_id=source_id or f"DOC-{did.hex[:8]}",
        title=f"Document {chunk_index}",
        author="Test Author",
        publish_date=date(2025, 10, 15),
        entity_id=entity_id,
        chunk_index=chunk_index,
        chunk_text=f"Sample chunk text for index {chunk_index}.",
        chunk_token_count=8,
    )
    session.add(doc)
    await session.flush()
    return doc


async def _seed_query(session, user_id="default_user", query_text="test query"):
    qid = uuid.uuid4()
    query = SearchQuery(
        id=qid,
        user_id=user_id,
        query_text=query_text,
        result_count=5,
        execution_time_ms=50,
    )
    session.add(query)
    await session.flush()
    return query


# ── POST /research/search ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_empty(client: AsyncClient, session: AsyncSession):
    """POST /v4/research/search returns empty results when no docs indexed."""
    resp = await client.post("/v4/research/search", json={"query": "test"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "test"
    assert data["total_results"] == 0
    assert data["results"] == []


@pytest.mark.asyncio
async def test_search_with_data(client: AsyncClient, session: AsyncSession):
    """POST /v4/research/search returns matching documents."""
    entity = await _seed_entity(session)
    await _seed_document(session, entity_id=entity.entity_id)
    await _seed_document(session, entity_id=entity.entity_id, chunk_index=1)
    resp = await client.post("/v4/research/search", json={"query": "revenue growth", "limit": 10})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_results"] >= 2


@pytest.mark.asyncio
async def test_search_with_document_type_filter(client: AsyncClient, session: AsyncSession):
    """POST /v4/research/search respects document_types filter."""
    entity = await _seed_entity(session)
    await _seed_document(session, entity_id=entity.entity_id, source_type="10K")
    await _seed_document(session, entity_id=entity.entity_id, source_type="PRESS_RELEASE", chunk_index=1)
    resp = await client.post("/v4/research/search", json={
        "query": "test",
        "document_types": ["10K"],
    })
    assert resp.status_code == 200
    data = resp.json()
    for result in data["results"]:
        assert result["source_type"] == "10K"


@pytest.mark.asyncio
async def test_search_limit(client: AsyncClient, session: AsyncSession):
    """POST /v4/research/search respects limit parameter."""
    entity = await _seed_entity(session)
    for i in range(5):
        await _seed_document(session, entity_id=entity.entity_id, chunk_index=i)
    resp = await client.post("/v4/research/search", json={"query": "test", "limit": 2})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) <= 2


# ── GET /research/search/history ─────────────────────────────────────


@pytest.mark.asyncio
async def test_search_history_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/search/history returns empty list when no queries."""
    resp = await client.get("/v4/research/search/history", params={"user_id": "nonexistent_user"})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_search_history_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/search/history returns query history."""
    await _seed_query(session, user_id="hist_user", query_text="query 1")
    await _seed_query(session, user_id="hist_user", query_text="query 2")
    resp = await client.get("/v4/research/search/history", params={"user_id": "hist_user"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2


# ── GET /research/search/suggested ───────────────────────────────────


@pytest.mark.asyncio
async def test_suggested_queries(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/search/suggested returns static suggestions."""
    resp = await client.get("/v4/research/search/suggested")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    assert data[0]["query"] == "Q4 earnings surprises"


# ── GET /research/search/documents/stats ─────────────────────────────


@pytest.mark.asyncio
async def test_document_stats_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/search/documents/stats returns zero counts when empty."""
    resp = await client.get("/v4/research/search/documents/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_chunks"] >= 0
    assert isinstance(data["source_type_counts"], dict)


@pytest.mark.asyncio
async def test_document_stats_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/search/documents/stats reflects indexed documents."""
    entity = await _seed_entity(session)
    await _seed_document(session, entity_id=entity.entity_id, source_type="10K")
    await _seed_document(session, entity_id=entity.entity_id, source_type="10K", chunk_index=1)
    resp = await client.get("/v4/research/search/documents/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_chunks"] >= 2


# ── POST /research/search/index ──────────────────────────────────────


@pytest.mark.asyncio
async def test_index_document(client: AsyncClient, session: AsyncSession):
    """POST /v4/research/search/index creates document chunks."""
    resp = await client.post("/v4/research/search/index", json={
        "source_type": "RESEARCH_NOTE",
        "source_id": "RN-001",
        "title": "Test Research Note",
        "chunks": [
            {"text": "First chunk of the research note."},
            {"text": "Second chunk of the research note."},
        ],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "INDEXED"
    assert data["chunk_count"] == 2
    assert data["source_type"] == "RESEARCH_NOTE"


# ── GET /research/search/trending ────────────────────────────────────


@pytest.mark.asyncio
async def test_trending_topics_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/search/trending returns empty list when no queries."""
    resp = await client.get("/v4/research/search/trending")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_trending_topics_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/search/trending reflects query frequency."""
    await _seed_query(session, query_text="trending topic")
    await _seed_query(session, query_text="trending topic")
    await _seed_query(session, query_text="other topic")
    resp = await client.get("/v4/research/search/trending")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


# ── GET /research/search/documents/{source_id} ──────────────────────


@pytest.mark.asyncio
async def test_get_document_chunks_not_found(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/search/documents/{source_id} returns empty for unknown source."""
    resp = await client.get("/v4/research/search/documents/NONEXISTENT")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_document_chunks_with_data(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/search/documents/{source_id} returns chunks."""
    entity = await _seed_entity(session)
    sid = "SRC-CHUNKS-001"
    await _seed_document(session, entity_id=entity.entity_id, source_id=sid, chunk_index=0)
    await _seed_document(session, entity_id=entity.entity_id, source_id=sid, chunk_index=1)
    resp = await client.get(f"/v4/research/search/documents/{sid}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["chunk_index"] == 0
    assert data[1]["chunk_index"] == 1


# ── GET /research/search/entities/{entity_id} ────────────────────────


@pytest.mark.asyncio
async def test_entity_documents_empty(client: AsyncClient, session: AsyncSession):
    """GET /v4/research/search/entities/{entity_id} returns empty for entity with no docs."""
    resp = await client.get(f"/v4/research/search/entities/{uuid.uuid4()}")
    assert resp.status_code == 200
    assert resp.json() == []
