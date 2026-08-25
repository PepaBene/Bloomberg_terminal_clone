"""API tests for the Layer 2 Deep Research endpoint
(src/api/routers/research_deep.py).

Only request validation and the GET-by-id read path are exercised here.
``POST /v5/research/deep``'s streaming generator deliberately opens its
OWN session via ``get_session_factory()`` (see that router's module
docstring for why -- FastAPI tears down ``Depends(get_session)`` before a
StreamingResponse's body generator runs), which means it always talks to
the real configured database, not this test suite's SQLite engine --
there's no live Postgres in this sandbox to run it against. Same
untestable-via-HTTP situation as scripts/interpret_batch.py and
scripts/backfill.py. The actual business logic that runs inside the
stream (gather_research/structure_report/run_and_persist_research) has
full unit coverage in tests/test_ai/test_researcher.py and
tests/test_ai/test_research_store.py against the SQLite session fixture
directly, bypassing this router's get_session_factory() indirection.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.research_report import ResearchReport


@pytest.mark.asyncio
async def test_post_deep_research_requires_subject_id_or_free_text(client: AsyncClient):
    resp = await client.post("/v5/research/deep", json={"subject_type": "FREE_TEXT"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_research_report_404_for_unknown_id(client: AsyncClient):
    resp = await client.get(f"/v5/research/reports/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_research_report_returns_completed_report(client: AsyncClient, session: AsyncSession):
    report_id = uuid.uuid4()
    session.add(ResearchReport(
        id=report_id, subject_type="ENTITY", subject_id="e1", subject_label="Acme Corp",
        focus="competitive risk",
        sections=[{"title": "Overview", "content": "All is well.", "citations": ["Reuters"]}],
        sources=["Reuters"], confidence=0.75, model="claude-opus-4-8", status="COMPLETE",
        completed_at=datetime.now(timezone.utc),
    ))
    await session.commit()

    resp = await client.get(f"/v5/research/reports/{report_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["subject_label"] == "Acme Corp"
    assert body["status"] == "COMPLETE"
    assert body["sections"][0]["title"] == "Overview"
    assert body["sources"] == ["Reuters"]
    assert body["confidence"] == 0.75


@pytest.mark.asyncio
async def test_get_research_report_pending_status(client: AsyncClient, session: AsyncSession):
    report_id = uuid.uuid4()
    session.add(ResearchReport(
        id=report_id, subject_type="FREE_TEXT", subject_label="What is the EV battery outlook?",
        status="PENDING",
    ))
    await session.commit()

    resp = await client.get(f"/v5/research/reports/{report_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "PENDING"
    assert body["sections"] == []
    assert body["sources"] == []
