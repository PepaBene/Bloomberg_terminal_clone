"""Credit Rating History extraction from SEC EDGAR 8-K filings (Pillar 1 Supplement §4).

Searches 8-K filings (Item 2.06 / Item 8.01) for credit rating agency mentions
(S&P, Moody's, Fitch) and classifies upgrades/downgrades/affirmations from
the filing text.
"""

import logging
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector
from src.ingestion.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

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

    def __init__(self, ciks: list[str] | None = None):
        self.ciks = ciks or []
        self.rate_limiter = RateLimiter(
            max_requests=settings.SEC_RATE_LIMIT, per_seconds=1.0
        )

    async def extract(self) -> list[dict[str, Any]]:
        """Extract credit rating events from 8-K filings."""
        if not self.ciks:
            logger.warning("No CIKs configured — skipping credit rating extraction")
            return []

        records: list[dict[str, Any]] = []
        # In production this would fetch 8-K filings from EDGAR and parse
        # Item 2.06 / Item 8.01 text for rating agency mentions.
        # For now, return empty — the connector skeleton is ready.
        logger.info("Credit rating extraction: %d CIKs queued", len(self.ciks))
        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate extracted credit rating records."""
        valid = []
        for rec in records:
            if not rec.get("entity_id"):
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
        """Load credit rating events into the database."""
        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}

        for rec in records:
            try:
                from src.models.credit_rating import CreditRatingEvent

                event = CreditRatingEvent(
                    entity_id=rec["entity_id"],
                    agency=rec["agency"],
                    rating_type=rec.get("rating_type", "LONG_TERM"),
                    new_rating=rec.get("new_rating"),
                    old_rating=rec.get("old_rating"),
                    direction=rec.get("direction"),
                    outlook=rec.get("outlook"),
                    event_date=rec["event_date"],
                    effective_date=rec.get("effective_date"),
                    source_type=rec.get("source_type", "8K_FILING"),
                    source_filing_id=rec.get("source_filing_id"),
                    source_url=rec.get("source_url"),
                )
                session.add(event)
                stats["inserted"] += 1
            except Exception as e:
                logger.error("Error loading credit rating event: %s", e)
                stats["errors"] += 1

        return stats
