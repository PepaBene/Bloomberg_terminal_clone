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
    # ── Entity / Security Master (D1) ─────────────────────────────────
    #    ROOT OF THE INGESTION CASCADE. Everything downstream (XBRL,
    #    ownership, ESG, segments, analytics) builds its CIK/ticker work
    #    lists from these tables. They were reachable only via `make`
    #    targets and so never ran in a normal deployment, leaving the
    #    master empty and silently no-oping every downstream job. Scheduled
    #    here early each morning, before the filing-derived jobs.
    BatchJob(
        name="edgar_entities_ingest",
        cron="0 3 * * *",  # 3 AM daily
        script="scripts/ingest_edgar.py",
        sla_minutes=240,
        domain="D1",
        description="SEC EDGAR company tickers -> entities + CIK identifiers (entity master).",
    ),
    BatchJob(
        name="gleif_lei_ingest",
        cron="30 3 * * *",  # 3:30 AM daily (after entity master)
        script="scripts/ingest_gleif.py",
        sla_minutes=240,
        domain="D1",
        description="GLEIF LEI records -> entity LEI identifiers + legal hierarchy.",
        depends_on=("edgar_entities_ingest",),
    ),
    BatchJob(
        name="openfigi_securities_ingest",
        cron="0 4 * * *",  # 4 AM daily (after entity master)
        script="scripts/ingest_openfigi.py",
        sla_minutes=240,
        domain="D1",
        description="OpenFIGI mapping -> securities + FIGI/ticker identifiers (security master).",
        depends_on=("edgar_entities_ingest",),
    ),
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
    BatchJob(
        name="segments_ingest",
        cron="0 */4 * * *",  # every 4 hours
        script="scripts/ingest_segments.py",
        sla_minutes=120,
        domain="D3",
        description=(
            "SEC EDGAR XBRL company-facts dimensional segment members -> "
            "segment_data (business/geographic revenue+income+assets). Was a "
            "real, tested connector class with no script entry point at all "
            "(Makefile's ingest-segments target pointed at a nonexistent "
            "module) — now wired end-to-end."
        ),
    ),
    # ── Corporate Actions (D5) ────────────────────────────────────────
    BatchJob(
        name="corporate_actions_ingest",
        cron="0 6 * * *",  # 6 AM daily
        script="scripts/ingest_corporate_actions.py",
        sla_minutes=120,
        domain="D5",
        description=(
            "Dividends + splits from Polygon.io -> corporate_actions/"
            "dividend_actions/split_actions, with real ex/record/pay dates "
            "(replaces the prior Edgar8KConnector wiring, which actually "
            "wrote to the unrelated eight_k_events table)."
        ),
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
    # ── E3 Composite Scores (after Piotroski/Altman/Beneish complete —
    #    CompositeScoreEngine reads their AnalyticsResult rows) ───────────
    BatchJob(
        name="analytics_composite_scores",
        cron="30 21 * * 1-5",  # 9:30 PM ET weekdays (after quality scoring)
        script="scripts/run_analytics_batch.py --engine e3_composites",
        sla_minutes=45,
        domain="ANALYTICS",
        description=(
            "Compute earnings-quality/financial-strength/dividend-safety/"
            "value-trap composite scores -> composite_scores. Was a real, "
            "correct engine with zero callers anywhere in the batch "
            "pipeline (only reachable by a direct API call, which itself "
            "404'd on a score_type case mismatch) -- /scores/*/composites "
            "and its 4 single-score siblings were permanently empty."
        ),
        depends_on=("analytics_quality_scoring",),
    ),
    # ── E1 Trends / Industry KPIs / E2 DCF-Comps-FootballField (real
    #    engines, valid --engine choices in run_analytics_batch.py's
    #    ENGINE_GROUPS -- e1_trends/e1_kpis/e2_dcf/e2_comps/
    #    e2_football_field were never actually scheduled anywhere, so a
    #    security's trend analysis / industry KPIs / DCF / comps /
    #    football-field range only ever got computed if something else
    #    (recompute_security, triggered by an XBRL refresh) happened to
    #    invoke "all". Fundamentals-driven, so a daily backstop cron (no
    #    --refresh-days) that only picks up new/never-computed securities
    #    is sufficient -- recompute_security already refreshes existing
    #    ones on new filings.
    BatchJob(
        name="analytics_trends",
        cron="0 22 * * 1-5",  # 10 PM ET weekdays (after quality scoring settles)
        script="scripts/run_analytics_batch.py --engine e1_trends",
        sla_minutes=60,
        domain="ANALYTICS",
        description="Compute revenue/earnings/margin trend analysis for all active securities.",
        depends_on=("analytics_ratios",),
    ),
    BatchJob(
        name="analytics_industry_kpis",
        cron="10 22 * * 1-5",
        script="scripts/run_analytics_batch.py --engine e1_kpis",
        sla_minutes=45,
        domain="ANALYTICS",
        description="Compute industry-specific KPIs (rule-of-40, FFO, efficiency ratio, capex intensity, etc.) for all active securities.",
        depends_on=("analytics_ratios",),
    ),
    BatchJob(
        name="analytics_dcf",
        cron="20 22 * * 1-5",
        script="scripts/run_analytics_batch.py --engine e2_dcf",
        sla_minutes=90,
        domain="ANALYTICS",
        description="Compute DCF valuations for all active securities.",
        depends_on=("analytics_wacc",),
    ),
    BatchJob(
        name="analytics_comps",
        cron="30 22 * * 1-5",
        script="scripts/run_analytics_batch.py --engine e2_comps",
        sla_minutes=90,
        domain="ANALYTICS",
        description="Compute comparable-company analysis for all active securities.",
        depends_on=("analytics_multiples",),
    ),
    BatchJob(
        name="analytics_football_field",
        cron="0 23 * * 1-5",
        script="scripts/run_analytics_batch.py --engine e2_football_field",
        sla_minutes=45,
        domain="ANALYTICS",
        description="Assemble DCF + comps football-field valuation ranges for all active securities.",
        depends_on=("analytics_dcf", "analytics_comps"),
    ),
    # ── E5 risk / E7 quant: unlike the fundamentals-driven engines above,
    #    these depend on the day's new EOD prices, which recompute_security's
    #    XBRL-triggered refresh never catches -- --refresh-days-scoped
    #    forces a daily recompute of ONLY this engine (not a full
    #    whole-security wipe like --refresh-days would cause; see
    #    reopen_stale_engine_analytics's docstring in run_analytics_batch.py).
    BatchJob(
        name="analytics_risk_var",
        cron="45 19 * * 1-5",  # 7:45 PM ET weekdays (after EOD prices land at 7 PM)
        script="scripts/run_analytics_batch.py --engine e5_risk --refresh-days-scoped 1",
        sla_minutes=60,
        domain="ANALYTICS",
        description=(
            "Compute VaR/CVaR/stress/factor-exposure risk metrics for all active "
            "securities. Was a real, correct engine (E5) with no scheduled caller at "
            "all -- only ever ran live, on-demand, per API request."
        ),
        depends_on=("analytics_ratios", "polygon_eod_ingest"),
    ),
    # ── E7 quant runs weekly, not daily: beta/correlation/autocorrelation/
    #    stationarity are computed over trailing return windows that don't
    #    materially shift day to day, so a weekly scoped refresh (vs E5's
    #    daily one) is enough to keep them current without redundant recompute.
    BatchJob(
        name="analytics_quant_weekly",
        cron="0 20 * * 0",  # Sunday 8 PM ET (after the week's EOD prices settle)
        script="scripts/run_analytics_batch.py --engine e7_quant --refresh-days-scoped 7",
        sla_minutes=60,
        domain="ANALYTICS",
        description=(
            "Compute beta/correlation/autocorrelation/stationarity quant metrics for "
            "all active securities. Same previously-unscheduled gap as analytics_risk_var."
        ),
        depends_on=("polygon_eod_ingest",),
    ),
    # ── E6 institutional flows: depends on 13F/Form4/short-interest
    #    ownership data, which updates on its own (much slower) cadence --
    #    weekly refresh matches that, not the daily price-driven cadence
    #    risk/quant need.
    BatchJob(
        name="analytics_institutional_flows",
        cron="0 9 * * *",  # 9 AM daily (after ownership ingestion settles)
        script="scripts/run_analytics_batch.py --engine e6 --refresh-days-scoped 7",
        sla_minutes=60,
        domain="ANALYTICS",
        description=(
            "Compute institutional-ownership flow metrics (accumulation/distribution, "
            "smart-money signal, squeeze potential) for all active securities. Was a "
            "real, correct engine (E6) with no scheduled caller at all."
        ),
        depends_on=("edgar_13f_ingest",),
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
    BatchJob(
        name="money_market_ingest",
        cron="45 18 * * 1-5",  # 6:45 PM ET weekdays
        script="scripts/ingest_money_market.py",
        sla_minutes=30,
        domain="FI",
        description=(
            "SOFR / effective + target fed funds / T-bill / commercial paper "
            "/ prime rates from FRED (reuses FRED_API_KEY) -> "
            "money_market_rates. extract() was previously a stub returning "
            "[]; now mirrors the fred_credit_spreads.py pattern."
        ),
    ),
    BatchJob(
        name="treasury_securities_ingest",
        cron="0 7 * * *",  # 7 AM daily
        script="scripts/ingest_treasury_securities.py",
        sla_minutes=60,
        domain="FI",
        description="US Treasury marketable securities (Fiscal Data API, keyless) -> treasury_securities.",
    ),
    BatchJob(
        name="capital_structure_ingest",
        cron="0 5 * * *",  # 5 AM daily
        script="scripts/ingest_capital_structure.py",
        sla_minutes=240,
        domain="FI",
        description=(
            "SEC EDGAR 10-K XBRL debt aggregates + footnote-parsed debt "
            "tranches -> capital_structures/debt_tranches, plus (when a "
            "matching traded FI security exists) fixed_income_details / "
            "call_put_schedule."
        ),
    ),
    BatchJob(
        name="credit_ratings_ingest",
        cron="15 5 * * *",  # 5:15 AM daily
        script="scripts/ingest_credit_ratings.py",
        sla_minutes=240,
        domain="FI",
        description=(
            "SEC EDGAR 8-K rating-agency mentions -> credit_rating_events, "
            "plus (when a rating was actually extracted) security-level "
            "credit_ratings for the issuer's fixed-income securities."
        ),
    ),
    # ── Corporate Events & Fund Holdings (real, tested connectors that
    #    were Makefile-only and never scheduled -> /deals, /ipos and
    #    /fund-holdings stayed empty in a normal deployment) ─────────────
    BatchJob(
        name="ma_deals_ingest",
        cron="0 6 * * *",  # 6 AM daily
        script="scripts/ingest_ma_deals.py --days-back 90",
        sla_minutes=240,
        domain="D5",
        description="SEC EDGAR 8-K merger/acquisition disclosures -> ma_deals.",
        depends_on=("edgar_entities_ingest",),
    ),
    BatchJob(
        name="ipo_events_ingest",
        cron="30 6 * * *",  # 6:30 AM daily
        script="scripts/ingest_ipo.py --days-back 365",
        sla_minutes=240,
        domain="D5",
        description="SEC EDGAR S-1/424B IPO events -> ipo_events.",
        depends_on=("edgar_entities_ingest",),
    ),
    BatchJob(
        name="nport_holdings_ingest",
        cron="0 8 * * 1",  # Monday 8 AM (N-PORT filed monthly, quarterly public)
        script="scripts/ingest_nport.py --days-back 120",
        sla_minutes=1440,
        domain="D6",
        description="SEC N-PORT fund portfolio holdings -> fund_holdings.",
        depends_on=("edgar_entities_ingest",),
    ),
    # ── Pillar 1 Supplement: Executives + Macro Policy (real, tested
    #    connectors that were only reachable via manual `make` targets —
    #    the same "orphaned engine" pattern already fixed for Pillar 3) ──
    BatchJob(
        name="executives_ingest",
        cron="0 7 * * 3",  # Wednesday 7 AM
        script="scripts/ingest_executives.py",
        sla_minutes=1440,
        domain="P1S",
        description="SEC EDGAR ownership filings -> executives/directors.",
    ),
    BatchJob(
        name="fomc_meetings_ingest",
        cron="20 5 * * *",  # 5:20 AM daily
        script="scripts/ingest_fomc.py",
        sla_minutes=30,
        domain="P1S",
        description="FOMC rate decisions derived from FRED target-range series (reuses FRED_API_KEY).",
    ),
    BatchJob(
        name="central_bank_policy_ingest",
        cron="25 5 * * *",  # 5:25 AM daily
        script="scripts/ingest_central_bank.py",
        sla_minutes=30,
        domain="P1S",
        description=(
            "Central-bank policy decisions (Fed/ECB/BOE) derived from FRED "
            "policy-rate series. ECB/BOE series are present but, per the "
            "connector's own docs, not yet validated against live payloads."
        ),
    ),
    # ── Pillar 1 Supplement: Rollups (pure computation over already-
    #    ingested data, no external calls — same orphaned pattern) ──────
    BatchJob(
        name="ownership_summary_compute",
        cron="0 8 * * *",  # 8 AM daily (after 13F/Form4/short-interest ingest)
        script="scripts/compute_ownership_summary.py",
        sla_minutes=60,
        domain="P1S",
        description="Rolls up InstitutionalHolding/InsiderHolding/ShortInterest -> ownership_summaries.",
        depends_on=("edgar_13f_ingest",),
    ),
    BatchJob(
        name="technical_studies_compute",
        cron="30 19 * * 1-5",  # 7:30 PM ET weekdays (after EOD prices)
        script="scripts/compute_technicals.py",
        sla_minutes=60,
        domain="P1S",
        description="Computes technical indicators from EODPrice history -> technical_study_values.",
        depends_on=("polygon_eod_ingest",),
    ),
    BatchJob(
        name="esg_temperature_compute",
        cron="15 7 * * 1",  # Monday 7:15 AM (after weekly ESG ingest)
        script="scripts/compute_esg_temperature.py",
        sla_minutes=30,
        domain="P1S",
        description="Paris-alignment ESG implied-temperature scoring -> esg_temperature_scores.",
        depends_on=("esg_ingest",),
    ),
    BatchJob(
        name="debt_maturity_compute",
        cron="30 5 * * *",  # 5:30 AM daily (after capital structure ingest)
        script="scripts/compute_debt_maturity.py",
        sla_minutes=30,
        domain="P1S",
        description="Buckets debt_tranches by maturity year -> debt_maturity_profiles/maturity_buckets.",
        depends_on=("capital_structure_ingest",),
    ),
    BatchJob(
        name="shares_outstanding_compute",
        cron="0 6 * * *",  # 6 AM daily (after overnight XBRL polling settles)
        script="scripts/compute_shares_outstanding.py",
        sla_minutes=30,
        domain="P1S",
        description=(
            "Fills equity_details.shares_outstanding from the most recent XBRL "
            "period's basic/diluted shares (feeds market-cap + per-share "
            "valuation). Was fully orphaned — not in cron or Makefile."
        ),
        depends_on=("edgar_xbrl_ingest",),
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
        name="eia_commodity_inventory_ingest",
        cron="30 10 * * 3",  # Wednesday 10:30 AM ET, after EIA's Wed AM petroleum
                              # status + natural gas storage report releases
        script="scripts/ingest_eia_commodity_inventory.py",
        sla_minutes=30,
        domain="P3",
        description=(
            "EIA weekly US petroleum/natural-gas stock levels (WTI, GASOLINE, "
            "NATGAS) -> commodity_inventories. Real supply/demand data source "
            "for GET /global/commodities/{code}/supply-demand (R-023 fix) -- "
            "requires EIA_API_KEY (free)."
        ),
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
    BatchJob(
        name="theme_scores_compute",
        cron="0 7 * * *",  # 7 AM daily (after fundamentals/EOD prices settle)
        script="scripts/compute_theme_scores.py",
        sla_minutes=30,
        domain="P3",
        description=(
            "Compute macro_theme_scores (GDP/inflation/rates/oil exposure per entity) "
            "from real GICS-sector sensitivity -- pure local computation, no external calls."
        ),
    ),
    # ── Pillar 3 Data-Source Build-Out (previously "no data source chosen"
    #    gaps -- see CONNECTING_TO_REAL_DATA.md for setup/API-key details.
    #    All flagged FLAG — UNTESTED AGAINST LIVE DATA in their module
    #    docstrings: written to-pattern against each source's documented
    #    shape, unit-tested against synthetic fixtures, never exercised
    #    against a live response in this sandbox (outbound network access
    #    is blocked here). Validate against real payloads before relying on
    #    these in production. NOTE: FINRA TRACE is deliberately NOT
    #    scheduled here -- it ingests a local bulk-dissemination file a
    #    human must obtain via registration; see
    #    scripts/ingest_finra_trace.py and CONNECTING_TO_REAL_DATA.md. ────
    BatchJob(
        name="esg_controversies_ingest",
        cron="30 6 * * 1",  # Monday 6:30 AM (after esg_ingest)
        script="scripts/ingest_esg_controversies.py",
        sla_minutes=240,
        domain="P3",
        description=(
            "ESG controversies via GDELT DOC 2.0 API (keyless) -- keyword+tone "
            "heuristic classification into controversy_type/severity, an "
            "explicitly-documented proxy, not an authoritative RepRisk/MSCI-style "
            "rating. Optional ESG_CONTROVERSY_FEED_URL overrides with a paid feed."
        ),
    ),
    BatchJob(
        name="esg_environmental_ingest",
        cron="40 6 * * 1",  # Monday 6:40 AM (after esg_controversies_ingest)
        script="scripts/ingest_esg_environmental.py",
        sla_minutes=240,
        domain="P3",
        description=(
            "Environmental/social ESG scores from 10-K disclosure text (GHG, "
            "renewable %, diversity, safety), a documented deterministic proxy "
            "-- not an authoritative score. Optional EPA Envirofacts GHGRP "
            "enrichment (keyless, EPA_ENVIROFACTS_BASE_URL)."
        ),
    ),
    BatchJob(
        name="bond_issuances_ingest",
        cron="0 5 * * *",  # 5 AM daily (alongside capital_structure_ingest)
        script="scripts/ingest_bond_issuances.py",
        sla_minutes=240,
        domain="FI",
        description=(
            "Primary-market bond issuances via SEC EDGAR full-text search over "
            "424B2/424B3/424B5/FWP filings, regex pricing-term extraction "
            "(coupon/maturity/size/bookrunners). Optional BOND_ISSUANCES_FEED_URL "
            "overrides with a paid new-issue-monitor feed."
        ),
    ),
    BatchJob(
        name="agency_bonds_ingest",
        cron="10 5 * * *",  # 5:10 AM daily
        script="scripts/ingest_agency_bonds.py",
        sla_minutes=60,
        domain="FI",
        description=(
            "Agency/GSE bonds from FHLB Office of Finance consolidated-"
            "obligation data (FHLB_OF_DATA_URL, CSV/JSON auto-detected). "
            "Optional AGENCY_BONDS_FEED_URL overrides with a paid feed."
        ),
    ),
    BatchJob(
        name="consensus_estimates_ingest",
        cron="0 6 * * *",  # 6 AM daily
        script="scripts/ingest_consensus_estimates.py",
        sla_minutes=60,
        domain="P3",
        description=(
            "Forward consensus EPS/revenue estimates from Alpha Vantage "
            "(ALPHA_VANTAGE_API_KEY; free tier is 25 requests/day -- default "
            "--limit keeps each run within that cap). Fills the gap left by "
            "Finnhub's free tier 403ing on /stock/eps-estimate."
        ),
    ),
    BatchJob(
        name="guidance_tracking_ingest",
        cron="45 7 * * *",  # 7:45 AM daily (after earnings_surprises_ingest)
        script="scripts/ingest_guidance.py",
        sla_minutes=240,
        domain="P3",
        description=(
            "Management guidance figures extracted from SEC EDGAR 8-K Item "
            "2.02 filing bodies (regex range/point extraction), with an "
            "optional best-effort Claude augmentation pass when "
            "ANTHROPIC_API_KEY is configured."
        ),
        depends_on=("earnings_surprises_ingest",),
    ),
    BatchJob(
        name="subsidiaries_ingest",
        cron="0 6 * * 3",  # Wednesday 6 AM (alongside filing_diff_ingest cadence)
        script="scripts/ingest_subsidiaries.py",
        sla_minutes=1440,
        domain="P3",
        description=(
            "SEC Exhibit 21 (subsidiary list) filings -> subsidiaries, feeding "
            "the complex_structure engine's org-tree analysis. EX-21 is filed "
            "annually alongside the 10-K, hence the weekly rather than daily "
            "cadence."
        ),
    ),
    # ── Pillar 4: Portfolio Backtesting ───────────────────────────────
    BatchJob(
        name="backtest_worker",
        cron="*/15 * * * *",  # every 15 min
        script="scripts/run_backtest_worker.py",
        sla_minutes=30,
        domain="P4",
        description=(
            "Advances PENDING BacktestRun rows (from POST /v1/analytics/backtest) "
            "to COMPLETED/FAILED: runs the strategy through the real screening "
            "engine, weights the basket, simulates it day-by-day against stored "
            "EOD prices, and persists a BacktestResult. Run bare (no CLI args) "
            "so it drains the pending queue and exits each invocation, per "
            "run_scheduler.py's no-args subprocess convention."
        ),
    ),
    BatchJob(
        name="performance_snapshot_backfill",
        cron="0 22 * * 1-5",  # 10 PM ET weekdays (after NAV/EOD prices settle)
        script="scripts/backfill_performance_snapshots.py",
        sla_minutes=60,
        domain="P4",
        description=(
            "Derives historical DAILY (since-inception-to-date) + MONTHLY "
            "(single-month) PerformanceSnapshot rows from each portfolio's "
            "existing NAVSnapshot history -- pure local re-derivation via "
            "performance_engine.build_performance_summary(), no external "
            "calls. Fixes GET .../returns/calendar and .../returns/rolling "
            "returning empty grids for portfolios whose NAV history predates "
            "the live per-request DAILY snapshot write path, or that are "
            "rarely queried."
        ),
    ),
]

# Lookup by name for programmatic access
BATCH_JOBS_BY_NAME: dict[str, BatchJob] = {j.name: j for j in BATCH_JOBS}
