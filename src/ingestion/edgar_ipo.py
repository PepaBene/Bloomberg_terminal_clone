"""SEC EDGAR IPO connector (S-1 / 424B filings).

Tracks the IPO lifecycle from registration and prospectus filings:

* S-1 / S-1/A — registration statement → IPO ``FILED``
* 424B1..5 / 424B — final prospectus (pricing) → IPO ``PRICED``

CIK-driven, following the ``edgar_8k`` submissions pattern. The connector
records the filing event, dates and accession; the S-1 accession is stored on
the IPOEvent.

FLAG — needs-live-data-validation:
    Offer price, shares offered, proceeds and the underwriter syndicate live in
    the free-text 424B prospectus body, not in the structured submissions
    index. Parsing those requires the live prospectus documents and is NOT
    attempted here — this connector establishes the lifecycle events only.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector
from src.ingestion.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

S1_FORMS = ("S-1", "S-1/A")
PROSPECTUS_FORMS = ("424B1", "424B2", "424B3", "424B4", "424B5", "424B", "424B7", "424B8")


class EdgarIpoConnector(BaseConnector):
    """Ingest IPO lifecycle events from SEC EDGAR S-1 / 424B filings."""

    name = "SEC EDGAR IPO"
    connector_type = "BATCH_API"
    data_domain = "CORPORATE_ACTIONS"

    def __init__(self, ciks: list[str] | None = None, days_back: int = 365):
        self.ciks = ciks or []
        self.days_back = days_back
        self.rate_limiter = RateLimiter(max_requests=settings.SEC_RATE_LIMIT, per_seconds=1.0)
        self.headers = {"User-Agent": settings.SEC_USER_AGENT}
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(headers=self.headers, timeout=30.0)
        return self._client

    async def _fetch_submissions(self, cik: str) -> dict[str, Any] | None:
        url = SUBMISSIONS_URL.format(cik=cik.zfill(10))
        await self.rate_limiter.acquire()
        client = await self._get_client()
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # pragma: no cover - network
            logger.warning("Failed to fetch submissions for CIK %s: %s", cik, exc)
            return None

    def _extract_ipo_filings(
        self, submissions: dict[str, Any], cik: str
    ) -> list[dict[str, Any]]:
        """Extract S-1 / 424B filings for a CIK. Pure (no I/O)."""
        recent = submissions.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        accessions = recent.get("accessionNumber", [])
        filed = recent.get("filingDate", [])
        entity_name = submissions.get("name", "")

        out: list[dict[str, Any]] = []
        for i, form in enumerate(forms):
            if form in S1_FORMS:
                kind = "S1"
            elif form in PROSPECTUS_FORMS:
                kind = "PROSPECTUS"
            else:
                continue
            out.append(
                {
                    "cik": cik,
                    "entity_name": entity_name,
                    "form": form,
                    "kind": kind,
                    "accession_number": accessions[i] if i < len(accessions) else "",
                    "filing_date": filed[i] if i < len(filed) else "",
                }
            )
        return out

    async def extract(self) -> list[dict[str, Any]]:
        if not self.ciks:
            logger.warning("No CIKs configured — skipping IPO extraction")
            return []
        from datetime import timedelta

        cutoff = date.today() - timedelta(days=self.days_back)
        records: list[dict[str, Any]] = []
        for cik in self.ciks:
            submissions = await self._fetch_submissions(cik)
            if submissions is None:
                continue
            for filing in self._extract_ipo_filings(submissions, cik):
                try:
                    if date.fromisoformat(filing["filing_date"]) < cutoff:
                        continue
                except (ValueError, TypeError):
                    continue
                records.append(filing)
        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            r
            for r in records
            if r.get("cik") and r.get("accession_number") and r.get("filing_date")
        ]

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Map S-1 / 424B filings to IPOEvent field dicts. Pure (no I/O)."""
        out: list[dict[str, Any]] = []
        for r in records:
            if r["kind"] == "S1":
                out.append(
                    {
                        "cik": r["cik"],
                        "status": "FILED",
                        "s1_filing_date": r["filing_date"],
                        "s1_accession_number": r["accession_number"][:25],
                        "pricing_date": None,
                        "accession_number": r["accession_number"],
                    }
                )
            else:  # PROSPECTUS
                out.append(
                    {
                        "cik": r["cik"],
                        "status": "PRICED",
                        "s1_filing_date": None,
                        "s1_accession_number": None,
                        "pricing_date": r["filing_date"],
                        "accession_number": r["accession_number"],
                    }
                )
        logger.info("IPO: transformed %d lifecycle events", len(out))
        return out

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        from src.models.entity import EntityIdentifier
        from src.models.ipo import IPOEvent

        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        if getattr(self, "dry_run", False):
            return stats

        for rec in records:
            try:
                ident = (
                    await session.execute(
                        select(EntityIdentifier).where(
                            EntityIdentifier.identifier_type == "CIK",
                            EntityIdentifier.identifier_value == rec["cik"],
                        )
                    )
                ).scalar_one_or_none()
                entity_id = ident.entity_id if ident else None

                accession = rec.get("accession_number")
                existing = (
                    await session.execute(
                        select(IPOEvent).where(
                            IPOEvent.entity_id == entity_id,
                            IPOEvent.status == rec["status"],
                        )
                    )
                ).scalars().all()
                if any(
                    (e.source_filings or []) and accession in (e.source_filings or [])
                    for e in existing
                ):
                    stats["skipped"] += 1
                    continue

                session.add(
                    IPOEvent(
                        ipo_id=uuid.uuid4(),
                        entity_id=entity_id,
                        status=rec["status"],
                        s1_filing_date=date.fromisoformat(rec["s1_filing_date"])
                        if rec.get("s1_filing_date")
                        else None,
                        s1_accession_number=rec.get("s1_accession_number"),
                        pricing_date=date.fromisoformat(rec["pricing_date"])
                        if rec.get("pricing_date")
                        else None,
                        source_filings=[accession] if accession else None,
                    )
                )
                stats["inserted"] += 1
            except Exception:  # pragma: no cover - defensive
                logger.exception("[%s] failed to load IPO event", self.name)
                stats["errors"] += 1

        await session.flush()
        return stats

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
