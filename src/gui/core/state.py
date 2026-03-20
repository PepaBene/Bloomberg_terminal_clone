"""Global application state for the Bloomberg Terminal GUI.

``AppState`` is a singleton-style QObject that holds the current user context
(selected security, entity, watchlist, command history) and emits Qt signals
whenever the context changes.  Panels and widgets connect to these signals to
reactively update their displays.

Typical usage in a panel::

    app_state.security_changed.connect(self._on_security_changed)

From a command handler::

    app_state.set_security({"security_id": "...", "name": "AAPL", ...})
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)

# Maximum number of command history entries to keep in memory.
_MAX_HISTORY = 500


class AppState(QObject):
    """Holds current application context and emits signals on changes.

    All data is stored as plain ``dict`` objects (not ORM instances) to
    avoid SQLAlchemy lazy-load issues when accessed from the GUI thread.
    """

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    #: Emitted when the active security changes.  Payload is a dict
    #: representation of the Security row (or ``None`` to clear).
    security_changed = Signal(object)

    #: Emitted when the active entity changes.  Payload is a dict
    #: representation of the Entity row (or ``None`` to clear).
    entity_changed = Signal(object)

    #: Emitted when the watchlist is modified.  Payload is the full
    #: list of watched security_id strings.
    watchlist_changed = Signal(list)

    #: Emitted whenever a command is executed (for status bar / history).
    command_executed = Signal(str)

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)

        # Current selection context
        self.current_security_id: str | None = None
        self.current_entity_id: str | None = None
        self.current_security: dict[str, Any] | None = None
        self.current_entity: dict[str, Any] | None = None

        # Watchlist: ordered list of security_id strings
        self.watchlist: list[str] = []

        # Command history (most recent last)
        self.command_history: list[str] = []

    # ------------------------------------------------------------------
    # Mutators
    # ------------------------------------------------------------------

    def set_security(self, security_data: dict[str, Any] | None) -> None:
        """Set the currently active security and emit *security_changed*.

        Parameters
        ----------
        security_data:
            A plain dict from ``_orm_to_dict(Security(...))`` or ``None``
            to clear the current selection.
        """
        self.current_security = security_data
        self.current_security_id = (
            security_data.get("security_id") if security_data else None
        )
        logger.debug("AppState: security -> %s", self.current_security_id)
        self.security_changed.emit(security_data)

    def set_entity(self, entity_data: dict[str, Any] | None) -> None:
        """Set the currently active entity and emit *entity_changed*.

        Parameters
        ----------
        entity_data:
            A plain dict from ``_orm_to_dict(Entity(...))`` or ``None``
            to clear the current selection.
        """
        self.current_entity = entity_data
        self.current_entity_id = (
            entity_data.get("entity_id") if entity_data else None
        )
        logger.debug("AppState: entity -> %s", self.current_entity_id)
        self.entity_changed.emit(entity_data)

    # ------------------------------------------------------------------
    # Watchlist
    # ------------------------------------------------------------------

    def add_to_watchlist(self, security_id: str) -> None:
        """Add *security_id* to the watchlist if not already present."""
        if security_id and security_id not in self.watchlist:
            self.watchlist.append(security_id)
            logger.debug("AppState: watchlist += %s (total %d)", security_id, len(self.watchlist))
            self.watchlist_changed.emit(list(self.watchlist))

    def remove_from_watchlist(self, security_id: str) -> None:
        """Remove *security_id* from the watchlist."""
        if security_id in self.watchlist:
            self.watchlist.remove(security_id)
            logger.debug("AppState: watchlist -= %s (total %d)", security_id, len(self.watchlist))
            self.watchlist_changed.emit(list(self.watchlist))

    def clear_watchlist(self) -> None:
        """Remove all entries from the watchlist."""
        self.watchlist.clear()
        self.watchlist_changed.emit([])

    # ------------------------------------------------------------------
    # Command history
    # ------------------------------------------------------------------

    def push_command(self, command: str) -> None:
        """Record *command* in history (deduplicating consecutive repeats)."""
        command = command.strip()
        if not command:
            return
        # Avoid duplicating the last entry when the user hammers Enter.
        if self.command_history and self.command_history[-1] == command:
            return
        self.command_history.append(command)
        if len(self.command_history) > _MAX_HISTORY:
            self.command_history = self.command_history[-_MAX_HISTORY:]
        self.command_executed.emit(command)

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Reset all state to defaults (e.g. on logout or workspace reset)."""
        self.set_security(None)
        self.set_entity(None)
        self.clear_watchlist()
        self.command_history.clear()
