"""FLOW -- Fund Flow Analytics panel (E6: Institutional Flows).

Displays institutional fund flow data and trends.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
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
_FONT = "Consolas, 'Courier New', monospace"


class FlowPanel(BasePanel):
    """FLOW -- fund flow analytics panel."""

    panel_name = "FLOW"
    panel_title = "FLOW - Fund Flow Analytics"

    def __init__(self, data_service, app_state, parent=None):
        super().__init__(data_service, app_state, parent)
        self.setStyleSheet(f"background: {_BG};")

        self._header = QLabel("FUND FLOW ANALYTICS")
        self._header.setStyleSheet(
            f"color: {_ORANGE}; font-family: {_FONT}; font-size: 14px; font-weight: bold;"
        )
        self._layout.addWidget(self._header)

        desc = QLabel(
            "Track institutional fund flows and ownership changes.\n\n"
            "This panel interfaces with the E6 Flow Engine to display:\n"
            "  - Net institutional buying/selling trends\n"
            "  - 13F filing aggregation\n"
            "  - Sector rotation analysis\n"
            "  - Concentration metrics\n\n"
            "Use the command bar:\n"
            "  AAPL FLOW              - View flows for Apple\n"
            "  FLOW                   - Open flow dashboard"
        )
        desc.setStyleSheet(f"color: {_TEXT_DIM}; font-family: {_FONT}; font-size: 12px;")
        self._layout.addWidget(desc)

        self._layout.addStretch(1)

    def activate(self, context: dict | None = None):
        pass
