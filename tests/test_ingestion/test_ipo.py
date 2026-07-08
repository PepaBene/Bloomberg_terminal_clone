"""Tests for the SEC EDGAR IPO connector.

Exercises the pure S-1/424B filing extraction, transform, and the DB load of
IPOEvent rows against a seeded entity. No network.
"""

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from src.ingestion.edgar_ipo import EdgarIpoConnector

SAMPLE_SUBMISSIONS = {
    "name": "NewCo Inc.",
    "filings": {
        "recent": {
            "form": ["S-1", "S-1/A", "424B4", "10-K"],
            "accessionNumber": [
                "0000000000-24-000010",
                "0000000000-24-000011",
                "0000000000-24-000012",
                "0000000000-24-000013",
            ],
            "filingDate": ["2024-01-10", "2024-02-01", "2024-03-05", "2024-05-01"],
        }
    },
}


def test_extract_ipo_filings_pure():
    conn = EdgarIpoConnector()
    filings = conn._extract_ipo_filings(SAMPLE_SUBMISSIONS, "0009000042")
    # S-1, S-1/A, 424B4 → 3 IPO-related filings; 10-K excluded.
    assert len(filings) == 3
    kinds = {f["form"]: f["kind"] for f in filings}
    assert kinds["S-1"] == "S1"
    assert kinds["424B4"] == "PROSPECTUS"


@pytest.mark.asyncio
async def test_transform_status_mapping():
    conn = EdgarIpoConnector()
    filings = conn._extract_ipo_filings(SAMPLE_SUBMISSIONS, "0009000042")
    out = await conn.transform(await conn.validate(filings))
    by_acc = {r["accession_number"]: r for r in out}
    assert by_acc["0000000000-24-000010"]["status"] == "FILED"
    assert by_acc["0000000000-24-000010"]["s1_filing_date"] == "2024-01-10"
    assert by_acc["0000000000-24-000012"]["status"] == "PRICED"
    assert by_acc["0000000000-24-000012"]["pricing_date"] == "2024-03-05"


@pytest.mark.asyncio
async def test_load_inserts_and_dedupes(session):
    from src.models.entity import Entity, EntityIdentifier

    eid = uuid.uuid4()
    session.add(Entity(entity_id=eid, entity_type="PUBLIC_COMPANY", legal_name="NewCo Inc.", status="ACTIVE", source="TEST"))
    session.add(EntityIdentifier(id=uuid.uuid4(), entity_id=eid, identifier_type="CIK", identifier_value="0009000042"))
    await session.flush()

    conn = EdgarIpoConnector()
    filings = conn._extract_ipo_filings(SAMPLE_SUBMISSIONS, "0009000042")
    recs = await conn.transform(await conn.validate(filings))
    stats = await conn.load(recs, session)
    assert stats["inserted"] == 3
    await session.flush()

    from src.models.ipo import IPOEvent

    rows = (await session.execute(select(IPOEvent))).scalars().all()
    assert len(rows) == 3
    priced = [r for r in rows if r.status == "PRICED"]
    assert priced[0].pricing_date == date(2024, 3, 5)

    stats2 = await conn.load(recs, session)
    assert stats2["inserted"] == 0
    assert stats2["skipped"] == 3
