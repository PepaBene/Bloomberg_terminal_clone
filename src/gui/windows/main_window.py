"""Main application window for the Bloomberg Data Fabric Terminal.

Provides the top-level QMainWindow with a Bloomberg-style command bar,
panel-switching via QStackedWidget, a custom status bar, and menu/shortcut
navigation for all major functions (DES, FA, GP, DASH, etc.).
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QAction, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.gui.widgets.command_bar import CommandBar
from src.gui.widgets.status_bar import StatusBar

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global application stylesheet (dark Bloomberg theme)
# ---------------------------------------------------------------------------
_APP_STYLE = """
/* ----- Global defaults -------------------------------------------------- */
QMainWindow {
    background-color: #0D0D1A;
}
QWidget {
    background-color: #0D0D1A;
    color: #D4D4D4;
    font-family: "Consolas", "Courier New", monospace;
}

/* ----- Menu bar --------------------------------------------------------- */
QMenuBar {
    background-color: #111122;
    color: #999999;
    border-bottom: 1px solid #333344;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 11px;
    padding: 2px 0;
}
QMenuBar::item {
    padding: 4px 10px;
    background: transparent;
}
QMenuBar::item:selected {
    background-color: #1A1A2E;
    color: #FFA500;
}
QMenuBar::item:pressed {
    background-color: #FF8C00;
    color: #000000;
}

/* ----- Menus ------------------------------------------------------------ */
QMenu {
    background-color: #1A1A2E;
    color: #D4D4D4;
    border: 1px solid #333344;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 11px;
    padding: 4px 0;
}
QMenu::item {
    padding: 5px 24px 5px 12px;
}
QMenu::item:selected {
    background-color: #FF8C00;
    color: #000000;
}
QMenu::separator {
    height: 1px;
    background-color: #333344;
    margin: 4px 8px;
}

/* ----- Scroll bars (global) --------------------------------------------- */
QScrollBar:vertical {
    background-color: #0D0D1A;
    width: 10px;
    border: none;
}
QScrollBar::handle:vertical {
    background-color: #333344;
    min-height: 20px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background-color: #555566;
}
QScrollBar:horizontal {
    background-color: #0D0D1A;
    height: 10px;
    border: none;
}
QScrollBar::handle:horizontal {
    background-color: #333344;
    min-width: 20px;
    border-radius: 4px;
}
QScrollBar::add-line, QScrollBar::sub-line {
    height: 0px;
    width: 0px;
}
QScrollBar::add-page, QScrollBar::sub-page {
    background: none;
}

