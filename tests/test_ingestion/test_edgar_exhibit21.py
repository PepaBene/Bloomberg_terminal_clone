"""Tests for the SEC EDGAR Exhibit 21 (subsidiaries) connector.

Exercises the pure 10-K lookup, exhibit-locator, XML/HTML parsing, transform
and DB load against realistic fixture data — no network. Per repo policy,
outbound access to SEC EDGAR is blocked in this sandbox, so nothing here
calls httpx against a live endpoint.
"""

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from src.ingestion.edgar_exhibit21 import (
    EdgarExhibit21Connector,
    _find_exhibit21_document,
    _find_latest_10k,
    _parse_exhibit21_document,
    _parse_html_table_exhibit21,
    _parse_xml_exhibit21,
)

SAMPLE_SUBMISSIONS = {
    "name": "Acme Holdings Inc.",
    "filings": {
        "recent": {
            "form": ["8-K", "10-K", "10-K", "10-Q", "10-K/A"],
            "accessionNumber": [
                "0001193125-23-000001",
                "0001193125-23-000050",
                "0001193125-24-000075",
                "0001193125-24-000090",
                "0001193125-24-000099",
            ],
            "filingDate": [
                "2023-06-01",
                "2023-02-15",
                "2024-02-20",
                "2024-05-01",
                "2024-03-01",
            ],
        }
    },
}

SAMPLE_INDEX_JSON = {
    "directory": {
        "item": [
            {"name": "acme-10k.htm", "type": "10-K", "size": "12345"},
            {"name": "ex-4.htm", "type": "EX-4.1", "size": "500"},
            {"name": "ex21subsidiariesofacme.htm", "type": "EX-21.1", "size": "900"},
            {"name": "ex23.htm", "type": "EX-23.1", "size": "400"},
        ]
    }
}

SAMPLE_INDEX_JSON_NO_MATCH = {
    "directory": {
        "item": [
            {"name": "acme-10k.htm", "type": "10-K", "size": "12345"},
            {"name": "ex-4.htm", "type": "EX-4.1", "size": "500"},
        ]
    }
}

# Seven subsidiaries across four jurisdictions (Delaware, Cayman Islands,
# Netherlands, California) -- three offshore-flagged jurisdictions per
# TAX_ADVANTAGED_JURISDICTIONS in the complex_structure engine.
_EXPECTED_NAMES_JURISDICTIONS = [
    ("Acme Manufacturing LLC", "Delaware"),
    ("Acme Distribution LLC", "Delaware"),
    ("Acme International Holdings Ltd.", "Cayman Islands"),
    ("Acme Finance Ltd.", "Cayman Islands"),
    ("Acme Europe B.V.", "Netherlands"),
    ("Acme Trading Co.", "California"),
    ("Acme Logistics Co.", "California"),
]

XML_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<ex-21>
  <subsidiary>
    <name>Acme Manufacturing LLC</name>
    <jurisdiction>Delaware</jurisdiction>
    <ownership>100</ownership>
  </subsidiary>
  <subsidiary>
    <name>Acme Distribution LLC</name>
    <jurisdiction>Delaware</jurisdiction>
    <ownership>100</ownership>
  </subsidiary>
  <subsidiary>
    <name>Acme International Holdings Ltd.</name>
    <jurisdiction>Cayman Islands</jurisdiction>
    <ownership>100</ownership>
  </subsidiary>
  <subsidiary>
    <name>Acme Finance Ltd.</name>
    <jurisdiction>Cayman Islands</jurisdiction>
  </subsidiary>
  <subsidiary>
    <name>Acme Europe B.V.</name>
    <jurisdiction>Netherlands</jurisdiction>
    <ownership>75.5</ownership>
  </subsidiary>
  <subsidiary>
    <name>Acme Trading Co.</name>
    <jurisdiction>California</jurisdiction>
  </subsidiary>
  <subsidiary>
    <name>Acme Logistics Co.</name>
    <jurisdiction>California</jurisdiction>
  </subsidiary>
