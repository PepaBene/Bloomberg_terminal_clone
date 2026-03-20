"""Key-value display panel for entity / security details.

Renders structured data as a dense grid of label-value pairs grouped
by section -- matching the Bloomberg terminal's compact information
density.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------------------
# Style constants
# ---------------------------------------------------------------------------
_SECTION_HEADER_STYLE = (
    "color: #FFA500; font-family: 'Consolas', monospace; font-size: 12px; "
    "font-weight: bold; border-bottom: 1px solid #333344; padding: 4px 0 2px 0; "
    "background: transparent;"
)
_LABEL_STYLE = (
    "color: #777788; font-family: 'Consolas', monospace; font-size: 11px; "
    "padding: 1px 6px 1px 0; background: transparent;"
)
_VALUE_STYLE = (
    "color: #D4D4D4; font-family: 'Consolas', monospace; font-size: 11px; "
    "padding: 1px 0; background: transparent;"
)
_CONTAINER_STYLE = """
QWidget#KVPanelInner {
    background-color: #0D0D1A;
}
QScrollArea {
    background-color: #0D0D1A;
    border: none;
}
"""


class KVPanel(QWidget):
    """Compact key-value display with grouped sections.

    Usage::

        panel = KVPanel()
        panel.set_data({
            "General": {"Legal Name": "Apple Inc.", "Status": "ACTIVE"},
            "Identifiers": {"ISIN": "US0378331005", "FIGI": "BBG000B9XRY4"},
        })
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._build_ui()
        self.setStyleSheet(_CONTAINER_STYLE)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        outer.addWidget(self._scroll)

        self._inner = QWidget()
        self._inner.setObjectName("KVPanelInner")
        self._inner_layout = QVBoxLayout(self._inner)
        self._inner_layout.setContentsMargins(10, 6, 10, 6)
        self._inner_layout.setSpacing(2)
        self._inner_layout.addStretch(1)

        self._scroll.setWidget(self._inner)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_data(self, sections: dict[str, dict[str, str]]) -> None:
        """Populate the panel with grouped key-value data.

        Parameters
        ----------
        sections:
            Mapping of section name -> {label: value}.
            Example::

                {
                    "General": {"Legal Name": "Apple Inc.", "Status": "ACTIVE"},
                    "Identifiers": {"ISIN": "US0378331005"},
                }
        """
        self._clear_layout()

        for section_name, pairs in sections.items():
            self._add_section(section_name, pairs)

        self._inner_layout.addStretch(1)

    def clear(self) -> None:
        """Remove all content."""
        self._clear_layout()
        self._inner_layout.addStretch(1)

    def append_section(self, name: str, pairs: dict[str, str]) -> None:
        """Add a single section without clearing existing content.

        If the layout already has a trailing stretch, it is removed first
        so the new section is appended cleanly, then a new stretch is
        added afterward.
        """
        # Remove trailing stretch
        count = self._inner_layout.count()
        if count > 0:
            last = self._inner_layout.itemAt(count - 1)
            if last and last.spacerItem():
                self._inner_layout.removeItem(last)

        self._add_section(name, pairs)
        self._inner_layout.addStretch(1)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _add_section(self, name: str, pairs: dict[str, str]) -> None:
        # Section header
        header = QLabel(name.upper())
        header.setStyleSheet(_SECTION_HEADER_STYLE)
        header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._inner_layout.addWidget(header)

        # Grid of label-value pairs (two columns per pair, support 2 pairs
        # per row for density if there are many fields).
        grid = QGridLayout()
        grid.setContentsMargins(4, 2, 4, 6)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(1)

        items = list(pairs.items())
        # Use two columns of pairs when there are > 6 items.
        use_double = len(items) > 6

        for i, (label, value) in enumerate(items):
            lbl = QLabel(f"{label}:")
            lbl.setStyleSheet(_LABEL_STYLE)
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
            lbl.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)

            val = QLabel(str(value))
            val.setStyleSheet(_VALUE_STYLE)
            val.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
                | Qt.TextInteractionFlag.TextSelectableByKeyboard
            )
            val.setWordWrap(True)
            val.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

            if use_double:
                row = i // 2
                base_col = (i % 2) * 2
            else:
                row = i
                base_col = 0

            grid.addWidget(lbl, row, base_col)
            grid.addWidget(val, row, base_col + 1)

        # Set column stretch so value columns expand
        grid.setColumnStretch(1, 1)
        if use_double:
            grid.setColumnStretch(3, 1)

        self._inner_layout.addLayout(grid)

    def _clear_layout(self) -> None:
        """Recursively remove all items from the inner layout."""
        while self._inner_layout.count():
            item = self._inner_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            elif item.layout() is not None:
                self._clear_child_layout(item.layout())

    @staticmethod
    def _clear_child_layout(layout) -> None:
        """Recursively delete all items in a child layout."""
        while layout.count():
            child = layout.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()
            elif child.layout() is not None:
                KVPanel._clear_child_layout(child.layout())
