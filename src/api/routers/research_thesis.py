"""Investment Thesis API endpoints (Pillar 3 Phase 4B)."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.llm_client import get_llm_client
from src.api.deps import get_session
from src.models.entity import Entity
from src.models.investment_thesis import InvestmentThesis, ThesisVersion
from src.schemas.investment_thesis_schema import (
    ThesisCreateRequest,
    ThesisDiffResponse,
    ThesisElevatorPitchResponse,
    ThesisListResponse,
    ThesisQualityReportResponse,
    ThesisResponse,
    ThesisSlideOutlineResponse,
    ThesisUpdateRequest,
    ThesisVersionResponse,
)

router = APIRouter(tags=["Research - Investment Thesis"])


def _float(val):
    return float(val) if val is not None else None


async def _get_entity(session: AsyncSession, entity_id: uuid.UUID) -> Entity:
    result = await session.execute(
        select(Entity).where(Entity.entity_id == entity_id)
    )
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


def _thesis_response(row: InvestmentThesis) -> ThesisResponse:
    return ThesisResponse(
        id=row.id,
        entity_id=row.entity_id,
        analyst_id=row.analyst_id,
        version=row.version,
        thesis_title=row.thesis_title,
        investment_horizon=row.investment_horizon,
        conviction_level=row.conviction_level,
        executive_summary=row.executive_summary,
        key_drivers=row.key_drivers,
        primary_risks=row.primary_risks,
        valuation_scenarios=row.valuation_scenarios,
        catalysts=row.catalysts,
        quality_metrics=row.quality_metrics,
        elevator_pitch=row.elevator_pitch,
        slide_outline=row.slide_outline,
        ai_enabled=row.ai_enabled,
        created_at=getattr(row, "created_at", None),
        updated_at=getattr(row, "updated_at", None),
    )


_QUALITY_FIELDS = (
    "thesis_title", "executive_summary", "key_drivers",
    "primary_risks", "valuation_scenarios", "catalysts",
)


def _compute_quality_metrics(body: ThesisCreateRequest) -> dict:
    """Pure completeness metric — how much of the thesis the analyst
    actually filled in, not an AI judgement of its quality."""
    filled = sum(1 for f in _QUALITY_FIELDS if getattr(body, f, None))
    return {
        "data_coverage": round(filled / len(_QUALITY_FIELDS), 2),
        "staleness_days": 0,
    }


def _parse_driver_items(key_drivers: dict | None) -> list[dict]:
    if not isinstance(key_drivers, dict):
        return []
    items = key_drivers.get("items")
    if not isinstance(items, list):
        return []
    return [i for i in items if isinstance(i, dict) and i.get("driver")]


def _parse_risk_items(primary_risks: dict | None) -> list[dict]:
    if not isinstance(primary_risks, dict):
        return []
    items = primary_risks.get("items")
    if not isinstance(items, list):
        return []
    return [i for i in items if isinstance(i, dict) and i.get("risk")]


def _parse_catalyst_items(catalysts: dict | None) -> list[dict]:
    if not isinstance(catalysts, dict):
        return []
    items = catalysts.get("items")
    if not isinstance(items, list):
        return []
    return [i for i in items if isinstance(i, dict) and i.get("description")]


def _parse_valuation(valuation_scenarios: dict | None) -> dict | None:
    """Only returns a value when current_price + all three scenarios' numeric
    fields are present and parse as floats -- partial valuation data isn't
    enough to render an honest slide."""
    if not isinstance(valuation_scenarios, dict):
        return None
    try:
        current_price = float(valuation_scenarios["current_price"])
        scenarios = {}
        for key in ("bull", "base", "bear"):
            s = valuation_scenarios[key]
            scenarios[key] = {
                "target_price": float(s["target_price"]),
                "implied_return": float(s["implied_return"]),
            }
        return {"current_price": current_price, **scenarios}
    except (KeyError, TypeError, ValueError):
        return None


def _build_slide_outline(
    thesis_title: str | None,
    conviction_level: str | None,
    investment_horizon: str | None,
    elevator_pitch: str | None,
    key_drivers: dict | None,
    primary_risks: dict | None,
    valuation_scenarios: dict | None,
    catalysts: dict | None,
) -> list[dict] | None:
    """Best-effort slide outline built from analyst-authored, unconstrained
    JSON fields.

    ``investment_thesis_engine.generate_slide_outline()`` expects a rigidly
    -typed dataclass (numeric bull/base/bear price targets, structured
    driver/risk/catalyst objects), but ``InvestmentThesis.key_drivers`` /
    ``primary_risks`` / ``valuation_scenarios`` / ``catalysts`` are
    unconstrained ``dict | None`` with no schema enforced anywhere else in
    the system. Rather than force that engine call (which would either
    crash on missing fields or require fabricating a schema), this reads a
    documented-but-not-enforced convention --
    ``key_drivers``/``primary_risks``/``catalysts`` as ``{"items": [...]}``,
    ``valuation_scenarios`` as ``{"current_price", "bull"/"base"/"bear":
    {"target_price", "implied_return"}}`` -- and builds each slide
    independently, skipping any section whose data isn't present in that
    shape instead of fabricating placeholder content. Returns None if the
    thesis has no title or no section could be built from real data.
    """
    if not thesis_title:
        return None

    drivers = _parse_driver_items(key_drivers)
    risks = _parse_risk_items(primary_risks)
    catalyst_items = _parse_catalyst_items(catalysts)
    valuation = _parse_valuation(valuation_scenarios)

    if not (drivers or risks or catalyst_items or valuation):
        return None

    slides = [{
        "slide_number": 1,
        "title": f"Investment Thesis: {thesis_title}",
        "bullet_points": [
            b for b in (
                f"Conviction: {conviction_level}" if conviction_level else None,
                f"Horizon: {investment_horizon}" if investment_horizon else None,
                elevator_pitch[:200] if elevator_pitch else None,
            ) if b
        ],
    }]

    if drivers:
        slides.append({
            "slide_number": len(slides) + 1,
            "title": "Key Investment Drivers",
            "bullet_points": [
                f"{d['driver']} ({d['current_impact']})" if d.get("current_impact") else d["driver"]
                for d in drivers[:4]
            ],
        })

    if valuation:
        slides.append({
            "slide_number": len(slides) + 1,
            "title": "Valuation Framework",
            "bullet_points": [
                f"Current: ${valuation['current_price']:.0f}",
                f"Bull: ${valuation['bull']['target_price']:.0f} ({valuation['bull']['implied_return']:+.0f}%)",
                f"Base: ${valuation['base']['target_price']:.0f} ({valuation['base']['implied_return']:+.0f}%)",
                f"Bear: ${valuation['bear']['target_price']:.0f} ({valuation['bear']['implied_return']:+.0f}%)",
            ],
        })

    if risks:
        slides.append({
            "slide_number": len(slides) + 1,
            "title": "Primary Risks",
            "bullet_points": [
                f"{r['risk']} (severity: {r['severity']})" if r.get("severity") else r["risk"]
                for r in risks[:4]
            ],
        })

    if catalyst_items:
        slides.append({
            "slide_number": len(slides) + 1,
            "title": "Catalysts & Timeline",
            "bullet_points": [
                f"{c['description']} — {c['timing']}" if c.get("timing") else c["description"]
                for c in catalyst_items[:4]
            ],
        })

    return slides


def _thesis_list_response(row: InvestmentThesis) -> ThesisListResponse:
    return ThesisListResponse(
        id=row.id,
        entity_id=row.entity_id,
        analyst_id=row.analyst_id,
        version=row.version,
        thesis_title=row.thesis_title,
        conviction_level=row.conviction_level,
        executive_summary=row.executive_summary,
        created_at=getattr(row, "created_at", None),
        updated_at=getattr(row, "updated_at", None),
    )


# ── Static routes (MUST come before parametric routes) ──────────────


@router.get(
    "/research/thesis/recent",
    response_model=list[ThesisListResponse],
)
async def get_recent_theses(
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Recently generated theses across all entities."""
    result = await session.execute(
        select(InvestmentThesis)
        .order_by(InvestmentThesis.created_at.desc().nulls_last())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [_thesis_list_response(row) for row in rows]


@router.get(
    "/research/thesis/quality-report",
    response_model=ThesisQualityReportResponse,
)
async def get_quality_report(
    session: AsyncSession = Depends(get_session),
):
    """Get overall thesis quality report."""
    total_result = await session.execute(
        select(func.count()).select_from(InvestmentThesis)
    )
    total = total_result.scalar() or 0

    conviction_result = await session.execute(
        select(InvestmentThesis.conviction_level, func.count())
        .group_by(InvestmentThesis.conviction_level)
    )
    by_conviction = {row[0] or "UNSET": row[1] for row in conviction_result.all()}

    horizon_result = await session.execute(
        select(InvestmentThesis.investment_horizon, func.count())
        .group_by(InvestmentThesis.investment_horizon)
    )
    by_horizon = {row[0] or "UNSET": row[1] for row in horizon_result.all()}

    return ThesisQualityReportResponse(
        total_theses=total,
        avg_quality_score=None,
        by_conviction=by_conviction,
        by_horizon=by_horizon,
    )


@router.get(
    "/research/thesis/by-conviction/{level}",
    response_model=list[ThesisListResponse],
)
async def get_theses_by_conviction(
    level: str,
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Get theses filtered by conviction level."""
    result = await session.execute(
        select(InvestmentThesis)
        .where(InvestmentThesis.conviction_level == level)
        .order_by(InvestmentThesis.created_at.desc().nulls_last())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [_thesis_list_response(row) for row in rows]


@router.get(
    "/research/thesis/by-analyst/{analyst_id}",
    response_model=list[ThesisListResponse],
)
async def get_theses_by_analyst(
    analyst_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Get theses written by a specific analyst."""
    result = await session.execute(
        select(InvestmentThesis)
        .where(InvestmentThesis.analyst_id == analyst_id)
        .order_by(InvestmentThesis.created_at.desc().nulls_last())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [_thesis_list_response(row) for row in rows]


# ── Entity-scoped routes ────────────────────────────────────────────


@router.post(
    "/research/thesis/{entity_id}",
    response_model=ThesisResponse,
)
async def generate_thesis(
    entity_id: uuid.UUID,
    body: ThesisCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Generate a new investment thesis for an entity.

    The thesis content itself is analyst-authored (from the request body —
    this is a research tool, not an auto-writer). When the LLM is
    configured, an elevator pitch is additionally generated from that
    content; quality_metrics is always computed (real completeness, not AI).
    """
    entity = await _get_entity(session, entity_id)

    # Determine next version
    version_result = await session.execute(
        select(func.max(InvestmentThesis.version))
        .where(InvestmentThesis.entity_id == entity_id)
    )
    max_version = version_result.scalar() or 0

    llm = get_llm_client()
    elevator_pitch = None
    if llm.enabled and (body.executive_summary or body.key_drivers):
        elevator_pitch = await llm.generate(
            system_prompt=(
                "You are a Bloomberg financial research AI assistant. Write a single "
                "sentence (under 400 characters) elevator pitch for an investment "
                "thesis, grounded only in the provided content."
            ),
            user_prompt=(
                f"Company: {entity.legal_name}\n"
                f"Thesis title: {body.thesis_title}\n"
                f"Executive summary: {body.executive_summary}\n"
                f"Key drivers: {body.key_drivers}\n"
                f"Conviction: {body.conviction_level}"
            ),
        )
        if elevator_pitch:
            elevator_pitch = elevator_pitch[:500]

    slide_outline = _build_slide_outline(
        body.thesis_title, body.conviction_level, body.investment_horizon,
        elevator_pitch, body.key_drivers, body.primary_risks,
        body.valuation_scenarios, body.catalysts,
    )

    thesis = InvestmentThesis(
        id=uuid.uuid4(),
        entity_id=entity_id,
        analyst_id=body.analyst_id,
        version=max_version + 1,
        thesis_title=body.thesis_title,
        investment_horizon=body.investment_horizon,
        conviction_level=body.conviction_level,
        executive_summary=body.executive_summary,
        key_drivers=body.key_drivers,
        primary_risks=body.primary_risks,
        valuation_scenarios=body.valuation_scenarios,
        catalysts=body.catalysts,
        quality_metrics=_compute_quality_metrics(body),
        elevator_pitch=elevator_pitch,
        slide_outline=slide_outline,
        ai_enabled=elevator_pitch is not None,
    )
    session.add(thesis)
    await session.commit()

    return _thesis_response(thesis)


@router.get(
    "/research/thesis/{entity_id}/latest",
    response_model=ThesisResponse,
)
async def get_latest_thesis(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get the latest investment thesis for an entity."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(InvestmentThesis)
        .where(InvestmentThesis.entity_id == entity_id)
        .order_by(InvestmentThesis.version.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="No thesis found for this entity")

    return _thesis_response(row)


@router.get(
    "/research/thesis/{entity_id}/versions",
    response_model=list[ThesisListResponse],
)
async def get_thesis_versions(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get version history of theses for an entity."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(InvestmentThesis)
        .where(InvestmentThesis.entity_id == entity_id)
        .order_by(InvestmentThesis.version.desc())
    )
    rows = result.scalars().all()
    return [_thesis_list_response(row) for row in rows]


# ── Thesis-ID-scoped routes ─────────────────────────────────────────


@router.get(
    "/research/thesis/{thesis_id}/detail",
    response_model=ThesisResponse,
)
async def get_thesis_detail(
    thesis_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get a specific thesis by ID (use /detail to avoid path collision)."""
    result = await session.execute(
        select(InvestmentThesis)
        .where(InvestmentThesis.id == thesis_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Thesis not found")

    return _thesis_response(row)


@router.put(
    "/research/thesis/{thesis_id}/update",
    response_model=ThesisResponse,
)
async def update_thesis(
    thesis_id: uuid.UUID,
    body: ThesisUpdateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Update an existing thesis and create a version snapshot."""
    result = await session.execute(
        select(InvestmentThesis)
        .where(InvestmentThesis.id == thesis_id)
    )
    thesis = result.scalar_one_or_none()
    if not thesis:
        raise HTTPException(status_code=404, detail="Thesis not found")

    # Compute conviction_change as numeric difference between old and new levels
    conviction_change = None
    if body.conviction_level is not None and thesis.conviction_level is not None:
        _conviction_scores = {"VERY_LOW": 1, "LOW": 2, "MEDIUM": 3, "HIGH": 4, "VERY_HIGH": 5}
        old_score = _conviction_scores.get(thesis.conviction_level)
        new_score = _conviction_scores.get(body.conviction_level)
        if old_score is not None and new_score is not None:
            conviction_change = Decimal(new_score - old_score)

    # Snapshot for diff
    version_snapshot = ThesisVersion(
        id=uuid.uuid4(),
        thesis_id=thesis.id,
        version=thesis.version,
        updated_drivers=body.key_drivers,
        analyst_note=body.analyst_note,
        conviction_change=conviction_change,
    )
    session.add(version_snapshot)

    # Apply updates
    if body.conviction_level is not None:
        thesis.conviction_level = body.conviction_level
    if body.executive_summary is not None:
        thesis.executive_summary = body.executive_summary
    if body.key_drivers is not None:
        thesis.key_drivers = body.key_drivers
    if body.primary_risks is not None:
        thesis.primary_risks = body.primary_risks
    if body.valuation_scenarios is not None:
        thesis.valuation_scenarios = body.valuation_scenarios
    if body.catalysts is not None:
        thesis.catalysts = body.catalysts

    thesis.slide_outline = _build_slide_outline(
        thesis.thesis_title, thesis.conviction_level, thesis.investment_horizon,
        thesis.elevator_pitch, thesis.key_drivers, thesis.primary_risks,
        thesis.valuation_scenarios, thesis.catalysts,
    )

    thesis.version = thesis.version + 1
    await session.commit()
    await session.refresh(thesis)

    return _thesis_response(thesis)


@router.get(
    "/research/thesis/{thesis_id}/diff",
    response_model=ThesisDiffResponse,
)
async def get_thesis_diff(
    thesis_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get diff between current thesis and previous version."""
    result = await session.execute(
        select(InvestmentThesis)
        .where(InvestmentThesis.id == thesis_id)
    )
    thesis = result.scalar_one_or_none()
    if not thesis:
        raise HTTPException(status_code=404, detail="Thesis not found")

    version_result = await session.execute(
        select(ThesisVersion)
        .where(ThesisVersion.thesis_id == thesis_id)
        .order_by(ThesisVersion.version.desc())
        .limit(1)
    )
    version = version_result.scalar_one_or_none()

    return ThesisDiffResponse(
        thesis_id=thesis.id,
        current_version=thesis.version,
        previous_version=version.version if version else None,
        conviction_change=_float(version.conviction_change) if version else None,
        updated_drivers=version.updated_drivers if version else None,
        analyst_note=version.analyst_note if version else None,
    )


@router.get(
    "/research/thesis/{thesis_id}/slides",
    response_model=ThesisSlideOutlineResponse,
)
async def get_thesis_slides(
    thesis_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get slide outline for a thesis presentation."""
    result = await session.execute(
        select(InvestmentThesis)
        .where(InvestmentThesis.id == thesis_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Thesis not found")

    if row.slide_outline is None:
        # Backfill for theses created/updated before slide_outline was wired.
        rebuilt = _build_slide_outline(
            row.thesis_title, row.conviction_level, row.investment_horizon,
            row.elevator_pitch, row.key_drivers, row.primary_risks,
            row.valuation_scenarios, row.catalysts,
        )
        if rebuilt is not None:
            row.slide_outline = rebuilt
            await session.commit()

    return ThesisSlideOutlineResponse(
        thesis_id=row.id,
        thesis_title=row.thesis_title,
        slide_outline=row.slide_outline,
    )


@router.get(
    "/research/thesis/{thesis_id}/elevator",
    response_model=ThesisElevatorPitchResponse,
)
async def get_thesis_elevator_pitch(
    thesis_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get elevator pitch for a thesis."""
    result = await session.execute(
        select(InvestmentThesis)
        .where(InvestmentThesis.id == thesis_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Thesis not found")

    return ThesisElevatorPitchResponse(
        thesis_id=row.id,
        thesis_title=row.thesis_title,
        elevator_pitch=row.elevator_pitch,
    )
