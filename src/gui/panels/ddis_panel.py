"""DDIS -- Debt Distribution / Maturity profile panel."""

from __future__ import annotations

import logging

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QLabel, QTabWidget

from ._common import cell, fmt_money, header_label_style, kv_table, make_table, populate_kv, FONT, TEXT
from .base_panel import BasePanel

logger = logging.getLogger(__name__)


class DebtMaturityPanel(BasePanel):
    """DDIS -- debt maturity profile and maturity wall."""

    panel_name = "DDIS"
    panel_title = "DDIS - Debt Maturity"

    def __init__(self, data_service, app_state, parent=None):
        super().__init__(data_service, app_state, parent)

        header = QLabel("DEBT MATURITY PROFILE")
        header.setStyleSheet(header_label_style())
        self._layout.addWidget(header)

        self._headline = QLabel("Load a company (e.g. AAPL DDIS) to view its maturity profile")
        self._headline.setStyleSheet(f"color: {TEXT}; font-family: {FONT}; font-size: 13px;")
        self._layout.addWidget(self._headline)

        self._tabs = QTabWidget()
        self._summary = kv_table()
        self._buckets = make_table(["Year", "Amount Maturing", "Breakdown"])
        self._tabs.addTab(self._summary, "Summary")
        self._tabs.addTab(self._buckets, "Maturity Buckets")
        self._layout.addWidget(self._tabs, stretch=1)

        if hasattr(data_service, "debt_maturity_loaded"):
            data_service.debt_maturity_loaded.connect(self._on_loaded)

    def activate(self, context: dict | None = None):
        context = context or {}
        entity_id = context.get("entity_id")
        if entity_id and hasattr(self.data_service, "run_debt_maturity"):
            self._headline.setText("Loading debt maturity profile...")
            self.data_service.run_debt_maturity(entity_id)

    @Slot(object)
    def _on_loaded(self, payload: dict):
        payload = payload or {}
        profile = payload.get("profile") or {}
        if not profile:
            self._headline.setText("No debt maturity data on file")
            return
        self._headline.setText(payload.get("subject") or "Debt Maturity")
        populate_kv(self._summary, [
            ("Weighted avg maturity (yrs)", profile.get("weighted_avg_maturity_years")),
            ("Weighted avg coupon", profile.get("weighted_avg_coupon")),
            ("Debt maturing <=1yr", fmt_money(profile.get("debt_maturing_1yr"))),
            ("% maturing <=1yr", profile.get("pct_debt_maturing_1yr")),
            ("% maturing <=3yr", profile.get("pct_debt_maturing_3yr")),
            ("Cash / 1yr maturities", profile.get("cash_to_1yr_maturities")),
            ("Maturity wall alert", "YES" if profile.get("maturity_wall_alert") else "no"),
            ("Near-term stress", "YES" if profile.get("near_term_stress") else "no"),
        ])
        buckets = payload.get("buckets") or []
        self._buckets.setRowCount(len(buckets))
        for r, b in enumerate(buckets):
            self._buckets.setItem(r, 0, cell(b.get("year")))
            self._buckets.setItem(r, 1, cell(fmt_money(b.get("total_amount")), align_right=True))
            breakdown = b.get("breakdown") or {}
            self._buckets.setItem(r, 2, cell(", ".join(f"{k}:{v}" for k, v in breakdown.items())))
