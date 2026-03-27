"""Macro Themes & Scenarios API endpoints (Pillar 3 Phase 4C)."""

import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.models.macro_themes import MacroThemeScore, MacroScenario
from src.models.scenario_impact import ScenarioCompanyImpact
from src.schemas.macro_themes_schema import (
    ScenarioCreateRequest,
    ScenarioImpactResponse,
    ScenarioResponse,
    ThemeScoreResponse,
    ThemeScreenRequest,
    ThemeScreenResponse,
)

router = APIRouter(tags=["Research - Macro Themes & Scenarios"])


def _float(val):
    return float(val) if val is not None else None


def _theme_score_response(row: MacroThemeScore) -> ThemeScoreResponse:
    return ThemeScoreResponse(
        id=row.id,
        entity_id=row.entity_id,
        theme=row.theme,
        exposure_score=_float(row.exposure_score),
        sensitivity_direction=row.sensitivity_direction,
        evidence=row.evidence,
        quantified_exposure=row.quantified_exposure,
        as_of_date=row.as_of_date,
        created_at=row.created_at,
    )


def _scenario_response(row: MacroScenario) -> ScenarioResponse:
    return ScenarioResponse(
        id=row.id,
        scenario_name=row.scenario_name,
        scenario_type=row.scenario_type,
        description=row.description,
        assumptions=row.assumptions,
        is_active=row.is_active,
        created_by=row.created_by,
        created_at=row.created_at,
    )


def _impact_response(row: ScenarioCompanyImpact) -> ScenarioImpactResponse:
    return ScenarioImpactResponse(
        id=row.id,
        scenario_id=row.scenario_id,
        entity_id=row.entity_id,
        base_eps=_float(row.base_eps),
        scenario_eps=_float(row.scenario_eps),
        eps_change_pct=_float(row.eps_change_pct),
        margin_impact_bps=_float(row.margin_impact_bps),
        rating_implication=row.rating_implication,
        price_target_scenario=_float(row.price_target_scenario),
        narrative=row.narrative,
        created_at=row.created_at,
    )


# ── Static routes (MUST come before parametric routes) ──────────────


