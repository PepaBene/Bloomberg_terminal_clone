"""Industry Intelligence API endpoints (Pillar 3 Phase 3A)."""

import statistics
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.engines import industry_cycle, industry_economics
from src.models.analytics import AnalyticsResult
from src.models.entity import Entity
from src.models.fundamentals import BalanceSheet, FinancialPeriod, IncomeStatement
from src.models.industry_intelligence import (
    IndustryCompetitiveStructure,
    IndustryCyclePosition,
    IndustryProfile,
)
from src.models.security import EODPrice, EquityDetails, Security
from src.schemas.industry_intelligence import (
    IndustryCompareResponse,
    IndustryCycleResponse,
    IndustryProfileResponse,
    IndustryRankingEntry,
    IndustryRankingResponse,
    IndustryStructureResponse,
)

router = APIRouter(tags=["Industry Intelligence"])

_GICS_COL_BY_LEN = {2: "gics_sector", 4: "gics_industry_group", 6: "gics_industry", 8: "gics_sub_industry"}
_GICS_LEVEL_BY_LEN = {2: "SECTOR", 4: "INDUSTRY_GROUP", 6: "INDUSTRY", 8: "SUB_INDUSTRY"}


def _gics_filter(gics_code: str):
    col = _GICS_COL_BY_LEN.get(len(gics_code))
    if col is None:
        return (Entity.gics_industry == gics_code) | (Entity.gics_sub_industry == gics_code)
    return getattr(Entity, col) == gics_code


