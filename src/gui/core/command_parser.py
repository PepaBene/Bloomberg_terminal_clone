"""Bloomberg-style command parser for the terminal command bar.

The Bloomberg Terminal uses a terse command language: a ticker followed by
a panel mnemonic, e.g. ``AAPL DES`` opens the Description panel for Apple,
``FA`` opens Financial Analysis for the currently loaded security, and a
bare string like ``MSFT`` is treated as a search query.

Public API
----------
- ``parse_command(text) -> ParsedCommand``
- ``PANEL_CODES`` -- mapping of mnemonic -> panel name
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ======================================================================
# Panel code registry
# ======================================================================

PANEL_CODES: dict[str, str] = {
    "DES":  "description",
    "FA":   "financials",
    "GP":   "price_chart",
    "OWN":  "ownership",
    "ERN":  "estimates",
    "ESG":  "esg",
    "CACS": "corporate_actions",
    "SPLC": "relationships",
    "ECFC": "macro",
    "RV":   "relative_value",
    "SI":   "short_interest",
    "TREE": "hierarchy",
    "QUAL": "quality",
    # Pillar 2: Analytics Engines
    "ANLY": "analytics",
    "VAL":  "valuation",
    "SCOR": "scores",
    "EQS":  "equity_screen",
    "RISK": "risk",
    "FLOW": "flows",
    "QANT": "quant",
    "SCEN": "scenario",
}

# Reverse lookup: panel name -> mnemonic (useful for status display).
PANEL_NAMES_TO_CODES: dict[str, str] = {v: k for k, v in PANEL_CODES.items()}

# Asset-class hints that can optionally follow a ticker to disambiguate.
ASSET_CLASS_TOKENS: dict[str, str] = {
    "EQUITY": "Equity",
    "EQ":     "Equity",
    "BOND":   "Bond",
    "FI":     "Bond",
    "COMDTY": "Commodity",
    "INDEX":  "Index",
    "GOVT":   "Government",
    "CORP":   "Corporate",
    "CURNCY": "Currency",
    "PFD":    "Preferred",
}

# ======================================================================
# ParsedCommand data class
# ======================================================================


@dataclass
class ParsedCommand:
    """Result of parsing a Bloomberg-style command string.

    Attributes
    ----------
    query:
        The search query portion (ticker, name, or keyword).  Empty string
        if no search query was present (e.g. a bare panel code).
    panel:
        The panel name to open (value from ``PANEL_CODES``), or ``None`` if
        the command is a pure search.
    asset_class:
        Optional asset-class filter (``"Equity"``, ``"Bond"``, etc.).
    filters:
        Additional key=value filters extracted from the command.  Reserved
        for future use (e.g. ``AAPL FA Q`` for quarterly view).
    raw:
        The original command string before parsing.
    """

    query: str = ""
    panel: str | None = None
    asset_class: str | None = None
    filters: dict[str, str] = field(default_factory=dict)
    raw: str = ""


# ======================================================================
# Parser
# ======================================================================

# Pre-compiled pattern: tokens are whitespace-delimited uppercase words,
# digits, or combinations like "US0378331005".
_TOKEN_RE = re.compile(r"\S+")


def parse_command(text: str) -> ParsedCommand:
    """Parse a Bloomberg-style command string.

    Examples
    --------
    >>> parse_command("AAPL").query
    'AAPL'
    >>> parse_command("AAPL DES").panel
    'description'
    >>> parse_command("AAPL DES").query
    'AAPL'
    >>> parse_command("FA").panel
    'financials'
    >>> parse_command("FA").query
    ''
    >>> parse_command("AAPL EQUITY FA").asset_class
    'Equity'
    >>> parse_command("Apple Inc").query
    'Apple Inc'
    """
    result = ParsedCommand(raw=text.strip())

    if not text or not text.strip():
        return result

    tokens = _TOKEN_RE.findall(text.strip())
    upper_tokens = [t.upper() for t in tokens]

    # -- Pass 1: Identify and extract panel codes ----------------------
    panel_idx: int | None = None
    for i, tok in enumerate(upper_tokens):
        if tok in PANEL_CODES:
            result.panel = PANEL_CODES[tok]
            panel_idx = i
            break

    # -- Pass 2: Identify and extract asset-class tokens ---------------
    asset_idx: int | None = None
    for i, tok in enumerate(upper_tokens):
        if i == panel_idx:
            continue
        if tok in ASSET_CLASS_TOKENS:
            result.asset_class = ASSET_CLASS_TOKENS[tok]
            asset_idx = i
            break

    # -- Pass 3: Everything else is the search query -------------------
    query_parts: list[str] = []
    for i, tok in enumerate(tokens):
        if i == panel_idx or i == asset_idx:
            continue
        query_parts.append(tok)

    result.query = " ".join(query_parts)

    return result
