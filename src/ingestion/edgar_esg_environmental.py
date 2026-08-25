"""EDGAR ESG connector — environmental & social pillars from 10-K disclosures.

Mirrors ``edgar_esg.py`` (SEC EDGAR submissions fetch by CIK, 10-K retrieval,
regex-based text extraction, rate limiter, User-Agent header pattern), which
is explicitly governance-only by its own docstring. This connector fills the
``ESGScore.environmental_score`` / ``ESGScore.social_score`` gap (both
Numeric(5,2) columns that are otherwise always NULL) using two inputs:

1. Regex-based disclosure signals pulled from 10-K Item 1A (Risk Factors) /
   Item 7 (MD&A) / sustainability-section text: GHG emissions figures,
   renewable-energy commitments, net-zero/carbon-neutral target years,
   workforce diversity percentages, safety incident rates (TRIR), and
   employee turnover rates.
2. An optional, best-effort secondary enrichment from EPA Envirofacts'
   Greenhouse Gas Reporting Program (GHGRP) facility/emissions tables,
   queried by company name via ``settings.EPA_ENVIROFACTS_BASE_URL``. This
   is real, independently-sourced regulatory emissions data layered on top
   of the text-disclosure proxy when a facility match is found; it is
   skipped gracefully (never blocks the primary text-based score) when no
   match is found.

Scores are written under ``provider="EDGAR_DISCLOSURE_PROXY"`` — deliberately
NOT a real vendor name like MSCI or Sustainalytics, because this is not
sourced from them. ``environmental_score`` / ``social_score`` here are a
disclosure-based proxy: "how much did the filer disclose, and do the
disclosed figures look directionally favorable" — NOT an authoritative
third-party ESG rating, and do not claim to benchmark absolute magnitudes
(e.g. raw GHG tonnage) without industry-normalized context we don't have.
This is documented at each scoring step below; callers should not present
these scores as equivalent to a licensed ESG rating.

FLAG — UNTESTED AGAINST LIVE DATA
----------------------------------
Outbound network access to external domains (SEC EDGAR and EPA Envirofacts
included) is blocked in this sandbox by network policy, so this connector —
both the 10-K text extraction path and the EPA Envirofacts enrichment path —
has never been exercised against a live response. The SEC EDGAR submissions
fetch and 10-K retrieval are written to the same pattern as ``edgar_esg.py``,
which is already relied upon elsewhere in this codebase, so that part is
low-risk. The EPA Envirofacts query path is written against EPA's documented
REST convention (``{base}/{table}/{column}/{value}/{format}``, with
``CONTAINING``/``BEGINNING``/``ENDING`` operators for substring matches on
text columns) using our best-effort understanding of the GHG Reporting
Program's facility (``PUB_DIM_FACILITY``) and emissions
(``PUB_FACTS_SECTOR_GHG_EMISSION``) table/column names — those exact table
and column names have NOT been validated against a live Envirofacts
response and may not be exactly right; the lookup is wrapped in a
best-effort try/except that skips enrichment entirely (never fabricates a
match) on any failure, including a wrong table/column name. Both paths are
unit-tested exclusively against hand-constructed fixture 10-K text snippets
and a hand-constructed fixture EPA Envirofacts JSON response, not live
calls. The regex extraction patterns, the EPA table/column names, and the
scoring heuristic's weights must all be validated against live data before
production use. No scores or metrics are fabricated: filings/entities that
cannot be resolved to an existing entity are skipped and logged, and a
record with no extractable signal produces no score component (score stays
``None``), never an invented number.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector
from src.ingestion.redis_rate_limiter import RedisRateLimiter

logger = logging.getLogger(__name__)

# Disk-persisted EPA Envirofacts cache — each backfill pass runs this
# connector in a fresh short-lived subprocess, so an in-memory-only cache
# (like the old ``_epa_cache``) never survives past one ~8-minute pass and
# every pass re-queries EPA for companies already looked up. Persisting to
# disk means a company's EPA lookup happens at most once, ever.
_EPA_CACHE_PATH = Path(__file__).resolve().parent.parent.parent / ".cache" / "epa_envirofacts_cache.json"

# SEC EDGAR endpoints (same as edgar_esg.py)
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
FULL_TEXT_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{primary_doc}"

# Only 10-K: environmental/social disclosure signals (risk factors, MD&A,
# sustainability sections) live there. DEF 14A (proxy) is governance-focused
# and already covered by edgar_esg.py.
ESG_FILING_TYPES = {"10-K"}

# Provider label written to ESGScore.provider. Deliberately NOT a real
# vendor name (MSCI/Sustainalytics/etc) -- this is a disclosure-based proxy
# derived from public filings + EPA data, not a licensed third-party rating.
PROVIDER = "EDGAR_DISCLOSURE_PROXY"

# --------------------------------------------------------------------------
# Regex patterns -- honest, deterministic disclosure-signal extraction.
# Each pattern is intentionally narrow (mirrors edgar_esg.py's
# _BOARD_INDEPENDENCE_PATTERN style): better to miss a disclosure than to
# mis-extract one.
# --------------------------------------------------------------------------

_GHG_EMISSIONS_PATTERN = re.compile(
    r"(?:total\s+)?(?:scope\s+1\s+and\s+(?:scope\s+)?2\s+)?"
    r"(?:ghg\s+|greenhouse\s+gas\s+)?emissions\s+of\s+(?:approximately\s+)?"
    r"([\d,]+(?:\.\d+)?)\s*(metric\s+tons?|tons?|tco2e|mt\s*co2e)",
    re.IGNORECASE,
)

_RENEWABLE_PCT_PATTERN = re.compile(
    r"(\d{1,3})%\s+of\s+(?:our\s+)?(?:total\s+)?(?:energy|electricity|power)\s+"
    r"(?:consumption\s+)?(?:was|is|came from)\s+(?:derived from\s+)?renewable",
    re.IGNORECASE,
)

_NET_ZERO_PATTERN = re.compile(
    r"(?:net[- ]zero|carbon\s+neutral(?:ity)?)\s+(?:emissions\s+)?by\s+(\d{4})",
    re.IGNORECASE,
)

_WORKFORCE_DIVERSITY_PATTERN = re.compile(
    r"(\d{1,3})%\s+of\s+(?:our\s+)?(?:global\s+)?workforce\s+identif(?:y|ies)\s+as\s+"
    r"(women|female|racially\s+diverse|people\s+of\s+color|underrepresented\s+minorities)",
    re.IGNORECASE,
)

_SAFETY_TRIR_PATTERN = re.compile(
    r"(?:total\s+recordable\s+incident\s+rate|TRIR)\s*(?:\(TRIR\))?\s+of\s+([\d]+(?:\.\d+)?)",
    re.IGNORECASE,
)

_TURNOVER_PATTERN = re.compile(
    r"(?:voluntary\s+)?(?:employee\s+)?turnover\s+rate\s+of\s+([\d]+(?:\.\d+)?)%",
    re.IGNORECASE,
)

# --------------------------------------------------------------------------
# EPA Envirofacts (secondary, best-effort, real-data enrichment)
# --------------------------------------------------------------------------

# EPA Envirofacts GHG Reporting Program tables/columns. Best-effort names
# per EPA's documented REST convention -- see the FLAG above; not validated
# against a live response.
EPA_GHGRP_FACILITY_TABLE = "PUB_DIM_FACILITY"
EPA_GHGRP_FACILITY_NAME_COLUMN = "FACILITY_NAME"
EPA_GHGRP_FACILITY_ID_COLUMN = "FACILITY_ID"
EPA_GHGRP_EMISSIONS_TABLE = "PUB_FACTS_SECTOR_GHG_EMISSION"
EPA_GHGRP_EMISSIONS_VALUE_COLUMN = "CO2E_EMISSION"
EPA_GHGRP_REPORTING_YEAR_COLUMN = "REPORTING_YEAR"


class _PlainTextExtractor(HTMLParser):
    """Collect text nodes, dropping <script>/<style> content (stdlib only —
    no bs4/lxml dependency, matching the pattern in edgar_proxy.py)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in ("script", "style"):
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._parts.append(data)

    def text(self) -> str:
        return " ".join("".join(self._parts).split())


