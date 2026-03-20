"""SRCH -- Search results panel.

Displays search results from the command bar with tabs for Entities,
Securities, and All.  Double-clicking a row navigates to its DES panel.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSizePolicy,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .base_panel import BasePanel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------
_BG = "#0a0e17"
_BG_CARD = "#111827"
_TEXT = "#e2e8f0"
_TEXT_DIM = "#94a3b8"
_ORANGE = "#ff6600"
_GREEN = "#22c55e"
_RED = "#ef4444"
_BORDER = "#1e293b"
_FONT = "Consolas, 'Courier New', monospace"


# ---------------------------------------------------------------------------
# Results table
# ---------------------------------------------------------------------------
class _ResultsTable(QWidget):
    """Table of search results for a single scope (entities/securities/all)."""

    def __init__(self, columns: list[str], on_double_click, parent=None):
        super().__init__(parent)
        self._on_double_click = on_double_click
        self._rows: list[dict[str, Any]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._count_label = QLabel("0 results")
        self._count_label.setStyleSheet(
            f"color: {_TEXT_DIM}; font-family: {_FONT}; font-size: 10px;"
        )
        layout.addWidget(self._count_label)

        self._table = QTableWidget()
        self._columns = columns
        self._configure_table(self._table, columns)
        self._table.doubleClicked.connect(self._handle_double_click)
        layout.addWidget(self._table)

        # Show loading by default
        self._set_loading()

    def _set_loading(self):
        self._table.setRowCount(1)
        item = QTableWidgetItem("Enter a search query...")
        item.setForeground(QColor(_TEXT_DIM))
        self._table.setItem(0, 0, item)
        self._count_label.setText("")

    def populate(self, rows: list[dict[str, Any]]):
        """Fill table from search result dicts."""
        self._rows = rows
        self._count_label.setText(f"{len(rows)} results")

        if not rows:
            self._table.setRowCount(1)
            item = QTableWidgetItem("No results found")
            item.setForeground(QColor(_TEXT_DIM))
            self._table.setItem(0, 0, item)
            return

        self._table.setRowCount(len(rows))
        for r, row_data in enumerate(rows):
            for c, col_key in enumerate(self._columns):
                value = self._extract(row_data, col_key)
                item = QTableWidgetItem(value)
                item.setForeground(QColor(_TEXT))
                self._table.setItem(r, c, item)

    def _handle_double_click(self, index):
        row = index.row()
        if 0 <= row < len(self._rows):
            self._on_double_click(self._rows[row])

    @staticmethod
    def _extract(data: dict[str, Any], col: str) -> str:
        """Map a column header name to the best matching field."""
        col_lower = col.lower()
        # Direct field-name mappings
        mappings = {
            "name": ["legal_name", "name", "short_name"],
            "type": ["entity_type", "security_type"],
            "ticker": ["ticker", "short_name"],
            "country": ["incorporation_country", "country_code"],
            "status": ["status"],
            "asset class": ["asset_class"],
            "exchange": ["exchange", "primary_exchange_mic"],
            "score": ["score"],
            "identifiers": ["identifiers"],
        }
        candidates = mappings.get(col_lower, [col_lower])
        for field in candidates:
            val = data.get(field)
            if val is not None:
                if isinstance(val, list):
                    # e.g. identifiers list
                    return ", ".join(
                        f"{i.get('identifier_type', '')}:{i.get('identifier_value', '')}"
                        for i in val[:3]
                    )
                return str(val)
        return "--"

    @staticmethod
    def _configure_table(table: QTableWidget, headers: list[str]):
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setStyleSheet(f"""
            QTableWidget {{
                background: {_BG_CARD};
                color: {_TEXT};
                font-family: {_FONT};
                font-size: 12px;
                gridline-color: {_BORDER};
                border: 1px solid {_BORDER};
            }}
            QTableWidget::item {{
                padding: 3px 6px;
            }}
            QTableWidget::item:selected {{
                background: #1e293b;
            }}
            QHeaderView::section {{
                background: {_BG};
                color: {_ORANGE};
                font-family: {_FONT};
                font-size: 11px;
                font-weight: bold;
                border: none;
                border-bottom: 1px solid {_BORDER};
                padding: 4px 6px;
            }}
        """)


# ---------------------------------------------------------------------------
# Search Panel
# ---------------------------------------------------------------------------
class SearchPanel(BasePanel):
    """SRCH -- search results panel."""

    panel_name = "SRCH"
    panel_title = "Search Results"

    _ENTITY_COLS = ["Name", "Type", "Country", "Status", "Score"]
    _SECURITY_COLS = ["Name", "Ticker", "Type", "Asset Class", "Exchange", "Status", "Score"]
    _ALL_COLS = ["Name", "Type", "Country", "Status", "Score"]

    def __init__(self, data_service, app_state, parent=None):
        super().__init__(data_service, app_state, parent)

        self.setStyleSheet(f"background: {_BG};")

        # ---- Header ----
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        lbl = QLabel("SEARCH RESULTS")
        lbl.setStyleSheet(
            f"color: {_ORANGE}; font-family: {_FONT}; font-size: 14px; font-weight: bold;"
        )
        header_row.addWidget(lbl)

        self._query_label = QLabel("")
        self._query_label.setStyleSheet(
            f"color: {_TEXT}; font-family: {_FONT}; font-size: 13px;"
        )
        header_row.addWidget(self._query_label, stretch=1)
        self._layout.addLayout(header_row)

        # ---- Tabs ----
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {_BORDER};
                background: {_BG};
            }}
            QTabBar::tab {{
                background: {_BG_CARD};
                color: {_TEXT_DIM};
                font-family: {_FONT};
                font-size: 11px;
                padding: 6px 16px;
                border: 1px solid {_BORDER};
                border-bottom: none;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background: {_BG};
                color: {_ORANGE};
                font-weight: bold;
            }}
            QTabBar::tab:hover {{
                color: {_TEXT};
            }}
        """)

        self._entities_table = _ResultsTable(
            self._ENTITY_COLS, self._on_entity_clicked
        )
        self._securities_table = _ResultsTable(
            self._SECURITY_COLS, self._on_security_clicked
        )
        self._all_table = _ResultsTable(
            self._ALL_COLS, self._on_all_clicked
        )

        self._tabs.addTab(self._all_table, "All")
        self._tabs.addTab(self._entities_table, "Entities")
        self._tabs.addTab(self._securities_table, "Securities")

        self._layout.addWidget(self._tabs, stretch=1)

        # ---- Keyboard shortcut: Enter to open selected ----
        # (Handled via table's activated signal, which fires on Enter/double-click)

        # ---- Connect signals ----
        if hasattr(data_service, "search_results_loaded"):
            data_service.search_results_loaded.connect(self._on_search_loaded)

        self._current_query: str = ""

    # ------------------------------------------------------------------
    # Panel lifecycle
    # ------------------------------------------------------------------
    def activate(self, context: dict | None = None):
        context = context or {}
        query = context.get("query", "")
        self._current_query = query

        if query:
            self._query_label.setText(f'"{query}"')
            if hasattr(self.data_service, "search"):
                self.data_service.search(query)
        else:
            self._query_label.setText("")

    # ------------------------------------------------------------------
    # Data callback
    # ------------------------------------------------------------------
    @Slot(object)
    def _on_search_loaded(self, data: dict[str, Any]):
        """Handle search results.

        Expected shape::

            {
                "query": "...",
                "entities": [ {EntitySearchResult}, ... ],
                "securities": [ {SecuritySearchResult}, ... ],
            }
        """
        # Only process results for our active query
        if data.get("query", "") != self._current_query:
            return

        entities = data.get("entities", [])
        securities = data.get("securities", [])
        all_results = entities + securities

        self._entities_table.populate(entities)
        self._securities_table.populate(securities)
        self._all_table.populate(all_results)

        # Update tab labels with counts
        self._tabs.setTabText(0, f"All ({len(all_results)})")
        self._tabs.setTabText(1, f"Entities ({len(entities)})")
        self._tabs.setTabText(2, f"Securities ({len(securities)})")

    # ------------------------------------------------------------------
    # Navigation callbacks
    # ------------------------------------------------------------------
    def _on_entity_clicked(self, row_data: dict[str, Any]):
        eid = row_data.get("entity_id")
        if eid and hasattr(self.app_state, "navigate"):
            self.app_state.navigate("DES", {"entity_id": str(eid)})

    def _on_security_clicked(self, row_data: dict[str, Any]):
        sid = row_data.get("security_id")
        if sid and hasattr(self.app_state, "navigate"):
            self.app_state.navigate("DES", {"security_id": str(sid)})

    def _on_all_clicked(self, row_data: dict[str, Any]):
        """Navigate based on whichever ID is present."""
        sid = row_data.get("security_id")
        eid = row_data.get("entity_id")
        if sid and hasattr(self.app_state, "navigate"):
            self.app_state.navigate("DES", {"security_id": str(sid)})
        elif eid and hasattr(self.app_state, "navigate"):
            self.app_state.navigate("DES", {"entity_id": str(eid)})
