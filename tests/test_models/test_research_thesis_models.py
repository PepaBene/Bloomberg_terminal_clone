"""Tests for Pillar 3 Phase 4B: Investment Thesis + Analyst Q&A models."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from src.models.auth import User
from src.models.entity import Entity
from src.models.investment_thesis import InvestmentThesis, ThesisVersion
from src.models.analyst_qa import QASession, QAFeedback


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_entity(session, entity_id: uuid.UUID | None = None) -> Entity:
    eid = entity_id or uuid.uuid4()
    entity = Entity(
        entity_id=eid,
        entity_type="PUBLIC_COMPANY",
        legal_name="Thesis Test Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()
    return entity


async def _seed_analyst(session) -> uuid.UUID:
    """M-005: InvestmentThesis.analyst_id is now a real FK to users.user_id."""
    user_id = uuid.uuid4()
    session.add(User(
        user_id=user_id,
        username=f"analyst_{user_id.hex[:8]}",
        email=f"{user_id.hex[:8]}@test.example",
        hashed_password="x",
    ))
    await session.flush()
    return user_id


# ── InvestmentThesis Tests ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_investment_thesis(session):
    """Create an investment thesis with all fields and verify."""
    entity = await _seed_entity(session)
    analyst_id = await _seed_analyst(session)
    tid = uuid.uuid4()
    thesis = InvestmentThesis(
        id=tid,
        entity_id=entity.entity_id,
        analyst_id=analyst_id,
        version=1,
        thesis_title="Bullish on Cloud Transition",
        investment_horizon="12M",
        conviction_level="HIGH",
        executive_summary="Company poised for margin expansion from cloud migration.",
        key_drivers={"drivers": ["cloud ARR growth", "margin expansion"]},
        primary_risks={"risks": ["competition", "macro slowdown"]},
        valuation_scenarios={"bull": 220, "base": 180, "bear": 140},
        catalysts={"events": ["Q4 earnings", "product launch"]},
        quality_metrics={"data_coverage": 0.92, "source_count": 15},
        elevator_pitch="Leading cloud transition play with 30% upside.",
        slide_outline={"slides": ["Overview", "Thesis", "Valuation", "Risks"]},
        ai_enabled=True,
    )
    session.add(thesis)
    await session.flush()

    result = await session.execute(
        select(InvestmentThesis).where(InvestmentThesis.id == tid)
    )
    fetched = result.scalar_one()
    assert fetched.entity_id == entity.entity_id
    assert fetched.analyst_id == analyst_id
    assert fetched.version == 1
    assert fetched.thesis_title == "Bullish on Cloud Transition"
    assert fetched.investment_horizon == "12M"
    assert fetched.conviction_level == "HIGH"
    assert fetched.ai_enabled is True
    assert fetched.elevator_pitch == "Leading cloud transition play with 30% upside."


@pytest.mark.asyncio
async def test_thesis_jsonb_roundtrip(session):
    """Verify JSONB fields round-trip correctly."""
    entity = await _seed_entity(session)
    analyst_id = await _seed_analyst(session)
    tid = uuid.uuid4()
    key_drivers = {"growth": ["SaaS ARR", "International expansion"], "margin": "improving"}
    primary_risks = {"regulatory": "MEDIUM", "execution": "LOW"}

    thesis = InvestmentThesis(
        id=tid,
        entity_id=entity.entity_id,
        analyst_id=analyst_id,
        version=1,
        key_drivers=key_drivers,
        primary_risks=primary_risks,
    )
    session.add(thesis)
    await session.flush()

    result = await session.execute(
        select(InvestmentThesis).where(InvestmentThesis.id == tid)
    )
    fetched = result.scalar_one()
    assert fetched.key_drivers == key_drivers
    assert fetched.primary_risks == primary_risks


@pytest.mark.asyncio
async def test_thesis_defaults(session):
    """Verify default values for ai_enabled and version."""
    entity = await _seed_entity(session)
    analyst_id = await _seed_analyst(session)
    tid = uuid.uuid4()
    thesis = InvestmentThesis(
        id=tid,
        entity_id=entity.entity_id,
        analyst_id=analyst_id,
    )
    session.add(thesis)
    await session.flush()

    result = await session.execute(
        select(InvestmentThesis).where(InvestmentThesis.id == tid)
    )
    fetched = result.scalar_one()
    assert fetched.ai_enabled is False
    assert fetched.version == 1


@pytest.mark.asyncio
async def test_thesis_version_increment(session):
    """Test creating multiple thesis versions for same entity."""
    entity = await _seed_entity(session)
    analyst_id = await _seed_analyst(session)
    for v in range(1, 4):
        session.add(InvestmentThesis(
            id=uuid.uuid4(),
            entity_id=entity.entity_id,
            analyst_id=analyst_id,
            version=v,
            conviction_level="HIGH" if v <= 2 else "MEDIUM",
        ))
    await session.flush()

    result = await session.execute(
        select(InvestmentThesis)
        .where(InvestmentThesis.entity_id == entity.entity_id)
        .order_by(InvestmentThesis.version.desc())
    )
    rows = result.scalars().all()
    assert len(rows) == 3
    assert rows[0].version == 3
    assert rows[0].conviction_level == "MEDIUM"


# ── ThesisVersion Tests ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_thesis_version(session):
    """Create a thesis version snapshot."""
    entity = await _seed_entity(session)
    analyst_id = await _seed_analyst(session)
    thesis = InvestmentThesis(
        id=uuid.uuid4(),
        entity_id=entity.entity_id,
        analyst_id=analyst_id,
        version=1,
    )
    session.add(thesis)
    await session.flush()

    vid = uuid.uuid4()
    version = ThesisVersion(
        id=vid,
        thesis_id=thesis.id,
        version=1,
        conviction_change=Decimal("0.50"),
        updated_drivers={"added": ["new catalyst"]},
        analyst_note="Upgraded on strong Q3 results.",
    )
    session.add(version)
    await session.flush()

    result = await session.execute(
        select(ThesisVersion).where(ThesisVersion.id == vid)
    )
    fetched = result.scalar_one()
    assert fetched.thesis_id == thesis.id
    assert fetched.version == 1
    assert fetched.conviction_change == Decimal("0.50")
    assert fetched.updated_drivers == {"added": ["new catalyst"]}
    assert fetched.analyst_note == "Upgraded on strong Q3 results."


@pytest.mark.asyncio
async def test_thesis_version_decimal_precision(session):
    """Decimal conviction_change retains precision."""
    entity = await _seed_entity(session)
    analyst_id = await _seed_analyst(session)
    thesis = InvestmentThesis(
        id=uuid.uuid4(),
        entity_id=entity.entity_id,
        analyst_id=analyst_id,
        version=1,
    )
    session.add(thesis)
    await session.flush()

    vid = uuid.uuid4()
    version = ThesisVersion(
        id=vid,
        thesis_id=thesis.id,
        version=1,
        conviction_change=Decimal("-1.25"),
    )
    session.add(version)
    await session.flush()

    result = await session.execute(
        select(ThesisVersion).where(ThesisVersion.id == vid)
    )
    fetched = result.scalar_one()
    assert fetched.conviction_change == Decimal("-1.25")


# ── QASession Tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_qa_session(session):
    """Create a Q&A session with all fields and verify."""
    entity = await _seed_entity(session)
    sid = uuid.uuid4()
    qa = QASession(
        id=sid,
        user_id="analyst_010",
        entity_id=entity.entity_id,
        question="What are the key risk factors for this company?",
        answer_text="The primary risks include regulatory changes and competitive pressure.",
        answer_type="AI_GENERATED",
        confidence_level=Decimal("0.88"),
        confidence_narrative="High confidence based on 3 source documents.",
        sources={"filings": ["10K-2024", "10Q-Q3"], "news": ["article-001"]},
        supporting_data={"metrics": {"revenue_growth": 0.12}},
        follow_up_suggestions={"suggestions": ["What about valuation?"]},
        data_completeness={"score": 0.85, "missing": ["insider trades"]},
        user_rating=4,
        execution_time_ms=250,
    )
    session.add(qa)
    await session.flush()

    result = await session.execute(
        select(QASession).where(QASession.id == sid)
    )
    fetched = result.scalar_one()
    assert fetched.user_id == "analyst_010"
    assert fetched.entity_id == entity.entity_id
    assert fetched.answer_type == "AI_GENERATED"
    assert fetched.confidence_level == Decimal("0.88")
    assert fetched.user_rating == 4
    assert fetched.execution_time_ms == 250
    assert fetched.sources["filings"] == ["10K-2024", "10Q-Q3"]


@pytest.mark.asyncio
async def test_qa_session_minimal(session):
    """Create a Q&A session with minimal required fields."""
    sid = uuid.uuid4()
    qa = QASession(
        id=sid,
        user_id="analyst_011",
        question="Quick question about revenue?",
    )
    session.add(qa)
    await session.flush()

    result = await session.execute(
        select(QASession).where(QASession.id == sid)
    )
    fetched = result.scalar_one()
    assert fetched.user_id == "analyst_011"
    assert fetched.question == "Quick question about revenue?"
    assert fetched.answer_text is None
    assert fetched.entity_id is None
    assert fetched.user_rating is None


# ── QAFeedback Tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_qa_feedback(session):
    """Create Q&A feedback and verify."""
    qa = QASession(
        id=uuid.uuid4(),
        user_id="analyst_012",
        question="Test question for feedback.",
    )
    session.add(qa)
    await session.flush()

    fid = uuid.uuid4()
    feedback = QAFeedback(
        id=fid,
        session_id=qa.id,
        rating=5,
        feedback_text="Very helpful and accurate answer.",
        is_accurate=True,
    )
    session.add(feedback)
    await session.flush()

    result = await session.execute(
        select(QAFeedback).where(QAFeedback.id == fid)
    )
    fetched = result.scalar_one()
    assert fetched.session_id == qa.id
    assert fetched.rating == 5
    assert fetched.feedback_text == "Very helpful and accurate answer."
    assert fetched.is_accurate is True


@pytest.mark.asyncio
async def test_qa_feedback_partial(session):
    """Create Q&A feedback with only rating."""
    qa = QASession(
        id=uuid.uuid4(),
        user_id="analyst_013",
        question="Partial feedback test.",
    )
    session.add(qa)
    await session.flush()

    fid = uuid.uuid4()
    feedback = QAFeedback(
        id=fid,
        session_id=qa.id,
        rating=3,
    )
    session.add(feedback)
    await session.flush()

    result = await session.execute(
        select(QAFeedback).where(QAFeedback.id == fid)
    )
    fetched = result.scalar_one()
    assert fetched.rating == 3
    assert fetched.feedback_text is None
    assert fetched.is_accurate is None
