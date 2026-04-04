"""E1 -- Industry-Specific KPI Engine.

Computes industry-specific KPIs based on GICS classification.  Each
security is mapped to a KPI set via its issuer entity's primary GICS
code.  When the sector/industry group is not in the dispatch map the
engine returns only the universal informational outputs.

Every output carries full input lineage for auditability.
"""

from __future__ import annotations

import logging
from typing import Any, Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.engines.base import BaseEngine, EngineOutput, make_input, safe_divide
from src.models.analytics import AnalyticsResult
from src.models.entity import Entity
from src.models.fundamentals import (
    BalanceSheet, CashFlowStatement, FinancialPeriod, IncomeStatement,
)
from src.models.reference import GICSClassification
from src.models.security import Security

logger = logging.getLogger(__name__)

ENGINE_ID = "E1"
METRIC_CATEGORY = "INDUSTRY_KPI"


# ---------------------------------------------------------------------------
# Internal data container
# ---------------------------------------------------------------------------

class _Data:
    """Financial data bundle consumed by industry KPI functions."""

    __slots__ = (
        "security_id", "entity_id", "entity",
        "inc", "bs", "cf",
        "period_label", "period_end_date", "ttm",
    )

    def __init__(self, security_id: UUID, entity: Entity,
                 period: FinancialPeriod | None, ttm: dict[str, float | None]) -> None:
        self.security_id = security_id
        self.entity_id = entity.entity_id
        self.entity = entity
        self.ttm = ttm
        if period is not None:
            self.inc: IncomeStatement | None = period.income_statement
            self.bs: BalanceSheet | None = period.balance_sheet
            self.cf: CashFlowStatement | None = period.cash_flow
            pt = period.period_type or "FY"
            if pt.upper() in ("TTM", "LTM"):
                self.period_label = "TTM"
            elif period.fiscal_quarter is not None:
                self.period_label = f"Q{period.fiscal_quarter}_{period.fiscal_year}"
            else:
                self.period_label = f"FY_{period.fiscal_year}"
            self.period_end_date = period.period_end_date
        else:
            self.inc = self.bs = self.cf = None
            self.period_label = "LATEST"
            self.period_end_date = None

    def iv(self, f: str) -> float | None:
        v = getattr(self.inc, f, None) if self.inc else None
        return float(v) if v is not None else None

    def bv(self, f: str) -> float | None:
        v = getattr(self.bs, f, None) if self.bs else None
        return float(v) if v is not None else None

    def cv(self, f: str) -> float | None:
        v = getattr(self.cf, f, None) if self.cf else None
        return float(v) if v is not None else None

    def t(self, metric: str) -> float | None:
        return self.ttm.get(metric)


def _o(d: _Data, name: str, val: float | None, *, unit: str = "RATIO",
       dq: str | None = None, inp: list[dict] | None = None, note: str = "") -> EngineOutput:
    """Build a single EngineOutput."""
    if dq is None:
        dq = "COMPLETE" if val is not None else "INSUFFICIENT_DATA"
    if note and inp is None:
        inp = [make_input(name="note", source="engine", value=None, period=note)]
    return EngineOutput(
        security_id=d.security_id, entity_id=d.entity_id, engine_id=ENGINE_ID,
        metric_name=name, metric_category=METRIC_CATEGORY, value=val, unit=unit,
        period=d.period_label, period_end_date=d.period_end_date,
        data_quality=dq, inputs=inp,
    )


_mi = make_input  # local alias for brevity


# ---------------------------------------------------------------------------
# KPI functions per industry
# ---------------------------------------------------------------------------

def _software(d: _Data) -> list[EngineOutput]:
    """Software / Technology (GICS 4510, 4520)."""
    out: list[EngineOutput] = []
    rev_g = d.t("revenue_growth_yoy")
    fcf = d.t("ttm_free_cash_flow")
    rev = d.iv("total_revenue") or d.t("ttm_total_revenue")
    fcf_m = safe_divide(fcf, rev)
    r40 = (rev_g + fcf_m) if rev_g is not None and fcf_m is not None else None
    out.append(_o(d, "rule_of_40", r40, inp=[
        _mi("revenue_growth_yoy", "analytics_results", rev_g),
        _mi("fcf_margin", "derived", fcf_m),
    ]))
    out.append(_o(d, "revenue_per_employee", None, unit="CURRENCY",
                  note="requires employee_count from supplemental data"))
    rd = d.iv("research_development") or d.t("ttm_research_development")
    out.append(_o(d, "rd_intensity", safe_divide(rd, rev), inp=[
        _mi("research_development", "income_statement", rd),
        _mi("total_revenue", "income_statement", rev),
    ]))
    gp = d.iv("gross_profit") or d.t("ttm_gross_profit")
    gm = safe_divide(gp, rev)
    out.append(_o(d, "gross_margin_software", gm, unit="PERCENT", inp=[
        _mi("gross_profit", "income_statement", gp),
        _mi("total_revenue", "income_statement", rev),
    ]))
    # recurring_revenue_ratio -- estimated from gross margin stability
    if gm is not None and gm > 0.65:
        rrr = min(gm * 1.1, 1.0)
        out.append(_o(d, "recurring_revenue_ratio", rrr, dq="ESTIMATED",
                      inp=[_mi("gross_margin_proxy", "derived", gm)]))
    else:
        out.append(_o(d, "recurring_revenue_ratio", None,
                      note="estimated from gross margin; insufficient data"))
    return out


