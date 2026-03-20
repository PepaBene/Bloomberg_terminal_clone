"""Financial charting widget built on pyqtgraph.

Supports line charts (for macro data / single metrics), OHLC candlestick
charts (for EOD prices), and volume bars.  Styled with a dark Bloomberg
theme, crosshair cursor, date axis, and period-selector buttons.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Sequence

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------------------
# Theme constants
# ---------------------------------------------------------------------------
BG_COLOR = "#0D0D1A"
GRID_COLOR = (50, 50, 80, 120)
LINE_COLOR = "#FFA500"
UP_COLOR = QColor("#00C805")
DOWN_COLOR = QColor("#FF3333")
VOLUME_COLOR = QColor(100, 100, 160, 100)
CROSSHAIR_COLOR = QColor(200, 200, 200, 120)
TEXT_COLOR = "#D4D4D4"

_BUTTON_STYLE = """
QPushButton {
    background-color: #1A1A2E;
    color: #999999;
    border: 1px solid #333344;
    border-radius: 3px;
    padding: 3px 8px;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 10px;
    font-weight: bold;
    min-width: 32px;
}
QPushButton:hover {
    background-color: #252540;
    color: #FFA500;
    border-color: #FFA500;
}
QPushButton:checked {
    background-color: #FF8C00;
    color: #000000;
    border-color: #FF8C00;
}
"""

_LABEL_STYLE = (
    "color: #D4D4D4; font-family: 'Consolas', monospace; font-size: 11px; "
    "background: transparent; padding: 2px 4px;"
)


# ---------------------------------------------------------------------------
# Date axis
# ---------------------------------------------------------------------------
class _DateAxisItem(pg.AxisItem):
    """X-axis that converts POSIX timestamps to date strings."""

    def tickStrings(self, values, scale, spacing):
        strings = []
        for v in values:
            try:
                dt = datetime.fromtimestamp(v)
                if spacing > 86400 * 180:
                    strings.append(dt.strftime("%Y"))
                elif spacing > 86400 * 10:
                    strings.append(dt.strftime("%b %Y"))
                else:
                    strings.append(dt.strftime("%Y-%m-%d"))
            except (OSError, ValueError, OverflowError):
                strings.append("")
        return strings


# ---------------------------------------------------------------------------
# Candlestick item
# ---------------------------------------------------------------------------
class _CandlestickItem(pg.GraphicsObject):
    """Custom graphics item that draws OHLC candlestick bars."""

    def __init__(self, data: np.ndarray):
        """*data* columns: [timestamp, open, high, low, close]."""
        super().__init__()
        self._data = data
        self._picture = None
        self._generate_picture()

    def _generate_picture(self) -> None:
        from PySide6.QtGui import QPicture

        self._picture = QPicture()
        painter = QPainter(self._picture)
        painter.setPen(pg.mkPen("w"))

        if len(self._data) < 2:
            w = 0.4
        else:
            w = (self._data[1][0] - self._data[0][0]) * 0.3

        for row in self._data:
            t, o, h, l, c = row[0], row[1], row[2], row[3], row[4]
            if c >= o:
                color = UP_COLOR
            else:
                color = DOWN_COLOR
            pen = QPen(color)
            pen.setWidth(1)
            painter.setPen(pen)
            painter.setBrush(pg.mkBrush(color))
            # High-low wick
            painter.drawLine(pg.QtCore.QPointF(t, l), pg.QtCore.QPointF(t, h))
            # Body
            body_top = max(o, c)
            body_bot = min(o, c)
            body_h = body_top - body_bot
            if body_h < 1e-9:
                body_h = (h - l) * 0.01 or 0.01
            painter.drawRect(pg.QtCore.QRectF(t - w, body_bot, w * 2, body_h))

        painter.end()

    def paint(self, painter, option, widget):
        if self._picture is not None:
            self._picture.play(painter)

    def boundingRect(self):
        if self._picture is not None:
            return pg.QtCore.QRectF(self._picture.boundingRect())
        return pg.QtCore.QRectF()


# ---------------------------------------------------------------------------
# Main chart widget
# ---------------------------------------------------------------------------
class ChartWidget(QWidget):
    """Financial charting widget with line and OHLC modes.

    Signals
    -------
    period_changed(str)
        Emitted when the user clicks a period-selector button (e.g. "1M").
    """

    period_changed = Signal(str)

    PERIODS = ["1M", "3M", "6M", "1Y", "5Y", "MAX"]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._timestamps: np.ndarray | None = None
        self._values: np.ndarray | None = None
        self._current_period: str = "MAX"
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # -- Period selector bar ------------------------------------------
        period_bar = QHBoxLayout()
        period_bar.setContentsMargins(4, 4, 4, 2)
        period_bar.setSpacing(4)

        self._title_label = QLabel("")
        self._title_label.setStyleSheet(
            "color: #FFA500; font-family: 'Consolas', monospace; "
            "font-size: 12px; font-weight: bold; background: transparent;"
        )
        period_bar.addWidget(self._title_label)
        period_bar.addStretch(1)

        self._period_buttons: dict[str, QPushButton] = {}
        for p in self.PERIODS:
            btn = QPushButton(p)
            btn.setCheckable(True)
            btn.setStyleSheet(_BUTTON_STYLE)
            btn.clicked.connect(lambda checked, period=p: self._on_period(period))
            period_bar.addWidget(btn)
            self._period_buttons[p] = btn
        self._period_buttons["MAX"].setChecked(True)

        layout.addLayout(period_bar)

        # -- Crosshair value label ----------------------------------------
        self._crosshair_label = QLabel("")
        self._crosshair_label.setStyleSheet(_LABEL_STYLE)
        self._crosshair_label.setFixedHeight(16)
        layout.addWidget(self._crosshair_label)

        # -- Main plot area -----------------------------------------------
        date_axis = _DateAxisItem(orientation="bottom")
        self._plot_widget = pg.PlotWidget(axisItems={"bottom": date_axis})
        self._plot_widget.setBackground(BG_COLOR)
        self._plot_widget.showGrid(x=True, y=True, alpha=0.15)
        self._plot_widget.setMouseEnabled(x=True, y=True)

        # Style axes
        for axis_name in ("left", "bottom"):
            ax = self._plot_widget.getAxis(axis_name)
            ax.setPen(pg.mkPen(color=TEXT_COLOR, width=1))
            ax.setTextPen(pg.mkPen(color=TEXT_COLOR))
            font = QFont("Consolas", 9)
            ax.setTickFont(font)

        self._plot = self._plot_widget.getPlotItem()
        layout.addWidget(self._plot_widget, stretch=1)

        # -- Volume sub-plot (ViewBox linked to main x-axis) ---------------
        self._volume_vb = pg.ViewBox()
        self._plot.scene().addItem(self._volume_vb)
        self._plot.getAxis("right").linkToView(self._volume_vb)
        self._volume_vb.setXLink(self._plot.getViewBox())
        self._plot.getAxis("right").setWidth(0)  # hidden by default
        self._update_volume_geometry()
        self._plot.getViewBox().sigResized.connect(self._update_volume_geometry)

        # -- Crosshair ----------------------------------------------------
        self._vline = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen(CROSSHAIR_COLOR, width=1))
        self._hline = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen(CROSSHAIR_COLOR, width=1))
        self._plot.addItem(self._vline, ignoreBounds=True)
        self._plot.addItem(self._hline, ignoreBounds=True)
        self._plot_widget.scene().sigMouseMoved.connect(self._on_mouse_moved)

    def _update_volume_geometry(self) -> None:
        self._volume_vb.setGeometry(self._plot.getViewBox().sceneBoundingRect())

    # ------------------------------------------------------------------
    # Mouse / crosshair
    # ------------------------------------------------------------------

    def _on_mouse_moved(self, pos) -> None:
        if self._plot.sceneBoundingRect().contains(pos):
            mouse_point = self._plot.getViewBox().mapSceneToView(pos)
            x = mouse_point.x()
            y = mouse_point.y()
            self._vline.setPos(x)
            self._hline.setPos(y)

            # Resolve date
            try:
                dt = datetime.fromtimestamp(x)
                date_str = dt.strftime("%Y-%m-%d")
            except (OSError, ValueError, OverflowError):
                date_str = ""
            self._crosshair_label.setText(f"  {date_str}   Value: {y:,.2f}")

    # ------------------------------------------------------------------
    # Period selector
    # ------------------------------------------------------------------

    def _on_period(self, period: str) -> None:
        for p, btn in self._period_buttons.items():
            btn.setChecked(p == period)
        self._current_period = period
        self.period_changed.emit(period)

    # ------------------------------------------------------------------
    # Public API -- Line chart
    # ------------------------------------------------------------------

    def set_line_data(
        self,
        dates: Sequence[date | datetime | float],
        values: Sequence[float],
        label: str = "",
    ) -> None:
        """Plot a single time-series as a line chart.

        Parameters
        ----------
        dates:
            X-axis values -- ``date``, ``datetime``, or POSIX timestamps.
        values:
            Y-axis values (one per date).
        label:
            Optional chart title label.
        """
        self.clear()
        if not dates or not values:
            return

        ts = self._to_timestamps(dates)
        vals = np.asarray(values, dtype=float)

        self._timestamps = ts
        self._values = vals

        pen = pg.mkPen(color=LINE_COLOR, width=2)
        self._plot.plot(ts, vals, pen=pen, clear=True)
        self._title_label.setText(label)

    # ------------------------------------------------------------------
    # Public API -- OHLC / candlestick
    # ------------------------------------------------------------------

    def set_ohlc_data(
        self,
        dates: Sequence[date | datetime | float],
        opens: Sequence[float],
        highs: Sequence[float],
        lows: Sequence[float],
        closes: Sequence[float],
        volumes: Sequence[float] | None = None,
    ) -> None:
        """Plot OHLC candlestick chart with optional volume bars.

        Parameters
        ----------
        dates:
            One entry per bar.
        opens, highs, lows, closes:
            Price arrays (same length as *dates*).
        volumes:
            Optional volume per bar.
        """
        self.clear()
        if not dates:
            return

        ts = self._to_timestamps(dates)
        self._timestamps = ts

        ohlc = np.column_stack([
            ts,
            np.asarray(opens, dtype=float),
            np.asarray(highs, dtype=float),
            np.asarray(lows, dtype=float),
            np.asarray(closes, dtype=float),
        ])

        candles = _CandlestickItem(ohlc)
        self._plot.addItem(candles)

        # Auto-range on price
        self._plot.getViewBox().autoRange()

        # Volume bars
        if volumes is not None:
            vol = np.asarray(volumes, dtype=float)
            if len(ts) > 1:
                bar_w = (ts[1] - ts[0]) * 0.6
            else:
                bar_w = 86400 * 0.6
            bar_item = pg.BarGraphItem(
                x=ts, height=vol, width=bar_w, brush=pg.mkBrush(VOLUME_COLOR)
            )
            self._volume_vb.addItem(bar_item)
            self._volume_vb.autoRange()

    # ------------------------------------------------------------------
    # Public API -- clear
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Remove all plotted data."""
        self._plot.clear()
        self._volume_vb.clear()
        # Re-add crosshair lines after clearing
        self._plot.addItem(self._vline, ignoreBounds=True)
        self._plot.addItem(self._hline, ignoreBounds=True)
        self._title_label.setText("")
        self._crosshair_label.setText("")
        self._timestamps = None
        self._values = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_timestamps(dates: Sequence[date | datetime | float]) -> np.ndarray:
        """Convert a sequence of dates/datetimes/floats to POSIX float array."""
        out: list[float] = []
        for d in dates:
            if isinstance(d, datetime):
                out.append(d.timestamp())
            elif isinstance(d, date):
                out.append(datetime(d.year, d.month, d.day).timestamp())
            else:
                out.append(float(d))
        return np.asarray(out, dtype=float)
