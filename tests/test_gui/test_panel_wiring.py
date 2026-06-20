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


def test_command_resolves_ticker_into_context(window):
    """`AAPL FA` must resolve the ticker and pass ids into the panel context."""
    window.data_service.resolve_security.return_value = {
        "ticker": "AAPL",
        "security_id": "sid-1",
        "security_name": "AAPL",
        "entity_id": "eid-1",
        "entity_name": "Apple Inc.",
    }
    captured = {}
    window.navigate_to = lambda name, ctx=None: captured.update({"name": name, "ctx": ctx or {}})

    window.on_command("AAPL FA")

    window.data_service.resolve_security.assert_called_once_with("AAPL")
    assert captured["name"] == "financials"
    assert captured["ctx"]["entity_id"] == "eid-1"
    assert captured["ctx"]["security_id"] == "sid-1"
    assert captured["ctx"]["ticker"] == "AAPL"


def test_command_single_ticker_defaults_to_description_with_ids(window):
    window.data_service.resolve_security.return_value = {
        "ticker": "MSFT", "security_id": "s2", "security_name": "MSFT",
        "entity_id": "e2", "entity_name": "Microsoft",
    }
    captured = {}
    window.navigate_to = lambda name, ctx=None: captured.update({"name": name, "ctx": ctx or {}})

    window.on_command("MSFT")

    assert captured["name"] == "description"
    assert captured["ctx"]["security_id"] == "s2"
    assert captured["ctx"]["entity_id"] == "e2"


def test_command_unresolved_ticker_still_opens_panel(window):
    """An unknown ticker must still open the panel (graceful), just without ids."""
    window.data_service.resolve_security.return_value = None
    captured = {}
    window.navigate_to = lambda name, ctx=None: captured.update({"name": name, "ctx": ctx or {}})

    window.on_command("NOPE VAL")

    assert captured["name"] == "valuation"
    assert captured["ctx"].get("security_id") is None
    assert captured["ctx"]["ticker"] == "NOPE"


@pytest.mark.asyncio
async def test_resolve_security_against_db(engine):
    """The DataService resolver maps a real ticker to security + entity ids."""
    import uuid as _uuid

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from src.gui.core.data_service import DataService
    from src.models.entity import Entity
    from src.models.security import Security, SecurityIdentifier

    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    ent_id = _uuid.uuid4()
    sec_id = _uuid.uuid4()
    async with sf() as s:
        s.add(Entity(entity_id=ent_id, entity_type="PUBLIC_COMPANY",
                     legal_name="Zeta Test Corp", status="ACTIVE", source="TEST"))
        s.add(Security(security_id=sec_id, security_type="COMMON_STOCK",
                       name="Zeta Test Corp Common", short_name="ZZTESTQ",
                       status="ACTIVE", asset_class="EQUITY", issuer_entity_id=ent_id))
        s.add(SecurityIdentifier(security_id=sec_id, identifier_type="TICKER",
                                 identifier_value="ZZTESTQ"))
        await s.commit()

    ds = DataService.__new__(DataService)  # bypass QObject init; no worker needed
    ds._session_factory = sf

    # Exact ticker match resolves both ids.
    res = await ds._resolve_security("ZZTESTQ")
    assert res is not None
    assert res["security_id"] == str(sec_id)
    assert res["entity_id"] == str(ent_id)
    assert res["entity_name"] == "Zeta Test Corp"

    # Case-insensitive ticker also resolves.
    assert (await ds._resolve_security("zztestq"))["security_id"] == str(sec_id)

    # Unknown ticker resolves to None (graceful).
    assert await ds._resolve_security("NO_SUCH_TICKER_XYZ") is None

    # cleanup so the shared session-scoped DB isn't polluted
    async with sf() as s:
        for model, pk_col, pk in (
            (SecurityIdentifier, SecurityIdentifier.security_id, sec_id),
            (Security, Security.security_id, sec_id),
            (Entity, Entity.entity_id, ent_id),
        ):
            for obj in (await s.execute(__import__("sqlalchemy").select(model).where(pk_col == pk))).scalars().all():
                await s.delete(obj)
        await s.commit()


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
