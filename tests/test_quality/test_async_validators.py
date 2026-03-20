"""Tests for async data quality validators that query the database.

Each validator takes an AsyncSession, queries specific models, and
returns a list of ValidationIssue instances for records that violate
business rules.  These tests seed data that should (or should not)
trigger issues and verify the validators behave correctly.
"""

import uuid
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.quality.validators import (
    ValidationIssue,
    validate_balance_sheet_balances,
    validate_entity_has_country,
    validate_esg_score_range,
    validate_fiscal_year_end,
    validate_lei_format,
    validate_relationship_no_self_reference,
)


# ── validate_lei_format ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lei_format_valid(session: AsyncSession):
    """A valid 20-character alphanumeric LEI should produce no issues."""
    from src.models.entity import Entity, EntityIdentifier

    entity = Entity(
        entity_id=uuid.uuid4(),
        entity_type="CORPORATION",
        legal_name="Good LEI Corp",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
        confidence_score=0.95,
    )
    session.add(entity)
    await session.flush()

    ident = EntityIdentifier(
        entity_id=entity.entity_id,
        identifier_type="LEI",
        identifier_value="529900HNOAA1KXQJUQ27",  # Valid LEI format
        is_primary=True,
    )
    session.add(ident)
    await session.flush()

    issues = await validate_lei_format(session)
    lei_issues_for_entity = [
        i for i in issues if i.record_id == entity.entity_id
    ]
    assert len(lei_issues_for_entity) == 0


@pytest.mark.asyncio
async def test_lei_format_invalid_too_short(session: AsyncSession):
    """An LEI that is too short should produce an issue."""
    from src.models.entity import Entity, EntityIdentifier

    entity = Entity(
        entity_id=uuid.uuid4(),
        entity_type="CORPORATION",
        legal_name="Bad LEI Corp",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
        confidence_score=0.95,
    )
    session.add(entity)
    await session.flush()

    ident = EntityIdentifier(
        entity_id=entity.entity_id,
        identifier_type="LEI",
        identifier_value="SHORT123",  # Invalid: too short
        is_primary=True,
    )
    session.add(ident)
    await session.flush()

    issues = await validate_lei_format(session)
    lei_issues_for_entity = [
        i for i in issues if i.record_id == entity.entity_id
    ]
    assert len(lei_issues_for_entity) == 1
    assert lei_issues_for_entity[0].severity == "HIGH"
    assert lei_issues_for_entity[0].issue_type == "INVALID_VALUE"


@pytest.mark.asyncio
async def test_lei_format_invalid_special_chars(session: AsyncSession):
    """An LEI with special characters should produce an issue."""
    from src.models.entity import Entity, EntityIdentifier

    entity = Entity(
        entity_id=uuid.uuid4(),
        entity_type="CORPORATION",
        legal_name="Special Char LEI Corp",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
        confidence_score=0.95,
    )
    session.add(entity)
    await session.flush()

    ident = EntityIdentifier(
        entity_id=entity.entity_id,
        identifier_type="LEI",
        identifier_value="5299-0HNOAA1KXQJUQ2!",  # Invalid characters
        is_primary=True,
    )
    session.add(ident)
    await session.flush()

    issues = await validate_lei_format(session)
    lei_issues_for_entity = [
        i for i in issues if i.record_id == entity.entity_id
    ]
    assert len(lei_issues_for_entity) == 1


# ── validate_balance_sheet_balances ────────────────────────────────


@pytest.mark.asyncio
async def test_balance_sheet_balanced(session: AsyncSession):
    """A balanced balance sheet should produce no issues."""
    from src.models.fundamentals import BalanceSheet, FinancialPeriod

    entity_id = uuid.uuid4()
    # Create a minimal entity for the FK
    from src.models.entity import Entity

    entity = Entity(
        entity_id=entity_id,
        entity_type="CORPORATION",
        legal_name="Balanced Corp",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
    )
    session.add(entity)
    await session.flush()

    period = FinancialPeriod(
        period_id=uuid.uuid4(),
        entity_id=entity_id,
        period_end_date=date(2024, 12, 31),
        period_type="ANNUAL",
        fiscal_year=2024,
    )
    session.add(period)
    await session.flush()

    bs = BalanceSheet(
        statement_id=uuid.uuid4(),
        period_id=period.period_id,
        total_assets=1_000_000,
        total_liabilities_and_equity=1_000_000,
    )
    session.add(bs)
    await session.flush()

    issues = await validate_balance_sheet_balances(session)
    bs_issues = [i for i in issues if i.record_id == period.period_id]
    assert len(bs_issues) == 0


