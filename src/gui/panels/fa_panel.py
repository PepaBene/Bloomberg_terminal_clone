"""FA -- Financial Analysis panel.

Tabbed view of Income Statement, Balance Sheet, Cash Flow, Ratios, and
Segments.  Financial tables use the standard Bloomberg transposed layout where
rows are line items and columns are fiscal periods.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSizePolicy,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .base_panel import BasePanel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Theme constants
# ---------------------------------------------------------------------------
_BG = "#0a0e17"
_BG_CARD = "#111827"
_TEXT = "#e2e8f0"
_TEXT_DIM = "#94a3b8"
_ORANGE = "#ff6600"
_GREEN = "#22c55e"
_RED = "#ef4444"
_BORDER = "#1e293b"
_FONT = "Consolas, 'Courier New', monospace"

# ---------------------------------------------------------------------------
# Line-item definitions per statement
# ---------------------------------------------------------------------------
_IS_ITEMS: list[tuple[str, str]] = [
    ("Revenue", "total_revenue"),
    ("Cost of Revenue", "cost_of_revenue"),
    ("Gross Profit", "gross_profit"),
    ("R&D", "research_development"),
    ("SG&A", "selling_general_admin"),
    ("D&A", "depreciation_amortization"),
    ("Total Opex", "total_operating_expense"),
    ("Operating Income", "operating_income"),
    ("Interest Expense", "interest_expense"),
    ("Pre-Tax Income", "pretax_income"),
    ("Income Tax", "income_tax_expense"),
    ("Net Income", "net_income"),
    ("EBITDA", "ebitda"),
    ("Adj. EBITDA", "adjusted_ebitda"),
    ("Basic EPS", "basic_eps"),
    ("Diluted EPS", "diluted_eps"),
    ("Shares Out. (Diluted)", "diluted_shares_outstanding"),
]

_BS_ITEMS: list[tuple[str, str]] = [
    ("Cash & Equivalents", "cash_and_equivalents"),
    ("Short-Term Investments", "short_term_investments"),
    ("Accounts Receivable", "accounts_receivable"),
    ("Inventory", "inventory"),
    ("Total Current Assets", "total_current_assets"),
    ("PP&E (Net)", "ppe_net"),
    ("Goodwill", "goodwill"),
    ("Intangible Assets", "intangible_assets"),
    ("Total Assets", "total_assets"),
    ("Accounts Payable", "accounts_payable"),
    ("Short-Term Debt", "short_term_debt"),
    ("Total Current Liabilities", "total_current_liabilities"),
    ("Long-Term Debt", "long_term_debt"),
    ("Total Liabilities", "total_liabilities"),
    ("Common Equity", "total_common_equity"),
    ("Total Equity", "total_equity"),
    ("Total Liabilities & Equity", "total_liabilities_and_equity"),
    ("Total Debt", "total_debt"),
    ("Net Debt", "net_debt"),
    ("Working Capital", "working_capital"),
]

_CF_ITEMS: list[tuple[str, str]] = [
    ("Net Income", "net_income"),
    ("D&A", "depreciation_amortization"),
    ("Stock-Based Comp", "stock_based_comp"),
    ("Change in Receivables", "change_in_receivables"),
    ("Change in Inventory", "change_in_inventory"),
    ("Change in Payables", "change_in_payables"),
    ("Cash from Operations", "cash_from_operations"),
    ("Capital Expenditures", "capital_expenditures"),
    ("Acquisitions", "acquisitions"),
    ("Cash from Investing", "cash_from_investing"),
    ("Debt Issued", "debt_issued"),
    ("Debt Repaid", "debt_repaid"),
    ("Stock Repurchased", "stock_repurchased"),
    ("Dividends Paid", "dividends_paid"),
    ("Cash from Financing", "cash_from_financing"),
    ("Net Change in Cash", "net_change_in_cash"),
    ("Free Cash Flow", "free_cash_flow"),
]

_RATIO_DEFS: list[tuple[str, str]] = [
    ("Gross Margin", "gross_margin"),
    ("Operating Margin", "operating_margin"),
    ("Net Margin", "net_margin"),
    ("EBITDA Margin", "ebitda_margin"),
    ("ROE", "roe"),
    ("ROA", "roa"),
    ("ROIC", "roic"),
    ("Debt / Equity", "debt_to_equity"),
    ("Current Ratio", "current_ratio"),
    ("Quick Ratio", "quick_ratio"),
    ("Interest Coverage", "interest_coverage"),
    ("Asset Turnover", "asset_turnover"),
    ("FCF Yield", "fcf_yield"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _fmt_millions(val: float | None) -> str:
    if val is None:
        return "--"
    if abs(val) >= 1e9:
        return f"{val / 1e6:>12,.0f}"
    if abs(val) >= 1e6:
        return f"{val / 1e6:>12,.1f}"
    return f"{val / 1e6:>12,.2f}"


def _fmt_ratio(val: float | None) -> str:
    if val is None:
        return "--"
    return f"{val:>10,.2f}"


def _fmt_eps(val: float | None) -> str:
    if val is None:
        return "--"
    return f"{val:>10,.2f}"


def _period_label(period: dict[str, Any]) -> str:
    """Build a column header like 'FY2023' or 'Q2 2024'."""
    pt = period.get("period_type", "")
    fy = period.get("fiscal_year", "")
    fq = period.get("fiscal_quarter")
    if pt == "QUARTERLY" and fq is not None:
        return f"Q{fq} {fy}"
    return f"FY{fy}"


# ---------------------------------------------------------------------------
# Financial statement table (transposed layout)
# ---------------------------------------------------------------------------
class _FinancialTable(QWidget):
    """A table where rows = line items, columns = fiscal periods."""

    def __init__(self, items: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self._items = items

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._table = QTableWidget()
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._style_table()
        layout.addWidget(self._table)

        # Default: show loading
        self._set_loading()

    def _style_table(self):
        self._table.setStyleSheet(f"""
            QTableWidget {{
                background: {_BG_CARD};
                color: {_TEXT};
                font-family: {_FONT};
                font-size: 12px;
                gridline-color: {_BORDER};
                border: 1px solid {_BORDER};
            }}
            QTableWidget::item {{
                padding: 2px 6px;
            }}
            QTableWidget::item:selected {{
                background: #1e293b;
            }}
            QHeaderView::section {{
                background: {_BG};
                color: {_ORANGE};
                font-family: {_FONT};
                font-size: 11px;
                font-weight: bold;
                border: none;
                border-bottom: 1px solid {_BORDER};
                padding: 4px 6px;
            }}
        """)

    def _set_loading(self):
        self._table.setColumnCount(2)
        self._table.setHorizontalHeaderLabels(["Line Item", ""])
        self._table.setRowCount(1)
        item = QTableWidgetItem("Loading...")
        item.setForeground(QColor(_TEXT_DIM))
        self._table.setItem(0, 0, item)

    def populate(
        self,
        periods: list[dict[str, Any]],
        statements: list[dict[str, Any] | None],
        formatter=_fmt_millions,
    ):
        """Fill the table.

        Parameters
        ----------
        periods:
            List of period dicts (newest first).
        statements:
            Parallel list of statement dicts (one per period, same order).
        formatter:
            Callable to format numeric values.
        """
        ncols = 1 + len(periods)
        headers = ["Line Item"] + [_period_label(p) for p in periods]

        self._table.setColumnCount(ncols)
        self._table.setHorizontalHeaderLabels(headers)
        self._table.setRowCount(len(self._items))

        # Fix first column width for line-item labels
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Fixed
        )
        self._table.setColumnWidth(0, 200)
        for c in range(1, ncols):
            self._table.horizontalHeader().setSectionResizeMode(
                c, QHeaderView.ResizeMode.Stretch
            )

        for r, (label, field) in enumerate(self._items):
            # Line item label
            lbl_item = QTableWidgetItem(label)
            lbl_item.setForeground(QColor(_TEXT_DIM))
            self._table.setItem(r, 0, lbl_item)

            # Values per period
            for c, stmt in enumerate(statements):
                val = stmt.get(field) if stmt else None
                text = formatter(val)
                cell = QTableWidgetItem(text)
                cell.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                if val is not None and val < 0:
                    cell.setForeground(QColor(_RED))
                else:
                    cell.setForeground(QColor(_TEXT))
                self._table.setItem(r, c + 1, cell)


# ---------------------------------------------------------------------------
# Ratios table (computed from raw data)
# ---------------------------------------------------------------------------
class _RatiosTable(_FinancialTable):
    """Like _FinancialTable but values are already ratios -- use ratio fmt."""

    def __init__(self, parent=None):
        super().__init__(_RATIO_DEFS, parent)

    def populate_ratios(
        self,
        periods: list[dict[str, Any]],
        ratios: list[dict[str, Any]],
    ):
        self.populate(periods, ratios, formatter=_fmt_ratio)


# ---------------------------------------------------------------------------
# Segments table
# ---------------------------------------------------------------------------
class _SegmentsTable(QWidget):
    """Revenue breakdown by segment."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._table = QTableWidget()
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setStyleSheet(f"""
            QTableWidget {{
                background: {_BG_CARD};
                color: {_TEXT};
                font-family: {_FONT};
                font-size: 12px;
                gridline-color: {_BORDER};
                border: 1px solid {_BORDER};
            }}
            QTableWidget::item {{ padding: 2px 6px; }}
            QTableWidget::item:selected {{ background: #1e293b; }}
            QHeaderView::section {{
                background: {_BG};
                color: {_ORANGE};
                font-family: {_FONT};
                font-size: 11px;
                font-weight: bold;
                border: none;
                border-bottom: 1px solid {_BORDER};
                padding: 4px 6px;
            }}
        """)
        layout.addWidget(self._table)
        self._set_loading()

    def _set_loading(self):
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(
            ["Segment", "Revenue ($M)", "Oper. Income ($M)", "Margin"]
        )
        self._table.setRowCount(1)
        item = QTableWidgetItem("Loading...")
        item.setForeground(QColor(_TEXT_DIM))
        self._table.setItem(0, 0, item)

    def populate(self, segments: list[dict[str, Any]]):
        headers = ["Segment", "Type", "Revenue ($M)", "Oper. Income ($M)", "Margin"]
        self._table.setColumnCount(len(headers))
        self._table.setHorizontalHeaderLabels(headers)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        for c in range(1, len(headers)):
            self._table.horizontalHeader().setSectionResizeMode(
                c, QHeaderView.ResizeMode.ResizeToContents
            )

        self._table.setRowCount(len(segments))
        for r, seg in enumerate(segments):
            name = seg.get("segment_name", "--")
            stype = seg.get("segment_type", "--")
            rev = seg.get("revenue")
            oi = seg.get("operating_income")
            margin = seg.get("operating_margin")

            self._table.setItem(r, 0, self._cell(name, color=_TEXT))
            self._table.setItem(r, 1, self._cell(stype, color=_TEXT_DIM))
            self._table.setItem(
                r, 2, self._cell(_fmt_millions(rev), align_right=True)
            )
            self._table.setItem(
                r, 3, self._cell(_fmt_millions(oi), align_right=True)
            )
            self._table.setItem(
                r, 4,
                self._cell(
                    f"{margin:.1f}%" if margin is not None else "--",
                    align_right=True,
                ),
            )

    @staticmethod
    def _cell(text: str, color: str = _TEXT, align_right: bool = False):
        item = QTableWidgetItem(text)
        item.setForeground(QColor(color))
        if align_right:
            item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
        return item


