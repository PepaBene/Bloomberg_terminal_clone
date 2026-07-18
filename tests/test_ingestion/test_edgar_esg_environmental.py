"""Tests for the EDGAR ESG environmental/social connector.

Exercises the regex extraction helpers, the scoring heuristic, mocked-HTTP
extract() (SEC EDGAR submissions + filing text + EPA Envirofacts GHGRP
lookup), and the DB upsert of ESGScore.environmental_score/social_score
against a seeded entity. No network calls -- httpx.AsyncClient is monkeypatched
throughout.
"""

import uuid
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from src.ingestion.edgar_esg_environmental import (
    EPA_GHGRP_EMISSIONS_TABLE,
    EPA_GHGRP_FACILITY_TABLE,
    PROVIDER,
    EdgarESGEnvironmentalConnector,
)

# A realistic-looking 10-K excerpt covering every regex signal this
# connector looks for. Deliberately hand-constructed (not a real filing).
FIXTURE_10K_TEXT = (
    "Item 1A. Risk Factors\n\n"
    "Climate-related regulations could increase our operating costs. "
    "Our total Scope 1 and Scope 2 greenhouse gas emissions of approximately "
    "1,250,000 metric tons of CO2-equivalent decreased 8% year-over-year, "
    "reflecting continued investment in efficiency projects. "
    "In fiscal 2025, 42% of our total electricity consumption was derived "
    "from renewable sources, including solar and wind power purchase "
    "agreements. We have committed to achieving net-zero emissions by 2040 "
    "across our global operations.\n\n"
    "Item 7. Management's Discussion and Analysis\n\n"
    "Approximately 38% of our global workforce identifies as women, "
    "reflecting continued progress on our diversity, equity and inclusion "
    "initiatives. Our total recordable incident rate (TRIR) of 0.85 remains "
    "below the industry average, underscoring our continued commitment to "
    "workplace safety. Voluntary employee turnover rate of 12.4% for fiscal "
    "year 2025, compares favorably to 15.1% in the prior fiscal year.\n"
)

SAMPLE_SUBMISSIONS = {
    "name": "Acme Corp",
    "filings": {
        "recent": {
            "form": ["10-K", "8-K", "10-K"],
            "accessionNumber": [
                "0001234567-25-000123",
                "0001234567-25-000050",
                "0001234567-24-000110",
            ],
            "primaryDocument": ["acme-10k-2025.htm", "acme-8k.htm", "acme-10k-2024.htm"],
            "filingDate": ["2025-02-15", "2025-01-10", "2024-02-14"],
        }
    },
}

SAMPLE_EPA_FACILITIES = [
    {"FACILITY_NAME": "ACME CORP MANUFACTURING PLANT", "FACILITY_ID": "1000123"}
]

SAMPLE_EPA_EMISSIONS = [
    {"FACILITY_ID": "1000123", "REPORTING_YEAR": 2023, "CO2E_EMISSION": "980000"},
    {"FACILITY_ID": "1000123", "REPORTING_YEAR": 2024, "CO2E_EMISSION": "1020000"},
]


# --------------------------------------------------------------------------
# Regex extraction helpers (pure)
# --------------------------------------------------------------------------


def test_extract_ghg_emissions():
    value, unit = EdgarESGEnvironmentalConnector._extract_ghg_emissions(FIXTURE_10K_TEXT)
    assert value == Decimal("1250000")
    assert "metric" in unit.lower()


def test_extract_renewable_pct():
    pct = EdgarESGEnvironmentalConnector._extract_renewable_pct(FIXTURE_10K_TEXT)
    assert pct == 42.0


def test_extract_net_zero_year():
    year = EdgarESGEnvironmentalConnector._extract_net_zero_year(FIXTURE_10K_TEXT)
    assert year == 2040


def test_extract_workforce_diversity():
    pct, category = EdgarESGEnvironmentalConnector._extract_workforce_diversity(FIXTURE_10K_TEXT)
    assert pct == 38.0
    assert category == "women"


def test_extract_safety_trir():
    trir = EdgarESGEnvironmentalConnector._extract_safety_trir(FIXTURE_10K_TEXT)
    assert trir == 0.85


