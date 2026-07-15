"""E5 Risk Analytics Engine.

Computes Value at Risk (historical + parametric), stress-test impacts,
style-factor exposures, volatility metrics, and fundamental risk scores.
All metrics are persisted both to dedicated result tables and to
AnalyticsResult for screening.
"""

from __future__ import annotations

import logging
import math
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.engines.base import BaseEngine, EngineOutput, make_input, safe_divide
from src.engines.e5_stress_scenarios import (
    HISTORICAL_SCENARIOS,
    HYPOTHETICAL_SCENARIOS,
    get_all_scenarios,
)
from src.models.analytics import AnalyticsResult
from src.models.risk import FactorExposure, StressTestResult, VaRResult
from src.models.security import EODPrice, EquityDetails, Security

logger = logging.getLogger(__name__)

# Trading days per year used to annualize daily volatility (standard
# convention for US equities; ~252 trading days/year).
TRADING_DAYS_PER_YEAR = 252

# Amihud illiquidity is mean(|return| / dollar_volume), which is a tiny
# number (dollar volume is in the millions+). Scale by 1e6 so the metric
# reads as "price impact per $1M of volume" instead of a string of leading
# zeros.
AMIHUD_SCALE_FACTOR = 1e6

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:  # pragma: no cover
    _HAS_NUMPY = False


# ---------------------------------------------------------------------------
# Pure-Python helpers (used when numpy unavailable)
# ---------------------------------------------------------------------------

def _percentile_pure(sorted_vals: list[float], pct: float) -> float:
    """Return the *pct*-th percentile of already-sorted values (0-100)."""
    n = len(sorted_vals)
    if n == 0:
        return 0.0
    k = (pct / 100.0) * (n - 1)
    f = int(k)
    c = f + 1 if f + 1 < n else f
    d = k - f
    return sorted_vals[f] + d * (sorted_vals[c] - sorted_vals[f])


