"""Macro Themes & Scenarios API endpoints (Pillar 3 Phase 4C)."""

import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.engines import macro_scenario_engine
from src.models.entity import Entity
from src.models.fundamentals import FinancialPeriod  # noqa: F401 — relationships load IncomeStatement etc.
from src.models.macro_themes import MacroThemeScore, MacroScenario
from src.models.scenario_impact import ScenarioCompanyImpact
from src.models.security import EODPrice, Security
from src.schemas.macro_themes_schema import (
    ScenarioCreateRequest,
    ScenarioImpactResponse,
    ScenarioResponse,
    ThemeScoreResponse,
    ThemeScreenRequest,
    ThemeScreenResponse,
    ThemeSummaryResponse,
)

router = APIRouter(tags=["Research - Macro Themes & Scenarios"])

# Standard GICS sector code -> name, matching the keys macro_scenario_engine's
# SECTOR_SENSITIVITIES table is written against.
_GICS_SECTOR_NAMES = {
    "10": "Energy", "15": "Materials", "20": "Industrials",
    "25": "Consumer Discretionary", "30": "Consumer Staples",
    "35": "Health Care", "40": "Financials",
    "45": "Information Technology", "50": "Communication Services",
    "55": "Utilities", "60": "Real Estate",
}
_SCENARIO_MAX_ENTITIES = 50


def _float(val):
    return float(val) if val is not None else None


def _theme_score_response(row: MacroThemeScore) -> ThemeScoreResponse:
    return ThemeScoreResponse(
        id=row.id,
        entity_id=row.entity_id,
        theme=row.theme,
        exposure_score=_float(row.exposure_score),
        sensitivity_direction=row.sensitivity_direction,
        evidence=row.evidence,
        quantified_exposure=row.quantified_exposure,
        as_of_date=row.as_of_date,
        created_at=row.created_at,
    )


def _scenario_response(row: MacroScenario) -> ScenarioResponse:
    return ScenarioResponse(
        id=row.id,
        scenario_name=row.scenario_name,
        scenario_type=row.scenario_type,
        description=row.description,
        assumptions=row.assumptions,
        is_active=row.is_active,
        created_by=row.created_by,
        created_at=row.created_at,
    )


def _impact_response(row: ScenarioCompanyImpact) -> ScenarioImpactResponse:
    return ScenarioImpactResponse(
        id=row.id,
        scenario_id=row.scenario_id,
        entity_id=row.entity_id,
        base_eps=_float(row.base_eps),
        scenario_eps=_float(row.scenario_eps),
        eps_change_pct=_float(row.eps_change_pct),
        margin_impact_bps=_float(row.margin_impact_bps),
        rating_implication=row.rating_implication,
        price_target_scenario=_float(row.price_target_scenario),
        narrative=row.narrative,
        created_at=row.created_at,
    )


# ── Static routes (MUST come before parametric routes) ──────────────


@router.get(
    "/research/themes/dashboard",
    response_model=list[ThemeScoreResponse],
)
async def get_themes_dashboard(
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
):
    """Get all themes overview / dashboard."""

    async def _q():
        return (await session.execute(
            select(MacroThemeScore)
            .order_by(MacroThemeScore.as_of_date.desc())
            .limit(limit)
        )).scalars().all()

    rows = await _q()
    if not rows:
        # Bounded first-population pass so a fresh install shows real scores
        # immediately, mirroring the entity cap run_scenario already uses.
        entities = (
            await session.execute(
                select(Entity.entity_id, Entity.gics_sector)
                .where(Entity.gics_sector.isnot(None))
                .limit(_SCENARIO_MAX_ENTITIES)
            )
        ).all()
        wrote = False
        for entity_id, gics_sector in entities:
            if await _compute_theme_scores_for_entity(session, entity_id, gics_sector):
                wrote = True
        if wrote:
            await session.commit()
            rows = await _q()

    return [_theme_score_response(r) for r in rows]


