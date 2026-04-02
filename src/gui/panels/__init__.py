"""Bloomberg Terminal GUI panels.

Each panel is a PySide6 QWidget inheriting from :class:`BasePanel`,
styled with the Bloomberg Terminal dark theme.
"""

from src.gui.panels.base_panel import BasePanel
from src.gui.panels.cacs_panel import CacsPanel
from src.gui.panels.dashboard import DashboardPanel
from src.gui.panels.des_panel import DESPanel
from src.gui.panels.ecfc_panel import ECFCPanel
from src.gui.panels.esg_panel import EsgPanel
from src.gui.panels.fa_panel import FAPanel
from src.gui.panels.gp_panel import GPPanel
from src.gui.panels.own_panel import OwnPanel
from src.gui.panels.quality_panel import QualityPanel
from src.gui.panels.resolution_panel import ResolutionPanel
from src.gui.panels.rv_panel import RvPanel
from src.gui.panels.search_panel import SearchPanel
from src.gui.panels.splc_panel import SplcPanel

# Pillar 2: Analytics Engine panels
from src.gui.panels.anly_panel import AnlyPanel
from src.gui.panels.val_panel import ValPanel
from src.gui.panels.scor_panel import ScorPanel
from src.gui.panels.eqs_panel import EqsPanel
from src.gui.panels.risk_panel import RiskPanel
from src.gui.panels.flow_panel import FlowPanel
from src.gui.panels.qant_panel import QantPanel
from src.gui.panels.scen_panel import ScenPanel

__all__ = [
    "BasePanel",
    "CacsPanel",
    "DashboardPanel",
    "DESPanel",
    "ECFCPanel",
    "EsgPanel",
    "FAPanel",
    "GPPanel",
    "OwnPanel",
    "QualityPanel",
    "ResolutionPanel",
    "RvPanel",
    "SearchPanel",
    "SplcPanel",
    # Pillar 2
    "AnlyPanel",
    "ValPanel",
    "ScorPanel",
    "EqsPanel",
    "RiskPanel",
    "FlowPanel",
    "QantPanel",
    "ScenPanel",
]