@pytest.mark.asyncio
async def test_balance_sheet_imbalanced(session: AsyncSession):
    """An imbalanced balance sheet (>1% diff) should produce an issue."""
    from src.models.fundamentals import BalanceSheet, FinancialPeriod

    entity_id = uuid.uuid4()
    from src.models.entity import Entity

    entity = Entity(
        entity_id=entity_id,
        entity_type="CORPORATION",
        legal_name="Imbalanced Corp",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
    )
    session.add(entity)
    await session.flush()

    period = FinancialPeriod(
        period_id=uuid.uuid4(),
        entity_id=entity_id,
        period_end_date=date(2024, 12, 31),
        period_type="ANNUAL",
        fiscal_year=2024,
    )
    session.add(period)
    await session.flush()

    bs = BalanceSheet(
        statement_id=uuid.uuid4(),
        period_id=period.period_id,
        total_assets=1_000_000,
        total_liabilities_and_equity=900_000,  # 10% difference
    )
    session.add(bs)
    await session.flush()

    issues = await validate_balance_sheet_balances(session)
    bs_issues = [i for i in issues if i.record_id == period.period_id]
    assert len(bs_issues) == 1
    assert bs_issues[0].severity == "CRITICAL"
    assert "imbalance" in bs_issues[0].description.lower()


# ── validate_esg_score_range ───────────────────────────────────────


@pytest.mark.asyncio
async def test_esg_score_in_range(session: AsyncSession):
    """ESG scores between 0 and 100 should produce no issues."""
    from src.models.esg import ESGScore
    from src.models.entity import Entity

    entity = Entity(
        entity_id=uuid.uuid4(),
        entity_type="CORPORATION",
        legal_name="Green Corp",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
    )
    session.add(entity)
    await session.flush()

    score_id = uuid.uuid4()
    esg = ESGScore(
        score_id=score_id,
        entity_id=entity.entity_id,
        provider="MSCI",
        as_of_date=date(2024, 6, 30),
        esg_score=75.0,
        environmental_score=80.0,
        social_score=70.0,
        governance_score=72.0,
    )
    session.add(esg)
    await session.flush()

    issues = await validate_esg_score_range(session)
    esg_issues = [i for i in issues if i.record_id == score_id]
    assert len(esg_issues) == 0


@pytest.mark.asyncio
async def test_esg_score_out_of_range(session: AsyncSession):
    """ESG scores outside 0-100 should produce issues."""
    from src.models.esg import ESGScore
    from src.models.entity import Entity

    entity = Entity(
        entity_id=uuid.uuid4(),
        entity_type="CORPORATION",
        legal_name="Bad Score Corp",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
    )
    session.add(entity)
    await session.flush()

    score_id = uuid.uuid4()
    esg = ESGScore(
        score_id=score_id,
        entity_id=entity.entity_id,
        provider="MSCI",
        as_of_date=date(2024, 6, 30),
        esg_score=105.0,  # Out of range
        environmental_score=-5.0,  # Out of range
        social_score=50.0,  # OK
        governance_score=200.0,  # Out of range
    )
    session.add(esg)
    await session.flush()

    issues = await validate_esg_score_range(session)
    esg_issues = [i for i in issues if i.record_id == score_id]
    # Should flag esg_score (105), environmental_score (-5), governance_score (200)
    assert len(esg_issues) == 3
    flagged_fields = {i.field_name for i in esg_issues}
    assert "esg_score" in flagged_fields
    assert "environmental_score" in flagged_fields
    assert "governance_score" in flagged_fields


# ── validate_relationship_no_self_reference ────────────────────────


