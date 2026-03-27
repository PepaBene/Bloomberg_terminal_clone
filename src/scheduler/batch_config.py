"""Centralized batch schedule definitions.

Each entry defines a job with its cron schedule, script path, SLA, and
domain ownership.  This module is consumed by ``scripts/run_scheduler.py``
and the SLA monitor.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BatchJob:
    """Specification for a scheduled ingestion job."""

    name: str
    cron: str  # crontab expression
    script: str  # relative to project root
    sla_minutes: int  # max allowed runtime
    domain: str
    description: str = ""
    depends_on: tuple[str, ...] = ()  # names of jobs that must complete first


# ---------------------------------------------------------------------------
# Schedule registry
# ---------------------------------------------------------------------------

BATCH_JOBS: list[BatchJob] = [
    # ── Reference Data ────────────────────────────────────────────────
    BatchJob(
        name="reference_data_refresh",
        cron="0 5 * * *",  # 5 AM daily
        script="scripts/seed_reference.py",
        sla_minutes=30,
        domain="D8",
        description="Refresh reference data (countries, currencies, exchanges).",
    ),
    # ── Macro (D7) ────────────────────────────────────────────────────
    BatchJob(
        name="fred_macro_ingest",
        cron="0 * * * *",  # hourly
        script="scripts/ingest_fred.py",
        sla_minutes=120,
        domain="D7",
        description="Pull macroeconomic data from FRED API.",
    ),
    # ── Fundamentals (D3) ─────────────────────────────────────────────
    BatchJob(
        name="edgar_xbrl_ingest",
        cron="*/15 * * * *",  # every 15 min
        script="scripts/ingest_edgar_xbrl.py",
        sla_minutes=240,
        domain="D3",
        description="Poll SEC EDGAR for new XBRL filings.",
    ),
    # ── Corporate Actions (D5) ────────────────────────────────────────
    BatchJob(
        name="edgar_8k_ingest",
        cron="*/15 * * * *",
        script="scripts/ingest_corporate_actions.py",
        sla_minutes=120,
        domain="D5",
        description="Poll SEC EDGAR for 8-K corporate event filings.",
    ),
    # ── Ownership (D6) ────────────────────────────────────────────────
    BatchJob(
        name="edgar_13f_ingest",
        cron="0 6 * * *",  # 6 AM daily
        script="scripts/ingest_ownership.py",
        sla_minutes=1440,
        domain="D6",
        description="Parse 13F-HR + Form 4 filings for ownership data.",
    ),
    BatchJob(
        name="finra_short_interest",
        cron="0 6 1,16 * *",  # 1st and 16th
        script="scripts/ingest_short_interest.py",
        sla_minutes=1440,
        domain="D6",
        description="FINRA bi-weekly short interest data.",
    ),
    # ── ESG (D9) ──────────────────────────────────────────────────────
    BatchJob(
        name="esg_ingest",
        cron="0 6 * * 1",  # Monday 6 AM
        script="scripts/ingest_esg.py",
        sla_minutes=1440,
        domain="D9",
        description="Parse 10-K/DEF 14A for ESG governance data.",
    ),
    # ── Relationships (D10) ───────────────────────────────────────────
    BatchJob(
        name="relationship_nlp_ingest",
        cron="0 6 * * 1",  # Monday 6 AM
        script="scripts/ingest_relationships.py",
        sla_minutes=1440,
        domain="D10",
        description="NLP extraction of business relationships from 10-K filings.",
    ),
    # ── EOD Prices ────────────────────────────────────────────────────
    BatchJob(
        name="polygon_eod_ingest",
        cron="0 19 * * 1-5",  # 7 PM ET weekdays
        script="scripts/ingest_eod_prices.py",
        sla_minutes=180,
        domain="D2",
        description="End-of-day price data from Polygon.io.",
    ),
    # ── Pillar 2: Analytics Engines ──────────────────────────────────
    BatchJob(
        name="analytics_ratios",
        cron="0 20 * * 1-5",  # 8 PM ET weekdays (after EOD prices at 7 PM)
        script="scripts/run_analytics_batch.py --engine e1",
        sla_minutes=120,
        domain="ANALYTICS",
        description="Compute financial ratios + DuPont + TTM for all active securities.",
    ),
    BatchJob(
        name="analytics_multiples",
        cron="0 21 * * 1-5",  # 9 PM ET weekdays (after ratios)
        script="scripts/run_analytics_batch.py --engine e2_multiples",
        sla_minutes=60,
        domain="ANALYTICS",
        description="Compute valuation multiples for all active securities.",
        depends_on=("analytics_ratios",),
    ),
    BatchJob(
        name="analytics_wacc",
        cron="0 21 * * 1-5",  # 9 PM ET weekdays (parallel with multiples)
        script="scripts/run_analytics_batch.py --engine e2_wacc",
        sla_minutes=60,
        domain="ANALYTICS",
        description="Compute WACC for all active entities.",
        depends_on=("analytics_ratios",),
    ),
    # ── E3 Quality Scoring (after E1 completes) ───────────────────────
    BatchJob(
        name="analytics_quality_scoring",
        cron="0 21 * * 1-5",  # 9 PM ET weekdays
        script="scripts/run_analytics_batch.py --engine e3",
        sla_minutes=45,
        domain="ANALYTICS",
        description="Compute Piotroski F-Score, Altman Z-Score, Beneish M-Score for all securities.",
        depends_on=("analytics_ratios",),
    ),
    # ── E5 Risk Analytics ─────────────────────────────────────────────
    BatchJob(
        name="analytics_risk_var",
        cron="0 22 * * 1-5",  # 10 PM ET weekdays
        script="scripts/run_analytics_batch.py --engine e5",
        sla_minutes=60,
        domain="ANALYTICS",
        description="Compute VaR and volatility metrics for all securities.",
        depends_on=("analytics_ratios",),
    ),
    # ── E7 Quantitative (weekly) ──────────────────────────────────────
    BatchJob(
        name="analytics_quant_weekly",
        cron="0 0 * * 0",  # Sunday midnight
        script="scripts/run_analytics_batch.py --engine e7",
        sla_minutes=120,
        domain="ANALYTICS",
        description="Compute correlation matrices and factor definitions.",
    ),
    # ── E6 Institutional Flows (daily check for quarterly filings) ────
    BatchJob(
        name="analytics_institutional_flows",
        cron="0 6 * * 1-5",  # 6 AM ET weekdays (check for new filings)
        script="scripts/run_analytics_batch.py --engine e6",
        sla_minutes=90,
        domain="ANALYTICS",
        description="Process 13F filings and compute institutional flow analytics.",
    ),
    # ── Quality ───────────────────────────────────────────────────────
    BatchJob(
        name="quality_check",
        cron="0 8 * * *",  # 8 AM daily
        script="scripts/run_quality_check.py",
        sla_minutes=60,
        domain="ALL",
        description="Run data quality checks across all domains.",
    ),
]

# Lookup by name for programmatic access
BATCH_JOBS_BY_NAME: dict[str, BatchJob] = {j.name: j for j in BATCH_JOBS}
