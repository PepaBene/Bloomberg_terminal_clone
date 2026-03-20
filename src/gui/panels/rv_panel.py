"""RV -- Relative Value / Peer Comparison panel.

Displays a peer comparison table with key financial metrics.  The
current security's row is highlighted in Bloomberg orange.

Bloomberg mnemonic: RV
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

_PEER_COLUMNS = [
    ColumnConfig("Company", "company_name", 180, "left", "text"),
    ColumnConfig("Ticker", "ticker", 80, "center", "text"),
    ColumnConfig("Market Cap", "market_cap", 120, "right", "currency", decimals=0),
    ColumnConfig("Revenue", "revenue", 120, "right", "currency", decimals=0),
    ColumnConfig("Net Income", "net_income", 110, "right", "currency", decimals=0),
    ColumnConfig("P/E", "pe_ratio", 80, "right", "number"),
    ColumnConfig("EV/EBITDA", "ev_ebitda", 90, "right", "number"),
    ColumnConfig("Gross Margin", "gross_margin", 100, "right", "percent"),
    ColumnConfig("ROE", "roe", 80, "right", "percent"),
    ColumnConfig("Div Yield", "dividend_yield", 90, "right", "percent"),
]


# ======================================================================
# Custom model that highlights the current entity row
# ======================================================================

class _PeerTableModel(GenericTableModel):
    """GenericTableModel with row-highlight for the current entity."""

    def __init__(self, columns: list[ColumnConfig], parent=None):
        super().__init__(columns, parent)
        self._highlight_ticker: str | None = None

    def set_highlight_ticker(self, ticker: str | None) -> None:
        self._highlight_ticker = ticker
        # Force full repaint
        if self.rowCount() > 0:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(self.rowCount() - 1, self.columnCount() - 1),
            )

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None

        # Highlight the matching row's background
        if role == Qt.ItemDataRole.BackgroundRole:
            row_data = self.get_row(index.row())
            if (
                row_data
                and self._highlight_ticker
                and row_data.get("ticker") == self._highlight_ticker
            ):
                return QColor(SELECTION)
            return None

        # Orange foreground for the highlighted row
        if role == Qt.ItemDataRole.ForegroundRole:
            row_data = self.get_row(index.row())
            if (
                row_data
                and self._highlight_ticker
                and row_data.get("ticker") == self._highlight_ticker
            ):
                return QColor(BLOOMBERG_ORANGE)
            # Fall through to parent for color-coded columns
            return super().data(index, role)

        return super().data(index, role)


# ======================================================================
# RV Panel
# ======================================================================

class RvPanel(BasePanel):
    """Relative Value / Peer Comparison panel (RV)."""

    panel_name = "RV"
    panel_title = "Relative Value -- Peer Comparison"

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

        # Peer group info
        self._peer_info = QLabel("  GICS Sub-Industry: --")
        self._peer_info.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 9pt; padding: 2px 4px; "
            f"background-color: {BG_SURFACE}; border: 1px solid {BORDER};"
        )
        self._layout.addWidget(self._peer_info)

        # Peer table
        self._peer_model = _PeerTableModel(_PEER_COLUMNS)
        self._peer_table = QTableView()
        self._peer_table.setModel(self._peer_model)
        self._peer_table.setAlternatingRowColors(True)
        self._peer_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._peer_table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self._peer_table.setSortingEnabled(True)
        self._peer_table.verticalHeader().setDefaultSectionSize(22)
        self._peer_table.verticalHeader().hide()
        self._peer_table.horizontalHeader().setStretchLastSection(True)
        self._peer_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self._layout.addWidget(self._peer_table)

        # Notice for single-entity mode
        self._notice = QLabel(
            "  NOTE: Peer data requires ingestion of multiple entities. "
            "Showing current entity metrics only."
        )
        self._notice.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 8pt; font-style: italic; "
            f"padding: 4px; background-color: {BG_PANEL}; border: 1px solid {BORDER};"
        )
        self._layout.addWidget(self._notice)

    # ------------------------------------------------------------------
    # Signal connections
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        # RV can listen to fundamentals + security data being loaded
        if hasattr(self.data_service, "peer_data_loaded"):
            self.data_service.peer_data_loaded.connect(self._on_peer_data_loaded)
        # Fallback: listen for fundamentals
        if hasattr(self.data_service, "fundamentals_loaded"):
            self.data_service.fundamentals_loaded.connect(
                self._on_fundamentals_loaded
            )

    # ------------------------------------------------------------------
    # Activation
    # ------------------------------------------------------------------

    def activate(self, context: dict | None = None) -> None:
        ctx = context or {}
        security_id = ctx.get("security_id") or self.app_state.current_security_id

        # Try dedicated peer loader first
        if security_id and hasattr(self.data_service, "load_peer_data"):
            self.data_service.load_peer_data(security_id)
        elif security_id and hasattr(self.data_service, "load_fundamentals"):
            # Fallback: load current entity fundamentals for the single-row view
            self.data_service.load_fundamentals(security_id)

    # ------------------------------------------------------------------
    # Data slots
    # ------------------------------------------------------------------

    @Slot(object)
    def _on_peer_data_loaded(self, data: dict[str, Any]) -> None:
        """Full peer data available."""
        peers = data.get("peers", [])
        gics = data.get("gics_sub_industry", "--")
        current_ticker = data.get("current_ticker")

        self._peer_info.setText(f"  GICS Sub-Industry: {gics}")
        self._peer_model.set_data(peers)
        self._peer_model.set_highlight_ticker(current_ticker)

        if len(peers) > 1:
            self._notice.hide()
        else:
            self._notice.show()

    @Slot(object)
    def _on_fundamentals_loaded(self, data: dict[str, Any]) -> None:
        """Fallback: build single-row view from fundamentals data."""
        security = self.app_state.current_security or {}
        entity = self.app_state.current_entity or {}
        fundamentals = data if isinstance(data, dict) else {}

        ticker = security.get("ticker", "--")
        row = {
            "company_name": entity.get("legal_name", security.get("name", "--")),
            "ticker": ticker,
            "market_cap": fundamentals.get("market_cap"),
            "revenue": fundamentals.get("revenue"),
            "net_income": fundamentals.get("net_income"),
            "pe_ratio": fundamentals.get("pe_ratio"),
            "ev_ebitda": fundamentals.get("ev_ebitda"),
            "gross_margin": fundamentals.get("gross_margin"),
            "roe": fundamentals.get("roe"),
            "dividend_yield": fundamentals.get("dividend_yield"),
        }

        gics = entity.get("gics_sub_industry", "--")
        self._peer_info.setText(f"  GICS Sub-Industry: {gics}")
        self._peer_model.set_data([row])
        self._peer_model.set_highlight_ticker(ticker)
        self._notice.show()
