"""Layer 3 (AI_THREE_LAYER_REBUILD_PLAN.md §5.1): wires the previously-
dormant ``whatif_engine`` / ``drift_engine`` / ``trade_list_engine`` to
real portfolio data, for both direct API endpoints
(``src/api/routers/portfolio_advisor.py``) and Layer-3 agent tools
(``src/ai/tools/portfolio.py``). All four "dark engines" §5.1 refers to
(these three plus ``compliance_engine.py``) are pure computation with zero
production callers as of this phase -- confirmed via survey. Pre-trade
compliance already has a LIVE, tested endpoint
(``portfolio_risk.py::pre_trade_check``) using its own inline rule
evaluation rather than the dormant ``compliance_engine.py`` -- ``
check_pretrade_compliance`` below is that same logic, extracted so both
the existing endpoint and the new adviser tool share one implementation
instead of two copies that could drift apart.

``compute_whatif``'s factor/VaR/correlation dimensions are wired to real
per-security analytics (``AnalyticsResult``'s FACTOR category,
``VaRResult``, and a correlation matrix computed on demand from
``EODPrice`` returns -- see ``_factor_data_for_tickers``/
``_risk_metrics_for_tickers``/``_correlation_matrix_for_tickers`` below),
not guessed placeholders. A ticker with no matching security_id or no
analytics rows yet simply has no entry in these dicts --
``whatif_engine``'s own documented fallbacks (beta defaults to 1.0,
volatility to current portfolio volatility, that ticker excluded from
the parametric VaR sum) already handle that gracefully.

Remaining, still-deliberate gap: ``Position`` has no ``sector`` column,
so drift's sector dimension is skipped.
"""
from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.engines import drift_engine, trade_list_engine, whatif_engine
from src.models.analytics import AnalyticsResult
from src.models.compliance import ComplianceRule, DriftSnapshot
from src.models.portfolio import Portfolio
from src.models.portfolio_risk import PortfolioVarSnapshot
from src.models.position import Position
from src.models.risk import VaRResult
from src.models.security import EODPrice, SecurityIdentifier

# How far back to pull daily prices for the on-demand pairwise correlation
# matrix. Matches e7_quant.py's own lookback convention (its
# ``_load_price_series`` default is 756 trading days / ~3y); this uses a
# shorter, cheaper window since whatif's correlation input only needs to
# be "recent enough to be representative," not a long-horizon factor input.
CORRELATION_LOOKBACK_DAYS = 252
MIN_CORRELATION_OBSERVATIONS = 20


async def get_portfolio(session: AsyncSession, portfolio_id: uuid.UUID) -> Portfolio | None:
    return await session.get(Portfolio, portfolio_id)


async def load_open_positions(session: AsyncSession, portfolio_id: uuid.UUID) -> list[Position]:
    rows = await session.execute(
        select(Position).where(Position.portfolio_id == portfolio_id, Position.status == "OPEN")
    )
    return list(rows.scalars().all())


def position_dicts(
    positions: list[Position],
    *,
    beta_by_ticker: dict[str, float] | None = None,
    volatility_by_ticker: dict[str, float] | None = None,
) -> list[dict]:
    """``Position`` rows -> the shape ``whatif_engine``/``drift_engine``
    expect. ``Position.weight`` is stored as a 0-1 fraction
    (``market_value / nav``, see ``portfolios.py``); these engines expect
    a 0-100 percentage (their own docstrings: "weight is a percentage,
    e.g. 10.0 = 10%") -- this is the one place that unit conversion
    happens, so it isn't silently wrong at every call site.

    ``beta_by_ticker``/``volatility_by_ticker`` are optional and only
    used by ``compute_whatif`` (``estimate_risk_impact`` reads ``beta``/
    ``volatility`` straight off each position dict) -- ``compute_drift``/
    ``build_trade_list`` call this without them, so a missing key per
    position is the normal case there, not an oversight.
    """
    beta_by_ticker = beta_by_ticker or {}
    volatility_by_ticker = volatility_by_ticker or {}
    out = []
    for p in positions:
        d = {
            "ticker": p.ticker,
            "shares": float(p.shares or 0),
            "market_value": float(p.market_value or 0),
            "weight": float(p.weight or 0) * 100.0,
        }
        if p.ticker in beta_by_ticker:
            d["beta"] = beta_by_ticker[p.ticker]
        if p.ticker in volatility_by_ticker:
            d["volatility"] = volatility_by_ticker[p.ticker]
        out.append(d)
    return out


