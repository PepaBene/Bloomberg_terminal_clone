"""Tests for Point-in-Time temporal queries."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.entity import Entity, EntityHistory
from src.temporal.pit import (
    get_current_revision,
    get_entity_as_of,
    get_entity_revisions,
    record_entity_history,
)


def _make_entity(**overrides) -> Entity:
    """Create an Entity instance with sensible defaults."""
    defaults = dict(
        entity_id=uuid.uuid4(),
        entity_type="CORPORATION",
        legal_name="Test Corp",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
        confidence_score=0.95,
    )
    defaults.update(overrides)
    return Entity(**defaults)


# ── record_entity_history ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_record_entity_history_creates_snapshot(session: AsyncSession):
    """Recording history should create an EntityHistory row matching the entity."""
    entity = _make_entity()
    session.add(entity)
    await session.flush()

    history = await record_entity_history(entity, session)

    assert history is not None
    assert history.entity_id == entity.entity_id
    assert history.legal_name == entity.legal_name
    assert history.entity_type == entity.entity_type
    assert history.status == entity.status
    assert history.revision_number == 0
    assert history.valid_to is None
    assert history.valid_from is not None


@pytest.mark.asyncio
async def test_record_entity_history_increments_revision(session: AsyncSession):
    """Each call to record_entity_history should bump the revision number."""
    entity = _make_entity()
    session.add(entity)
    await session.flush()

    h0 = await record_entity_history(entity, session)
    assert h0.revision_number == 0

    # Simulate an entity change
    entity.legal_name = "Test Corp Updated"
    await session.flush()

    h1 = await record_entity_history(entity, session)
    assert h1.revision_number == 1
    assert h1.legal_name == "Test Corp Updated"


@pytest.mark.asyncio
async def test_record_entity_history_closes_previous(session: AsyncSession):
    """Recording a new history snapshot should set valid_to on the previous one."""
    entity = _make_entity()
    session.add(entity)
    await session.flush()

    h0 = await record_entity_history(entity, session)
    assert h0.valid_to is None

    h1 = await record_entity_history(entity, session)

    # Refresh h0 to pick up the valid_to that was set by the second call
    await session.refresh(h0)
    assert h0.valid_to is not None
    assert h1.valid_to is None


# ── get_entity_as_of ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_entity_as_of_returns_correct_version(session: AsyncSession):
    """Querying as-of a timestamp should return the version that was active then."""
    entity = _make_entity()
    session.add(entity)
    await session.flush()

    h0 = await record_entity_history(entity, session)

    # Change entity and record again
    entity.legal_name = "Renamed Corp"
    await session.flush()
    h1 = await record_entity_history(entity, session)

    # Query as-of a time between h0.valid_from and h0.valid_to
    await session.refresh(h0)
    midpoint = h0.valid_from + timedelta(microseconds=1)
    result = await get_entity_as_of(entity.entity_id, midpoint, session)

    assert result is not None
    assert result.legal_name == "Test Corp"

    # Query as-of now should return the latest version
    result_now = await get_entity_as_of(
        entity.entity_id, datetime.now(timezone.utc), session
    )
    assert result_now is not None
    assert result_now.legal_name == "Renamed Corp"


@pytest.mark.asyncio
async def test_get_entity_as_of_returns_none_for_future_entity(session: AsyncSession):
    """Querying before the entity existed should return None."""
    entity = _make_entity()
    session.add(entity)
    await session.flush()

    await record_entity_history(entity, session)

    # Query as-of the distant past
    distant_past = datetime(2000, 1, 1, tzinfo=timezone.utc)
    result = await get_entity_as_of(entity.entity_id, distant_past, session)
    assert result is None


@pytest.mark.asyncio
async def test_get_entity_as_of_unknown_entity(session: AsyncSession):
    """Querying a nonexistent entity_id should return None."""
    result = await get_entity_as_of(
        uuid.uuid4(), datetime.now(timezone.utc), session
    )
    assert result is None


# ── get_entity_revisions ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_entity_revisions_returns_all(session: AsyncSession):
    """get_entity_revisions should return every history snapshot in order."""
    entity = _make_entity()
    session.add(entity)
    await session.flush()

    await record_entity_history(entity, session)
    entity.legal_name = "V2"
    await session.flush()
    await record_entity_history(entity, session)
    entity.legal_name = "V3"
    await session.flush()
    await record_entity_history(entity, session)

    revisions = await get_entity_revisions(entity.entity_id, session)
    assert len(revisions) == 3
    assert [r.revision_number for r in revisions] == [0, 1, 2]
    assert revisions[0].legal_name == "Test Corp"
    assert revisions[1].legal_name == "V2"
    assert revisions[2].legal_name == "V3"


@pytest.mark.asyncio
async def test_get_entity_revisions_empty(session: AsyncSession):
    """Querying revisions for a nonexistent entity should return an empty list."""
    revisions = await get_entity_revisions(uuid.uuid4(), session)
    assert revisions == []


# ── get_current_revision ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_current_revision(session: AsyncSession):
    """get_current_revision should return the record with valid_to IS NULL."""
    entity = _make_entity()
    session.add(entity)
    await session.flush()

    await record_entity_history(entity, session)
    entity.legal_name = "Latest Name"
    await session.flush()
    await record_entity_history(entity, session)

    current = await get_current_revision(entity.entity_id, session)
    assert current is not None
    assert current.legal_name == "Latest Name"
    assert current.valid_to is None


@pytest.mark.asyncio
async def test_get_current_revision_none(session: AsyncSession):
    """get_current_revision for an unknown entity should return None."""
    result = await get_current_revision(uuid.uuid4(), session)
    assert result is None
