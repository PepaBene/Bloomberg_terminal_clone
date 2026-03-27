"""Tests for Pillar 4 Phase 2 — Reporting Engine."""

import pytest

from src.engines.reporting_engine import (
    ExportResult,
    ReportData,
    build_attribution_report,
    build_holdings_report,
    build_performance_report,
    build_portfolio_summary_report,
    compute_report_metadata,
    format_holdings_csv,
    format_nav_csv,
    format_returns_csv,
    format_transactions_csv,
    format_xlsx_workbook,
)


# ── TestPortfolioSummaryReport ─────────────────────────────────────────


class TestPortfolioSummaryReport:
    """Tests for build_portfolio_summary_report."""

    def test_basic_summary(self):
        """Build summary with all fields."""
        portfolio = {"id": "P001", "name": "Growth Fund", "inception_date": "2020-01-01", "strategy": "Growth"}
        positions = [
            {"ticker": "AAPL", "shares": 100, "market_value": 17500, "weight": 0.35},
            {"ticker": "MSFT", "shares": 50, "market_value": 20000, "weight": 0.40},
            {"ticker": "GOOG", "shares": 30, "market_value": 12500, "weight": 0.25},
        ]
        nav = {"nav": 50000, "market_value": 45000, "cash_balance": 5000, "unrealized_pnl": 3000}
        result = build_portfolio_summary_report(portfolio, positions, nav)
        assert result["portfolio"]["name"] == "Growth Fund"
        assert result["nav"]["current_nav"] == 50000
        assert result["position_count"] == 3
        assert len(result["top_holdings"]) == 3

    def test_with_performance(self):
        """Summary includes performance when provided."""
        portfolio = {"id": "P001", "name": "Test"}
        positions = []
        nav = {"nav": 100000}
        perf = {"twr_return": 0.12, "annualized_return": 0.10, "sharpe_ratio": 1.5}
        result = build_portfolio_summary_report(portfolio, positions, nav, perf)
        assert "performance" in result
        assert result["performance"]["twr_return"] == 0.12

    def test_without_performance(self):
        """Summary omits performance when None."""
        portfolio = {"id": "P001", "name": "Test"}
        result = build_portfolio_summary_report(portfolio, [], {"nav": 0}, None)
        assert "performance" not in result

    def test_top_holdings_sorted(self):
        """Top holdings sorted by weight descending."""
        portfolio = {"id": "P001", "name": "Test"}
        positions = [
            {"ticker": "A", "weight": 0.10, "market_value": 1000},
            {"ticker": "B", "weight": 0.50, "market_value": 5000},
            {"ticker": "C", "weight": 0.40, "market_value": 4000},
        ]
        result = build_portfolio_summary_report(portfolio, positions, {"nav": 10000})
        assert result["top_holdings"][0]["ticker"] == "B"


# ── TestPerformanceReport ──────────────────────────────────────────────


class TestPerformanceReport:
    """Tests for build_performance_report."""

    def test_basic_report(self):
        """Performance report with returns and risk."""
        perf = {
            "twr_return": 0.12, "annualized_return": 0.10,
            "volatility": 0.15, "sharpe_ratio": 0.67,
            "max_drawdown": -0.08, "positive_days": 130, "negative_days": 120,
            "best_day": 0.03, "worst_day": -0.025,
        }
        result = build_performance_report(perf)
        assert result["returns"]["twr_return"] == 0.12
        assert result["risk"]["volatility"] == 0.15
        assert result["day_stats"]["positive_days"] == 130

    def test_with_benchmark(self):
        """Report includes benchmark name."""
        perf = {"twr_return": 0.12, "benchmark_return": 0.10, "active_return": 0.02}
        result = build_performance_report(perf, benchmark_name="S&P 500")
        assert result["benchmark_name"] == "S&P 500"

    def test_with_attribution(self):
        """Report includes attribution summary."""
        perf = {"twr_return": 0.12}
        attr = {"total_allocation": 0.01, "total_selection": 0.005, "total_interaction": 0.003}
        result = build_performance_report(perf, attribution=attr)
        assert "attribution_summary" in result
        assert result["attribution_summary"]["total_allocation"] == 0.01


# ── TestAttributionReport ──────────────────────────────────────────────


