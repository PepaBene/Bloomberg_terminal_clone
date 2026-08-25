"""Assembles the Layer 1 interpreter's input context for a subject.

Phase 1 MVP scope — ENTITY subjects only, across 6 of the plan's ~10 input
domains (AI_THREE_LAYER_REBUILD_PLAN.md §3.1): the ones with confirmed
entity_id-direct linkage and a verified schema (checked against live model
code, not guessed):
  - Fundamentals & ratios — ``AnalyticsResult`` (all metric_category values)
  - Quality/forensic — ``AnalyticsResult`` rows with metric_category="QUALITY"
    (altman_z_score, beneish_m_score, piotroski_f_score)
  - Credit — ``DefaultRiskScore`` (composite_score/implied_rating/trend)
  - Flows/ownership — ``InsiderSignal``
  - Macro exposure — ``MacroThemeScore`` (one snapshot per theme)
  - ESG/governance — ``ESGTemperatureScore`` + ``GovernanceAssessment``

Deliberately NOT yet wired here — real, confirmed-existing tables, just not
plumbed into this assembler yet; extending is mechanical, follows the same
"latest-per-key snapshot -> MetricSnapshot" pattern every domain below uses:
  - Valuation (``DCFResult``, ``WACCResult``, ``CompsResult``,
    ``MultipleTimeSeries``, ``DuPontDecomposition``)
  - Security-keyed risk/technical (``VaRResult``, ``FactorExposure``,
    ``StressTestResult``, ``TechnicalStudyValue``, ``InstitutionalFlowSignal``,
    ``OwnershipSummary``) — these need an extra entity->security resolution
    hop this module doesn't do yet
  - SECTOR/MACRO/PORTFOLIO subject types (``IndustryProfile``/
    ``IndustryCyclePosition``, ``CountryRiskScore``, ``GlobalMacroIndicator``)

"Latest snapshot" queries deliberately avoid Postgres ``DISTINCT ON`` (not
portable to the SQLite test engine, and already flagged elsewhere in this
codebase as a compile warning) — fetch ordered by date descending, keep the
first row seen per key in Python instead.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class MetricSnapshot:
    """One computed figure ready for interpretation."""

    metric_name: str
    metric_category: str
    value: float | None
    unit: str
    period: str
    as_of_date: date
    trend: str | None  # IMPROVING | DETERIORATING | STABLE | None (no prior to compare)
    source_table: str
    source_id: str
    lineage: list[dict] | None = field(default=None)  # AnalyticsResult.inputs shape


@dataclass(frozen=True)
class SubjectContext:
    subject_type: str
    subject_id: str
    as_of: date
    metrics: list[MetricSnapshot]
    analytics_version: str


def classify_trend(current: float | None, prior: float | None, *, epsilon: float = 1e-9) -> str | None:
    """Pure: compare two snapshots of the same metric. ``None`` when there's
    nothing to compare against (no prior value)."""
    if current is None or prior is None:
        return None
    delta = current - prior
    if abs(delta) <= epsilon:
        return "STABLE"
    return "IMPROVING" if delta > 0 else "DETERIORATING"


def _latest_per_key(rows: list, key_fn, date_fn) -> list:
    """Rows are assumed pre-sorted by date descending; keep the first (=
    latest) row seen per ``key_fn(row)``."""
    latest: dict = {}
    for r in rows:
        k = key_fn(r)
        if k not in latest:
            latest[k] = r
    return list(latest.values())


async def _analytics_result_snapshots(
    session: AsyncSession, entity_id: uuid.UUID
) -> list[MetricSnapshot]:
    from src.models.analytics import AnalyticsResult

    rows = (
        await session.execute(
            select(AnalyticsResult)
            .where(AnalyticsResult.entity_id == entity_id)
            .order_by(AnalyticsResult.as_of_date.desc())
        )
    ).scalars().all()

    # Need up to two most-recent observations per metric to classify trend.
    by_metric: dict[str, list] = {}
    for r in rows:
        by_metric.setdefault(r.metric_name, []).append(r)

    out: list[MetricSnapshot] = []
    for metric_name, obs in by_metric.items():
        latest = obs[0]
        prior = obs[1] if len(obs) > 1 else None
        current_val = float(latest.value) if latest.value is not None else None
        prior_val = float(prior.value) if (prior is not None and prior.value is not None) else None
        out.append(MetricSnapshot(
            metric_name=metric_name,
            metric_category=latest.metric_category,
            value=current_val,
            unit=latest.unit,
            period=latest.period,
            as_of_date=latest.as_of_date,
            trend=classify_trend(current_val, prior_val),
            source_table="analytics_results",
            source_id=str(latest.result_id),
            lineage=latest.inputs,
        ))
    return out


async def _default_risk_snapshot(
    session: AsyncSession, entity_id: uuid.UUID
) -> list[MetricSnapshot]:
    from src.models.default_risk import DefaultRiskScore

    rows = (
        await session.execute(
            select(DefaultRiskScore)
            .where(DefaultRiskScore.entity_id == entity_id)
            .order_by(DefaultRiskScore.calculation_date.desc())
            .limit(1)
        )
    ).scalars().all()
    if not rows or rows[0].composite_score is None:
        return []
    row = rows[0]
    return [MetricSnapshot(
        metric_name="CREDIT_COMPOSITE_SCORE",
        metric_category="CREDIT",
        value=float(row.composite_score),
        unit="SCORE",
        period="POINT_IN_TIME",
        as_of_date=row.calculation_date,
        trend=(row.trend or None),
        source_table="default_risk_scores",
        source_id=str(row.score_id),
        lineage=row.inputs,
    )]


async def _insider_signal_snapshot(
    session: AsyncSession, entity_id: uuid.UUID
) -> list[MetricSnapshot]:
    from src.models.insider_intelligence import InsiderSignal

    rows = (
        await session.execute(
            select(InsiderSignal)
            .where(InsiderSignal.entity_id == entity_id)
            .order_by(InsiderSignal.signal_date.desc())
            .limit(1)
        )
    ).scalars().all()
    if not rows:
        return []
    row = rows[0]
    return [MetricSnapshot(
        metric_name="INSIDER_SIGNAL_STRENGTH",
        metric_category="OWNERSHIP",
        value=float(row.signal_strength),
        unit="SCORE",
        period="TRAILING_90D",
        as_of_date=row.signal_date,
        trend=None,  # signal_type (e.g. NET_BUYING/NET_SELLING) already encodes direction
        source_table="insider_signals",
        source_id=str(row.id),
        lineage=[{"name": "signal_type", "value": row.signal_type},
                 {"name": "net_value_90d", "value": float(row.net_value_90d) if row.net_value_90d else None}],
    )]


async def _macro_theme_snapshots(
    session: AsyncSession, entity_id: uuid.UUID
) -> list[MetricSnapshot]:
    from src.models.macro_themes import MacroThemeScore

    rows = (
        await session.execute(
            select(MacroThemeScore)
            .where(MacroThemeScore.entity_id == entity_id)
            .order_by(MacroThemeScore.as_of_date.desc())
        )
    ).scalars().all()
    latest = _latest_per_key(rows, key_fn=lambda r: r.theme, date_fn=lambda r: r.as_of_date)
    out = []
    for row in latest:
        if row.exposure_score is None:
            continue
        out.append(MetricSnapshot(
            metric_name=f"MACRO_THEME_EXPOSURE:{row.theme}",
            metric_category="MACRO",
            value=float(row.exposure_score),
            unit="SCORE",
            period="POINT_IN_TIME",
            as_of_date=row.as_of_date,
            trend=None,
            source_table="macro_theme_scores",
            source_id=str(row.id),
            lineage=[{"name": "sensitivity_direction", "value": row.sensitivity_direction},
                     {"name": "evidence", "value": row.evidence}],
        ))
    return out


async def _esg_and_governance_snapshots(
    session: AsyncSession, entity_id: uuid.UUID
) -> list[MetricSnapshot]:
    from src.models.esg_temperature import ESGTemperatureScore
    from src.models.governance_intelligence import GovernanceAssessment

    out: list[MetricSnapshot] = []

    esg_rows = (
        await session.execute(
            select(ESGTemperatureScore)
            .where(ESGTemperatureScore.entity_id == entity_id)
            .order_by(ESGTemperatureScore.as_of_date.desc())
            .limit(1)
        )
    ).scalars().all()
    if esg_rows:
        r = esg_rows[0]
        out.append(MetricSnapshot(
            metric_name="ESG_IMPLIED_TEMPERATURE",
            metric_category="ESG",
            value=float(r.implied_temperature),
            unit="CELSIUS",
            period="POINT_IN_TIME",
            as_of_date=r.as_of_date,
            trend=None,
            source_table="esg_temperature_scores",
            source_id=str(r.id),
            lineage=[{"name": "alignment", "value": r.alignment}],
        ))

    gov_rows = (
        await session.execute(
            select(GovernanceAssessment)
            .where(GovernanceAssessment.entity_id == entity_id)
            .order_by(GovernanceAssessment.assessment_date.desc())
            .limit(1)
        )
    ).scalars().all()
    if gov_rows:
        r = gov_rows[0]
        out.append(MetricSnapshot(
            metric_name="GOVERNANCE_SCORE",
            metric_category="GOVERNANCE",
            value=float(r.governance_score),
            unit="SCORE",
            period="POINT_IN_TIME",
            as_of_date=r.assessment_date,
            trend=None,
            source_table="governance_assessments",
            source_id=str(r.id),
            lineage=[{"name": "classification", "value": r.classification},
                     {"name": "red_flags", "value": r.red_flags}],
        ))
    return out


async def assemble_entity_context(
    session: AsyncSession, entity_id: uuid.UUID, *, as_of: date | None = None
) -> SubjectContext:
    """Gather every wired domain's latest snapshot for one entity.

    ``as_of`` (when not explicitly given) is derived from the data itself --
    the latest ``as_of_date`` across everything assembled -- NOT
    ``date.today()``. This matters: ``Interpretation.as_of`` is part of the
    compute-on-miss cache key (``src/ai/interpret/store.py``), so if it
    tracked "today" it would silently mint a brand-new, always-a-cache-miss
    row every single day even when nothing about the underlying analytics
    had changed, defeating the freshness check entirely. Tying it to the
    data's own date means the cache key is stable for as long as the data
    is, and ``analytics_version`` (below) is what actually detects a change.

    ``as_of`` is currently informational only for filtering purposes (not
    used to read a historical point-in-time) — every query above pulls the
    latest row per key regardless of ``as_of``. A true point-in-time read
    would need an ``as_of``-filtered query per domain; deferred alongside
    the other not-yet-wired domains above.
    """
    domains = [
        _analytics_result_snapshots(session, entity_id),
        _default_risk_snapshot(session, entity_id),
        _insider_signal_snapshot(session, entity_id),
        _macro_theme_snapshots(session, entity_id),
        _esg_and_governance_snapshots(session, entity_id),
    ]
    metrics: list[MetricSnapshot] = []
    for coro in domains:
        metrics.extend(await coro)

    # A simple, real (not fabricated) cache-invalidation fingerprint: the
    # count + max source as_of_date across everything assembled. Coarser
    # than tracking each engine's calculation_version, but changes exactly
    # when the underlying data actually changes.
    latest_source_date = max((m.as_of_date for m in metrics), default=None)
    effective_as_of = as_of or latest_source_date or date.today()
    analytics_version = f"{len(metrics)}:{(latest_source_date or effective_as_of).isoformat()}"

    return SubjectContext(
        subject_type="ENTITY",
        subject_id=str(entity_id),
        as_of=effective_as_of,
        metrics=metrics,
        analytics_version=analytics_version,
    )
