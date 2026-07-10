"""Regulatory actions connector (US Federal Register, keyless).

Ingests recently published regulatory documents (Rules, Proposed Rules,
Notices, Presidential Documents) from the Federal Register public API
(https://www.federalregister.gov/api/v1/documents.json). This is a free,
keyless JSON API.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import date, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector

logger = logging.getLogger(__name__)

_STOPWORDS = {"OF", "THE", "AND", "FOR", "SYSTEM", "US", "U.S."}

_FIELDS = [
    "title",
    "type",
    "document_number",
    "agencies",
    "publication_date",
    "abstract",
    "html_url",
]


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def _agency_code(agencies: list[dict[str, Any]] | None) -> str | None:
    """Derive a short (<=10 char) agency code from the first agency."""
    if not agencies:
        return None
    a = agencies[0]
    acronym = a.get("acronym")
    if acronym:
        return str(acronym)[:10]
    name = a.get("name") or a.get("raw_name") or ""
    words = [w for w in re.findall(r"[A-Za-z]+", name) if w.upper() not in _STOPWORDS]
    initials = "".join(w[0] for w in words).upper()
    if 2 <= len(initials) <= 10:
        return initials
    return (name or "")[:10] or None


class RegulatoryActionsConnector(BaseConnector):
    """Ingest recent regulatory documents from the Federal Register API."""

    name = "Federal Register Regulatory Actions"
    connector_type = "BATCH_API"
    data_domain = "POLITICAL"

    def __init__(self, per_page: int = 50, api_url: str | None = None):
        self._url = api_url or settings.FEDERAL_REGISTER_API_URL
        self.per_page = per_page

    async def extract(self) -> list[dict[str, Any]]:
        params: list[tuple[str, Any]] = [
            ("per_page", self.per_page),
            ("order", "newest"),
        ]
        params += [("fields[]", f) for f in _FIELDS]
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            resp = await client.get(
                self._url,
                params=params,
                headers={"User-Agent": settings.SEC_USER_AGENT},
            )
            resp.raise_for_status()
            data = resp.json()
        results = data.get("results", [])
        logger.info("[%s] fetched %d raw documents", self.name, len(results))
        return results

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [r for r in records if (r.get("title") or "").strip()]

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize Federal Register documents into RegulatoryAction dicts."""
        out: list[dict[str, Any]] = []
        for r in records:
            agencies = r.get("agencies") or []
            agency_names = [a.get("name") or a.get("raw_name") for a in agencies]
            out.append(
                {
                    "agency": _agency_code(agencies),
                    "action_type": (r.get("type") or None) and str(r["type"])[:20],
                    "title": str(r["title"])[:500],
                    "description": r.get("abstract") or None,
                    "affected_entity_ids": None,
                    "affected_sectors": (
                        {"agencies": [n for n in agency_names if n]}
                        if agency_names
                        else None
                    ),
                    "severity": None,
                    "financial_impact": None,
                    "action_date": _parse_date(r.get("publication_date")),
                    "source_url": (r.get("html_url") or "")[:500] or None,
                    # Not a model column; used only for dedup in load().
                    "_document_number": r.get("document_number"),
                }
            )
        return out

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        from src.models.political_intelligence import RegulatoryAction

        counts = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        if getattr(self, "dry_run", False):
            return counts

        for rec in records:
            rec = dict(rec)
            rec.pop("_document_number", None)
            try:
                # Dedup on (title, action_date, source_url) — no natural key column.
                existing = (
                    await session.execute(
                        select(RegulatoryAction).where(
                            RegulatoryAction.title == rec["title"],
                            RegulatoryAction.action_date == rec["action_date"],
                            RegulatoryAction.source_url == rec["source_url"],
                        )
                    )
                ).scalar_one_or_none()
                if existing:
                    counts["skipped"] += 1
                    continue
                session.add(RegulatoryAction(id=uuid.uuid4(), **rec))
                counts["inserted"] += 1
            except Exception:  # pragma: no cover - defensive
                logger.exception("[%s] failed to load action", self.name)
                counts["errors"] += 1
        await session.flush()
        return counts
