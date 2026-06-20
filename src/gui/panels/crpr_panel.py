"""CRPR -- Credit Ratings panel (current ratings + rating-action history)."""

from __future__ import annotations

import logging

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QLabel, QTabWidget

from ._common import GREEN, RED, TEXT, FONT, cell, header_label_style, make_table
from .base_panel import BasePanel

logger = logging.getLogger(__name__)


class CreditRatingPanel(BasePanel):
    """CRPR -- agency credit ratings and rating events."""

    panel_name = "CRPR"
    panel_title = "CRPR - Credit Ratings"

    def __init__(self, data_service, app_state, parent=None):
        super().__init__(data_service, app_state, parent)

        header = QLabel("CREDIT RATINGS")
        header.setStyleSheet(header_label_style())
        self._layout.addWidget(header)

        self._headline = QLabel("Load a company (e.g. F CRPR) to view its credit ratings")
        self._headline.setStyleSheet(f"color: {TEXT}; font-family: {FONT}; font-size: 13px;")
        self._layout.addWidget(self._headline)

        self._tabs = QTabWidget()
        self._current = make_table(["Agency", "Rating", "Outlook", "Watch", "IG?", "Last Action"])
        self._events = make_table(["Date", "Agency", "Old", "New", "Direction", "Notches"])
        self._tabs.addTab(self._current, "Current Ratings")
        self._tabs.addTab(self._events, "Rating Actions")
        self._layout.addWidget(self._tabs, stretch=1)

        if hasattr(data_service, "credit_ratings_loaded"):
            data_service.credit_ratings_loaded.connect(self._on_loaded)

    def activate(self, context: dict | None = None):
        context = context or {}
        entity_id = context.get("entity_id")
        if entity_id and hasattr(self.data_service, "run_credit_ratings"):
            self._headline.setText("Loading credit ratings...")
            self.data_service.run_credit_ratings(entity_id)

    @Slot(object)
    def _on_loaded(self, payload: dict):
        payload = payload or {}
        current = payload.get("current") or []
        events = payload.get("events") or []
        if not current and not events:
            self._headline.setText("No credit rating data on file")
            return
        self._headline.setText(payload.get("subject") or "Credit Ratings")

        self._current.setRowCount(len(current))
        for r, c in enumerate(current):
            self._current.setItem(r, 0, cell(c.get("agency")))
            self._current.setItem(r, 1, cell(c.get("current_rating")))
            self._current.setItem(r, 2, cell(c.get("outlook")))
            self._current.setItem(r, 3, cell(c.get("watch_status")))
            ig = c.get("is_investment_grade")
            self._current.setItem(r, 4, cell("IG" if ig else ("HY" if ig is False else "--"),
                                             GREEN if ig else RED))
            self._current.setItem(r, 5, cell(c.get("last_action_date")))

        self._events.setRowCount(len(events))
        for r, e in enumerate(events):
            direction = (e.get("direction") or "").upper()
            color = GREEN if "UPGRADE" in direction else RED if "DOWNGRADE" in direction else TEXT
            self._events.setItem(r, 0, cell(e.get("event_date")))
            self._events.setItem(r, 1, cell(e.get("agency")))
            self._events.setItem(r, 2, cell(e.get("old_rating")))
            self._events.setItem(r, 3, cell(e.get("new_rating")))
            self._events.setItem(r, 4, cell(direction or "--", color))
            self._events.setItem(r, 5, cell(e.get("notches_changed")))
