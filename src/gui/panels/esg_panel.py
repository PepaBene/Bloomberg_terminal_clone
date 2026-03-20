"""ESG -- Environmental, Social & Governance Scores panel.

Displays ESG score cards with gauges, a metrics table grouped by
category, and a controversies log.

Bloomberg mnemonic: ESG
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor, QFont, QPainter, QPen
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
from src.gui.table_models.generic_table_model import ColumnConfig, GenericTableModel

logger = logging.getLogger(__name__)

# ======================================================================
# Column definitions
# ======================================================================

_METRICS_COLUMNS = [
    ColumnConfig("Category", "category", 120, "left", "text"),
    ColumnConfig("Metric Name", "metric_name", 200, "left", "text"),
    ColumnConfig("Value", "value", 100, "right", "number"),
    ColumnConfig("Unit", "unit", 80, "center", "text"),
    ColumnConfig("Period", "period", 100, "center", "text"),
]

_CONTROVERSIES_COLUMNS = [
    ColumnConfig("Title", "title", 260, "left", "text"),
    ColumnConfig("Category", "category", 120, "left", "text"),
    ColumnConfig("Level", "level", 90, "center", "text"),
    ColumnConfig("Status", "status", 90, "center", "text"),
    ColumnConfig("Start Date", "start_date", 100, "center", "date"),
    ColumnConfig("End Date", "end_date", 100, "center", "date"),
]


# ======================================================================
# Score card widget with large number + trend arrow
# ======================================================================

class _ESGScoreCard(QWidget):
    """Displays a single ESG score as a large number with a label and
    an optional trend indicator."""

    _GRADE_COLORS = {
        "A": POSITIVE,
        "B": "#4ade80",
        "C": WARNING,
        "D": NEGATIVE,
    }

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
            f"color: {TEXT_PRIMARY}; font-size: 26pt; font-weight: bold; "
            f"background: transparent;"
        )
        layout.addWidget(self._score_label)

        self._trend_label = QLabel("")
        self._trend_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._trend_label.setStyleSheet(
            f"font-size: 10pt; background: transparent;"
        )
        layout.addWidget(self._trend_label)

        self.setStyleSheet(
            f"background-color: {BG_SURFACE}; border: 1px solid {BORDER}; "
            f"border-top: 3px solid {accent_color}; border-radius: 3px;"
        )
        self.setMinimumWidth(140)
        self.setMinimumHeight(110)

    def set_score(self, score: float | str | None, trend: float | None = None) -> None:
        if score is None:
            self._score_label.setText("--")
            self._trend_label.setText("")
            return

        if isinstance(score, (int, float)):
            self._score_label.setText(f"{score:.1f}")
            # Color based on score (0-100 scale)
            if score >= 70:
                self._score_label.setStyleSheet(
                    f"color: {POSITIVE}; font-size: 26pt; font-weight: bold; "
                    f"background: transparent;"
                )
            elif score >= 40:
                self._score_label.setStyleSheet(
                    f"color: {WARNING}; font-size: 26pt; font-weight: bold; "
                    f"background: transparent;"
                )
            else:
                self._score_label.setStyleSheet(
                    f"color: {NEGATIVE}; font-size: 26pt; font-weight: bold; "
                    f"background: transparent;"
                )
        else:
            self._score_label.setText(str(score))

        if trend is not None:
            arrow = "^" if trend > 0 else "v" if trend < 0 else "-"
            color = POSITIVE if trend > 0 else NEGATIVE if trend < 0 else TEXT_SECONDARY
            self._trend_label.setText(f"{arrow} {abs(trend):.1f}")
            self._trend_label.setStyleSheet(
                f"color: {color}; font-size: 10pt; background: transparent;"
            )
        else:
            self._trend_label.setText("")


# ======================================================================
# ESG Panel
# ======================================================================

class EsgPanel(BasePanel):
    """ESG Scores panel."""

    panel_name = "ESG"
    panel_title = "ESG Scores"

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

        # Splitter: top=score cards, middle=metrics, bottom=controversies
        splitter = QSplitter(Qt.Orientation.Vertical)
        self._layout.addWidget(splitter)

        # --- Top: Score cards ---
        cards_widget = QWidget()
        cards_layout = QHBoxLayout(cards_widget)
        cards_layout.setContentsMargins(4, 4, 4, 4)
        cards_layout.setSpacing(8)

        self._card_overall = _ESGScoreCard("OVERALL", BLOOMBERG_ORANGE)
        self._card_env = _ESGScoreCard("ENVIRONMENTAL", "#22c55e")
        self._card_social = _ESGScoreCard("SOCIAL", "#3b82f6")
        self._card_gov = _ESGScoreCard("GOVERNANCE", "#a855f7")

        for card in (self._card_overall, self._card_env, self._card_social, self._card_gov):
            cards_layout.addWidget(card)

        splitter.addWidget(cards_widget)

        # --- Middle: ESG Metrics table ---
        metrics_container = QWidget()
        ml = QVBoxLayout(metrics_container)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(2)
        mlbl = QLabel("  ESG METRICS")
        mlbl.setStyleSheet(
            f"color: {BLOOMBERG_ORANGE}; font-size: 9pt; font-weight: bold; "
            f"background-color: {BG_SURFACE}; padding: 2px;"
        )
        ml.addWidget(mlbl)
        self._metrics_model = GenericTableModel(_METRICS_COLUMNS)
        self._metrics_table = self._make_table(self._metrics_model)
        ml.addWidget(self._metrics_table)
        splitter.addWidget(metrics_container)

        # --- Bottom: Controversies ---
        contro_container = QWidget()
        cll = QVBoxLayout(contro_container)
        cll.setContentsMargins(0, 0, 0, 0)
        cll.setSpacing(2)
        cllbl = QLabel("  CONTROVERSIES")
        cllbl.setStyleSheet(
            f"color: {BLOOMBERG_ORANGE}; font-size: 9pt; font-weight: bold; "
            f"background-color: {BG_SURFACE}; padding: 2px;"
        )
        cll.addWidget(cllbl)
        self._contro_model = GenericTableModel(_CONTROVERSIES_COLUMNS)
        self._contro_table = self._make_table(self._contro_model)
        cll.addWidget(self._contro_table)
        splitter.addWidget(contro_container)

        # Proportions
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
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
        if hasattr(self.data_service, "esg_loaded"):
            self.data_service.esg_loaded.connect(self._on_esg_loaded)

    # ------------------------------------------------------------------
    # Activation
    # ------------------------------------------------------------------

    def activate(self, context: dict | None = None) -> None:
        entity_id = (
            (context or {}).get("entity_id")
            or self.app_state.current_entity_id
        )
        if entity_id and hasattr(self.data_service, "load_esg"):
            self.data_service.load_esg(entity_id)

    # ------------------------------------------------------------------
    # Data slots
    # ------------------------------------------------------------------

    @Slot(object)
    def _on_esg_loaded(self, data: dict[str, Any]) -> None:
        """Populate all sections from the data_service payload."""
        scores = data.get("scores", {})
        self._card_overall.set_score(
            scores.get("overall"), scores.get("overall_trend")
        )
        self._card_env.set_score(
            scores.get("environmental"), scores.get("environmental_trend")
        )
        self._card_social.set_score(
            scores.get("social"), scores.get("social_trend")
        )
        self._card_gov.set_score(
            scores.get("governance"), scores.get("governance_trend")
        )

        # Metrics table
        metrics = data.get("metrics", [])
        self._metrics_model.set_data(metrics)

        # Controversies table
        controversies = data.get("controversies", [])
        self._contro_model.set_data(controversies)
