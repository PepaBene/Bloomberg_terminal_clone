"""Industry Intelligence API endpoints (Pillar 3 Phase 3A)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.models.entity import Entity
from src.models.industry_intelligence import (
    IndustryCompetitiveStructure,
    IndustryCyclePosition,
    IndustryProfile,
)
from src.schemas.industry_intelligence import (
    IndustryCompareResponse,
    IndustryCycleResponse,
    IndustryProfileResponse,
    IndustryRankingEntry,
    IndustryRankingResponse,
    IndustryStructureResponse,
)

router = APIRouter(tags=["Industry Intelligence"])


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
    result = await session.execute(
        select(IndustryProfile)
        .where(IndustryProfile.gics_code == gics_code)
        .order_by(IndustryProfile.as_of_date.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
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
    # (industry_group=4, industry=6, sub_industry=8 chars).
    code_len = len(gics_code)
    if code_len == 8:
        ent_filter = Entity.gics_sub_industry == gics_code
    elif code_len == 6:
        ent_filter = Entity.gics_industry == gics_code
    elif code_len == 4:
        ent_filter = Entity.gics_industry_group == gics_code
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
    result = await session.execute(
        select(IndustryProfile)
        .where(IndustryProfile.gics_code == gics_code)
        .order_by(IndustryProfile.as_of_date.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
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
    result = await session.execute(
        select(IndustryCompetitiveStructure)
        .where(IndustryCompetitiveStructure.gics_code == gics_code)
        .order_by(IndustryCompetitiveStructure.as_of_date.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
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
    result = await session.execute(
        select(IndustryCyclePosition)
        .where(IndustryCyclePosition.gics_code == gics_code)
        .order_by(IndustryCyclePosition.as_of_date.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
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