def _banks(d: _Data) -> list[EngineOutput]:
    """Banks / Diversified Financials (GICS 4010, 4020)."""
    out: list[EngineOutput] = []
    rev = d.iv("total_revenue") or d.t("ttm_total_revenue")
    opex = d.iv("total_operating_expense")
    out.append(_o(d, "efficiency_ratio", safe_divide(opex, rev), inp=[
        _mi("total_operating_expense", "income_statement", opex),
        _mi("total_revenue", "income_statement", rev),
    ]))
    net_int = d.iv("net_interest")
    assets = d.bv("total_assets")
    out.append(_o(d, "net_interest_margin", safe_divide(net_int, assets), unit="PERCENT",
                  inp=[_mi("net_interest", "income_statement", net_int),
                       _mi("total_assets", "balance_sheet", assets)]))
    # [Bug 17 fix] Omit always-None placeholders (loans_to_deposits,
    # provision_coverage, tier1_capital_ratio) that require detailed
    # bank regulatory data not in the standard schema.
    return out


def _reits(d: _Data) -> list[EngineOutput]:
    """REITs (GICS 6010)."""
    out: list[EngineOutput] = []
    ni = d.iv("net_income") or d.t("ttm_net_income")
    da = (d.cv("depreciation_amortization") or d.t("ttm_cf_depreciation_amortization")
          or d.iv("depreciation_amortization") or d.t("ttm_depreciation_amortization"))
    gain = 0.0  # gain_on_sale not in standard schema
    ffo = (ni + da - gain) if ni is not None and da is not None else None
    out.append(_o(d, "ffo", ffo, unit="CURRENCY", inp=[
        _mi("net_income", "income_statement", ni),
        _mi("depreciation_amortization", "cash_flow", da),
        _mi("gain_on_sale", "estimated", gain),
    ]))
    shares = d.iv("diluted_shares_outstanding")
    out.append(_o(d, "ffo_per_share", safe_divide(ffo, shares), unit="CURRENCY", inp=[
        _mi("ffo", "derived", ffo), _mi("diluted_shares", "income_statement", shares),
    ]))
    # [Bug 16 fix] Use actual maintenance capex from cash flow if available;
    # fall back to D&A × 0.125 heuristic only when field is null.
    actual_capex = d.cv("capital_expenditures")
    if actual_capex is not None:
        mcap = abs(actual_capex)
        mcap_quality = "COMPLETE"
    elif da is not None:
        mcap = da * 0.125
        mcap_quality = "ESTIMATED"
    else:
        mcap = None
        mcap_quality = "INSUFFICIENT_DATA"
    affo = (ffo - mcap) if ffo is not None and mcap is not None else None
    out.append(_o(d, "affo", affo, unit="CURRENCY",
                  dq=mcap_quality if affo is not None else None,
                  inp=[_mi("ffo", "derived", ffo), _mi("maint_capex", "cash_flow" if actual_capex else "derived", mcap)]))
    out.append(_o(d, "affo_per_share", safe_divide(affo, shares), unit="CURRENCY",
                  dq=mcap_quality if affo is not None else None,
                  inp=[_mi("affo", "derived", affo),
                       _mi("diluted_shares", "income_statement", shares)]))
    # NAV per share (simple book NAV)
    ta, tl = d.bv("total_assets"), d.bv("total_liabilities")
    nav = (ta - tl) if ta is not None and tl is not None else None
    out.append(_o(d, "nav_per_share", safe_divide(nav, shares), unit="CURRENCY", inp=[
        _mi("total_assets", "balance_sheet", ta),
        _mi("total_liabilities", "balance_sheet", tl),
        _mi("diluted_shares", "income_statement", shares),
    ]))
    divs = d.cv("dividends_paid") or d.t("ttm_dividends_paid")
    if divs is not None:
        divs = abs(divs)
    out.append(_o(d, "dividend_to_ffo", safe_divide(divs, ffo), inp=[
        _mi("dividends_paid", "cash_flow", divs), _mi("ffo", "derived", ffo),
    ]))
    return out


