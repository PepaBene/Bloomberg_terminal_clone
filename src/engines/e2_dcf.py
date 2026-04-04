"""E2 DCF Valuation Engine — Discounted Cash Flow.

Implements both FCFF (Free Cash Flow to the Firm) and FCFE (Free Cash
Flow to Equity) DCF models.  Projects explicit-period free cash flows
based on historical financial data, discounts them at the appropriate
rate (WACC for FCFF, cost of equity for FCFE), and adds a Gordon-Growth
terminal value to arrive at an implied share price.

FCFF Model
----------
FCFF = EBIT * (1 - Tax Rate) + D&A - CapEx - Delta Working Capital

    Discount rate : WACC
    Result        : Enterprise Value -> subtract Net Debt -> Equity Value

FCFE Model
----------
FCFE = Net Income + D&A - CapEx - Delta WC + Net Borrowing

    Discount rate : Cost of Equity (Ke)
    Result        : Equity Value directly

Terminal Value (Gordon Growth)
------------------------------
TV = FCF_last * (1 + g) / (r - g)

Both models produce ~15 EngineOutput metrics with full lineage and
persist the detailed result to the ``DCFResult`` table.

Part of Pillar 2 analytics — consumes Pillar 1 fundamentals and the
WACC engine output.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.engines.base import BaseEngine, EngineOutput, cagr, make_input, safe_divide
from src.models.analytics import DCFResult, WACCResult
from src.models.fundamentals import (
    BalanceSheet,
    CashFlowStatement,
    FinancialPeriod,
    IncomeStatement,
)
from src.models.security import EODPrice, EquityDetails, Security

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_PROJECTION_YEARS = 5
_DEFAULT_TERMINAL_GROWTH = 0.025          # 2.5%
_DEFAULT_WACC = 0.10                      # 10% fallback
_DEFAULT_TAX_RATE = 0.21                  # US statutory
_MIN_WACC_TERMINAL_GAP = 0.005           # terminal_growth must be < WACC - 0.5%
_HIGH_TERMINAL_PCT_THRESHOLD = 0.90       # flag if TV > 90% of EV
_SENSITIVITY_WACC_STEPS = 7              # 7x7 grid
_SENSITIVITY_GROWTH_STEPS = 7
_SENSITIVITY_WACC_RANGE = 0.02           # +/- 2%
_SENSITIVITY_GROWTH_RANGE = 0.015        # +/- 1.5%
_UNDERVALUED_THRESHOLD = 0.15            # upside > 15%
_OVERVALUED_THRESHOLD = -0.15            # downside < -15%
_DEFAULT_EXIT_MULTIPLE = 10.0            # sector median EV/EBITDA fallback


# ---------------------------------------------------------------------------
# Helper: float conversion
# ---------------------------------------------------------------------------

def _f(val: Any) -> float | None:
    """Convert a Decimal/numeric DB value to float, returning None if null."""
    return float(val) if val is not None else None


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class DCFEngine(BaseEngine):
    """Discounted Cash Flow valuation engine (E2).

    Supports two methods via the ``method`` kwarg:
    - ``"FCFF"`` (default) — Free Cash Flow to the Firm
    - ``"FCFE"`` — Free Cash Flow to Equity

    Custom assumptions can be provided via the ``assumptions`` kwarg dict
    to override any default projection parameter.

    Output metrics (~15 items):
        dcf_enterprise_value, dcf_equity_value, dcf_implied_price,
        dcf_current_price, dcf_upside_downside, dcf_wacc_used,
        dcf_terminal_value, dcf_terminal_pct_of_ev, dcf_pv_explicit,
        dcf_pv_terminal, dcf_method, dcf_projection_years,
        dcf_terminal_method, dcf_terminal_growth, dcf_implied_vs_current
    """

    engine_id = "E2"
    engine_name = "DCF Valuation"
    engine_version = "1.0.0"

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def compute(
        self,
        session: AsyncSession,
        security_id: UUID,
        **kwargs: Any,
    ) -> list[EngineOutput]:
        method: str = kwargs.get("method", "FCFF")
        user_assumptions: dict | None = kwargs.get("assumptions", None)

        # 1. Resolve security -> entity
        security, entity_id = await self._resolve_security(session, security_id)
        if security is None or entity_id is None:
            return []

        today = date.today()

        # 2. Load historical annual financials (most recent 5 years max)
        periods = await self._load_annual_financials(session, entity_id, limit=5)
        if len(periods) < 1:
            logger.info("DCF: no annual financials for entity %s", entity_id)
            return []

        # 3. Extract historical data arrays (most recent first in periods)
        hist = self._extract_historical(periods)
        if hist is None:
            logger.info("DCF: insufficient historical data for entity %s", entity_id)
            return []

        # 4. Load or default discount rate
        wacc_val, cost_of_equity = await self._load_discount_rates(
            session, entity_id, security_id
        )

        # 5. Load current price and shares outstanding
        current_price = await self._load_current_price(session, security_id)
        shares = await self._load_shares_outstanding(session, security_id)

        # 6. Build assumptions (merge defaults with user overrides)
        assumptions = self._build_assumptions(
            hist, method, wacc_val, cost_of_equity, user_assumptions
        )

        # 7. Run the DCF projection
        if method == "FCFE":
            result = self._project_fcfe(hist, assumptions)
        else:
            result = self._project_fcff(hist, assumptions)

        if result is None:
            logger.warning("DCF: projection returned None for %s", security_id)
            return []

        # 8. Compute final values
        discount_rate = assumptions["discount_rate"]
        terminal_growth = assumptions["terminal_growth"]

        projected_fcfs: list[float] = result["projected_fcfs"]
        pv_explicit = result["pv_explicit"]
        terminal_value = result["terminal_value"]
        pv_terminal = result["pv_terminal"]

        enterprise_value = pv_explicit + pv_terminal

        # For FCFF: Equity Value = EV - Net Debt
        # For FCFE: Equity Value = EV directly (already equity)
        if method == "FCFF":
            net_debt = self._compute_net_debt(hist)
            equity_value = enterprise_value - net_debt
        else:
            net_debt = 0.0
            equity_value = enterprise_value

        # Implied price per share
        implied_price: float | None = None
        if shares is not None and shares > 0:
            implied_price = equity_value / shares
        else:
            implied_price = None

        # Upside / downside
        upside_downside: float | None = None
        if implied_price is not None and current_price is not None and current_price > 0:
            upside_downside = (implied_price - current_price) / current_price

        # Terminal value as % of EV
        terminal_pct: float | None = None
        if enterprise_value != 0:
            terminal_pct = pv_terminal / enterprise_value

        # Data quality flags
        data_quality = "COMPLETE"
        flags: list[str] = []

        if all(f <= 0 for f in projected_fcfs):
            data_quality = "NEGATIVE_FCF"
            flags.append("NEGATIVE_FCF")
            implied_price = None

        if terminal_pct is not None and terminal_pct > _HIGH_TERMINAL_PCT_THRESHOLD:
            flags.append("HIGH_TERMINAL_DEPENDENCY")

        if implied_price is None and shares is not None and shares <= 0:
            flags.append("ZERO_SHARES")

        if flags and data_quality == "COMPLETE":
            data_quality = "|".join(flags)

        # Implied vs current classification
        implied_vs_current = self._classify_valuation(upside_downside)

        # 9. Build sensitivity grid
        sensitivity = self._build_sensitivity_grid(
            result["last_fcf"],
            enterprise_value,
            net_debt if method == "FCFF" else 0.0,
            shares,
            discount_rate,
            terminal_growth,
            assumptions["projection_years"],
            projected_fcfs=result.get("projected_fcfs"),  # [Bug 19] pass FCFs for full re-discount
        )

        # 10. Persist DCFResult
        dcf_row = DCFResult(
            entity_id=entity_id,
            security_id=security_id,
            calculation_date=today,
            method=method,
            assumptions=assumptions,
            wacc_used=discount_rate if method == "FCFF" else None,
            cost_of_equity=cost_of_equity,
            projected_cashflows={
                "years": list(range(1, assumptions["projection_years"] + 1)),
                "fcfs": projected_fcfs,
            },
            terminal_value=terminal_value,
            terminal_method=assumptions.get("terminal_method", "GORDON_GROWTH"),
            terminal_growth_rate=terminal_growth,
            terminal_exit_multiple=assumptions.get("terminal_exit_multiple"),
            pv_terminal=pv_terminal,
            terminal_pct_of_ev=terminal_pct,
            pv_of_fcf=pv_explicit,
            enterprise_value=enterprise_value,
            net_debt=net_debt if method == "FCFF" else None,
            equity_value=equity_value,
            shares_outstanding=shares,
            implied_price=implied_price,
            current_price=current_price,
            upside_downside_pct=upside_downside,
            sensitivity_grid=sensitivity,
            data_quality=data_quality,
            currency=security.primary_currency,
        )
        session.add(dcf_row)

        # 11. Build EngineOutput list
        outputs = self._build_outputs(
            security_id=security_id,
            entity_id=entity_id,
            today=today,
            method=method,
            enterprise_value=enterprise_value,
            equity_value=equity_value,
            implied_price=implied_price,
            current_price=current_price,
            upside_downside=upside_downside,
            discount_rate=discount_rate,
            terminal_value=terminal_value,
            terminal_pct=terminal_pct,
            pv_explicit=pv_explicit,
            pv_terminal=pv_terminal,
            projection_years=assumptions["projection_years"],
            terminal_growth=terminal_growth,
            terminal_method=assumptions.get("terminal_method", "GORDON_GROWTH"),
            implied_vs_current=implied_vs_current,
            data_quality=data_quality,
        )

        logger.info(
            "DCF (%s): computed %d metrics for security %s — "
            "EV=%.0f, Equity=%.0f, Implied=$%.2f, Current=$%.2f, Upside=%.1f%% (quality=%s)",
            method,
            len(outputs),
            security_id,
            enterprise_value,
            equity_value,
            implied_price if implied_price is not None else 0.0,
            current_price if current_price is not None else 0.0,
            (upside_downside * 100) if upside_downside is not None else 0.0,
            data_quality,
        )
        return outputs

    # ------------------------------------------------------------------
    # Data loading helpers
    # ------------------------------------------------------------------

    async def _resolve_security(
        self,
        session: AsyncSession,
        security_id: UUID,
    ) -> tuple[Security | None, UUID | None]:
        """Resolve security_id to Security row and entity_id."""
        result = await session.execute(
            select(Security).where(Security.security_id == security_id)
        )
        security = result.scalar_one_or_none()
        if security is None or security.issuer_entity_id is None:
            logger.warning("DCF: security %s not found or no issuer", security_id)
            return None, None
        return security, security.issuer_entity_id

    async def _load_annual_financials(
        self,
        session: AsyncSession,
        entity_id: UUID,
        limit: int = 5,
    ) -> list[FinancialPeriod]:
        """Load most recent annual financial periods with all three statements.

        Returns periods ordered by period_end_date descending (newest first).
        """
        stmt = (
            select(FinancialPeriod)
            .where(
                FinancialPeriod.entity_id == entity_id,
                FinancialPeriod.period_type == "ANNUAL",
            )
            .order_by(FinancialPeriod.period_end_date.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        all_periods = list(result.scalars().all())

        # Filter to periods that have all three statements
        complete = [
            p for p in all_periods
            if p.income_statement is not None
            and p.balance_sheet is not None
            and p.cash_flow is not None
        ]
        return complete

    async def _load_discount_rates(
        self,
        session: AsyncSession,
        entity_id: UUID,
        security_id: UUID,
    ) -> tuple[float, float | None]:
        """Load WACC and cost of equity from WACCResult.

        Returns (wacc, cost_of_equity).  Falls back to defaults if not found.
        """
        stmt = (
            select(WACCResult)
            .where(
                WACCResult.entity_id == entity_id,
                WACCResult.security_id == security_id,
            )
            .order_by(WACCResult.calculation_date.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        wacc_row = result.scalar_one_or_none()

        if wacc_row is not None:
            wacc = _f(wacc_row.wacc) if wacc_row.wacc is not None else _DEFAULT_WACC
            ke = _f(wacc_row.cost_of_equity)
            return wacc, ke

        logger.info(
            "DCF: no WACCResult for entity %s / security %s — using default %.1f%%",
            entity_id, security_id, _DEFAULT_WACC * 100,
        )
        return _DEFAULT_WACC, None

    async def _load_current_price(
        self,
        session: AsyncSession,
        security_id: UUID,
    ) -> float | None:
        """Load the latest adjusted close price."""
        stmt = (
            select(EODPrice.close_adjusted)
            .where(
                EODPrice.security_id == security_id,
                EODPrice.close_adjusted.isnot(None),
            )
            .order_by(EODPrice.price_date.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        val = result.scalar_one_or_none()
        return _f(val)

    async def _load_shares_outstanding(
        self,
        session: AsyncSession,
        security_id: UUID,
    ) -> float | None:
        """Load shares outstanding from EquityDetails."""
        stmt = (
            select(EquityDetails.shares_outstanding)
            .where(EquityDetails.security_id == security_id)
        )
        result = await session.execute(stmt)
        val = result.scalar_one_or_none()
        return _f(val)

    # ------------------------------------------------------------------
    # Historical extraction
    # ------------------------------------------------------------------

    def _extract_historical(
        self,
        periods: list[FinancialPeriod],
    ) -> dict[str, Any] | None:
        """Extract historical financial arrays from periods.

        Periods must be in descending date order (newest first).
        Returns None if the latest period lacks essential data.
        """
        if not periods:
            return None

        latest = periods[0]
        inc = latest.income_statement
        bs = latest.balance_sheet
        cf = latest.cash_flow

        if inc is None or bs is None or cf is None:
            return None

        # Latest-year values (base year for projections)
        revenue = _f(inc.total_revenue)
        if revenue is None or revenue <= 0:
            logger.info("DCF: latest revenue is None or non-positive")
            return None

        ebit = _f(inc.operating_income)
        net_income = _f(inc.net_income)
        dna = _f(cf.depreciation_amortization) or _f(inc.depreciation_amortization) or 0.0
        capex = _f(cf.capital_expenditures) or 0.0
        # CapEx is typically reported as negative in cash flow; use absolute
        capex = abs(capex)

        # Tax rate from income statement or default
        tax_rate = _f(inc.effective_tax_rate)
        if tax_rate is None or tax_rate < 0 or tax_rate > 0.60:
            pretax = _f(inc.pretax_income)
            tax_exp = _f(inc.income_tax_expense)
            if pretax is not None and pretax > 0 and tax_exp is not None:
                tax_rate = max(0.0, min(tax_exp / pretax, 0.50))
            else:
                tax_rate = _DEFAULT_TAX_RATE

        # Working capital
        wc = _f(bs.working_capital)
        if wc is None:
            # Compute: current assets - current liabilities
            ca = _f(bs.total_current_assets) or 0.0
            cl = _f(bs.total_current_liabilities) or 0.0
            wc = ca - cl

        # Debt values for net debt calculation
        total_debt = _f(bs.total_debt) or 0.0
        cash = _f(bs.cash_and_equivalents) or _f(bs.cash_and_short_term) or 0.0

        # Net borrowing for FCFE (debt issued - debt repaid)
        debt_issued = _f(cf.debt_issued) or 0.0
        debt_repaid = _f(cf.debt_repaid) or 0.0
        net_borrowing = debt_issued - abs(debt_repaid)

        # Historical revenue series for CAGR (oldest to newest)
        rev_series: list[float] = []
        for p in reversed(periods):
            if p.income_statement is not None:
                r = _f(p.income_statement.total_revenue)
                if r is not None and r > 0:
                    rev_series.append(r)

        # Historical EBIT margins for averaging
        ebit_margins: list[float] = []
        for p in reversed(periods):
            if p.income_statement is not None:
                r = _f(p.income_statement.total_revenue)
                e = _f(p.income_statement.operating_income)
                if r is not None and r > 0 and e is not None:
                    ebit_margins.append(e / r)

        # Historical ratios for projection defaults
        capex_rev_ratios: list[float] = []
        dna_rev_ratios: list[float] = []
        wc_rev_ratios: list[float] = []

        for p in reversed(periods):
            pi = p.income_statement
            pb = p.balance_sheet
            pc = p.cash_flow
            if pi is None or pb is None or pc is None:
                continue
            r = _f(pi.total_revenue)
            if r is None or r <= 0:
                continue

            cx = _f(pc.capital_expenditures) or 0.0
            capex_rev_ratios.append(abs(cx) / r)

            da = _f(pc.depreciation_amortization) or _f(pi.depreciation_amortization) or 0.0
            dna_rev_ratios.append(da / r)

            w = _f(pb.working_capital)
            if w is None:
                ca = _f(pb.total_current_assets) or 0.0
                cl = _f(pb.total_current_liabilities) or 0.0
                w = ca - cl
            wc_rev_ratios.append(w / r)

        # Previous-year working capital for delta WC calculation
        prev_wc: float | None = None
        if len(periods) >= 2:
            prev_bs = periods[1].balance_sheet
            if prev_bs is not None:
                prev_wc = _f(prev_bs.working_capital)
                if prev_wc is None:
                    ca2 = _f(prev_bs.total_current_assets) or 0.0
                    cl2 = _f(prev_bs.total_current_liabilities) or 0.0
                    prev_wc = ca2 - cl2

        return {
            "revenue": revenue,
            "ebit": ebit or 0.0,
            "net_income": net_income or 0.0,
            "dna": dna,
            "capex": capex,
            "tax_rate": tax_rate,
            "wc": wc,
            "prev_wc": prev_wc,
            "total_debt": total_debt,
            "cash": cash,
            "net_borrowing": net_borrowing,
            "rev_series": rev_series,
            "ebit_margins": ebit_margins,
            "capex_rev_ratios": capex_rev_ratios,
            "dna_rev_ratios": dna_rev_ratios,
            "wc_rev_ratios": wc_rev_ratios,
            "period_label": f"FY_{periods[0].fiscal_year}",
        }

    # ------------------------------------------------------------------
    # Assumption builder
    # ------------------------------------------------------------------

    def _build_assumptions(
        self,
        hist: dict[str, Any],
        method: str,
        wacc: float,
        cost_of_equity: float | None,
        user_overrides: dict | None,
    ) -> dict[str, Any]:
        """Construct full assumptions dict, merging defaults with user overrides.

        Default logic:
        - Revenue growth: 3Y historical CAGR, fading linearly to terminal growth
        - EBIT margin: 3Y average, held constant
        - CapEx/Rev, D&A/Rev, WC/Rev: historical averages
        - Terminal growth: 2.5%
        - Projection years: 5
        """
        projection_years = _DEFAULT_PROJECTION_YEARS
        terminal_growth = _DEFAULT_TERMINAL_GROWTH

        # Discount rate selection
        if method == "FCFE":
            discount_rate = cost_of_equity if cost_of_equity is not None else wacc
        else:
            discount_rate = wacc

        # Revenue growth: historical CAGR
        rev_series = hist["rev_series"]
        num_hist_years = len(rev_series)
        if num_hist_years >= 2:
            hist_cagr = cagr(rev_series[-1], rev_series[0], num_hist_years - 1)
        else:
            hist_cagr = None

        if hist_cagr is None or hist_cagr < -0.20 or hist_cagr > 0.50:
            # Clamp to reasonable range or use moderate default
            base_growth = 0.05
        else:
            base_growth = hist_cagr

        # Build fading growth path: year 1 = base_growth, year N = terminal_growth
        growth_path: list[float] = []
        for yr in range(projection_years):
            if projection_years > 1:
                fade_factor = yr / (projection_years - 1)
            else:
                fade_factor = 1.0
            g = base_growth * (1.0 - fade_factor) + terminal_growth * fade_factor
            growth_path.append(round(g, 4))

        # EBIT margin: average of available historical
        ebit_margins = hist["ebit_margins"]
        if ebit_margins:
            avg_ebit_margin = sum(ebit_margins) / len(ebit_margins)
        else:
            avg_ebit_margin = hist["ebit"] / hist["revenue"] if hist["revenue"] > 0 else 0.10

        # Ratio averages
        def _avg(lst: list[float], default: float) -> float:
            return sum(lst) / len(lst) if lst else default

        capex_rev = _avg(hist["capex_rev_ratios"], hist["capex"] / hist["revenue"] if hist["revenue"] > 0 else 0.05)
        dna_rev = _avg(hist["dna_rev_ratios"], hist["dna"] / hist["revenue"] if hist["revenue"] > 0 else 0.03)
        wc_rev = _avg(hist["wc_rev_ratios"], hist["wc"] / hist["revenue"] if hist["revenue"] > 0 else 0.10)

        # Cap terminal growth below discount rate
        if terminal_growth >= discount_rate - _MIN_WACC_TERMINAL_GAP:
            terminal_growth = discount_rate - _MIN_WACC_TERMINAL_GAP
            if terminal_growth < 0:
                terminal_growth = 0.0

        assumptions = {
            "method": method,
            "projection_years": projection_years,
            "terminal_growth": round(terminal_growth, 4),
            "discount_rate": round(discount_rate, 4),
            "wacc": round(wacc, 4),
            "cost_of_equity": round(cost_of_equity, 4) if cost_of_equity is not None else None,
            "base_revenue": hist["revenue"],
            "revenue_growth_path": growth_path,
            "ebit_margin": round(avg_ebit_margin, 4),
            "tax_rate": round(hist["tax_rate"], 4),
            "capex_to_revenue": round(capex_rev, 4),
            "dna_to_revenue": round(dna_rev, 4),
            "wc_to_revenue": round(wc_rev, 4),
            "terminal_method": "GORDON_GROWTH",
            "terminal_exit_multiple": None,
            "leverage_target": None,  # [Bug 21] will be resolved in _project_fcfe if still None
            "historical_cagr": round(hist_cagr, 4) if hist_cagr is not None else None,
            "historical_years": num_hist_years,
        }

        # Apply user overrides
        if user_overrides:
            for key in (
                "projection_years", "terminal_growth", "discount_rate",
                "revenue_growth_path", "ebit_margin", "tax_rate",
                "capex_to_revenue", "dna_to_revenue", "wc_to_revenue",
                "terminal_method", "terminal_exit_multiple", "leverage_target",
            ):
                if key in user_overrides:
                    assumptions[key] = user_overrides[key]

            # Re-validate terminal growth vs discount rate after overrides
            tg = assumptions["terminal_growth"]
            dr = assumptions["discount_rate"]
            if tg >= dr - _MIN_WACC_TERMINAL_GAP:
                assumptions["terminal_growth"] = dr - _MIN_WACC_TERMINAL_GAP
                if assumptions["terminal_growth"] < 0:
                    assumptions["terminal_growth"] = 0.0

        return assumptions

    # ------------------------------------------------------------------
    # FCFF projection
    # ------------------------------------------------------------------

    def _project_fcff(
        self,
        hist: dict[str, Any],
        assumptions: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Project FCFF for the explicit forecast period and compute values.

        FCFF = EBIT * (1 - t) + D&A - CapEx - Delta WC
        """
        n = assumptions["projection_years"]
        growth_path = assumptions["revenue_growth_path"]
        ebit_margin = assumptions["ebit_margin"]
        tax_rate = assumptions["tax_rate"]
        capex_rev = assumptions["capex_to_revenue"]
        dna_rev = assumptions["dna_to_revenue"]
        wc_rev = assumptions["wc_to_revenue"]
        discount_rate = assumptions["discount_rate"]
        terminal_growth = assumptions["terminal_growth"]

        base_revenue = hist["revenue"]

        projected_fcfs: list[float] = []
        projected_revenues: list[float] = []
        prev_wc = hist["wc"]

        revenue = base_revenue
        for yr in range(n):
            g = growth_path[yr] if yr < len(growth_path) else growth_path[-1]
            revenue = revenue * (1.0 + g)
            projected_revenues.append(revenue)

            ebit = revenue * ebit_margin
            nopat = ebit * (1.0 - tax_rate)
            dna = revenue * dna_rev
            capex = revenue * capex_rev
            wc = revenue * wc_rev
            delta_wc = wc - prev_wc
            prev_wc = wc

            fcff = nopat + dna - capex - delta_wc
            projected_fcfs.append(round(fcff, 2))

        # Discount explicit-period FCFs
        pv_explicit = 0.0
        for yr_idx, fcf in enumerate(projected_fcfs):
            pv_explicit += fcf / ((1.0 + discount_rate) ** (yr_idx + 1))

        # Terminal value
        last_fcf = projected_fcfs[-1]
        terminal_method = assumptions.get("terminal_method", "GORDON_GROWTH")

        if terminal_method == "EXIT_MULTIPLE":
            # [Bug 22 fix] Exit multiple terminal value: TV = terminal EBITDA × multiple
            exit_multiple = assumptions.get("terminal_exit_multiple")
            if exit_multiple is None:
                exit_multiple = _DEFAULT_EXIT_MULTIPLE
                logger.info(
                    "DCF FCFF: no exit_multiple provided, using sector median "
                    "default EV/EBITDA of %.1fx", exit_multiple,
                )
            # Terminal EBITDA = last projected revenue × EBIT margin + D&A
            last_revenue = projected_revenues[-1]
            terminal_ebitda = last_revenue * ebit_margin + last_revenue * dna_rev
            terminal_value = terminal_ebitda * exit_multiple
        else:
            # Gordon Growth: TV = FCF_last × (1 + g) / (r - g)
            denom = discount_rate - terminal_growth
            if denom <= 0:
                # Should not happen after assumption capping, but guard anyway
                logger.warning("DCF FCFF: discount_rate <= terminal_growth, cannot compute TV")
                return None
            terminal_value = last_fcf * (1.0 + terminal_growth) / denom

        pv_terminal = terminal_value / ((1.0 + discount_rate) ** n)

        return {
            "projected_fcfs": projected_fcfs,
            "projected_revenues": projected_revenues,
            "pv_explicit": round(pv_explicit, 2),
            "terminal_value": round(terminal_value, 2),
            "pv_terminal": round(pv_terminal, 2),
            "last_fcf": last_fcf,
        }

    # ------------------------------------------------------------------
    # FCFE projection
    # ------------------------------------------------------------------

    def _project_fcfe(
        self,
        hist: dict[str, Any],
        assumptions: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Project FCFE for the explicit forecast period and compute values.

        FCFE = Net Income + D&A - CapEx - Delta WC + Net Borrowing
        """
        n = assumptions["projection_years"]
        growth_path = assumptions["revenue_growth_path"]
        ebit_margin = assumptions["ebit_margin"]
        tax_rate = assumptions["tax_rate"]
        capex_rev = assumptions["capex_to_revenue"]
        dna_rev = assumptions["dna_to_revenue"]
        wc_rev = assumptions["wc_to_revenue"]
        discount_rate = assumptions["discount_rate"]
        terminal_growth = assumptions["terminal_growth"]

        base_revenue = hist["revenue"]

        # Estimate net income margin from latest data
        ni_margin = safe_divide(hist["net_income"], base_revenue) or (ebit_margin * (1 - tax_rate))

        # [Bug 21 fix] Fade net borrowing ratio toward target over projection period
        nb_rev = safe_divide(hist["net_borrowing"], base_revenue) or 0.0
        leverage_target = assumptions.get("leverage_target")
        if leverage_target is None:
            leverage_target = nb_rev * 0.5  # default: halve current leverage

        projected_fcfs: list[float] = []
        projected_revenues: list[float] = []
        prev_wc = hist["wc"]

        revenue = base_revenue
        for yr in range(n):
            g = growth_path[yr] if yr < len(growth_path) else growth_path[-1]
            revenue = revenue * (1.0 + g)
            projected_revenues.append(revenue)

            net_income = revenue * ni_margin
            dna = revenue * dna_rev
            capex = revenue * capex_rev
            wc = revenue * wc_rev
            delta_wc = wc - prev_wc
            prev_wc = wc
            # Fade nb_rev linearly from current value to leverage_target
            fade_factor = (yr + 1) / n
            nb_rev_yr = nb_rev + (leverage_target - nb_rev) * fade_factor
            net_borrowing = revenue * nb_rev_yr

            fcfe = net_income + dna - capex - delta_wc + net_borrowing
            projected_fcfs.append(round(fcfe, 2))

        # Discount explicit-period FCFs
        pv_explicit = 0.0
        for yr_idx, fcf in enumerate(projected_fcfs):
            pv_explicit += fcf / ((1.0 + discount_rate) ** (yr_idx + 1))

        # Terminal value
        last_fcf = projected_fcfs[-1]
        terminal_method = assumptions.get("terminal_method", "GORDON_GROWTH")

        if terminal_method == "EXIT_MULTIPLE":
            # [Bug 22 fix] Exit multiple terminal value: TV = terminal EBITDA × multiple
            exit_multiple = assumptions.get("terminal_exit_multiple")
            if exit_multiple is None:
                exit_multiple = _DEFAULT_EXIT_MULTIPLE
                logger.info(
                    "DCF FCFE: no exit_multiple provided, using sector median "
                    "default EV/EBITDA of %.1fx", exit_multiple,
                )
            # Terminal EBITDA = last projected revenue × EBIT margin + D&A
            last_revenue = projected_revenues[-1]
            terminal_ebitda = last_revenue * ebit_margin + last_revenue * dna_rev
            terminal_value = terminal_ebitda * exit_multiple
        else:
            # Gordon Growth: TV = FCF_last × (1 + g) / (r - g)
            denom = discount_rate - terminal_growth
            if denom <= 0:
                logger.warning("DCF FCFE: discount_rate <= terminal_growth, cannot compute TV")
                return None
            terminal_value = last_fcf * (1.0 + terminal_growth) / denom

        pv_terminal = terminal_value / ((1.0 + discount_rate) ** n)

        return {
            "projected_fcfs": projected_fcfs,
            "projected_revenues": projected_revenues,
            "pv_explicit": round(pv_explicit, 2),
            "terminal_value": round(terminal_value, 2),
            "pv_terminal": round(pv_terminal, 2),
            "last_fcf": last_fcf,
        }

    # ------------------------------------------------------------------
    # Net debt
    # ------------------------------------------------------------------

    def _compute_net_debt(self, hist: dict[str, Any]) -> float:
        """Net Debt = Total Debt - Cash."""
        return hist["total_debt"] - hist["cash"]

    # ------------------------------------------------------------------
    # Valuation classification
    # ------------------------------------------------------------------

    def _classify_valuation(self, upside_downside: float | None) -> str:
        """Classify implied vs current price."""
        if upside_downside is None:
            return "UNKNOWN"
        if upside_downside > _UNDERVALUED_THRESHOLD:
            return "UNDERVALUED"
        if upside_downside < _OVERVALUED_THRESHOLD:
            return "OVERVALUED"
        return "FAIRLY_VALUED"

    # ------------------------------------------------------------------
    # Sensitivity grid
    # ------------------------------------------------------------------

    def _build_sensitivity_grid(
        self,
        last_fcf: float,
        base_ev: float,
        net_debt: float,
        shares: float | None,
        base_discount: float,
        base_terminal_growth: float,
        projection_years: int,
        projected_fcfs: list[float] | None = None,
    ) -> dict[str, Any]:
        """Build a 7x7 sensitivity table varying discount rate and terminal growth.

        [Bug 19 fix] Re-discounts ALL explicit-period FCFs plus a new terminal
        value at each (WACC, growth) combination.  The previous implementation
        only varied the terminal value while keeping explicit-period PV fixed,
        which produced incorrect implied prices.

        Returns a dict with:
            wacc_values: list of discount rates tested
            growth_values: list of terminal growth rates tested
            implied_prices: 7x7 nested list  (row=wacc, col=growth)
        """
        # Build axis values
        wacc_values: list[float] = []
        half_steps = _SENSITIVITY_WACC_STEPS // 2
        for i in range(-half_steps, half_steps + 1):
            w = base_discount + i * (_SENSITIVITY_WACC_RANGE / half_steps)
            wacc_values.append(round(w, 4))

        growth_values: list[float] = []
        half_g = _SENSITIVITY_GROWTH_STEPS // 2
        for i in range(-half_g, half_g + 1):
            g = base_terminal_growth + i * (_SENSITIVITY_GROWTH_RANGE / half_g)
            growth_values.append(round(max(g, 0.0), 4))

        # Use actual projected FCFs if available; otherwise just use last_fcf
        fcfs = projected_fcfs if projected_fcfs else [last_fcf] * projection_years

        grid: list[list[float | None]] = []
        for w in wacc_values:
            row: list[float | None] = []
            for g in growth_values:
                # Ensure g < w
                if g >= w - _MIN_WACC_TERMINAL_GAP:
                    row.append(None)
                    continue

                # [Bug 19 fix] Full DCF re-computation per grid cell
                # 1. Re-discount all explicit-period FCFs at new WACC
                pv_explicit = 0.0
                for yr_idx, fcf in enumerate(fcfs):
                    pv_explicit += fcf / ((1.0 + w) ** (yr_idx + 1))

                # 2. Gordon Growth terminal value with new growth
                tv = last_fcf * (1.0 + g) / (w - g)
                pv_tv = tv / ((1.0 + w) ** projection_years)

                # 3. Enterprise value → equity value → per-share price
                ev_new = pv_explicit + pv_tv
                eq_new = ev_new - net_debt

                if shares is not None and shares > 0:
                    ip = round(eq_new / shares, 2)
                    row.append(ip)
                else:
                    row.append(None)
            grid.append(row)

        return {
            "wacc_values": wacc_values,
            "growth_values": growth_values,
            "implied_prices": grid,
        }

    # ------------------------------------------------------------------
    # EngineOutput builder
    # ------------------------------------------------------------------

    def _build_outputs(
        self,
        *,
        security_id: UUID,
        entity_id: UUID,
        today: date,
        method: str,
        enterprise_value: float,
        equity_value: float,
        implied_price: float | None,
        current_price: float | None,
        upside_downside: float | None,
        discount_rate: float,
        terminal_value: float,
        terminal_pct: float | None,
        pv_explicit: float,
        pv_terminal: float,
        projection_years: int,
        terminal_growth: float,
        terminal_method: str,
        implied_vs_current: str,
        data_quality: str,
    ) -> list[EngineOutput]:
        """Construct the list of EngineOutput metrics."""
        outputs: list[EngineOutput] = []

        def _out(
            metric_name: str,
            value: float | None,
            unit: str = "CURRENCY",
            dq: str | None = None,
            inputs: list[dict] | None = None,
        ) -> EngineOutput:
            return EngineOutput(
                security_id=security_id,
                entity_id=entity_id,
                engine_id=self.engine_id,
                metric_name=metric_name,
                metric_category="VALUATION",
                value=value,
                unit=unit,
                period="LATEST",
                period_end_date=today,
                as_of_date=today,
                data_quality=dq or data_quality,
                inputs=inputs or [],
            )

        # Enterprise Value
        outputs.append(
            _out(
                "dcf_enterprise_value",
                enterprise_value,
                inputs=[
                    make_input("pv_explicit", "dcf_engine", pv_explicit),
                    make_input("pv_terminal", "dcf_engine", pv_terminal),
                ],
            )
        )

        # Equity Value
        outputs.append(
            _out(
                "dcf_equity_value",
                equity_value,
                inputs=[
                    make_input("enterprise_value", "dcf_engine", enterprise_value),
                    make_input("method", "dcf_engine", None),
                ],
            )
        )

        # Implied Price
        outputs.append(
            _out(
                "dcf_implied_price",
                implied_price,
                inputs=[
                    make_input("equity_value", "dcf_engine", equity_value),
                ],
            )
        )

        # Current Price
        outputs.append(
            _out(
                "dcf_current_price",
                current_price,
                inputs=[
                    make_input("close_adjusted", "eod_prices", current_price),
                ],
            )
        )

        # Upside / Downside
        outputs.append(
            _out(
                "dcf_upside_downside",
                upside_downside,
                unit="PERCENT",
                inputs=[
                    make_input("implied_price", "dcf_engine", implied_price),
                    make_input("current_price", "eod_prices", current_price),
                ],
            )
        )

        # WACC / Discount Rate Used
        outputs.append(
            _out(
                "dcf_wacc_used",
                discount_rate,
                unit="PERCENT",
                inputs=[
                    make_input("discount_rate", "wacc_results", discount_rate),
                ],
            )
        )

        # Terminal Value (undiscounted)
        outputs.append(
            _out(
                "dcf_terminal_value",
                terminal_value,
                inputs=[
                    make_input("terminal_growth", "dcf_engine", terminal_growth),
                    make_input("discount_rate", "dcf_engine", discount_rate),
                ],
            )
        )

        # Terminal Value as % of EV
        outputs.append(
            _out(
                "dcf_terminal_pct_of_ev",
                terminal_pct,
                unit="PERCENT",
                inputs=[
                    make_input("pv_terminal", "dcf_engine", pv_terminal),
                    make_input("enterprise_value", "dcf_engine", enterprise_value),
                ],
            )
        )

        # PV of Explicit Period
        outputs.append(
            _out(
                "dcf_pv_explicit",
                pv_explicit,
                inputs=[
                    make_input("projection_years", "dcf_engine", float(projection_years)),
                    make_input("discount_rate", "dcf_engine", discount_rate),
                ],
            )
        )

        # PV of Terminal Value
        outputs.append(
            _out(
                "dcf_pv_terminal",
                pv_terminal,
                inputs=[
                    make_input("terminal_value", "dcf_engine", terminal_value),
                    make_input("discount_rate", "dcf_engine", discount_rate),
                ],
            )
        )

        # Method (CLASSIFICATION — value=None, info in data_quality)
        outputs.append(
            _out(
                "dcf_method",
                None,
                unit="CLASSIFICATION",
                dq=method,
                inputs=[],
            )
        )

        # Projection Years
        outputs.append(
            _out(
                "dcf_projection_years",
                float(projection_years),
                unit="SCORE",
                inputs=[],
            )
        )

        # Terminal Method
        outputs.append(
            _out(
                "dcf_terminal_method",
                None,
                unit="CLASSIFICATION",
                dq=terminal_method,
                inputs=[],
            )
        )

        # Terminal Growth Rate
        outputs.append(
            _out(
                "dcf_terminal_growth",
                terminal_growth,
                unit="PERCENT",
                inputs=[],
            )
        )

        # Implied vs Current Classification
        outputs.append(
            _out(
                "dcf_implied_vs_current",
                None,
                unit="CLASSIFICATION",
                dq=implied_vs_current,
                inputs=[
                    make_input("upside_downside", "dcf_engine", upside_downside),
                ],
            )
        )

        return outputs
