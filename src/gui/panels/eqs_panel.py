"""EQS -- Equity Screening panel (E4: Screen & Rank).

Provides a placeholder for the screening engine. The full screening
engine (E4) runs server-side; this panel provides the UI entry point.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QLabel,
    QVBoxLayout,
)

from .base_panel import BasePanel

logger = logging.getLogger(__name__)

_BG = "#0a0e17"
_TEXT = "#e2e8f0"
_TEXT_DIM = "#94a3b8"
_ORANGE = "#ff6600"
_BORDER = "#1e293b"
_FONT = "Consolas, 'Courier New', monospace"


class EqsPanel(BasePanel):
    """EQS -- equity screening panel."""

    panel_name = "EQS"
    panel_title = "EQS - Equity Screening"

    def __init__(self, data_service, app_state, parent=None):
        super().__init__(data_service, app_state, parent)
        self.setStyleSheet(f"background: {_BG};")

        self._header = QLabel("EQUITY SCREENING")
        self._header.setStyleSheet(
            f"color: {_ORANGE}; font-family: {_FONT}; font-size: 14px; font-weight: bold;"
        )
        self._layout.addWidget(self._header)

        desc = QLabel(
            "Screen equities across financial, valuation, and quality metrics.\n\n"
            "This panel interfaces with the E4 Screening Engine to provide\n"
            "multi-factor ranking and filtering capabilities.\n\n"
            "Use the command bar to run screens:\n"
            "  EQS                    - Open screening panel\n"
            "  EQS VALUE              - Run value screen\n"
            "  EQS QUALITY            - Run quality screen"
        )
        desc.setStyleSheet(f"color: {_TEXT_DIM}; font-family: {_FONT}; font-size: 12px;")
        self._layout.addWidget(desc)

        self._layout.addStretch(1)

    def activate(self, context: dict | None = None):
        pass
