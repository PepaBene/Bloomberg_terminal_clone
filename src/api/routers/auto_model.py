"""Automatic Model Builder API endpoints.

Auto-assembles scored analytical models for ECONOMIC, MARKET, INDUSTRY,
CORPORATE, and COMPANY scopes. The generic ``/build`` endpoint accepts
caller-supplied metrics; the convenience endpoints assemble inputs from the
platform's own data (fundamentals, macro series) before modeling.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.engines.auto_model_builder import SCOPES, build_model
from src.models.analytics import AnalyticsResult, CompsResult, DCFResult
from src.models.entity import Entity
from src.models.fundamentals import BalanceSheet, CashFlowStatement, FinancialPeriod, IncomeStatement
from src.models.security import Security
from src.schemas.auto_model import AnalyticalModelResponse, ModelBuildRequest

router = APIRouter(prefix="/models", tags=["Auto Model Builder"])


@router.get("/scopes")
async def list_scopes():
    """List the analytical model scopes the builder supports."""
    return {"scopes": list(SCOPES)}


@router.post("/build", response_model=AnalyticalModelResponse)
async def build(request: ModelBuildRequest):
    """Build a model from caller-supplied metrics for any scope."""
    try:
        model = build_model(request.scope, request.data, request.subject)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return model.to_dict()


@router.get("/company/{entity_id}", response_model=AnalyticalModelResponse)
async def build_company_model_endpoint(
    entity_id: uuid.UUID, session: AsyncSession = Depends(get_session)
):
    """Auto-build a full company model from the latest fundamentals on file.

    Previously only ``revenue_growth``/``ebitda_margin`` were populated, so
    quality/value/safety silently fell back to build_company_model()'s
    neutral 50.0 defaults regardless of what real DCF/comps/Altman/
    Piotroski data existed for the entity. Now wires those in too.
    (``smart_money_signal``/``insider_buy_ratio`` remain unwired — they'd
    need their own quarter-over-quarter diffing query, out of scope here —
    so sentiment_score still defaults to neutral.)
    """
    entity = (
        await session.execute(select(Entity).where(Entity.entity_id == entity_id))
    ).scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    # Pull the two most recent annual income statements for growth/margins.
    periods = (
        await session.execute(
            select(FinancialPeriod)
            .where(FinancialPeriod.entity_id == entity_id)
            .order_by(FinancialPeriod.period_end_date.desc())
            .limit(2)
        )
    ).scalars().all()

    data: dict = {}
    statements = []
    for period in periods:
        stmt = (
            await session.execute(
                select(IncomeStatement).where(IncomeStatement.period_id == period.period_id)
            )
        ).scalar_one_or_none()
        if stmt:
            statements.append(stmt)

    if statements:
        latest = statements[0]
        rev = float(latest.total_revenue) if latest.total_revenue is not None else None
        op = float(latest.operating_income) if latest.operating_income is not None else None
        ni = float(latest.net_income) if latest.net_income is not None else None
        if rev and op is not None:
            data["ebitda_margin"] = round(op / rev * 100, 2)
        if len(statements) > 1 and statements[1].total_revenue:
            prev_rev = float(statements[1].total_revenue)
            if prev_rev:
                data["revenue_growth"] = round((rev - prev_rev) / prev_rev * 100, 2)
        if rev and ni is not None:
            data["net_income"] = ni

        # ROE from the latest period's balance sheet.
        latest_period = periods[0]
        bs = (
            await session.execute(
                select(BalanceSheet).where(BalanceSheet.period_id == latest_period.period_id)
            )
        ).scalar_one_or_none()
        if bs and bs.total_equity and ni is not None:
            data["roe"] = round(ni / float(bs.total_equity) * 100, 2)

        # FCF margin from the latest period's cash flow statement.
        cf = (
            await session.execute(
                select(CashFlowStatement).where(CashFlowStatement.period_id == latest_period.period_id)
            )
        ).scalar_one_or_none()
        if cf and cf.free_cash_flow is not None and rev:
            data["fcf_margin"] = round(float(cf.free_cash_flow) / rev * 100, 2)

    # Piotroski F-Score / Altman Z-Score (batch-computed AnalyticsResult rows).
    score_result = await session.execute(
        select(AnalyticsResult.metric_name, AnalyticsResult.value)
        .where(
            AnalyticsResult.entity_id == entity_id,
            AnalyticsResult.metric_name.in_(["piotroski_f_score", "altman_z_score"]),
        )
        .order_by(AnalyticsResult.as_of_date.desc())
    )
    scores: dict = {}
    for name, value in score_result.all():
        if value is not None and name not in scores:
            scores[name] = float(value)
    if "piotroski_f_score" in scores:
        data["piotroski"] = scores["piotroski_f_score"]
    if "altman_z_score" in scores:
        data["altman_z"] = scores["altman_z_score"]

    # DCF upside/downside and relative-valuation percentile need the
    # entity's primary equity security (DCF/comps results are security-keyed).
    sec_row = (
        await session.execute(
            select(Security.security_id, Security.security_type, Security.status)
            .where(Security.issuer_entity_id == entity_id, Security.asset_class == "EQUITY")
        )
    ).all()
    if sec_row:
        sec_row.sort(key=lambda r: (r[2] != "ACTIVE", r[1] != "COMMON_STOCK"))
        security_id = sec_row[0][0]

        dcf = (
            await session.execute(
                select(DCFResult)
                .where(DCFResult.security_id == security_id)
                .order_by(DCFResult.calculation_date.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if dcf and dcf.upside_downside_pct is not None:
            data["dcf_upside_pct"] = float(dcf.upside_downside_pct)

        pe_percentile_result = await session.execute(
            select(AnalyticsResult.value)
            .where(
                AnalyticsResult.security_id == security_id,
                AnalyticsResult.metric_name == "comps_pe_trailing_percentile",
            )
            .order_by(AnalyticsResult.as_of_date.desc())
            .limit(1)
        )
        pe_percentile = pe_percentile_result.scalar_one_or_none()
        if pe_percentile is not None:
            # Convert 0-100 percentile to build_company_model's -1..1 scale
            # (negative = cheaper than peers, matching its sign convention).
            data["pe_vs_peers"] = round((float(pe_percentile) - 50.0) / 50.0, 4)

    subject = getattr(entity, "legal_name", None) or getattr(entity, "name", None) or str(entity_id)
    model = build_model("COMPANY", data, subject)
    return model.to_dict()
