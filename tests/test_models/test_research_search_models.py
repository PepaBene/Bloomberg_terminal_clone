"""Tests for Pillar 3 Phase 4B: Semantic Search models."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from src.models.entity import Entity
from src.models.semantic_search import SearchDocument, SearchQuery


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_entity(session, entity_id: uuid.UUID | None = None) -> Entity:
    eid = entity_id or uuid.uuid4()
    entity = Entity(
        entity_id=eid,
        entity_type="PUBLIC_COMPANY",
        legal_name="Search Test Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()
    return entity


# ── SearchDocument Tests ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_search_document(session):
    """Create a search document with all fields and verify."""
    entity = await _seed_entity(session)
    did = uuid.uuid4()
    doc = SearchDocument(
        id=did,
        source_type="10K",
        source_id="SEC-10K-2025-001",
        title="Annual Report 2024",
        author="Apple Inc.",
        publish_date=date(2025, 10, 30),
        entity_id=entity.entity_id,
        chunk_index=0,
        chunk_text="Revenue grew 12% year over year driven by services.",
        chunk_token_count=10,
        embedding_model="text-embedding-3-small",
    )
    session.add(doc)
    await session.flush()

    result = await session.execute(
        select(SearchDocument).where(SearchDocument.id == did)
    )
    fetched = result.scalar_one()
    assert fetched.source_type == "10K"
    assert fetched.source_id == "SEC-10K-2025-001"
    assert fetched.title == "Annual Report 2024"
    assert fetched.chunk_index == 0
    assert fetched.chunk_text == "Revenue grew 12% year over year driven by services."
    assert fetched.chunk_token_count == 10
    assert fetched.embedding_model == "text-embedding-3-small"
    assert fetched.entity_id == entity.entity_id


@pytest.mark.asyncio
async def test_search_document_nullable_fields(session):
    """Create a search document with minimal required fields."""
    did = uuid.uuid4()
    doc = SearchDocument(
        id=did,
        source_type="PRESS_RELEASE",
        chunk_index=0,
        chunk_text="Minimal document chunk.",
    )
    session.add(doc)
    await session.flush()

    result = await session.execute(
        select(SearchDocument).where(SearchDocument.id == did)
    )
    fetched = result.scalar_one()
    assert fetched.source_type == "PRESS_RELEASE"
    assert fetched.source_id is None
    assert fetched.title is None
    assert fetched.author is None
    assert fetched.publish_date is None
    assert fetched.entity_id is None


@pytest.mark.asyncio
async def test_search_document_jsonb_metadata(session):
    """Verify JSONB metadata field round-trips correctly."""
    did = uuid.uuid4()
    metadata = {"section": "Risk Factors", "page": 42, "tags": ["risk", "regulatory"]}
    doc = SearchDocument(
        id=did,
        source_type="10K",
        chunk_index=1,
        chunk_text="Risk factor content here.",
        metadata_=metadata,
    )
    session.add(doc)
    await session.flush()

    result = await session.execute(
        select(SearchDocument).where(SearchDocument.id == did)
    )
    fetched = result.scalar_one()
    assert fetched.metadata_ == metadata
    assert fetched.metadata_["section"] == "Risk Factors"


@pytest.mark.asyncio
async def test_search_document_embedding_vector(session):
    """Verify JSONB embedding_vector field round-trips."""
    did = uuid.uuid4()
    embedding = {"vector": [0.1, 0.2, 0.3, 0.4], "dimensions": 4}
    doc = SearchDocument(
        id=did,
        source_type="EARNINGS_CALL",
        chunk_index=0,
        chunk_text="Embedding test chunk.",
        embedding_vector=embedding,
    )
    session.add(doc)
    await session.flush()

    result = await session.execute(
        select(SearchDocument).where(SearchDocument.id == did)
    )
    fetched = result.scalar_one()
    assert fetched.embedding_vector == embedding
    assert len(fetched.embedding_vector["vector"]) == 4


@pytest.mark.asyncio
async def test_search_document_multiple_chunks(session):
    """Create multiple chunks for the same source document."""
    entity = await _seed_entity(session)
    source_id = "DOC-MULTI-001"

    for i in range(5):
        session.add(SearchDocument(
            id=uuid.uuid4(),
            source_type="RESEARCH_NOTE",
            source_id=source_id,
            entity_id=entity.entity_id,
            chunk_index=i,
            chunk_text=f"Chunk {i} text content.",
        ))
    await session.flush()

    result = await session.execute(
        select(SearchDocument)
        .where(SearchDocument.source_id == source_id)
        .order_by(SearchDocument.chunk_index)
    )
    rows = result.scalars().all()
    assert len(rows) == 5
    assert rows[0].chunk_index == 0
    assert rows[4].chunk_index == 4


# ── SearchQuery Tests ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_search_query(session):
    """Create a search query record and verify."""
    qid = uuid.uuid4()
    query = SearchQuery(
        id=qid,
        user_id="analyst_001",
        query_text="Fed rate impact on tech sector",
        result_count=15,
        execution_time_ms=120,
        top_result_relevance=Decimal("0.95"),
        ai_synthesis="The Fed rate decision is expected to impact tech valuations.",
    )
    session.add(query)
    await session.flush()

    result = await session.execute(
        select(SearchQuery).where(SearchQuery.id == qid)
    )
    fetched = result.scalar_one()
    assert fetched.user_id == "analyst_001"
    assert fetched.query_text == "Fed rate impact on tech sector"
    assert fetched.result_count == 15
    assert fetched.execution_time_ms == 120
    assert fetched.top_result_relevance == Decimal("0.95")
    assert fetched.ai_synthesis is not None


@pytest.mark.asyncio
async def test_search_query_minimal(session):
    """Create a search query with minimal fields."""
    qid = uuid.uuid4()
    query = SearchQuery(
        id=qid,
        user_id="analyst_002",
        query_text="earnings surprise",
    )
    session.add(query)
    await session.flush()

    result = await session.execute(
        select(SearchQuery).where(SearchQuery.id == qid)
    )
    fetched = result.scalar_one()
    assert fetched.user_id == "analyst_002"
    assert fetched.query_text == "earnings surprise"
    assert fetched.result_count is None
    assert fetched.execution_time_ms is None


@pytest.mark.asyncio
async def test_search_query_decimal_precision(session):
    """Decimal relevance score retains precision."""
    qid = uuid.uuid4()
    query = SearchQuery(
        id=qid,
        user_id="analyst_003",
        query_text="precision test",
        top_result_relevance=Decimal("0.87"),
    )
    session.add(query)
    await session.flush()

    result = await session.execute(
        select(SearchQuery).where(SearchQuery.id == qid)
    )
    fetched = result.scalar_one()
    assert fetched.top_result_relevance == Decimal("0.87")


@pytest.mark.asyncio
async def test_search_query_ordering(session):
    """Verify queries can be ordered by created_at."""
    ids = []
    for i in range(3):
        qid = uuid.uuid4()
        ids.append(qid)
        session.add(SearchQuery(
            id=qid,
            user_id="analyst_order",
            query_text=f"query {i}",
        ))
    await session.flush()

    result = await session.execute(
        select(SearchQuery)
        .where(SearchQuery.user_id == "analyst_order")
        .order_by(SearchQuery.created_at.desc().nullslast())
    )
    rows = result.scalars().all()
    assert len(rows) == 3
