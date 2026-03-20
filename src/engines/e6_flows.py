"""E6 Institutional Flow Analytics Engine.

Computes institutional flow signals for a single security by comparing
consecutive quarterly 13F filing snapshots.  Produces position-change
counts, net flow, buy/sell breadth, tier-weighted conviction, smart-money
(whale-tier) signals, multi-quarter trend detection, short-interest
integration, and squeeze-potential classification.

Part of Pillar 2 analytics -- consumes Pillar 1 ownership data
(InstitutionalHolding, InstitutionProfile, ShortInterest) and produces
composable EngineOutput metrics plus persisted InstitutionalFlowSignal
rows and FlowAlert records.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.engines.base import BaseEngine, EngineOutput, make_input
from src.models.flows import FlowAlert, InstitutionalFlowSignal
from src.models.ownership import InstitutionalHolding, InstitutionProfile, ShortInterest
from src.models.security import Security

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tier weights for conviction scoring
# ---------------------------------------------------------------------------
TIER_WEIGHTS: dict[str, int] = {
    "WHALE": 4,
    "MAJOR": 3,
    "NOTABLE": 2,
    "SMALL": 1,
}

SMART_MONEY_TIERS: set[str] = {"WHALE", "MAJOR"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _f(val: Any) -> float | None:
    """Convert a Decimal/numeric value to float, or None."""
    return float(val) if val is not None else None


def _clamp(value: float, lo: float = -1.0, hi: float = 1.0) -> float:
    """Clamp *value* to [lo, hi]."""
    return max(lo, min(hi, value))


def _build_output(
    security_id: UUID,
    entity_id: UUID,
    metric_name: str,
    value: float | None,
    period_label: str,
    period_end_date: date | None,
    inputs: list[dict],
    *,
    data_quality: str = "COMPLETE",
    unit: str = "RATIO",
) -> EngineOutput:
    """Convenience factory for an E6 EngineOutput."""
    return EngineOutput(
        security_id=security_id,
        entity_id=entity_id,
        engine_id="E6",
        metric_name=metric_name,
        metric_category="INSTITUTIONAL_FLOW",
        value=value,
        unit=unit,
        period=period_label,
        period_end_date=period_end_date,
        data_quality=data_quality,
        inputs=inputs,
    )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class InstitutionalFlowEngine(BaseEngine):
    """E6 Institutional Flow Analytics Engine.

    Analyses consecutive quarterly institutional holdings snapshots to
    compute flow signals, breadth, conviction, smart-money indicators,
    trend detection, short-interest integration, and squeeze potential.

    Persists an ``InstitutionalFlowSignal`` row and emits ``FlowAlert``
    records for notable whale moves, full exits, and large new positions.

    Returns ~16 ``EngineOutput`` metrics for composability with other engines.
    """

    engine_id = "E6"
    engine_name = "Institutional Flows"
    engine_version = "1.0.0"

    async def compute(
        self,
        session: AsyncSession,
        security_id: UUID,
        **kwargs: Any,
    ) -> list[EngineOutput]:
        # ------------------------------------------------------------------
        # 1. Resolve security -> entity_id
        # ------------------------------------------------------------------
        sec_result = await session.execute(
            select(Security).where(Security.security_id == security_id)
        )
        security = sec_result.scalar_one_or_none()
        if security is None or security.issuer_entity_id is None:
            logger.warning("E6: security %s not found or has no issuer", security_id)
            return []

        entity_id: UUID = security.issuer_entity_id

        # ------------------------------------------------------------------
        # 2. Find the 2 most recent distinct report_dates
        # ------------------------------------------------------------------
        dates_stmt = (
            select(InstitutionalHolding.report_date)
            .where(InstitutionalHolding.security_id == security_id)
            .distinct()
            .order_by(desc(InstitutionalHolding.report_date))
            .limit(2)
        )
        dates_result = await session.execute(dates_stmt)
        report_dates: list[date] = [row[0] for row in dates_result.all()]

        # ------------------------------------------------------------------
        # 3. No holdings at all -> INSUFFICIENT_DATA
        # ------------------------------------------------------------------
        if len(report_dates) == 0:
            return [
                _build_output(
                    security_id, entity_id,
                    "inst_data_quality", None,
                    "LATEST", None, [],
                    data_quality="INSUFFICIENT_DATA",
                    unit="CLASSIFICATION",
                ),
            ]

        q2_date = report_dates[0]  # current (most recent) quarter
        q1_date = report_dates[1] if len(report_dates) >= 2 else None

        period_label = f"Q_{q2_date.isoformat()}"

        # ------------------------------------------------------------------
        # 4. Fetch holdings for Q2 (current) and Q1 (prior)
        # ------------------------------------------------------------------
        q2_rows = await self._fetch_holdings(session, security_id, q2_date)
        q1_rows = await self._fetch_holdings(session, security_id, q1_date) if q1_date else {}

        # ------------------------------------------------------------------
        # 4b. Fetch institution profiles for tier info (join)
        # ------------------------------------------------------------------
        all_inst_ids = set(q2_rows.keys()) | set(q1_rows.keys())
        tier_map = await self._fetch_tiers(session, all_inst_ids)

        # ------------------------------------------------------------------
        # SINGLE-DATE PARTIAL PATH
        # ------------------------------------------------------------------
        if q1_date is None:
            return await self._compute_partial(
                session, security_id, entity_id,
                q2_date, q2_rows, tier_map, period_label,
            )

        # ------------------------------------------------------------------
        # 5. Position change detection
        # ------------------------------------------------------------------
        new_positions: list[UUID] = []
        closed_positions: list[UUID] = []
        increased_positions: list[UUID] = []
        decreased_positions: list[UUID] = []
        unchanged_positions: list[UUID] = []

        for inst_id, h2 in q2_rows.items():
            if inst_id not in q1_rows:
                new_positions.append(inst_id)
            else:
                h1 = q1_rows[inst_id]
                shares_change = _f(h2.shares_change) or 0.0
                prior_shares = _f(h1.shares_held) or 0.0
                # Threshold: |shares_change / prior_shares| < 0.05 -> UNCHANGED
                if prior_shares != 0 and abs(shares_change / prior_shares) < 0.05:
                    unchanged_positions.append(inst_id)
                elif shares_change > 0:
                    increased_positions.append(inst_id)
                elif shares_change < 0:
                    decreased_positions.append(inst_id)
                else:
                    unchanged_positions.append(inst_id)

        for inst_id in q1_rows:
            if inst_id not in q2_rows:
                closed_positions.append(inst_id)

        new_count = len(new_positions)
        closed_count = len(closed_positions)
        increased_count = len(increased_positions)
        decreased_count = len(decreased_positions)
        unchanged_count = len(unchanged_positions)
        total_institutions = new_count + closed_count + increased_count + decreased_count + unchanged_count

        # ------------------------------------------------------------------
        # 6. Aggregate metrics
        # ------------------------------------------------------------------
        net_shares_change = sum(
            _f(h.shares_change) or 0.0 for h in q2_rows.values()
        )

        # net_value_change: common + new - closed
        net_value_change = 0.0
        common_ids = set(q2_rows.keys()) & set(q1_rows.keys())
        for inst_id in common_ids:
            mv_q2 = _f(q2_rows[inst_id].market_value) or 0.0
            mv_q1 = _f(q1_rows[inst_id].market_value) or 0.0
            net_value_change += mv_q2 - mv_q1
        for inst_id in new_positions:
            net_value_change += _f(q2_rows[inst_id].market_value) or 0.0
        for inst_id in closed_positions:
            net_value_change -= _f(q1_rows[inst_id].market_value) or 0.0

        buy_sell_ratio = (new_count + increased_count) / max(closed_count + decreased_count, 1)

        breadth_raw = (
            (new_count + increased_count - closed_count - decreased_count)
            / max(total_institutions, 1)
        )
        breadth_score = _clamp(breadth_raw)

        # ------------------------------------------------------------------
        # 7. Conviction scoring (tier-weighted)
        # ------------------------------------------------------------------
        weighted_positive = 0.0
        weighted_all = 0.0

        for inst_id in new_positions + increased_positions:
            tier = tier_map.get(inst_id, "SMALL")
            w = TIER_WEIGHTS.get(tier, 1)
            weighted_positive += w
            weighted_all += w
        for inst_id in closed_positions + decreased_positions:
            tier = tier_map.get(inst_id, "SMALL")
            w = TIER_WEIGHTS.get(tier, 1)
            weighted_all += w
        for inst_id in unchanged_positions:
            tier = tier_map.get(inst_id, "SMALL")
            w = TIER_WEIGHTS.get(tier, 1)
            weighted_all += w

        conviction_score = (weighted_positive / max(weighted_all, 1)) * 100.0

        # ------------------------------------------------------------------
        # 8. Smart money (whale-tier only)
        # ------------------------------------------------------------------
        whale_net_shares = 0.0
        whale_net_value = 0.0
        whale_buyers = 0
        whale_sellers = 0
        total_whales = 0

        for inst_id in q2_rows:
            tier = tier_map.get(inst_id, "SMALL")
            if tier not in SMART_MONEY_TIERS:
                continue
            total_whales += 1
            sc = _f(q2_rows[inst_id].shares_change) or 0.0
            whale_net_shares += sc

            if inst_id in q1_rows:
                mv_q2 = _f(q2_rows[inst_id].market_value) or 0.0
                mv_q1 = _f(q1_rows[inst_id].market_value) or 0.0
                whale_net_value += mv_q2 - mv_q1
            else:
                whale_net_value += _f(q2_rows[inst_id].market_value) or 0.0

            if sc > 0 or inst_id in new_positions:
                whale_buyers += 1
            elif sc < 0:
                whale_sellers += 1

        # Also count whale/major institutions that closed
        for inst_id in closed_positions:
            tier = tier_map.get(inst_id, "SMALL")
            if tier in SMART_MONEY_TIERS:
                total_whales += 1
                whale_sellers += 1
                whale_net_value -= _f(q1_rows[inst_id].market_value) or 0.0

        smart_money_flow = _clamp(
            (whale_buyers - whale_sellers) / max(total_whales, 1)
        )

        # ------------------------------------------------------------------
        # 9. Multi-quarter trend
        # ------------------------------------------------------------------
        flow_trend_3q, flow_trend_4q = await self._compute_trend(
            session, security_id, q2_date,
        )

        # ------------------------------------------------------------------
        # 10. Short interest
        # ------------------------------------------------------------------
        short_pct_float, si_days_to_cover = await self._fetch_short_interest(
            session, security_id, q2_date,
        )

        # ------------------------------------------------------------------
        # 11. Squeeze potential
        # ------------------------------------------------------------------
        squeeze_potential = self._classify_squeeze(
            short_pct_float, flow_trend_4q or flow_trend_3q, breadth_score,
        )

        # ------------------------------------------------------------------
        # 12. Persist InstitutionalFlowSignal
        # ------------------------------------------------------------------
        signal = InstitutionalFlowSignal(
            signal_id=uuid.uuid4(),
            security_id=security_id,
            report_date=q2_date,
            new_positions_count=new_count,
            closed_positions_count=closed_count,
            increased_positions_count=increased_count,
            decreased_positions_count=decreased_count,
            unchanged_positions_count=unchanged_count,
            net_shares_change=net_shares_change,
            net_value_change=net_value_change,
            buy_sell_ratio=buy_sell_ratio,
            breadth_score=breadth_score,
            conviction_score=conviction_score,
            whale_net_shares=whale_net_shares,
            whale_net_value=whale_net_value,
            smart_money_flow=smart_money_flow,
            flow_trend_3q=flow_trend_3q,
            flow_trend_4q=flow_trend_4q,
            short_interest_ratio=short_pct_float,
            days_to_cover=si_days_to_cover,
            squeeze_potential=squeeze_potential,
            data_quality="COMPLETE",
            inputs={
                "q2_date": q2_date.isoformat(),
                "q1_date": q1_date.isoformat() if q1_date else None,
                "total_institutions": total_institutions,
            },
        )
        session.add(signal)

        # ------------------------------------------------------------------
        # 13. Generate alerts
        # ------------------------------------------------------------------
        alerts = await self._generate_alerts(
            session, security_id, entity_id, q2_date,
            q2_rows, q1_rows, tier_map,
            new_positions, closed_positions,
        )
        for alert in alerts:
            session.add(alert)

        # ------------------------------------------------------------------
        # 14. Build EngineOutput list (~16 metrics)
        # ------------------------------------------------------------------
        def _inp(name: str, value: float | None) -> dict:
            return make_input(name=name, source="institutional_holdings", value=value, period=period_label)

        outputs: list[EngineOutput] = []

        outputs.append(_build_output(
            security_id, entity_id,
            "inst_new_positions_count", float(new_count),
            period_label, q2_date, [_inp("new_positions", float(new_count))],
            unit="COUNT",
        ))
        outputs.append(_build_output(
            security_id, entity_id,
            "inst_closed_positions_count", float(closed_count),
            period_label, q2_date, [_inp("closed_positions", float(closed_count))],
            unit="COUNT",
        ))
        outputs.append(_build_output(
            security_id, entity_id,
            "inst_increased_positions_count", float(increased_count),
            period_label, q2_date, [_inp("increased_positions", float(increased_count))],
            unit="COUNT",
        ))
        outputs.append(_build_output(
            security_id, entity_id,
            "inst_decreased_positions_count", float(decreased_count),
            period_label, q2_date, [_inp("decreased_positions", float(decreased_count))],
            unit="COUNT",
        ))
        outputs.append(_build_output(
            security_id, entity_id,
            "inst_unchanged_positions_count", float(unchanged_count),
            period_label, q2_date, [_inp("unchanged_positions", float(unchanged_count))],
            unit="COUNT",
        ))
        outputs.append(_build_output(
            security_id, entity_id,
            "inst_net_shares_change", net_shares_change,
            period_label, q2_date, [_inp("net_shares_change", net_shares_change)],
            unit="SHARES",
        ))
        outputs.append(_build_output(
            security_id, entity_id,
            "inst_net_value_change", net_value_change,
            period_label, q2_date, [_inp("net_value_change", net_value_change)],
            unit="CURRENCY",
        ))
        outputs.append(_build_output(
            security_id, entity_id,
            "inst_buy_sell_ratio", buy_sell_ratio,
            period_label, q2_date, [
                _inp("buyers", float(new_count + increased_count)),
                _inp("sellers", float(closed_count + decreased_count)),
            ],
            unit="RATIO",
        ))
        outputs.append(_build_output(
            security_id, entity_id,
            "inst_breadth_score", breadth_score,
            period_label, q2_date, [_inp("breadth_score", breadth_score)],
            unit="SCORE",
        ))
        outputs.append(_build_output(
            security_id, entity_id,
            "inst_conviction_score", conviction_score,
            period_label, q2_date, [_inp("conviction_score", conviction_score)],
            unit="SCORE",
        ))
        outputs.append(_build_output(
            security_id, entity_id,
            "inst_whale_net_shares", whale_net_shares,
            period_label, q2_date, [_inp("whale_net_shares", whale_net_shares)],
            unit="SHARES",
        ))
        outputs.append(_build_output(
            security_id, entity_id,
            "inst_whale_net_value", whale_net_value,
            period_label, q2_date, [_inp("whale_net_value", whale_net_value)],
            unit="CURRENCY",
        ))
        outputs.append(_build_output(
            security_id, entity_id,
            "inst_smart_money_flow", smart_money_flow,
            period_label, q2_date, [_inp("smart_money_flow", smart_money_flow)],
            unit="SCORE",
        ))
        outputs.append(_build_output(
            security_id, entity_id,
            "inst_flow_trend", None,
            period_label, q2_date, [
                _inp("flow_trend_3q", None),
                _inp("flow_trend_4q", None),
            ],
            unit="CLASSIFICATION",
        ))
        outputs[-1].inputs.append(  # type: ignore[union-attr]
            make_input(name="trend_3q", source="derived", value=None, period=flow_trend_3q or "NEUTRAL")
        )
        outputs[-1].inputs.append(  # type: ignore[union-attr]
            make_input(name="trend_4q", source="derived", value=None, period=flow_trend_4q or "NEUTRAL")
        )

        outputs.append(_build_output(
            security_id, entity_id,
            "inst_short_interest_ratio", short_pct_float,
            period_label, q2_date, [_inp("short_percent_float", short_pct_float)],
            unit="RATIO",
        ))
        outputs.append(_build_output(
            security_id, entity_id,
            "inst_squeeze_potential", None,
            period_label, q2_date, [
                _inp("short_percent_float", short_pct_float),
                _inp("breadth_score", breadth_score),
            ],
            unit="CLASSIFICATION",
        ))
        outputs[-1].inputs.append(  # type: ignore[union-attr]
            make_input(name="squeeze", source="derived", value=None, period=squeeze_potential)
        )

        logger.info(
            "E6: %d metrics for security %s (period %s, %d alerts)",
            len(outputs), security_id, period_label, len(alerts),
        )
        return outputs

    # ======================================================================
    # Private helpers
    # ======================================================================

    async def _fetch_holdings(
        self,
        session: AsyncSession,
        security_id: UUID,
        report_date: date,
    ) -> dict[UUID, InstitutionalHolding]:
        """Return {institution_id: InstitutionalHolding} for a given quarter."""
        stmt = select(InstitutionalHolding).where(
            InstitutionalHolding.security_id == security_id,
            InstitutionalHolding.report_date == report_date,
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()
        return {row.institution_id: row for row in rows}

    async def _fetch_tiers(
        self,
        session: AsyncSession,
        institution_ids: set[UUID],
    ) -> dict[UUID, str]:
        """Return {institution_id: tier} for a set of institutions.

        Missing profiles default to ``"SMALL"``.
        """
        if not institution_ids:
            return {}
        stmt = select(
            InstitutionProfile.institution_id,
            InstitutionProfile.tier,
        ).where(
            InstitutionProfile.institution_id.in_(list(institution_ids))
        )
        result = await session.execute(stmt)
        rows = result.all()
        tier_map: dict[UUID, str] = {
            inst_id: (tier or "SMALL") for inst_id, tier in rows
        }
        # Default missing profiles to SMALL
        for inst_id in institution_ids:
            if inst_id not in tier_map:
                tier_map[inst_id] = "SMALL"
        return tier_map

    async def _compute_trend(
        self,
        session: AsyncSession,
        security_id: UUID,
        current_date: date,
    ) -> tuple[str | None, str | None]:
        """Compute multi-quarter flow trend from net_shares_change across
        consecutive quarter pairs.

        Returns (flow_trend_3q, flow_trend_4q).
        """
        # Fetch last 5 report_dates (need 5 dates to form 4 quarter-pairs)
        dates_stmt = (
            select(InstitutionalHolding.report_date)
            .where(InstitutionalHolding.security_id == security_id)
            .distinct()
            .order_by(desc(InstitutionalHolding.report_date))
            .limit(5)
        )
        dates_result = await session.execute(dates_stmt)
        all_dates: list[date] = [row[0] for row in dates_result.all()]

        if len(all_dates) < 3:
            return (None, None)

        # Compute net_shares_change for each consecutive pair
        # all_dates[0] is most recent, all_dates[1] is prior, etc.
        quarter_changes: list[float] = []
        for i in range(len(all_dates) - 1):
            later_date = all_dates[i]
            earlier_date = all_dates[i + 1]

            stmt = select(
                func.sum(InstitutionalHolding.shares_change)
            ).where(
                InstitutionalHolding.security_id == security_id,
                InstitutionalHolding.report_date == later_date,
            )
            result = await session.execute(stmt)
            net = result.scalar_one_or_none()
            quarter_changes.append(_f(net) or 0.0)

        def _classify_trend(changes: list[float]) -> str:
            """Classify a series of net changes."""
            pos_count = sum(1 for c in changes if c > 0)
            neg_count = sum(1 for c in changes if c < 0)
            if pos_count >= 3:
                return "ACCUMULATION"
            if neg_count >= 3:
                return "DISTRIBUTION"
            return "NEUTRAL"

        trend_3q: str | None = None
        trend_4q: str | None = None

        if len(quarter_changes) >= 3:
            trend_3q = _classify_trend(quarter_changes[:3])
        if len(quarter_changes) >= 4:
            trend_4q = _classify_trend(quarter_changes[:4])

        return (trend_3q, trend_4q)

    async def _fetch_short_interest(
        self,
        session: AsyncSession,
        security_id: UUID,
        report_date: date,
    ) -> tuple[float | None, float | None]:
        """Return (short_percent_float, days_to_cover) for the latest
        settlement_date <= report_date."""
        stmt = (
            select(ShortInterest)
            .where(
                ShortInterest.security_id == security_id,
                ShortInterest.settlement_date <= report_date,
            )
            .order_by(desc(ShortInterest.settlement_date))
            .limit(1)
        )
        result = await session.execute(stmt)
        si = result.scalar_one_or_none()
        if si is None:
            return (None, None)
        return (_f(si.short_percent_float), _f(si.days_to_cover))

    @staticmethod
    def _classify_squeeze(
        short_pct_float: float | None,
        flow_trend: str | None,
        breadth_score: float,
    ) -> str:
        """Classify squeeze potential: HIGH, MODERATE, or LOW."""
        spf = short_pct_float or 0.0
        if spf > 0.20 and flow_trend == "ACCUMULATION":
            return "HIGH"
        if spf > 0.10 and breadth_score > 0:
            return "MODERATE"
        return "LOW"

    async def _generate_alerts(
        self,
        session: AsyncSession,
        security_id: UUID,
        entity_id: UUID,
        report_date: date,
        q2_rows: dict[UUID, InstitutionalHolding],
        q1_rows: dict[UUID, InstitutionalHolding],
        tier_map: dict[UUID, str],
        new_position_ids: list[UUID],
        closed_position_ids: list[UUID],
    ) -> list[FlowAlert]:
        """Generate FlowAlert records for notable events."""
        alerts: list[FlowAlert] = []

        # Fetch institution names for alert headlines
        all_alert_ids = set()
        # Pre-compute candidates
        whale_move_candidates: list[UUID] = []
        full_exit_candidates: list[UUID] = []
        new_whale_candidates: list[UUID] = []

        # WHALE_MOVE: whale/major institution with |pct_outstanding change| > 1%
        for inst_id in set(q2_rows.keys()) & set(q1_rows.keys()):
            tier = tier_map.get(inst_id, "SMALL")
            if tier not in SMART_MONEY_TIERS:
                continue
            pct_q2 = _f(q2_rows[inst_id].percent_of_outstanding) or 0.0
            pct_q1 = _f(q1_rows[inst_id].percent_of_outstanding) or 0.0
            if abs(pct_q2 - pct_q1) > 0.01:
                whale_move_candidates.append(inst_id)
                all_alert_ids.add(inst_id)

        # FULL_EXIT: notable+ institution that closed position, prior MV > 10M
        notable_plus = {"WHALE", "MAJOR", "NOTABLE"}
        for inst_id in closed_position_ids:
            tier = tier_map.get(inst_id, "SMALL")
            if tier not in notable_plus:
                continue
            mv_prior = _f(q1_rows[inst_id].market_value) or 0.0
            if mv_prior > 10_000_000:
                full_exit_candidates.append(inst_id)
                all_alert_ids.add(inst_id)

        # NEW_POSITION: whale/major with new position, MV > 50M
        for inst_id in new_position_ids:
            tier = tier_map.get(inst_id, "SMALL")
            if tier not in SMART_MONEY_TIERS:
                continue
            mv = _f(q2_rows[inst_id].market_value) or 0.0
            if mv > 50_000_000:
                new_whale_candidates.append(inst_id)
                all_alert_ids.add(inst_id)

        # Bulk-fetch institution names
        name_map: dict[UUID, str] = {}
        if all_alert_ids:
            name_stmt = select(
                InstitutionProfile.institution_id,
                InstitutionProfile.institution_name,
            ).where(InstitutionProfile.institution_id.in_(list(all_alert_ids)))
            name_result = await session.execute(name_stmt)
            name_map = {row[0]: row[1] for row in name_result.all()}

        # Build WHALE_MOVE alerts
        for inst_id in whale_move_candidates:
            inst_name = name_map.get(inst_id, "Unknown Institution")
            h2 = q2_rows[inst_id]
            h1 = q1_rows[inst_id]
            shares_change = _f(h2.shares_change) or 0.0
            pct_q2 = _f(h2.percent_of_outstanding) or 0.0
            pct_q1 = _f(h1.percent_of_outstanding) or 0.0
            direction = "increased" if shares_change > 0 else "decreased"

            alerts.append(FlowAlert(
                alert_id=uuid.uuid4(),
                alert_type="WHALE_MOVE",
                security_id=security_id,
                institution_id=inst_id,
                report_date=report_date,
                headline=f"{inst_name} {direction} position by {abs(pct_q2 - pct_q1):.2%} of outstanding",
                shares_involved=abs(shares_change),
                value_involved=abs((_f(h2.market_value) or 0.0) - (_f(h1.market_value) or 0.0)),
                percent_of_outstanding=abs(pct_q2 - pct_q1),
                details={
                    "prior_pct": pct_q1,
                    "current_pct": pct_q2,
                    "direction": direction,
                    "tier": tier_map.get(inst_id, "SMALL"),
                },
                severity="HIGH",
            ))

        # Build FULL_EXIT alerts
        for inst_id in full_exit_candidates:
            inst_name = name_map.get(inst_id, "Unknown Institution")
            h1 = q1_rows[inst_id]
            mv_prior = _f(h1.market_value) or 0.0
            shares_prior = _f(h1.shares_held) or 0.0

            alerts.append(FlowAlert(
                alert_id=uuid.uuid4(),
                alert_type="FULL_EXIT",
                security_id=security_id,
                institution_id=inst_id,
                report_date=report_date,
                headline=f"{inst_name} fully exited position (prior value ${mv_prior:,.0f})",
                shares_involved=shares_prior,
                value_involved=mv_prior,
                percent_of_outstanding=_f(h1.percent_of_outstanding),
                details={
                    "prior_shares": shares_prior,
                    "prior_market_value": mv_prior,
                    "tier": tier_map.get(inst_id, "SMALL"),
                },
                severity="HIGH",
            ))

        # Build NEW_POSITION alerts
        for inst_id in new_whale_candidates:
            inst_name = name_map.get(inst_id, "Unknown Institution")
            h2 = q2_rows[inst_id]
            mv = _f(h2.market_value) or 0.0
            shares = _f(h2.shares_held) or 0.0

            alerts.append(FlowAlert(
                alert_id=uuid.uuid4(),
                alert_type="NEW_POSITION",
                security_id=security_id,
                institution_id=inst_id,
                report_date=report_date,
                headline=f"{inst_name} initiated new position (value ${mv:,.0f})",
                shares_involved=shares,
                value_involved=mv,
                percent_of_outstanding=_f(h2.percent_of_outstanding),
                details={
                    "shares": shares,
                    "market_value": mv,
                    "tier": tier_map.get(inst_id, "SMALL"),
                },
                severity="MEDIUM",
            ))

        return alerts

    async def _compute_partial(
        self,
        session: AsyncSession,
        security_id: UUID,
        entity_id: UUID,
        q2_date: date,
        q2_rows: dict[UUID, InstitutionalHolding],
        tier_map: dict[UUID, str],
        period_label: str,
    ) -> list[EngineOutput]:
        """Compute what we can from a single report_date (no prior quarter).

        Uses is_new_position / is_sold_out flags from holdings data.
        """
        new_count = sum(1 for h in q2_rows.values() if h.is_new_position)
        total_count = len(q2_rows)

        net_shares_change = sum(_f(h.shares_change) or 0.0 for h in q2_rows.values())

        # Short interest
        short_pct_float, si_days_to_cover = await self._fetch_short_interest(
            session, security_id, q2_date,
        )

        # Persist a partial signal
        signal = InstitutionalFlowSignal(
            signal_id=uuid.uuid4(),
            security_id=security_id,
            report_date=q2_date,
            new_positions_count=new_count,
            closed_positions_count=None,
            increased_positions_count=None,
            decreased_positions_count=None,
            unchanged_positions_count=None,
            net_shares_change=net_shares_change,
            net_value_change=None,
            buy_sell_ratio=None,
            breadth_score=None,
            conviction_score=None,
            whale_net_shares=None,
            whale_net_value=None,
            smart_money_flow=None,
            flow_trend_3q=None,
            flow_trend_4q=None,
            short_interest_ratio=short_pct_float,
            days_to_cover=si_days_to_cover,
            squeeze_potential=None,
            data_quality="PARTIAL",
            inputs={
                "q2_date": q2_date.isoformat(),
                "q1_date": None,
                "total_institutions": total_count,
                "note": "single_quarter_only",
            },
        )
        session.add(signal)

        def _inp(name: str, value: float | None) -> dict:
            return make_input(name=name, source="institutional_holdings", value=value, period=period_label)

        outputs: list[EngineOutput] = []
        outputs.append(_build_output(
            security_id, entity_id,
            "inst_new_positions_count", float(new_count),
            period_label, q2_date, [_inp("new_positions", float(new_count))],
            data_quality="PARTIAL", unit="COUNT",
        ))
        outputs.append(_build_output(
            security_id, entity_id,
            "inst_total_institutions", float(total_count),
            period_label, q2_date, [_inp("total_institutions", float(total_count))],
            data_quality="PARTIAL", unit="COUNT",
        ))
        outputs.append(_build_output(
            security_id, entity_id,
            "inst_net_shares_change", net_shares_change,
            period_label, q2_date, [_inp("net_shares_change", net_shares_change)],
            data_quality="PARTIAL", unit="SHARES",
        ))
        outputs.append(_build_output(
            security_id, entity_id,
            "inst_short_interest_ratio", short_pct_float,
            period_label, q2_date, [_inp("short_percent_float", short_pct_float)],
            data_quality="PARTIAL", unit="RATIO",
        ))

        logger.info(
            "E6: %d PARTIAL metrics for security %s (single quarter %s)",
            len(outputs), security_id, period_label,
        )
        return outputs
