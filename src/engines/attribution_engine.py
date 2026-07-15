"""Pillar 4 Phase 2 — Performance & Attribution: Attribution Engine.

Pure computation engine for Brinson BHB sector attribution, security-level
contribution analysis, and factor-based attribution.

No database access — all functions accept and return plain data.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Fraction of total active return that the Brinson residual (interaction
# noise / non-additivity between the arithmetic effects) may consume before
# it's flagged as suspiciously large — usually signals a data mismatch
# between portfolio and benchmark sector definitions.
RESIDUAL_WARNING_RATIO = 0.10
# Absolute floor for the same check when total_active_return is ~0 (a ratio
# would be meaningless/undefined there).
RESIDUAL_WARNING_ABS_FLOOR = 0.005

# Tolerance for validating that portfolio/benchmark sector weights sum to
# ~1.0 (100%) before running Brinson attribution.
WEIGHT_SUM_TOLERANCE = 0.01


# ── Dataclasses ─────────────────────────────────────────────────────────


@dataclass
class SectorAttribution:
    """Brinson attribution for a single sector."""
    sector: str
    portfolio_weight: float
    benchmark_weight: float
    portfolio_return: float
    benchmark_return: float
    allocation_effect: float
    selection_effect: float
    interaction_effect: float
    total_effect: float


@dataclass
class SecurityContribution:
    """Return contribution from a single security."""
    ticker: str
    weight: float
    security_return: float
    contribution: float  # weight * return


@dataclass
class FactorAttribution:
    """Attribution for a single factor."""
    factor: str
    portfolio_exposure: float
    benchmark_exposure: float
    active_exposure: float
    factor_return: float
    contribution: float  # active_exposure * factor_return


@dataclass
class BrinsonResult:
    """Full Brinson BHB attribution result."""
    total_portfolio_return: float
    total_benchmark_return: float
    total_active_return: float
    total_allocation: float
    total_selection: float
    total_interaction: float
    residual: float
    sector_detail: list[SectorAttribution] = field(default_factory=list)


@dataclass
class FactorResult:
    """Factor attribution result."""
    total_factor_return: float
    stock_specific_return: float
    factors: list[FactorAttribution] = field(default_factory=list)


# ── Sector Weight & Return Helpers ─────────────────────────────────────


def compute_sector_weights(
    positions: list[dict],
    total_value: float,
) -> dict:
    """Compute sector weights from positions.

    Each position: {sector: str, market_value: float}.
    Returns {sector: weight}.
    """
    if total_value == 0.0:
        return {}

    sector_values: dict[str, float] = {}
    for pos in positions:
        sector = pos["sector"]
        sector_values[sector] = sector_values.get(sector, 0.0) + pos["market_value"]

    return {
        sector: value / total_value
        for sector, value in sector_values.items()
    }


def compute_sector_returns(positions: list[dict]) -> dict:
    """Compute weighted average return within each sector.

    Each position: {sector: str, market_value: float, return: float}.
    Returns {sector: weighted_average_return}.
    """
    sector_mv: dict[str, float] = {}
    sector_weighted_ret: dict[str, float] = {}

    for pos in positions:
        sector = pos["sector"]
        mv = pos["market_value"]
        ret = pos["return"]
        sector_mv[sector] = sector_mv.get(sector, 0.0) + mv
        sector_weighted_ret[sector] = (
            sector_weighted_ret.get(sector, 0.0) + mv * ret
        )

    results: dict[str, float] = {}
    for sector in sector_mv:
        if sector_mv[sector] != 0.0:
            results[sector] = sector_weighted_ret[sector] / sector_mv[sector]
        else:
            results[sector] = 0.0

    return results


# ── Brinson BHB Effects ────────────────────────────────────────────────


def compute_allocation_effect(
    wp: float,
    wb: float,
    rb_s: float,
    rb: float,
) -> float:
    """Allocation effect: (wp - wb) * (rb_s - rb).

    wp: portfolio weight in sector
    wb: benchmark weight in sector
    rb_s: benchmark return of sector
    rb: total benchmark return
    """
    return (wp - wb) * (rb_s - rb)


def compute_selection_effect(
    wb: float,
    rp_s: float,
    rb_s: float,
) -> float:
    """Selection effect: wb * (rp_s - rb_s).

    wb: benchmark weight in sector
    rp_s: portfolio return of sector
    rb_s: benchmark return of sector
    """
    return wb * (rp_s - rb_s)


def compute_interaction_effect(
    wp: float,
    wb: float,
    rp_s: float,
    rb_s: float,
) -> float:
    """Interaction effect: (wp - wb) * (rp_s - rb_s).

    wp: portfolio weight in sector
    wb: benchmark weight in sector
    rp_s: portfolio return of sector
    rb_s: benchmark return of sector
    """
    return (wp - wb) * (rp_s - rb_s)


def compute_brinson_attribution(
    portfolio_sectors: list[dict],
    benchmark_sectors: list[dict],
    total_benchmark_return: float,
) -> BrinsonResult:
    """Compute full Brinson BHB attribution.

    Each sector dict: {sector: str, weight: float, return: float}.
    """
    # Sanity-check that weights are actual portfolio/benchmark fractions
    # (should sum to ~1.0) rather than, e.g., raw dollar amounts or a
    # subset of sectors — a silent mismatch here would skew every effect.
    port_weight_sum = sum(s["weight"] for s in portfolio_sectors)
    if portfolio_sectors and abs(port_weight_sum - 1.0) > WEIGHT_SUM_TOLERANCE:
        logger.warning(
            "Brinson attribution: portfolio sector weights sum to %.4f, "
            "expected ~1.0",
            port_weight_sum,
        )
    bench_weight_sum = sum(s["weight"] for s in benchmark_sectors)
    if benchmark_sectors and abs(bench_weight_sum - 1.0) > WEIGHT_SUM_TOLERANCE:
        logger.warning(
            "Brinson attribution: benchmark sector weights sum to %.4f, "
            "expected ~1.0",
            bench_weight_sum,
        )

    # Build lookup maps
    port_map = {s["sector"]: s for s in portfolio_sectors}
    bench_map = {s["sector"]: s for s in benchmark_sectors}

    # Union of all sectors
    all_sectors = set(port_map.keys()) | set(bench_map.keys())

    sector_details: list[SectorAttribution] = []
    total_alloc = 0.0
    total_select = 0.0
    total_interact = 0.0

    total_port_return = 0.0
    for s in portfolio_sectors:
        total_port_return += s["weight"] * s["return"]

    for sector in sorted(all_sectors):
        wp = port_map[sector]["weight"] if sector in port_map else 0.0
        wb = bench_map[sector]["weight"] if sector in bench_map else 0.0
        rp_s = port_map[sector]["return"] if sector in port_map else 0.0
        rb_s = bench_map[sector]["return"] if sector in bench_map else 0.0

        alloc = compute_allocation_effect(wp, wb, rb_s, total_benchmark_return)
        select = compute_selection_effect(wb, rp_s, rb_s)
        interact = compute_interaction_effect(wp, wb, rp_s, rb_s)

        sector_details.append(SectorAttribution(
            sector=sector,
            portfolio_weight=wp,
            benchmark_weight=wb,
            portfolio_return=rp_s,
            benchmark_return=rb_s,
            allocation_effect=alloc,
            selection_effect=select,
            interaction_effect=interact,
            total_effect=alloc + select + interact,
        ))

        total_alloc += alloc
        total_select += select
        total_interact += interact

    total_active = total_port_return - total_benchmark_return
    residual = total_active - (total_alloc + total_select + total_interact)

    residual_threshold = max(
        abs(total_active) * RESIDUAL_WARNING_RATIO, RESIDUAL_WARNING_ABS_FLOOR
    )
    if abs(residual) > residual_threshold:
        logger.warning(
            "Brinson attribution residual %.6f is large relative to total "
            "active return %.6f (allocation=%.6f, selection=%.6f, "
            "interaction=%.6f) — check sector coverage/weight consistency "
            "between portfolio and benchmark",
            residual, total_active, total_alloc, total_select, total_interact,
        )

    return BrinsonResult(
        total_portfolio_return=total_port_return,
        total_benchmark_return=total_benchmark_return,
        total_active_return=total_active,
        total_allocation=total_alloc,
        total_selection=total_select,
        total_interaction=total_interact,
        residual=residual,
        sector_detail=sector_details,
    )


# ── Security Contribution ──────────────────────────────────────────────


def compute_security_contribution(
    positions: list[dict],
) -> list[SecurityContribution]:
    """Compute return contribution for each security.

    Each position: {ticker: str, weight: float, return: float}.
    contribution = weight * return.
    """
    results: list[SecurityContribution] = []
    for pos in positions:
        contrib = pos["weight"] * pos["return"]
        results.append(SecurityContribution(
            ticker=pos["ticker"],
            weight=pos["weight"],
            security_return=pos["return"],
            contribution=contrib,
        ))
    return results


def compute_top_contributors(
    contributions: list[SecurityContribution],
    n: int = 5,
) -> list[SecurityContribution]:
    """Return top N contributors sorted by contribution descending."""
    return sorted(contributions, key=lambda c: c.contribution, reverse=True)[:n]


def compute_bottom_contributors(
    contributions: list[SecurityContribution],
    n: int = 5,
) -> list[SecurityContribution]:
    """Return bottom N contributors sorted by contribution ascending."""
    return sorted(contributions, key=lambda c: c.contribution)[:n]


# ── Factor Attribution ─────────────────────────────────────────────────


def compute_factor_attribution(
    portfolio_exposures: dict,
    benchmark_exposures: dict,
    factor_returns: dict,
) -> FactorResult:
    """Compute factor-based attribution.

    For each factor: contribution = active_exposure * factor_return.
    Standard factors: {value, momentum, quality, size, low_vol, growth}.
    """
    all_factors = set(portfolio_exposures.keys()) | set(benchmark_exposures.keys())
    # Only include factors that have returns
    dropped_factors = all_factors - set(factor_returns.keys())
    if dropped_factors:
        logger.warning(
            "Factor attribution: dropping factor(s) with no entry in "
            "factor_returns: %s",
            sorted(dropped_factors),
        )
    all_factors &= set(factor_returns.keys())

    factors: list[FactorAttribution] = []
    total_factor_return = 0.0

    for factor in sorted(all_factors):
        port_exp = portfolio_exposures.get(factor, 0.0)
        bench_exp = benchmark_exposures.get(factor, 0.0)
        active_exp = port_exp - bench_exp
        f_ret = factor_returns.get(factor, 0.0)
        contrib = active_exp * f_ret

        factors.append(FactorAttribution(
            factor=factor,
            portfolio_exposure=port_exp,
            benchmark_exposure=bench_exp,
            active_exposure=active_exp,
            factor_return=f_ret,
            contribution=contrib,
        ))
        total_factor_return += contrib

    return FactorResult(
        total_factor_return=total_factor_return,
        stock_specific_return=0.0,  # set by caller via compute_stock_specific_return
        factors=factors,
    )


def compute_stock_specific_return(
    total_active: float,
    total_factor: float,
) -> float:
    """Stock-specific return: total_active - total_factor."""
    return total_active - total_factor


# ── Multi-Period Linking ───────────────────────────────────────────────


def link_multi_period_attribution(
    period_results: list[BrinsonResult],
) -> BrinsonResult:
    """Link multiple single-period Brinson results.

    NOTE — arithmetic (not geometric/Carino) linking: each period's
    allocation/selection/interaction effects are simply summed. This is a
    documented approximation, not a bug: true multi-period Brinson linking
    requires a Carino (or GRAP) log-scaling adjustment per period so effects
    compound consistently with the geometrically-linked total return.
    Arithmetic linking is exact only when returns are small/period count is
    low; for long/volatile periods it can drift from the geometrically
    linked total active return (the ``residual`` field captures this gap —
    see the large-residual warning in ``compute_brinson_attribution``).
    """
    if not period_results:
        return BrinsonResult(
            total_portfolio_return=0.0,
            total_benchmark_return=0.0,
            total_active_return=0.0,
            total_allocation=0.0,
            total_selection=0.0,
            total_interaction=0.0,
            residual=0.0,
            sector_detail=[],
        )

    total_port = sum(r.total_portfolio_return for r in period_results)
    total_bench = sum(r.total_benchmark_return for r in period_results)
    total_alloc = sum(r.total_allocation for r in period_results)
    total_select = sum(r.total_selection for r in period_results)
    total_interact = sum(r.total_interaction for r in period_results)
    total_active = total_port - total_bench
    residual = total_active - (total_alloc + total_select + total_interact)

    # Aggregate sector details across periods
    sector_alloc: dict[str, float] = {}
    sector_select: dict[str, float] = {}
    sector_interact: dict[str, float] = {}
    # Beginning-of-period (BOP) weight per sector: the weight recorded on
    # the *first* period_results entry each sector appears in. period_results
    # is caller-supplied in chronological order, so this is the sector's
    # weight at the start of the linked window — the standard convention
    # for multi-period attribution — rather than an average across periods,
    # which would blend in weight drift that happened *during* the window.
    sector_bop_pw: dict[str, float] = {}
    sector_bop_bw: dict[str, float] = {}
    sector_pr: dict[str, list[float]] = {}
    sector_br: dict[str, list[float]] = {}

    for result in period_results:
        for sd in result.sector_detail:
            s = sd.sector
            sector_alloc[s] = sector_alloc.get(s, 0.0) + sd.allocation_effect
            sector_select[s] = sector_select.get(s, 0.0) + sd.selection_effect
            sector_interact[s] = sector_interact.get(s, 0.0) + sd.interaction_effect
            sector_bop_pw.setdefault(s, sd.portfolio_weight)
            sector_bop_bw.setdefault(s, sd.benchmark_weight)
            sector_pr.setdefault(s, []).append(sd.portfolio_return)
            sector_br.setdefault(s, []).append(sd.benchmark_return)

    linked_sectors: list[SectorAttribution] = []
    for sector in sorted(sector_alloc.keys()):
        alloc = sector_alloc[sector]
        select = sector_select[sector]
        interact = sector_interact[sector]
        avg_pr = sum(sector_pr[sector]) / len(sector_pr[sector])
        avg_br = sum(sector_br[sector]) / len(sector_br[sector])

        linked_sectors.append(SectorAttribution(
            sector=sector,
            portfolio_weight=sector_bop_pw[sector],
            benchmark_weight=sector_bop_bw[sector],
            portfolio_return=avg_pr,
            benchmark_return=avg_br,
            allocation_effect=alloc,
            selection_effect=select,
            interaction_effect=interact,
            total_effect=alloc + select + interact,
        ))

    return BrinsonResult(
        total_portfolio_return=total_port,
        total_benchmark_return=total_bench,
        total_active_return=total_active,
        total_allocation=total_alloc,
        total_selection=total_select,
        total_interaction=total_interact,
        residual=residual,
        sector_detail=linked_sectors,
    )
