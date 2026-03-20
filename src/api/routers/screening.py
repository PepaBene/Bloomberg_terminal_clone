"""Pillar 2: Screening & Ranking API (E4).

Endpoints for custom screening, pre-built screens, multi-factor ranking,
saved screens, universe management, and field metadata.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.models.screening import SavedScreen
from src.models.security import Security
from src.schemas.screening import (
    CustomUniverseRequest,
    PrebuiltScreenDetail,
    PrebuiltScreenSummary,
    RankRequest,
    SavedScreenResponse,
    SaveScreenRequest,
    ScreenFieldMeta,
    ScreenFieldsResponse,
    ScreenedSecurity,
    ScreenRequest,
    ScreenResult,
    UniverseResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v2/analytics", tags=["Screening"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_filter_group(raw: dict) -> Any:
    """Convert a raw dict to engine-internal ScreenFilterGroup."""
    from src.engines.e4_screening import ScreenFilter, ScreenFilterGroup

    logic = raw.get("logic", "AND")
    filters = []
    for f in raw.get("filters", []):
        if "logic" in f:
            filters.append(_parse_filter_group(f))
        else:
            filters.append(ScreenFilter(
                field=f["field"],
                source=f.get("source", "ANALYTICS_RESULT"),
                op=f.get("op", "GT"),
                value=f.get("value"),
                value2=f.get("value2"),
            ))
    return ScreenFilterGroup(logic=logic, filters=filters)


def _to_response(result) -> ScreenResult:
    """Convert engine ScreenResult to API ScreenResult."""
    return ScreenResult(
        total_matches=result.total_matches,
        securities=[
            ScreenedSecurity(
                security_id=s.security_id,
                entity_id=s.entity_id,
                ticker=s.ticker,
                name=s.name,
                rank=s.rank,
                composite_score=s.composite_score,
                metrics=s.metrics,
            )
            for s in result.securities
        ],
        screen_name=result.screen_name,
        universe=result.universe,
        execution_time_ms=result.execution_time_ms,
    )


# ---------------------------------------------------------------------------
# Custom Screen
# ---------------------------------------------------------------------------

@router.post("/screen", response_model=ScreenResult)
async def run_custom_screen(
    request: ScreenRequest,
    session: AsyncSession = Depends(get_session),
):
    """Run a custom screen with arbitrary filters and optional ranking."""
    from src.engines.e4_screening import ScreeningEngine, RankFactor

    engine = ScreeningEngine()
    filter_group = _parse_filter_group(request.filters.model_dump())
    ranking = None
    if request.ranking:
        ranking = [
            RankFactor(field=r.field, weight=r.weight, ascending=r.ascending)
            for r in request.ranking
        ]

    result = await engine.run_screen(
        session,
        filters=filter_group,
        universe_ids=request.custom_universe_ids,
        limit=request.limit,
        include_metrics=request.include_metrics,
        ranking=ranking,
    )
    return _to_response(result)


# ---------------------------------------------------------------------------
# Pre-built Screen Library
# ---------------------------------------------------------------------------

@router.get("/screens/library", response_model=list[PrebuiltScreenSummary])
async def list_prebuilt_screens():
    """List all pre-built screening strategies."""
    from src.engines.e4_screens_library import get_all_prebuilt_screens

    screens = get_all_prebuilt_screens()
    return [
        PrebuiltScreenSummary(
            screen_id=sid,
            name=s["name"],
            description=s.get("description"),
            tags=s.get("tags", []),
            filter_count=len(s.get("filters", {}).get("filters", [])),
        )
        for sid, s in screens.items()
    ]


@router.get("/screens/library/{screen_id}", response_model=PrebuiltScreenDetail)
async def get_prebuilt_screen(screen_id: str):
    """Get the full definition of a pre-built screen."""
    from src.engines.e4_screens_library import get_prebuilt_screen

    screen = get_prebuilt_screen(screen_id)
    if screen is None:
        raise HTTPException(status_code=404, detail=f"Pre-built screen '{screen_id}' not found")
    return PrebuiltScreenDetail(
        screen_id=screen_id,
        name=screen["name"],
        description=screen.get("description"),
        tags=screen.get("tags", []),
        filters=screen.get("filters", {}),
        ranking=screen.get("ranking"),
    )


@router.post("/screens/library/{screen_id}/run", response_model=ScreenResult)
async def run_prebuilt_screen(
    screen_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Execute a pre-built screen."""
    from src.engines.e4_screens_library import get_prebuilt_screen
    from src.engines.e4_screening import ScreeningEngine, RankFactor

    screen = get_prebuilt_screen(screen_id)
    if screen is None:
        raise HTTPException(status_code=404, detail=f"Pre-built screen '{screen_id}' not found")

    engine = ScreeningEngine()
    filter_group = _parse_filter_group(screen["filters"])
    ranking = None
    if screen.get("ranking"):
        ranking = [
            RankFactor(field=r["field"], weight=r.get("weight", 1.0), ascending=r.get("ascending", False))
            for r in screen["ranking"]
        ]

    result = await engine.run_screen(
        session,
        filters=filter_group,
        ranking=ranking,
        limit=100,
    )
    result.screen_name = screen["name"]
    return _to_response(result)


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

