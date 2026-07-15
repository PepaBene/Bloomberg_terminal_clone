"""Tests for the primary-market bond issuances connector.

Covers the pure normalize/extraction helpers, the SEC EDGAR full-text-search
extract() path against mocked httpx responses (a synthetic full-text-search
JSON hit + a synthetic 424B3 filing body with a known coupon/maturity/amount
so the regex extraction can be asserted precisely), the legacy configurable
JSON feed path, and the DB load. No network access.
"""

import uuid
from datetime import date
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from src.ingestion.bond_issuances import (
    BondIssuancesConnector,
    _strip_html,
    extract_pricing_terms,
    normalize_issuance,
)

# A short synthetic 424B3 prospectus-supplement paragraph with a known
# coupon, full maturity date, principal amount and bookrunner syndicate —
# modeled on conventional SEC pricing-term-sheet phrasing.
SAMPLE_FILING_BODY = """
<html><body>
<p>PROSPECTUS SUPPLEMENT</p>
<p>
Example Issuer Corp. is offering $750,000,000 aggregate principal amount of
5.250% Notes due July 15, 2035 (the "Notes"). Interest on the Notes is
payable semi-annually.
</p>
<p>
Joint Book-Running Managers

Goldman Sachs & Co. LLC          J.P. Morgan Securities LLC          Citigroup Global Markets Inc.

</p>
</body></html>
"""

# A filing that only gives a year-level maturity ("due 2035") — the coupon
# and amount should still be parsed, but maturity_date must stay None rather
# than a fabricated month/day.
SAMPLE_FILING_BODY_YEAR_ONLY_MATURITY = """
<p>
We are offering $500,000,000 aggregate principal amount of 4.750% Notes due
2035.
</p>
"""

# A representative SEC EDGAR full-text search response for one CIK.
SAMPLE_SEARCH_RESPONSE = {
    "hits": {
        "total": {"value": 1, "relation": "eq"},
        "hits": [
            {
                "_id": "0001193125-25-123456:d123456d424b3.htm",
                "_source": {
                    "display_names": ["EXAMPLE ISSUER CORP (0000320193)"],
                    "form": "424B3",
                    "file_date": "2025-06-20",
                    "root_forms": ["424B3"],
                },
            }
        ],
    }
}


def test_extract_pricing_terms_full_match():
    parsed = extract_pricing_terms(_strip_html(SAMPLE_FILING_BODY))
    assert parsed["coupon_rate"] == "5.250"
    assert parsed["maturity_date"] == "2035-07-15"
    assert parsed["announced_size_mm"] == "750"
    assert parsed["all_bookrunners"] is not None
    assert "Goldman Sachs & Co. LLC" in parsed["all_bookrunners"]
    assert "J.P. Morgan Securities LLC" in parsed["all_bookrunners"]
    assert "Citigroup Global Markets Inc." in parsed["all_bookrunners"]


def test_extract_pricing_terms_year_only_maturity_not_fabricated():
    parsed = extract_pricing_terms(_strip_html(SAMPLE_FILING_BODY_YEAR_ONLY_MATURITY))
    assert parsed["coupon_rate"] == "4.750"
    assert parsed["announced_size_mm"] == "500"
    # No confident full date -> must not guess a month/day.
    assert parsed["maturity_date"] is None


def test_extract_pricing_terms_empty_text_returns_all_none():
    parsed = extract_pricing_terms("nothing relevant here")
    assert parsed == {
        "coupon_rate": None,
        "maturity_date": None,
        "announced_size_mm": None,
        "all_bookrunners": None,
    }


def test_normalize_issuance_from_edgar_shaped_record():
    row = {
        "issuer_cik": "0000320193",
        "issuer_name": "EXAMPLE ISSUER CORP",
        "pricing_date": "2025-06-20",
        "coupon_rate": "5.250",
        "maturity_date": "2035-07-15",
        "announced_size_mm": "750",
        "all_bookrunners": ["Goldman Sachs & Co. LLC", "J.P. Morgan Securities LLC"],
        "lead_left_bookrunner": "Goldman Sachs & Co. LLC",
        "currency": "USD",
    }
    norm = normalize_issuance(row)
    assert norm["issuer_cik"] == "0000320193"
    assert norm["pricing_date"] == date(2025, 6, 20)
    assert norm["coupon_rate"] == Decimal("5.250")
    assert norm["maturity_date"] == date(2035, 7, 15)
    assert norm["announced_size_mm"] == Decimal("750")
    assert norm["all_bookrunners"] == ["Goldman Sachs & Co. LLC", "J.P. Morgan Securities LLC"]
    assert norm["currency"] == "USD"


def test_normalize_issuance_returns_none_without_any_date():
    assert normalize_issuance({"issuer_cik": "123"}) is None


@pytest.mark.asyncio
async def test_extract_edgar_path_mocked_http(monkeypatch):
    """Full extract() pipeline: full-text search hit -> filing fetch -> regex parse."""

    class _Resp:
        def __init__(self, *, json_data=None, text_data=None):
            self._json_data = json_data
            self.text = text_data

        def raise_for_status(self):
            pass

        def json(self):
            return self._json_data

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def get(self, url, params=None):
            if "efts.sec.gov" in url:
                return _Resp(json_data=SAMPLE_SEARCH_RESPONSE)
            return _Resp(text_data=SAMPLE_FILING_BODY)

        async def aclose(self):
            pass

    monkeypatch.setattr(httpx, "AsyncClient", _Client)

    conn = BondIssuancesConnector(ciks=["320193"], days_back=180)
    raw = await conn.extract()
    assert len(raw) == 1
    rec = raw[0]
    assert rec["issuer_cik"] == "320193"
    assert rec["issuer_name"] == "EXAMPLE ISSUER CORP"
    assert rec["pricing_date"] == "2025-06-20"
    assert rec["coupon_rate"] == "5.250"
    assert rec["maturity_date"] == "2035-07-15"
    assert rec["announced_size_mm"] == "750"
    assert rec["lead_left_bookrunner"] == "Goldman Sachs & Co. LLC"

    valid = await conn.validate(raw)
    transformed = await conn.transform(valid)
    assert len(transformed) == 1
    assert transformed[0]["coupon_rate"] == Decimal("5.250")
    assert transformed[0]["maturity_date"] == date(2035, 7, 15)


