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
    # ── NOTE: E5 (risk/VaR), E6 (institutional flows) and E7 (quant) are
    #    NOT scheduled here. ``run_analytics_batch.py`` only accepts the
    #    --engine choices: e1, e1_trends, e1_kpis, e2_multiples, e2_wacc,
    #    e3, all. e5/e6/e7 are not wired into the batch runner (see
    #    DATA_WIRING_AUDIT.md §5.1) and only ever run live, on-demand, per
    #    API request. Scheduling them with an invalid --engine choice made
    #    argparse exit non-zero, so those jobs failed on every fire. They
    #    have been removed; re-add them only once the runner supports them.
    # ── Quality ───────────────────────────────────────────────────────
    BatchJob(
        name="quality_check",
        cron="0 8 * * *",  # 8 AM daily
        script="scripts/run_quality_check.py",
        sla_minutes=60,
        domain="ALL",
        description="Run data quality checks across all domains.",
    ),
    # ── Fixed Income (D2 supplement — real connectors existed but were
    #    never scheduled; DATA_WIRING_AUDIT.md §4.3/§5.3 flagged both as
    #    "stub extract()" from a stale read — load() was fixed, just never
    #    wired here) ────────────────────────────────────────────────────
    BatchJob(
        name="treasury_yield_curve_ingest",
        cron="30 18 * * 1-5",  # 6:30 PM ET weekdays (after EOD prices)
        script="scripts/ingest_treasury_curve.py",
        sla_minutes=30,
        domain="FI",
        description="Daily US Treasury nominal yield curve from FRED (keyless-ish, FRED_API_KEY).",
    ),
    BatchJob(
        name="credit_spreads_ingest",
        cron="30 18 * * 1-5",  # 6:30 PM ET weekdays
        script="scripts/ingest_credit_spreads.py",
        sla_minutes=30,
        domain="FI",
        description="BofA/ICE OAS credit spread indices from FRED.",
    ),
    BatchJob(
        name="fi_market_briefings",
        cron="0 19 * * 1-5",  # 7 PM ET weekdays (after curve + spreads)
        script="scripts/generate_fi_briefings.py",
        sla_minutes=15,
        domain="FI",
        description="Compute + persist FIMarketBriefing (yield-curve + credit) from real FRED data.",
        depends_on=("treasury_yield_curve_ingest", "credit_spreads_ingest"),
    ),
    # ── Pillar 3: Intelligence (added in 924e640, never scheduled —
    #    all keyless/free sources except earnings, which reuses
    #    FINNHUB_API_KEY) ────────────────────────────────────────────────
    BatchJob(
        name="proxy_governance_ingest",
        cron="0 6 * * 2",  # Tuesday 6 AM
        script="scripts/ingest_proxy.py",
        sla_minutes=1440,
        domain="P3",
        description="SEC DEF 14A proxy filings -> proxy_filings/board_members/executive_compensation/shareholder_proposals.",
    ),
    BatchJob(
        name="form4_insiders_ingest",
        cron="0 7 * * *",  # 7 AM daily
        script="scripts/ingest_form4.py",
        sla_minutes=240,
        domain="P3",
        description="SEC Form 4 -> insider_holdings + insider_transactions_p3 + insider_signals.",
    ),
    BatchJob(
        name="econ_calendar_ingest",
        cron="0 5 * * *",  # 5 AM daily
        script="scripts/ingest_econ_calendar.py",
        sla_minutes=30,
        domain="P3",
        description="FRED economic-release calendar -> economic_releases.",
    ),
    BatchJob(
        name="commodities_ingest",
        cron="0 6 * * 1-5",  # 6 AM weekdays
        script="scripts/ingest_commodities.py",
        sla_minutes=30,
        domain="P3",
        description="FRED commodity prices -> commodity_profiles/commodity_prices.",
    ),
    BatchJob(
        name="legislative_bills_ingest",
        cron="0 8 * * *",  # 8 AM daily
        script="scripts/ingest_legislative_bills.py",
        sla_minutes=30,
        domain="P3",
        description="GovInfo bills RSS (keyless) -> legislative_bills.",
    ),
    BatchJob(
        name="regulatory_actions_ingest",
        cron="15 8 * * *",  # 8:15 AM daily
        script="scripts/ingest_regulatory_actions.py",
        sla_minutes=30,
        domain="P3",
        description="Federal Register API (keyless) -> regulatory_actions.",
    ),
    BatchJob(
        name="sanctions_ingest",
        cron="0 9 * * 1",  # Monday 9 AM — SDN list changes infrequently
        script="scripts/ingest_sanctions.py",
        sla_minutes=60,
        domain="P3",
        description="OFAC SDN sanctions list (keyless CSV) -> sanctions_entries.",
    ),
    BatchJob(
        name="country_risk_ingest",
        cron="0 10 * * 1",  # Monday 10 AM — World Bank annual series
        script="scripts/ingest_country_risk.py",
        sla_minutes=60,
        domain="P3",
        description="World Bank indicators (keyless) -> non-US global_macro_indicators, country_profiles, country_risk_scores.",
    ),
    BatchJob(
        name="geopolitical_events_ingest",
        cron="0 */6 * * *",  # every 6 hours
        script="scripts/ingest_geopolitical.py",
        sla_minutes=30,
        domain="P3",
        description="GDELT 2.0 (keyless, IP-throttled) -> geopolitical_events.",
    ),
    BatchJob(
        name="filing_diff_ingest",
        cron="0 6 * * 3",  # Wednesday 6 AM
        script="scripts/ingest_filing_diff.py",
        sla_minutes=1440,
        domain="P3",
        description="Section-level 10-K/10-Q diffs from EDGAR -> filing_sections/filing_diffs.",
    ),
    BatchJob(
        name="earnings_surprises_ingest",
        cron="30 7 * * *",  # 7:30 AM daily
        script="scripts/ingest_earnings.py",
        sla_minutes=240,
        domain="P3",
        description=(
            "Finnhub actual-vs-consensus EPS -> earnings_surprises/estimate_surprises. "
            "Forward consensus estimates/guidance are NOT covered — Finnhub free tier "
            "403s on /stock/price-target and /stock/eps-estimate (needs a premium plan "
            "or another provider)."
        ),
    ),
    # ── Pillar 3: News + Sentiment (resumable, bounded per-run — safe to
    #    fire frequently; each pass picks up where the last left off via
    #    ingestion_progress) ───────────────────────────────────────────
    BatchJob(
        name="news_backfill",
        cron="*/15 * * * *",  # every 15 min
        script="scripts/backfill_news.py --batch-size 20 --max-minutes 8 --days 30",
        sla_minutes=15,
        domain="P3",
        description="Resumable Finnhub company-news backfill -> news_articles/article_entity_links.",
    ),
    BatchJob(
        name="sentiment_compute",
        cron="0 * * * *",  # hourly
        script="scripts/compute_sentiment.py --max-minutes 10",
        sla_minutes=15,
        domain="P3",
        description="Score ingested news into sentiment_scores + roll up sentiment_aggregates (no LLM required).",
        depends_on=("news_backfill",),
    ),
]

# Lookup by name for programmatic access
BATCH_JOBS_BY_NAME: dict[str, BatchJob] = {j.name: j for j in BATCH_JOBS}
