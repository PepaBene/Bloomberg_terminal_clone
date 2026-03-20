"""Bridge between Qt's synchronous event loop and asyncio.

Qt requires all UI operations to happen on the main thread, while database
queries run asynchronously via SQLAlchemy's asyncpg driver.  This module
provides an AsyncWorker that owns a dedicated asyncio event loop running on
a background QThread so coroutines can be submitted from the GUI thread and
their results delivered back through Qt signals / concurrent.futures.Future.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from concurrent.futures import Future
from typing import Any, Coroutine

from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)


class AsyncWorker(QThread):
    """Runs a dedicated asyncio event loop in a background QThread.

    Usage::

        worker = AsyncWorker()
        worker.start()
        future = worker.submit(some_async_function())
        future.add_done_callback(lambda f: print(f.result()))
        # ... eventually ...
        worker.stop()
    """

    # Emitted when an unhandled exception surfaces from any submitted coro.
    error_occurred = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.loop: asyncio.AbstractEventLoop | None = None
        # threading.Event (not asyncio.Event) because the waiter is the
        # main/GUI thread and the setter is this background thread.
        self._ready = threading.Event()

    # ------------------------------------------------------------------
    # QThread entry-point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Thread entry-point -- creates and runs the asyncio event loop."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        logger.debug("AsyncWorker: event loop created on thread %s", threading.current_thread().name)
        self._ready.set()
        try:
            self.loop.run_forever()
        finally:
            # Drain pending tasks before closing.
            pending = asyncio.all_tasks(self.loop)
            if pending:
                self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            self.loop.close()
            logger.debug("AsyncWorker: event loop closed.")

    # ------------------------------------------------------------------
    # Public API (called from the GUI / main thread)
    # ------------------------------------------------------------------

    def wait_ready(self, timeout: float = 5.0) -> bool:
        """Block (main thread) until the background loop is running.

        Returns ``True`` if the loop became ready within *timeout* seconds.
        """
        return self._ready.wait(timeout)

    def submit(self, coro: Coroutine[Any, Any, Any]) -> Future:
        """Schedule *coro* on the background loop.

        Returns a :class:`concurrent.futures.Future` that will hold the
        coroutine result (or exception) once it completes.  The caller can
        attach ``add_done_callback`` to relay the result back to Qt signals.

        Raises ``RuntimeError`` if the worker is not running.
        """
        if self.loop is None or not self.loop.is_running():
            raise RuntimeError("AsyncWorker event loop is not running. Call start() first.")
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def stop(self, timeout_ms: int = 5000) -> None:
        """Gracefully stop the event loop and wait for the thread to exit.

        Parameters
        ----------
        timeout_ms:
            Maximum time in milliseconds to wait for the thread to finish.
        """
        if self.loop is not None and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        self.wait(timeout_ms)
        logger.debug("AsyncWorker: thread joined (finished=%s).", self.isFinished())
