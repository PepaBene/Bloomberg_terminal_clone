"""E1 Trend Analysis Engine.

Computes trend metrics for key financial ratios stored in ``analytics_results``.
For each ratio produces up to 10 derived metrics across four dimensions:

* **Direction** -- 1Y/3Y/5Y trend direction with percentage change.
* **Momentum** -- rate-of-change and acceleration of YoY shifts.
* **Consistency** -- std dev, coefficient of variation, classification (5Y).
* **Mean Reversion** -- z-score vs 5Y mean and signal label.

Reads already-computed ratios from ``AnalyticsResult`` (engine_id ``E1``)
and only processes the ~25 most important ratios in ``TREND_RATIOS``.
"""

from __future__ import annotations

import logging
import statistics
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.engines.base import BaseEngine, EngineOutput, make_input
from src.models.analytics import AnalyticsResult
from src.models.security import Security

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ratios to track — fallback list used when dynamic discovery is unavailable
# [Bug 5 fix] Prefer dynamic discovery from AnalyticsResult; this list
# serves only as a default when no prior E1 results exist yet.
# ---------------------------------------------------------------------------

_DEFAULT_TREND_RATIOS: list[str] = [
    "gross_margin", "operating_margin", "ebitda_margin", "net_margin", "fcf_margin",
    "roe", "roa", "roic", "roce",
    "debt_to_equity", "net_debt_to_ebitda", "interest_coverage", "current_ratio",
    "asset_turnover", "inventory_turnover", "receivables_turnover",
    "revenue_yoy", "ebitda_yoy", "net_income_yoy", "eps_yoy",
    "dso", "dio", "dpo", "ccc",
    "payout_ratio",
]

# Keep module-level alias for backward compatibility
TREND_RATIOS = _DEFAULT_TREND_RATIOS

_MIN_STDEV_POINTS = 4  # [Bug 12] minimum data points for reliable stdev

_STABLE_PCT = 0.05
_COV_HIGHLY_CONSISTENT = 0.15
_COV_MODERATE = 0.40

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _data_quality_for(n_points: int) -> str:
    """Map data-point count to a quality flag."""
    if n_points >= 3:
        return "COMPLETE"
    if n_points >= 1:
        return "PARTIAL"
    return "INSUFFICIENT_DATA"


def _direction_label(pct: float | None) -> str | None:
    if pct is None:
        return None
    if pct > _STABLE_PCT:
        return "IMPROVING"
    if pct < -_STABLE_PCT:
        return "DETERIORATING"
    return "STABLE"


def _consistency_label(cov: float | None) -> str | None:
    if cov is None:
        return None
    if cov < _COV_HIGHLY_CONSISTENT:
        return "HIGHLY_CONSISTENT"
    if cov <= _COV_MODERATE:
        return "MODERATE"
    return "VOLATILE"


def _mean_reversion_label(z: float | None) -> str | None:
    if z is None:
        return None
    if z > 2:
        return "SIGNIFICANTLY_ABOVE"
    if z > 1:
        return "ABOVE"
    if z >= -1:
        return "NORMAL"
    if z >= -2:
        return "BELOW"
    return "SIGNIFICANTLY_BELOW"


def _pct_change(current: float | None, prior: float | None) -> float | None:
    """Percentage change: (current - prior) / |prior|."""
    if current is None or prior is None or prior == 0:
        return None
    return (current - prior) / abs(prior)


def _build_output(
    security_id: UUID, entity_id: UUID, metric_name: str, value: float | None,
    *, unit: str = "RATIO", data_quality: str = "COMPLETE",
    inputs: list[dict] | None = None,
) -> EngineOutput:
    """Convenience factory for a trend EngineOutput."""
    return EngineOutput(
        security_id=security_id, entity_id=entity_id,
        engine_id="E1", metric_name=metric_name, metric_category="TREND",
        value=value, unit=unit, period="TREND",
        period_end_date=date.today(), data_quality=data_quality, inputs=inputs,
    )

# ---------------------------------------------------------------------------
# Historical data container
# ---------------------------------------------------------------------------

