"""Compute and persist IndustryProfile rollups (GICS-sector aggregates).

The Sector Rankings page (/sector, GET /v3/industry/rankings) reads from the
``industry_profiles`` table, but nothing in the codebase ever populated it --
the model and API endpoint existed, the per-company inputs it needs already
exist in ``analytics_results`` (gross_margin, operating_margin, roic,
capex_to_revenue, revenue_yoy/3y/5y CAGR -- computed by the E1 ratio engines)
and ``eod_prices``/``equity_details`` (for market cap), but no engine or
script ever aggregated them up to the GICS-sector level and wrote a row here.
This computes that rollup at the 2-digit GICS sector level (the level the
Sector page actually ranks by) and upserts one row per sector per run.

Not computed (left NULL, same as before this script existed): median_wacc /
roic_wacc_spread (no WACC estimate exists anywhere in the codebase --
fabricating one would be worse than an honest gap) and
median_rd_to_revenue / capital_cycle_indicator (no R&D-to-revenue metric or
cycle-classification logic exists yet). revenue_dispersion / roic_dispersion
ARE computed (population stddev across the sector).

Usage:
    python -m scripts.compute_industry_profiles
    python -m scripts.compute_industry_profiles --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import uuid
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from src.database import get_session_factory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("compute_industry_profiles")

# Same mapping already used for GICS sector display names elsewhere
# (src/api/routers/research_themes.py) -- kept in sync deliberately rather
# than imported, since that module pulls in unrelated research-theme deps.
GICS_SECTOR_NAMES = {
    "10": "Energy", "15": "Materials", "20": "Industrials",
    "25": "Consumer Discretionary", "30": "Consumer Staples",
    "35": "Health Care", "40": "Financials",
    "45": "Information Technology", "50": "Communication Services",
    "55": "Utilities", "60": "Real Estate",
}

# Metrics pulled from analytics_results, keyed by the IndustryProfile column
# they feed. Each is reduced to one "latest" value per security first (a
# company can have many periods on file), then median'd across the sector.
_MEDIAN_METRICS = {
    "median_gross_margin": "gross_margin",
    "median_operating_margin": "operating_margin",
    "median_capex_to_revenue": "capex_to_revenue",
    "median_roic": "roic",
}

_SQL = text(
    """
    WITH latest_metric AS (
        SELECT DISTINCT ON (ar.security_id, ar.metric_name)
            ar.security_id, ar.metric_name, ar.value
        FROM analytics_results ar
        WHERE ar.metric_name = ANY(:metric_names)
        ORDER BY ar.security_id, ar.metric_name, ar.as_of_date DESC
    ),
    latest_price AS (
        SELECT DISTINCT ON (security_id) security_id, close
        FROM eod_prices
        ORDER BY security_id, price_date DESC
    ),
    company AS (
        SELECT
            s.security_id,
            e.gics_sector,
            lp.close * ed.shares_outstanding AS market_cap,
            MAX(CASE WHEN lm.metric_name = 'gross_margin' THEN lm.value END) AS gross_margin,
            MAX(CASE WHEN lm.metric_name = 'operating_margin' THEN lm.value END) AS operating_margin,
            MAX(CASE WHEN lm.metric_name = 'capex_to_revenue' THEN lm.value END) AS capex_to_revenue,
            MAX(CASE WHEN lm.metric_name = 'roic' THEN lm.value END) AS roic,
            MAX(CASE WHEN lm.metric_name = 'revenue_yoy' THEN lm.value END) AS revenue_yoy,
            MAX(CASE WHEN lm.metric_name = 'revenue_3y_cagr' THEN lm.value END) AS revenue_3y_cagr,
            MAX(CASE WHEN lm.metric_name = 'revenue_5y_cagr' THEN lm.value END) AS revenue_5y_cagr
        FROM securities s
        JOIN entities e ON e.entity_id = s.issuer_entity_id
        LEFT JOIN equity_details ed ON ed.security_id = s.security_id
        LEFT JOIN latest_price lp ON lp.security_id = s.security_id
        LEFT JOIN latest_metric lm ON lm.security_id = s.security_id
        WHERE e.gics_sector IS NOT NULL
        GROUP BY s.security_id, e.gics_sector, lp.close, ed.shares_outstanding
    )
    SELECT
        gics_sector,
        COUNT(*) AS company_count,
        SUM(market_cap) AS total_market_cap,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY market_cap) AS median_market_cap,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY revenue_3y_cagr) AS revenue_growth_3y_cagr,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY revenue_5y_cagr) AS revenue_growth_5y_cagr,
        STDDEV_POP(revenue_yoy) AS revenue_dispersion,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY gross_margin) AS median_gross_margin,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY operating_margin) AS median_operating_margin,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY capex_to_revenue) AS median_capex_to_revenue,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY roic) AS median_roic,
        STDDEV_POP(roic) AS roic_dispersion
    FROM company
    GROUP BY gics_sector
    """
)


async def run(dry_run: bool = False) -> None:
    factory = get_session_factory()
    today = date.today()
    async with factory() as session:
        rows = (await session.execute(_SQL, {"metric_names": list(_MEDIAN_METRICS.values()) + ["revenue_yoy", "revenue_3y_cagr", "revenue_5y_cagr"]})).all()
        logger.info("Computed rollups for %d GICS sectors", len(rows))

        if dry_run:
            for r in rows:
                logger.info("  %s (%s): %d companies, median ROIC %s", r.gics_sector, GICS_SECTOR_NAMES.get(r.gics_sector, "?"), r.company_count, r.median_roic)
            return

        for r in rows:
            existing = (
                await session.execute(
                    text(
                        "SELECT id FROM industry_profiles WHERE gics_code = :code "
                        "AND gics_level = 'SECTOR' AND as_of_date = :d"
                    ),
                    {"code": r.gics_sector, "d": today},
                )
            ).first()
            params = {
                "id": existing[0] if existing else uuid.uuid4(),
                "gics_code": r.gics_sector,
                "gics_level": "SECTOR",
                "gics_name": GICS_SECTOR_NAMES.get(r.gics_sector, r.gics_sector),
                "as_of_date": today,
                "company_count": r.company_count,
                "total_market_cap": r.total_market_cap,
                "median_market_cap": r.median_market_cap,
                "revenue_growth_3y_cagr": r.revenue_growth_3y_cagr,
                "revenue_growth_5y_cagr": r.revenue_growth_5y_cagr,
                "revenue_dispersion": r.revenue_dispersion,
                "median_gross_margin": r.median_gross_margin,
                "median_operating_margin": r.median_operating_margin,
                "median_capex_to_revenue": r.median_capex_to_revenue,
                "median_roic": r.median_roic,
                "roic_dispersion": r.roic_dispersion,
            }
            if existing:
                await session.execute(
                    text(
                        """
                        UPDATE industry_profiles SET
                            company_count = :company_count,
                            total_market_cap = :total_market_cap,
                            median_market_cap = :median_market_cap,
                            revenue_growth_3y_cagr = :revenue_growth_3y_cagr,
                            revenue_growth_5y_cagr = :revenue_growth_5y_cagr,
                            revenue_dispersion = :revenue_dispersion,
                            median_gross_margin = :median_gross_margin,
                            median_operating_margin = :median_operating_margin,
                            median_capex_to_revenue = :median_capex_to_revenue,
                            median_roic = :median_roic,
                            roic_dispersion = :roic_dispersion,
                            updated_at = now()
                        WHERE id = :id
                        """
                    ),
                    params,
                )
            else:
                await session.execute(
                    text(
                        """
                        INSERT INTO industry_profiles (
                            id, gics_code, gics_level, gics_name, as_of_date,
                            company_count, total_market_cap, median_market_cap,
                            revenue_growth_3y_cagr, revenue_growth_5y_cagr, revenue_dispersion,
                            median_gross_margin, median_operating_margin, median_capex_to_revenue,
                            median_roic, roic_dispersion, created_at, updated_at
                        ) VALUES (
                            :id, :gics_code, :gics_level, :gics_name, :as_of_date,
                            :company_count, :total_market_cap, :median_market_cap,
                            :revenue_growth_3y_cagr, :revenue_growth_5y_cagr, :revenue_dispersion,
                            :median_gross_margin, :median_operating_margin, :median_capex_to_revenue,
                            :median_roic, :roic_dispersion, now(), now()
                        )
                        """
                    ),
                    params,
                )
        await session.commit()
        logger.info("Industry profile rollup complete: %d sectors written", len(rows))


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute IndustryProfile GICS-sector rollups")
    parser.add_argument("--dry-run", action="store_true", help="Compute but don't persist")
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
