"""STRC -- Complex Financial Structure panel.

Shows the structural-complexity assessment for the loaded company: subsidiary
tree, multi-class voting wedge, off-balance-sheet exposure, and the debt
subordination waterfall.
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

_RATING_COLOR = {
    "SIMPLE": _GREEN,
    "MODERATE": _ORANGE,
    "COMPLEX": _RED,
    "VERY_COMPLEX": _RED,
}


def _kv_table() -> QTableWidget:
    t = QTableWidget()
    t.setColumnCount(2)
    t.setHorizontalHeaderLabels(["Metric", "Value"])
    t.verticalHeader().setVisible(False)
    t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setStyleSheet(_TABLE_STYLE)
    return t


def _populate_kv(table: QTableWidget, items: list[tuple[str, str]]):
    table.setRowCount(len(items))
    for r, (k, v) in enumerate(items):
        key_item = QTableWidgetItem(str(k))
        key_item.setForeground(QColor(_TEXT_DIM))
        table.setItem(r, 0, key_item)
        val_item = QTableWidgetItem(str(v))
        val_item.setForeground(QColor(_TEXT))
        val_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        table.setItem(r, 1, val_item)


class ComplexStructurePanel(BasePanel):
    """STRC -- complex financial structure analysis."""

    panel_name = "STRC"
    panel_title = "STRC - Complex Structure"

    def __init__(self, data_service, app_state, parent=None):
        super().__init__(data_service, app_state, parent)
        self.setStyleSheet(f"background: {_BG};")

        header = QLabel("COMPLEX FINANCIAL STRUCTURE")
        header.setStyleSheet(
            f"color: {_ORANGE}; font-family: {_FONT}; font-size: 14px; font-weight: bold;"
        )
        self._layout.addWidget(header)

        self._headline = QLabel("Load a company (e.g. AAPL STRC) to analyze its structure")
        self._headline.setStyleSheet(f"color: {_TEXT}; font-family: {_FONT}; font-size: 14px;")
        self._layout.addWidget(self._headline)

        self._flags = QLabel("")
        self._flags.setWordWrap(True)
        self._flags.setStyleSheet(f"color: {_RED}; font-family: {_FONT}; font-size: 11px;")
        self._layout.addWidget(self._flags)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(_TAB_STYLE)
        self._tree_table = _kv_table()
        self._equity_table = _kv_table()
        self._obs_table = _kv_table()
        self._debt_table = _kv_table()
        self._tabs.addTab(self._tree_table, "Subsidiary Tree")
        self._tabs.addTab(self._equity_table, "Share Classes")
        self._tabs.addTab(self._obs_table, "Off-Balance-Sheet")
        self._tabs.addTab(self._debt_table, "Debt Waterfall")
        self._layout.addWidget(self._tabs, stretch=1)

        if hasattr(data_service, "complex_structure_loaded"):
            data_service.complex_structure_loaded.connect(self._on_structure)

    def activate(self, context: dict | None = None):
        context = context or {}
        entity_id = context.get("entity_id")
        if entity_id and hasattr(self.data_service, "run_complex_structure"):
            self._headline.setText("Analyzing structure...")
            self.data_service.run_complex_structure(entity_id)

    @Slot(object)
    def _on_structure(self, report: dict):
        if not report:
            self._headline.setText("No structure data available")
            return
        rating = report.get("complexity_rating", "SIMPLE")
        score = report.get("complexity_score", 0.0)
        subject = report.get("subject") or "Company"
        self._headline.setText(f"{subject}  —  {rating}  (complexity {score:.0f}/100)")
        self._headline.setStyleSheet(
            f"color: {_RATING_COLOR.get(rating, _ORANGE)}; font-family: {_FONT}; "
            f"font-size: 16px; font-weight: bold;"
        )

        flags = report.get("flags", [])
        self._flags.setText(("⚠ " + "   ⚠ ".join(flags)) if flags else "")

        tree = report.get("subsidiary_tree", {})
        _populate_kv(self._tree_table, [
            ("Total subsidiaries", tree.get("total_subsidiaries", 0)),
            ("Distinct jurisdictions", tree.get("distinct_jurisdictions", 0)),
            ("Offshore subsidiaries", tree.get("offshore_count", 0)),
            ("Offshore %", f"{tree.get('offshore_pct', 0)}%"),
            ("VIE count", tree.get("vie_count", 0)),
            ("Max tree depth", tree.get("max_depth", 0)),
        ])

        eq = report.get("share_classes", {})
        _populate_kv(self._equity_table, [
            ("Dual-class?", "Yes" if eq.get("is_dual_class") else "No"),
            ("Number of classes", eq.get("num_classes", 0)),
            ("Control wedge", f"{eq.get('control_wedge', 0)}%"),
            ("Max voting %", f"{eq.get('max_voting_pct', 0)}%"),
            ("Assessment", eq.get("assessment", "--")),
        ])

        obs = report.get("off_balance_sheet", {})
        _populate_kv(self._obs_table, [
            ("Total off-B/S", f"{obs.get('total_off_balance_sheet', 0):,.0f}"),
            ("OBS / assets %", f"{obs.get('obs_to_assets_pct', '--')}"),
            ("Materiality", obs.get("materiality", "--")),
            ("Has VIE?", "Yes" if obs.get("has_vie") else "No"),
        ])

        debt = report.get("debt_waterfall", {})
        _populate_kv(self._debt_table, [
            ("Total debt", f"{debt.get('total_debt', 0):,.0f}"),
            ("Tranches", debt.get("num_tranches", 0)),
            ("Secured %", f"{debt.get('secured_pct', 0)}%"),
            ("Structural subordination?", "Yes" if debt.get("structural_subordination") else "No"),
            ("Assessment", debt.get("assessment", "--")),
        ])