async def _compute_industry_intelligence(session: AsyncSession, gics_code: str) -> bool:
    """Compute and persist the three industry tables (profile / competitive
    structure / cycle position) for a GICS code by aggregating its member
    companies' real fundamentals + analytics. Returns False when the GICS
    has no companies with fundamentals to aggregate.

    This is the missing producer for `industry_profiles` /
    `industry_competitive_structures` / `industry_cycle_positions` — the
    engines (`industry_economics`, `industry_cycle`) existed but had no caller.
    """
    entities = (
        await session.execute(
            select(Entity.entity_id).where(_gics_filter(gics_code), Entity.status != "INACTIVE").limit(500)
        )
    ).scalars().all()
    if not entities:
        return False

    company_data: list[dict] = []
    company_revenues: list[dict] = []
    market_caps: list[float] = []
    capex_ratios: list[float] = []
    rd_ratios: list[float] = []

    for eid in entities:
        periods = (
            await session.execute(
                select(FinancialPeriod)
                .where(FinancialPeriod.entity_id == eid)
                .order_by(FinancialPeriod.period_end_date.asc())
                .limit(8)
            )
        ).scalars().all()
        if not periods:
            continue

        rev_hist, latest = [], periods[-1]
        for p in periods:
            if p.income_statement and p.income_statement.total_revenue is not None:
                rev_hist.append(float(p.income_statement.total_revenue))
        inc = latest.income_statement
        if not inc or inc.total_revenue is None or float(inc.total_revenue) <= 0:
            continue
        rev = float(inc.total_revenue)

        gm = round(float(inc.gross_profit) / rev * 100, 2) if inc.gross_profit is not None else None
        om = round(float(inc.operating_income) / rev * 100, 2) if inc.operating_income is not None else None
        capex_to_rev = None
        if latest.cash_flow and latest.cash_flow.capital_expenditures is not None:
            capex_to_rev = round(abs(float(latest.cash_flow.capital_expenditures)) / rev * 100, 2)
        rd_to_rev = None

        # roic / wacc from analytics.
        met = {}
        for name, val in (
            await session.execute(
                select(AnalyticsResult.metric_name, AnalyticsResult.value)
                .where(AnalyticsResult.entity_id == eid,
                       AnalyticsResult.metric_name.in_(["roic", "wacc"]))
                .order_by(AnalyticsResult.as_of_date.desc())
            )
        ).all():
            if val is not None and name not in met:
                met[name] = float(val)

        company_data.append({
            "revenue_history": rev_hist,
            "gross_margin": gm,
            "operating_margin": om,
            "capex_to_revenue": capex_to_rev,
            "rd_to_revenue": rd_to_rev,
            "roic": met.get("roic"),
            "wacc": met.get("wacc"),
        })
        company_revenues.append({"entity_id": str(eid), "revenue": rev})
        if capex_to_rev is not None:
            capex_ratios.append(capex_to_rev)

        # Market cap.
        sec = (
            await session.execute(
                select(Security.security_id)
                .where(Security.issuer_entity_id == eid, Security.asset_class == "EQUITY").limit(1)
            )
        ).scalar_one_or_none()
        if sec is not None:
            shares = (await session.execute(
                select(EquityDetails.shares_outstanding).where(EquityDetails.security_id == sec)
            )).scalar_one_or_none()
            close = (await session.execute(
                select(EODPrice.close).where(EODPrice.security_id == sec, EODPrice.close.isnot(None))
                .order_by(EODPrice.price_date.desc()).limit(1)
            )).scalar_one_or_none()
            if shares is not None and close is not None:
                market_caps.append(float(shares) * float(close))

    if not company_data:
        return False

    today = date.today()
    gics_level = _GICS_LEVEL_BY_LEN.get(len(gics_code), "INDUSTRY")

    # ── Profile ───────────────────────────────────────────────────────
    econ = industry_economics.compute_industry_economics(company_data)
    total_mcap = sum(market_caps) if market_caps else None
    median_mcap = statistics.median(market_caps) if market_caps else None
    await _upsert_industry(session, IndustryProfile, gics_code, today, dict(
        gics_level=gics_level, gics_name=gics_code,
        company_count=len(company_data),
        total_market_cap=total_mcap, median_market_cap=median_mcap,
        revenue_growth_3y_cagr=econ.revenue_growth_3y_cagr,
        revenue_growth_5y_cagr=econ.revenue_growth_5y_cagr,
        revenue_dispersion=econ.revenue_dispersion,
        median_gross_margin=econ.median_gross_margin,
        median_operating_margin=econ.median_operating_margin,
        median_capex_to_revenue=econ.median_capex_to_revenue,
        median_rd_to_revenue=econ.median_rd_to_revenue,
        median_roic=econ.median_roic, median_wacc=econ.median_wacc,
        roic_wacc_spread=econ.roic_wacc_spread, roic_dispersion=econ.roic_dispersion,
        capital_cycle_indicator=econ.capital_cycle_indicator,
    ), profile=True)

    # ── Competitive structure ─────────────────────────────────────────
    gm_hist = [c["gross_margin"] for c in company_data if c.get("gross_margin") is not None]
    struct = industry_cycle.compute_competitive_structure(
        company_revenues,
        gross_margin_history=gm_hist,
        capex_intensity=(statistics.mean(capex_ratios) if capex_ratios else 0.0),
        rd_intensity=0.0,
    )
    await _upsert_industry(session, IndustryCompetitiveStructure, gics_code, today, dict(
        hhi_index=struct.hhi_index, hhi_classification=struct.hhi_classification,
        top3_market_share=struct.top3_market_share, top5_market_share=struct.top5_market_share,
        top10_market_share=struct.top10_market_share, consolidation_trend=struct.consolidation_trend,
        barrier_to_entry=struct.barrier_to_entry, pricing_power=struct.pricing_power,
        competitive_dynamics=struct.competitive_dynamics,
        market_share_data={"companies": company_revenues},
    ))

    # ── Cycle position (industry-aggregate per-fiscal-year series) ─────
    agg = (
        await session.execute(
            select(
                FinancialPeriod.fiscal_year,
                func.sum(IncomeStatement.total_revenue),
                func.sum(IncomeStatement.operating_income),
            )
            .join(IncomeStatement, IncomeStatement.period_id == FinancialPeriod.period_id)
            .where(FinancialPeriod.entity_id.in_(entities))
            .group_by(FinancialPeriod.fiscal_year)
            .order_by(FinancialPeriod.fiscal_year.asc())
        )
    ).all()
    rev_series = [float(r) for _yr, r, _oi in agg if r is not None]
    margin_series = [
        round(float(oi) / float(r) * 100, 2)
        for _yr, r, oi in agg if r and oi is not None
    ]
    cycle = industry_cycle.compute_cycle_position(
        revenue_history=rev_series or None,
        margin_history=margin_series or None,
    )
    await _upsert_industry(session, IndustryCyclePosition, gics_code, today, dict(
        revenue_growth_acceleration=cycle.revenue_growth_acceleration,
        capacity_utilization_proxy=cycle.capacity_utilization_proxy,
        inventory_dynamics=cycle.inventory_dynamics,
        margin_cycle_direction=cycle.margin_cycle_direction,
        cycle_position=cycle.cycle_position, cycle_confidence=cycle.confidence,
    ))

    await session.commit()
    return True


async def _upsert_industry(session, model, gics_code, as_of, values: dict, profile: bool = False) -> None:
    existing = (
        await session.execute(
            select(model).where(model.gics_code == gics_code, model.as_of_date == as_of)
        )
    ).scalar_one_or_none()
    if existing is not None:
        for k, v in values.items():
            setattr(existing, k, v)
    else:
        session.add(model(id=uuid.uuid4(), gics_code=gics_code, as_of_date=as_of, **values))


