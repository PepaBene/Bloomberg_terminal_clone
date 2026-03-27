"""E1 – Financial Statement Analysis Engine.

Computes 200+ financial ratios organised into eight categories:
Profitability, Leverage, Efficiency, Growth, Per-Share, Cash-Flow Quality,
Capital Allocation, and Dividend.  Every output carries full input lineage
so downstream engines and the API layer can trace any derived number back
to its source Pillar 1 data points.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.engines.base import BaseEngine, EngineOutput, cagr, make_input, pct_change, safe_divide
from src.models.estimates import ConsensusEstimate
from src.models.fundamentals import BalanceSheet, CashFlowStatement, FinancialPeriod, IncomeStatement
from src.models.security import EODPrice, EquityDetails, Security

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal data containers
# ---------------------------------------------------------------------------

class _FinancialSnapshot:
    """Convenience wrapper around a FinancialPeriod and its statements."""

    __slots__ = (
        "period", "inc", "bs", "cf",
        "period_label", "period_end_date",
    )

    def __init__(self, period: FinancialPeriod) -> None:
        self.period = period
        self.inc: IncomeStatement | None = period.income_statement
        self.bs: BalanceSheet | None = period.balance_sheet
        self.cf: CashFlowStatement | None = period.cash_flow
        self.period_end_date: date = period.period_end_date
        pt = period.period_type or "FY"
        fy = period.fiscal_year
        fq = period.fiscal_quarter
        if pt.upper() in ("TTM", "LTM"):
            self.period_label = "TTM"
        elif fq is not None:
            self.period_label = f"Q{fq}_{fy}"
        else:
            self.period_label = f"FY_{fy}"

    # Convenience accessors – return None when the sub-statement is missing
    def iv(self, field: str) -> float | None:
        """Income-statement value."""
        if self.inc is None:
            return None
        return getattr(self.inc, field, None)

    def bv(self, field: str) -> float | None:
        """Balance-sheet value."""
        if self.bs is None:
            return None
        return getattr(self.bs, field, None)

    def cv(self, field: str) -> float | None:
        """Cash-flow-statement value."""
        if self.cf is None:
            return None
        return getattr(self.cf, field, None)


class _PriceSnapshot:
    """Latest market-data snapshot for a security."""

    __slots__ = ("close", "market_cap", "shares_diluted", "shares_basic", "price_date")

    def __init__(
        self,
        close: float | None = None,
        market_cap: float | None = None,
        shares_diluted: float | None = None,
        shares_basic: float | None = None,
        price_date: date | None = None,
    ) -> None:
        self.close = close
        self.market_cap = market_cap
        self.shares_diluted = shares_diluted
        self.shares_basic = shares_basic
        self.price_date = price_date


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class RatioEngine(BaseEngine):
    """E1 – Financial Statement Analysis.

    Computes profitability, leverage, efficiency, growth, per-share,
    cash-flow quality, capital-allocation, and dividend ratios from
    Pillar 1 fundamentals and market data.
    """

    engine_id: str = "E1"
    engine_name: str = "Financial Statement Analysis"
    engine_version: str = "1.0.0"

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def compute(
        self,
        session: Any,
        security_id: UUID,
        **kwargs: Any,
    ) -> list[EngineOutput]:
        """Compute all financial ratios for *security_id*."""

        # Resolve entity
        entity_id = await self._resolve_entity(session, security_id)
        if entity_id is None:
            logger.warning("E1: no entity mapping for security %s", security_id)
            return []

        # Load financial data (latest + history for growth)
        snapshots = await self._load_financials(session, entity_id)
        if not snapshots:
            logger.warning("E1: no financial periods for entity %s", entity_id)
            return []

        latest = snapshots[0]

        # Load price data
        price = await self._load_price(session, security_id, latest)

        # Load forward EPS estimate (best-effort)
        fwd_eps = await self._load_forward_eps(session, security_id)

        # Build outputs from each category
        outputs: list[EngineOutput] = []
        ctx = _ComputeContext(
            security_id=security_id,
            entity_id=entity_id,
            latest=latest,
            snapshots=snapshots,
            price=price,
            fwd_eps=fwd_eps,
        )

        outputs.extend(self._profitability(ctx))
        outputs.extend(self._leverage(ctx))
        outputs.extend(self._efficiency(ctx))
        outputs.extend(self._growth(ctx))
        outputs.extend(self._per_share(ctx))
        outputs.extend(self._cash_flow_quality(ctx))
        outputs.extend(self._capital_allocation(ctx))
        outputs.extend(self._dividend(ctx))

        logger.info(
            "E1: computed %d ratios for security %s (entity %s)",
            len(outputs), security_id, entity_id,
        )
        return outputs

    # ------------------------------------------------------------------
    # Data loaders
    # ------------------------------------------------------------------

    async def _resolve_entity(self, session: Any, security_id: UUID) -> UUID | None:
        stmt = select(Security.issuer_entity_id).where(Security.security_id == security_id)
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        return row

    async def _load_financials(
        self,
        session: Any,
        entity_id: UUID,
        limit: int = 21,
    ) -> list[_FinancialSnapshot]:
        """Load up to *limit* most-recent financial periods (desc by date).

        We load 21 periods to support 5-year CAGR (needing at least 6 annual
        periods) plus some margin for quarterly data.
        """
        stmt = (
            select(FinancialPeriod)
            .where(FinancialPeriod.entity_id == entity_id)
            .options(
                selectinload(FinancialPeriod.income_statement),
                selectinload(FinancialPeriod.balance_sheet),
                selectinload(FinancialPeriod.cash_flow),
            )
            .order_by(FinancialPeriod.period_end_date.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        periods = result.scalars().all()
        return [_FinancialSnapshot(p) for p in periods]

    async def _load_price(
        self,
        session: Any,
        security_id: UUID,
        latest: _FinancialSnapshot,
    ) -> _PriceSnapshot:
        """Load most-recent EOD price and share counts."""
        stmt = (
            select(EODPrice)
            .where(EODPrice.security_id == security_id)
            .order_by(EODPrice.price_date.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        eod: EODPrice | None = result.scalar_one_or_none()

        # Shares from equity details (authoritative share count)
        eq_stmt = select(EquityDetails).where(EquityDetails.security_id == security_id)
        eq_result = await session.execute(eq_stmt)
        eq: EquityDetails | None = eq_result.scalar_one_or_none()

        close = float(eod.close_adjusted) if eod and eod.close_adjusted is not None else None
        price_date = eod.price_date if eod else None

        # Prefer diluted shares from income statement, fallback to equity details
        shares_diluted = latest.iv("diluted_shares_outstanding")
        shares_basic = latest.iv("basic_shares_outstanding")
        if shares_diluted is None and eq is not None:
            shares_diluted = float(eq.shares_outstanding) if eq.shares_outstanding else None
        if shares_basic is None and eq is not None:
            shares_basic = float(eq.shares_outstanding) if eq.shares_outstanding else None

        market_cap: float | None = None
        if close is not None and shares_diluted is not None:
            market_cap = close * float(shares_diluted)

        return _PriceSnapshot(
            close=close,
            market_cap=market_cap,
            shares_diluted=float(shares_diluted) if shares_diluted is not None else None,
            shares_basic=float(shares_basic) if shares_basic is not None else None,
            price_date=price_date,
        )

    async def _load_forward_eps(
        self,
        session: Any,
        security_id: UUID,
    ) -> float | None:
        """Load the latest forward EPS consensus estimate."""
        today = date.today()
        stmt = (
            select(ConsensusEstimate.mean)
            .where(
                ConsensusEstimate.security_id == security_id,
                ConsensusEstimate.metric == "EPS",
                ConsensusEstimate.period_end_date >= today,
            )
            .order_by(ConsensusEstimate.period_end_date.asc())
            .limit(1)
        )
        result = await session.execute(stmt)
        val = result.scalar_one_or_none()
        return float(val) if val is not None else None

    # ------------------------------------------------------------------
    # Snapshot history helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _prior(snapshots: list[_FinancialSnapshot], years_back: int) -> _FinancialSnapshot | None:
        """Find the snapshot approximately *years_back* years before the latest.

        Uses simple heuristic: look for a period whose end date is within
        a 45-day window of (latest_date - years_back * 365).
        """
        if not snapshots:
            return None
        target = snapshots[0].period_end_date
        target_ordinal = target.toordinal() - years_back * 365
        best: _FinancialSnapshot | None = None
        best_diff = 9999
        for s in snapshots[1:]:
            diff = abs(s.period_end_date.toordinal() - target_ordinal)
            if diff < best_diff:
                best_diff = diff
                best = s
        if best is not None and best_diff <= 45:
            return best
        return None

    # ------------------------------------------------------------------
    # Output builder
    # ------------------------------------------------------------------

    def _out(
        self,
        ctx: _ComputeContext,
        name: str,
        category: str,
        value: float | None,
        unit: str = "RATIO",
        period: str | None = None,
        quality: str | None = None,
        inputs: list[dict] | None = None,
    ) -> EngineOutput:
        return EngineOutput(
            security_id=ctx.security_id,
            entity_id=ctx.entity_id,
            engine_id=self.engine_id,
            metric_name=name,
            metric_category=category,
            value=value,
            unit=unit,
            period=period or ctx.latest.period_label,
            period_end_date=ctx.latest.period_end_date,
            as_of_date=date.today(),
            data_quality=quality or ("COMPLETE" if value is not None else "INSUFFICIENT_DATA"),
            inputs=inputs,
            calculation_version=self.engine_version,
        )

    # ==================================================================
    # CATEGORY 1: PROFITABILITY
    # ==================================================================

    def _profitability(self, ctx: _ComputeContext) -> list[EngineOutput]:
        CAT = "PROFITABILITY"
        s = ctx.latest
        out: list[EngineOutput] = []

        revenue = s.iv("total_revenue")
        cogs = s.iv("cost_of_revenue")
        gross = s.iv("gross_profit")
        op_inc = s.iv("operating_income")
        ebitda = s.iv("ebitda")
        net_inc = s.iv("net_income")
        net_common = s.iv("net_income_to_common")
        pretax = s.iv("pretax_income")
        interest = s.iv("interest_expense")
        tax = s.iv("income_tax_expense")
        da = s.iv("depreciation_amortization")
        rd = s.iv("research_development")
        sga = s.iv("selling_general_admin")
        sbc = s.iv("stock_based_compensation")
        eff_tax = s.iv("effective_tax_rate")

        total_assets = s.bv("total_assets")
        total_equity = s.bv("total_equity")
        common_equity = s.bv("total_common_equity")
        total_debt = s.bv("total_debt")
        tangible_bv = s.bv("tangible_book_value")
        cash = s.bv("cash_and_equivalents")
        goodwill = s.bv("goodwill")
        intangibles = s.bv("intangible_assets")

        ocf = s.cv("cash_from_operations")
        fcf = s.cv("free_cash_flow")

        def _mi(pairs: list[tuple[str, float | None]]) -> list[dict]:
            return [make_input(n, "fundamentals", v, s.period_label) for n, v in pairs]

        # -- Margin ratios --
        gross_margin = safe_divide(gross, revenue)
        out.append(self._out(ctx, "gross_margin", CAT, gross_margin, "PERCENT",
                             inputs=_mi([("gross_profit", gross), ("total_revenue", revenue)])))

        op_margin = safe_divide(op_inc, revenue)
        out.append(self._out(ctx, "operating_margin", CAT, op_margin, "PERCENT",
                             inputs=_mi([("operating_income", op_inc), ("total_revenue", revenue)])))

        ebitda_margin = safe_divide(ebitda, revenue)
        out.append(self._out(ctx, "ebitda_margin", CAT, ebitda_margin, "PERCENT",
                             inputs=_mi([("ebitda", ebitda), ("total_revenue", revenue)])))

        net_margin = safe_divide(net_inc, revenue)
        out.append(self._out(ctx, "net_margin", CAT, net_margin, "PERCENT",
                             inputs=_mi([("net_income", net_inc), ("total_revenue", revenue)])))

        pretax_margin = safe_divide(pretax, revenue)
        out.append(self._out(ctx, "pretax_margin", CAT, pretax_margin, "PERCENT",
                             inputs=_mi([("pretax_income", pretax), ("total_revenue", revenue)])))

        # EBIT margin (operating_income is EBIT proxy)
        ebit_margin = safe_divide(op_inc, revenue)
        out.append(self._out(ctx, "ebit_margin", CAT, ebit_margin, "PERCENT",
                             inputs=_mi([("operating_income", op_inc), ("total_revenue", revenue)])))

        # Net income margin adjusted (uses net_income_to_common)
        net_margin_adj = safe_divide(net_common, revenue)
        out.append(self._out(ctx, "net_income_margin_adj", CAT, net_margin_adj, "PERCENT",
                             inputs=_mi([("net_income_to_common", net_common), ("total_revenue", revenue)])))

        # NOPAT margin: operating_income * (1 - tax_rate)
        nopat: float | None = None
        if op_inc is not None and eff_tax is not None:
            nopat = float(op_inc) * (1.0 - float(eff_tax))
        elif op_inc is not None and tax is not None and pretax is not None and pretax != 0:
            implied_tax = float(tax) / float(pretax)
            nopat = float(op_inc) * (1.0 - implied_tax)
        nopat_margin = safe_divide(nopat, revenue)
        out.append(self._out(ctx, "nopat_margin", CAT, nopat_margin, "PERCENT",
                             inputs=_mi([("operating_income", op_inc), ("effective_tax_rate", eff_tax),
                                         ("total_revenue", revenue)])))

        # FCF margin
        fcf_margin = safe_divide(fcf, revenue)
        out.append(self._out(ctx, "fcf_margin", CAT, fcf_margin, "PERCENT",
                             inputs=_mi([("free_cash_flow", fcf), ("total_revenue", revenue)])))

        # -- Return ratios --
        roe = safe_divide(net_inc, total_equity)
        equity_quality = "COMPLETE"
        if total_equity is not None and float(total_equity) < 0:
            equity_quality = "NEGATIVE_EQUITY"
        out.append(self._out(ctx, "roe", CAT, roe, "PERCENT", quality=equity_quality if roe is not None else None,
                             inputs=_mi([("net_income", net_inc), ("total_equity", total_equity)])))

        roa = safe_divide(net_inc, total_assets)
        out.append(self._out(ctx, "roa", CAT, roa, "PERCENT",
                             inputs=_mi([("net_income", net_inc), ("total_assets", total_assets)])))

        # ROIC = NOPAT / invested_capital, where invested_capital = total_equity + total_debt - cash
        invested_capital: float | None = None
        if total_equity is not None and total_debt is not None:
            ic = float(total_equity) + float(total_debt)
            if cash is not None:
                ic -= float(cash)
            invested_capital = ic
        roic = safe_divide(nopat, invested_capital)
        out.append(self._out(ctx, "roic", CAT, roic, "PERCENT",
                             inputs=_mi([("nopat", nopat), ("total_equity", total_equity),
                                         ("total_debt", total_debt), ("cash_and_equivalents", cash)])))

        # ROCE = EBIT / capital_employed, capital_employed = total_assets - current_liabilities
        cur_liab = s.bv("total_current_liabilities")
        capital_employed: float | None = None
        if total_assets is not None and cur_liab is not None:
            capital_employed = float(total_assets) - float(cur_liab)
        roce = safe_divide(op_inc, capital_employed)
        out.append(self._out(ctx, "roce", CAT, roce, "PERCENT",
                             inputs=_mi([("operating_income", op_inc), ("total_assets", total_assets),
                                         ("total_current_liabilities", cur_liab)])))

        # Return on tangible equity
        rote = safe_divide(net_inc, tangible_bv)
        out.append(self._out(ctx, "return_on_tangible_equity", CAT, rote, "PERCENT",
                             inputs=_mi([("net_income", net_inc), ("tangible_book_value", tangible_bv)])))

        # ROIC adjusted (uses net_income_to_common instead of NOPAT)
        roic_adj = safe_divide(net_common, invested_capital)
        out.append(self._out(ctx, "return_on_invested_capital_adj", CAT, roic_adj, "PERCENT",
                             inputs=_mi([("net_income_to_common", net_common),
                                         ("invested_capital", invested_capital)])))

        # Cash return on assets = OCF / total_assets
        cash_roa = safe_divide(ocf, total_assets)
        out.append(self._out(ctx, "cash_return_on_assets", CAT, cash_roa, "PERCENT",
                             inputs=_mi([("cash_from_operations", ocf), ("total_assets", total_assets)])))

        # -- Expense ratios --
        research_intensity = safe_divide(rd, revenue)
        out.append(self._out(ctx, "research_intensity", CAT, research_intensity, "PERCENT",
                             inputs=_mi([("research_development", rd), ("total_revenue", revenue)])))

        sga_ratio = safe_divide(sga, revenue)
        out.append(self._out(ctx, "sga_ratio", CAT, sga_ratio, "PERCENT",
                             inputs=_mi([("selling_general_admin", sga), ("total_revenue", revenue)])))

        cost_rev_ratio = safe_divide(cogs, revenue)
        out.append(self._out(ctx, "cost_of_revenue_ratio", CAT, cost_rev_ratio, "PERCENT",
                             inputs=_mi([("cost_of_revenue", cogs), ("total_revenue", revenue)])))

        # Operating expense ratio = (revenue - operating_income) / revenue = 1 - operating_margin
        opex_ratio: float | None = None
        if revenue is not None and op_inc is not None and float(revenue) != 0:
            opex_ratio = (float(revenue) - float(op_inc)) / float(revenue)
        out.append(self._out(ctx, "operating_expense_ratio", CAT, opex_ratio, "PERCENT",
                             inputs=_mi([("total_revenue", revenue), ("operating_income", op_inc)])))

        # Tax rate effective (pass-through from statement)
        eff_tax_val = float(eff_tax) if eff_tax is not None else None
        out.append(self._out(ctx, "tax_rate_effective", CAT, eff_tax_val, "PERCENT",
                             inputs=_mi([("effective_tax_rate", eff_tax)])))

        # Operating leverage (approximation): operating_income growth / revenue growth
        prior_1y = self._prior(ctx.snapshots, 1)
        op_lev: float | None = None
        if prior_1y is not None:
            rev_prior = prior_1y.iv("total_revenue")
            op_prior = prior_1y.iv("operating_income")
            rev_chg = pct_change(revenue, rev_prior)
            op_chg = pct_change(op_inc, op_prior)
            op_lev = safe_divide(op_chg, rev_chg)
        out.append(self._out(ctx, "operating_leverage", CAT, op_lev, "RATIO",
                             inputs=_mi([("operating_income", op_inc), ("total_revenue", revenue)])))

        # Earnings yield = net_income / market_cap (inverse P/E)
        market_cap = ctx.price.market_cap
        earnings_yield = safe_divide(net_inc, market_cap)
        mkt_input = make_input("market_cap", "market_data", market_cap, "LATEST")
        out.append(self._out(ctx, "earnings_yield", CAT, earnings_yield, "PERCENT",
                             inputs=_mi([("net_income", net_inc)]) + [mkt_input]))

        # EBITDA to interest expense
        ebitda_to_int = safe_divide(ebitda, interest)
        out.append(self._out(ctx, "ebitda_to_interest", CAT, ebitda_to_int, "RATIO",
                             inputs=_mi([("ebitda", ebitda), ("interest_expense", interest)])))

        return out

    # ==================================================================
    # CATEGORY 2: LEVERAGE
    # ==================================================================

    def _leverage(self, ctx: _ComputeContext) -> list[EngineOutput]:
        CAT = "LEVERAGE"
        s = ctx.latest
        out: list[EngineOutput] = []

        total_debt = s.bv("total_debt")
        total_equity = s.bv("total_equity")
        total_assets = s.bv("total_assets")
        cur_assets = s.bv("total_current_assets")
        cur_liab = s.bv("total_current_liabilities")
        net_debt = s.bv("net_debt")
        cash = s.bv("cash_and_equivalents")
        cash_st = s.bv("cash_and_short_term")
        inventory = s.bv("inventory")
        lt_debt = s.bv("long_term_debt")
        st_debt = s.bv("short_term_debt")

        ebitda = s.iv("ebitda")
        op_inc = s.iv("operating_income")
        interest = s.iv("interest_expense")

        ocf = s.cv("cash_from_operations")

        def _mi(pairs: list[tuple[str, float | None]]) -> list[dict]:
            return [make_input(n, "fundamentals", v, s.period_label) for n, v in pairs]

        # Quality flag for negative equity
        equity_quality = None
        if total_equity is not None and float(total_equity) < 0:
            equity_quality = "NEGATIVE_EQUITY"

        # Debt-to-equity
        d_e = safe_divide(total_debt, total_equity)
        out.append(self._out(ctx, "debt_to_equity", CAT, d_e, "RATIO",
                             quality=equity_quality if d_e is not None else None,
                             inputs=_mi([("total_debt", total_debt), ("total_equity", total_equity)])))

        # Debt-to-assets
        d_a = safe_divide(total_debt, total_assets)
        out.append(self._out(ctx, "debt_to_assets", CAT, d_a, "RATIO",
                             inputs=_mi([("total_debt", total_debt), ("total_assets", total_assets)])))

        # Net debt to EBITDA
        nd_ebitda: float | None = None
        nd_quality = None
        if ebitda is not None and float(ebitda) <= 0:
            nd_ebitda = None
            nd_quality = "EBITDA_NON_POSITIVE"
        else:
            nd_ebitda = safe_divide(net_debt, ebitda)
        out.append(self._out(ctx, "net_debt_to_ebitda", CAT, nd_ebitda, "RATIO",
                             quality=nd_quality,
                             inputs=_mi([("net_debt", net_debt), ("ebitda", ebitda)])))

        # Interest coverage = EBIT / interest_expense
        int_cov: float | None = None
        int_quality = None
        if interest is not None and float(interest) == 0:
            int_cov = None
            int_quality = "NO_INTEREST_EXPENSE"
        else:
            int_cov = safe_divide(op_inc, interest)
        out.append(self._out(ctx, "interest_coverage", CAT, int_cov, "RATIO",
                             quality=int_quality,
                             inputs=_mi([("operating_income", op_inc), ("interest_expense", interest)])))

        # Equity multiplier = total_assets / total_equity
        eq_mult = safe_divide(total_assets, total_equity)
        out.append(self._out(ctx, "equity_multiplier", CAT, eq_mult, "RATIO",
                             quality=equity_quality if eq_mult is not None else None,
                             inputs=_mi([("total_assets", total_assets), ("total_equity", total_equity)])))

        # Current ratio
        current_ratio = safe_divide(cur_assets, cur_liab)
        out.append(self._out(ctx, "current_ratio", CAT, current_ratio, "RATIO",
                             inputs=_mi([("total_current_assets", cur_assets),
                                         ("total_current_liabilities", cur_liab)])))

        # Quick ratio = (current_assets - inventory) / current_liabilities
        quick: float | None = None
        if cur_assets is not None and cur_liab is not None and float(cur_liab) != 0:
            inv_val = float(inventory) if inventory is not None else 0.0
            quick = (float(cur_assets) - inv_val) / float(cur_liab)
        out.append(self._out(ctx, "quick_ratio", CAT, quick, "RATIO",
                             inputs=_mi([("total_current_assets", cur_assets),
                                         ("inventory", inventory),
                                         ("total_current_liabilities", cur_liab)])))

        # Debt-to-capital = total_debt / (total_debt + total_equity)
        debt_cap_denom: float | None = None
        if total_debt is not None and total_equity is not None:
            debt_cap_denom = float(total_debt) + float(total_equity)
        d_cap = safe_divide(total_debt, debt_cap_denom)
        out.append(self._out(ctx, "debt_to_capital", CAT, d_cap, "RATIO",
                             inputs=_mi([("total_debt", total_debt), ("total_equity", total_equity)])))

        # Long-term debt ratio = lt_debt / total_assets
        lt_debt_ratio = safe_divide(lt_debt, total_assets)
        out.append(self._out(ctx, "long_term_debt_ratio", CAT, lt_debt_ratio, "RATIO",
                             inputs=_mi([("long_term_debt", lt_debt), ("total_assets", total_assets)])))

        # Net debt to equity
        nd_eq = safe_divide(net_debt, total_equity)
        out.append(self._out(ctx, "net_debt_to_equity", CAT, nd_eq, "RATIO",
                             quality=equity_quality if nd_eq is not None else None,
                             inputs=_mi([("net_debt", net_debt), ("total_equity", total_equity)])))

        # Financial leverage = total_assets / total_equity (same as equity_multiplier, alias)
        fin_lev = safe_divide(total_assets, total_equity)
        out.append(self._out(ctx, "financial_leverage", CAT, fin_lev, "RATIO",
                             quality=equity_quality if fin_lev is not None else None,
                             inputs=_mi([("total_assets", total_assets), ("total_equity", total_equity)])))

        # Debt service coverage = OCF / total_debt
        dscr = safe_divide(ocf, total_debt)
        out.append(self._out(ctx, "debt_service_coverage", CAT, dscr, "RATIO",
                             inputs=_mi([("cash_from_operations", ocf), ("total_debt", total_debt)])))

        # Cash to debt
        cash_debt = safe_divide(cash, total_debt)
        out.append(self._out(ctx, "cash_to_debt", CAT, cash_debt, "RATIO",
                             inputs=_mi([("cash_and_equivalents", cash), ("total_debt", total_debt)])))

        # Times interest earned (alias of interest_coverage, but uses EBITDA)
        tie: float | None = None
        tie_quality = None
        if interest is not None and float(interest) == 0:
            tie = None
            tie_quality = "NO_INTEREST_EXPENSE"
        else:
            tie = safe_divide(ebitda, interest)
        out.append(self._out(ctx, "times_interest_earned", CAT, tie, "RATIO",
                             quality=tie_quality,
                             inputs=_mi([("ebitda", ebitda), ("interest_expense", interest)])))

        # LT debt to total capital
        lt_total_cap_denom: float | None = None
        if lt_debt is not None and total_equity is not None:
            lt_total_cap_denom = float(lt_debt) + float(total_equity)
        lt_cap = safe_divide(lt_debt, lt_total_cap_denom)
        out.append(self._out(ctx, "lt_debt_to_total_capital", CAT, lt_cap, "RATIO",
                             inputs=_mi([("long_term_debt", lt_debt), ("total_equity", total_equity)])))

        # Total debt to total assets
        td_ta = safe_divide(total_debt, total_assets)
        out.append(self._out(ctx, "total_debt_to_total_assets", CAT, td_ta, "RATIO",
                             inputs=_mi([("total_debt", total_debt), ("total_assets", total_assets)])))

        # Net debt to total assets
        nd_ta = safe_divide(net_debt, total_assets)
        out.append(self._out(ctx, "net_debt_to_total_assets", CAT, nd_ta, "RATIO",
                             inputs=_mi([("net_debt", net_debt), ("total_assets", total_assets)])))

        # Current liabilities ratio = current_liabilities / total_liabilities
        total_liab = s.bv("total_liabilities")
        cl_ratio = safe_divide(cur_liab, total_liab)
        out.append(self._out(ctx, "current_liabilities_ratio", CAT, cl_ratio, "RATIO",
                             inputs=_mi([("total_current_liabilities", cur_liab),
                                         ("total_liabilities", total_liab)])))

        # Fixed charge coverage = (EBITDA + lease_payments) / (interest + lease_payments)
        lease_payments = s.cv("operating_lease_payments")
        fcc: float | None = None
        if ebitda is not None and interest is not None:
            lp = float(lease_payments) if lease_payments is not None else 0.0
            numerator = float(ebitda) + lp
            denominator = float(interest) + lp
            if denominator != 0:
                fcc = numerator / denominator
        out.append(self._out(ctx, "fixed_charge_coverage", CAT, fcc, "RATIO",
                             inputs=_mi([("ebitda", ebitda), ("interest_expense", interest),
                                         ("operating_lease_payments", lease_payments)])))

        # Debt growth YoY = (total_debt / prior_total_debt - 1) * 100
        prior_1y = self._prior(ctx.snapshots, 1)
        prior_total_debt = prior_1y.bv("total_debt") if prior_1y else None
        debt_growth = pct_change(total_debt, prior_total_debt)
        out.append(self._out(ctx, "debt_growth_yoy", CAT,
                             debt_growth * 100 if debt_growth is not None else None, "PERCENT",
                             inputs=_mi([("total_debt_current", total_debt),
                                         ("total_debt_prior", prior_total_debt)])))

        return out

    # ==================================================================
    # CATEGORY 3: EFFICIENCY
    # ==================================================================

    def _efficiency(self, ctx: _ComputeContext) -> list[EngineOutput]:
        CAT = "EFFICIENCY"
        s = ctx.latest
        out: list[EngineOutput] = []

        revenue = s.iv("total_revenue")
        cogs = s.iv("cost_of_revenue")

        total_assets = s.bv("total_assets")
        total_equity = s.bv("total_equity")
        inventory = s.bv("inventory")
        receivables = s.bv("accounts_receivable")
        payables = s.bv("accounts_payable")
        ppe = s.bv("ppe_net")
        working_cap = s.bv("working_capital")
        total_debt = s.bv("total_debt")
        cash = s.bv("cash_and_equivalents")

        def _mi(pairs: list[tuple[str, float | None]]) -> list[dict]:
            return [make_input(n, "fundamentals", v, s.period_label) for n, v in pairs]

        # Asset turnover = revenue / total_assets
        asset_turn = safe_divide(revenue, total_assets)
        out.append(self._out(ctx, "asset_turnover", CAT, asset_turn, "RATIO",
                             inputs=_mi([("total_revenue", revenue), ("total_assets", total_assets)])))

        # Inventory turnover = COGS / inventory
        inv_turn = safe_divide(cogs, inventory)
        out.append(self._out(ctx, "inventory_turnover", CAT, inv_turn, "RATIO",
                             inputs=_mi([("cost_of_revenue", cogs), ("inventory", inventory)])))

        # Receivables turnover = revenue / accounts_receivable
        rec_turn = safe_divide(revenue, receivables)
        out.append(self._out(ctx, "receivables_turnover", CAT, rec_turn, "RATIO",
                             inputs=_mi([("total_revenue", revenue), ("accounts_receivable", receivables)])))

        # Payables turnover = COGS / accounts_payable
        pay_turn = safe_divide(cogs, payables)
        out.append(self._out(ctx, "payables_turnover", CAT, pay_turn, "RATIO",
                             inputs=_mi([("cost_of_revenue", cogs), ("accounts_payable", payables)])))

        # DSO = 365 / receivables_turnover
        dso = safe_divide(365.0, rec_turn)
        out.append(self._out(ctx, "dso", CAT, dso, "DAYS",
                             inputs=_mi([("total_revenue", revenue), ("accounts_receivable", receivables)])))

        # DIO = 365 / inventory_turnover (None if no inventory)
        dio: float | None = None
        if inventory is not None and inv_turn is not None:
            dio = safe_divide(365.0, inv_turn)
        out.append(self._out(ctx, "dio", CAT, dio, "DAYS",
                             inputs=_mi([("cost_of_revenue", cogs), ("inventory", inventory)])))

        # DPO = 365 / payables_turnover
        dpo = safe_divide(365.0, pay_turn)
        out.append(self._out(ctx, "dpo", CAT, dpo, "DAYS",
                             inputs=_mi([("cost_of_revenue", cogs), ("accounts_payable", payables)])))

        # Cash conversion cycle = DSO + DIO - DPO
        # If no inventory (dio=None), CCC = DSO - DPO
        ccc: float | None = None
        if dso is not None and dpo is not None:
            dio_component = dio if dio is not None else 0.0
            ccc = dso + dio_component - dpo
        out.append(self._out(ctx, "cash_conversion_cycle", CAT, ccc, "DAYS",
                             inputs=_mi([("dso", dso), ("dio", dio), ("dpo", dpo)])))

        # Fixed asset turnover = revenue / PPE_net
        fa_turn = safe_divide(revenue, ppe)
        out.append(self._out(ctx, "fixed_asset_turnover", CAT, fa_turn, "RATIO",
                             inputs=_mi([("total_revenue", revenue), ("ppe_net", ppe)])))

        # Working capital turnover = revenue / working_capital
        wc_turn = safe_divide(revenue, working_cap)
        out.append(self._out(ctx, "working_capital_turnover", CAT, wc_turn, "RATIO",
                             inputs=_mi([("total_revenue", revenue), ("working_capital", working_cap)])))

        # Equity turnover = revenue / total_equity
        eq_turn = safe_divide(revenue, total_equity)
        out.append(self._out(ctx, "equity_turnover", CAT, eq_turn, "RATIO",
                             inputs=_mi([("total_revenue", revenue), ("total_equity", total_equity)])))

        # Total capital turnover = revenue / (total_equity + total_debt)
        total_cap: float | None = None
        if total_equity is not None and total_debt is not None:
            total_cap = float(total_equity) + float(total_debt)
        tc_turn = safe_divide(revenue, total_cap)
        out.append(self._out(ctx, "total_capital_turnover", CAT, tc_turn, "RATIO",
                             inputs=_mi([("total_revenue", revenue), ("total_equity", total_equity),
                                         ("total_debt", total_debt)])))

        # PPE turnover (alias for fixed_asset_turnover)
        out.append(self._out(ctx, "ppe_turnover", CAT, fa_turn, "RATIO",
                             inputs=_mi([("total_revenue", revenue), ("ppe_net", ppe)])))

        # Invested capital turnover = revenue / invested_capital
        invested_capital: float | None = None
        if total_equity is not None and total_debt is not None:
            ic = float(total_equity) + float(total_debt)
            if cash is not None:
                ic -= float(cash)
            invested_capital = ic
        ic_turn = safe_divide(revenue, invested_capital)
        out.append(self._out(ctx, "invested_capital_turnover", CAT, ic_turn, "RATIO",
                             inputs=_mi([("total_revenue", revenue), ("total_equity", total_equity),
                                         ("total_debt", total_debt), ("cash_and_equivalents", cash)])))

        # Revenue to fixed assets (net PPE) — explicit alias that survives
        # even if fixed_asset_turnover is filtered out by downstream consumers.
        rev_to_fa = safe_divide(revenue, ppe)
        out.append(self._out(ctx, "revenue_to_fixed_assets", CAT, rev_to_fa, "RATIO",
                             inputs=_mi([("total_revenue", revenue), ("ppe_net", ppe)])))

        return out

    # ==================================================================
    # CATEGORY 4: GROWTH
    # ==================================================================

    def _growth(self, ctx: _ComputeContext) -> list[EngineOutput]:
        CAT = "GROWTH"
        s = ctx.latest
        out: list[EngineOutput] = []

        def _mi(pairs: list[tuple[str, float | None]], period_label: str = "") -> list[dict]:
            return [make_input(n, "fundamentals", v, period_label or s.period_label) for n, v in pairs]

        prior_1y = self._prior(ctx.snapshots, 1)
        prior_3y = self._prior(ctx.snapshots, 3)
        prior_5y = self._prior(ctx.snapshots, 5)

        # --- YoY growth rates ---
        yoy_metrics: list[tuple[str, str, str]] = [
            # (output_name, income_statement_field, statement_type)
            ("revenue_yoy", "total_revenue", "iv"),
            ("gross_profit_yoy", "gross_profit", "iv"),
            ("operating_income_yoy", "operating_income", "iv"),
            ("ebitda_yoy", "ebitda", "iv"),
            ("net_income_yoy", "net_income", "iv"),
            ("eps_yoy", "diluted_eps", "iv"),
        ]

        for metric_name, field_name, stmt_type in yoy_metrics:
            current_val = getattr(s, stmt_type)(field_name) if stmt_type == "iv" else None
            prior_val = None
            if prior_1y is not None:
                prior_val = getattr(prior_1y, stmt_type)(field_name) if stmt_type == "iv" else None
            chg = pct_change(current_val, prior_val)
            inputs = _mi([
                (f"{field_name}_current", current_val),
                (f"{field_name}_prior", prior_val),
            ])
            out.append(self._out(ctx, metric_name, CAT, chg, "PERCENT", inputs=inputs))

        # FCF YoY (cash-flow statement)
        fcf_curr = s.cv("free_cash_flow")
        fcf_prior = prior_1y.cv("free_cash_flow") if prior_1y else None
        out.append(self._out(ctx, "fcf_yoy", CAT, pct_change(fcf_curr, fcf_prior), "PERCENT",
                             inputs=_mi([("fcf_current", fcf_curr), ("fcf_prior", fcf_prior)])))

        # Total assets YoY (balance sheet)
        ta_curr = s.bv("total_assets")
        ta_prior = prior_1y.bv("total_assets") if prior_1y else None
        out.append(self._out(ctx, "total_assets_yoy", CAT, pct_change(ta_curr, ta_prior), "PERCENT",
                             inputs=_mi([("total_assets_current", ta_curr), ("total_assets_prior", ta_prior)])))

        # Book value YoY
        bv_curr = s.bv("total_common_equity")
        bv_prior = prior_1y.bv("total_common_equity") if prior_1y else None
        out.append(self._out(ctx, "book_value_yoy", CAT, pct_change(bv_curr, bv_prior), "PERCENT",
                             inputs=_mi([("book_value_current", bv_curr), ("book_value_prior", bv_prior)])))

        # Dividend YoY
        div_curr = s.cv("dividends_paid")
        div_prior = prior_1y.cv("dividends_paid") if prior_1y else None
        # dividends_paid is typically negative (cash outflow); use absolute for growth
        div_curr_abs = abs(float(div_curr)) if div_curr is not None else None
        div_prior_abs = abs(float(div_prior)) if div_prior is not None else None
        out.append(self._out(ctx, "dividend_yoy", CAT, pct_change(div_curr_abs, div_prior_abs), "PERCENT",
                             inputs=_mi([("dividends_paid_current", div_curr),
                                         ("dividends_paid_prior", div_prior)])))

        # --- CAGR metrics ---
        cagr_specs: list[tuple[str, str, str, int]] = [
            # (output_name, field_name, stmt_type, years)
            ("revenue_3y_cagr", "total_revenue", "iv", 3),
            ("revenue_5y_cagr", "total_revenue", "iv", 5),
            ("eps_3y_cagr", "diluted_eps", "iv", 3),
            ("eps_5y_cagr", "diluted_eps", "iv", 5),
            ("ebitda_3y_cagr", "ebitda", "iv", 3),
            ("net_income_3y_cagr", "net_income", "iv", 3),
            ("operating_income_3y_cagr", "operating_income", "iv", 3),
        ]

        for metric_name, field_name, stmt_type, years in cagr_specs:
            current_val = getattr(s, stmt_type)(field_name)
            prior_snap = self._prior(ctx.snapshots, years)
            start_val = getattr(prior_snap, stmt_type)(field_name) if prior_snap else None
            c = cagr(current_val, start_val, years)
            out.append(self._out(ctx, metric_name, CAT, c, "PERCENT",
                                 inputs=_mi([
                                     (f"{field_name}_current", current_val),
                                     (f"{field_name}_{years}y_prior", start_val),
                                 ])))

        # FCF CAGR (cash flow)
        fcf_3y_prior = prior_3y.cv("free_cash_flow") if prior_3y else None
        out.append(self._out(ctx, "fcf_3y_cagr", CAT,
                             cagr(fcf_curr, fcf_3y_prior, 3), "PERCENT",
                             inputs=_mi([("fcf_current", fcf_curr), ("fcf_3y_prior", fcf_3y_prior)])))

        # Book value CAGR
        bv_3y_prior = prior_3y.bv("total_common_equity") if prior_3y else None
        out.append(self._out(ctx, "book_value_3y_cagr", CAT,
                             cagr(bv_curr, bv_3y_prior, 3), "PERCENT",
                             inputs=_mi([("book_value_current", bv_curr),
                                         ("book_value_3y_prior", bv_3y_prior)])))

        # Dividend CAGR (using absolute values)
        div_3y_prior = prior_3y.cv("dividends_paid") if prior_3y else None
        div_3y_prior_abs = abs(float(div_3y_prior)) if div_3y_prior is not None else None
        out.append(self._out(ctx, "dividend_3y_cagr", CAT,
                             cagr(div_curr_abs, div_3y_prior_abs, 3), "PERCENT",
                             inputs=_mi([("dividends_paid_current", div_curr),
                                         ("dividends_paid_3y_prior", div_3y_prior)])))

        # Tangible BVPS YoY
        tbvps_curr = s.bv("tangible_book_value")
        tbvps_prior = prior_1y.bv("tangible_book_value") if prior_1y else None
        tbvps_yoy = pct_change(tbvps_curr, tbvps_prior)
        out.append(self._out(ctx, "tangible_bvps_yoy", CAT,
                             tbvps_yoy * 100 if tbvps_yoy is not None else None, "PERCENT",
                             inputs=_mi([("tangible_bv_current", tbvps_curr),
                                         ("tangible_bv_prior", tbvps_prior)])))

        # Debt growth 3Y CAGR
        debt_curr = s.bv("total_debt")
        debt_3y_prior = prior_3y.bv("total_debt") if prior_3y else None
        out.append(self._out(ctx, "debt_growth_3y_cagr", CAT,
                             cagr(debt_curr, debt_3y_prior, 3), "PERCENT",
                             inputs=_mi([("total_debt_current", debt_curr),
                                         ("total_debt_3y_prior", debt_3y_prior)])))

        # Operating income 5Y CAGR
        oi_curr = s.iv("operating_income")
        oi_5y_prior = prior_5y.iv("operating_income") if prior_5y else None
        out.append(self._out(ctx, "operating_income_5y_cagr", CAT,
                             cagr(oi_curr, oi_5y_prior, 5), "PERCENT",
                             inputs=_mi([("operating_income_current", oi_curr),
                                         ("operating_income_5y_prior", oi_5y_prior)])))

        return out

    # ==================================================================
    # CATEGORY 5: PER-SHARE
    # ==================================================================

    def _per_share(self, ctx: _ComputeContext) -> list[EngineOutput]:
        CAT = "PER_SHARE"
        s = ctx.latest
        price = ctx.price
        out: list[EngineOutput] = []

        shares_basic = price.shares_basic
        shares_diluted = price.shares_diluted

        revenue = s.iv("total_revenue")
        ebitda = s.iv("ebitda")
        basic_eps = s.iv("basic_eps")
        diluted_eps = s.iv("diluted_eps")

        common_equity = s.bv("total_common_equity")
        tangible_bv = s.bv("tangible_book_value")
        cash = s.bv("cash_and_equivalents")

        fcf = s.cv("free_cash_flow")
        ocf = s.cv("cash_from_operations")
        dividends = s.cv("dividends_paid")

        def _mi(pairs: list[tuple[str, float | None]]) -> list[dict]:
            return [make_input(n, "fundamentals", v, s.period_label) for n, v in pairs]

        # EPS basic (pass-through)
        out.append(self._out(ctx, "eps_basic", CAT,
                             float(basic_eps) if basic_eps is not None else None, "CURRENCY",
                             inputs=_mi([("basic_eps", basic_eps)])))

        # EPS diluted (pass-through)
        out.append(self._out(ctx, "eps_diluted", CAT,
                             float(diluted_eps) if diluted_eps is not None else None, "CURRENCY",
                             inputs=_mi([("diluted_eps", diluted_eps)])))

        # BVPS = common_equity / shares_diluted
        bvps = safe_divide(common_equity, shares_diluted)
        out.append(self._out(ctx, "bvps", CAT, bvps, "CURRENCY",
                             inputs=_mi([("total_common_equity", common_equity),
                                         ("diluted_shares", shares_diluted)])))

        # Tangible BVPS
        tbvps = safe_divide(tangible_bv, shares_diluted)
        out.append(self._out(ctx, "tangible_bvps", CAT, tbvps, "CURRENCY",
                             inputs=_mi([("tangible_book_value", tangible_bv),
                                         ("diluted_shares", shares_diluted)])))

        # FCFPS
        fcfps = safe_divide(fcf, shares_diluted)
        out.append(self._out(ctx, "fcfps", CAT, fcfps, "CURRENCY",
                             inputs=_mi([("free_cash_flow", fcf),
                                         ("diluted_shares", shares_diluted)])))

        # DPS = abs(dividends_paid) / shares_basic
        div_abs = abs(float(dividends)) if dividends is not None else None
        dps = safe_divide(div_abs, shares_basic)
        out.append(self._out(ctx, "dps", CAT, dps, "CURRENCY",
                             inputs=_mi([("dividends_paid", dividends),
                                         ("basic_shares", shares_basic)])))

        # Revenue per share
        rev_ps = safe_divide(revenue, shares_diluted)
        out.append(self._out(ctx, "revenue_per_share", CAT, rev_ps, "CURRENCY",
                             inputs=_mi([("total_revenue", revenue),
                                         ("diluted_shares", shares_diluted)])))

        # EBITDA per share
        ebitda_ps = safe_divide(ebitda, shares_diluted)
        out.append(self._out(ctx, "ebitda_per_share", CAT, ebitda_ps, "CURRENCY",
                             inputs=_mi([("ebitda", ebitda),
                                         ("diluted_shares", shares_diluted)])))

        # Cash per share
        cash_ps = safe_divide(cash, shares_diluted)
        out.append(self._out(ctx, "cash_per_share", CAT, cash_ps, "CURRENCY",
                             inputs=_mi([("cash_and_equivalents", cash),
                                         ("diluted_shares", shares_diluted)])))

        # Operating cash flow per share
        ocf_ps = safe_divide(ocf, shares_diluted)
        out.append(self._out(ctx, "operating_cf_per_share", CAT, ocf_ps, "CURRENCY",
                             inputs=_mi([("cash_from_operations", ocf),
                                         ("diluted_shares", shares_diluted)])))

        # Net income per employee (if employee_count available on entity)
        net_inc = s.iv("net_income")
        employee_count = s.iv("employee_count") or s.bv("employee_count")
        ni_per_emp = safe_divide(net_inc, employee_count)
        out.append(self._out(ctx, "net_income_per_employee", CAT, ni_per_emp, "CURRENCY",
                             inputs=_mi([("net_income", net_inc),
                                         ("employee_count", employee_count)])))

        # Revenue per employee
        rev_per_emp = safe_divide(revenue, employee_count)
        out.append(self._out(ctx, "revenue_per_employee", CAT, rev_per_emp, "CURRENCY",
                             inputs=_mi([("total_revenue", revenue),
                                         ("employee_count", employee_count)])))

        return out

    # ==================================================================
    # CATEGORY 6: CASH FLOW QUALITY
    # ==================================================================

    def _cash_flow_quality(self, ctx: _ComputeContext) -> list[EngineOutput]:
        CAT = "CASH_FLOW_QUALITY"
        s = ctx.latest
        price = ctx.price
        out: list[EngineOutput] = []

        net_inc = s.iv("net_income")
        revenue = s.iv("total_revenue")
        da = s.iv("depreciation_amortization")

        total_assets = s.bv("total_assets")
        cur_liab = s.bv("total_current_liabilities")

        ocf = s.cv("cash_from_operations")
        capex = s.cv("capital_expenditures")
        fcf = s.cv("free_cash_flow")

        def _mi(pairs: list[tuple[str, float | None]]) -> list[dict]:
            return [make_input(n, "fundamentals", v, s.period_label) for n, v in pairs]

        # OCF to net income
        ocf_ni = safe_divide(ocf, net_inc)
        out.append(self._out(ctx, "ocf_to_net_income", CAT, ocf_ni, "RATIO",
                             inputs=_mi([("cash_from_operations", ocf), ("net_income", net_inc)])))

        # FCF to net income
        fcf_ni = safe_divide(fcf, net_inc)
        out.append(self._out(ctx, "fcf_to_net_income", CAT, fcf_ni, "RATIO",
                             inputs=_mi([("free_cash_flow", fcf), ("net_income", net_inc)])))

        # Capex to depreciation (both are typically negative/positive respectively)
        capex_abs = abs(float(capex)) if capex is not None else None
        da_float = float(da) if da is not None else None
        capex_depr = safe_divide(capex_abs, da_float)
        out.append(self._out(ctx, "capex_to_depreciation", CAT, capex_depr, "RATIO",
                             inputs=_mi([("capital_expenditures", capex),
                                         ("depreciation_amortization", da)])))

        # Capex to revenue
        capex_rev = safe_divide(capex_abs, revenue)
        out.append(self._out(ctx, "capex_to_revenue", CAT, capex_rev, "RATIO",
                             inputs=_mi([("capital_expenditures", capex), ("total_revenue", revenue)])))

        # Accruals ratio = (net_income - OCF) / total_assets
        accruals: float | None = None
        if net_inc is not None and ocf is not None:
            accruals = float(net_inc) - float(ocf)
        accruals_ratio = safe_divide(accruals, total_assets)
        out.append(self._out(ctx, "accruals_ratio", CAT, accruals_ratio, "RATIO",
                             inputs=_mi([("net_income", net_inc), ("cash_from_operations", ocf),
                                         ("total_assets", total_assets)])))

        # Cash flow coverage = OCF / total_debt
        total_debt = s.bv("total_debt")
        cf_cov = safe_divide(ocf, total_debt)
        out.append(self._out(ctx, "cash_flow_coverage", CAT, cf_cov, "RATIO",
                             inputs=_mi([("cash_from_operations", ocf), ("total_debt", total_debt)])))

        # FCF yield = FCF / market_cap
        fcf_yield = safe_divide(fcf, price.market_cap)
        mkt_input = make_input("market_cap", "market_data", price.market_cap, "LATEST")
        out.append(self._out(ctx, "fcf_yield", CAT, fcf_yield, "PERCENT",
                             inputs=_mi([("free_cash_flow", fcf)]) + [mkt_input]))

        # Operating cash flow ratio = OCF / current_liabilities
        ocf_ratio = safe_divide(ocf, cur_liab)
        out.append(self._out(ctx, "operating_cash_flow_ratio", CAT, ocf_ratio, "RATIO",
                             inputs=_mi([("cash_from_operations", ocf),
                                         ("total_current_liabilities", cur_liab)])))

        # Capex to operating CF
        capex_ocf = safe_divide(capex_abs, ocf)
        out.append(self._out(ctx, "capex_to_operating_cf", CAT, capex_ocf, "RATIO",
                             inputs=_mi([("capital_expenditures", capex),
                                         ("cash_from_operations", ocf)])))

        # Quality of earnings = OCF / net_income (alias of ocf_to_net_income)
        out.append(self._out(ctx, "quality_of_earnings", CAT, ocf_ni, "RATIO",
                             inputs=_mi([("cash_from_operations", ocf), ("net_income", net_inc)])))

        # Operating cash flow to total debt
        ocf_to_debt = safe_divide(ocf, total_debt)
        out.append(self._out(ctx, "operating_cf_to_debt", CAT, ocf_to_debt, "RATIO",
                             inputs=_mi([("cash_from_operations", ocf), ("total_debt", total_debt)])))

        # Free cash flow to total debt
        fcf_to_debt = safe_divide(fcf, total_debt)
        out.append(self._out(ctx, "fcf_to_debt", CAT, fcf_to_debt, "RATIO",
                             inputs=_mi([("free_cash_flow", fcf), ("total_debt", total_debt)])))

        return out

    # ==================================================================
    # CATEGORY 7: CAPITAL ALLOCATION
    # ==================================================================

    def _capital_allocation(self, ctx: _ComputeContext) -> list[EngineOutput]:
        CAT = "CAPITAL_ALLOCATION"
        s = ctx.latest
        price = ctx.price
        out: list[EngineOutput] = []

        net_inc = s.iv("net_income")
        net_common = s.iv("net_income_to_common")

        fcf = s.cv("free_cash_flow")
        dividends = s.cv("dividends_paid")
        buybacks = s.cv("stock_repurchased")

        def _mi(pairs: list[tuple[str, float | None]]) -> list[dict]:
            return [make_input(n, "fundamentals", v, s.period_label) for n, v in pairs]

        div_abs = abs(float(dividends)) if dividends is not None else None
        buyback_abs = abs(float(buybacks)) if buybacks is not None else None

        # Payout ratio = dividends / net_income
        payout = safe_divide(div_abs, net_inc)
        out.append(self._out(ctx, "payout_ratio", CAT, payout, "PERCENT",
                             inputs=_mi([("dividends_paid", dividends), ("net_income", net_inc)])))

        # FCF payout ratio = dividends / FCF
        fcf_payout = safe_divide(div_abs, fcf)
        out.append(self._out(ctx, "fcf_payout_ratio", CAT, fcf_payout, "PERCENT",
                             inputs=_mi([("dividends_paid", dividends), ("free_cash_flow", fcf)])))

        # Retention ratio = 1 - payout_ratio
        retention: float | None = None
        if payout is not None:
            retention = 1.0 - payout
        out.append(self._out(ctx, "retention_ratio", CAT, retention, "PERCENT",
                             inputs=_mi([("dividends_paid", dividends), ("net_income", net_inc)])))

        # Buyback yield = buybacks / market_cap
        buyback_yield = safe_divide(buyback_abs, price.market_cap)
        mkt_input = make_input("market_cap", "market_data", price.market_cap, "LATEST")
        out.append(self._out(ctx, "buyback_yield", CAT, buyback_yield, "PERCENT",
                             inputs=_mi([("stock_repurchased", buybacks)]) + [mkt_input]))

        # Shareholder yield = (dividends + buybacks) / market_cap
        total_return_cash: float | None = None
        if div_abs is not None or buyback_abs is not None:
            total_return_cash = (div_abs or 0.0) + (buyback_abs or 0.0)
        sh_yield = safe_divide(total_return_cash, price.market_cap)
        out.append(self._out(ctx, "shareholder_yield", CAT, sh_yield, "PERCENT",
                             inputs=_mi([("dividends_paid", dividends),
                                         ("stock_repurchased", buybacks)]) + [mkt_input]))

        # Reinvestment rate = retention_ratio * ROE
        total_equity = s.bv("total_equity")
        roe = safe_divide(net_inc, total_equity)
        reinvest: float | None = None
        if retention is not None and roe is not None:
            reinvest = retention * roe
        out.append(self._out(ctx, "reinvestment_rate", CAT, reinvest, "PERCENT",
                             inputs=_mi([("retention_ratio", retention), ("roe", roe)])))

        # Dividend to FCF = dividends / FCF (same as fcf_payout but named differently)
        out.append(self._out(ctx, "dividend_to_fcf", CAT, fcf_payout, "PERCENT",
                             inputs=_mi([("dividends_paid", dividends), ("free_cash_flow", fcf)])))

        # Total shareholder return proxy = (dividends + buybacks) / market_cap (alias)
        out.append(self._out(ctx, "total_shareholder_return_proxy", CAT, sh_yield, "PERCENT",
                             inputs=_mi([("dividends_paid", dividends),
                                         ("stock_repurchased", buybacks)]) + [mkt_input]))

        return out

    # ==================================================================
    # CATEGORY 8: DIVIDEND
    # ==================================================================

    def _dividend(self, ctx: _ComputeContext) -> list[EngineOutput]:
        CAT = "DIVIDEND"
        s = ctx.latest
        price = ctx.price
        out: list[EngineOutput] = []

        dividends = s.cv("dividends_paid")
        net_inc = s.iv("net_income")
        fcf = s.cv("free_cash_flow")

        shares_basic = price.shares_basic

        def _mi(pairs: list[tuple[str, float | None]]) -> list[dict]:
            return [make_input(n, "fundamentals", v, s.period_label) for n, v in pairs]

        div_abs = abs(float(dividends)) if dividends is not None else None

        # DPS for yield calculation
        dps = safe_divide(div_abs, shares_basic)

        # Trailing dividend yield = DPS / price
        trailing_yield = safe_divide(dps, price.close)
        price_input = make_input("close", "market_data", price.close, "LATEST")
        out.append(self._out(ctx, "dividend_yield_trailing", CAT, trailing_yield, "PERCENT",
                             inputs=_mi([("dividends_paid", dividends),
                                         ("basic_shares", shares_basic)]) + [price_input]))

        # Forward dividend yield (if forward EPS available and payout ratio available)
        fwd_yield: float | None = None
        fwd_quality = None
        if ctx.fwd_eps is not None and price.close is not None:
            # Estimate forward DPS using current payout ratio applied to forward EPS
            payout = safe_divide(div_abs, net_inc)
            if payout is not None:
                fwd_dps = payout * ctx.fwd_eps
                fwd_yield = safe_divide(fwd_dps, price.close)
            else:
                fwd_quality = "INSUFFICIENT_DATA"
        else:
            fwd_quality = "INSUFFICIENT_DATA" if ctx.fwd_eps is None else None
        est_input = make_input("forward_eps", "estimates", ctx.fwd_eps, "FWD")
        out.append(self._out(ctx, "dividend_yield_forward", CAT, fwd_yield, "PERCENT",
                             quality=fwd_quality,
                             inputs=_mi([("dividends_paid", dividends),
                                         ("net_income", net_inc)]) + [price_input, est_input]))

        # Dividend growth 1Y
        prior_1y = self._prior(ctx.snapshots, 1)
        div_prior_1 = prior_1y.cv("dividends_paid") if prior_1y else None
        div_prior_1_abs = abs(float(div_prior_1)) if div_prior_1 is not None else None
        dg_1y = pct_change(div_abs, div_prior_1_abs)
        out.append(self._out(ctx, "dividend_growth_1y", CAT, dg_1y, "PERCENT",
                             inputs=_mi([("dividends_current", dividends),
                                         ("dividends_1y_prior", div_prior_1)])))

        # Dividend growth 3Y CAGR
        prior_3y = self._prior(ctx.snapshots, 3)
        div_prior_3 = prior_3y.cv("dividends_paid") if prior_3y else None
        div_prior_3_abs = abs(float(div_prior_3)) if div_prior_3 is not None else None
        dg_3y = cagr(div_abs, div_prior_3_abs, 3)
        out.append(self._out(ctx, "dividend_growth_3y", CAT, dg_3y, "PERCENT",
                             inputs=_mi([("dividends_current", dividends),
                                         ("dividends_3y_prior", div_prior_3)])))

        # Dividend growth 5Y CAGR
        prior_5y = self._prior(ctx.snapshots, 5)
        div_prior_5 = prior_5y.cv("dividends_paid") if prior_5y else None
        div_prior_5_abs = abs(float(div_prior_5)) if div_prior_5 is not None else None
        dg_5y = cagr(div_abs, div_prior_5_abs, 5)
        out.append(self._out(ctx, "dividend_growth_5y", CAT, dg_5y, "PERCENT",
                             inputs=_mi([("dividends_current", dividends),
                                         ("dividends_5y_prior", div_prior_5)])))

        # Payout ratio (earnings) = dividends / net_income
        payout_earn = safe_divide(div_abs, net_inc)
        out.append(self._out(ctx, "payout_ratio_earnings", CAT, payout_earn, "PERCENT",
                             inputs=_mi([("dividends_paid", dividends), ("net_income", net_inc)])))

        # Payout ratio (FCF) = dividends / FCF
        payout_fcf = safe_divide(div_abs, fcf)
        out.append(self._out(ctx, "payout_ratio_fcf", CAT, payout_fcf, "PERCENT",
                             inputs=_mi([("dividends_paid", dividends), ("free_cash_flow", fcf)])))

        # Consecutive dividend years — count how many consecutive periods
        # (walking backwards) have non-zero dividends paid.
        consec = 0
        for snap in ctx.snapshots:
            d = snap.cv("dividends_paid")
            if d is not None and float(d) != 0.0:
                consec += 1
            else:
                break
        out.append(self._out(ctx, "consecutive_dividend_years", CAT, float(consec), "YEARS",
                             inputs=_mi([("dividends_paid", dividends)])))

        # Dividend growth 10Y CAGR
        prior_10y = self._prior(ctx.snapshots, 10)
        div_prior_10 = prior_10y.cv("dividends_paid") if prior_10y else None
        div_prior_10_abs = abs(float(div_prior_10)) if div_prior_10 is not None else None
        dg_10y = cagr(div_abs, div_prior_10_abs, 10)
        out.append(self._out(ctx, "dividend_growth_10y_cagr", CAT, dg_10y, "PERCENT",
                             inputs=_mi([("dividends_current", dividends),
                                         ("dividends_10y_prior", div_prior_10)])))

        return out


# ---------------------------------------------------------------------------
# Internal context object
# ---------------------------------------------------------------------------

class _ComputeContext:
    """Bundles all loaded data for a single compute() call."""

    __slots__ = (
        "security_id", "entity_id", "latest", "snapshots",
        "price", "fwd_eps",
    )

    def __init__(
        self,
        security_id: UUID,
        entity_id: UUID,
        latest: _FinancialSnapshot,
        snapshots: list[_FinancialSnapshot],
        price: _PriceSnapshot,
        fwd_eps: float | None,
    ) -> None:
        self.security_id = security_id
        self.entity_id = entity_id
        self.latest = latest
        self.snapshots = snapshots
        self.price = price
        self.fwd_eps = fwd_eps
