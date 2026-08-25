"""Portfolio Risk Batch (Pillar 4): VaR, concentration, factor exposure,
security-level attribution, and compliance results for every portfolio.

Gap (DEEP_AUDIT_2026-07-16 Dimension 2/3, item 2 + 53): ``attribution_engine``,
``portfolio_risk_engine`` (VaR/concentration/factor exposure), and
``compliance_engine`` are all correct pure-computation modules with real math,
but nothing ever called them outside of the on-demand stress-test endpoints
-- their tables (``portfolio_var_snapshots``, ``concentration_analyses``,
``factor_exposure_snapshots``, ``attribution_results``, ``compliance_results``)
had zero writers, so every read endpoint for those metrics returned empty/None
forever, no matter how healthy the underlying engines were.

This script computes real snapshots from real data for every portfolio with
open positions:

* Concentration -- HHI/top-N/sector-industry-country breakdown from current
  position weights (``portfolio_risk_engine.analyze_concentration``).
* VaR -- variance-covariance decomposition using each holding's own
  historical VaR (the already-scheduled E5 ``var_historical_95_1d``
  AnalyticsResult metric) and a real pairwise return correlation matrix
  built from EODPrice history (``portfolio_risk_engine.calculate_portfolio_var``).
* Factor exposure -- weighted-average portfolio exposure to
  value/growth/momentum/quality/size/low_vol, using real cross-sectional
  z-scores of each factor's AnalyticsResult metrics (the same metric-name
  mapping used by ``GET /v2/analytics/correlation``'s factor performance)
  computed across the "coverage universe" of securities actually held by
  any portfolio in this run. There is no benchmark-constituent factor data
  anywhere in this system (Benchmark is a bare ETF-proxy ticker with no
  constituent weights), so benchmark/active exposures are left null rather
  than fabricated -- only the portfolio's own exposures are real here.
* Attribution -- security-level return contribution
  (``attribution_engine.compute_security_contribution``) using each
  holding's period return from EODPrice and its current NAV weight. Full
  Brinson sector attribution needs benchmark sector composition, which
  (for the same reason as factor exposure) doesn't exist in this system,
  so ``sector_detail``/``factor_detail`` are left null -- an honest gap,
  not a fabricated Brinson split.
* Compliance results -- evaluates every active ``ComplianceRule`` via
  ``compliance_engine.evaluate_all_rules`` against current positions, using
  the already-scheduled composite financial-strength score (QUALITY),
  latest P/E (VALUATION), and this run's own VaR + weighted beta (RISK) as
  context, and persists one ``ComplianceResult`` row per rule per day.

Drift is deliberately NOT computed here: ``POST .../drift/target``
(src/api/routers/portfolio_risk.py) now computes and persists a real
DriftSnapshot the moment a target allocation is set, and this script has no
independent target-allocation input to drift against.

Usage:
    python -m scripts.run_portfolio_risk_batch
    python -m scripts.run_portfolio_risk_batch --portfolio-id <uuid>
    python -m scripts.run_portfolio_risk_batch --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import math
import statistics
import sys
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.routers.analytics import _FACTOR_METRICS, _INVERT_FOR_SCORING
from src.api.routers.portfolio_risk import load_position_dicts_with_classification
from src.database import get_session_factory
from src.engines import attribution_engine, compliance_engine, portfolio_risk_engine
from src.engines.e7_quant import _align_return_series, _load_price_series, _prices_to_return_series
from src.models.analytics import AnalyticsResult, CompositeScore
from src.models.attribution import AttributionResult
from src.models.compliance import ComplianceResult, ComplianceRule
from src.models.portfolio import Portfolio
from src.models.portfolio_risk import ConcentrationAnalysis, FactorExposureSnapshot, PortfolioVarSnapshot
from src.models.security import EODPrice

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("run_portfolio_risk_batch")

# Portfolio-risk factor names (portfolio_risk_engine.FACTORS) mapped to the
# analytics-router factor names their AnalyticsResult metrics are filed
# under. "low_vol" is the sign-flipped counterpart of "volatility" -- a low
# realized-volatility/beta security should score HIGH on low_vol, not high
# on volatility.
_PORTFOLIO_FACTOR_TO_PERF_FACTOR = {
    "value": "value",
    "growth": "growth",
    "momentum": "momentum",
    "quality": "quality",
    "size": "size",
    "low_vol": "volatility",
}
_INVERT_EXPOSURE = {"low_vol"}

VAR_LOOKBACK_DAYS = 400  # buffer past the 252-trading-day window for weekends/holidays


async def _price_on_or_after(session: AsyncSession, security_id, d: date) -> float | None:
    row = (
        await session.execute(
            select(EODPrice.close_adjusted, EODPrice.close)
            .where(EODPrice.security_id == security_id, EODPrice.price_date >= d)
            .order_by(EODPrice.price_date.asc())
            .limit(1)
        )
    ).first()
    if row is None:
        return None
    px = float(row[0] or row[1] or 0)
    return px if px > 0 else None


async def _price_on_or_before(session: AsyncSession, security_id, d: date) -> float | None:
    row = (
        await session.execute(
            select(EODPrice.close_adjusted, EODPrice.close)
            .where(EODPrice.security_id == security_id, EODPrice.price_date <= d)
            .order_by(EODPrice.price_date.desc())
            .limit(1)
        )
    ).first()
    if row is None:
        return None
    px = float(row[0] or row[1] or 0)
    return px if px > 0 else None


# ── Concentration ────────────────────────────────────────────────────────


async def _upsert_concentration(
    session: AsyncSession, portfolio_id: uuid.UUID, today: date, positions: list[dict], nav: float
) -> None:
    if nav <= 0 or not positions:
        return
    engine_positions = [
        {
            "ticker": p["ticker"],
            "weight": p["market_value"] / nav,
            "sector": p["sector"],
            "industry": p["industry"],
            "country": p["country"],
            "market_value": p["market_value"],
        }
        for p in positions
    ]
    result = portfolio_risk_engine.analyze_concentration(engine_positions)

    existing = (
        await session.execute(
            select(ConcentrationAnalysis).where(
                ConcentrationAnalysis.portfolio_id == portfolio_id,
                ConcentrationAnalysis.snapshot_date == today,
            )
        )
    ).scalar_one_or_none()
    row = existing or ConcentrationAnalysis(id=uuid.uuid4(), portfolio_id=portfolio_id, snapshot_date=today)
    row.hhi_position = Decimal(str(round(result.hhi_position, 4)))
    row.hhi_sector = Decimal(str(round(result.hhi_sector, 4)))
    row.hhi_industry = Decimal(str(round(result.hhi_industry, 4)))
    row.largest_position_weight = Decimal(str(round(result.largest_position_weight, 4)))
    row.top_5_weight = Decimal(str(round(result.top_5_weight, 4)))
    row.top_10_weight = Decimal(str(round(result.top_10_weight, 4)))
    row.effective_num_positions = Decimal(str(round(result.effective_num_positions, 2)))
    row.concentration_classification = result.classification
    row.sector_detail = result.sector_detail
    row.industry_detail = result.industry_detail
    row.geographic_detail = result.geographic_detail
    row.flags = {"flags": result.flags}
    if not existing:
        session.add(row)


# ── VaR ──────────────────────────────────────────────────────────────────


def _pearson_corr(x: list[float], y: list[float]) -> float:
    n = len(x)
    if n < 2:
        return 0.0
    mean_x, mean_y = sum(x) / n, sum(y) / n
    cov = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    var_x = sum((v - mean_x) ** 2 for v in x)
    var_y = sum((v - mean_y) ** 2 for v in y)
    denom = math.sqrt(var_x * var_y)
    return cov / denom if denom > 0 else 0.0


async def _build_var_inputs(
    session: AsyncSession,
    positions: list[dict],
    return_cache: dict,
) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    """Individual VaRs (from the already-scheduled E5 metric) and a real
    pairwise return-correlation matrix (from EODPrice history) for the
    positions' securities.
    """
    tickers_by_sec = {p["security_id"]: p["ticker"] for p in positions if p["security_id"] is not None}

    individual_vars: dict[str, float] = {}
    if tickers_by_sec:
        rows = (
            await session.execute(
                select(AnalyticsResult.security_id, AnalyticsResult.value, AnalyticsResult.as_of_date)
                .where(
                    AnalyticsResult.security_id.in_(list(tickers_by_sec.keys())),
                    AnalyticsResult.metric_name == "var_historical_95_1d",
                )
                .order_by(AnalyticsResult.as_of_date.desc())
            )
        ).all()
        seen: set = set()
        for sec_id, value, _as_of in rows:
            if sec_id in seen or value is None:
                continue
            seen.add(sec_id)
            individual_vars[tickers_by_sec[sec_id]] = float(value)

    # Pairwise return correlation from EODPrice, reusing the same
    # date-joined return-series helpers e7_quant uses for security/
    # benchmark beta so a calendar gap between two securities' price
    # histories can't silently misalign their returns.
    return_series: dict[str, list[tuple[date, float]]] = {}
    for sec_id, ticker in tickers_by_sec.items():
        if sec_id not in return_cache:
            dates, prices = await _load_price_series(session, sec_id, VAR_LOOKBACK_DAYS)
            return_cache[sec_id] = _prices_to_return_series(dates, prices)
        return_series[ticker] = return_cache[sec_id]

    correlation_matrix: dict[str, dict[str, float]] = {}
    tickers = list(return_series.keys())
    for i, ti in enumerate(tickers):
        correlation_matrix[ti] = {ti: 1.0}
        for tj in tickers[i + 1 :]:
            a, b = _align_return_series(return_series[ti], return_series[tj])
            rho = _pearson_corr(a, b) if len(a) >= 20 else 0.0
            correlation_matrix[ti][tj] = rho
            correlation_matrix.setdefault(tj, {})[ti] = rho

    return individual_vars, correlation_matrix


async def _upsert_var(
    session: AsyncSession,
    portfolio_id: uuid.UUID,
    today: date,
    positions: list[dict],
    nav: float,
    return_cache: dict,
) -> portfolio_risk_engine.VaRResult | None:
    if nav <= 0 or not positions:
        return None

    weights = {p["ticker"]: p["market_value"] / nav for p in positions}
    individual_vars, correlation_matrix = await _build_var_inputs(session, positions, return_cache)
    if not individual_vars:
        # No E5 VaR coverage for any holding yet (e.g. brand-new securities
        # awaiting their first analytics_risk_var run) -- an honest gap,
        # not a zero-VaR portfolio.
        return None

    result = portfolio_risk_engine.calculate_portfolio_var(weights, individual_vars, correlation_matrix, nav)

    existing = (
        await session.execute(
            select(PortfolioVarSnapshot).where(
                PortfolioVarSnapshot.portfolio_id == portfolio_id,
                PortfolioVarSnapshot.snapshot_date == today,
            )
        )
    ).scalar_one_or_none()
    # VaR is expressed as its dollar P&L impact (negative = loss), matching
    # this codebase's stress-test convention (PortfolioStressTestResult.
    # total_pnl_dollar) -- the engine itself returns positive loss
    # *magnitudes*, so the headline/component figures are negated on the
    # way in. marginal_var/incremental_var keep the engine's own sign: they
    # are sensitivities ("does adding to this position increase or decrease
    # portfolio VaR"), not P&L, and forcing them negative would invert a
    # position's hedge/risk-adding meaning.
    row = existing or PortfolioVarSnapshot(id=uuid.uuid4(), portfolio_id=portfolio_id, snapshot_date=today)
    row.var_1d_95 = Decimal(str(round(-result.var_1d_95 * nav, 4)))
    row.var_1d_99 = Decimal(str(round(-result.var_1d_99 * nav, 4)))
    row.var_10d_95 = Decimal(str(round(-result.var_10d_95 * nav, 4)))
    row.var_10d_99 = Decimal(str(round(-result.var_10d_99 * nav, 4)))
    row.undiversified_var = Decimal(str(round(-result.undiversified_var * nav, 4)))
    row.diversification_ratio = Decimal(str(round(result.diversification_ratio, 4)))
    row.marginal_var = {k: round(v * nav, 2) for k, v in result.marginal_var.items()}
    row.component_var = {k: round(-v * nav, 2) for k, v in result.component_var.items()}
    row.incremental_var = {k: round(v * nav, 2) for k, v in result.incremental_var.items()}
    row.portfolio_nav = Decimal(str(round(nav, 2)))
    row.method = "HISTORICAL"
    if not existing:
        session.add(row)
    return result


# ── Factor exposure ─────────────────────────────────────────────────────


async def build_factor_zscore_universe(
    session: AsyncSession, security_ids: list,
) -> dict[str, dict]:
    """Cross-sectional z-scores per factor across every security held by
    any portfolio in this run -- the real, currently-investable coverage
    universe, not a fabricated benchmark population.
    """
    if not security_ids:
        return {}

    all_metric_names = sorted({m for names in _FACTOR_METRICS.values() for m in names})
    rows = (
        await session.execute(
            select(AnalyticsResult.security_id, AnalyticsResult.metric_name, AnalyticsResult.value)
            .where(
                AnalyticsResult.security_id.in_(security_ids),
                AnalyticsResult.metric_name.in_(all_metric_names),
            )
            .order_by(AnalyticsResult.as_of_date.desc())
        )
    ).all()

    latest: dict[tuple, float] = {}
    seen: set = set()
    for sec_id, metric_name, value in rows:
        key = (sec_id, metric_name)
        if key in seen or value is None:
            continue
        seen.add(key)
        latest[key] = float(value)

    raw_scores: dict[str, dict] = {}
    for factor, metric_names in _FACTOR_METRICS.items():
        per_sec: dict = {}
        for sec_id in security_ids:
            vals = [
                (-v if m in _INVERT_FOR_SCORING else v)
                for m in metric_names
                if (v := latest.get((sec_id, m))) is not None
            ]
            if vals:
                per_sec[sec_id] = sum(vals) / len(vals)
        raw_scores[factor] = per_sec

    zscores: dict[str, dict] = {}
    for factor, per_sec in raw_scores.items():
        vals = list(per_sec.values())
        if len(vals) < 2:
            zscores[factor] = {}
            continue
        mean = statistics.fmean(vals)
        stdev = statistics.pstdev(vals)
        zscores[factor] = (
            {sid: 0.0 for sid in per_sec} if stdev == 0
            else {sid: (v - mean) / stdev for sid, v in per_sec.items()}
        )
    return zscores


async def _upsert_factor_exposure(
    session: AsyncSession,
    portfolio_id: uuid.UUID,
    today: date,
    positions: list[dict],
    nav: float,
    factor_zscores: dict[str, dict],
) -> None:
    if nav <= 0 or not positions:
        return

    engine_positions = []
    for p in positions:
        exposures = {}
        for pf_factor, perf_factor in _PORTFOLIO_FACTOR_TO_PERF_FACTOR.items():
            z = factor_zscores.get(perf_factor, {}).get(p["security_id"], 0.0)
            exposures[pf_factor] = -z if pf_factor in _INVERT_EXPOSURE else z
        engine_positions.append({
            "ticker": p["ticker"],
            "weight": p["market_value"] / nav,
            "factor_exposures": exposures,
        })

    # Prior snapshots (own portfolio-side exposures only) for drift detection.
    hist_rows = (
        await session.execute(
            select(FactorExposureSnapshot)
            .where(FactorExposureSnapshot.portfolio_id == portfolio_id)
            .order_by(FactorExposureSnapshot.snapshot_date.desc())
            .limit(10)
        )
    ).scalars().all()
    historical_exposures = [
        {
            "date": h.snapshot_date.isoformat(),
            "exposures": {
                "value": float(h.value_exposure or 0),
                "growth": float(h.growth_exposure or 0),
                "momentum": float(h.momentum_exposure or 0),
                "quality": float(h.quality_exposure or 0),
                "size": float(h.size_exposure or 0),
                "low_vol": float(h.low_vol_exposure or 0),
            },
        }
        for h in hist_rows
    ]

    result = portfolio_risk_engine.compute_factor_exposures(
        engine_positions, benchmark_positions=None, historical_exposures=historical_exposures,
    )
    # No benchmark-constituent factor data exists anywhere in this system,
    # so benchmark_exp is the engine's own all-zero default for
    # benchmark_positions=None -- persisting that as "benchmark exposure"
    # would misrepresent an absence of data as a real market-neutral
    # reading. Only the portfolio's own (real) exposures are stored; drift
    # flags (which only compare the portfolio to its own history) survive,
    # the ">0.5 active exposure" flag (which needs a real benchmark) doesn't.
    drift_flags = [f for f in result.unintended_flags if "drift" in f.get("message", "").lower()]

    existing = (
        await session.execute(
            select(FactorExposureSnapshot).where(
                FactorExposureSnapshot.portfolio_id == portfolio_id,
                FactorExposureSnapshot.snapshot_date == today,
            )
        )
    ).scalar_one_or_none()
    row = existing or FactorExposureSnapshot(id=uuid.uuid4(), portfolio_id=portfolio_id, snapshot_date=today)
    row.value_exposure = Decimal(str(round(result.portfolio_exposures["value"], 4)))
    row.growth_exposure = Decimal(str(round(result.portfolio_exposures["growth"], 4)))
    row.momentum_exposure = Decimal(str(round(result.portfolio_exposures["momentum"], 4)))
    row.quality_exposure = Decimal(str(round(result.portfolio_exposures["quality"], 4)))
    row.size_exposure = Decimal(str(round(result.portfolio_exposures["size"], 4)))
    row.low_vol_exposure = Decimal(str(round(result.portfolio_exposures["low_vol"], 4)))
    row.unintended_flags = {"flags": drift_flags}
    if not existing:
        session.add(row)


# ── Attribution (security-level contribution) ───────────────────────────


async def _upsert_attribution(
    session: AsyncSession, portfolio: Portfolio, today: date, positions: list[dict], nav: float,
) -> None:
    if nav <= 0 or not positions:
        return

    period_start = today.replace(day=1)

    engine_positions = []
    for p in positions:
        if p["security_id"] is None:
            continue
        start_px = await _price_on_or_after(session, p["security_id"], period_start)
        end_px = await _price_on_or_before(session, p["security_id"], today)
        if start_px is None or end_px is None:
            continue
        # Simplification: weight is TODAY's weight, not the period-average
        # weight (no intraperiod weight history is stored) -- the same
        # kind of documented approximation link_multi_period_attribution
        # already makes for multi-period linking.
        engine_positions.append({
            "ticker": p["ticker"],
            "weight": p["market_value"] / nav,
            "return": (end_px - start_px) / start_px,
        })
    if not engine_positions:
        return

    contributions = attribution_engine.compute_security_contribution(engine_positions)
    total_portfolio_return = sum(c.contribution for c in contributions)

    total_benchmark_return = None
    if portfolio.benchmark_id:
        from src.api.routers.portfolio_performance import _resolve_benchmark_security_id

        bench_id = await _resolve_benchmark_security_id(session, portfolio.benchmark_id)
        if bench_id is not None:
            b_start = await _price_on_or_after(session, bench_id, period_start)
            b_end = await _price_on_or_before(session, bench_id, today)
            if b_start is not None and b_end is not None:
                total_benchmark_return = (b_end - b_start) / b_start

    security_detail = [
        {"ticker": c.ticker, "weight": c.weight, "return": c.security_return, "contribution": c.contribution}
        for c in contributions
    ]

    existing = (
        await session.execute(
            select(AttributionResult).where(
                AttributionResult.portfolio_id == portfolio.id,
                AttributionResult.period_start == period_start,
                AttributionResult.period_end == today,
            )
        )
    ).scalar_one_or_none()
    row = existing or AttributionResult(
        id=uuid.uuid4(), portfolio_id=portfolio.id, period_start=period_start, period_end=today,
    )
    # SECURITY: only real per-security contribution is computed here.
    # Brinson sector attribution needs benchmark sector composition, which
    # doesn't exist in this system -- sector_detail/factor_detail stay
    # null (an honest gap) rather than fabricated.
    row.attribution_type = "SECURITY"
    row.total_portfolio_return = Decimal(str(round(total_portfolio_return, 8)))
    row.total_benchmark_return = (
        Decimal(str(round(total_benchmark_return, 8))) if total_benchmark_return is not None else None
    )
    row.total_active_return = (
        Decimal(str(round(total_portfolio_return - total_benchmark_return, 8)))
        if total_benchmark_return is not None else None
    )
    row.security_detail = security_detail
    if not existing:
        session.add(row)


# ── Compliance results ───────────────────────────────────────────────────


def _rule_to_dict(rule: ComplianceRule) -> dict:
    d = dict(rule.rule_definition or {})
    d["rule_type"] = rule.rule_type
    d["rule_name"] = rule.rule_name
    d["comparison"] = rule.comparison
    d["threshold"] = float(rule.threshold) if rule.threshold is not None else 0.0
    if rule.upper_threshold is not None:
        d["upper_threshold"] = float(rule.upper_threshold)
    d["severity"] = rule.severity or "BREACH"
    return d


async def _upsert_compliance_results(
    session: AsyncSession,
    portfolio_id: uuid.UUID,
    today: date,
    positions: list[dict],
    nav: float,
    var_result: portfolio_risk_engine.VaRResult | None,
) -> None:
    rules = (
        await session.execute(
            select(ComplianceRule).where(
                ComplianceRule.portfolio_id == portfolio_id,
                ComplianceRule.is_active.is_(True),
            )
        )
    ).scalars().all()
    if not rules or nav <= 0 or not positions:
        return

    engine_positions = [
        {"ticker": p["ticker"], "weight": p["market_value"] / nav * 100.0, "sector": p["sector"]}
        for p in positions
    ]

    sec_ids = [p["security_id"] for p in positions if p["security_id"] is not None]
    scores: dict[str, float] = {}
    valuations: dict[str, float] = {}
    if sec_ids:
        tickers_by_sec = {p["security_id"]: p["ticker"] for p in positions if p["security_id"] is not None}
        score_rows = (
            await session.execute(
                select(CompositeScore.security_id, CompositeScore.score_value, CompositeScore.calculation_date)
                .where(CompositeScore.security_id.in_(sec_ids), CompositeScore.score_type == "financial_strength")
                .order_by(CompositeScore.calculation_date.desc())
            )
        ).all()
        seen = set()
        for sec_id, value, _dt in score_rows:
            if sec_id in seen or value is None:
                continue
            seen.add(sec_id)
            scores[tickers_by_sec[sec_id]] = float(value)

        val_rows = (
            await session.execute(
                select(AnalyticsResult.security_id, AnalyticsResult.value, AnalyticsResult.as_of_date)
                .where(AnalyticsResult.security_id.in_(sec_ids), AnalyticsResult.metric_name == "pe_trailing")
                .order_by(AnalyticsResult.as_of_date.desc())
            )
        ).all()
        seen = set()
        for sec_id, value, _dt in val_rows:
            if sec_id in seen or value is None:
                continue
            seen.add(sec_id)
            valuations[tickers_by_sec[sec_id]] = float(value)

    risk_data: dict[str, float] = {}
    if var_result is not None:
        risk_data["var_95"] = var_result.var_1d_95
        weighted_beta = sum((p["market_value"] / nav) * p["beta"] for p in positions)
        risk_data["beta"] = weighted_beta

    summary = compliance_engine.evaluate_all_rules(
        engine_positions, [_rule_to_dict(r) for r in rules],
        {"scores": scores, "valuations": valuations, "risk_data": risk_data},
    )

    for rule, check in zip(rules, summary.results):
        existing = (
            await session.execute(
                select(ComplianceResult).where(
                    ComplianceResult.portfolio_id == portfolio_id,
                    ComplianceResult.rule_id == rule.rule_id,
                    ComplianceResult.check_date == today,
                )
            )
        ).scalar_one_or_none()
        row = existing or ComplianceResult(
            result_id=uuid.uuid4(), portfolio_id=portfolio_id, rule_id=rule.rule_id, check_date=today,
        )
        row.status = check.status
        row.current_value = Decimal(str(round(check.current_value, 6))) if check.current_value is not None else None
        row.threshold_value = Decimal(str(round(check.threshold, 6))) if check.threshold is not None else None
        row.breach_positions = {"breaches": check.breach_positions} if check.breach_positions else None
        row.notes = check.notes
        if not existing:
            session.add(row)


# ── Orchestration ─────────────────────────────────────────────────────────


async def run(dry_run: bool = False, portfolio_id: uuid.UUID | None = None) -> None:
    today = date.today()
    factory = get_session_factory()
    async with factory() as session:
        query = select(Portfolio)
        if portfolio_id is not None:
            query = query.where(Portfolio.id == portfolio_id)
        portfolios = (await session.execute(query)).scalars().all()
        logger.info("Running portfolio risk batch for %d portfolio(s)", len(portfolios))

        # Build the factor z-score coverage universe once across every
        # portfolio's holdings, rather than per-portfolio, both for cost
        # and so two portfolios holding the same security get the same
        # factor exposure for it.
        all_positions: dict = {}
        security_ids: set = set()
        for portfolio in portfolios:
            positions = await load_position_dicts_with_classification(session, portfolio.id)
            all_positions[portfolio.id] = positions
            security_ids.update(p["security_id"] for p in positions if p["security_id"] is not None)

        factor_zscores = await build_factor_zscore_universe(session, list(security_ids))
        return_cache: dict = {}

        processed = 0
        for portfolio in portfolios:
            positions = all_positions[portfolio.id]
            if not positions:
                continue
            try:
                nav = float(portfolio.current_cash or 0.0) + sum(p["market_value"] for p in positions)
                await _upsert_concentration(session, portfolio.id, today, positions, nav)
                var_result = await _upsert_var(session, portfolio.id, today, positions, nav, return_cache)
                await _upsert_factor_exposure(session, portfolio.id, today, positions, nav, factor_zscores)
                await _upsert_attribution(session, portfolio, today, positions, nav)
                await _upsert_compliance_results(session, portfolio.id, today, positions, nav, var_result)
                processed += 1
            except Exception:
                logger.exception("Failed to compute risk snapshots for portfolio %s", portfolio.id)
                continue

        if dry_run:
            await session.rollback()
            logger.info("Dry run: %d portfolio(s) would have been updated (no commit)", processed)
        else:
            await session.commit()
            logger.info("Committed risk snapshots for %d portfolio(s)", processed)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute portfolio risk/attribution/compliance snapshots")
    parser.add_argument("--portfolio-id", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    pid = uuid.UUID(args.portfolio_id) if args.portfolio_id else None
    asyncio.run(run(dry_run=args.dry_run, portfolio_id=pid))


if __name__ == "__main__":
    main()
