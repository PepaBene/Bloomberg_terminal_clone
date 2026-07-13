"""Governance Intelligence API endpoints (Pillar 3 Phase 1)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.engines import governance_scoring
from src.models.analytics import AnalyticsResult
from src.models.entity import Entity
from src.models.fundamentals import FinancialPeriod
from src.models.security import EODPrice, Security
from src.models.governance_intelligence import (
    BoardMember,
    ExecutiveCompensation,
    GovernanceAssessment,
    ProxyFiling,
    ShareholderProposal,
)
from src.schemas.governance_intelligence import (
    BoardMemberResponse,
    ExecutiveCompensationResponse,
    GovernanceAssessmentResponse,
    GovernanceRedFlagResponse,
    ProxyFilingResponse,
    ShareholderProposalResponse,
)

router = APIRouter(tags=["Governance Intelligence"])




async def _load_pay_performance_metrics(session: AsyncSession, entity_id: uuid.UUID) -> dict:
    """Load real TSR, revenue growth, and ROIC inputs for pay alignment."""
    metrics: dict[str, float | None] = {"tsr_1y": None, "revenue_growth_pct": None, "roic": None}

    security = (await session.execute(
        select(Security)
        .where(Security.issuer_entity_id == entity_id, Security.asset_class == "EQUITY")
        .order_by(Security.status.desc().nulls_last())
        .limit(1)
    )).scalar_one_or_none()
    if security:
        prices = (await session.execute(
            select(EODPrice.close)
            .where(EODPrice.security_id == security.security_id, EODPrice.close.isnot(None))
            .order_by(EODPrice.price_date.desc())
            .limit(252)
        )).scalars().all()
        if len(prices) >= 2 and prices[-1]:
            metrics["tsr_1y"] = (float(prices[0]) - float(prices[-1])) / abs(float(prices[-1])) * 100.0

    periods = (await session.execute(
        select(FinancialPeriod)
        .where(FinancialPeriod.entity_id == entity_id)
        .order_by(FinancialPeriod.period_end_date.desc())
        .limit(2)
    )).scalars().all()
    if len(periods) >= 2 and periods[0].income_statement and periods[1].income_statement:
        latest_rev = periods[0].income_statement.total_revenue
        prior_rev = periods[1].income_statement.total_revenue
        if latest_rev is not None and prior_rev:
            metrics["revenue_growth_pct"] = (float(latest_rev) - float(prior_rev)) / abs(float(prior_rev)) * 100.0

    roic = (await session.execute(
        select(AnalyticsResult.value)
        .where(AnalyticsResult.entity_id == entity_id, AnalyticsResult.metric_name == "roic")
        .order_by(AnalyticsResult.as_of_date.desc())
        .limit(1)
    )).scalar_one_or_none()
    if roic is not None:
        metrics["roic"] = float(roic) * (100.0 if abs(float(roic)) <= 1.0 else 1.0)

    return {key: (0.0 if value is None else value) for key, value in metrics.items()}

async def _get_entity(session: AsyncSession, entity_id: uuid.UUID) -> Entity:
    result = await session.execute(
        select(Entity).where(Entity.entity_id == entity_id)
    )
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


def _parse_red_flags(raw) -> list[GovernanceRedFlagResponse]:
    """Convert the JSONB-stored red flags into typed responses.

    Tolerates schema drift: a raw value that is not a list, or items that
    are not dicts, simply yield empty / safe defaults rather than raising.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: list[GovernanceRedFlagResponse] = []
    for rf in raw:
        if not isinstance(rf, dict):
            continue
        result.append(
            GovernanceRedFlagResponse(
                flag=rf.get("flag", ""),
                severity=rf.get("severity", "LOW"),
                detail=rf.get("detail", ""),
                weight=rf.get("weight", 0),
            )
        )
    return result


