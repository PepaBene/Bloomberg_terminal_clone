"""Primary-market bond issuance ingestion connector.

Ingests new-issue (primary market) corporate bond deals into the
``BondIssuance`` table: pricing/spread dynamics, deal size, bookrunners.

FLAG — NEEDS A DATA-SOURCE DECISION + LIVE VALIDATION
-----------------------------------------------------
Primary-market new-issue data (initial price talk, final spread, bookrunner
syndicate, deal size) has no clean free public feed — it is sourced from paid
services (Bloomberg new-issue monitor, Ipreo/IHS Markit, LevFin/Bond Radar,
etc.). This connector is implemented to-pattern against a *configurable* JSON
feed URL (mirroring ``congress_trades.py``) with a real, unit-tested
transform/load. The extract() data source must be chosen and validated against
live data before production use. Deals whose issuer cannot be resolved to an
existing entity are skipped — no issuance rows are fabricated.
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


def _parse_int(value: Any) -> int | None:
    value = _clean(value)
    if value is None:
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def _parse_bool(value: Any) -> bool:
    value = _clean(value)
    return bool(value) and str(value).strip().lower() in ("y", "yes", "true", "1")


def normalize_issuance(row: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize one raw new-issue row into a BondIssuance field dict (pure).

    ``issuer_cik`` / ``issuer_name`` are retained so the loader can resolve the
    (non-nullable) issuer entity FK. Returns ``None`` if the row lacks a
    pricing/announcement date entirely.
    """
    pricing_date = _parse_date(row.get("pricing_date"))
    announce_date = _parse_date(row.get("announcement_date"))
    if not pricing_date and not announce_date:
        return None

    talk_low = _parse_int(row.get("initial_talk_low_bps"))
    talk_high = _parse_int(row.get("initial_talk_high_bps"))
    final_spread = _parse_int(row.get("final_spread_bps"))
    tightening = _parse_int(row.get("tightening_bps"))
    # Derive tightening from talk midpoint → final if not supplied.
    if tightening is None and final_spread is not None and talk_low is not None:
        talk_mid = (talk_low + talk_high) / 2 if talk_high is not None else talk_low
        tightening = int(round(talk_mid - final_spread))

    bookrunners = row.get("all_bookrunners")
    if isinstance(bookrunners, str):
        bookrunners = [b.strip() for b in bookrunners.split(",") if b.strip()]
    elif not isinstance(bookrunners, list):
        bookrunners = None

    return {
        "issuer_cik": _clean(row.get("issuer_cik") or row.get("cik")),
        "issuer_name": _clean(row.get("issuer_name") or row.get("company_name")),
        "pricing_date": pricing_date,
        "settlement_date": _parse_date(row.get("settlement_date")),
        "announcement_date": announce_date,
        "coupon_rate": _parse_decimal(row.get("coupon_rate") or row.get("coupon")),
        "maturity_date": _parse_date(row.get("maturity_date")),
        "seniority": (_clean(row.get("seniority")) or None),
        "issue_price": _parse_decimal(row.get("issue_price")),
        "issue_yield": _parse_decimal(row.get("issue_yield")),
        "initial_talk_low_bps": talk_low,
        "initial_talk_high_bps": talk_high,
        "final_spread_bps": final_spread,
        "tightening_bps": tightening,
        "announced_size_mm": _parse_decimal(row.get("announced_size_mm")),
        "issued_size_mm": _parse_decimal(row.get("issued_size_mm")),
        "lead_left_bookrunner": _clean(row.get("lead_left_bookrunner")),
        "all_bookrunners": bookrunners,
        "use_of_proceeds": _clean(row.get("use_of_proceeds")),
        "currency": (_clean(row.get("currency")) or "USD")[:3],
        "is_benchmark": _parse_bool(row.get("is_benchmark")),
        "is_144a": _parse_bool(row.get("is_144a")),
        "is_registered": _parse_bool(row.get("is_registered")),
    }


