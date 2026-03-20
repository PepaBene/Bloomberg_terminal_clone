"""GP -- Price chart panel.

Displays an OHLC/candlestick chart with volume bars, period selector buttons,
an info bar, and a recent-prices data table.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSeries,
    QBarSet,
    QCandlestickSeries,
    QCandlestickSet,
    QChart,
    QChartView,
    QDateTimeAxis,
    QValueAxis,
)
from PySide6.QtCore import QDateTime, QPointF, Qt, Slot
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSplitter,
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
_TEXT = "#e2e8f0"
_TEXT_DIM = "#94a3b8"
_ORANGE = "#ff6600"
_GREEN = "#22c55e"
_RED = "#ef4444"
_BORDER = "#1e293b"
_FONT = "Consolas, 'Courier New', monospace"

# Period button definitions: label -> days
_PERIODS: list[tuple[str, int | None]] = [
    ("1M", 30),
    ("3M", 90),
    ("6M", 180),
    ("1Y", 365),
    ("3Y", 365 * 3),
    ("5Y", 365 * 5),
    ("MAX", None),
]


# ---------------------------------------------------------------------------
# Period selector buttons
# ---------------------------------------------------------------------------
class _PeriodBar(QWidget):
    """Horizontal bar of period-selector buttons."""

    def __init__(self, on_period_changed, parent=None):
        super().__init__(parent)
        self._callback = on_period_changed
        self._buttons: list[QPushButton] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(4)

        for label, days in _PERIODS:
            btn = QPushButton(label)
            btn.setFixedWidth(48)
            btn.setCheckable(True)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {_BG_CARD};
                    color: {_TEXT_DIM};
                    font-family: {_FONT};
                    font-size: 11px;
                    border: 1px solid {_BORDER};
                    border-radius: 3px;
                    padding: 3px 0;
                }}
                QPushButton:checked {{
                    background: {_ORANGE};
                    color: {_BG};
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    border-color: {_ORANGE};
                }}
            """)
            btn.clicked.connect(lambda checked, d=days, b=btn: self._on_click(d, b))
            layout.addWidget(btn)
            self._buttons.append(btn)

        layout.addStretch()

        # Default: 1Y
        self._buttons[3].setChecked(True)

    def _on_click(self, days: int | None, btn: QPushButton):
        for b in self._buttons:
            b.setChecked(b is btn)
        self._callback(days)


