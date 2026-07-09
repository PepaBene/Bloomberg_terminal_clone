"""Custom Index API endpoints (Pillar 2 Supplement – Part 4)."""

import uuid
from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.engines.custom_index import compute_index_performance, compute_index_weights
from src.models.custom_index import CustomIndex, IndexConstituent, IndexPerformance
from src.models.security import EODPrice
from src.schemas.custom_index import (
    CreateIndexRequest,
    CustomIndexResponse,
    IndexConstituentResponse,
    IndexPerformancePointResponse,
    IndexPerformanceResponse,
    SetConstituentsRequest,
)

router = APIRouter(tags=["Custom Index"])


@router.post(
    "/analytics/indices",
    response_model=CustomIndexResponse,
    status_code=201,
)
async def create_index(
    body: CreateIndexRequest,
    session: AsyncSession = Depends(get_session),
):
    """Create a new custom index."""
    index = CustomIndex(
        index_id=uuid.uuid4(),
        name=body.name,
        description=body.description,
        status="ACTIVE",
        weighting_method=body.weighting_method,
        rebalance_frequency=body.rebalance_frequency,
        max_constituents=body.max_constituents,
        inception_date=date.today(),
    )
    session.add(index)
    await session.commit()
    return CustomIndexResponse.model_validate(index)


@router.get(
    "/analytics/indices",
    response_model=list[CustomIndexResponse],
)
async def list_indices(
    session: AsyncSession = Depends(get_session),
    status: str | None = Query(None, description="Filter by status"),
):
    """List all custom indices."""
    query = select(CustomIndex).order_by(CustomIndex.name)
    if status:
        query = query.where(CustomIndex.status == status.upper())
    result = await session.execute(query)
    rows = result.scalars().all()
    return [CustomIndexResponse.model_validate(r) for r in rows]


