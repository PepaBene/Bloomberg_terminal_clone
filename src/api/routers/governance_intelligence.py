"""Governance Intelligence API endpoints (Pillar 3 Phase 1)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.engines import governance_scoring
from src.models.entity import Entity
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

    independent_count = sum(1 for m in board_members if m.get("is_independent"))
    board_total = len(board_members) or 0
    ceo_is_chair = any(
        m.get("is_chair") and (m.get("expertise_areas") or m.get("role") == "CEO")
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
