"""Legislative bills connector (US Congress, keyless).

Ingests recently published congressional bills from the GovInfo Congressional
Bills RSS feed (https://www.govinfo.gov/rss/bills.xml). This is a free, keyless
XML feed covering newly published House and Senate legislative proposals.

Note: the ``CONGRESS_HOUSE_FEED_URL`` / ``CONGRESS_SENATE_FEED_URL`` settings
point at STOCK Act *trade* JSON feeds (consumed by ``CongressTradesConnector``),
not bill feeds, so this connector uses the GovInfo bills RSS instead
(``GOVINFO_BILLS_FEED_URL``), which is the correct keyless source for bills.
"""

from __future__ import annotations

import html
import logging
import re
import uuid
import xml.etree.ElementTree as ET
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector

logger = logging.getLogger(__name__)

# GovInfo bill package-id pattern, e.g. "BILLS-119s4925is" ->
#   congress=119, type=s, number=4925, version=is
_BILL_ID_RE = re.compile(
    r"BILLS-(\d+)(hconres|hjres|hres|sconres|sjres|sres|hr|s)(\d+)([a-z]+)?",
    re.IGNORECASE,
)

# GovInfo bill-version suffix -> human-readable status (subset of common codes).
_VERSION_STATUS = {
    "ih": "Introduced in House",
    "is": "Introduced in Senate",
    "rh": "Reported in House",
    "rs": "Reported in Senate",
    "eh": "Engrossed in House",
    "es": "Engrossed in Senate",
    "enr": "Enrolled",
    "pcs": "Placed on Calendar Senate",
    "pch": "Placed on Calendar House",
    "rfh": "Referred in House",
    "rfs": "Referred in Senate",
    "ath": "Agreed to House",
    "ats": "Agreed to Senate",
    "cps": "Considered and Passed Senate",
    "cph": "Considered and Passed House",
}


def _clean_text(value: str | None) -> str:
    """Unescape HTML entities and collapse whitespace."""
    if not value:
        return ""
    return " ".join(html.unescape(value).split())


def _parse_pubdate(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).date()
    except (TypeError, ValueError):
        for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue
    return None


class LegislativeBillsConnector(BaseConnector):
    """Ingest recent congressional bills from the GovInfo bills RSS feed."""

    name = "GovInfo Legislative Bills"
    connector_type = "BATCH_API"
    data_domain = "POLITICAL"

    def __init__(self, feed_url: str | None = None):
        self._url = feed_url or settings.GOVINFO_BILLS_FEED_URL

    async def extract(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            resp = await client.get(
                self._url, headers={"User-Agent": settings.SEC_USER_AGENT}
            )
            resp.raise_for_status()
            root = ET.fromstring(resp.content)

        records: list[dict[str, Any]] = []
        for item in root.findall(".//item"):
            rec: dict[str, Any] = {}
            for child in item:
                tag = child.tag.split("}")[-1]
                rec[tag] = child.text
            records.append(rec)
        logger.info("[%s] fetched %d raw items", self.name, len(records))
        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        valid = []
        for r in records:
            guid = (r.get("guid") or "").strip()
            if guid and (r.get("title") or "").strip():
                valid.append(r)
        return valid

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize RSS items into LegislativeBill field dicts. Pure (no I/O)."""
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in records:
            guid = (r.get("guid") or "").strip()
            if not guid or guid in seen:
                continue
            seen.add(guid)

            bill_type: str | None = None
            status: str | None = None
            match = _BILL_ID_RE.search(guid)
            if match:
                bill_type = match.group(2).upper()
                version = (match.group(4) or "").lower()
                status = _VERSION_STATUS.get(version, version.upper() or None)

            pub = _parse_pubdate(r.get("pubDate"))
            title = _clean_text(r.get("title"))
            summary = _clean_text(r.get("description")) or None

            out.append(
                {
                    "bill_id": guid[:30],
                    "title": title[:500],
                    "summary": summary[:5000] if summary else None,
                    "bill_type": bill_type,
                    "status": status[:30] if status else None,
                    "sponsor_count": None,
                    "passage_probability": None,
                    "affected_sectors": None,
                    "affected_entity_ids": None,
                    "introduced_date": pub,
                    "last_action_date": pub,
                    "source_url": (r.get("link") or self._url)[:500],
                }
            )
        return out

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        from src.models.political_intelligence import LegislativeBill

        counts = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        if getattr(self, "dry_run", False):
            return counts

        for rec in records:
            try:
                existing = (
                    await session.execute(
                        select(LegislativeBill).where(
                            LegislativeBill.bill_id == rec["bill_id"]
                        )
                    )
                ).scalar_one_or_none()
                if existing:
                    counts["skipped"] += 1
                    continue
                session.add(LegislativeBill(id=uuid.uuid4(), **rec))
                counts["inserted"] += 1
            except Exception:  # pragma: no cover - defensive
                logger.exception("[%s] failed to load bill", self.name)
                counts["errors"] += 1
        await session.flush()
        return counts
