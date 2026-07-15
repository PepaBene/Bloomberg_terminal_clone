"""Tests for the SEC EDGAR 8-K Item 2.02 guidance-extraction connector.

Exercises the pure Item 2.02 filing filter, the regex guidance-figure
extraction against realistic synthetic press-release paragraphs (raising
guidance, reaffirming guidance, and a negative case with no guidance
language at all), the optional AI-augmentation fallback path, and the DB
load of GuidanceTracking rows against a seeded entity. No live network
calls — extract() is exercised against a mocked httpx response.
"""

import uuid
from datetime import date, timedelta

import httpx
import pytest
from sqlalchemy import select

from src.ingestion.guidance_extraction import (
    GuidanceExtractionConnector,
    extract_guidance_figures,
)

TODAY = date.today()
RECENT = (TODAY - timedelta(days=5)).isoformat()

SAMPLE_SUBMISSIONS = {
    "name": "Acme Corporation",
    "filings": {
        "recent": {
            "form": ["8-K", "8-K", "10-K", "8-K"],
            "accessionNumber": [
                "0000000000-24-000101",
                "0000000000-24-000102",
                "0000000000-24-000103",
                "0000000000-24-000104",
            ],
            "filingDate": [RECENT, RECENT, RECENT, RECENT],
            "primaryDocument": ["ex991.htm", "ex991-noguidance.htm", "10k.htm", "ex991-oldstyle.htm"],
            "items": ["2.02,9.01", "5.02", "", "1.01"],
        }
    },
}

TEXT_RAISED = (
    "ACME Corporation (NASDAQ: ACME) today announced financial results for the "
    "quarter ended March 31, 2024 and is raising its full-year fiscal 2024 "
    "guidance. Management now expects full-year revenue in the range of $5.2 "
    "to $5.4 billion for fiscal 2024, compared to prior guidance of $4.8 to "
    "$5.0 billion. The increase reflects stronger than anticipated demand "
    "across all segments and represents continued momentum heading into the "
    "back half of the year. The Company will host a conference call today at "
    "5:00 p.m. Eastern Time to discuss these results in more detail with "
    "analysts and investors."
)

TEXT_REAFFIRMED = (
    "BETA Industries Inc. (NYSE: BETA) reported second quarter fiscal 2024 "
    "results today. The Company is reaffirming its previously issued full-year "
    "guidance. Management continues to expect revenue in the range of $2.1 to "
    "$2.3 billion for fiscal 2024, consistent with the outlook provided last "
    "quarter. All other elements of the Company's guidance remain unchanged. "
    "A conference call will be held at 8:30 a.m. Eastern Time to review results."
)

TEXT_NO_GUIDANCE = (
    "GAMMA Holdings plc announced today that it has completed its previously "
    "announced acquisition of Delta Logistics for approximately $340 million "
    "in cash. Gamma's Chief Executive Officer commented that the transaction "
    "strengthens the Company's supply-chain footprint and is expected to be "
    "immediately accretive to operating margins. Terms of the transaction "
    "were not otherwise disclosed. The Company does not undertake any "
    "obligation to update this release."
)


def test_extract_item_202_filings_pure():
    conn = GuidanceExtractionConnector()
    filings = conn._extract_item_202_filings(SAMPLE_SUBMISSIONS, "0001234567")
    # Only the first 8-K (items "2.02,9.01") qualifies; the 5.02-only 8-K,
    # the 10-K, and the 1.01-only 8-K are excluded.
    assert len(filings) == 1
    assert filings[0]["accession_number"] == "0000000000-24-000101"
    assert filings[0]["document_url"].endswith("/1234567/000000000024000101/ex991.htm")


def test_extract_guidance_figures_raised_range():
    figures = extract_guidance_figures(TEXT_RAISED)
    assert figures is not None
    assert figures["metric"] == "REVENUE"
    assert figures["guidance_low"] == pytest.approx(5.2e9)
    assert figures["guidance_high"] == pytest.approx(5.4e9)
    assert figures["guidance_midpoint"] == pytest.approx(5.3e9)
    assert figures["guidance_type"] == "RAISED"
    assert figures["prior_guidance_low"] == pytest.approx(4.8e9)
    assert figures["prior_guidance_high"] == pytest.approx(5.0e9)


def test_extract_guidance_figures_reaffirmed_range():
    figures = extract_guidance_figures(TEXT_REAFFIRMED)
    assert figures is not None
    assert figures["metric"] == "REVENUE"
    assert figures["guidance_low"] == pytest.approx(2.1e9)
    assert figures["guidance_high"] == pytest.approx(2.3e9)
    assert figures["guidance_type"] == "MAINTAINED"


def test_extract_guidance_figures_no_guidance_language():
    """Negative case: no parseable forward-guidance language — must return None."""
    assert extract_guidance_figures(TEXT_NO_GUIDANCE) is None