@pytest.mark.asyncio
async def test_extract_no_ciks_and_no_feed_url_noop():
    conn = BondIssuancesConnector(ciks=[], feed_url="")
    raw = await conn.extract()
    assert raw == []


@pytest.mark.asyncio
async def test_extract_legacy_feed_url_path_mocked_http(monkeypatch):
    """The pre-existing configurable JSON feed path still works and wins over EDGAR."""

    feed_payload = [
        {
            "issuer_cik": "0000320193",
            "pricing_date": "2025-01-15",
            "maturity_date": "2030-01-15",
            "coupon_rate": "4.000",
            "issued_size_mm": "500",
            "currency": "USD",
        }
    ]

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return feed_payload

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, headers=None):
            return _Resp()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)

    # feed_url set alongside ciks -> feed path takes priority.
    conn = BondIssuancesConnector(ciks=["320193"], feed_url="http://example.com/feed")
    raw = await conn.extract()
    assert raw == feed_payload


@pytest.mark.asyncio
async def test_load_resolves_issuer_and_dedupes(session):
    from src.models.bond_issuance import BondIssuance
    from src.models.entity import Entity, EntityIdentifier

    entity_id = uuid.uuid4()
    session.add(Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name="Example Issuer Corp", status="ACTIVE", source="TEST",
    ))
    session.add(EntityIdentifier(
        id=uuid.uuid4(), entity_id=entity_id,
        identifier_type="CIK", identifier_value="0000320193",
    ))
    await session.flush()

    conn = BondIssuancesConnector()
    raw = [
        {
            "issuer_cik": "0000320193",
            "pricing_date": "2025-06-20",
            "maturity_date": "2035-07-15",
            "coupon_rate": "5.250",
            "announced_size_mm": "750",
            "currency": "USD",
        }
    ]
    recs = await conn.transform(await conn.validate(raw))
    stats = await conn.load(recs, session)
    assert stats["inserted"] == 1
    await session.flush()

    rows = (await session.execute(select(BondIssuance))).scalars().all()
    assert len(rows) == 1
    assert rows[0].issuer_entity_id == entity_id
    assert rows[0].coupon_rate == Decimal("5.250")

    # Re-running the same (issuer, pricing_date, maturity_date) is deduped.
    recs2 = await conn.transform(await conn.validate(raw))
    stats2 = await conn.load(recs2, session)
    assert stats2["inserted"] == 0
    assert stats2["skipped"] == 1


@pytest.mark.asyncio
async def test_load_also_feeds_new_issuance_event(session):
    """Same real deal should also populate fi_intelligence.NewIssuanceEvent
    (the Pillar 3 FI Intelligence dashboard's issuance table), which
    previously had zero producers anywhere."""
    from src.models.entity import Entity, EntityIdentifier
    from src.models.fi_intelligence import NewIssuanceEvent

    entity_id = uuid.uuid4()
    session.add(Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name="Example Issuer Corp", status="ACTIVE", source="TEST",
    ))
    session.add(EntityIdentifier(
        id=uuid.uuid4(), entity_id=entity_id,
        identifier_type="CIK", identifier_value="0000320193",
    ))
    await session.flush()

    conn = BondIssuancesConnector()
    raw = [
        {
            "issuer_cik": "0000320193",
            "pricing_date": "2025-06-20",
            "maturity_date": "2035-07-15",
            "coupon_rate": "5.250",
            "issued_size_mm": "750",
            "final_spread_bps": "120",
            "initial_talk_low_bps": "137",
            "initial_talk_high_bps": "150",
            "use_of_proceeds": "REFINANCING",
            "currency": "USD",
        }
    ]
    recs = await conn.transform(await conn.validate(raw))
    await conn.load(recs, session)
    await session.flush()

    events = (await session.execute(select(NewIssuanceEvent))).scalars().all()
    assert len(events) == 1
    event = events[0]
    assert event.entity_id == entity_id
    assert event.issue_date == date(2025, 6, 20)
    assert event.maturity_date == date(2035, 7, 15)
    assert event.coupon_rate == Decimal("5.250")
    assert event.size_mm == Decimal("750")
    assert event.spread_at_issue_bps == Decimal("120")
    assert event.initial_talk_bps == Decimal("143.5")  # midpoint(137, 150)
    assert event.use_of_proceeds == "REFINANCING"

    # Re-running the same deal doesn't duplicate the NewIssuanceEvent either.
    recs2 = await conn.transform(await conn.validate(raw))
    await conn.load(recs2, session)
    await session.flush()
    events2 = (await session.execute(select(NewIssuanceEvent))).scalars().all()
    assert len(events2) == 1


@pytest.mark.asyncio
async def test_load_skips_unresolved_issuer(session):
    conn = BondIssuancesConnector()
    raw = [
        {
            "issuer_cik": "9999999999",  # never seeded -> unresolvable
            "pricing_date": "2025-06-20",
            "maturity_date": "2035-07-15",
            "currency": "USD",
        }
    ]
    recs = await conn.transform(await conn.validate(raw))
    stats = await conn.load(recs, session)
    assert stats["skipped"] == 1
    assert stats["inserted"] == 0