class TestAttributionReport:
    """Tests for build_attribution_report."""

    def test_brinson_only(self):
        """Report with Brinson data only."""
        brinson = {
            "total_allocation": 0.01, "total_selection": 0.005,
            "total_interaction": 0.003, "residual": 0.001,
            "sector_detail": [{"sector": "Tech", "allocation_effect": 0.005}],
        }
        result = build_attribution_report(brinson=brinson)
        assert "brinson" in result
        assert result["brinson"]["total_allocation"] == 0.01

    def test_factor_only(self):
        """Report with factor data only."""
        factor = {
            "total_factor_return": 0.02,
            "stock_specific_return": 0.01,
            "factors": [{"factor": "value", "contribution": 0.01}],
        }
        result = build_attribution_report(factor=factor)
        assert "factor" in result
        assert result["factor"]["total_factor_return"] == 0.02

    def test_contributors_only(self):
        """Report with contributor data only."""
        contributors = {
            "top": [{"ticker": "AAPL", "contribution": 0.01}],
            "bottom": [{"ticker": "META", "contribution": -0.005}],
        }
        result = build_attribution_report(contributors=contributors)
        assert "contributors" in result
        assert len(result["contributors"]["top"]) == 1

    def test_empty_report(self):
        """All None → empty dict."""
        result = build_attribution_report()
        assert result == {}


# ── TestHoldingsReport ─────────────────────────────────────────────────


class TestHoldingsReport:
    """Tests for build_holdings_report."""

    def test_basic_holdings(self):
        """Holdings report with basic data."""
        positions = [
            {"ticker": "AAPL", "shares": 100, "market_value": 17500, "weight": 0.35, "cost_basis": 15000, "unrealized_pnl": 2500},
            {"ticker": "MSFT", "shares": 50, "market_value": 20000, "weight": 0.40, "cost_basis": 18000, "unrealized_pnl": 2000},
        ]
        result = build_holdings_report(positions)
        assert result["total_positions"] == 2
        assert result["total_market_value"] == 37500

    def test_with_enrichment(self):
        """Holdings enriched with sector/name data."""
        positions = [{"ticker": "AAPL", "shares": 100, "market_value": 17500, "weight": 0.35}]
        enrichment = {"AAPL": {"name": "Apple Inc.", "sector": "Technology", "industry": "Consumer Electronics"}}
        result = build_holdings_report(positions, enrichment)
        assert result["holdings"][0]["name"] == "Apple Inc."
        assert result["holdings"][0]["sector"] == "Technology"

    def test_no_enrichment(self):
        """Without enrichment, no name/sector fields."""
        positions = [{"ticker": "XYZ", "shares": 50, "market_value": 5000, "weight": 0.10}]
        result = build_holdings_report(positions)
        assert "name" not in result["holdings"][0]


# ── TestFormatHoldingsCSV ──────────────────────────────────────────────


class TestFormatHoldingsCSV:
    """Tests for format_holdings_csv."""

    def test_default_columns(self):
        """Default columns: ticker, shares, market_value, weight."""
        positions = [
            {"ticker": "AAPL", "shares": 100, "market_value": 17500, "weight": 0.35},
        ]
        csv = format_holdings_csv(positions)
        lines = csv.split("\n")
        assert lines[0] == "ticker,shares,market_value,weight"
        assert "AAPL" in lines[1]

    def test_custom_columns(self):
        """Custom columns selection."""
        positions = [{"ticker": "AAPL", "shares": 100, "sector": "Tech"}]
        csv = format_holdings_csv(positions, columns=["ticker", "sector"])
        lines = csv.split("\n")
        assert lines[0] == "ticker,sector"
        assert "Tech" in lines[1]

    def test_multiple_rows(self):
        """Multiple positions → header + N rows."""
        positions = [
            {"ticker": "AAPL", "shares": 100, "market_value": 17500, "weight": 0.35},
            {"ticker": "MSFT", "shares": 50, "market_value": 20000, "weight": 0.40},
        ]
        csv = format_holdings_csv(positions)
        lines = csv.split("\n")
        assert len(lines) == 3  # header + 2 rows

    def test_empty(self):
        """Empty positions → header only."""
        csv = format_holdings_csv([])
        lines = csv.split("\n")
        assert len(lines) == 1


