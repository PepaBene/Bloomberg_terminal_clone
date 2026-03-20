"""Semi-transparent loading overlay with a spinning animation.

Drop this over any widget to indicate an asynchronous operation is in
progress.  Call :meth:`show` / :meth:`hide` to toggle visibility.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_OVERLAY_BG = QColor(13, 13, 26, 180)  # semi-transparent dark
_SPINNER_COLOR = QColor("#FFA500")
_TEXT_COLOR = QColor("#D4D4D4")
_SPINNER_RADIUS = 28
_DOT_COUNT = 10
_DOT_RADIUS = 4


class LoadingOverlay(QWidget):
    """A semi-transparent overlay with a spinning dot animation.

    Usage::

        overlay = LoadingOverlay(parent_widget)
        overlay.show_message("Loading data...")
        # ... later ...
        overlay.hide()

    The overlay automatically resizes to cover its parent widget.
    """

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setVisible(False)

        self._angle = 0.0
        self._message = "Loading..."

        self._timer = QTimer(self)
        self._timer.setInterval(50)  # ~20 fps
        self._timer.timeout.connect(self._tick)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_message(self, message: str = "Loading...") -> None:
        """Show the overlay with the given *message*."""
        self._message = message
        self._resize_to_parent()
        self.setVisible(True)
        self.raise_()
        self._timer.start()

    def hide(self) -> None:
        """Hide the overlay and stop the animation."""
        self._timer.stop()
        self.setVisible(False)

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Darkened background
        painter.fillRect(self.rect(), _OVERLAY_BG)

        cx = self.width() / 2
        cy = self.height() / 2

        # Spinning dots
        for i in range(_DOT_COUNT):
            angle_rad = math.radians(self._angle + i * (360 / _DOT_COUNT))
            x = cx + _SPINNER_RADIUS * math.cos(angle_rad)
            y = cy + _SPINNER_RADIUS * math.sin(angle_rad)

            # Fade dots -- the "leading" dot is brightest
            alpha = int(255 * (1.0 - i / _DOT_COUNT))
            color = QColor(_SPINNER_COLOR)
            color.setAlpha(alpha)
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)

            radius = _DOT_RADIUS * (1.0 - 0.3 * (i / _DOT_COUNT))
            painter.drawEllipse(QPointF(x, y), radius, radius)

        # Message text below the spinner
        painter.setPen(QPen(_TEXT_COLOR))
        font = QFont("Consolas", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        painter.setFont(font)
        text_rect = QRectF(0, cy + _SPINNER_RADIUS + 16, self.width(), 30)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, self._message)

        painter.end()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _tick(self) -> None:
        self._angle = (self._angle + 12) % 360
        self.update()

    def _resize_to_parent(self) -> None:
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.rect())

    def resizeEvent(self, event) -> None:
        self._resize_to_parent()
        super().resizeEvent(event)

    def showEvent(self, event) -> None:
        self._resize_to_parent()
        super().showEvent(event)