def _retail(d: _Data) -> list[EngineOutput]:
    """Retail (GICS 2550, 3010)."""
    out: list[EngineOutput] = []
    cogs = d.iv("cost_of_revenue") or d.t("ttm_cost_of_revenue")
    inv = d.bv("inventory")
    it = safe_divide(cogs, inv)
    out.append(_o(d, "inventory_turnover_retail", it, inp=[
        _mi("cost_of_revenue", "income_statement", cogs),
        _mi("inventory", "balance_sheet", inv),
    ]))
    # [Bug 17 fix] revenue_per_sqft omitted — requires supplemental square-footage data
    rev = d.iv("total_revenue") or d.t("ttm_total_revenue")
    gp = d.iv("gross_profit") or d.t("ttm_gross_profit")
    out.append(_o(d, "gross_margin_retail", safe_divide(gp, rev), unit="PERCENT", inp=[
        _mi("gross_profit", "income_statement", gp),
        _mi("total_revenue", "income_statement", rev),
    ]))
    out.append(_o(d, "inventory_days_retail", safe_divide(365.0, it) if it else None,
                  unit="DAYS", inp=[_mi("inventory_turnover", "derived", it)]))
    # [Bug 17 fix] revenue_per_sqft requires supplemental data — omit
    return out


def _insurance(d: _Data) -> list[EngineOutput]:
    """Insurance (GICS 4030)."""
    out: list[EngineOutput] = []
    losses = d.iv("cost_of_revenue")
    opex = d.iv("selling_general_admin")
    prem = d.iv("total_revenue")
    comb: float | None = None
    if losses is not None and opex is not None and prem is not None and prem != 0:
        comb = (losses + opex) / prem
    out.append(_o(d, "combined_ratio", comb,
                  dq="ESTIMATED" if comb is not None else None, inp=[
        _mi("losses_proxy", "income_statement", losses),
        _mi("opex_proxy", "income_statement", opex),
        _mi("premiums_proxy", "income_statement", prem),
    ]))
    ii = d.iv("interest_income") or d.iv("other_income_expense")
    ia = d.bv("long_term_investments")
    iy = safe_divide(ii, ia)
    out.append(_o(d, "investment_yield", iy, unit="PERCENT",
                  dq="ESTIMATED" if iy is not None else None, inp=[
        _mi("investment_income_proxy", "income_statement", ii),
        _mi("long_term_investments", "balance_sheet", ia),
    ]))
    return out


def _energy(d: _Data) -> list[EngineOutput]:
    """Energy / Mining (GICS 1010, 1510).

    [Bug 17 fix] Skip always-None placeholders that require supplemental
    data not present in the standard schema.
    """
    # reserve_life_index, finding_cost, netback: all require reserve/production
    # data not available in standard financials — omit entirely.
    return []


def _pharma(d: _Data) -> list[EngineOutput]:
    """Healthcare / Pharma (GICS 3510, 3520)."""
    out: list[EngineOutput] = []
    rd = d.iv("research_development") or d.t("ttm_research_development")
    rev = d.iv("total_revenue") or d.t("ttm_total_revenue")
    out.append(_o(d, "rd_to_revenue", safe_divide(rd, rev), inp=[
        _mi("research_development", "income_statement", rd),
        _mi("total_revenue", "income_statement", rev),
    ]))
    rdg = d.t("rd_expense_growth_yoy")
    out.append(_o(d, "pipeline_proxy", rdg,
                  dq="ESTIMATED" if rdg is not None else "INSUFFICIENT_DATA",
                  inp=[_mi("rd_growth_proxy", "analytics_results", rdg)]))
    return out


# ---------------------------------------------------------------------------
# GICS dispatch map
# ---------------------------------------------------------------------------

_KPI_FN = Callable[[_Data], list[EngineOutput]]

INDUSTRY_KPI_MAP: dict[str, _KPI_FN] = {
    "4510": _software, "4520": _software,       # Software / Tech Hardware
    "4010": _banks,    "4020": _banks,           # Banks / Diversified Financials
    "6010": _reits,                              # Real Estate
    "2550": _retail,   "3010": _retail,          # Retailing
    "4030": _insurance,                          # Insurance
    "1010": _energy,   "1510": _energy,          # Energy / Mining
    "3510": _pharma,   "3520": _pharma,          # Pharma / HC Equipment
}