@router.get(
    "/analytics/indices/{index_id}",
    response_model=CustomIndexResponse,
)
async def get_index(
    index_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get a custom index by ID."""
    result = await session.execute(
        select(CustomIndex).where(CustomIndex.index_id == index_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Custom index not found")
    return CustomIndexResponse.model_validate(row)


@router.get(
    "/analytics/indices/{index_id}/constituents",
    response_model=list[IndexConstituentResponse],
)
async def get_index_constituents(
    index_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    active_only: bool = Query(True, description="Only active constituents"),
):
    """Get constituents of a custom index."""
    query = select(IndexConstituent).where(IndexConstituent.index_id == index_id)
    if active_only:
        query = query.where(IndexConstituent.is_active == True)  # noqa: E712
    result = await session.execute(query)
    rows = result.scalars().all()
    return [IndexConstituentResponse.model_validate(r) for r in rows]


@router.post(
    "/analytics/indices/{index_id}/constituents",
    response_model=list[IndexConstituentResponse],
    status_code=201,
)
async def set_index_constituents(
    index_id: uuid.UUID,
    body: SetConstituentsRequest,
    session: AsyncSession = Depends(get_session),
):
    """Set (replace) an index's constituents, computing weights via the engine."""
    index = (
        await session.execute(
            select(CustomIndex).where(CustomIndex.index_id == index_id)
        )
    ).scalar_one_or_none()
    if not index:
        raise HTTPException(status_code=404, detail="Custom index not found")
    if not body.security_ids:
        raise HTTPException(status_code=400, detail="security_ids must not be empty")

    method = (body.weighting_method or index.weighting_method or "EQUAL").upper()
    weights = compute_index_weights(
        security_ids=[str(s) for s in body.security_ids],
        method=method,
        market_caps=body.market_caps,
        scores=body.scores,
        max_constituents=index.max_constituents,
    )

    today = date.today()
    existing_active = {
        c.security_id: c
        for c in (
            await session.execute(
                select(IndexConstituent).where(
                    IndexConstituent.index_id == index_id,
                    IndexConstituent.is_active == True,  # noqa: E712
                )
            )
        ).scalars().all()
    }

    new_ids = set(body.security_ids)
    # Deactivate any currently-active constituent no longer requested.
    for sid, c in existing_active.items():
        if sid not in new_ids:
            c.is_active = False
            c.removed_date = today

    result_rows: list[IndexConstituent] = []
    for sid in body.security_ids:
        weight = weights.get(str(sid))
        if weight is None:
            continue  # dropped by max_constituents cap
        c = existing_active.get(sid)
        if c is not None:
            c.weight = weight
            c.is_active = True
            c.removed_date = None
        else:
            c = IndexConstituent(
                constituent_id=uuid.uuid4(),
                index_id=index_id,
                security_id=sid,
                weight=weight,
                added_date=today,
                is_active=True,
            )
            session.add(c)
        result_rows.append(c)

    await session.commit()
    for c in result_rows:
        await session.refresh(c)
    return [IndexConstituentResponse.model_validate(c) for c in result_rows]


@router.post(
    "/analytics/indices/{index_id}/performance/compute",
    response_model=IndexPerformanceResponse,
)
async def compute_and_store_index_performance(
    index_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    start: date | None = Query(None),
    end: date | None = Query(None),
    base_level: float = Query(1000.0, gt=0),
):
    """Compute (and persist) the index performance series via the engine.

    Weighted daily returns are derived from constituent EOD prices and passed
    to ``compute_index_performance`` for level/cumulative-return computation.
    """
    index = (
        await session.execute(
            select(CustomIndex).where(CustomIndex.index_id == index_id)
        )
    ).scalar_one_or_none()
    if not index:
        raise HTTPException(status_code=404, detail="Custom index not found")

    constituents = (
        await session.execute(
            select(IndexConstituent).where(
                IndexConstituent.index_id == index_id,
                IndexConstituent.is_active == True,  # noqa: E712
                IndexConstituent.weight.isnot(None),
            )
        )
    ).scalars().all()
    if not constituents:
        raise HTTPException(
            status_code=400,
            detail="Index has no active weighted constituents; set constituents first",
        )

    weights = {c.security_id: float(c.weight) for c in constituents}
    total_w = sum(weights.values())
    if total_w <= 0:
        raise HTTPException(status_code=400, detail="Constituent weights sum to zero")
    weights = {sid: w / total_w for sid, w in weights.items()}

    price_q = select(
        EODPrice.security_id, EODPrice.price_date, EODPrice.close
    ).where(EODPrice.security_id.in_(list(weights.keys())))
    if start:
        price_q = price_q.where(EODPrice.price_date >= start)
    if end:
        price_q = price_q.where(EODPrice.price_date <= end)

    rows = (await session.execute(price_q)).all()
    prices_by_date: dict[date, dict] = defaultdict(dict)
    for sid, pdate, close in rows:
        if close is not None:
            prices_by_date[pdate][sid] = float(close)

    dates = sorted(prices_by_date)
    if len(dates) < 2:
        raise HTTPException(
            status_code=400, detail="Insufficient constituent price history to compute performance"
        )

    daily_returns: list[float] = []
    perf_dates: list[date] = []
    prev = prices_by_date[dates[0]]
    for d in dates[1:]:
        cur = prices_by_date[d]
        weighted_ret = 0.0
        weight_sum = 0.0
        for sid, w in weights.items():
            p0 = prev.get(sid)
            p1 = cur.get(sid)
            if p0 and p1 and p0 > 0:
                weighted_ret += w * (p1 / p0 - 1.0)
                weight_sum += w
        if weight_sum > 0:
            daily_returns.append(weighted_ret / weight_sum)
            perf_dates.append(d)
        prev = cur

    if not daily_returns:
        raise HTTPException(
            status_code=400, detail="No overlapping constituent prices to compute returns"
        )

    series = compute_index_performance(daily_returns, base_level=base_level)

    existing_perf = {
        p.perf_date: p
        for p in (
            await session.execute(
                select(IndexPerformance).where(IndexPerformance.index_id == index_id)
            )
        ).scalars().all()
    }

    points: list[IndexPerformancePointResponse] = []
    for d, pt in zip(perf_dates, series):
        row = existing_perf.get(d)
        if row is not None:
            row.index_level = pt["index_level"]
            row.daily_return = pt["daily_return"]
            row.cumulative_return = pt["cumulative_return"]
        else:
            session.add(IndexPerformance(
                id=uuid.uuid4(),
                index_id=index_id,
                perf_date=d,
                index_level=pt["index_level"],
                daily_return=pt["daily_return"],
                cumulative_return=pt["cumulative_return"],
            ))
        points.append(IndexPerformancePointResponse(
            perf_date=d,
            index_level=pt["index_level"],
            daily_return=pt["daily_return"],
            cumulative_return=pt["cumulative_return"],
        ))

    await session.commit()
    return IndexPerformanceResponse(index_id=index_id, points=points)


@router.get(
    "/analytics/indices/{index_id}/performance",
    response_model=IndexPerformanceResponse,
)
async def get_index_performance(
    index_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    start: date | None = Query(None),
    end: date | None = Query(None),
):
    """Get performance time series for a custom index."""
    query = (
        select(IndexPerformance)
        .where(IndexPerformance.index_id == index_id)
        .order_by(IndexPerformance.perf_date.asc())
    )
    if start:
        query = query.where(IndexPerformance.perf_date >= start)
    if end:
        query = query.where(IndexPerformance.perf_date <= end)

    result = await session.execute(query)
    rows = result.scalars().all()

    points = [
        IndexPerformancePointResponse(
            perf_date=r.perf_date,
            index_level=float(r.index_level) if r.index_level else None,
            daily_return=float(r.daily_return) if r.daily_return else None,
            cumulative_return=float(r.cumulative_return) if r.cumulative_return else None,
        )
        for r in rows
    ]
    return IndexPerformanceResponse(index_id=index_id, points=points)


@router.delete(
    "/analytics/indices/{index_id}",
    status_code=204,
)
async def archive_index(
    index_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Archive (soft delete) a custom index."""
    result = await session.execute(
        select(CustomIndex).where(CustomIndex.index_id == index_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Custom index not found")
    row.status = "ARCHIVED"
    await session.commit()
    return None
