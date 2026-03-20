"""HOME -- Main dashboard panel.

Shows macro summary tiles, a user watchlist table, and a recent-activity /
data-quality summary at the bottom.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .base_panel import BasePanel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Theme constants
# ---------------------------------------------------------------------------
_BG = "#0a0e17"
_BG_CARD = "#111827"
_BG_CARD_HOVER = "#1e293b"
_TEXT = "#e2e8f0"
_TEXT_DIM = "#94a3b8"
_ORANGE = "#ff6600"
_GREEN = "#22c55e"
_RED = "#ef4444"
_BORDER = "#1e293b"
_FONT_FAMILY = "Consolas, 'Courier New', monospace"


# ---------------------------------------------------------------------------
# Mini sparkline widget -- draws a tiny line chart inside a fixed area.
# ---------------------------------------------------------------------------
class _SparkLine(QWidget):
    """Tiny sparkline rendered from a list of float values."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._values: list[float] = []
        self._color = QColor(_ORANGE)
        self.setFixedSize(80, 28)

    def set_values(self, values: list[float], color: str | None = None):
        self._values = list(values) if values else []
        if color:
            self._color = QColor(color)
        self.update()

    def paintEvent(self, event):  # noqa: N802
        if len(self._values) < 2:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self._color, 1.5)
        painter.setPen(pen)

        w = self.width()
        h = self.height()
        mn = min(self._values)
        mx = max(self._values)
        rng = mx - mn if mx != mn else 1.0
        n = len(self._values)
        step = w / max(n - 1, 1)

        points = []
        for i, v in enumerate(self._values):
            x = int(i * step)
            y = int(h - (v - mn) / rng * (h - 4) - 2)
            points.append((x, y))

        for i in range(len(points) - 1):
            painter.drawLine(points[i][0], points[i][1],
                             points[i + 1][0], points[i + 1][1])
        painter.end()


