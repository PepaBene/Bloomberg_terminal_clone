"""Tests for custom classification models."""

import uuid

import pytest
from sqlalchemy import select

from src.models.auth import User
from src.models.custom_classifications import ClassificationMember, CustomClassification
from src.models.entity import Entity


@pytest.mark.asyncio
async def test_create_classification(session):
    """Test creating a custom classification."""
    user_id = uuid.uuid4()
    session.add(User(
        user_id=user_id, username="testuser", email="t@test.com",
        hashed_password="x",
    ))
    await session.flush()

    cid = uuid.uuid4()
    session.add(CustomClassification(
        classification_id=cid, user_id=user_id,
        name="My Watchlist", description="Top picks", visibility="PRIVATE",
    ))
    await session.flush()

    result = await session.execute(
        select(CustomClassification).where(CustomClassification.classification_id == cid)
    )
    fetched = result.scalar_one()
    assert fetched.name == "My Watchlist"
    assert fetched.visibility == "PRIVATE"


@pytest.mark.asyncio
async def test_add_member(session):
    """Test adding a member entity to a classification."""
    user_id = uuid.uuid4()
    session.add(User(
        user_id=user_id, username="testuser2", email="t2@test.com",
        hashed_password="x",
    ))
    entity_id = uuid.uuid4()
    session.add(Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name="Member Corp", status="ACTIVE", source="SEC_EDGAR",
    ))
    await session.flush()

    cid = uuid.uuid4()
    session.add(CustomClassification(
        classification_id=cid, user_id=user_id,
        name="Sector List",
    ))
    await session.flush()

    mid = uuid.uuid4()
    session.add(ClassificationMember(
        id=mid, classification_id=cid, entity_id=entity_id,
        tags={"sector": "tech"},
    ))
    await session.flush()

    result = await session.execute(
        select(ClassificationMember).where(ClassificationMember.id == mid)
    )
    fetched = result.scalar_one()
    assert fetched.entity_id == entity_id


@pytest.mark.asyncio
async def test_classification_members_relationship(session):
    """Test that members load via the classification relationship."""
    user_id = uuid.uuid4()
    session.add(User(
        user_id=user_id, username="testuser3", email="t3@test.com",
        hashed_password="x",
    ))
    await session.flush()

    entities = []
    for name in ["A Corp", "B Corp"]:
        eid = uuid.uuid4()
        session.add(Entity(
            entity_id=eid, entity_type="PUBLIC_COMPANY",
            legal_name=name, status="ACTIVE", source="SEC_EDGAR",
        ))
        entities.append(eid)
    await session.flush()

    cid = uuid.uuid4()
    session.add(CustomClassification(
        classification_id=cid, user_id=user_id, name="Pair Trade",
    ))
    await session.flush()

    for eid in entities:
        session.add(ClassificationMember(
            id=uuid.uuid4(), classification_id=cid, entity_id=eid,
        ))
    await session.flush()

    result = await session.execute(
        select(CustomClassification).where(CustomClassification.classification_id == cid)
    )
    fetched = result.scalar_one()
    assert len(fetched.members) == 2


@pytest.mark.asyncio
async def test_list_classifications_by_user(session):
    """Test querying classifications by user."""
    user_id = uuid.uuid4()
    session.add(User(
        user_id=user_id, username="testuser4", email="t4@test.com",
        hashed_password="x",
    ))
    await session.flush()

    for name in ["List A", "List B", "List C"]:
        session.add(CustomClassification(
            classification_id=uuid.uuid4(), user_id=user_id, name=name,
        ))
    await session.flush()

    result = await session.execute(
        select(CustomClassification).where(CustomClassification.user_id == user_id)
    )
    rows = result.scalars().all()
    assert len(rows) == 3
