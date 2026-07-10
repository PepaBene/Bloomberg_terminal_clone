"""SEC EDGAR 8-K connector for corporate event ingestion.

Fetches 8-K filings from SEC EDGAR full-text search API and extracts
corporate actions for key item types:
- Item 2.01: Completion of Acquisition or Disposition of Assets
- Item 5.02: Departure/Election of Directors or Principal Officers
- Item 8.01: Other Events
"""

import logging
import re
import uuid
from datetime import date, datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector
from src.ingestion.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

EFTS_BASE_URL = "https://efts.sec.gov/LATEST/search-index"
FULL_TEXT_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
EDGAR_FILINGS_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
EDGAR_FULL_TEXT_URL = "https://efts.sec.gov/LATEST/search-index"

# SEC EDGAR full-text search API
EDGAR_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"

# Primary search endpoint for 8-K filings
EDGAR_8K_SEARCH_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

# Items of interest in 8-K filings: item_number -> (label, priority 1-5, materiality)
# Priority 1 = most urgent/material; 5 = least.
ITEMS_OF_INTEREST = {
    "2.01": ("ACQUISITION", 1, "HIGH"),          # Completion of Acquisition or Disposition
    "2.02": ("EARNINGS", 1, "HIGH"),             # Results of Operations / Financial Condition
    "5.02": ("MANAGEMENT_CHANGE", 2, "MEDIUM"),  # Departure/Election of Directors/Officers
    "1.01": ("MATERIAL_AGREEMENT", 2, "MEDIUM"), # Entry into Material Definitive Agreement
    "5.07": ("SHAREHOLDER_VOTE", 3, "LOW"),      # Submission of Matters to Vote
    "8.01": ("OTHER_EVENT", 4, "LOW"),           # Other Events
}


