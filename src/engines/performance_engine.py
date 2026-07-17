"""Pillar 4 Phase 2 — Performance & Attribution: Return Calculation Engine.

Pure computation engine for time-weighted returns, money-weighted returns,
risk-adjusted metrics, drawdown analysis, and standard period calculations.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import reduce

# Newton-Raphson search bounds for MWR/IRR. -99% floors out at "lost almost
# everything"; +1000% ceilings guard against the solver diverging/oscillating
# into an absurd rate when cash-flow data is malformed (a data-entry error,
# not a real return, would otherwise blow up the compounding math downstream).
MWR_MIN_RATE = -0.99
MWR_MAX_RATE = 10.0


# ── Dataclasses ─────────────────────────────────────────────────────────


@dataclass
class DrawdownAnalysis:
    """Result of maximum drawdown analysis."""
    max_drawdown: float  # negative percentage
    peak_value: float
    trough_value: float
    peak_index: int
    trough_index: int
    recovery_index: int | None  # None if not yet recovered
    duration_to_trough: int  # days
    duration_to_recovery: int | None


@dataclass
class RiskMetrics:
    """Collection of risk-adjusted performance metrics."""
    sharpe_ratio: float
    sortino_ratio: float
    information_ratio: float | None
    tracking_error: float | None
    calmar_ratio: float
    beta: float | None
    alpha: float | None
    volatility: float
    max_drawdown: float
    up_capture: float | None
    down_capture: float | None
    batting_average: float | None


@dataclass
class PerformanceSummary:
    """Full performance summary for a portfolio."""
    twr_return: float
    mwr_return: float | None
    annualized_return: float
    benchmark_return: float | None
    active_return: float | None
    risk_metrics: RiskMetrics
    drawdown: DrawdownAnalysis
    positive_days: int
    negative_days: int
    best_day: float
    worst_day: float


# ── Return Calculations ────────────────────────────────────────────────


def compute_twr(daily_returns: list[float]) -> float:
    """Compute time-weighted return via geometric linking: prod(1 + r) - 1."""
    if not daily_returns:
        return 0.0
    return reduce(lambda acc, r: acc * (1.0 + r), daily_returns, 1.0) - 1.0


def compute_mwr(
    cash_flows: list[dict],
    final_value: float,
    tolerance: float = 1e-8,
    max_iter: int = 100,
    horizon_days: int = 365,
) -> float:
    """Compute money-weighted return (IRR) using Newton-Raphson.

    Each cash_flow dict: {date_offset: int, amount: float}.
    The final_value is treated as a positive inflow at the horizon.
    Solve for r in: sum(cf_amount / (1+r)^(t/365)) + final_value / (1+r)^(T/365) = 0

    Cash flows: negative = investment (outflow), positive = distribution.
    final_value is the ending portfolio value (positive).
    horizon_days: total days for the investment period (default 365).
    """
    if not cash_flows:
        return 0.0

    max_t = max(cf.get("date_offset", 0) for cf in cash_flows)
    # The terminal date is at least horizon_days or the max cash flow offset
    terminal_t = max(max_t, horizon_days)
    if terminal_t <= 0:
        return 0.0

    # Build full list: cash flows + final value as positive terminal flow
    all_flows = [(cf.get("date_offset", 0), cf["amount"]) for cf in cash_flows]
    all_flows.append((terminal_t, final_value))

    r = 0.05  # initial guess

    for _ in range(max_iter):
        npv = 0.0
        dnpv = 0.0
        for t, amount in all_flows:
            t_years = t / 365.0
            denom = (1.0 + r) ** t_years
            if denom == 0.0:
                continue
            npv += amount / denom
            if t_years != 0.0:
                dnpv -= amount * t_years / ((1.0 + r) ** (t_years + 1.0))

        if abs(dnpv) < 1e-15:
            break

        r_new = r - npv / dnpv

        # Clamp to reasonable range
        r_new = max(MWR_MIN_RATE, min(r_new, MWR_MAX_RATE))

        if abs(r_new - r) < tolerance:
            return r_new

        r = r_new

    return r


def annualize_return(total_return: float, days: int) -> float:
    """Annualize a total return: (1 + r)^(365/days) - 1."""
    if days <= 0:
        return 0.0
    if total_return <= -1.0:
        return -1.0
    return (1.0 + total_return) ** (365.0 / days) - 1.0


# ── Risk Calculations ──────────────────────────────────────────────────


def compute_volatility(daily_returns: list[float], annualize: bool = True) -> float:
    """Compute return volatility (sample standard deviation).

    If annualize=True, multiply by sqrt(252).
    """
    if len(daily_returns) < 2:
        return 0.0
    n = len(daily_returns)
    mean = sum(daily_returns) / n
    variance = sum((r - mean) ** 2 for r in daily_returns) / (n - 1)
    std = math.sqrt(variance)
    if annualize:
        std *= math.sqrt(252)
    return std


def compute_downside_deviation(
    daily_returns: list[float],
    mar: float = 0.0,
) -> float:
    """Compute downside deviation: sqrt(mean(min(r - mar, 0)^2)) * sqrt(252)."""
    if not daily_returns:
        return 0.0
    downside_sq = [min(r - mar, 0.0) ** 2 for r in daily_returns]
    mean_sq = sum(downside_sq) / len(downside_sq)
    return math.sqrt(mean_sq) * math.sqrt(252)


def compute_sharpe_ratio(
    annualized_return: float,
    risk_free_rate: float,
    volatility: float,
) -> float:
    """Sharpe ratio: (annualized_return - risk_free) / volatility."""
    if volatility == 0.0:
        return 0.0
    return (annualized_return - risk_free_rate) / volatility


def compute_sortino_ratio(
    annualized_return: float,
    risk_free_rate: float,
    downside_dev: float,
) -> float:
    """Sortino ratio: (annualized_return - risk_free) / downside_deviation."""
    if downside_dev == 0.0:
        return 0.0
    return (annualized_return - risk_free_rate) / downside_dev


def compute_information_ratio(
    active_return: float,
    tracking_error: float,
) -> float:
    """Information ratio: active_return / tracking_error."""
    if tracking_error == 0.0:
        return 0.0
    return active_return / tracking_error


def compute_tracking_error(active_returns: list[float]) -> float:
    """Tracking error: stdev(active_returns) * sqrt(252)."""
    if len(active_returns) < 2:
        return 0.0
    return compute_volatility(active_returns, annualize=True)


# ── Drawdown Analysis ──────────────────────────────────────────────────


def compute_max_drawdown(nav_series: list[float]) -> DrawdownAnalysis:
    """Compute maximum drawdown from a NAV series.

    Track running peak, compute drawdown at each point, find worst.
    """
    if len(nav_series) < 2:
        return DrawdownAnalysis(
            max_drawdown=0.0,
            peak_value=nav_series[0] if nav_series else 0.0,
            trough_value=nav_series[0] if nav_series else 0.0,
            peak_index=0,
            trough_index=0,
            recovery_index=None,
            duration_to_trough=0,
            duration_to_recovery=None,
        )

    running_peak = nav_series[0]
    peak_idx = 0
    max_dd = 0.0
    best_peak_idx = 0
    worst_trough_idx = 0
    best_peak_val = nav_series[0]
    worst_trough_val = nav_series[0]

    for i, nav in enumerate(nav_series):
        if nav >= running_peak:
            running_peak = nav
            peak_idx = i

        if running_peak > 0:
            dd = (nav - running_peak) / running_peak
        else:
            dd = 0.0

        if dd < max_dd:
            max_dd = dd
            best_peak_idx = peak_idx
            best_peak_val = running_peak
            worst_trough_idx = i
            worst_trough_val = nav

    # Find recovery: first point after trough where NAV >= peak value
    recovery_idx: int | None = None
    for i in range(worst_trough_idx + 1, len(nav_series)):
        if nav_series[i] >= best_peak_val:
            recovery_idx = i
            break

    duration_to_trough = worst_trough_idx - best_peak_idx
    duration_to_recovery = (
        (recovery_idx - best_peak_idx) if recovery_idx is not None else None
    )

    return DrawdownAnalysis(
        max_drawdown=max_dd,
        peak_value=best_peak_val,
        trough_value=worst_trough_val,
        peak_index=best_peak_idx,
        trough_index=worst_trough_idx,
        recovery_index=recovery_idx,
        duration_to_trough=duration_to_trough,
        duration_to_recovery=duration_to_recovery,
    )


def compute_calmar_ratio(annualized_return: float, max_drawdown: float) -> float:
    """Calmar ratio: annualized_return / abs(max_drawdown)."""
    if max_drawdown == 0.0:
        return 0.0
    return annualized_return / abs(max_drawdown)


# ── Benchmark-Relative Metrics ─────────────────────────────────────────


def compute_up_down_capture(
    portfolio_returns: list[float],
    benchmark_returns: list[float],
) -> dict:
    """Compute up-capture and down-capture ratios.

    up_capture = mean(port when bench > 0) / mean(bench when bench > 0)
    down_capture = mean(port when bench < 0) / mean(bench when bench < 0)
    """
    if len(portfolio_returns) != len(benchmark_returns):
        raise ValueError("Portfolio and benchmark return lists must be same length")

    up_port = [p for p, b in zip(portfolio_returns, benchmark_returns) if b > 0]
    up_bench = [b for b in benchmark_returns if b > 0]
    down_port = [p for p, b in zip(portfolio_returns, benchmark_returns) if b < 0]
    down_bench = [b for b in benchmark_returns if b < 0]

    up_capture = None
    if up_bench:
        mean_up_port = sum(up_port) / len(up_port)
        mean_up_bench = sum(up_bench) / len(up_bench)
        if mean_up_bench != 0.0:
            up_capture = mean_up_port / mean_up_bench

    down_capture = None
    if down_bench:
        mean_down_port = sum(down_port) / len(down_port)
        mean_down_bench = sum(down_bench) / len(down_bench)
        if mean_down_bench != 0.0:
            down_capture = mean_down_port / mean_down_bench

    return {"up_capture": up_capture, "down_capture": down_capture}


def compute_batting_average(
    portfolio_returns: list[float],
    benchmark_returns: list[float],
) -> float:
    """Batting average: fraction of periods where portfolio > benchmark."""
    if len(portfolio_returns) != len(benchmark_returns):
        raise ValueError("Portfolio and benchmark return lists must be same length")
    if not portfolio_returns:
        return 0.0
    wins = sum(1 for p, b in zip(portfolio_returns, benchmark_returns) if p > b)
    return wins / len(portfolio_returns)


def compute_beta(
    portfolio_returns: list[float],
    benchmark_returns: list[float],
) -> float:
    """Beta: cov(portfolio, benchmark) / var(benchmark)."""
    if len(portfolio_returns) != len(benchmark_returns):
        raise ValueError("Portfolio and benchmark return lists must be same length")
    n = len(portfolio_returns)
    if n < 2:
        return 0.0

    mean_p = sum(portfolio_returns) / n
    mean_b = sum(benchmark_returns) / n

    cov = sum(
        (p - mean_p) * (b - mean_b)
        for p, b in zip(portfolio_returns, benchmark_returns)
    ) / (n - 1)
    var_b = sum((b - mean_b) ** 2 for b in benchmark_returns) / (n - 1)

    if var_b == 0.0:
        return 0.0
    return cov / var_b


def compute_alpha(
    portfolio_return: float,
    benchmark_return: float,
    beta: float,
    risk_free: float,
) -> float:
    """Jensen's alpha: port - (rf + beta * (bench - rf))."""
    return portfolio_return - (risk_free + beta * (benchmark_return - risk_free))


