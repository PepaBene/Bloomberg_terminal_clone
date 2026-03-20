"""Bloomberg Terminal dark theme for the PySide6 GUI.

Provides a comprehensive QSS stylesheet, a QPalette, and named colour
constants that match the Bloomberg Terminal aesthetic -- dense, dark,
monospaced, with orange highlights.

Public API
----------
- ``get_stylesheet() -> str``   -- complete QSS string
- ``get_palette()    -> QPalette`` -- dark QPalette for QApplication
- Colour constants (``BG_DARK``, ``BLOOMBERG_ORANGE``, etc.)
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette

# ======================================================================
# Colour constants
# ======================================================================

BG_DARK: str        = "#0a0e17"   # Near-black application background
BG_PANEL: str       = "#111827"   # Panel / dock background
BG_SURFACE: str     = "#1e293b"   # Cards, inputs, table cells
TEXT_PRIMARY: str    = "#e2e8f0"   # Light grey -- main text
TEXT_SECONDARY: str  = "#94a3b8"   # Dimmed labels
TEXT_DISABLED: str   = "#475569"   # Disabled / placeholder
BLOOMBERG_ORANGE: str = "#ff6600" # Headers, active highlights
POSITIVE: str       = "#22c55e"   # Green -- up / positive
NEGATIVE: str       = "#ef4444"   # Red -- down / negative
WARNING: str        = "#f59e0b"   # Amber warnings
BORDER: str         = "#334155"   # Subtle borders
SELECTION: str      = "#1e3a5f"   # Row / text selection
SCROLLBAR: str      = "#475569"   # Scrollbar thumb

# Font stack -- Consolas first (ships with Windows), then Source Code Pro,
# then any available monospace font.
FONT_FAMILY: str    = '"Consolas", "Source Code Pro", "Courier New", monospace'
FONT_SIZE: str      = "10pt"

# ======================================================================
# QSS Stylesheet
# ======================================================================

_QSS = f"""
/* ------------------------------------------------------------------ */
/* Global defaults                                                     */
/* ------------------------------------------------------------------ */
QWidget {{
    background-color: {BG_DARK};
    color: {TEXT_PRIMARY};
    font-family: {FONT_FAMILY};
    font-size: {FONT_SIZE};
    border: none;
}}

QMainWindow {{
    background-color: {BG_DARK};
}}

QMainWindow::separator {{
    background-color: {BORDER};
    width: 2px;
    height: 2px;
}}

/* ------------------------------------------------------------------ */
/* QLabel                                                              */
/* ------------------------------------------------------------------ */
QLabel {{
    background: transparent;
    padding: 1px;
}}

/* ------------------------------------------------------------------ */
/* QGroupBox                                                           */
/* ------------------------------------------------------------------ */
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 3px;
    margin-top: 8px;
    padding-top: 12px;
    font-weight: bold;
    color: {BLOOMBERG_ORANGE};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 6px;
    color: {BLOOMBERG_ORANGE};
}}

/* ------------------------------------------------------------------ */
/* QPushButton                                                         */
/* ------------------------------------------------------------------ */
QPushButton {{
    background-color: {BG_SURFACE};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 2px;
    padding: 4px 12px;
    min-height: 20px;
}}

QPushButton:hover {{
    background-color: {SELECTION};
    border-color: {BLOOMBERG_ORANGE};
}}

QPushButton:pressed {{
    background-color: {BLOOMBERG_ORANGE};
    color: {BG_DARK};
}}

QPushButton:disabled {{
    background-color: {BG_PANEL};
    color: {TEXT_DISABLED};
    border-color: {BG_SURFACE};
}}

/* ------------------------------------------------------------------ */
/* QLineEdit  (command-bar style)                                      */
/* ------------------------------------------------------------------ */
QLineEdit {{
    background-color: {BG_SURFACE};
    color: {BLOOMBERG_ORANGE};
    border: 1px solid {BORDER};
    border-radius: 2px;
    padding: 4px 8px;
    selection-background-color: {SELECTION};
    selection-color: {TEXT_PRIMARY};
    font-weight: bold;
}}

QLineEdit:focus {{
    border-color: {BLOOMBERG_ORANGE};
}}

