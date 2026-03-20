"""OWN -- Ownership Analysis panel.

Displays institutional holdings, insider transactions, and an ownership
summary with a breakdown pie chart and key statistics.

Bloomberg mnemonic: OWN / HDS
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
    QTabWidget,
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

_INSTITUTIONAL_COLUMNS = [
    ColumnConfig("Institution Name", "institution_name", 220, "left", "text"),
    ColumnConfig("Type", "institution_type", 130, "left", "text"),
    ColumnConfig("Shares Held", "shares_held", 120, "right", "number", decimals=0),
    ColumnConfig("Market Value", "market_value", 140, "right", "currency", decimals=0),
    ColumnConfig("% Outstanding", "pct_outstanding", 110, "right", "percent"),
    ColumnConfig("Change (QoQ)", "change_qoq", 110, "right", "percent", color_code=True),
    ColumnConfig("Filing Date", "filing_date", 110, "center", "date"),
]

_INSIDER_COLUMNS = [
    ColumnConfig("Insider Name", "insider_name", 180, "left", "text"),
    ColumnConfig("Title", "title", 160, "left", "text"),
    ColumnConfig("Transaction", "transaction_type", 110, "center", "text"),
    ColumnConfig("Shares", "shares", 100, "right", "number", decimals=0),
    ColumnConfig("Value", "value", 130, "right", "currency", decimals=0),
    ColumnConfig("Date", "date", 110, "center", "date"),
]


# ======================================================================
# Simple pie-chart widget (no external dep)
# ======================================================================

class _OwnershipPieChart(QWidget):
    """Minimal pie chart for ownership breakdown."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._slices: list[tuple[str, float, QColor]] = []
        self.setMinimumSize(200, 200)

    def set_data(self, slices: list[tuple[str, float, QColor]]) -> None:
        self._slices = slices
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        if not self._slices:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        size = min(self.width(), self.height()) - 20
        x = (self.width() - size) // 2
        y = 10

        total = sum(s[1] for s in self._slices) or 1.0
        start_angle = 90 * 16  # 12 o'clock

        for label, value, color in self._slices:
            span = int((value / total) * 360 * 16)
            painter.setPen(QPen(QColor(BORDER), 1))
            painter.setBrush(color)
            painter.drawPie(x, y, size, size, start_angle, span)
            start_angle += span

        # Legend below
        legend_y = y + size + 12
        font = QFont("Consolas", 9)
        painter.setFont(font)
        for i, (label, value, color) in enumerate(self._slices):
            lx = x + (i * 160)
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(lx, legend_y, 10, 10)
            painter.setPen(QColor(TEXT_PRIMARY))
            pct = (value / total) * 100
            painter.drawText(lx + 14, legend_y + 10, f"{label}: {pct:.1f}%")

        painter.end()


# ======================================================================
# Key-value stat widget
# ======================================================================

class _StatCard(QWidget):
    """Single key-value stat displayed with Bloomberg styling."""

    def __init__(self, label: str, value: str = "--", parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        self._label = QLabel(label)
        self._label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 9pt; font-weight: bold;"
        )
        self._value = QLabel(value)
        self._value.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 12pt; font-weight: bold;"
        )
        layout.addWidget(self._label)
        layout.addWidget(self._value)

        self.setStyleSheet(
            f"background-color: {BG_SURFACE}; border: 1px solid {BORDER}; border-radius: 3px;"
        )

    def set_value(self, value: str) -> None:
        self._value.setText(value)


# ======================================================================
# OWN Panel
# ======================================================================

class OwnPanel(BasePanel):
    """Ownership analysis panel (OWN)."""

    panel_name = "OWN"
    panel_title = "Ownership Analysis"

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

        # Tab widget
        self._tabs = QTabWidget()
        self._layout.addWidget(self._tabs)

        # --- Tab 1: Institutional Holdings ---
        self._inst_model = GenericTableModel(_INSTITUTIONAL_COLUMNS)
        self._inst_table = self._make_table(self._inst_model)
        self._tabs.addTab(self._inst_table, "Institutional Holdings")

        # --- Tab 2: Insider Holdings ---
        self._insider_model = GenericTableModel(_INSIDER_COLUMNS)
        self._insider_table = self._make_table(self._insider_model)
        self._tabs.addTab(self._insider_table, "Insider Holdings")

        # --- Tab 3: Ownership Summary ---
        summary_widget = QWidget()
        summary_layout = QVBoxLayout(summary_widget)
        summary_layout.setContentsMargins(4, 4, 4, 4)
        summary_layout.setSpacing(6)

        # Pie chart
        self._pie = _OwnershipPieChart()
        self._pie.setMinimumHeight(260)
        summary_layout.addWidget(self._pie)

        # Stats row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(8)
        self._stat_total_inst = _StatCard("Total Institutions")
        self._stat_top10 = _StatCard("Top 10 Concentration")
        self._stat_insider_pct = _StatCard("Insider Ownership %")
        self._stat_short_interest = _StatCard("Short Interest Ratio")
        for w in (self._stat_total_inst, self._stat_top10,
                  self._stat_insider_pct, self._stat_short_interest):
            stats_row.addWidget(w)
        summary_layout.addLayout(stats_row)

        self._tabs.addTab(summary_widget, "Ownership Summary")

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
        if hasattr(self.data_service, "ownership_loaded"):
            self.data_service.ownership_loaded.connect(self._on_ownership_loaded)

    # ------------------------------------------------------------------
    # Activation
    # ------------------------------------------------------------------

    def activate(self, context: dict | None = None) -> None:
        security_id = (
            (context or {}).get("security_id")
            or self.app_state.current_security_id
        )
        if security_id and hasattr(self.data_service, "load_ownership"):
            self.data_service.load_ownership(security_id)

    # ------------------------------------------------------------------
    # Data slots
    # ------------------------------------------------------------------

    @Slot(object)
    def _on_ownership_loaded(self, data: dict[str, Any]) -> None:
        """Populate all three tabs from the data_service payload."""
        # Institutional holdings
        institutional = data.get("institutional_holdings", [])
        self._inst_model.set_data(institutional)
        # Default sort by market value descending
        if institutional:
            self._inst_model.sort(3, Qt.SortOrder.DescendingOrder)

        # Insider holdings -- color-code buys/sells via transaction_type
        insider = data.get("insider_holdings", [])
        self._insider_model.set_data(insider)

        # Summary
        summary = data.get("summary", {})
        inst_pct = summary.get("institutional_pct", 0)
        insider_pct = summary.get("insider_pct", 0)
        retail_pct = max(0, 100 - inst_pct - insider_pct)

        self._pie.set_data([
            ("Institutional", inst_pct, QColor(BLOOMBERG_ORANGE)),
            ("Insider", insider_pct, QColor(POSITIVE)),
            ("Retail", retail_pct, QColor(TEXT_SECONDARY)),
        ])

        self._stat_total_inst.set_value(str(summary.get("total_institutions", "--")))
        top10 = summary.get("top10_concentration")
        self._stat_top10.set_value(f"{top10:.1f}%" if top10 is not None else "--")
        ins_pct = summary.get("insider_pct")
        self._stat_insider_pct.set_value(f"{ins_pct:.2f}%" if ins_pct is not None else "--")
        sir = summary.get("short_interest_ratio")
        self._stat_short_interest.set_value(f"{sir:.2f}" if sir is not None else "--")
