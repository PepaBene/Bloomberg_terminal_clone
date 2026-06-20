"""Congressional trading connector (US STOCK Act periodic transaction reports).

Ingests free, public, machine-readable aggregations of House and Senate
financial disclosures filed under the STOCK Act. Used to follow politician
trading activity (e.g. Nancy Pelosi).

The feed URLs are configurable (``CONGRESS_HOUSE_FEED_URL`` /
``CONGRESS_SENATE_FEED_URL``) so any compatible JSON source can be used.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector

logger = logging.getLogger(__name__)

# STOCK Act disclosure deadline (days from transaction to filing).
_DISCLOSURE_DEADLINE_DAYS = 45

# Amount-range strings used by the public feeds → (low, high) USD.
_AMOUNT_RANGES: dict[str, tuple[float, float]] = {
    "$1,001 -": (1_001, 15_000),
    "$1,001 - $15,000": (1_001, 15_000),
    "$15,001 - $50,000": (15_001, 50_000),
    "$50,001 - $100,000": (50_001, 100_000),
    "$100,001 - $250,000": (100_001, 250_000),
    "$250,001 - $500,000": (250_001, 500_000),
    "$500,001 - $1,000,000": (500_001, 1_000_000),
    "$1,000,001 - $5,000,000": (1_000_001, 5_000_000),
    "$5,000,001 - $25,000,000": (5_000_001, 25_000_000),
    "$25,000,001 - $50,000,000": (25_000_001, 50_000_000),
    "$50,000,000 +": (50_000_000, 50_000_000),
    "Over $50,000,000": (50_000_000, 50_000_000),
}

_TYPE_MAP = {
    "purchase": "BUY",
    "buy": "BUY",
    "sale": "SELL",
    "sale_full": "SELL",
    "sale_partial": "SELL",
    "sell": "SELL",
    "exchange": "EXCHANGE",
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


def _parse_amount(value: Any) -> tuple[float | None, float | None]:
    if not value:
        return None, None
    key = str(value).strip()
    if key in _AMOUNT_RANGES:
        return _AMOUNT_RANGES[key]
    # Fall back to a loose match by collapsing whitespace.
    collapsed = " ".join(key.split())
    for k, v in _AMOUNT_RANGES.items():
        if " ".join(k.split()) == collapsed:
            return v
    return None, None


class CongressTradesConnector(BaseConnector):
    """Ingest STOCK Act trades from public House/Senate JSON feeds."""

    name = "Congress STOCK Act"
    connector_type = "BATCH_API"
    data_domain = "OWNERSHIP"

    def __init__(self, chamber: str = "HOUSE"):
        self.chamber = chamber.upper()
        self._url = (
            settings.CONGRESS_HOUSE_FEED_URL
            if self.chamber == "HOUSE"
            else settings.CONGRESS_SENATE_FEED_URL
        )

    async def extract(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(
                self._url, headers={"User-Agent": settings.SEC_USER_AGENT}
            )
            resp.raise_for_status()
            data = resp.json()
        records = data if isinstance(data, list) else data.get("transactions", [])
        logger.info("[%s] fetched %d raw rows", self.name, len(records))
        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        valid = []
        for r in records:
            # Must have a representative/senator name and a transaction date.
            name = r.get("representative") or r.get("senator") or r.get("name")
            if name and (r.get("transaction_date") or r.get("transactionDate")):
                valid.append(r)
        return valid

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize raw feed rows into CongressionalTrade field dicts.

        Pure (no I/O) so it can be unit-tested directly.
        """
        out: list[dict[str, Any]] = []
        for r in records:
            name = r.get("representative") or r.get("senator") or r.get("name")
            tx_date = _parse_date(r.get("transaction_date") or r.get("transactionDate"))
            disc_date = _parse_date(r.get("disclosure_date") or r.get("disclosureDate"))
            if not name or not tx_date:
                continue

            raw_type = str(r.get("type") or r.get("transaction_type") or "").lower().strip()
            tx_type = _TYPE_MAP.get(raw_type, "BUY" if "purchase" in raw_type else "SELL" if "sale" in raw_type else "EXCHANGE")
            low, high = _parse_amount(r.get("amount"))

            lag = (disc_date - tx_date).days if disc_date else None
            ticker = r.get("ticker")
            if ticker in (None, "--", "", "N/A"):
                ticker = None

            out.append(
                {
                    "politician_name": name.strip(),
                    "bioguide_id": r.get("bioguide_id"),
                    "chamber": self.chamber,
                    "party": r.get("party"),
                    "state": r.get("state"),
                    "ticker": ticker.upper() if ticker else None,
                    "asset_description": r.get("asset_description") or r.get("description"),
                    "asset_type": (r.get("asset_type") or r.get("type") or "").upper()[:40] or None,
                    "transaction_type": tx_type,
                    "transaction_date": tx_date,
                    "disclosure_date": disc_date,
                    "amount_range_low": low,
                    "amount_range_high": high,
                    "owner": (r.get("owner") or "").upper()[:20] or None,
                    "disclosure_lag_days": lag,
                    "is_late_disclosure": bool(lag is not None and lag > _DISCLOSURE_DEADLINE_DAYS),
                    "committees": r.get("committees"),
                    "source_url": r.get("ptr_link") or r.get("source") or self._url,
                }
            )
        return out

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        from src.models.congressional_trades import CongressionalTrade

        counts = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        if getattr(self, "dry_run", False):
            return counts

        for rec in records:
            try:
                existing = (
                    await session.execute(
                        select(CongressionalTrade).where(
                            CongressionalTrade.politician_name == rec["politician_name"],
                            CongressionalTrade.transaction_date == rec["transaction_date"],
                            CongressionalTrade.ticker == rec["ticker"],
                            CongressionalTrade.transaction_type == rec["transaction_type"],
                            CongressionalTrade.amount_range_low == rec["amount_range_low"],
                        )
                    )
                ).scalar_one_or_none()
                if existing:
                    counts["skipped"] += 1
                    continue
                session.add(CongressionalTrade(id=uuid.uuid4(), **rec))
                counts["inserted"] += 1
            except Exception:  # pragma: no cover - defensive
                logger.exception("[%s] failed to load row", self.name)
                counts["errors"] += 1
        await session.flush()
        return counts
