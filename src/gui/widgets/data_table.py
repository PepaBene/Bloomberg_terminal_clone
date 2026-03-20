"""Reusable financial data table widget.

A styled QTableView subclass with Bloomberg-terminal aesthetics:
dark alternating rows, right-aligned numerics, color-coded values,
column sorting, clipboard copy, and CSV export.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QAction, QClipboard, QFont, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QHeaderView,
    QMenu,
    QTableView,
    QWidget,
)

from src.gui.table_models.generic_table_model import ColumnConfig, GenericTableModel

# ---------------------------------------------------------------------------
# Stylesheet
# ---------------------------------------------------------------------------
_TABLE_STYLE = """
QTableView {
    background-color: #0D0D1A;
    alternate-background-color: #12122A;
    color: #D4D4D4;
    gridline-color: #222233;
    border: 1px solid #333344;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
    selection-background-color: #FF8C00;
    selection-color: #000000;
}
QTableView::item {
    padding: 2px 6px;
    border: none;
}
QTableView::item:selected {
    background-color: #FF8C00;
    color: #000000;
}
QHeaderView::section {
    background-color: #1A1A2E;
    color: #FFA500;
    border: 1px solid #333344;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 11px;
    font-weight: bold;
    padding: 3px 6px;
}
QHeaderView::section:hover {
    background-color: #252540;
}
QScrollBar:vertical {
    background-color: #0D0D1A;
    width: 10px;
    border: none;
}
QScrollBar::handle:vertical {
    background-color: #333344;
    min-height: 20px;
    border-radius: 4px;
}
QScrollBar:horizontal {
    background-color: #0D0D1A;
    height: 10px;
    border: none;
}
QScrollBar::handle:horizontal {
    background-color: #333344;
    min-width: 20px;
    border-radius: 4px;
}
"""


class DataTable(QTableView):
    """A QTableView styled for dense financial data display.

    Parameters
    ----------
    columns:
        List of :class:`ColumnConfig` definitions describing each column.
    parent:
        Optional parent widget.
    """

    def __init__(self, columns: list[ColumnConfig], parent: QWidget | None = None):
        super().__init__(parent)
        self._columns = columns
        self._model = GenericTableModel(columns, self)
        self.setModel(self._model)
        self._configure_view()
        self._setup_shortcuts()
        self.setStyleSheet(_TABLE_STYLE)

    # ------------------------------------------------------------------
    # View configuration
    # ------------------------------------------------------------------

    def _configure_view(self) -> None:
        # General behaviour
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSortingEnabled(True)
        self.setShowGrid(True)
        self.setWordWrap(False)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(22)

        # Font
        font = QFont("Consolas", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)

        # Column widths
        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionsClickable(True)
        header.setHighlightSections(False)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        for i, col in enumerate(self._columns):
            if col.width:
                self.setColumnWidth(i, col.width)

        # Context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------

    def _setup_shortcuts(self) -> None:
        copy_sc = QShortcut(QKeySequence.StandardKey.Copy, self)
        copy_sc.activated.connect(self.copy_selection)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_data(self, rows: list[dict]) -> None:
        """Replace all table data."""
        self._model.set_data(rows)

    def get_model(self) -> GenericTableModel:
        """Return the underlying :class:`GenericTableModel`."""
        return self._model

    def copy_selection(self) -> None:
        """Copy the currently selected cells to the clipboard as TSV."""
        indexes = self.selectionModel().selectedIndexes()
        if not indexes:
            return

        # Group by row
        rows: dict[int, dict[int, str]] = {}
        for idx in indexes:
            rows.setdefault(idx.row(), {})[idx.column()] = (
                self._model.data(idx, Qt.ItemDataRole.DisplayRole) or ""
            )

        min_col = min(c for row_cols in rows.values() for c in row_cols)
        max_col = max(c for row_cols in rows.values() for c in row_cols)

        lines: list[str] = []
        for r in sorted(rows):
            cells = [str(rows[r].get(c, "")) for c in range(min_col, max_col + 1)]
            lines.append("\t".join(cells))

        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText("\n".join(lines))

    def export_csv(self, file_path: str | None = None) -> str | None:
        """Export all table data to a CSV file.

        Parameters
        ----------
        file_path:
            Destination path.  If ``None``, a save-file dialog is shown.

        Returns
        -------
        str or None
            The path written to, or ``None`` if the user cancelled.
        """
        if file_path is None:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Export to CSV", "", "CSV Files (*.csv);;All Files (*)"
            )
            if not file_path:
                return None

        data = self._model.get_all_data()
        if not data:
            return None

        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[c.key for c in self._columns])
            writer.writeheader()
            writer.writerows(data)

        return file_path

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def _show_context_menu(self, pos) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background-color: #1A1A2E; color: #D4D4D4; border: 1px solid #333344; }"
            "QMenu::item:selected { background-color: #FF8C00; color: #000000; }"
        )

        copy_action = QAction("Copy Selection\tCtrl+C", self)
        copy_action.triggered.connect(self.copy_selection)
        menu.addAction(copy_action)

        export_action = QAction("Export to CSV...", self)
        export_action.triggered.connect(lambda: self.export_csv())
        menu.addAction(export_action)

        menu.popup(self.viewport().mapToGlobal(pos))