@pytest.mark.asyncio
async def test_relationship_no_self_reference_valid(session: AsyncSession):
    """A relationship between two different entities should produce no issues."""
    from src.models.entity import Entity
    from src.models.relationships import BusinessRelationship

    e1 = Entity(
        entity_id=uuid.uuid4(),
        entity_type="CORPORATION",
        legal_name="Source Corp",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
    )
    e2 = Entity(
        entity_id=uuid.uuid4(),
        entity_type="CORPORATION",
        legal_name="Target Corp",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
    )
    session.add_all([e1, e2])
    await session.flush()

    rel_id = uuid.uuid4()
    rel = BusinessRelationship(
        relationship_id=rel_id,
        source_entity_id=e1.entity_id,
        target_entity_id=e2.entity_id,
        relationship_type="SUPPLIER",
    )
    session.add(rel)
    await session.flush()

    issues = await validate_relationship_no_self_reference(session)
    rel_issues = [i for i in issues if i.record_id == rel_id]
    assert len(rel_issues) == 0


@pytest.mark.asyncio
async def test_relationship_self_reference_flagged(session: AsyncSession):
    """A self-referencing relationship should produce an issue."""
    from src.models.entity import Entity
    from src.models.relationships import BusinessRelationship

    entity = Entity(
        entity_id=uuid.uuid4(),
        entity_type="CORPORATION",
        legal_name="Self Ref Corp",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
    )
    session.add(entity)
    await session.flush()

    rel_id = uuid.uuid4()
    rel = BusinessRelationship(
        relationship_id=rel_id,
        source_entity_id=entity.entity_id,
        target_entity_id=entity.entity_id,  # Self-reference!
        relationship_type="SUPPLIER",
    )
    session.add(rel)
    await session.flush()

    issues = await validate_relationship_no_self_reference(session)
    rel_issues = [i for i in issues if i.record_id == rel_id]
    assert len(rel_issues) == 1
    assert rel_issues[0].severity == "CRITICAL"
    assert "self-referencing" in rel_issues[0].description.lower()


# ── validate_entity_has_country ────────────────────────────────────


@pytest.mark.asyncio
async def test_entity_has_country_valid(session: AsyncSession):
    """An active entity with a country should produce no issues."""
    from src.models.entity import Entity

    entity = Entity(
        entity_id=uuid.uuid4(),
        entity_type="CORPORATION",
        legal_name="Country Corp",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
    )
    session.add(entity)
    await session.flush()

    issues = await validate_entity_has_country(session)
    entity_issues = [i for i in issues if i.record_id == entity.entity_id]
    assert len(entity_issues) == 0


@pytest.mark.asyncio
async def test_entity_has_country_missing(session: AsyncSession):
    """An active entity without a country should produce an issue."""
    from src.models.entity import Entity

    entity = Entity(
        entity_id=uuid.uuid4(),
        entity_type="CORPORATION",
        legal_name="No Country Corp",
        status="ACTIVE",
        incorporation_country=None,
        source="TEST",
    )
    session.add(entity)
    await session.flush()

    issues = await validate_entity_has_country(session)
    entity_issues = [i for i in issues if i.record_id == entity.entity_id]
    assert len(entity_issues) == 1
    assert entity_issues[0].severity == "CRITICAL"


# ── validate_fiscal_year_end ───────────────────────────────────────


@pytest.mark.asyncio
async def test_fiscal_year_end_valid(session: AsyncSession):
    """A valid MM-DD fiscal year end should produce no issues."""
    from src.models.entity import Entity

    entity = Entity(
        entity_id=uuid.uuid4(),
        entity_type="CORPORATION",
        legal_name="FY Valid Corp",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
        fiscal_year_end="12-31",
    )
    session.add(entity)
    await session.flush()

    issues = await validate_fiscal_year_end(session)
    fy_issues = [i for i in issues if i.record_id == entity.entity_id]
    assert len(fy_issues) == 0


@pytest.mark.asyncio
async def test_fiscal_year_end_invalid(session: AsyncSession):
    """An invalid fiscal year end format should produce an issue."""
    from src.models.entity import Entity

    entity = Entity(
        entity_id=uuid.uuid4(),
        entity_type="CORPORATION",
        legal_name="FY Invalid Corp",
        status="ACTIVE",
        incorporation_country="US",
        source="TEST",
        fiscal_year_end="31-12",  # Wrong: DD-MM instead of MM-DD
    )
    session.add(entity)
    await session.flush()

    issues = await validate_fiscal_year_end(session)
    fy_issues = [i for i in issues if i.record_id == entity.entity_id]
    assert len(fy_issues) == 1
    assert fy_issues[0].issue_type == "FORMAT_ERROR"
