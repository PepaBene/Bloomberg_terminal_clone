"""Pillar 1 Supplement: Debt Maturity Profile engine (DDIS).

Pure computation over already-ingested ``DebtTranche`` rows to produce a
``DebtMaturityProfile`` plus per-year ``MaturityBucket`` rows for an entity.

There is **no external data source** for this feature — the debt tranches are
populated by the capital-structure ingestion workstream, and the maturity
profile is entirely *computed* from them (bucketing by maturity year, weighted
averages, refinancing-risk indicators).

The computation helpers are side-effect-free so they can be unit-tested
directly. :func:`compute_and_persist_profiles` wires them to the database.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_DAYS_PER_YEAR = 365.25

# Refinancing-risk thresholds (documented, deterministic).
_MATURITY_WALL_PCT = 0.20   # >20% of debt maturing within 1yr → wall alert
_NEAR_TERM_STRESS_PCT = 0.30  # >30% within 1yr → near-term stress
_CASH_COVERAGE_STRESS = 1.0   # cash < 1x of 1yr maturities → stress


@dataclass
class MaturityBucketResult:
    """One calendar-year maturity bucket."""

    year: int
    total_amount: float
    breakdown: dict[str, float] = field(default_factory=dict)


@dataclass
class MaturityProfileResult:
    """Computed aggregate maturity metrics for one entity."""

    as_of_date: date
    debt_maturing_1yr: float
    debt_maturing_2yr: float
    debt_maturing_3yr: float
    total_debt: float
    pct_debt_maturing_1yr: float | None
    pct_debt_maturing_3yr: float | None
    weighted_avg_maturity_years: float | None
    weighted_avg_coupon: float | None
    cash_to_1yr_maturities: float | None
    fcf_to_1yr_maturities: float | None
    maturity_wall_alert: bool
    near_term_stress: bool
    buckets: list[MaturityBucketResult] = field(default_factory=list)


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _tranche_view(tranche: Any) -> dict[str, Any]:
    """Normalize an ORM ``DebtTranche`` or a plain dict into a field dict."""
    if isinstance(tranche, dict):
        get = tranche.get
    else:
        def get(key, default=None):
            return getattr(tranche, key, default)

    return {
        "principal_amount": _as_float(get("principal_amount")),
        "maturity_date": get("maturity_date"),
        "coupon_rate": _as_float(get("coupon_rate")),
        "seniority_type": get("seniority_type"),
        "instrument_type": get("instrument_type"),
    }


def compute_maturity_profile(
    tranches: Iterable[Any],
    as_of_date: date,
    *,
    cash: float | None = None,
    free_cash_flow: float | None = None,
) -> MaturityProfileResult:
    """Compute a maturity profile from an iterable of debt tranches.

    Tranches may be ORM ``DebtTranche`` objects or plain dicts carrying
    ``principal_amount``, ``maturity_date``, ``coupon_rate``,
    ``seniority_type``/``instrument_type``. Tranches without a principal or a
    future maturity date are ignored for maturity-window purposes.
    """
    views = [_tranche_view(t) for t in tranches]

    total_debt = 0.0
    debt_1yr = debt_2yr = debt_3yr = 0.0
    wam_num = 0.0            # Σ principal * years-to-maturity
    wam_den = 0.0            # Σ principal (with a future maturity)
    coupon_num = 0.0         # Σ principal * coupon
    coupon_den = 0.0         # Σ principal (with a coupon)
    buckets: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for v in views:
        principal = v["principal_amount"]
        if not principal or principal <= 0:
            continue
        total_debt += principal

        coupon = v["coupon_rate"]
        if coupon is not None:
            coupon_num += principal * coupon
            coupon_den += principal

        maturity = v["maturity_date"]
        if not isinstance(maturity, date):
            continue
        days = (maturity - as_of_date).days
        if days < 0:
            # Already matured relative to as-of; not a refinancing risk.
            continue

        years = days / _DAYS_PER_YEAR
        wam_num += principal * years
        wam_den += principal

        if days <= _DAYS_PER_YEAR:
            debt_1yr += principal
        if days <= 2 * _DAYS_PER_YEAR:
            debt_2yr += principal
        if days <= 3 * _DAYS_PER_YEAR:
            debt_3yr += principal

        seniority = v["seniority_type"] or v["instrument_type"] or "UNCLASSIFIED"
        buckets[maturity.year][seniority] += principal

    pct_1yr = (debt_1yr / total_debt) if total_debt else None
    pct_3yr = (debt_3yr / total_debt) if total_debt else None
    wam = (wam_num / wam_den) if wam_den else None
    wac = (coupon_num / coupon_den) if coupon_den else None

    cash_to_1yr = (cash / debt_1yr) if (cash is not None and debt_1yr) else None
    fcf_to_1yr = (
        free_cash_flow / debt_1yr
        if (free_cash_flow is not None and debt_1yr)
        else None
    )

    maturity_wall = bool(pct_1yr is not None and pct_1yr > _MATURITY_WALL_PCT)
    near_term_stress = bool(
        (pct_1yr is not None and pct_1yr > _NEAR_TERM_STRESS_PCT)
        or (cash_to_1yr is not None and cash_to_1yr < _CASH_COVERAGE_STRESS)
    )

    bucket_results = [
        MaturityBucketResult(
            year=year,
            total_amount=round(sum(by_sen.values()), 2),
            breakdown={k: round(v, 2) for k, v in by_sen.items()},
        )
        for year, by_sen in sorted(buckets.items())
    ]

    return MaturityProfileResult(
        as_of_date=as_of_date,
        debt_maturing_1yr=round(debt_1yr, 2),
        debt_maturing_2yr=round(debt_2yr, 2),
        debt_maturing_3yr=round(debt_3yr, 2),
        total_debt=round(total_debt, 2),
        pct_debt_maturing_1yr=round(pct_1yr, 4) if pct_1yr is not None else None,
        pct_debt_maturing_3yr=round(pct_3yr, 4) if pct_3yr is not None else None,
        weighted_avg_maturity_years=round(wam, 2) if wam is not None else None,
        weighted_avg_coupon=round(wac, 4) if wac is not None else None,
        cash_to_1yr_maturities=round(cash_to_1yr, 4) if cash_to_1yr is not None else None,
        fcf_to_1yr_maturities=round(fcf_to_1yr, 4) if fcf_to_1yr is not None else None,
        maturity_wall_alert=maturity_wall,
        near_term_stress=near_term_stress,
        buckets=bucket_results,
    )


async def persist_profile(
    session: AsyncSession,
    entity_id: Any,
    result: MaturityProfileResult,
    *,
    filing_id: Any | None = None,
) -> str:
    """Persist a computed profile + buckets for an entity.

    Replaces any existing profile for the same (entity_id, as_of_date) so the
    job is idempotent. Returns ``"inserted"`` or ``"replaced"``.
    """
    import uuid as _uuid

    from src.models.debt_maturity import DebtMaturityProfile, MaturityBucket

    existing = (
        await session.execute(
            select(DebtMaturityProfile).where(
                DebtMaturityProfile.entity_id == entity_id,
                DebtMaturityProfile.as_of_date == result.as_of_date,
            )
        )
    ).scalars().all()

    status = "inserted"
    for prof in existing:
        # Cascade isn't declared on the profile→bucket relationship, so drop
        # buckets explicitly before removing the parent profile.
        old_buckets = (
            await session.execute(
                select(MaturityBucket).where(
                    MaturityBucket.profile_id == prof.profile_id
                )
            )
        ).scalars().all()
        for b in old_buckets:
            await session.delete(b)
        await session.delete(prof)
        status = "replaced"
    if existing:
        await session.flush()

    profile = DebtMaturityProfile(
        profile_id=_uuid.uuid4(),
        entity_id=entity_id,
        as_of_date=result.as_of_date,
        filing_id=filing_id,
        debt_maturing_1yr=result.debt_maturing_1yr,
        debt_maturing_2yr=result.debt_maturing_2yr,
        debt_maturing_3yr=result.debt_maturing_3yr,
        pct_debt_maturing_1yr=result.pct_debt_maturing_1yr,
        pct_debt_maturing_3yr=result.pct_debt_maturing_3yr,
        weighted_avg_maturity_years=result.weighted_avg_maturity_years,
        weighted_avg_coupon=result.weighted_avg_coupon,
        cash_to_1yr_maturities=result.cash_to_1yr_maturities,
        fcf_to_1yr_maturities=result.fcf_to_1yr_maturities,
        maturity_wall_alert=result.maturity_wall_alert,
        near_term_stress=result.near_term_stress,
    )
    session.add(profile)
    await session.flush()

    for bucket in result.buckets:
        session.add(
            MaturityBucket(
                bucket_id=_uuid.uuid4(),
                profile_id=profile.profile_id,
                year=bucket.year,
                total_amount=bucket.total_amount,
                breakdown=bucket.breakdown,
            )
        )
    await session.flush()
    return status


async def compute_and_persist_profiles(
    session: AsyncSession,
    *,
    as_of_date: date | None = None,
    entity_ids: list[Any] | None = None,
) -> dict[str, int]:
    """Compute + persist maturity profiles for every entity that has tranches.

    Returns counts: ``{profiles, buckets, entities, replaced}``.
    """
    from src.models.capital_structure import DebtTranche

    as_of = as_of_date or date.today()
    counts = {"profiles": 0, "buckets": 0, "entities": 0, "replaced": 0}

    # Determine which entities to process.
    if entity_ids is None:
        rows = await session.execute(select(DebtTranche.entity_id).distinct())
        target_ids = [r[0] for r in rows.all()]
    else:
        target_ids = entity_ids

    for entity_id in target_ids:
        tranches = (
            await session.execute(
                select(DebtTranche).where(DebtTranche.entity_id == entity_id)
            )
        ).scalars().all()
        if not tranches:
            continue

        result = compute_maturity_profile(tranches, as_of)
        status = await persist_profile(session, entity_id, result)
        counts["entities"] += 1
        counts["profiles"] += 1
        counts["buckets"] += len(result.buckets)
        if status == "replaced":
            counts["replaced"] += 1
        logger.info(
            "Debt maturity profile for entity %s: %d buckets, WAM=%s, wall_alert=%s",
            entity_id,
            len(result.buckets),
            result.weighted_avg_maturity_years,
            result.maturity_wall_alert,
        )

    return counts
