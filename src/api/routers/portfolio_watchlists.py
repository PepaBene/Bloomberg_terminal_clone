"""Portfolio Watchlist API endpoints (Pillar 4 Phase 1)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.models.entity import Entity
from src.models.portfolio_watchlist import PortfolioWatchlist, PortfolioWatchlistEntry
from src.schemas.watchlist_schema import (
    AlertConfigRequest,
    AlertDigestResponse,
    EarningsCalendarEntry,
    EarningsCalendarResponse,
    WatchlistAlertItem,
    WatchlistAlertResponse,
    WatchlistCreateRequest,
    WatchlistDashboardEntity,
    WatchlistDashboardResponse,
    WatchlistEntityResponse,
    WatchlistResponse,
)

router = APIRouter(tags=["Portfolio Watchlists"])

DEFAULT_USER = "default_user"


# ── Helpers ──────────────────────────────────────────────────────────


async def _get_watchlist(session: AsyncSession, wl_id: uuid.UUID) -> PortfolioWatchlist:
    result = await session.execute(
        select(PortfolioWatchlist).where(PortfolioWatchlist.id == wl_id)
    )
    wl = result.scalar_one_or_none()
    if not wl:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    return wl


async def _get_entity(session: AsyncSession, entity_id: uuid.UUID) -> Entity:
    result = await session.execute(
        select(Entity).where(Entity.entity_id == entity_id)
    )
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


async def _get_watchlist_entities(
    session: AsyncSession, wl_id: uuid.UUID
) -> list[WatchlistEntityResponse]:
    """Fetch all entities in a watchlist."""
    result = await session.execute(
        select(PortfolioWatchlistEntry, Entity)
        .outerjoin(Entity, PortfolioWatchlistEntry.entity_id == Entity.entity_id)
        .where(PortfolioWatchlistEntry.watchlist_id == wl_id)
        .order_by(PortfolioWatchlistEntry.added_date.desc())
    )
    rows = result.all()
    return [
        WatchlistEntityResponse(
            entity_id=entry.entity_id,
            legal_name=entity.legal_name if entity else None,
            added_date=entry.added_date,
        )
        for entry, entity in rows
    ]


# ══════════════════════════════════════════════════════════════════════
# Watchlist CRUD
# ══════════════════════════════════════════════════════════════════════


@router.post("/portfolios/watchlists", response_model=WatchlistResponse, status_code=201)
async def create_watchlist(
    body: WatchlistCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Create a new named watchlist."""
    wl = PortfolioWatchlist(
        id=uuid.uuid4(),
        user_id=DEFAULT_USER,
        name=body.name,
        description=body.description,
    )
    session.add(wl)
    await session.flush()

    return WatchlistResponse(
        id=wl.id,
        name=wl.name,
        description=wl.description,
        entities=[],
    )


@router.get("/portfolios/watchlists", response_model=list[WatchlistResponse])
async def list_watchlists(
    session: AsyncSession = Depends(get_session),
):
    """List all watchlists for the current user."""
    result = await session.execute(
        select(PortfolioWatchlist)
        .where(PortfolioWatchlist.user_id == DEFAULT_USER)
        .order_by(PortfolioWatchlist.name)
    )
    watchlists = result.scalars().all()
    responses = []
    for wl in watchlists:
        entities = await _get_watchlist_entities(session, wl.id)
        responses.append(
            WatchlistResponse(
                id=wl.id,
                name=wl.name,
                description=wl.description,
                entities=entities,
            )
        )
    return responses