def portfolio_nav(portfolio: Portfolio, positions: list[Position]) -> float:
    total_mv = sum(float(p.market_value or 0) for p in positions)
    return float(portfolio.current_cash or 0) + total_mv


async def latest_var_95(session: AsyncSession, portfolio_id: uuid.UUID) -> dict:
    """Best-effort ``current_risk`` for ``estimate_risk_impact`` -- real
    portfolio-level VaR when a snapshot exists, empty otherwise (the
    engine degrades to a zero-change result gracefully, verified by
    reading its own fallback logic)."""
    snap = (
        await session.execute(
            select(PortfolioVarSnapshot)
            .where(PortfolioVarSnapshot.portfolio_id == portfolio_id)
            .order_by(PortfolioVarSnapshot.snapshot_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if snap is None or snap.var_1d_95 is None:
        return {}
    return {"var_95": float(snap.var_1d_95)}


async def _compliance_rules_for_whatif(session: AsyncSession, portfolio_id: uuid.UUID) -> list[dict]:
    """Real ``ComplianceRule`` rows -> the ``{rule_name, rule_type,
    max_weight, max_sector_weight}`` shape
    ``whatif_engine.check_compliance_impact`` expects (a DIFFERENT shape
    than ``ComplianceRule``'s own ``threshold``/``rule_type`` fields, and
    different again from ``check_pretrade_compliance`` below's rule
    types -- these are two independent pure functions in this codebase
    that were never reconciled with each other). Only POSITION_LIMIT/
    CONCENTRATION_LIMIT (-> ``max_weight``) and SECTOR_LIMIT (->
    ``max_sector_weight``) map cleanly onto what this specific function
    understands; SINGLE_SECURITY_LIMIT/LEVERAGE_LIMIT rules are simply
    not evaluated by it -- harmless, since ``check_pretrade_compliance``
    is the authoritative check for those, and this is whatif's own
    supplementary "would this trade change compliance status" preview.
    """
    rows = (
        await session.execute(
            select(ComplianceRule).where(
                ComplianceRule.portfolio_id == portfolio_id,
                ComplianceRule.is_active.is_(True),
            )
        )
    ).scalars().all()
    out: list[dict] = []
    for r in rows:
        if r.threshold is None:
            continue
        threshold_pct = float(r.threshold) * 100.0
        rule_type = (r.rule_type or "").upper()
        if rule_type in ("POSITION_LIMIT", "CONCENTRATION_LIMIT"):
            out.append({"rule_name": r.rule_name, "rule_type": "POSITION_LIMIT", "max_weight": threshold_pct})
        elif rule_type == "SECTOR_LIMIT":
            out.append({"rule_name": r.rule_name, "rule_type": "SECTOR_LIMIT", "max_sector_weight": threshold_pct})
    return out


async def _resolve_security_ids(
    session: AsyncSession, positions: list[Position], proposed_trades: list[dict],
) -> dict[str, uuid.UUID]:
    """``{ticker: security_id}`` for every ticker a what-if run touches --
    currently-held positions (which already carry ``security_id``) plus
    any newly-traded ticker not currently held, resolved via
    ``SecurityIdentifier`` (TICKER type), the same lookup pattern
    ``e2_wacc.py``'s benchmark-security resolution uses. A ticker that
    can't be resolved either way (unknown symbol, or a held position with
    no ``security_id`` populated) is simply absent from the returned map
    -- every downstream helper here treats that as "no analytics data for
    this ticker," which is factually true, not a bug to work around.
    """
    ticker_to_id: dict[str, uuid.UUID] = {
        p.ticker: p.security_id for p in positions if p.security_id is not None
    }
    unresolved = {
        t.get("ticker") for t in proposed_trades
        if t.get("ticker") and t.get("ticker") not in ticker_to_id
    }
    if unresolved:
        rows = (
            await session.execute(
                select(SecurityIdentifier.identifier_value, SecurityIdentifier.security_id)
                .where(
                    SecurityIdentifier.identifier_type == "TICKER",
                    SecurityIdentifier.identifier_value.in_(unresolved),
                )
            )
        ).all()
        for ticker, security_id in rows:
            ticker_to_id.setdefault(ticker, security_id)
    return ticker_to_id


async def _factor_data_for_tickers(
    session: AsyncSession, ticker_to_security_id: dict[str, uuid.UUID],
) -> dict[str, dict[str, float]]:
    """§whatif factor-impact dimension: real per-security factor loadings
    from ``AnalyticsResult``'s FACTOR category (momentum/low-vol/value/
    size/quality/growth/dividend -- raw ratios, written by
    ``e5_risk.py::_compute_factor_exposures``, not z-scores). A ticker
    with no FACTOR rows yet is simply absent --
    ``estimate_factor_impact`` already excludes it from the weighted
    average rather than erroring.
    """
    out: dict[str, dict[str, float]] = {}
    for ticker, security_id in ticker_to_security_id.items():
        rows = (
            await session.execute(
                select(AnalyticsResult.metric_name, AnalyticsResult.value)
                .where(
                    AnalyticsResult.security_id == security_id,
                    AnalyticsResult.metric_category == "FACTOR",
                )
                .order_by(AnalyticsResult.as_of_date.desc())
            )
        ).all()
        latest: dict[str, float] = {}
        for metric_name, value in rows:
            if value is not None and metric_name not in latest:
                latest[metric_name] = float(value)
        if latest:
            out[ticker] = latest
    return out


async def _risk_metrics_for_tickers(
    session: AsyncSession,
    ticker_to_security_id: dict[str, uuid.UUID],
    market_value_by_ticker: dict[str, float],
) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    """§whatif risk-impact dimension: real per-security VaR/volatility/beta,
    keyed by ticker. Returns ``(individual_vars, volatility, beta)``.

    ``individual_vars`` is in dollar terms (``VaRResult.var_value``, a
    proportional 1-day-95%-VaR ratio, scaled by that ticker's current
    ``market_value``) -- matching ``estimate_risk_impact``'s documented
    "dollar terms or proportional to market value" contract and directly
    comparable to ``current_risk["var_95"]``, which is likewise a dollar
    figure whenever a ``PortfolioVarSnapshot`` exists.

    Filters ``confidence_level`` in Python rather than SQL: it's a
    ``Numeric(4,2)`` column, and comparing the ``Decimal`` SQLAlchemy
    returns against the Python float literal ``0.95`` can be
    False even for the "same" value (0.95 has no exact binary
    representation), so an exact-equality WHERE clause is a real
    footgun here -- a tolerance comparison after fetching sidesteps it.
    """
    individual_vars: dict[str, float] = {}
    volatility: dict[str, float] = {}
    beta: dict[str, float] = {}

    for ticker, security_id in ticker_to_security_id.items():
        var_rows = (
            await session.execute(
                select(VaRResult)
                .where(
                    VaRResult.security_id == security_id,
                    VaRResult.method == "HISTORICAL",
                    VaRResult.holding_period_days == 1,
                )
                .order_by(VaRResult.calculation_date.desc())
                .limit(10)
            )
        ).scalars().all()
        var_row = next(
            (r for r in var_rows if r.confidence_level is not None and abs(float(r.confidence_level) - 0.95) < 0.01),
            None,
        )
        if var_row is not None:
            if var_row.var_value is not None:
                individual_vars[ticker] = float(var_row.var_value) * market_value_by_ticker.get(ticker, 0.0)
            if var_row.annualized_volatility is not None:
                volatility[ticker] = float(var_row.annualized_volatility)

        beta_val = (
            await session.execute(
                select(AnalyticsResult.value)
                .where(
                    AnalyticsResult.security_id == security_id,
                    AnalyticsResult.metric_name == "beta_market",
                )
                .order_by(AnalyticsResult.as_of_date.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if beta_val is not None:
            beta[ticker] = float(beta_val)

    return individual_vars, volatility, beta


async def _returns_by_ticker(
    session: AsyncSession, ticker_to_security_id: dict[str, uuid.UUID],
) -> dict[str, dict[date, float]]:
    """``{ticker: {price_date: daily_return}}`` from ``EODPrice``, for
    pairwise correlation. Keyed by date rather than a plain list so
    ``_pearson_correlation`` can align on the dates two tickers actually
    share -- different securities don't always have the same trading-day
    set (different listing histories, different exchange holidays).
    """
    out: dict[str, dict[date, float]] = {}
    cutoff = date.today() - timedelta(days=int(CORRELATION_LOOKBACK_DAYS * 1.6))
    for ticker, security_id in ticker_to_security_id.items():
        rows = (
            await session.execute(
                select(EODPrice.price_date, EODPrice.close_adjusted, EODPrice.close)
                .where(EODPrice.security_id == security_id, EODPrice.price_date >= cutoff)
                .order_by(EODPrice.price_date)
            )
        ).all()
        prices: list[tuple[date, float]] = []
        for price_date, close_adjusted, close in rows:
            p = float(close_adjusted or close or 0)
            if p > 0:
                prices.append((price_date, p))
        returns: dict[date, float] = {}
        for i in range(1, len(prices)):
            prev_date, prev_price = prices[i - 1]
            cur_date, cur_price = prices[i]
            if prev_price > 0:
                returns[cur_date] = (cur_price - prev_price) / prev_price
        if returns:
            out[ticker] = returns
    return out


def _pearson_correlation(a: dict[date, float], b: dict[date, float]) -> float | None:
    """Pure. Correlation over the dates both return series actually
    share; ``None`` (not 0.0) below ``MIN_CORRELATION_OBSERVATIONS`` --
    too little overlap to be a meaningful estimate, and the caller should
    omit the pair rather than assert a false "uncorrelated" reading.
    """
    shared = sorted(set(a) & set(b))
    if len(shared) < MIN_CORRELATION_OBSERVATIONS:
        return None
    xs = [a[d] for d in shared]
    ys = [b[d] for d in shared]
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    covariance = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x <= 0 or var_y <= 0:
        return None
    return covariance / math.sqrt(var_x * var_y)


async def _correlation_matrix_for_tickers(
    session: AsyncSession, ticker_to_security_id: dict[str, uuid.UUID],
) -> dict[str, dict[str, float]]:
    """§whatif's on-demand pairwise correlation matrix -- computed from
    real ``EODPrice`` returns rather than a systematic stored correlation
    table (none exists in this codebase; ``CorrelationResult`` is only
    ever written on-demand for an arbitrary caller-chosen pair via
    ``POST /v1/quant/correlation``, not for a portfolio's holdings).
    """
    returns = await _returns_by_ticker(session, ticker_to_security_id)
    tickers = list(returns.keys())
    matrix: dict[str, dict[str, float]] = {}
    for i, ticker_a in enumerate(tickers):
        for ticker_b in tickers[i + 1:]:
            corr = _pearson_correlation(returns[ticker_a], returns[ticker_b])
            if corr is None:
                continue
            matrix.setdefault(ticker_a, {})[ticker_b] = corr
            matrix.setdefault(ticker_b, {})[ticker_a] = corr
    return matrix


async def compute_whatif(
    session: AsyncSession, portfolio_id: uuid.UUID, proposed_trades: list[dict],
) -> whatif_engine.WhatIfResult | None:
    """§5.1: ``whatif_engine.run_whatif_analysis`` wired to live portfolio
    data. Returns ``None`` if the portfolio doesn't exist."""
    portfolio = await get_portfolio(session, portfolio_id)
    if portfolio is None:
        return None
    positions = await load_open_positions(session, portfolio_id)
    nav = portfolio_nav(portfolio, positions)
    risk_data = await latest_var_95(session, portfolio_id)
    compliance_rules = await _compliance_rules_for_whatif(session, portfolio_id)

    ticker_to_security_id = await _resolve_security_ids(session, positions, proposed_trades)
    market_value_by_ticker = {p.ticker: float(p.market_value or 0) for p in positions}
    factor_data = await _factor_data_for_tickers(session, ticker_to_security_id)
    individual_vars, volatility_by_ticker, beta_by_ticker = await _risk_metrics_for_tickers(
        session, ticker_to_security_id, market_value_by_ticker,
    )
    correlation_matrix = await _correlation_matrix_for_tickers(session, ticker_to_security_id)

    return whatif_engine.run_whatif_analysis(
        portfolio_id=str(portfolio_id),
        positions=position_dicts(
            positions, beta_by_ticker=beta_by_ticker, volatility_by_ticker=volatility_by_ticker,
        ),
        proposed_trades=proposed_trades,
        portfolio_nav=nav,
        risk_data=risk_data,
        factor_data=factor_data,
        compliance_rules=compliance_rules,
        compliance_context={"risk_data": risk_data},
        individual_vars=individual_vars,
        correlation_matrix=correlation_matrix,
    )


async def _latest_target_allocation(session: AsyncSession, portfolio_id: uuid.UUID) -> dict | None:
    snap = (
        await session.execute(
            select(DriftSnapshot)
            .where(DriftSnapshot.portfolio_id == portfolio_id, DriftSnapshot.target_allocation.isnot(None))
            .order_by(DriftSnapshot.snapshot_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return snap.target_allocation if snap else None


@dataclass(frozen=True)
class DriftAnalysis:
    result: drift_engine.DriftResult
    rebalance_trades: list[dict]
    target_allocation: dict


async def compute_drift(session: AsyncSession, portfolio_id: uuid.UUID) -> DriftAnalysis | None:
    """§5.1: ``drift_engine.analyze_drift`` + ``suggest_rebalance_trades``
    wired to live positions and the portfolio's most recently set target
    allocation (``DriftSnapshot.target_allocation``, set via the existing
    ``POST /v4/portfolios/{id}/drift/target``). Returns ``None`` when the
    portfolio doesn't exist or no target allocation has ever been set --
    drift is undefined without a target to drift from.

    Unlike the existing ``/v4/.../drift`` GET endpoints (which only ever
    read back whatever was last stored -- confirmed via survey that
    nothing in this codebase actually computes and persists real drift
    today), this always computes fresh from current positions.
    """
    portfolio = await get_portfolio(session, portfolio_id)
    if portfolio is None:
        return None
    target_allocation = await _latest_target_allocation(session, portfolio_id)
    if not target_allocation:
        return None

    positions = await load_open_positions(session, portfolio_id)
    nav = portfolio_nav(portfolio, positions)
    current_weights = {p.ticker: float(p.weight or 0) * 100.0 for p in positions}
    target_weights = {k: float(v) for k, v in target_allocation.items()}

    result = drift_engine.analyze_drift(
        current_weights=current_weights, target_weights=target_weights,
        positions=position_dicts(positions), target_sector_weights=None,
        portfolio_nav=nav,
    )
    rebalance_trades = drift_engine.suggest_rebalance_trades(result.position_drifts, nav)
    return DriftAnalysis(result=result, rebalance_trades=rebalance_trades, target_allocation=target_weights)


async def build_trade_list(
    session: AsyncSession, portfolio_id: uuid.UUID, rebalance_trades: list[dict],
) -> trade_list_engine.TradeList | None:
    """§5.1: ``trade_list_engine.generate_trade_list`` wired to live
    positions/prices. ``rebalance_trades`` is typically
    ``compute_drift(...).rebalance_trades`` but callers may pass a custom
    list (e.g. an adviser-proposed rebalance). Prices come from
    ``Position.closing_price`` -- only covers tickers already held; a
    brand-new ticker with no existing position has no price source here.
    """
    portfolio = await get_portfolio(session, portfolio_id)
    if portfolio is None:
        return None
    positions = await load_open_positions(session, portfolio_id)
    nav = portfolio_nav(portfolio, positions)
    prices = {p.ticker: float(p.closing_price) for p in positions if p.closing_price is not None}

    return trade_list_engine.generate_trade_list(
        portfolio_id=str(portfolio_id), portfolio_name=portfolio.portfolio_name,
        rebalance_trades=rebalance_trades, positions=position_dicts(positions),
        prices=prices, portfolio_nav=nav,
    )


@dataclass(frozen=True)
class PreTradeCheckResult:
    approved: bool
    violations: list[dict]
    warnings: list[dict]


async def check_pretrade_compliance(
    session: AsyncSession, portfolio_id: uuid.UUID, *, ticker: str, action: str, shares: float, price: float,
) -> PreTradeCheckResult | None:
    """The same rule evaluation ``portfolio_risk.py::pre_trade_check``
    already runs live in production, extracted so the adviser tool and
    that endpoint share one implementation. Returns ``None`` if the
    portfolio doesn't exist.
    """
    portfolio = await get_portfolio(session, portfolio_id)
    if portfolio is None:
        return None

    rules = (
        await session.execute(
            select(ComplianceRule).where(
                ComplianceRule.portfolio_id == portfolio_id, ComplianceRule.is_active.is_(True),
            )
        )
    ).scalars().all()
    positions = await load_open_positions(session, portfolio_id)

    violations: list[dict] = []
    warnings: list[dict] = []
    trade_value = shares * price
    total_mv = sum(float(p.market_value) for p in positions if p.market_value is not None)
    nav = float(portfolio.current_cash or 0.0) + total_mv
    proposed_nav = nav if nav > 0 else (trade_value if trade_value > 0 else 1.0)
    action_upper = action.upper()

    def _record(rule: ComplianceRule, message: str, *, severity: str | None = None) -> None:
        violations.append({
            "rule_id": str(rule.rule_id), "rule_name": rule.rule_name,
            "rule_type": rule.rule_type, "severity": severity or rule.severity, "message": message,
        })

    for rule in rules:
        if rule.threshold is None:
            continue
        threshold = float(rule.threshold)
        rule_type = (rule.rule_type or "").upper()

        if rule_type == "POSITION_LIMIT":
            if trade_value > threshold:
                _record(rule, f"Trade value {trade_value:.2f} exceeds limit {threshold:.2f}")
        elif rule_type == "SINGLE_SECURITY_LIMIT":
            existing_mv = sum(float(p.market_value) for p in positions if p.ticker == ticker and p.market_value is not None)
            new_mv = existing_mv + (trade_value if action_upper == "BUY" else -trade_value)
            ratio = new_mv / proposed_nav if proposed_nav > 0 else 0.0
            if ratio > threshold:
                _record(rule, f"{ticker} would be {ratio*100:.1f}% of NAV (limit {threshold*100:.1f}%)")
        elif rule_type == "CONCENTRATION_LIMIT":
            weights = [float(p.market_value) for p in positions if p.market_value is not None]
            top = max(weights, default=0.0)
            if action_upper == "BUY":
                top = max(top, trade_value)
            ratio = top / proposed_nav if proposed_nav > 0 else 0.0
            if ratio > threshold:
                _record(rule, f"Largest holding would be {ratio*100:.1f}% of NAV (limit {threshold*100:.1f}%)")
        elif rule_type == "SECTOR_LIMIT":
            sector_target = (rule.rule_definition or {}).get("sector") if isinstance(rule.rule_definition, dict) else None
            if sector_target:
                same_sector_mv = sum(
                    float(p.market_value) for p in positions
                    if p.market_value is not None and (getattr(p, "sector", None) or "").lower() == sector_target.lower()
                )
                ratio = same_sector_mv / proposed_nav if proposed_nav > 0 else 0.0
                if ratio > threshold:
                    _record(rule, f"Sector {sector_target} would be {ratio*100:.1f}% of NAV (limit {threshold*100:.1f}%)")
        elif rule_type == "LEVERAGE_LIMIT":
            cash_after = float(portfolio.current_cash or 0.0)
            if action_upper == "BUY":
                cash_after -= trade_value
            leverage = (proposed_nav - cash_after) / proposed_nav if proposed_nav > 0 else 0.0
            if leverage > threshold:
                _record(rule, f"Leverage would be {leverage*100:.1f}% (limit {threshold*100:.1f}%)")

    return PreTradeCheckResult(approved=len(violations) == 0, violations=violations, warnings=warnings)
