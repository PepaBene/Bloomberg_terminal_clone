"""Tests for the SEC EDGAR business-segment connector + ingest script.

No test previously existed for ``EdgarSegmentsConnector`` at all (the
connector class was real but had no unit-test coverage and no script entry
point — ``scripts/ingest_segments.py`` did not exist). This covers the pure
``parse_segments`` function, the CIK-loading helper in the new script, and
an end-to-end load against a seeded entity/financial-period. No network.
"""

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from src.ingestion.edgar_segments import EdgarSegmentsConnector, parse_segments

# Representative company-facts-style us-gaap payload with dimensional segment
# members (mirrors the shape live XBRL frames carry per the module docstring).
# "Americas"/"EMEA" carry a geographical axis -> GEOGRAPHIC; the operating
# segments ("iPhone"/"Services") carry the business-segments axis -> BUSINESS.
SAMPLE_US_GAAP = {
    "RevenueFromContractWithCustomerExcludingAssessedTax": {
        "units": {
            "USD": [
                {"end": "2025-12-31", "val": 100_000_000, "form": "10-K", "fy": 2025,
                 "segment": "Americas", "axis": "srt:StatementGeographicalAxis"},
                {"end": "2025-12-31", "val": 50_000_000, "form": "10-K", "fy": 2025,
                 "segment": "EMEA", "axis": "srt:StatementGeographicalAxis"},
                {"end": "2025-12-31", "val": 80_000_000, "form": "10-K", "fy": 2025,
                 "segment": "iPhone", "axis": "us-gaap:StatementBusinessSegmentsAxis"},
                # No segment member -> consolidated fact, must be excluded.
                {"end": "2025-12-31", "val": 150_000_000, "form": "10-K", "fy": 2025},
            ]
        }
    },
    "OperatingIncomeLoss": {
        "units": {
            "USD": [
                {"end": "2025-12-31", "val": 20_000_000, "form": "10-K", "fy": 2025,
                 "segment": "iPhone", "axis": "us-gaap:StatementBusinessSegmentsAxis"},
            ]
        }
    },
}


def test_parse_segments_classifies_geographic_and_business():
    segments = parse_segments(SAMPLE_US_GAAP)
    assert ("2025-12-31", "GEOGRAPHIC", "Americas") in segments
    assert ("2025-12-31", "GEOGRAPHIC", "EMEA") in segments
    assert ("2025-12-31", "BUSINESS", "iPhone") in segments
    americas = segments[("2025-12-31", "GEOGRAPHIC", "Americas")]
    assert americas["revenue"] == 100_000_000
    assert americas["segment_type"] == "GEOGRAPHIC"
    iphone = segments[("2025-12-31", "BUSINESS", "iPhone")]
    assert iphone["revenue"] == 80_000_000
    assert iphone["operating_income"] == 20_000_000
    emea = segments[("2025-12-31", "GEOGRAPHIC", "EMEA")]
    assert emea["revenue"] == 50_000_000
    assert "operating_income" not in emea


def test_parse_segments_defaults_to_business_without_axis():
    # Member with no axis -> conservative BUSINESS default.
    payload = {
        "Revenues": {
            "units": {"USD": [
                {"end": "2025-12-31", "val": 1_000, "form": "10-K", "fy": 2025, "segment": "Foo"},
            ]}
        }
    }
    segments = parse_segments(payload)
    assert ("2025-12-31", "BUSINESS", "Foo") in segments


@pytest.mark.asyncio
async def test_transform_produces_segment_data_dicts():
    conn = EdgarSegmentsConnector()
    records = [{"cik": "0000320193", "entity_name": "Apple Inc.", "us_gaap_facts": SAMPLE_US_GAAP}]
    out = await conn.transform(records)
    names = {r["segment_name"] for r in out}
    assert names == {"Americas", "EMEA", "iPhone"}
    types = {r["segment_name"]: r["segment_type"] for r in out}
    assert types["Americas"] == "GEOGRAPHIC"
    assert types["EMEA"] == "GEOGRAPHIC"
    assert types["iPhone"] == "BUSINESS"
    assert all(r["period_type"] == "ANNUAL" for r in out)


@pytest.mark.asyncio
async def test_load_writes_segment_data_linked_to_financial_period(session):
    from src.models.entity import Entity, EntityIdentifier
    from src.models.fundamentals import FinancialPeriod, SegmentData

    entity_id = uuid.uuid4()
    session.add(Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name="Apple Inc.", status="ACTIVE", source="TEST",
    ))
    session.add(EntityIdentifier(
        id=uuid.uuid4(), entity_id=entity_id,
        identifier_type="CIK", identifier_value="0000320193",
    ))
    period_id = uuid.uuid4()
    session.add(FinancialPeriod(
        period_id=period_id, entity_id=entity_id,
        period_end_date=date(2025, 12, 31), period_type="ANNUAL",
        fiscal_year=2025, data_version="AS_REPORTED",
    ))
    await session.flush()

    conn = EdgarSegmentsConnector(ciks=["0000320193"])
    records = [{"cik": "0000320193", "entity_name": "Apple Inc.", "us_gaap_facts": SAMPLE_US_GAAP}]
    transformed = await conn.transform(records)
    stats = await conn.load(transformed, session)
    assert stats["inserted"] == 3
    await session.flush()

    rows = (await session.execute(select(SegmentData))).scalars().all()
    assert len(rows) == 3
    assert all(r.period_id == period_id for r in rows)
    assert all(r.entity_id == entity_id for r in rows)
    # Geographic segments are now classified (were all hardcoded BUSINESS).
    geo = {r.segment_name for r in rows if r.segment_type == "GEOGRAPHIC"}
    assert geo == {"Americas", "EMEA"}


@pytest.mark.asyncio
async def test_load_skips_when_no_matching_financial_period(session):
    from src.models.entity import Entity, EntityIdentifier

    entity_id = uuid.uuid4()
    session.add(Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name="Apple Inc.", status="ACTIVE", source="TEST",
    ))
    session.add(EntityIdentifier(
        id=uuid.uuid4(), entity_id=entity_id,
        identifier_type="CIK", identifier_value="0000320193",
    ))
    await session.flush()

    conn = EdgarSegmentsConnector(ciks=["0000320193"])
    records = [{"cik": "0000320193", "entity_name": "Apple Inc.", "us_gaap_facts": SAMPLE_US_GAAP}]
    transformed = await conn.transform(records)
    stats = await conn.load(transformed, session)
    # No FinancialPeriod row exists for this entity/period_end_date -> skipped.
    assert stats["inserted"] == 0
    assert stats["skipped"] == 3


@pytest.mark.asyncio
async def test_ingest_script_load_ciks_respects_limit(session):
    from scripts.ingest_segments import _load_ciks
    from src.models.entity import Entity, EntityIdentifier

    for i in range(3):
        eid = uuid.uuid4()
        session.add(Entity(
            entity_id=eid, entity_type="PUBLIC_COMPANY",
            legal_name=f"Company {i}", status="ACTIVE", source="TEST",
        ))
        session.add(EntityIdentifier(
            id=uuid.uuid4(), entity_id=eid,
            identifier_type="CIK", identifier_value=f"000000000{i}",
        ))
    await session.flush()

    all_ciks = await _load_ciks(session, None)
    assert len(all_ciks) == 3

    limited = await _load_ciks(session, 2)
    assert len(limited) == 2
