"""Pillar 2 FI Supplement -- Part 6: FI Screening & Scenarios API.

Endpoints for bond screening, rate shock scenarios, sensitivity tables,
and multi-variable scenario analysis.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.engines.e4_fi_screening import (
    BondScreenFilter,
    apply_bond_filters,
    rank_bonds,
    rating_to_numeric,
)
from src.engines.e5_fi_rate_shocks import (
    apply_fi_rate_scenario,
    get_fi_rate_scenarios,
)
from src.engines.e8_fi_scenarios import (
    fi_scenario_shift,
    fi_sensitivity_table,
)
from src.schemas.fi_screening import (
    BondScreenRequest,
    BondScreenResponse,
    BondScreenResult,
    PortfolioPositionInput,
    RateScenarioInfo,
    RateScenarioListResponse,
    RateScenarioPortfolioRequest,
    RateScenarioResponse,
    ScenarioAnalysisRequest,
    ScenarioAnalysisResponse,
    ScenarioPositionPnl,
    SensitivityCell,
    SensitivityRequest,
    SensitivityResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v2/analytics", tags=["FI Screening & Scenarios"])


# ---------------------------------------------------------------------------
# Default ranges for sensitivity tables
# ---------------------------------------------------------------------------

_DEFAULT_RANGE = [-200, -100, -50, 0, 50, 100, 200]


# ---------------------------------------------------------------------------
# POST /bonds/screen — multi-factor bond screening
# ---------------------------------------------------------------------------

@router.post("/bonds/screen", response_model=BondScreenResponse)
async def screen_bonds(
    request: BondScreenRequest,
    session: AsyncSession = Depends(get_session),
):
    """Screen corporate bonds using multi-factor filters.

    Loads all bonds from the database, enriches with EOD price data,
    applies filters, ranks, and returns results.
    """
    from src.models.corporate_bond import BondEODPrice, CorporateBond

    # Load bonds
    stmt = select(CorporateBond)
    result = await session.execute(stmt)
    bonds_orm = result.scalars().unique().all()

    # Load latest EOD prices (keyed by bond_id)
    eod_stmt = select(BondEODPrice)
    eod_result = await session.execute(eod_stmt)
    eod_rows = eod_result.scalars().all()

    # Build bond_id -> latest EOD mapping
    eod_map: dict = {}
    for eod in eod_rows:
        bid = eod.bond_id
        if bid not in eod_map or eod.price_date > eod_map[bid].price_date:
            eod_map[bid] = eod

    # Build bond dicts for screening
    bond_dicts: list[dict] = []
    for b in bonds_orm:
        eod = eod_map.get(b.bond_id)
        rating_num = rating_to_numeric(getattr(b, "initial_rating_sp", None))
        is_ig = getattr(b, "is_investment_grade", None)
        if is_ig is None and rating_num is not None:
            is_ig = rating_num <= 10

        bond_dict = {
            "cusip": b.cusip,
            "name": getattr(b, "name", None),
            "coupon_rate": getattr(b, "coupon_rate", None),
            "maturity_date": getattr(b, "maturity_date", None),
            "seniority": getattr(b, "seniority", None),
            "is_callable": getattr(b, "is_callable", None),
            "is_investment_grade": is_ig,
            "outstanding_amount": getattr(b, "outstanding_amount", None),
            "rating_numeric": rating_num,
            "spread_bps": eod.g_spread_bps if eod else None,
            "yield_to_worst": eod.yield_to_worst if eod else None,
            "yield_to_maturity": eod.yield_to_maturity if eod else None,
            "liquidity_score": eod.liquidity_score if eod else None,
        }
        bond_dicts.append(bond_dict)

    # Apply filters
    filters = [
        BondScreenFilter(
            field=f.field,
            op=f.op,
            value=f.value,
            value2=f.value2,
        )
        for f in request.filters
    ]
    filtered = apply_bond_filters(bond_dicts, filters)

    # Rank & limit
    ranked = rank_bonds(filtered, request.sort_by, request.ascending, request.limit)

    results = [
        BondScreenResult(
            cusip=b["cusip"],
            name=b.get("name"),
            coupon_rate=b.get("coupon_rate"),
            maturity_date=b.get("maturity_date"),
            spread_bps=b.get("spread_bps"),
            yield_to_worst=b.get("yield_to_worst"),
            liquidity_score=b.get("liquidity_score"),
            is_investment_grade=b.get("is_investment_grade"),
        )
        for b in ranked
    ]

    return BondScreenResponse(results=results, total=len(results))


# ---------------------------------------------------------------------------
# GET /bonds/rate-scenarios — list available FI rate shock scenarios
# ---------------------------------------------------------------------------

@router.get("/bonds/rate-scenarios", response_model=RateScenarioListResponse)
async def list_rate_scenarios():
    """Return all available fixed-income rate shock scenarios."""
    scenarios = get_fi_rate_scenarios()
    items = [
        RateScenarioInfo(
            scenario_id=sid,
            label=s["label"],
            rate_shift_bps=s["rate_shift_bps"],
            spread_impact_ig_bps=s["spread_impact_ig_bps"],
            spread_impact_hy_bps=s["spread_impact_hy_bps"],
            description=s["description"],
        )
        for sid, s in scenarios.items()
    ]
    return RateScenarioListResponse(scenarios=items)


# ---------------------------------------------------------------------------
# POST /bonds/rate-scenario/{scenario_id} — apply a rate scenario
# ---------------------------------------------------------------------------

@router.post(
    "/bonds/rate-scenario/{scenario_id}",
    response_model=RateScenarioResponse,
)
async def apply_rate_scenario(
    scenario_id: str,
    request: RateScenarioPortfolioRequest,
):
    """Apply a historical rate shock scenario to a bond portfolio."""
    positions = [p.model_dump() for p in request.positions]

    try:
        result = apply_fi_rate_scenario(positions, scenario_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return RateScenarioResponse(
        scenario_id=scenario_id,
        scenario_label=result["scenario"]["label"],
        total_pnl=result["total_pnl"],
        total_pnl_pct=result["total_pnl_pct"],
        rate_pnl=result["rate_pnl"],
        spread_pnl=result["spread_pnl"],
        by_position=[
            ScenarioPositionPnl(**bp) for bp in result["by_position"]
        ],
    )


# ---------------------------------------------------------------------------
# POST /bonds/sensitivity — 1D or 2D sensitivity table
# ---------------------------------------------------------------------------

@router.post("/bonds/sensitivity", response_model=SensitivityResponse)
async def bond_sensitivity(request: SensitivityRequest):
    """Generate a 1D or 2D sensitivity table for a bond using duration-convexity."""
    var1_range = request.var1_range or [float(x) for x in _DEFAULT_RANGE]
    var2_range = request.var2_range

    result = fi_sensitivity_table(
        base_price=request.base_price,
        modified_duration=request.modified_duration,
        convexity=request.convexity,
        var1_name=request.var1_name,
        var1_range=var1_range,
        var2_name=request.var2_name,
        var2_range=var2_range,
    )

    cells = [
        SensitivityCell(
            var1_value=r["var1_value"],
            var2_value=r.get("var2_value"),
            price=r["price"],
            price_change_pct=r["price_change_pct"],
        )
        for r in result["results"]
    ]

    return SensitivityResponse(
        var1_name=result["var1_name"],
        var2_name=result.get("var2_name"),
        results=cells,
    )


# ---------------------------------------------------------------------------
# POST /bonds/scenario-analysis — multi-variable scenario shift
# ---------------------------------------------------------------------------

@router.post("/bonds/scenario-analysis", response_model=ScenarioAnalysisResponse)
async def scenario_analysis(request: ScenarioAnalysisRequest):
    """Apply a multi-variable scenario shift (yield + spread + migration) to a portfolio."""
    positions = [p.model_dump() for p in request.positions]

    result = fi_scenario_shift(
        positions=positions,
        yield_shift_bps=request.yield_shift_bps,
        spread_shift_bps=request.spread_shift_bps,
        rating_migration_notches=request.rating_migration_notches,
    )

    return ScenarioAnalysisResponse(
        total_pnl=result["total_pnl"],
        total_pnl_pct=result["total_pnl_pct"],
        yield_impact=result["yield_impact"],
        spread_impact=result["spread_impact"],
        migration_impact=result["migration_impact"],
        position_count=result["position_count"],
    )