def _mean(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def _std(vals: list[float], ddof: int = 1) -> float:
    if len(vals) < 2:
        return 0.0
    m = _mean(vals)
    ss = sum((v - m) ** 2 for v in vals)
    return math.sqrt(ss / (len(vals) - ddof))


def _skewness(vals: list[float]) -> float:
    n = len(vals)
    if n < 3:
        return 0.0
    m = _mean(vals)
    s = _std(vals)
    if s == 0:
        return 0.0
    return (n / ((n - 1) * (n - 2))) * sum(((v - m) / s) ** 3 for v in vals)


def _kurtosis_excess(vals: list[float]) -> float:
    n = len(vals)
    if n < 4:
        return 0.0
    m = _mean(vals)
    s = _std(vals)
    if s == 0:
        return 0.0
    k4 = sum(((v - m) / s) ** 4 for v in vals) / n
    return k4 - 3.0


def _max_drawdown(cumulative: list[float]) -> float | None:
    """Max drawdown from a cumulative return series (1+r_1)*(1+r_2)*...

    Returns ``None`` for an empty series ("no data"), distinct from
    ``0.0`` ("data exists and shows zero drawdown").
    """
    if not cumulative:
        return None
    peak = cumulative[0]
    mdd = 0.0
    for v in cumulative:
        if v > peak:
            peak = v
        dd = (peak - v) / peak if peak > 0 else 0.0
        if dd > mdd:
            mdd = dd
    return mdd


# ---------------------------------------------------------------------------
# Price data loader
# ---------------------------------------------------------------------------

async def _load_returns(
    session: AsyncSession,
    security_id: UUID,
    lookback_days: int = 504,
) -> tuple[list[date], list[float], list[float], list[float], list[float]]:
    """Load EOD prices and compute daily returns.

    Returns (dates, returns, close_prices, volumes, high_low_close_ratios).
    """
    cutoff = date.today() - timedelta(days=int(lookback_days * 1.6))
    result = await session.execute(
        select(EODPrice)
        .where(
            EODPrice.security_id == security_id,
            EODPrice.price_date >= cutoff,
        )
        .order_by(EODPrice.price_date)
    )
    rows = result.scalars().all()

    dates: list[date] = []
    returns: list[float] = []
    closes: list[float] = []
    volumes: list[float] = []
    hl_ratios: list[float] = []

    for i, r in enumerate(rows):
        close = float(r.close_adjusted or r.close or 0)
        if close <= 0:
            continue
        closes.append(close)
        dates.append(r.price_date)
        vol = float(r.volume) if r.volume else 0.0
        volumes.append(vol)
        high = float(r.high) if r.high else close
        low = float(r.low) if r.low else close
        hl_ratios.append((high - low) / close if close > 0 else 0.0)
        if i > 0 and len(closes) >= 2:
            prev = closes[-2]
            if prev > 0:
                returns.append((close - prev) / prev)

    return dates, returns, closes, volumes, hl_ratios


# ---------------------------------------------------------------------------
# E5 Risk Engine
# ---------------------------------------------------------------------------

class RiskEngine(BaseEngine):
    """Risk Analytics Engine (E5).

    Computes VaR, stress tests, volatility metrics, factor exposures,
    and fundamental risk indicators for a single security.
    """

    engine_id = "E5"
    engine_name = "Risk Analytics"
    engine_version = "1.0.0"

    # Minimum days of price data to compute risk metrics
    MIN_OBSERVATIONS = 30

    async def compute(
        self,
        session: AsyncSession,
        security_id: UUID,
        *,
        lookback_days: int = 252,
        **kwargs: Any,
    ) -> list[EngineOutput]:
        outputs: list[EngineOutput] = []

        # Resolve entity_id
        sec_result = await session.execute(
            select(Security).where(Security.security_id == security_id)
        )
        sec = sec_result.scalar_one_or_none()
        if sec is None:
            return []
        entity_id = sec.issuer_entity_id or security_id

        # Load price data
        dates, returns, closes, volumes, hl_ratios = await _load_returns(
            session, security_id, lookback_days=lookback_days
        )

        if len(returns) < self.MIN_OBSERVATIONS:
            outputs.append(EngineOutput(
                security_id=security_id,
                entity_id=entity_id,
                engine_id=self.engine_id,
                metric_name="risk_data_status",
                metric_category="RISK",
                value=None,
                data_quality="INSUFFICIENT_DATA",
                inputs=[make_input("price_observations", "EODPrice", len(returns))],
            ))
            return outputs

        # Use the last `lookback_days` returns (or all if fewer)
        rets = returns[-lookback_days:] if len(returns) > lookback_days else returns
        n = len(rets)

        # ── Volatility metrics ────────────────────────────────────
        daily_mean = _mean(rets)
        daily_std = _std(rets)
        ann_vol = daily_std * math.sqrt(TRADING_DAYS_PER_YEAR)
        skew = _skewness(rets)
        kurt = _kurtosis_excess(rets)

        # Max drawdown from cumulative returns
        cum = [1.0]
        for r in rets:
            cum.append(cum[-1] * (1.0 + r))
        mdd = _max_drawdown(cum)

        vol_metrics = {
            "annualized_volatility": ann_vol,
            "daily_volatility": daily_std,
            "skewness": skew,
            "kurtosis": kurt,
            "max_drawdown": mdd,
            "daily_mean_return": daily_mean,
        }
        for name, val in vol_metrics.items():
            outputs.append(EngineOutput(
                security_id=security_id,
                entity_id=entity_id,
                engine_id=self.engine_id,
                metric_name=name,
                metric_category="RISK",
                value=val,
                unit="RATIO",
                inputs=[make_input("n_observations", "EODPrice", n)],
            ))

        # ── Historical VaR ────────────────────────────────────────
        sorted_rets = sorted(rets)
        var_configs = [
            ("var_historical_95_1d", 5.0, 1),
            ("var_historical_99_1d", 1.0, 1),
            ("var_historical_95_10d", 5.0, 10),
            ("var_historical_99_10d", 1.0, 10),
            ("var_historical_95_30d", 5.0, 30),
            ("var_historical_99_30d", 1.0, 30),
        ]
        for metric_name, pct, holding in var_configs:
            var_1d = -_percentile_pure(sorted_rets, pct)
            var_val = var_1d * math.sqrt(holding)
            outputs.append(EngineOutput(
                security_id=security_id,
                entity_id=entity_id,
                engine_id=self.engine_id,
                metric_name=metric_name,
                metric_category="RISK",
                value=var_val,
                unit="RATIO",
                inputs=[
                    make_input("lookback_days", "config", n),
                    make_input("confidence", "config", 1.0 - pct / 100.0),
                ],
            ))

        # Expected shortfall (CVaR). Use ceil() so the tail captures *at least*
        # the requested percentile worth of observations — `int()` floors and
        # under-samples (e.g. 5% of 50 → cutoff=2 covers only 4%).
        for conf_label, pct in [("95", 5.0), ("99", 1.0)]:
            cutoff_idx = max(1, math.ceil(n * pct / 100.0))
            tail = sorted_rets[:cutoff_idx]
            cvar = -_mean(tail) if tail else 0.0
            outputs.append(EngineOutput(
                security_id=security_id,
                entity_id=entity_id,
                engine_id=self.engine_id,
                metric_name=f"cvar_{conf_label}_1d",
                metric_category="RISK",
                value=cvar,
                unit="RATIO",
            ))

        # ── Parametric VaR ────────────────────────────────────────
        z_scores = {"95": 1.645, "99": 2.326}
        for conf_label, z in z_scores.items():
            pvar_1d = -(daily_mean - z * daily_std)
            outputs.append(EngineOutput(
                security_id=security_id,
                entity_id=entity_id,
                engine_id=self.engine_id,
                metric_name=f"var_parametric_{conf_label}_1d",
                metric_category="RISK",
                value=pvar_1d,
                unit="RATIO",
            ))

        # ── Stress tests (hypothetical) ──────────────────────────
        for scenario_name, scenario in HYPOTHETICAL_SCENARIOS.items():
            if "shock_pct" in scenario:
                shock = scenario["shock_pct"]
                outputs.append(EngineOutput(
                    security_id=security_id,
                    entity_id=entity_id,
                    engine_id=self.engine_id,
                    metric_name=f"stress_{scenario_name.lower()}",
                    metric_category="RISK",
                    value=shock,
                    unit="RATIO",
                    inputs=[make_input("scenario", "stress", scenario_name)],
                ))

        # ── Liquidity metrics ─────────────────────────────────────
        recent_volumes = volumes[-60:] if len(volumes) >= 60 else volumes
        vol_20d = _mean(recent_volumes[-20:]) if len(recent_volumes) >= 20 else _mean(recent_volumes)
        vol_60d = _mean(recent_volumes)

        outputs.append(EngineOutput(
            security_id=security_id, entity_id=entity_id,
            engine_id=self.engine_id, metric_name="avg_volume_20d",
            metric_category="RISK", value=vol_20d, unit="SHARES",
        ))
        outputs.append(EngineOutput(
            security_id=security_id, entity_id=entity_id,
            engine_id=self.engine_id, metric_name="avg_volume_60d",
            metric_category="RISK", value=vol_60d, unit="SHARES",
        ))

        # Bid-ask proxy = mean (high-low)/close. This is the simple
        # high-low range estimator, not a Corwin-Schultz-style estimator —
        # it only captures intraday range and does not correct for
        # overnight gaps (a large gap gets attributed to "spread" here when
        # it's really a price-level jump between sessions). Treat this as a
        # liquidity-proxy approximation, not a precise effective-spread
        # estimate.
        recent_hl = hl_ratios[-20:] if len(hl_ratios) >= 20 else hl_ratios
        ba_proxy = _mean(recent_hl) if recent_hl else None
        outputs.append(EngineOutput(
            security_id=security_id, entity_id=entity_id,
            engine_id=self.engine_id, metric_name="bid_ask_proxy",
            metric_category="RISK", value=ba_proxy, unit="RATIO",
        ))

        # Amihud illiquidity: mean(|return| / dollar_volume)
        amihud_vals: list[float] = []
        recent_rets = rets[-20:]
        recent_closes_20 = closes[-(20 + 1):]  # need closes to pair with returns
        recent_vols_20 = volumes[-20:]
        for i, ret in enumerate(recent_rets):
            if i < len(recent_vols_20) and recent_vols_20[i] > 0:
                close_price = recent_closes_20[i + 1] if (i + 1) < len(recent_closes_20) else 1.0
                dollar_vol = recent_vols_20[i] * close_price
                if dollar_vol > 0:
                    amihud_vals.append(abs(ret) / dollar_vol)
        amihud = _mean(amihud_vals) * AMIHUD_SCALE_FACTOR if amihud_vals else None
        outputs.append(EngineOutput(
            security_id=security_id, entity_id=entity_id,
            engine_id=self.engine_id, metric_name="amihud_illiquidity",
            metric_category="RISK", value=amihud, unit="RATIO",
        ))

        # ── Factor exposures ──────────────────────────────────────
        factor_outputs = await self._compute_factor_exposures(
            session, security_id, entity_id, closes, rets
        )
        outputs.extend(factor_outputs)

        # ── Fundamental risk (from AnalyticsResult) ───────────────
        fund_outputs = await self._compute_fundamental_risk(
            session, security_id, entity_id
        )
        outputs.extend(fund_outputs)

        # ── Persist VaR to dedicated table ────────────────────────
        await self._persist_var(session, security_id, outputs, n, daily_mean, daily_std, ann_vol, skew, kurt)

        return outputs

    # ------------------------------------------------------------------
    # Factor exposures
    # ------------------------------------------------------------------

    async def _compute_factor_exposures(
        self,
        session: AsyncSession,
        security_id: UUID,
        entity_id: UUID,
        closes: list[float],
        returns: list[float],
    ) -> list[EngineOutput]:
        outputs: list[EngineOutput] = []

        # Momentum: 12M return excluding last month
        if len(closes) > 252:
            start_price = closes[-(252 + 1)]
            end_price = closes[-22]  # approx 1 month ago
            momentum_12m = (end_price - start_price) / start_price if start_price > 0 else None
        elif len(closes) > 22:
            start_price = closes[0]
            end_price = closes[-22]
            momentum_12m = (end_price - start_price) / start_price if start_price > 0 else None
        else:
            momentum_12m = None

        if momentum_12m is not None:
            outputs.append(EngineOutput(
                security_id=security_id, entity_id=entity_id,
                engine_id=self.engine_id, metric_name="factor_momentum",
                metric_category="FACTOR", value=momentum_12m, unit="RATIO",
            ))

        # Low Volatility: inverse of annualized vol (higher = lower risk)
        if returns:
            ann_vol = _std(returns) * math.sqrt(TRADING_DAYS_PER_YEAR)
            low_vol = 1.0 / ann_vol if ann_vol > 0 else None
            outputs.append(EngineOutput(
                security_id=security_id, entity_id=entity_id,
                engine_id=self.engine_id, metric_name="factor_low_vol",
                metric_category="FACTOR", value=low_vol, unit="RATIO",
            ))

        # Value, Size, Quality, Growth, Dividend from AnalyticsResult
        factor_metric_map = {
            "factor_value": "pb",  # P/B inverted → B/P
            "factor_size": None,  # computed from market_cap below
            "factor_quality": "roic",
            "factor_growth": "revenue_3y_cagr",
            "factor_dividend": "dividend_yield",
        }

        for factor_name, ar_metric in factor_metric_map.items():
            if ar_metric is None:
                continue
            result = await session.execute(
                select(AnalyticsResult.value)
                .where(
                    AnalyticsResult.security_id == security_id,
                    AnalyticsResult.metric_name == ar_metric,
                )
                .order_by(desc(AnalyticsResult.as_of_date))
                .limit(1)
            )
            val = result.scalar_one_or_none()
            if val is not None:
                raw = float(val)
                # For value factor, use B/P (inverse of P/B)
                if factor_name == "factor_value" and raw > 0:
                    raw = 1.0 / raw
                outputs.append(EngineOutput(
                    security_id=security_id, entity_id=entity_id,
                    engine_id=self.engine_id, metric_name=factor_name,
                    metric_category="FACTOR", value=raw, unit="RATIO",
                    inputs=[make_input(ar_metric, "AnalyticsResult", float(val))],
                ))

        # Size factor: log(market_cap) = log(price × shares_outstanding).
        # Shares outstanding is read from EquityDetails (populated by the EDGAR
        # DEI cover-page ingestion in `edgar_securities.py`), the real source —
        # not the `shares_outstanding` AnalyticsResult row, which has no writer.
        if closes:
            last_price = closes[-1]
            shares_result = await session.execute(
                select(EquityDetails.shares_outstanding)
                .where(EquityDetails.security_id == security_id)
                .limit(1)
            )
            shares = shares_result.scalar_one_or_none()
            if shares and float(shares) > 0:
                mcap = last_price * float(shares)
                log_mcap = math.log(mcap) if mcap > 0 else None
                if log_mcap is not None:
                    outputs.append(EngineOutput(
                        security_id=security_id, entity_id=entity_id,
                        engine_id=self.engine_id, metric_name="factor_size",
                        metric_category="FACTOR", value=log_mcap, unit="RATIO",
                        inputs=[make_input("shares_outstanding", "EquityDetails", float(shares))],
                    ))

        return outputs

    # ------------------------------------------------------------------
    # Fundamental risk
    # ------------------------------------------------------------------

    async def _compute_fundamental_risk(
        self,
        session: AsyncSession,
        security_id: UUID,
        entity_id: UUID,
    ) -> list[EngineOutput]:
        """Fetch pre-computed E1 ratios and derive fundamental risk metrics."""
        outputs: list[EngineOutput] = []

        risk_metrics = [
            "net_debt_to_ebitda",
            "interest_coverage",
            "debt_to_equity",
            "current_ratio",
        ]

        for metric_name in risk_metrics:
            result = await session.execute(
                select(AnalyticsResult.value)
                .where(
                    AnalyticsResult.security_id == security_id,
                    AnalyticsResult.metric_name == metric_name,
                )
                .order_by(desc(AnalyticsResult.as_of_date))
                .limit(1)
            )
            val = result.scalar_one_or_none()
            if val is not None:
                outputs.append(EngineOutput(
                    security_id=security_id, entity_id=entity_id,
                    engine_id=self.engine_id,
                    metric_name=f"risk_{metric_name}",
                    metric_category="FUNDAMENTAL_RISK",
                    value=float(val),
                    unit="RATIO",
                    inputs=[make_input(metric_name, "AnalyticsResult", float(val))],
                ))

        # Leverage risk score: simple composite
        nde_r = await self._get_metric(session, security_id, "net_debt_to_ebitda")
        ic_r = await self._get_metric(session, security_id, "interest_coverage")
        leverage_score = None
        if nde_r is not None or ic_r is not None:
            score = 50.0  # neutral
            if nde_r is not None:
                if nde_r > 4:
                    score += 25
                elif nde_r > 2:
                    score += 10
                elif nde_r < 1:
                    score -= 15
            if ic_r is not None:
                if ic_r < 2:
                    score += 25
                elif ic_r < 5:
                    score += 10
                elif ic_r > 10:
                    score -= 15
            leverage_score = max(0.0, min(100.0, score))
            outputs.append(EngineOutput(
                security_id=security_id, entity_id=entity_id,
                engine_id=self.engine_id, metric_name="risk_leverage_score",
                metric_category="FUNDAMENTAL_RISK", value=leverage_score,
                unit="SCORE",
            ))

        return outputs

    async def _get_metric(
        self, session: AsyncSession, security_id: UUID, metric_name: str
    ) -> float | None:
        result = await session.execute(
            select(AnalyticsResult.value)
            .where(
                AnalyticsResult.security_id == security_id,
                AnalyticsResult.metric_name == metric_name,
            )
            .order_by(desc(AnalyticsResult.as_of_date))
            .limit(1)
        )
        val = result.scalar_one_or_none()
        return float(val) if val is not None else None

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def _persist_var(
        self,
        session: AsyncSession,
        security_id: UUID,
        outputs: list[EngineOutput],
        n: int,
        daily_mean: float,
        daily_std: float,
        ann_vol: float,
        skew: float,
        kurt: float,
    ) -> None:
        """Persist VaR results to the dedicated table.

        Metric names follow ``var_historical_<conf>_<holding>d``. We parse
        defensively: an unexpected suffix should skip the row, not crash the
        whole persistence pass.
        """
        today = date.today()
        for out in outputs:
            if not out.metric_name.startswith("var_historical_"):
                continue
            parts = out.metric_name.replace("var_historical_", "").split("_")
            if len(parts) < 2:
                logger.warning("Skipping VaR row with unparseable metric name: %s", out.metric_name)
                continue
            try:
                conf = float(parts[0]) / 100.0  # "95" → 0.95
                holding = int(parts[1].replace("d", ""))
            except (ValueError, TypeError) as exc:
                logger.warning("Skipping VaR row %s: %s", out.metric_name, exc)
                continue
            var_row = VaRResult(
                security_id=security_id,
                calculation_date=today,
                method="HISTORICAL",
                confidence_level=conf,
                holding_period_days=holding,
                var_value=out.value,
                lookback_days=n,
                annualized_volatility=ann_vol,
                daily_mean_return=daily_mean,
                daily_std_return=daily_std,
                skewness=skew,
                kurtosis=kurt,
                data_quality="COMPLETE",
            )
            session.add(var_row)

        await session.flush()

    # ------------------------------------------------------------------
    # Stress test (standalone, called by API)
    # ------------------------------------------------------------------

    async def run_stress_test(
        self,
        session: AsyncSession,
        security_id: UUID,
        scenario_name: str,
        shock_pct: float | None = None,
    ) -> StressTestResult | None:
        """Run a single stress scenario and persist the result."""
        sec_result = await session.execute(
            select(Security).where(Security.security_id == security_id)
        )
        sec = sec_result.scalar_one_or_none()
        if sec is None:
            return None

        if scenario_name in HYPOTHETICAL_SCENARIOS:
            scenario = HYPOTHETICAL_SCENARIOS[scenario_name]
            pnl = shock_pct if shock_pct is not None else scenario.get("shock_pct", -0.10)
            result = StressTestResult(
                security_id=security_id,
                calculation_date=date.today(),
                scenario_type="HYPOTHETICAL",
                scenario_name=scenario_name,
                scenario_params=scenario,
                pnl_percent=pnl,
                max_drawdown=pnl if pnl < 0 else 0.0,
                data_quality="COMPLETE",
            )
        elif scenario_name in HISTORICAL_SCENARIOS:
            # For historical, compute PnL from actual price data during that period
            scenario = HISTORICAL_SCENARIOS[scenario_name]
            _, returns, _, _, _ = await _load_returns(session, security_id, lookback_days=5000)
            if not returns:
                return None
            # Compound the trailing 1y of daily log/simple returns rather than
            # annualising an arithmetic mean — the latter overstates returns
            # in volatile periods and ignores compounding.
            window = returns[-252:]
            cumulative = 1.0
            for r in window:
                cumulative *= (1.0 + r)
            pnl = cumulative - 1.0
            result = StressTestResult(
                security_id=security_id,
                calculation_date=date.today(),
                scenario_type="HISTORICAL",
                scenario_name=scenario_name,
                scenario_params=scenario,
                pnl_percent=pnl,
                data_quality="ESTIMATED",
            )
        else:
            return None

        session.add(result)
        await session.flush()
        return result

    # ------------------------------------------------------------------
    # Static helpers for classification
    # ------------------------------------------------------------------

    @staticmethod
    def classify_risk_level(var_95_1d: float | None) -> str:
        """Classify VaR into risk tiers."""
        if var_95_1d is None:
            return "UNKNOWN"
        if var_95_1d > 0.05:
            return "HIGH"
        if var_95_1d > 0.02:
            return "MODERATE"
        return "LOW"
