"""Layer 2 §4.7 Pillar-3 follow-through: commodity and insider/
congressional narrative endpoints.

Compute-on-miss, same shape as ``src/api/routers/interpret.py``: a GET
either serves a fresh cached row or computes+persists it inline.
``?refresh=true`` forces recomputation even when a fresh row exists.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.client import get_ai_client
from src.ai.narratives.commodity import get_or_compute_commodity_narrative
from src.ai.narratives.insider import get_or_compute_insider_narrative
from src.api.deps import get_session
from src.schemas.pillar3_narratives import CommodityNarrativeResponse, InsiderNarrativeResponse

router = APIRouter(tags=["AI - Pillar 3 Narratives"])


@router.get("/commodities/{commodity_code}/narrative", response_model=CommodityNarrativeResponse)
async def get_commodity_narrative(
    commodity_code: str,
    refresh: bool = Query(False, description="Force recompute, bypassing the cache"),
    session: AsyncSession = Depends(get_session),
):
    """AI narrative over this commodity's recent price action, inventory
    level, and any corroborating COMMODITY-tagged news."""
    client = get_ai_client()
    row = await get_or_compute_commodity_narrative(
        session, client, commodity_code.upper(), force_refresh=refresh,
    )
    await session.commit()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No narrative available for commodity '{commodity_code}' "
                "(no price data, or AI disabled with no cached result)"
            ),
        )
    return CommodityNarrativeResponse.model_validate(row)


@router.get("/entities/{entity_id}/insider-narrative", response_model=InsiderNarrativeResponse)
async def get_insider_narrative(
    entity_id: uuid.UUID,
    refresh: bool = Query(False, description="Force recompute, bypassing the cache"),
    session: AsyncSession = Depends(get_session),
):
    """AI narrative over this entity's recent Form 4 insider signals and
    congressional STOCK Act disclosures."""
    client = get_ai_client()
    row = await get_or_compute_insider_narrative(
        session, client, entity_id, force_refresh=refresh,
    )
    await session.commit()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No narrative available for entity '{entity_id}' "
                "(unknown entity, no insider/congressional data, or AI disabled with no cached result)"
            ),
        )
    return InsiderNarrativeResponse.model_validate(row)
