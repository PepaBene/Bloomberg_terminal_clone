"""Global Intelligence API endpoints (Pillar 3 Phase 3B)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.engines import commodity_intelligence, global_macro as global_macro_engine
from src.models.entity import Entity
from src.models.macro import MacroIndicator, MacroValue
from src.models.country_risk import (
    CompanyCountryExposure,
    CountryProfile,
    CountryRiskScore,
    GeopoliticalEvent,
)
from src.models.global_macro import (
    CentralBankDecision,
    CentralBankProfile,
    GlobalMacroIndicator,
)
from src.models.commodity_intelligence import (
    CommodityCompanyExposure,
    CommodityPrice,
    CommodityProfile,
)
from src.models.political_intelligence import (
    LegislativeBill,
    RegulatoryAction,
    SanctionsEntry,
)
from src.schemas.country_risk import (
    CompanyExposureResponse,
    CountryProfileResponse,
    CountryRiskRankingResponse,
    CountryRiskScoreResponse,
    GeopoliticalEventResponse,
)
from src.schemas.global_macro import (
    CentralBankDecisionResponse,
    CentralBankResponse,
    GlobalMacroDashboardResponse,
    InflationComparisonResponse,
    RecessionProbabilityResponse,
)
from src.schemas.commodity_intelligence import (
    CommodityDashboardResponse,
    CommodityExposureResponse,
    CommodityPriceResponse,
    CommodityProfileResponse,
    CommodityScenarioRequest,
    CommodityScenarioResponse,
)
from src.schemas.political_intelligence import (
    LegislativeBillResponse,
    RegulatoryActionResponse,
    SanctionsEntryResponse,
)

router = APIRouter(tags=["Global Intelligence"])


async def _latest_macro(session: AsyncSession, code: str) -> MacroValue | None:
    """Latest FRED observation for a series code."""
    ind = (
        await session.execute(select(MacroIndicator).where(MacroIndicator.indicator_code == code))
    ).scalar_one_or_none()
    if ind is None:
        return None
    return (
        await session.execute(
            select(MacroValue)
            .where(MacroValue.indicator_id == ind.indicator_id)
            .order_by(MacroValue.observation_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _ensure_us_macro_indicators(session: AsyncSession) -> bool:
    """Populate US GlobalMacroIndicator rows for today from real FRED data
    (macro_values), computing recession probability via the global_macro
    engine. Returns True if any rows now exist. This is the producer the
    /global/macro/* endpoints were missing — global_macro_indicators had no
    writer, and the compute engines had no caller. US-only (FRED)."""
    today = date.today()
    have = (
        await session.execute(
            select(func.count()).select_from(GlobalMacroIndicator)
            .where(GlobalMacroIndicator.country_code == "US",
                   GlobalMacroIndicator.release_date == today)
        )
    ).scalar() or 0
    if have:
        return True

    rows_written = 0

    async def _put(indicator_type: str, value, prior=None, period="LATEST"):
        nonlocal rows_written
        if value is None:
            return
        session.add(GlobalMacroIndicator(
            id=uuid.uuid4(), country_code="US", indicator_type=indicator_type,
            period_label=period, value=value,
            prior_value=prior, source="FRED", release_date=today,
        ))
        rows_written += 1

    # Inflation (CPI YoY %).
    cpi = await _latest_macro(session, "CPIAUCSL")
    if cpi is not None and cpi.value_yoy_percent is not None:
        await _put("CPI", float(cpi.value_yoy_percent))

    # Real GDP growth (annualized QoQ, fall back to YoY).
    gdp = await _latest_macro(session, "GDPC1")
    if gdp is not None:
        g = gdp.value_qoq_annualized if gdp.value_qoq_annualized is not None else gdp.value_yoy_percent
        if g is not None:
            await _put("GDP_GROWTH", float(g))

    # Recession probability via the engine (yield-curve spread + unemployment).
    t10y2y = await _latest_macro(session, "T10Y2Y")
    unrate = await _latest_macro(session, "UNRATE")
    if t10y2y is not None and t10y2y.value is not None:
        unemp_change = float(unrate.value_yoy) if unrate is not None and unrate.value_yoy is not None else None
        rec = global_macro_engine.compute_recession_probability(
            yield_curve_spread=float(t10y2y.value),
            pmi=50.0,  # No PMI series in the FRED seed set — neutral placeholder.
            credit_spreads_bps=400.0,
            unemployment_change=unemp_change,
        )
        await _put("RECESSION_PROB", round(rec.probability, 2))

    if rows_written:
        await session.commit()
    return rows_written > 0


# ══════════════════════════════════════════════════════════════════════
# Country Risk
# ══════════════════════════════════════════════════════════════════════

# ── Static routes (MUST come before parametric) ──────────────────────


@router.get(
    "/global/countries",
    response_model=list[CountryProfileResponse],
)
async def list_countries(
    session: AsyncSession = Depends(get_session),
    region: str | None = Query(None, description="Filter by region"),
    is_g20: bool | None = Query(None, description="Filter G20 members"),
):
    """List all tracked countries."""
    stmt = select(CountryProfile).order_by(CountryProfile.country_name)
    if region:
        stmt = stmt.where(CountryProfile.region == region)
    if is_g20 is not None:
        stmt = stmt.where(CountryProfile.is_g20 == is_g20)
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        CountryProfileResponse(
            id=r.id,
            country_code=r.country_code,
            country_name=r.country_name,
            region=r.region,
            income_group=r.income_group,
            is_g20=r.is_g20,
            is_eu=r.is_eu,
            population=float(r.population) if r.population is not None else None,
            gdp_usd=float(r.gdp_usd) if r.gdp_usd is not None else None,
        )
        for r in rows
    ]


@router.get(
    "/global/countries/risk-ranking",
    response_model=list[CountryRiskRankingResponse],
)
async def get_country_risk_ranking(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(20, ge=1, le=200, description="Number of results"),
):
    """Get countries ranked by composite risk score (highest risk first)."""
    # Get the latest risk score per country via subquery
    latest_sub = (
        select(
            CountryRiskScore.country_code,
            func.max(CountryRiskScore.as_of_date).label("max_date"),
        )
        .group_by(CountryRiskScore.country_code)
        .subquery()
    )
    stmt = (
        select(CountryRiskScore, CountryProfile.country_name)
        .join(
            latest_sub,
            (CountryRiskScore.country_code == latest_sub.c.country_code)
            & (CountryRiskScore.as_of_date == latest_sub.c.max_date),
        )
        .outerjoin(
            CountryProfile,
            CountryRiskScore.country_code == CountryProfile.country_code,
        )
        .order_by(CountryRiskScore.composite_risk_score.desc().nulls_last())
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = result.all()
    return [
        CountryRiskRankingResponse(
            country_code=r[0].country_code,
            country_name=r[1] or r[0].country_code,
            composite_risk_score=float(r[0].composite_risk_score) if r[0].composite_risk_score is not None else None,
            risk_classification=r[0].risk_classification,
            rank=idx + 1,
        )
        for idx, r in enumerate(rows)
    ]


# ── Parametric country routes ────────────────────────────────────────


@router.get(
    "/global/countries/{country_code}",
    response_model=CountryProfileResponse,
)
async def get_country_profile(
    country_code: str,
    session: AsyncSession = Depends(get_session),
):
    """Get country profile details."""
    result = await session.execute(
        select(CountryProfile).where(CountryProfile.country_code == country_code.upper())
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Country not found")
    return CountryProfileResponse(
        id=r.id,
        country_code=r.country_code,
        country_name=r.country_name,
        region=r.region,
        income_group=r.income_group,
        is_g20=r.is_g20,
        is_eu=r.is_eu,
        population=float(r.population) if r.population is not None else None,
        gdp_usd=float(r.gdp_usd) if r.gdp_usd is not None else None,
    )


@router.get(
    "/global/countries/{country_code}/risk",
    response_model=list[CountryRiskScoreResponse],
)
async def get_country_risk(
    country_code: str,
    session: AsyncSession = Depends(get_session),
    limit: int = Query(10, ge=1, le=100),
):
    """Get risk scores and history for a country."""
    result = await session.execute(
        select(CountryRiskScore)
        .where(CountryRiskScore.country_code == country_code.upper())
        .order_by(CountryRiskScore.as_of_date.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        CountryRiskScoreResponse(
            id=r.id,
            country_code=r.country_code,
            as_of_date=r.as_of_date,
            political_risk_score=float(r.political_risk_score) if r.political_risk_score is not None else None,
            economic_risk_score=float(r.economic_risk_score) if r.economic_risk_score is not None else None,
            sanctions_risk_score=float(r.sanctions_risk_score) if r.sanctions_risk_score is not None else None,
            composite_risk_score=float(r.composite_risk_score) if r.composite_risk_score is not None else None,
            risk_classification=r.risk_classification,
            risk_trend=r.risk_trend,
            political_components=r.political_components,
            economic_components=r.economic_components,
            sanctions_components=r.sanctions_components,
        )
        for r in rows
    ]


@router.get(
    "/global/countries/{country_code}/exposed-companies",
    response_model=list[CompanyExposureResponse],
)
async def get_country_exposed_companies(
    country_code: str,
    session: AsyncSession = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
):
    """Get US companies with exposure to a given country."""
    result = await session.execute(
        select(CompanyCountryExposure)
        .where(CompanyCountryExposure.country_code == country_code.upper())
        .order_by(CompanyCountryExposure.exposure_pct.desc().nulls_last())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        CompanyExposureResponse(
            id=r.id,
            entity_id=r.entity_id,
            country_code=r.country_code,
            exposure_type=r.exposure_type,
            exposure_pct=float(r.exposure_pct) if r.exposure_pct is not None else None,
            source=r.source,
            as_of_date=r.as_of_date,
        )
        for r in rows
    ]


@router.get(
    "/global/countries/{country_code}/events",
    response_model=list[GeopoliticalEventResponse],
)
async def get_country_events(
    country_code: str,
    session: AsyncSession = Depends(get_session),
):
    """Get active geopolitical events for a country."""
    cc = country_code.upper()
    # On PostgreSQL push the filter to SQL: the JSONB '?' operator (exposed
    # via has_key()) returns true when the string exists as an array
    # element *or* as an object key, matching the semantics we need for
    # countries_involved. SQLite (used in tests) lacks that operator, so
    # fall back to in-memory filtering on dialect mismatch — still bounded
    # to the most recent rows.
    dialect = session.bind.dialect.name if session.bind else ""
    if dialect == "postgresql":
        result = await session.execute(
            select(GeopoliticalEvent)
            .where(GeopoliticalEvent.countries_involved.has_key(cc))
            .order_by(GeopoliticalEvent.start_date.desc().nulls_last())
            .limit(200)
        )
        rows = list(result.scalars().all())
    else:
        result = await session.execute(
            select(GeopoliticalEvent)
            .order_by(GeopoliticalEvent.start_date.desc().nulls_last())
            .limit(500)
        )
        rows = []
        for r in result.scalars():
            involved = r.countries_involved or []
            if isinstance(involved, list) and cc in involved:
                rows.append(r)
            elif isinstance(involved, dict) and cc in involved:
                rows.append(r)
    return [
        GeopoliticalEventResponse(
            id=r.id,
            event_type=r.event_type,
            title=r.title,
            description=r.description,
            countries_involved=r.countries_involved,
            severity=r.severity,
            status=r.status,
            start_date=r.start_date,
            commodity_impact=r.commodity_impact,
            sector_impact=r.sector_impact,
            affected_entity_ids=r.affected_entity_ids,
        )
        for r in rows
    ]


# ══════════════════════════════════════════════════════════════════════
# Geopolitical Events
# ══════════════════════════════════════════════════════════════════════


@router.get(
    "/global/events/geopolitical",
    response_model=list[GeopoliticalEventResponse],
)
async def list_geopolitical_events(
    session: AsyncSession = Depends(get_session),
    severity: str | None = Query(None, description="Filter by severity"),
    status: str | None = Query(None, description="Filter by status"),
):
    """List all active geopolitical events."""
    stmt = select(GeopoliticalEvent).order_by(GeopoliticalEvent.start_date.desc().nulls_last())
    if severity:
        stmt = stmt.where(GeopoliticalEvent.severity == severity.upper())
    if status:
        stmt = stmt.where(GeopoliticalEvent.status == status.upper())
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        GeopoliticalEventResponse(
            id=r.id,
            event_type=r.event_type,
            title=r.title,
            description=r.description,
            countries_involved=r.countries_involved,
            severity=r.severity,
            status=r.status,
            start_date=r.start_date,
            commodity_impact=r.commodity_impact,
            sector_impact=r.sector_impact,
            affected_entity_ids=r.affected_entity_ids,
        )
        for r in rows
    ]


@router.get(
    "/global/events/geopolitical/{event_id}",
    response_model=GeopoliticalEventResponse,
)
async def get_geopolitical_event(
    event_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get detail for a single geopolitical event."""
    result = await session.execute(
        select(GeopoliticalEvent).where(GeopoliticalEvent.id == event_id)
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Geopolitical event not found")
    return GeopoliticalEventResponse(
        id=r.id,
        event_type=r.event_type,
        title=r.title,
        description=r.description,
        countries_involved=r.countries_involved,
        severity=r.severity,
        status=r.status,
        start_date=r.start_date,
        commodity_impact=r.commodity_impact,
        sector_impact=r.sector_impact,
        affected_entity_ids=r.affected_entity_ids,
    )


@router.get(
    "/global/scenarios",
    response_model=list[dict],
)
async def list_scenarios(
    session: AsyncSession = Depends(get_session),
):
    """List pre-built geopolitical scenarios."""
    # Scenarios derived from high-severity events
    result = await session.execute(
        select(GeopoliticalEvent)
        .where(GeopoliticalEvent.severity.in_(["HIGH", "CRITICAL"]))
        .order_by(GeopoliticalEvent.start_date.desc().nulls_last())
    )
    rows = result.scalars().all()
    return [
        {
            "scenario_id": str(r.id),
            "title": r.title,
            "event_type": r.event_type,
            "severity": r.severity,
            "countries_involved": r.countries_involved,
            "commodity_impact": r.commodity_impact,
            "sector_impact": r.sector_impact,
        }
        for r in rows
    ]


@router.post(
    "/global/scenarios/{scenario_id}/impact",
    response_model=dict,
)
async def run_scenario_impact(
    scenario_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Run impact analysis for a pre-built scenario."""
    result = await session.execute(
        select(GeopoliticalEvent).where(GeopoliticalEvent.id == scenario_id)
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return {
        "scenario_id": str(r.id),
        "title": r.title,
        "commodity_impact": r.commodity_impact,
        "sector_impact": r.sector_impact,
        "affected_entity_ids": r.affected_entity_ids,
    }


# ══════════════════════════════════════════════════════════════════════
# Global Macro
# ══════════════════════════════════════════════════════════════════════

# ── Static macro routes ──────────────────────────────────────────────


@router.get(
    "/global/macro/dashboard",
    response_model=list[GlobalMacroDashboardResponse],
)
async def get_macro_dashboard(
    session: AsyncSession = Depends(get_session),
):
    """G20 macro overview dashboard — latest indicator per country."""
    await _ensure_us_macro_indicators(session)
    # Get the latest indicator per country
    latest_sub = (
        select(
            GlobalMacroIndicator.country_code,
            func.max(GlobalMacroIndicator.release_date).label("max_date"),
        )
        .group_by(GlobalMacroIndicator.country_code)
        .subquery()
    )
    stmt = (
        select(GlobalMacroIndicator)
        .join(
            latest_sub,
            (GlobalMacroIndicator.country_code == latest_sub.c.country_code)
            & (GlobalMacroIndicator.release_date == latest_sub.c.max_date),
        )
        .order_by(GlobalMacroIndicator.country_code)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        GlobalMacroDashboardResponse(
            country_code=r.country_code,
            indicator_type=r.indicator_type,
            period_label=r.period_label,
            value=float(r.value) if r.value is not None else None,
            prior_value=float(r.prior_value) if r.prior_value is not None else None,
            forecast_value=float(r.forecast_value) if r.forecast_value is not None else None,
            source=r.source,
            release_date=r.release_date,
        )
        for r in rows
    ]


@router.get(
    "/global/macro/central-banks",
    response_model=list[CentralBankResponse],
)
async def list_central_banks(
    session: AsyncSession = Depends(get_session),
):
    """List all central bank profiles."""
    result = await session.execute(
        select(CentralBankProfile).order_by(CentralBankProfile.bank_code)
    )
    rows = result.scalars().all()
    return [
        CentralBankResponse(
            id=r.id,
            bank_code=r.bank_code,
            bank_name=r.bank_name,
            country_code=r.country_code,
            current_rate=float(r.current_rate) if r.current_rate is not None else None,
            policy_stance=r.policy_stance,
            next_meeting_date=r.next_meeting_date,
            forward_guidance_summary=r.forward_guidance_summary,
        )
        for r in rows
    ]


@router.get(
    "/global/macro/inflation",
    response_model=list[InflationComparisonResponse],
)
async def get_inflation_comparison(
    session: AsyncSession = Depends(get_session),
):
    """Global inflation comparison across countries."""
    await _ensure_us_macro_indicators(session)
    result = await session.execute(
        select(GlobalMacroIndicator)
        .where(GlobalMacroIndicator.indicator_type == "CPI")
        .order_by(GlobalMacroIndicator.release_date.desc().nulls_last())
    )
    rows = result.scalars().all()
    # Keep only latest per country
    seen: dict[str, GlobalMacroIndicator] = {}
    for r in rows:
        if r.country_code not in seen:
            seen[r.country_code] = r
    return [
        InflationComparisonResponse(
            country_code=r.country_code,
            value=float(r.value) if r.value is not None else None,
            prior_value=float(r.prior_value) if r.prior_value is not None else None,
            period_label=r.period_label,
            release_date=r.release_date,
        )
        for r in seen.values()
    ]


@router.get(
    "/global/macro/growth",
    response_model=list[GlobalMacroDashboardResponse],
)
async def get_growth_ranking(
    session: AsyncSession = Depends(get_session),
):
    """Global growth ranking by country (GDP growth)."""
    await _ensure_us_macro_indicators(session)
    result = await session.execute(
        select(GlobalMacroIndicator)
        .where(GlobalMacroIndicator.indicator_type == "GDP_GROWTH")
        .order_by(GlobalMacroIndicator.release_date.desc().nulls_last())
    )
    rows = result.scalars().all()
    seen: dict[str, GlobalMacroIndicator] = {}
    for r in rows:
        if r.country_code not in seen:
            seen[r.country_code] = r
    sorted_indicators = sorted(
        seen.values(),
        key=lambda x: float(x.value) if x.value is not None else 0,
        reverse=True,
    )
    return [
        GlobalMacroDashboardResponse(
            country_code=r.country_code,
            indicator_type=r.indicator_type,
            period_label=r.period_label,
            value=float(r.value) if r.value is not None else None,
            prior_value=float(r.prior_value) if r.prior_value is not None else None,
            forecast_value=float(r.forecast_value) if r.forecast_value is not None else None,
            source=r.source,
            release_date=r.release_date,
        )
        for r in sorted_indicators
    ]


@router.get(
    "/global/macro/recession-probability",
    response_model=list[RecessionProbabilityResponse],
)
async def get_recession_probability(
    session: AsyncSession = Depends(get_session),
):
    """Recession probability indicators by country."""
    await _ensure_us_macro_indicators(session)
    result = await session.execute(
        select(GlobalMacroIndicator)
        .where(GlobalMacroIndicator.indicator_type == "RECESSION_PROB")
        .order_by(GlobalMacroIndicator.release_date.desc().nulls_last())
    )
    rows = result.scalars().all()
    seen: dict[str, GlobalMacroIndicator] = {}
    for r in rows:
        if r.country_code not in seen:
            seen[r.country_code] = r
    return [
        RecessionProbabilityResponse(
            country_code=r.country_code,
            indicator_type=r.indicator_type,
            value=float(r.value) if r.value is not None else None,
            period_label=r.period_label,
            release_date=r.release_date,
        )
        for r in seen.values()
    ]


# ── Parametric macro routes ──────────────────────────────────────────


@router.get(
    "/global/macro/{country_code}/indicators",
    response_model=list[GlobalMacroDashboardResponse],
)
async def get_country_indicators(
    country_code: str,
    session: AsyncSession = Depends(get_session),
    indicator_type: str | None = Query(None, description="Filter by indicator type"),
):
    """Get key macro indicators for a country."""
    stmt = (
        select(GlobalMacroIndicator)
        .where(GlobalMacroIndicator.country_code == country_code.upper())
        .order_by(GlobalMacroIndicator.release_date.desc().nulls_last())
    )
    if indicator_type:
        stmt = stmt.where(GlobalMacroIndicator.indicator_type == indicator_type.upper())
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        GlobalMacroDashboardResponse(
            country_code=r.country_code,
            indicator_type=r.indicator_type,
            period_label=r.period_label,
            value=float(r.value) if r.value is not None else None,
            prior_value=float(r.prior_value) if r.prior_value is not None else None,
            forecast_value=float(r.forecast_value) if r.forecast_value is not None else None,
            source=r.source,
            release_date=r.release_date,
        )
        for r in rows
    ]


@router.get(
    "/global/macro/central-banks/{bank_code}",
    response_model=CentralBankResponse,
)
async def get_central_bank(
    bank_code: str,
    session: AsyncSession = Depends(get_session),
):
    """Get detail for a specific central bank."""
    result = await session.execute(
        select(CentralBankProfile).where(CentralBankProfile.bank_code == bank_code.upper())
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Central bank not found")
    return CentralBankResponse(
        id=r.id,
        bank_code=r.bank_code,
        bank_name=r.bank_name,
        country_code=r.country_code,
        current_rate=float(r.current_rate) if r.current_rate is not None else None,
        policy_stance=r.policy_stance,
        next_meeting_date=r.next_meeting_date,
        forward_guidance_summary=r.forward_guidance_summary,
    )


@router.get(
    "/global/macro/central-banks/{bank_code}/meetings",
    response_model=list[CentralBankDecisionResponse],
)
async def get_central_bank_meetings(
    bank_code: str,
    session: AsyncSession = Depends(get_session),
    limit: int = Query(10, ge=1, le=100),
):
    """Get meeting/decision history for a central bank."""
    result = await session.execute(
        select(CentralBankDecision)
        .where(CentralBankDecision.bank_code == bank_code.upper())
        .order_by(CentralBankDecision.decision_date.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        CentralBankDecisionResponse(
            id=r.id,
            bank_code=r.bank_code,
            decision_date=r.decision_date,
            rate_before=float(r.rate_before) if r.rate_before is not None else None,
            rate_after=float(r.rate_after) if r.rate_after is not None else None,
            rate_change_bps=r.rate_change_bps,
            decision_type=r.decision_type,
            was_surprise=r.was_surprise,
            vote_split=r.vote_split,
            statement_summary=r.statement_summary,
        )
        for r in rows
    ]


# ══════════════════════════════════════════════════════════════════════
# Commodities
# ══════════════════════════════════════════════════════════════════════

# ── Static commodity routes ──────────────────────────────────────────


@router.get(
    "/global/commodities",
    response_model=list[CommodityProfileResponse],
)
async def list_commodities(
    session: AsyncSession = Depends(get_session),
    category: str | None = Query(None, description="Filter by category"),
):
    """List all tracked commodities."""
    stmt = select(CommodityProfile).order_by(CommodityProfile.commodity_code)
    if category:
        stmt = stmt.where(CommodityProfile.category == category.upper())
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        CommodityProfileResponse(
            id=r.id,
            commodity_code=r.commodity_code,
            commodity_name=r.commodity_name,
            category=r.category,
            unit=r.unit,
            primary_source=r.primary_source,
        )
        for r in rows
    ]


@router.get(
    "/global/commodities/dashboard",
    response_model=list[CommodityDashboardResponse],
)
async def get_commodity_dashboard(
    session: AsyncSession = Depends(get_session),
):
    """Commodity overview dashboard with latest prices."""
    profiles_result = await session.execute(
        select(CommodityProfile).order_by(CommodityProfile.commodity_code)
    )
    profiles = profiles_result.scalars().all()

    dashboard = []
    for p in profiles:
        price_result = await session.execute(
            select(CommodityPrice)
            .where(CommodityPrice.commodity_code == p.commodity_code)
            .order_by(CommodityPrice.price_date.desc())
            .limit(1)
        )
        latest_price = price_result.scalar_one_or_none()
        dashboard.append(
            CommodityDashboardResponse(
                commodity_code=p.commodity_code,
                commodity_name=p.commodity_name,
                category=p.category,
                latest_price=float(latest_price.close_price) if latest_price and latest_price.close_price is not None else None,
                price_date=latest_price.price_date if latest_price else None,
            )
        )
    return dashboard


# ── Parametric commodity routes ──────────────────────────────────────


@router.get(
    "/global/commodities/{code}",
    response_model=CommodityProfileResponse,
)
async def get_commodity_profile(
    code: str,
    session: AsyncSession = Depends(get_session),
):
    """Get commodity profile detail."""
    result = await session.execute(
        select(CommodityProfile).where(CommodityProfile.commodity_code == code.upper())
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Commodity not found")
    return CommodityProfileResponse(
        id=r.id,
        commodity_code=r.commodity_code,
        commodity_name=r.commodity_name,
        category=r.category,
        unit=r.unit,
        primary_source=r.primary_source,
    )


@router.get(
    "/global/commodities/{code}/history",
    response_model=list[CommodityPriceResponse],
)
async def get_commodity_history(
    code: str,
    session: AsyncSession = Depends(get_session),
    limit: int = Query(30, ge=1, le=365),
):
    """Get historical prices for a commodity."""
    result = await session.execute(
        select(CommodityPrice)
        .where(CommodityPrice.commodity_code == code.upper())
        .order_by(CommodityPrice.price_date.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        CommodityPriceResponse(
            id=r.id,
            commodity_code=r.commodity_code,
            price_date=r.price_date,
            close_price=float(r.close_price) if r.close_price is not None else None,
            open_price=float(r.open_price) if r.open_price is not None else None,
            high_price=float(r.high_price) if r.high_price is not None else None,
            low_price=float(r.low_price) if r.low_price is not None else None,
            volume=float(r.volume) if r.volume is not None else None,
            source=r.source,
        )
        for r in rows
    ]


@router.get(
    "/global/commodities/{code}/companies",
    response_model=list[CommodityExposureResponse],
)
async def get_commodity_companies(
    code: str,
    session: AsyncSession = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
):
    """Get companies exposed to a commodity."""
    result = await session.execute(
        select(CommodityCompanyExposure)
        .where(CommodityCompanyExposure.commodity_code == code.upper())
        .order_by(CommodityCompanyExposure.sensitivity_score.desc().nulls_last())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        CommodityExposureResponse(
            id=r.id,
            commodity_code=r.commodity_code,
            entity_id=r.entity_id,
            exposure_type=r.exposure_type,
            exposure_description=r.exposure_description,
            sensitivity_score=float(r.sensitivity_score) if r.sensitivity_score is not None else None,
            historical_correlation=float(r.historical_correlation) if r.historical_correlation is not None else None,
            source=r.source,
        )
        for r in rows
    ]


@router.get(
    "/global/commodities/{code}/supply-demand",
    response_model=dict,
)
async def get_commodity_supply_demand(
    code: str,
    session: AsyncSession = Depends(get_session),
):
    """Get supply/demand balance for a commodity (derived from price trends)."""
    result = await session.execute(
        select(CommodityPrice)
        .where(CommodityPrice.commodity_code == code.upper())
        .order_by(CommodityPrice.price_date.desc())
        .limit(30)
    )
    rows = result.scalars().all()
    if not rows:
        raise HTTPException(status_code=404, detail="No price data found for commodity")
    prices = [float(r.close_price) for r in rows if r.close_price is not None]
    avg_price = sum(prices) / len(prices) if prices else None
    latest_price = prices[0] if prices else None
    trend = "NEUTRAL"
    if latest_price and avg_price:
        # PLACEHOLDER: Supply/demand signal is a naive heuristic based on
        # price deviation from the 30-day average.  A real implementation
        # should incorporate actual supply/demand data (e.g. EIA inventory
        # reports, USDA crop estimates, exchange warehouse stocks).
        if latest_price > avg_price * 1.05:
            trend = "DEFICIT"
        elif latest_price < avg_price * 0.95:
            trend = "SURPLUS"
    return {
        "commodity_code": code.upper(),
        "latest_price": latest_price,
        "avg_30d_price": round(avg_price, 4) if avg_price else None,
        "supply_demand_indicator": trend,
        "data_points": len(prices),
    }


@router.post(
    "/global/commodities/{code}/scenario",
    response_model=CommodityScenarioResponse,
)
async def run_commodity_scenario(
    code: str,
    body: CommodityScenarioRequest,
    session: AsyncSession = Depends(get_session),
):
    """Run a price scenario impact analysis for a commodity.

    Delegates to commodity_intelligence.run_commodity_scenario (a real,
    unit-tested engine with no prior production caller) so that PRODUCER vs
    CONSUMER exposure flips the impact direction and revenue exposure is
    weighted in — rather than the previous flat `price_change × score`
    linear product that ignored exposure direction entirely.
    """
    result = await session.execute(
        select(CommodityCompanyExposure)
        .where(CommodityCompanyExposure.commodity_code == code.upper())
        .order_by(CommodityCompanyExposure.sensitivity_score.desc().nulls_last())
    )
    rows = result.scalars().all()

    # Resolve entity names for the engine's most-impacted list.
    entity_ids = [r.entity_id for r in rows]
    names: dict = {}
    if entity_ids:
        name_rows = (
            await session.execute(
                select(Entity.entity_id, Entity.legal_name).where(Entity.entity_id.in_(entity_ids))
            )
        ).all()
        names = {eid: nm for eid, nm in name_rows}

    exposed_companies = [
        {
            "entity_id": str(r.entity_id),
            "entity_name": names.get(r.entity_id) or str(r.entity_id),
            "exposure_type": r.exposure_type or "INDIRECT",
            "sensitivity_score": float(r.sensitivity_score) if r.sensitivity_score is not None else 0.0,
            # revenue_exposure_pct isn't stored on this model; historical
            # correlation is the closest available proxy for how much of the
            # sensitivity translates to revenue.
            "revenue_exposure_pct": (
                abs(float(r.historical_correlation)) * 100
                if r.historical_correlation is not None
                else None
            ),
            "commodity_code": code.upper(),
        }
        for r in rows
    ]

    # The request carries a percentage change, not absolute prices — anchor
    # to a nominal 100 so the engine's price_change_pct matches the input.
    current_price = 100.0
    scenario_price = current_price * (1.0 + body.price_change_pct / 100.0)
    scenario = commodity_intelligence.run_commodity_scenario(
        current_price=current_price,
        scenario_price=scenario_price,
        exposed_companies=exposed_companies,
    )

    affected = [
        {
            "entity_id": imp.entity_id,
            "exposure_type": imp.exposure_type,
            "sensitivity_score": imp.sensitivity_score,
            "direction": imp.direction,
            "estimated_impact_pct": imp.estimated_revenue_impact_pct,
        }
        for imp in scenario.affected_companies
    ]
    return CommodityScenarioResponse(
        commodity_code=code.upper(),
        scenario_price_change_pct=body.price_change_pct,
        affected_companies=affected,
    )


# ══════════════════════════════════════════════════════════════════════
# Political & Policy
# ══════════════════════════════════════════════════════════════════════


@router.get(
    "/global/political/us/bills",
    response_model=list[LegislativeBillResponse],
)
async def list_us_bills(
    session: AsyncSession = Depends(get_session),
    status: str | None = Query(None, description="Filter by bill status"),
    limit: int = Query(50, ge=1, le=200),
):
    """List market-moving legislative bills."""
    stmt = select(LegislativeBill).order_by(LegislativeBill.last_action_date.desc().nulls_last()).limit(limit)
    if status:
        stmt = stmt.where(LegislativeBill.status == status.upper())
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        LegislativeBillResponse(
            id=r.id,
            bill_id=r.bill_id,
            title=r.title,
            summary=r.summary,
            bill_type=r.bill_type,
            status=r.status,
            sponsor_count=r.sponsor_count,
            passage_probability=float(r.passage_probability) if r.passage_probability is not None else None,
            affected_sectors=r.affected_sectors,
            affected_entity_ids=r.affected_entity_ids,
            introduced_date=r.introduced_date,
            last_action_date=r.last_action_date,
            source_url=r.source_url,
        )
        for r in rows
    ]


@router.get(
    "/global/political/us/bills/{bill_id}",
    response_model=LegislativeBillResponse,
)
async def get_us_bill(
    bill_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get detail for a specific legislative bill."""
    result = await session.execute(
        select(LegislativeBill).where(LegislativeBill.bill_id == bill_id)
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Bill not found")
    return LegislativeBillResponse(
        id=r.id,
        bill_id=r.bill_id,
        title=r.title,
        summary=r.summary,
        bill_type=r.bill_type,
        status=r.status,
        sponsor_count=r.sponsor_count,
        passage_probability=float(r.passage_probability) if r.passage_probability is not None else None,
        affected_sectors=r.affected_sectors,
        affected_entity_ids=r.affected_entity_ids,
        introduced_date=r.introduced_date,
        last_action_date=r.last_action_date,
        source_url=r.source_url,
    )


@router.get(
    "/global/political/us/regulations",
    response_model=list[RegulatoryActionResponse],
)
async def list_regulatory_actions(
    session: AsyncSession = Depends(get_session),
    agency: str | None = Query(None, description="Filter by agency"),
    limit: int = Query(50, ge=1, le=200),
):
    """List active regulatory rulemaking."""
    stmt = select(RegulatoryAction).order_by(RegulatoryAction.action_date.desc().nulls_last()).limit(limit)
    if agency:
        stmt = stmt.where(RegulatoryAction.agency == agency.upper())
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        RegulatoryActionResponse(
            id=r.id,
            agency=r.agency,
            action_type=r.action_type,
            title=r.title,
            description=r.description,
            affected_entity_ids=r.affected_entity_ids,
            affected_sectors=r.affected_sectors,
            severity=r.severity,
            financial_impact=float(r.financial_impact) if r.financial_impact is not None else None,
            action_date=r.action_date,
            source_url=r.source_url,
        )
        for r in rows
    ]


@router.get(
    "/global/political/us/enforcement",
    response_model=list[RegulatoryActionResponse],
)
async def list_enforcement_actions(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
):
    """List enforcement actions."""
    result = await session.execute(
        select(RegulatoryAction)
        .where(RegulatoryAction.action_type == "ENFORCEMENT")
        .order_by(RegulatoryAction.action_date.desc().nulls_last())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        RegulatoryActionResponse(
            id=r.id,
            agency=r.agency,
            action_type=r.action_type,
            title=r.title,
            description=r.description,
            affected_entity_ids=r.affected_entity_ids,
            affected_sectors=r.affected_sectors,
            severity=r.severity,
            financial_impact=float(r.financial_impact) if r.financial_impact is not None else None,
            action_date=r.action_date,
            source_url=r.source_url,
        )
        for r in rows
    ]


@router.get(
    "/global/political/elections",
    response_model=list[dict],
)
async def list_elections(
    session: AsyncSession = Depends(get_session),
):
    """List upcoming elections with market impact."""
    result = await session.execute(
        select(GeopoliticalEvent)
        .where(GeopoliticalEvent.event_type == "ELECTION")
        .order_by(GeopoliticalEvent.start_date.asc().nulls_last())
    )
    rows = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "title": r.title,
            "description": r.description,
            "countries_involved": r.countries_involved,
            "election_date": r.start_date.isoformat() if r.start_date else None,
            "severity": r.severity,
            "sector_impact": r.sector_impact,
        }
        for r in rows
    ]


@router.get(
    "/global/political/sanctions",
    response_model=list[SanctionsEntryResponse],
)
async def list_sanctions(
    session: AsyncSession = Depends(get_session),
    program: str | None = Query(None, description="Filter by sanctions program"),
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
):
    """List active sanctions entries."""
    stmt = select(SanctionsEntry).order_by(SanctionsEntry.effective_date.desc().nulls_last()).limit(limit)
    if program:
        stmt = stmt.where(SanctionsEntry.program == program.upper())
    if status:
        stmt = stmt.where(SanctionsEntry.status == status.upper())
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        SanctionsEntryResponse(
            id=r.id,
            program=r.program,
            country_code=r.country_code,
            target_name=r.target_name,
            target_type=r.target_type,
            status=r.status,
            effective_date=r.effective_date,
            description=r.description,
            affected_sectors=r.affected_sectors,
            source_url=r.source_url,
        )
        for r in rows
    ]


@router.get(
    "/global/political/sanctions/{country_code}",
    response_model=list[SanctionsEntryResponse],
)
async def get_sanctions_by_country(
    country_code: str,
    session: AsyncSession = Depends(get_session),
):
    """Get sanctions entries for a specific country."""
    result = await session.execute(
        select(SanctionsEntry)
        .where(SanctionsEntry.country_code == country_code.upper())
        .order_by(SanctionsEntry.effective_date.desc().nulls_last())
    )
    rows = result.scalars().all()
    return [
        SanctionsEntryResponse(
            id=r.id,
            program=r.program,
            country_code=r.country_code,
            target_name=r.target_name,
            target_type=r.target_type,
            status=r.status,
            effective_date=r.effective_date,
            description=r.description,
            affected_sectors=r.affected_sectors,
            source_url=r.source_url,
        )
        for r in rows
    ]
