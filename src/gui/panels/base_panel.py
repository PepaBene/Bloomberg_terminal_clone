from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Signal


class BasePanel(QWidget):
    """Base class for all Bloomberg-style panels."""
    panel_name = "base"
    panel_title = "Base Panel"

    def __init__(self, data_service, app_state, parent=None):
        super().__init__(parent)
        self.data_service = data_service
        self.app_state = app_state
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(2)

    def activate(self, context: dict = None):
        """Called when panel becomes visible. Override to load data."""
        pass

    def deactivate(self):
        """Called when panel is hidden."""
        pass
