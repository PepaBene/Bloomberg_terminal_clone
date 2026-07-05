"""HELP -- command reference panel listing every terminal mnemonic."""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QLabel

from ._common import TEXT_DIM, FONT, cell, header_label_style, make_table
from .base_panel import BasePanel

logger = logging.getLogger(__name__)

# Mnemonic -> human description (grouped logically when rendered).
_COMMANDS: list[tuple[str, str]] = [
    ("DES", "Security description / overview"),
    ("FA", "Financial analysis (income / balance / cash flow)"),
    ("GP", "Price chart"),
    ("GIP", "Intraday price"),
    ("OWN / HDS", "Ownership: institutions & insiders"),
    ("SI", "Short interest"),
    ("DVD", "Dividends"),
    ("CACS", "Corporate actions"),
    ("DDIS", "Debt maturity profile"),
    ("CRPR", "Credit ratings & rating actions"),
    ("ISSD", "New (primary-market) issuance"),
    ("RELS / SPLC", "Relationships / supply chain"),
    ("ESG", "ESG scores & controversies"),
    ("RV", "Relative value vs peers"),
    ("QUAL", "Data quality"),
    ("ECFC / ECO / ECST / WECO", "Economics & macro"),
    ("ANLY", "Financial analytics"),
    ("VAL", "Valuation (DCF / WACC)"),
    ("SCOR", "Scoring models (Piotroski / Altman / Beneish)"),
    ("EQS", "Equity screening"),
    ("RISK", "Risk analytics"),
    ("FLOW", "Fund flows"),
    ("QANT", "Quant analytics"),
    ("SCEN", "Scenario & sensitivity"),
    ("PORT", "Portfolios"),
    ("SMRT", "Smart money: follow notable investors / insiders / politicians"),
    ("MODL", "Automatic model builder (economic/market/industry/corporate/company)"),
    ("STRC", "Complex financial structure analysis"),
    ("SRCH / SECF", "Search / security finder"),
    ("RESO", "Entity resolution queue"),
    ("DASH", "Dashboard"),
]


class HelpPanel(BasePanel):
    """HELP -- terminal command reference."""

    panel_name = "HELP"
    panel_title = "HELP - Commands"

    def __init__(self, data_service, app_state, parent=None):
        super().__init__(data_service, app_state, parent)

        header = QLabel("COMMAND REFERENCE")
        header.setStyleSheet(header_label_style())
        self._layout.addWidget(header)

        hint = QLabel("Type a ticker then a mnemonic, e.g.  AAPL FA  ·  F CRPR  ·  AAPL SMRT")
        hint.setStyleSheet(f"color: {TEXT_DIM}; font-family: {FONT}; font-size: 11px;")
        self._layout.addWidget(hint)

        table = make_table(["Command", "Description"])
        table.setRowCount(len(_COMMANDS))
        for r, (mnem, desc) in enumerate(_COMMANDS):
            table.setItem(r, 0, cell(mnem))
            table.setItem(r, 1, cell(desc))
        self._layout.addWidget(table, stretch=1)

    def activate(self, context: dict | None = None):
        pass
