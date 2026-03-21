"""Tests for Custom Classifications API endpoints."""

import uuid

import pytest

from src.models.auth import User
from src.models.custom_classifications import ClassificationMember, CustomClassification
from src.models.entity import Entity


@pytest.mark.asyncio
async def test_create_classification(client, session):
    """Test creating a classification via POST."""
    user_id = uuid.uuid4()
    session.add(User(
        user_id=user_id, username="apiuser1", email="a1@test.com",
        hashed_password="x",
    ))
    await session.flush()

    response = await client.post(
        "/v1/classifications",
        json={"name": "My Watchlist", "description": "Top picks"},
        params={"user_id": str(user_id)},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "My Watchlist"


@pytest.mark.asyncio
async def test_list_classifications_empty(client):
    """Test listing classifications when DB is empty."""
    response = await client.get("/v1/classifications")
    assert response.status_code == 200
    assert response.json()["data"] == []


@pytest.mark.asyncio
async def test_list_classifications(client, session):
    """Test listing classifications."""
    user_id = uuid.uuid4()
    session.add(User(
        user_id=user_id, username="apiuser2", email="a2@test.com",
        hashed_password="x",
    ))
    await session.flush()

    for name in ["List A", "List B"]:
        session.add(CustomClassification(
            classification_id=uuid.uuid4(), user_id=user_id, name=name,
        ))
    await session.flush()

    response = await client.get("/v1/classifications")
    assert response.status_code == 200
    assert response.json()["meta"]["total_count"] == 2


@pytest.mark.asyncio
async def test_list_classifications_filter_user(client, session):
    """Test filtering classifications by user."""
    u1 = uuid.uuid4()
    u2 = uuid.uuid4()
    session.add(User(user_id=u1, username="u_a", email="ua@test.com", hashed_password="x"))
    session.add(User(user_id=u2, username="u_b", email="ub@test.com", hashed_password="x"))
    await session.flush()

    session.add(CustomClassification(
        classification_id=uuid.uuid4(), user_id=u1, name="User1 List",
    ))
    session.add(CustomClassification(
        classification_id=uuid.uuid4(), user_id=u2, name="User2 List",
    ))
    await session.flush()

    response = await client.get("/v1/classifications", params={"user_id": str(u1)})
    assert response.status_code == 200
    assert response.json()["meta"]["total_count"] == 1


@pytest.mark.asyncio
async def test_get_classification_not_found(client):
    """Test 404 for non-existent classification."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/v1/classifications/{fake_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_classification(client, session):
    """Test fetching a single classification."""
    user_id = uuid.uuid4()
    session.add(User(
        user_id=user_id, username="apiuser3", email="a3@test.com",
        hashed_password="x",
    ))
    await session.flush()

    cid = uuid.uuid4()
    session.add(CustomClassification(
        classification_id=cid, user_id=user_id, name="Fetch Me",
    ))
    await session.flush()

    response = await client.get(f"/v1/classifications/{cid}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Fetch Me"


@pytest.mark.asyncio
async def test_add_member(client, session):
    """Test adding a member to a classification."""
    user_id = uuid.uuid4()
    session.add(User(
        user_id=user_id, username="apiuser4", email="a4@test.com",
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
        classification_id=cid, user_id=user_id, name="Add Member",
    ))
    await session.flush()

    response = await client.put(
        f"/v1/classifications/{cid}/members",
        json={"entity_id": str(entity_id)},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["members"]) == 1


@pytest.mark.asyncio
async def test_add_member_not_found(client):
    """Test adding member to non-existent classification."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.put(
        f"/v1/classifications/{fake_id}/members",
        json={"entity_id": "00000000-0000-0000-0000-000000000001"},
    )
    assert response.status_code == 404