class _RatioHistory:
    """Chronologically ordered (date, value) pairs for a single ratio."""

    __slots__ = ("name", "points")

    def __init__(self, name: str) -> None:
        self.name = name
        self.points: list[tuple[date, float]] = []  # ascending by date

    @property
    def n(self) -> int:
        return len(self.points)

    @property
    def latest(self) -> float | None:
        return self.points[-1][1] if self.points else None

    def value_n_years_ago(self, years: int) -> float | None:
        """Value closest to *years* before the latest point (180-day tolerance)."""
        if not self.points:
            return None
        target = self.points[-1][0] - timedelta(days=365 * years)
        best: tuple[int, float] | None = None
        for dt, val in self.points:
            delta = abs((dt - target).days)
            if best is None or delta < best[0]:
                best = (delta, val)
        if best is None or best[0] > 180:
            return None
        return best[1]

    def values_last_n_years(self, years: int) -> list[float]:
        """All values within the last *years* from the latest date."""
        if not self.points:
            return []
        cutoff = self.points[-1][0] - timedelta(days=365 * years)
        return [v for d, v in self.points if d >= cutoff]

    def prior_year_momentum(self) -> float | None:
        """1Y momentum computed one period earlier (for acceleration calc).

        Takes the second-latest point and the point ~1 year before it.
        [Bug 14 fix] Requires the comparison point to be at least
        180 days before the reference point to avoid matching the
        same observation twice in sparse series.
        """
        if len(self.points) < 3:
            return None
        prior_date = self.points[-2][0]
        prior_val = self.points[-2][1]
        target = prior_date - timedelta(days=365)
        best: tuple[int, float] | None = None
        for dt, val in self.points[:-1]:
            # [Bug 14] Skip points that are too close to the reference
            separation = (prior_date - dt).days
            if separation < 180:
                continue
            delta = abs((dt - target).days)
            if best is None or delta < best[0]:
                best = (delta, val)
        if best is None or best[0] > 180:
            return None
        if best[1] == 0:
            return None
        return (prior_val - best[1]) / abs(best[1])

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class TrendEngine(BaseEngine):
    """Trend analysis engine (E1).

    Reads historical ratio values from ``analytics_results`` and computes
    direction, momentum, consistency, and mean-reversion metrics for each
    key ratio.  Produces up to ~250 outputs per security.
    """

    engine_id = "E1"
    engine_name = "Trend Analysis"
    engine_version = "1.0.0"

    async def compute(
        self,
        session: AsyncSession,
        security_id: UUID,
        **kwargs: Any,
    ) -> list[EngineOutput]:
        # 1. Resolve security -> entity
        sec_row = await session.execute(
            select(Security).where(Security.security_id == security_id)
        )
        security = sec_row.scalar_one_or_none()
        if security is None or security.issuer_entity_id is None:
            logger.warning("Trend: security %s not found or has no issuer", security_id)
            return []
        entity_id: UUID = security.issuer_entity_id

        # 2. [Bug 5 fix] Dynamically discover all E1 metric names for this
        #    security, falling back to _DEFAULT_TREND_RATIOS if no prior
        #    results exist yet.
        from sqlalchemy import distinct as sa_distinct

        disc_stmt = (
            select(sa_distinct(AnalyticsResult.metric_name))
            .where(
                AnalyticsResult.security_id == security_id,
                AnalyticsResult.engine_id == "E1",
                AnalyticsResult.metric_category != "TREND",  # exclude our own output
                AnalyticsResult.value.is_not(None),
            )
        )
        disc_rows = await session.execute(disc_stmt)
        discovered_ratios = [row[0] for row in disc_rows.all()]
        ratio_list = discovered_ratios if discovered_ratios else list(_DEFAULT_TREND_RATIOS)

        # Load all E1 ratio history for this security
        stmt = (
            select(
                AnalyticsResult.metric_name,
                AnalyticsResult.period_end_date,
                AnalyticsResult.value,
            )
            .where(
                AnalyticsResult.security_id == security_id,
                AnalyticsResult.engine_id == "E1",
                AnalyticsResult.metric_name.in_(ratio_list),
                AnalyticsResult.value.is_not(None),
                AnalyticsResult.period_end_date.is_not(None),
            )
            .order_by(
                AnalyticsResult.metric_name,
                AnalyticsResult.period_end_date.asc(),
            )
        )
        rows = await session.execute(stmt)
        all_rows = rows.all()

        histories: dict[str, _RatioHistory] = {}
        for metric_name, period_end_date, value in all_rows:
            if metric_name not in histories:
                histories[metric_name] = _RatioHistory(metric_name)
            histories[metric_name].points.append((period_end_date, float(value)))

        # 3. Compute trend metrics for each ratio
        outputs: list[EngineOutput] = []
        for ratio_name in ratio_list:
            hist = histories.get(ratio_name)
            if hist is None or hist.n < 2:
                continue
            outputs.extend(self._compute_ratio_trends(security_id, entity_id, hist))

        logger.info(
            "Trend: computed %d metrics for security %s (%d ratios analysed)",
            len(outputs), security_id, len(histories),
        )
        return outputs

    # ------------------------------------------------------------------
    # Per-ratio computation
    # ------------------------------------------------------------------

    def _compute_ratio_trends(
        self, security_id: UUID, entity_id: UUID, hist: _RatioHistory,
    ) -> list[EngineOutput]:
        """Produce all trend outputs for a single ratio's history."""
        outputs: list[EngineOutput] = []
        name = hist.name
        current = hist.latest
        quality = _data_quality_for(hist.n)

        def _inp(label: str, val: float | None, period: str = "") -> dict:
            return make_input(name=label, source="analytics_results", value=val, period=period)

        def _out(
            metric: str, value: float | None, *,
            unit: str = "RATIO", dq: str = quality, inputs: list[dict] | None = None,
        ) -> EngineOutput:
            return _build_output(
                security_id, entity_id, metric, value,
                unit=unit, data_quality=dq, inputs=inputs,
            )

        # -- Direction (1Y, 3Y, 5Y) ----------------------------------------
        for horizon in (1, 3, 5):
            prior = hist.value_n_years_ago(horizon)
            pct = _pct_change(current, prior)
            label = _direction_label(pct)
            outputs.append(_out(
                f"{name}_trend_{horizon}y", pct, unit="DIRECTION",
                inputs=[
                    _inp(f"{name}_current", current),
                    _inp(f"{name}_{horizon}y_ago", prior),
                    _inp("direction", None, period=label or ""),
                ],
            ))

        # -- Momentum -------------------------------------------------------
        prior_1y = hist.value_n_years_ago(1)
        momentum = _pct_change(current, prior_1y)
        outputs.append(_out(
            f"{name}_momentum", momentum,
            inputs=[_inp(f"{name}_current", current), _inp(f"{name}_1y_ago", prior_1y)],
        ))

        prior_momentum = hist.prior_year_momentum()
        acceleration: float | None = None
        if momentum is not None and prior_momentum is not None:
            acceleration = momentum - prior_momentum
        outputs.append(_out(
            f"{name}_acceleration", acceleration,
            inputs=[_inp("current_momentum", momentum), _inp("prior_momentum", prior_momentum)],
        ))

        # -- Consistency (5-year window) ------------------------------------
        vals_5y = hist.values_last_n_years(5)
        n5 = len(vals_5y)
        dq_5y = _data_quality_for(n5)

        std_5y: float | None = None
        mean_5y: float | None = None
        cov_5y: float | None = None
        consistency: str | None = None

        # [Bug 12 fix] Require minimum _MIN_STDEV_POINTS for reliable stdev
        if n5 >= _MIN_STDEV_POINTS:
            std_5y = statistics.stdev(vals_5y)
            mean_5y = statistics.mean(vals_5y)
            if mean_5y != 0:
                cov_5y = std_5y / abs(mean_5y)
            consistency = _consistency_label(cov_5y)
        elif n5 >= 2:
            # Enough for mean but not for reliable stdev
            mean_5y = statistics.mean(vals_5y)
            dq_5y = "INSUFFICIENT_DATA"

        outputs.append(_out(
            f"{name}_std_5y", std_5y, dq=dq_5y,
            inputs=[_inp("n_periods", float(n5))],
        ))
        outputs.append(_out(
            f"{name}_cov_5y", cov_5y, dq=dq_5y,
            inputs=[_inp("std_5y", std_5y), _inp("mean_5y", mean_5y)],
        ))
        outputs.append(_out(
            f"{name}_consistency", cov_5y, unit="CLASSIFICATION", dq=dq_5y,
            inputs=[
                _inp("cov_5y", cov_5y),
                _inp("classification", None, period=consistency or ""),
            ],
        ))

        # -- Mean Reversion -------------------------------------------------
        zscore: float | None = None
        mr_signal: str | None = None
        if std_5y is not None and mean_5y is not None and current is not None:
            if std_5y == 0:
                # [Bug 13 fix] Zero variance means perfectly stable
                zscore = 0.0
                mr_signal = "NORMAL"
                dq_5y = "HIGHLY_CONSISTENT"
            else:
                zscore = (current - mean_5y) / std_5y
                mr_signal = _mean_reversion_label(zscore)

        outputs.append(_out(
            f"{name}_zscore_5y", zscore, unit="SCORE", dq=dq_5y,
            inputs=[
                _inp(f"{name}_current", current),
                _inp("mean_5y", mean_5y),
                _inp("std_5y", std_5y),
            ],
        ))
        outputs.append(_out(
            f"{name}_mean_reversion_signal", zscore, unit="CLASSIFICATION", dq=dq_5y,
            inputs=[
                _inp("zscore_5y", zscore),
                _inp("signal", None, period=mr_signal or ""),
            ],
        ))

        return outputs
