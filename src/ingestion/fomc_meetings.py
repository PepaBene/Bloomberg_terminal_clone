"""FOMC rate-decision connector derived from FRED policy-rate series.

The federal funds target range is published by FRED as two daily series:

* ``DFEDTARU`` — federal funds target range, upper limit
* ``DFEDTARL`` — federal funds target range, lower limit

The target range only moves on an FOMC rate decision, so the dates on which
either series changes value are the effective decision dates. This connector
fetches both series (reusing the ``fred_macro`` HTTP/key/rate-limit pattern),
detects the change points, and writes one ``FedMeeting`` per rate change with
the new range and the size/direction of the move.

NOTE: FRED carries no signal for a *no-change* ("HOLD") meeting, so only
meetings that changed the target range are derived here. HOLD meetings would
require the published FOMC calendar as an additional source.
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
UPPER_SERIES = "DFEDTARU"
LOWER_SERIES = "DFEDTARL"


def _to_float(value: Any) -> float | None:
    try:
        if value in (None, "", "."):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def derive_rate_decisions(
    upper_obs: list[dict[str, Any]],
    lower_obs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge upper/lower target-range observations into rate-change events.

    Pure (no I/O) — directly unit-testable. Returns one dict per date on which
    the target range changed, ordered by date.
    """
    upper_by_date = {o["date"]: _to_float(o.get("value")) for o in upper_obs if o.get("date")}
    lower_by_date = {o["date"]: _to_float(o.get("value")) for o in lower_obs if o.get("date")}

    all_dates = sorted(set(upper_by_date) | set(lower_by_date))

    decisions: list[dict[str, Any]] = []
    prev_upper: float | None = None
    prev_lower: float | None = None
    for d in all_dates:
        up = upper_by_date.get(d)
        lo = lower_by_date.get(d)
        if up is None and lo is None:
            continue
        changed = (
            (prev_upper is not None and up is not None and up != prev_upper)
            or (prev_lower is not None and lo is not None and lo != prev_lower)
        )
        if changed:
            ref_new = up if up is not None else lo
            ref_prev = prev_upper if prev_upper is not None else prev_lower
            change_bps = None
            if ref_new is not None and ref_prev is not None:
                change_bps = int(round((ref_new - ref_prev) * 100))
            if change_bps is None or change_bps == 0:
                decision = "HOLD"
            elif change_bps > 0:
                decision = "HIKE"
            else:
                decision = "CUT"
            decisions.append(
                {
                    "meeting_date": d,
                    "fed_funds_upper": up if up is not None else prev_upper,
                    "fed_funds_lower": lo if lo is not None else prev_lower,
                    "change_bps": change_bps,
                    "rate_decision": decision,
                }
            )
        if up is not None:
            prev_upper = up
        if lo is not None:
            prev_lower = lo

    return decisions


class FomcMeetingsConnector(BaseConnector):
    """Derive FOMC rate-decision meetings from FRED target-range series."""

    name = "FOMC Meetings (FRED)"
    connector_type = "BATCH_API"
    data_domain = "MACRO"

    def __init__(self, api_key: str | None = None, start_date: str | None = None):
        self.api_key = api_key or getattr(settings, "FRED_API_KEY", "")
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
            logger.warning("FRED_API_KEY not set — skipping FOMC extraction")
            return []
        upper = await self._fred_observations(UPPER_SERIES)
        lower = await self._fred_observations(LOWER_SERIES)
        logger.info("FOMC: %d upper / %d lower observations", len(upper), len(lower))
        return [{"upper": upper, "lower": lower}]

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [r for r in records if r.get("upper") or r.get("lower")]

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for rec in records:
            out.extend(
                derive_rate_decisions(rec.get("upper", []), rec.get("lower", []))
            )
        logger.info("FOMC: derived %d rate-change meetings", len(out))
        return out

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        from src.models.fed_meeting import FedMeeting

        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        if getattr(self, "dry_run", False):
            return stats

        for rec in records:
            try:
                meeting_date = date.fromisoformat(rec["meeting_date"])
                existing = (
                    await session.execute(
                        select(FedMeeting).where(FedMeeting.meeting_date == meeting_date)
                    )
                ).scalar_one_or_none()

                upper = rec.get("fed_funds_upper")
                lower = rec.get("fed_funds_lower")
                if existing is not None:
                    existing.rate_decision = rec.get("rate_decision")
                    existing.change_bps = rec.get("change_bps")
                    existing.fed_funds_upper = Decimal(str(upper)) if upper is not None else None
                    existing.fed_funds_lower = Decimal(str(lower)) if lower is not None else None
                    stats["updated"] += 1
                    continue

                session.add(
                    FedMeeting(
                        meeting_id=uuid.uuid4(),
                        meeting_date=meeting_date,
                        meeting_type="SCHEDULED",
                        rate_decision=rec.get("rate_decision"),
                        fed_funds_upper=Decimal(str(upper)) if upper is not None else None,
                        fed_funds_lower=Decimal(str(lower)) if lower is not None else None,
                        change_bps=rec.get("change_bps"),
                    )
                )
                stats["inserted"] += 1
            except Exception:  # pragma: no cover - defensive
                logger.exception("[%s] failed to load meeting", self.name)
                stats["errors"] += 1

        await session.flush()
        return stats

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
