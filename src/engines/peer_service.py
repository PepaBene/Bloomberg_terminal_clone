"""Peer Group Service for Pillar 2 Analytics.

Constructs GICS-based peer groups and computes comparative analytics
(percentile ranks, premium/discount vs median, distribution stats).
Not a BaseEngine subclass -- this is a service that orchestrates
queries and statistics for peer comparison.
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.analytics import AnalyticsResult
from src.models.entity import Entity
from src.models.security import EODPrice, EquityDetails, Security, SecurityIdentifier

logger = logging.getLogger(__name__)

DEFAULT_COMPARISON_METRICS: tuple[str, ...] = (
    "gross_margin", "operating_margin", "net_margin",
    "roe", "roa", "roic",
    "debt_to_equity", "current_ratio", "revenue_yoy",
    "pe_trailing", "ev_ebitda", "pb",
    "dividend_yield", "fcf_margin", "asset_turnover",
)

_GICS_LEVELS: tuple[str, ...] = (
    "GICS_SUB_INDUSTRY", "GICS_INDUSTRY", "GICS_SECTOR",
)

_MCAP_LOWER_FACTOR = 0.2
_MCAP_UPPER_FACTOR = 5.0
_SIMILARITY: dict[str, float] = {
    "sub_industry": 1.0, "industry": 0.6, "sector": 0.3,
}


@dataclass
class PeerMember:
    """A single peer within a PeerGroup."""

    security_id: UUID
    entity_id: UUID
    ticker: str | None
    name: str | None
    gics_sub_industry: str | None
    market_cap: float | None
    similarity_score: float  # 0-1


@dataclass
class PeerGroup:
    """Peer group returned by ``PeerService.get_peers``."""

    subject_security_id: UUID
    subject_ticker: str | None
    method: str
    peers: list[PeerMember]
    generated_at: date = field(default_factory=date.today)
    quality_flag: str = "OK"  # "OK" | "INSUFFICIENT_PEERS"


@dataclass
class MetricComparison:
    """Per-metric comparison stats vs the peer group."""

    metric_name: str
    subject_value: float | None
    peer_mean: float | None
    peer_median: float | None
    peer_min: float | None
    peer_max: float | None
    peer_std: float | None
    percentile: int | None       # 0-100
    premium_discount: float | None  # (subj - median) / |median|


@dataclass
class PeerComparison:
    """Full peer comparison result from ``compare_vs_peers``."""

    subject_security_id: UUID
    peer_group: PeerGroup
    comparisons: list[MetricComparison]
    as_of_date: date = field(default_factory=date.today)


async def _ticker_for(session: AsyncSession, security_id: UUID) -> str | None:
    """Return the TICKER identifier value for *security_id*, or None."""
    return (
        await session.execute(
            select(SecurityIdentifier.identifier_value).where(
                SecurityIdentifier.security_id == security_id,
                SecurityIdentifier.identifier_type == "TICKER",
            )
        )
    ).scalar_one_or_none()


async def _estimate_market_cap(
    session: AsyncSession, security_id: UUID,
) -> float | None:
    """Best-effort market-cap: AnalyticsResult first, then EOD * shares."""
    ar = (
        await session.execute(
            select(AnalyticsResult.value).where(
                AnalyticsResult.security_id == security_id,
                AnalyticsResult.metric_name.ilike("%market_cap%"),
                AnalyticsResult.value.isnot(None),
            ).order_by(AnalyticsResult.as_of_date.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if ar is not None:
        return float(ar)

    shares = (
        await session.execute(
            select(EquityDetails.shares_outstanding).where(
                EquityDetails.security_id == security_id,
            )
        )
    ).scalar_one_or_none()
    if shares is None or shares <= 0:
        return None

    price = (
        await session.execute(
            select(EODPrice.close).where(
                EODPrice.security_id == security_id,
                EODPrice.close.isnot(None),
            ).order_by(EODPrice.price_date.desc()).limit(1)
        )
    ).scalar_one_or_none()
    return float(price) * float(shares) if price is not None else None


def _similarity(subject: Entity, peer: Entity) -> float:
    """Score 0-1 measuring GICS overlap between *subject* and *peer*."""
    if (subject.gics_sub_industry and peer.gics_sub_industry
            and subject.gics_sub_industry == peer.gics_sub_industry):
        return _SIMILARITY["sub_industry"]
    if (subject.gics_industry and peer.gics_industry
            and subject.gics_industry == peer.gics_industry):
        return _SIMILARITY["industry"]
    if (subject.gics_sector and peer.gics_sector
            and subject.gics_sector == peer.gics_sector):
        return _SIMILARITY["sector"]
    return 0.0


def _percentile(value: float, all_values: list[float]) -> int:
    """Percentile of *value* within *all_values* (inclusive count method)."""
    if not all_values:
        return 0
    return int(sum(1 for v in all_values if v <= value) / len(all_values) * 100)


class PeerService:
    """Peer group construction and comparison analytics.

    All public methods are async and take an ``AsyncSession`` first so
    they compose naturally with the rest of the analytics pipeline.
    """

    async def get_peers(
        self,
        session: AsyncSession,
        security_id: UUID,
        method: str = "GICS_SUB_INDUSTRY",
        max_peers: int = 15,
    ) -> PeerGroup:
        """Auto-select peers sharing a GICS classification.

        Filters to active securities within a 0.2x-5x market-cap band,
        ranks by GICS similarity, and returns the top *max_peers*.
        Falls back to broader GICS levels when <3 candidates found.
        Raises ``ValueError`` when the subject cannot be resolved.
        """
        if method not in _GICS_LEVELS:
            raise ValueError(f"method must be one of {_GICS_LEVELS}")

        # Resolve subject security and issuer entity
        sec = (
            await session.execute(
                select(Security).where(Security.security_id == security_id)
            )
        ).scalar_one_or_none()
        if sec is None:
            raise ValueError(f"Security {security_id} not found")
        if sec.issuer_entity_id is None:
            raise ValueError(f"Security {security_id} has no issuer_entity_id")

        entity = (
            await session.execute(
                select(Entity).where(Entity.entity_id == sec.issuer_entity_id)
            )
        ).scalar_one_or_none()
        if entity is None:
            raise ValueError(f"Issuer entity {sec.issuer_entity_id} not found")

        subj_ticker = await _ticker_for(session, security_id)
        subj_mcap = await _estimate_market_cap(session, security_id)

        # Candidate search with GICS fallback
        candidates: list[tuple[Security, Entity]] = []
        for level in _GICS_LEVELS[_GICS_LEVELS.index(method):]:
            candidates = await self._candidates(
                session, entity, security_id, level,
            )
            if len(candidates) >= 3:
                break

        # Filter by market-cap band, compute similarity, build members
        peers: list[PeerMember] = []
        for p_sec, p_ent in candidates:
            p_mcap = await _estimate_market_cap(session, p_sec.security_id)
            if subj_mcap is not None and p_mcap is not None:
                if not (subj_mcap * _MCAP_LOWER_FACTOR
                        <= p_mcap
                        <= subj_mcap * _MCAP_UPPER_FACTOR):
                    continue
            peers.append(PeerMember(
                security_id=p_sec.security_id,
                entity_id=p_ent.entity_id,
                ticker=await _ticker_for(session, p_sec.security_id),
                name=p_ent.legal_name,
                gics_sub_industry=p_ent.gics_sub_industry,
                market_cap=p_mcap,
                similarity_score=_similarity(entity, p_ent),
            ))

        # Rank: highest similarity, then closest market cap
        peers.sort(key=lambda p: (
            -p.similarity_score,
            abs((p.market_cap or 0) - (subj_mcap or 0)),
        ))
        peers = peers[:max_peers]

        return PeerGroup(
            subject_security_id=security_id,
            subject_ticker=subj_ticker,
            method=method,
            peers=peers,
            quality_flag="INSUFFICIENT_PEERS" if len(peers) < 3 else "OK",
        )

    async def compare_vs_peers(
        self,
        session: AsyncSession,
        security_id: UUID,
        metrics: list[str] | None = None,
        peer_group: PeerGroup | None = None,
    ) -> PeerComparison:
        """Compare *security_id* metrics against its peer group.

        Computes peer mean/median/min/max/std, percentile rank, and
        premium/discount vs median for each metric.  Auto-generates
        the peer group and uses the default 15-metric set when the
        corresponding arguments are ``None``.
        """
        if metrics is None:
            metrics = list(DEFAULT_COMPARISON_METRICS)
        if peer_group is None:
            peer_group = await self.get_peers(session, security_id)

        peer_ids = [p.security_id for p in peer_group.peers]
        subj_vals = await self._latest_values(session, security_id, metrics)

        # Bulk-fetch peer metric values
        pv_map: dict[str, list[float]] = {m: [] for m in metrics}
        if peer_ids:
            rows = (await session.execute(
                select(AnalyticsResult.metric_name, AnalyticsResult.value).where(
                    AnalyticsResult.security_id.in_(peer_ids),
                    AnalyticsResult.metric_name.in_(metrics),
                    AnalyticsResult.value.isnot(None),
                )
            )).all()
            for name, val in rows:
                pv_map[name].append(float(val))

        comparisons: list[MetricComparison] = []
        for m in metrics:
            sv = subj_vals.get(m)
            pv = pv_map.get(m, [])
            if not pv:
                comparisons.append(MetricComparison(
                    m, sv, None, None, None, None, None, None, None,
                ))
                continue

            p_med = statistics.median(pv)
            pct = _percentile(sv, pv + [sv]) if sv is not None else None
            pd_ = ((sv - p_med) / abs(p_med)) if (sv is not None and p_med != 0) else None
            comparisons.append(MetricComparison(
                metric_name=m,
                subject_value=sv,
                peer_mean=statistics.mean(pv),
                peer_median=p_med,
                peer_min=min(pv),
                peer_max=max(pv),
                peer_std=statistics.stdev(pv) if len(pv) >= 2 else 0.0,
                percentile=pct,
                premium_discount=pd_,
            ))

        return PeerComparison(
            subject_security_id=security_id,
            peer_group=peer_group,
            comparisons=comparisons,
        )

    async def get_percentile_ranks(
        self,
        session: AsyncSession,
        security_id: UUID,
        metrics: list[str] | None = None,
    ) -> dict[str, int]:
        """Return ``{metric_name: percentile}`` for each computable metric.

        Convenience wrapper around ``compare_vs_peers``; omits metrics
        where no subject value or peer data is available.
        """
        cmp = await self.compare_vs_peers(session, security_id, metrics=metrics)
        return {
            c.metric_name: c.percentile
            for c in cmp.comparisons
            if c.percentile is not None
        }

    # -- internal helpers ------------------------------------------------

    async def _candidates(
        self,
        session: AsyncSession,
        subject_entity: Entity,
        exclude_id: UUID,
        level: str,
    ) -> list[tuple[Security, Entity]]:
        """Active (Security, Entity) pairs at the requested GICS *level*."""
        gf = self._gics_clause(subject_entity, level)
        if gf is None:
            return []
        rows = (await session.execute(
            select(Security, Entity)
            .join(Entity, Security.issuer_entity_id == Entity.entity_id)
            .where(
                Security.security_id != exclude_id,
                Security.status == "ACTIVE",
                Entity.status == "ACTIVE",
                gf,
            )
        )).all()
        return [(s, e) for s, e in rows]

    @staticmethod
    def _gics_clause(entity: Entity, level: str):
        """SQLAlchemy filter clause for the requested GICS level."""
        if level == "GICS_SUB_INDUSTRY" and entity.gics_sub_industry:
            return Entity.gics_sub_industry == entity.gics_sub_industry
        if level == "GICS_INDUSTRY" and entity.gics_industry:
            return Entity.gics_industry == entity.gics_industry
        if level == "GICS_SECTOR" and entity.gics_sector:
            return Entity.gics_sector == entity.gics_sector
        return None

    async def _latest_values(
        self,
        session: AsyncSession,
        security_id: UUID,
        metrics: list[str],
    ) -> dict[str, float]:
        """Most recent non-null value per metric (ROW_NUMBER window)."""
        if not metrics:
            return {}
        ranked = (
            select(
                AnalyticsResult.metric_name,
                AnalyticsResult.value,
                func.row_number().over(
                    partition_by=AnalyticsResult.metric_name,
                    order_by=AnalyticsResult.as_of_date.desc(),
                ).label("rn"),
            ).where(
                AnalyticsResult.security_id == security_id,
                AnalyticsResult.metric_name.in_(metrics),
                AnalyticsResult.value.isnot(None),
            ).subquery()
        )
        rows = (await session.execute(
            select(ranked.c.metric_name, ranked.c.value).where(ranked.c.rn == 1)
        )).all()
        return {name: float(val) for name, val in rows}
