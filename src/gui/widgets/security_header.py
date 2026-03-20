"""Security / entity header bar widget.

Displays the current security context in a horizontal bar:
ticker (large, orange), full name, last price with change indicators,
and an asset-class badge.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

# ---------------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------------
_HEADER_STYLE = """
QWidget#SecurityHeader {
    background-color: #111122;
    border-bottom: 2px solid #FFA500;
    padding: 0px;
    min-height: 36px;
}
"""

_BADGE_STYLE = """
QLabel#AssetBadge {{
    background-color: {bg};
    color: {fg};
    font-family: "Consolas", "Courier New", monospace;
    font-size: 10px;
    font-weight: bold;
    padding: 2px 8px;
    border-radius: 3px;
}}
"""

_BADGE_COLORS: dict[str, tuple[str, str]] = {
    "equity": ("#1A3D1A", "#00C805"),
    "corp bond": ("#3D2E1A", "#FFA500"),
    "govt bond": ("#1A2E3D", "#5599FF"),
    "index": ("#2E1A3D", "#BB88FF"),
    "fx": ("#3D1A1A", "#FF5555"),
    "commodity": ("#3D3D1A", "#CCCC00"),
    "fund": ("#1A3D3D", "#00CCCC"),
}


class SecurityHeader(QWidget):
    """Horizontal bar showing the current security context.

    Designed to sit at the top of any security-centric panel (DES, FA,
    GP, etc.).  Call :meth:`set_security` to update all fields at once.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("SecurityHeader")
        self._build_ui()
        self.setStyleSheet(_HEADER_STYLE)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(12)

        # Ticker (large, orange, bold)
        self._ticker_label = QLabel("")
        ticker_font = QFont("Consolas", 18, QFont.Weight.Bold)
        ticker_font.setStyleHint(QFont.StyleHint.Monospace)
        self._ticker_label.setFont(ticker_font)
        self._ticker_label.setStyleSheet("color: #FFA500; background: transparent;")
        layout.addWidget(self._ticker_label)

        # Full name
        self._name_label = QLabel("")
        name_font = QFont("Consolas", 13)
        name_font.setStyleHint(QFont.StyleHint.Monospace)
        self._name_label.setFont(name_font)
        self._name_label.setStyleSheet("color: #AAAAAA; background: transparent;")
        layout.addWidget(self._name_label)

        layout.addStretch(1)

        # Last price
        self._price_label = QLabel("")
        price_font = QFont("Consolas", 16, QFont.Weight.Bold)
        price_font.setStyleHint(QFont.StyleHint.Monospace)
        self._price_label.setFont(price_font)
        self._price_label.setStyleSheet("color: #FFFFFF; background: transparent;")
        self._price_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._price_label)

        # Change / percent change
        self._change_label = QLabel("")
        change_font = QFont("Consolas", 12)
        change_font.setStyleHint(QFont.StyleHint.Monospace)
        self._change_label.setFont(change_font)
        self._change_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._change_label)

        # Asset class badge
        self._badge_label = QLabel("")
        self._badge_label.setObjectName("AssetBadge")
        self._badge_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._badge_label)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_security(
        self,
        ticker: str = "",
        name: str = "",
        last_price: float | None = None,
        change: float | None = None,
        pct_change: float | None = None,
        asset_class: str = "",
    ) -> None:
        """Update all header fields.

        Parameters
        ----------
        ticker:
            Short identifier, e.g. ``"AAPL US"``.
        name:
            Full entity name, e.g. ``"Apple Inc."``.
        last_price:
            Last traded price.
        change:
            Absolute price change.
        pct_change:
            Percent change (already multiplied by 100).
        asset_class:
            E.g. ``"Equity"``, ``"Corp Bond"``, ``"Index"``.
        """
        self._ticker_label.setText(ticker)
        self._name_label.setText(name)

        # Price
        if last_price is not None:
            self._price_label.setText(f"{last_price:,.2f}")
        else:
            self._price_label.setText("")

        # Change
        if change is not None and pct_change is not None:
            sign = "+" if change >= 0 else ""
            color = "#00C805" if change >= 0 else "#FF3333"
            arrow = "\u25B2" if change > 0 else ("\u25BC" if change < 0 else " ")
            self._change_label.setText(f"{arrow} {sign}{change:,.2f}  ({sign}{pct_change:.2f}%)")
            self._change_label.setStyleSheet(f"color: {color}; background: transparent;")
        elif change is not None:
            sign = "+" if change >= 0 else ""
            color = "#00C805" if change >= 0 else "#FF3333"
            self._change_label.setText(f"{sign}{change:,.2f}")
            self._change_label.setStyleSheet(f"color: {color}; background: transparent;")
        else:
            self._change_label.setText("")

        # Badge
        if asset_class:
            key = asset_class.lower().strip()
            bg, fg = _BADGE_COLORS.get(key, ("#1A1A2E", "#999999"))
            self._badge_label.setText(asset_class)
            self._badge_label.setStyleSheet(
                _BADGE_STYLE.format(bg=bg, fg=fg)
            )
            self._badge_label.setVisible(True)
        else:
            self._badge_label.setVisible(False)

    def clear(self) -> None:
        """Reset the header to its empty state."""
        self.set_security()
