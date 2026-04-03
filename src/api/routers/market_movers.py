"""Market Movers API endpoints (Pillar 2 Supplement – Part 5)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.models.market_movers import MarketMoversSnapshot
from src.schemas.market_movers import (
    MarketMoversResponse,
    MarketMoversSummaryResponse,
    MoverEntry,
)

router = APIRouter(tags=["Market Movers"])


@router.get(
    "/analytics/movers",
    response_model=MarketMoversResponse,
)
async def get_market_movers(
    session: AsyncSession = Depends(get_session),
    category: str = Query("TOP_GAINERS", description="TOP_GAINERS, TOP_LOSERS, MOST_ACTIVE"),
    snapshot_date: date | None = Query(None, description="Specific date (defaults to latest)"),
):
    """Return market movers for a given category."""
    query = (
        select(MarketMoversSnapshot)
        .where(MarketMoversSnapshot.category == category.upper())
        .order_by(MarketMoversSnapshot.snapshot_date.desc())
    )
    if snapshot_date:
        query = query.where(MarketMoversSnapshot.snapshot_date == snapshot_date)
    query = query.limit(1)

    result = await session.execute(query)
    row = result.scalar_one_or_none()

    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"No market movers data found for category '{category.upper()}'"
            + (f" on {snapshot_date}" if snapshot_date else ""),
        )

    movers = []
    if row.rankings and isinstance(row.rankings, list):
        for i, entry in enumerate(row.rankings):
            movers.append(MoverEntry(
                rank=i + 1,
                security_id=entry.get("security_id"),
                name=entry.get("name"),
                ticker=entry.get("ticker"),
                price=entry.get("price"),
                change_pct=entry.get("change_pct"),
                volume=entry.get("volume"),
            ))

    return MarketMoversResponse(
        snapshot_date=row.snapshot_date,
        category=row.category,
        movers=movers,
    )


@router.get(
    "/analytics/movers/summary",
    response_model=MarketMoversSummaryResponse,
)
async def get_movers_summary(
    session: AsyncSession = Depends(get_session),
    snapshot_date: date | None = Query(None),
):
    """Return summary counts of movers across categories."""
    query = select(MarketMoversSnapshot).order_by(MarketMoversSnapshot.snapshot_date.desc())
    if snapshot_date:
        query = query.where(MarketMoversSnapshot.snapshot_date == snapshot_date)
    query = query.limit(10)

    result = await session.execute(query)
    rows = result.scalars().all()

    counts = {"TOP_GAINERS": 0, "TOP_LOSERS": 0, "MOST_ACTIVE": 0}
    snap_date = snapshot_date or date.today()
    for i, row in enumerate(rows):
        if i == 0:
            snap_date = row.snapshot_date
        if row.category in counts and row.rankings:
            counts[row.category] = len(row.rankings)

    return MarketMoversSummaryResponse(
        snapshot_date=snap_date,
        gainers_count=counts["TOP_GAINERS"],
        losers_count=counts["TOP_LOSERS"],
        most_active_count=counts["MOST_ACTIVE"],
    )