@router.get("/portfolios/watchlists/{wl_id}", response_model=WatchlistResponse)
async def get_watchlist(
    wl_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get a watchlist by ID with its entities."""
    wl = await _get_watchlist(session, wl_id)
    entities = await _get_watchlist_entities(session, wl.id)
    return WatchlistResponse(
        id=wl.id,
        name=wl.name,
        description=wl.description,
        entities=entities,
    )


@router.post(
    "/portfolios/watchlists/{wl_id}/add/{entity_id}",
    response_model=WatchlistResponse,
)
async def add_entity_to_watchlist(
    wl_id: uuid.UUID,
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Add an entity to a watchlist."""
    wl = await _get_watchlist(session, wl_id)
    await _get_entity(session, entity_id)

    # Check if already in watchlist
    existing = await session.execute(
        select(PortfolioWatchlistEntry).where(
            PortfolioWatchlistEntry.watchlist_id == wl_id,
            PortfolioWatchlistEntry.entity_id == entity_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Entity already in watchlist")

    entry = PortfolioWatchlistEntry(
        id=uuid.uuid4(),
        watchlist_id=wl_id,
        entity_id=entity_id,
        added_date=date.today(),
    )
    session.add(entry)
    await session.flush()

    entities = await _get_watchlist_entities(session, wl.id)
    return WatchlistResponse(
        id=wl.id,
        name=wl.name,
        description=wl.description,
        entities=entities,
    )


@router.delete(
    "/portfolios/watchlists/{wl_id}/remove/{entity_id}",
    response_model=WatchlistResponse,
)
async def remove_entity_from_watchlist(
    wl_id: uuid.UUID,
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Remove an entity from a watchlist."""
    wl = await _get_watchlist(session, wl_id)

    result = await session.execute(
        select(PortfolioWatchlistEntry).where(
            PortfolioWatchlistEntry.watchlist_id == wl_id,
            PortfolioWatchlistEntry.entity_id == entity_id,
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Entity not in watchlist")

    await session.delete(entry)
    await session.flush()

    entities = await _get_watchlist_entities(session, wl.id)
    return WatchlistResponse(
        id=wl.id,
        name=wl.name,
        description=wl.description,
        entities=entities,
    )


# ══════════════════════════════════════════════════════════════════════
# Watchlist Monitoring
# ══════════════════════════════════════════════════════════════════════


@router.get(
    "/portfolios/watchlists/{wl_id}/alerts",
    response_model=WatchlistAlertResponse,
)
async def get_watchlist_alerts(
    wl_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get active alerts for entities in a watchlist."""
    await _get_watchlist(session, wl_id)
    # Stub: in production this would query an alert engine
    return WatchlistAlertResponse(alerts=[])


@router.get(
    "/portfolios/watchlists/{wl_id}/alerts/digest",
    response_model=AlertDigestResponse,
)
async def get_watchlist_alert_digest(
    wl_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get an alert digest summary for the watchlist."""
    await _get_watchlist(session, wl_id)
    return AlertDigestResponse(
        total_alerts=0,
        high_severity=0,
        medium_severity=0,
        low_severity=0,
        summary="No active alerts.",
    )


@router.post(
    "/portfolios/watchlists/{wl_id}/alerts/configure",
    response_model=WatchlistResponse,
)
async def configure_alerts(
    wl_id: uuid.UUID,
    body: AlertConfigRequest,
    session: AsyncSession = Depends(get_session),
):
    """Configure alert settings for a watchlist."""
    wl = await _get_watchlist(session, wl_id)

    wl.alert_config = {
        "muted_types": body.muted_types or [],
        "min_severity": body.min_severity or "LOW",
    }
    await session.flush()

    entities = await _get_watchlist_entities(session, wl.id)
    return WatchlistResponse(
        id=wl.id,
        name=wl.name,
        description=wl.description,
        entities=entities,
    )


@router.get(
    "/portfolios/watchlists/{wl_id}/earnings-calendar",
    response_model=EarningsCalendarResponse,
)
async def get_watchlist_earnings_calendar(
    wl_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get earnings calendar for entities in the watchlist."""
    await _get_watchlist(session, wl_id)
    # Stub: in production this would query earnings data
    return EarningsCalendarResponse(entries=[])


@router.get(
    "/portfolios/watchlists/{wl_id}/dashboard",
    response_model=WatchlistDashboardResponse,
)
async def get_watchlist_dashboard(
    wl_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get a dashboard view of watchlist entities with key metrics."""
    wl = await _get_watchlist(session, wl_id)

    # Fetch entities
    result = await session.execute(
        select(PortfolioWatchlistEntry, Entity)
        .outerjoin(Entity, PortfolioWatchlistEntry.entity_id == Entity.entity_id)
        .where(PortfolioWatchlistEntry.watchlist_id == wl_id)
    )
    rows = result.all()

    entities = [
        WatchlistDashboardEntity(
            entity_id=entry.entity_id,
            legal_name=entity.legal_name if entity else None,
        )
        for entry, entity in rows
    ]

    return WatchlistDashboardResponse(entities=entities)
