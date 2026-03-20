"""CACS -- Corporate Actions panel.

Displays a timeline of corporate actions with tabbed detail views for
all actions, dividends, stock splits, and M&A activity.

Bloomberg mnemonic: CACS
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor, QFont, QPainter, QPen
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
    SELECTION,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING,
)
from src.gui.panels.base_panel import BasePanel
from src.gui.table_models.generic_table_model import ColumnConfig, GenericTableModel

logger = logging.getLogger(__name__)

# ======================================================================
# Column definitions
# ======================================================================

_ALL_ACTIONS_COLUMNS = [
    ColumnConfig("Action Type", "action_type", 140, "left", "text"),
    ColumnConfig("Status", "status", 100, "center", "text"),
    ColumnConfig("Effective Date", "effective_date", 110, "center", "date"),
    ColumnConfig("Record Date", "record_date", 110, "center", "date"),
    ColumnConfig("Description", "description", 300, "left", "text"),
]

_DIVIDEND_COLUMNS = [
    ColumnConfig("Ex-Date", "ex_date", 100, "center", "date"),
    ColumnConfig("Record Date", "record_date", 100, "center", "date"),
    ColumnConfig("Payment Date", "payment_date", 100, "center", "date"),
    ColumnConfig("Amount", "amount", 100, "right", "currency"),
    ColumnConfig("Type", "dividend_type", 110, "center", "text"),
    ColumnConfig("Currency", "currency", 80, "center", "text"),
    ColumnConfig("Yield", "yield_pct", 80, "right", "percent"),
]

_SPLIT_COLUMNS = [
    ColumnConfig("Effective Date", "effective_date", 120, "center", "date"),
    ColumnConfig("Split Ratio", "split_ratio", 120, "center", "text"),
    ColumnConfig("Adjustment Factor", "adjustment_factor", 140, "right", "number", decimals=4),
]

_MA_COLUMNS = [
    ColumnConfig("Announcement Date", "announcement_date", 130, "center", "date"),
    ColumnConfig("Target", "target", 180, "left", "text"),
    ColumnConfig("Acquirer", "acquirer", 180, "left", "text"),
    ColumnConfig("Consideration", "consideration_type", 120, "center", "text"),
    ColumnConfig("Value", "deal_value", 140, "right", "currency", decimals=0),
]


# ======================================================================
# Timeline widget
# ======================================================================

class _ActionTimeline(QWidget):
    """Horizontal timeline showing corporate action events."""

    # Mapping of action type prefixes to colours
    _TYPE_COLORS = {
        "CASH_DIVIDEND": POSITIVE,
        "STOCK_DIVIDEND": POSITIVE,
        "STOCK_SPLIT": BLOOMBERG_ORANGE,
        "REVERSE_SPLIT": WARNING,
        "MERGER": "#3b82f6",
        "ACQUISITION": "#3b82f6",
        "SPIN_OFF": "#a855f7",
        "SHARE_BUYBACK": "#06b6d4",
    }

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._events: list[dict[str, Any]] = []
        self.setMinimumHeight(90)
        self.setMaximumHeight(110)

    def set_data(self, events: list[dict[str, Any]]) -> None:
        """Each dict: effective_date (str/date), action_type, description."""
        self._events = sorted(events, key=lambda e: str(e.get("effective_date", "")))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        margin_l = 30
        margin_r = 30
        line_y = h // 2
        usable = w - margin_l - margin_r

        # Background
        painter.fillRect(0, 0, w, h, QColor(BG_PANEL))

        if not self._events:
            painter.setPen(QColor(TEXT_SECONDARY))
            painter.setFont(QFont("Consolas", 9))
            painter.drawText(margin_l, line_y + 4, "No corporate action events to display")
            painter.end()
            return

        # Draw main line
        painter.setPen(QPen(QColor(BORDER), 2))
        painter.drawLine(margin_l, line_y, w - margin_r, line_y)

        n = len(self._events)
        font = QFont("Consolas", 7)
        painter.setFont(font)

        for i, ev in enumerate(self._events):
            x = margin_l + int(usable * i / max(n - 1, 1)) if n > 1 else margin_l + usable // 2
            action_type = str(ev.get("action_type", ""))
            color_hex = self._TYPE_COLORS.get(action_type, TEXT_SECONDARY)
            color = QColor(color_hex)

            # Dot
            painter.setBrush(color)
            painter.setPen(QPen(color, 2))
            painter.drawEllipse(x - 5, line_y - 5, 10, 10)

            # Date label (alternating above/below)
            date_str = str(ev.get("effective_date", ""))[:10]
            if i % 2 == 0:
                painter.setPen(QColor(TEXT_SECONDARY))
                painter.drawText(x - 25, line_y - 14, date_str)
                painter.setPen(color)
                painter.drawText(x - 25, line_y - 26, action_type[:12])
            else:
                painter.setPen(QColor(TEXT_SECONDARY))
                painter.drawText(x - 25, line_y + 22, date_str)
                painter.setPen(color)
                painter.drawText(x - 25, line_y + 34, action_type[:12])

        painter.end()


# ======================================================================
# CACS Panel
# ======================================================================

class CacsPanel(BasePanel):
    """Corporate Actions panel (CACS)."""

    panel_name = "CACS"
    panel_title = "Corporate Actions"

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

        # Timeline at top
        self._timeline = _ActionTimeline()
        self._timeline.setStyleSheet(
            f"border: 1px solid {BORDER}; border-radius: 3px;"
        )
        self._layout.addWidget(self._timeline)

        # Tab widget for detail tables
        self._tabs = QTabWidget()
        self._layout.addWidget(self._tabs)

        # --- Tab 1: All Actions ---
        self._all_model = GenericTableModel(_ALL_ACTIONS_COLUMNS)
        self._all_table = self._make_table(self._all_model)
        self._tabs.addTab(self._all_table, "All Actions")

        # --- Tab 2: Dividends ---
        self._div_model = GenericTableModel(_DIVIDEND_COLUMNS)
        self._div_table = self._make_table(self._div_model)
        self._tabs.addTab(self._div_table, "Dividends")

        # --- Tab 3: Splits ---
        self._split_model = GenericTableModel(_SPLIT_COLUMNS)
        self._split_table = self._make_table(self._split_model)
        self._tabs.addTab(self._split_table, "Splits")

        # --- Tab 4: M&A ---
        self._ma_model = GenericTableModel(_MA_COLUMNS)
        self._ma_table = self._make_table(self._ma_model)
        self._tabs.addTab(self._ma_table, "M&A")

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
        if hasattr(self.data_service, "corporate_actions_loaded"):
            self.data_service.corporate_actions_loaded.connect(
                self._on_corporate_actions_loaded
            )

    # ------------------------------------------------------------------
    # Activation
    # ------------------------------------------------------------------

    def activate(self, context: dict | None = None) -> None:
        security_id = (
            (context or {}).get("security_id")
            or self.app_state.current_security_id
        )
        if security_id and hasattr(self.data_service, "load_corporate_actions"):
            self.data_service.load_corporate_actions(security_id)

    # ------------------------------------------------------------------
    # Data slots
    # ------------------------------------------------------------------

    @Slot(object)
    def _on_corporate_actions_loaded(self, data: dict[str, Any]) -> None:
        """Populate timeline and all tabs from the data_service payload."""
        all_actions = data.get("all_actions", [])
        dividends = data.get("dividends", [])
        splits = data.get("splits", [])
        mergers = data.get("mergers", [])

        # Timeline uses all actions
        self._timeline.set_data(all_actions)

        # Tables
        self._all_model.set_data(all_actions)
        self._div_model.set_data(dividends)
        self._split_model.set_data(splits)
        self._ma_model.set_data(mergers)
