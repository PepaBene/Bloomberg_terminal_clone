"""Application singleton for global access to services.

The ``App`` singleton provides a well-known access point for any widget or
panel that needs to reach the core services (data service, application state,
async worker) without requiring explicit dependency injection through every
constructor in the widget tree.

Usage::

    from src.gui.app import App

    # Read current state
    security = App.instance().app_state.current_security

    # Submit an async task
    future = App.instance().worker.submit(some_coroutine())

    # Access the data service
    App.instance().data_service.search_securities("AAPL")

The singleton is populated during application startup in ``main.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.gui.core.async_bridge import AsyncWorker
    from src.gui.core.data_service import DataService
    from src.gui.core.state import AppState
    from src.gui.windows.main_window import MainWindow


class App:
    """Global application context -- singleton.

    Attributes
    ----------
    worker : AsyncWorker | None
        Background thread that owns the asyncio event loop.
    data_service : DataService | None
        High-level API for querying the Data Fabric backend.
    app_state : AppState | None
        Observable application state (selected security, entity, etc.).
    main_window : MainWindow | None
        Reference to the top-level ``QMainWindow``.
    """

    _instance: App | None = None

    def __init__(self) -> None:
        self.worker: AsyncWorker | None = None
        self.data_service: DataService | None = None
        self.app_state: AppState | None = None
        self.main_window: MainWindow | None = None

    # ------------------------------------------------------------------
    # Singleton accessor
    # ------------------------------------------------------------------

    @classmethod
    def instance(cls) -> App:
        """Return the single ``App`` instance, creating it on first call."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Discard the singleton -- mainly useful for testing."""
        cls._instance = None

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @property
    def is_ready(self) -> bool:
        """Return ``True`` when all core services have been initialised."""
        return (
            self.worker is not None
            and self.data_service is not None
            and self.app_state is not None
            and self.main_window is not None
        )
