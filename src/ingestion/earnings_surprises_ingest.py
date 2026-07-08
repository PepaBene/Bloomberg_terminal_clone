"""Earnings-surprise connector: actual EPS/revenue vs consensus estimate.

An earnings surprise is ``actual - consensus``. This connector computes the
surprise metrics and writes ``EarningsSurprise`` rows from paired
actual/consensus inputs. The pure surprise math and the DB load path are fully
implemented and unit-tested.

FLAG — needs-source-decision / needs-live-data:
    There is no *free* consensus-estimate feed ingested in this repository, and
    actual EPS/revenue must come from an XBRL fundamentals source. This
    connector therefore consumes *already-paired* actual+consensus records
    (assembled by the driver from the ``consensus_estimates`` table plus an
    actuals source). Wiring a real consensus-estimate provider and an
    actual-EPS extractor remains outstanding. Do NOT run this against fabricated
    inputs — feed it only real actual/consensus pairs.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ingestion.base import BaseConnector

logger = logging.getLogger(__name__)


def compute_surprise(
    actual: float | None, consensus: float | None
) -> tuple[float | None, float | None]:
    """Return (surprise, surprise_pct) for an actual vs consensus pair.

    surprise = actual - consensus; surprise_pct = surprise / |consensus| * 100.
    Pure — directly unit-testable. Returns (None, None) when inputs are missing;
    surprise_pct is None (not a division error) when consensus is zero.
    """
    if actual is None or consensus is None:
        return None, None
    surprise = round(actual - consensus, 4)
    if consensus == 0:
        return surprise, None
    pct = round(surprise / abs(consensus) * 100, 4)
    return surprise, pct


class EarningsSurprisesConnector(BaseConnector):
    """Compute and load EarningsSurprise rows from actual/consensus pairs."""

    name = "Earnings Surprises"
    connector_type = "BATCH_COMPUTE"
    data_domain = "EARNINGS"

    def __init__(self, records: list[dict[str, Any]] | None = None):
        # Each record: entity_id, security_id?, fiscal_year, fiscal_quarter,
        # period_end_date?, announcement_date?, actual_eps?, consensus_eps?,
        # actual_revenue?, consensus_revenue?, number_of_estimates?
        self.records = records or []

    async def extract(self) -> list[dict[str, Any]]:
        return list(self.records)

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        valid = []
        for r in records:
            if not r.get("entity_id"):
                continue
            if r.get("fiscal_year") is None or r.get("fiscal_quarter") is None:
                continue
            # Need at least one actual/consensus pair to compute a surprise.
            has_eps = r.get("actual_eps") is not None and r.get("consensus_eps") is not None
            has_rev = r.get("actual_revenue") is not None and r.get("consensus_revenue") is not None
            if not (has_eps or has_rev):
                continue
            valid.append(r)
        return valid

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for r in records:
            eps_surprise, eps_surprise_pct = compute_surprise(
                r.get("actual_eps"), r.get("consensus_eps")
            )
            rev_surprise, rev_surprise_pct = compute_surprise(
                r.get("actual_revenue"), r.get("consensus_revenue")
            )
            out.append(
                {
                    "entity_id": r["entity_id"],
                    "security_id": r.get("security_id"),
                    "fiscal_year": int(r["fiscal_year"]),
                    "fiscal_quarter": int(r["fiscal_quarter"]),
                    "period_end_date": r.get("period_end_date"),
                    "announcement_date": r.get("announcement_date"),
                    "actual_eps": r.get("actual_eps"),
                    "consensus_eps": r.get("consensus_eps"),
                    "actual_revenue": r.get("actual_revenue"),
                    "consensus_revenue": r.get("consensus_revenue"),
                    "number_of_estimates": r.get("number_of_estimates"),
                    "eps_surprise": eps_surprise,
                    "eps_surprise_pct": eps_surprise_pct,
                    "revenue_surprise": rev_surprise,
                    "revenue_surprise_pct": rev_surprise_pct,
                }
            )
        logger.info("EarningsSurprises: computed %d surprise rows", len(out))
        return out

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        from src.models.earnings_intelligence import EarningsSurprise

        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        if getattr(self, "dry_run", False):
            return stats

        def _dec(v: Any) -> Decimal | None:
            return Decimal(str(v)) if v is not None else None

        def _as_date(v: Any) -> date | None:
            if v is None:
                return None
            if isinstance(v, date):
                return v
            return date.fromisoformat(str(v))

        for rec in records:
            try:
                existing = (
                    await session.execute(
                        select(EarningsSurprise).where(
                            EarningsSurprise.entity_id == rec["entity_id"],
                            EarningsSurprise.fiscal_year == rec["fiscal_year"],
                            EarningsSurprise.fiscal_quarter == rec["fiscal_quarter"],
                        )
                    )
                ).scalar_one_or_none()

                fields = dict(
                    security_id=rec.get("security_id"),
                    period_end_date=_as_date(rec.get("period_end_date")),
                    announcement_date=_as_date(rec.get("announcement_date")),
                    actual_eps=_dec(rec.get("actual_eps")),
                    consensus_eps=_dec(rec.get("consensus_eps")),
                    actual_revenue=_dec(rec.get("actual_revenue")),
                    consensus_revenue=_dec(rec.get("consensus_revenue")),
                    number_of_estimates=rec.get("number_of_estimates"),
                    eps_surprise=_dec(rec.get("eps_surprise")),
                    eps_surprise_pct=_dec(rec.get("eps_surprise_pct")),
                    revenue_surprise=_dec(rec.get("revenue_surprise")),
                    revenue_surprise_pct=_dec(rec.get("revenue_surprise_pct")),
                )

                if existing is not None:
                    for k, v in fields.items():
                        setattr(existing, k, v)
                    stats["updated"] += 1
                    continue

                session.add(
                    EarningsSurprise(
                        surprise_id=uuid.uuid4(),
                        entity_id=rec["entity_id"],
                        fiscal_year=rec["fiscal_year"],
                        fiscal_quarter=rec["fiscal_quarter"],
                        **fields,
                    )
                )
                stats["inserted"] += 1
            except Exception:  # pragma: no cover - defensive
                logger.exception("[%s] failed to load surprise row", self.name)
                stats["errors"] += 1

        await session.flush()
        return stats