QLineEdit:disabled {{
    color: {TEXT_DISABLED};
}}

/* ------------------------------------------------------------------ */
/* QComboBox                                                           */
/* ------------------------------------------------------------------ */
QComboBox {{
    background-color: {BG_SURFACE};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 2px;
    padding: 3px 8px;
    min-height: 20px;
}}

QComboBox:hover {{
    border-color: {BLOOMBERG_ORANGE};
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TEXT_SECONDARY};
    margin-right: 6px;
}}

QComboBox QAbstractItemView {{
    background-color: {BG_PANEL};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    selection-background-color: {SELECTION};
    selection-color: {BLOOMBERG_ORANGE};
    outline: none;
}}

/* ------------------------------------------------------------------ */
/* QSpinBox                                                            */
/* ------------------------------------------------------------------ */
QSpinBox {{
    background-color: {BG_SURFACE};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 2px;
    padding: 3px 8px;
}}

QSpinBox:focus {{
    border-color: {BLOOMBERG_ORANGE};
}}

QSpinBox::up-button, QSpinBox::down-button {{
    background-color: {BG_PANEL};
    border: none;
    width: 16px;
}}

QSpinBox::up-arrow {{
    border-left: 3px solid transparent;
    border-right: 3px solid transparent;
    border-bottom: 4px solid {TEXT_SECONDARY};
}}

QSpinBox::down-arrow {{
    border-left: 3px solid transparent;
    border-right: 3px solid transparent;
    border-top: 4px solid {TEXT_SECONDARY};
}}

/* ------------------------------------------------------------------ */
/* QTableView (dense data grid)                                        */
/* ------------------------------------------------------------------ */
QTableView {{
    background-color: {BG_PANEL};
    alternate-background-color: {BG_SURFACE};
    color: {TEXT_PRIMARY};
    gridline-color: {BORDER};
    border: 1px solid {BORDER};
    selection-background-color: {SELECTION};
    selection-color: {TEXT_PRIMARY};
    outline: none;
}}

QTableView::item {{
    padding: 2px 6px;
    border: none;
}}

QTableView::item:selected {{
    background-color: {SELECTION};
    color: {TEXT_PRIMARY};
}}

QTableView QTableCornerButton::section {{
    background-color: {BG_SURFACE};
    border: 1px solid {BORDER};
}}

/* ------------------------------------------------------------------ */
/* QHeaderView (Bloomberg orange headers)                              */
/* ------------------------------------------------------------------ */
QHeaderView {{
    background-color: {BG_SURFACE};
    border: none;
}}

QHeaderView::section {{
    background-color: {BG_SURFACE};
    color: {BLOOMBERG_ORANGE};
    border: 1px solid {BORDER};
    padding: 3px 6px;
    font-weight: bold;
    font-size: 9pt;
}}

QHeaderView::section:hover {{
    background-color: {SELECTION};
}}

/* ------------------------------------------------------------------ */
/* QTabWidget / QTabBar                                                */
/* ------------------------------------------------------------------ */
QTabWidget::pane {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER};
    border-top: 2px solid {BLOOMBERG_ORANGE};
}}

QTabBar {{
    background: transparent;
}}

QTabBar::tab {{
    background-color: {BG_SURFACE};
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER};
    border-bottom: none;
    padding: 4px 14px;
    margin-right: 1px;
    min-width: 60px;
}}

QTabBar::tab:selected {{
    background-color: {BG_PANEL};
    color: {BLOOMBERG_ORANGE};
    border-bottom: 2px solid {BLOOMBERG_ORANGE};
    font-weight: bold;
}}

QTabBar::tab:hover:!selected {{
    background-color: {SELECTION};
    color: {TEXT_PRIMARY};
}}

