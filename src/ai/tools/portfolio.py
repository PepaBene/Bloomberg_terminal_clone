"""Layer 3 (AI_THREE_LAYER_REBUILD_PLAN.md §5.1/§5.2) portfolio-action
tools: the adviser's access to portfolio state, what-if trade simulation,
drift/rebalance analysis, and pre-trade compliance. All wrap
``src/services/portfolio_advisory.py`` -- the exact same code paths
``src/api/routers/portfolio_advisor.py`` exposes directly, so a human
using the API and the adviser reasoning about the same portfolio always
see identical numbers.

Results are rendered as compact text (not raw JSON) -- cheaper in tokens
and easier for the model to reason over inline, matching
``DataQueryTool``'s formatting convention.
"""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.tools.base import BaseTool, ToolResult
from src.services import portfolio_advisory


def _parse_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return None


class PortfolioSnapshotTool(BaseTool):
    """Read a portfolio's current positions, NAV, cash, and latest VaR."""

    name = "portfolio_snapshot"
    description = (
        "Get a portfolio's current holdings: positions (ticker, shares, market value, "
        "weight), total NAV, cash, and the most recent portfolio VaR snapshot if one exists."
    )
    input_schema = {
        "type": "object",
        "properties": {"portfolio_id": {"type": "string", "description": "UUID of the portfolio"}},
        "required": ["portfolio_id"],
    }

    def __init__(self, session: AsyncSession):
        self._session = session

    async def run(self, *, portfolio_id: str) -> ToolResult:
        pid = _parse_uuid(portfolio_id)
        if pid is None:
            return ToolResult(content=f"Invalid portfolio_id: {portfolio_id!r}", is_error=True)

        portfolio = await portfolio_advisory.get_portfolio(self._session, pid)
        if portfolio is None:
            return ToolResult(content=f"No portfolio found with id {portfolio_id}", is_error=True)

        positions = await portfolio_advisory.load_open_positions(self._session, pid)
        nav = portfolio_advisory.portfolio_nav(portfolio, positions)
        risk = await portfolio_advisory.latest_var_95(self._session, pid)

        lines = [
            f"Portfolio: {portfolio.portfolio_name} ({portfolio.portfolio_type}, status={portfolio.status})",
            f"NAV: {nav:,.2f}  Cash: {float(portfolio.current_cash or 0):,.2f}",
        ]
        if risk:
            lines.append(f"Latest VaR (95%, 1-day): {risk['var_95']:,.2f}")
        if not positions:
            lines.append("No open positions.")
        else:
            lines.append(f"{len(positions)} open position(s):")
            for p in sorted(positions, key=lambda p: float(p.market_value or 0), reverse=True):
                lines.append(
                    f"  {p.ticker}: {float(p.shares or 0):,.2f} sh, "
                    f"MV={float(p.market_value or 0):,.2f}, weight={float(p.weight or 0)*100:.2f}%"
                )
        return ToolResult(content="\n".join(lines))


class WhatIfTool(BaseTool):
    """Simulate proposed trades' impact on a portfolio."""

    name = "whatif_trade_impact"
    description = (
        "Simulate the impact of proposed trades on a portfolio's position weights, risk "
        "(VaR/volatility/beta), compliance rules, and transaction costs -- BEFORE "
        "recommending them. Always run this on any trade you're about to propose."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "portfolio_id": {"type": "string", "description": "UUID of the portfolio"},
            "trades": {
                "type": "array",
                "description": "Proposed trades to simulate",
                "items": {
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string"},
                        "action": {"type": "string", "description": "BUY or SELL"},
                        "shares": {"type": "number"},
                        "price_per_share": {"type": "number"},
                    },
                    "required": ["ticker", "action", "shares", "price_per_share"],
                },
            },
        },
        "required": ["portfolio_id", "trades"],
    }

    def __init__(self, session: AsyncSession):
        self._session = session

    async def run(self, *, portfolio_id: str, trades: list[dict]) -> ToolResult:
        pid = _parse_uuid(portfolio_id)
        if pid is None:
            return ToolResult(content=f"Invalid portfolio_id: {portfolio_id!r}", is_error=True)

        result = await portfolio_advisory.compute_whatif(self._session, pid, trades)
        if result is None:
            return ToolResult(content=f"No portfolio found with id {portfolio_id}", is_error=True)

        lines = ["Position impact:"]
        for pi in result.position_impacts:
            lines.append(
                f"  {pi.ticker}: weight {pi.current_weight:.2f}% -> {pi.proposed_weight:.2f}% "
                f"({pi.weight_change:+.2f}pp)"
            )
        r = result.risk_impact
        lines.append(
            f"Risk: VaR95 {r.current_var_95:,.2f} -> {r.proposed_var_95:,.2f} "
            f"({r.var_change:+,.2f}), beta {r.current_beta:.2f} -> {r.proposed_beta:.2f}"
        )
        if result.compliance_impacts:
            lines.append("Compliance:")
            for ci in result.compliance_impacts:
                flag = " *** NEW BREACH ***" if ci.breach_introduced else ""
                lines.append(f"  {ci.rule_name}: {ci.current_status} -> {ci.proposed_status}{flag}")
        tc = result.transaction_cost
        lines.append(
            f"Estimated transaction cost: {tc.total_cost:,.2f} "
            f"({tc.cost_pct_of_nav:.3f}% of NAV)"
        )
        return ToolResult(content="\n".join(lines))