# ── Static routes (MUST come before parametric routes) ──────────────


@router.get(
    "/industry/compare",
    response_model=list[IndustryCompareResponse],
)
async def compare_industries(
    codes: str = Query(..., description="Comma-separated GICS codes"),
    session: AsyncSession = Depends(get_session),
):
    """Side-by-side comparison of multiple industries."""
    code_list = [c.strip() for c in codes.split(",") if c.strip()]
    if not code_list:
        return []

    result = await session.execute(
        select(IndustryProfile)
        .where(IndustryProfile.gics_code.in_(code_list))
        .order_by(IndustryProfile.as_of_date.desc())
    )
    rows = result.scalars().all()

    # Keep only the latest profile per gics_code
    seen: dict[str, IndustryProfile] = {}
    for row in rows:
        if row.gics_code not in seen:
            seen[row.gics_code] = row

    return [
        IndustryCompareResponse(
            gics_code=row.gics_code,
            gics_name=row.gics_name,
            company_count=row.company_count,
            total_market_cap=float(row.total_market_cap) if row.total_market_cap is not None else None,
            median_gross_margin=float(row.median_gross_margin) if row.median_gross_margin is not None else None,
            median_operating_margin=float(row.median_operating_margin) if row.median_operating_margin is not None else None,
            median_roic=float(row.median_roic) if row.median_roic is not None else None,
            revenue_growth_3y_cagr=float(row.revenue_growth_3y_cagr) if row.revenue_growth_3y_cagr is not None else None,
            capital_cycle_indicator=row.capital_cycle_indicator,
        )
        for row in seen.values()
    ]


@router.get(
    "/industry/rankings",
    response_model=IndustryRankingResponse,
)
async def rank_industries(
    metric: str = Query(..., description="Metric to rank by (e.g. median_roic, median_gross_margin)"),
    session: AsyncSession = Depends(get_session),
):
    """Rank industries by a given metric."""
    allowed_metrics = {
        "median_roic",
        "median_gross_margin",
        "median_operating_margin",
        "revenue_growth_3y_cagr",
        "revenue_growth_5y_cagr",
        "total_market_cap",
        "company_count",
        "roic_wacc_spread",
    }
    if metric not in allowed_metrics:
        raise HTTPException(status_code=400, detail=f"Invalid metric. Allowed: {sorted(allowed_metrics)}")

    # PostgreSQL DISTINCT ON keeps only the latest snapshot per GICS code in
    # SQL — the previous implementation loaded every historical row into
    # memory and deduplicated in Python, which scaled poorly.
    try:
        stmt = (
            select(IndustryProfile)
            .distinct(IndustryProfile.gics_code)
            .order_by(IndustryProfile.gics_code, IndustryProfile.as_of_date.desc())
        )
        result = await session.execute(stmt)
        deduped = list(result.scalars().all())
    except Exception:
        # Some dialects (e.g. SQLite in tests) lack DISTINCT ON; fall back
        # to the safe Python-side dedup path.
        result = await session.execute(
            select(IndustryProfile).order_by(IndustryProfile.as_of_date.desc())
        )
        seen: dict[str, IndustryProfile] = {}
        for row in result.scalars().all():
            if row.gics_code not in seen:
                seen[row.gics_code] = row
        deduped = list(seen.values())

    # Sort by metric descending
    entries = []
    for row in deduped:
        val = getattr(row, metric, None)
        entries.append((row, float(val) if val is not None else None))

    entries.sort(key=lambda x: x[1] if x[1] is not None else float("-inf"), reverse=True)

    rankings = [
        IndustryRankingEntry(
            gics_code=row.gics_code,
            gics_name=row.gics_name,
            metric_value=val,
            rank=i + 1,
        )
        for i, (row, val) in enumerate(entries)
    ]

    return IndustryRankingResponse(metric=metric, rankings=rankings)


# ── Parametric routes ───────────────────────────────────────────────


