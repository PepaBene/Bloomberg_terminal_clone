"""Tests for the SEC EDGAR Schedule 13D/13G beneficial-ownership connector.

Covers the pure daily-index / SEC-HEADER / cover-page parsers (no network --
all HTTP fetching is bypassed by feeding in-memory sample text directly to
the parse functions) and the DB load path.
"""

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from src.ingestion.edgar_13d13g import (
    Edgar13D13GConnector,
    daily_index_url,
    extract_cover_page_terms,
    parse_daily_index,
    parse_sec_header,
    submission_text_url,
)

SAMPLE_DAILY_INDEX = """Description:           Daily Index of EDGAR Dissemination Feed
Last Data Received:    March 3, 2026
Comments:               webmaster@sec.gov
Anonymous FTP:          Directory: edgar/daily-index

Form Type   Company Name                                                  CIK         Date Filed  File Name
-----------------------------------------------------------------------------------------------------------
4           SOME INSIDER                                                  0001111111  2026-03-03  edgar/data/1111111/0001111111-26-000001.txt
SC 13D      ACTIVIST CAPITAL PARTNERS LP                                  0001234567  2026-03-03  edgar/data/1234567/0001234567-26-000099.txt
SC 13G      PASSIVE INDEX FUND TRUST                                      0007654321  2026-03-03  edgar/data/7654321/0007654321-26-000042.txt
8-K         UNRELATED CORP                                                0009999999  2026-03-03  edgar/data/9999999/0009999999-26-000003.txt
"""

SAMPLE_SEC_HEADER = """<SEC-HEADER>0001234567-26-000099.hdr.sgml : 20260303
<ACCEPTANCE-DATETIME>20260303173000
SC 13D
SUBJECT COMPANY:

    COMPANY DATA:
        COMPANY CONFORMED NAME:            TARGETCO INC
        CENTRAL INDEX KEY:            0000320193
        STANDARD INDUSTRIAL CLASSIFICATION:    [7372]

FILED BY:

    COMPANY DATA:
        COMPANY CONFORMED NAME:            ACTIVIST CAPITAL PARTNERS LP
        CENTRAL INDEX KEY:            0001234567
</SEC-HEADER>
"""

SAMPLE_COVER_PAGE = """
1. NAMES OF REPORTING PERSONS
   Activist Capital Partners LP

7. SOLE VOTING POWER
   0

8. SHARED VOTING POWER
   4,500,000

9. SOLE DISPOSITIVE POWER
   0

10. SHARED DISPOSITIVE POWER
   4,500,000

11. AGGREGATE AMOUNT BENEFICIALLY OWNED BY EACH REPORTING PERSON
   4,500,000

13. PERCENT OF CLASS REPRESENTED BY AMOUNT IN ROW (11)
   7.8%

14. TYPE OF REPORTING PERSON
   PN
"""


def test_daily_index_url_builds_quarter_from_date():
    assert daily_index_url(date(2026, 3, 3)) == (
        "https://www.sec.gov/Archives/edgar/daily-index/2026/QTR1/form.20260303.idx"
    )
    assert daily_index_url(date(2026, 11, 15)) == (
        "https://www.sec.gov/Archives/edgar/daily-index/2026/QTR4/form.20261115.idx"
    )


def test_parse_daily_index_filters_to_target_forms_only():
    stubs = parse_daily_index(SAMPLE_DAILY_INDEX)
    forms = {s["form"] for s in stubs}
    assert forms == {"SC 13D", "SC 13G"}
    assert len(stubs) == 2

    activist = next(s for s in stubs if s["form"] == "SC 13D")
    assert activist["daily_index_name"] == "ACTIVIST CAPITAL PARTNERS LP"
    assert activist["daily_index_cik"] == "0001234567"
    assert activist["filing_date"] == "2026-03-03"
    assert activist["file_name"] == "edgar/data/1234567/0001234567-26-000099.txt"


def test_parse_daily_index_returns_empty_for_unrecognized_layout():
    assert parse_daily_index("not an index file at all") == []


def test_submission_text_url():
    assert submission_text_url("edgar/data/1234567/0001234567-26-000099.txt") == (
        "https://www.sec.gov/Archives/edgar/data/1234567/0001234567-26-000099.txt"
    )


def test_parse_sec_header_disambiguates_subject_company_and_filer():
    header = parse_sec_header(SAMPLE_SEC_HEADER)
    assert header["issuer_name"] == "TARGETCO INC"
    assert header["issuer_cik"] == "320193"
    assert header["filer_name"] == "ACTIVIST CAPITAL PARTNERS LP"
    assert header["filer_cik"] == "1234567"


def test_parse_sec_header_handles_missing_blocks():
    header = parse_sec_header("<SEC-HEADER>nothing useful here</SEC-HEADER>")
    assert header == {
        "issuer_name": None, "issuer_cik": None,
        "filer_name": None, "filer_cik": None,
    }


