"""Tests for the SEC EDGAR credit ratings connector.

Covers the pure agency/direction/outlook/rating detectors and the DB load,
including the security-level ``CreditRating`` upsert this connector now
performs for an entity's fixed-income securities (Pillar 1 Open Items #4 —
``CreditRating`` at the security level previously had zero writers).
"""

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from src.ingestion.edgar_credit_ratings import (
    EdgarCreditRatingConnector,
    detect_agency,
    detect_direction,
    detect_outlook,
    extract_sp_rating,
)


def test_detect_agency_and_direction():
    text = "S&P Global Ratings downgraded the Company's senior notes to BBB with a negative outlook."
    assert detect_agency(text) == "SP"
    assert detect_direction(text) == "DOWNGRADE"
    assert detect_outlook(text) == "NEGATIVE"
    assert extract_sp_rating(text) == "BBB"


@pytest.mark.asyncio
async def test_load_writes_entity_event_and_security_ratings(session):
    from src.models.credit_rating import CreditRatingEvent
    from src.models.entity import Entity, EntityIdentifier
    from src.models.security import CreditRating as SecurityCreditRating
    from src.models.security import Security

    entity_id = uuid.uuid4()
    session.add(Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name="MegaCorp Inc.", status="ACTIVE", source="TEST",
    ))
    session.add(EntityIdentifier(
        id=uuid.uuid4(), entity_id=entity_id,
        identifier_type="CIK", identifier_value="0009000000",
    ))
    # A fixed-income security issued by this entity, and one equity security
    # that must NOT receive a security-level credit rating.
    fi_security_id = uuid.uuid4()
    session.add(Security(
        security_id=fi_security_id, security_type="CORPORATE_BOND",
        issuer_entity_id=entity_id, name="MegaCorp 4.875% Notes due 2030",
        status="ACTIVE", asset_class="FIXED_INCOME",
    ))
    equity_security_id = uuid.uuid4()
    session.add(Security(
        security_id=equity_security_id, security_type="COMMON_STOCK",
        issuer_entity_id=entity_id, name="MegaCorp Common Stock",
        status="ACTIVE", asset_class="EQUITY",
    ))
    await session.flush()

    conn = EdgarCreditRatingConnector()
    rec = {
        "cik": "0009000000",
        "agency": "SP",
        "event_date": "2026-03-01",
        "new_rating": "BBB",
        "direction": "DOWNGRADE",
        "outlook": "NEGATIVE",
        "source_type": "8K_FILING",
        "source_url": "https://www.sec.gov/Archives/example.htm",
    }
    stats = await conn.load([rec], session)
    assert stats["inserted"] == 1
    assert stats["security_ratings_inserted"] == 1
    await session.flush()

    events = (await session.execute(select(CreditRatingEvent))).scalars().all()
    assert len(events) == 1
    assert events[0].new_rating == "BBB"

    sec_ratings = (await session.execute(select(SecurityCreditRating))).scalars().all()
    assert len(sec_ratings) == 1
    assert sec_ratings[0].security_id == fi_security_id
    assert sec_ratings[0].rating == "BBB"
    assert sec_ratings[0].agency == "SP"
    assert sec_ratings[0].rating_date == date(2026, 3, 1)


@pytest.mark.asyncio
async def test_load_skips_security_rating_when_no_rating_extracted(session):
    from src.models.entity import Entity, EntityIdentifier
    from src.models.security import CreditRating as SecurityCreditRating
    from src.models.security import Security

    entity_id = uuid.uuid4()
    session.add(Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name="MegaCorp Inc.", status="ACTIVE", source="TEST",
    ))
    session.add(EntityIdentifier(
        id=uuid.uuid4(), entity_id=entity_id,
        identifier_type="CIK", identifier_value="0009000000",
    ))
    session.add(Security(
        security_id=uuid.uuid4(), security_type="CORPORATE_BOND",
        issuer_entity_id=entity_id, name="MegaCorp Notes",
        status="ACTIVE", asset_class="FIXED_INCOME",
    ))
    await session.flush()

    conn = EdgarCreditRatingConnector()
    # No new_rating extracted from the filing text — must not fabricate one.
    rec = {
        "cik": "0009000000",
        "agency": "MOODYS",
        "event_date": "2026-03-01",
        "new_rating": None,
    }
    stats = await conn.load([rec], session)
    assert stats["inserted"] == 1
    assert stats["security_ratings_inserted"] == 0
    await session.flush()

    sec_ratings = (await session.execute(select(SecurityCreditRating))).scalars().all()
    assert len(sec_ratings) == 0


@pytest.mark.asyncio
async def test_load_dedupes_security_ratings_on_rerun(session):
    from src.models.entity import Entity, EntityIdentifier
    from src.models.security import CreditRating as SecurityCreditRating
    from src.models.security import Security

    entity_id = uuid.uuid4()
    session.add(Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name="MegaCorp Inc.", status="ACTIVE", source="TEST",
    ))
    session.add(EntityIdentifier(
        id=uuid.uuid4(), entity_id=entity_id,
        identifier_type="CIK", identifier_value="0009000000",
    ))
    session.add(Security(
        security_id=uuid.uuid4(), security_type="CORPORATE_BOND",
        issuer_entity_id=entity_id, name="MegaCorp Notes",
        status="ACTIVE", asset_class="FIXED_INCOME",
    ))
    await session.flush()

    conn = EdgarCreditRatingConnector()
    rec = {"cik": "0009000000", "agency": "SP", "event_date": "2026-03-01", "new_rating": "BBB"}
    await conn.load([rec], session)
    await session.flush()
    stats2 = await conn.load([rec], session)
    await session.flush()

    assert stats2["security_ratings_inserted"] == 0
    sec_ratings = (await session.execute(select(SecurityCreditRating))).scalars().all()
    assert len(sec_ratings) == 1
