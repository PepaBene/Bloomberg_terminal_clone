"""Tests for the SEC EDGAR executives connector.

Exercises the pure ownership-XML parse, the transform de-duplication, and the
DB load path (Executive + ExecutiveRole) against a seeded entity so the
write path is proven without network access.
"""

import uuid

import pytest
from sqlalchemy import select

from src.ingestion.edgar_executives import (
    EdgarExecutivesConnector,
    parse_ownership_owner,
)

# A representative SEC Form 4 ownership-document XML (trimmed to the identity
# and relationship blocks the connector reads).
SAMPLE_FORM4_XML = """<?xml version="1.0"?>
<ownershipDocument>
  <issuer>
    <issuerCik>0009000193</issuerCik>
    <issuerName>Apple Inc.</issuerName>
    <issuerTradingSymbol>AAPL</issuerTradingSymbol>
  </issuer>
  <reportingOwner>
    <reportingOwnerId>
      <rptOwnerCik>0001214156</rptOwnerCik>
      <rptOwnerName>COOK TIMOTHY D</rptOwnerName>
    </reportingOwnerId>
    <reportingOwnerRelationship>
      <isDirector>1</isDirector>
      <isOfficer>1</isOfficer>
      <isTenPercentOwner>0</isTenPercentOwner>
      <officerTitle>Chief Executive Officer</officerTitle>
    </reportingOwnerRelationship>
  </reportingOwner>
</ownershipDocument>
"""

DIRECTOR_ONLY_XML = """<?xml version="1.0"?>
<ownershipDocument>
  <issuer><issuerCik>0000320193</issuerCik><issuerName>Apple Inc.</issuerName></issuer>
  <reportingOwner>
    <reportingOwnerId><rptOwnerName>LEVINSON ARTHUR D</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship>
      <isDirector>1</isDirector><isOfficer>0</isOfficer><isTenPercentOwner>0</isTenPercentOwner>
    </reportingOwnerRelationship>
  </reportingOwner>
</ownershipDocument>
"""


def test_parse_ownership_owner_officer():
    parsed = parse_ownership_owner(SAMPLE_FORM4_XML)
    assert parsed is not None
    assert parsed["issuer_cik"] == "0009000193"
    assert parsed["person_name"] == "COOK TIMOTHY D"
    assert parsed["is_officer"] is True
    assert parsed["is_director"] is True
    assert parsed["officer_title"] == "Chief Executive Officer"


def test_parse_ownership_owner_no_name_returns_none():
    xml = "<ownershipDocument><issuer><issuerCik>1</issuerCik></issuer></ownershipDocument>"
    assert parse_ownership_owner(xml) is None


@pytest.mark.asyncio
async def test_transform_prefers_officer_and_dedupes():
    conn = EdgarExecutivesConnector()
    parsed = parse_ownership_owner(SAMPLE_FORM4_XML)
    parsed["issuer_cik"] = "0009000193"
    # Same person filing twice at the same issuer → one OFFICER role.
    out = await conn.transform([parsed, dict(parsed)])
    assert len(out) == 1
    assert out[0]["role_type"] == "OFFICER"
    assert out[0]["title"] == "Chief Executive Officer"
    assert out[0]["is_independent"] is False


@pytest.mark.asyncio
async def test_transform_director_only():
    conn = EdgarExecutivesConnector()
    parsed = parse_ownership_owner(DIRECTOR_ONLY_XML)
    parsed["issuer_cik"] = "0009000193"
    out = await conn.transform([parsed])
    assert out[0]["role_type"] == "DIRECTOR"
    assert out[0]["title"] == "Director"


@pytest.mark.asyncio
async def test_load_creates_executive_and_role(session):
    from src.models.entity import Entity, EntityIdentifier

    entity_id = uuid.uuid4()
    session.add(Entity(entity_id=entity_id, entity_type="PUBLIC_COMPANY", legal_name="Apple Inc.", status="ACTIVE", source="SEC_EDGAR"))
    session.add(EntityIdentifier(id=uuid.uuid4(), entity_id=entity_id, identifier_type="CIK", identifier_value="0009000193"))
    await session.flush()

    conn = EdgarExecutivesConnector()
    parsed = parse_ownership_owner(SAMPLE_FORM4_XML)
    recs = await conn.transform([parsed])
    stats = await conn.load(recs, session)
    assert stats["inserted"] == 1
    await session.flush()

    from src.models.executives import Executive, ExecutiveRole

    execs = (await session.execute(select(Executive))).scalars().all()
    roles = (await session.execute(select(ExecutiveRole))).scalars().all()
    assert len(execs) == 1
    assert execs[0].person_name == "COOK TIMOTHY D"
    assert len(roles) == 1
    assert roles[0].entity_id == entity_id
    assert roles[0].role_type == "OFFICER"

    # Re-loading is idempotent (skipped, not duplicated).
    stats2 = await conn.load(recs, session)
    assert stats2["inserted"] == 0
    assert stats2["skipped"] == 1


@pytest.mark.asyncio
async def test_load_skips_when_cik_unresolved(session):
    conn = EdgarExecutivesConnector()
    parsed = parse_ownership_owner(SAMPLE_FORM4_XML)
    parsed["issuer_cik"] = "0009999193"  # never seeded → unresolved
    recs = await conn.transform([parsed])
    stats = await conn.load(recs, session)
    assert stats["skipped"] == 1
    assert stats["inserted"] == 0
