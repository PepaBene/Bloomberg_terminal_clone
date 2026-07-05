"""Complex Financial Structure analysis API endpoints.

Analyzes corporate org/subsidiary trees, multi-class voting structures,
off-balance-sheet/VIE exposure, and debt subordination waterfalls. The
generic ``/analyze`` endpoint accepts a caller-supplied payload; the
``/entity/{id}`` endpoint enriches it with the platform's stored
capital-structure tranches.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.engines.complex_structure import analyze_complex_structure
from src.models.capital_structure import CapitalStructure, DebtTranche
from src.models.entity import Entity
from src.schemas.complex_structure import (
    StructureAnalysisRequest,
    StructureReportResponse,
)

router = APIRouter(prefix="/complex-structure", tags=["Complex Structure"])


@router.post("/analyze", response_model=StructureReportResponse)
async def analyze_structure(request: StructureAnalysisRequest):
    """Analyze a complex financial structure from a caller-supplied payload."""
    report = analyze_complex_structure(request.model_dump(exclude={"subject"}), request.subject)
    return asdict(report)


@router.get("/entity/{entity_id}", response_model=StructureReportResponse)
async def analyze_entity_structure(
    entity_id: uuid.UUID, session: AsyncSession = Depends(get_session)
):
    """Analyze structure for an entity, pulling its stored debt tranches.

    Subsidiary, share-class, and off-balance-sheet inputs are included when
    available; debt tranches are sourced from the latest capital structure.
    """
    entity = (
        await session.execute(select(Entity).where(Entity.entity_id == entity_id))
    ).scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    cap = (
        await session.execute(
            select(CapitalStructure)
            .where(CapitalStructure.entity_id == entity_id)
            .order_by(CapitalStructure.as_of_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    debt_tranches: list[dict] = []
    if cap is not None:
        tranches = (
            await session.execute(
                select(DebtTranche).where(
                    DebtTranche.capital_structure_id == cap.capital_structure_id
                )
            )
        ).scalars().all()
        for t in tranches:
            debt_tranches.append(
                {
                    "instrument_name": t.instrument_name,
                    "principal_amount": float(t.principal_amount)
                    if t.principal_amount is not None
                    else 0.0,
                    "seniority_rank": t.seniority_rank,
                    "is_secured": (t.instrument_type or "").upper().startswith("SECURED")
                    if t.instrument_type
                    else False,
                }
            )

    subject = getattr(entity, "legal_name", None) or str(entity_id)
    payload = {"debt_tranches": debt_tranches}
    report = analyze_complex_structure(payload, subject)
    return asdict(report)
