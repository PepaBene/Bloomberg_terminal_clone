"""E8 Scenario & Sensitivity Engine (Spec §10).

On-demand service class that re-uses E2 DCFEngine's internal projection
methods to systematically vary DCF assumptions and produce:
- 2D sensitivity tables
- 3D sensitivity tables (multiple 2D slices)
- Tornado charts
- Multi-variable shock analyses (including pre-built macro scenarios)
- Break-even search (bisection)

Design: load financial data **once** via ``_load_dcf_context``, then call
``_quick_dcf`` (pure-Python, no DB) for every grid cell / bar / shock.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.engines.e2_dcf import DCFEngine
from src.models.scenario import ScenarioResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Auto-range defaults (±pp from base) per variable
# ---------------------------------------------------------------------------
_AUTO_RANGES: dict[str, float] = {
    "discount_rate": 0.02,
    "terminal_growth": 0.015,
    "revenue_growth": 0.05,
    "ebit_margin": 0.03,
    "tax_rate": 0.03,
    "capex_to_revenue": 0.02,
    "dna_to_revenue": 0.02,
    "wc_to_revenue": 0.02,
}

# Mapping from sensitivity variable name → assumption key.
# revenue_growth is special: it shifts every element of revenue_growth_path.
_VAR_TO_KEY: dict[str, str] = {
    "discount_rate": "discount_rate",
    "terminal_growth": "terminal_growth",
    "revenue_growth": "revenue_growth",
    "ebit_margin": "ebit_margin",
    "tax_rate": "tax_rate",
    "capex_to_revenue": "capex_to_revenue",
    "dna_to_revenue": "dna_to_revenue",
    "wc_to_revenue": "wc_to_revenue",
}

_DEFAULT_STEPS = 7
_DEFAULT_SWING_PCT = 0.20
_BREAKEVEN_MAX_ITER = 50
_BREAKEVEN_TOLERANCE = 0.50  # dollars


# ---------------------------------------------------------------------------
# Internal dataclass for loaded context
# ---------------------------------------------------------------------------

@dataclass
class _DCFContext:
    """All data needed to run quick DCF projections (loaded once)."""
    hist: dict[str, Any]
    base_assumptions: dict[str, Any]
    shares: float | None
    current_price: float | None
    net_debt: float
    method: str


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class ScenarioEngine:
    """On-demand scenario & sensitivity analysis service."""

    def __init__(self) -> None:
        self._dcf = DCFEngine()

    # ------------------------------------------------------------------
    # Data loading (one DB round-trip set per analysis)
    # ------------------------------------------------------------------

    async def _load_dcf_context(
        self,
        session: AsyncSession,
        security_id: UUID,
        method: str = "FCFF",
    ) -> _DCFContext | None:
        """Load all financial data and build base DCF assumptions.

        Returns None if the security lacks sufficient data.
        """
        security, entity_id = await self._dcf._resolve_security(session, security_id)
        if security is None or entity_id is None:
            return None

        periods = await self._dcf._load_annual_financials(session, entity_id, limit=5)
        if len(periods) < 1:
            return None

        hist = self._dcf._extract_historical(periods)
        if hist is None:
            return None

        wacc, cost_of_equity = await self._dcf._load_discount_rates(
            session, entity_id, security_id
        )
        current_price = await self._dcf._load_current_price(session, security_id)
        shares = await self._dcf._load_shares_outstanding(session, security_id)

        base_assumptions = self._dcf._build_assumptions(
            hist, method, wacc, cost_of_equity, None
        )

        net_debt = self._dcf._compute_net_debt(hist) if method == "FCFF" else 0.0

        return _DCFContext(
            hist=hist,
            base_assumptions=base_assumptions,
            shares=shares,
            current_price=current_price,
            net_debt=net_debt,
            method=method,
        )

    # ------------------------------------------------------------------
    # Quick DCF (pure-Python, no DB)
    # ------------------------------------------------------------------

    def _quick_dcf(
        self,
        ctx: _DCFContext,
        overrides: dict[str, Any] | None = None,
    ) -> float | None:
        """Run a DCF projection with optional assumption overrides.

        Returns the implied share price, or None if computation fails.
        """
        assumptions = dict(ctx.base_assumptions)

        if overrides:
            for key, val in overrides.items():
                if key == "revenue_growth":
                    # Shift every year's growth rate by the delta
                    base_path = ctx.base_assumptions["revenue_growth_path"]
                    delta = val  # additive delta
                    assumptions["revenue_growth_path"] = [
                        g + delta for g in base_path
                    ]
                elif key in assumptions:
                    assumptions[key] = val

            # Re-validate terminal growth < discount rate
            tg = assumptions["terminal_growth"]
            dr = assumptions["discount_rate"]
            if tg >= dr - 0.005:
                assumptions["terminal_growth"] = dr - 0.005
                if assumptions["terminal_growth"] < 0:
                    assumptions["terminal_growth"] = 0.0

        # Run projection
        if ctx.method == "FCFE":
            result = self._dcf._project_fcfe(ctx.hist, assumptions)
        else:
            result = self._dcf._project_fcff(ctx.hist, assumptions)

        if result is None:
            return None

        ev = result["pv_explicit"] + result["pv_terminal"]
        equity = ev - ctx.net_debt
        if ctx.shares is not None and ctx.shares > 0:
            return equity / ctx.shares
        return None

    # ------------------------------------------------------------------
    # Helper: resolve base value for a variable
    # ------------------------------------------------------------------

    def _base_value(self, ctx: _DCFContext, variable: str) -> float:
        """Return the base assumption value for a variable name."""
        if variable == "revenue_growth":
            path = ctx.base_assumptions["revenue_growth_path"]
            return path[0] if path else 0.0
        return ctx.base_assumptions.get(variable, 0.0)

    def _make_override(self, variable: str, absolute_value: float, ctx: _DCFContext) -> dict:
        """Build an override dict setting *variable* to *absolute_value*.

        For revenue_growth the override is stored as a delta from the base
        path since ``_quick_dcf`` shifts the entire path additively.
        """
        if variable == "revenue_growth":
            base = self._base_value(ctx, "revenue_growth")
            return {"revenue_growth": absolute_value - base}
        return {variable: absolute_value}

    # ------------------------------------------------------------------
    # 2D Sensitivity
    # ------------------------------------------------------------------

    async def run_sensitivity_2d(
        self,
        session: AsyncSession,
        security_id: UUID,
        row_variable: str,
        col_variable: str,
        *,
        row_min: float | None = None,
        row_max: float | None = None,
        col_min: float | None = None,
        col_max: float | None = None,
        steps: int = _DEFAULT_STEPS,
        method: str = "FCFF",
        persist: bool = True,
    ) -> dict[str, Any] | None:
        """Produce an NxN sensitivity grid varying two DCF assumptions."""
        ctx = await self._load_dcf_context(session, security_id, method)
        if ctx is None:
            return None

        base_case = self._quick_dcf(ctx)

        # Build axis values
        row_values = self._axis_values(ctx, row_variable, row_min, row_max, steps)
        col_values = self._axis_values(ctx, col_variable, col_min, col_max, steps)

        # Compute grid
        grid: list[list[float | None]] = []
        for rv in row_values:
            row: list[float | None] = []
            for cv in col_values:
                ov = {
                    **self._make_override(row_variable, rv, ctx),
                    **self._make_override(col_variable, cv, ctx),
                }
                row.append(self._quick_dcf(ctx, ov))
            grid.append(row)

        result = {
            "row_variable": row_variable,
            "col_variable": col_variable,
            "row_values": row_values,
            "col_values": col_values,
            "grid": grid,
            "base_case_value": base_case,
            "current_price": ctx.current_price,
        }

        if persist:
            all_prices = [p for row in grid for p in row if p is not None]
            await self._persist(
                session,
                security_id=security_id,
                entity_id=None,
                scenario_type="SENSITIVITY_2D",
                scenario_name=f"{row_variable} vs {col_variable}",
                input_params={
                    "row_variable": row_variable,
                    "col_variable": col_variable,
                    "steps": steps,
                    "method": method,
                },
                output_data=result,
                base_case_value=base_case,
                min_value=min(all_prices) if all_prices else None,
                max_value=max(all_prices) if all_prices else None,
            )

        return result

    def _axis_values(
        self,
        ctx: _DCFContext,
        variable: str,
        vmin: float | None,
        vmax: float | None,
        steps: int,
    ) -> list[float]:
        """Build evenly-spaced axis values for a sensitivity variable."""
        base = self._base_value(ctx, variable)
        half = _AUTO_RANGES.get(variable, 0.03)
        lo = vmin if vmin is not None else base - half
        hi = vmax if vmax is not None else base + half
        if steps < 2:
            return [base]
        return [round(lo + i * (hi - lo) / (steps - 1), 6) for i in range(steps)]

    # ------------------------------------------------------------------
    # 3D Sensitivity
    # ------------------------------------------------------------------

    async def run_sensitivity_3d(
        self,
        session: AsyncSession,
        security_id: UUID,
        fixed_variable: str,
        fixed_values: list[float],
        row_variable: str,
        col_variable: str,
        *,
        steps: int = _DEFAULT_STEPS,
        method: str = "FCFF",
        persist: bool = True,
    ) -> dict[str, Any] | None:
        """Multiple 2D tables, one per fixed_value."""
        ctx = await self._load_dcf_context(session, security_id, method)
        if ctx is None:
            return None

        tables: list[dict] = []
        for fv in fixed_values:
            # Temporarily patch context base assumptions for the fixed variable
            saved = dict(ctx.base_assumptions)
            if fixed_variable == "revenue_growth":
                base_growth = self._base_value(ctx, "revenue_growth")
                delta = fv - base_growth
                ctx.base_assumptions["revenue_growth_path"] = [
                    g + delta for g in saved["revenue_growth_path"]
                ]
            else:
                ctx.base_assumptions[fixed_variable] = fv

            base_case = self._quick_dcf(ctx)
            row_values = self._axis_values(ctx, row_variable, None, None, steps)
            col_values = self._axis_values(ctx, col_variable, None, None, steps)

            grid: list[list[float | None]] = []
            for rv in row_values:
                row: list[float | None] = []
                for cv in col_values:
                    ov = {
                        **self._make_override(row_variable, rv, ctx),
                        **self._make_override(col_variable, cv, ctx),
                    }
                    row.append(self._quick_dcf(ctx, ov))
                grid.append(row)

            tables.append({
                "fixed_value": fv,
                "base_case_value": base_case,
                "row_values": row_values,
                "col_values": col_values,
                "grid": grid,
            })

            # Restore
            ctx.base_assumptions = saved

        result = {
            "fixed_variable": fixed_variable,
            "fixed_values": fixed_values,
            "row_variable": row_variable,
            "col_variable": col_variable,
            "tables": tables,
            "current_price": ctx.current_price,
        }

        if persist:
            all_prices = [
                p
                for t in tables
                for row in t["grid"]
                for p in row
                if p is not None
            ]
            await self._persist(
                session,
                security_id=security_id,
                entity_id=None,
                scenario_type="SENSITIVITY_3D",
                scenario_name=f"{fixed_variable} slices: {row_variable} vs {col_variable}",
                input_params={
                    "fixed_variable": fixed_variable,
                    "fixed_values": fixed_values,
                    "row_variable": row_variable,
                    "col_variable": col_variable,
                    "steps": steps,
                    "method": method,
                },
                output_data=result,
                base_case_value=tables[0]["base_case_value"] if tables else None,
                min_value=min(all_prices) if all_prices else None,
                max_value=max(all_prices) if all_prices else None,
            )

        return result

    # ------------------------------------------------------------------
    # Tornado chart
    # ------------------------------------------------------------------

    async def run_tornado(
        self,
        session: AsyncSession,
        security_id: UUID,
        *,
        variables: list[str] | None = None,
        swing_pct: float = _DEFAULT_SWING_PCT,
        method: str = "FCFF",
        persist: bool = True,
    ) -> dict[str, Any] | None:
        """For each variable, perturb ±swing_pct and record impact on price."""
        ctx = await self._load_dcf_context(session, security_id, method)
        if ctx is None:
            return None

        if variables is None:
            variables = list(_VAR_TO_KEY.keys())

        base_case = self._quick_dcf(ctx)
        if base_case is None:
            return None

        bars: list[dict] = []
        for var in variables:
            base_val = self._base_value(ctx, var)
            low_val = base_val * (1.0 - swing_pct)
            high_val = base_val * (1.0 + swing_pct)

            low_output = self._quick_dcf(ctx, self._make_override(var, low_val, ctx))
            high_output = self._quick_dcf(ctx, self._make_override(var, high_val, ctx))

            if low_output is not None and high_output is not None:
                impact_range = abs(high_output - low_output)
            else:
                impact_range = 0.0

            bars.append({
                "variable": var,
                "base_value": round(base_val, 6),
                "low_value": round(low_val, 6),
                "high_value": round(high_val, 6),
                "low_output": round(low_output, 2) if low_output is not None else None,
                "high_output": round(high_output, 2) if high_output is not None else None,
                "impact_range": round(impact_range, 2),
            })

        # Sort by impact descending
        bars.sort(key=lambda b: b["impact_range"], reverse=True)

        result = {
            "base_case_value": round(base_case, 2),
            "current_price": ctx.current_price,
            "bars": bars,
        }

        if persist:
            all_outputs = [
                v
                for b in bars
                for v in (b["low_output"], b["high_output"])
                if v is not None
            ]
            await self._persist(
                session,
                security_id=security_id,
                entity_id=None,
                scenario_type="TORNADO",
                scenario_name="Tornado Chart",
                input_params={
                    "variables": variables,
                    "swing_pct": swing_pct,
                    "method": method,
                },
                output_data=result,
                base_case_value=base_case,
                min_value=min(all_outputs) if all_outputs else None,
                max_value=max(all_outputs) if all_outputs else None,
            )

        return result

    # ------------------------------------------------------------------
    # Shock analysis
    # ------------------------------------------------------------------

    async def run_shock(
        self,
        session: AsyncSession,
        security_id: UUID,
        shock_vector: dict[str, float],
        *,
        name: str | None = None,
        method: str = "FCFF",
        persist: bool = True,
    ) -> dict[str, Any] | None:
        """Apply simultaneous additive deltas to multiple assumptions."""
        ctx = await self._load_dcf_context(session, security_id, method)
        if ctx is None:
            return None

        base_case = self._quick_dcf(ctx)
        if base_case is None:
            return None

        # Build combined override
        combined_override: dict[str, Any] = {}
        for var, delta in shock_vector.items():
            base_val = self._base_value(ctx, var)
            new_val = base_val + delta
            combined_override.update(self._make_override(var, new_val, ctx))

        shocked_value = self._quick_dcf(ctx, combined_override)

        # Individual impacts for decomposition
        individual_impacts: list[dict] = []
        for var, delta in shock_vector.items():
            base_val = self._base_value(ctx, var)
            new_val = base_val + delta
            single_ov = self._make_override(var, new_val, ctx)
            single_result = self._quick_dcf(ctx, single_ov)
            impact = (single_result - base_case) if single_result is not None else None
            individual_impacts.append({
                "variable": var,
                "delta": delta,
                "base_value": round(base_val, 6),
                "shocked_value_individual": round(single_result, 2) if single_result is not None else None,
                "impact": round(impact, 2) if impact is not None else None,
            })

        impact_pct = None
        if shocked_value is not None and base_case != 0:
            impact_pct = (shocked_value - base_case) / abs(base_case)

        result = {
            "base_case_value": round(base_case, 2),
            "shocked_value": round(shocked_value, 2) if shocked_value is not None else None,
            "impact_pct": round(impact_pct, 4) if impact_pct is not None else None,
            "current_price": ctx.current_price,
            "individual_impacts": individual_impacts,
        }

        if persist:
            await self._persist(
                session,
                security_id=security_id,
                entity_id=None,
                scenario_type="SHOCK",
                scenario_name=name or "Custom Shock",
                input_params={
                    "shock_vector": shock_vector,
                    "method": method,
                },
                output_data=result,
                base_case_value=base_case,
                min_value=shocked_value,
                max_value=base_case,
            )

        return result

    # ------------------------------------------------------------------
    # Break-even search (bisection)
    # ------------------------------------------------------------------

    async def run_breakeven(
        self,
        session: AsyncSession,
        security_id: UUID,
        variable: str,
        target_price: float,
        *,
        search_min: float | None = None,
        search_max: float | None = None,
        tolerance: float = _BREAKEVEN_TOLERANCE,
        method: str = "FCFF",
        persist: bool = True,
    ) -> dict[str, Any] | None:
        """Binary search for the assumption value that yields target_price."""
        ctx = await self._load_dcf_context(session, security_id, method)
        if ctx is None:
            return None

        base_val = self._base_value(ctx, variable)
        lo = search_min if search_min is not None else base_val - _AUTO_RANGES.get(variable, 0.05) * 5
        hi = search_max if search_max is not None else base_val + _AUTO_RANGES.get(variable, 0.05) * 5

        converged = False
        mid = (lo + hi) / 2.0
        iterations = 0

        # Determine direction: does increasing the variable increase or decrease price?
        price_lo = self._quick_dcf(ctx, self._make_override(variable, lo, ctx))
        price_hi = self._quick_dcf(ctx, self._make_override(variable, hi, ctx))

        if price_lo is None or price_hi is None:
            return {
                "variable": variable,
                "target_price": target_price,
                "breakeven_value": None,
                "converged": False,
                "iterations": 0,
            }

        # If target is outside the range, cannot converge
        if not (min(price_lo, price_hi) - tolerance <= target_price <= max(price_lo, price_hi) + tolerance):
            return {
                "variable": variable,
                "target_price": target_price,
                "breakeven_value": None,
                "converged": False,
                "iterations": 0,
            }

        increasing = price_hi > price_lo  # price increases with variable

        for i in range(_BREAKEVEN_MAX_ITER):
            iterations = i + 1
            mid = (lo + hi) / 2.0
            price_mid = self._quick_dcf(ctx, self._make_override(variable, mid, ctx))
            if price_mid is None:
                break

            if abs(price_mid - target_price) <= tolerance:
                converged = True
                break

            if increasing:
                if price_mid < target_price:
                    lo = mid
                else:
                    hi = mid
            else:
                if price_mid > target_price:
                    lo = mid
                else:
                    hi = mid

        result = {
            "variable": variable,
            "target_price": target_price,
            "breakeven_value": round(mid, 6),
            "converged": converged,
            "iterations": iterations,
            "base_value": round(base_val, 6),
        }

        if persist and converged:
            await self._persist(
                session,
                security_id=security_id,
                entity_id=None,
                scenario_type="BREAKEVEN",
                scenario_name=f"Breakeven {variable}",
                input_params={
                    "variable": variable,
                    "target_price": target_price,
                    "method": method,
                },
                output_data=result,
                base_case_value=self._quick_dcf(ctx),
                min_value=None,
                max_value=None,
            )

        return result

    # ------------------------------------------------------------------
    # Persistence helper
    # ------------------------------------------------------------------

    async def _persist(
        self,
        session: AsyncSession,
        *,
        security_id: UUID,
        entity_id: UUID | None,
        scenario_type: str,
        scenario_name: str | None,
        input_params: dict,
        output_data: dict,
        base_case_value: float | None,
        min_value: float | None,
        max_value: float | None,
    ) -> ScenarioResult:
        row = ScenarioResult(
            security_id=security_id,
            entity_id=entity_id,
            calculation_date=date.today(),
            scenario_type=scenario_type,
            scenario_name=scenario_name,
            input_params=input_params,
            output_data=output_data,
            base_case_value=base_case_value,
            min_value=min_value,
            max_value=max_value,
        )
        session.add(row)
        await session.flush()
        return row
