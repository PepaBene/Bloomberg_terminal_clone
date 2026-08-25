"""Layer 1 — Interpreter API endpoints (AI_THREE_LAYER_REBUILD_PLAN.md Phase 1).

Compute-on-miss: a GET either serves a fresh cached ``interpretations`` row
or computes+persists it inline (no separate "warm the cache" step needed
for a first-time read) — see ``src/ai/interpret/store.py``. ``?refresh=true``
forces recomputation even when a fresh row exists.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.client import get_ai_client
from src.ai.interpret.store import (
    get_or_compute_entity_interpretation,
    get_or_compute_metric_interpretation,
)
from src.api.deps import get_session
from src.models.entity import Entity
from src.schemas.interpretation import (
    EntityInterpretationResponse,
    MetricInterpretationResponse,
    SubjectInterpretationResponse,
)

router = APIRouter(tags=["AI - Interpreter"])


async def _get_entity_or_404(session: AsyncSession, entity_id: uuid.UUID) -> Entity:
    entity = (
        await session.execute(select(Entity).where(Entity.entity_id == entity_id))
    ).scalar_one_or_none()
    if entity is None:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")
    return entity


@router.get("/interpret/entities/{entity_id}", response_model=EntityInterpretationResponse)
async def get_entity_interpretation(
    entity_id: uuid.UUID,
    refresh: bool = Query(False, description="Force recompute, bypassing the cache"),
    session: AsyncSession = Depends(get_session),
):
    """Grounded interpretations for every computed metric this entity has,
    plus a connected subject-level synthesis. Powers the entity page's
    "Interpretation" panel.
    """
    entity = await _get_entity_or_404(session, entity_id)
    client = get_ai_client()

    result = await get_or_compute_entity_interpretation(
        session, client, entity_id, subject_label=entity.legal_name, force_refresh=refresh,
    )
    await session.commit()

    ctx = result["context"]
    return EntityInterpretationResponse(
        entity_id=entity_id,
        as_of=ctx.as_of,
        analytics_version=ctx.analytics_version,
        metrics={
            name: MetricInterpretationResponse.model_validate(row)
            for name, row in result["metrics"].items()
        },
        subject=(
            SubjectInterpretationResponse.model_validate(result["subject"])
            if result["subject"] is not None else None
        ),
    )


@router.get(
    "/interpret/entities/{entity_id}/metrics/{metric_key}",
    response_model=MetricInterpretationResponse,
)
async def get_metric_interpretation(
    entity_id: uuid.UUID,
    metric_key: str,
    refresh: bool = Query(False, description="Force recompute, bypassing the cache"),
    session: AsyncSession = Depends(get_session),
):
    """Single-metric popover: "Interpret this number" for one displayed
    figure. Lighter than the full entity endpoint -- only the requested
    metric is computed on a cache miss, not every metric plus synthesis.
    """
    await _get_entity_or_404(session, entity_id)
    client = get_ai_client()

    ctx, row = await get_or_compute_metric_interpretation(
        session, client, entity_id, metric_key.upper(), force_refresh=refresh,
    )
    await session.commit()

    if row is None:
        if not any(m.metric_name == metric_key.upper() for m in ctx.metrics):
            raise HTTPException(
                status_code=404,
                detail=f"No computed metric '{metric_key}' found for entity '{entity_id}'",
            )
        raise HTTPException(
            status_code=503,
            detail="Interpretation unavailable (AI disabled and no cached result)",
        )
    return MetricInterpretationResponse.model_validate(row)
