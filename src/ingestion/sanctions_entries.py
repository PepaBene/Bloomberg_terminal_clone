"""Sanctions connector (US OFAC SDN list, keyless).

Ingests entries from the OFAC Specially Designated Nationals (SDN) list, a
free, keyless CSV download (https://www.treasury.gov/ofac/downloads/sdn.csv).

SDN CSV column layout (no header row):
    0 ent_num, 1 SDN_Name, 2 SDN_Type, 3 Program, 4 Title, 5 Call_Sign,
    6 Vess_type, 7 Tonnage, 8 GRT, 9 Vess_flag, 10 Vess_owner, 11 Remarks
The literal string "-0-" is OFAC's placeholder for an empty field.
"""

from __future__ import annotations

import csv
import io
import logging
import uuid
from datetime import date
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector

logger = logging.getLogger(__name__)

# OFAC SDN_Type value -> our target_type. Blank ("-0-") means an entity/org.
_TYPE_MAP = {
    "individual": "individual",
    "vessel": "vessel",
    "aircraft": "aircraft",
    "": "entity",
}


def _clean(value: str | None) -> str | None:
    """Strip OFAC padding; treat the '-0-' placeholder as null."""
    if value is None:
        return None
    text = value.strip()
    if not text or text == "-0-":
        return None
    return text


class SanctionsEntriesConnector(BaseConnector):
    """Ingest OFAC SDN sanctions entries from the keyless CSV download."""

    name = "OFAC SDN Sanctions"
    connector_type = "BATCH_API"
    data_domain = "POLITICAL"

    def __init__(self, csv_url: str | None = None, max_entries: int | None = None):
        self._url = csv_url or settings.OFAC_SDN_CSV_URL
        self.max_entries = max_entries

    async def extract(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            resp = await client.get(
                self._url, headers={"User-Agent": settings.SEC_USER_AGENT}
            )
            resp.raise_for_status()
            text = resp.text

        records: list[dict[str, Any]] = []
        reader = csv.reader(io.StringIO(text))
        for row in reader:
            if len(row) < 4:
                continue
            records.append(
                {
                    "ent_num": row[0].strip(),
                    "name": row[1],
                    "sdn_type": row[2],
                    "program": row[3],
                    "title": row[4] if len(row) > 4 else None,
                    "vess_flag": row[9] if len(row) > 9 else None,
                    "remarks": row[11] if len(row) > 11 else None,
                }
            )
            if self.max_entries and len(records) >= self.max_entries:
                break
        logger.info("[%s] fetched %d raw SDN rows", self.name, len(records))
        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [r for r in records if _clean(r.get("name"))]

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize SDN rows into SanctionsEntry field dicts. Pure (no I/O)."""
        out: list[dict[str, Any]] = []
        for r in records:
            name = _clean(r.get("name"))
            if not name:
                continue
            sdn_type = (_clean(r.get("sdn_type")) or "").lower()
            target_type = _TYPE_MAP.get(sdn_type, sdn_type or "entity")
            program = _clean(r.get("program"))

            title = _clean(r.get("title"))
            remarks = _clean(r.get("remarks"))
            desc_parts = [p for p in (title, remarks) if p]
            description = "; ".join(desc_parts) or None

            out.append(
                {
                    "program": program[:20] if program else None,
                    "country_code": None,  # SDN.csv has no ISO country code
                    "target_name": name[:200],
                    "target_type": target_type[:20] if target_type else None,
                    "status": "ACTIVE",
                    "effective_date": None,  # not present in SDN.csv
                    "description": description,
                    "affected_sectors": None,
                    "source_url": self._url[:500],
                    # Not a model column; used only for dedup in load().
                    "_ent_num": r.get("ent_num"),
                }
            )
        return out

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        from src.models.political_intelligence import SanctionsEntry

        counts = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        if getattr(self, "dry_run", False):
            return counts

        for rec in records:
            rec = dict(rec)
            rec.pop("_ent_num", None)
            try:
                # Dedup on (target_name, program) — no natural key column.
                existing = (
                    await session.execute(
                        select(SanctionsEntry).where(
                            SanctionsEntry.target_name == rec["target_name"],
                            SanctionsEntry.program == rec["program"],
                        )
                    )
                ).scalar_one_or_none()
                if existing:
                    counts["skipped"] += 1
                    continue
                session.add(SanctionsEntry(id=uuid.uuid4(), **rec))
                counts["inserted"] += 1
            except Exception:  # pragma: no cover - defensive
                logger.exception("[%s] failed to load sanctions entry", self.name)
                counts["errors"] += 1
        await session.flush()
        return counts