class BondIssuancesConnector(BaseConnector):
    """Ingest primary-market bond issuances from a configurable JSON feed."""

    name = "Bond Issuances"
    connector_type = "BATCH_API"
    data_domain = "FIXED_INCOME"

    def __init__(self, *, feed_url: str | None = None, api_key: str | None = None):
        self.feed_url = feed_url or getattr(settings, "BOND_ISSUANCES_FEED_URL", "")
        self.api_key = api_key or getattr(settings, "BOND_ISSUANCES_API_KEY", "")

    def auth_headers(self) -> dict[str, str]:
        headers = {"User-Agent": settings.SEC_USER_AGENT, "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def extract(self) -> list[dict[str, Any]]:
        if not self.feed_url:
            logger.warning(
                "[%s] no BOND_ISSUANCES_FEED_URL configured — needs a data-source "
                "decision + live validation; skipping extraction",
                self.name,
            )
            return []
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(self.feed_url, headers=self.auth_headers())
            resp.raise_for_status()
            data = resp.json()
        records = data if isinstance(data, list) else data.get("issuances", data.get("data", []))
        logger.info("[%s] fetched %d raw rows", self.name, len(records))
        return records

    async def validate(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        valid = []
        for r in records:
            has_issuer = _clean(r.get("issuer_cik") or r.get("cik") or r.get("issuer_name"))
            has_date = _parse_date(r.get("pricing_date")) or _parse_date(
                r.get("announcement_date")
            )
            if has_issuer and has_date:
                valid.append(r)
        return valid

    async def transform(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        out = []
        for r in records:
            norm = normalize_issuance(r)
            if norm:
                out.append(norm)
        logger.info("[%s] normalized %d issuances", self.name, len(out))
        return out

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        from src.models.bond_issuance import BondIssuance
        from src.models.entity import Entity, EntityIdentifier

        counts = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        if getattr(self, "dry_run", False):
            return counts

        for rec in records:
            try:
                # Resolve the (non-nullable) issuer entity — never fabricate one.
                issuer_entity_id = None
                cik = rec.pop("issuer_cik", None)
                issuer_name = rec.pop("issuer_name", None)
                if cik:
                    issuer_entity_id = (
                        await session.execute(
                            select(EntityIdentifier.entity_id).where(
                                EntityIdentifier.identifier_type == "CIK",
                                EntityIdentifier.identifier_value == str(cik),
                            )
                        )
                    ).scalar_one_or_none()
                if issuer_entity_id is None and issuer_name:
                    issuer_entity_id = (
                        await session.execute(
                            select(Entity.entity_id).where(
                                Entity.legal_name == issuer_name
                            )
                        )
                    ).scalar_one_or_none()
                if issuer_entity_id is None:
                    logger.info(
                        "[%s] skipping issuance — issuer '%s' not resolvable to an "
                        "existing entity (no fabricated row created)",
                        self.name,
                        issuer_name or cik,
                    )
                    counts["skipped"] += 1
                    continue

                # De-dupe on (issuer, pricing_date, maturity_date).
                existing = (
                    await session.execute(
                        select(BondIssuance).where(
                            BondIssuance.issuer_entity_id == issuer_entity_id,
                            BondIssuance.pricing_date == rec["pricing_date"],
                            BondIssuance.maturity_date == rec["maturity_date"],
                        )
                    )
                ).scalar_one_or_none()
                if existing:
                    counts["skipped"] += 1
                    continue

                session.add(
                    BondIssuance(
                        issuance_id=uuid.uuid4(),
                        issuer_entity_id=issuer_entity_id,
                        **rec,
                    )
                )
                counts["inserted"] += 1
            except Exception:  # pragma: no cover - defensive
                logger.exception("[%s] failed to load issuance", self.name)
                counts["errors"] += 1
        await session.flush()
        return counts