@router.post("/rank", response_model=ScreenResult)
async def run_ranking(
    request: RankRequest,
    session: AsyncSession = Depends(get_session),
):
    """Rank securities by multi-factor composite score."""
    from src.engines.e4_screening import ScreeningEngine, RankFactor

    engine = ScreeningEngine()

    # If no security_ids provided, use universe
    security_ids = request.security_ids
    if security_ids is None:
        # Fetch all active equity security IDs
        stmt = select(Security.security_id).where(Security.status == "ACTIVE")
        rows = (await session.execute(stmt)).scalars().all()
        security_ids = list(rows)

    factors = [
        RankFactor(field=f.field, weight=f.weight, ascending=f.ascending)
        for f in request.factors
    ]
    ranked = await engine.run_ranking(session, security_ids, factors, request.limit)
    return ScreenResult(
        total_matches=len(ranked),
        securities=[
            ScreenedSecurity(
                security_id=s.security_id,
                entity_id=s.entity_id,
                ticker=s.ticker,
                name=s.name,
                rank=s.rank,
                composite_score=s.composite_score,
                metrics=s.metrics,
            )
            for s in ranked
        ],
        universe=request.universe,
    )


# ---------------------------------------------------------------------------
# Saved Screens
# ---------------------------------------------------------------------------

@router.post("/screens/save", response_model=SavedScreenResponse)
async def save_custom_screen(
    request: SaveScreenRequest,
    session: AsyncSession = Depends(get_session),
):
    """Save a custom screen definition for later re-use."""
    screen = SavedScreen(
        name=request.name,
        description=request.description,
        screen_type="CUSTOM",
        is_prebuilt=False,
        definition=request.definition.model_dump(mode="json"),
        tags=request.tags,
    )
    session.add(screen)
    await session.flush()
    return SavedScreenResponse.model_validate(screen)


@router.get("/screens/saved", response_model=list[SavedScreenResponse])
async def list_saved_screens(
    session: AsyncSession = Depends(get_session),
):
    """List all saved custom screens."""
    result = await session.execute(
        select(SavedScreen)
        .where(SavedScreen.screen_type == "CUSTOM")
        .order_by(SavedScreen.created_at.desc())
    )
    return [SavedScreenResponse.model_validate(s) for s in result.scalars().all()]


