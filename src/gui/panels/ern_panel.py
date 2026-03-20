"""ERN -- Estimates / Earnings panel.

Displays consensus estimates, earnings surprise history, and company
guidance in a vertically-split layout.

Bloomberg mnemonic: ERN / EE
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor, QPainter, QPen, QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from src.gui.core.theme import (
    BG_PANEL,
    BG_SURFACE,
    BLOOMBERG_ORANGE,
    BORDER,
    NEGATIVE,
    POSITIVE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from src.gui.panels.base_panel import BasePanel
from src.gui.table_models.generic_table_model import ColumnConfig, GenericTableModel

logger = logging.getLogger(__name__)

# ======================================================================
# Column definitions
# ======================================================================

_CONSENSUS_COLUMNS = [
    ColumnConfig("Metric", "metric", 110, "left", "text"),
    ColumnConfig("Period", "period", 100, "center", "text"),
    ColumnConfig("Mean", "mean", 100, "right", "number"),
    ColumnConfig("Median", "median", 100, "right", "number"),
    ColumnConfig("High", "high", 100, "right", "number"),
    ColumnConfig("Low", "low", 100, "right", "number"),
    ColumnConfig("# Estimates", "num_estimates", 90, "right", "number", decimals=0),
]

_GUIDANCE_COLUMNS = [
    ColumnConfig("Metric", "metric", 120, "left", "text"),
    ColumnConfig("Period", "period", 100, "center", "text"),
    ColumnConfig("Low", "low", 120, "right", "number"),
    ColumnConfig("High", "high", 120, "right", "number"),
    ColumnConfig("Tone", "tone", 100, "center", "text"),
]


# ======================================================================
# Earnings surprise bar chart (custom paint)
# ======================================================================

class _EarningsSurpriseChart(QWidget):
    """Horizontal bar chart comparing actual vs. estimate per quarter."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._data: list[dict[str, Any]] = []
        self.setMinimumHeight(160)

    def set_data(self, data: list[dict[str, Any]]) -> None:
        """Each dict: period, actual, estimate."""
        self._data = data
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        margin_left = 70
        margin_right = 20
        margin_top = 24
        margin_bottom = 24
        chart_w = w - margin_left - margin_right
        chart_h = h - margin_top - margin_bottom

        # Title
        painter.setPen(QColor(BLOOMBERG_ORANGE))
        painter.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        painter.drawText(margin_left, 16, "Earnings Surprises (Actual vs. Estimate)")

        if not self._data:
            painter.setPen(QColor(TEXT_SECONDARY))
            painter.setFont(QFont("Consolas", 9))
            painter.drawText(
                margin_left, margin_top + 40, "No earnings surprise data available"
            )
            painter.end()
            return

        n = len(self._data)
        bar_group_w = chart_w / max(n, 1)
        bar_w = max(int(bar_group_w * 0.3), 4)

        # Determine scale
        all_vals = []
        for d in self._data:
            if d.get("actual") is not None:
                all_vals.append(d["actual"])
            if d.get("estimate") is not None:
                all_vals.append(d["estimate"])
        if not all_vals:
            painter.end()
            return

        max_val = max(abs(v) for v in all_vals) or 1
        scale = chart_h / (max_val * 1.2)

        baseline_y = margin_top + chart_h // 2

        # Baseline
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawLine(margin_left, baseline_y, w - margin_right, baseline_y)

        font_small = QFont("Consolas", 8)
        painter.setFont(font_small)

        for i, d in enumerate(self._data):
            cx = margin_left + int(bar_group_w * (i + 0.5))
            estimate = d.get("estimate")
            actual = d.get("actual")

            # Estimate bar (grey)
            if estimate is not None:
                bh = int(abs(estimate) * scale)
                by = baseline_y - bh if estimate >= 0 else baseline_y
                painter.setBrush(QColor(TEXT_SECONDARY))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRect(cx - bar_w - 1, by, bar_w, bh)

            # Actual bar (green=beat, red=miss)
            if actual is not None:
                beat = (
                    actual >= estimate
                    if estimate is not None
                    else True
                )
                color = QColor(POSITIVE) if beat else QColor(NEGATIVE)
                bh = int(abs(actual) * scale)
                by = baseline_y - bh if actual >= 0 else baseline_y
                painter.setBrush(color)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRect(cx + 1, by, bar_w, bh)

            # Period label
            painter.setPen(QColor(TEXT_SECONDARY))
            period_label = str(d.get("period", ""))
            painter.drawText(
                cx - 20, baseline_y + chart_h // 2 + 14, period_label
            )

        painter.end()


