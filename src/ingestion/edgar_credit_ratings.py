"""Credit Rating History extraction from SEC EDGAR 8-K filings (Pillar 1 Supplement §4).

Searches 8-K filings (Item 2.06 / Item 8.01) for credit rating agency mentions
(S&P, Moody's, Fitch) and classifies upgrades/downgrades/affirmations from
the filing text.
"""

import logging
import re
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
FILING_DOC_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{primary_doc}"

# 8-K items most likely to disclose a rating action.
RATING_8K_ITEMS = ("2.06", "8.01")

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(raw: str) -> str:
    """Cheap HTML-to-text so 8-K prose can be regex-scanned."""
    return _HTML_TAG_RE.sub(" ", raw)

# Patterns to detect rating agency mentions
AGENCY_PATTERNS = {
    "SP": [
        r"S&P\s+Global\s+Ratings",
        r"Standard\s+&\s+Poor",
        r"S&P\s+Rating",
    ],
    "MOODYS": [
        r"Moody'?s\s+Investors?\s+Service",
        r"Moody'?s\s+Ratings?",
        r"Moody'?s",
    ],
    "FITCH": [
        r"Fitch\s+Ratings?",
        r"Fitch\s+Group",
        r"Fitch",
    ],
}

# Direction detection keywords
DIRECTION_KEYWORDS = {
    "UPGRADE": ["upgrade", "raised", "increase"],
    "DOWNGRADE": ["downgrade", "lowered", "cut", "reduced"],
    "AFFIRM": ["affirm", "maintain", "reaffirm", "confirmed"],
    "INITIATED": ["initiat", "first-time", "assign"],
    "WITHDRAWN": ["withdrawn", "withdrew", "discontinue"],
}

# S&P rating scale (descending)
SP_RATINGS = [
    "AAA", "AA+", "AA", "AA-", "A+", "A", "A-",
    "BBB+", "BBB", "BBB-", "BB+", "BB", "BB-",
    "B+", "B", "B-", "CCC+", "CCC", "CCC-", "CC", "C", "D",
]

# Moody's rating scale (descending)
MOODYS_RATINGS = [
    "Aaa", "Aa1", "Aa2", "Aa3", "A1", "A2", "A3",
    "Baa1", "Baa2", "Baa3", "Ba1", "Ba2", "Ba3",
    "B1", "B2", "B3", "Caa1", "Caa2", "Caa3", "Ca", "C",
]

# Outlook keywords
OUTLOOK_KEYWORDS = {
    "POSITIVE": ["positive outlook", "positive watch"],
    "STABLE": ["stable outlook"],
    "NEGATIVE": ["negative outlook", "negative watch", "creditwatch negative"],
    "DEVELOPING": ["developing outlook", "developing watch"],
}


def detect_agency(text: str) -> str | None:
    """Detect which rating agency is mentioned in the text."""
    for agency, patterns in AGENCY_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, text, re.IGNORECASE):
                return agency
    return None


def detect_direction(text: str) -> str | None:
    """Detect rating action direction from text."""
    lower = text.lower()
    for direction, keywords in DIRECTION_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                return direction
    return None


def detect_outlook(text: str) -> str | None:
    """Detect outlook from text."""
    lower = text.lower()
    for outlook, keywords in OUTLOOK_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                return outlook
    return None


def extract_sp_rating(text: str) -> str | None:
    """Extract an S&P-style rating from text."""
    for rating in SP_RATINGS:
        escaped = re.escape(rating)
        if re.search(rf"\b{escaped}\b", text):
            return rating
    return None


def extract_moodys_rating(text: str) -> str | None:
    """Extract a Moody's-style rating from text."""
    for rating in MOODYS_RATINGS:
        escaped = re.escape(rating)
        if re.search(rf"\b{escaped}\b", text):
            return rating
    return None


