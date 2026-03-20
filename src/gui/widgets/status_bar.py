"""Bottom status bar for the Bloomberg Terminal GUI.

Displays connection status, current security context, and a real-time
clock -- all in a compact, Bloomberg-style horizontal bar.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

# ---------------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------------
_STATUS_BAR_STYLE = """
QWidget#StatusBarContainer {
    background-color: #0D0D1A;
    border-top: 1px solid #333344;
    padding: 0px;
    min-height: 24px;
    max-height: 28px;
}
QLabel {
    font-family: "Consolas", "Courier New", monospace;
    font-size: 11px;
    padding: 2px 6px;
}
"""


class StatusBar(QWidget):
    """Custom status bar with connection indicator, security context, and clock.

    Unlike the built-in ``QStatusBar``, this widget provides fixed zones
    (left / center / right) with Bloomberg-style formatting.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("StatusBarContainer")
        self._build_ui()
        self._start_clock()
        self.setStyleSheet(_STATUS_BAR_STYLE)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(0)

        mono = QFont("Consolas", 10)
        mono.setStyleHint(QFont.StyleHint.Monospace)

        # -- Left: connection indicator ------------------------------------
        self._conn_dot = QLabel("\u25CF")  # filled circle
        self._conn_dot.setFont(mono)
        self._conn_dot.setFixedWidth(18)
        self._conn_dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._conn_dot)

        self._conn_label = QLabel("PostgreSQL")
        self._conn_label.setFont(mono)
        self._conn_label.setStyleSheet("color: #999999;")
        layout.addWidget(self._conn_label)

        # Spacer
        layout.addStretch(1)

        # -- Center: security context --------------------------------------
        self._security_label = QLabel("No security selected")
        self._security_label.setFont(mono)
        self._security_label.setStyleSheet("color: #888888;")
        self._security_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._security_label)

        # Spacer
        layout.addStretch(1)

        # -- Right: clock --------------------------------------------------
        self._clock_label = QLabel("00:00:00")
        self._clock_label.setFont(mono)
        self._clock_label.setStyleSheet("color: #FFA500; font-weight: bold;")
        self._clock_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(self._clock_label)

        # Start in disconnected state.
        self.set_connected(False)

    # ------------------------------------------------------------------
    # Clock
    # ------------------------------------------------------------------

    def _start_clock(self) -> None:
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._update_clock)
        self._timer.start()
        self._update_clock()

    @Slot()
    def _update_clock(self) -> None:
        from datetime import datetime

        now = datetime.now()
        self._clock_label.setText(now.strftime("%H:%M:%S"))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_connected(self, connected: bool) -> None:
        """Update the connection indicator dot and label."""
        if connected:
            self._conn_dot.setStyleSheet("color: #00C805;")  # green
            self._conn_label.setText("PostgreSQL  Connected")
            self._conn_label.setStyleSheet("color: #00C805;")
        else:
            self._conn_dot.setStyleSheet("color: #FF3333;")  # red
            self._conn_label.setText("PostgreSQL  Disconnected")
            self._conn_label.setStyleSheet("color: #FF3333;")

    def set_security_context(self, ticker: str = "", name: str = "") -> None:
        """Update the center security context label.

        Parameters
        ----------
        ticker:
            Short identifier, e.g. ``"AAPL US Equity"``.
        name:
            Full entity name, e.g. ``"Apple Inc."``.
        """
        if ticker:
            display = f"{ticker}"
            if name:
                display += f" - {name}"
            self._security_label.setText(display)
            self._security_label.setStyleSheet("color: #FFA500; font-weight: bold;")
        else:
            self._security_label.setText("No security selected")
            self._security_label.setStyleSheet("color: #888888;")

    def set_message(self, text: str, timeout_ms: int = 5000) -> None:
        """Temporarily show a message in the security-context area.

        The previous context is restored after *timeout_ms* milliseconds.
        """
        prev_text = self._security_label.text()
        prev_style = self._security_label.styleSheet()
        self._security_label.setText(text)
        self._security_label.setStyleSheet("color: #FFFF00;")

        QTimer.singleShot(
            timeout_ms,
            lambda: (
                self._security_label.setText(prev_text),
                self._security_label.setStyleSheet(prev_style),
            ),
        )
