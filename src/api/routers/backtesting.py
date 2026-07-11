"""Backtesting API endpoints (Pillar 2 Supplement – Part 3)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.models.backtesting import BacktestResult, BacktestRun
from src.schemas.backtesting import (
    BacktestCompareRequest,
    BacktestCompareResponse,
    BacktestHoldingsResponse,
    BacktestPerformanceResponse,
    BacktestRequest,
    BacktestRunResponse,
)

router = APIRouter(tags=["Backtesting"])

# Mounted without the "/v1" prefix the rest of this module's router gets
# (see src/api/app.py) -- the frontend (frontend/src/api/endpoints.ts
# BACKTESTING.strategies) calls this at the /v2 path screening.py's
# prebuilt-screen-library endpoints already live under, since a "backtest
# strategy" is just that same library reshaped for submission as
# BacktestRequest.strategy_definition (Pillar 2 Frontend Bug 93).
strategies_router = APIRouter(tags=["Backtesting"])


class BacktestStrategyOption(BaseModel):
    """A selectable backtest strategy: a pre-built screen definition
    (src/engines/e4_screens_library.py) reshaped so its `strategy_definition`
    can be submitted directly to `POST /v1/analytics/backtest`.
    """

    strategy_id: str
    name: str
    description: str | None = None
    tags: list[str] = []
    strategy_definition: dict


@strategies_router.get(
    "/v2/analytics/backtest/strategies",
    response_model=list[BacktestStrategyOption],
)
async def list_backtest_strategies():
    """List available backtest strategies.

    Reuses the same pre-built screen library `GET /v2/analytics/screens/
    library` (src/api/routers/screening.py) already exposes, rather than
    inventing a second, parallel strategy-template system -- a "backtest
    strategy" here is naturally just a named, pre-built screen definition
    that can also be run historically via the backtest worker.
    """
    from src.engines.e4_screens_library import get_all_prebuilt_screens

    screens = get_all_prebuilt_screens()
    return [
        BacktestStrategyOption(
            strategy_id=sid,
            name=s["name"],
            description=s.get("description"),
            tags=s.get("tags", []),
            strategy_definition=s.get("filters", {}),
        )
        for sid, s in screens.items()
    ]


@router.post(
    "/analytics/backtest",
    response_model=BacktestRunResponse,
    status_code=201,
)
async def submit_backtest(
    body: BacktestRequest,
    session: AsyncSession = Depends(get_session),
):
    """Submit a new backtest.

    The run is queued with status PENDING. Marking it COMPLETED on insert
    would lie to the client because the underlying backtest engine has not
    yet executed. ``scripts/run_backtest_worker.py`` polls for PENDING rows,
    runs the actual strategy-basket simulation, and writes a BacktestResult
    before flipping status to COMPLETED (or FAILED on error). Run it via
    ``python -m scripts.run_backtest_worker --once`` or ``--loop``; it is not
    yet wired into a scheduler (see that script's module docstring).
    """
    run = BacktestRun(
        backtest_id=uuid.uuid4(),
        name=body.name,
        description=body.description,
        status="PENDING",
        strategy_definition=body.strategy_definition,
        start_date=body.start_date,
        end_date=body.end_date,
        benchmark=body.benchmark,
        weighting_method=body.weighting_method,
        rebalance_frequency=body.rebalance_frequency,
        max_positions=body.max_positions,
        transaction_cost_bps=body.transaction_cost_bps,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return BacktestRunResponse.model_validate(run)


@router.get(
    "/analytics/backtest/{backtest_id}/results",
    response_model=BacktestPerformanceResponse,
)
async def get_backtest_results(
    backtest_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Return performance metrics for a backtest."""
    query = (
        select(BacktestResult)
        .where(BacktestResult.backtest_id == backtest_id)
        .limit(1)
    )
    result = await session.execute(query)
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="No results found for this backtest")

    return BacktestPerformanceResponse(
        backtest_id=backtest_id,
        total_return=float(row.total_return) if row.total_return else None,
        annualized_return=float(row.annualized_return) if row.annualized_return else None,
        benchmark_return=float(row.benchmark_return) if row.benchmark_return else None,
        excess_return=float(row.excess_return) if row.excess_return else None,
        sharpe_ratio=float(row.sharpe_ratio) if row.sharpe_ratio else None,
        sortino_ratio=float(row.sortino_ratio) if row.sortino_ratio else None,
        max_drawdown=float(row.max_drawdown) if row.max_drawdown else None,
        max_drawdown_duration_days=row.max_drawdown_duration_days,
        annualized_volatility=float(row.annualized_volatility) if row.annualized_volatility else None,
        beta=float(row.beta) if row.beta else None,
        tracking_error=float(row.tracking_error) if row.tracking_error else None,
        information_ratio=float(row.information_ratio) if row.information_ratio else None,
        win_rate=float(row.win_rate) if row.win_rate else None,
        avg_win=float(row.avg_win) if row.avg_win else None,
        avg_loss=float(row.avg_loss) if row.avg_loss else None,
        turnover_annual=float(row.turnover_annual) if row.turnover_annual else None,
        total_trades=row.total_trades,
        monthly_returns=row.monthly_returns,
    )


@router.get(
    "/analytics/backtest/{backtest_id}/holdings",
    response_model=BacktestHoldingsResponse,
)
async def get_backtest_holdings(
    backtest_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Return holdings for a backtest."""
    query = (
        select(BacktestResult)
        .where(BacktestResult.backtest_id == backtest_id)
        .limit(1)
    )
    result = await session.execute(query)
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="No results found for this backtest")

    return BacktestHoldingsResponse(
        backtest_id=backtest_id,
        period_holdings=row.period_holdings,
    )


@router.post(
    "/analytics/backtest/compare",
    response_model=BacktestCompareResponse,
)
async def compare_backtests(
    body: BacktestCompareRequest,
    session: AsyncSession = Depends(get_session),
):
    """Compare performance of multiple backtests."""
    results = []
    for bid in body.backtest_ids:
        query = (
            select(BacktestResult)
            .where(BacktestResult.backtest_id == bid)
            .limit(1)
        )
        result = await session.execute(query)
        row = result.scalar_one_or_none()
        if row:
            results.append(BacktestPerformanceResponse(
                backtest_id=bid,
                total_return=float(row.total_return) if row.total_return else None,
                annualized_return=float(row.annualized_return) if row.annualized_return else None,
                benchmark_return=float(row.benchmark_return) if row.benchmark_return else None,
                excess_return=float(row.excess_return) if row.excess_return else None,
                sharpe_ratio=float(row.sharpe_ratio) if row.sharpe_ratio else None,
                sortino_ratio=float(row.sortino_ratio) if row.sortino_ratio else None,
                max_drawdown=float(row.max_drawdown) if row.max_drawdown else None,
                max_drawdown_duration_days=row.max_drawdown_duration_days,
                annualized_volatility=float(row.annualized_volatility) if row.annualized_volatility else None,
            ))

    return BacktestCompareResponse(backtests=results)
