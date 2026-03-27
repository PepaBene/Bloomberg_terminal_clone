"""Tests for Pillar 3 Phase 1: Filing Intelligence models."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.models.entity import Entity
from src.models.filing_intelligence import EightKEvent, FilingDiff, FilingSection


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_entity(session, entity_id: uuid.UUID | None = None) -> Entity:
    eid = entity_id or uuid.uuid4()
    entity = Entity(
        entity_id=eid,
        entity_type="PUBLIC_COMPANY",
        legal_name="Filing Test Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()
    return entity


# ── Tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_filing_section(session):
    """Create a filing section with all fields and verify round-trip."""
    entity = await _seed_entity(session)
    sid = uuid.uuid4()
    section = FilingSection(
        id=sid,
        entity_id=entity.entity_id,
        filing_type="10-K",
        filing_date=date(2025, 3, 1),
        fiscal_year=2024,
        fiscal_quarter=None,
        section_key="ITEM_1A",
        section_text="Risk factors include market volatility and regulatory changes.",
        word_count=8,
        filing_accession_number="0001193125-25-000001",
        filing_url="https://sec.gov/filings/example",
    )
    session.add(section)
    await session.flush()

    result = await session.execute(
        select(FilingSection).where(FilingSection.id == sid)
    )
    fetched = result.scalar_one()
    assert fetched.entity_id == entity.entity_id
    assert fetched.filing_type == "10-K"
    assert fetched.filing_date == date(2025, 3, 1)
    assert fetched.fiscal_year == 2024
    assert fetched.fiscal_quarter is None
    assert fetched.section_key == "ITEM_1A"
    assert fetched.word_count == 8
    assert fetched.filing_accession_number == "0001193125-25-000001"
    assert fetched.filing_url == "https://sec.gov/filings/example"


@pytest.mark.asyncio
async def test_filing_section_unique_constraint(session):
    """Same entity+type+year+section_key should raise IntegrityError."""
    entity = await _seed_entity(session)
    common = dict(
        entity_id=entity.entity_id,
        filing_type="10-K",
        fiscal_year=2024,
        section_key="ITEM_1A",
        filing_date=date(2025, 3, 1),
        section_text="First version",
        word_count=2,
    )
    session.add(FilingSection(**common))
    await session.flush()

    session.add(FilingSection(**{**common, "section_text": "Duplicate version", "word_count": 2}))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_create_filing_diff(session):
    """Create a filing diff with JSONB fields and verify round-trip."""
    entity = await _seed_entity(session)
    did = uuid.uuid4()
    added = [{"paragraph": "New risk disclosure about AI regulation."}]
    removed = [{"paragraph": "Removed boilerplate language."}]
    modified = [{"old": "Revenue grew 5%", "new": "Revenue grew 12%"}]

    diff = FilingDiff(
        id=did,
        entity_id=entity.entity_id,
        section_key="ITEM_1A",
        year_old=2023,
        year_new=2024,
        change_pct=Decimal("15.50"),
        change_classification="MATERIAL",
        substantive_change_count=3,
        boilerplate_change_count=1,
        numerical_change_count=2,
        structural_change_count=0,
        added_paragraphs=added,
        removed_paragraphs=removed,
        modified_paragraphs=modified,
        ai_summary="Significant expansion of risk factor disclosures.",
        materiality="HIGH",
    )
    session.add(diff)
    await session.flush()

    result = await session.execute(
        select(FilingDiff).where(FilingDiff.id == did)
    )
    fetched = result.scalar_one()
    assert fetched.section_key == "ITEM_1A"
    assert fetched.year_old == 2023
    assert fetched.year_new == 2024
    assert float(fetched.change_pct) == pytest.approx(15.50, abs=0.01)
    assert fetched.substantive_change_count == 3
    assert fetched.added_paragraphs == added
    assert fetched.removed_paragraphs == removed
    assert fetched.modified_paragraphs == modified
    assert fetched.materiality == "HIGH"


@pytest.mark.asyncio
async def test_filing_diff_materiality_values(session):
    """Test HIGH, MEDIUM, LOW, CRITICAL materiality values."""
    entity = await _seed_entity(session)
    for i, materiality in enumerate(("HIGH", "MEDIUM", "LOW", "CRITICAL")):
        did = uuid.uuid4()
        session.add(FilingDiff(
            id=did,
            entity_id=entity.entity_id,
            section_key="ITEM_1A",
            year_old=2020 + i,
            year_new=2021 + i,
            materiality=materiality,
        ))
        await session.flush()

        result = await session.execute(
            select(FilingDiff).where(FilingDiff.id == did)
        )
        fetched = result.scalar_one()
        assert fetched.materiality == materiality


@pytest.mark.asyncio
async def test_create_eight_k_event(session):
    """Create an 8-K event with monetary_figures, key_dates, key_people JSONB."""
    entity = await _seed_entity(session)
    eid = uuid.uuid4()
    monetary = [{"label": "Acquisition price", "amount": 2500000000, "currency": "USD"}]
    dates = [{"label": "Closing date", "date": "2025-06-30"}]
    people = [{"name": "Jane Smith", "role": "CEO"}]

    event = EightKEvent(
        id=eid,
        entity_id=entity.entity_id,
        filing_date=date(2025, 4, 15),
        item_number="1.01",
        item_description="Entry into a Material Definitive Agreement",
        priority=1,
        raw_text="The company entered into a definitive merger agreement.",
        monetary_figures=monetary,
        key_dates=dates,
        key_people=people,
        ai_summary="Major acquisition announced.",
        materiality="CRITICAL",
        filing_accession_number="0001193125-25-000099",
        filing_url="https://sec.gov/filings/8k-example",
        is_processed=False,
    )
    session.add(event)
    await session.flush()

    result = await session.execute(
        select(EightKEvent).where(EightKEvent.id == eid)
    )
    fetched = result.scalar_one()
    assert fetched.item_number == "1.01"
    assert fetched.priority == 1
    assert fetched.monetary_figures == monetary
    assert fetched.key_dates == dates
    assert fetched.key_people == people
    assert fetched.materiality == "CRITICAL"
    assert fetched.is_processed is False


@pytest.mark.asyncio
async def test_eight_k_priority_values(session):
    """Test priority 1, 2, 3 events."""
    entity = await _seed_entity(session)
    ids = []
    for priority in (1, 2, 3):
        eid = uuid.uuid4()
        ids.append(eid)
        session.add(EightKEvent(
            id=eid,
            entity_id=entity.entity_id,
            filing_date=date(2025, 5, priority),
            item_number=f"{priority}.01",
            priority=priority,
            is_processed=False,
        ))
    await session.flush()

    for i, priority in enumerate((1, 2, 3)):
        result = await session.execute(
            select(EightKEvent).where(EightKEvent.id == ids[i])
        )
        fetched = result.scalar_one()
        assert fetched.priority == priority


@pytest.mark.asyncio
async def test_query_eight_k_by_entity_and_date(session):
    """Create multiple 8-K events, query by entity + date range."""
    entity = await _seed_entity(session)
    for day in (1, 10, 20, 28):
        session.add(EightKEvent(
            entity_id=entity.entity_id,
            filing_date=date(2025, 6, day),
            item_number="2.02",
            priority=2,
            is_processed=False,
        ))
    await session.flush()

    result = await session.execute(
        select(EightKEvent)
        .where(EightKEvent.entity_id == entity.entity_id)
        .where(EightKEvent.filing_date >= date(2025, 6, 5))
        .where(EightKEvent.filing_date <= date(2025, 6, 25))
    )
    events = result.scalars().all()
    assert len(events) == 2
    filing_days = sorted(e.filing_date.day for e in events)
    assert filing_days == [10, 20]


@pytest.mark.asyncio
async def test_eight_k_is_processed_flag(session):
    """Default is_processed=False, update to True."""
    entity = await _seed_entity(session)
    eid = uuid.uuid4()
    event = EightKEvent(
        id=eid,
        entity_id=entity.entity_id,
        filing_date=date(2025, 7, 1),
        item_number="5.02",
        priority=1,
    )
    session.add(event)
    await session.flush()

    result = await session.execute(
        select(EightKEvent).where(EightKEvent.id == eid)
    )
    fetched = result.scalar_one()
    assert fetched.is_processed is False

    fetched.is_processed = True
    await session.flush()

    result2 = await session.execute(
        select(EightKEvent).where(EightKEvent.id == eid)
    )
    updated = result2.scalar_one()
    assert updated.is_processed is True
