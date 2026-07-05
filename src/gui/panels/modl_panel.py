"""MODL -- Automatic Model Builder panel.

Shows the auto-assembled analytical model (composite score, rating, sub-scores,
drivers, and sections) for the loaded company.
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

_BULLISH_RATINGS = {"STRONG_BUY", "BUY", "EXPANSION"}
_BEARISH_RATINGS = {"SELL", "STRONG_SELL", "CONTRACTION", "DISTRESSED"}


def _rating_color(rating: str) -> str:
    if rating in _BULLISH_RATINGS:
        return _GREEN
    if rating in _BEARISH_RATINGS:
        return _RED
    return _ORANGE


class AutoModelPanel(BasePanel):
    """MODL -- automatic analytical model builder."""

    panel_name = "MODL"
    panel_title = "MODL - Auto Model"

    def __init__(self, data_service, app_state, parent=None):
        super().__init__(data_service, app_state, parent)
        self.setStyleSheet(f"background: {_BG};")

        header = QLabel("AUTOMATIC MODEL BUILDER")
        header.setStyleSheet(
            f"color: {_ORANGE}; font-family: {_FONT}; font-size: 14px; font-weight: bold;"
        )
        self._layout.addWidget(header)

        self._headline = QLabel("Load a company (e.g. AAPL MODL) to build its model")
        self._headline.setStyleSheet(f"color: {_TEXT}; font-family: {_FONT}; font-size: 13px;")
        self._layout.addWidget(self._headline)

        self._summary = QLabel("")
        self._summary.setWordWrap(True)
        self._summary.setStyleSheet(f"color: {_TEXT_DIM}; font-family: {_FONT}; font-size: 11px;")
        self._layout.addWidget(self._summary)

        self._scores_table = QTableWidget()
        self._scores_table.setColumnCount(2)
        self._scores_table.setHorizontalHeaderLabels(["Sub-Score", "Value (0-100)"])
        self._scores_table.verticalHeader().setVisible(False)
        self._scores_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._scores_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._scores_table.setStyleSheet(_TABLE_STYLE)
        self._layout.addWidget(self._scores_table)

        self._drivers = QLabel("")
        self._drivers.setWordWrap(True)
        self._drivers.setStyleSheet(f"color: {_TEXT}; font-family: {_FONT}; font-size: 12px;")
        self._layout.addWidget(self._drivers, stretch=1)

        if hasattr(data_service, "auto_model_loaded"):
            data_service.auto_model_loaded.connect(self._on_model)

    def activate(self, context: dict | None = None):
        context = context or {}
        entity_id = context.get("entity_id")
        if entity_id and hasattr(self.data_service, "run_auto_model"):
            self._headline.setText("Building model...")
            self.data_service.run_auto_model(entity_id)

    @Slot(object)
    def _on_model(self, model: dict):
        if not model:
            self._headline.setText("No model data available")
            return
        rating = model.get("rating", "NEUTRAL")
        score = model.get("composite_score", 0.0)
        subject = model.get("subject") or "Company"
        self._headline.setText(f"{subject}  —  {rating}  ({score:.0f}/100)")
        self._headline.setStyleSheet(
            f"color: {_rating_color(rating)}; font-family: {_FONT}; font-size: 16px; font-weight: bold;"
        )
        self._summary.setText(model.get("summary", ""))

        scores = model.get("scores", {})
        self._scores_table.setRowCount(len(scores))
        for r, (k, v) in enumerate(scores.items()):
            key_item = QTableWidgetItem(k.replace("_", " ").title())
            key_item.setForeground(QColor(_TEXT_DIM))
            self._scores_table.setItem(r, 0, key_item)
            try:
                val_text = f"{float(v):.1f}"
            except (TypeError, ValueError):
                val_text = str(v)
            val_item = QTableWidgetItem(val_text)
            val_item.setForeground(QColor(_TEXT))
            val_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._scores_table.setItem(r, 1, val_item)

        drivers = model.get("drivers", [])
        if drivers:
            self._drivers.setText("Key drivers:\n" + "\n".join(f"  • {d}" for d in drivers))
        else:
            self._drivers.setText("")
