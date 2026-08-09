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

Known, deliberate gaps (real portfolio data this app doesn't have in an
easily joinable form, not guessed): no per-ticker factor loadings (so
``compute_whatif``'s factor-impact dimension is always empty), no
per-ticker VaR/correlation data (so its risk-impact dimension degrades to
the engine's own "scale by volatility ratio" fallback), and ``Position``
has no ``sector`` column (so drift's sector dimension is skipped).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.engines import drift_engine, trade_list_engine, whatif_engine
from src.models.compliance import ComplianceRule, DriftSnapshot
from src.models.portfolio import Portfolio
from src.models.portfolio_risk import PortfolioVarSnapshot
from src.models.position import Position


async def get_portfolio(session: AsyncSession, portfolio_id: uuid.UUID) -> Portfolio | None:
    return await session.get(Portfolio, portfolio_id)


async def load_open_positions(session: AsyncSession, portfolio_id: uuid.UUID) -> list[Position]:
    rows = await session.execute(
        select(Position).where(Position.portfolio_id == portfolio_id, Position.status == "OPEN")
    )
    return list(rows.scalars().all())


def position_dicts(positions: list[Position]) -> list[dict]:
    """``Position`` rows -> the shape ``whatif_engine``/``drift_engine``
    expect. ``Position.weight`` is stored as a 0-1 fraction
    (``market_value / nav``, see ``portfolios.py``); these engines expect
    a 0-100 percentage (their own docstrings: "weight is a percentage,
    e.g. 10.0 = 10%") -- this is the one place that unit conversion
    happens, so it isn't silently wrong at every call site.
    """
    return [
        {
            "ticker": p.ticker,
            "shares": float(p.shares or 0),
            "market_value": float(p.market_value or 0),
            "weight": float(p.weight or 0) * 100.0,
        }
        for p in positions
    ]


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

    return whatif_engine.run_whatif_analysis(
        portfolio_id=str(portfolio_id),
        positions=position_dicts(positions),
        proposed_trades=proposed_trades,
        portfolio_nav=nav,
        risk_data=risk_data,
        factor_data={},
        compliance_rules=compliance_rules,
        compliance_context={"risk_data": risk_data},
        individual_vars={},
        correlation_matrix={},
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
