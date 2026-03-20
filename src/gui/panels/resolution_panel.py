"""RESO -- Entity Resolution Queue panel.

Displays pending entity resolution candidates with approve/reject
actions and a side-by-side detail comparison view.

Internal panel (not a Bloomberg mnemonic).
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt, Slot, QModelIndex
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
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
    SELECTION,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING,
)
from src.gui.panels.base_panel import BasePanel
from src.gui.table_models.generic_table_model import (
    COLOR_NEUTRAL,
    ColumnConfig,
    GenericTableModel,
)

logger = logging.getLogger(__name__)

# ======================================================================
# Column definitions
# ======================================================================

_QUEUE_COLUMNS = [
    ColumnConfig("Source Entity", "source_name", 180, "left", "text"),
    ColumnConfig("Matched Entity", "matched_name", 180, "left", "text"),
    ColumnConfig("Confidence", "confidence", 100, "right", "percent"),
    ColumnConfig("Strategy", "strategy", 140, "left", "text"),
    ColumnConfig("Status", "status", 100, "center", "text"),
]

_DETAIL_COLUMNS = [
    ColumnConfig("Field", "field", 140, "left", "text"),
    ColumnConfig("Source Value", "source_value", 200, "left", "text"),
    ColumnConfig("Matched Value", "matched_value", 200, "left", "text"),
    ColumnConfig("Match", "is_match", 70, "center", "text"),
]


# ======================================================================
# Custom model with confidence color coding
# ======================================================================

class _ResolutionQueueModel(GenericTableModel):
    """GenericTableModel that color-codes confidence and status columns."""

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None

        col_cfg = self._columns[index.column()]

        # Color-code confidence
        if role == Qt.ItemDataRole.ForegroundRole and col_cfg.key == "confidence":
            raw = self._data[index.row()].get("confidence")
            if isinstance(raw, (int, float)):
                if raw >= 90:
                    return QColor(POSITIVE)
                elif raw >= 70:
                    return QColor(WARNING)
                else:
                    return QColor(NEGATIVE)
            return COLOR_NEUTRAL

        # Color-code status
        if role == Qt.ItemDataRole.ForegroundRole and col_cfg.key == "status":
            status = str(self._data[index.row()].get("status", "")).upper()
            if status == "APPROVED":
                return QColor(POSITIVE)
            elif status == "REJECTED":
                return QColor(NEGATIVE)
            elif status == "PENDING":
                return QColor(WARNING)
            return COLOR_NEUTRAL

        return super().data(index, role)


# ======================================================================
# Detail comparison model
# ======================================================================

class _DetailCompareModel(GenericTableModel):
    """Color-code the match column."""

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None

        col_cfg = self._columns[index.column()]

        if role == Qt.ItemDataRole.ForegroundRole and col_cfg.key == "is_match":
            raw = str(self._data[index.row()].get("is_match", "")).upper()
            if raw in ("YES", "TRUE", "MATCH"):
                return QColor(POSITIVE)
            elif raw in ("NO", "FALSE", "MISMATCH"):
                return QColor(NEGATIVE)
            return QColor(WARNING)

        return super().data(index, role)


# ======================================================================
# Entity detail card
# ======================================================================

class _EntityDetailCard(QWidget):
    """Displays key-value fields for one entity in the comparison."""

    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(3)

        self._title = QLabel(title)
        self._title.setStyleSheet(
            f"color: {BLOOMBERG_ORANGE}; font-size: 9pt; font-weight: bold; "
            f"background: transparent;"
        )
        layout.addWidget(self._title)

        self._fields_container = QVBoxLayout()
        self._fields_container.setSpacing(2)
        layout.addLayout(self._fields_container)
        layout.addStretch()

        self._field_labels: list[QLabel] = []

        self.setStyleSheet(
            f"background-color: {BG_SURFACE}; border: 1px solid {BORDER}; "
            f"border-radius: 3px;"
        )

    def set_entity(self, entity: dict[str, Any] | None) -> None:
        # Clear existing
        for lbl in self._field_labels:
            lbl.deleteLater()
        self._field_labels.clear()

        if not entity:
            lbl = QLabel("  No entity data")
            lbl.setStyleSheet(
                f"color: {TEXT_SECONDARY}; font-size: 9pt; background: transparent;"
            )
            self._fields_container.addWidget(lbl)
            self._field_labels.append(lbl)
            return

        display_fields = [
            ("Entity ID", "entity_id"),
            ("Legal Name", "legal_name"),
            ("Type", "entity_type"),
            ("Country", "country"),
            ("LEI", "lei"),
            ("CIK", "cik"),
            ("Status", "status"),
            ("GICS Sector", "gics_sector"),
            ("GICS Industry", "gics_industry"),
            ("Founded", "founded_date"),
        ]

        for label, key in display_fields:
            val = entity.get(key, "--")
            lbl = QLabel(f"  {label}: {val}")
            lbl.setStyleSheet(
                f"color: {TEXT_PRIMARY}; font-size: 9pt; background: transparent; "
                f"padding: 1px 0;"
            )
            self._fields_container.addWidget(lbl)
            self._field_labels.append(lbl)


# ======================================================================
# RESO Panel
# ======================================================================

class ResolutionPanel(BasePanel):
    """Entity Resolution Queue panel (RESO)."""

    panel_name = "RESO"
    panel_title = "Entity Resolution Queue"

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

        # Main splitter: top=queue table + buttons, bottom=detail view
        splitter = QSplitter(Qt.Orientation.Vertical)
        self._layout.addWidget(splitter)

        # --- Top: Queue table with action buttons ---
        queue_container = QWidget()
        ql = QVBoxLayout(queue_container)
        ql.setContentsMargins(0, 0, 0, 0)
        ql.setSpacing(4)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        qlbl = QLabel("  PENDING RESOLUTIONS")
        qlbl.setStyleSheet(
            f"color: {BLOOMBERG_ORANGE}; font-size: 9pt; font-weight: bold; "
            f"background-color: {BG_SURFACE}; padding: 2px;"
        )
        toolbar.addWidget(qlbl, stretch=1)

        self._btn_approve = QPushButton("Approve")
        self._btn_approve.setStyleSheet(
            f"background-color: {POSITIVE}; color: #000; font-weight: bold; "
            f"padding: 4px 16px; border-radius: 2px;"
        )
        self._btn_approve.setEnabled(False)
        self._btn_approve.clicked.connect(self._on_approve)
        toolbar.addWidget(self._btn_approve)

        self._btn_reject = QPushButton("Reject")
        self._btn_reject.setStyleSheet(
            f"background-color: {NEGATIVE}; color: #000; font-weight: bold; "
            f"padding: 4px 16px; border-radius: 2px;"
        )
        self._btn_reject.setEnabled(False)
        self._btn_reject.clicked.connect(self._on_reject)
        toolbar.addWidget(self._btn_reject)

        ql.addLayout(toolbar)

        # Queue table
        self._queue_model = _ResolutionQueueModel(_QUEUE_COLUMNS)
        self._queue_table = QTableView()
        self._queue_table.setModel(self._queue_model)
        self._queue_table.setAlternatingRowColors(True)
        self._queue_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._queue_table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self._queue_table.setSortingEnabled(True)
        self._queue_table.verticalHeader().setDefaultSectionSize(22)
        self._queue_table.verticalHeader().hide()
        self._queue_table.horizontalHeader().setStretchLastSection(True)
        self._queue_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self._queue_table.selectionModel().selectionChanged.connect(
            self._on_queue_selection_changed
        )
        ql.addWidget(self._queue_table)

        self._placeholder_label = QLabel(
            "  Entity resolution queue is empty. "
            "Resolution candidates appear here during data ingestion."
        )
        self._placeholder_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 9pt; font-style: italic; "
            f"padding: 12px; background-color: {BG_PANEL}; "
            f"border: 1px solid {BORDER};"
        )
        self._placeholder_label.setWordWrap(True)
        ql.addWidget(self._placeholder_label)

        splitter.addWidget(queue_container)

        # --- Bottom: Detail comparison ---
        detail_container = QWidget()
        dl = QVBoxLayout(detail_container)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(4)

        dlbl = QLabel("  ENTITY COMPARISON")
        dlbl.setStyleSheet(
            f"color: {BLOOMBERG_ORANGE}; font-size: 9pt; font-weight: bold; "
            f"background-color: {BG_SURFACE}; padding: 2px;"
        )
        dl.addWidget(dlbl)

        # Side-by-side cards
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(8)
        self._source_card = _EntityDetailCard("SOURCE ENTITY")
        self._matched_card = _EntityDetailCard("MATCHED ENTITY")
        cards_layout.addWidget(self._source_card)
        cards_layout.addWidget(self._matched_card)
        dl.addLayout(cards_layout)

        # Field-level comparison table
        self._detail_model = _DetailCompareModel(_DETAIL_COLUMNS)
        self._detail_table = QTableView()
        self._detail_table.setModel(self._detail_model)
        self._detail_table.setAlternatingRowColors(True)
        self._detail_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._detail_table.verticalHeader().setDefaultSectionSize(22)
        self._detail_table.verticalHeader().hide()
        self._detail_table.horizontalHeader().setStretchLastSection(True)
        self._detail_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        dl.addWidget(self._detail_table)

        splitter.addWidget(detail_container)

        # Proportions
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        # Internal state
        self._queue_data: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Signal connections
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        if hasattr(self.data_service, "resolution_queue_loaded"):
            self.data_service.resolution_queue_loaded.connect(
                self._on_resolution_queue_loaded
            )
        if hasattr(self.data_service, "resolution_action_completed"):
            self.data_service.resolution_action_completed.connect(
                self._on_action_completed
            )

    # ------------------------------------------------------------------
    # Activation
    # ------------------------------------------------------------------

    def activate(self, context: dict | None = None) -> None:
        if hasattr(self.data_service, "load_resolution_queue"):
            self.data_service.load_resolution_queue()
        else:
            # Show placeholder -- no resolution queue service available
            self._queue_model.set_data([])
            self._placeholder_label.show()

    # ------------------------------------------------------------------
    # Data slots
    # ------------------------------------------------------------------

    @Slot(object)
    def _on_resolution_queue_loaded(self, data: dict[str, Any]) -> None:
        """Populate the queue table."""
        self._queue_data = data.get("queue", [])
        self._queue_model.set_data(self._queue_data)

        if self._queue_data:
            self._placeholder_label.hide()
            self._queue_table.show()
        else:
            self._queue_table.hide()
            self._placeholder_label.show()

        # Clear detail view
        self._source_card.set_entity(None)
        self._matched_card.set_entity(None)
        self._detail_model.set_data([])
        self._btn_approve.setEnabled(False)
        self._btn_reject.setEnabled(False)

    @Slot(object)
    def _on_action_completed(self, result: dict[str, Any]) -> None:
        """Refresh the queue after an approve/reject action."""
        logger.info("Resolution action completed: %s", result.get("status"))
        self.activate()

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    def _on_queue_selection_changed(self, selected, deselected) -> None:
        """Update detail view and enable buttons when a row is selected."""
        indexes = selected.indexes()
        if not indexes:
            self._btn_approve.setEnabled(False)
            self._btn_reject.setEnabled(False)
            return

        row = indexes[0].row()
        row_data = self._queue_model.get_row(row)
        if not row_data:
            return

        is_pending = str(row_data.get("status", "")).upper() == "PENDING"
        self._btn_approve.setEnabled(is_pending)
        self._btn_reject.setEnabled(is_pending)

        # Populate entity detail cards
        self._source_card.set_entity(row_data.get("source_entity"))
        self._matched_card.set_entity(row_data.get("matched_entity"))

        # Build field comparison
        comparisons = row_data.get("field_comparisons", [])
        self._detail_model.set_data(comparisons)

    def _on_approve(self) -> None:
        """Approve the selected resolution candidate."""
        row_data = self._get_selected_row()
        if not row_data:
            return
        resolution_id = row_data.get("resolution_id")
        if resolution_id and hasattr(self.data_service, "approve_resolution"):
            logger.info("Approving resolution %s", resolution_id)
            self.data_service.approve_resolution(resolution_id)

    def _on_reject(self) -> None:
        """Reject the selected resolution candidate."""
        row_data = self._get_selected_row()
        if not row_data:
            return
        resolution_id = row_data.get("resolution_id")
        if resolution_id and hasattr(self.data_service, "reject_resolution"):
            logger.info("Rejecting resolution %s", resolution_id)
            self.data_service.reject_resolution(resolution_id)

    def _get_selected_row(self) -> dict[str, Any] | None:
        indexes = self._queue_table.selectionModel().selectedRows()
        if not indexes:
            return None
        return self._queue_model.get_row(indexes[0].row())
