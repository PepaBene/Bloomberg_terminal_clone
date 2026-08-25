"""Layer 3 (AI_THREE_LAYER_REBUILD_PLAN.md §5.1): direct API access to the
previously-dormant whatif/drift/trade-list engines, now wired to real
portfolio data via ``src/services/portfolio_advisory.py``. These are the
same code paths the Layer-3 adviser's tools (``src/ai/tools/portfolio.py``)
call -- this router is the human/direct-integration front door onto the
identical logic, not a separate reimplementation.

Engine dataclasses (``WhatIfResult``, ``DriftResult``, ``TradeList``, ...)
are returned via ``dataclasses.asdict()`` rather than a parallel hand-
written Pydantic schema tree -- they're already well-typed and documented
in the engine modules themselves; mirroring that shape field-for-field in
a second schema layer would be pure duplication for a purely internal-
tooling surface like this one.
"""
from __future__ import annotations

import dataclasses
import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.engines import trade_list_engine
from src.services import portfolio_advisory

router = APIRouter(tags=["AI - Portfolio Advisor Tools"])


@router.post("/portfolios/{portfolio_id}/whatif")
async def whatif(
    portfolio_id: uuid.UUID,
    trades: list[dict] = Body(..., description="[{ticker, action, shares, price_per_share}]"),
    session: AsyncSession = Depends(get_session),
):
    """Simulate proposed trades' impact on position weights, risk,
    factor exposure, compliance, and transaction costs, against this
    portfolio's real current holdings."""
    result = await portfolio_advisory.compute_whatif(session, portfolio_id, trades)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Portfolio '{portfolio_id}' not found")
    return dataclasses.asdict(result)


@router.post("/portfolios/{portfolio_id}/drift-analysis")
async def drift_analysis(
    portfolio_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Compute FRESH drift vs. this portfolio's most recently set target
    allocation, from real current positions -- unlike the existing
    ``GET /v4/.../drift``, which only ever reads back a stored snapshot
    (nothing in this codebase actually computes drift today; confirmed
    via the Phase 3 infrastructure survey).
    """
    portfolio = await portfolio_advisory.get_portfolio(session, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail=f"Portfolio '{portfolio_id}' not found")

    analysis = await portfolio_advisory.compute_drift(session, portfolio_id)
    if analysis is None:
        return {
            "portfolio_id": str(portfolio_id),
            "target_allocation_set": False,
            "detail": "No target allocation set yet -- POST /v4/portfolios/{id}/drift/target first.",
        }
    return {
        "portfolio_id": str(portfolio_id),
        "target_allocation_set": True,
        "target_allocation": analysis.target_allocation,
        "result": dataclasses.asdict(analysis.result),
        "rebalance_trades": analysis.rebalance_trades,
    }


@router.post("/portfolios/{portfolio_id}/trade-list")
async def trade_list(
    portfolio_id: uuid.UUID,
    export_format: str = Query("json", pattern="^(json|csv|fix|ems)$"),
    rebalance_trades: list[dict] | None = Body(
        None, description="Defaults to this portfolio's current suggested rebalance trades when omitted",
    ),
    session: AsyncSession = Depends(get_session),
):
    """Generate a broker-ready trade list. Without an explicit
    ``rebalance_trades`` body, uses this portfolio's current drift-based
    rebalance suggestions (requires a target allocation to already be set,
    same as ``drift-analysis``).
    """
    portfolio = await portfolio_advisory.get_portfolio(session, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail=f"Portfolio '{portfolio_id}' not found")

    trades = rebalance_trades
    if trades is None:
        analysis = await portfolio_advisory.compute_drift(session, portfolio_id)
        if analysis is None:
            raise HTTPException(
                status_code=400,
                detail="No rebalance_trades supplied and no target allocation set to derive them from.",
            )
        trades = analysis.rebalance_trades

    result = await portfolio_advisory.build_trade_list(session, portfolio_id, trades)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Portfolio '{portfolio_id}' not found")

    if export_format == "csv":
        return PlainTextResponse(trade_list_engine.format_trade_list_csv(result), media_type="text/csv")
    if export_format == "fix":
        return trade_list_engine.format_trade_list_fix(result)
    if export_format == "ems":
        return trade_list_engine.format_trade_list_ems(result)
    return dataclasses.asdict(result)
