"""Shared styling + table helpers for Financial Analysis Suite panels.

Keeps the newer panels consistent without repeating the Bloomberg dark-theme
boilerplate in every file.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

BG = "#0a0e17"
BG_CARD = "#111827"
TEXT = "#e2e8f0"
TEXT_DIM = "#94a3b8"
ORANGE = "#ff6600"
GREEN = "#22c55e"
RED = "#ef4444"
BORDER = "#1e293b"
FONT = "Consolas, 'Courier New', monospace"

TAB_STYLE = f"""
    QTabWidget::pane {{ border: 1px solid {BORDER}; background: {BG}; }}
    QTabBar::tab {{
        background: {BG_CARD}; color: {TEXT_DIM};
        font-family: {FONT}; font-size: 11px;
        padding: 6px 14px; border: 1px solid {BORDER};
        border-bottom: none; margin-right: 2px;
    }}
    QTabBar::tab:selected {{ background: {BG}; color: {ORANGE}; font-weight: bold; }}
"""

TABLE_STYLE = f"""
    QTableWidget {{
        background: {BG_CARD}; color: {TEXT};
        font-family: {FONT}; font-size: 12px;
        gridline-color: {BORDER}; border: 1px solid {BORDER};
    }}
    QTableWidget::item {{ padding: 2px 6px; }}
    QHeaderView::section {{
        background: {BG}; color: {ORANGE};
        font-family: {FONT}; font-size: 11px; font-weight: bold;
        border: none; border-bottom: 1px solid {BORDER}; padding: 4px 6px;
    }}
"""


def header_label_style(size: int = 14) -> str:
    return f"color: {ORANGE}; font-family: {FONT}; font-size: {size}px; font-weight: bold;"


def make_table(headers: list[str]) -> QTableWidget:
    t = QTableWidget()
    t.setColumnCount(len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.verticalHeader().setVisible(False)
    t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setStyleSheet(TABLE_STYLE)
    return t


def kv_table() -> QTableWidget:
    return make_table(["Metric", "Value"])


def cell(text, color: str = TEXT, align_right: bool = False) -> QTableWidgetItem:
    item = QTableWidgetItem("--" if text is None else str(text))
    item.setForeground(QColor(color))
    if align_right:
        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return item


def populate_kv(table: QTableWidget, items: list[tuple[str, object]]) -> None:
    table.setRowCount(len(items))
    for r, (k, v) in enumerate(items):
        table.setItem(r, 0, cell(k, TEXT_DIM))
        table.setItem(r, 1, cell(v, TEXT, align_right=True))


def fmt_money(val, decimals: int = 0) -> str:
    if val is None:
        return "--"
    try:
        return f"{float(val):,.{decimals}f}"
    except (TypeError, ValueError):
        return str(val)
