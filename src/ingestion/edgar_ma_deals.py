"""SEC EDGAR M&A deal connector (8-K Item 1.01 / 2.01).

Detects merger & acquisition events from 8-K filings:

* Item 1.01 — Entry into a Material Definitive Agreement (e.g. a signed merger
  agreement) → deal ANNOUNCED
* Item 2.01 — Completion of Acquisition or Disposition of Assets → deal
  COMPLETED

CIK-driven, following the ``edgar_8k`` pattern. The filer is recorded as the
acquirer (denormalized name + resolved entity_id); the accession is retained in
``source_filings``.

FLAG — needs-live-data-validation:
    Reliable extraction of the *target* entity, deal *value* and *multiples*
    requires parsing the free-text body / exhibits of each 8-K (often the merger
    agreement exhibit). That NLP step is intentionally NOT attempted here — this
    connector records the deal event, filer/acquirer, status and source filing.
    Target/value enrichment needs live filings + a parsing decision.
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
from src.ingestion.redis_rate_limiter import RedisRateLimiter

logger = logging.getLogger(__name__)

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

# 8-K items that signal an M&A event → (deal_status).
MA_ITEMS = {
    "1.01": "ANNOUNCED",   # Entry into a Material Definitive Agreement
    "2.01": "COMPLETED",   # Completion of Acquisition or Disposition of Assets
}


class EdgarMaDealsConnector(BaseConnector):
    """Ingest M&A deal events from SEC EDGAR 8-K filings."""

    name = "SEC EDGAR M&A Deals"
    connector_type = "BATCH_API"
    data_domain = "CORPORATE_ACTIONS"

    def __init__(self, ciks: list[str] | None = None, days_back: int = 90):
        self.ciks = ciks or []
        self.days_back = days_back
        self.rate_limiter = RedisRateLimiter(key="sec_edgar", max_requests=settings.SEC_RATE_LIMIT, per_seconds=1.0)
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

    def _extract_ma_filings(
        self, submissions: dict[str, Any], cik: str
    ) -> list[dict[str, Any]]:
        """Extract 8-K filings carrying an M&A item. Pure (no I/O)."""
        recent = submissions.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        accessions = recent.get("accessionNumber", [])
        filed = recent.get("filingDate", [])
        items_list = recent.get("items", [])
        entity_name = submissions.get("name", "")

        out: list[dict[str, Any]] = []
        for i, form in enumerate(forms):
            if form not in ("8-K", "8-K/A"):
                continue
            items_raw = items_list[i] if i < len(items_list) else ""
            items = [it.strip() for it in items_raw.split(",") if it.strip()]
            ma_items = [it for it in items if it in MA_ITEMS]
            if not ma_items:
                continue
            out.append(
                {
                    "cik": cik,
                    "entity_name": entity_name,
                    "accession_number": accessions[i] if i < len(accessions) else "",
                    "filing_date": filed[i] if i < len(filed) else "",
                    "ma_items": ma_items,
                    "is_amendment": "/A" in form,
                }
            )
        return out

    async def extract(self) -> list[dict[str, Any]]:
        if not self.ciks:
            logger.warning("No CIKs configured — skipping M&A extraction")
            return []
        from datetime import timedelta

        cutoff = date.today() - timedelta(days=self.days_back)
        records: list[dict[str, Any]] = []
        for cik in self.ciks:
            submissions = await self._fetch_submissions(cik)
            if submissions is None:
                continue
            for filing in self._extract_ma_filings(submissions, cik):
                try:
                    if date.fromisoformat(filing["filing_date"]) < cutoff:
                        continue
                except (ValueError, TypeError):
                    continue
                records.append(filing)
        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        valid = []
        for r in records:
            if not r.get("cik") or not r.get("accession_number") or not r.get("filing_date"):
                continue
            if not r.get("ma_items"):
                continue
            valid.append(r)
        return valid

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Map M&A 8-K filings to MandADeal field dicts. Pure (no I/O)."""
        out: list[dict[str, Any]] = []
        for r in records:
            # Prefer the "most complete" status: a completion (2.01) supersedes
            # a bare announcement (1.01) when both appear on one filing.
            status = "COMPLETED" if "2.01" in r["ma_items"] else "ANNOUNCED"
            filing_date = r["filing_date"]
            out.append(
                {
                    "cik": r["cik"],
                    "acquirer_name": r.get("entity_name") or None,
                    "deal_type": "ACQUISITION",
                    "deal_status": status,
                    "announcement_date": filing_date if status == "ANNOUNCED" else None,
                    "completion_date": filing_date if status == "COMPLETED" else None,
                    "accession_number": r["accession_number"],
                    "ma_items": r["ma_items"],
                }
            )
        logger.info("M&A: transformed %d deal events", len(out))
        return out

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        from src.models.entity import EntityIdentifier
        from src.models.ma_deals import MandADeal

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
                acquirer_entity_id = ident.entity_id if ident else None

                event_date = None
                for key in ("announcement_date", "completion_date"):
                    if rec.get(key):
                        event_date = date.fromisoformat(rec[key])
                        break

                # Dedupe on acquirer + status + event date + source filing.
                accession = rec.get("accession_number")
                existing = (
                    await session.execute(
                        select(MandADeal).where(
                            MandADeal.acquirer_entity_id == acquirer_entity_id,
                            MandADeal.deal_status == rec["deal_status"],
                            MandADeal.announcement_date
                            == (event_date if rec["deal_status"] == "ANNOUNCED" else None),
                            MandADeal.completion_date
                            == (event_date if rec["deal_status"] == "COMPLETED" else None),
                        )
                    )
                ).scalars().all()
                if any(
                    (d.source_filings or []) and accession in (d.source_filings or [])
                    for d in existing
                ):
                    stats["skipped"] += 1
                    continue

                session.add(
                    MandADeal(
                        deal_id=uuid.uuid4(),
                        acquirer_entity_id=acquirer_entity_id,
                        acquirer_name=rec.get("acquirer_name"),
                        deal_type=rec.get("deal_type"),
                        deal_status=rec["deal_status"],
                        announcement_date=event_date if rec["deal_status"] == "ANNOUNCED" else None,
                        completion_date=event_date if rec["deal_status"] == "COMPLETED" else None,
                        primary_source="SEC_EDGAR_8K",
                        source_filings=[accession] if accession else None,
                    )
                )
                stats["inserted"] += 1
            except Exception:  # pragma: no cover - defensive
                logger.exception("[%s] failed to load deal", self.name)
                stats["errors"] += 1

        await session.flush()
        return stats

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
