"""VAL -- Valuation panel (E2: DCF, WACC).

Displays DCF intrinsic value, WACC breakdown, and key valuation metrics.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
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
    QTableWidget::item:selected {{ background: #1e293b; }}
    QHeaderView::section {{
        background: {_BG}; color: {_ORANGE};
        font-family: {_FONT}; font-size: 11px; font-weight: bold;
        border: none; border-bottom: 1px solid {_BORDER}; padding: 4px 6px;
    }}
"""


def _fmt(val, decimals=2) -> str:
    if val is None:
        return "--"
    if isinstance(val, float):
        return f"{val:,.{decimals}f}"
    return str(val)


def _pct(val) -> str:
    if val is None:
        return "--"
    return f"{val * 100:.2f}%"


class _KVTable(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._table = QTableWidget()
        self._table.setColumnCount(2)
        self._table.setHorizontalHeaderLabels(["Metric", "Value"])
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.setStyleSheet(_TABLE_STYLE)
        layout.addWidget(self._table)

    def populate(self, items: list[tuple[str, str]]):
        self._table.setRowCount(len(items))
        for r, (key, val) in enumerate(items):
            k_item = QTableWidgetItem(key)
            k_item.setForeground(QColor(_TEXT_DIM))
            self._table.setItem(r, 0, k_item)
            v_item = QTableWidgetItem(val)
            v_item.setForeground(QColor(_TEXT))
            v_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(r, 1, v_item)


class ValPanel(BasePanel):
    """VAL -- DCF valuation and WACC panel."""

    panel_name = "VAL"
    panel_title = "VAL - Valuation"

    def __init__(self, data_service, app_state, parent=None):
        super().__init__(data_service, app_state, parent)
        self.setStyleSheet(f"background: {_BG};")

        self._header = QLabel("VALUATION")
        self._header.setStyleSheet(
            f"color: {_ORANGE}; font-family: {_FONT}; font-size: 14px; font-weight: bold;"
        )
        self._layout.addWidget(self._header)

        self._security_label = QLabel("Select a security to view valuation")
        self._security_label.setStyleSheet(f"color: {_TEXT}; font-family: {_FONT}; font-size: 12px;")
        self._layout.addWidget(self._security_label)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(_TAB_STYLE)

        self._dcf_table = _KVTable()
        self._wacc_table = _KVTable()
        self._tabs.addTab(self._dcf_table, "DCF Valuation")
        self._tabs.addTab(self._wacc_table, "WACC Breakdown")
        self._layout.addWidget(self._tabs, stretch=1)

        if hasattr(data_service, "dcf_loaded"):
            data_service.dcf_loaded.connect(self._on_dcf)
        if hasattr(data_service, "wacc_loaded"):
            data_service.wacc_loaded.connect(self._on_wacc)

        self._current_security_id: str | None = None

    def activate(self, context: dict | None = None):
        context = context or {}
        sec_id = context.get("security_id")
        self._current_security_id = sec_id
        if sec_id:
            self._security_label.setText(context.get("security_name", "Loading..."))
            if hasattr(self.data_service, "run_dcf"):
                self.data_service.run_dcf(sec_id)
            if hasattr(self.data_service, "run_wacc"):
                self.data_service.run_wacc(sec_id)

    @Slot(object)
    def _on_dcf(self, data: dict):
        if not data:
            return
        items = [
            ("Method", str(data.get("method", "--"))),
            ("Implied Price", f"${_fmt(data.get('implied_share_price'))}"),
            ("Current Price", f"${_fmt(data.get('current_price'))}"),
            ("Upside / Downside", _pct(data.get("upside_downside_pct"))),
            ("Enterprise Value", _fmt(data.get("enterprise_value"), 0)),
            ("Equity Value", _fmt(data.get("equity_value"), 0)),
            ("Terminal Value", _fmt(data.get("terminal_value"), 0)),
            ("Projection Years", str(data.get("projection_years", "--"))),
            ("Terminal Growth", _pct(data.get("terminal_growth_rate"))),
            ("Data Quality", str(data.get("data_quality", "--"))),
        ]
        self._dcf_table.populate(items)

    @Slot(object)
    def _on_wacc(self, data: dict):
        if not data:
            return
        items = [
            ("WACC", _pct(data.get("wacc"))),
            ("Cost of Equity", _pct(data.get("cost_of_equity"))),
            ("Risk-Free Rate", _pct(data.get("risk_free_rate"))),
            ("Equity Risk Premium", _pct(data.get("equity_risk_premium"))),
            ("Beta", _fmt(data.get("beta"))),
            ("Cost of Debt (Pre-Tax)", _pct(data.get("cost_of_debt_pretax"))),
            ("Cost of Debt (After-Tax)", _pct(data.get("cost_of_debt_aftertax"))),
            ("Effective Tax Rate", _pct(data.get("effective_tax_rate"))),
            ("Debt Weight", _pct(data.get("debt_weight"))),
            ("Equity Weight", _pct(data.get("equity_weight"))),
            ("Market Cap", _fmt(data.get("market_cap"), 0)),
            ("Total Debt", _fmt(data.get("total_debt"), 0)),
        ]
        self._wacc_table.populate(items)