/* ------------------------------------------------------------------ */
/* QScrollBar (thin, unobtrusive)                                      */
/* ------------------------------------------------------------------ */
QScrollBar:vertical {{
    background-color: {BG_DARK};
    width: 8px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background-color: {SCROLLBAR};
    min-height: 30px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {TEXT_SECONDARY};
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{
    background: none;
    height: 0;
    border: none;
}}

QScrollBar:horizontal {{
    background-color: {BG_DARK};
    height: 8px;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background-color: {SCROLLBAR};
    min-width: 30px;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {TEXT_SECONDARY};
}}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {{
    background: none;
    width: 0;
    border: none;
}}

/* ------------------------------------------------------------------ */
/* QDockWidget                                                         */
/* ------------------------------------------------------------------ */
QDockWidget {{
    color: {BLOOMBERG_ORANGE};
    font-weight: bold;
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
}}

QDockWidget::title {{
    background-color: {BG_SURFACE};
    border: 1px solid {BORDER};
    padding: 4px 8px;
    text-align: left;
}}

QDockWidget::close-button,
QDockWidget::float-button {{
    background: transparent;
    border: none;
    padding: 2px;
}}

QDockWidget::close-button:hover,
QDockWidget::float-button:hover {{
    background-color: {SELECTION};
}}

/* ------------------------------------------------------------------ */
/* QSplitter                                                           */
/* ------------------------------------------------------------------ */
QSplitter::handle {{
    background-color: {BORDER};
}}

QSplitter::handle:horizontal {{
    width: 2px;
}}

QSplitter::handle:vertical {{
    height: 2px;
}}

QSplitter::handle:hover {{
    background-color: {BLOOMBERG_ORANGE};
}}

/* ------------------------------------------------------------------ */
/* QToolTip                                                            */
/* ------------------------------------------------------------------ */
QToolTip {{
    background-color: {BG_SURFACE};
    color: {TEXT_PRIMARY};
    border: 1px solid {BLOOMBERG_ORANGE};
    padding: 4px;
}}

/* ------------------------------------------------------------------ */
/* QMenu                                                               */
/* ------------------------------------------------------------------ */
QMenu {{
    background-color: {BG_PANEL};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    padding: 2px;
}}

QMenu::item {{
    padding: 4px 24px 4px 12px;
}}

QMenu::item:selected {{
    background-color: {SELECTION};
    color: {BLOOMBERG_ORANGE};
}}

QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 4px 8px;
}}

/* ------------------------------------------------------------------ */
/* QStatusBar                                                          */
/* ------------------------------------------------------------------ */
QStatusBar {{
    background-color: {BG_SURFACE};
    color: {TEXT_SECONDARY};
    border-top: 1px solid {BORDER};
    font-size: 9pt;
}}

QStatusBar::item {{
    border: none;
}}

/* ------------------------------------------------------------------ */
/* QProgressBar                                                        */
/* ------------------------------------------------------------------ */
QProgressBar {{
    background-color: {BG_SURFACE};
    border: 1px solid {BORDER};
    border-radius: 2px;
    text-align: center;
    color: {TEXT_PRIMARY};
    height: 14px;
}}

QProgressBar::chunk {{
    background-color: {BLOOMBERG_ORANGE};
    border-radius: 1px;
}}
"""


def get_stylesheet() -> str:
    """Return the complete QSS stylesheet string."""
    return _QSS


def get_palette() -> QPalette:
    """Build and return a QPalette configured for the Bloomberg dark theme.

    Apply to ``QApplication.setPalette(get_palette())`` before showing any
    widgets so that native dialogs and un-styled widgets also look correct.
    """
    palette = QPalette()

    # Window / background roles
    palette.setColor(QPalette.ColorRole.Window, QColor(BG_DARK))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Base, QColor(BG_PANEL))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(BG_SURFACE))

    # Text roles
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(BLOOMBERG_ORANGE))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(TEXT_DISABLED))

    # Button roles
    palette.setColor(QPalette.ColorRole.Button, QColor(BG_SURFACE))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT_PRIMARY))

    # Selection / highlight roles
    palette.setColor(QPalette.ColorRole.Highlight, QColor(SELECTION))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(TEXT_PRIMARY))

    # Tooltip
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(BG_SURFACE))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT_PRIMARY))

    # Links
    palette.setColor(QPalette.ColorRole.Link, QColor(BLOOMBERG_ORANGE))
    palette.setColor(QPalette.ColorRole.LinkVisited, QColor(TEXT_SECONDARY))

    # Disabled group
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(TEXT_DISABLED)
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(TEXT_DISABLED)
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(TEXT_DISABLED)
    )

    return palette
