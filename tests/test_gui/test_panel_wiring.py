"""Headless GUI tests: verify every command mnemonic opens a real panel.

These tests confirm the regression where panels were defined but never wired
into the window (navigate_to only ever produced placeholders) stays fixed, and
that the Financial Analysis Suite panels (SMRT/MODL/STRC) are present.

Skipped automatically when PySide6 (the optional ``gui`` extra) is not
installed, so they never break a headless backend-only CI run.
"""

import os
from unittest.mock import MagicMock

import pytest

# Force the offscreen Qt platform before any PySide6 import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from src.gui.windows.main_window import _COMMAND_PANEL_MAP, _build_panel_registry  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def window(qapp):
    from src.gui.windows.main_window import MainWindow

    return MainWindow(MagicMock(), MagicMock())


def test_registry_is_populated():
    registry = _build_panel_registry()
    # The registry must resolve real classes (the bug was an empty/placeholder map).
    assert len(registry) >= 20
    assert {"smart_money", "auto_model", "complex_structure"} <= set(registry)


def test_new_feature_panels_open_real_widgets(window):
    from src.gui.panels.modl_panel import AutoModelPanel
    from src.gui.panels.smrt_panel import SmartMoneyPanel
    from src.gui.panels.strc_panel import ComplexStructurePanel

    expected = {
        "smart_money": SmartMoneyPanel,
        "auto_model": AutoModelPanel,
        "complex_structure": ComplexStructurePanel,
    }
    for key, cls in expected.items():
        window.navigate_to(key)
        widget = window.panel_stack.currentWidget()
        assert isinstance(widget, cls), f"{key} did not open {cls.__name__}"


def test_every_mnemonic_opens_a_real_panel(window):
    """Each mnemonic in the command map must open a real (non-placeholder) panel.

    A placeholder is a bare ``QWidget``; real panels subclass BasePanel.
    """
    from src.gui.panels.base_panel import BasePanel

    registry = _build_panel_registry()
    placeholders = []
    for mnemonic, panel_key in _COMMAND_PANEL_MAP.items():
        if panel_key not in registry:
            # No panel class mapped for this mnemonic yet — record it.
            placeholders.append(mnemonic)
            continue
        window.navigate_to(panel_key)
        widget = window.panel_stack.currentWidget()
        assert isinstance(widget, BasePanel), f"{mnemonic} -> {panel_key} is not a real panel"
        assert type(widget) is not QWidget

    # Every command mnemonic must now resolve to a real panel (no placeholders).
    assert placeholders == [], f"commands still missing panels: {placeholders}"


def test_activate_does_not_crash_with_context(window):
    """Navigating with a context dict must not raise (activate is called)."""
    for key in ("smart_money", "auto_model", "complex_structure", "valuation", "ownership"):
        window.navigate_to(key, {"security": "AAPL", "entity_id": None, "security_id": None})
        assert window.panel_stack.currentWidget() is not None


def test_every_panel_class_instantiates(qapp):
    """Every distinct panel class in the registry must construct without error.

    This guards against latent per-panel runtime bugs (e.g. wrong Qt symbol)
    that only surface when the panel is actually built.
    """
    from src.gui.panels.base_panel import BasePanel

    registry = _build_panel_registry()
    failures = []
    for cls in set(registry.values()):
        try:
            panel = cls(MagicMock(), MagicMock())
            assert isinstance(panel, BasePanel)
            # activate() must also be safe to call with an empty context.
            if hasattr(panel, "activate"):
                panel.activate({})
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{cls.__name__}: {type(exc).__name__}: {exc}")
    assert not failures, "panels failed to construct/activate:\n" + "\n".join(failures)
