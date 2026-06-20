"""Automatic Model Builder API endpoints.

Auto-assembles scored analytical models for ECONOMIC, MARKET, INDUSTRY,
CORPORATE, and COMPANY scopes. The generic ``/build`` endpoint accepts
caller-supplied metrics; the convenience endpoints assemble inputs from the
platform's own data (fundamentals, macro series) before modeling.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.engines.auto_model_builder import SCOPES, build_model
from src.models.entity import Entity
from src.models.fundamentals import FinancialPeriod, IncomeStatement
from src.schemas.auto_model import AnalyticalModelResponse, ModelBuildRequest

router = APIRouter(prefix="/models", tags=["Auto Model Builder"])


@router.get("/scopes")
async def list_scopes():
    """List the analytical model scopes the builder supports."""
    return {"scopes": list(SCOPES)}


@router.post("/build", response_model=AnalyticalModelResponse)
async def build(request: ModelBuildRequest):
    """Build a model from caller-supplied metrics for any scope."""
    try:
        model = build_model(request.scope, request.data, request.subject)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return model.to_dict()


@router.get("/company/{entity_id}", response_model=AnalyticalModelResponse)
async def build_company_model_endpoint(
    entity_id: uuid.UUID, session: AsyncSession = Depends(get_session)
):
    """Auto-build a full company model from the latest fundamentals on file."""
    entity = (
        await session.execute(select(Entity).where(Entity.entity_id == entity_id))
    ).scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    # Pull the two most recent annual income statements for growth/margins.
    periods = (
        await session.execute(
            select(FinancialPeriod)
            .where(FinancialPeriod.entity_id == entity_id)
            .order_by(FinancialPeriod.period_end_date.desc())
            .limit(2)
        )
    ).scalars().all()

    data: dict = {}
    statements = []
    for period in periods:
        stmt = (
            await session.execute(
                select(IncomeStatement).where(IncomeStatement.period_id == period.period_id)
            )
        ).scalar_one_or_none()
        if stmt:
            statements.append(stmt)

    if statements:
        latest = statements[0]
        rev = float(latest.total_revenue) if latest.total_revenue is not None else None
        op = float(latest.operating_income) if latest.operating_income is not None else None
        ni = float(latest.net_income) if latest.net_income is not None else None
        if rev and op is not None:
            data["ebitda_margin"] = round(op / rev * 100, 2)
        if len(statements) > 1 and statements[1].total_revenue:
            prev_rev = float(statements[1].total_revenue)
            if prev_rev:
                data["revenue_growth"] = round((rev - prev_rev) / prev_rev * 100, 2)
        if rev and ni is not None:
            data["net_income"] = ni

    subject = getattr(entity, "legal_name", None) or getattr(entity, "name", None) or str(entity_id)
    model = build_model("COMPANY", data, subject)
    return model.to_dict()