class EdgarCreditRatingConnector(BaseConnector):
    """Extract credit rating events from SEC EDGAR 8-K filings."""

    name = "SEC EDGAR Credit Ratings"
    connector_type = "BATCH_API"
    data_domain = "CREDIT_RATINGS"

    def __init__(self, ciks: list[str] | None = None, filing_limit: int = 20):
        self.ciks = ciks or []
        self.filing_limit = filing_limit
        self.rate_limiter = RateLimiter(
            max_requests=settings.SEC_RATE_LIMIT, per_seconds=1.0
        )
        self.headers = {"User-Agent": settings.SEC_USER_AGENT}
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(headers=self.headers, timeout=30.0)
        return self._client

    async def _sec_get_json(self, url: str) -> dict[str, Any] | None:
        await self.rate_limiter.acquire()
        client = await self._get_client()
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:  # noqa: BLE001
            logger.warning("Credit ratings: failed GET %s: %s", url, e)
            return None

    async def _fetch_8k_index(self, cik: str) -> list[dict[str, Any]]:
        """Return recent 8-K filing metadata (with rating-relevant items) for a CIK."""
        data = await self._sec_get_json(SUBMISSIONS_URL.format(cik=cik.zfill(10)))
        if not data:
            return []
        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        accessions = recent.get("accessionNumber", [])
        primary_docs = recent.get("primaryDocument", [])
        filing_dates = recent.get("filingDate", [])
        items = recent.get("items", [])

        filings: list[dict[str, Any]] = []
        for i, form in enumerate(forms):
            if form != "8-K":
                continue
            item_str = items[i] if i < len(items) else ""
            if not any(it in item_str for it in RATING_8K_ITEMS):
                continue
            filings.append({
                "cik": cik,
                "accession_number": accessions[i],
                "filing_date": filing_dates[i],
                "url": FILING_DOC_URL.format(
                    cik=cik,
                    accession=accessions[i].replace("-", ""),
                    primary_doc=primary_docs[i],
                ),
            })
            if len(filings) >= self.filing_limit:
                break
        return filings

    async def _fetch_text(self, url: str) -> str | None:
        await self.rate_limiter.acquire()
        client = await self._get_client()
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text
        except Exception as e:  # noqa: BLE001
            logger.warning("Credit ratings: failed text GET %s: %s", url, e)
            return None

    async def extract(self) -> list[dict[str, Any]]:
        """Extract candidate credit-rating events from recent 8-K filings.

        Only 8-Ks whose text mentions a recognised rating agency are emitted;
        transform() then classifies direction/outlook and extracts the rating.
        """
        if not self.ciks:
            logger.warning("No CIKs configured — skipping credit rating extraction")
            return []

        records: list[dict[str, Any]] = []
        for cik in self.ciks:
            filings = await self._fetch_8k_index(cik)
            for filing in filings:
                raw = await self._fetch_text(filing["url"])
                if not raw:
                    continue
                text = strip_html(raw)
                agency = detect_agency(text)
                if agency is None:
                    continue
                records.append({
                    "cik": cik,
                    "agency": agency,
                    "event_date": filing["filing_date"],
                    "raw_text": text,
                    "source_type": "8K_FILING",
                    "source_url": filing["url"],
                })
            logger.info("  RATC: CIK %s — %d rating-related 8-Ks", cik, len(filings))
        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate extracted credit rating records."""
        valid = []
        for rec in records:
            if not (rec.get("cik") or rec.get("entity_id")):
                continue
            if not rec.get("agency"):
                continue
            if not rec.get("event_date"):
                continue
            valid.append(rec)
        return valid

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Transform raw 8-K text into structured credit rating events."""
        transformed = []
        for rec in records:
            text = rec.get("raw_text", "")

            if not rec.get("agency") and text:
                rec["agency"] = detect_agency(text)
            if not rec.get("direction") and text:
                rec["direction"] = detect_direction(text)
            if not rec.get("outlook") and text:
                rec["outlook"] = detect_outlook(text)

            # Try to extract the actual rating
            if not rec.get("new_rating") and text:
                agency = rec.get("agency")
                if agency == "MOODYS":
                    rec["new_rating"] = extract_moodys_rating(text)
                else:
                    rec["new_rating"] = extract_sp_rating(text)

            transformed.append(rec)
        return transformed

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        """Load credit rating events into the database.

        Also upserts security-level ``CreditRating`` rows (``src/models/
        security.py``) for any fixed-income securities issued by the rated
        entity — this is the only real source this codebase has for that
        table. SEC 8-Ks disclose ratings at the *issuer* level, not per
        instrument, so the issuer-level rating is applied to each of the
        issuer's outstanding fixed-income securities; this is a genuine,
        non-fabricated rating (the agency/rating/date are all extracted from
        the filing text), just attributed at issuer granularity rather than
        a specific CUSIP. Only done when a rating was actually extracted
        (``new_rating`` present) — never fabricated when extraction fails.
        """
        stats = {
            "inserted": 0, "updated": 0, "skipped": 0, "errors": 0,
            "security_ratings_inserted": 0,
        }

        for rec in records:
            try:
                from src.models.credit_rating import CreditRatingEvent
                from src.models.entity import EntityIdentifier

                entity_id = rec.get("entity_id")
                if entity_id is None and rec.get("cik"):
                    result = await session.execute(
                        select(EntityIdentifier).where(
                            EntityIdentifier.identifier_type == "CIK",
                            EntityIdentifier.identifier_value == rec["cik"],
                        )
                    )
                    ident = result.scalar_one_or_none()
                    if ident is None:
                        logger.debug("No entity for CIK %s — skipping", rec["cik"])
                        stats["skipped"] += 1
                        continue
                    entity_id = ident.entity_id

                event_date = rec["event_date"]
                if isinstance(event_date, str):
                    event_date = date.fromisoformat(event_date)

                event = CreditRatingEvent(
                    entity_id=entity_id,
                    agency=rec["agency"],
                    rating_type=rec.get("rating_type", "LONG_TERM"),
                    new_rating=rec.get("new_rating"),
                    old_rating=rec.get("old_rating"),
                    direction=rec.get("direction"),
                    outlook=rec.get("outlook"),
                    event_date=event_date,
                    effective_date=rec.get("effective_date"),
                    source_type=rec.get("source_type", "8K_FILING"),
                    source_filing_id=rec.get("source_filing_id"),
                    source_url=rec.get("source_url"),
                )
                session.add(event)
                stats["inserted"] += 1

                if rec.get("new_rating"):
                    inserted = await self._apply_security_ratings(
                        session,
                        entity_id=entity_id,
                        agency=rec["agency"],
                        rating=rec["new_rating"],
                        outlook=rec.get("outlook"),
                        rating_date=event_date,
                    )
                    stats["security_ratings_inserted"] += inserted
            except Exception as e:
                logger.error("Error loading credit rating event: %s", e)
                stats["errors"] += 1

        await session.flush()
        return stats

    @staticmethod
    async def _apply_security_ratings(
        session: AsyncSession,
        *,
        entity_id: Any,
        agency: str,
        rating: str,
        outlook: str | None,
        rating_date: date,
    ) -> int:
        """Upsert security-level CreditRating for the entity's FI securities."""
        from src.models.security import CreditRating as SecurityCreditRating
        from src.models.security import Security

        fi_securities = (
            await session.execute(
                select(Security.security_id).where(
                    Security.issuer_entity_id == entity_id,
                    Security.asset_class == "FIXED_INCOME",
                )
            )
        ).scalars().all()

        inserted = 0
        for security_id in fi_securities:
            existing = await session.execute(
                select(SecurityCreditRating).where(
                    SecurityCreditRating.security_id == security_id,
                    SecurityCreditRating.agency == agency,
                    SecurityCreditRating.rating_date == rating_date,
                )
            )
            if existing.scalar_one_or_none() is not None:
                continue
            session.add(SecurityCreditRating(
                security_id=security_id,
                agency=agency,
                rating=rating,
                outlook=outlook,
                rating_date=rating_date,
                source="SEC_EDGAR_8K",
            ))
            inserted += 1
        return inserted

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
