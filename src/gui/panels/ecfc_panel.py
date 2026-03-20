"""ECFC -- Macro / Economic Indicators dashboard.

Left sidebar shows a filterable list of macro indicators grouped by category.
Right panel shows a time-series line chart and data table for the selected
indicator.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCharts import (
    QChart,
    QChartView,
    QDateTimeAxis,
    QLineSeries,
    QValueAxis,
)
from PySide6.QtCore import QDateTime, Qt, Slot
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
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

# Category filter labels
_CATEGORIES = [
    "ALL",
    "GDP",
    "LABOR",
    "PRICES",
    "RATES",
    "HOUSING",
    "CONSUMER",
    "MANUFACTURING",
    "TRADE",
    "MONEY_SUPPLY",
    "FISCAL",
    "OTHER",
]


# ---------------------------------------------------------------------------
# Category filter bar
# ---------------------------------------------------------------------------
class _CategoryBar(QWidget):
    """Horizontal row of category filter buttons."""

    def __init__(self, on_category_changed, parent=None):
        super().__init__(parent)
        self._callback = on_category_changed
        self._buttons: list[QPushButton] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(3)

        for cat in _CATEGORIES:
            btn = QPushButton(cat)
            btn.setCheckable(True)
            btn.setFixedHeight(24)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {_BG_CARD};
                    color: {_TEXT_DIM};
                    font-family: {_FONT};
                    font-size: 10px;
                    border: 1px solid {_BORDER};
                    border-radius: 3px;
                    padding: 2px 8px;
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
            btn.clicked.connect(lambda checked, c=cat, b=btn: self._on_click(c, b))
            layout.addWidget(btn)
            self._buttons.append(btn)

        layout.addStretch()
        # Default: ALL selected
        self._buttons[0].setChecked(True)

    def _on_click(self, cat: str, btn: QPushButton):
        for b in self._buttons:
            b.setChecked(b is btn)
        self._callback(cat)


# ---------------------------------------------------------------------------
# Indicator list item (sidebar)
# ---------------------------------------------------------------------------
class _IndicatorListItem(QListWidgetItem):
    """List widget item carrying indicator metadata."""

    def __init__(self, indicator: dict[str, Any]):
        name = indicator.get("name") or indicator.get("indicator_code", "???")
        super().__init__(name)
        self.indicator = indicator
        self.setForeground(QColor(_TEXT))


# ---------------------------------------------------------------------------
# Indicator detail view (right panel)
# ---------------------------------------------------------------------------
class _IndicatorDetail(QWidget):
    """Chart + info + table for a single macro indicator."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # -- Header info row --
        self._info_frame = QFrame()
        self._info_frame.setStyleSheet(
            f"background: {_BG_CARD}; border: 1px solid {_BORDER}; border-radius: 4px;"
        )
        info_layout = QHBoxLayout(self._info_frame)
        info_layout.setContentsMargins(10, 6, 10, 6)
        info_layout.setSpacing(20)

        self._name_label = QLabel("Select an indicator")
        self._name_label.setStyleSheet(
            f"color: {_ORANGE}; font-family: {_FONT}; font-size: 14px; "
            f"font-weight: bold; border: none;"
        )
        self._meta_label = QLabel("")
        self._meta_label.setStyleSheet(
            f"color: {_TEXT_DIM}; font-family: {_FONT}; font-size: 11px; border: none;"
        )
        self._value_label = QLabel("")
        self._value_label.setStyleSheet(
            f"color: {_TEXT}; font-family: {_FONT}; font-size: 16px; "
            f"font-weight: bold; border: none;"
        )
        self._change_label = QLabel("")
        self._change_label.setStyleSheet(
            f"font-family: {_FONT}; font-size: 12px; border: none;"
        )

        info_layout.addWidget(self._name_label, stretch=1)
        info_layout.addWidget(self._meta_label)
        info_layout.addWidget(self._value_label)
        info_layout.addWidget(self._change_label)
        layout.addWidget(self._info_frame)

        # -- Chart --
        self._chart = QChart()
        self._chart.setBackgroundBrush(QColor(_BG_CARD))
        self._chart.legend().hide()
        self._chart.setMargins(Qt.QMargins(4, 4, 4, 4))  # type: ignore[arg-type]

        self._chart_view = QChartView(self._chart)
        self._chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._chart_view.setStyleSheet(
            f"background: {_BG_CARD}; border: 1px solid {_BORDER};"
        )
        layout.addWidget(self._chart_view, stretch=1)

        # -- Data table --
        tbl_header = QLabel("HISTORICAL VALUES")
        tbl_header.setStyleSheet(
            f"color: {_ORANGE}; font-family: {_FONT}; font-size: 11px; "
            f"font-weight: bold; padding-top: 4px;"
        )
        layout.addWidget(tbl_header)

        self._table = QTableWidget()
        self._configure_table(self._table, [
            "Date", "Value", "YoY %", "MoM %", "Revised",
            "Consensus", "Surprise", "Source",
        ])
        self._table.setMaximumHeight(220)
        layout.addWidget(self._table)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_indicator_info(self, indicator: dict[str, Any]):
        name = indicator.get("name") or indicator.get("indicator_code", "")
        self._name_label.setText(name)

        freq = indicator.get("frequency", "")
        unit = indicator.get("unit", "")
        source = indicator.get("source_agency", "")
        country = indicator.get("country_code", "")
        parts = [p for p in [country, freq, unit, source] if p]
        self._meta_label.setText("  |  ".join(parts))

        self._value_label.setText("Loading...")
        self._change_label.setText("")

    def set_values(
        self,
        values: list[dict[str, Any]],
        indicator: dict[str, Any] | None = None,
    ):
        """Populate chart and table from macro-value records (newest first)."""
        if not values:
            self._value_label.setText("No data")
            self._table.setRowCount(0)
            return

        # Update latest value in header
        latest = values[0]
        val = latest.get("value")
        self._value_label.setText(f"{val:,.2f}" if val is not None else "--")

        change = latest.get("change") or latest.get("value_mom")
        pct = latest.get("change_percent") or latest.get("value_mom_percent")
        if change is not None:
            sign = "+" if change >= 0 else ""
            color = _GREEN if change >= 0 else _RED
            pct_str = f"  ({sign}{pct:.2f}%)" if pct is not None else ""
            self._change_label.setText(f"{sign}{change:.4g}{pct_str}")
            self._change_label.setStyleSheet(
                f"color: {color}; font-family: {_FONT}; font-size: 12px; border: none;"
            )
        else:
            self._change_label.setText("")

        # Build chart
        self._build_chart(values)
        # Build table
        self._build_table(values)

    # ------------------------------------------------------------------
    # Chart
    # ------------------------------------------------------------------
    def _build_chart(self, values: list[dict[str, Any]]):
        self._chart.removeAllSeries()
        for ax in self._chart.axes():
            self._chart.removeAxis(ax)

        series = QLineSeries()
        series.setColor(QColor(_ORANGE))

        min_val = float("inf")
        max_val = float("-inf")

        # values are newest-first; iterate in chronological order
        for v in reversed(values):
            obs_date = v.get("observation_date")
            val = v.get("value")
            if obs_date is None or val is None:
                continue

            if isinstance(obs_date, str):
                parts = obs_date.split("-")
                y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            else:
                y, m, d = obs_date.year, obs_date.month, obs_date.day

            ts = float(QDateTime(y, m, d, 0, 0).toMSecsSinceEpoch())
            series.append(ts, val)
            min_val = min(min_val, val)
            max_val = max(max_val, val)

        self._chart.addSeries(series)

        # X-axis
        axis_x = QDateTimeAxis()
        axis_x.setFormat("yyyy-MM")
        axis_x.setLabelsColor(QColor(_TEXT_DIM))
        axis_x.setGridLineColor(QColor(_BORDER))
        axis_x.setTickCount(8)
        self._chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        # Y-axis
        axis_y = QValueAxis()
        rng = max_val - min_val if max_val > min_val else 1
        axis_y.setRange(min_val - rng * 0.05, max_val + rng * 0.05)
        axis_y.setLabelsColor(QColor(_TEXT_DIM))
        axis_y.setGridLineColor(QColor(_BORDER))
        self._chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

    # ------------------------------------------------------------------
    # Table
    # ------------------------------------------------------------------
    def _build_table(self, values: list[dict[str, Any]]):
        self._table.setRowCount(len(values))
        for r, v in enumerate(values):
            dt = str(v.get("observation_date", "--"))
            val = v.get("value")
            yoy = v.get("value_yoy_percent")
            mom = v.get("value_mom_percent")
            revised = "Y" if v.get("is_revised") else ""
            consensus = v.get("consensus_estimate")
            surprise = v.get("surprise_percent")
            source = v.get("source", "")

            self._set(r, 0, dt)
            self._set(r, 1, f"{val:,.2f}" if val is not None else "--", right=True)
            self._set(r, 2, f"{yoy:.2f}%" if yoy is not None else "--", right=True,
                      color=_GREEN if yoy and yoy >= 0 else _RED if yoy else _TEXT_DIM)
            self._set(r, 3, f"{mom:.2f}%" if mom is not None else "--", right=True)
            self._set(r, 4, revised)
            self._set(r, 5, f"{consensus:,.2f}" if consensus is not None else "--", right=True)
            self._set(r, 6, f"{surprise:.2f}%" if surprise is not None else "--", right=True,
                      color=_GREEN if surprise and surprise >= 0 else _RED if surprise else _TEXT_DIM)
            self._set(r, 7, source)

    def _set(self, r: int, c: int, text: str, right: bool = False, color: str = _TEXT):
        item = QTableWidgetItem(text)
        align = Qt.AlignmentFlag.AlignRight if right else Qt.AlignmentFlag.AlignLeft
        item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
        item.setForeground(QColor(color))
        self._table.setItem(r, c, item)

    # ------------------------------------------------------------------
    # Table setup helper
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


