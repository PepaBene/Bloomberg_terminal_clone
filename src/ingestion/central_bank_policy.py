"""Central-bank policy-rate connector derived from FRED policy-rate series.

Each central bank's headline policy rate is published on FRED as a single
series. This connector fetches one series per bank (reusing the ``fred_macro``
HTTP/key/rate-limit pattern), detects the dates on which the rate changed, and
writes one ``CentralBankPolicy`` row per change with the new rate, the previous
rate, the size of the move and its direction.

The default bank→series map covers the Fed (target-range upper limit). ECB and
BOE FRED series IDs are included as sensible defaults but their exact IDs and
publication cadence should be confirmed against live FRED data before relying
on them in production — see the FLAG in the module docstring.

FLAG: needs-live-data-validation for the non-Fed (ECB/BOE) FRED series IDs.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector
from src.ingestion.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

FRED_BASE_URL = "https://api.stlouisfed.org/fred"

# bank_code -> FRED series id for the headline policy rate.
# FED uses the target-range upper limit (DFEDTARU). ECB/BOE default series
# should be validated against live FRED data (see module FLAG).
DEFAULT_BANK_SERIES: dict[str, str] = {
    "FED": "DFEDTARU",   # Federal funds target range, upper limit
    "ECB": "ECBMRRFR",   # ECB main refinancing operations rate
    "BOE": "BOERUKM",    # Bank of England official Bank Rate (validate)
}


def _to_float(value: Any) -> float | None:
    try:
        if value in (None, "", "."):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def derive_policy_changes(
    bank_code: str, observations: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Detect policy-rate change points in a single FRED rate series.

    Pure (no I/O) — directly unit-testable. Returns one dict per change date.
    """
    out: list[dict[str, Any]] = []
    prev: float | None = None
    for obs in sorted(observations, key=lambda o: o.get("date", "")):
        d = obs.get("date")
        val = _to_float(obs.get("value"))
        if d is None or val is None:
            continue
        if prev is not None and val != prev:
            change = round(val - prev, 4)
            direction = "HIKE" if change > 0 else "CUT" if change < 0 else "HOLD"
            out.append(
                {
                    "bank_code": bank_code,
                    "meeting_date": d,
                    "policy_rate": val,
                    "previous_rate": prev,
                    "rate_change": change,
                    "rate_direction": direction,
                }
            )
        prev = val
    return out


class CentralBankPolicyConnector(BaseConnector):
    """Derive central-bank policy decisions from FRED policy-rate series."""

    name = "Central Bank Policy (FRED)"
    connector_type = "BATCH_API"
    data_domain = "MACRO"

    def __init__(
        self,
        api_key: str | None = None,
        banks: dict[str, str] | None = None,
        start_date: str | None = None,
    ):
        self.api_key = api_key or getattr(settings, "FRED_API_KEY", "")
        self.banks = banks or dict(DEFAULT_BANK_SERIES)
        self.start_date = start_date
        rate_limit = getattr(settings, "FRED_RATE_LIMIT", 120)
        self.rate_limiter = RateLimiter(max_requests=rate_limit, per_seconds=60.0)
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def _fred_observations(self, series_id: str) -> list[dict[str, Any]]:
        await self.rate_limiter.acquire()
        client = await self._get_client()
        params: dict[str, Any] = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
        }
        if self.start_date:
            params["observation_start"] = self.start_date
        resp = await client.get(f"{FRED_BASE_URL}/series/observations", params=params)
        resp.raise_for_status()
        return resp.json().get("observations", [])

    async def extract(self) -> list[dict[str, Any]]:
        if not self.api_key:
            logger.warning("FRED_API_KEY not set — skipping central-bank extraction")
            return []
        records: list[dict[str, Any]] = []
        for bank_code, series_id in self.banks.items():
            try:
                obs = await self._fred_observations(series_id)
                records.append({"bank_code": bank_code, "series_id": series_id, "observations": obs})
                logger.info("CentralBank: %s (%s) — %d observations", bank_code, series_id, len(obs))
            except Exception as exc:  # pragma: no cover - network
                logger.error("CentralBank: failed to fetch %s/%s: %s", bank_code, series_id, exc)
        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [r for r in records if r.get("bank_code") and r.get("observations")]

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for rec in records:
            out.extend(derive_policy_changes(rec["bank_code"], rec.get("observations", [])))
        logger.info("CentralBank: derived %d policy changes", len(out))
        return out

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        from src.models.macro import CentralBankPolicy

        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        if getattr(self, "dry_run", False):
            return stats

        for rec in records:
            try:
                meeting_date = date.fromisoformat(rec["meeting_date"])
                existing = (
                    await session.execute(
                        select(CentralBankPolicy).where(
                            CentralBankPolicy.bank_code == rec["bank_code"],
                            CentralBankPolicy.meeting_date == meeting_date,
                        )
                    )
                ).scalar_one_or_none()

                def _dec(v: Any) -> Decimal | None:
                    return Decimal(str(v)) if v is not None else None

                if existing is not None:
                    existing.policy_rate = _dec(rec.get("policy_rate"))
                    existing.previous_rate = _dec(rec.get("previous_rate"))
                    existing.rate_change = _dec(rec.get("rate_change"))
                    existing.rate_direction = rec.get("rate_direction")
                    stats["updated"] += 1
                    continue

                session.add(
                    CentralBankPolicy(
                        policy_id=uuid.uuid4(),
                        bank_code=rec["bank_code"],
                        meeting_date=meeting_date,
                        decision_date=meeting_date,
                        policy_rate=_dec(rec.get("policy_rate")),
                        previous_rate=_dec(rec.get("previous_rate")),
                        rate_change=_dec(rec.get("rate_change")),
                        rate_direction=rec.get("rate_direction"),
                        source="FRED",
                    )
                )
                stats["inserted"] += 1
            except Exception:  # pragma: no cover - defensive
                logger.exception("[%s] failed to load policy row", self.name)
                stats["errors"] += 1

        await session.flush()
        return stats

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
