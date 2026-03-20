"""SCOR -- Scoring Models panel (E3: Piotroski, Altman, Beneish).

Displays composite financial health scores with component breakdowns.
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


def _fmt(val) -> str:
    if val is None:
        return "--"
    if isinstance(val, bool):
        return "PASS" if val else "FAIL"
    if isinstance(val, float):
        return f"{val:.2f}"
    return str(val)


class _ScoreTable(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._table = QTableWidget()
        self._table.setColumnCount(2)
        self._table.setHorizontalHeaderLabels(["Component", "Value"])
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.setStyleSheet(_TABLE_STYLE)
        layout.addWidget(self._table)

    def populate(self, items: list[tuple[str, str, str | None]]):
        """items: list of (label, value_str, color_override)."""
        self._table.setRowCount(len(items))
        for r, (key, val, color) in enumerate(items):
            k_item = QTableWidgetItem(key)
            k_item.setForeground(QColor(_TEXT_DIM))
            self._table.setItem(r, 0, k_item)
            v_item = QTableWidgetItem(val)
            v_item.setForeground(QColor(color or _TEXT))
            v_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(r, 1, v_item)


class ScorPanel(BasePanel):
    """SCOR -- scoring models panel."""

    panel_name = "SCOR"
    panel_title = "SCOR - Scoring Models"

    def __init__(self, data_service, app_state, parent=None):
        super().__init__(data_service, app_state, parent)
        self.setStyleSheet(f"background: {_BG};")

        self._header = QLabel("SCORING MODELS")
        self._header.setStyleSheet(
            f"color: {_ORANGE}; font-family: {_FONT}; font-size: 14px; font-weight: bold;"
        )
        self._layout.addWidget(self._header)

        self._entity_label = QLabel("Select a security to view scores")
        self._entity_label.setStyleSheet(f"color: {_TEXT}; font-family: {_FONT}; font-size: 12px;")
        self._layout.addWidget(self._entity_label)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(_TAB_STYLE)

        self._piotroski_table = _ScoreTable()
        self._altman_table = _ScoreTable()
        self._beneish_table = _ScoreTable()
        self._tabs.addTab(self._piotroski_table, "Piotroski F-Score")
        self._tabs.addTab(self._altman_table, "Altman Z-Score")
        self._tabs.addTab(self._beneish_table, "Beneish M-Score")
        self._layout.addWidget(self._tabs, stretch=1)

        if hasattr(data_service, "scores_loaded"):
            data_service.scores_loaded.connect(self._on_scores)

        self._current_entity_id: str | None = None

    def activate(self, context: dict | None = None):
        context = context or {}
        entity_id = context.get("entity_id")
        self._current_entity_id = entity_id
        if entity_id:
            self._entity_label.setText(context.get("entity_name", "Loading..."))
            if hasattr(self.data_service, "run_scores"):
                self.data_service.run_scores(entity_id)

    @Slot(object)
    def _on_scores(self, data: dict):
        if not data:
            return

        # Piotroski
        pio = data.get("piotroski", {})
        if pio:
            score = pio.get("f_score", pio.get("total_score"))
            color = _GREEN if score is not None and score >= 7 else (_RED if score is not None and score <= 3 else _TEXT)
            items = [("F-Score (Total)", _fmt(score), color)]
            for k, v in pio.items():
                if k not in ("f_score", "total_score", "entity_id", "calculation_date",
                             "data_quality", "result_id"):
                    c = _GREEN if v is True or (isinstance(v, (int, float)) and v > 0) else _RED if v is False else None
                    items.append((k.replace("_", " ").title(), _fmt(v), c))
            self._piotroski_table.populate(items)

        # Altman
        alt = data.get("altman", {})
        if alt:
            z = alt.get("z_score")
            zone = alt.get("zone", "--")
            color = _GREEN if zone == "SAFE" else (_RED if zone == "DISTRESS" else _ORANGE)
            items = [("Z-Score", _fmt(z), color), ("Zone", str(zone), color)]
            for k, v in alt.items():
                if k not in ("z_score", "zone", "entity_id", "calculation_date",
                             "data_quality", "result_id"):
                    items.append((k.replace("_", " ").title(), _fmt(v), None))
            self._altman_table.populate(items)

        # Beneish
        ben = data.get("beneish", {})
        if ben:
            m = ben.get("m_score")
            flag = ben.get("likely_manipulator", False)
            color = _RED if flag else _GREEN
            items = [
                ("M-Score", _fmt(m), color),
                ("Likely Manipulator", "YES" if flag else "NO", color),
            ]
            for k, v in ben.items():
                if k not in ("m_score", "likely_manipulator", "entity_id",
                             "calculation_date", "data_quality", "result_id"):
                    items.append((k.replace("_", " ").title(), _fmt(v), None))
            self._beneish_table.populate(items)
