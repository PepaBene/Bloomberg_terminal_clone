"""Tests for business relationship models."""

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

from src.models.relationships import BusinessRelationship, RelationshipHistory


@pytest.fixture
def relationship_data():
    """Sample business relationship data."""
    return {
        "relationship_id": uuid.uuid4(),
        "source_entity_id": uuid.uuid4(),
        "target_entity_id": uuid.uuid4(),
        "relationship_type": "MAJOR_CUSTOMER",
        "direction": "OUTBOUND",
        "revenue_percentage": 0.15,
        "is_single_source": False,
        "materiality_score": 75.0,
        "confidence_score": 0.92,
        "extraction_method": "SEC_FILING",
        "effective_date": date(2023, 1, 1),
        "is_active": True,
    }


@pytest.mark.asyncio
async def test_create_business_relationship(session, relationship_data):
    """Test creating a business relationship."""
    rel = BusinessRelationship(**relationship_data)
    session.add(rel)
    await session.flush()

    result = await session.execute(
        select(BusinessRelationship).where(
            BusinessRelationship.relationship_id == relationship_data["relationship_id"]
        )
    )
    fetched = result.scalar_one()
    assert fetched.relationship_type == "MAJOR_CUSTOMER"
    assert fetched.direction == "OUTBOUND"
    assert float(fetched.revenue_percentage) == 0.15
    assert fetched.is_active is True


@pytest.mark.asyncio
async def test_relationship_with_contract(session):
    """Test a relationship with contract details."""
    rel = BusinessRelationship(
        relationship_id=uuid.uuid4(),
        source_entity_id=uuid.uuid4(),
        target_entity_id=uuid.uuid4(),
        relationship_type="CRITICAL_SUPPLIER",
        direction="INBOUND",
        contract_value=5000000.00,
        contract_start_date=date(2023, 6, 1),
        contract_end_date=date(2026, 5, 31),
        is_single_source=True,
        materiality_score=90.0,
        confidence_score=0.98,
        extraction_method="MANUAL",
        is_active=True,
    )
    session.add(rel)
    await session.flush()

    result = await session.execute(
        select(BusinessRelationship).where(
            BusinessRelationship.relationship_id == rel.relationship_id
        )
    )
    fetched = result.scalar_one()
    assert float(fetched.contract_value) == 5000000.00
    assert fetched.is_single_source is True
    assert fetched.contract_start_date == date(2023, 6, 1)


@pytest.mark.asyncio
async def test_relationship_history(session, relationship_data):
    """Test creating relationship history entries."""
    rel = BusinessRelationship(**relationship_data)
    session.add(rel)
    await session.flush()

    history = RelationshipHistory(
        history_id=uuid.uuid4(),
        relationship_id=relationship_data["relationship_id"],
        change_type="UPDATED",
        change_date=date(2024, 6, 1),
        previous_revenue_percentage=0.12,
        new_revenue_percentage=0.15,
        previous_materiality_score=60.0,
        new_materiality_score=75.0,
        source="10-K Filing",
    )
    session.add(history)
    await session.flush()

    result = await session.execute(
        select(RelationshipHistory).where(
            RelationshipHistory.relationship_id == relationship_data["relationship_id"]
        )
    )
    fetched = result.scalar_one()
    assert fetched.change_type == "UPDATED"
    assert float(fetched.previous_revenue_percentage) == 0.12
    assert float(fetched.new_revenue_percentage) == 0.15


@pytest.mark.asyncio
async def test_query_relationships_by_type(session):
    """Test querying relationships by type."""
    source_id = uuid.uuid4()
    types = ["MAJOR_CUSTOMER", "DIRECT_COMPETITOR", "CRITICAL_SUPPLIER"]

    for rtype in types:
        rel = BusinessRelationship(
            relationship_id=uuid.uuid4(),
            source_entity_id=source_id,
            target_entity_id=uuid.uuid4(),
            relationship_type=rtype,
            is_active=True,
        )
        session.add(rel)
    await session.flush()

    result = await session.execute(
        select(BusinessRelationship).where(
            BusinessRelationship.source_entity_id == source_id,
            BusinessRelationship.relationship_type == "DIRECT_COMPETITOR",
        )
    )
    competitors = result.scalars().all()
    assert len(competitors) == 1
    assert competitors[0].relationship_type == "DIRECT_COMPETITOR"


@pytest.mark.asyncio
async def test_inactive_relationship(session):
    """Test creating an inactive (terminated) relationship."""
    rel = BusinessRelationship(
        relationship_id=uuid.uuid4(),
        source_entity_id=uuid.uuid4(),
        target_entity_id=uuid.uuid4(),
        relationship_type="KNOWN_SUPPLIER",
        effective_date=date(2020, 1, 1),
        termination_date=date(2024, 6, 30),
        is_active=False,
    )
    session.add(rel)
    await session.flush()

    result = await session.execute(
        select(BusinessRelationship).where(
            BusinessRelationship.relationship_id == rel.relationship_id
        )
    )
    fetched = result.scalar_one()
    assert fetched.is_active is False
    assert fetched.termination_date == date(2024, 6, 30)