# ---------------------------------------------------------------------------
# Summary tile widget
# ---------------------------------------------------------------------------
class _SummaryTile(QFrame):
    """A single macro-indicator summary tile."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SummaryTile")
        self.setStyleSheet(f"""
            #SummaryTile {{
                background: {_BG_CARD};
                border: 1px solid {_BORDER};
                border-radius: 4px;
            }}
        """)
        self.setMinimumHeight(90)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        # Row 1: name
        self._name_label = QLabel("--")
        self._name_label.setStyleSheet(
            f"color: {_TEXT_DIM}; font-family: {_FONT_FAMILY}; font-size: 11px;"
        )
        layout.addWidget(self._name_label)

        # Row 2: value + sparkline
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        self._value_label = QLabel("--")
        self._value_label.setStyleSheet(
            f"color: {_TEXT}; font-family: {_FONT_FAMILY}; font-size: 18px; font-weight: bold;"
        )
        self._sparkline = _SparkLine()
        row2.addWidget(self._value_label)
        row2.addStretch()
        row2.addWidget(self._sparkline)
        layout.addLayout(row2)

        # Row 3: change / pct change
        self._change_label = QLabel("")
        self._change_label.setStyleSheet(
            f"font-family: {_FONT_FAMILY}; font-size: 11px;"
        )
        layout.addWidget(self._change_label)

    # -- public API --

    def set_data(
        self,
        name: str,
        value: str,
        change: float | None = None,
        change_pct: float | None = None,
        sparkline_values: list[float] | None = None,
    ):
        self._name_label.setText(name)
        self._value_label.setText(value)

        if change is not None:
            sign = "+" if change >= 0 else ""
            color = _GREEN if change >= 0 else _RED
            pct_str = ""
            if change_pct is not None:
                pct_str = f"  ({sign}{change_pct:.2f}%)"
            self._change_label.setText(f"{sign}{change:.2f}{pct_str}")
            self._change_label.setStyleSheet(
                f"color: {color}; font-family: {_FONT_FAMILY}; font-size: 11px;"
            )
            spark_color = color
        else:
            self._change_label.setText("")
            spark_color = _ORANGE

        if sparkline_values:
            self._sparkline.set_values(sparkline_values, spark_color)

    def set_loading(self):
        self._name_label.setText("Loading...")
        self._value_label.setText("--")
        self._change_label.setText("")


# ---------------------------------------------------------------------------
# Dashboard panel
# ---------------------------------------------------------------------------
class DashboardPanel(BasePanel):
    """HOME panel -- main landing dashboard."""

    panel_name = "HOME"
    panel_title = "HOME"

    def __init__(self, data_service, app_state, parent=None):
        super().__init__(data_service, app_state, parent)

        self.setStyleSheet(f"background: {_BG};")

        # ---- Top section: summary tiles ----
        tiles_frame = QFrame()
        tiles_frame.setStyleSheet("background: transparent;")
        self._tiles_layout = QGridLayout(tiles_frame)
        self._tiles_layout.setContentsMargins(0, 0, 0, 0)
        self._tiles_layout.setSpacing(8)

        self._tiles: list[_SummaryTile] = []
        tile_names = ["S&P 500", "US 10Y Yield", "DXY Index", "VIX"]
        for i, name in enumerate(tile_names):
            tile = _SummaryTile()
            tile.set_data(name, "--")
            self._tiles.append(tile)
            self._tiles_layout.addWidget(tile, 0, i)

        self._layout.addWidget(tiles_frame)

        # ---- Section header: Watchlist ----
        self._layout.addSpacing(6)
        wl_header = QLabel("WATCHLIST")
        wl_header.setStyleSheet(
            f"color: {_ORANGE}; font-family: {_FONT_FAMILY}; "
            f"font-size: 12px; font-weight: bold; padding: 2px 0;"
        )
        self._layout.addWidget(wl_header)

        # ---- Middle section: watchlist table ----
        self._watchlist_table = QTableWidget()
        self._configure_table(
            self._watchlist_table,
            ["Ticker", "Name", "Last Price", "Change", "% Change", "Volume", "Market Cap"],
        )
        self._watchlist_table.setMinimumHeight(200)
        self._watchlist_table.doubleClicked.connect(self._on_watchlist_double_click)
        self._layout.addWidget(self._watchlist_table, stretch=1)

        # ---- Bottom section: recent activity ----
        self._layout.addSpacing(6)
        act_header = QLabel("DATA QUALITY SUMMARY")
        act_header.setStyleSheet(
            f"color: {_ORANGE}; font-family: {_FONT_FAMILY}; "
            f"font-size: 12px; font-weight: bold; padding: 2px 0;"
        )
        self._layout.addWidget(act_header)

        self._activity_table = QTableWidget()
        self._configure_table(
            self._activity_table,
            ["Domain", "Records", "Completeness", "Issues", "Last Updated"],
        )
        self._activity_table.setMaximumHeight(160)
        self._layout.addWidget(self._activity_table)

        # ---- Connect data_service signals ----
        if hasattr(data_service, "macro_indicators_loaded"):
            data_service.macro_indicators_loaded.connect(self._on_macro_loaded)
        if hasattr(data_service, "prices_loaded"):
            data_service.prices_loaded.connect(self._on_prices_loaded)

    # ------------------------------------------------------------------
    # Table setup helper
    # ------------------------------------------------------------------
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
                font-family: {_FONT_FAMILY};
                font-size: 12px;
                gridline-color: {_BORDER};
                border: 1px solid {_BORDER};
            }}
            QTableWidget::item {{
                padding: 3px 6px;
            }}
            QTableWidget::item:selected {{
                background: {_BG_CARD_HOVER};
            }}
            QHeaderView::section {{
                background: {_BG};
                color: {_ORANGE};
                font-family: {_FONT_FAMILY};
                font-size: 11px;
                font-weight: bold;
                border: none;
                border-bottom: 1px solid {_BORDER};
                padding: 4px 6px;
            }}
        """)

    # ------------------------------------------------------------------
    # Panel lifecycle
    # ------------------------------------------------------------------
    def activate(self, context: dict = None):
        """Load dashboard data."""
        logger.debug("DashboardPanel.activate")
        for tile in self._tiles:
            tile.set_loading()
        self._set_watchlist_loading()

        if hasattr(self.data_service, "load_macro_indicators"):
            self.data_service.load_macro_indicators()

        watchlist = getattr(self.app_state, "watchlist", [])
        if watchlist and hasattr(self.data_service, "load_prices"):
            self.data_service.load_prices(watchlist)

    # ------------------------------------------------------------------
    # Data callbacks
    # ------------------------------------------------------------------
    @Slot(object)
    def _on_macro_loaded(self, indicators: list[dict[str, Any]]):
        """Populate summary tiles from macro indicator results."""
        # Map the first 4 indicators to tiles
        tile_keys = ["SPX", "US10Y", "DXY", "VIX"]
        for i, tile in enumerate(self._tiles):
            matched = None
            if i < len(tile_keys):
                for ind in indicators:
                    code = ind.get("indicator_code", "")
                    if tile_keys[i].lower() in code.lower():
                        matched = ind
                        break
            if matched is None and i < len(indicators):
                matched = indicators[i]

            if matched:
                name = matched.get("name", matched.get("indicator_code", "N/A"))
                val = matched.get("value")
                val_str = f"{val:,.2f}" if val is not None else "--"
                change = matched.get("change")
                change_pct = matched.get("change_percent")
                spark = matched.get("sparkline", [])
                tile.set_data(name, val_str, change, change_pct, spark)
            else:
                tile.set_data(self._tiles[i]._name_label.text(), "--")

    @Slot(object)
    def _on_prices_loaded(self, prices: list[dict[str, Any]]):
        """Populate the watchlist table from loaded price data."""
        self._watchlist_table.setRowCount(len(prices))
        for row, item in enumerate(prices):
            ticker = item.get("ticker", "")
            name = item.get("name", "")
            last = item.get("close") or item.get("last_price")
            change = item.get("change")
            pct = item.get("change_percent")
            volume = item.get("volume")
            mcap = item.get("market_cap")

            self._set_cell(self._watchlist_table, row, 0, ticker)
            self._set_cell(self._watchlist_table, row, 1, name)
            self._set_cell(
                self._watchlist_table, row, 2,
                f"{last:,.2f}" if last is not None else "--",
                align=Qt.AlignmentFlag.AlignRight,
            )
            self._set_change_cell(self._watchlist_table, row, 3, change)
            self._set_change_cell(self._watchlist_table, row, 4, pct, suffix="%")
            self._set_cell(
                self._watchlist_table, row, 5,
                f"{volume:,.0f}" if volume is not None else "--",
                align=Qt.AlignmentFlag.AlignRight,
            )
            self._set_cell(
                self._watchlist_table, row, 6,
                self._fmt_mcap(mcap),
                align=Qt.AlignmentFlag.AlignRight,
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _set_watchlist_loading(self):
        self._watchlist_table.setRowCount(1)
        item = QTableWidgetItem("Loading...")
        item.setForeground(QColor(_TEXT_DIM))
        self._watchlist_table.setItem(0, 0, item)

    @staticmethod
    def _set_cell(
        table: QTableWidget,
        row: int,
        col: int,
        text: str,
        align: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft,
        color: str = _TEXT,
    ):
        item = QTableWidgetItem(text)
        item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
        item.setForeground(QColor(color))
        table.setItem(row, col, item)

    @staticmethod
    def _set_change_cell(
        table: QTableWidget,
        row: int,
        col: int,
        value: float | None,
        suffix: str = "",
    ):
        if value is None:
            text = "--"
            color = _TEXT_DIM
        else:
            sign = "+" if value >= 0 else ""
            text = f"{sign}{value:.2f}{suffix}"
            color = _GREEN if value >= 0 else _RED
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        item.setForeground(QColor(color))
        table.setItem(row, col, item)

    @staticmethod
    def _fmt_mcap(value: float | None) -> str:
        if value is None:
            return "--"
        if value >= 1e12:
            return f"{value / 1e12:,.1f}T"
        if value >= 1e9:
            return f"{value / 1e9:,.1f}B"
        if value >= 1e6:
            return f"{value / 1e6:,.1f}M"
        return f"{value:,.0f}"

    def _on_watchlist_double_click(self, index):
        """Navigate to DES panel for the double-clicked security."""
        row = index.row()
        ticker_item = self._watchlist_table.item(row, 0)
        if ticker_item and hasattr(self.app_state, "navigate"):
            self.app_state.navigate("DES", {"ticker": ticker_item.text()})
