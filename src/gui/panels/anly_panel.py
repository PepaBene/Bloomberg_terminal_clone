"""ANLY -- Analytics panel (E1: Financial Ratios & DuPont Analysis).

Displays computed financial ratios across periods plus DuPont ROE
decomposition in a tabbed layout.
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
    QTabBar::tab:hover {{ color: {_TEXT}; }}
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


def _fmt(val: float | None) -> str:
    if val is None:
        return "--"
    return f"{val:.2f}"


class _KVTable(QWidget):
    """Simple two-column key-value table."""

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


class AnlyPanel(BasePanel):
    """ANLY -- financial ratios and DuPont analysis."""

    panel_name = "ANLY"
    panel_title = "ANLY - Financial Analytics"

    def __init__(self, data_service, app_state, parent=None):
        super().__init__(data_service, app_state, parent)
        self.setStyleSheet(f"background: {_BG};")

        self._header = QLabel("FINANCIAL ANALYTICS")
        self._header.setStyleSheet(
            f"color: {_ORANGE}; font-family: {_FONT}; font-size: 14px; font-weight: bold;"
        )
        self._layout.addWidget(self._header)

        self._entity_label = QLabel("Select a security to view analytics")
        self._entity_label.setStyleSheet(f"color: {_TEXT}; font-family: {_FONT}; font-size: 12px;")
        self._layout.addWidget(self._entity_label)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(_TAB_STYLE)

        self._ratios_table = _KVTable()
        self._dupont_table = _KVTable()
        self._tabs.addTab(self._ratios_table, "Key Ratios")
        self._tabs.addTab(self._dupont_table, "DuPont Analysis")
        self._layout.addWidget(self._tabs, stretch=1)

        if hasattr(data_service, "ratios_loaded"):
            data_service.ratios_loaded.connect(self._on_ratios)
        if hasattr(data_service, "dupont_loaded"):
            data_service.dupont_loaded.connect(self._on_dupont)

        self._current_entity_id: str | None = None

    def activate(self, context: dict | None = None):
        context = context or {}
        entity_id = context.get("entity_id")
        self._current_entity_id = entity_id
        if entity_id:
            self._entity_label.setText(context.get("entity_name", "Loading..."))
            if hasattr(self.data_service, "run_ratios"):
                self.data_service.run_ratios(entity_id)
            if hasattr(self.data_service, "run_dupont"):
                self.data_service.run_dupont(entity_id)

    @Slot(object)
    def _on_ratios(self, data: dict):
        if not data:
            return
        items = [(k.replace("_", " ").title(), _fmt(v)) for k, v in data.items()
                 if isinstance(v, (int, float)) or v is None]
        self._ratios_table.populate(items[:30])

    @Slot(object)
    def _on_dupont(self, data: dict):
        if not data:
            return
        items = [(k.replace("_", " ").title(), _fmt(v)) for k, v in data.items()
                 if isinstance(v, (int, float)) or v is None]
        self._dupont_table.populate(items[:20])