class Edgar8KConnector(BaseConnector):
    """Ingest 8-K corporate events from SEC EDGAR."""

    name = "SEC EDGAR 8-K"
    connector_type = "BATCH_API"
    data_domain = "CORPORATE_ACTIONS"

    def __init__(self, ciks: list[str] | None = None, days_back: int = 30):
        """Initialize connector.

        Args:
            ciks: List of CIK numbers to fetch. If None, must be set before extract().
            days_back: Number of days of history to look back for filings.
        """
        self.ciks = ciks or []
        self.days_back = days_back
        self.rate_limiter = RateLimiter(
            max_requests=settings.SEC_RATE_LIMIT, per_seconds=1.0
        )
        self.headers = {"User-Agent": settings.SEC_USER_AGENT}
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers=self.headers, timeout=30.0
            )
        return self._client

    async def _fetch_submissions(self, cik: str) -> dict[str, Any] | None:
        """Fetch filing submissions for a single CIK."""
        padded_cik = cik.zfill(10)
        url = EDGAR_8K_SEARCH_URL.format(cik=padded_cik)

        await self.rate_limiter.acquire()
        client = await self._get_client()

        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.warning(f"Failed to fetch submissions for CIK {cik}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching submissions for CIK {cik}: {e}")
            return None

    def _extract_8k_filings(
        self, submissions: dict[str, Any], cik: str
    ) -> list[dict[str, Any]]:
        """Extract 8-K filing entries from the submissions JSON."""
        recent = submissions.get("filings", {}).get("recent", {})
        if not recent:
            return []

        forms = recent.get("form", [])
        accession_numbers = recent.get("accessionNumber", [])
        filing_dates = recent.get("filingDate", [])
        primary_docs = recent.get("primaryDocument", [])
        items_list = recent.get("items", [])

        filings_8k = []
        for i, form in enumerate(forms):
            if form not in ("8-K", "8-K/A"):
                continue

            accession = accession_numbers[i] if i < len(accession_numbers) else ""
            filed = filing_dates[i] if i < len(filing_dates) else ""
            primary_doc = primary_docs[i] if i < len(primary_docs) else ""
            items_raw = items_list[i] if i < len(items_list) else ""

            # Parse item numbers from the items string
            items = [item.strip() for item in items_raw.split(",") if item.strip()]

            # Build document URL
            accession_clean = accession.replace("-", "")
            doc_url = (
                f"https://www.sec.gov/Archives/edgar/data/"
                f"{cik.lstrip('0')}/{accession_clean}/{primary_doc}"
            )

            filings_8k.append({
                "cik": cik,
                "form": form,
                "accession_number": accession,
                "filing_date": filed,
                "items": items,
                "document_url": doc_url,
                "is_amendment": "/A" in form,
            })

        return filings_8k

    async def extract(self) -> list[dict[str, Any]]:
        """Pull 8-K filing data from SEC EDGAR for all configured CIKs."""
        if not self.ciks:
            logger.warning("No CIKs configured — skipping 8-K extraction")
            return []

        records: list[dict[str, Any]] = []
        cutoff = date.today().isoformat()

        for cik in self.ciks:
            submissions = await self._fetch_submissions(cik)
            if submissions is None:
                continue

            entity_name = submissions.get("name", "")
            filings_8k = self._extract_8k_filings(submissions, cik)

            # Filter by date range
            from datetime import timedelta
            cutoff_date = date.today() - timedelta(days=self.days_back)
            filtered = []
            for filing in filings_8k:
                try:
                    filed_date = date.fromisoformat(filing["filing_date"])
                    if filed_date >= cutoff_date:
                        filtered.append(filing)
                except (ValueError, TypeError):
                    continue

            for filing in filtered:
                filing["entity_name"] = entity_name

            records.extend(filtered)
            logger.info(
                f"  8-K: CIK {cik} ({entity_name}) — "
                f"{len(filtered)} 8-K filings in last {self.days_back} days"
            )

        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate 8-K records — ensure required fields are present."""
        valid = []
        for rec in records:
            if not rec.get("cik"):
                continue
            if not rec.get("accession_number"):
                continue
            if not rec.get("filing_date"):
                continue
            # Must have at least one item of interest
            items = rec.get("items", [])
            relevant = [item for item in items if item in ITEMS_OF_INTEREST]
            if not relevant:
                continue
            rec["relevant_items"] = relevant
            valid.append(rec)
        return valid

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Transform 8-K data into EightKEvent records."""
        transformed = []

        for rec in records:
            cik = rec["cik"]
            entity_name = rec.get("entity_name", "")
            filing_date_str = rec["filing_date"]
            accession = rec["accession_number"]
            relevant_items = rec.get("relevant_items", [])

            for item_number in relevant_items:
                label, priority, materiality = ITEMS_OF_INTEREST.get(
                    item_number, ("OTHER_EVENT", 4, "LOW")
                )

                item_description = (
                    f"Item {item_number}: {label} — Filed by {entity_name} (CIK {cik})"
                )

                transformed.append({
                    "cik": cik,
                    "item_number": item_number,
                    "item_description": item_description,
                    "priority": priority,
                    "materiality": materiality,
                    "filing_date": filing_date_str,
                    "source": "SEC_EDGAR_8K",
                    "accession_number": accession,
                    "document_url": rec.get("document_url"),
                    "is_amendment": rec.get("is_amendment", False),
                })

        logger.info(f"Transformed {len(transformed)} 8-K event records")
        return transformed

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        """Write 8-K event records to the eight_k_events table.

        This is the table /v3/filings/events/* actually queries — a prior
        version of this connector wrote to CorporateAction, which no 8-K
        endpoint reads, so persisted rows were invisible to the API.
        """
        from src.models.entity import EntityIdentifier
        from src.models.filing_intelligence import EightKEvent

        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}

        for rec in records:
            try:
                cik = rec["cik"]

                # Resolve entity_id from CIK
                result = await session.execute(
                    select(EntityIdentifier).where(
                        EntityIdentifier.identifier_type == "CIK",
                        EntityIdentifier.identifier_value == cik,
                    )
                )
                entity_ident = result.scalar_one_or_none()
                entity_id = entity_ident.entity_id if entity_ident else None
                if entity_id is None:
                    stats["skipped"] += 1
                    continue

                filing_date = date.fromisoformat(rec["filing_date"])

                # Check for duplicate by entity + accession + item
                # (one 8-K can produce multiple events for different items)
                existing = await session.execute(
                    select(EightKEvent).where(
                        EightKEvent.entity_id == entity_id,
                        EightKEvent.item_number == rec["item_number"],
                        EightKEvent.filing_date == filing_date,
                        EightKEvent.filing_accession_number == rec["accession_number"],
                    )
                )
                if existing.scalar_one_or_none() is not None:
                    stats["skipped"] += 1
                    continue

                event = EightKEvent(
                    id=uuid.uuid4(),
                    entity_id=entity_id,
                    filing_date=filing_date,
                    item_number=rec["item_number"],
                    item_description=rec.get("item_description"),
                    priority=rec["priority"],
                    materiality=rec["materiality"],
                    filing_accession_number=rec["accession_number"],
                    filing_url=rec.get("document_url"),
                    is_processed=False,
                )
                session.add(event)
                stats["inserted"] += 1

            except Exception as e:
                logger.error(f"Error loading 8-K event: {e}")
                stats["errors"] += 1

        await session.flush()
        return stats

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