def test_extract_turnover_rate():
    turnover = EdgarESGEnvironmentalConnector._extract_turnover_rate(FIXTURE_10K_TEXT)
    assert turnover == 12.4


def test_extractors_return_none_on_no_match():
    empty_text = "This filing discusses unrelated matters at length. " * 20
    assert EdgarESGEnvironmentalConnector._extract_ghg_emissions(empty_text) == (None, None)
    assert EdgarESGEnvironmentalConnector._extract_renewable_pct(empty_text) is None
    assert EdgarESGEnvironmentalConnector._extract_net_zero_year(empty_text) is None
    assert EdgarESGEnvironmentalConnector._extract_workforce_diversity(empty_text) == (None, None)
    assert EdgarESGEnvironmentalConnector._extract_safety_trir(empty_text) is None
    assert EdgarESGEnvironmentalConnector._extract_turnover_rate(empty_text) is None


# --------------------------------------------------------------------------
# Scoring heuristic (pure)
# --------------------------------------------------------------------------


def test_score_environmental_no_signal_is_none():
    assert (
        EdgarESGEnvironmentalConnector._score_environmental(None, None, None, 2025, False)
        is None
    )


def test_score_environmental_combines_available_signals():
    # High renewable pct + near-term net-zero target + EPA verification
    # should pull the blended score above the flat GHG-disclosure-only credit.
    score = EdgarESGEnvironmentalConnector._score_environmental(
        Decimal("1250000"), 90.0, 2030, 2025, True
    )
    assert score is not None
    assert 0 <= score <= 100
    ghg_only = EdgarESGEnvironmentalConnector._score_environmental(
        Decimal("1250000"), None, None, 2025, False
    )
    assert score > ghg_only


def test_score_social_no_signal_is_none():
    assert EdgarESGEnvironmentalConnector._score_social(None, None, None) is None


def test_score_social_low_turnover_and_trir_score_higher():
    good = EdgarESGEnvironmentalConnector._score_social(40.0, 0.5, 5.0)
    bad = EdgarESGEnvironmentalConnector._score_social(40.0, 4.5, 45.0)
    assert good > bad


# --------------------------------------------------------------------------
# transform() end-to-end (pure)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transform_produces_metrics_and_scores():
    conn = EdgarESGEnvironmentalConnector(cik_list=["9000789"])
    records = [
        {
            "cik": "9000789",
            "entity_name": "Acme Corp",
            "form_type": "10-K",
            "accession_number": "0001234567-25-000123",
            "filing_date": "2025-02-15",
            "text": FIXTURE_10K_TEXT,
            "epa_emissions": {
                "facility_name": "ACME CORP MANUFACTURING PLANT",
                "facility_id": "1000123",
                "co2e_emission_metric_tons": Decimal("1020000"),
            },
        }
    ]
    out = await conn.transform(records)
    assert len(out) == 1
    row = out[0]
    assert row["environmental_score"] is not None
    assert row["social_score"] is not None
    metric_types = {m["metric_type"] for m in row["metrics"]}
    assert "GHG_EMISSIONS_DISCLOSED" in metric_types
    assert "RENEWABLE_ENERGY_PCT" in metric_types
    assert "NET_ZERO_TARGET_YEAR" in metric_types
    assert "GHG_EMISSIONS_EPA_VERIFIED" in metric_types
    assert "WORKFORCE_DIVERSITY_PCT" in metric_types
    assert "SAFETY_INCIDENT_RATE_TRIR" in metric_types
    assert "EMPLOYEE_TURNOVER_RATE" in metric_types


@pytest.mark.asyncio
async def test_transform_no_signal_yields_none_scores():
    conn = EdgarESGEnvironmentalConnector(cik_list=["9000789"])
    records = [
        {
            "cik": "9000789",
            "entity_name": "Acme Corp",
            "form_type": "10-K",
            "accession_number": "0001",
            "filing_date": "2025-02-15",
            "text": "This filing discusses unrelated matters at length. " * 30,
            "epa_emissions": None,
        }
    ]
    out = await conn.transform(records)
    assert out[0]["environmental_score"] is None
    assert out[0]["social_score"] is None
    assert out[0]["metrics"] == []