@router.get(
    "/research/scenarios",
    response_model=list[ScenarioResponse],
)
async def list_scenarios(
    active_only: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """List available macro scenarios."""
    stmt = select(MacroScenario)
    if active_only:
        stmt = stmt.where(MacroScenario.is_active == True)  # noqa: E712
    stmt = stmt.order_by(MacroScenario.created_at.desc().nulls_last()).limit(limit)

    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [_scenario_response(r) for r in rows]


@router.post(
    "/research/scenarios/custom",
    response_model=ScenarioResponse,
)
async def create_custom_scenario(
    body: ScenarioCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Create a custom macro scenario."""
    scenario = MacroScenario(
        id=uuid.uuid4(),
        scenario_name=body.scenario_name,
        scenario_type=body.scenario_type or "CUSTOM",
        description=body.description,
        assumptions=body.assumptions,
        created_by=body.created_by,
    )
    session.add(scenario)
    await session.commit()
    return _scenario_response(scenario)


@router.get(
    "/research/scenarios/compare",
    response_model=list[ScenarioImpactResponse],
)
async def compare_scenarios(
    scenario_ids: str = Query(description="Comma-separated scenario UUIDs"),
    entity_id: uuid.UUID = Query(description="Entity to compare across scenarios"),
    session: AsyncSession = Depends(get_session),
):
    """Compare impact of multiple scenarios on a single entity."""
    ids = [uuid.UUID(s.strip()) for s in scenario_ids.split(",") if s.strip()]
    if not ids:
        raise HTTPException(status_code=400, detail="At least one scenario_id is required")

    result = await session.execute(
        select(ScenarioCompanyImpact)
        .where(
            and_(
                ScenarioCompanyImpact.entity_id == entity_id,
                ScenarioCompanyImpact.scenario_id.in_(ids),
            )
        )
        .order_by(ScenarioCompanyImpact.created_at.desc().nulls_last())
    )
    rows = result.scalars().all()
    return [_impact_response(r) for r in rows]


# ── Parametric routes ───────────────────────────────────────────────


@router.get(
    "/research/themes/{entity_id}",
    response_model=list[ThemeScoreResponse],
)
async def get_entity_theme_exposures(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get macro theme exposure scores for an entity."""

    async def _q():
        return (await session.execute(
            select(MacroThemeScore)
            .where(MacroThemeScore.entity_id == entity_id)
            .order_by(MacroThemeScore.as_of_date.desc())
        )).scalars().all()

    rows = await _q()
    if not rows:
        entity = (
            await session.execute(select(Entity).where(Entity.entity_id == entity_id))
        ).scalar_one_or_none()
        if entity is not None and await _compute_theme_scores_for_entity(session, entity_id, entity.gics_sector):
            await session.commit()
            rows = await _q()

    return [_theme_score_response(r) for r in rows]


@router.get(
    "/research/themes/{entity_id}/history",
    response_model=list[ThemeScoreResponse],
)
async def get_theme_score_history(
    entity_id: uuid.UUID,
    theme: str = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
):
    """Get historical theme scores for an entity."""
    stmt = select(MacroThemeScore).where(MacroThemeScore.entity_id == entity_id)
    if theme:
        stmt = stmt.where(MacroThemeScore.theme == theme)
    stmt = stmt.order_by(MacroThemeScore.as_of_date.desc()).limit(limit)

    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [_theme_score_response(r) for r in rows]


async def _entity_names(session: AsyncSession, entity_ids: set[uuid.UUID]) -> dict:
    if not entity_ids:
        return {}
    result = await session.execute(
        select(Entity.entity_id, Entity.legal_name).where(Entity.entity_id.in_(entity_ids))
    )
    return {eid: name for eid, name in result.all()}


def _direction_bucket(direction: str | None) -> str:
    d = (direction or "").upper()
    if "POS" in d or "BULL" in d:
        return "bullish"
    if "NEG" in d or "BEAR" in d:
        return "bearish"
    return "neutral"


@router.get(
    "/research/themes/summary/{theme}",
    response_model=ThemeSummaryResponse,
)
async def get_theme_summary(
    theme: str,
    session: AsyncSession = Depends(get_session),
):
    """Aggregate exposure stats for one theme label across all scored
    entities. There is no fixed theme catalog -- any label that has scored
    rows works; an unrecognized label just returns entity_count=0 rather
    than a fabricated 404 (macro themes aren't user-created resources, they're
    labels the scoring engine assigns)."""
    result = await session.execute(
        select(MacroThemeScore).where(MacroThemeScore.theme == theme)
    )
    rows = result.scalars().all()
    if not rows:
        return ThemeSummaryResponse(theme=theme, entity_count=0)

    scores = [float(r.exposure_score) for r in rows if r.exposure_score is not None]
    buckets = {"bullish": 0, "bearish": 0, "neutral": 0}
    for r in rows:
        buckets[_direction_bucket(r.sensitivity_direction)] += 1

    return ThemeSummaryResponse(
        theme=theme,
        entity_count=len({r.entity_id for r in rows}),
        avg_exposure_score=round(sum(scores) / len(scores), 2) if scores else None,
        bullish_count=buckets["bullish"],
        bearish_count=buckets["bearish"],
        neutral_count=buckets["neutral"],
        latest_as_of_date=max(r.as_of_date for r in rows),
    )


@router.get(
    "/research/themes/{theme}/securities",
    response_model=list[ThemeScreenResponse],
)
async def get_theme_securities(
    theme: str,
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """List entities scored against a theme, most-exposed first. Same query
    screen_by_theme runs, exposed as a plain GET for a theme-detail page
    (no filter body needed for the common "who's exposed to this theme" case)."""
    result = await session.execute(
        select(MacroThemeScore)
        .where(MacroThemeScore.theme == theme)
        .order_by(MacroThemeScore.exposure_score.desc().nulls_last())
        .limit(limit)
    )
    rows = result.scalars().all()
    names = await _entity_names(session, {r.entity_id for r in rows})
    return [
        ThemeScreenResponse(
            entity_id=r.entity_id,
            entity_name=names.get(r.entity_id),
            theme=r.theme,
            exposure_score=_float(r.exposure_score),
            sensitivity_direction=r.sensitivity_direction,
            quantified_exposure=r.quantified_exposure,
            as_of_date=r.as_of_date,
        )
        for r in rows
    ]


@router.post(
    "/research/themes/screen",
    response_model=list[ThemeScreenResponse],
)
async def screen_by_theme(
    body: ThemeScreenRequest,
    session: AsyncSession = Depends(get_session),
):
    """Screen entities by macro theme exposure."""
    stmt = select(MacroThemeScore).where(MacroThemeScore.theme == body.theme)
    if body.min_exposure is not None:
        stmt = stmt.where(MacroThemeScore.exposure_score >= body.min_exposure)
    if body.max_exposure is not None:
        stmt = stmt.where(MacroThemeScore.exposure_score <= body.max_exposure)
    if body.sensitivity_direction:
        stmt = stmt.where(MacroThemeScore.sensitivity_direction == body.sensitivity_direction)
    stmt = stmt.order_by(MacroThemeScore.exposure_score.desc().nulls_last()).limit(body.limit)

    result = await session.execute(stmt)
    rows = result.scalars().all()
    names = await _entity_names(session, {r.entity_id for r in rows})

    return [
        ThemeScreenResponse(
            entity_id=r.entity_id,
            entity_name=names.get(r.entity_id),
            theme=r.theme,
            exposure_score=_float(r.exposure_score),
            sensitivity_direction=r.sensitivity_direction,
            quantified_exposure=r.quantified_exposure,
            as_of_date=r.as_of_date,
        )
        for r in rows
    ]


@router.get(
    "/research/scenarios/{scenario_id}",
    response_model=ScenarioResponse,
)
async def get_scenario_detail(
    scenario_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get detailed information about a scenario."""
    result = await session.execute(
        select(MacroScenario).where(MacroScenario.id == scenario_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return _scenario_response(row)


async def _load_scenario_company(session: AsyncSession, entity_id: uuid.UUID, gics_sector: str | None) -> dict | None:
    """Assemble the {base_eps, sector, current_price, ...} inputs
    macro_scenario_engine.run_company_scenario() needs, from real Pillar 1/2
    data. Returns None when there isn't enough data to compute a scenario.
    """
    fp = (
        await session.execute(
            select(FinancialPeriod)
            .where(FinancialPeriod.entity_id == entity_id)
            .order_by(FinancialPeriod.period_end_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if not fp or not fp.income_statement or fp.income_statement.diluted_eps is None:
        return None
    base_eps = float(fp.income_statement.diluted_eps)

    base_margin_bps = None
    inc = fp.income_statement
    if inc.operating_income is not None and inc.total_revenue:
        base_margin_bps = float(inc.operating_income) / float(inc.total_revenue) * 10000

    sec_row = (
        await session.execute(
            select(Security.security_id, Security.security_type, Security.status)
            .where(Security.issuer_entity_id == entity_id, Security.asset_class == "EQUITY")
        )
    ).all()
    if not sec_row:
        return None
    sec_row.sort(key=lambda r: (r[2] != "ACTIVE", r[1] != "COMMON_STOCK"))
    security_id = sec_row[0][0]

    price_row = (
        await session.execute(
            select(EODPrice.close)
            .where(EODPrice.security_id == security_id, EODPrice.close.isnot(None))
            .order_by(EODPrice.price_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if price_row is None:
        return None

    return {
        "entity_id": entity_id,
        "sector": _GICS_SECTOR_NAMES.get(gics_sector, ""),
        "base_eps": base_eps,
        "current_price": float(price_row),
        "base_margin_bps": base_margin_bps if base_margin_bps is not None else 1500.0,
    }


_THEME_SHOCK_LABELS = {
    "GDP_GROWTH": "+2pp GDP growth",
    "INFLATION": "+2pp inflation",
    "RATE_HIKES": "+100bp Fed funds rate",
    "OIL_PRICES": "+25% oil price",
}


def _quantify_theme_exposure(theme: str, sector: str, exp: dict, base_eps: float | None) -> str:
    line = f"{_THEME_SHOCK_LABELS.get(theme, theme)} -> {sector} sector EPS {exp['exposure_score']:+.2f}%"
    if exp.get("scenario_eps") is not None and base_eps:
        line += f" (${base_eps:.2f} -> ${exp['scenario_eps']:.2f})"
    return line


async def _compute_theme_scores_for_entity(
    session: AsyncSession, entity_id: uuid.UUID, gics_sector: str | None
) -> bool:
    """Populate real theme-exposure scores for one entity from its GICS
    sector's sensitivity to 4 standardized macro shocks (GDP growth,
    inflation, rate hikes, oil prices), reusing
    macro_scenario_engine.compute_theme_exposures() (built on the same
    tested SECTOR_SENSITIVITIES/estimate_eps_impact() the scenario-run
    endpoint already uses). ``macro_theme_scores`` had zero producers
    anywhere before this. Returns False when the entity has no GICS sector
    to score against."""
    sector = _GICS_SECTOR_NAMES.get(gics_sector)
    if not sector:
        return False

    company = await _load_scenario_company(session, entity_id, gics_sector)
    base_eps = company["base_eps"] if company else None

    exposures = macro_scenario_engine.compute_theme_exposures(sector, base_eps)
    today = date.today()
    for theme, exp in exposures.items():
        existing = (
            await session.execute(
                select(MacroThemeScore).where(
                    MacroThemeScore.entity_id == entity_id,
                    MacroThemeScore.theme == theme,
                    MacroThemeScore.as_of_date == today,
                )
            )
        ).scalar_one_or_none()
        values = dict(
            exposure_score=exp["exposure_score"],
            sensitivity_direction=exp["direction"],
            evidence={
                "sector": sector, "shock": exp["shock"],
                "base_eps": base_eps, "scenario_eps": exp.get("scenario_eps"),
            },
            quantified_exposure=_quantify_theme_exposure(theme, sector, exp, base_eps),
        )
        if existing is not None:
            for k, v in values.items():
                setattr(existing, k, v)
        else:
            session.add(MacroThemeScore(id=uuid.uuid4(), entity_id=entity_id, as_of_date=today, **values))
    return True


@router.post(
    "/research/scenarios/{scenario_id}/run",
    response_model=list[ScenarioImpactResponse],
)
async def run_scenario(
    scenario_id: uuid.UUID,
    entity_ids: str | None = Query(
        default=None,
        description="Comma-separated entity UUIDs to run the scenario for. "
        "If omitted, runs for up to 50 entities with sufficient data.",
    ),
    session: AsyncSession = Depends(get_session),
):
    """Run a macro scenario and return company impacts.

    Actually computes EPS/margin/rating/price-target impact via
    macro_scenario_engine.run_company_scenario() (a real, unit-tested engine
    that previously had no production caller) and persists the results —
    this endpoint used to just echo back whatever was already cached.
    """
    sc_result = await session.execute(
        select(MacroScenario).where(MacroScenario.id == scenario_id)
    )
    sc = sc_result.scalar_one_or_none()
    if not sc:
        raise HTTPException(status_code=404, detail="Scenario not found")

    scenario_dict = {
        "scenario_name": sc.scenario_name,
        "assumptions": sc.assumptions or {},
    }

    entity_stmt = select(Entity.entity_id, Entity.gics_sector)
    if entity_ids:
        ids = [uuid.UUID(s.strip()) for s in entity_ids.split(",") if s.strip()]
        entity_stmt = entity_stmt.where(Entity.entity_id.in_(ids))
    else:
        entity_stmt = entity_stmt.where(Entity.gics_sector.isnot(None)).limit(_SCENARIO_MAX_ENTITIES)

    entities = (await session.execute(entity_stmt)).all()

    computed: list[ScenarioCompanyImpact] = []
    for entity_id, gics_sector in entities:
        company = await _load_scenario_company(session, entity_id, gics_sector)
        if company is None:
            continue

        impact = macro_scenario_engine.run_company_scenario(company, scenario_dict)
        narrative = macro_scenario_engine.generate_scenario_narrative_template(impact)

        existing = (
            await session.execute(
                select(ScenarioCompanyImpact).where(
                    ScenarioCompanyImpact.scenario_id == scenario_id,
                    ScenarioCompanyImpact.entity_id == entity_id,
                )
            )
        ).scalar_one_or_none()

        if existing:
            existing.base_eps = impact["base_eps"]
            existing.scenario_eps = impact["scenario_eps"]
            existing.eps_change_pct = impact["eps_change_pct"]
            existing.margin_impact_bps = impact["margin_impact_bps"]
            existing.rating_implication = impact["rating_implication"]
            existing.price_target_scenario = impact["price_target_scenario"]
            existing.narrative = narrative
            computed.append(existing)
        else:
            row = ScenarioCompanyImpact(
                id=uuid.uuid4(),
                scenario_id=scenario_id,
                entity_id=entity_id,
                base_eps=impact["base_eps"],
                scenario_eps=impact["scenario_eps"],
                eps_change_pct=impact["eps_change_pct"],
                margin_impact_bps=impact["margin_impact_bps"],
                rating_implication=impact["rating_implication"],
                price_target_scenario=impact["price_target_scenario"],
                narrative=narrative,
            )
            session.add(row)
            computed.append(row)

    if computed:
        await session.commit()

    # Entities we couldn't (re)compute this pass (missing sector/EPS/price
    # data) keep whatever was already cached, rather than losing previously
    # computed impacts just because live data wasn't available this time.
    already_covered = {r.entity_id for r in computed}
    stale_stmt = select(ScenarioCompanyImpact).where(ScenarioCompanyImpact.scenario_id == scenario_id)
    if already_covered:
        stale_stmt = stale_stmt.where(ScenarioCompanyImpact.entity_id.notin_(already_covered))
    stale_result = await session.execute(stale_stmt)
    all_impacts = computed + list(stale_result.scalars().all())

    all_impacts.sort(key=lambda r: r.eps_change_pct if r.eps_change_pct is not None else 0)
    return [_impact_response(r) for r in all_impacts]


@router.get(
    "/research/scenarios/{scenario_id}/results",
    response_model=list[ScenarioImpactResponse],
)
async def get_scenario_results(
    scenario_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Get cached results from a previously run scenario."""
    result = await session.execute(
        select(ScenarioCompanyImpact)
        .where(ScenarioCompanyImpact.scenario_id == scenario_id)
        .order_by(ScenarioCompanyImpact.created_at.desc().nulls_last())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [_impact_response(r) for r in rows]
