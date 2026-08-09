"""GDELT connector: recent geopolitical events -> ``geopolitical_events``.

Source: GDELT 2.0 DOC API (https://api.gdeltproject.org/api/v2/doc/doc) —
KEYLESS, free. This is the source DATA_WIRING_AUDIT §6 flagged as missing for
geopolitical events.

GDELT's ``artlist`` mode returns news-derived global coverage. Each article
provides: url, title, seendate, domain, language, sourcecountry. It does NOT
expose per-article tone in this mode, so we derive ``severity`` deterministically
from which topic bucket the article matched (documented in TOPIC_BUCKETS), and
leave commodity/sector/entity impact NULL honestly.

We issue one query per topic bucket so every event lands with a meaningful
``event_type`` and ``severity``. GDELT asks callers to pace to ~1 request / 5s,
so the connector rate-limits accordingly.
"""

import asyncio
import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ingestion.base import BaseConnector
from src.ingestion.rate_limiter import RateLimiter
from src.models.country_risk import GeopoliticalEvent

logger = logging.getLogger(__name__)

GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

# event_type -> (GDELT query, severity). Higher-impact topics -> higher severity.
TOPIC_BUCKETS: dict[str, tuple[str, str]] = {
    "MILITARY_CONFLICT": ('("military conflict" OR airstrike OR "armed clashes")', "HIGH"),
    "SANCTIONS": ('(sanctions OR embargo)', "MEDIUM"),
    "TRADE_WAR": ('("trade war" OR tariffs OR "export controls")', "MEDIUM"),
    "COUP": ('(coup OR "military takeover")', "HIGH"),
    "ELECTION": ('("national election" OR "disputed election")', "LOW"),
    "TERRORISM": ('("terrorist attack" OR bombing)', "HIGH"),
}


class GdeltGeopoliticalConnector(BaseConnector):
    """Ingest recent geopolitical events from the GDELT 2.0 DOC API."""

    name = "GDELT Geopolitical"
    connector_type = "BATCH_API"
    data_domain = "GEOPOLITICAL"

    def __init__(
        self,
        topics: list[str] | None = None,
        timespan: str = "3d",
        max_per_topic: int = 10,
    ):
        self.topics = topics or list(TOPIC_BUCKETS.keys())
        self.timespan = timespan
        self.max_per_topic = max_per_topic
        # GDELT requests ~1 call / 5s; stay under that.
        self.rate_limiter = RateLimiter(max_requests=1, per_seconds=6.0)
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=60.0,
                headers={"User-Agent": "Mozilla/5.0 bloomberg-data-fabric/1.0"},
            )
        return self._client

    async def _gdelt_get(self, query: str) -> list[dict[str, Any]]:
        client = await self._get_client()
        params = {
            "query": f"{query} sourcelang:english",
            "mode": "artlist",
            "format": "json",
            "maxrecords": str(self.max_per_topic),
            "sort": "datedesc",
            "timespan": self.timespan,
        }
        # GDELT throttles hard (HTTP 429 or a plain-text notice). Back off and
        # retry a couple of times rather than aborting the whole topic.
        for attempt in range(3):
            await self.rate_limiter.acquire()
            resp = await client.get(GDELT_DOC_URL, params=params)
            if resp.status_code == 429:
                logger.warning("  GDELT: 429 throttled, backing off (attempt %d)", attempt + 1)
                await asyncio.sleep(10.0)
                continue
            resp.raise_for_status()
            text = resp.text.strip()
            if not text.startswith("{"):
                # GDELT returns a plain-text notice on rate-limit / bad query.
                logger.warning("  GDELT: non-JSON response: %s", text[:160])
                await asyncio.sleep(10.0)
                continue
            return resp.json().get("articles", []) or []
        return []

    async def extract(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for event_type in self.topics:
            query, severity = TOPIC_BUCKETS[event_type]
            try:
                articles = await self._gdelt_get(query)
                for art in articles:
                    records.append({
                        "event_type": event_type,
                        "severity": severity,
                        "article": art,
                    })
                logger.info("  GDELT: %s -> %d articles", event_type, len(articles))
            except Exception as e:  # noqa: BLE001
                logger.error("  GDELT: failed topic %s: %s", event_type, e)
        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Keep only articles with a title and url; de-dup by url within a run."""
        seen: set[str] = set()
        valid = []
        for rec in records:
            art = rec.get("article", {})
            url = art.get("url")
            title = art.get("title")
            if not url or not title or url in seen:
                continue
            seen.add(url)
            valid.append(rec)
        return valid

    @staticmethod
    def _parse_seendate(raw: str | None) -> date | None:
        """GDELT seendate is 'YYYYMMDDTHHMMSSZ'."""
        if not raw:
            return None
        try:
            return datetime.strptime(raw, "%Y%m%dT%H%M%SZ").replace(
                tzinfo=timezone.utc
            ).date()
        except ValueError:
            return None

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out = []
        for rec in records:
            art = rec["article"]
            title = art["title"][:500]
            url = art.get("url")
            domain = art.get("domain")
            source_country = art.get("sourcecountry")
            out.append({
                "event_type": rec["event_type"],
                "title": title,
                # No article body in artlist mode; record provenance honestly.
                "description": f"Source: {domain} — {url}" if url else None,
                "countries_involved": (
                    {"source_country": source_country} if source_country else None
                ),
                "severity": rec["severity"],
                "status": "REPORTED",
                "start_date": self._parse_seendate(art.get("seendate")),
                "source_url": url,
            })
        return out

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        for row in records:
            try:
                # De-dup by source_url when we have one (real GDELT
                # articles always do); fall back to title for the rare
                # row without a url, matching the old behavior.
                dedup_filter = (
                    GeopoliticalEvent.source_url == row["source_url"]
                    if row.get("source_url")
                    else GeopoliticalEvent.title == row["title"]
                )
                existing = (
                    await session.execute(select(GeopoliticalEvent).where(dedup_filter))
                ).scalar_one_or_none()
                if existing is not None:
                    stats["skipped"] += 1
                    continue
                session.add(GeopoliticalEvent(
                    id=uuid.uuid4(),
                    event_type=row["event_type"],
                    title=row["title"],
                    description=row["description"],
                    countries_involved=row["countries_involved"],
                    severity=row["severity"],
                    status=row["status"],
                    start_date=row["start_date"],
                    source_url=row.get("source_url"),
                    # No free keyless source for these impact dimensions.
                    commodity_impact=None,
                    sector_impact=None,
                    affected_entity_ids=None,
                ))
                stats["inserted"] += 1
            except Exception as e:  # noqa: BLE001
                logger.error("  GDELT load error: %s", e)
                stats["errors"] += 1
        await session.flush()
        return stats

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
