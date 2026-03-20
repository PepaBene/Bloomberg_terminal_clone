"""QUAL -- Data Quality Dashboard panel.

Displays completeness, accuracy, and timeliness scores along with a
table of data quality issues for the current entity.

Internal panel (not a Bloomberg mnemonic).
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
    NEGATIVE,
    POSITIVE,
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

_ISSUES_COLUMNS = [
    ColumnConfig("Domain", "domain", 110, "left", "text"),
    ColumnConfig("Field", "field", 140, "left", "text"),
    ColumnConfig("Severity", "severity", 90, "center", "text"),
    ColumnConfig("Issue Type", "issue_type", 150, "left", "text"),
    ColumnConfig("Details", "details", 300, "left", "text"),
    ColumnConfig("Detected At", "detected_at", 140, "center", "date"),
]

# Severity colour map
_SEVERITY_COLORS = {
    "CRITICAL": NEGATIVE,
    "HIGH": NEGATIVE,
    "MEDIUM": WARNING,
    "LOW": "#3b82f6",  # Blue for info-level
}


# ======================================================================
# Custom model with severity color coding
# ======================================================================

class _QualityIssueModel(GenericTableModel):
    """GenericTableModel that color-codes the Severity column."""

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None

        col_cfg = self._columns[index.column()]

        if role == Qt.ItemDataRole.ForegroundRole and col_cfg.key == "severity":
            raw = self._data[index.row()].get("severity", "")
            color_hex = _SEVERITY_COLORS.get(str(raw).upper(), TEXT_PRIMARY)
            return QColor(color_hex)

        # Background tint for critical rows
        if role == Qt.ItemDataRole.BackgroundRole:
            severity = self._data[index.row()].get("severity", "")
            if str(severity).upper() == "CRITICAL":
                return QColor("#2d1215")  # subtle red tint

        return super().data(index, role)


# ======================================================================
# Score gauge widget
# ======================================================================

class _QualityScoreCard(QWidget):
    """Displays a data quality score as a large number with label and
    a color-coded bar."""

    def __init__(
        self,
        title: str,
        accent_color: str = BLOOMBERG_ORANGE,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._accent = accent_color
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._title_label = QLabel(title)
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setStyleSheet(
            f"color: {accent_color}; font-size: 9pt; font-weight: bold; "
            f"background: transparent;"
        )
        layout.addWidget(self._title_label)

        self._score_label = QLabel("--")
        self._score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._score_label.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 28pt; font-weight: bold; "
            f"background: transparent;"
        )
        layout.addWidget(self._score_label)

        self._detail_label = QLabel("")
        self._detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._detail_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 8pt; background: transparent;"
        )
        layout.addWidget(self._detail_label)

        # Bar container
        self._bar_bg = QWidget()
        self._bar_bg.setFixedHeight(6)
        self._bar_bg.setStyleSheet(
            f"background-color: {BG_PANEL}; border-radius: 3px;"
        )
        bar_layout = QHBoxLayout(self._bar_bg)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        self._bar_fill = QWidget()
        self._bar_fill.setFixedHeight(6)
        self._bar_fill.setStyleSheet(
            f"background-color: {accent_color}; border-radius: 3px;"
        )
        bar_layout.addWidget(self._bar_fill)
        bar_layout.addStretch()
        layout.addWidget(self._bar_bg)

        self.setStyleSheet(
            f"background-color: {BG_SURFACE}; border: 1px solid {BORDER}; "
            f"border-top: 3px solid {accent_color}; border-radius: 3px;"
        )
        self.setMinimumWidth(160)
        self.setMinimumHeight(130)

    def set_score(self, score: float | None, detail: str = "") -> None:
        if score is None:
            self._score_label.setText("--")
            self._score_label.setStyleSheet(
                f"color: {TEXT_PRIMARY}; font-size: 28pt; font-weight: bold; "
                f"background: transparent;"
            )
            self._detail_label.setText("")
            self._bar_fill.setFixedWidth(0)
            return

        self._score_label.setText(f"{score:.1f}%")
        self._detail_label.setText(detail)

        # Color based on score
        if score >= 90:
            color = POSITIVE
        elif score >= 70:
            color = WARNING
        else:
            color = NEGATIVE

        self._score_label.setStyleSheet(
            f"color: {color}; font-size: 28pt; font-weight: bold; "
            f"background: transparent;"
        )

        # Update bar width proportionally
        bar_width = int(self._bar_bg.width() * score / 100)
        self._bar_fill.setFixedWidth(max(bar_width, 0))
        self._bar_fill.setStyleSheet(
            f"background-color: {color}; border-radius: 3px;"
        )

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        # Recalculate bar width on resize
        text = self._score_label.text()
        if text and text != "--":
            try:
                score = float(text.rstrip("%"))
                bar_width = int(self._bar_bg.width() * score / 100)
                self._bar_fill.setFixedWidth(max(bar_width, 0))
            except ValueError:
                pass


# ======================================================================
# QUAL Panel
# ======================================================================

class QualityPanel(BasePanel):
    """Data Quality Dashboard panel (QUAL)."""

    panel_name = "QUAL"
    panel_title = "Data Quality Dashboard"

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

        # Splitter: top=score cards, bottom=issues table
        splitter = QSplitter(Qt.Orientation.Vertical)
        self._layout.addWidget(splitter)

        # --- Top: Score cards ---
        cards_widget = QWidget()
        cards_layout = QHBoxLayout(cards_widget)
        cards_layout.setContentsMargins(4, 4, 4, 4)
        cards_layout.setSpacing(8)

        self._card_completeness = _QualityScoreCard("COMPLETENESS", POSITIVE)
        self._card_accuracy = _QualityScoreCard("ACCURACY", BLOOMBERG_ORANGE)
        self._card_timeliness = _QualityScoreCard("TIMELINESS", "#3b82f6")

        for card in (self._card_completeness, self._card_accuracy, self._card_timeliness):
            cards_layout.addWidget(card)

        splitter.addWidget(cards_widget)

        # --- Bottom: Issues table ---
        issues_container = QWidget()
        il = QVBoxLayout(issues_container)
        il.setContentsMargins(0, 0, 0, 0)
        il.setSpacing(2)

        # Issue count header
        self._issues_header = QLabel("  QUALITY ISSUES")
        self._issues_header.setStyleSheet(
            f"color: {BLOOMBERG_ORANGE}; font-size: 9pt; font-weight: bold; "
            f"background-color: {BG_SURFACE}; padding: 2px;"
        )
        il.addWidget(self._issues_header)

        self._issues_model = _QualityIssueModel(_ISSUES_COLUMNS)
        self._issues_table = QTableView()
        self._issues_table.setModel(self._issues_model)
        self._issues_table.setAlternatingRowColors(True)
        self._issues_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._issues_table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self._issues_table.setSortingEnabled(True)
        self._issues_table.verticalHeader().setDefaultSectionSize(22)
        self._issues_table.verticalHeader().hide()
        self._issues_table.horizontalHeader().setStretchLastSection(True)
        self._issues_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        il.addWidget(self._issues_table)

        self._no_issues_label = QLabel("  No quality issues detected")
        self._no_issues_label.setStyleSheet(
            f"color: {POSITIVE}; font-size: 9pt; padding: 8px;"
        )
        self._no_issues_label.hide()
        il.addWidget(self._no_issues_label)

        splitter.addWidget(issues_container)

        # Proportions
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

    # ------------------------------------------------------------------
    # Signal connections
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        if hasattr(self.data_service, "quality_loaded"):
            self.data_service.quality_loaded.connect(self._on_quality_loaded)

    # ------------------------------------------------------------------
    # Activation
    # ------------------------------------------------------------------

    def activate(self, context: dict | None = None) -> None:
        entity_id = (
            (context or {}).get("entity_id")
            or self.app_state.current_entity_id
        )
        if entity_id and hasattr(self.data_service, "load_quality"):
            self.data_service.load_quality(entity_id)

    # ------------------------------------------------------------------
    # Data slots
    # ------------------------------------------------------------------

    @Slot(object)
    def _on_quality_loaded(self, data: dict[str, Any]) -> None:
        """Populate score cards and issues table."""
        scores = data.get("scores", {})

        self._card_completeness.set_score(
            scores.get("completeness"),
            detail=scores.get("completeness_detail", ""),
        )
        self._card_accuracy.set_score(
            scores.get("accuracy"),
            detail=scores.get("accuracy_detail", ""),
        )
        self._card_timeliness.set_score(
            scores.get("timeliness"),
            detail=scores.get("timeliness_detail", ""),
        )

        # Issues table
        issues = data.get("issues", [])
        self._issues_model.set_data(issues)

        count = len(issues)
        critical = sum(
            1 for i in issues if str(i.get("severity", "")).upper() == "CRITICAL"
        )
        self._issues_header.setText(
            f"  QUALITY ISSUES ({count} total, {critical} critical)"
        )

        if issues:
            self._no_issues_label.hide()
            self._issues_table.show()
        else:
            self._issues_table.hide()
            self._no_issues_label.show()
