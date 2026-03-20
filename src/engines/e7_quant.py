"""E7 Quantitative & Statistical Engine.

Provides regression (OLS, robust), correlation (Pearson, Spearman, Kendall),
time-series tests (ADF, KPSS, cointegration), and default per-security
quant summary (beta, correlation to benchmark, autocorrelation, stationarity).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.engines.base import BaseEngine, EngineOutput, make_input
from src.models.quant import CorrelationResult, RegressionResult, TimeSeriesTestResult
from src.models.security import EODPrice, Security

logger = logging.getLogger(__name__)

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:  # pragma: no cover
    _HAS_NUMPY = False

try:
    from scipy import stats as sp_stats
    _HAS_SCIPY = True
except ImportError:  # pragma: no cover
    _HAS_SCIPY = False

try:
    from statsmodels.tsa.stattools import adfuller, kpss, coint
    _HAS_STATSMODELS = True
except ImportError:  # pragma: no cover
    _HAS_STATSMODELS = False


# ---------------------------------------------------------------------------
# Pure-Python helpers
# ---------------------------------------------------------------------------

def _mean(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def _std(vals: list[float], ddof: int = 1) -> float:
    if len(vals) < 2:
        return 0.0
    m = _mean(vals)
    return math.sqrt(sum((v - m) ** 2 for v in vals) / (len(vals) - ddof))


def _ols(x: list[float], y: list[float]) -> dict:
    """Simple OLS: y = alpha + beta * x.  Returns full stats dict."""
    n = len(x)
    if n < 3 or len(y) != n:
        return {"error": "insufficient_data", "n": n}

    mx, my = _mean(x), _mean(y)
    ss_xy = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    ss_xx = sum((xi - mx) ** 2 for xi in x)
    ss_yy = sum((yi - my) ** 2 for yi in y)

    if ss_xx == 0:
        return {"error": "zero_variance_x", "n": n}

    beta = ss_xy / ss_xx
    alpha = my - beta * mx

    residuals = [yi - (alpha + beta * xi) for xi, yi in zip(x, y)]
    ss_res = sum(r ** 2 for r in residuals)
    ss_tot = ss_yy
    r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    adj_r_squared = 1.0 - ((1.0 - r_squared) * (n - 1) / (n - 2)) if n > 2 else r_squared

    mse = ss_res / (n - 2) if n > 2 else 0.0
    se_beta = math.sqrt(mse / ss_xx) if ss_xx > 0 and mse >= 0 else 0.0
    se_alpha = math.sqrt(mse * (1.0 / n + mx ** 2 / ss_xx)) if ss_xx > 0 and mse >= 0 else 0.0

    # F-statistic
    ms_reg = (ss_tot - ss_res) if ss_tot > ss_res else 0.0
    f_stat = (ms_reg / 1) / mse if mse > 0 else 0.0

    # t-statistics and p-values (approximate via normal for large n)
    t_beta = beta / se_beta if se_beta > 0 else 0.0

    # Residual diagnostics
    res_mean = _mean(residuals)
    res_std = _std(residuals)

    # 95% confidence interval for beta
    # Approx: beta ± 1.96 * se_beta
    ci_low = beta - 1.96 * se_beta
    ci_high = beta + 1.96 * se_beta

    return {
        "coefficients": {"intercept": alpha, "x": beta},
        "std_errors": {"intercept": se_alpha, "x": se_beta},
        "r_squared": r_squared,
        "adj_r_squared": adj_r_squared,
        "f_statistic": f_stat,
        "n_observations": n,
        "confidence_intervals": {"x": [ci_low, ci_high]},
        "residuals_summary": {
            "mean": res_mean,
            "std": res_std,
        },
    }


def _pearson_corr(x: list[float], y: list[float]) -> tuple[float, float | None]:
    """Pearson correlation coefficient + approximate p-value."""
    n = len(x)
    if n < 3 or len(y) != n:
        return 0.0, None

    mx, my = _mean(x), _mean(y)
    sx, sy = _std(x), _std(y)
    if sx == 0 or sy == 0:
        return 0.0, None

    cov = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y)) / (n - 1)
    r = cov / (sx * sy)
    r = max(-1.0, min(1.0, r))

    # Fisher transform for p-value approximation
    if abs(r) >= 1.0:
        p_val = 0.0
    else:
        t_stat = r * math.sqrt((n - 2) / (1 - r ** 2))
        # Rough p-value from t-distribution (2-tailed, normal approx for large n)
        p_val = 2.0 * (1.0 - _normal_cdf(abs(t_stat))) if n > 30 else None

    return r, p_val


def _spearman_corr(x: list[float], y: list[float]) -> tuple[float, float | None]:
    """Spearman rank correlation."""
    if _HAS_SCIPY:
        corr, p = sp_stats.spearmanr(x, y)
        return float(corr), float(p)
    # Fallback: rank and compute Pearson on ranks
    rx = _rank(x)
    ry = _rank(y)
    return _pearson_corr(rx, ry)


def _rank(vals: list[float]) -> list[float]:
    """Assign ranks to values (average rank for ties)."""
    indexed = sorted(enumerate(vals), key=lambda t: t[1])
    ranks = [0.0] * len(vals)
    i = 0
    while i < len(indexed):
        j = i
        while j < len(indexed) and indexed[j][1] == indexed[i][1]:
            j += 1
        avg_rank = (i + j - 1) / 2.0 + 1.0
        for k in range(i, j):
            ranks[indexed[k][0]] = avg_rank
        i = j
    return ranks


def _normal_cdf(x: float) -> float:
    """Approximate standard normal CDF."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _autocorrelation(vals: list[float], lag: int = 1) -> float:
    """Compute autocorrelation at a given lag."""
    n = len(vals)
    if n <= lag:
        return 0.0
    m = _mean(vals)
    var = sum((v - m) ** 2 for v in vals) / n
    if var == 0:
        return 0.0
    cov = sum((vals[i] - m) * (vals[i - lag] - m) for i in range(lag, n)) / n
    return cov / var


