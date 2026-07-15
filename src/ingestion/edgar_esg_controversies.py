"""ESG controversies connector (GDELT primary path; configurable JSON feed fallback).

There is no clean, free, structured public source for ESG controversies (the
established providers — RepRisk, MSCI, Sustainalytics — are paid). This
connector supports two extract paths:

1. ``_extract_gdelt`` (primary, keyless, free) — queries the GDELT 2.0 DOC
   API (already used elsewhere in this codebase by
   ``gdelt_geopolitical.py``) per-entity, combining the entity's legal name
   with a controversy keyword set (lawsuit, investigation, fine, violation,
   scandal, recall, ...) and GDELT's own ``tone<`` query operator to bias
   toward negative-sentiment coverage. Used automatically whenever
   ``ESG_CONTROVERSY_FEED_URL`` is unset and entities are supplied.
2. ``_extract_generic_feed`` (fallback/alternative) — ingests from a
   *configurable* JSON feed URL, mirroring the ``congress_trades`` pattern
   (feed URL taken from settings / constructor). Any compatible feed emitting
   controversy rows can be plugged in. Used whenever
   ``ESG_CONTROVERSY_FEED_URL`` (or the ``feed_url`` constructor arg) is set,
   taking precedence over the GDELT path.

Both paths emit the same raw row shape (cik/entity_id, controversy_type,
severity, description, start_date, status, estimated_financial_impact,
source, source_url) so ``validate()``/``transform()``/``load()`` are shared
and unit-tested once against a representative payload from each path.

FLAG — UNTESTED AGAINST LIVE DATA
----------------------------------
Outbound network access to external domains (GDELT included) is blocked in
this sandbox by network policy, so neither extract path has been exercised
against a live response in this environment. Both are written to-pattern
against each source's documented request/response shape — the GDELT path
mirrors ``gdelt_geopolitical.py``'s existing, already-relied-upon DOC 2.0 API
request pattern (``mode=artlist``, ``format=json``, tab/JSON article list
with ``url``/``title``/``seendate``/``domain``/``sourcecountry`` fields) — and
are unit-tested exclusively against hand-constructed fixture payloads
matching each source's documented JSON schema, not live calls. The GDELT
severity/controversy-type classification is an explicit, documented
heuristic (keyword-in-title matching, gated by GDELT's ``tone<`` operator to
bias toward negative coverage, plus an article-recency bump) — it is NOT an
authoritative severity rating from a provider such as RepRisk/MSCI/
Sustainalytics, and code comments say so. Both the GDELT query syntax/rate
limits and the generic-feed wire schema must be validated against live
responses before production use. No controversy rows are fabricated:
articles/rows that cannot be resolved to an existing entity (CIK or
entity_id) are skipped and logged, never invented.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector
from src.ingestion.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

# Normalize incoming severity strings to the model's expected vocabulary.
_SEVERITY_MAP = {
    "low": "LOW",
    "minor": "LOW",
    "moderate": "MODERATE",
    "medium": "MODERATE",
    "high": "HIGH",
    "major": "HIGH",
    "severe": "SEVERE",
    "critical": "CRITICAL",
}

# Ordered rank used for the recency bump in the GDELT heuristic below.
_SEVERITY_RANK = ["low", "moderate", "high", "severe", "critical"]

# --------------------------------------------------------------------------
# GDELT extract path
# --------------------------------------------------------------------------

GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

# Default lookback window for the GDELT query (days). GDELT's DOC 2.0 API
# ``timespan`` parameter accepts a "<n>d" suffix for day-granularity windows;
# 90d keeps us within GDELT's supported timespan range.
GDELT_ESG_QUERY_LOOKBACK_DAYS = 90

# keyword (as it would appear, lowercased, in an article title) ->
# (controversy_type, base_severity). This is a hand-picked, honest heuristic
# mapping — NOT an authoritative severity taxonomy from a rating provider.
# Order matters only in that the first matching keyword wins when a title
# contains more than one; roughly most-severe-signal-first.
_CONTROVERSY_KEYWORD_MAP: dict[str, tuple[str, str]] = {
    "fraud": ("REPUTATIONAL", "severe"),
    "scandal": ("REPUTATIONAL", "severe"),
    "misconduct": ("REPUTATIONAL", "high"),
    "class action": ("LEGAL", "high"),
    "lawsuit": ("LEGAL", "high"),
    "litigation": ("LEGAL", "high"),
    "investigation": ("REGULATORY", "high"),
    "probe": ("REGULATORY", "high"),
    "subpoena": ("REGULATORY", "high"),
    "recall": ("PRODUCT_SAFETY", "moderate"),
    "fine": ("REGULATORY", "moderate"),
    "penalty": ("REGULATORY", "moderate"),
    "violation": ("REGULATORY", "moderate"),
}


def _gdelt_keyword_query() -> str:
    """Build the GDELT OR-group of controversy keywords. Pure."""
    parts = [f'"{kw}"' if " " in kw else kw for kw in _CONTROVERSY_KEYWORD_MAP]
    return "(" + " OR ".join(parts) + ")"


def _classify_article(title: str) -> tuple[str, str]:
    """Map an article title to (controversy_type, base severity). Pure.

    Purely a keyword-in-title heuristic — documented as such, not a claim of
    editorial fact-checking or an authoritative severity determination.
    """
    lowered = title.lower()
    for kw, (ctype, sev) in _CONTROVERSY_KEYWORD_MAP.items():
        if kw in lowered:
            return ctype, sev
    return "OTHER", "moderate"


def _bump_for_recency(severity: str, seen_date: date | None, *, today: date | None = None) -> str:
    """Bump severity one rank if the article is very recent (<=7 days). Pure.

    A crude recency proxy for "still developing / actively unfolding" — not a
    substitute for tracking resolution status.
    """
    if seen_date is None:
        return severity
    today = today or date.today()
    days_old = (today - seen_date).days
    if days_old < 0 or days_old > 7:
        return severity
    try:
        idx = _SEVERITY_RANK.index(severity)
    except ValueError:
        return severity
    # Cap the recency bump at "severe" — a single recent article is not
    # sufficient signal to call something "critical".
    capped = min(idx + 1, _SEVERITY_RANK.index("severe"))
    return _SEVERITY_RANK[capped]


def _parse_seendate(raw: str | None) -> date | None:
    """GDELT ``seendate`` is 'YYYYMMDDTHHMMSSZ'. Pure."""
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y%m%dT%H%M%SZ").date()
    except ValueError:
        return None


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _to_decimal(value: Any) -> Decimal | None:
    if value in (None, "", "N/A"):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


class EsgControversiesConnector(BaseConnector):
    """Ingest ESG controversies from GDELT (primary) or a configurable JSON feed."""

    name = "ESG Controversies"
    connector_type = "BATCH_API"
    data_domain = "ESG"

    def __init__(
        self,
        feed_url: str | None = None,
        entities: list[dict[str, Any]] | None = None,
        gdelt_lookback_days: int = GDELT_ESG_QUERY_LOOKBACK_DAYS,
        max_articles_per_entity: int = 10,
    ):
        self.feed_url = feed_url or getattr(settings, "ESG_CONTROVERSY_FEED_URL", "")
        # Each entity dict: {"cik": ..., "entity_id": ..., "legal_name": ...}.
        # "legal_name" drives the GDELT query; at least one of cik/entity_id
        # is required to resolve the row to a DB entity in load().
        self.entities = entities or []
        self.gdelt_lookback_days = gdelt_lookback_days
        self.max_articles_per_entity = max_articles_per_entity
        # GDELT requests ~1 call / 5s; stay under that (mirrors gdelt_geopolitical.py).
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
        """Issue one GDELT DOC 2.0 API query, with 429 backoff/retry."""
        client = await self._get_client()
        params = {
            "query": query,
            "mode": "artlist",
            "format": "json",
            "maxrecords": str(self.max_articles_per_entity),
            "sort": "datedesc",
            "timespan": f"{self.gdelt_lookback_days}d",
        }
        for attempt in range(3):
            await self.rate_limiter.acquire()
            resp = await client.get(GDELT_DOC_URL, params=params)
            if resp.status_code == 429:
                logger.warning(
                    "[%s] GDELT: 429 throttled, backing off (attempt %d)",
                    self.name,
                    attempt + 1,
                )
                await asyncio.sleep(10.0)
                continue
            resp.raise_for_status()
            text = resp.text.strip()
            if not text.startswith("{"):
                # GDELT returns a plain-text notice on rate-limit / bad query.
                logger.warning("[%s] GDELT: non-JSON response: %s", self.name, text[:160])
                await asyncio.sleep(10.0)
                continue
            return resp.json().get("articles", []) or []
        return []

    async def _extract_gdelt(self) -> list[dict[str, Any]]:
        """Query GDELT per entity for controversy-keyword coverage. I/O."""
        keyword_query = _gdelt_keyword_query()
        records: list[dict[str, Any]] = []

        for ent in self.entities:
            legal_name = ent.get("legal_name")
            cik = ent.get("cik")
            entity_id = ent.get("entity_id")
            if not legal_name:
                continue
            if not cik and not entity_id:
                logger.debug(
                    "[%s] entity %r has neither cik nor entity_id — skipping GDELT query",
                    self.name,
                    legal_name,
                )
                continue

            # Combine the legal name with the controversy keyword group and
            # GDELT's negative-tone operator (tone<-2) to bias toward
            # genuinely negative coverage rather than routine mentions.
            query = f'"{legal_name}" {keyword_query} tone<-2 sourcelang:english'
            try:
                articles = await self._gdelt_get(query)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[%s] GDELT query failed for %r: %s", self.name, legal_name, exc)
                continue

            for art in articles:
                title = art.get("title")
                url = art.get("url")
                if not title or not url:
                    continue
                seen = _parse_seendate(art.get("seendate"))
                controversy_type, severity = _classify_article(title)
                severity = _bump_for_recency(severity, seen)
                domain = art.get("domain")
                records.append(
                    {
                        "cik": cik,
                        "entity_id": entity_id,
                        "controversy_type": controversy_type,
                        "severity": severity,
                        "description": f"{title} (source: {domain})" if domain else title,
                        "start_date": seen.isoformat() if seen else None,
                        # News-sourced, not a confirmed regulatory/legal
                        # outcome — "alleged" rather than "confirmed".
                        "status": "alleged",
                        "estimated_financial_impact": None,
                        "source": "GDELT",
                        "source_url": url,
                    }
                )
            logger.info(
                "[%s] GDELT: %r -> %d matching articles", self.name, legal_name, len(articles)
            )

        return records

    async def _extract_generic_feed(self) -> list[dict[str, Any]]:
        """Fetch controversy rows from a configurable JSON feed. I/O."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(
                self.feed_url, headers={"User-Agent": settings.SEC_USER_AGENT}
            )
            resp.raise_for_status()
            data = resp.json()
        records = data if isinstance(data, list) else data.get("controversies", [])
        logger.info("[%s] fetched %d raw rows", self.name, len(records))
        return records

    async def extract(self) -> list[dict[str, Any]]:
        # An explicitly configured feed URL takes precedence (opt-in
        # override); otherwise GDELT is the primary keyless path whenever
        # entities were supplied.
        if self.feed_url:
            return await self._extract_generic_feed()
        if self.entities:
            return await self._extract_gdelt()
        logger.warning(
            "[%s] neither ESG_CONTROVERSY_FEED_URL nor entities configured — "
            "skipping extraction",
            self.name,
        )
        return []

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        valid = []
        for r in records:
            if not r.get("controversy_type"):
                continue
            if not (r.get("cik") or r.get("entity_id")):
                continue
            valid.append(r)
        return valid

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize raw feed/GDELT rows into ESGControversy field dicts. Pure (no I/O)."""
        out: list[dict[str, Any]] = []
        for r in records:
            severity_raw = str(r.get("severity") or "").lower().strip()
            out.append(
                {
                    "cik": (str(r["cik"]).zfill(10) if r.get("cik") else None),
                    "entity_id": r.get("entity_id"),
                    "controversy_type": str(r["controversy_type"]).upper()[:30],
                    "severity": _SEVERITY_MAP.get(severity_raw),
                    "description": r.get("description"),
                    "start_date": _parse_date(r.get("start_date") or r.get("date")),
                    "resolution_date": _parse_date(r.get("resolution_date")),
                    "status": (r.get("status") or "").upper()[:20] or None,
                    "estimated_financial_impact": _to_decimal(
                        r.get("estimated_financial_impact") or r.get("impact")
                    ),
                    "source": (r.get("source") or "FEED")[:50],
                    "source_url": r.get("source_url") or r.get("url"),
                }
            )
        logger.info("[%s] transformed %d controversy rows", self.name, len(out))
        return out

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        from src.models.entity import EntityIdentifier
        from src.models.esg import ESGControversy

        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        if getattr(self, "dry_run", False):
            return stats

        for rec in records:
            try:
                entity_id = rec.get("entity_id")
                if entity_id is None and rec.get("cik"):
                    ident = (
                        await session.execute(
                            select(EntityIdentifier).where(
                                EntityIdentifier.identifier_type == "CIK",
                                EntityIdentifier.identifier_value == rec["cik"],
                            )
                        )
                    ).scalar_one_or_none()
                    entity_id = ident.entity_id if ident else None
                if entity_id is None:
                    logger.info(
                        "[%s] skipping controversy row — entity not resolvable "
                        "(no fabricated row created)",
                        self.name,
                    )
                    stats["skipped"] += 1
                    continue

                existing = (
                    await session.execute(
                        select(ESGControversy).where(
                            ESGControversy.entity_id == entity_id,
                            ESGControversy.controversy_type == rec["controversy_type"],
                            ESGControversy.start_date == rec.get("start_date"),
                            ESGControversy.description == rec.get("description"),
                        )
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    stats["skipped"] += 1
                    continue

                session.add(
                    ESGControversy(
                        controversy_id=uuid.uuid4(),
                        entity_id=entity_id,
                        controversy_type=rec["controversy_type"],
                        severity=rec.get("severity"),
                        description=rec.get("description"),
                        start_date=rec.get("start_date"),
                        resolution_date=rec.get("resolution_date"),
                        status=rec.get("status"),
                        estimated_financial_impact=rec.get("estimated_financial_impact"),
                        source=rec.get("source"),
                        source_url=rec.get("source_url"),
                    )
                )
                stats["inserted"] += 1
            except Exception:  # pragma: no cover - defensive
                logger.exception("[%s] failed to load controversy row", self.name)
                stats["errors"] += 1

        await session.flush()
        return stats

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