# ---------------------------------------------------------------------------
# ECFC Panel
# ---------------------------------------------------------------------------
class ECFCPanel(BasePanel):
    """ECFC -- macroeconomic indicators dashboard."""

    panel_name = "ECFC"
    panel_title = "ECFC - Economic Data"

    def __init__(self, data_service, app_state, parent=None):
        super().__init__(data_service, app_state, parent)

        self.setStyleSheet(f"background: {_BG};")

        # ---- Header ----
        header = QLabel("ECONOMIC INDICATORS")
        header.setStyleSheet(
            f"color: {_ORANGE}; font-family: {_FONT}; font-size: 14px; font-weight: bold;"
        )
        self._layout.addWidget(header)

        # ---- Category filter ----
        self._category_bar = _CategoryBar(self._on_category_changed)
        self._layout.addWidget(self._category_bar)

        # ---- Splitter: sidebar | detail ----
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background: {_BORDER};
                width: 3px;
            }}
        """)

        # -- Left sidebar: indicator list --
        sidebar = QWidget()
        sidebar.setMaximumWidth(300)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(2)

        self._indicator_count_label = QLabel("0 indicators")
        self._indicator_count_label.setStyleSheet(
            f"color: {_TEXT_DIM}; font-family: {_FONT}; font-size: 10px;"
        )
        sidebar_layout.addWidget(self._indicator_count_label)

        self._indicator_list = QListWidget()
        self._indicator_list.setStyleSheet(f"""
            QListWidget {{
                background: {_BG_CARD};
                color: {_TEXT};
                font-family: {_FONT};
                font-size: 12px;
                border: 1px solid {_BORDER};
            }}
            QListWidget::item {{
                padding: 4px 8px;
                border-bottom: 1px solid {_BORDER};
            }}
            QListWidget::item:selected {{
                background: {_ORANGE};
                color: {_BG};
            }}
            QListWidget::item:hover {{
                background: #1e293b;
            }}
        """)
        self._indicator_list.currentItemChanged.connect(self._on_indicator_selected)
        sidebar_layout.addWidget(self._indicator_list)

        splitter.addWidget(sidebar)

        # -- Right: detail view --
        self._detail = _IndicatorDetail()
        splitter.addWidget(self._detail)

        splitter.setSizes([250, 600])
        self._layout.addWidget(splitter, stretch=1)

        # ---- State ----
        self._all_indicators: list[dict[str, Any]] = []
        self._current_category: str = "ALL"
        self._current_indicator: dict[str, Any] | None = None

        # ---- Connect signals ----
        if hasattr(data_service, "macro_indicators_loaded"):
            data_service.macro_indicators_loaded.connect(self._on_indicators_loaded)
        if hasattr(data_service, "macro_values_loaded"):
            data_service.macro_values_loaded.connect(self._on_values_loaded)

    # ------------------------------------------------------------------
    # Panel lifecycle
    # ------------------------------------------------------------------
    def activate(self, context: dict | None = None):
        self._indicator_list.clear()
        self._indicator_list.addItem(
            QListWidgetItem("Loading indicators...")
        )
        if hasattr(self.data_service, "load_macro_indicators"):
            self.data_service.load_macro_indicators()

    # ------------------------------------------------------------------
    # Category filter
    # ------------------------------------------------------------------
    def _on_category_changed(self, category: str):
        self._current_category = category
        self._refresh_list()

    # ------------------------------------------------------------------
    # Data callbacks
    # ------------------------------------------------------------------
    @Slot(object)
    def _on_indicators_loaded(self, indicators: list[dict[str, Any]]):
        self._all_indicators = indicators
        self._refresh_list()

    @Slot(object)
    def _on_values_loaded(self, data: dict[str, Any]):
        """Handle loaded macro values.

        Expected shape::

            {
                "indicator_id": "...",
                "values": [ {MacroValueResponse dict}, ... ],  # newest first
            }
        """
        values = data.get("values", [])
        self._detail.set_values(values, self._current_indicator)

    # ------------------------------------------------------------------
    # List management
    # ------------------------------------------------------------------
    def _refresh_list(self):
        self._indicator_list.clear()
        cat = self._current_category

        filtered = [
            ind for ind in self._all_indicators
            if cat == "ALL" or ind.get("category", "").upper() == cat
        ]

        self._indicator_count_label.setText(f"{len(filtered)} indicators")

        for ind in filtered:
            item = _IndicatorListItem(ind)
            freq = ind.get("frequency", "")
            country = ind.get("country_code", "")
            suffix = f"  [{country}]" if country else ""
            item.setText(
                f"{ind.get('name', ind.get('indicator_code', '???'))}{suffix}"
            )
            tooltip_parts = [
                f"Code: {ind.get('indicator_code', '')}",
                f"Freq: {freq}",
                f"Unit: {ind.get('unit', '')}",
                f"Source: {ind.get('source_agency', '')}",
            ]
            item.setToolTip("\n".join(tooltip_parts))
            self._indicator_list.addItem(item)

    def _on_indicator_selected(self, current: QListWidgetItem | None, previous):
        if current is None or not isinstance(current, _IndicatorListItem):
            return
        indicator = current.indicator
        self._current_indicator = indicator
        self._detail.set_indicator_info(indicator)

        ind_id = indicator.get("indicator_id")
        if ind_id and hasattr(self.data_service, "load_macro_values"):
            self.data_service.load_macro_values(ind_id)