# ── Rolling & Calendar Returns ─────────────────────────────────────────


def compute_rolling_returns(
    daily_returns: list[float],
    window: int,
) -> list[float]:
    """Compute rolling returns with given window size.

    Each element = geometric product of window-size chunk.
    """
    if window <= 0 or window > len(daily_returns):
        return []
    results = []
    for i in range(len(daily_returns) - window + 1):
        chunk = daily_returns[i : i + window]
        rolling = reduce(lambda acc, r: acc * (1.0 + r), chunk, 1.0) - 1.0
        results.append(rolling)
    return results


def compute_calendar_year_returns(daily_data: list[dict]) -> list[dict]:
    """Compute calendar year returns from daily data.

    Each dict: {date: "YYYY-MM-DD", return: float}.
    Group by year, geometric link. Return [{year: int, return: float}].
    """
    if not daily_data:
        return []

    # Group by year
    by_year: dict[int, list[float]] = {}
    for d in daily_data:
        year = int(d["date"][:4])
        by_year.setdefault(year, []).append(d["return"])

    results = []
    for year in sorted(by_year.keys()):
        returns = by_year[year]
        yr_return = reduce(lambda acc, r: acc * (1.0 + r), returns, 1.0) - 1.0
        results.append({"year": year, "return": yr_return})

    return results


