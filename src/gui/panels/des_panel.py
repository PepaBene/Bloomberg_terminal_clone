"""DES -- Entity / Security description panel.

Displays entity and security details in key-value panels with an identifiers
table at the bottom, closely modelled on the Bloomberg DES function.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .base_panel import BasePanel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Theme constants
# ---------------------------------------------------------------------------
_BG = "#0a0e17"
_BG_CARD = "#111827"
_TEXT = "#e2e8f0"
_TEXT_DIM = "#94a3b8"
_ORANGE = "#ff6600"
_GREEN = "#22c55e"
_RED = "#ef4444"
_BORDER = "#1e293b"
_FONT = "Consolas, 'Courier New', monospace"


# ---------------------------------------------------------------------------
# Reusable KV pair row widget
# ---------------------------------------------------------------------------
class _KVRow(QWidget):
    """Single key-value row: fixed-width label on the left, value on the right."""

    def __init__(self, key: str, value: str = "--", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 1, 0, 1)
        layout.setSpacing(8)

        self._key_label = QLabel(key)
        self._key_label.setFixedWidth(180)
        self._key_label.setStyleSheet(
            f"color: {_TEXT_DIM}; font-family: {_FONT}; font-size: 12px;"
        )
        self._val_label = QLabel(value)
        self._val_label.setStyleSheet(
            f"color: {_TEXT}; font-family: {_FONT}; font-size: 12px;"
        )
        self._val_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self._key_label)
        layout.addWidget(self._val_label, stretch=1)

    def set_value(self, value: str):
        self._val_label.setText(value or "--")


# ---------------------------------------------------------------------------
# KV card (a group of KV rows with an optional title)
# ---------------------------------------------------------------------------
class _KVCard(QFrame):
    """Bordered card containing a title and a list of KV rows."""

    def __init__(self, title: str, keys: list[str], parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            _KVCard {{
                background: {_BG_CARD};
                border: 1px solid {_BORDER};
                border-radius: 4px;
            }}
        """)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            QFrame {{
                background: {_BG_CARD};
                border: 1px solid {_BORDER};
                border-radius: 4px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        header = QLabel(title)
        header.setStyleSheet(
            f"color: {_ORANGE}; font-family: {_FONT}; font-size: 12px; "
            f"font-weight: bold; border: none; padding-bottom: 4px;"
        )
        layout.addWidget(header)

        self._rows: dict[str, _KVRow] = {}
        for key in keys:
            row = _KVRow(key)
            self._rows[key] = row
            layout.addWidget(row)

    def set_value(self, key: str, value: str):
        if key in self._rows:
            self._rows[key].set_value(value)

    def set_all(self, mapping: dict[str, str]):
        for k, v in mapping.items():
            self.set_value(k, v)

    def clear_all(self):
        for row in self._rows.values():
            row.set_value("--")


# ---------------------------------------------------------------------------
# DES Panel
# ---------------------------------------------------------------------------
class DESPanel(BasePanel):
    """DES -- entity/security description panel."""

    panel_name = "DES"
    panel_title = "DES - Description"

    # Entity detail keys
    _ENTITY_KEYS = [
        "Legal Name",
        "Entity Type",
        "Status",
        "Country (Inc.)",
        "Domicile",
        "GICS Sector",
        "GICS Industry",
        "SIC Code",
        "Accounting Std",
        "Fiscal Year End",
        "Currency",
        "Source",
    ]

    # Security detail keys
    _SECURITY_KEYS = [
        "Security Name",
        "Security Type",
        "Asset Class",
        "Exchange (MIC)",
        "Currency",
        "Status",
        "Issue Date",
        "Maturity",
        "ISIN",
        "CUSIP",
        "SEDOL",
        "FIGI",
    ]

    def __init__(self, data_service, app_state, parent=None):
        super().__init__(data_service, app_state, parent)

        self.setStyleSheet(f"background: {_BG};")

        # ---- Security header bar ----
        self._header_frame = QFrame()
        self._header_frame.setStyleSheet(
            f"background: {_BG_CARD}; border: 1px solid {_BORDER}; border-radius: 4px;"
        )
        hdr_layout = QHBoxLayout(self._header_frame)
        hdr_layout.setContentsMargins(12, 8, 12, 8)
        hdr_layout.setSpacing(16)

        self._ticker_label = QLabel("--")
        self._ticker_label.setStyleSheet(
            f"color: {_ORANGE}; font-family: {_FONT}; font-size: 20px; "
            f"font-weight: bold; border: none;"
        )
        self._name_label = QLabel("Loading...")
        self._name_label.setStyleSheet(
            f"color: {_TEXT}; font-family: {_FONT}; font-size: 14px; border: none;"
        )
        self._price_label = QLabel("")
        self._price_label.setStyleSheet(
            f"color: {_TEXT}; font-family: {_FONT}; font-size: 16px; "
            f"font-weight: bold; border: none;"
        )
        self._change_label = QLabel("")
        self._change_label.setStyleSheet(
            f"font-family: {_FONT}; font-size: 13px; border: none;"
        )

        hdr_layout.addWidget(self._ticker_label)
        hdr_layout.addWidget(self._name_label, stretch=1)
        hdr_layout.addWidget(self._price_label)
        hdr_layout.addWidget(self._change_label)

        self._layout.addWidget(self._header_frame)

        # ---- Scrollable body ----
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea {{ background: {_BG}; border: none; }}"
        )
        body = QWidget()
        body.setStyleSheet(f"background: {_BG};")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 6, 0, 0)
        body_layout.setSpacing(8)

        # ---- Two-column KV cards ----
        columns = QHBoxLayout()
        columns.setSpacing(8)

        self._entity_card = _KVCard("ENTITY DETAILS", self._ENTITY_KEYS)
        self._security_card = _KVCard("SECURITY DETAILS", self._SECURITY_KEYS)
        columns.addWidget(self._entity_card, stretch=1)
        columns.addWidget(self._security_card, stretch=1)
        body_layout.addLayout(columns)

        # ---- Identifiers table ----
        id_header = QLabel("IDENTIFIERS")
        id_header.setStyleSheet(
            f"color: {_ORANGE}; font-family: {_FONT}; font-size: 12px; "
            f"font-weight: bold; padding-top: 4px;"
        )
        body_layout.addWidget(id_header)

        self._id_table = QTableWidget()
        self._configure_table(
            self._id_table,
            ["Scope", "Type", "Value", "Source", "Primary"],
        )
        self._id_table.setMaximumHeight(220)
        body_layout.addWidget(self._id_table)

        body_layout.addStretch()
        scroll.setWidget(body)
        self._layout.addWidget(scroll, stretch=1)

        # ---- Connect data_service signals ----
        if hasattr(data_service, "entity_loaded"):
            data_service.entity_loaded.connect(self._on_entity_loaded)
        if hasattr(data_service, "security_loaded"):
            data_service.security_loaded.connect(self._on_security_loaded)

        # Internal state
        self._current_entity: dict[str, Any] | None = None
        self._current_security: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # Table helper (same style as dashboard)
    # ------------------------------------------------------------------
    @staticmethod
    def _configure_table(table: QTableWidget, headers: list[str]):
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setStyleSheet(f"""
            QTableWidget {{
                background: {_BG_CARD};
                color: {_TEXT};
                font-family: {_FONT};
                font-size: 12px;
                gridline-color: {_BORDER};
                border: 1px solid {_BORDER};
            }}
            QTableWidget::item {{
                padding: 3px 6px;
            }}
            QTableWidget::item:selected {{
                background: #1e293b;
            }}
            QHeaderView::section {{
                background: {_BG};
                color: {_ORANGE};
                font-family: {_FONT};
                font-size: 11px;
                font-weight: bold;
                border: none;
                border-bottom: 1px solid {_BORDER};
                padding: 4px 6px;
            }}
        """)

    # ------------------------------------------------------------------
    # Panel lifecycle
    # ------------------------------------------------------------------
    def activate(self, context: dict | None = None):
        context = context or {}
        self._entity_card.clear_all()
        self._security_card.clear_all()
        self._id_table.setRowCount(0)
        self._ticker_label.setText("--")
        self._name_label.setText("Loading...")
        self._price_label.setText("")
        self._change_label.setText("")

        security_id = context.get("security_id")
        entity_id = context.get("entity_id")
        ticker = context.get("ticker")

        if security_id and hasattr(self.data_service, "load_security"):
            self.data_service.load_security(security_id)
        elif entity_id and hasattr(self.data_service, "load_entity"):
            self.data_service.load_entity(entity_id)
        elif ticker and hasattr(self.data_service, "load_security_by_ticker"):
            self.data_service.load_security_by_ticker(ticker)

    def deactivate(self):
        self._current_entity = None
        self._current_security = None

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    @Slot(object)
    def _on_entity_loaded(self, entity: dict[str, Any]):
        self._current_entity = entity
        self._populate_entity(entity)
        self._rebuild_identifiers()
        # Also load the primary security for this entity
        eid = entity.get("entity_id")
        if eid and hasattr(self.data_service, "load_primary_security"):
            self.data_service.load_primary_security(eid)

    @Slot(object)
    def _on_security_loaded(self, security: dict[str, Any]):
        self._current_security = security
        self._populate_security(security)
        self._populate_header(security)
        self._rebuild_identifiers()
        # Also load the entity
        eid = security.get("issuer_entity_id")
        if eid and self._current_entity is None:
            if hasattr(self.data_service, "load_entity"):
                self.data_service.load_entity(eid)

    # ------------------------------------------------------------------
    # Populate helpers
    # ------------------------------------------------------------------
    def _populate_entity(self, e: dict[str, Any]):
        self._entity_card.set_all({
            "Legal Name": e.get("legal_name", "--"),
            "Entity Type": e.get("entity_type", "--"),
            "Status": e.get("status", "--"),
            "Country (Inc.)": e.get("incorporation_country", "--"),
            "Domicile": e.get("domicile_country", "--"),
            "GICS Sector": e.get("gics_sector", "--"),
            "GICS Industry": e.get("gics_industry", "--"),
            "SIC Code": e.get("primary_sic", "--"),
            "Accounting Std": e.get("accounting_standard", "--"),
            "Fiscal Year End": e.get("fiscal_year_end", "--"),
            "Currency": e.get("reporting_currency", "--"),
            "Source": e.get("source", "--"),
        })
        # Update header name if no security loaded yet
        if self._current_security is None:
            self._name_label.setText(e.get("legal_name", "--"))

    def _populate_security(self, s: dict[str, Any]):
        # Extract identifier values from the identifiers list
        ids = {
            ident.get("identifier_type", ""): ident.get("identifier_value", "")
            for ident in (s.get("identifiers") or [])
        }
        self._security_card.set_all({
            "Security Name": s.get("name", "--"),
            "Security Type": s.get("security_type", "--"),
            "Asset Class": s.get("asset_class", "--"),
            "Exchange (MIC)": s.get("primary_exchange_mic", "--"),
            "Currency": s.get("primary_currency", "--"),
            "Status": s.get("status", "--"),
            "Issue Date": str(s.get("issue_date", "--")),
            "Maturity": str(s.get("maturity_date", "--")) if s.get("maturity_date") else "--",
            "ISIN": ids.get("ISIN", "--"),
            "CUSIP": ids.get("CUSIP", "--"),
            "SEDOL": ids.get("SEDOL", "--"),
            "FIGI": ids.get("FIGI", "--"),
        })

    def _populate_header(self, s: dict[str, Any]):
        # Find ticker from identifiers
        ids = {
            ident.get("identifier_type", ""): ident.get("identifier_value", "")
            for ident in (s.get("identifiers") or [])
        }
        ticker = ids.get("TICKER") or s.get("short_name") or s.get("name", "--")
        self._ticker_label.setText(ticker)
        self._name_label.setText(s.get("name", "--"))

        price = s.get("last_price") or s.get("close")
        if price is not None:
            self._price_label.setText(f"{price:,.2f}")
            change = s.get("change")
            pct = s.get("change_percent")
            if change is not None:
                sign = "+" if change >= 0 else ""
                color = _GREEN if change >= 0 else _RED
                pct_str = f"  ({sign}{pct:.2f}%)" if pct is not None else ""
                self._change_label.setText(f"{sign}{change:.2f}{pct_str}")
                self._change_label.setStyleSheet(
                    f"color: {color}; font-family: {_FONT}; font-size: 13px; border: none;"
                )

    def _rebuild_identifiers(self):
        """Merge entity + security identifiers into the bottom table."""
        rows: list[tuple[str, str, str, str, str]] = []

        if self._current_entity:
            for ident in self._current_entity.get("identifiers") or []:
                rows.append((
                    "Entity",
                    ident.get("identifier_type", ""),
                    ident.get("identifier_value", ""),
                    ident.get("source", "--"),
                    "Y" if ident.get("is_primary") else "",
                ))

        if self._current_security:
            for ident in self._current_security.get("identifiers") or []:
                rows.append((
                    "Security",
                    ident.get("identifier_type", ""),
                    ident.get("identifier_value", ""),
                    ident.get("source", "--"),
                    "",
                ))

        self._id_table.setRowCount(len(rows))
        for r, (scope, itype, ival, src, prim) in enumerate(rows):
            for c, text in enumerate([scope, itype, ival, src, prim]):
                item = QTableWidgetItem(text)
                item.setForeground(QColor(_TEXT))
                self._id_table.setItem(r, c, item)
