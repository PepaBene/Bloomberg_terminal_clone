"""Agency (GSE) bond ingestion connector.

Ingests U.S. federal-agency / GSE debt reference data (FNMA, FHLMC, FHLB,
FFCB, TVA, GNMA, SBA, ...) into the ``AgencyBond`` table.

FLAG — NEEDS A DATA-SOURCE DECISION + LIVE VALIDATION
-----------------------------------------------------
There is no single clean, keyless public feed for the full GSE/agency debt
universe. Fannie Mae, Freddie Mac and the FHLBanks publish debt-issuance data
on their own investor-relations sites (often as XML/CSV/Excel behind bespoke
schemas), and the consolidated feeds (e.g. Bloomberg / ICE / Refinitiv) are
paid. This connector is therefore implemented to-pattern against a
*configurable* JSON feed URL (mirroring how ``congress_trades.py`` takes a
configurable feed URL) with a normalizing transform/load for ``AgencyBond``.
The transform/load is real and unit-tested against a representative sample;
the extract() source must be chosen and validated against live data before
production use. No agency bond rows are fabricated.
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

# Normalize common issuer descriptors onto our short agency_type codes.
_AGENCY_TYPE_MAP = {
    "fannie mae": "FNMA",
    "federal national mortgage association": "FNMA",
    "fnma": "FNMA",
    "freddie mac": "FHLMC",
    "federal home loan mortgage corporation": "FHLMC",
    "fhlmc": "FHLMC",
    "federal home loan bank": "FHLB",
    "fhlb": "FHLB",
    "federal farm credit": "FFCB",
    "ffcb": "FFCB",
    "tennessee valley authority": "TVA",
    "tva": "TVA",
    "ginnie mae": "GNMA",
    "gnma": "GNMA",
    "small business administration": "SBA",
    "sba": "SBA",
}

# Backing/guarantee inference by agency type.
_BACKING_MAP = {
    "GNMA": "EXPLICIT_GUARANTEE",
    "TVA": "EXPLICIT_GUARANTEE",
    "SBA": "EXPLICIT_GUARANTEE",
    "FNMA": "CONSERVATORSHIP",
    "FHLMC": "CONSERVATORSHIP",
    "FHLB": "IMPLICIT_SUPPORT",
    "FFCB": "IMPLICIT_SUPPORT",
}


def _clean(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip()
        if v == "" or v.lower() in ("null", "none", "n/a"):
            return None
        return v
    return value


def _parse_date(value: Any) -> date | None:
    value = _clean(value)
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y%m%d"):
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


def _agency_type(issuer: Any, explicit: Any = None) -> str | None:
    explicit = _clean(explicit)
    if explicit:
        return str(explicit).upper()[:20]
    issuer = _clean(issuer)
    if not issuer:
        return None
    text = str(issuer).lower()
    for needle, code in _AGENCY_TYPE_MAP.items():
        if needle in text:
            return code
    return None


class AgencyBondsConnector(BaseConnector):
    """Ingest GSE/agency debt reference data from a configurable JSON feed."""

    name = "Agency Bonds"
    connector_type = "BATCH_API"
    data_domain = "FIXED_INCOME"

    def __init__(self, *, feed_url: str | None = None, api_key: str | None = None):
        self.feed_url = feed_url or getattr(settings, "AGENCY_BONDS_FEED_URL", "")
        self.api_key = api_key or getattr(settings, "AGENCY_BONDS_API_KEY", "")

    def auth_headers(self) -> dict[str, str]:
        headers = {"User-Agent": settings.SEC_USER_AGENT, "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def extract(self) -> list[dict[str, Any]]:
        if not self.feed_url:
            logger.warning(
                "[%s] no AGENCY_BONDS_FEED_URL configured — needs a data-source "
                "decision + live validation; skipping extraction",
                self.name,
            )
            return []
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(self.feed_url, headers=self.auth_headers())
            resp.raise_for_status()
            data = resp.json()
        records = data if isinstance(data, list) else data.get("bonds", data.get("data", []))
        logger.info("[%s] fetched %d raw rows", self.name, len(records))
        return records

    async def validate(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return [
            r
            for r in records
            if _clean(r.get("cusip")) and _parse_date(r.get("maturity_date"))
        ]

    async def transform(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Normalize raw feed rows into AgencyBond field dicts (pure)."""
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in records:
            cusip = _clean(r.get("cusip"))
            maturity = _parse_date(r.get("maturity_date"))
            if not cusip or not maturity or cusip in seen:
                continue
            seen.add(cusip)

            agency_type = _agency_type(r.get("issuer_name"), r.get("agency_type"))
            backing = _clean(r.get("backing_type")) or (
                _BACKING_MAP.get(agency_type) if agency_type else None
            )
            first_call = _parse_date(r.get("first_call_date"))
            out.append(
                {
                    "cusip": str(cusip)[:9],
                    "issuer_name": _clean(r.get("issuer_name")),
                    "agency_type": agency_type,
                    "backing_type": backing[:25] if backing else None,
                    "coupon_rate": _parse_decimal(r.get("coupon_rate") or r.get("coupon")),
                    "coupon_type": (_clean(r.get("coupon_type")) or "FIXED").upper()[:20],
                    "coupon_frequency": int(r["coupon_frequency"])
                    if _clean(r.get("coupon_frequency")) is not None
                    else 2,
                    "maturity_date": maturity,
                    "issue_date": _parse_date(r.get("issue_date")),
                    "original_amount_mm": _parse_decimal(r.get("original_amount_mm")),
                    "outstanding_amount_mm": _parse_decimal(r.get("outstanding_amount_mm")),
                    "currency": (_clean(r.get("currency")) or "USD")[:3],
                    "is_callable": bool(first_call)
                    or str(r.get("is_callable")).lower() in ("y", "yes", "true", "1"),
                    "first_call_date": first_call,
                    "is_outstanding": True,
                    "status": "OUTSTANDING",
                }
            )
        logger.info("[%s] transformed %d unique agency bonds", self.name, len(out))
        return out

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        from src.models.agency_bond import AgencyBond

        counts = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        if getattr(self, "dry_run", False):
            return counts

        for rec in records:
            try:
                existing = (
                    await session.execute(
                        select(AgencyBond).where(AgencyBond.cusip == rec["cusip"])
                    )
                ).scalar_one_or_none()
                if existing:
                    for key, val in rec.items():
                        if val is not None:
                            setattr(existing, key, val)
                    counts["updated"] += 1
                else:
                    session.add(AgencyBond(bond_id=uuid.uuid4(), **rec))
                    counts["inserted"] += 1
            except Exception:  # pragma: no cover - defensive
                logger.exception("[%s] failed to load row", self.name)
                counts["errors"] += 1
        await session.flush()
        return counts
