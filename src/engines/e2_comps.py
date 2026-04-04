"""E2 Comparable Company Analysis Engine.

Uses GICS-based peer groups (via PeerService) to compare a subject
security's valuation multiples against its peer cohort.  For each
multiple the engine computes distribution statistics (mean, median,
quartiles, std), a percentile rank for the subject, a premium/discount
versus the peer median, and an implied share price derived from the
peer median multiple applied to the subject's own fundamentals.

The composite implied price is the equal-weighted average of all
non-None per-multiple implied prices.  All results are persisted to the
CompsResult table and returned as composable EngineOutput metrics.

Part of Pillar 2 analytics — engine_id "E2", metric_category "VALUATION".
"""

from __future__ import annotations

import logging
import statistics
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.engines.base import BaseEngine, EngineOutput, make_input, safe_divide
from src.engines.peer_service import PeerService, PeerGroup
from src.models.analytics import AnalyticsResult, CompsResult
from src.models.security import EODPrice, EquityDetails, Security

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MULTIPLES: list[str] = [
    "pe_trailing",
    "ev_ebitda",
    "ev_sales",
    "pb",
    "dividend_yield",
]

# Maps a multiple name to the AnalyticsResult metric_name for the
# denominator that converts it into an implied price.
# Format: (denominator_metric, needs_ev_bridge)
#   - needs_ev_bridge=True  → implied equity = peer_median * subj_denom − net_debt
#   - needs_ev_bridge=False → implied price = peer_median * subj_denom_per_share
# [Bug 30 fix] Aligned metric names with actual E1 TTM engine output.
# Original names like "eps_diluted" don't match E1 output "ttm_diluted_eps".
_MULTIPLE_DENOM_MAP: dict[str, tuple[str, bool]] = {
    "pe_trailing": ("ttm_diluted_eps", False),
    "ev_ebitda": ("ttm_ebitda", True),
    "ev_sales": ("ttm_total_revenue", True),
    "pb": ("ttm_bvps", False),
    "dividend_yield": ("ttm_dividends_per_share", False),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _percentile_rank(value: float, population: list[float]) -> int:
    """Percentile of *value* within *population* (inclusive count)."""
    if not population:
        return 0
    return int(sum(1 for v in population if v <= value) / len(population) * 100)


def _quartiles(vals: list[float]) -> tuple[float, float]:
    """Return (Q1, Q3) for a sorted list of values."""
    n = len(vals)
    if n < 4:
        return (min(vals), max(vals))
    sv = sorted(vals)
    q1_idx = n // 4
    q3_idx = (3 * n) // 4
    return (sv[q1_idx], sv[q3_idx])


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class CompsEngine(BaseEngine):
    """Comparable Company Analysis engine (E2).

    Computes for each valuation multiple:
    - Peer distribution statistics (mean, median, min, max, q1, q3, std)
    - Subject percentile rank within the peer distribution
    - Premium/discount of the subject vs the peer median
    - Implied share price from the peer median multiple

    Aggregate outputs:
    - Composite implied price (equal-weighted average of per-multiple
      implied prices)
    - Upside/downside vs current market price
    - Peer count

    Edge cases:
    - < 3 peers: quality flag INSUFFICIENT_PEERS, computation continues
    - Subject multiple is None: that multiple is skipped
    - All peers have None for a multiple: that multiple is skipped
    - Negative denominator (e.g. negative earnings): implied_price = None
    """

    engine_id = "E2"
    engine_name = "Comparable Analysis"
    engine_version = "1.0.0"

    async def compute(
        self,
        session: AsyncSession,
        security_id: UUID,
        **kwargs: Any,
    ) -> list[EngineOutput]:
        peer_ids: list[UUID] | None = kwargs.get("peer_ids")
        multiples: list[str] | None = kwargs.get("multiples")

        # ------------------------------------------------------------------
        # 1. Resolve security -> entity
        # ------------------------------------------------------------------
        sec_result = await session.execute(
            select(Security).where(Security.security_id == security_id)
        )
        security = sec_result.scalar_one_or_none()
        if security is None or security.issuer_entity_id is None:
            logger.warning("Comps: security %s not found or has no issuer", security_id)
            return []

        entity_id: UUID = security.issuer_entity_id
        today = date.today()

        # ------------------------------------------------------------------
        # 2. Get peer group
        # ------------------------------------------------------------------
        peer_svc = PeerService()
        if peer_ids is not None:
            # Caller supplied explicit peer list — wrap into a PeerGroup
            peer_group = await peer_svc.get_peers(session, security_id)
            # Override with explicit ids
            peer_group.peers = [
                p for p in peer_group.peers if p.security_id in peer_ids
            ]
            if not peer_group.peers:
                # [Bug 29 fix] Respect caller intent: if none of the specified
                # peer_ids are valid, raise rather than silently falling back
                logger.warning(
                    "Comps: none of the %d specified peer_ids matched valid peers for %s",
                    len(peer_ids), security_id,
                )
                raise ValueError(
                    f"None of the specified {len(peer_ids)} peer_ids are valid "
                    f"peers for security {security_id}"
                )
        else:
            peer_group = await peer_svc.get_peers(session, security_id)

        peer_security_ids = [p.security_id for p in peer_group.peers]
        peer_count = len(peer_security_ids)

        quality_flag = "COMPLETE"
        if peer_count < 3:
            quality_flag = "INSUFFICIENT_PEERS"
            logger.info(
                "Comps: only %d peers for %s — flagging INSUFFICIENT_PEERS",
                peer_count, security_id,
            )

        # ------------------------------------------------------------------
        # 3. Determine multiples to analyse
        # ------------------------------------------------------------------
        if multiples is None:
            multiples = list(DEFAULT_MULTIPLES)

        # ------------------------------------------------------------------
        # 4. Load subject values for each multiple
        # ------------------------------------------------------------------
        subject_multiples = await self._latest_values(
            session, security_id, multiples,
        )

        # ------------------------------------------------------------------
        # 5. Load peer values for each multiple
        # ------------------------------------------------------------------
        peer_values_map = await self._bulk_peer_values(
            session, peer_security_ids, multiples,
        )

        # ------------------------------------------------------------------
        # 6. Load subject denominator values for implied price calc
        # ------------------------------------------------------------------
        denom_metrics = [
            _MULTIPLE_DENOM_MAP[m][0]
            for m in multiples
            if m in _MULTIPLE_DENOM_MAP
        ]
        subject_denoms = await self._latest_values(
            session, security_id, denom_metrics,
        )

        # Net debt (for EV-based multiples)
        net_debt = await self._latest_metric(
            session, security_id, "net_debt",
        )

        # Shares outstanding
        shares = await self._get_shares(session, security_id, entity_id)

        # Current price
        current_price = await self._latest_price(session, security_id)

        # ------------------------------------------------------------------
        # 7. Per-multiple analysis
        # ------------------------------------------------------------------
        outputs: list[EngineOutput] = []
        implied_prices: dict[str, float | None] = {}
        multiples_comparison: dict[str, dict] = {}

        for mult_name in multiples:
            subj_val = subject_multiples.get(mult_name)
            peer_vals = peer_values_map.get(mult_name, [])

            if not peer_vals:
                # No peer data for this multiple — skip
                implied_prices[mult_name] = None
                continue

            # Distribution stats
            p_mean = statistics.mean(peer_vals)
            p_median = statistics.median(peer_vals)
            p_min = min(peer_vals)
            p_max = max(peer_vals)
            p_std = statistics.stdev(peer_vals) if len(peer_vals) >= 2 else 0.0
            p_q1, p_q3 = _quartiles(peer_vals)

            # Percentile rank
            pct: int | None = None
            if subj_val is not None:
                pct = _percentile_rank(subj_val, peer_vals + [subj_val])

            # Premium / discount
            prem_disc: float | None = None
            if subj_val is not None and p_median != 0:
                prem_disc = (subj_val - p_median) / abs(p_median)

            # Implied price
            imp_price = self._compute_implied_price(
                mult_name, p_median, subject_denoms, net_debt, shares,
            )
            implied_prices[mult_name] = imp_price

            # Store comparison data for CompsResult persistence
            multiples_comparison[mult_name] = {
                "subject_value": subj_val,
                "peer_mean": p_mean,
                "peer_median": p_median,
                "peer_min": p_min,
                "peer_max": p_max,
                "peer_q1": p_q1,
                "peer_q3": p_q3,
                "peer_std": p_std,
                "peer_count": len(peer_vals),
                "percentile": pct,
                "premium_discount": prem_disc,
                "implied_price": imp_price,
            }

            # --- Emit EngineOutput metrics for this multiple ---

            # Implied price
            outputs.append(self._o(
                security_id, entity_id, today,
                f"comps_{mult_name}_implied", imp_price, "CURRENCY",
                quality_flag,
                [
                    make_input("peer_median", "comps_engine", p_median),
                    make_input("multiple", "config", None, period=mult_name),
                ],
            ))

            # Percentile rank
            outputs.append(self._o(
                security_id, entity_id, today,
                f"comps_{mult_name}_percentile",
                float(pct) if pct is not None else None,
                "SCORE", quality_flag,
                [
                    make_input("subject_value", "analytics_results", subj_val),
                    make_input("peer_count", "comps_engine", float(len(peer_vals))),
                ],
            ))

        # ------------------------------------------------------------------
        # 8. Composite implied price
        # ------------------------------------------------------------------
        valid_implied = [v for v in implied_prices.values() if v is not None]
        composite_implied: float | None = None
        if valid_implied:
            composite_implied = statistics.mean(valid_implied)

        outputs.append(self._o(
            security_id, entity_id, today,
            "comps_composite_implied_price", composite_implied, "CURRENCY",
            quality_flag,
            [make_input(f"implied_{k}", "comps_engine", v)
             for k, v in implied_prices.items()],
        ))

        # ------------------------------------------------------------------
        # 9. Upside / downside
        # ------------------------------------------------------------------
        upside_downside: float | None = None
        if composite_implied is not None and current_price is not None and current_price > 0:
            upside_downside = (composite_implied - current_price) / current_price

        outputs.append(self._o(
            security_id, entity_id, today,
            "comps_upside_downside", upside_downside, "PERCENT",
            quality_flag,
            [
                make_input("composite_implied", "comps_engine", composite_implied),
                make_input("current_price", "eod_prices", current_price),
            ],
        ))

        # ------------------------------------------------------------------
        # 10. Peer count
        # ------------------------------------------------------------------
        outputs.append(self._o(
            security_id, entity_id, today,
            "comps_peer_count", float(peer_count), "SCORE",
            quality_flag,
            [make_input("peer_count", "peer_service", float(peer_count))],
        ))

        # ------------------------------------------------------------------
        # 11. Persist CompsResult
        # ------------------------------------------------------------------
        comps_row = CompsResult(
            security_id=security_id,
            calculation_date=today,
            peer_security_ids=[str(pid) for pid in peer_security_ids],
            peer_count=peer_count,
            peer_selection_method=peer_group.method,
            multiples_comparison=multiples_comparison,
            primary_multiple=self._select_primary_multiple(multiples_comparison),
            composite_implied_price=composite_implied,
            current_price=current_price,
            data_quality=quality_flag,
        )
        # [Bug 31 fix] Use merge() for upsert semantics so re-running the
        # batch on the same day doesn't raise IntegrityError.
        await session.merge(comps_row)

        logger.info(
            "Comps: computed %d metrics for security %s — "
            "composite_implied=%.2f, peers=%d (quality=%s)",
            len(outputs), security_id,
            composite_implied if composite_implied is not None else 0.0,
            peer_count, quality_flag,
        )
        return outputs

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _o(
        security_id: UUID,
        entity_id: UUID,
        as_of: date,
        metric_name: str,
        value: float | None,
        unit: str,
        data_quality: str,
        inputs: list[dict],
    ) -> EngineOutput:
        """Shorthand factory for a Comps EngineOutput."""
        return EngineOutput(
            security_id=security_id,
            entity_id=entity_id,
            engine_id="E2",
            metric_name=metric_name,
            metric_category="VALUATION",
            value=value,
            unit=unit,
            period="LATEST",
            period_end_date=as_of,
            as_of_date=as_of,
            data_quality=data_quality,
            inputs=inputs,
        )

    @staticmethod
    def _compute_implied_price(
        multiple_name: str,
        peer_median: float,
        subject_denoms: dict[str, float],
        net_debt: float | None,
        shares: float | None,
    ) -> float | None:
        """Derive implied price from a peer-median multiple.

        For P/E, P/B, dividend_yield:
            implied = peer_median × subject_denominator_per_share

        For EV-based (EV/EBITDA, EV/Sales):
            implied = (peer_median × subject_denom_per_share × shares − net_debt) / shares

        Returns None when the denominator is negative or missing.
        """
        if multiple_name not in _MULTIPLE_DENOM_MAP:
            return None

        denom_metric, needs_ev = _MULTIPLE_DENOM_MAP[multiple_name]
        denom_val = subject_denoms.get(denom_metric)
        if denom_val is None or denom_val <= 0:
            return None
        if peer_median is None or peer_median <= 0:
            return None

        if multiple_name == "dividend_yield":
            # dividend_yield = DPS / Price  →  implied_price = DPS / peer_median_yield
            if peer_median == 0:
                return None
            return denom_val / peer_median

        if not needs_ev:
            # Price-based multiple: implied = median_multiple × per-share denom
            return peer_median * denom_val

        # EV-based multiple
        if shares is None or shares <= 0:
            return None
        # EV = multiple × denom_per_share × shares
        implied_ev = peer_median * denom_val * shares
        debt = net_debt if net_debt is not None else 0.0
        implied_equity = implied_ev - debt
        if implied_equity <= 0:
            return None
        return implied_equity / shares

    @staticmethod
    def _select_primary_multiple(
        comparisons: dict[str, dict],
    ) -> str | None:
        """Choose the primary multiple as the one with the most peer data."""
        if not comparisons:
            return None
        return max(
            comparisons.keys(),
            key=lambda k: comparisons[k].get("peer_count", 0),
        )

    async def _latest_values(
        self,
        session: AsyncSession,
        security_id: UUID,
        metrics: list[str],
    ) -> dict[str, float]:
        """Most recent non-null value per metric from AnalyticsResult."""
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

    async def _bulk_peer_values(
        self,
        session: AsyncSession,
        peer_ids: list[UUID],
        metrics: list[str],
    ) -> dict[str, list[float]]:
        """Fetch latest metric values for all peers, grouped by metric."""
        result_map: dict[str, list[float]] = {m: [] for m in metrics}
        if not peer_ids or not metrics:
            return result_map

        rows = (await session.execute(
            select(
                AnalyticsResult.metric_name,
                AnalyticsResult.value,
            ).where(
                AnalyticsResult.security_id.in_(peer_ids),
                AnalyticsResult.metric_name.in_(metrics),
                AnalyticsResult.value.isnot(None),
            )
        )).all()

        for name, val in rows:
            if name in result_map:
                result_map[name].append(float(val))

        return result_map

    async def _latest_metric(
        self,
        session: AsyncSession,
        security_id: UUID,
        metric_name: str,
    ) -> float | None:
        """Load the latest single metric from AnalyticsResult."""
        stmt = (
            select(AnalyticsResult.value)
            .where(
                AnalyticsResult.security_id == security_id,
                AnalyticsResult.metric_name == metric_name,
                AnalyticsResult.value.isnot(None),
            )
            .order_by(AnalyticsResult.as_of_date.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        val = result.scalar_one_or_none()
        return float(val) if val is not None else None

    async def _get_shares(
        self,
        session: AsyncSession,
        security_id: UUID,
        entity_id: UUID,
    ) -> float | None:
        """Best-effort shares outstanding: EquityDetails first, then AnalyticsResult."""
        eq_result = await session.execute(
            select(EquityDetails.shares_outstanding).where(
                EquityDetails.security_id == security_id,
            )
        )
        shares_val = eq_result.scalar_one_or_none()
        if shares_val is not None and float(shares_val) > 0:
            return float(shares_val)

        # Fallback to TTM diluted shares from analytics
        return await self._latest_metric(
            session, security_id, "ttm_diluted_shares_outstanding",
        )

    async def _latest_price(
        self,
        session: AsyncSession,
        security_id: UUID,
    ) -> float | None:
        """Return the most recent adjusted close price."""
        stmt = (
            select(EODPrice.close_adjusted)
            .where(
                EODPrice.security_id == security_id,
                EODPrice.close_adjusted.isnot(None),
            )
            .order_by(EODPrice.price_date.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        val = result.scalar_one_or_none()
        return float(val) if val is not None else None
