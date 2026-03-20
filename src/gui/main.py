"""Bloomberg Data Fabric Terminal -- Desktop Application.

This is the main entry point for the Bloomberg Terminal GUI.  It wires
together the core services (async bridge, data service, application state)
and the main window, then enters the Qt event loop.

Launch
------
    python -m src.gui.main          # as module
    bloomberg-terminal              # via setuptools entry-point
"""

from __future__ import annotations

import logging
import sys
import traceback

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Logging setup -- configure once, early, before any library imports that
# might create loggers with default handlers.
# ---------------------------------------------------------------------------

def _configure_logging() -> None:
    """Set up root logging for the desktop application."""
    log_format = (
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt="%H:%M:%S",
    )
    # Quieten noisy third-party loggers.
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("PySide6").setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------

def _check_dependencies() -> bool:
    """Return *True* if all required GUI dependencies are importable.

    On failure a user-friendly message is printed to stderr and the
    function returns *False*.
    """
    missing: list[str] = []

    try:
        import PySide6  # noqa: F401
    except ImportError:
        missing.append("PySide6 (install with: pip install PySide6>=6.6.0)")

    if missing:
        sys.stderr.write(
            "\n[Bloomberg Terminal] Missing required dependencies:\n"
        )
        for dep in missing:
            sys.stderr.write(f"  - {dep}\n")
        sys.stderr.write(
            "\nInstall them with:\n"
            "  pip install -e '.[gui]'\n\n"
        )
        return False
    return True


# ---------------------------------------------------------------------------
# Fatal-error dialog (shown when the app cannot start)
# ---------------------------------------------------------------------------

def _fatal_error(title: str, message: str, detail: str = "") -> None:
    """Show a blocking error dialog or fall back to stderr.

    This is used when something goes wrong *after* QApplication exists
    but before the main window is visible.
    """
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox

        # Ensure we have a QApplication to drive the dialog.
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle(title)
        box.setText(message)
        if detail:
            box.setDetailedText(detail)
        box.exec()
    except Exception:
        # If even the dialog fails, dump to stderr.
        sys.stderr.write(f"\n[FATAL] {title}\n{message}\n")
        if detail:
            sys.stderr.write(f"{detail}\n")


# ---------------------------------------------------------------------------
# Application bootstrap
# ---------------------------------------------------------------------------

_ASYNC_WORKER_READY_TIMEOUT = 5.0  # seconds


def main() -> None:
    """Entry-point for the Bloomberg Terminal desktop application."""

    # 1. Logging --------------------------------------------------------
    _configure_logging()
    logger.info("Bloomberg Data Fabric Terminal starting...")

    # 2. Dependency gate ------------------------------------------------
    if not _check_dependencies():
        sys.exit(1)

    # 3. Create QApplication -------------------------------------------
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QIcon

    app = QApplication(sys.argv)
    app.setApplicationName("Bloomberg Data Fabric Terminal")
    app.setOrganizationName("Bloomberg")
    app.setStyle("Fusion")

    # 4. Apply dark theme (stylesheet + palette) -----------------------
    try:
        from src.gui.core.theme import get_stylesheet, get_palette

        app.setStyleSheet(get_stylesheet())
        app.setPalette(get_palette())
    except Exception:
        logger.warning(
            "Could not apply Bloomberg theme -- falling back to defaults.",
            exc_info=True,
        )

    # 5. Start async worker (background event-loop thread) -------------
    try:
        from src.gui.core.async_bridge import AsyncWorker

        worker = AsyncWorker()
        worker.start()

        if not worker.wait_ready(timeout=_ASYNC_WORKER_READY_TIMEOUT):
            _fatal_error(
                "Startup Error",
                "The background async worker did not become ready in time.",
                "The asyncio event loop failed to start within "
                f"{_ASYNC_WORKER_READY_TIMEOUT} seconds.",
            )
            sys.exit(1)

        logger.info("Async worker started (loop running).")
    except Exception as exc:
        _fatal_error(
            "Startup Error",
            "Failed to start the background async worker.",
            traceback.format_exc(),
        )
        sys.exit(1)

    # 6. Initialise core services --------------------------------------
    try:
        from src.gui.core.data_service import DataService
        from src.gui.core.state import AppState

        data_service = DataService(worker)
        app_state = AppState()

        logger.info("Core services initialised.")
    except Exception as exc:
        _fatal_error(
            "Startup Error",
            "Failed to initialise application services.",
            traceback.format_exc(),
        )
        worker.stop()
        sys.exit(1)

    # 7. Register with App singleton -----------------------------------
    from src.gui.app import App

    ctx = App.instance()
    ctx.worker = worker
    ctx.data_service = data_service
    ctx.app_state = app_state

    # 8. Create and show main window -----------------------------------
    try:
        from src.gui.windows.main_window import MainWindow

        window = MainWindow(data_service, app_state)
        ctx.main_window = window

        window.showMaximized()
        logger.info("Main window shown -- entering event loop.")
    except Exception as exc:
        _fatal_error(
            "Startup Error",
            "Failed to create the main application window.",
            traceback.format_exc(),
        )
        worker.stop()
        sys.exit(1)

    # 9. Run event loop ------------------------------------------------
    exit_code = app.exec()

    # 10. Cleanup ------------------------------------------------------
    logger.info("Event loop exited (code=%d). Cleaning up...", exit_code)
    worker.stop()
    logger.info("Shutdown complete.")

    sys.exit(exit_code)


# Allow ``python -m src.gui.main`` invocation.
if __name__ == "__main__":
    main()
