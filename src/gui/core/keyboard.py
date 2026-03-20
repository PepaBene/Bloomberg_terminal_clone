"""Global keyboard shortcut registry for the Bloomberg Terminal GUI.

Centralises all shortcut definitions so they can be changed in one place.
The ``register_shortcuts`` helper binds them to a parent widget (typically
the QMainWindow) and returns a dict of ``QShortcut`` instances keyed by
action name.

Public API
----------
- ``SHORTCUTS``             -- canonical mapping of action name -> key string
- ``register_shortcuts()``  -- bind shortcuts to a widget
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QWidget

# ======================================================================
# Shortcut definitions
# ======================================================================

SHORTCUTS: dict[str, str] = {
    # Navigation & search
    "search":       "Ctrl+F",
    "command_bar":  "F2",
    "go_back":      "Escape",

    # Panel shortcuts (mapped to function keys for Bloomberg feel)
    "dashboard":    "F3",
    "description":  "F4",
    "financials":   "F5",
    "chart":        "F6",
    "ownership":    "F7",
    "estimates":    "F8",
    "esg":          "F9",
    "macro":        "F10",

    # Data actions
    "refresh":      "F12",
    "add_watchlist": "Ctrl+W",

    # Application
    "quit":         "Ctrl+Q",
}


def register_shortcuts(
    parent: QWidget,
    callbacks: dict[str, Callable[[], Any]],
) -> dict[str, QShortcut]:
    """Create ``QShortcut`` objects on *parent* for each entry in *callbacks*.

    Parameters
    ----------
    parent:
        The widget that owns the shortcuts (usually the main window).
    callbacks:
        A mapping of action name (must exist in ``SHORTCUTS``) to a
        zero-argument callable that should fire when the key is pressed.

    Returns
    -------
    dict[str, QShortcut]:
        The created shortcut objects, keyed by action name.  Callers
        rarely need these, but they can be used to enable/disable shortcuts
        dynamically.

    Example
    -------
    ::

        shortcuts = register_shortcuts(main_window, {
            "search":      lambda: command_bar.setFocus(),
            "command_bar": lambda: command_bar.setFocus(),
            "quit":        lambda: QApplication.quit(),
            "financials":  lambda: panel_stack.show_panel("financials"),
        })
    """
    created: dict[str, QShortcut] = {}
    for action, callback in callbacks.items():
        key_string = SHORTCUTS.get(action)
        if key_string is None:
            continue
        shortcut = QShortcut(QKeySequence(key_string), parent)
        shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        shortcut.activated.connect(callback)
        created[action] = shortcut
    return created