async def _compute_governance_assessment_live(
    session: AsyncSession, entity_id: uuid.UUID
) -> dict | None:
    """Compute a governance assessment on-the-fly from current proxy data.

    Returns ``None`` if no proxy filing has been ingested for the entity.
    Used as a fallback when no batch-computed ``GovernanceAssessment`` row
    exists yet, so the router's outputs aren't permanently empty just
    because a worker hasn't run.
    """
    proxy_result = await session.execute(
        select(ProxyFiling)
        .where(ProxyFiling.entity_id == entity_id)
        .order_by(ProxyFiling.fiscal_year.desc())
        .limit(1)
    )
    proxy = proxy_result.scalar_one_or_none()
    if not proxy:
        return None

    board_rows = (
        await session.execute(
            select(BoardMember).where(BoardMember.proxy_id == proxy.id)
        )
    ).scalars().all()
    board_members = [
        {
            "person_name": m.person_name,
            "is_independent": m.is_independent,
            "is_chair": m.is_chair,
            "tenure_years": m.tenure_years,
            "age": m.age,
            "gender": m.gender,
            "committees": m.committees,
            "expertise_areas": m.expertise_areas,
        }
        for m in board_rows
    ]

    # Determine who holds the CEO title from the proxy's executive
    # compensation table (BoardMember carries no role/title field) and
    # cross-reference by name against the board chair.
    exec_rows = (
        await session.execute(
            select(ExecutiveCompensation.person_name, ExecutiveCompensation.role)
            .where(ExecutiveCompensation.proxy_id == proxy.id)
        )
    ).all()
    ceo_names = {
        name.strip().lower()
        for name, role in exec_rows
        if "CEO" in role.upper() or "CHIEF EXECUTIVE" in role.upper()
    }

    independent_count = sum(1 for m in board_members if m.get("is_independent"))
    board_total = len(board_members) or 0
    ceo_is_chair = any(
        m.get("is_chair") and m.get("person_name", "").strip().lower() in ceo_names
        for m in board_members
    )

    governance_data = {
        "ceo_is_chair": ceo_is_chair,
        "board_independence_pct": (
            (independent_count / board_total * 100.0) if board_total else None
        ),
        "board_members": board_members,
    }

    score = governance_scoring.compute_governance_score(governance_data)
    diversity = governance_scoring.compute_board_diversity(board_members)
    return {
        "score": score["score"],
        "classification": score["classification"],
        "red_flags": score["red_flags"],
        "board_independence_pct": governance_data["board_independence_pct"],
        "board_diversity_pct": diversity.get("women_pct"),
        "ceo_is_chair": ceo_is_chair,
    }