def _strip_tags(html: str) -> str:
    """Return whitespace-collapsed plain text from an HTML/inline-XBRL document.

    SEC 10-K documents fetched via ``FULL_TEXT_URL`` are inline-XBRL HTML —
    every disclosed number (and often surrounding words) is wrapped in
    ``<ix:nonFraction>``/``<span>`` tags. The regex patterns below expect
    plain prose like "emissions of 1,250,000 metric tons"; run directly
    against raw markup they never match, since the tag boundaries break the
    phrase apart. Stripping tags reconstructs the original word sequence.
    """
    parser = _PlainTextExtractor()
    try:
        parser.feed(html)
    except Exception:  # pragma: no cover - malformed HTML
        pass
    return parser.text()


def _to_decimal(value: Any) -> Decimal | None:
    if value in (None, "", "N/A"):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


class EdgarESGEnvironmentalConnector(BaseConnector):
    """Parse ESG environmental/social disclosure signals from SEC 10-K filings."""

    name = "EDGAR ESG Environmental"
    connector_type = "BATCH_API"
    data_domain = "ESG"

    def __init__(
        self,
        cik_list: list[str] | None = None,
        filing_limit: int = 5,
        enable_epa_enrichment: bool = True,
        epa_base_url: str | None = None,
        concurrency: int = 5,
    ) -> None:
        """Initialize the connector.

        Args:
            cik_list: List of CIK numbers to process. If None, must be set
                      before calling extract().
            filing_limit: Max recent 10-K filings to fetch per company.
            enable_epa_enrichment: Whether to attempt the secondary EPA
                      Envirofacts GHGRP lookup (best-effort; skipped
                      gracefully on any failure or no facility match).
            epa_base_url: Override for settings.EPA_ENVIROFACTS_BASE_URL.
            concurrency: Max CIKs processed concurrently in extract(). Safe
                      to raise — every actual HTTP call still goes through
                      the shared ``rate_limiter`` token bucket, so this only
                      controls how many CIKs have requests in flight at
                      once, not the aggregate request rate.
        """
        self.cik_list = cik_list or []
        self.filing_limit = filing_limit
        self.enable_epa_enrichment = enable_epa_enrichment
        self.epa_base_url = (epa_base_url or getattr(settings, "EPA_ENVIROFACTS_BASE_URL", "")).rstrip("/")
        self.concurrency = max(1, concurrency)
        self.rate_limiter = RedisRateLimiter(key="sec_edgar", max_requests=settings.SEC_RATE_LIMIT, per_seconds=1.0)
        self.headers = {"User-Agent": settings.SEC_USER_AGENT}
        self._client: httpx.AsyncClient | None = None
        # Disk-persisted so repeat lookups across separate backfill passes
        # (each a fresh subprocess) are avoided, not just repeat filings for
        # the same CIK within one run. Best-effort load: a missing/corrupt
        # cache file just starts empty, never blocks extraction.
        self._epa_cache: dict[str, dict[str, Any] | None] = self._load_epa_cache()

    @staticmethod
    def _load_epa_cache() -> dict[str, dict[str, Any] | None]:
        try:
            raw = json.loads(_EPA_CACHE_PATH.read_text())
        except (OSError, json.JSONDecodeError):
            return {}
        for entry in raw.values():
            if entry and entry.get("co2e_emission_metric_tons") is not None:
                entry["co2e_emission_metric_tons"] = _to_decimal(
                    entry["co2e_emission_metric_tons"]
                )
        return raw

    def _save_epa_cache(self) -> None:
        try:
            _EPA_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            _EPA_CACHE_PATH.write_text(
                json.dumps(self._epa_cache, default=str)
            )
        except OSError as exc:  # noqa: BLE001 - best-effort persistence
            logger.debug("[%s] Failed to persist EPA cache: %s", self.name, exc)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(headers=self.headers, timeout=30.0)
        return self._client

    async def _sec_get(self, url: str) -> httpx.Response:
        """Make a rate-limited GET request to SEC EDGAR."""
        await self.rate_limiter.acquire()
        client = await self._get_client()
        resp = await client.get(url)
        resp.raise_for_status()
        return resp

    async def _fetch_filing_index(self, cik: str) -> list[dict[str, Any]]:
        """Fetch recent 10-K filing metadata (+ entity name) for a CIK."""
        padded_cik = cik.zfill(10)
        url = SUBMISSIONS_URL.format(cik=padded_cik)

        try:
            resp = await self._sec_get(url)
            data = resp.json()
        except Exception as e:
            logger.error("Failed to fetch submissions for CIK %s: %s", cik, e)
            return []

        entity_name = data.get("name", "")
        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        accessions = recent.get("accessionNumber", [])
        primary_docs = recent.get("primaryDocument", [])
        filing_dates = recent.get("filingDate", [])

        filings: list[dict[str, Any]] = []
        counts: dict[str, int] = {}

        for i, form in enumerate(forms):
            if form not in ESG_FILING_TYPES:
                continue
            if counts.get(form, 0) >= self.filing_limit:
                continue

            counts[form] = counts.get(form, 0) + 1
            accession_clean = accessions[i].replace("-", "")
            filings.append({
                "cik": cik,
                "entity_name": entity_name,
                "form_type": form,
                "accession_number": accessions[i],
                "primary_document": primary_docs[i],
                "filing_date": filing_dates[i],
                "url": FULL_TEXT_URL.format(
                    cik=cik,
                    accession=accession_clean,
                    primary_doc=primary_docs[i],
                ),
            })

        return filings

    async def _fetch_filing_text(self, filing: dict[str, Any]) -> str | None:
        """Fetch a filing document and return its plain text (tags stripped)."""
        try:
            resp = await self._sec_get(filing["url"])
            return _strip_tags(resp.text)
        except Exception as e:
            logger.warning(
                "Failed to fetch filing text for CIK %s (%s): %s",
                filing["cik"],
                filing["accession_number"],
                e,
            )
            return None

    async def _fetch_epa_emissions(self, entity_name: str) -> dict[str, Any] | None:
        """Best-effort EPA Envirofacts GHGRP lookup by company/facility name.

        Returns a dict with facility_name/facility_id/co2e_emission_metric_tons
        on a match, or None if no facility matched or the lookup failed for
        any reason (network error, unexpected schema, etc). Never raises --
        this is a secondary enrichment, not a hard dependency.
        """
        if not self.enable_epa_enrichment or not self.epa_base_url or not entity_name:
            return None
        if entity_name in self._epa_cache:
            return self._epa_cache[entity_name]

        result: dict[str, Any] | None = None
        try:
            client = await self._get_client()
            # Trim common corporate suffixes/punctuation for a looser match
            # (e.g. "Acme Corp, Inc." -> "Acme Corp").
            search_name = entity_name.split(",")[0].strip()

            facility_url = (
                f"{self.epa_base_url}/{EPA_GHGRP_FACILITY_TABLE}/"
                f"{EPA_GHGRP_FACILITY_NAME_COLUMN}/CONTAINING/"
                f"{quote(search_name)}/JSON"
            )
            resp = await client.get(facility_url)
            resp.raise_for_status()
            facilities = resp.json()
            if not isinstance(facilities, list) or not facilities:
                self._epa_cache[entity_name] = None
                return None

            facility = facilities[0]
            facility_id = facility.get(EPA_GHGRP_FACILITY_ID_COLUMN) or facility.get(
                EPA_GHGRP_FACILITY_ID_COLUMN.lower()
            )
            if not facility_id:
                self._epa_cache[entity_name] = None
                return None

            emissions_url = (
                f"{self.epa_base_url}/{EPA_GHGRP_EMISSIONS_TABLE}/"
                f"{EPA_GHGRP_FACILITY_ID_COLUMN}/{facility_id}/JSON"
            )
            eresp = await client.get(emissions_url)
            eresp.raise_for_status()
            emission_rows = eresp.json()

            co2e = None
            if isinstance(emission_rows, list) and emission_rows:
                emission_rows = sorted(
                    emission_rows,
                    key=lambda r: r.get(EPA_GHGRP_REPORTING_YEAR_COLUMN)
                    or r.get(EPA_GHGRP_REPORTING_YEAR_COLUMN.lower())
                    or 0,
                    reverse=True,
                )
                latest = emission_rows[0]
                raw_val = latest.get(EPA_GHGRP_EMISSIONS_VALUE_COLUMN) or latest.get(
                    EPA_GHGRP_EMISSIONS_VALUE_COLUMN.lower()
                )
                co2e = _to_decimal(raw_val)

            result = {
                "facility_name": facility.get(EPA_GHGRP_FACILITY_NAME_COLUMN)
                or facility.get(EPA_GHGRP_FACILITY_NAME_COLUMN.lower()),
                "facility_id": str(facility_id),
                "co2e_emission_metric_tons": co2e,
            }
        except Exception as exc:  # noqa: BLE001 - best-effort secondary enrichment
            logger.debug(
                "[%s] EPA Envirofacts lookup failed for %r (skipping enrichment): %s",
                self.name,
                entity_name,
                exc,
            )
            result = None

        self._epa_cache[entity_name] = result
        return result

    async def _extract_one(self, cik: str) -> list[dict[str, Any]]:
        """Fetch + assemble records for a single CIK (filing index, EPA, filing text)."""
        filings = await self._fetch_filing_index(cik)
        logger.info(
            "  EDGAR ESG Environmental: CIK %s — found %d 10-K filing(s)",
            cik,
            len(filings),
        )
        if not filings:
            return []

        entity_name = filings[0].get("entity_name")
        epa_data = await self._fetch_epa_emissions(entity_name) if entity_name else None

        records: list[dict[str, Any]] = []
        for filing in filings:
            text = await self._fetch_filing_text(filing)
            if text:
                records.append({
                    "cik": cik,
                    "entity_name": entity_name,
                    "form_type": filing["form_type"],
                    "accession_number": filing["accession_number"],
                    "filing_date": filing["filing_date"],
                    "text": text,
                    "epa_emissions": epa_data,
                })
        return records

    async def extract(self) -> list[dict[str, Any]]:
        """Pull 10-K filing text from SEC EDGAR, with best-effort EPA enrichment.

        CIKs are processed concurrently (bounded by ``self.concurrency``) —
        this is I/O-bound work gated by the shared ``rate_limiter``, so
        overlapping CIKs' waits doesn't exceed SEC's request rate, it just
        stops one company's 6 sequential round-trips from blocking the next
        company's from starting.
        """
        if not self.cik_list:
            logger.warning("[%s] No CIK list provided — skipping extraction", self.name)
            return []

        semaphore = asyncio.Semaphore(self.concurrency)

        async def _bounded(cik: str) -> list[dict[str, Any]]:
            async with semaphore:
                return await self._extract_one(cik)

        results = await asyncio.gather(*(_bounded(cik) for cik in self.cik_list))
        self._save_epa_cache()
        return [rec for batch in results for rec in batch]

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate extracted filing records."""
        valid: list[dict[str, Any]] = []
        for rec in records:
            if not rec.get("cik"):
                continue
            if not rec.get("text") or len(rec["text"]) < 500:
                logger.debug(
                    "Skipping filing for CIK %s — text too short (%d chars)",
                    rec.get("cik"),
                    len(rec.get("text", "")),
                )
                continue
            if not rec.get("filing_date"):
                continue
            valid.append(rec)
        return valid

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Extract environmental/social disclosure metrics + scores. Pure (no I/O)."""
        transformed: list[dict[str, Any]] = []

        for rec in records:
            text = rec["text"]
            cik = rec["cik"]
            filing_date = rec["filing_date"]
            form_type = rec["form_type"]
            accession = rec["accession_number"]
            epa = rec.get("epa_emissions")

            metrics: list[dict[str, Any]] = []

            # --- Environmental disclosure signals ---
            ghg_tons, ghg_unit = self._extract_ghg_emissions(text)
            if ghg_tons is not None:
                metrics.append({
                    "metric_type": "GHG_EMISSIONS_DISCLOSED",
                    "metric_category": "ENVIRONMENTAL",
                    "value": float(ghg_tons),
                    "unit": ghg_unit,
                    "source": f"SEC_{form_type}",
                })

            renewable_pct = self._extract_renewable_pct(text)
            if renewable_pct is not None:
                metrics.append({
                    "metric_type": "RENEWABLE_ENERGY_PCT",
                    "metric_category": "ENVIRONMENTAL",
                    "value": renewable_pct,
                    "unit": "pct",
                    "source": f"SEC_{form_type}",
                })

            net_zero_year = self._extract_net_zero_year(text)
            if net_zero_year is not None:
                metrics.append({
                    "metric_type": "NET_ZERO_TARGET_YEAR",
                    "metric_category": "ENVIRONMENTAL",
                    "value": float(net_zero_year),
                    "unit": "year",
                    "source": f"SEC_{form_type}",
                })

            epa_verified = False
            if epa and epa.get("co2e_emission_metric_tons") is not None:
                epa_verified = True
                metrics.append({
                    "metric_type": "GHG_EMISSIONS_EPA_VERIFIED",
                    "metric_category": "ENVIRONMENTAL",
                    "value": float(epa["co2e_emission_metric_tons"]),
                    "unit": "metric tons CO2e",
                    "source": "EPA_ENVIROFACTS_GHGRP",
                })

            # --- Social disclosure signals ---
            diversity_pct, diversity_category = self._extract_workforce_diversity(text)
            if diversity_pct is not None:
                metrics.append({
                    "metric_type": "WORKFORCE_DIVERSITY_PCT",
                    "metric_category": "SOCIAL",
                    "value": diversity_pct,
                    "unit": f"pct ({diversity_category})" if diversity_category else "pct",
                    "source": f"SEC_{form_type}",
                })

            trir = self._extract_safety_trir(text)
            if trir is not None:
                metrics.append({
                    "metric_type": "SAFETY_INCIDENT_RATE_TRIR",
                    "metric_category": "SOCIAL",
                    "value": trir,
                    "unit": "incidents per 200,000 hours",
                    "source": f"SEC_{form_type}",
                })

            turnover_pct = self._extract_turnover_rate(text)
            if turnover_pct is not None:
                metrics.append({
                    "metric_type": "EMPLOYEE_TURNOVER_RATE",
                    "metric_category": "SOCIAL",
                    "value": turnover_pct,
                    "unit": "pct",
                    "source": f"SEC_{form_type}",
                })

            try:
                filing_year = date.fromisoformat(filing_date).year
            except (ValueError, TypeError):
                filing_year = datetime.now(timezone.utc).year

            environmental_score = self._score_environmental(
                ghg_tons, renewable_pct, net_zero_year, filing_year, epa_verified
            )
            social_score = self._score_social(diversity_pct, trir, turnover_pct)

            transformed.append({
                "cik": cik,
                "filing_date": filing_date,
                "form_type": form_type,
                "accession_number": accession,
                "metrics": metrics,
                "environmental_score": environmental_score,
                "social_score": social_score,
            })

        return transformed

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        """Upsert ESGScore.environmental_score/social_score + write ESGMetric rows."""
        from src.models.entity import EntityIdentifier
        from src.models.esg import ESGMetric, ESGScore

        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        if getattr(self, "dry_run", False):
            return stats

        for rec in records:
            try:
                cik = rec["cik"]
                as_of_date = date.fromisoformat(rec["filing_date"])

                result = await session.execute(
                    select(EntityIdentifier).where(
                        EntityIdentifier.identifier_type == "CIK",
                        EntityIdentifier.identifier_value == cik,
                    )
                )
                eid_row = result.scalar_one_or_none()
                if eid_row is None:
                    logger.info(
                        "[%s] skipping CIK %s — entity not resolvable "
                        "(no fabricated score row created)",
                        self.name,
                        cik,
                    )
                    stats["skipped"] += 1
                    continue
                entity_id = eid_row.entity_id

                env_score = rec.get("environmental_score")
                soc_score = rec.get("social_score")

                # Upsert by (entity_id, provider, as_of_date) -- the unique
                # index already on esg_scores.
                existing = await session.execute(
                    select(ESGScore).where(
                        ESGScore.entity_id == entity_id,
                        ESGScore.provider == PROVIDER,
                        ESGScore.as_of_date == as_of_date,
                    )
                )
                existing_score = existing.scalar_one_or_none()
                if existing_score is not None:
                    if env_score is not None:
                        existing_score.environmental_score = Decimal(str(env_score))
                    if soc_score is not None:
                        existing_score.social_score = Decimal(str(soc_score))
                    stats["updated"] += 1
                elif env_score is not None or soc_score is not None:
                    session.add(
                        ESGScore(
                            score_id=uuid.uuid4(),
                            entity_id=entity_id,
                            provider=PROVIDER,
                            as_of_date=as_of_date,
                            environmental_score=Decimal(str(env_score))
                            if env_score is not None
                            else None,
                            social_score=Decimal(str(soc_score))
                            if soc_score is not None
                            else None,
                            esg_rating=None,  # Disclosure proxy; no composite rating.
                        )
                    )
                    stats["inserted"] += 1
                else:
                    # No environmental/social signal extracted at all for
                    # this filing -- nothing to write, not even an empty row.
                    stats["skipped"] += 1

                for metric_data in rec.get("metrics", []):
                    metric = ESGMetric(
                        metric_id=uuid.uuid4(),
                        entity_id=entity_id,
                        metric_type=metric_data["metric_type"],
                        metric_category=metric_data.get("metric_category"),
                        period_end_date=as_of_date,
                        period_type="ANNUAL",
                        value=Decimal(str(metric_data["value"]))
                        if metric_data.get("value") is not None
                        else None,
                        unit=metric_data.get("unit"),
                        is_reported=True,
                        source=metric_data.get("source", PROVIDER),
                    )
                    session.add(metric)
                    stats["inserted"] += 1

                await session.flush()

            except Exception as e:
                logger.error(
                    "Error loading environmental/social ESG data for CIK %s: %s",
                    rec.get("cik"),
                    e,
                )
                stats["errors"] += 1

        await session.flush()
        return stats

    # ------------------------------------------------------------------
    # Private extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_ghg_emissions(text: str) -> tuple[Decimal | None, str | None]:
        """Extract a disclosed GHG emissions figure ("emissions of X tons")."""
        match = _GHG_EMISSIONS_PATTERN.search(text)
        if not match:
            return None, None
        try:
            value = Decimal(match.group(1).replace(",", ""))
        except InvalidOperation:
            return None, None
        return value, match.group(2).strip()

    @staticmethod
    def _extract_renewable_pct(text: str) -> float | None:
        """Extract a disclosed renewable-energy percentage."""
        match = _RENEWABLE_PCT_PATTERN.search(text)
        if not match:
            return None
        try:
            pct = float(match.group(1))
        except ValueError:
            return None
        return pct if 0 <= pct <= 100 else None

    @staticmethod
    def _extract_net_zero_year(text: str) -> int | None:
        """Extract a disclosed net-zero / carbon-neutrality target year."""
        match = _NET_ZERO_PATTERN.search(text)
        if not match:
            return None
        try:
            year = int(match.group(1))
        except ValueError:
            return None
        return year if 2020 <= year <= 2100 else None

    @staticmethod
    def _extract_workforce_diversity(text: str) -> tuple[float | None, str | None]:
        """Extract a disclosed workforce-diversity percentage + category."""
        match = _WORKFORCE_DIVERSITY_PATTERN.search(text)
        if not match:
            return None, None
        try:
            pct = float(match.group(1))
        except ValueError:
            return None, None
        if not (0 <= pct <= 100):
            return None, None
        return pct, match.group(2).strip().lower()

    @staticmethod
    def _extract_safety_trir(text: str) -> float | None:
        """Extract a disclosed Total Recordable Incident Rate (TRIR)."""
        match = _SAFETY_TRIR_PATTERN.search(text)
        if not match:
            return None
        try:
            value = float(match.group(1))
        except ValueError:
            return None
        # Sanity bound -- real-world TRIR values are rarely above ~20.
        return value if 0 <= value <= 50 else None

    @staticmethod
    def _extract_turnover_rate(text: str) -> float | None:
        """Extract a disclosed employee turnover rate."""
        match = _TURNOVER_PATTERN.search(text)
        if not match:
            return None
        try:
            value = float(match.group(1))
        except ValueError:
            return None
        return value if 0 <= value <= 100 else None

    # ------------------------------------------------------------------
    # Scoring heuristic
    #
    # Both scores are a *disclosure-based proxy*, not an authoritative
    # third-party ESG rating: they reward the presence and directional
    # favorability of a small set of regex-extractable disclosures, not a
    # comprehensive or benchmarked assessment of environmental/social
    # performance. Absolute magnitudes we cannot benchmark (e.g. raw GHG
    # tonnage without industry-normalized context) get a flat "disclosed"
    # credit rather than a magnitude-graded score.
    # ------------------------------------------------------------------

    @staticmethod
    def _score_environmental(
        ghg_tons: Decimal | None,
        renewable_pct: float | None,
        net_zero_year: int | None,
        filing_year: int,
        epa_verified: bool,
    ) -> float | None:
        components: list[float] = []
        if ghg_tons is not None:
            # Disclosure itself is the honest signal here -- we cannot grade
            # absolute tonnage without industry-normalized (e.g. per-revenue
            # or per-unit-output) benchmarks this connector does not have.
            components.append(65.0)
        if renewable_pct is not None:
            components.append(min(max(renewable_pct, 0.0), 100.0))
        if net_zero_year is not None:
            years_out = net_zero_year - filing_year
            # Nearer-term, more-credible-looking targets score higher;
            # targets far in the future taper off. Crude, documented proxy.
            component = max(0.0, min(100.0, 100.0 - max(0, years_out - 5) * 3))
            components.append(component)
        if epa_verified:
            # A real EPA GHGRP facility match is an independently sourced
            # transparency signal layered on top of the text-disclosure
            # proxy -- again a flat "verified reporting exists" credit, not
            # a magnitude grade.
            components.append(80.0)
        if not components:
            return None
        return round(sum(components) / len(components), 2)

    @staticmethod
    def _score_social(
        diversity_pct: float | None,
        trir: float | None,
        turnover_pct: float | None,
    ) -> float | None:
        components: list[float] = []
        if diversity_pct is not None:
            # Scaled against a 40%-representation reference point, mirroring
            # edgar_esg.py's board-diversity scoring approach -- not a claim
            # about what an "ideal" workforce composition is.
            components.append(min(diversity_pct / 40.0, 1.0) * 100)
        if trir is not None:
            # Lower TRIR is better; ~5.0 treated as the zero-credit ceiling
            # for this rough proxy (a crude industry-agnostic reference).
            components.append(max(0.0, min(100.0, 100.0 - trir * 20)))
        if turnover_pct is not None:
            # Lower turnover is better; >=50% annual turnover -> zero credit.
            components.append(max(0.0, min(100.0, 100.0 - turnover_pct * 2)))
        if not components:
            return None
        return round(sum(components) / len(components), 2)

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
