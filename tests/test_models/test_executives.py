"""Tests for executive/director models."""

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from src.models.entity import Entity
from src.models.executives import Executive, ExecutiveRole


@pytest.mark.asyncio
async def test_create_executive(session):
    """Test creating an executive."""
    exec_id = uuid.uuid4()
    executive = Executive(
        executive_id=exec_id,
        person_name="Tim Cook",
        age=64,
        total_compensation=98734000.00,
        base_salary=3000000.00,
        stock_awards=75000000.00,
        education=["Auburn University", "Duke University MBA"],
    )
    session.add(executive)
    await session.flush()

    result = await session.execute(
        select(Executive).where(Executive.executive_id == exec_id)
    )
    fetched = result.scalar_one()
    assert fetched.person_name == "Tim Cook"
    assert float(fetched.total_compensation) == 98734000.00


@pytest.mark.asyncio
async def test_create_executive_role(session):
    """Test creating an executive role linked to an entity."""
    entity_id = uuid.uuid4()
    session.add(Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name="Apple Inc.", status="ACTIVE", source="SEC_EDGAR",
    ))
    exec_id = uuid.uuid4()
    session.add(Executive(executive_id=exec_id, person_name="Tim Cook"))
    await session.flush()

    role = ExecutiveRole(
        role_id=uuid.uuid4(),
        executive_id=exec_id,
        entity_id=entity_id,
        title="CEO",
        role_type="EXECUTIVE",
        start_date=date(2011, 8, 24),
    )
    session.add(role)
    await session.flush()

    result = await session.execute(
        select(ExecutiveRole).where(ExecutiveRole.executive_id == exec_id)
    )
    fetched = result.scalar_one()
    assert fetched.title == "CEO"
    assert fetched.role_type == "EXECUTIVE"


@pytest.mark.asyncio
async def test_executive_roles_relationship(session):
    """Test that roles are loaded via the executive relationship."""
    entity_id = uuid.uuid4()
    session.add(Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name="Multi-Role Corp", status="ACTIVE", source="SEC_EDGAR",
    ))
    exec_id = uuid.uuid4()
    session.add(Executive(executive_id=exec_id, person_name="Jane Doe"))
    await session.flush()

    session.add(ExecutiveRole(
        role_id=uuid.uuid4(), executive_id=exec_id,
        entity_id=entity_id, title="CEO", role_type="EXECUTIVE",
    ))
    session.add(ExecutiveRole(
        role_id=uuid.uuid4(), executive_id=exec_id,
        entity_id=entity_id, title="Director", role_type="DIRECTOR",
    ))
    await session.flush()

    result = await session.execute(
        select(Executive).where(Executive.executive_id == exec_id)
    )
    fetched = result.scalar_one()
    assert len(fetched.roles) == 2
    titles = {r.title for r in fetched.roles}
    assert titles == {"CEO", "Director"}


@pytest.mark.asyncio
async def test_list_executives_by_entity(session):
    """Test querying executives by entity."""
    entity_id = uuid.uuid4()
    session.add(Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name="Team Corp", status="ACTIVE", source="SEC_EDGAR",
    ))
    await session.flush()

    for name in ["Alice CEO", "Bob CFO", "Charlie Director"]:
        exec_id = uuid.uuid4()
        session.add(Executive(executive_id=exec_id, person_name=name))
        await session.flush()
        session.add(ExecutiveRole(
            role_id=uuid.uuid4(), executive_id=exec_id,
            entity_id=entity_id, title=name.split()[1],
            role_type="EXECUTIVE" if "Director" not in name else "DIRECTOR",
        ))
    await session.flush()

    result = await session.execute(
        select(ExecutiveRole).where(ExecutiveRole.entity_id == entity_id)
    )
    roles = result.scalars().all()
    assert len(roles) == 3