# ---------------------------------------------------------------------------
# FA Panel
# ---------------------------------------------------------------------------
class FAPanel(BasePanel):
    """FA -- financial analysis panel with tabbed statements."""

    panel_name = "FA"
    panel_title = "FA - Financial Analysis"

    def __init__(self, data_service, app_state, parent=None):
        super().__init__(data_service, app_state, parent)

        self.setStyleSheet(f"background: {_BG};")

        # ---- Header ----
        self._header = QLabel("FINANCIAL ANALYSIS")
        self._header.setStyleSheet(
            f"color: {_ORANGE}; font-family: {_FONT}; font-size: 14px; "
            f"font-weight: bold;"
        )
        self._layout.addWidget(self._header)

        self._entity_label = QLabel("Loading...")
        self._entity_label.setStyleSheet(
            f"color: {_TEXT}; font-family: {_FONT}; font-size: 12px;"
        )
        self._layout.addWidget(self._entity_label)

        # Units note
        self._units_label = QLabel("All values in USD millions unless noted")
        self._units_label.setStyleSheet(
            f"color: {_TEXT_DIM}; font-family: {_FONT}; font-size: 10px;"
        )
        self._layout.addWidget(self._units_label)

        # ---- Tab widget ----
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {_BORDER};
                background: {_BG};
            }}
            QTabBar::tab {{
                background: {_BG_CARD};
                color: {_TEXT_DIM};
                font-family: {_FONT};
                font-size: 11px;
                padding: 6px 14px;
                border: 1px solid {_BORDER};
                border-bottom: none;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background: {_BG};
                color: {_ORANGE};
                font-weight: bold;
            }}
            QTabBar::tab:hover {{
                color: {_TEXT};
            }}
        """)

        self._is_table = _FinancialTable(_IS_ITEMS)
        self._bs_table = _FinancialTable(_BS_ITEMS)
        self._cf_table = _FinancialTable(_CF_ITEMS)
        self._ratios_table = _RatiosTable()
        self._segments_table = _SegmentsTable()

        self._tabs.addTab(self._is_table, "Income Statement")
        self._tabs.addTab(self._bs_table, "Balance Sheet")
        self._tabs.addTab(self._cf_table, "Cash Flow")
        self._tabs.addTab(self._ratios_table, "Ratios")
        self._tabs.addTab(self._segments_table, "Segments")

        self._layout.addWidget(self._tabs, stretch=1)

        # ---- Connect signals ----
        if hasattr(data_service, "fundamentals_loaded"):
            data_service.fundamentals_loaded.connect(self._on_fundamentals_loaded)

        self._current_entity_id: str | None = None

    # ------------------------------------------------------------------
    # Panel lifecycle
    # ------------------------------------------------------------------
    def activate(self, context: dict | None = None):
        context = context or {}
        entity_id = context.get("entity_id")
        entity_name = context.get("entity_name", "")

        if entity_name:
            self._entity_label.setText(entity_name)
        else:
            self._entity_label.setText("Loading...")

        self._current_entity_id = entity_id
        if entity_id and hasattr(self.data_service, "load_fundamentals"):
            self.data_service.load_fundamentals(entity_id)

    # ------------------------------------------------------------------
    # Data callbacks
    # ------------------------------------------------------------------
    @Slot(object)
    def _on_fundamentals_loaded(self, data: dict[str, Any]):
        """Handle loaded fundamentals.

        Expected *data* shape::

            {
                "entity_id": "...",
                "entity_name": "...",
                "periods": [ {period dict}, ... ],   # newest first
                "income_statements": [ {...}, ... ],
                "balance_sheets": [ {...}, ... ],
                "cash_flows": [ {...}, ... ],
                "ratios": [ {...}, ... ],             # optional, computed
                "segments": [ {...}, ... ],           # optional
            }
        """
        # Ignore if we have navigated away
        if str(data.get("entity_id")) != str(self._current_entity_id):
            return

        if data.get("entity_name"):
            self._entity_label.setText(data["entity_name"])

        currency = data.get("reporting_currency", "USD")
        self._units_label.setText(
            f"All values in {currency} millions unless noted"
        )

        periods = data.get("periods", [])
        self._is_table.populate(
            periods,
            data.get("income_statements", []),
            formatter=_fmt_millions,
        )
        self._bs_table.populate(
            periods,
            data.get("balance_sheets", []),
            formatter=_fmt_millions,
        )
        self._cf_table.populate(
            periods,
            data.get("cash_flows", []),
            formatter=_fmt_millions,
        )

        ratios = data.get("ratios")
        if ratios is not None:
            self._ratios_table.populate_ratios(periods, ratios)
        else:
            # Compute ratios from raw statements
            computed = self._compute_ratios(
                data.get("income_statements", []),
                data.get("balance_sheets", []),
                data.get("cash_flows", []),
            )
            self._ratios_table.populate_ratios(periods, computed)

        segments = data.get("segments")
        if segments:
            self._segments_table.populate(segments)

    # ------------------------------------------------------------------
    # Ratio computation
    # ------------------------------------------------------------------
    @staticmethod
    def _compute_ratios(
        income_statements: list[dict],
        balance_sheets: list[dict],
        cash_flows: list[dict],
    ) -> list[dict[str, float | None]]:
        """Derive common ratios from raw financial statement data."""
        result: list[dict[str, float | None]] = []
        n = max(len(income_statements), len(balance_sheets), len(cash_flows))

        for i in range(n):
            inc = income_statements[i] if i < len(income_statements) else {}
            bs = balance_sheets[i] if i < len(balance_sheets) else {}
            cf = cash_flows[i] if i < len(cash_flows) else {}

            rev = inc.get("total_revenue")
            gp = inc.get("gross_profit")
            oi = inc.get("operating_income")
            ni = inc.get("net_income")
            ebitda = inc.get("ebitda")

            ta = bs.get("total_assets")
            te = bs.get("total_equity")
            tl = bs.get("total_liabilities")
            td = bs.get("total_debt")
            tca = bs.get("total_current_assets")
            tcl = bs.get("total_current_liabilities")
            inv = bs.get("inventory")
            ie = inc.get("interest_expense")
            fcf = cf.get("free_cash_flow")

            def safe_div(a, b):
                if a is None or b is None or b == 0:
                    return None
                return a / b

            ratios: dict[str, float | None] = {
                "gross_margin": safe_div(gp, rev) * 100 if safe_div(gp, rev) is not None else None,
                "operating_margin": safe_div(oi, rev) * 100 if safe_div(oi, rev) is not None else None,
                "net_margin": safe_div(ni, rev) * 100 if safe_div(ni, rev) is not None else None,
                "ebitda_margin": safe_div(ebitda, rev) * 100 if safe_div(ebitda, rev) is not None else None,
                "roe": safe_div(ni, te) * 100 if safe_div(ni, te) is not None else None,
                "roa": safe_div(ni, ta) * 100 if safe_div(ni, ta) is not None else None,
                "roic": None,  # Would need invested capital
                "debt_to_equity": safe_div(td, te),
                "current_ratio": safe_div(tca, tcl),
                "quick_ratio": safe_div((tca - inv) if tca is not None and inv is not None else None, tcl),
                "interest_coverage": safe_div(ebitda, ie) if ie and ie != 0 else None,
                "asset_turnover": safe_div(rev, ta),
                "fcf_yield": None,  # Would need market cap
            }
            result.append(ratios)
        return result
