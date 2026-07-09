"""E2 Football Field (Valuation Summary) Engine.

Aggregates valuation ranges from every available methodology — DCF,
comps, historical multiples, 52-week trading range, and analyst
consensus — into a single summary view that can be rendered as a
football field chart.

For each methodology the engine produces a low / mid / high triplet
(or a single value where ranges don't apply), plus a current-price
reference line and a consensus view classification.

Part of Pillar 2 analytics — engine_id "E2", metric_category "VALUATION".
"""

from __future__ import annotations

import logging
import statistics
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.engines.base import BaseEngine, EngineOutput, make_input
from src.models.analytics import AnalyticsResult, CompsResult, DCFResult, MultipleTimeSeries
from src.models.estimates import ConsensusEstimate
from src.models.security import EODPrice, Security

logger = logging.getLogger(__name__)

# Threshold for UNDERVALUED / OVERVALUED classification (±10%)
_VALUATION_THRESHOLD = 0.10


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class FootballFieldEngine(BaseEngine):
    """Football Field valuation summary engine (E2).

    Gathers implied-value ranges from:
    - **DCF**: low / mid / high from sensitivity grid corners
    - **Comps**: q1 / median / q3 implied prices from peer multiples
    - **Historical multiples**: implied value at own 1Y and 3Y average
      multiples applied to current fundamentals
    - **52-week range**: high and low traded prices
    - **Analyst consensus**: target price from ConsensusEstimate

    Produces a ``football_consensus_view`` classification:
        UNDERVALUED   — median of all midpoints > current price + threshold
        OVERVALUED    — median of all midpoints < current price − threshold
        FAIRLY_VALUED — otherwise

    Edge cases:
    - No DCF result: DCF bars skipped, flag NO_DCF_DATA
    - No comps: comps bars skipped
    - No analyst targets: football_analyst_target = None
    - Only one methodology: still returns available data
    """

    engine_id = "E2"
    engine_name = "Football Field"
    engine_version = "1.0.0"

    async def compute(
        self,
        session: AsyncSession,
        security_id: UUID,
        **kwargs: Any,
    ) -> list[EngineOutput]:
        # ------------------------------------------------------------------
        # 1. Resolve security -> entity
        # ------------------------------------------------------------------
        sec_result = await session.execute(
            select(Security).where(Security.security_id == security_id)
        )
        security = sec_result.scalar_one_or_none()
        if security is None or security.issuer_entity_id is None:
            logger.warning("FootballField: security %s not found or no issuer", security_id)
            return []

        entity_id: UUID = security.issuer_entity_id
        today = date.today()
        outputs: list[EngineOutput] = []
        flags: list[str] = []
        midpoints: list[float] = []

        # ------------------------------------------------------------------
        # 2. DCF
        # ------------------------------------------------------------------
        dcf_low, dcf_mid, dcf_high = await self._load_dcf(session, security_id)
        if dcf_mid is None:
            flags.append("NO_DCF_DATA")
        else:
            if dcf_mid is not None:
                midpoints.append(dcf_mid)

        outputs.append(self._o(security_id, entity_id, today, "football_dcf_low", dcf_low, "CURRENCY", [
            make_input("dcf_implied_price", "dcf_results", dcf_low),
        ]))
        outputs.append(self._o(security_id, entity_id, today, "football_dcf_mid", dcf_mid, "CURRENCY", [
            make_input("dcf_implied_price", "dcf_results", dcf_mid),
        ]))
        outputs.append(self._o(security_id, entity_id, today, "football_dcf_high", dcf_high, "CURRENCY", [
            make_input("dcf_implied_price", "dcf_results", dcf_high),
        ]))

        # ------------------------------------------------------------------
        # 3. Comps
        # ------------------------------------------------------------------
        comps_low, comps_mid, comps_high = await self._load_comps(session, security_id)
        if comps_mid is not None:
            midpoints.append(comps_mid)

        outputs.append(self._o(security_id, entity_id, today, "football_comps_low", comps_low, "CURRENCY", [
            make_input("comps_q1", "comps_results", comps_low),
        ]))
        outputs.append(self._o(security_id, entity_id, today, "football_comps_mid", comps_mid, "CURRENCY", [
            make_input("comps_median", "comps_results", comps_mid),
        ]))
        outputs.append(self._o(security_id, entity_id, today, "football_comps_high", comps_high, "CURRENCY", [
            make_input("comps_q3", "comps_results", comps_high),
        ]))

        # ------------------------------------------------------------------
        # 4. Historical multiples
        # ------------------------------------------------------------------
        hist_low, hist_mid, hist_high = await self._load_historical(
            session, security_id,
        )
        if hist_mid is not None:
            midpoints.append(hist_mid)

        outputs.append(self._o(security_id, entity_id, today, "football_historical_low", hist_low, "CURRENCY", [
            make_input("historical_avg_1y", "multiple_time_series", hist_low),
        ]))
        outputs.append(self._o(security_id, entity_id, today, "football_historical_mid", hist_mid, "CURRENCY", [
            make_input("historical_avg_blend", "multiple_time_series", hist_mid),
        ]))
        outputs.append(self._o(security_id, entity_id, today, "football_historical_high", hist_high, "CURRENCY", [
            make_input("historical_avg_3y", "multiple_time_series", hist_high),
        ]))

        # ------------------------------------------------------------------
        # 5. 52-week range
        # ------------------------------------------------------------------
        w52_low, w52_high = await self._load_52w_range(session, security_id)
        if w52_low is not None and w52_high is not None:
            midpoints.append((w52_low + w52_high) / 2.0)

        outputs.append(self._o(security_id, entity_id, today, "football_52w_low", w52_low, "CURRENCY", [
            make_input("52w_low", "eod_prices", w52_low),
        ]))
        outputs.append(self._o(security_id, entity_id, today, "football_52w_high", w52_high, "CURRENCY", [
            make_input("52w_high", "eod_prices", w52_high),
        ]))

        # ------------------------------------------------------------------
        # 6. Analyst target
        # ------------------------------------------------------------------
        analyst_target = await self._load_analyst_target(session, security_id)
        if analyst_target is not None:
            midpoints.append(analyst_target)

        outputs.append(self._o(security_id, entity_id, today, "football_analyst_target", analyst_target, "CURRENCY", [
            make_input("analyst_target_price", "consensus_estimates", analyst_target),
        ]))

        # ------------------------------------------------------------------
        # 7. Current price
        # ------------------------------------------------------------------
        current_price = await self._latest_price(session, security_id)
        outputs.append(self._o(security_id, entity_id, today, "football_current_price", current_price, "CURRENCY", [
            make_input("current_price", "eod_prices", current_price),
        ]))

        # ------------------------------------------------------------------
        # 8. Consensus view classification
        # ------------------------------------------------------------------
        consensus_view = self._classify(midpoints, current_price)
        outputs.append(self._o(
            security_id, entity_id, today,
            "football_consensus_view",
            consensus_view,  # [Bug 35 fix] stored in value instead of data_quality
            "CLASSIFICATION",
            [
                make_input("midpoint_count", "computed", float(len(midpoints))),
                make_input("current_price", "eod_prices", current_price),
            ],
            data_quality="COMPLETE" if consensus_view != "INSUFFICIENT_DATA" else "INSUFFICIENT_DATA",
        ))

        # Determine overall quality
        overall_quality = "COMPLETE"
        if flags:
            overall_quality = ",".join(flags)

        # Stamp quality on all outputs (except consensus_view which carries its own)
        for o in outputs:
            if o.metric_name != "football_consensus_view":
                o.data_quality = overall_quality

        logger.info(
            "FootballField: computed %d metrics for security %s — "
            "consensus=%s, midpoints=%d (flags=%s)",
            len(outputs), security_id,
            consensus_view, len(midpoints),
            overall_quality,
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
        inputs: list[dict],
        *,
        data_quality: str = "COMPLETE",
    ) -> EngineOutput:
        """Shorthand factory for a FootballField EngineOutput."""
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
    def _classify(
        midpoints: list[float],
        current_price: float | None,
    ) -> str:
        """Derive consensus classification from methodology midpoints."""
        if not midpoints or current_price is None or current_price <= 0:
            return "INSUFFICIENT_DATA"

        median_mid = statistics.median(midpoints)
        pct_diff = (median_mid - current_price) / current_price

        if pct_diff > _VALUATION_THRESHOLD:
            return "UNDERVALUED"
        if pct_diff < -_VALUATION_THRESHOLD:
            return "OVERVALUED"
        return "FAIRLY_VALUED"

    # --- Data loaders ---------------------------------------------------

    async def _load_dcf(
        self,
        session: AsyncSession,
        security_id: UUID,
    ) -> tuple[float | None, float | None, float | None]:
        """Load DCF implied price and derive low/mid/high from sensitivity grid."""
        stmt = (
            select(DCFResult)
            .where(
                DCFResult.security_id == security_id,
                DCFResult.implied_price.isnot(None),
            )
            .order_by(DCFResult.calculation_date.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        dcf: DCFResult | None = result.scalar_one_or_none()
        if dcf is None:
            return None, None, None

        mid = float(dcf.implied_price) if dcf.implied_price is not None else None

        # Try to extract low/high from sensitivity grid
        low: float | None = None
        high: float | None = None

        if dcf.sensitivity_grid:
            grid = dcf.sensitivity_grid
            if isinstance(grid, str):
                import json
                try:
                    grid = json.loads(grid)
                except Exception:
                    grid = {}
            if isinstance(grid, dict):
                grid_values = self._extract_grid_values(grid)
                if grid_values:
                    low = min(grid_values)
                    high = max(grid_values)

        # Fallback: ±15% around mid if no grid
        if low is None and mid is not None:
            low = mid * 0.85
        if high is None and mid is not None:
            high = mid * 1.15

        return low, mid, high

    @staticmethod
    def _extract_grid_values(grid: dict) -> list[float]:
        """Pull numeric implied-price values from a DCF sensitivity grid.

        DCFEngine._build_sensitivity_grid stores the grid as::

            {"wacc_values": [...], "growth_values": [...],
             "implied_prices": [[float | None, ...], ...]}  # rows=wacc, cols=growth

        i.e. ``implied_prices`` is a *nested* list whose cells are per-(WACC,
        growth) implied prices (or ``None`` where growth >= WACC). The previous
        implementation treated it as a flat list, so every element was a row
        (a list) rather than a number and nothing was collected — silently
        forcing the flat ±15% fallback. Recurse so both nested and flat shapes
        (and legacy "values" grids) yield the real per-cell prices.
        """
        values: list[float] = []

        def _collect(container: Any) -> None:
            if isinstance(container, list):
                for item in container:
                    _collect(item)
            elif (
                isinstance(container, (int, float))
                and not isinstance(container, bool)
                and container > 0
            ):
                values.append(float(container))

        if isinstance(grid.get("implied_prices"), list):
            _collect(grid["implied_prices"])
        # Backwards-compat: some older grids stored a nested "values" list.
        if not values and isinstance(grid.get("values"), list):
            _collect(grid["values"])
        return values

    async def _load_comps(
        self,
        session: AsyncSession,
        security_id: UUID,
    ) -> tuple[float | None, float | None, float | None]:
        """Load comps q1/median/q3 implied prices from CompsResult."""
        stmt = (
            select(CompsResult)
            .where(CompsResult.security_id == security_id)
            .order_by(CompsResult.calculation_date.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        comps: CompsResult | None = result.scalar_one_or_none()
        if comps is None or comps.multiples_comparison is None:
            return None, None, None

        # Gather implied prices from each multiple's comparison data
        implied_prices: list[float] = []
        q1_prices: list[float] = []
        q3_prices: list[float] = []

        mc = comps.multiples_comparison
        if isinstance(mc, dict):
            for mult_name, data in mc.items():
                if not isinstance(data, dict):
                    continue
                ip = data.get("implied_price")
                if ip is not None and isinstance(ip, (int, float)) and ip > 0:
                    implied_prices.append(float(ip))

                # Use peer_q1 and peer_q3 to derive low/high ranges
                pq1 = data.get("peer_q1")
                pq3 = data.get("peer_q3")
                if pq1 is not None and isinstance(pq1, (int, float)):
                    q1_prices.append(float(pq1))
                if pq3 is not None and isinstance(pq3, (int, float)):
                    q3_prices.append(float(pq3))

        if not implied_prices:
            return None, None, None

        mid = statistics.median(implied_prices)
        
        # [Bug 33 fix] Ensure an artificial spread so single-point comps
        # still render correctly on the football field.
        if len(implied_prices) == 1:
            low = mid * 0.90
            high = mid * 1.10
        else:
            low = min(implied_prices)
            high = max(implied_prices)

        return low, mid, high

    async def _load_historical(
        self,
        session: AsyncSession,
        security_id: UUID,
    ) -> tuple[float | None, float | None, float | None]:
        """Compute implied value from own historical average multiples.

        Uses PE trailing as the reference multiple.  Loads 1Y and 3Y
        average from MultipleTimeSeries and multiplies by current EPS.
        """
        # Load current EPS
        # [Bug 32 fix] Use emitted name "ttm_diluted_eps"
        eps = await self._latest_metric(session, security_id, "ttm_diluted_eps")
        if eps is None or eps <= 0:
            return None, None, None

        today = date.today()
        cutoff_1y = today - timedelta(days=365)
        cutoff_3y = today - timedelta(days=3 * 365)

        # 1Y average PE
        avg_pe_1y = await self._avg_multiple(
            session, security_id, "pe_trailing", cutoff_1y,
        )
        # 3Y average PE
        avg_pe_3y = await self._avg_multiple(
            session, security_id, "pe_trailing", cutoff_3y,
        )

        implied_1y = avg_pe_1y * eps if avg_pe_1y is not None else None
        implied_3y = avg_pe_3y * eps if avg_pe_3y is not None else None

        # low = min, mid = average, high = max of available
        available = [v for v in (implied_1y, implied_3y) if v is not None]
        if not available:
            return None, None, None

        low = min(available)
        high = max(available)
        mid = statistics.mean(available)

        return low, mid, high

    async def _avg_multiple(
        self,
        session: AsyncSession,
        security_id: UUID,
        multiple_type: str,
        since: date,
    ) -> float | None:
        """Average value from MultipleTimeSeries since *since*."""
        stmt = (
            select(func.avg(MultipleTimeSeries.value))
            .where(
                MultipleTimeSeries.security_id == security_id,
                MultipleTimeSeries.multiple_type == multiple_type,
                MultipleTimeSeries.calculation_date >= since,
                MultipleTimeSeries.value.isnot(None),
                MultipleTimeSeries.value > 0,
            )
        )
        result = await session.execute(stmt)
        val = result.scalar_one_or_none()
        return float(val) if val is not None else None

    async def _load_52w_range(
        self,
        session: AsyncSession,
        security_id: UUID,
    ) -> tuple[float | None, float | None]:
        """52-week high and low from EODPrice."""
        cutoff = date.today() - timedelta(days=365)
        stmt = (
            select(
                func.min(EODPrice.low).label("w52_low"),
                func.max(EODPrice.high).label("w52_high"),
            )
            .where(
                EODPrice.security_id == security_id,
                EODPrice.price_date >= cutoff,
            )
        )
        result = await session.execute(stmt)
        row = result.one_or_none()
        if row is None:
            return None, None
        w52_low = float(row.w52_low) if row.w52_low is not None else None
        w52_high = float(row.w52_high) if row.w52_high is not None else None
        return w52_low, w52_high

    async def _load_analyst_target(
        self,
        session: AsyncSession,
        security_id: UUID,
    ) -> float | None:
        """Load analyst consensus target price from ConsensusEstimate."""
        stmt = (
            select(ConsensusEstimate.median)
            .where(
                ConsensusEstimate.security_id == security_id,
                ConsensusEstimate.metric == "TARGET_PRICE",
                ConsensusEstimate.median.isnot(None),
            )
            .order_by(ConsensusEstimate.as_of_date.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        val = result.scalar_one_or_none()
        return float(val) if val is not None else None

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