@pytest.mark.asyncio
async def test_validate_drops_short_and_failed_bodies():
    conn = GuidanceExtractionConnector()
    records = [
        {"cik": "1", "filing_date": RECENT, "body": TEXT_RAISED, "accession_number": "a"},
        {"cik": "2", "filing_date": RECENT, "body": None, "accession_number": "b"},
        {"cik": "3", "filing_date": RECENT, "body": "too short", "accession_number": "c"},
        {"cik": "4", "filing_date": None, "body": TEXT_RAISED, "accession_number": "d"},
    ]
    valid = await conn.validate(records)
    assert len(valid) == 1
    assert valid[0]["cik"] == "1"


@pytest.mark.asyncio
async def test_transform_builds_guidance_rows():
    conn = GuidanceExtractionConnector()
    records = [
        {"cik": "0001234567", "filing_date": RECENT, "body": TEXT_RAISED},
        {"cik": "0007654321", "filing_date": RECENT, "body": TEXT_REAFFIRMED},
        {"cik": "0009999999", "filing_date": RECENT, "body": TEXT_NO_GUIDANCE},
    ]
    out = await conn.transform(records)
    # The no-guidance-language filing produces no row.
    assert len(out) == 2
    by_cik = {r["cik"]: r for r in out}
    assert by_cik["0001234567"]["guidance_type"] == "RAISED"
    assert by_cik["0001234567"]["guidance_fiscal_year"] == 2024
    assert by_cik["0007654321"]["guidance_type"] == "MAINTAINED"
    # Raw text is stashed for the optional AI pass, not a persisted field.
    assert "_raw_text" in by_cik["0001234567"]


@pytest.mark.asyncio
async def test_resolve_falls_back_to_regex_without_anthropic_key(monkeypatch):
    """ANTHROPIC_API_KEY unset -> resolve() must not crash and must strip _raw_text."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    conn = GuidanceExtractionConnector()
    records = await conn.transform(
        [{"cik": "0001234567", "filing_date": RECENT, "body": TEXT_RAISED}]
    )
    out = await conn.resolve(records)
    assert len(out) == 1
    assert "_raw_text" not in out[0]
    assert out[0]["guidance_type"] == "RAISED"
    assert out[0]["guidance_low"] == pytest.approx(5.2e9)


@pytest.mark.asyncio
async def test_extract_mocked_http(monkeypatch):
    """Extract path against mocked submissions + document-body httpx responses."""

    class _Resp:
        def __init__(self, payload):
            self._payload = payload
            self.text = payload if isinstance(payload, str) else ""

        def raise_for_status(self):
            pass

        def json(self):
            return self._payload

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def get(self, url, params=None):
            if "data.sec.gov" in url:
                return _Resp(SAMPLE_SUBMISSIONS)
            return _Resp(TEXT_RAISED)

        async def aclose(self):
            pass

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    conn = GuidanceExtractionConnector(ciks=["0001234567"], days_back=30)
    raw = await conn.extract()
    assert len(raw) == 1
    assert raw[0]["body"] == TEXT_RAISED
    await conn.close()


@pytest.mark.asyncio
async def test_extract_noops_without_ciks():
    conn = GuidanceExtractionConnector(ciks=[])
    assert await conn.extract() == []


@pytest.mark.asyncio
async def test_load_inserts_dedupes_and_skips_unresolvable(session):
    from src.models.entity import Entity, EntityIdentifier

    eid = uuid.uuid4()
    session.add(
        Entity(
            entity_id=eid,
            entity_type="PUBLIC_COMPANY",
            legal_name="Acme Corporation",
            status="ACTIVE",
            source="TEST",
        )
    )
    session.add(
        EntityIdentifier(
            id=uuid.uuid4(), entity_id=eid, identifier_type="CIK", identifier_value="0001234567"
        )
    )
    await session.flush()

    conn = GuidanceExtractionConnector()
    records = await conn.transform(
        [
            {"cik": "0001234567", "filing_date": RECENT, "body": TEXT_RAISED},
            # Unresolvable CIK — must be skipped, not fabricated.
            {"cik": "0009999998", "filing_date": RECENT, "body": TEXT_REAFFIRMED},
        ]
    )
    resolved = await conn.resolve(records)
    stats = await conn.load(resolved, session)
    assert stats["inserted"] == 1
    assert stats["skipped"] == 1
    await session.flush()

    from src.models.earnings_intelligence import GuidanceTracking

    rows = (await session.execute(select(GuidanceTracking))).scalars().all()
    assert len(rows) == 1
    assert rows[0].entity_id == eid
    assert rows[0].guidance_type == "RAISED"
    assert rows[0].metric == "REVENUE"

    # Re-loading the same (entity_id, metric, guidance_date) upserts.
    records2 = await conn.transform(
        [{"cik": "0001234567", "filing_date": RECENT, "body": TEXT_RAISED}]
    )
    resolved2 = await conn.resolve(records2)
    stats2 = await conn.load(resolved2, session)
    assert stats2["inserted"] == 0
    assert stats2["updated"] == 1