@router.get(
    "/research/themes/dashboard",
    response_model=list[ThemeScoreResponse],
)
async def get_themes_dashboard(
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
):
    """Get all themes overview / dashboard."""
    result = await session.execute(
        select(MacroThemeScore)
        .order_by(MacroThemeScore.as_of_date.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [_theme_score_response(r) for r in rows]


@router.get(
    "/research/scenarios",
    response_model=list[ScenarioResponse],
)
async def list_scenarios(
    active_only: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """List available macro scenarios."""
    stmt = select(MacroScenario)
    if active_only:
        stmt = stmt.where(MacroScenario.is_active == True)  # noqa: E712
    stmt = stmt.order_by(MacroScenario.created_at.desc().nullslast()).limit(limit)

    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [_scenario_response(r) for r in rows]


@router.post(
    "/research/scenarios/custom",
    response_model=ScenarioResponse,
)
async def create_custom_scenario(
    body: ScenarioCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Create a custom macro scenario."""
    scenario = MacroScenario(
        id=uuid.uuid4(),
        scenario_name=body.scenario_name,
        scenario_type=body.scenario_type or "CUSTOM",
        description=body.description,
        assumptions=body.assumptions,
        created_by=body.created_by,
    )
    session.add(scenario)
    await session.flush()
    return _scenario_response(scenario)


@router.get(
    "/research/scenarios/compare",
    response_model=list[ScenarioImpactResponse],
)
async def compare_scenarios(
    scenario_ids: str = Query(description="Comma-separated scenario UUIDs"),
    entity_id: uuid.UUID = Query(description="Entity to compare across scenarios"),
    session: AsyncSession = Depends(get_session),
):
    """Compare impact of multiple scenarios on a single entity."""
    ids = [uuid.UUID(s.strip()) for s in scenario_ids.split(",") if s.strip()]
    if not ids:
        raise HTTPException(status_code=400, detail="At least one scenario_id is required")

    result = await session.execute(
        select(ScenarioCompanyImpact)
        .where(
            and_(
                ScenarioCompanyImpact.entity_id == entity_id,
                ScenarioCompanyImpact.scenario_id.in_(ids),
            )
        )
        .order_by(ScenarioCompanyImpact.created_at.desc().nullslast())
    )
    rows = result.scalars().all()
    return [_impact_response(r) for r in rows]


# ── Parametric routes ───────────────────────────────────────────────


@router.get(
    "/research/themes/{entity_id}",
    response_model=list[ThemeScoreResponse],
)
async def get_entity_theme_exposures(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get macro theme exposure scores for an entity."""
    result = await session.execute(
        select(MacroThemeScore)
        .where(MacroThemeScore.entity_id == entity_id)
        .order_by(MacroThemeScore.as_of_date.desc())
    )
    rows = result.scalars().all()
    return [_theme_score_response(r) for r in rows]


@router.get(
    "/research/themes/{entity_id}/history",
    response_model=list[ThemeScoreResponse],
)
async def get_theme_score_history(
    entity_id: uuid.UUID,
    theme: str = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
):
    """Get historical theme scores for an entity."""
    stmt = select(MacroThemeScore).where(MacroThemeScore.entity_id == entity_id)
    if theme:
        stmt = stmt.where(MacroThemeScore.theme == theme)
    stmt = stmt.order_by(MacroThemeScore.as_of_date.desc()).limit(limit)

    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [_theme_score_response(r) for r in rows]


@router.post(
    "/research/themes/screen",
    response_model=list[ThemeScreenResponse],
)
async def screen_by_theme(
    body: ThemeScreenRequest,
    session: AsyncSession = Depends(get_session),
):
    """Screen entities by macro theme exposure."""
    stmt = select(MacroThemeScore).where(MacroThemeScore.theme == body.theme)
    if body.min_exposure is not None:
        stmt = stmt.where(MacroThemeScore.exposure_score >= body.min_exposure)
    if body.max_exposure is not None:
        stmt = stmt.where(MacroThemeScore.exposure_score <= body.max_exposure)
    if body.sensitivity_direction:
        stmt = stmt.where(MacroThemeScore.sensitivity_direction == body.sensitivity_direction)
    stmt = stmt.order_by(MacroThemeScore.exposure_score.desc().nullslast()).limit(body.limit)

    result = await session.execute(stmt)
    rows = result.scalars().all()

    return [
        ThemeScreenResponse(
            entity_id=r.entity_id,
            theme=r.theme,
            exposure_score=_float(r.exposure_score),
            sensitivity_direction=r.sensitivity_direction,
            quantified_exposure=r.quantified_exposure,
            as_of_date=r.as_of_date,
        )
        for r in rows
    ]


@router.get(
    "/research/scenarios/{scenario_id}",
    response_model=ScenarioResponse,
)
async def get_scenario_detail(
    scenario_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get detailed information about a scenario."""
    result = await session.execute(
        select(MacroScenario).where(MacroScenario.id == scenario_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return _scenario_response(row)


@router.post(
    "/research/scenarios/{scenario_id}/run",
    response_model=list[ScenarioImpactResponse],
)
async def run_scenario(
    scenario_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Run a macro scenario and return company impacts."""
    # Verify scenario exists
    sc_result = await session.execute(
        select(MacroScenario).where(MacroScenario.id == scenario_id)
    )
    sc = sc_result.scalar_one_or_none()
    if not sc:
        raise HTTPException(status_code=404, detail="Scenario not found")

    # Return any cached impacts (in production this would trigger computation)
    result = await session.execute(
        select(ScenarioCompanyImpact)
        .where(ScenarioCompanyImpact.scenario_id == scenario_id)
        .order_by(ScenarioCompanyImpact.created_at.desc().nullslast())
    )
    rows = result.scalars().all()
    return [_impact_response(r) for r in rows]


@router.get(
    "/research/scenarios/{scenario_id}/results",
    response_model=list[ScenarioImpactResponse],
)
async def get_scenario_results(
    scenario_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Get cached results from a previously run scenario."""
    result = await session.execute(
        select(ScenarioCompanyImpact)
        .where(ScenarioCompanyImpact.scenario_id == scenario_id)
        .order_by(ScenarioCompanyImpact.created_at.desc().nullslast())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [_impact_response(r) for r in rows]
