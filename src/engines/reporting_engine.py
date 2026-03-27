"""Pillar 4 Phase 2 — Performance & Attribution: Reporting Engine.

Pure computation engine for assembling report data structures and
formatting CSV/XLSX export payloads.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


# ── Dataclasses ─────────────────────────────────────────────────────────


@dataclass
class ReportData:
    """Assembled report data ready for rendering."""
    report_type: str
    metadata: dict
    sections: dict = field(default_factory=dict)


@dataclass
class ExportResult:
    """Result of a report export operation."""
    format: str  # "csv" or "xlsx"
    filename: str
    content: str | dict  # CSV string or XLSX workbook dict
    row_count: int
    column_count: int


# ── Portfolio Summary Report ───────────────────────────────────────────


def build_portfolio_summary_report(
    portfolio: dict,
    positions: list[dict],
    nav: dict,
    performance: dict | None = None,
) -> dict:
    """Build a portfolio summary report.

    portfolio: {id, name, inception_date, strategy, ...}
    positions: [{ticker, shares, market_value, weight, ...}, ...]
    nav: {nav, market_value, cash_balance, unrealized_pnl, ...}
    performance: {twr_return, annualized_return, sharpe_ratio, ...} or None
    """
    summary: dict = {
        "portfolio": {
            "id": portfolio.get("id", ""),
            "name": portfolio.get("name", ""),
            "inception_date": portfolio.get("inception_date", ""),
            "strategy": portfolio.get("strategy", ""),
        },
        "nav": {
            "current_nav": nav.get("nav", 0.0),
            "market_value": nav.get("market_value", 0.0),
            "cash_balance": nav.get("cash_balance", 0.0),
            "unrealized_pnl": nav.get("unrealized_pnl", 0.0),
        },
        "position_count": len(positions),
        "top_holdings": sorted(
            positions, key=lambda p: p.get("weight", 0.0), reverse=True
        )[:10],
    }

    if performance is not None:
        summary["performance"] = {
            "twr_return": performance.get("twr_return", 0.0),
            "annualized_return": performance.get("annualized_return", 0.0),
            "sharpe_ratio": performance.get("sharpe_ratio"),
            "max_drawdown": performance.get("max_drawdown"),
            "volatility": performance.get("volatility"),
        }

    return summary


# ── Performance Report ─────────────────────────────────────────────────


def build_performance_report(
    performance: dict,
    attribution: dict | None = None,
    benchmark_name: str | None = None,
) -> dict:
    """Build a performance report.

    performance: {twr_return, annualized_return, volatility, sharpe_ratio, ...}
    attribution: {total_allocation, total_selection, ...} or None
    """
    report: dict = {
        "returns": {
            "twr_return": performance.get("twr_return", 0.0),
            "annualized_return": performance.get("annualized_return", 0.0),
            "benchmark_return": performance.get("benchmark_return"),
            "active_return": performance.get("active_return"),
        },
        "risk": {
            "volatility": performance.get("volatility", 0.0),
            "sharpe_ratio": performance.get("sharpe_ratio", 0.0),
            "sortino_ratio": performance.get("sortino_ratio"),
            "max_drawdown": performance.get("max_drawdown", 0.0),
            "beta": performance.get("beta"),
            "alpha": performance.get("alpha"),
            "tracking_error": performance.get("tracking_error"),
            "information_ratio": performance.get("information_ratio"),
        },
        "day_stats": {
            "positive_days": performance.get("positive_days", 0),
            "negative_days": performance.get("negative_days", 0),
            "best_day": performance.get("best_day", 0.0),
            "worst_day": performance.get("worst_day", 0.0),
        },
    }

    if benchmark_name is not None:
        report["benchmark_name"] = benchmark_name

    if attribution is not None:
        report["attribution_summary"] = {
            "total_allocation": attribution.get("total_allocation", 0.0),
            "total_selection": attribution.get("total_selection", 0.0),
            "total_interaction": attribution.get("total_interaction", 0.0),
        }

    return report


# ── Attribution Report ─────────────────────────────────────────────────


def build_attribution_report(
    brinson: dict | None = None,
    factor: dict | None = None,
    contributors: dict | None = None,
) -> dict:
    """Build an attribution report.

    brinson: {sector_detail: [...], total_allocation, ...} or None
    factor: {factors: [...], total_factor_return, ...} or None
    contributors: {top: [...], bottom: [...]} or None
    """
    report: dict = {}

    if brinson is not None:
        report["brinson"] = {
            "total_allocation": brinson.get("total_allocation", 0.0),
            "total_selection": brinson.get("total_selection", 0.0),
            "total_interaction": brinson.get("total_interaction", 0.0),
            "residual": brinson.get("residual", 0.0),
            "sector_detail": brinson.get("sector_detail", []),
        }

    if factor is not None:
        report["factor"] = {
            "total_factor_return": factor.get("total_factor_return", 0.0),
            "stock_specific_return": factor.get("stock_specific_return", 0.0),
            "factors": factor.get("factors", []),
        }

    if contributors is not None:
        report["contributors"] = {
            "top": contributors.get("top", []),
            "bottom": contributors.get("bottom", []),
        }

    return report


# ── Holdings Report ────────────────────────────────────────────────────


def build_holdings_report(
    positions: list[dict],
    enrichment: dict | None = None,
) -> dict:
    """Build a holdings report with optional enrichment data.

    positions: [{ticker, shares, market_value, weight, ...}, ...]
    enrichment: {ticker: {sector, name, ...}, ...} or None
    """
    holdings: list[dict] = []
    for pos in positions:
        holding = {
            "ticker": pos.get("ticker", ""),
            "shares": pos.get("shares", 0.0),
            "market_value": pos.get("market_value", 0.0),
            "weight": pos.get("weight", 0.0),
            "cost_basis": pos.get("cost_basis", 0.0),
            "unrealized_pnl": pos.get("unrealized_pnl", 0.0),
        }

        if enrichment and pos.get("ticker") in enrichment:
            enrich = enrichment[pos["ticker"]]
            holding["name"] = enrich.get("name", "")
            holding["sector"] = enrich.get("sector", "")
            holding["industry"] = enrich.get("industry", "")

        holdings.append(holding)

    return {
        "holdings": holdings,
        "total_positions": len(holdings),
        "total_market_value": sum(h["market_value"] for h in holdings),
    }


# ── CSV Formatters ─────────────────────────────────────────────────────


def format_holdings_csv(
    positions: list[dict],
    columns: list[str] | None = None,
) -> str:
    """Format positions into a CSV string with header row.

    If columns is None, use default: [ticker, shares, market_value, weight].
    """
    if columns is None:
        columns = ["ticker", "shares", "market_value", "weight"]

    lines: list[str] = [",".join(columns)]
    for pos in positions:
        row = [str(pos.get(col, "")) for col in columns]
        lines.append(",".join(row))

    return "\n".join(lines)


def format_nav_csv(nav_history: list[dict]) -> str:
    """Format NAV history into CSV.

    Each entry: {date, nav, daily_return, cumulative_return}.
    """
    columns = ["date", "nav", "daily_return", "cumulative_return"]
    lines: list[str] = [",".join(columns)]
    for entry in nav_history:
        row = [str(entry.get(col, "")) for col in columns]
        lines.append(",".join(row))
    return "\n".join(lines)


def format_returns_csv(returns: list[dict]) -> str:
    """Format returns data into CSV.

    Each entry: {period, return, benchmark_return, active_return}.
    """
    columns = ["period", "return", "benchmark_return", "active_return"]
    lines: list[str] = [",".join(columns)]
    for entry in returns:
        row = [str(entry.get(col, "")) for col in columns]
        lines.append(",".join(row))
    return "\n".join(lines)


def format_transactions_csv(transactions: list[dict]) -> str:
    """Format transactions into CSV.

    Each entry: {date, ticker, type, shares, price, amount}.
    """
    columns = ["date", "ticker", "type", "shares", "price", "amount"]
    lines: list[str] = [",".join(columns)]
    for txn in transactions:
        row = [str(txn.get(col, "")) for col in columns]
        lines.append(",".join(row))
    return "\n".join(lines)


# ── XLSX Formatter ─────────────────────────────────────────────────────


def format_xlsx_workbook(sheets: dict) -> dict:
    """Format data into an XLSX workbook structure.

    Input: {sheet_name: {headers: [...], rows: [[...], ...]}}.
    Output: {sheet_name: [[header_row], [row1], [row2], ...]}.
    """
    workbook: dict = {}
    for sheet_name, data in sheets.items():
        headers = data.get("headers", [])
        rows = data.get("rows", [])
        workbook[sheet_name] = [headers] + rows
    return workbook


# ── Report Metadata ────────────────────────────────────────────────────


def compute_report_metadata(
    portfolio_name: str,
    period_start: str,
    period_end: str,
    generated_at: str | None = None,
) -> dict:
    """Compute report metadata.

    Returns dict with portfolio_name, period_start, period_end, generated_at.
    """
    if generated_at is None:
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "portfolio_name": portfolio_name,
        "period_start": period_start,
        "period_end": period_end,
        "generated_at": generated_at,
        "report_version": "1.0",
    }