@router.get(
    "/governance/{entity_id}/score",
    response_model=GovernanceAssessmentResponse,
)
async def get_governance_score(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get governance score for an entity, computing on-demand if needed."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(GovernanceAssessment)
        .where(GovernanceAssessment.entity_id == entity_id)
        .order_by(GovernanceAssessment.assessment_date.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()

    if row:
        return GovernanceAssessmentResponse(
            entity_id=row.entity_id,
            assessment_date=row.assessment_date,
            governance_score=row.governance_score,
            classification=row.classification,
            red_flags=_parse_red_flags(row.red_flags),
            board_independence_pct=float(row.board_independence_pct) if row.board_independence_pct is not None else None,
            board_diversity_pct=float(row.board_diversity_pct) if row.board_diversity_pct is not None else None,
            ceo_is_chair=row.ceo_is_chair,
        )

    # No pre-computed score — compute on-demand from real proxy/board data.
    # NOTE: this must never fall back to fabricated governance_data (all
    # fields defaulted/False) — a prior version did that and persisted the
    # fabricated result here, permanently poisoning this cache for the
    # entity even after real proxy data was later ingested.
    live = await _compute_governance_assessment_live(session, entity_id)
    if not live:
        raise HTTPException(
            status_code=404,
            detail="No proxy filing data available to compute a governance score for this entity",
        )

    return GovernanceAssessmentResponse(
        entity_id=entity_id,
        assessment_date=date.today(),
        governance_score=live["score"],
        classification=live["classification"],
        red_flags=_parse_red_flags(live["red_flags"]),
        board_independence_pct=live["board_independence_pct"],
        board_diversity_pct=live["board_diversity_pct"],
        ceo_is_chair=live["ceo_is_chair"],
    )


@router.get(
    "/filings/{entity_id}/proxy",
    response_model=list[ProxyFilingResponse],
)
async def get_proxy_filings(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get proxy filing history for an entity."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(ProxyFiling)
        .where(ProxyFiling.entity_id == entity_id)
        .order_by(ProxyFiling.fiscal_year.desc())
        .limit(10)
    )
    rows = result.scalars().all()

    return [
        ProxyFilingResponse(
            id=row.id,
            entity_id=row.entity_id,
            fiscal_year=row.fiscal_year,
            filing_date=row.filing_date,
            meeting_date=row.meeting_date,
            filing_url=row.filing_url,
        )
        for row in rows
    ]


@router.get(
    "/filings/{entity_id}/proxy/compensation",
    response_model=list[ExecutiveCompensationResponse],
)
async def get_executive_compensation(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get executive compensation data from the latest proxy filing."""
    await _get_entity(session, entity_id)

    # Find the most recent proxy filing
    proxy_result = await session.execute(
        select(ProxyFiling)
        .where(ProxyFiling.entity_id == entity_id)
        .order_by(ProxyFiling.fiscal_year.desc())
        .limit(1)
    )
    proxy = proxy_result.scalar_one_or_none()
    if not proxy:
        raise HTTPException(status_code=404, detail="No proxy filings found for this entity")

    result = await session.execute(
        select(ExecutiveCompensation)
        .where(ExecutiveCompensation.proxy_id == proxy.id)
        .order_by(ExecutiveCompensation.total_compensation.desc().nulls_last())
    )
    rows = result.scalars().all()

    return [
        ExecutiveCompensationResponse(
            person_name=row.person_name,
            role=row.role,
            fiscal_year=row.fiscal_year,
            total_compensation=float(row.total_compensation) if row.total_compensation is not None else None,
            base_salary=float(row.base_salary) if row.base_salary is not None else None,
            bonus=float(row.bonus) if row.bonus is not None else None,
            stock_awards=float(row.stock_awards) if row.stock_awards is not None else None,
            option_awards=float(row.option_awards) if row.option_awards is not None else None,
            yoy_change_pct=float(row.yoy_change_pct) if row.yoy_change_pct is not None else None,
            pay_ratio_to_median=float(row.pay_ratio_to_median) if row.pay_ratio_to_median is not None else None,
        )
        for row in rows
    ]


@router.get(
    "/filings/{entity_id}/proxy/governance",
    response_model=GovernanceAssessmentResponse,
)
async def get_governance_assessment(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get the latest governance assessment for an entity."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(GovernanceAssessment)
        .where(GovernanceAssessment.entity_id == entity_id)
        .order_by(GovernanceAssessment.assessment_date.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()

    if row:
        red_flag_items = _parse_red_flags(row.red_flags)
        return GovernanceAssessmentResponse(
            entity_id=row.entity_id,
            assessment_date=row.assessment_date,
            governance_score=row.governance_score,
            classification=row.classification,
            red_flags=red_flag_items,
            board_independence_pct=float(row.board_independence_pct) if row.board_independence_pct is not None else None,
            board_diversity_pct=float(row.board_diversity_pct) if row.board_diversity_pct is not None else None,
            ceo_is_chair=row.ceo_is_chair,
        )

    # No batch-computed assessment yet — compute one on the fly so the
    # endpoint returns real data instead of a 404 the moment proxy data
    # exists but the scoring batch has not run.
    live = await _compute_governance_assessment_live(session, entity_id)
    if not live:
        raise HTTPException(status_code=404, detail="No governance assessment found for this entity")

    return GovernanceAssessmentResponse(
        entity_id=entity_id,
        assessment_date=date.today(),
        governance_score=live["score"],
        classification=live["classification"],
        red_flags=_parse_red_flags(live["red_flags"]),
        board_independence_pct=live["board_independence_pct"],
        board_diversity_pct=live["board_diversity_pct"],
        ceo_is_chair=live["ceo_is_chair"],
    )


@router.get(
    "/filings/{entity_id}/proxy/red-flags",
    response_model=list[GovernanceRedFlagResponse],
)
async def get_governance_red_flags(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get red flags from the latest governance assessment."""
    await _get_entity(session, entity_id)

    result = await session.execute(
        select(GovernanceAssessment)
        .where(GovernanceAssessment.entity_id == entity_id)
        .order_by(GovernanceAssessment.assessment_date.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if row:
        return _parse_red_flags(row.red_flags)

    live = await _compute_governance_assessment_live(session, entity_id)
    if not live:
        raise HTTPException(status_code=404, detail="No governance assessment found for this entity")
    return _parse_red_flags(live["red_flags"])


@router.get(
    "/filings/{entity_id}/proxy/proposals",
    response_model=list[ShareholderProposalResponse],
)
async def get_shareholder_proposals(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get shareholder proposals from the latest proxy filing."""
    await _get_entity(session, entity_id)

    # Find the most recent proxy filing
    proxy_result = await session.execute(
        select(ProxyFiling)
        .where(ProxyFiling.entity_id == entity_id)
        .order_by(ProxyFiling.fiscal_year.desc())
        .limit(1)
    )
    proxy = proxy_result.scalar_one_or_none()
    if not proxy:
        raise HTTPException(status_code=404, detail="No proxy filings found for this entity")

    result = await session.execute(
        select(ShareholderProposal)
        .where(ShareholderProposal.proxy_id == proxy.id)
        .order_by(ShareholderProposal.proposal_number)
    )
    rows = result.scalars().all()

    return [
        ShareholderProposalResponse(
            proposal_number=row.proposal_number,
            topic=row.topic,
            description=row.description,
            management_recommendation=row.management_recommendation,
            vote_for_pct=float(row.vote_for_pct) if row.vote_for_pct is not None else None,
            vote_against_pct=float(row.vote_against_pct) if row.vote_against_pct is not None else None,
            passed=row.passed,
        )
        for row in rows
    ]


@router.get(
    "/filings/{entity_id}/proxy/board",
    response_model=list[BoardMemberResponse],
)
async def get_board_members(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get board of directors from the latest proxy filing."""
    await _get_entity(session, entity_id)

    # Find the most recent proxy filing
    proxy_result = await session.execute(
        select(ProxyFiling)
        .where(ProxyFiling.entity_id == entity_id)
        .order_by(ProxyFiling.fiscal_year.desc())
        .limit(1)
    )
    proxy = proxy_result.scalar_one_or_none()
    if not proxy:
        raise HTTPException(status_code=404, detail="No proxy filings found for this entity")

    result = await session.execute(
        select(BoardMember)
        .where(BoardMember.proxy_id == proxy.id)
        .order_by(BoardMember.is_chair.desc(), BoardMember.person_name)
    )
    rows = result.scalars().all()

    return [
        BoardMemberResponse(
            person_name=row.person_name,
            is_independent=row.is_independent,
            is_chair=row.is_chair,
            tenure_years=row.tenure_years,
            age=row.age,
            gender=row.gender,
            committees=row.committees,
            expertise_areas=row.expertise_areas,
        )
        for row in rows
    ]

@router.get(
    "/filings/{entity_id}/proxy/pay-alignment",
    response_model=dict,
)
async def get_pay_alignment(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Expose pay-for-performance alignment from latest proxy compensation."""
    await _get_entity(session, entity_id)
    proxy = (await session.execute(
        select(ProxyFiling).where(ProxyFiling.entity_id == entity_id).order_by(ProxyFiling.fiscal_year.desc()).limit(1)
    )).scalar_one_or_none()
    if not proxy:
        raise HTTPException(status_code=404, detail="No proxy filings found for this entity")
    rows = (await session.execute(select(ExecutiveCompensation).where(ExecutiveCompensation.proxy_id == proxy.id))).scalars().all()
    if not rows:
        raise HTTPException(status_code=404, detail="No executive compensation found for this entity")
    ceo = next((r for r in rows if r.role and "CEO" in r.role.upper()), rows[0])
    peer_comp = [
        {"total_compensation": float(r.total_compensation)}
        for r in rows
        if r.id != ceo.id and r.total_compensation is not None
    ]
    return governance_scoring.compute_pay_alignment(
        {
            "total_compensation": float(ceo.total_compensation or 0),
            "yoy_change_pct": float(ceo.yoy_change_pct or 0),
        },
        await _load_pay_performance_metrics(session, entity_id),
        peer_comp,
    )


@router.get(
    "/filings/{entity_id}/proxy/board-interlocks",
    response_model=list[dict],
)
async def get_board_interlocks(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Expose board interlock detection from latest proxy board members."""
    await _get_entity(session, entity_id)
    proxy = (await session.execute(
        select(ProxyFiling).where(ProxyFiling.entity_id == entity_id).order_by(ProxyFiling.fiscal_year.desc()).limit(1)
    )).scalar_one_or_none()
    if not proxy:
        raise HTTPException(status_code=404, detail="No proxy filings found for this entity")
    rows = (await session.execute(select(BoardMember).where(BoardMember.proxy_id == proxy.id))).scalars().all()
    members = [
        {"person_name": r.person_name, "other_boards": (r.committees or {}).get("other_boards", []) if isinstance(r.committees, dict) else []}
        for r in rows
    ]
    return governance_scoring.detect_board_interlocks(members)


@router.get(
    "/filings/{entity_id}/proxy/proposal-analysis",
    response_model=dict,
)
async def get_shareholder_proposal_analysis(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Expose shareholder proposal voting analytics from latest proxy."""
    await _get_entity(session, entity_id)
    proxy = (await session.execute(
        select(ProxyFiling).where(ProxyFiling.entity_id == entity_id).order_by(ProxyFiling.fiscal_year.desc()).limit(1)
    )).scalar_one_or_none()
    if not proxy:
        raise HTTPException(status_code=404, detail="No proxy filings found for this entity")
    rows = (await session.execute(select(ShareholderProposal).where(ShareholderProposal.proxy_id == proxy.id))).scalars().all()
    proposals = [
        {"topic": r.topic, "vote_for_pct": float(r.vote_for_pct or 0), "management_recommendation": r.management_recommendation, "passed": r.passed}
        for r in rows
    ]
    return governance_scoring.analyze_shareholder_proposals(proposals)
