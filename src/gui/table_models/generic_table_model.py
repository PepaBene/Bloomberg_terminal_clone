"""Generic table model for financial data display.

Provides a QAbstractTableModel that works with list[dict] data and a
declarative ColumnConfig for formatting, alignment, and color coding.
"""

from __future__ import annotations

import locale
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor

# ---------------------------------------------------------------------------
# Bloomberg-style palette constants
# ---------------------------------------------------------------------------
COLOR_POSITIVE = QColor("#00C805")   # Bloomberg green
COLOR_NEGATIVE = QColor("#FF3333")   # Bloomberg red
COLOR_NEUTRAL = QColor("#D4D4D4")    # Default text color
COLOR_HEADER_FG = QColor("#FFA500")  # Orange header text


@dataclass
class ColumnConfig:
    """Declarative column specification for :class:`GenericTableModel`.

    Parameters
    ----------
    name:
        Human-readable column header displayed in the table.
    key:
        Dictionary key used to look up the value in each row dict.
    width:
        Preferred column width in pixels (hint for the view).
    align:
        Horizontal alignment -- ``"left"``, ``"right"``, or ``"center"``.
    format:
        Display format: ``"text"``, ``"number"``, ``"currency"``,
        ``"percent"``, ``"date"``.
    color_code:
        When ``True`` and the value is numeric, positive values are shown
        in green and negative values in red.
    decimals:
        Number of decimal places for numeric formats.  Defaults to 2.
    """

    name: str
    key: str
    width: int = 120
    align: str = "left"
    format: str = "text"
    color_code: bool = False
    decimals: int = 2


_ALIGN_MAP = {
    "left": Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
    "right": Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
    "center": Qt.AlignmentFlag.AlignCenter,
}


class GenericTableModel(QAbstractTableModel):
    """A flexible table model that accepts ``list[dict]`` rows.

    Usage::

        cols = [
            ColumnConfig("Ticker", "ticker", 80, "left", "text"),
            ColumnConfig("Price", "price", 100, "right", "currency", color_code=True),
        ]
        model = GenericTableModel(cols)
        model.set_data([{"ticker": "AAPL", "price": 189.25}, ...])
    """

    def __init__(self, columns: list[ColumnConfig], parent=None):
        super().__init__(parent)
        self._columns = columns
        self._data: list[dict] = []
        self._sort_column: int = 0
        self._sort_order: Qt.SortOrder = Qt.SortOrder.AscendingOrder

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def set_data(self, rows: list[dict]) -> None:
        """Replace all model data and reset the view."""
        self.beginResetModel()
        self._data = list(rows)
        self.endResetModel()

    def get_row(self, row: int) -> dict | None:
        """Return the raw dict for *row*, or ``None`` if out of range."""
        if 0 <= row < len(self._data):
            return self._data[row]
        return None

    def get_all_data(self) -> list[dict]:
        """Return a shallow copy of the underlying data."""
        return list(self._data)

    # ------------------------------------------------------------------
    # QAbstractTableModel required overrides
    # ------------------------------------------------------------------

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return len(self._data)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()
        if row < 0 or row >= len(self._data) or col < 0 or col >= len(self._columns):
            return None

        col_cfg = self._columns[col]
        raw = self._data[row].get(col_cfg.key)

        # -- Display text --------------------------------------------------
        if role == Qt.ItemDataRole.DisplayRole:
            return self._format_value(raw, col_cfg)

        # -- Text alignment ------------------------------------------------
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return _ALIGN_MAP.get(col_cfg.align, _ALIGN_MAP["left"])

        # -- Foreground color (positive / negative) ------------------------
        if role == Qt.ItemDataRole.ForegroundRole:
            if col_cfg.color_code and isinstance(raw, (int, float)):
                if raw > 0:
                    return COLOR_POSITIVE
                elif raw < 0:
                    return COLOR_NEGATIVE
            return COLOR_NEUTRAL

        # -- Raw value for sorting -----------------------------------------
        if role == Qt.ItemDataRole.UserRole:
            return raw

        return None

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal and 0 <= section < len(self._columns):
                return self._columns[section].name
            if orientation == Qt.Orientation.Vertical:
                return str(section + 1)
        if role == Qt.ItemDataRole.ForegroundRole and orientation == Qt.Orientation.Horizontal:
            return COLOR_HEADER_FG
        return None

    # ------------------------------------------------------------------
    # Sorting
    # ------------------------------------------------------------------

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        """Sort the data by *column*."""
        if column < 0 or column >= len(self._columns):
            return
        self._sort_column = column
        self._sort_order = order
        col_cfg = self._columns[column]

        self.layoutAboutToBeChanged.emit()

        def sort_key(row: dict) -> Any:
            val = row.get(col_cfg.key)
            if val is None:
                # Push nulls to the end regardless of direction.
                return (1, "")
            if isinstance(val, str):
                return (0, val.lower())
            return (0, val)

        self._data.sort(
            key=sort_key,
            reverse=(order == Qt.SortOrder.DescendingOrder),
        )
        self.layoutChanged.emit()

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_value(raw: Any, cfg: ColumnConfig) -> str:
        """Format a raw value for display according to *cfg*."""
        if raw is None:
            return ""

        fmt = cfg.format

        if fmt == "text":
            return str(raw)

        if fmt == "number":
            if isinstance(raw, (int, float)):
                return f"{raw:,.{cfg.decimals}f}"
            return str(raw)

        if fmt == "currency":
            if isinstance(raw, (int, float)):
                sign = "-" if raw < 0 else ""
                return f"{sign}${abs(raw):,.{cfg.decimals}f}"
            return str(raw)

        if fmt == "percent":
            if isinstance(raw, (int, float)):
                return f"{raw:,.{cfg.decimals}f}%"
            return str(raw)

        if fmt == "date":
            if isinstance(raw, datetime):
                return raw.strftime("%Y-%m-%d %H:%M")
            if isinstance(raw, date):
                return raw.strftime("%Y-%m-%d")
            return str(raw)

        return str(raw)
