"""Tests for credit rating FI extension models (D11 FI Supplement P5)."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.models.credit_rating import CreditRatingEvent, CurrentCreditRating
from src.models.entity import Entity


def _make_entity(session, **overrides):
    """Helper to create and flush a test entity."""
    defaults = {
        "entity_id": uuid.uuid4(),
        "entity_type": "CORPORATION",
        "legal_name": "Test Corp FI",
        "status": "ACTIVE",
        "source": "TEST",
        "confidence_score": 0.99,
    }
    defaults.update(overrides)
    entity = Entity(**defaults)
    session.add(entity)
    return entity


@pytest.mark.asyncio
async def test_credit_rating_event_new_columns(session):
    """Test creating a credit rating event with numeric, notches, and fallen_angel fields."""
    entity = _make_entity(session)
    await session.flush()

    event = CreditRatingEvent(
        event_id=uuid.uuid4(),
        entity_id=entity.entity_id,
        agency="SP",
        new_rating="BB+",
        old_rating="BBB-",
        direction="DOWNGRADE",
        event_date=date(2026, 3, 1),
        new_rating_numeric=11,
        old_rating_numeric=10,
        notches_changed=-1,
        is_fallen_angel=True,
        is_rising_star=False,
    )
    session.add(event)
    await session.flush()

    result = await session.execute(
        select(CreditRatingEvent).where(CreditRatingEvent.event_id == event.event_id)
    )
    fetched = result.scalar_one()
    assert fetched.new_rating_numeric == 11
    assert fetched.old_rating_numeric == 10
    assert fetched.notches_changed == -1
    assert fetched.is_fallen_angel is True
    assert fetched.is_rising_star is False


@pytest.mark.asyncio
async def test_fallen_angel_flag(session):
    """Test setting the is_fallen_angel flag."""
    entity = _make_entity(session, legal_name="Fallen Angel Corp")
    await session.flush()

    event = CreditRatingEvent(
        event_id=uuid.uuid4(),
        entity_id=entity.entity_id,
        agency="MOODYS",
        new_rating="Ba1",
        old_rating="Baa3",
        direction="DOWNGRADE",
        event_date=date(2026, 2, 15),
        is_fallen_angel=True,
        is_rising_star=False,
    )
    session.add(event)
    await session.flush()

    result = await session.execute(
        select(CreditRatingEvent).where(CreditRatingEvent.event_id == event.event_id)
    )
    assert result.scalar_one().is_fallen_angel is True


@pytest.mark.asyncio
async def test_rising_star_flag(session):
    """Test setting the is_rising_star flag."""
    entity = _make_entity(session, legal_name="Rising Star Corp")
    await session.flush()

    event = CreditRatingEvent(
        event_id=uuid.uuid4(),
        entity_id=entity.entity_id,
        agency="SP",
        new_rating="BBB-",
        old_rating="BB+",
        direction="UPGRADE",
        event_date=date(2026, 2, 20),
        is_fallen_angel=False,
        is_rising_star=True,
    )
    session.add(event)
    await session.flush()

    result = await session.execute(
        select(CreditRatingEvent).where(CreditRatingEvent.event_id == event.event_id)
    )
    assert result.scalar_one().is_rising_star is True


@pytest.mark.asyncio
async def test_watch_status(session):
    """Test watch_status field on CreditRatingEvent."""
    entity = _make_entity(session, legal_name="Watch Corp")
    await session.flush()

    event = CreditRatingEvent(
        event_id=uuid.uuid4(),
        entity_id=entity.entity_id,
        agency="FITCH",
        new_rating="A-",
        direction="AFFIRM",
        event_date=date(2026, 3, 5),
        watch_status="NEGATIVE",
        is_fallen_angel=False,
        is_rising_star=False,
    )
    session.add(event)
    await session.flush()

    result = await session.execute(
        select(CreditRatingEvent).where(CreditRatingEvent.event_id == event.event_id)
    )
    assert result.scalar_one().watch_status == "NEGATIVE"


@pytest.mark.asyncio
async def test_market_context_fields(session):
    """Test entity_stock_price_at_event and bond_spread_at_event fields."""
    entity = _make_entity(session, legal_name="Market Context Corp")
    await session.flush()

    event = CreditRatingEvent(
        event_id=uuid.uuid4(),
        entity_id=entity.entity_id,
        agency="SP",
        new_rating="BBB",
        direction="DOWNGRADE",
        event_date=date(2026, 3, 10),
        entity_stock_price_at_event=145.123456,
        bond_spread_at_event=250.50,
        is_fallen_angel=False,
        is_rising_star=False,
    )
    session.add(event)
    await session.flush()

    result = await session.execute(
        select(CreditRatingEvent).where(CreditRatingEvent.event_id == event.event_id)
    )
    fetched = result.scalar_one()
    # Compare as floats since Numeric may return Decimal
    assert float(fetched.entity_stock_price_at_event) == pytest.approx(145.123456, rel=1e-4)
    assert float(fetched.bond_spread_at_event) == pytest.approx(250.50, rel=1e-2)


@pytest.mark.asyncio
async def test_current_credit_rating_create(session):
    """Test creating a CurrentCreditRating record."""
    entity = _make_entity(session, legal_name="Current Rating Corp")
    await session.flush()

    rating = CurrentCreditRating(
        id=uuid.uuid4(),
        entity_id=entity.entity_id,
        agency="SP",
        rating_type="LONG_TERM",
        current_rating="BBB+",
        current_rating_numeric=8,
        outlook="STABLE",
        watch_status=None,
        last_action_date=date(2026, 3, 1),
        last_action_type="AFFIRM",
        is_investment_grade=True,
    )
    session.add(rating)
    await session.flush()

    result = await session.execute(
        select(CurrentCreditRating).where(CurrentCreditRating.id == rating.id)
    )
    fetched = result.scalar_one()
    assert fetched.current_rating == "BBB+"
    assert fetched.current_rating_numeric == 8
    assert fetched.is_investment_grade is True
    assert fetched.agency == "SP"


@pytest.mark.asyncio
async def test_current_credit_rating_unique(session):
    """Duplicate (entity_id, agency, rating_type) should raise an error."""
    entity = _make_entity(session, legal_name="Unique Constraint Corp")
    await session.flush()

    for _ in range(2):
        session.add(CurrentCreditRating(
            id=uuid.uuid4(),
            entity_id=entity.entity_id,
            agency="SP",
            rating_type="LONG_TERM",
            current_rating="A-",
            is_investment_grade=True,
        ))

    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_current_credit_rating_ig_flag(session):
    """Test is_investment_grade flag on CurrentCreditRating."""
    entity = _make_entity(session, legal_name="IG Flag Corp")
    await session.flush()

    # Investment grade
    ig_rating = CurrentCreditRating(
        id=uuid.uuid4(),
        entity_id=entity.entity_id,
        agency="MOODYS",
        rating_type="LONG_TERM",
        current_rating="Baa3",
        current_rating_numeric=10,
        is_investment_grade=True,
    )
    session.add(ig_rating)
    await session.flush()

    result = await session.execute(
        select(CurrentCreditRating).where(CurrentCreditRating.id == ig_rating.id)
    )
    assert result.scalar_one().is_investment_grade is True

    # High yield
    hy_rating = CurrentCreditRating(
        id=uuid.uuid4(),
        entity_id=entity.entity_id,
        agency="FITCH",
        rating_type="LONG_TERM",
        current_rating="BB+",
        current_rating_numeric=11,
        is_investment_grade=False,
    )
    session.add(hy_rating)
    await session.flush()

    result = await session.execute(
        select(CurrentCreditRating).where(CurrentCreditRating.id == hy_rating.id)
    )
    assert result.scalar_one().is_investment_grade is False
