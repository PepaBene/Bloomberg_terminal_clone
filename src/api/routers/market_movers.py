"""Market Movers API endpoints (Pillar 2 Supplement – Part 5).

Computes daily gainers/losers/most-active LIVE from end-of-day prices via the
``market_movers`` engine (no dependency on a pre-built snapshot table).
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.engines.market_movers import compute_daily_movers
from src.models.security import EODPrice, Security, SecurityIdentifier
from src.schemas.market_movers import (
    MarketMoversResponse,
    MarketMoversSummaryResponse,
    MoverEntry,
)

router = APIRouter(tags=["Market Movers"])

VALID_CATEGORIES = {"TOP_GAINERS", "TOP_LOSERS", "MOST_ACTIVE"}


async def _resolve_dates(
    session: AsyncSession, snapshot_date: date | None
) -> tuple[date | None, date | None]:
    """Resolve the latest trading date (<= snapshot_date) and the prior one."""
    latest_q = select(sa_func.max(EODPrice.price_date))
    if snapshot_date:
        latest_q = latest_q.where(EODPrice.price_date <= snapshot_date)
    latest_date = (await session.execute(latest_q)).scalar_one_or_none()
    if latest_date is None:
        return None, None

    prior_date = (
        await session.execute(
            select(sa_func.max(EODPrice.price_date)).where(
                EODPrice.price_date < latest_date
            )
        )
    ).scalar_one_or_none()
    return latest_date, prior_date


async def _compute_all_movers(
    session: AsyncSession, latest_date: date, prior_date: date, top_n: int
) -> dict:
    """Load prices for the two dates and delegate to the engine."""
    rows = (
        await session.execute(
            select(
                EODPrice.security_id,
                EODPrice.price_date,
                EODPrice.close,
                EODPrice.volume,
                Security.name,
            )
            .join(Security, Security.security_id == EODPrice.security_id)
            .where(EODPrice.price_date.in_([latest_date, prior_date]))
        )
    ).all()

    latest_map: dict[uuid.UUID, tuple] = {}
    prior_map: dict[uuid.UUID, object] = {}
    names: dict[uuid.UUID, str] = {}
    for sid, pdate, close, volume, name in rows:
        names[sid] = name
        if pdate == latest_date:
            latest_map[sid] = (close, volume)
        elif pdate == prior_date:
            prior_map[sid] = close

    securities = []
    for sid, (close, volume) in latest_map.items():
        prior = prior_map.get(sid)
        securities.append({
            "security_id": str(sid),
            "name": names.get(sid),
            "ticker": None,
            "price": float(close) if close is not None else None,
            "prior_price": float(prior) if prior is not None else None,
            "volume": float(volume) if volume is not None else None,
        })

    return compute_daily_movers(securities, top_n=top_n)


async def _ticker_map(
    session: AsyncSession, security_ids: list[uuid.UUID]
) -> dict[str, str]:
    """Map security_id (str) -> primary ticker for the given securities."""
    if not security_ids:
        return {}
    rows = (
        await session.execute(
            select(
                SecurityIdentifier.security_id,
                SecurityIdentifier.identifier_value,
            ).where(
                SecurityIdentifier.security_id.in_(security_ids),
                SecurityIdentifier.identifier_type == "TICKER",
            )
        )
    ).all()
    return {str(sid): value for sid, value in rows}


@router.get(
    "/analytics/movers",
    response_model=MarketMoversResponse,
)
async def get_market_movers(
    session: AsyncSession = Depends(get_session),
    category: str = Query("TOP_GAINERS", description="TOP_GAINERS, TOP_LOSERS, MOST_ACTIVE"),
    snapshot_date: date | None = Query(None, description="As-of date (defaults to latest available)"),
    top_n: int = Query(10, ge=1, le=100, description="Entries per category"),
):
    """Return market movers for a given category, computed live from EOD prices."""
    category = category.upper()
    if category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category '{category}'. Must be one of {sorted(VALID_CATEGORIES)}",
        )

    latest_date, prior_date = await _resolve_dates(session, snapshot_date)
    if latest_date is None:
        raise HTTPException(status_code=404, detail="No end-of-day price data available")
    if prior_date is None:
        raise HTTPException(
            status_code=404, detail="Insufficient price history to compute movers"
        )

    computed = await _compute_all_movers(session, latest_date, prior_date, top_n)
    entries = computed.get(category, [])

    sec_ids = [uuid.UUID(e.security_id) for e in entries if e.security_id]
    tickers = await _ticker_map(session, sec_ids)

    movers = [
        MoverEntry(
            rank=e.rank,
            security_id=e.security_id,
            name=e.name,
            ticker=tickers.get(e.security_id),
            price=e.price,
            change_pct=e.change_pct,
            volume=e.volume,
        )
        for e in entries
    ]

    return MarketMoversResponse(
        snapshot_date=latest_date,
        category=category,
        movers=movers,
    )


@router.get(
    "/analytics/movers/summary",
    response_model=MarketMoversSummaryResponse,
)
async def get_movers_summary(
    session: AsyncSession = Depends(get_session),
    snapshot_date: date | None = Query(None),
    top_n: int = Query(10, ge=1, le=100, description="Entries per category"),
):
    """Return summary counts of movers across categories (live computation)."""
    latest_date, prior_date = await _resolve_dates(session, snapshot_date)
    if latest_date is None:
        raise HTTPException(status_code=404, detail="No end-of-day price data available")
    if prior_date is None:
        raise HTTPException(
            status_code=404, detail="Insufficient price history to compute movers"
        )

    computed = await _compute_all_movers(session, latest_date, prior_date, top_n)

    return MarketMoversSummaryResponse(
        snapshot_date=latest_date,
        gainers_count=len(computed.get("TOP_GAINERS", [])),
        losers_count=len(computed.get("TOP_LOSERS", [])),
        most_active_count=len(computed.get("MOST_ACTIVE", [])),
    )
