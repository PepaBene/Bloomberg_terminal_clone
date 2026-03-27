"""Tests for Pillar 3 Phase 1: Governance Intelligence models."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.models.entity import Entity
from src.models.governance_intelligence import (
    BoardMember,
    ExecutiveCompensation,
    GovernanceAssessment,
    ProxyFiling,
    ShareholderProposal,
)


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_entity(session, entity_id: uuid.UUID | None = None) -> Entity:
    eid = entity_id or uuid.uuid4()
    entity = Entity(
        entity_id=eid,
        entity_type="PUBLIC_COMPANY",
        legal_name="Governance Test Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()
    return entity


async def _seed_proxy(session, entity_id: uuid.UUID, fiscal_year: int = 2024) -> ProxyFiling:
    pid = uuid.uuid4()
    proxy = ProxyFiling(
        id=pid,
        entity_id=entity_id,
        fiscal_year=fiscal_year,
        filing_date=date(2025, 4, 15),
        meeting_date=date(2025, 6, 10),
        filing_accession_number="0001193125-25-000200",
        filing_url="https://sec.gov/filings/def14a-example",
    )
    session.add(proxy)
    await session.flush()
    return proxy


# ── Tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_proxy_filing(session):
    """Create a proxy filing with all fields and verify."""
    entity = await _seed_entity(session)
    pid = uuid.uuid4()
    proxy = ProxyFiling(
        id=pid,
        entity_id=entity.entity_id,
        fiscal_year=2024,
        filing_date=date(2025, 4, 15),
        meeting_date=date(2025, 6, 10),
        filing_accession_number="0001193125-25-000200",
        filing_url="https://sec.gov/filings/def14a-example",
    )
    session.add(proxy)
    await session.flush()

    result = await session.execute(
        select(ProxyFiling).where(ProxyFiling.id == pid)
    )
    fetched = result.scalar_one()
    assert fetched.entity_id == entity.entity_id
    assert fetched.fiscal_year == 2024
    assert fetched.filing_date == date(2025, 4, 15)
    assert fetched.meeting_date == date(2025, 6, 10)
    assert fetched.filing_accession_number == "0001193125-25-000200"


@pytest.mark.asyncio
async def test_proxy_filing_unique_constraint(session):
    """entity_id + fiscal_year should be unique."""
    entity = await _seed_entity(session)
    await _seed_proxy(session, entity.entity_id, fiscal_year=2023)

    session.add(ProxyFiling(
        entity_id=entity.entity_id,
        fiscal_year=2023,
        filing_date=date(2024, 4, 1),
    ))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_create_executive_compensation(session):
    """Create executive compensation with Decimal fields for all comp components."""
    entity = await _seed_entity(session)
    proxy = await _seed_proxy(session, entity.entity_id)
    cid = uuid.uuid4()

    comp = ExecutiveCompensation(
        id=cid,
        proxy_id=proxy.id,
        entity_id=entity.entity_id,
        person_name="Jane Q. CEO",
        role="CEO",
        fiscal_year=2024,
        total_compensation=Decimal("15250000.00"),
        base_salary=Decimal("1500000.00"),
        bonus=Decimal("3000000.00"),
        stock_awards=Decimal("6000000.00"),
        option_awards=Decimal("2500000.00"),
        non_equity_incentive=Decimal("1750000.00"),
        other_compensation=Decimal("250000.00"),
        change_in_pension=Decimal("250000.00"),
        yoy_change_pct=Decimal("12.5000"),
        pay_ratio_to_median=Decimal("305.00"),
    )
    session.add(comp)
    await session.flush()

    result = await session.execute(
        select(ExecutiveCompensation).where(ExecutiveCompensation.id == cid)
    )
    fetched = result.scalar_one()
    assert fetched.person_name == "Jane Q. CEO"
    assert fetched.role == "CEO"
    assert fetched.total_compensation == Decimal("15250000.00")
    assert fetched.base_salary == Decimal("1500000.00")
    assert fetched.bonus == Decimal("3000000.00")
    assert fetched.stock_awards == Decimal("6000000.00")
    assert fetched.option_awards == Decimal("2500000.00")
    assert fetched.non_equity_incentive == Decimal("1750000.00")
    assert fetched.other_compensation == Decimal("250000.00")
    assert fetched.change_in_pension == Decimal("250000.00")
    assert fetched.yoy_change_pct == Decimal("12.5000")
    assert fetched.pay_ratio_to_median == Decimal("305.00")


@pytest.mark.asyncio
async def test_create_board_member(session):
    """Create a board member with JSONB committees and expertise_areas."""
    entity = await _seed_entity(session)
    proxy = await _seed_proxy(session, entity.entity_id)
    bid = uuid.uuid4()
    committees = ["Audit", "Compensation", "Nominating"]
    expertise = ["Finance", "Technology", "Governance"]
    other_boards = ["OtherCorp Inc.", "TechFirm LLC"]

    member = BoardMember(
        id=bid,
        proxy_id=proxy.id,
        entity_id=entity.entity_id,
        person_name="Robert Q. Director",
        is_independent=True,
        is_chair=False,
        tenure_years=8,
        age=62,
        gender="Male",
        committees=committees,
        expertise_areas=expertise,
        other_boards=other_boards,
    )
    session.add(member)
    await session.flush()

    result = await session.execute(
        select(BoardMember).where(BoardMember.id == bid)
    )
    fetched = result.scalar_one()
    assert fetched.person_name == "Robert Q. Director"
    assert fetched.is_independent is True
    assert fetched.is_chair is False
    assert fetched.tenure_years == 8
    assert fetched.age == 62
    assert fetched.gender == "Male"
    assert fetched.committees == committees
    assert fetched.expertise_areas == expertise
    assert fetched.other_boards == other_boards


@pytest.mark.asyncio
async def test_create_shareholder_proposal(session):
    """Create a shareholder proposal with vote percentages."""
    entity = await _seed_entity(session)
    proxy = await _seed_proxy(session, entity.entity_id)
    spid = uuid.uuid4()

    proposal = ShareholderProposal(
        id=spid,
        proxy_id=proxy.id,
        entity_id=entity.entity_id,
        proposal_number=3,
        topic="ESG",
        description="Require annual climate risk report",
        proponent="Climate Action Now Fund",
        management_recommendation="AGAINST",
        vote_for_pct=Decimal("42.50"),
        vote_against_pct=Decimal("55.30"),
        vote_abstain_pct=Decimal("2.20"),
        passed=False,
    )
    session.add(proposal)
    await session.flush()

    result = await session.execute(
        select(ShareholderProposal).where(ShareholderProposal.id == spid)
    )
    fetched = result.scalar_one()
    assert fetched.proposal_number == 3
    assert fetched.topic == "ESG"
    assert fetched.proponent == "Climate Action Now Fund"
    assert fetched.management_recommendation == "AGAINST"
    assert fetched.vote_for_pct == Decimal("42.50")
    assert fetched.vote_against_pct == Decimal("55.30")
    assert fetched.vote_abstain_pct == Decimal("2.20")
    assert fetched.passed is False


@pytest.mark.asyncio
async def test_create_governance_assessment(session):
    """Create a governance assessment with all boolean red flags + score."""
    entity = await _seed_entity(session)
    gid = uuid.uuid4()

    assessment = GovernanceAssessment(
        id=gid,
        entity_id=entity.entity_id,
        assessment_date=date(2025, 7, 1),
        governance_score=72,
        classification="ADEQUATE",
        dual_class=False,
        ceo_is_chair=True,
        board_independence_pct=Decimal("75.00"),
        avg_board_tenure=Decimal("7.5"),
        has_poison_pill=False,
        has_staggered_board=True,
        has_majority_voting=True,
        related_party_flag=False,
        ceo_pay_ratio=Decimal("305.00"),
        long_term_incentive_pct=Decimal("65.00"),
        board_diversity_pct=Decimal("40.00"),
        board_interlock_count=1,
        red_flags=["CEO_IS_CHAIR", "STAGGERED_BOARD"],
    )
    session.add(assessment)
    await session.flush()

    result = await session.execute(
        select(GovernanceAssessment).where(GovernanceAssessment.id == gid)
    )
    fetched = result.scalar_one()
    assert fetched.governance_score == 72
    assert fetched.classification == "ADEQUATE"
    assert fetched.dual_class is False
    assert fetched.ceo_is_chair is True
    assert fetched.board_independence_pct == Decimal("75.00")
    assert fetched.avg_board_tenure == Decimal("7.5")
    assert fetched.has_poison_pill is False
    assert fetched.has_staggered_board is True
    assert fetched.has_majority_voting is True
    assert fetched.related_party_flag is False
    assert fetched.ceo_pay_ratio == Decimal("305.00")
    assert fetched.board_interlock_count == 1


@pytest.mark.asyncio
async def test_governance_score_classification(session):
    """Test score values for STRONG / ADEQUATE / CONCERNS / SIGNIFICANT_RISK."""
    entity = await _seed_entity(session)
    classifications = [
        (95, "STRONG"),
        (72, "ADEQUATE"),
        (45, "CONCERNS"),
        (20, "SIGNIFICANT_RISK"),
    ]
    ids = []
    for score, classification in classifications:
        gid = uuid.uuid4()
        ids.append(gid)
        session.add(GovernanceAssessment(
            id=gid,
            entity_id=entity.entity_id,
            assessment_date=date(2025, 7, score % 28 + 1),
            governance_score=score,
            classification=classification,
        ))
    await session.flush()

    for i, (expected_score, expected_class) in enumerate(classifications):
        result = await session.execute(
            select(GovernanceAssessment).where(GovernanceAssessment.id == ids[i])
        )
        fetched = result.scalar_one()
        assert fetched.governance_score == expected_score
        assert fetched.classification == expected_class


@pytest.mark.asyncio
async def test_governance_red_flags_jsonb(session):
    """Round-trip JSONB red_flags list."""
    entity = await _seed_entity(session)
    gid = uuid.uuid4()
    red_flags = [
        "DUAL_CLASS_STOCK",
        "CEO_IS_CHAIR",
        "NO_MAJORITY_VOTING",
        "POISON_PILL",
        "RELATED_PARTY_TRANSACTIONS",
    ]
    session.add(GovernanceAssessment(
        id=gid,
        entity_id=entity.entity_id,
        assessment_date=date(2025, 8, 1),
        governance_score=30,
        classification="SIGNIFICANT_RISK",
        red_flags=red_flags,
    ))
    await session.flush()

    result = await session.execute(
        select(GovernanceAssessment).where(GovernanceAssessment.id == gid)
    )
    fetched = result.scalar_one()
    assert fetched.red_flags == red_flags
    assert len(fetched.red_flags) == 5
    assert "DUAL_CLASS_STOCK" in fetched.red_flags
    assert "POISON_PILL" in fetched.red_flags
