"""SEC EDGAR business/geographic segment connector (Spec 5.3).

Parses segment-level facts from the SEC XBRL companyfacts JSON and maps them to
the ``segment_data`` table. Uses its own fetch (does not touch ``edgar_xbrl``).

IMPORTANT — needs live-data validation:
    The SEC ``companyfacts`` endpoint flattens facts to consolidated values and
    generally does NOT expose the dimensional ``us-gaap`` segment *members*
    (e.g. ``StatementBusinessSegmentsAxis``) that identify a segment. Reliable
    segment extraction requires the dimensional R-files / Frames data of an
    individual filing. This connector is therefore implemented *to-pattern*:
    :func:`parse_segments` reads a per-entry ``segment`` member label and its
    ``axis``/``dimension`` when present (the shape live dimensional XBRL
    carries) and is exercised by a mocked-payload unit test. It must be
    validated against real dimensional SEC data before production use.

    Segment kind (BUSINESS vs GEOGRAPHIC) is derived from the dimensional axis
    via :func:`_classify_segment_type` — a geographical axis
    (``srt:StatementGeographicalAxis``) yields ``"GEOGRAPHIC"``, otherwise
    ``"BUSINESS"``. This feeds the geographic-revenue surfaces in
    ``competitive.py`` / ``company_intel_p2.py`` / ``research_primers.py``,
    which filter on ``segment_type == "GEOGRAPHIC"``.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector
from src.ingestion.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

# us-gaap concepts that carry segment-level revenue / profitability.
_REVENUE_CONCEPTS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
)
_OPERATING_INCOME_CONCEPTS = (
    "OperatingIncomeLoss",
    "SegmentReportingInformationOperatingIncomeLoss",
)
_ASSET_CONCEPTS = ("Assets", "SegmentReportingInformationAssets")

_ACCEPTED_FORMS = ("10-K", "10-Q", "10-K/A", "10-Q/A")

# Substrings that mark a dimensional axis (or member label) as a GEOGRAPHIC
# rather than an operating/BUSINESS segment. Live dimensional XBRL identifies
# the segment *kind* by its axis: ``srt:StatementGeographicalAxis`` (geographic
# revenue breakdowns) vs ``us-gaap:StatementBusinessSegmentsAxis`` (operating
# segments). Matched case-insensitively.
_GEOGRAPHIC_AXIS_HINTS = ("geograph", "country", "region")


def _classify_segment_type(axis: str | None, segment_type: str | None) -> str:
    """Classify a dimensional segment fact as GEOGRAPHIC or BUSINESS.

    Prefers an explicit ``segment_type`` on the entry, then infers from the
    dimensional axis, and defaults to BUSINESS. Previously every row was
    hardcoded ``"BUSINESS"``, so the three GEOGRAPHIC consumers
    (competitive / company_intel_p2 / research_primers) never matched a row
    and all geographic-revenue surfaces were permanently blank.
    """
    if segment_type:
        st = segment_type.strip().upper()
        if st in ("GEOGRAPHIC", "BUSINESS"):
            return st
    if axis and any(hint in axis.lower() for hint in _GEOGRAPHIC_AXIS_HINTS):
        return "GEOGRAPHIC"
    return "BUSINESS"


def _iter_segment_entries(
    us_gaap: dict[str, Any], concepts: tuple[str, ...]
) -> list[dict[str, Any]]:
    """Yield entries that carry a segment member, across the given concepts."""
    out: list[dict[str, Any]] = []
    for concept_name in concepts:
        concept = us_gaap.get(concept_name)
        if not concept:
            continue
        for entries in concept.get("units", {}).values():
            for entry in entries:
                # A segment fact is identified by a dimensional member label.
                segment = entry.get("segment") or entry.get("member")
                if not segment:
                    continue
                if entry.get("form") not in _ACCEPTED_FORMS:
                    continue
                if entry.get("end") is None or entry.get("val") is None:
                    continue
                # The dimensional axis (when present) tells us whether this is
                # a business or geographic segment.
                axis = entry.get("axis") or entry.get("dimension")
                out.append(
                    {
                        "segment": segment,
                        "segment_type": _classify_segment_type(
                            axis, entry.get("segment_type")
                        ),
                        "end": entry["end"],
                        "form": entry["form"],
                        "val": float(entry["val"]),
                        "fy": entry.get("fy"),
                        "fp": entry.get("fp"),
                    }
                )
    return out


def parse_segments(
    us_gaap: dict[str, Any],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    """Parse segment facts into a dict keyed by (period_end, segment_type, name).

    Keyed on ``segment_type`` as well as name so a geographic and a business
    segment that happen to share a label don't collide. Pure function — no
    I/O — so it is directly unit-testable on a sample companyfacts-style
    payload.
    """
    segments: dict[tuple[str, str, str], dict[str, Any]] = defaultdict(dict)

    def _apply(concept_group: tuple[str, ...], field: str) -> None:
        for e in _iter_segment_entries(us_gaap, concept_group):
            key = (e["end"], e["segment_type"], e["segment"])
            rec = segments[key]
            rec.setdefault("segment_name", e["segment"])
            rec.setdefault("segment_type", e["segment_type"])
            rec.setdefault("period_end_date", e["end"])
            rec.setdefault("form", e["form"])
            rec.setdefault("fiscal_year", e.get("fy"))
            # First-seen wins for a given field/period/segment.
            rec.setdefault(field, e["val"])

    _apply(_REVENUE_CONCEPTS, "revenue")
    _apply(_OPERATING_INCOME_CONCEPTS, "operating_income")
    _apply(_ASSET_CONCEPTS, "assets")

    return dict(segments)


class EdgarSegmentsConnector(BaseConnector):
    """Ingest business-segment data from SEC EDGAR XBRL company facts."""

    name = "SEC EDGAR Segments"
    connector_type = "BATCH_API"
    data_domain = "FUNDAMENTALS"

    def __init__(self, ciks: list[str] | None = None):
        self.ciks = ciks or []
        self.rate_limiter = RateLimiter(
            max_requests=settings.SEC_RATE_LIMIT, per_seconds=1.0
        )
        self.headers = {"User-Agent": settings.SEC_USER_AGENT}
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(headers=self.headers, timeout=30.0)
        return self._client

    async def _fetch_company_facts(self, cik: str) -> dict[str, Any] | None:
        url = COMPANY_FACTS_URL.format(cik=cik.zfill(10))
        await self.rate_limiter.acquire()
        client = await self._get_client()
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.warning("Failed to fetch segment facts for CIK %s: %s", cik, e)
            return None
        except Exception as e:  # pragma: no cover - defensive
            logger.error("Unexpected error fetching segments for CIK %s: %s", cik, e)
            return None

    async def extract(self) -> list[dict[str, Any]]:
        if not self.ciks:
            logger.warning("No CIKs configured — skipping segment extraction")
            return []
        records: list[dict[str, Any]] = []
        for cik in self.ciks:
            data = await self._fetch_company_facts(cik)
            if data is None:
                continue
            us_gaap = data.get("facts", {}).get("us-gaap", {})
            if not us_gaap:
                continue
            records.append(
                {
                    "cik": str(data.get("cik", cik)),
                    "entity_name": data.get("entityName", ""),
                    "us_gaap_facts": us_gaap,
                }
            )
        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [r for r in records if r.get("cik") and r.get("us_gaap_facts")]

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Flatten parsed segment facts into SegmentData field dicts (pure)."""
        out: list[dict[str, Any]] = []
        for rec in records:
            segments = parse_segments(rec["us_gaap_facts"])
            for (period_end, segment_type, _segment), fields in segments.items():
                form = fields.get("form", "10-K")
                out.append(
                    {
                        "cik": rec["cik"],
                        "entity_name": rec.get("entity_name", ""),
                        "period_end_date": period_end,
                        "fiscal_year": fields.get("fiscal_year"),
                        "period_type": "ANNUAL" if "10-K" in form else "QUARTERLY",
                        "segment_type": segment_type,
                        "segment_name": fields["segment_name"],
                        "revenue": fields.get("revenue"),
                        "operating_income": fields.get("operating_income"),
                        "assets": fields.get("assets"),
                    }
                )
        logger.info("Transformed %d segment records", len(out))
        return out

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        from datetime import date

        from src.models.entity import EntityIdentifier
        from src.models.fundamentals import FinancialPeriod, SegmentData

        counts = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        if getattr(self, "dry_run", False):
            return counts

        for rec in records:
            try:
                # Resolve entity via CIK.
                entity_ident = (
                    await session.execute(
                        select(EntityIdentifier).where(
                            EntityIdentifier.identifier_type == "CIK",
                            EntityIdentifier.identifier_value == rec["cik"],
                        )
                    )
                ).scalar_one_or_none()
                if entity_ident is None:
                    counts["skipped"] += 1
                    continue
                entity_id = entity_ident.entity_id

                period_end = rec["period_end_date"]
                if isinstance(period_end, str):
                    period_end = date.fromisoformat(period_end)

                # Segment data is filing-specific: resolve the matching period.
                period = (
                    await session.execute(
                        select(FinancialPeriod).where(
                            FinancialPeriod.entity_id == entity_id,
                            FinancialPeriod.period_end_date == period_end,
                        )
                    )
                ).scalars().first()
                if period is None:
                    counts["skipped"] += 1
                    continue

                # Avoid duplicate segment rows for the same period/segment.
                existing = (
                    await session.execute(
                        select(SegmentData).where(
                            SegmentData.period_id == period.period_id,
                            SegmentData.entity_id == entity_id,
                            SegmentData.segment_name == rec["segment_name"],
                            SegmentData.segment_type == rec["segment_type"],
                        )
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    counts["skipped"] += 1
                    continue

                session.add(
                    SegmentData(
                        period_id=period.period_id,
                        entity_id=entity_id,
                        segment_type=rec["segment_type"],
                        segment_name=rec["segment_name"],
                        revenue=rec.get("revenue"),
                        operating_income=rec.get("operating_income"),
                        assets=rec.get("assets"),
                    )
                )
                counts["inserted"] += 1
            except Exception:
                logger.exception("Failed to load segment record")
                counts["errors"] += 1

        await session.flush()
        return counts

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