def test_extract_cover_page_terms():
    terms = extract_cover_page_terms(SAMPLE_COVER_PAGE)
    assert terms["shares_owned"] == "4,500,000"
    assert terms["percent_of_class"] == "7.8"
    assert terms["reporting_person_type"] == "PN"
    assert terms["sole_voting_power"] == "0"
    assert terms["shared_voting_power"] == "4,500,000"
    assert terms["sole_dispositive_power"] == "0"
    assert terms["shared_dispositive_power"] == "4,500,000"


def test_extract_cover_page_terms_missing_fields_stay_none():
    terms = extract_cover_page_terms("no cover page content here")
    assert all(v is None for v in terms.values())


@pytest.mark.asyncio
async def test_load_writes_filing_when_issuer_resolves(session):
    from src.models.entity import Entity, EntityIdentifier
    from src.models.ownership import BeneficialOwnershipFiling
    from src.models.security import Security

    issuer_id = uuid.uuid4()
    session.add(Entity(
        entity_id=issuer_id, entity_type="PUBLIC_COMPANY",
        legal_name="TARGETCO INC", status="ACTIVE", source="TEST",
    ))
    session.add(EntityIdentifier(
        id=uuid.uuid4(), entity_id=issuer_id,
        identifier_type="CIK", identifier_value="320193",
    ))
    security_id = uuid.uuid4()
    session.add(Security(
        security_id=security_id, security_type="COMMON_STOCK",
        issuer_entity_id=issuer_id, name="TargetCo Common Stock",
        status="ACTIVE", asset_class="EQUITY",
    ))
    await session.flush()

    conn = Edgar13D13GConnector()
    rec = {
        "issuer_cik": "320193",
        "issuer_name": "TARGETCO INC",
        "filer_name": "ACTIVIST CAPITAL PARTNERS LP",
        "filer_cik": None,
        "reporting_person_type": "PN",
        "schedule_type": "SC 13D",
        "is_activist": True,
        "is_amendment": False,
        "filing_date": "2026-03-03",
        "shares_owned": "4,500,000",
        "percent_of_class": "7.8",
        "sole_voting_power": "0",
        "shared_voting_power": "4,500,000",
        "sole_dispositive_power": "0",
        "shared_dispositive_power": "4,500,000",
        "accession_number": "0001234567-26-000099",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/1234567/0001234567-26-000099.txt",
    }
    stats = await conn.load([rec], session)
    assert stats["inserted"] == 1
    await session.flush()

    filings = (await session.execute(select(BeneficialOwnershipFiling))).scalars().all()
    assert len(filings) == 1
    f = filings[0]
    assert f.issuer_entity_id == issuer_id
    assert f.security_id == security_id
    assert f.filer_name == "ACTIVIST CAPITAL PARTNERS LP"
    assert f.schedule_type == "SC 13D"
    assert f.is_activist is True
    assert float(f.percent_of_class) == 7.8
    assert float(f.shares_owned) == 4500000


@pytest.mark.asyncio
async def test_load_skips_when_issuer_unresolved(session):
    conn = Edgar13D13GConnector()
    rec = {
        "issuer_cik": "999999999",
        "issuer_name": "NO SUCH COMPANY",
        "filer_name": "SOME FUND LP",
        "schedule_type": "SC 13G",
        "is_activist": False,
        "is_amendment": False,
        "filing_date": "2026-03-03",
        "accession_number": "0000000000-26-000001",
    }
    stats = await conn.load([rec], session)
    assert stats["inserted"] == 0
    assert stats["skipped"] == 1


@pytest.mark.asyncio
async def test_load_dedupes_on_accession_number(session):
    from src.models.entity import Entity, EntityIdentifier

    issuer_id = uuid.uuid4()
    session.add(Entity(
        entity_id=issuer_id, entity_type="PUBLIC_COMPANY",
        legal_name="TARGETCO INC", status="ACTIVE", source="TEST",
    ))
    session.add(EntityIdentifier(
        id=uuid.uuid4(), entity_id=issuer_id,
        identifier_type="CIK", identifier_value="320193",
    ))
    await session.flush()

    conn = Edgar13D13GConnector()
    rec = {
        "issuer_cik": "320193",
        "issuer_name": "TARGETCO INC",
        "filer_name": "ACTIVIST CAPITAL PARTNERS LP",
        "schedule_type": "SC 13D",
        "is_activist": True,
        "is_amendment": False,
        "filing_date": "2026-03-03",
        "accession_number": "0001234567-26-000099",
    }
    stats1 = await conn.load([rec], session)
    await session.flush()
    stats2 = await conn.load([rec], session)
    await session.flush()

    assert stats1["inserted"] == 1
    assert stats2["inserted"] == 0
    assert stats2["skipped"] == 1
