"""SMRT -- Smart-Money / Notable-Filer tracking panel.

Shows the curated registry of notable investors, insiders, and politicians you
can follow (Michael Burry, Jamie Dimon, Nancy Pelosi, ...) and the latest
congressional STOCK Act trades.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
)

from .base_panel import BasePanel

logger = logging.getLogger(__name__)

_BG = "#0a0e17"
_BG_CARD = "#111827"
_TEXT = "#e2e8f0"
_TEXT_DIM = "#94a3b8"
_ORANGE = "#ff6600"
_GREEN = "#22c55e"
_RED = "#ef4444"
_BORDER = "#1e293b"
_FONT = "Consolas, 'Courier New', monospace"

_TAB_STYLE = f"""
    QTabWidget::pane {{ border: 1px solid {_BORDER}; background: {_BG}; }}
    QTabBar::tab {{
        background: {_BG_CARD}; color: {_TEXT_DIM};
        font-family: {_FONT}; font-size: 11px;
        padding: 6px 14px; border: 1px solid {_BORDER};
        border-bottom: none; margin-right: 2px;
    }}
    QTabBar::tab:selected {{ background: {_BG}; color: {_ORANGE}; font-weight: bold; }}
"""

_TABLE_STYLE = f"""
    QTableWidget {{
        background: {_BG_CARD}; color: {_TEXT};
        font-family: {_FONT}; font-size: 12px;
        gridline-color: {_BORDER}; border: 1px solid {_BORDER};
    }}
    QTableWidget::item {{ padding: 2px 6px; }}
    QHeaderView::section {{
        background: {_BG}; color: {_ORANGE};
        font-family: {_FONT}; font-size: 11px; font-weight: bold;
        border: none; border-bottom: 1px solid {_BORDER}; padding: 4px 6px;
    }}
"""

_CATEGORY_LABELS = {
    "GURU_13F": "13F Manager",
    "INSIDER_FORM4": "Corporate Insider",
    "POLITICIAN": "Politician (STOCK Act)",
}


def _table(headers: list[str]) -> QTableWidget:
    t = QTableWidget()
    t.setColumnCount(len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.verticalHeader().setVisible(False)
    t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setStyleSheet(_TABLE_STYLE)
    return t


def _cell(text: str, color: str = _TEXT, align_right: bool = False) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setForeground(QColor(color))
    if align_right:
        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return item


class SmartMoneyPanel(BasePanel):
    """SMRT -- follow notable investors, insiders, and politicians."""

    panel_name = "SMRT"
    panel_title = "SMRT - Smart Money"

    def __init__(self, data_service, app_state, parent=None):
        super().__init__(data_service, app_state, parent)
        self.setStyleSheet(f"background: {_BG};")

        header = QLabel("SMART MONEY  ·  Notable Filer Tracking")
        header.setStyleSheet(
            f"color: {_ORANGE}; font-family: {_FONT}; font-size: 14px; font-weight: bold;"
        )
        self._layout.addWidget(header)

        sub = QLabel("Follow 13F managers (Burry), insiders (Dimon) & politicians (Pelosi) — free EDGAR / STOCK Act data")
        sub.setStyleSheet(f"color: {_TEXT_DIM}; font-family: {_FONT}; font-size: 11px;")
        self._layout.addWidget(sub)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(_TAB_STYLE)

        self._investors_table = _table(["Name", "Category", "Vehicle / Role", "Tags"])
        self._congress_table = _table(
            ["Politician", "Ticker", "Type", "Trade Date", "Amount", "Size", "Late?"]
        )
        self._tabs.addTab(self._investors_table, "Notable Investors")
        self._tabs.addTab(self._congress_table, "Congressional Trades")
        self._layout.addWidget(self._tabs, stretch=1)

        if hasattr(data_service, "notable_investors_loaded"):
            data_service.notable_investors_loaded.connect(self._on_investors)
        if hasattr(data_service, "congress_trades_loaded"):
            data_service.congress_trades_loaded.connect(self._on_congress)

    def activate(self, context: dict | None = None):
        if hasattr(self.data_service, "load_notable_investors"):
            self.data_service.load_notable_investors()
        if hasattr(self.data_service, "load_congress_trades"):
            self.data_service.load_congress_trades()

    @Slot(object)
    def _on_investors(self, rows: list):
        rows = rows or []
        self._investors_table.setRowCount(len(rows))
        for r, inv in enumerate(rows):
            self._investors_table.setItem(r, 0, _cell(inv.get("display_name", "--"), _ORANGE))
            self._investors_table.setItem(
                r, 1, _cell(_CATEGORY_LABELS.get(inv.get("category"), inv.get("category", "--")))
            )
            vehicle = inv.get("vehicle") or inv.get("role") or "--"
            self._investors_table.setItem(r, 2, _cell(vehicle))
            self._investors_table.setItem(r, 3, _cell(", ".join(inv.get("tags", [])), _TEXT_DIM))

    @Slot(object)
    def _on_congress(self, rows: list):
        rows = rows or []
        self._congress_table.setRowCount(len(rows))
        for r, t in enumerate(rows):
            tx_type = (t.get("transaction_type") or "").upper()
            color = _GREEN if tx_type == "BUY" else _RED if tx_type == "SELL" else _TEXT
            low = t.get("amount_range_low")
            high = t.get("amount_range_high")
            amount = f"${low:,.0f}-${high:,.0f}" if (low and high) else "--"
            self._congress_table.setItem(r, 0, _cell(t.get("politician_name", "--"), _ORANGE))
            self._congress_table.setItem(r, 1, _cell(t.get("ticker") or "--"))
            self._congress_table.setItem(r, 2, _cell(tx_type or "--", color))
            self._congress_table.setItem(r, 3, _cell(str(t.get("transaction_date") or "--")))
            self._congress_table.setItem(r, 4, _cell(amount, align_right=True))
            self._congress_table.setItem(r, 5, _cell(t.get("size_bucket") or "--"))
            self._congress_table.setItem(
                r, 6, _cell("LATE" if t.get("is_late_disclosure") else "", _RED)
            )
