"""Bloomberg-style command bar widget.

Provides a prominent text input with autocomplete, a green GO indicator,
and Bloomberg orange focus styling.  Emits ``command_submitted`` when the
user presses Enter and ``text_changed`` on every keystroke for live search.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCompleter,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QWidget,
)

# ---------------------------------------------------------------------------
# Style constants
# ---------------------------------------------------------------------------
_COMMAND_BAR_STYLE = """
QWidget#CommandBarContainer {
    background-color: #1A1A2E;
    border: 2px solid #333344;
    border-radius: 4px;
    padding: 2px;
}
QWidget#CommandBarContainer:focus-within {
    border-color: #FF8C00;
}
QLineEdit#CommandInput {
    background-color: #1A1A2E;
    color: #FFFFFF;
    border: none;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 15px;
    padding: 6px 8px;
    selection-background-color: #FF8C00;
    selection-color: #000000;
}
QLineEdit#CommandInput:focus {
    border: none;
    outline: none;
}
QLabel#GoLabel {
    background-color: #00C805;
    color: #000000;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 13px;
    font-weight: bold;
    padding: 4px 10px;
    border-radius: 3px;
    margin: 2px 4px;
}
"""

_COMPLETER_STYLE = """
QListView {
    background-color: #1A1A2E;
    color: #D4D4D4;
    border: 1px solid #FF8C00;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 13px;
    padding: 2px;
    selection-background-color: #FF8C00;
    selection-color: #000000;
}
"""

# Default command completions (Bloomberg function mnemonics).
_DEFAULT_COMPLETIONS = [
    "DES", "FA", "GP", "GIP", "DVD", "DDIS", "HDS",
    "RELS", "SPLC", "ISSD", "CACS", "CRPR",
    "ECFC", "ECST", "WECO", "ECO",
    "SRCH", "EQS", "SECF",
    "PORT", "DASH",
    "HELP", "EXIT",
]


class CommandBar(QWidget):
    """Bloomberg-style command input with autocomplete and GO indicator.

    Signals
    -------
    command_submitted(str)
        Emitted when the user presses Enter.  The text is stripped and
        upper-cased.
    text_changed(str)
        Emitted on every keystroke (raw text, not upper-cased) so callers
        can provide live search / suggestions.
    """

    command_submitted = Signal(str)
    text_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("CommandBarContainer")
        self._build_ui()
        self._connect_signals()
        self.setStyleSheet(_COMMAND_BAR_STYLE)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Prompt label (Bloomberg-style "1>" prompt)
        self._prompt = QLabel("1>")
        self._prompt.setStyleSheet(
            "color: #FFA500; font-family: 'Consolas', monospace; "
            "font-size: 15px; font-weight: bold; padding: 6px 4px 6px 8px; "
            "background: transparent;"
        )
        layout.addWidget(self._prompt)

        # Main input
        self._input = QLineEdit()
        self._input.setObjectName("CommandInput")
        self._input.setPlaceholderText("Enter command (e.g., AAPL DES, GDP ECFC)...")
        self._input.setClearButtonEnabled(True)
        font = QFont("Consolas", 13)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self._input.setFont(font)
        layout.addWidget(self._input, stretch=1)

        # GO indicator
        self._go_label = QLabel("GO")
        self._go_label.setObjectName("GoLabel")
        self._go_label.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self._go_label)

        # Completer
        self._completer = QCompleter(_DEFAULT_COMPLETIONS, self)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._completer.popup().setStyleSheet(_COMPLETER_STYLE)
        self._input.setCompleter(self._completer)

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self._input.returnPressed.connect(self._on_return)
        self._input.textChanged.connect(self.text_changed.emit)
        # Clicking the GO label submits too.
        self._go_label.mousePressEvent = lambda _evt: self._on_return()

    def _on_return(self) -> None:
        text = self._input.text().strip()
        if text:
            self.command_submitted.emit(text.upper())
            self._input.clear()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_completions(self, items: list[str]) -> None:
        """Replace the autocomplete word list at runtime."""
        from PySide6.QtCore import QStringListModel

        model = QStringListModel(items, self._completer)
        self._completer.setModel(model)

    def focus_input(self) -> None:
        """Convenience: give keyboard focus to the command input."""
        self._input.setFocus(Qt.FocusReason.OtherFocusReason)

    def set_text(self, text: str) -> None:
        """Set the input text programmatically (e.g., from history)."""
        self._input.setText(text)