@router.get(
    "/industry/{gics_code}/overview",
    response_model=IndustryProfileResponse | None,
)
async def get_industry_overview(
    gics_code: str,
    session: AsyncSession = Depends(get_session),
):
    """Full industry profile for a given GICS code."""
    async def _q():
        return (await session.execute(
            select(IndustryProfile).where(IndustryProfile.gics_code == gics_code)
            .order_by(IndustryProfile.as_of_date.desc()).limit(1)
        )).scalar_one_or_none()
    row = await _q()
    if not row and await _compute_industry_intelligence(session, gics_code):
        row = await _q()
    if not row:
        raise HTTPException(status_code=404, detail="Industry profile not found")

    return IndustryProfileResponse(
        id=row.id,
        gics_code=row.gics_code,
        gics_level=row.gics_level,
        gics_name=row.gics_name,
        as_of_date=row.as_of_date,
        company_count=row.company_count,
        total_market_cap=float(row.total_market_cap) if row.total_market_cap is not None else None,
        median_market_cap=float(row.median_market_cap) if row.median_market_cap is not None else None,
        revenue_growth_3y_cagr=float(row.revenue_growth_3y_cagr) if row.revenue_growth_3y_cagr is not None else None,
        revenue_growth_5y_cagr=float(row.revenue_growth_5y_cagr) if row.revenue_growth_5y_cagr is not None else None,
        revenue_dispersion=float(row.revenue_dispersion) if row.revenue_dispersion is not None else None,
        median_gross_margin=float(row.median_gross_margin) if row.median_gross_margin is not None else None,
        median_operating_margin=float(row.median_operating_margin) if row.median_operating_margin is not None else None,
        median_capex_to_revenue=float(row.median_capex_to_revenue) if row.median_capex_to_revenue is not None else None,
        median_rd_to_revenue=float(row.median_rd_to_revenue) if row.median_rd_to_revenue is not None else None,
        median_roic=float(row.median_roic) if row.median_roic is not None else None,
        median_wacc=float(row.median_wacc) if row.median_wacc is not None else None,
        roic_wacc_spread=float(row.roic_wacc_spread) if row.roic_wacc_spread is not None else None,
        roic_dispersion=float(row.roic_dispersion) if row.roic_dispersion is not None else None,
        capital_cycle_indicator=row.capital_cycle_indicator,
    )


@router.get(
    "/industry/{gics_code}/companies",
    response_model=dict,
)
async def get_industry_companies(
    gics_code: str,
    session: AsyncSession = Depends(get_session),
):
    """Companies in a given industry."""
    profile_row = await session.execute(
        select(IndustryProfile)
        .where(IndustryProfile.gics_code == gics_code)
        .order_by(IndustryProfile.as_of_date.desc())
        .limit(1)
    )
    profile = profile_row.scalar_one_or_none()

    # Match against the GICS column whose width matches the requested code
    # (sector=2, industry_group=4, industry=6, sub_industry=8 chars).
    code_len = len(gics_code)
    if code_len == 2:
        ent_filter = Entity.gics_sector == gics_code
    elif code_len == 4:
        ent_filter = Entity.gics_industry_group == gics_code
    elif code_len == 6:
        ent_filter = Entity.gics_industry == gics_code
    elif code_len == 8:
        ent_filter = Entity.gics_sub_industry == gics_code
    else:
        ent_filter = (
            (Entity.gics_industry == gics_code)
            | (Entity.gics_sub_industry == gics_code)
        )

    ent_rows = await session.execute(
        select(Entity)
        .where(ent_filter, Entity.status != "INACTIVE")
        .order_by(Entity.legal_name)
        .limit(500)
    )
    companies = [
        {
            "entity_id": str(e.entity_id),
            "legal_name": e.legal_name,
            "ticker": getattr(e, "primary_ticker", None),
            "gics_industry": e.gics_industry,
            "gics_sub_industry": e.gics_sub_industry,
        }
        for e in ent_rows.scalars().all()
    ]

    if profile is None and not companies:
        # Preserve the 404 behaviour for unknown industries — the
        # endpoint should signal "no such industry" rather than return
        # an empty payload.
        raise HTTPException(status_code=404, detail="Industry profile not found")

    return {
        "gics_code": gics_code,
        "gics_name": profile.gics_name if profile else None,
        "company_count": profile.company_count if profile else len(companies),
        "companies": companies,
    }


