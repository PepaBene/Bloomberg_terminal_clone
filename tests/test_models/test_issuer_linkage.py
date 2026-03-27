"""Tests for Entity issuer linkage columns (D11 FI Supplement P9)."""

import uuid

import pytest
from sqlalchemy import select

from src.models.entity import Entity


# ── Helpers ──────────────────────────────────────────────────────────


def _make_entity(session, **overrides):
    """Helper to create and flush a test entity."""
    defaults = {
        "entity_id": uuid.uuid4(),
        "entity_type": "CORPORATION",
        "legal_name": "Issuer Linkage Test Corp",
        "status": "ACTIVE",
        "source": "TEST",
        "confidence_score": 0.99,
    }
    defaults.update(overrides)
    entity = Entity(**defaults)
    session.add(entity)
    return entity


# ── Tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_entity_financing_subsidiary_default(session):
    """Default is_financing_subsidiary should be False."""
    entity = _make_entity(session, legal_name="Default Sub Test Corp")
    await session.flush()

    result = await session.execute(
        select(Entity).where(Entity.entity_id == entity.entity_id)
    )
    fetched = result.scalar_one()
    assert fetched.is_financing_subsidiary is False


@pytest.mark.asyncio
async def test_entity_set_financing_subsidiary(session):
    """Setting is_financing_subsidiary to True should persist."""
    entity = _make_entity(
        session,
        legal_name="Apple Capital LLC P9",
        is_financing_subsidiary=True,
    )
    await session.flush()

    result = await session.execute(
        select(Entity).where(Entity.entity_id == entity.entity_id)
    )
    fetched = result.scalar_one()
    assert fetched.is_financing_subsidiary is True


@pytest.mark.asyncio
async def test_entity_financing_parent_link(session):
    """Set financing_parent_id to another entity's ID."""
    parent = _make_entity(session, legal_name="Parent Corp P9")
    await session.flush()

    child = _make_entity(
        session,
        legal_name="Parent Capital LLC P9",
        is_financing_subsidiary=True,
        financing_parent_id=parent.entity_id,
    )
    await session.flush()

    result = await session.execute(
        select(Entity).where(Entity.entity_id == child.entity_id)
    )
    fetched = result.scalar_one()
    assert fetched.financing_parent_id == parent.entity_id


@pytest.mark.asyncio
async def test_entity_financing_parent_null(session):
    """financing_parent_id should be nullable."""
    entity = _make_entity(session, legal_name="No Parent Corp P9")
    await session.flush()

    result = await session.execute(
        select(Entity).where(Entity.entity_id == entity.entity_id)
    )
    fetched = result.scalar_one()
    assert fetched.financing_parent_id is None


@pytest.mark.asyncio
async def test_subsidiary_query(session):
    """Filter entities where is_financing_subsidiary=True."""
    parent = _make_entity(session, legal_name="Query Parent Corp P9")
    sub1 = _make_entity(
        session,
        legal_name="Query Capital LLC P9",
        is_financing_subsidiary=True,
    )
    sub2 = _make_entity(
        session,
        legal_name="Query Funding Corp P9",
        is_financing_subsidiary=True,
    )
    await session.flush()

    result = await session.execute(
        select(Entity).where(
            Entity.is_financing_subsidiary == True,  # noqa: E712
            Entity.entity_id.in_([parent.entity_id, sub1.entity_id, sub2.entity_id]),
        )
    )
    subs = result.scalars().all()
    sub_ids = {s.entity_id for s in subs}
    assert sub1.entity_id in sub_ids
    assert sub2.entity_id in sub_ids
    assert parent.entity_id not in sub_ids


@pytest.mark.asyncio
async def test_parent_child_relationship(session):
    """Create parent + child, query child's parent."""
    parent = _make_entity(session, legal_name="Hierarchy Parent Corp P9")
    await session.flush()

    child = _make_entity(
        session,
        legal_name="Hierarchy Capital LLC P9",
        is_financing_subsidiary=True,
        financing_parent_id=parent.entity_id,
    )
    await session.flush()

    # Query the child and verify parent link
    result = await session.execute(
        select(Entity).where(Entity.entity_id == child.entity_id)
    )
    fetched_child = result.scalar_one()
    assert fetched_child.financing_parent_id == parent.entity_id
    assert fetched_child.is_financing_subsidiary is True

    # Query parent to confirm it's not a subsidiary
    result = await session.execute(
        select(Entity).where(Entity.entity_id == parent.entity_id)
    )
    fetched_parent = result.scalar_one()
    assert fetched_parent.is_financing_subsidiary is False
    assert fetched_parent.financing_parent_id is None