def compute_standard_periods(
    daily_data: list[dict],
    as_of_date: str,
) -> dict:
    """Calculate standard period returns: MTD/QTD/YTD/1M/3M/6M/1Y/3Y/5Y/SI.

    Each daily_data entry: {date: "YYYY-MM-DD", return: float}.
    as_of_date: "YYYY-MM-DD".
    """
    if not daily_data:
        return {
            "mtd": 0.0, "qtd": 0.0, "ytd": 0.0,
            "1m": 0.0, "3m": 0.0, "6m": 0.0,
            "1y": 0.0, "3y": 0.0, "5y": 0.0,
            "si": 0.0,
        }

    # Sort by date
    sorted_data = sorted(daily_data, key=lambda x: x["date"])

    # Parse as_of_date
    ao_year = int(as_of_date[:4])
    ao_month = int(as_of_date[5:7])

    # Determine quarter start month
    quarter_start_month = ((ao_month - 1) // 3) * 3 + 1

    def _filter_from(start_date: str) -> list[float]:
        return [d["return"] for d in sorted_data if start_date <= d["date"] <= as_of_date]

    def _geo_link(returns: list[float]) -> float:
        if not returns:
            return 0.0
        return reduce(lambda acc, r: acc * (1.0 + r), returns, 1.0) - 1.0

    def _subtract_months(year: int, month: int, n_months: int) -> str:
        total_months = year * 12 + (month - 1) - n_months
        new_year = total_months // 12
        new_month = total_months % 12 + 1
        return f"{new_year:04d}-{new_month:02d}-01"

    # MTD: from start of current month
    mtd_start = f"{ao_year:04d}-{ao_month:02d}-01"
    mtd = _geo_link(_filter_from(mtd_start))

    # QTD: from start of current quarter
    qtd_start = f"{ao_year:04d}-{quarter_start_month:02d}-01"
    qtd = _geo_link(_filter_from(qtd_start))

    # YTD: from start of current year
    ytd_start = f"{ao_year:04d}-01-01"
    ytd = _geo_link(_filter_from(ytd_start))

    # Fixed lookback periods
    m1 = _geo_link(_filter_from(_subtract_months(ao_year, ao_month, 1)))
    m3 = _geo_link(_filter_from(_subtract_months(ao_year, ao_month, 3)))
    m6 = _geo_link(_filter_from(_subtract_months(ao_year, ao_month, 6)))
    y1 = _geo_link(_filter_from(_subtract_months(ao_year, ao_month, 12)))
    y3 = _geo_link(_filter_from(_subtract_months(ao_year, ao_month, 36)))
    y5 = _geo_link(_filter_from(_subtract_months(ao_year, ao_month, 60)))

    # Since inception
    si = _geo_link([d["return"] for d in sorted_data if d["date"] <= as_of_date])

    return {
        "mtd": mtd, "qtd": qtd, "ytd": ytd,
        "1m": m1, "3m": m3, "6m": m6,
        "1y": y1, "3y": y3, "5y": y5,
        "si": si,
    }


# ── Full Orchestrator ──────────────────────────────────────────────────


def build_performance_summary(
    nav_history: list[dict],
    benchmark_history: list[dict] | None = None,
    cash_flows: list[dict] | None = None,
    risk_free_rate: float = 0.04,
) -> PerformanceSummary:
    """Build a complete performance summary.

    nav_history: [{date: str, nav: float}, ...] sorted by date.
    benchmark_history: [{date: str, nav: float}, ...] or None.
    cash_flows: [{date_offset: int, amount: float}, ...] or None.
    """
    # Compute daily returns from NAV series
    daily_returns: list[float] = []
    nav_values: list[float] = [entry["nav"] for entry in nav_history]

    for i in range(1, len(nav_values)):
        if nav_values[i - 1] != 0.0:
            daily_returns.append(
                (nav_values[i] - nav_values[i - 1]) / nav_values[i - 1]
            )
        else:
            daily_returns.append(0.0)

    # TWR
    twr = compute_twr(daily_returns)

    # MWR
    mwr: float | None = None
    if cash_flows:
        mwr = compute_mwr(cash_flows, nav_values[-1] if nav_values else 0.0)

    # Annualized
    days = len(daily_returns)
    ann_return = annualize_return(twr, days) if days > 0 else 0.0

    # Volatility
    vol = compute_volatility(daily_returns)

    # Downside deviation
    dd_dev = compute_downside_deviation(daily_returns)

    # Drawdown
    drawdown = compute_max_drawdown(nav_values)

    # Benchmark metrics
    benchmark_return: float | None = None
    active_return: float | None = None
    info_ratio: float | None = None
    te: float | None = None
    beta_val: float | None = None
    alpha_val: float | None = None
    up_cap: float | None = None
    down_cap: float | None = None
    bat_avg: float | None = None

    if benchmark_history and len(benchmark_history) == len(nav_history):
        bench_navs = [entry["nav"] for entry in benchmark_history]
        bench_returns: list[float] = []
        for i in range(1, len(bench_navs)):
            if bench_navs[i - 1] != 0.0:
                bench_returns.append(
                    (bench_navs[i] - bench_navs[i - 1]) / bench_navs[i - 1]
                )
            else:
                bench_returns.append(0.0)

        benchmark_return = compute_twr(bench_returns)
        active_return = twr - benchmark_return

        active_returns = [
            p - b for p, b in zip(daily_returns, bench_returns)
        ]
        te = compute_tracking_error(active_returns)
        ann_bench = annualize_return(benchmark_return, days) if days > 0 else 0.0
        ann_active = ann_return - ann_bench
        info_ratio = compute_information_ratio(ann_active, te)

        beta_val = compute_beta(daily_returns, bench_returns)
        alpha_val = compute_alpha(ann_return, ann_bench, beta_val, risk_free_rate)

        capture = compute_up_down_capture(daily_returns, bench_returns)
        up_cap = capture["up_capture"]
        down_cap = capture["down_capture"]
        bat_avg = compute_batting_average(daily_returns, bench_returns)

    # Sharpe / Sortino / Calmar
    sharpe = compute_sharpe_ratio(ann_return, risk_free_rate, vol)
    sortino = compute_sortino_ratio(ann_return, risk_free_rate, dd_dev)
    calmar = compute_calmar_ratio(ann_return, drawdown.max_drawdown)

    # Day stats
    positive_days = sum(1 for r in daily_returns if r > 0)
    negative_days = sum(1 for r in daily_returns if r < 0)
    best_day = max(daily_returns) if daily_returns else 0.0
    worst_day = min(daily_returns) if daily_returns else 0.0

    risk = RiskMetrics(
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        information_ratio=info_ratio,
        tracking_error=te,
        calmar_ratio=calmar,
        beta=beta_val,
        alpha=alpha_val,
        volatility=vol,
        max_drawdown=drawdown.max_drawdown,
        up_capture=up_cap,
        down_capture=down_cap,
        batting_average=bat_avg,
    )

    return PerformanceSummary(
        twr_return=twr,
        mwr_return=mwr,
        annualized_return=ann_return,
        benchmark_return=benchmark_return,
        active_return=active_return,
        risk_metrics=risk,
        drawdown=drawdown,
        positive_days=positive_days,
        negative_days=negative_days,
        best_day=best_day,
        worst_day=worst_day,
    )
