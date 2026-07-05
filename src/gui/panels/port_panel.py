"""PORT -- Portfolio panel (list of managed portfolios)."""

from __future__ import annotations

import logging

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QLabel

from ._common import TEXT, FONT, cell, fmt_money, header_label_style, make_table
from .base_panel import BasePanel

logger = logging.getLogger(__name__)


class PortfolioPanel(BasePanel):
    """PORT -- managed portfolios overview."""

    panel_name = "PORT"
    panel_title = "PORT - Portfolios"

    def __init__(self, data_service, app_state, parent=None):
        super().__init__(data_service, app_state, parent)

        header = QLabel("PORTFOLIOS")
        header.setStyleSheet(header_label_style())
        self._layout.addWidget(header)

        self._headline = QLabel("Your portfolios")
        self._headline.setStyleSheet(f"color: {TEXT}; font-family: {FONT}; font-size: 13px;")
        self._layout.addWidget(self._headline)

        self._table = make_table(
            ["Name", "Type", "Inception", "Base Ccy", "Initial Cash", "Current Cash", "Status"]
        )
        self._layout.addWidget(self._table, stretch=1)

        if hasattr(data_service, "portfolios_loaded"):
            data_service.portfolios_loaded.connect(self._on_loaded)

    def activate(self, context: dict | None = None):
        if hasattr(self.data_service, "load_portfolios"):
            self.data_service.load_portfolios()

    @Slot(object)
    def _on_loaded(self, rows: list):
        rows = rows or []
        if not rows:
            self._headline.setText("No portfolios found — create one via the API (/v4/portfolios)")
        else:
            self._headline.setText(f"{len(rows)} portfolio(s)")
        self._table.setRowCount(len(rows))
        for r, p in enumerate(rows):
            self._table.setItem(r, 0, cell(p.get("portfolio_name")))
            self._table.setItem(r, 1, cell(p.get("portfolio_type")))
            self._table.setItem(r, 2, cell(p.get("inception_date")))
            self._table.setItem(r, 3, cell(p.get("base_currency")))
            self._table.setItem(r, 4, cell(fmt_money(p.get("initial_cash")), align_right=True))
            self._table.setItem(r, 5, cell(fmt_money(p.get("current_cash")), align_right=True))
            self._table.setItem(r, 6, cell(p.get("status")))