</ex-21>
"""

HTML_TABLE_FIXTURE = """
<html>
<head><title>EX-21.1</title></head>
<body>
<p>Exhibit 21.1 &#8212; Subsidiaries of the Registrant</p>
<table border="1">
<tr><th>Name of Subsidiary</th><th>State or Jurisdiction of Incorporation</th></tr>
<tr><td>Acme Manufacturing LLC</td><td>Delaware</td></tr>
<tr><td>Acme Distribution LLC</td><td>Delaware</td></tr>
<tr><td>Acme International Holdings Ltd.</td><td>Cayman Islands</td></tr>
<tr><td>Acme Finance Ltd.</td><td>Cayman&nbsp;Islands</td></tr>
<tr><td>Acme Europe B.V.</td><td>Netherlands</td></tr>
<tr><td>Acme Trading Co.</td><td>California</td></tr>
<tr><td>Acme Logistics Co.</td><td>California</td></tr>
</table>
</body>
</html>
"""

HTML_TABLE_WITH_OWNERSHIP_FIXTURE = """
<table>
<tr><td>Name of Subsidiary</td><td>Jurisdiction</td><td>Percent Owned</td></tr>
<tr><td>Acme Manufacturing LLC</td><td>Delaware</td><td>100%</td></tr>
<tr><td>Acme Finance Ltd.</td><td>Cayman Islands</td><td>80%</td></tr>
</table>
"""


# ── Pure function tests ──────────────────────────────────────────────


def test_find_latest_10k_picks_most_recent_and_excludes_amendment():
    filing = _find_latest_10k(SAMPLE_SUBMISSIONS, "0001234567")
    assert filing is not None
    assert filing["accession_number"] == "0001193125-24-000075"
    assert filing["filing_date"] == "2024-02-20"


def test_find_latest_10k_returns_none_when_no_10k():
    empty = {"filings": {"recent": {"form": ["8-K"], "accessionNumber": ["x"], "filingDate": ["2024-01-01"]}}}
    assert _find_latest_10k(empty, "0001234567") is None


def test_find_exhibit21_document_matches_by_type_and_name():
    doc = _find_exhibit21_document(SAMPLE_INDEX_JSON)
    assert doc == "ex21subsidiariesofacme.htm"


def test_find_exhibit21_document_returns_none_when_absent():
    assert _find_exhibit21_document(SAMPLE_INDEX_JSON_NO_MATCH) is None


def test_parse_xml_exhibit21_structured():
    rows = _parse_xml_exhibit21(XML_FIXTURE)
    assert len(rows) == 7
    by_name = {r["name"]: r for r in rows}
    assert by_name["Acme Manufacturing LLC"]["jurisdiction"] == "Delaware"
    assert by_name["Acme Manufacturing LLC"]["ownership_pct"] == 100.0
    # Ownership not disclosed for this one -- must stay None, not fabricated.
    assert by_name["Acme Finance Ltd."]["ownership_pct"] is None
    assert by_name["Acme Europe B.V."]["ownership_pct"] == 75.5

    names_jurisdictions = {(r["name"], r["jurisdiction"]) for r in rows}
    assert names_jurisdictions == set(_EXPECTED_NAMES_JURISDICTIONS)


def test_parse_html_table_exhibit21_skips_header_and_strips_entities():
    rows = _parse_html_table_exhibit21(HTML_TABLE_FIXTURE)
    assert len(rows) == 7
    names_jurisdictions = {(r["name"], r["jurisdiction"]) for r in rows}
    assert names_jurisdictions == set(_EXPECTED_NAMES_JURISDICTIONS)
    # &nbsp; entity between "Cayman" and "Islands" must be normalized to a
    # plain space, not left as a literal entity or smashed together.
    by_name = {r["name"]: r for r in rows}
    assert by_name["Acme Finance Ltd."]["jurisdiction"] == "Cayman Islands"
    # No ownership column in this fixture -- must not be fabricated.
    assert all(r["ownership_pct"] is None for r in rows)


def test_parse_html_table_exhibit21_with_ownership_column():
    rows = _parse_html_table_exhibit21(HTML_TABLE_WITH_OWNERSHIP_FIXTURE)
    assert len(rows) == 2
    by_name = {r["name"]: r for r in rows}
    assert by_name["Acme Manufacturing LLC"]["ownership_pct"] == 100.0
    assert by_name["Acme Finance Ltd."]["ownership_pct"] == 80.0


def test_parse_exhibit21_document_dispatches_xml_then_html():
    assert len(_parse_exhibit21_document(XML_FIXTURE)) == 7
    assert len(_parse_exhibit21_document(HTML_TABLE_FIXTURE)) == 7
    assert _parse_exhibit21_document("<html><body><p>no table here</p></body></html>") == []


# ── Transform tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_transform_maps_fields():
    conn = EdgarExhibit21Connector()
    rows = _parse_exhibit21_document(XML_FIXTURE)
    records = [
        {
            "cik": "0001234567",
            "name": r["name"],
            "jurisdiction": r["jurisdiction"],
            "ownership_pct": r["ownership_pct"],
            "accession_number": "0001193125-24-000075",
            "filing_date": "2024-02-20",
        }
        for r in rows
    ]
    validated = await conn.validate(records)
    assert len(validated) == 7
    out = await conn.transform(validated)
    assert len(out) == 7
    sample = next(r for r in out if r["name"] == "Acme Manufacturing LLC")
    assert sample["jurisdiction"] == "Delaware"
    assert sample["ownership_pct"] == 100.0
    assert sample["source_filing_accession"] == "0001193125-24-000075"
    assert sample["as_of_date"] == "2024-02-20"
    assert sample["cik"] == "0001234567"


@pytest.mark.asyncio
async def test_validate_drops_empty_names():
    conn = EdgarExhibit21Connector()
    records = [
        {"cik": "1", "name": "Real Sub", "jurisdiction": "Delaware", "ownership_pct": None,
         "accession_number": "a", "filing_date": "2024-01-01"},
        {"cik": "1", "name": "  ", "jurisdiction": "Delaware", "ownership_pct": None,
         "accession_number": "a", "filing_date": "2024-01-01"},
        {"cik": "1", "name": "", "jurisdiction": None, "ownership_pct": None,
         "accession_number": "a", "filing_date": "2024-01-01"},
    ]
    validated = await conn.validate(records)
    assert len(validated) == 1
    assert validated[0]["name"] == "Real Sub"


# ── Load tests (DB, via `session` fixture) ───────────────────────────


@pytest.mark.asyncio
async def test_load_inserts_resolves_by_cik_and_upserts(session):
    from src.models.entity import Entity, EntityIdentifier
    from src.models.subsidiary import Subsidiary

    eid = uuid.uuid4()
    session.add(Entity(entity_id=eid, entity_type="PUBLIC_COMPANY", legal_name="Acme Holdings Inc.", status="ACTIVE", source="TEST"))
    session.add(EntityIdentifier(id=uuid.uuid4(), entity_id=eid, identifier_type="CIK", identifier_value="0001234567"))
    await session.flush()

    conn = EdgarExhibit21Connector()
    rows = _parse_exhibit21_document(XML_FIXTURE)
    raw = [
        {
            "cik": "0001234567",
            "name": r["name"],
            "jurisdiction": r["jurisdiction"],
            "ownership_pct": r["ownership_pct"],
            "accession_number": "0001193125-24-000075",
            "filing_date": "2024-02-20",
        }
        for r in rows
    ]
    transformed = await conn.transform(await conn.validate(raw))
    stats = await conn.load(transformed, session)
    assert stats["inserted"] == 7
    assert stats["errors"] == 0
    await session.flush()

    db_rows = (
        await session.execute(select(Subsidiary).where(Subsidiary.parent_entity_id == eid))
    ).scalars().all()
    assert len(db_rows) == 7
    by_name = {r.name: r for r in db_rows}
    assert by_name["Acme Manufacturing LLC"].jurisdiction == "Delaware"
    assert by_name["Acme Manufacturing LLC"].as_of_date == date(2024, 2, 20)
    assert float(by_name["Acme Manufacturing LLC"].ownership_pct) == 100.0
    assert by_name["Acme Finance Ltd."].ownership_pct is None

    # Re-running load() with the same natural key updates rather than
    # duplicates (unique constraint on parent_entity_id, name, as_of_date).
    stats2 = await conn.load(transformed, session)
    assert stats2["inserted"] == 0
    assert stats2["updated"] == 7
    db_rows2 = (
        await session.execute(select(Subsidiary).where(Subsidiary.parent_entity_id == eid))
    ).scalars().all()
    assert len(db_rows2) == 7


@pytest.mark.asyncio
async def test_load_skips_unresolvable_cik(session):
    conn = EdgarExhibit21Connector()
    records = [
        {
            "cik": "9999999999",
            "name": "Ghost Sub LLC",
            "jurisdiction": "Delaware",
            "ownership_pct": None,
            "source_filing_accession": "0001193125-24-000075",
            "as_of_date": "2024-02-20",
        }
    ]
    stats = await conn.load(records, session)
    assert stats["skipped"] == 1
    assert stats["inserted"] == 0


# ── Downstream engine sanity check (no fabrication of offshore mix) ──


def test_parsed_fixture_feeds_analyze_subsidiary_tree_with_nontrivial_offshore_pct():
    from src.engines.complex_structure import analyze_subsidiary_tree

    rows = _parse_exhibit21_document(HTML_TABLE_FIXTURE)
    subs = [{"name": r["name"], "jurisdiction": r["jurisdiction"], "ownership_pct": r["ownership_pct"]} for r in rows]
    result = analyze_subsidiary_tree(subs)
    assert result["total_subsidiaries"] == 7
    assert result["distinct_jurisdictions"] == 4
    # Delaware, Cayman Islands and Netherlands are all offshore-flagged in
    # TAX_ADVANTAGED_JURISDICTIONS; California is not. 5 of 7 -> ~71.4%.
    assert result["offshore_count"] == 5
    assert result["offshore_pct"] == pytest.approx(71.4, abs=0.1)