# --------------------------------------------------------------------------
# Mocked-HTTP extract(): SEC EDGAR submissions + filing text + EPA lookup
# --------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, json_data=None, text_data=""):
        self._json = json_data
        self.text = text_data

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


class _FakeClient:
    """Routes GET requests by URL shape; no real network access."""

    def __init__(self, *a, **k):
        pass

    async def get(self, url, *a, **k):
        if url.startswith("https://data.sec.gov/submissions/"):
            return _FakeResponse(json_data=SAMPLE_SUBMISSIONS)
        if url.startswith("https://www.sec.gov/Archives/"):
            return _FakeResponse(text_data=FIXTURE_10K_TEXT)
        if EPA_GHGRP_FACILITY_TABLE in url:
            return _FakeResponse(json_data=SAMPLE_EPA_FACILITIES)
        if EPA_GHGRP_EMISSIONS_TABLE in url:
            return _FakeResponse(json_data=SAMPLE_EPA_EMISSIONS)
        raise AssertionError(f"unexpected URL in test: {url}")

    async def aclose(self):
        pass


@pytest.mark.asyncio
async def test_extract_mocked_http_with_epa_enrichment(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)

    conn = EdgarESGEnvironmentalConnector(
        cik_list=["9000789"], epa_base_url="https://data.epa.gov/efservice"
    )
    records = await conn.extract()
    await conn.close()

    # Only the two 10-K filings are kept (8-K is filtered out by ESG_FILING_TYPES).
    assert len(records) == 2
    assert all(r["form_type"] == "10-K" for r in records)
    assert all(r["entity_name"] == "Acme Corp" for r in records)
    # EPA enrichment attached to every filing for this CIK.
    assert all(r["epa_emissions"] is not None for r in records)
    assert records[0]["epa_emissions"]["facility_id"] == "1000123"
    assert records[0]["epa_emissions"]["co2e_emission_metric_tons"] == Decimal("1020000")


@pytest.mark.asyncio
async def test_extract_epa_disabled_skips_enrichment(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)

    conn = EdgarESGEnvironmentalConnector(cik_list=["9000789"], enable_epa_enrichment=False)
    records = await conn.extract()
    await conn.close()

    assert len(records) == 2
    assert all(r["epa_emissions"] is None for r in records)


@pytest.mark.asyncio
async def test_epa_lookup_no_facility_match_returns_none(monkeypatch):
    class _NoMatchClient(_FakeClient):
        async def get(self, url, *a, **k):
            if EPA_GHGRP_FACILITY_TABLE in url:
                return _FakeResponse(json_data=[])
            return await super().get(url, *a, **k)

    monkeypatch.setattr(httpx, "AsyncClient", _NoMatchClient)

    conn = EdgarESGEnvironmentalConnector(
        cik_list=["9000789"], epa_base_url="https://data.epa.gov/efservice"
    )
    result = await conn._fetch_epa_emissions("Acme Corp")
    await conn.close()
    assert result is None


@pytest.mark.asyncio
async def test_epa_lookup_failure_skips_gracefully(monkeypatch):
    class _BrokenClient:
        def __init__(self, *a, **k):
            pass

        async def get(self, url, *a, **k):
            raise httpx.ConnectError("simulated network failure")

        async def aclose(self):
            pass

    monkeypatch.setattr(httpx, "AsyncClient", _BrokenClient)

    conn = EdgarESGEnvironmentalConnector(
        cik_list=["9000789"], epa_base_url="https://data.epa.gov/efservice"
    )
    result = await conn._fetch_epa_emissions("Acme Corp")
    await conn.close()
    assert result is None  # best-effort: never raises


@pytest.mark.asyncio
async def test_extract_no_ciks_returns_empty():
    conn = EdgarESGEnvironmentalConnector(cik_list=[])
    assert await conn.extract() == []


