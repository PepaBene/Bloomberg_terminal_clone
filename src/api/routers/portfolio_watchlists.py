"""Portfolio Watchlist API endpoints (Pillar 4 Phase 1)."""

import uuid
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_optional_user, get_session
from src.engines import watchlist_monitoring
from src.models.calendar import CalendarEvent
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

# Fallback identity used only when no Bearer token is present and REQUIRE_AUTH
# is not set. Real authenticated users come from ``get_optional_user``.
ANONYMOUS_USER = "default_user"


def _resolve_user(user: str | None) -> str:
    return user or ANONYMOUS_USER


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
            legal_name=entity.legal_name if entity else "Unknown",
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
    user: str | None = Depends(get_optional_user),
):
    """Create a new named watchlist."""
    user_id = _resolve_user(user)
    wl = PortfolioWatchlist(
        id=uuid.uuid4(),
        user_id=user_id,
        name=body.name,
        description=body.description,
    )
    session.add(wl)
    await session.commit()
    await session.refresh(wl)

    return WatchlistResponse(
        id=wl.id,
        name=wl.name,
        description=wl.description,
        entities=[],
    )


@router.get("/portfolios/watchlists", response_model=list[WatchlistResponse])
async def list_watchlists(
    session: AsyncSession = Depends(get_session),
    user: str | None = Depends(get_optional_user),
):
    """List all watchlists for the current user."""
    user_id = _resolve_user(user)
    result = await session.execute(
        select(PortfolioWatchlist)
        .where(PortfolioWatchlist.user_id == user_id)
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
    user: str | None = Depends(get_optional_user),
):
    """Add an entity to a watchlist."""
    user_id = _resolve_user(user)
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
        created_by=user_id,
    )
    session.add(entry)
    await session.commit()

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
    await session.commit()

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


async def _evaluate_watchlist_alerts(
    session: AsyncSession, wl: PortfolioWatchlist
) -> list[watchlist_monitoring.WatchlistAlert]:
    """Run the watchlist_monitoring engine for every entity in the watchlist.

    Pulls upcoming earnings (within 14 days) from the calendar_events table
    so the engine has real data to evaluate. Score / news / filings sources
    can be wired in later as those tables become populated.
    """
    entry_rows = await session.execute(
        select(PortfolioWatchlistEntry, Entity)
        .outerjoin(Entity, PortfolioWatchlistEntry.entity_id == Entity.entity_id)
        .where(PortfolioWatchlistEntry.watchlist_id == wl.id)
    )
    pairs = entry_rows.all()
    if not pairs:
        return []

    entity_ids = [entry.entity_id for entry, _ in pairs]
    today = date.today()
    horizon = today + timedelta(days=14)

    earn_rows = await session.execute(
        select(CalendarEvent)
        .where(
            CalendarEvent.entity_id.in_(entity_ids),
            CalendarEvent.event_type == "EARNINGS",
            CalendarEvent.event_date >= today,
            CalendarEvent.event_date <= horizon,
        )
    )
    earnings_by_entity: dict[uuid.UUID, list[dict]] = {}
    for ev in earn_rows.scalars():
        earnings_by_entity.setdefault(ev.entity_id, []).append({
            "ticker": "",
            "earnings_date": ev.event_date.isoformat(),
            "is_confirmed": True,
        })

    aggregated: list[watchlist_monitoring.WatchlistAlert] = []
    config = wl.alert_config or {}

    for entry, entity in pairs:
        ticker = ""
        if entity is not None and getattr(entity, "primary_ticker", None):
            ticker = entity.primary_ticker
        entity_data = {
            "entity_id": str(entry.entity_id),
            "ticker": ticker,
            "earnings": earnings_by_entity.get(entry.entity_id, []),
        }
        result = watchlist_monitoring.evaluate_watchlist_alerts(entity_data, config)
        aggregated.extend(result.alerts)

    if config:
        aggregated = watchlist_monitoring.filter_by_user_preferences(aggregated, config)

    return aggregated


@router.get(
    "/portfolios/watchlists/{wl_id}/alerts",
    response_model=WatchlistAlertResponse,
)
async def get_watchlist_alerts(
    wl_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get active alerts for entities in a watchlist."""
    wl = await _get_watchlist(session, wl_id)
    alerts = await _evaluate_watchlist_alerts(session, wl)

    items: list[WatchlistAlertItem] = []
    for alert in alerts:
        triggered: datetime | None = None
        if alert.triggered_at:
            try:
                triggered = datetime.fromisoformat(alert.triggered_at)
            except ValueError:
                triggered = None
        try:
            entity_uuid = uuid.UUID(alert.entity_id) if alert.entity_id else None
        except ValueError:
            entity_uuid = None
        items.append(WatchlistAlertItem(
            alert_type=alert.alert_type,
            severity=alert.severity,
            message=alert.message,
            entity_id=entity_uuid,
            triggered_at=triggered,
        ))

    return WatchlistAlertResponse(alerts=items)


@router.get(
    "/portfolios/watchlists/{wl_id}/alerts/digest",
    response_model=AlertDigestResponse,
)
async def get_watchlist_alert_digest(
    wl_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get an alert digest summary for the watchlist."""
    wl = await _get_watchlist(session, wl_id)
    alerts = await _evaluate_watchlist_alerts(session, wl)

    if not alerts:
        return AlertDigestResponse(
            total_alerts=0,
            high_severity=0,
            medium_severity=0,
            low_severity=0,
            summary="No active alerts.",
        )

    digest = watchlist_monitoring.format_alert_digest(alerts)
    summary_lines = [
        f"{alert['ticker']}: {alert['title']}"
        for alert in digest["top_alerts"][:3]
    ]
    return AlertDigestResponse(
        total_alerts=len(alerts),
        high_severity=digest["high_count"],
        medium_severity=digest["medium_count"],
        low_severity=digest["low_count"],
        summary="; ".join(summary_lines) if summary_lines else None,
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
    await session.commit()

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
    """Get upcoming earnings dates (next 90 days) for watchlist entities."""
    await _get_watchlist(session, wl_id)

    entries_result = await session.execute(
        select(PortfolioWatchlistEntry.entity_id)
        .where(PortfolioWatchlistEntry.watchlist_id == wl_id)
    )
    entity_ids = [row[0] for row in entries_result.all()]
    if not entity_ids:
        return EarningsCalendarResponse(entries=[])

    today = date.today()
    horizon = today + timedelta(days=90)
    events_result = await session.execute(
        select(CalendarEvent, Entity)
        .outerjoin(Entity, CalendarEvent.entity_id == Entity.entity_id)
        .where(
            CalendarEvent.entity_id.in_(entity_ids),
            CalendarEvent.event_type == "EARNINGS",
            CalendarEvent.event_date >= today,
            CalendarEvent.event_date <= horizon,
        )
        .order_by(CalendarEvent.event_date.asc())
    )

    entries = [
        EarningsCalendarEntry(
            entity_id=ev.entity_id,
            legal_name=entity.legal_name if entity else "Unknown",
            report_date=ev.event_date,
            fiscal_quarter=None,
        )
        for ev, entity in events_result.all()
        if ev.entity_id is not None
    ]
    return EarningsCalendarResponse(entries=entries)


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
            legal_name=entity.legal_name if entity else "Unknown",
        )
        for entry, entity in rows
    ]

    return WatchlistDashboardResponse(entities=entities)
