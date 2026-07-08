"""Treasury securities ingestion connector (U.S. Treasury Fiscal Data API).

Ingests marketable Treasury securities (Bills, Notes, Bonds, TIPS, FRNs) from
the free, keyless U.S. Treasury Fiscal Data API. The ``auctions_query`` dataset
carries per-CUSIP reference data (type, coupon, issue/maturity dates) plus the
auction result fields (high yield, price, bid-to-cover).

Source: https://api.fiscaldata.treasury.gov/services/api/fiscal_service
Dataset: /v1/accounting/od/auctions_query  (JSON, no API key required)

This is a genuinely working, keyless connector.
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

FISCAL_DATA_BASE_URL = (
    "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
)
AUCTIONS_ENDPOINT = "/v1/accounting/od/auctions_query"

# Map Fiscal Data ``security_type`` values onto our TreasurySecurity.treasury_type.
_TYPE_MAP = {
    "Bill": "BILL",
    "Note": "NOTE",
    "Bond": "BOND",
    "TIPS": "TIPS",
    "FRN": "FRN",
    "CMB": "CMB",
}

# Only these fields are requested from the API (keeps payloads small).
_FIELDS = ",".join(
    [
        "cusip",
        "security_type",
        "security_term",
        "int_rate",
        "int_payment_frequency",
        "issue_date",
        "maturity_date",
        "auction_date",
        "high_yield",
        "low_yield",
        "avg_med_yield",
        "price_per100",
        "bid_to_cover_ratio",
        "offering_amt",
        "total_accepted",
        "currently_outstanding",
        "callable",
        "inflation_index_security",
        "floating_rate",
        "index_ratio_on_issue_date",
        "ref_cpi_on_issue_date",
        "reopening",
    ]
)


def _clean(value: Any) -> Any:
    """The Fiscal Data API returns the literal string ``"null"`` for empties."""
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip()
        if v == "" or v.lower() == "null":
            return None
        return v
    return value


def _parse_date(value: Any) -> date | None:
    value = _clean(value)
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(str(value), fmt).date()
        except ValueError:
            continue
    return None


def _parse_decimal(value: Any) -> Decimal | None:
    value = _clean(value)
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _is_yes(value: Any) -> bool:
    value = _clean(value)
    return bool(value) and str(value).strip().lower() in ("yes", "true", "y", "1")


class TreasurySecuritiesConnector(BaseConnector):
    """Ingest Treasury security reference + auction data from Fiscal Data API."""

    name = "Treasury Securities (Fiscal Data)"
    connector_type = "BATCH_API"
    data_domain = "FIXED_INCOME"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        page_size: int = 1000,
        max_pages: int = 5,
        start_date: str | None = None,
    ):
        self.base_url = (base_url or FISCAL_DATA_BASE_URL).rstrip("/")
        self.page_size = page_size
        self.max_pages = max_pages
        # Optional lower bound on auction_date (ISO ``YYYY-MM-DD``).
        self.start_date = start_date

    async def extract(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        url = f"{self.base_url}{AUCTIONS_ENDPOINT}"
        params: dict[str, Any] = {
            "fields": _FIELDS,
            "sort": "-auction_date",
            "page[size]": self.page_size,
        }
        if self.start_date:
            params["filter"] = f"auction_date:gte:{self.start_date}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            for page in range(1, self.max_pages + 1):
                params["page[number]"] = page
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                payload = resp.json()
                batch = payload.get("data", [])
                records.extend(batch)
                logger.info(
                    "[%s] page %d — %d rows", self.name, page, len(batch)
                )
                # Stop if this was the last page.
                meta = payload.get("meta", {})
                total_pages = meta.get("total-pages")
                if not batch or (total_pages and page >= total_pages):
                    break
        logger.info("[%s] extracted %d raw rows", self.name, len(records))
        return records

    async def validate(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        valid = []
        for r in records:
            # Must have a CUSIP and a maturity date (both non-nullable columns).
            if _clean(r.get("cusip")) and _parse_date(r.get("maturity_date")):
                valid.append(r)
        return valid

    async def transform(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Normalize raw Fiscal Data rows into TreasurySecurity field dicts.

        Pure (no I/O) so it can be unit-tested directly.
        """
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in records:
            cusip = _clean(r.get("cusip"))
            maturity = _parse_date(r.get("maturity_date"))
            if not cusip or not maturity:
                continue
            # Reopenings share a CUSIP; keep the first (most recent auction).
            if cusip in seen:
                continue
            seen.add(cusip)

            sec_type = _clean(r.get("security_type")) or ""
            is_tips = _is_yes(r.get("inflation_index_security"))
            is_frn = _is_yes(r.get("floating_rate"))
            if is_tips:
                treasury_type = "TIPS"
            elif is_frn:
                treasury_type = "FRN"
            else:
                treasury_type = _TYPE_MAP.get(sec_type, (sec_type or "UNKNOWN").upper())

            coupon = _parse_decimal(r.get("int_rate"))
            # Bills are zero-coupon (no periodic payments); notes/bonds pay semi-annually.
            if treasury_type in ("BILL", "CMB"):
                coupon_freq = 0
            elif treasury_type == "FRN":
                coupon_freq = 4
            else:
                coupon_freq = 2

            out.append(
                {
                    "cusip": cusip[:9],
                    "treasury_type": treasury_type[:25],
                    "coupon_rate": coupon,
                    "coupon_frequency": coupon_freq,
                    "issue_date": _parse_date(r.get("issue_date")),
                    "maturity_date": maturity,
                    "original_issue_amount": _parse_decimal(r.get("total_accepted"))
                    or _parse_decimal(r.get("offering_amt")),
                    "outstanding_amount": _parse_decimal(r.get("currently_outstanding")),
                    "auction_date": _parse_date(r.get("auction_date")),
                    "auction_high_yield": _parse_decimal(r.get("high_yield")),
                    "auction_price": _parse_decimal(r.get("price_per100")),
                    "auction_bid_to_cover": _parse_decimal(r.get("bid_to_cover_ratio")),
                    "auction_median_yield": _parse_decimal(r.get("avg_med_yield")),
                    "auction_low_yield": _parse_decimal(r.get("low_yield")),
                    "is_inflation_indexed": is_tips,
                    "index_ratio": _parse_decimal(r.get("index_ratio_on_issue_date")),
                    "ref_cpi_value": _parse_decimal(r.get("ref_cpi_on_issue_date")),
                    "is_outstanding": True,
                    "status": "OUTSTANDING",
                }
            )
        logger.info("[%s] transformed %d unique securities", self.name, len(out))
        return out

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        from src.models.treasury import TreasurySecurity

        counts = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        if getattr(self, "dry_run", False):
            return counts

        for rec in records:
            try:
                existing = (
                    await session.execute(
                        select(TreasurySecurity).where(
                            TreasurySecurity.cusip == rec["cusip"]
                        )
                    )
                ).scalar_one_or_none()
                if existing:
                    for key, val in rec.items():
                        if val is not None:
                            setattr(existing, key, val)
                    counts["updated"] += 1
                else:
                    session.add(TreasurySecurity(treasury_id=uuid.uuid4(), **rec))
                    counts["inserted"] += 1
            except Exception:  # pragma: no cover - defensive
                logger.exception("[%s] failed to load row", self.name)
                counts["errors"] += 1
        await session.flush()
        return counts