# ---------------------------------------------------------------------------
# Info bar (OHLCV for a selected date)
# ---------------------------------------------------------------------------
class _InfoBar(QFrame):
    """Horizontal bar showing O/H/L/C/V for the most recent or selected bar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"background: {_BG_CARD}; border: 1px solid {_BORDER}; border-radius: 3px;"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(16)

        self._labels: dict[str, QLabel] = {}
        for key in ["Date", "Open", "High", "Low", "Close", "Volume"]:
            lbl = QLabel(f"{key}: --")
            lbl.setStyleSheet(
                f"color: {_TEXT}; font-family: {_FONT}; font-size: 11px; border: none;"
            )
            layout.addWidget(lbl)
            self._labels[key] = lbl
        layout.addStretch()

    def set_data(
        self,
        dt: str = "--",
        o: str = "--",
        h: str = "--",
        l: str = "--",  # noqa: E741
        c: str = "--",
        v: str = "--",
    ):
        self._labels["Date"].setText(f"Date: {dt}")
        self._labels["Open"].setText(f"O: {o}")
        self._labels["High"].setText(f"H: {h}")
        self._labels["Low"].setText(f"L: {l}")
        self._labels["Close"].setText(f"C: {c}")
        self._labels["Volume"].setText(f"Vol: {v}")


# ---------------------------------------------------------------------------
# GP Panel
# ---------------------------------------------------------------------------
class GPPanel(BasePanel):
    """GP -- price chart panel with OHLC candlestick and volume."""

    panel_name = "GP"
    panel_title = "GP - Price Chart"

    def __init__(self, data_service, app_state, parent=None):
        super().__init__(data_service, app_state, parent)

        self.setStyleSheet(f"background: {_BG};")

        # ---- Header ----
        self._header = QLabel("PRICE CHART")
        self._header.setStyleSheet(
            f"color: {_ORANGE}; font-family: {_FONT}; font-size: 14px; font-weight: bold;"
        )
        self._layout.addWidget(self._header)

        self._security_label = QLabel("Loading...")
        self._security_label.setStyleSheet(
            f"color: {_TEXT}; font-family: {_FONT}; font-size: 12px;"
        )
        self._layout.addWidget(self._security_label)

        # ---- Period buttons ----
        self._period_bar = _PeriodBar(self._on_period_changed)
        self._layout.addWidget(self._period_bar)

        # ---- Info bar ----
        self._info_bar = _InfoBar()
        self._layout.addWidget(self._info_bar)

        # ---- Splitter: chart on top, table on bottom ----
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background: {_BORDER};
                height: 3px;
            }}
        """)

        # -- Chart --
        self._chart = QChart()
        self._chart.setBackgroundBrush(QColor(_BG_CARD))
        self._chart.legend().hide()
        self._chart.setMargins(Qt.QMargins(4, 4, 4, 4))  # type: ignore[arg-type]
        # Title styling
        self._chart.setTitleBrush(QColor(_TEXT))

        self._chart_view = QChartView(self._chart)
        self._chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._chart_view.setStyleSheet(f"background: {_BG_CARD}; border: 1px solid {_BORDER};")
        splitter.addWidget(self._chart_view)

        # -- Price table --
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)

        tbl_header = QLabel("RECENT PRICES")
        tbl_header.setStyleSheet(
            f"color: {_ORANGE}; font-family: {_FONT}; font-size: 11px; "
            f"font-weight: bold; padding: 4px 0 2px 0;"
        )
        table_layout.addWidget(tbl_header)

        self._price_table = QTableWidget()
        self._configure_table(
            self._price_table,
            ["Date", "Open", "High", "Low", "Close", "Volume", "Change", "% Change"],
        )
        table_layout.addWidget(self._price_table)
        splitter.addWidget(table_container)

        splitter.setSizes([400, 200])
        self._layout.addWidget(splitter, stretch=1)

        # ---- State ----
        self._current_security_id: str | None = None
        self._current_days: int | None = 365
        self._all_prices: list[dict[str, Any]] = []

        # ---- Connect signals ----
        if hasattr(data_service, "prices_loaded"):
            data_service.prices_loaded.connect(self._on_prices_loaded)

    # ------------------------------------------------------------------
    # Table helper
    # ------------------------------------------------------------------
    @staticmethod
    def _configure_table(table: QTableWidget, headers: list[str]):
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
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
            QTableWidget::item {{ padding: 2px 6px; }}
            QTableWidget::item:selected {{ background: #1e293b; }}
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

    # ------------------------------------------------------------------
    # Panel lifecycle
    # ------------------------------------------------------------------
    def activate(self, context: dict | None = None):
        context = context or {}
        self._current_security_id = context.get("security_id")
        security_name = context.get("security_name", "")

        if security_name:
            self._security_label.setText(security_name)
        else:
            self._security_label.setText("Loading...")

        self._load_prices(self._current_days)

    def _load_prices(self, days: int | None):
        sid = self._current_security_id
        if sid and hasattr(self.data_service, "load_prices"):
            kwargs: dict[str, Any] = {"security_id": sid}
            if days is not None:
                kwargs["days"] = days
            self.data_service.load_prices(**kwargs)

    def _on_period_changed(self, days: int | None):
        self._current_days = days
        self._load_prices(days)

    # ------------------------------------------------------------------
    # Data callback
    # ------------------------------------------------------------------
    @Slot(object)
    def _on_prices_loaded(self, prices: list[dict[str, Any]]):
        """Populate chart and table from loaded EOD price data.

        Each price dict should match EODPriceResponse fields: price_date,
        open, high, low, close, volume, etc.
        """
        if not prices:
            return

        self._all_prices = prices

        # Update info bar with most recent bar
        latest = prices[-1] if prices else {}
        self._info_bar.set_data(
            dt=str(latest.get("price_date", "--")),
            o=self._f(latest.get("open")),
            h=self._f(latest.get("high")),
            l=self._f(latest.get("low")),
            c=self._f(latest.get("close")),
            v=self._fv(latest.get("volume")),
        )

        self._build_chart(prices)
        self._build_table(prices)

    # ------------------------------------------------------------------
    # Chart builder
    # ------------------------------------------------------------------
    def _build_chart(self, prices: list[dict[str, Any]]):
        self._chart.removeAllSeries()
        for ax in self._chart.axes():
            self._chart.removeAxis(ax)

        if not prices:
            return

        # ---- Candlestick series ----
        candle = QCandlestickSeries()
        candle.setIncreasingColor(QColor(_GREEN))
        candle.setDecreasingColor(QColor(_RED))
        candle.setBodyOutlineVisible(False)

        min_price = float("inf")
        max_price = float("-inf")
        max_vol = 0

        for p in prices:
            dt = p.get("price_date")
            if dt is None:
                continue
            if isinstance(dt, str):
                parts = dt.split("-")
                y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            else:
                y, m, d = dt.year, dt.month, dt.day
            ts = QDateTime(y, m, d, 0, 0).toMSecsSinceEpoch()

            o = p.get("open") or p.get("close") or 0
            h = p.get("high") or o
            l = p.get("low") or o  # noqa: E741
            c = p.get("close") or o
            cs = QCandlestickSet(o, h, l, c, ts)
            candle.append(cs)

            min_price = min(min_price, l)
            max_price = max(max_price, h)
            vol = p.get("volume") or 0
            max_vol = max(max_vol, vol)

        self._chart.addSeries(candle)

        # ---- X-axis (datetime) ----
        axis_x = QDateTimeAxis()
        axis_x.setFormat("yyyy-MM-dd")
        axis_x.setLabelsColor(QColor(_TEXT_DIM))
        axis_x.setGridLineColor(QColor(_BORDER))
        axis_x.setLabelsAngle(-45)
        axis_x.setTickCount(8)
        self._chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        candle.attachAxis(axis_x)

        # ---- Y-axis (price) ----
        axis_y = QValueAxis()
        margin = (max_price - min_price) * 0.05 if max_price > min_price else 1
        axis_y.setRange(min_price - margin, max_price + margin)
        axis_y.setLabelsColor(QColor(_TEXT_DIM))
        axis_y.setGridLineColor(QColor(_BORDER))
        self._chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        candle.attachAxis(axis_y)

    # ------------------------------------------------------------------
    # Table builder
    # ------------------------------------------------------------------
    def _build_table(self, prices: list[dict[str, Any]]):
        # Show most recent first (reverse chronological)
        recent = list(reversed(prices))
        self._price_table.setRowCount(len(recent))

        for r, p in enumerate(recent):
            dt = str(p.get("price_date", "--"))
            o = p.get("open")
            h = p.get("high")
            lo = p.get("low")
            c = p.get("close")
            vol = p.get("volume")

            # Compute change from previous close
            change = None
            pct = None
            if r < len(recent) - 1:
                prev_close = recent[r + 1].get("close")
                if c is not None and prev_close is not None and prev_close != 0:
                    change = c - prev_close
                    pct = (change / prev_close) * 100

            self._set_cell(self._price_table, r, 0, dt)
            self._set_cell(self._price_table, r, 1, self._f(o), right=True)
            self._set_cell(self._price_table, r, 2, self._f(h), right=True)
            self._set_cell(self._price_table, r, 3, self._f(lo), right=True)
            self._set_cell(self._price_table, r, 4, self._f(c), right=True)
            self._set_cell(
                self._price_table, r, 5, self._fv(vol), right=True
            )
            self._set_change_cell(self._price_table, r, 6, change)
            self._set_change_cell(self._price_table, r, 7, pct, suffix="%")

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _f(val: float | None) -> str:
        return f"{val:,.2f}" if val is not None else "--"

    @staticmethod
    def _fv(val: int | float | None) -> str:
        if val is None:
            return "--"
        if val >= 1e6:
            return f"{val / 1e6:,.1f}M"
        return f"{val:,.0f}"

    @staticmethod
    def _set_cell(
        table: QTableWidget,
        row: int,
        col: int,
        text: str,
        right: bool = False,
        color: str = _TEXT,
    ):
        item = QTableWidgetItem(text)
        align = Qt.AlignmentFlag.AlignRight if right else Qt.AlignmentFlag.AlignLeft
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