# ======================================================================
# ERN Panel
# ======================================================================

class ErnPanel(BasePanel):
    """Estimates / Earnings panel (ERN)."""

    panel_name = "ERN"
    panel_title = "Estimates & Earnings"

    def __init__(self, data_service, app_state, parent=None):
        super().__init__(data_service, app_state, parent)
        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Header
        header = QLabel(f"  {self.panel_title}")
        header.setStyleSheet(
            f"color: {BLOOMBERG_ORANGE}; font-size: 11pt; font-weight: bold; "
            f"background-color: {BG_SURFACE}; padding: 4px; border: 1px solid {BORDER};"
        )
        self._layout.addWidget(header)

        # Splitter: top=consensus, mid=chart, bottom=guidance
        splitter = QSplitter(Qt.Orientation.Vertical)
        self._layout.addWidget(splitter)

        # --- Top: Consensus Estimates ---
        consensus_container = QWidget()
        cl = QVBoxLayout(consensus_container)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(2)
        clbl = QLabel("  CONSENSUS ESTIMATES")
        clbl.setStyleSheet(
            f"color: {BLOOMBERG_ORANGE}; font-size: 9pt; font-weight: bold; "
            f"background-color: {BG_SURFACE}; padding: 2px;"
        )
        cl.addWidget(clbl)
        self._consensus_model = GenericTableModel(_CONSENSUS_COLUMNS)
        self._consensus_table = self._make_table(self._consensus_model)
        cl.addWidget(self._consensus_table)
        splitter.addWidget(consensus_container)

        # --- Middle: Earnings Surprise Chart ---
        self._surprise_chart = _EarningsSurpriseChart()
        self._surprise_chart.setStyleSheet(
            f"background-color: {BG_PANEL}; border: 1px solid {BORDER};"
        )
        splitter.addWidget(self._surprise_chart)

        # --- Bottom: Company Guidance ---
        guidance_container = QWidget()
        gl = QVBoxLayout(guidance_container)
        gl.setContentsMargins(0, 0, 0, 0)
        gl.setSpacing(2)
        glbl = QLabel("  COMPANY GUIDANCE")
        glbl.setStyleSheet(
            f"color: {BLOOMBERG_ORANGE}; font-size: 9pt; font-weight: bold; "
            f"background-color: {BG_SURFACE}; padding: 2px;"
        )
        gl.addWidget(glbl)
        self._guidance_model = GenericTableModel(_GUIDANCE_COLUMNS)
        self._guidance_table = self._make_table(self._guidance_model)
        gl.addWidget(self._guidance_table)

        self._no_guidance_label = QLabel("  No guidance data available")
        self._no_guidance_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 9pt; padding: 8px;"
        )
        self._no_guidance_label.hide()
        gl.addWidget(self._no_guidance_label)

        splitter.addWidget(guidance_container)

        # Proportions
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 2)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_table(model: GenericTableModel) -> QTableView:
        table = QTableView()
        table.setModel(model)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        table.setSortingEnabled(True)
        table.verticalHeader().setDefaultSectionSize(22)
        table.verticalHeader().hide()
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        return table

    # ------------------------------------------------------------------
    # Signal connections
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        if hasattr(self.data_service, "estimates_loaded"):
            self.data_service.estimates_loaded.connect(self._on_estimates_loaded)

    # ------------------------------------------------------------------
    # Activation
    # ------------------------------------------------------------------

    def activate(self, context: dict | None = None) -> None:
        security_id = (
            (context or {}).get("security_id")
            or self.app_state.current_security_id
        )
        if security_id and hasattr(self.data_service, "load_estimates"):
            self.data_service.load_estimates(security_id)

    # ------------------------------------------------------------------
    # Data slots
    # ------------------------------------------------------------------

    @Slot(object)
    def _on_estimates_loaded(self, data: dict[str, Any]) -> None:
        """Populate all sections from the data_service payload."""
        # Consensus table
        consensus = data.get("consensus", [])
        self._consensus_model.set_data(consensus)

        # Earnings surprises chart
        surprises = data.get("surprises", [])
        self._surprise_chart.set_data(surprises)

        # Guidance table
        guidance = data.get("guidance", [])
        self._guidance_model.set_data(guidance)
        if guidance:
            self._no_guidance_label.hide()
            self._guidance_table.show()
        else:
            self._guidance_table.hide()
            self._no_guidance_label.show()
