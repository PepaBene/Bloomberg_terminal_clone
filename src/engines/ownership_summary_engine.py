"""Ownership summary rollup engine (Spec 8.4).

Aggregates already-ingested ownership rows (``InstitutionalHolding``,
``InsiderHolding``, ``ShortInterest``) into a per-security
``OwnershipSummary`` snapshot that is read by the E4 screening engine.

Pure computation — no external calls. The aggregation math lives in the
pure :func:`aggregate_ownership` helper so it can be unit-tested without a
database; :func:`compute_for_security` wires it up to the DB.

Note: the ``OwnershipSummary`` model has no short-interest columns, so short
interest is only used (optionally) as a ``report_date`` fallback and is not
persisted. Only the columns that exist on the model are populated.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.ownership import InsiderHolding, InstitutionalHolding, ShortInterest
from src.models.security import EquityDetails

logger = logging.getLogger(__name__)


@dataclass
class OwnershipRollup:
    """Computed rollup matching the ``OwnershipSummary`` columns."""

    report_date: date
    institutional_holders_count: int | None = None
    institutional_shares: float | None = None
    insider_shares: float | None = None
    institutional_percent: float | None = None
    insider_percent: float | None = None
    top_10_concentration: float | None = None

    def as_summary_values(self, security_id: UUID) -> dict[str, Any]:
        """Return a dict keyed by ``OwnershipSummary`` column names."""
        return {
            "security_id": security_id,
            "report_date": self.report_date,
            "institutional_holders_count": self.institutional_holders_count,
            "institutional_shares": self.institutional_shares,
            "insider_shares": self.insider_shares,
            "institutional_percent": self.institutional_percent,
            "insider_percent": self.insider_percent,
            "top_10_concentration": self.top_10_concentration,
        }


# NUMERIC(8,4) columns (institutional_percent/insider_percent/top_10_concentration)
# cap at +/-9999.9999. Legitimate percentages are 0-100; anything beyond this
# bound means the shares-outstanding denominator is bad/stale data, not a
# real ownership figure -- drop it rather than let it overflow the column and
# crash (and roll back) the whole batch.
_PERCENT_MAX = 9999.9999


def _round(value: float | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    value = round(value, digits)
    if abs(value) > _PERCENT_MAX:
        logger.warning("Discarding out-of-range percent value %.4f (bad shares_outstanding?)", value)
        return None
    return value


def aggregate_ownership(
    inst_holdings: list[dict[str, Any]],
    insider_shares_by_person: dict[str, float],
    shares_outstanding: float | None,
    report_date: date,
) -> OwnershipRollup:
    """Pure aggregation of ownership inputs into a rollup.

    Parameters
    ----------
    inst_holdings:
        One dict per institutional holder as-of ``report_date`` with keys
        ``shares_held`` and ``percent_of_outstanding`` (either may be None).
    insider_shares_by_person:
        Mapping of insider name -> latest ``shares_owned_after``.
    shares_outstanding:
        Security shares outstanding (used to derive percentages when the
        holding rows do not carry ``percent_of_outstanding``). May be None.
    report_date:
        The date stamped on the produced summary.
    """
    holders_count = len(inst_holdings) or None

    inst_shares_total = sum((h.get("shares_held") or 0.0) for h in inst_holdings)
    inst_shares = inst_shares_total or None

    # Institutional percent: prefer summing reported percent_of_outstanding,
    # otherwise derive from shares outstanding.
    pct_vals = [
        h["percent_of_outstanding"]
        for h in inst_holdings
        if h.get("percent_of_outstanding") is not None
    ]
    if pct_vals:
        inst_percent: float | None = sum(pct_vals)
    elif shares_outstanding and inst_shares:
        inst_percent = inst_shares / shares_outstanding * 100
    else:
        inst_percent = None

    # Top-10 concentration as a percent of shares outstanding (fallback: of the
    # total institutional block when shares outstanding is unknown).
    top10 = sorted(
        inst_holdings, key=lambda h: (h.get("shares_held") or 0.0), reverse=True
    )[:10]
    top10_shares = sum((h.get("shares_held") or 0.0) for h in top10)
    denom = shares_outstanding or inst_shares_total
    top_10_concentration = (top10_shares / denom * 100) if denom else None

    # Insider block.
    insider_total = sum(insider_shares_by_person.values())
    insider_shares = insider_total or None
    insider_percent = (
        insider_total / shares_outstanding * 100
        if insider_total and shares_outstanding
        else None
    )

    return OwnershipRollup(
        report_date=report_date,
        institutional_holders_count=holders_count,
        institutional_shares=inst_shares,
        insider_shares=insider_shares,
        institutional_percent=_round(inst_percent),
        insider_percent=_round(insider_percent),
        top_10_concentration=_round(top_10_concentration),
    )


async def _latest_insider_shares(
    session: AsyncSession, security_id: UUID
) -> tuple[dict[str, float], date | None]:
    """Reduce insider transactions to the latest shares_owned_after per person."""
    result = await session.execute(
        select(
            InsiderHolding.insider_name,
            InsiderHolding.transaction_date,
            InsiderHolding.shares_owned_after,
        ).where(InsiderHolding.security_id == security_id)
    )
    latest: dict[str, tuple[date | None, float]] = {}
    max_date: date | None = None
    for name, tx_date, shares_after in result.all():
        if shares_after is None:
            continue
        key = name or "UNKNOWN"
        prev = latest.get(key)
        # Prefer the most recent transaction for each insider.
        if prev is None or (tx_date is not None and (prev[0] is None or tx_date >= prev[0])):
            latest[key] = (tx_date, float(shares_after))
        if tx_date is not None and (max_date is None or tx_date > max_date):
            max_date = tx_date
    return {k: v[1] for k, v in latest.items()}, max_date


async def compute_for_security(
    session: AsyncSession, security_id: UUID
) -> OwnershipRollup | None:
    """Compute an ownership rollup for a single security, or None if no inputs."""
    # Latest institutional report date drives the summary report_date.
    inst_date = await session.scalar(
        select(func.max(InstitutionalHolding.report_date)).where(
            InstitutionalHolding.security_id == security_id
        )
    )

    inst_holdings: list[dict[str, Any]] = []
    if inst_date is not None:
        rows = await session.execute(
            select(
                InstitutionalHolding.shares_held,
                InstitutionalHolding.percent_of_outstanding,
            ).where(
                InstitutionalHolding.security_id == security_id,
                InstitutionalHolding.report_date == inst_date,
            )
        )
        for shares_held, pct in rows.all():
            inst_holdings.append(
                {
                    "shares_held": float(shares_held) if shares_held is not None else None,
                    "percent_of_outstanding": float(pct) if pct is not None else None,
                }
            )

    insider_shares, insider_date = await _latest_insider_shares(session, security_id)

    # Short interest is not a column on OwnershipSummary; only used as a
    # report_date fallback when there is no institutional/insider data.
    si_date = await session.scalar(
        select(func.max(ShortInterest.settlement_date)).where(
            ShortInterest.security_id == security_id
        )
    )

    report_date = inst_date or insider_date or si_date
    if report_date is None:
        return None
    if not inst_holdings and not insider_shares:
        # Nothing to summarise beyond a bare date — skip.
        return None

    shares_outstanding = await session.scalar(
        select(EquityDetails.shares_outstanding).where(
            EquityDetails.security_id == security_id
        )
    )
    shares_outstanding = float(shares_outstanding) if shares_outstanding is not None else None

    return aggregate_ownership(
        inst_holdings, insider_shares, shares_outstanding, report_date
    )