# --------------------------------------------------------------------------
# validate()
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_drops_short_text_and_missing_fields():
    conn = EdgarESGEnvironmentalConnector()
    records = [
        {"cik": "9000789", "text": FIXTURE_10K_TEXT, "filing_date": "2025-02-15"},
        {"cik": "9000789", "text": "too short", "filing_date": "2025-02-15"},
        {"cik": "9000789", "text": FIXTURE_10K_TEXT, "filing_date": None},
        {"cik": None, "text": FIXTURE_10K_TEXT, "filing_date": "2025-02-15"},
    ]
    valid = await conn.validate(records)
    assert len(valid) == 1


# --------------------------------------------------------------------------
# load(): upsert ESGScore.environmental_score/social_score + ESGMetric rows
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_inserts_then_updates_scores(session):
    from src.models.entity import Entity, EntityIdentifier
    from src.models.esg import ESGMetric, ESGScore

    eid = uuid.uuid4()
    session.add(
        Entity(
            entity_id=eid,
            entity_type="PUBLIC_COMPANY",
            legal_name="Acme Corp",
            status="ACTIVE",
            source="TEST",
        )
    )
    session.add(
        EntityIdentifier(
            id=uuid.uuid4(),
            entity_id=eid,
            identifier_type="CIK",
            identifier_value="0009000789",
        )
    )
    await session.flush()

    conn = EdgarESGEnvironmentalConnector(cik_list=["0009000789"])
    raw_record = {
        "cik": "0009000789",
        "entity_name": "Acme Corp",
        "form_type": "10-K",
        "accession_number": "0001234567-25-000123",
        "filing_date": "2025-02-15",
        "text": FIXTURE_10K_TEXT,
        "epa_emissions": None,
    }
    transformed = await conn.transform([raw_record])
    stats = await conn.load(transformed, session)
    assert stats["inserted"] >= 1  # one ESGScore + several ESGMetric rows

    rows = (await session.execute(select(ESGScore).where(ESGScore.provider == PROVIDER))).scalars().all()
    assert len(rows) == 1
    assert rows[0].entity_id == eid
    first_env_score = rows[0].environmental_score
    assert first_env_score is not None
    assert rows[0].social_score is not None
    # Composite esg_score is now populated (previously NULL forever). With no
    # governance pillar present, it is the mean of environmental + social.
    assert rows[0].esg_score is not None
    expected = round(
        (float(rows[0].environmental_score) + float(rows[0].social_score)) / 2, 2
    )
    assert float(rows[0].esg_score) == pytest.approx(expected)

    metric_rows = (await session.execute(select(ESGMetric))).scalars().all()
    assert len(metric_rows) >= 6

    # Re-run with a text that yields a different (higher) environmental
    # signal set for the *same* CIK + as_of_date -> should UPDATE, not
    # insert a second row (upsert by entity_id+provider+as_of_date).
    boosted_text = FIXTURE_10K_TEXT + " We have committed to achieving net-zero emissions by 2026."
    transformed2 = await conn.transform(
        [{**raw_record, "text": boosted_text}]
    )
    stats2 = await conn.load(transformed2, session)
    assert stats2["updated"] == 1  # the existing ESGScore row was updated...
    # ...while ESGMetric rows are always appended fresh (same as
    # edgar_esg.py's behavior -- metrics are a time series, not upserted).
    assert stats2["inserted"] == len(transformed2[0]["metrics"])

    rows_after = (await session.execute(select(ESGScore).where(ESGScore.provider == PROVIDER))).scalars().all()
    assert len(rows_after) == 1  # ...still exactly one ESGScore row
    assert rows_after[0].score_id == rows[0].score_id


@pytest.mark.asyncio
async def test_load_skips_unresolved_cik(session):
    conn = EdgarESGEnvironmentalConnector(cik_list=["9999999"])
    raw_record = {
        "cik": "9999999",  # never seeded -> unresolved
        "entity_name": "Nonexistent Co",
        "form_type": "10-K",
        "accession_number": "0001",
        "filing_date": "2025-02-15",
        "text": FIXTURE_10K_TEXT,
        "epa_emissions": None,
    }
    transformed = await conn.transform([raw_record])
    stats = await conn.load(transformed, session)
    assert stats["skipped"] == 1
    assert stats["inserted"] == 0
