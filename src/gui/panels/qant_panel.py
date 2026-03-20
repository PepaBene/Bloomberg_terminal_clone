"""QANT -- Quantitative Analytics panel (E7: Regression, Correlation, Stats).

Displays quantitative analytics computed by the E7 Quant Engine.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
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


def _fmt(val, decimals=4) -> str:
    if val is None:
        return "--"
    if isinstance(val, float):
        return f"{val:.{decimals}f}"
    return str(val)


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


class QantPanel(BasePanel):
    """QANT -- quantitative analytics panel."""

    panel_name = "QANT"
    panel_title = "QANT - Quantitative Analytics"

    def __init__(self, data_service, app_state, parent=None):
        super().__init__(data_service, app_state, parent)
        self.setStyleSheet(f"background: {_BG};")

        self._header = QLabel("QUANTITATIVE ANALYTICS")
        self._header.setStyleSheet(
            f"color: {_ORANGE}; font-family: {_FONT}; font-size: 14px; font-weight: bold;"
        )
        self._layout.addWidget(self._header)

        self._security_label = QLabel("Select a security to view quant analytics")
        self._security_label.setStyleSheet(f"color: {_TEXT}; font-family: {_FONT}; font-size: 12px;")
        self._layout.addWidget(self._security_label)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(_TAB_STYLE)

        self._regression_table = _KVTable()
        self._stats_table = _KVTable()
        self._tabs.addTab(self._regression_table, "Regression")
        self._tabs.addTab(self._stats_table, "Descriptive Stats")
        self._layout.addWidget(self._tabs, stretch=1)

        if hasattr(data_service, "quant_loaded"):
            data_service.quant_loaded.connect(self._on_quant)

        self._current_security_id: str | None = None

    def activate(self, context: dict | None = None):
        context = context or {}
        sec_id = context.get("security_id")
        self._current_security_id = sec_id
        if sec_id:
            self._security_label.setText(context.get("security_name", "Loading..."))
            if hasattr(self.data_service, "run_quant"):
                self.data_service.run_quant(sec_id)

    @Slot(object)
    def _on_quant(self, data: dict):
        if not data:
            return

        # Regression tab
        reg_items = []
        for k, v in data.items():
            if "regression" in k.lower() or "coefficient" in k.lower() or "r_squared" in k.lower():
                reg_items.append((k.replace("_", " ").title(), _fmt(v)))
        if not reg_items:
            reg_items = [(k.replace("_", " ").title(), _fmt(v))
                         for k, v in list(data.items())[:15]
                         if isinstance(v, (int, float)) or v is None]
        self._regression_table.populate(reg_items)

        # Stats tab
        stat_items = []
        for k, v in data.items():
            if any(s in k.lower() for s in ("mean", "std", "skew", "kurt", "median", "min", "max", "count")):
                stat_items.append((k.replace("_", " ").title(), _fmt(v)))
        if not stat_items:
            stat_items = [(k.replace("_", " ").title(), _fmt(v))
                          for k, v in list(data.items())[15:30]
                          if isinstance(v, (int, float)) or v is None]
        self._stats_table.populate(stat_items)