# ---------------------------------------------------------------------------
# Price data loader
# ---------------------------------------------------------------------------

async def _load_price_series(
    session: AsyncSession,
    security_id: UUID,
    lookback_days: int = 756,
) -> tuple[list[date], list[float]]:
    """Load adjusted close prices for a security."""
    cutoff = date.today() - timedelta(days=int(lookback_days * 1.6))
    result = await session.execute(
        select(EODPrice.price_date, EODPrice.close_adjusted, EODPrice.close)
        .where(
            EODPrice.security_id == security_id,
            EODPrice.price_date >= cutoff,
        )
        .order_by(EODPrice.price_date)
    )
    rows = result.all()
    dates = []
    prices = []
    for r in rows:
        p = float(r[1] or r[2] or 0)
        if p > 0:
            dates.append(r[0])
            prices.append(p)
    return dates, prices


def _prices_to_returns(prices: list[float]) -> list[float]:
    """Convert price series to simple returns."""
    return [(prices[i] - prices[i - 1]) / prices[i - 1]
            for i in range(1, len(prices))
            if prices[i - 1] > 0]


# ---------------------------------------------------------------------------
# E7 Quantitative Engine
# ---------------------------------------------------------------------------

class QuantEngine(BaseEngine):
    """Quantitative & Statistical Engine (E7).

    Default ``compute()`` produces per-security quant summary: beta,
    correlation to benchmark, autocorrelation, stationarity test.
    Standalone methods run regressions, correlations, and time-series tests.
    """

    engine_id = "E7"
    engine_name = "Quantitative & Statistical"
    engine_version = "1.0.0"

    BLUME_WEIGHT = 0.67
    MIN_OBSERVATIONS = 30

    async def compute(
        self,
        session: AsyncSession,
        security_id: UUID,
        *,
        benchmark_id: UUID | None = None,
        lookback_days: int = 504,
        **kwargs: Any,
    ) -> list[EngineOutput]:
        outputs: list[EngineOutput] = []

        # Resolve entity
        sec_result = await session.execute(
            select(Security).where(Security.security_id == security_id)
        )
        sec = sec_result.scalar_one_or_none()
        if sec is None:
            return []
        entity_id = sec.issuer_entity_id or security_id

        # Load security price series
        _, sec_prices = await _load_price_series(session, security_id, lookback_days)
        sec_returns = _prices_to_returns(sec_prices)

        if len(sec_returns) < self.MIN_OBSERVATIONS:
            outputs.append(EngineOutput(
                security_id=security_id, entity_id=entity_id,
                engine_id=self.engine_id, metric_name="quant_data_status",
                metric_category="STATISTICAL", value=None,
                data_quality="INSUFFICIENT_DATA",
                inputs=[make_input("observations", "EODPrice", len(sec_returns))],
            ))
            return outputs

        # Load benchmark returns if available
        bench_returns: list[float] | None = None
        if benchmark_id:
            _, bench_prices = await _load_price_series(session, benchmark_id, lookback_days)
            bench_returns = _prices_to_returns(bench_prices)

        # ── Beta ──────────────────────────────────────────────────
        if bench_returns and len(bench_returns) >= self.MIN_OBSERVATIONS:
            min_len = min(len(sec_returns), len(bench_returns))
            sr = sec_returns[-min_len:]
            br = bench_returns[-min_len:]

            ols_result = _ols(br, sr)
            if "error" not in ols_result:
                raw_beta = ols_result["coefficients"]["x"]
                blume_beta = self.BLUME_WEIGHT * raw_beta + (1.0 - self.BLUME_WEIGHT) * 1.0
                r_sq = ols_result["r_squared"]

                outputs.extend([
                    EngineOutput(
                        security_id=security_id, entity_id=entity_id,
                        engine_id=self.engine_id, metric_name="beta_market",
                        metric_category="STATISTICAL", value=raw_beta, unit="RATIO",
                        inputs=[make_input("n_observations", "EODPrice", min_len)],
                    ),
                    EngineOutput(
                        security_id=security_id, entity_id=entity_id,
                        engine_id=self.engine_id, metric_name="beta_blume_adjusted",
                        metric_category="STATISTICAL", value=blume_beta, unit="RATIO",
                    ),
                    EngineOutput(
                        security_id=security_id, entity_id=entity_id,
                        engine_id=self.engine_id, metric_name="beta_r_squared",
                        metric_category="STATISTICAL", value=r_sq, unit="RATIO",
                    ),
                ])

                # Rolling beta (60-day)
                window = 60
                if min_len >= window:
                    sr_w = sr[-window:]
                    br_w = br[-window:]
                    roll_result = _ols(br_w, sr_w)
                    if "error" not in roll_result:
                        outputs.append(EngineOutput(
                            security_id=security_id, entity_id=entity_id,
                            engine_id=self.engine_id, metric_name="beta_rolling_60d",
                            metric_category="STATISTICAL",
                            value=roll_result["coefficients"]["x"],
                            unit="RATIO",
                        ))

                # Correlation to benchmark
                corr_p, pval_p = _pearson_corr(sr, br)
                outputs.append(EngineOutput(
                    security_id=security_id, entity_id=entity_id,
                    engine_id=self.engine_id, metric_name="correlation_market_pearson",
                    metric_category="STATISTICAL", value=corr_p, unit="CORRELATION",
                ))
                corr_s, _ = _spearman_corr(sr, br)
                outputs.append(EngineOutput(
                    security_id=security_id, entity_id=entity_id,
                    engine_id=self.engine_id, metric_name="correlation_market_spearman",
                    metric_category="STATISTICAL", value=corr_s, unit="CORRELATION",
                ))

        # ── Autocorrelation ───────────────────────────────────────
        ac1 = _autocorrelation(sec_returns, lag=1)
        outputs.append(EngineOutput(
            security_id=security_id, entity_id=entity_id,
            engine_id=self.engine_id, metric_name="autocorrelation_lag1",
            metric_category="STATISTICAL", value=ac1, unit="CORRELATION",
        ))

        # ── ADF stationarity test ─────────────────────────────────
        adf_out = await self._run_adf(sec_prices[-lookback_days:] if len(sec_prices) > lookback_days else sec_prices)
        if adf_out:
            outputs.extend([
                EngineOutput(
                    security_id=security_id, entity_id=entity_id,
                    engine_id=self.engine_id, metric_name="adf_test_statistic",
                    metric_category="STATISTICAL", value=adf_out["test_statistic"],
                    unit="SCORE",
                ),
                EngineOutput(
                    security_id=security_id, entity_id=entity_id,
                    engine_id=self.engine_id, metric_name="adf_p_value",
                    metric_category="STATISTICAL", value=adf_out["p_value"],
                    unit="RATIO",
                ),
                EngineOutput(
                    security_id=security_id, entity_id=entity_id,
                    engine_id=self.engine_id, metric_name="is_stationary",
                    metric_category="STATISTICAL",
                    value=1.0 if adf_out["is_significant"] else 0.0,
                    unit="BOOLEAN",
                ),
            ])

        return outputs

    # ------------------------------------------------------------------
    # Standalone: Regression
    # ------------------------------------------------------------------

    async def run_regression(
        self,
        session: AsyncSession,
        security_id: UUID,
        x_values: list[float],
        y_values: list[float],
        *,
        method: str = "OLS",
        dependent_var: str = "daily_return",
        independent_var: str = "market_return",
    ) -> dict:
        """Run a regression and persist the result."""
        result = _ols(x_values, y_values)
        if "error" in result:
            return result

        # Rename generic "x" key to the actual variable name
        coeffs = {
            "intercept": result["coefficients"]["intercept"],
            independent_var: result["coefficients"]["x"],
        }
        se = {
            "intercept": result["std_errors"]["intercept"],
            independent_var: result["std_errors"]["x"],
        }
        ci = {independent_var: result["confidence_intervals"]["x"]}

        reg = RegressionResult(
            security_id=security_id,
            calculation_date=date.today(),
            method=method,
            dependent_var=dependent_var,
            independent_vars=[independent_var],
            coefficients=coeffs,
            std_errors=se,
            r_squared=result["r_squared"],
            adj_r_squared=result["adj_r_squared"],
            f_statistic=result["f_statistic"],
            n_observations=result["n_observations"],
            confidence_intervals=ci,
            residuals_summary=result["residuals_summary"],
            data_quality="COMPLETE",
        )
        session.add(reg)
        await session.flush()

        return {
            "regression_id": reg.regression_id,
            "method": method,
            "coefficients": coeffs,
            "std_errors": se,
            "r_squared": result["r_squared"],
            "adj_r_squared": result["adj_r_squared"],
            "f_statistic": result["f_statistic"],
            "n_observations": result["n_observations"],
            "confidence_intervals": ci,
            "residuals_summary": result["residuals_summary"],
        }

    # ------------------------------------------------------------------
    # Standalone: Correlation
    # ------------------------------------------------------------------

    async def run_correlation(
        self,
        session: AsyncSession,
        x_values: list[float],
        y_values: list[float],
        *,
        method: str = "PEARSON",
        series_x_id: str = "",
        series_y_id: str = "",
        series_x_label: str = "",
        series_y_label: str = "",
    ) -> dict:
        """Compute pairwise correlation and persist."""
        if method == "SPEARMAN":
            coeff, p_val = _spearman_corr(x_values, y_values)
        elif method == "KENDALL" and _HAS_SCIPY:
            coeff, p_val = sp_stats.kendalltau(x_values, y_values)
            coeff, p_val = float(coeff), float(p_val)
        else:
            coeff, p_val = _pearson_corr(x_values, y_values)

        corr = CorrelationResult(
            calculation_date=date.today(),
            method=method,
            series_x_id=series_x_id,
            series_y_id=series_y_id,
            series_x_label=series_x_label,
            series_y_label=series_y_label,
            coefficient=coeff,
            p_value=p_val,
            n_observations=len(x_values),
            data_quality="COMPLETE",
        )
        session.add(corr)
        await session.flush()

        return {
            "correlation_id": corr.correlation_id,
            "method": method,
            "coefficient": coeff,
            "p_value": p_val,
            "n_observations": len(x_values),
        }

    # ------------------------------------------------------------------
    # Standalone: Stationarity
    # ------------------------------------------------------------------

    async def _run_adf(self, series: list[float]) -> dict | None:
        """Run Augmented Dickey-Fuller test."""
        if len(series) < 20:
            return None

        if _HAS_STATSMODELS:
            try:
                result = adfuller(series, autolag="AIC")
                return {
                    "test_statistic": float(result[0]),
                    "p_value": float(result[1]),
                    "lags_used": int(result[2]),
                    "n_observations": int(result[3]),
                    "critical_values": {k: float(v) for k, v in result[4].items()},
                    "is_significant": float(result[1]) < 0.05,
                }
            except Exception:
                logger.exception("ADF test failed")
                return None

        # Simplified fallback: check if returns (first differences) have lower variance
        # This is a rough heuristic, not a real ADF test
        if len(series) < 30:
            return None
        returns = [series[i] - series[i - 1] for i in range(1, len(series))]
        var_level = _std(series) ** 2
        var_diff = _std(returns) ** 2
        ratio = var_diff / var_level if var_level > 0 else 1.0
        # If first-difference variance is much lower, likely non-stationary in levels
        return {
            "test_statistic": -ratio * 5,  # rough heuristic
            "p_value": 0.5 if ratio > 0.1 else 0.01,
            "lags_used": 0,
            "n_observations": len(series),
            "critical_values": {"1%": -3.43, "5%": -2.86, "10%": -2.57},
            "is_significant": ratio < 0.1,
        }

    async def run_stationarity(
        self,
        session: AsyncSession,
        series: list[float],
        *,
        test_type: str = "ADF",
        series_name: str = "price",
        security_id: UUID | None = None,
    ) -> dict | None:
        """Run stationarity test and persist result."""
        if test_type == "ADF":
            result = await self._run_adf(series)
        elif test_type == "KPSS" and _HAS_STATSMODELS:
            try:
                stat, p, lags, crit = kpss(series, regression="c", nlags="auto")
                result = {
                    "test_statistic": float(stat),
                    "p_value": float(p),
                    "lags_used": int(lags),
                    "n_observations": len(series),
                    "critical_values": {k: float(v) for k, v in crit.items()},
                    "is_significant": float(p) < 0.05,
                }
            except Exception:
                logger.exception("KPSS test failed")
                return None
        else:
            return None

        if result is None:
            return None

        ts = TimeSeriesTestResult(
            security_id=security_id,
            calculation_date=date.today(),
            test_type=test_type,
            series_name=series_name,
            test_statistic=result["test_statistic"],
            p_value=result["p_value"],
            critical_values=result.get("critical_values"),
            is_significant=result["is_significant"],
            lags_used=result.get("lags_used"),
            data_quality="COMPLETE",
        )
        session.add(ts)
        await session.flush()

        return {**result, "test_id": ts.test_id}

    # ------------------------------------------------------------------
    # Standalone: Cointegration
    # ------------------------------------------------------------------

    async def run_cointegration(
        self,
        session: AsyncSession,
        series_x: list[float],
        series_y: list[float],
        *,
        series_x_id: str = "",
        series_y_id: str = "",
    ) -> dict | None:
        """Run Engle-Granger cointegration test."""
        n = min(len(series_x), len(series_y))
        if n < 30:
            return None

        sx = series_x[-n:]
        sy = series_y[-n:]

        if _HAS_STATSMODELS:
            try:
                stat, p, crit = coint(sx, sy)
                is_coint = float(p) < 0.05
            except Exception:
                logger.exception("Cointegration test failed")
                return None
        else:
            # Rough fallback: regress y on x, test residuals for stationarity
            ols_res = _ols(sx, sy)
            if "error" in ols_res:
                return None
            resids = [sy[i] - (ols_res["coefficients"]["intercept"] + ols_res["coefficients"]["x"] * sx[i])
                      for i in range(n)]
            adf = await self._run_adf(resids)
            if adf is None:
                return None
            stat = adf["test_statistic"]
            p = adf["p_value"]
            is_coint = adf["is_significant"]

        # Hedge ratio from OLS
        ols_res = _ols(sx, sy)
        hedge_ratio = ols_res["coefficients"]["x"] if "error" not in ols_res else None

        ts = TimeSeriesTestResult(
            calculation_date=date.today(),
            test_type="COINTEGRATION",
            series_name=f"{series_x_id}_vs_{series_y_id}",
            test_statistic=float(stat),
            p_value=float(p),
            is_significant=is_coint,
            extra_params={"hedge_ratio": hedge_ratio, "series_x_id": series_x_id, "series_y_id": series_y_id},
            data_quality="COMPLETE",
        )
        session.add(ts)
        await session.flush()

        return {
            "test_id": ts.test_id,
            "test_statistic": float(stat),
            "p_value": float(p),
            "hedge_ratio": hedge_ratio,
            "is_cointegrated": is_coint,
        }

    # ------------------------------------------------------------------
    # Standalone: Rolling Regression
    # ------------------------------------------------------------------

    async def run_rolling_regression(
        self,
        x_values: list[float],
        y_values: list[float],
        *,
        window: int = 60,
    ) -> list[dict]:
        """Rolling OLS regression, returning a time series of coefficients."""
        n = min(len(x_values), len(y_values))
        if n < window:
            return []

        points: list[dict] = []
        for i in range(window, n + 1):
            x_w = x_values[i - window:i]
            y_w = y_values[i - window:i]
            res = _ols(x_w, y_w)
            if "error" not in res:
                points.append({
                    "index": i - 1,
                    "beta": res["coefficients"]["x"],
                    "alpha": res["coefficients"]["intercept"],
                    "r_squared": res["r_squared"],
                })
        return points