class DriftAnalysisTool(BaseTool):
    """Check a portfolio's drift from its target allocation and get
    suggested rebalance trades."""

    name = "portfolio_drift_analysis"
    description = (
        "Check how far a portfolio's current holdings have drifted from its target "
        "allocation, and get suggested rebalance trades to correct it. Requires the "
        "portfolio to already have a target allocation set -- if not, this tool says so."
    )
    input_schema = {
        "type": "object",
        "properties": {"portfolio_id": {"type": "string", "description": "UUID of the portfolio"}},
        "required": ["portfolio_id"],
    }

    def __init__(self, session: AsyncSession):
        self._session = session

    async def run(self, *, portfolio_id: str) -> ToolResult:
        pid = _parse_uuid(portfolio_id)
        if pid is None:
            return ToolResult(content=f"Invalid portfolio_id: {portfolio_id!r}", is_error=True)

        portfolio = await portfolio_advisory.get_portfolio(self._session, pid)
        if portfolio is None:
            return ToolResult(content=f"No portfolio found with id {portfolio_id}", is_error=True)

        analysis = await portfolio_advisory.compute_drift(self._session, pid)
        if analysis is None:
            return ToolResult(content="No target allocation set for this portfolio -- drift is undefined without one.")

        d = analysis.result
        lines = [
            f"Total drift: {d.total_drift_pct:.2f}% ({d.classification}), "
            f"rebalance needed: {d.rebalance_needed}",
        ]
        for pd in d.position_drifts:
            if pd.action_needed != "HOLD":
                lines.append(
                    f"  {pd.ticker}: {pd.current_weight:.2f}% vs target {pd.target_weight:.2f}% "
                    f"-> {pd.action_needed}"
                )
        if analysis.rebalance_trades:
            lines.append("Suggested rebalance trades:")
            for t in analysis.rebalance_trades:
                lines.append(f"  {t['action']} {t['ticker']}: notional {t['notional_amount']:,.2f}")
        return ToolResult(content="\n".join(lines))


class PreTradeComplianceTool(BaseTool):
    """Check a single proposed trade against a portfolio's compliance rules."""

    name = "pretrade_compliance_check"
    description = (
        "Check whether a single proposed trade would violate any of a portfolio's active "
        "compliance rules (position/sector/concentration/leverage limits). Always run this "
        "before finalizing a trade recommendation."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "portfolio_id": {"type": "string", "description": "UUID of the portfolio"},
            "ticker": {"type": "string"},
            "action": {"type": "string", "description": "BUY or SELL"},
            "shares": {"type": "number"},
            "price": {"type": "number"},
        },
        "required": ["portfolio_id", "ticker", "action", "shares", "price"],
    }

    def __init__(self, session: AsyncSession):
        self._session = session

    async def run(self, *, portfolio_id: str, ticker: str, action: str, shares: float, price: float) -> ToolResult:
        pid = _parse_uuid(portfolio_id)
        if pid is None:
            return ToolResult(content=f"Invalid portfolio_id: {portfolio_id!r}", is_error=True)

        result = await portfolio_advisory.check_pretrade_compliance(
            self._session, pid, ticker=ticker, action=action, shares=shares, price=price,
        )
        if result is None:
            return ToolResult(content=f"No portfolio found with id {portfolio_id}", is_error=True)

        if result.approved:
            return ToolResult(content=f"APPROVED: {action} {shares} {ticker} @ {price} passes all active compliance rules.")
        lines = [f"REJECTED: {action} {shares} {ticker} @ {price} violates compliance rules:"]
        for v in result.violations:
            lines.append(f"  [{v['severity']}] {v['rule_name']}: {v['message']}")
        return ToolResult(content="\n".join(lines))
