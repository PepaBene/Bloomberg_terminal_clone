"""ESG controversies connector (configurable JSON feed).

There is no clean, free, structured public source for ESG controversies (the
established providers — RepRisk, MSCI, Sustainalytics — are paid). This
connector therefore ingests from a *configurable* JSON feed URL, mirroring the
``congress_trades`` pattern (feed URL taken from settings / constructor). Any
compatible feed emitting controversy rows can be plugged in.

The transform and DB load (writing ``ESGControversy`` rows, resolving the
entity from its CIK) are implemented and unit-tested against a representative
feed payload.

FLAG — needs-source-decision:
    No default feed URL ships with this connector (``ESG_CONTROVERSY_FEED_URL``
    is unset). Choosing/licensing an actual ESG-controversy data source is an
    outstanding decision. Do NOT point this at fabricated data.
"""

from __future__ import annotations

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
    """Ingest ESG controversies from a configurable JSON feed."""

    name = "ESG Controversies"
    connector_type = "BATCH_API"
    data_domain = "ESG"

    def __init__(self, feed_url: str | None = None):
        self.feed_url = feed_url or getattr(settings, "ESG_CONTROVERSY_FEED_URL", "")

    async def extract(self) -> list[dict[str, Any]]:
        if not self.feed_url:
            logger.warning(
                "ESG_CONTROVERSY_FEED_URL not configured — skipping extraction "
                "(FLAG: needs a data-source decision)"
            )
            return []
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(
                self.feed_url, headers={"User-Agent": settings.SEC_USER_AGENT}
            )
            resp.raise_for_status()
            data = resp.json()
        records = data if isinstance(data, list) else data.get("controversies", [])
        logger.info("[%s] fetched %d raw rows", self.name, len(records))
        return records

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
        """Normalize raw feed rows into ESGControversy field dicts. Pure (no I/O)."""
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
