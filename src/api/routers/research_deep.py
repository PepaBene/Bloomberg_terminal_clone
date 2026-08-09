"""Layer 2 — on-demand Deep Research API (AI_THREE_LAYER_REBUILD_PLAN.md §4.6).

``POST /v5/research/deep`` creates a ``ResearchReport`` row immediately
(so callers always get a stable ``report_id``, even if the connection
drops mid-run) and streams progress over SSE while the multi-step
research agent runs, per the plan's "Streams progress over SSE"
requirement. ``GET /v5/research/reports/{id}`` serves a report without
re-running anything -- for a client that lost its stream or wants to
revisit a past report.

The streaming generator deliberately does NOT reuse the request-scoped
``Depends(get_session)`` session: FastAPI tears down generator-based
dependencies as soon as the endpoint FUNCTION returns, which happens the
moment a ``StreamingResponse`` is constructed -- well before Starlette
actually drains the generator body. Using that session inside the
generator would mean operating on an already-closed session for the
entire research run. Instead, the request-scoped session is used only for
the fast "create the pending row" step, and the generator opens its own
session via ``get_session_factory()`` for the run's lifetime, the same
pattern ``scripts/interpret_batch.py`` uses outside a request at all.
"""
from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.agents.loop import AgentStep
from src.ai.client import get_ai_client
from src.ai.research.store import create_pending_report, run_and_persist_research
from src.ai.streaming import SSEEvent, format_sse, sse_response
from src.api.deps import get_session
from src.database import get_session_factory
from src.models.research_report import ResearchReport
from src.schemas.research_report import DeepResearchRequest, ResearchReportResponse

router = APIRouter(tags=["AI - Deep Research"])

_SENTINEL = object()


async def _resolve_subject_label(session: AsyncSession, req: DeepResearchRequest) -> str:
    if req.free_text:
        return req.free_text
    if req.subject_type == "ENTITY" and req.subject_id:
        from src.models.entity import Entity

        try:
            entity_uuid = uuid.UUID(req.subject_id)
        except ValueError:
            return req.subject_id
        entity = await session.get(Entity, entity_uuid)
        if entity is not None:
            return entity.legal_name
    return req.subject_id or "(unspecified subject)"


async def _stream_research(report_id: uuid.UUID) -> "asyncio.AsyncIterator[str]":
    yield format_sse(SSEEvent(event="report_created", data={"report_id": str(report_id)}))

    queue: asyncio.Queue = asyncio.Queue()

    async def on_step(step: AgentStep) -> None:
        await queue.put({
            "tool_calls": [c["name"] for c in step.tool_calls],
            "note": (step.text or "")[:280] or None,
        })

    async def run_and_signal(session: AsyncSession, client) -> ResearchReport:
        report = await session.get(ResearchReport, report_id)
        try:
            return await run_and_persist_research(session, client, report, on_step=on_step)
        finally:
            await queue.put(_SENTINEL)

    async with get_session_factory()() as run_session:
        client = get_ai_client()
        task = asyncio.create_task(run_and_signal(run_session, client))

        while True:
            item = await queue.get()
            if item is _SENTINEL:
                break
            yield format_sse(SSEEvent(event="step", data=item))

        report = await task
        if report.status == "COMPLETE":
            payload = ResearchReportResponse.from_report(report).model_dump(mode="json")
            yield format_sse(SSEEvent(event="done", data=payload))
        else:
            yield format_sse(SSEEvent(
                event="error", data={"report_id": str(report_id), "message": report.error or "research failed"},
            ))


@router.post("/research/deep")
async def start_deep_research(
    req: DeepResearchRequest,
    session: AsyncSession = Depends(get_session),
):
    """Kick off a Deep Research run and stream its progress over SSE.

    Event types: ``report_created`` ({report_id}), ``step`` ({tool_calls,
    note}) per agent turn, then a terminal ``done`` (the full
    ResearchReportResponse) or ``error`` ({report_id, message}).
    """
    subject_label = await _resolve_subject_label(session, req)
    report = await create_pending_report(
        session, subject_type=req.subject_type, subject_id=req.subject_id,
        subject_label=subject_label, focus=req.focus,
    )
    await session.commit()

    return sse_response(_stream_research(report.id))


@router.get("/research/reports/{report_id}", response_model=ResearchReportResponse)
async def get_research_report(
    report_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Fetch a previously created/completed research report without
    re-running anything."""
    report = await session.get(ResearchReport, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Research report '{report_id}' not found")
    return ResearchReportResponse.from_report(report)
