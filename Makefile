.PHONY: up down migrate seed test quality dev \
	ingest-edgar ingest-gleif ingest-figi ingest-congress \
	ingest-xbrl ingest-corporate-actions ingest-ownership ingest-esg \
	ingest-relationships ingest-short-interest ingest-segments \
	ingest-capital-structure ingest-credit-ratings ingest-credit-spreads \
	ingest-treasury-securities ingest-trace-bonds ingest-agency-bonds \
	ingest-bond-issuances ingest-executives ingest-fomc ingest-central-bank \
	ingest-earnings-surprises ingest-ma-deals ingest-ipo ingest-nport \
	ingest-esg-controversies ingest-money-market \
	compute-debt-maturity compute-ownership-summary compute-esg-temperature \
	compute-technicals \
	backfill backfill-status backfill-reconcile backfill-loop backfill-refresh \
	analytics analytics-status analytics-loop analytics-refresh

up:
	docker compose up -d

down:
	docker compose down

migrate:
	alembic upgrade head

seed:
	python -m scripts.seed_reference

# --- Core Pillar 1 ingestion (entities, securities, prices, macro) ---
ingest-edgar:
	python -m scripts.ingest_edgar

ingest-gleif:
	python -m scripts.ingest_gleif

ingest-figi:
	python -m scripts.ingest_openfigi

ingest-congress:
	python -m scripts.ingest_congress

# --- SEC EDGAR filing-derived ingestion (CIK-driven) ---
ingest-xbrl:
	python -m scripts.ingest_edgar_xbrl

ingest-corporate-actions:
	python -m scripts.ingest_corporate_actions

ingest-ownership:
	python -m scripts.ingest_ownership

ingest-esg:
	python -m scripts.ingest_esg

ingest-relationships:
	python -m scripts.ingest_relationships

ingest-short-interest:
	python -m scripts.ingest_short_interest

ingest-segments:
	python -m scripts.ingest_segments

ingest-executives:
	python -m scripts.ingest_executives

ingest-ma-deals:
	python -m scripts.ingest_ma_deals

ingest-ipo:
	python -m scripts.ingest_ipo

ingest-nport:
	python -m scripts.ingest_nport

# --- Fixed income / credit ingestion ---
ingest-capital-structure:
	python -m scripts.ingest_capital_structure

ingest-credit-ratings:
	python -m scripts.ingest_credit_ratings

ingest-credit-spreads:
	python -m scripts.ingest_credit_spreads

ingest-treasury-securities:
	python -m scripts.ingest_treasury_securities

ingest-trace-bonds:
	python -m scripts.ingest_trace_bonds

ingest-agency-bonds:
	python -m scripts.ingest_agency_bonds

ingest-bond-issuances:
	python -m scripts.ingest_bond_issuances

# --- Macro / policy ingestion (FRED-derived) ---
ingest-fomc:
	python -m scripts.ingest_fomc

ingest-central-bank:
	python -m scripts.ingest_central_bank

ingest-money-market:
	python -m scripts.ingest_money_market

ingest-earnings-surprises:
	python -m scripts.ingest_earnings_surprises

ingest-esg-controversies:
	python -m scripts.ingest_esg_controversies

# --- Computed rollups (no external source; derive from ingested data) ---
compute-debt-maturity:
	python -m scripts.compute_debt_maturity

compute-ownership-summary:
	python -m scripts.compute_ownership_summary

compute-esg-temperature:
	python -m scripts.compute_esg_temperature

compute-technicals:
	python -m scripts.compute_technicals

# --- Automated resumable backfill (see BACKFILL.md) ---
backfill-status:      ## Show per-data-type coverage
	python -m scripts.backfill --status

backfill-reconcile:   ## Mark already-ingested data as done (run once)
	python -m scripts.backfill --reconcile

backfill:             ## Run one bounded backfill pass across all data types
	python -m scripts.backfill --all --max-minutes 8

backfill-refresh:     ## One pass: fill gaps AND re-fetch companies stale >7 days
	python -m scripts.backfill --all --refresh-days 7 --max-minutes 10

backfill-loop:        ## Run continuously until every company is complete
	python -m scripts.run_backfill_loop

# --- Resumable analytics (see FRESHNESS.md) ---
analytics-status:     ## Per-engine analytics coverage
	python -m scripts.run_analytics_batch --status

analytics:            ## One bounded analytics pass across all engines
	python -m scripts.run_analytics_batch --engine all --max-minutes 12

analytics-loop:       ## Run analytics continuously until every engine is complete
	python -m scripts.run_analytics_loop

analytics-refresh:    ## Recompute analytics for securities stale >7 days
	python -m scripts.run_analytics_batch --engine all --refresh-days 7 --max-minutes 12

test:
	pytest -v

quality:
	python -m scripts.run_quality_check

dev:
	uvicorn src.api.app:create_app --factory --reload --host 0.0.0.0 --port 8000