@router.get(
    "/industry/{gics_code}/economics",
    response_model=dict,
)
async def get_industry_economics(
    gics_code: str,
    session: AsyncSession = Depends(get_session),
):
    """Revenue, cost, and return profile for an industry."""
    async def _q():
        return (await session.execute(
            select(IndustryProfile).where(IndustryProfile.gics_code == gics_code)
            .order_by(IndustryProfile.as_of_date.desc()).limit(1)
        )).scalar_one_or_none()
    row = await _q()
    if not row and await _compute_industry_intelligence(session, gics_code):
        row = await _q()
    if not row:
        raise HTTPException(status_code=404, detail="Industry profile not found")

    return {
        "gics_code": row.gics_code,
        "gics_name": row.gics_name,
        "revenue_growth_3y_cagr": float(row.revenue_growth_3y_cagr) if row.revenue_growth_3y_cagr is not None else None,
        "revenue_growth_5y_cagr": float(row.revenue_growth_5y_cagr) if row.revenue_growth_5y_cagr is not None else None,
        "median_gross_margin": float(row.median_gross_margin) if row.median_gross_margin is not None else None,
        "median_operating_margin": float(row.median_operating_margin) if row.median_operating_margin is not None else None,
        "median_capex_to_revenue": float(row.median_capex_to_revenue) if row.median_capex_to_revenue is not None else None,
        "median_rd_to_revenue": float(row.median_rd_to_revenue) if row.median_rd_to_revenue is not None else None,
        "median_roic": float(row.median_roic) if row.median_roic is not None else None,
        "median_wacc": float(row.median_wacc) if row.median_wacc is not None else None,
        "roic_wacc_spread": float(row.roic_wacc_spread) if row.roic_wacc_spread is not None else None,
    }


@router.get(
    "/industry/{gics_code}/structure",
    response_model=IndustryStructureResponse | None,
)
async def get_industry_structure(
    gics_code: str,
    session: AsyncSession = Depends(get_session),
):
    """Concentration, barriers, and competitive dynamics for an industry."""
    async def _q():
        return (await session.execute(
            select(IndustryCompetitiveStructure).where(IndustryCompetitiveStructure.gics_code == gics_code)
            .order_by(IndustryCompetitiveStructure.as_of_date.desc()).limit(1)
        )).scalar_one_or_none()
    row = await _q()
    if not row and await _compute_industry_intelligence(session, gics_code):
        row = await _q()
    if not row:
        raise HTTPException(status_code=404, detail="Industry structure not found")

    return IndustryStructureResponse(
        id=row.id,
        gics_code=row.gics_code,
        as_of_date=row.as_of_date,
        hhi_index=float(row.hhi_index) if row.hhi_index is not None else None,
        hhi_classification=row.hhi_classification,
        top3_market_share=float(row.top3_market_share) if row.top3_market_share is not None else None,
        top5_market_share=float(row.top5_market_share) if row.top5_market_share is not None else None,
        top10_market_share=float(row.top10_market_share) if row.top10_market_share is not None else None,
        consolidation_trend=row.consolidation_trend,
        consolidation_5y_delta=float(row.consolidation_5y_delta) if row.consolidation_5y_delta is not None else None,
        barrier_to_entry=row.barrier_to_entry,
        barrier_factors=row.barrier_factors,
        pricing_power=row.pricing_power,
        pricing_power_evidence=row.pricing_power_evidence,
        competitive_dynamics=row.competitive_dynamics,
        market_share_data=row.market_share_data,
    )


@router.get(
    "/industry/{gics_code}/cycle",
    response_model=IndustryCycleResponse | None,
)
async def get_industry_cycle(
    gics_code: str,
    session: AsyncSession = Depends(get_session),
):
    """Cycle positioning for an industry."""
    async def _q():
        return (await session.execute(
            select(IndustryCyclePosition).where(IndustryCyclePosition.gics_code == gics_code)
            .order_by(IndustryCyclePosition.as_of_date.desc()).limit(1)
        )).scalar_one_or_none()
    row = await _q()
    if not row and await _compute_industry_intelligence(session, gics_code):
        row = await _q()
    if not row:
        raise HTTPException(status_code=404, detail="Industry cycle position not found")

    return IndustryCycleResponse(
        id=row.id,
        gics_code=row.gics_code,
        as_of_date=row.as_of_date,
        revenue_growth_acceleration=float(row.revenue_growth_acceleration) if row.revenue_growth_acceleration is not None else None,
        capacity_utilization_proxy=float(row.capacity_utilization_proxy) if row.capacity_utilization_proxy is not None else None,
        inventory_dynamics=row.inventory_dynamics,
        inventory_to_sales_trend=float(row.inventory_to_sales_trend) if row.inventory_to_sales_trend is not None else None,
        margin_cycle_direction=row.margin_cycle_direction,
        operating_margin_momentum=float(row.operating_margin_momentum) if row.operating_margin_momentum is not None else None,
        cycle_position=row.cycle_position,
        cycle_confidence=float(row.cycle_confidence) if row.cycle_confidence is not None else None,
        prior_cycle_position=row.prior_cycle_position,
        cycle_duration_quarters=row.cycle_duration_quarters,
    )