@router.get("/screens/saved/{screen_id}/run", response_model=ScreenResult)
async def run_saved_screen(
    screen_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Execute a previously saved screen."""
    result = await session.execute(
        select(SavedScreen).where(SavedScreen.screen_id == screen_id)
    )
    screen = result.scalar_one_or_none()
    if screen is None:
        raise HTTPException(status_code=404, detail="Saved screen not found")

    from src.engines.e4_screening import ScreeningEngine, RankFactor
    from datetime import datetime, timezone

    engine = ScreeningEngine()
    defn = screen.definition
    filter_group = _parse_filter_group(defn.get("filters", {"logic": "AND", "filters": []}))
    ranking = None
    if defn.get("ranking"):
        ranking = [
            RankFactor(field=r["field"], weight=r.get("weight", 1.0), ascending=r.get("ascending", False))
            for r in defn["ranking"]
        ]

    eng_result = await engine.run_screen(
        session,
        filters=filter_group,
        ranking=ranking,
        limit=defn.get("limit", 100),
    )
    eng_result.screen_name = screen.name

    # Update last_run metadata
    screen.last_run_at = datetime.now(timezone.utc)
    screen.result_count = eng_result.total_matches

    return _to_response(eng_result)


# ---------------------------------------------------------------------------
# Universe Management
# ---------------------------------------------------------------------------

@router.get("/universe/us-equities", response_model=UniverseResponse)
async def get_us_equities(session: AsyncSession = Depends(get_session)):
    """US equity universe: all active common stocks on US exchanges."""
    us_mics = {"XNYS", "XNAS", "XASE", "ARCX", "BATS", "IEXG"}
    stmt = select(Security.security_id).where(
        Security.security_type == "COMMON_STOCK",
        Security.status == "ACTIVE",
        Security.primary_exchange_mic.in_(us_mics),
    )
    rows = (await session.execute(stmt)).scalars().all()
    return UniverseResponse(
        universe_name="US_EQUITIES",
        security_count=len(rows),
        security_ids=list(rows),
    )


@router.get("/universe/sp500", response_model=UniverseResponse)
async def get_sp500(session: AsyncSession = Depends(get_session)):
    """S&P 500 members (from saved universe, or empty if not seeded)."""
    stmt = select(SavedScreen).where(
        SavedScreen.screen_type == "UNIVERSE",
        SavedScreen.name == "S&P 500",
    )
    result = await session.execute(stmt)
    screen = result.scalar_one_or_none()
    ids = screen.definition.get("security_ids", []) if screen else []
    return UniverseResponse(
        universe_name="SP500",
        security_count=len(ids),
        security_ids=[uuid.UUID(i) if isinstance(i, str) else i for i in ids],
    )


@router.get("/universe/russell1000", response_model=UniverseResponse)
async def get_russell1000(session: AsyncSession = Depends(get_session)):
    """Russell 1000 members (from saved universe, or empty if not seeded)."""
    stmt = select(SavedScreen).where(
        SavedScreen.screen_type == "UNIVERSE",
        SavedScreen.name == "Russell 1000",
    )
    result = await session.execute(stmt)
    screen = result.scalar_one_or_none()
    ids = screen.definition.get("security_ids", []) if screen else []
    return UniverseResponse(
        universe_name="RUSSELL1000",
        security_count=len(ids),
        security_ids=[uuid.UUID(i) if isinstance(i, str) else i for i in ids],
    )


@router.post("/universe/custom", response_model=UniverseResponse)
async def create_custom_universe(
    request: CustomUniverseRequest,
    session: AsyncSession = Depends(get_session),
):
    """Create a custom universe from a list of security IDs."""
    screen = SavedScreen(
        name=request.name,
        screen_type="UNIVERSE",
        is_prebuilt=False,
        definition={"security_ids": [str(s) for s in request.security_ids]},
    )
    session.add(screen)
    await session.flush()
    return UniverseResponse(
        universe_name=request.name,
        security_count=len(request.security_ids),
        security_ids=request.security_ids,
    )


# ---------------------------------------------------------------------------
# Field Metadata
# ---------------------------------------------------------------------------

@router.get("/screen/fields", response_model=ScreenFieldsResponse)
async def get_screenable_fields():
    """Return metadata for all screenable fields."""
    from src.engines.e4_screening import ScreeningEngine

    engine = ScreeningEngine()
    fields_raw = engine.get_field_metadata()
    fields = [
        ScreenFieldMeta(
            field_name=f["field_name"],
            source=f["source"],
            data_type=f["data_type"],
            description=f.get("description"),
            category=f.get("category"),
            unit=f.get("unit"),
        )
        for f in fields_raw
    ]
    return ScreenFieldsResponse(total_fields=len(fields), fields=fields)
