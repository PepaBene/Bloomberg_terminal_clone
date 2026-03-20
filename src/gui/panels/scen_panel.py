"""SCEN -- Scenario & Sensitivity panel (E8).

Displays sensitivity tables, tornado charts, shock analysis, and
breakeven search results from the E8 Scenario Engine.
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


def _fmt(val, decimals=2) -> str:
    if val is None:
        return "--"
    if isinstance(val, float):
        return f"{val:.{decimals}f}"
    return str(val)


def _pct(val) -> str:
    if val is None:
        return "--"
    return f"{val * 100:.2f}%"


class _SensitivityGrid(QWidget):
    """Displays a 2D sensitivity matrix as a QTableWidget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._info = QLabel("Run a sensitivity analysis to see results")
        self._info.setStyleSheet(f"color: {_TEXT_DIM}; font-family: {_FONT}; font-size: 11px;")
        layout.addWidget(self._info)

        self._table = QTableWidget()
        self._table.verticalHeader().setVisible(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setStyleSheet(_TABLE_STYLE)
        layout.addWidget(self._table)

    def populate(self, data: dict):
        row_vals = data.get("row_values", [])
        col_vals = data.get("col_values", [])
        grid = data.get("grid", [])
        row_var = data.get("row_variable", "Row")
        col_var = data.get("col_variable", "Col")
        base = data.get("base_case_value")

        self._info.setText(
            f"{row_var} vs {col_var}  |  Base case: ${_fmt(base)}"
        )

        ncols = len(col_vals)
        nrows = len(row_vals)
        self._table.setColumnCount(ncols)
        self._table.setRowCount(nrows)

        # Headers
        self._table.setHorizontalHeaderLabels([f"{v:.3f}" for v in col_vals])
        self._table.setVerticalHeaderLabels([f"{v:.3f}" for v in row_vals])

        for r in range(nrows):
            for c in range(ncols):
                val = grid[r][c] if r < len(grid) and c < len(grid[r]) else None
                cell = QTableWidgetItem(f"${_fmt(val)}")
                cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if val is not None and base is not None:
                    if val > base:
                        cell.setForeground(QColor(_GREEN))
                    elif val < base:
                        cell.setForeground(QColor(_RED))
                    else:
                        cell.setForeground(QColor(_ORANGE))
                else:
                    cell.setForeground(QColor(_TEXT))
                self._table.setItem(r, c, cell)

        self._table.resizeColumnsToContents()


class _TornadoTable(QWidget):
    """Displays tornado chart data as a table."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._info = QLabel("Run a tornado analysis to see results")
        self._info.setStyleSheet(f"color: {_TEXT_DIM}; font-family: {_FONT}; font-size: 11px;")
        layout.addWidget(self._info)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["Variable", "Low", "High", "Range", "Impact"])
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in range(1, 5):
            self._table.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setStyleSheet(_TABLE_STYLE)
        layout.addWidget(self._table)

    def populate(self, data: dict):
        bars = data.get("bars", [])
        base = data.get("base_case_value")
        self._info.setText(f"Base case: ${_fmt(base)}  |  {len(bars)} variables")

        self._table.setRowCount(len(bars))
        for r, bar in enumerate(bars):
            var_name = bar.get("variable", "--")
            low_out = bar.get("low_output")
            high_out = bar.get("high_output")
            impact = bar.get("impact_range", 0)

            self._table.setItem(r, 0, self._cell(var_name, _TEXT))
            self._table.setItem(r, 1, self._cell(f"${_fmt(low_out)}", _RED))
            self._table.setItem(r, 2, self._cell(f"${_fmt(high_out)}", _GREEN))
            self._table.setItem(r, 3, self._cell(f"${_fmt(impact)}", _ORANGE))
            pct = (impact / base * 100) if base and impact else 0
            self._table.setItem(r, 4, self._cell(f"{pct:.1f}%", _TEXT_DIM))

    @staticmethod
    def _cell(text: str, color: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setForeground(QColor(color))
        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return item


class _ShockTable(QWidget):
    """Displays shock analysis results."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._info = QLabel("Run a shock analysis to see results")
        self._info.setStyleSheet(f"color: {_TEXT_DIM}; font-family: {_FONT}; font-size: 11px;")
        layout.addWidget(self._info)

        self._table = QTableWidget()
        self._table.setColumnCount(2)
        self._table.setHorizontalHeaderLabels(["Metric", "Value"])
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.setStyleSheet(_TABLE_STYLE)
        layout.addWidget(self._table)

    def populate(self, data: dict):
        base = data.get("base_case_value")
        shocked = data.get("shocked_value")
        impact_pct = data.get("impact_pct")

        items = [
            ("Base Case Value", f"${_fmt(base)}"),
            ("Shocked Value", f"${_fmt(shocked)}"),
            ("Impact", _pct(impact_pct)),
        ]

        individual = data.get("individual_impacts", [])
        for imp in individual:
            var = imp.get("variable", "--")
            val = imp.get("impact")
            items.append((f"  {var}", f"${_fmt(val)}"))

        self._info.setText(f"Base: ${_fmt(base)}  →  Shocked: ${_fmt(shocked)}")

        self._table.setRowCount(len(items))
        for r, (key, val) in enumerate(items):
            k_item = QTableWidgetItem(key)
            k_item.setForeground(QColor(_TEXT_DIM))
            self._table.setItem(r, 0, k_item)
            v_item = QTableWidgetItem(val)
            v_item.setForeground(QColor(_TEXT))
            v_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(r, 1, v_item)


class ScenPanel(BasePanel):
    """SCEN -- scenario & sensitivity analysis panel."""

    panel_name = "SCEN"
    panel_title = "SCEN - Scenario Analysis"

    def __init__(self, data_service, app_state, parent=None):
        super().__init__(data_service, app_state, parent)
        self.setStyleSheet(f"background: {_BG};")

        self._header = QLabel("SCENARIO & SENSITIVITY ANALYSIS")
        self._header.setStyleSheet(
            f"color: {_ORANGE}; font-family: {_FONT}; font-size: 14px; font-weight: bold;"
        )
        self._layout.addWidget(self._header)

        self._security_label = QLabel("Select a security to run scenario analysis")
        self._security_label.setStyleSheet(f"color: {_TEXT}; font-family: {_FONT}; font-size: 12px;")
        self._layout.addWidget(self._security_label)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(_TAB_STYLE)

        self._sensitivity_grid = _SensitivityGrid()
        self._tornado_table = _TornadoTable()
        self._shock_table = _ShockTable()
        self._tabs.addTab(self._sensitivity_grid, "2D Sensitivity")
        self._tabs.addTab(self._tornado_table, "Tornado")
        self._tabs.addTab(self._shock_table, "Shock Analysis")
        self._layout.addWidget(self._tabs, stretch=1)

        if hasattr(data_service, "scenario_loaded"):
            data_service.scenario_loaded.connect(self._on_scenario)

        self._current_security_id: str | None = None

    def activate(self, context: dict | None = None):
        context = context or {}
        sec_id = context.get("security_id")
        self._current_security_id = sec_id
        if sec_id:
            self._security_label.setText(context.get("security_name", "Loading..."))
            if hasattr(self.data_service, "run_scenario"):
                self.data_service.run_scenario(sec_id, "sensitivity_2d")

    @Slot(object)
    def _on_scenario(self, data: dict):
        if not data:
            return

        # Detect type by keys present
        if "grid" in data:
            self._sensitivity_grid.populate(data)
            self._tabs.setCurrentIndex(0)
        elif "bars" in data:
            self._tornado_table.populate(data)
            self._tabs.setCurrentIndex(1)
        elif "shocked_value" in data:
            self._shock_table.populate(data)
            self._tabs.setCurrentIndex(2)
