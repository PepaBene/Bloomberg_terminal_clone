"""SPLC -- Supply Chain / Business Relationships panel.

Displays customers, suppliers, and competitors in a three-column
layout with a detail history section below.

Bloomberg mnemonic: SPLC
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt, Slot, QModelIndex
from PySide6.QtGui import QColor
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
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from src.gui.panels.base_panel import BasePanel
from src.gui.table_models.generic_table_model import ColumnConfig, GenericTableModel

logger = logging.getLogger(__name__)

# ======================================================================
# Column definitions
# ======================================================================

_RELATIONSHIP_COLUMNS = [
    ColumnConfig("Company Name", "company_name", 180, "left", "text"),
    ColumnConfig("Revenue %", "revenue_pct", 90, "right", "percent"),
    ColumnConfig("Confidence", "confidence", 90, "right", "percent"),
    ColumnConfig("Source", "source", 100, "left", "text"),
    ColumnConfig("Since", "since", 80, "center", "text"),
]

_HISTORY_COLUMNS = [
    ColumnConfig("Date", "date", 100, "center", "date"),
    ColumnConfig("Event", "event", 200, "left", "text"),
    ColumnConfig("Revenue %", "revenue_pct", 100, "right", "percent"),
    ColumnConfig("Source", "source", 120, "left", "text"),
    ColumnConfig("Details", "details", 300, "left", "text"),
]


# ======================================================================
# Relationship column widget (one of the three columns)
# ======================================================================

class _RelationshipColumn(QWidget):
    """A titled column containing a relationship table."""

    def __init__(
        self,
        title: str,
        accent_color: str = BLOOMBERG_ORANGE,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        header = QLabel(f"  {title}")
        header.setStyleSheet(
            f"color: {accent_color}; font-size: 9pt; font-weight: bold; "
            f"background-color: {BG_SURFACE}; padding: 3px; "
            f"border: 1px solid {BORDER}; border-top: 2px solid {accent_color};"
        )
        layout.addWidget(header)

        self.model = GenericTableModel(_RELATIONSHIP_COLUMNS)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        layout.addWidget(self.table)

        self._empty_label = QLabel(f"  No {title.lower()} data")
        self._empty_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 9pt; padding: 8px;"
        )
        self._empty_label.hide()
        layout.addWidget(self._empty_label)

    def set_data(self, rows: list[dict]) -> None:
        self.model.set_data(rows)
        if rows:
            self._empty_label.hide()
            self.table.show()
        else:
            self.table.hide()
            self._empty_label.show()


# ======================================================================
# SPLC Panel
# ======================================================================

class SplcPanel(BasePanel):
    """Supply Chain / Business Relationships panel (SPLC)."""

    panel_name = "SPLC"
    panel_title = "Supply Chain & Relationships"

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

        # Main splitter: top=three columns, bottom=history
        splitter = QSplitter(Qt.Orientation.Vertical)
        self._layout.addWidget(splitter)

        # --- Top: Three columns ---
        columns_widget = QWidget()
        columns_layout = QHBoxLayout(columns_widget)
        columns_layout.setContentsMargins(0, 0, 0, 0)
        columns_layout.setSpacing(4)

        self._customers_col = _RelationshipColumn("CUSTOMERS", BLOOMBERG_ORANGE)
        self._suppliers_col = _RelationshipColumn("SUPPLIERS", "#3b82f6")
        self._competitors_col = _RelationshipColumn("COMPETITORS", "#ef4444")

        columns_layout.addWidget(self._customers_col)
        columns_layout.addWidget(self._suppliers_col)
        columns_layout.addWidget(self._competitors_col)

        splitter.addWidget(columns_widget)

        # Connect double-click navigation
        for col in (self._customers_col, self._suppliers_col, self._competitors_col):
            col.table.doubleClicked.connect(self._on_company_double_clicked)
            col.table.selectionModel().selectionChanged.connect(
                self._on_selection_changed
            )

        # --- Bottom: Relationship history ---
        history_container = QWidget()
        hl = QVBoxLayout(history_container)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(2)

        hlbl = QLabel("  RELATIONSHIP HISTORY")
        hlbl.setStyleSheet(
            f"color: {BLOOMBERG_ORANGE}; font-size: 9pt; font-weight: bold; "
            f"background-color: {BG_SURFACE}; padding: 2px;"
        )
        hl.addWidget(hlbl)

        self._history_model = GenericTableModel(_HISTORY_COLUMNS)
        self._history_table = QTableView()
        self._history_table.setModel(self._history_model)
        self._history_table.setAlternatingRowColors(True)
        self._history_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._history_table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self._history_table.verticalHeader().setDefaultSectionSize(22)
        self._history_table.verticalHeader().hide()
        self._history_table.horizontalHeader().setStretchLastSection(True)
        self._history_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        hl.addWidget(self._history_table)

        self._history_placeholder = QLabel(
            "  Select a company above to view relationship history"
        )
        self._history_placeholder.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 9pt; padding: 8px;"
        )
        hl.addWidget(self._history_placeholder)

        splitter.addWidget(history_container)

        # Proportions
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        # Store full relationships data for history lookups
        self._all_relationships: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Signal connections
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        if hasattr(self.data_service, "relationships_loaded"):
            self.data_service.relationships_loaded.connect(
                self._on_relationships_loaded
            )

    # ------------------------------------------------------------------
    # Activation
    # ------------------------------------------------------------------

    def activate(self, context: dict | None = None) -> None:
        entity_id = (
            (context or {}).get("entity_id")
            or self.app_state.current_entity_id
        )
        if entity_id and hasattr(self.data_service, "load_relationships"):
            self.data_service.load_relationships(entity_id)

    # ------------------------------------------------------------------
    # Data slots
    # ------------------------------------------------------------------

    @Slot(object)
    def _on_relationships_loaded(self, data: dict[str, Any]) -> None:
        """Populate three columns from the data_service payload."""
        self._all_relationships = data

        self._customers_col.set_data(data.get("customers", []))
        self._suppliers_col.set_data(data.get("suppliers", []))
        self._competitors_col.set_data(data.get("competitors", []))

        # Clear history
        self._history_model.set_data([])
        self._history_placeholder.show()

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    def _on_company_double_clicked(self, index: QModelIndex) -> None:
        """Navigate to the DES panel for the double-clicked company."""
        model = index.model()
        if model is None:
            return
        row_data = model.get_row(index.row())
        if row_data and row_data.get("entity_id"):
            # Signal the app to navigate to DES for this entity
            self.app_state.set_entity({"entity_id": row_data["entity_id"]})
            logger.info(
                "SPLC: navigating to DES for entity %s", row_data["entity_id"]
            )

    def _on_selection_changed(self, selected, deselected) -> None:
        """Update the history table when a relationship row is selected."""
        indexes = selected.indexes()
        if not indexes:
            return
        model = indexes[0].model()
        if model is None:
            return
        row_data = model.get_row(indexes[0].row())
        if row_data:
            company_name = row_data.get("company_name", "")
            history = self._all_relationships.get("history", {}).get(company_name, [])
            self._history_model.set_data(history)
            if history:
                self._history_placeholder.hide()
            else:
                self._history_placeholder.show()
                self._history_placeholder.setText(
                    f"  No history data for {company_name}"
                )
