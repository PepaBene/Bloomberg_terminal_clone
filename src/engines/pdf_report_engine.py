"""Pillar 4 Module 6 — PDF Report Generation Engine.

Pure computation engine that produces self-contained HTML strings
suitable for rendering to PDF by any library (WeasyPrint, wkhtmltopdf,
Playwright, etc.).

No database access — all functions accept plain data and return
structured results.  HTML templates include inline CSS styled for a
professional Bloomberg-style report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


# ── Dataclasses ─────────────────────────────────────────────────────────


@dataclass
class PDFSection:
    """One logical section of a PDF report."""

    title: str
    content_html: str
    page_break_before: bool = False


@dataclass
class PDFReport:
    """Complete PDF report ready for rendering."""

    report_type: str
    title: str
    subtitle: str
    generated_at: str
    sections: list[PDFSection] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    html_content: str = ""


# ── Internal Helpers / HTML Primitives ──────────────────────────────────


def _css_styles() -> str:
    """Return the full inline CSS for the report.

    Dark professional theme for screen display, clean white for print.
    Uses tabular numerics for aligned columns and system sans-serif.
    """
    return """\
/* ── Reset & Base ───────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html {
    font-size: 10pt;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 Helvetica, Arial, sans-serif;
    color: #e0e0e0;
    background: #1a1a2e;
    line-height: 1.45;
    padding: 24px 32px;
}

/* ── Typography ─────────────────────────────────────────── */
h1 { font-size: 1.8rem; font-weight: 700; margin-bottom: 4px; color: #ffffff; }
h2 { font-size: 1.3rem; font-weight: 600; margin-bottom: 8px; color: #f0f0f0; }
h3 { font-size: 1.1rem; font-weight: 600; margin-bottom: 6px; color: #e8e8e8; }

.subtitle {
    font-size: 1.05rem;
    color: #9e9e9e;
    margin-bottom: 2px;
}

.generated-at {
    font-size: 0.85rem;
    color: #757575;
    margin-bottom: 20px;
}

/* ── Header ─────────────────────────────────────────────── */
.report-header {
    border-bottom: 2px solid #3a3a5c;
    padding-bottom: 16px;
    margin-bottom: 24px;
}

.report-header .logo-placeholder {
    display: inline-block;
    width: 32px;
    height: 32px;
    background: #ff6f00;
    border-radius: 4px;
    vertical-align: middle;
    margin-right: 10px;
}

.report-header .brand-text {
    display: inline-block;
    vertical-align: middle;
    font-size: 0.8rem;
    font-weight: 700;
    letter-spacing: 1.5px;
    color: #ff6f00;
    text-transform: uppercase;
}

.meta-row {
    font-size: 0.8rem;
    color: #757575;
    margin-top: 6px;
}

.meta-row span { margin-right: 18px; }

/* ── Sections ───────────────────────────────────────────── */
.section {
    margin-bottom: 28px;
}

.section-title {
    font-size: 1.15rem;
    font-weight: 600;
    color: #ffffff;
    border-left: 3px solid #ff6f00;
    padding-left: 10px;
    margin-bottom: 12px;
}

.page-break { page-break-before: always; }

/* ── Tables ─────────────────────────────────────────────── */
table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 16px;
    font-variant-numeric: tabular-nums;
}

thead th {
    text-align: left;
    padding: 8px 10px;
    font-size: 0.8rem;
    font-weight: 600;
    color: #b0b0b0;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    border-bottom: 2px solid #3a3a5c;
    background: #16162b;
}

tbody td {
    padding: 7px 10px;
    font-size: 0.88rem;
    font-family: "SF Mono", "Fira Code", "Consolas", monospace;
    border-bottom: 1px solid #2a2a45;
}

tbody tr:nth-child(even) { background: rgba(255,255,255,0.02); }
tbody tr:hover { background: rgba(255,111,0,0.06); }

table caption {
    caption-side: top;
    text-align: left;
    font-size: 0.85rem;
    color: #9e9e9e;
    margin-bottom: 6px;
    font-style: italic;
}

/* ── Metric Cards ───────────────────────────────────────── */
.metrics-row {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    margin-bottom: 18px;
}

.metric-card {
    flex: 1 1 140px;
    max-width: 200px;
    background: #16162b;
    border: 1px solid #3a3a5c;
    border-radius: 6px;
    padding: 12px 14px;
}

.metric-card .label {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: #9e9e9e;
    margin-bottom: 4px;
}

.metric-card .value {
    font-size: 1.25rem;
    font-weight: 700;
    font-family: "SF Mono", "Fira Code", "Consolas", monospace;
    color: #ffffff;
}

.metric-card .change {
    font-size: 0.78rem;
    margin-top: 3px;
}

.metric-card .change.positive { color: #4caf50; }
.metric-card .change.negative { color: #ef5350; }
.metric-card .change.neutral  { color: #9e9e9e; }

/* ── Print Styles ───────────────────────────────────────── */
@media print {
    body {
        background: #ffffff;
        color: #1a1a1a;
        padding: 0;
        font-size: 9pt;
    }

    h1 { color: #1a1a1a; }
    h2, h3 { color: #333333; }
    .subtitle { color: #555555; }
    .generated-at { color: #888888; }

    .report-header { border-bottom-color: #cccccc; }
    .report-header .logo-placeholder { background: #ff6f00; }
    .report-header .brand-text { color: #ff6f00; }

    .section-title {
        color: #1a1a1a;
        border-left-color: #ff6f00;
    }

    thead th {
        background: #f5f5f5;
        color: #333333;
        border-bottom-color: #cccccc;
    }

    tbody td {
        color: #1a1a1a;
        border-bottom-color: #e0e0e0;
    }

    tbody tr:nth-child(even) { background: #fafafa; }
    tbody tr:hover { background: none; }

    .metric-card {
        background: #f8f8f8;
        border-color: #d0d0d0;
    }

    .metric-card .label { color: #666666; }
    .metric-card .value { color: #1a1a1a; }
    .metric-card .change.positive { color: #2e7d32; }
    .metric-card .change.negative { color: #c62828; }

    .meta-row { color: #888888; }
}
"""


def _header_html(
    title: str,
    subtitle: str,
    generated_at: str,
    metadata: dict,
) -> str:
    """Render the report header block with logo placeholder, title, and date."""
    meta_spans = "".join(
        f'<span><strong>{k}:</strong> {v}</span>'
        for k, v in metadata.items()
    )
    return (
        '<div class="report-header">'
        '<div style="margin-bottom:10px;">'
        '<span class="logo-placeholder"></span>'
        '<span class="brand-text">Bloomberg Data Fabric</span>'
        "</div>"
        f"<h1>{_esc(title)}</h1>"
        f'<div class="subtitle">{_esc(subtitle)}</div>'
        f'<div class="generated-at">Generated {_esc(generated_at)}</div>'
        + (f'<div class="meta-row">{meta_spans}</div>' if meta_spans else "")
        + "</div>"
    )


def _table_html(
    headers: list[str],
    rows: list[list[str]],
    caption: str | None = None,
) -> str:
    """Format a data table as an HTML ``<table>`` element.

    *headers* — column names.
    *rows* — list of rows, each row a list of string cell values.
    *caption* — optional caption rendered above the table.
    """
    parts: list[str] = ["<table>"]
    if caption:
        parts.append(f"<caption>{_esc(caption)}</caption>")

    # Header row
    parts.append("<thead><tr>")
    for h in headers:
        parts.append(f"<th>{_esc(h)}</th>")
    parts.append("</tr></thead>")

    # Body rows
    parts.append("<tbody>")
    for row in rows:
        parts.append("<tr>")
        for cell in row:
            parts.append(f"<td>{_esc(str(cell))}</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")

    return "".join(parts)


def _metric_card_html(
    label: str,
    value: str,
    change: str | None = None,
) -> str:
    """Render a single metric card block.

    *change* — optional delta string (e.g. "+2.3%").  If it starts with
    ``-`` it is styled red, ``+`` green, otherwise neutral.
    """
    change_html = ""
    if change is not None:
        if change.startswith("-"):
            cls = "negative"
        elif change.startswith("+"):
            cls = "positive"
        else:
            cls = "neutral"
        change_html = f'<div class="change {cls}">{_esc(change)}</div>'

    return (
        '<div class="metric-card">'
        f'<div class="label">{_esc(label)}</div>'
        f'<div class="value">{_esc(value)}</div>'
        f"{change_html}"
        "</div>"
    )


def _section_html(title: str, content_html: str) -> str:
    """Wrap *content_html* in a titled section block with a left-border divider."""
    return (
        '<div class="section">'
        f'<div class="section-title">{_esc(title)}</div>'
        f"{content_html}"
        "</div>"
    )


def _esc(text: str) -> str:
    """Minimal HTML-escape for safe embedding in templates."""
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ── Formatting Utilities ────────────────────────────────────────────────


def _fmt_number(value: float | int | None, decimals: int = 2) -> str:
    """Format a number with thousand separators and fixed decimals."""
    if value is None:
        return "--"
    return f"{value:,.{decimals}f}"


def _fmt_pct(value: float | None, decimals: int = 2) -> str:
    """Format a value as a percentage string."""
    if value is None:
        return "--"
    return f"{value:,.{decimals}f}%"


def _fmt_currency(value: float | None, decimals: int = 2) -> str:
    """Format a value as a USD currency string."""
    if value is None:
        return "--"
    return f"${value:,.{decimals}f}"


def _change_str(value: float | None, decimals: int = 2, is_pct: bool = True) -> str | None:
    """Return a signed change string like ``+2.35%`` or ``None``."""
    if value is None:
        return None
    sign = "+" if value >= 0 else ""
    suffix = "%" if is_pct else ""
    return f"{sign}{value:,.{decimals}f}{suffix}"


# ── Report Builders ─────────────────────────────────────────────────────


def build_portfolio_summary_pdf(
    portfolio: dict,
    positions: list[dict],
    nav: dict,
    performance: dict | None = None,
) -> PDFReport:
    """Build a portfolio summary PDF report.

    Parameters
    ----------
    portfolio : dict
        ``{name, inception_date, strategy, ...}``
    positions : list[dict]
        ``[{ticker, shares, market_value, weight, sector, unrealized_pnl, ...}]``
    nav : dict
        ``{nav, market_value, cash_balance, unrealized_pnl, ...}``
    performance : dict | None
        ``{twr_return, annualized_return, sharpe_ratio, max_drawdown, ...}``
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    name = portfolio.get("name", "Portfolio")
    sections: list[PDFSection] = []

    # -- Portfolio info header --
    info_html = (
        f'<p><strong>Strategy:</strong> {_esc(str(portfolio.get("strategy", "N/A")))}</p>'
        f'<p><strong>Inception:</strong> {_esc(str(portfolio.get("inception_date", "N/A")))}</p>'
        f'<p><strong>Positions:</strong> {len(positions)}</p>'
    )
    sections.append(PDFSection(title="Portfolio Overview", content_html=info_html))

    # -- NAV metrics --
    nav_cards = '<div class="metrics-row">'
    nav_cards += _metric_card_html("NAV", _fmt_currency(nav.get("nav")))
    nav_cards += _metric_card_html("Market Value", _fmt_currency(nav.get("market_value")))
    nav_cards += _metric_card_html("Cash", _fmt_currency(nav.get("cash_balance")))
    nav_cards += _metric_card_html(
        "Unrealised P&L",
        _fmt_currency(nav.get("unrealized_pnl")),
        change=_change_str(nav.get("unrealized_pnl"), is_pct=False),
    )
    nav_cards += "</div>"
    sections.append(PDFSection(title="NAV Summary", content_html=nav_cards))

    # -- Performance metrics (optional) --
    if performance is not None:
        perf_cards = '<div class="metrics-row">'
        perf_cards += _metric_card_html(
            "TWR Return",
            _fmt_pct(performance.get("twr_return")),
            change=_change_str(performance.get("twr_return")),
        )
        perf_cards += _metric_card_html(
            "Annualised",
            _fmt_pct(performance.get("annualized_return")),
        )
        perf_cards += _metric_card_html(
            "Sharpe Ratio",
            _fmt_number(performance.get("sharpe_ratio")),
        )
        perf_cards += _metric_card_html(
            "Max Drawdown",
            _fmt_pct(performance.get("max_drawdown")),
            change=_change_str(performance.get("max_drawdown")),
        )
        perf_cards += "</div>"
        sections.append(PDFSection(title="Performance", content_html=perf_cards))

    # -- Top 10 holdings --
    top = sorted(
        positions, key=lambda p: p.get("weight", 0.0), reverse=True
    )[:10]
    headers = ["Ticker", "Shares", "Market Value", "Weight", "P&L"]
    rows = [
        [
            str(p.get("ticker", "")),
            _fmt_number(p.get("shares"), 0),
            _fmt_currency(p.get("market_value")),
            _fmt_pct(p.get("weight")),
            _fmt_currency(p.get("unrealized_pnl")),
        ]
        for p in top
    ]
    sections.append(PDFSection(
        title="Top 10 Holdings",
        content_html=_table_html(headers, rows),
        page_break_before=True,
    ))

    # -- Sector allocation --
    sector_map: dict[str, float] = {}
    for p in positions:
        sec = p.get("sector", "Unknown")
        sector_map[sec] = sector_map.get(sec, 0.0) + p.get("weight", 0.0)
    sector_sorted = sorted(sector_map.items(), key=lambda x: x[1], reverse=True)
    sector_rows = [[s, _fmt_pct(w)] for s, w in sector_sorted]
    sections.append(PDFSection(
        title="Sector Allocation",
        content_html=_table_html(["Sector", "Weight"], sector_rows),
    ))

    report = PDFReport(
        report_type="portfolio_summary",
        title=f"{name} — Portfolio Summary",
        subtitle=portfolio.get("strategy", ""),
        generated_at=now,
        sections=sections,
        metadata={
            "portfolio": name,
            "inception": str(portfolio.get("inception_date", "")),
            "positions": str(len(positions)),
        },
    )
    report.html_content = assemble_pdf_html(report)
    return report


def build_performance_pdf(
    portfolio_name: str,
    performance: dict,
    attribution: dict | None = None,
    benchmark_name: str | None = None,
    period_start: str | None = None,
    period_end: str | None = None,
) -> PDFReport:
    """Build a performance & attribution PDF report.

    Parameters
    ----------
    portfolio_name : str
    performance : dict
        ``{twr_return, annualized_return, volatility, sharpe_ratio,
          sortino_ratio, beta, alpha, max_drawdown, benchmark_return,
          active_return, ...}``
    attribution : dict | None
        ``{total_allocation, total_selection, total_interaction, ...}``
    benchmark_name : str | None
    period_start, period_end : str | None
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    sections: list[PDFSection] = []

    meta: dict = {"portfolio": portfolio_name}
    if period_start:
        meta["from"] = period_start
    if period_end:
        meta["to"] = period_end
    if benchmark_name:
        meta["benchmark"] = benchmark_name

    # -- Return summary cards --
    ret_cards = '<div class="metrics-row">'
    ret_cards += _metric_card_html(
        "TWR Return",
        _fmt_pct(performance.get("twr_return")),
        change=_change_str(performance.get("twr_return")),
    )
    ret_cards += _metric_card_html(
        "Annualised",
        _fmt_pct(performance.get("annualized_return")),
    )
    if benchmark_name and performance.get("benchmark_return") is not None:
        ret_cards += _metric_card_html(
            f"Benchmark ({benchmark_name})",
            _fmt_pct(performance.get("benchmark_return")),
        )
    if performance.get("active_return") is not None:
        ret_cards += _metric_card_html(
            "Active Return",
            _fmt_pct(performance.get("active_return")),
            change=_change_str(performance.get("active_return")),
        )
    ret_cards += "</div>"
    sections.append(PDFSection(title="Return Summary", content_html=ret_cards))

    # -- Risk metrics --
    risk_cards = '<div class="metrics-row">'
    risk_cards += _metric_card_html(
        "Volatility",
        _fmt_pct(performance.get("volatility")),
    )
    risk_cards += _metric_card_html(
        "Sharpe Ratio",
        _fmt_number(performance.get("sharpe_ratio")),
    )
    risk_cards += _metric_card_html(
        "Sortino Ratio",
        _fmt_number(performance.get("sortino_ratio")),
    )
    risk_cards += _metric_card_html(
        "Beta",
        _fmt_number(performance.get("beta")),
    )
    risk_cards += _metric_card_html(
        "Alpha",
        _fmt_pct(performance.get("alpha")),
    )
    risk_cards += _metric_card_html(
        "Max Drawdown",
        _fmt_pct(performance.get("max_drawdown")),
        change=_change_str(performance.get("max_drawdown")),
    )
    risk_cards += "</div>"
    sections.append(PDFSection(title="Risk Metrics", content_html=risk_cards))

    # -- Attribution summary (optional) --
    if attribution is not None:
        attr_headers = ["Effect", "Contribution"]
        attr_rows = [
            ["Allocation", _fmt_pct(attribution.get("total_allocation"))],
            ["Selection", _fmt_pct(attribution.get("total_selection"))],
            ["Interaction", _fmt_pct(attribution.get("total_interaction"))],
        ]
        sections.append(PDFSection(
            title="Attribution Summary",
            content_html=_table_html(attr_headers, attr_rows),
        ))

    subtitle_parts: list[str] = []
    if period_start and period_end:
        subtitle_parts.append(f"{period_start} to {period_end}")
    if benchmark_name:
        subtitle_parts.append(f"vs {benchmark_name}")

    report = PDFReport(
        report_type="performance",
        title=f"{portfolio_name} — Performance Report",
        subtitle=" | ".join(subtitle_parts),
        generated_at=now,
        sections=sections,
        metadata=meta,
    )
    report.html_content = assemble_pdf_html(report)
    return report


def build_risk_pdf(
    portfolio_name: str,
    var_data: dict,
    concentration: dict,
    stress_results: list[dict] | None = None,
    factor_exposures: list[dict] | None = None,
) -> PDFReport:
    """Build a risk analysis PDF report.

    Parameters
    ----------
    portfolio_name : str
    var_data : dict
        ``{var_1d_95, var_1d_99, var_10d_95, var_10d_99, ...}``
    concentration : dict
        ``{hhi, top_5_weight, top_10_weight, ...}``
    stress_results : list[dict] | None
        ``[{scenario, portfolio_impact, ...}]``
    factor_exposures : list[dict] | None
        ``[{factor, exposure, contribution, ...}]``
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    sections: list[PDFSection] = []

    # -- VaR summary --
    var_cards = '<div class="metrics-row">'
    var_cards += _metric_card_html(
        "VaR 1-Day 95%",
        _fmt_currency(var_data.get("var_1d_95")),
    )
    var_cards += _metric_card_html(
        "VaR 1-Day 99%",
        _fmt_currency(var_data.get("var_1d_99")),
    )
    var_cards += _metric_card_html(
        "VaR 10-Day 95%",
        _fmt_currency(var_data.get("var_10d_95")),
    )
    var_cards += _metric_card_html(
        "VaR 10-Day 99%",
        _fmt_currency(var_data.get("var_10d_99")),
    )
    var_cards += "</div>"
    sections.append(PDFSection(title="Value at Risk", content_html=var_cards))

    # -- Concentration --
    conc_cards = '<div class="metrics-row">'
    conc_cards += _metric_card_html(
        "HHI",
        _fmt_number(concentration.get("hhi"), 4),
    )
    conc_cards += _metric_card_html(
        "Top 5 Weight",
        _fmt_pct(concentration.get("top_5_weight")),
    )
    conc_cards += _metric_card_html(
        "Top 10 Weight",
        _fmt_pct(concentration.get("top_10_weight")),
    )
    conc_cards += "</div>"

    # Top holdings table if provided
    top_holdings = concentration.get("top_holdings", [])
    if top_holdings:
        conc_headers = ["Ticker", "Weight"]
        conc_rows = [
            [str(h.get("ticker", "")), _fmt_pct(h.get("weight"))]
            for h in top_holdings
        ]
        conc_cards += _table_html(conc_headers, conc_rows, caption="Largest positions")

    sections.append(PDFSection(title="Concentration", content_html=conc_cards))

    # -- Stress test results (optional) --
    if stress_results:
        stress_headers = ["Scenario", "Portfolio Impact"]
        stress_rows = [
            [
                str(s.get("scenario", "")),
                _fmt_pct(s.get("portfolio_impact")),
            ]
            for s in stress_results
        ]
        sections.append(PDFSection(
            title="Stress Test Results",
            content_html=_table_html(stress_headers, stress_rows),
            page_break_before=True,
        ))

    # -- Factor exposures (optional) --
    if factor_exposures:
        factor_headers = ["Factor", "Exposure", "Contribution"]
        factor_rows = [
            [
                str(f.get("factor", "")),
                _fmt_number(f.get("exposure")),
                _fmt_pct(f.get("contribution")),
            ]
            for f in factor_exposures
        ]
        sections.append(PDFSection(
            title="Factor Exposures",
            content_html=_table_html(factor_headers, factor_rows),
        ))

    report = PDFReport(
        report_type="risk",
        title=f"{portfolio_name} — Risk Report",
        subtitle="VaR, Concentration & Stress Analysis",
        generated_at=now,
        sections=sections,
        metadata={"portfolio": portfolio_name},
    )
    report.html_content = assemble_pdf_html(report)
    return report


def build_holdings_pdf(
    portfolio_name: str,
    positions: list[dict],
    as_of_date: str | None = None,
) -> PDFReport:
    """Build a full holdings PDF report.

    Parameters
    ----------
    portfolio_name : str
    positions : list[dict]
        ``[{ticker, name, shares, market_value, weight, cost_basis,
          unrealized_pnl, unrealized_pnl_pct, ...}]``
    as_of_date : str | None
        Display date for the snapshot; defaults to now.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if as_of_date is None:
        as_of_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    sections: list[PDFSection] = []

    # -- Summary cards --
    total_mv = sum(p.get("market_value", 0.0) for p in positions)
    total_pnl = sum(p.get("unrealized_pnl", 0.0) for p in positions)
    summary_cards = '<div class="metrics-row">'
    summary_cards += _metric_card_html("Positions", str(len(positions)))
    summary_cards += _metric_card_html("Total Market Value", _fmt_currency(total_mv))
    summary_cards += _metric_card_html(
        "Total Unrealised P&L",
        _fmt_currency(total_pnl),
        change=_change_str(total_pnl, is_pct=False),
    )
    summary_cards += "</div>"
    sections.append(PDFSection(title="Summary", content_html=summary_cards))

    # -- Full holdings table --
    headers = [
        "Ticker", "Name", "Shares", "Market Value",
        "Weight", "Cost Basis", "P&L", "P&L %",
    ]
    rows = [
        [
            str(p.get("ticker", "")),
            str(p.get("name", "")),
            _fmt_number(p.get("shares"), 0),
            _fmt_currency(p.get("market_value")),
            _fmt_pct(p.get("weight")),
            _fmt_currency(p.get("cost_basis")),
            _fmt_currency(p.get("unrealized_pnl")),
            _fmt_pct(p.get("unrealized_pnl_pct")),
        ]
        for p in sorted(
            positions, key=lambda p: p.get("weight", 0.0), reverse=True
        )
    ]
    sections.append(PDFSection(
        title="Holdings Detail",
        content_html=_table_html(headers, rows),
        page_break_before=True,
    ))

    report = PDFReport(
        report_type="holdings",
        title=f"{portfolio_name} — Holdings Report",
        subtitle=f"As of {as_of_date}",
        generated_at=now,
        sections=sections,
        metadata={
            "portfolio": portfolio_name,
            "as_of_date": as_of_date,
            "positions": str(len(positions)),
        },
    )
    report.html_content = assemble_pdf_html(report)
    return report


# ── Assembler ───────────────────────────────────────────────────────────


def assemble_pdf_html(report: PDFReport) -> str:
    """Combine all sections of *report* into a complete HTML document.

    The returned string is a self-contained HTML page with inline CSS
    that can be fed directly to WeasyPrint, wkhtmltopdf, Playwright
    ``page.pdf()``, or any similar tool.
    """
    body_parts: list[str] = []

    # Header
    body_parts.append(
        _header_html(report.title, report.subtitle, report.generated_at, report.metadata)
    )

    # Sections
    for sec in report.sections:
        wrapper_cls = "section"
        if sec.page_break_before:
            wrapper_cls += " page-break"
        body_parts.append(
            f'<div class="{wrapper_cls}">'
            f'<div class="section-title">{_esc(sec.title)}</div>'
            f"{sec.content_html}"
            "</div>"
        )

    # Footer
    body_parts.append(
        '<div style="margin-top:40px;border-top:1px solid #3a3a5c;'
        'padding-top:10px;font-size:0.7rem;color:#757575;text-align:center;">'
        f"Generated by Bloomberg Data Fabric | {_esc(report.generated_at)}"
        "</div>"
    )

    return (
        "<!DOCTYPE html>"
        '<html lang="en">'
        "<head>"
        '<meta charset="utf-8">'
        f"<title>{_esc(report.title)}</title>"
        f"<style>{_css_styles()}</style>"
        "</head>"
        "<body>"
        + "".join(body_parts)
        + "</body></html>"
    )