/* ----- Tooltips --------------------------------------------------------- */
QToolTip {
    background-color: #1A1A2E;
    color: #FFA500;
    border: 1px solid #FFA500;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 11px;
    padding: 4px;
}
"""

# Commands mapped to panel names.  When a command contains one of these
# tokens (either standalone or as the second word after a ticker), the
# main window will attempt to switch to the corresponding panel.
_COMMAND_PANEL_MAP: dict[str, str] = {
    "DASH": "dashboard",
    "DES": "description",
    "FA": "financials",
    "GP": "graph",
    "GIP": "intraday",
    "DVD": "dividends",
    "DDIS": "debt",
    "HDS": "holders",
    "RELS": "relationships",
    "SPLC": "supply_chain",
    "ISSD": "issuance",
    "CACS": "corporate_actions",
    "CRPR": "credit",
    "ECFC": "economic_forecast",
    "ECST": "economic_stats",
    "WECO": "world_economy",
    "ECO": "economics",
    "SRCH": "search",
    "EQS": "equity_screen",
    "SECF": "security_finder",
    "PORT": "portfolio",
    "HELP": "help",
    # Pillar 2: Analytics Engines
    "ANLY": "analytics",
    "VAL": "valuation",
    "SCOR": "scores",
    "RISK": "risk",
    "FLOW": "flows",
    "QANT": "quant",
    "SCEN": "scenario",
    # Financial Analysis Suite
    "SMRT": "smart_money",
    "MODL": "auto_model",
    "STRC": "complex_structure",
}


class MainWindow(QMainWindow):
    """Top-level window for the Bloomberg Data Fabric Terminal.

    Parameters
    ----------
    data_service:
        Application data-service layer providing async data access.
    app_state:
        Shared application state (current security, user prefs, etc.).
    """

    def __init__(self, data_service: Any, app_state: Any):
        super().__init__()
        self.data_service = data_service
        self.app_state = app_state
        self._panels: dict[str, QWidget] = {}

        self._setup_ui()
        self._setup_menu()
        self._setup_shortcuts()
        self._connect_signals()

        logger.info("MainWindow initialized.")

    # ==================================================================
    # UI SETUP
    # ==================================================================

    def _setup_ui(self) -> None:
        self.setWindowTitle("Bloomberg Data Fabric Terminal")
        self.setStyleSheet(_APP_STYLE)
        self.showMaximized()

        # Minimum reasonable size
        self.setMinimumSize(1024, 640)

        # Central container
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # -- Command bar (top) -------------------------------------------
        self._command_bar = CommandBar(self)
        main_layout.addWidget(self._command_bar)

        # -- Panel stack (center) -----------------------------------------
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background-color: #0D0D1A;")

        # Default welcome / empty panel
        self._welcome = self._create_welcome_panel()
        self._stack.addWidget(self._welcome)
        self._panels["welcome"] = self._welcome

        main_layout.addWidget(self._stack, stretch=1)

        # -- Status bar (bottom) ------------------------------------------
        self._status_bar = StatusBar(self)
        main_layout.addWidget(self._status_bar)

    def _create_welcome_panel(self) -> QWidget:
        """Build the default welcome screen shown on startup."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("BLOOMBERG DATA FABRIC")
        title_font = QFont("Consolas", 28, QFont.Weight.Bold)
        title_font.setStyleHint(QFont.StyleHint.Monospace)
        title.setFont(title_font)
        title.setStyleSheet("color: #FFA500; background: transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Terminal")
        sub_font = QFont("Consolas", 16)
        sub_font.setStyleHint(QFont.StyleHint.Monospace)
        subtitle.setFont(sub_font)
        subtitle.setStyleSheet("color: #555566; background: transparent;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        # Spacing
        spacer_label = QLabel("")
        spacer_label.setFixedHeight(24)
        layout.addWidget(spacer_label)

        hint = QLabel("Type a command above to get started\ne.g.  AAPL DES  |  MSFT FA  |  GDP ECFC")
        hint_font = QFont("Consolas", 12)
        hint_font.setStyleHint(QFont.StyleHint.Monospace)
        hint.setFont(hint_font)
        hint.setStyleSheet("color: #444455; background: transparent;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        return panel

    # ==================================================================
    # MENU BAR
    # ==================================================================

    def _setup_menu(self) -> None:
        menu_bar = self.menuBar()

        # -- File menu ----------------------------------------------------
        file_menu = menu_bar.addMenu("&File")

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence("Alt+F4"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # -- View menu ----------------------------------------------------
        view_menu = menu_bar.addMenu("&View")

        self._add_nav_action(view_menu, "&Dashboard", "dashboard", "Ctrl+1")
        view_menu.addSeparator()
        self._add_nav_action(view_menu, "D&ES  - Description", "description", "")
        self._add_nav_action(view_menu, "&FA   - Financial Analysis", "financials", "")
        self._add_nav_action(view_menu, "&GP   - Graph / Price", "graph", "")
        self._add_nav_action(view_menu, "&HDS  - Holders", "holders", "")
        self._add_nav_action(view_menu, "D&VD  - Dividends", "dividends", "")
        self._add_nav_action(view_menu, "&CACS - Corp Actions", "corporate_actions", "")
        view_menu.addSeparator()
        self._add_nav_action(view_menu, "&ECFC - Econ Forecast", "economic_forecast", "")
        self._add_nav_action(view_menu, "EC&ST - Econ Stats", "economic_stats", "")
        view_menu.addSeparator()
        self._add_nav_action(view_menu, "&SRCH - Search", "search", "Ctrl+F")
        self._add_nav_action(view_menu, "S&ECF - Security Finder", "security_finder", "")

        # -- Analytics menu ---------------------------------------------------
        analytics_menu = menu_bar.addMenu("&Analytics")
        self._add_nav_action(analytics_menu, "&ANLY - Financial Analytics", "analytics", "")
        self._add_nav_action(analytics_menu, "&VAL  - Valuation (DCF/WACC)", "valuation", "")
        self._add_nav_action(analytics_menu, "&SCOR - Scoring Models", "scores", "")
        self._add_nav_action(analytics_menu, "&EQS  - Equity Screening", "equity_screen", "")
        self._add_nav_action(analytics_menu, "&RISK - Risk Analytics", "risk", "")
        self._add_nav_action(analytics_menu, "&FLOW - Fund Flows", "flows", "")
        self._add_nav_action(analytics_menu, "&QANT - Quant Analytics", "quant", "")
        self._add_nav_action(analytics_menu, "SC&EN - Scenario Analysis", "scenario", "")

        # -- Help menu ----------------------------------------------------
        help_menu = menu_bar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _add_nav_action(
        self, menu: QMenu, label: str, panel_name: str, shortcut: str
    ) -> QAction:
        action = QAction(label, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(lambda _checked=False, pn=panel_name: self.navigate_to(pn))
        menu.addAction(action)
        return action

    # ==================================================================
    # KEYBOARD SHORTCUTS
    # ==================================================================

    def _setup_shortcuts(self) -> None:
        # Focus command bar
        focus_cmd = QShortcut(QKeySequence("Ctrl+L"), self)
        focus_cmd.activated.connect(self._command_bar.focus_input)

        # Also Escape returns focus to command bar
        esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        esc.activated.connect(self._command_bar.focus_input)

        # F1 = help
        f1 = QShortcut(QKeySequence(Qt.Key.Key_F1), self)
        f1.activated.connect(lambda: self.navigate_to("help"))

    # ==================================================================
    # SIGNAL CONNECTIONS
    # ==================================================================

    def _connect_signals(self) -> None:
        self._command_bar.command_submitted.connect(self.on_command)
        self._command_bar.text_changed.connect(self._on_live_search)

    # ==================================================================
    # COMMAND HANDLING
    # ==================================================================

    @Slot(str)
    def on_command(self, command_text: str) -> None:
        """Handle command bar input.

        Commands are parsed as either:
        - A single function mnemonic: ``DES``, ``FA``, ``SRCH`` ...
        - A security + function: ``AAPL DES``, ``MSFT FA``, ``GDP ECFC`` ...
        - A security alone (navigate to description by default).
        """
        logger.info("Command received: %s", command_text)
        tokens = command_text.strip().upper().split()
        if not tokens:
            return

        panel_name: str | None = None
        security_token: str | None = None

        if len(tokens) == 1:
            # Single token: could be a function or a ticker
            if tokens[0] in _COMMAND_PANEL_MAP:
                panel_name = _COMMAND_PANEL_MAP[tokens[0]]
            else:
                # Treat as a ticker -> default to description panel
                security_token = tokens[0]
                panel_name = "description"
        else:
            # Multi-token: last token is checked as a function, rest is security
            last = tokens[-1]
            if last in _COMMAND_PANEL_MAP:
                panel_name = _COMMAND_PANEL_MAP[last]
                security_token = " ".join(tokens[:-1])
            else:
                # Treat entire string as a search query -> search panel
                security_token = " ".join(tokens)
                panel_name = "search"

        # Update security context if a ticker was provided
        context: dict[str, Any] = {}
        if security_token:
            context["security"] = security_token
            self._status_bar.set_security_context(ticker=security_token)
            if self.app_state is not None:
                try:
                    self.app_state.current_security = security_token
                except AttributeError:
                    pass

        if panel_name:
            self.navigate_to(panel_name, context)
        else:
            self._status_bar.set_message(f"Unknown command: {command_text}", timeout_ms=4000)

    @Slot(str)
    def _on_live_search(self, text: str) -> None:
        """Handle live-search text changes (for autocomplete enrichment)."""
        # Future: query data_service for matching securities / entities
        # and feed results into self._command_bar.set_completions([...])
        pass

    # ==================================================================
    # PANEL NAVIGATION
    # ==================================================================

    def navigate_to(self, panel_name: str, context: dict | None = None) -> None:
        """Switch the central stack to the panel identified by *panel_name*.

        If the panel has not been registered yet, a placeholder is shown
        and a warning is logged.

        Parameters
        ----------
        panel_name:
            Identifier for the panel (e.g. ``"description"``, ``"financials"``).
        context:
            Optional dict of context data passed to the panel's
            ``load_data(context)`` method if it exists.
        """
        logger.debug("navigate_to(%s, context=%s)", panel_name, context)

        if panel_name not in self._panels:
            # Show a "not implemented" placeholder
            placeholder = self._create_placeholder(panel_name)
            self.register_panel(panel_name, placeholder)

        widget = self._panels[panel_name]
        self._stack.setCurrentWidget(widget)

        # Inform the panel about the navigation context
        if context and hasattr(widget, "load_data"):
            try:
                widget.load_data(context)
            except Exception:
                logger.exception("Error calling load_data on panel %s", panel_name)

        self._status_bar.set_message(f"Panel: {panel_name.upper()}", timeout_ms=2000)

    def register_panel(self, name: str, widget: QWidget) -> None:
        """Register a panel widget so it can be navigated to by *name*.

        Parameters
        ----------
        name:
            Unique panel identifier (lowercase, e.g. ``"description"``).
        widget:
            The panel widget to add to the stack.
        """
        if name in self._panels:
            # Replace existing
            old = self._panels[name]
            idx = self._stack.indexOf(old)
            self._stack.removeWidget(old)
            old.deleteLater()

        self._stack.addWidget(widget)
        self._panels[name] = widget
        logger.debug("Panel registered: %s", name)

    def _create_placeholder(self, panel_name: str) -> QWidget:
        """Create a simple placeholder widget for unregistered panels."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label = QLabel(f"{panel_name.upper()}")
        label_font = QFont("Consolas", 20, QFont.Weight.Bold)
        label_font.setStyleHint(QFont.StyleHint.Monospace)
        label.setFont(label_font)
        label.setStyleSheet("color: #FFA500; background: transparent;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        hint = QLabel("Panel not yet implemented")
        hint_font = QFont("Consolas", 12)
        hint_font.setStyleHint(QFont.StyleHint.Monospace)
        hint.setFont(hint_font)
        hint.setStyleSheet("color: #555566; background: transparent;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        return w

    # ==================================================================
    # CONVENIENCE ACCESSORS
    # ==================================================================

    @property
    def command_bar(self) -> CommandBar:
        """Return the command bar widget."""
        return self._command_bar

    @property
    def status_bar_widget(self) -> StatusBar:
        """Return the custom status bar widget (not ``QMainWindow.statusBar``)."""
        return self._status_bar

    @property
    def panel_stack(self) -> QStackedWidget:
        """Return the central QStackedWidget."""
        return self._stack

    # ==================================================================
    # DIALOGS
    # ==================================================================

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Bloomberg Data Fabric Terminal",
            "<p style='font-family: Consolas; color: #FFA500; font-size: 14px;'>"
            "<b>Bloomberg Data Fabric Terminal</b></p>"
            "<p style='font-family: Consolas; font-size: 11px;'>"
            "A financial data platform for reference, entity,<br>"
            "and security master data.<br><br>"
            "Built with PySide6 / Qt 6.<br>"
            "Data: EDGAR, GLEIF, OpenFIGI, FRED, Polygon.io</p>",
        )

    # ==================================================================
    # OVERRIDES
    # ==================================================================

    def closeEvent(self, event) -> None:
        """Clean up on window close."""
        logger.info("MainWindow closing.")
        # Stop the status bar clock timer
        if hasattr(self._status_bar, "_timer"):
            self._status_bar._timer.stop()
        super().closeEvent(event)