# ── TestFormatNavCSV ───────────────────────────────────────────────────


class TestFormatNavCSV:
    """Tests for format_nav_csv."""

    def test_basic(self):
        """NAV history formatted correctly."""
        history = [
            {"date": "2025-01-02", "nav": 100000, "daily_return": 0.0, "cumulative_return": 0.0},
            {"date": "2025-01-03", "nav": 101000, "daily_return": 0.01, "cumulative_return": 0.01},
        ]
        csv = format_nav_csv(history)
        lines = csv.split("\n")
        assert lines[0] == "date,nav,daily_return,cumulative_return"
        assert len(lines) == 3


# ── TestFormatReturnsCSV ───────────────────────────────────────────────


class TestFormatReturnsCSV:
    """Tests for format_returns_csv."""

    def test_basic(self):
        """Returns data formatted correctly."""
        returns = [
            {"period": "MTD", "return": 0.02, "benchmark_return": 0.015, "active_return": 0.005},
            {"period": "YTD", "return": 0.10, "benchmark_return": 0.08, "active_return": 0.02},
        ]
        csv = format_returns_csv(returns)
        lines = csv.split("\n")
        assert lines[0] == "period,return,benchmark_return,active_return"
        assert "MTD" in lines[1]


# ── TestFormatTransactionsCSV ──────────────────────────────────────────


class TestFormatTransactionsCSV:
    """Tests for format_transactions_csv."""

    def test_basic(self):
        """Transactions formatted correctly."""
        txns = [
            {"date": "2025-01-02", "ticker": "AAPL", "type": "BUY", "shares": 100, "price": 175.0, "amount": 17500.0},
        ]
        csv = format_transactions_csv(txns)
        lines = csv.split("\n")
        assert lines[0] == "date,ticker,type,shares,price,amount"
        assert "BUY" in lines[1]


# ── TestFormatXlsxWorkbook ─────────────────────────────────────────────


class TestFormatXlsxWorkbook:
    """Tests for format_xlsx_workbook."""

    def test_single_sheet(self):
        """Single sheet with headers and rows."""
        sheets = {
            "Holdings": {
                "headers": ["Ticker", "Shares", "Market Value"],
                "rows": [
                    ["AAPL", 100, 17500],
                    ["MSFT", 50, 20000],
                ],
            },
        }
        wb = format_xlsx_workbook(sheets)
        assert "Holdings" in wb
        assert wb["Holdings"][0] == ["Ticker", "Shares", "Market Value"]
        assert len(wb["Holdings"]) == 3

    def test_multiple_sheets(self):
        """Multiple sheets in workbook."""
        sheets = {
            "Holdings": {"headers": ["Ticker"], "rows": [["AAPL"]]},
            "Returns": {"headers": ["Period"], "rows": [["MTD"]]},
        }
        wb = format_xlsx_workbook(sheets)
        assert len(wb) == 2
        assert "Holdings" in wb
        assert "Returns" in wb

    def test_empty_sheet(self):
        """Sheet with no rows → just header."""
        sheets = {"Empty": {"headers": ["Col1", "Col2"], "rows": []}}
        wb = format_xlsx_workbook(sheets)
        assert len(wb["Empty"]) == 1


# ── TestComputeReportMetadata ──────────────────────────────────────────


class TestComputeReportMetadata:
    """Tests for compute_report_metadata."""

    def test_basic_metadata(self):
        """Metadata with all fields."""
        meta = compute_report_metadata(
            "Growth Fund", "2025-01-01", "2025-06-30",
            generated_at="2025-07-01T10:00:00Z",
        )
        assert meta["portfolio_name"] == "Growth Fund"
        assert meta["period_start"] == "2025-01-01"
        assert meta["period_end"] == "2025-06-30"
        assert meta["generated_at"] == "2025-07-01T10:00:00Z"
        assert meta["report_version"] == "1.0"

    def test_auto_generated_at(self):
        """Auto-generated timestamp when not provided."""
        meta = compute_report_metadata("Test", "2025-01-01", "2025-06-30")
        assert "generated_at" in meta
        assert meta["generated_at"] is not None
        assert "T" in meta["generated_at"]
