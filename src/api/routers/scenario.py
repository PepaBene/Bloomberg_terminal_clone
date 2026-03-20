"""Pillar 2: Scenario & Sensitivity API (Spec §10).

Endpoints for 2D/3D sensitivity, tornado charts, shock analysis,
pre-built scenarios, break-even search, and portfolio scenario impact.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.engines.e8_prebuilt_scenarios import list_prebuilt_scenarios, get_prebuilt_scenario
from src.engines.e8_scenario import ScenarioEngine
from src.schemas.scenario import (
    BreakevenRequest,
    BreakevenResponse,
    CustomShockRequest,
    PortfolioPositionImpact,
    PortfolioScenarioRequest,
    PortfolioScenarioResponse,
    PrebuiltScenarioSummary,
    Sensitivity2DRequest,
    Sensitivity2DResponse,
    Sensitivity3DRequest,
    Sensitivity3DResponse,
    ShockRequest,
    ShockResponse,
    TornadoRequest,
    TornadoResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v2/analytics/scenario", tags=["Scenario & Sensitivity"])

_engine = ScenarioEngine()


# ---------------------------------------------------------------------------
# 2D Sensitivity
# ---------------------------------------------------------------------------

@router.post("/sensitivity", response_model=Sensitivity2DResponse)
async def run_sensitivity_2d(
    req: Sensitivity2DRequest,
    session: AsyncSession = Depends(get_session),
):
    result = await _engine.run_sensitivity_2d(
        session,
        req.security_id,
        row_variable=req.row_variable,
        col_variable=req.col_variable,
        row_min=req.row_min,
        row_max=req.row_max,
        col_min=req.col_min,
        col_max=req.col_max,
        steps=req.steps,
        method=req.method,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Security not found or insufficient data")
    return result


# ---------------------------------------------------------------------------
# 3D Sensitivity
# ---------------------------------------------------------------------------

@router.post("/sensitivity/3d", response_model=Sensitivity3DResponse)
async def run_sensitivity_3d(
    req: Sensitivity3DRequest,
    session: AsyncSession = Depends(get_session),
):
    result = await _engine.run_sensitivity_3d(
        session,
        req.security_id,
        fixed_variable=req.fixed_variable,
        fixed_values=req.fixed_values,
        row_variable=req.row_variable,
        col_variable=req.col_variable,
        steps=req.steps,
        method=req.method,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Security not found or insufficient data")
    return result


# ---------------------------------------------------------------------------
# Tornado
# ---------------------------------------------------------------------------

@router.post("/tornado", response_model=TornadoResponse)
async def run_tornado(
    req: TornadoRequest,
    session: AsyncSession = Depends(get_session),
):
    result = await _engine.run_tornado(
        session,
        req.security_id,
        variables=req.variables,
        swing_pct=req.swing_pct,
        method=req.method,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Security not found or insufficient data")
    return result


# ---------------------------------------------------------------------------
# Shock
# ---------------------------------------------------------------------------

@router.post("/shock", response_model=ShockResponse)
async def run_shock(
    req: ShockRequest,
    session: AsyncSession = Depends(get_session),
):
    result = await _engine.run_shock(
        session,
        req.security_id,
        shock_vector=req.shock_vector,
        method=req.method,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Security not found or insufficient data")
    return result


# ---------------------------------------------------------------------------
# Pre-built Scenarios
# ---------------------------------------------------------------------------

@router.get("/shock/prebuilt", response_model=list[PrebuiltScenarioSummary])
async def list_prebuilt():
    return list_prebuilt_scenarios()


@router.post("/shock/custom", response_model=ShockResponse)
async def run_custom_shock(
    req: CustomShockRequest,
    session: AsyncSession = Depends(get_session),
):
    result = await _engine.run_shock(
        session,
        req.security_id,
        shock_vector=req.shock_vector,
        name=req.name,
        method=req.method,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Security not found or insufficient data")
    return result


# ---------------------------------------------------------------------------
# Breakeven
# ---------------------------------------------------------------------------

@router.post("/breakeven", response_model=BreakevenResponse)
async def run_breakeven(
    req: BreakevenRequest,
    session: AsyncSession = Depends(get_session),
):
    result = await _engine.run_breakeven(
        session,
        req.security_id,
        variable=req.variable,
        target_price=req.target_price,
        search_min=req.search_min,
        search_max=req.search_max,
        tolerance=req.tolerance,
        method=req.method,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Security not found or insufficient data")
    return result


# ---------------------------------------------------------------------------
# Portfolio Scenario
# ---------------------------------------------------------------------------

@router.post("/portfolio", response_model=PortfolioScenarioResponse)
async def run_portfolio_scenario(
    req: PortfolioScenarioRequest,
    session: AsyncSession = Depends(get_session),
):
    position_impacts: list[PortfolioPositionImpact] = []
    total_base = 0.0
    total_shocked = 0.0

    for pos in req.positions:
        result = await _engine.run_shock(
            session,
            pos.security_id,
            shock_vector=req.shock_vector,
            method=req.method,
            persist=False,
        )
        base = result["base_case_value"] if result else None
        shocked = result["shocked_value"] if result else None

        weighted_base = (base or 0.0) * pos.weight
        weighted_shocked = (shocked or 0.0) * pos.weight
        total_base += weighted_base
        total_shocked += weighted_shocked

        position_impacts.append(PortfolioPositionImpact(
            security_id=pos.security_id,
            weight=pos.weight,
            base_case_value=base,
            shocked_value=shocked,
            impact=round(weighted_shocked - weighted_base, 2) if base is not None and shocked is not None else None,
        ))

    total_impact = round(total_shocked - total_base, 2)
    impact_pct = round(total_impact / abs(total_base), 4) if total_base != 0 else None

    return PortfolioScenarioResponse(
        total_base_value=round(total_base, 2),
        total_shocked_value=round(total_shocked, 2),
        total_impact=total_impact,
        impact_pct=impact_pct,
        positions=position_impacts,
    )