_KPI_SET_NAMES: dict[str, str] = {
    "4510": "Software/Technology", "4520": "Software/Technology",
    "4010": "Banks/Financials",    "4020": "Banks/Financials",
    "6010": "REITs",
    "2550": "Retail",              "3010": "Retail",
    "4030": "Insurance",
    "1010": "Energy/Mining",       "1510": "Energy/Mining",
    "3510": "Healthcare/Pharma",   "3520": "Healthcare/Pharma",
}


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class IndustryKPIEngine(BaseEngine):
    """E1 -- Industry-Specific KPI Engine.

    Resolves a security to its issuer entity, determines the applicable
    GICS classification, and dispatches to the appropriate KPI set.
    Always produces universal classification outputs.
    """

    engine_id: str = "E1"
    engine_name: str = "Industry KPIs"
    engine_version: str = "1.0.0"

    async def compute(
        self, session: AsyncSession, security_id: UUID, **kwargs: Any,
    ) -> list[EngineOutput]:
        # 1. Resolve security -> entity
        sec_row = await session.execute(
            select(Security).where(Security.security_id == security_id))
        security = sec_row.scalar_one_or_none()
        if security is None or security.issuer_entity_id is None:
            logger.warning("IndustryKPI: security %s not found or no issuer", security_id)
            return []

        entity_id: UUID = security.issuer_entity_id
        ent_row = await session.execute(
            select(Entity).where(Entity.entity_id == entity_id))
        entity = ent_row.scalar_one_or_none()
        if entity is None:
            logger.warning("IndustryKPI: entity %s not found", entity_id)
            return []

        # 2. GICS classification
        gics_ig = entity.gics_industry_group    # 4-digit
        gics_sector = entity.gics_sector        # 2-digit
        gics_sub = entity.gics_sub_industry     # 8-digit
        sub_name = await self._sub_industry_name(session, gics_sub)

        # 3. Latest financial period (with eager-loaded statements)
        fp_row = await session.execute(
            select(FinancialPeriod)
            .where(FinancialPeriod.entity_id == entity_id,
                   FinancialPeriod.period_type.in_(["ANNUAL", "QUARTERLY"]))
            .order_by(FinancialPeriod.period_end_date.desc())
            .limit(1))
        latest_period = fp_row.scalar_one_or_none()

        # 4. Pre-computed TTM / ratio metrics
        ttm = await self._load_ttm(session, security_id)

        # 5. Build data bundle
        d = _Data(security_id, entity, latest_period, ttm)
        outputs: list[EngineOutput] = []

        # 6. Universal outputs
        outputs.append(_o(d, "industry_classified_as", None, unit="SCORE",
                          dq="INFORMATIONAL", inp=[_mi(
                              "gics_sub_industry_name", "gics_classifications",
                              None, period=sub_name or "UNCLASSIFIED")]))

        dispatch_key = self._dispatch_key(gics_ig, gics_sector)
        kpi_set = _KPI_SET_NAMES.get(dispatch_key, "Generic") if dispatch_key else "Generic"
        outputs.append(_o(d, "kpi_set_applied", None, unit="SCORE",
                          dq="INFORMATIONAL",
                          inp=[_mi("kpi_set", "engine", None, period=kpi_set)]))

        # 7. Dispatch
        if dispatch_key is not None:
            outputs.extend(INDUSTRY_KPI_MAP[dispatch_key](d))
        else:
            logger.info("IndustryKPI: GICS %s/%s not in KPI map for entity %s",
                        gics_sector, gics_ig, entity_id)

        logger.info("IndustryKPI: computed %d KPIs for security %s (set=%s)",
                     len(outputs), security_id, kpi_set)
        return outputs

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _dispatch_key(gics_ig: str | None, gics_sector: str | None) -> str | None:
        """Resolve best INDUSTRY_KPI_MAP key: 4-digit first, then 2-digit sector."""
        if gics_ig and gics_ig in INDUSTRY_KPI_MAP:
            return gics_ig
        if gics_sector:
            for key in INDUSTRY_KPI_MAP:
                if key[:2] == gics_sector:
                    return key
        return None

    @staticmethod
    async def _sub_industry_name(session: AsyncSession, code: str | None) -> str | None:
        if code is None:
            return None
        row = await session.execute(
            select(GICSClassification.sub_industry_name)
            .where(GICSClassification.sub_industry_code == code))
        return row.scalar_one_or_none()

    @staticmethod
    async def _load_ttm(session: AsyncSession, security_id: UUID) -> dict[str, float | None]:
        """Load latest pre-computed E1 metrics from analytics_results."""
        rows = await session.execute(
            select(AnalyticsResult.metric_name, AnalyticsResult.value)
            .where(AnalyticsResult.security_id == security_id,
                   AnalyticsResult.engine_id == "E1")
            .order_by(AnalyticsResult.as_of_date.desc()))
        metrics: dict[str, float | None] = {}
        for name, value in rows.all():
            if name not in metrics:
                metrics[name] = float(value) if value is not None else None
        return metrics
