"""Tests for entity master models."""

import uuid

import pytest
from sqlalchemy import select

from src.models.entity import (
    Entity,
    EntityHistory,
    EntityIdentifier,
    EntityName,
    EntityRelationship,
    ResolutionQueue,
)


@pytest.mark.asyncio
async def test_create_entity(session, entity_data):
    """Test creating an entity with all fields."""
    entity = Entity(**entity_data)
    session.add(entity)
    await session.flush()

    result = await session.execute(
        select(Entity).where(Entity.entity_id == entity_data["entity_id"])
    )
    fetched = result.scalar_one()
    assert fetched.legal_name == "Apple Inc."
    assert fetched.entity_type == "PUBLIC_COMPANY"
    assert fetched.status == "ACTIVE"
    assert fetched.fiscal_year_end == "09-30"


@pytest.mark.asyncio
async def test_entity_identifier_unique_constraint(session, entity_data):
    """Test that identifier type+value must be unique."""
    entity = Entity(**entity_data)
    session.add(entity)
    await session.flush()

    ident1 = EntityIdentifier(
        id=uuid.uuid4(),
        entity_id=entity_data["entity_id"],
        identifier_type="CIK",
        identifier_value="0000320193",
        source="SEC_EDGAR",
        is_primary=True,
    )
    session.add(ident1)
    await session.flush()

    # Verify it was created
    result = await session.execute(
        select(EntityIdentifier).where(
            EntityIdentifier.identifier_type == "CIK",
            EntityIdentifier.identifier_value == "0000320193",
        )
    )
    assert result.scalar_one() is not None


@pytest.mark.asyncio
async def test_entity_names(session, entity_data):
    """Test creating multiple name records for an entity."""
    entity = Entity(**entity_data)
    session.add(entity)
    await session.flush()

    names = [
        EntityName(
            id=uuid.uuid4(),
            entity_id=entity_data["entity_id"],
            name_type="LEGAL",
            name_value="Apple Inc.",
            source="SEC_EDGAR",
        ),
        EntityName(
            id=uuid.uuid4(),
            entity_id=entity_data["entity_id"],
            name_type="PREVIOUS",
            name_value="Apple Computer, Inc.",
            source="SEC_EDGAR",
        ),
        EntityName(
            id=uuid.uuid4(),
            entity_id=entity_data["entity_id"],
            name_type="TRADING",
            name_value="AAPL",
            source="SEC_EDGAR",
        ),
    ]
    for n in names:
        session.add(n)
    await session.flush()

    result = await session.execute(
        select(EntityName).where(
            EntityName.entity_id == entity_data["entity_id"]
        )
    )
    fetched = result.scalars().all()
    assert len(fetched) == 3


@pytest.mark.asyncio
async def test_entity_relationship(session, entity_data):
    """Test creating an entity relationship."""
    # Create parent and child entities
    parent_id = uuid.uuid4()
    parent = Entity(
        entity_id=parent_id,
        entity_type="PUBLIC_COMPANY",
        legal_name="Alphabet Inc.",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    child_id = uuid.uuid4()
    child = Entity(
        entity_id=child_id,
        entity_type="PUBLIC_COMPANY",
        legal_name="Google LLC",
        status="ACTIVE",
        source="SEC_EDGAR",
        ultimate_parent_id=parent_id,
        immediate_parent_id=parent_id,
    )
    session.add(parent)
    session.add(child)
    await session.flush()

    rel = EntityRelationship(
        relationship_id=uuid.uuid4(),
        source_entity_id=parent_id,
        target_entity_id=child_id,
        relationship_type="PARENT_OF",
        ownership_percentage=100.0,
        source="SEC_EDGAR",
    )
    session.add(rel)
    await session.flush()

    result = await session.execute(
        select(EntityRelationship).where(
            EntityRelationship.source_entity_id == parent_id
        )
    )
    fetched = result.scalar_one()
    assert fetched.relationship_type == "PARENT_OF"
    assert float(fetched.ownership_percentage) == 100.0


@pytest.mark.asyncio
async def test_entity_history(session, entity_data):
    """Test entity history (PIT) records."""
    from datetime import datetime, timezone

    entity = Entity(**entity_data)
    session.add(entity)
    await session.flush()

    now = datetime.now(timezone.utc)
    history = EntityHistory(
        history_id=uuid.uuid4(),
        entity_id=entity_data["entity_id"],
        entity_type="PUBLIC_COMPANY",
        legal_name="Apple Inc.",
        status="ACTIVE",
        source="SEC_EDGAR",
        valid_from=now,
        revision_number=0,
    )
    session.add(history)
    await session.flush()

    result = await session.execute(
        select(EntityHistory).where(
            EntityHistory.entity_id == entity_data["entity_id"]
        )
    )
    fetched = result.scalar_one()
    assert fetched.revision_number == 0
    assert fetched.valid_to is None
