"""Tests for the SEC EDGAR M&A deals connector.

Exercises the pure 8-K filing extraction, transform, and the DB load of
MandADeal rows against a seeded acquirer entity. No network.
"""

import uuid

import pytest
from sqlalchemy import select

from src.ingestion.edgar_ma_deals import EdgarMaDealsConnector

# Representative SEC submissions JSON slice (data.sec.gov/submissions/CIK*.json).
SAMPLE_SUBMISSIONS = {
    "name": "MegaCorp Inc.",
    "filings": {
        "recent": {
            "form": ["8-K", "8-K", "10-Q", "8-K"],
            "accessionNumber": ["0000000000-24-000001", "0000000000-24-000002", "x", "0000000000-24-000003"],
            "filingDate": ["2024-06-01", "2024-07-15", "2024-07-20", "2024-08-01"],
            "items": [
                "1.01,9.01",          # merger agreement signed → ANNOUNCED
                "2.02",               # earnings → not M&A
                "5.02",               # not M&A
                "2.01,1.01",          # completed acquisition → COMPLETED
            ],
        }
    },
}


def test_extract_ma_filings_pure():
    conn = EdgarMaDealsConnector()
    filings = conn._extract_ma_filings(SAMPLE_SUBMISSIONS, "0009000000")
    # Two 8-Ks carry M&A items (1.01 and 2.01,1.01); the 2.02/5.02 are excluded.
    assert len(filings) == 2
    assert filings[0]["ma_items"] == ["1.01"]
    assert filings[1]["ma_items"] == ["2.01", "1.01"]
    assert filings[0]["entity_name"] == "MegaCorp Inc."


@pytest.mark.asyncio
async def test_transform_status_mapping():
    conn = EdgarMaDealsConnector()
    filings = conn._extract_ma_filings(SAMPLE_SUBMISSIONS, "0009000000")
    valid = await conn.validate(filings)
    out = await conn.transform(valid)
    by_acc = {r["accession_number"]: r for r in out}
    announced = by_acc["0000000000-24-000001"]
    completed = by_acc["0000000000-24-000003"]
    assert announced["deal_status"] == "ANNOUNCED"
    assert announced["announcement_date"] == "2024-06-01"
    assert announced["completion_date"] is None
    # 2.01 present → COMPLETED supersedes 1.01.
    assert completed["deal_status"] == "COMPLETED"
    assert completed["completion_date"] == "2024-08-01"


@pytest.mark.asyncio
async def test_load_inserts_and_dedupes(session):
    from src.models.entity import Entity, EntityIdentifier

    eid = uuid.uuid4()
    session.add(Entity(entity_id=eid, entity_type="PUBLIC_COMPANY", legal_name="MegaCorp Inc.", status="ACTIVE", source="TEST"))
    session.add(EntityIdentifier(id=uuid.uuid4(), entity_id=eid, identifier_type="CIK", identifier_value="0009000000"))
    await session.flush()

    conn = EdgarMaDealsConnector()
    filings = conn._extract_ma_filings(SAMPLE_SUBMISSIONS, "0009000000")
    recs = await conn.transform(await conn.validate(filings))
    stats = await conn.load(recs, session)
    assert stats["inserted"] == 2
    await session.flush()

    from src.models.ma_deals import MandADeal

    rows = (await session.execute(select(MandADeal))).scalars().all()
    assert len(rows) == 2
    assert all(r.acquirer_entity_id == eid for r in rows)
    assert {r.deal_status for r in rows} == {"ANNOUNCED", "COMPLETED"}

    # Re-load is idempotent (same accessions → skipped).
    stats2 = await conn.load(recs, session)
    assert stats2["inserted"] == 0
    assert stats2["skipped"] == 2
