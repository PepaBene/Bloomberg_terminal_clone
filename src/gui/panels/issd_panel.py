"""ISSD -- New Issuance panel (primary-market bond issuance)."""

from __future__ import annotations

import logging

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QLabel

from ._common import TEXT, FONT, cell, fmt_money, header_label_style, make_table
from .base_panel import BasePanel

logger = logging.getLogger(__name__)


class IssuancePanel(BasePanel):
    """ISSD -- recent primary-market debt issuance."""

    panel_name = "ISSD"
    panel_title = "ISSD - New Issuance"

    def __init__(self, data_service, app_state, parent=None):
        super().__init__(data_service, app_state, parent)

        header = QLabel("NEW ISSUANCE  ·  Primary Market")
        header.setStyleSheet(header_label_style())
        self._layout.addWidget(header)

        self._headline = QLabel("Recent bond issuance (load a company for issuer-specific deals)")
        self._headline.setStyleSheet(f"color: {TEXT}; font-family: {FONT}; font-size: 12px;")
        self._layout.addWidget(self._headline)

        self._table = make_table(
            ["Pricing Date", "Coupon", "Maturity", "Size (mm)", "Spread (bps)", "Yield", "Seniority"]
        )
        self._layout.addWidget(self._table, stretch=1)

        if hasattr(data_service, "issuance_loaded"):
            data_service.issuance_loaded.connect(self._on_loaded)

    def activate(self, context: dict | None = None):
        if hasattr(self.data_service, "run_issuance"):
            self.data_service.run_issuance((context or {}).get("entity_id"))

    @Slot(object)
    def _on_loaded(self, rows: list):
        rows = rows or []
        if not rows:
            self._headline.setText("No issuance data on file")
        self._table.setRowCount(len(rows))
        for r, d in enumerate(rows):
            self._table.setItem(r, 0, cell(d.get("pricing_date")))
            self._table.setItem(r, 1, cell(d.get("coupon_rate")))
            self._table.setItem(r, 2, cell(d.get("maturity_date")))
            self._table.setItem(r, 3, cell(fmt_money(d.get("issued_size_mm"), 1), align_right=True))
            self._table.setItem(r, 4, cell(d.get("final_spread_bps"), align_right=True))
            self._table.setItem(r, 5, cell(d.get("issue_yield")))
            self._table.setItem(r, 6, cell(d.get("seniority")))
