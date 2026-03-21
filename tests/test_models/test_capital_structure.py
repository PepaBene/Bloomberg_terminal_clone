"""Tests for capital structure models."""

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from src.models.capital_structure import CapitalStructure, DebtTranche
from src.models.entity import Entity


@pytest.mark.asyncio
async def test_create_capital_structure(session):
    """Test creating a capital structure snapshot."""
    entity_id = uuid.uuid4()
    entity = Entity(
        entity_id=entity_id,
        entity_type="PUBLIC_COMPANY",
        legal_name="Test Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()

    cs_id = uuid.uuid4()
    cs = CapitalStructure(
        capital_structure_id=cs_id,
        entity_id=entity_id,
        as_of_date=date(2025, 12, 31),
        total_debt=5000000000.00,
        total_long_term_debt=4000000000.00,
        total_short_term_debt=1000000000.00,
        net_debt=3500000000.00,
        total_capitalization=12000000000.00,
        debt_to_capitalization=0.4167,
        source="SEC_10K",
        extraction_method="XBRL_STRUCTURED",
        confidence_score=0.95,
    )
    session.add(cs)
    await session.flush()

    result = await session.execute(
        select(CapitalStructure).where(CapitalStructure.capital_structure_id == cs_id)
    )
    fetched = result.scalar_one()
    assert fetched.entity_id == entity_id
    assert float(fetched.total_debt) == 5000000000.00
    assert float(fetched.debt_to_capitalization) == pytest.approx(0.4167, abs=0.0001)
    assert fetched.source == "SEC_10K"


@pytest.mark.asyncio
async def test_create_debt_tranche(session):
    """Test creating a debt tranche linked to a capital structure."""
    entity_id = uuid.uuid4()
    entity = Entity(
        entity_id=entity_id,
        entity_type="PUBLIC_COMPANY",
        legal_name="Tranche Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()

    cs_id = uuid.uuid4()
    cs = CapitalStructure(
        capital_structure_id=cs_id,
        entity_id=entity_id,
        as_of_date=date(2025, 12, 31),
        total_debt=2000000000.00,
    )
    session.add(cs)
    await session.flush()

    tranche_id = uuid.uuid4()
    tranche = DebtTranche(
        tranche_id=tranche_id,
        entity_id=entity_id,
        capital_structure_id=cs_id,
        instrument_name="4.875% Senior Notes due 2028",
        instrument_type="SENIOR_UNSECURED_NOTES",
        principal_amount=750000000.00,
        coupon_rate=0.04875,
        coupon_type="FIXED",
        maturity_date=date(2028, 6, 15),
        seniority_rank=1,
        seniority_type="SENIOR_UNSECURED",
        has_financial_covenants=True,
        has_change_of_control=True,
        has_cross_default=False,
        extracted_from="DEBT_FOOTNOTE",
    )
    session.add(tranche)
    await session.flush()

    result = await session.execute(
        select(DebtTranche).where(DebtTranche.tranche_id == tranche_id)
    )
    fetched = result.scalar_one()
    assert fetched.instrument_name == "4.875% Senior Notes due 2028"
    assert float(fetched.principal_amount) == 750000000.00
    assert float(fetched.coupon_rate) == pytest.approx(0.04875, abs=0.0001)
    assert fetched.has_financial_covenants is True
    assert fetched.has_cross_default is False


@pytest.mark.asyncio
async def test_capital_structure_tranche_relationship(session):
    """Test that tranches are loaded via the capital_structure relationship."""
    entity_id = uuid.uuid4()
    entity = Entity(
        entity_id=entity_id,
        entity_type="PUBLIC_COMPANY",
        legal_name="Relationship Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()

    cs_id = uuid.uuid4()
    cs = CapitalStructure(
        capital_structure_id=cs_id,
        entity_id=entity_id,
        as_of_date=date(2025, 9, 30),
        total_debt=3000000000.00,
    )
    session.add(cs)
    await session.flush()

    for i, name in enumerate(["Term Loan A", "Revolving Credit Facility"]):
        session.add(DebtTranche(
            tranche_id=uuid.uuid4(),
            entity_id=entity_id,
            capital_structure_id=cs_id,
            instrument_name=name,
            principal_amount=500000000.00 * (i + 1),
            seniority_rank=i + 1,
        ))
    await session.flush()

    result = await session.execute(
        select(CapitalStructure).where(CapitalStructure.capital_structure_id == cs_id)
    )
    fetched = result.scalar_one()
    assert len(fetched.tranches) == 2
    names = {t.instrument_name for t in fetched.tranches}
    assert "Term Loan A" in names
    assert "Revolving Credit Facility" in names


@pytest.mark.asyncio
async def test_list_tranches_by_entity(session):
    """Test querying tranches by entity_id."""
    entity_id = uuid.uuid4()
    entity = Entity(
        entity_id=entity_id,
        entity_type="PUBLIC_COMPANY",
        legal_name="Query Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()

    cs_id = uuid.uuid4()
    cs = CapitalStructure(
        capital_structure_id=cs_id,
        entity_id=entity_id,
        as_of_date=date(2025, 12, 31),
    )
    session.add(cs)
    await session.flush()

    for i in range(3):
        session.add(DebtTranche(
            tranche_id=uuid.uuid4(),
            entity_id=entity_id,
            capital_structure_id=cs_id,
            instrument_name=f"Note Series {chr(65 + i)}",
            seniority_rank=i + 1,
        ))
    await session.flush()

    result = await session.execute(
        select(DebtTranche).where(DebtTranche.entity_id == entity_id)
    )
    tranches = result.scalars().all()
    assert len(tranches) == 3


@pytest.mark.asyncio
async def test_floating_rate_tranche(session):
    """Test creating a floating rate debt tranche."""
    entity_id = uuid.uuid4()
    entity = Entity(
        entity_id=entity_id,
        entity_type="PUBLIC_COMPANY",
        legal_name="Float Corp",
        status="ACTIVE",
        source="SEC_EDGAR",
    )
    session.add(entity)
    await session.flush()

    cs_id = uuid.uuid4()
    cs = CapitalStructure(
        capital_structure_id=cs_id,
        entity_id=entity_id,
        as_of_date=date(2025, 12, 31),
    )
    session.add(cs)
    await session.flush()

    tranche = DebtTranche(
        tranche_id=uuid.uuid4(),
        entity_id=entity_id,
        capital_structure_id=cs_id,
        instrument_name="SOFR + 200bps Term Loan B",
        instrument_type="TERM_LOAN_B",
        coupon_type="FLOATING",
        floating_reference="SOFR",
        floating_spread=200.00,
        principal_amount=1000000000.00,
        seniority_type="SENIOR_SECURED",
    )
    session.add(tranche)
    await session.flush()

    result = await session.execute(
        select(DebtTranche).where(DebtTranche.entity_id == entity_id)
    )
    fetched = result.scalar_one()
    assert fetched.coupon_type == "FLOATING"
    assert fetched.floating_reference == "SOFR"
    assert float(fetched.floating_spread) == 200.00
