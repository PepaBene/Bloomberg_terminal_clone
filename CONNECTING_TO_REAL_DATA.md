# Connecting the Bloomberg Data Fabric to Real Data

This guide walks through wiring up the platform end-to-end against live
data sources. The repository ships with no production data — every
table starts empty and is populated by the ingestion connectors in
`src/ingestion/` driven by the scripts in `scripts/`.

The project layers cleanly:

| Layer | What it does | Where it lives |
|---|---|---|
| **Infrastructure** | PostgreSQL, Redis, Elasticsearch | `docker-compose.yml` |
| **Schema** | Alembic migrations defining 200+ tables | `migrations/versions/` |
| **Reference data** | Currencies, countries, GICS / NAICS / SIC, exchanges | `data/*.json` + `scripts/seed_reference.py` |
| **Ingestion connectors** | SEC EDGAR, FRED, Polygon, Finnhub, GLEIF, etc. | `src/ingestion/` + `scripts/ingest_*.py` |
| **Analytics engines** | Compute ratios, valuations, scores, risk, etc. from ingested data | `src/engines/` + `scripts/run_analytics_batch.py` |
| **API** | FastAPI app exposing the data | `src/api/` |
| **Frontend** | React + Vite UI consuming the API | `frontend/` |

---

## 1 — Prerequisites

| Tool | Version |
|---|---|
| Python | 3.11 or newer |
| Node.js | 20 or newer |
| Docker + Docker Compose | recent stable |
| `make` (optional, convenience) | any |
| ~10 GB free disk for PostgreSQL + Elasticsearch volumes | — |

---

## 2 — Clone, install, start infrastructure

```bash
git clone <your-fork-url> bloomberg-data-fabric
cd bloomberg-data-fabric

# Backend deps
python -m venv .venv
source .venv/bin/activate
pip install -e .

# Frontend deps
cd frontend && npm install && cd ..

# Bring up Postgres + Redis + Elasticsearch
make up               # or: docker compose up -d
```

`docker compose up -d` starts:

- **postgres** on `localhost:5432` (db `bloomberg`, user `bloomberg`, password `bloomberg_dev`)
- **redis** on `localhost:6379`
- **elasticsearch** on `localhost:9200`

The defaults match the `.env.example` values — no overrides needed
unless you change the compose file.

---

## 3 — Environment variables

Copy the template and edit:

```bash
cp .env.example .env
```

The connectors are split into three tiers based on what they unlock.

### 3.1 — Required for any real data

| Variable | Why | Where to get it |
|---|---|---|
| `SEC_USER_AGENT` | Every SEC EDGAR request must identify your firm + contact email; SEC will reject anonymous traffic. | Just put `"YourCompanyName admin@yourdomain.com"`. See <https://www.sec.gov/os/accessing-edgar-data>. |

### 3.2 — Free API keys (highly recommended)

| Variable | Unlocks | Where to get it |
|---|---|---|
| `FRED_API_KEY` | All macro indicators (CPI, GDP, yield curves, central-bank rates) | <https://fred.stlouisfed.org/docs/api/api_key.html> |
| `POLYGON_API_KEY` | EOD equity prices (Pillar 1 D2 + Pillar 2 valuations) | <https://polygon.io/dashboard/signup> (free tier: 5 req/min, EOD with 15-min delay) |
| `FINNHUB_API_KEY` | Index constituents (S&P 500, Russell 1000) — needed before EOD ingest can decide which tickers to fetch | <https://finnhub.io/register> |
| `OPENFIGI_API_KEY` | Cross-identifier mapping (CUSIP↔ISIN↔FIGI↔ticker). Optional — without a key you get 25 req/min vs 250 with. | <https://www.openfigi.com/api> |
| `ALPHA_VANTAGE_API_KEY` | Forward consensus EPS/revenue estimates (`ingest_consensus_estimates.py`) — Finnhub's free tier 403s on the equivalent endpoints | <https://www.alphavantage.co/support/#api-key> (free tier: 25 requests/day, 5/min — the script's default `--limit` respects this) |
| `EIA_API_KEY` | Real commodity supply/demand data — weekly US petroleum/natural-gas stock levels (`ingest_eia_commodity_inventory.py`), backing `GET /global/commodities/{code}/supply-demand` | <https://www.eia.gov/opendata/register.php> (free, instant, same signup model as FRED) |

### 3.3 — Optional (AI features)

| Variable | Unlocks | Where to get it |
|---|---|---|
| `ANTHROPIC_API_KEY` | LLM-driven features: morning briefings, analyst Q&A, company primers, investment thesis narratives, scenario commentary | <https://console.anthropic.com/> |
| `GOOGLE_API_KEY` | Text embeddings for semantic search over filings & transcripts | <https://aistudio.google.com/apikey> |
| `S3_*` | Persistent raw-file storage for SEC filings, transcripts, etc. (otherwise files are kept ephemerally) | Any S3-compatible store: AWS S3, MinIO, Cloudflare R2 |

### 3.4 — Auth & CORS

```env
# JWT secret — generate one with: openssl rand -hex 32
JWT_SECRET_KEY=<your-32+ byte random hex>

# Set to true to require Bearer tokens on every endpoint.
# Default is false so the dev API works without auth.
REQUIRE_AUTH=false

# CORS allowlist (comma-separated). Add your frontend origin here when
# you deploy somewhere other than localhost.
ALLOWED_ORIGINS=["http://localhost:5173","http://localhost:3000"]
```

---

## 4 — Initialize the schema

```bash
# Run all Alembic migrations (creates ~200 tables)
make migrate          # or: alembic upgrade head
```

If migrations fail, double-check `DATABASE_URL` and that PostgreSQL is
actually running (`docker compose ps`).

---

## 5 — Seed reference data

Reference tables (currencies, countries, GICS / NAICS / SIC sectors,
exchanges) are loaded from the JSON files under `data/`:

```bash
make seed             # or: python -m scripts.seed_reference
```

This is idempotent — safe to re-run.

---

## 6 — Ingest the data

Order matters. Earlier domains are dependencies for later ones — for
example, you can't ingest fundamentals before you have entities, and
you can't compute analytics before you have prices and fundamentals.

### Pillar 1 — Data Foundation (run in this order)

```bash
# 1. Entities — SEC EDGAR company list (~13k US public companies)
python scripts/ingest_edgar.py
#    • Pulls the full company tickers JSON, then enriches the first 100
#      with submissions detail. Bump --max-entities (or remove) to do all.

# 2. (Optional) Global entities — GLEIF LEI database (~2M legal entities)
python scripts/ingest_gleif.py
#    • Adds non-US entities by Legal Entity Identifier. Skip if you only
#      care about US public companies.

# 3. Securities — OpenFIGI cross-mapping (CUSIP/ISIN/FIGI/ticker)
python scripts/ingest_openfigi.py
#    • Required for any code path that joins by ticker or ISIN.

# 4. Index constituents — Finnhub (S&P 500, Russell 1000)
#    Trigger via run_analytics_batch.py or manually:
python -c "
import asyncio
from src.ingestion.index_constituents import IndexConstituentsConnector
from src.database import get_session_factory
async def main():
    async with get_session_factory()() as s:
        c = IndexConstituentsConnector()
        await c.run(s, indices=['SPX'])
        await s.commit()
asyncio.run(main())
"

# 5. End-of-day prices — Polygon (free tier is rate-limited; expect a long run)
python scripts/ingest_eod_prices.py --limit 100
#    • Drop --limit to fetch all securities. Free tier = 5 req/min.

# 6. Macroeconomic data — FRED (CPI, GDP, yield curves, etc.)
python scripts/ingest_fred.py

# 7. Treasury yield curve + credit spreads — FRED (reuses FRED_API_KEY)
python scripts/ingest_treasury_curve.py
python scripts/ingest_credit_spreads.py
#    • Note: `src.ingestion.treasury_yield_curve` (Treasury.gov direct) is an
#      older stub that never got a working extract() — the connectors above
#      (`fred_treasury_curve.py` / `fred_credit_spreads.py`) are the real,
#      working path and are what the scheduler (batch_config.py) runs.

# 8. Fundamentals — SEC EDGAR XBRL (income statement, balance sheet, cash flow)
python scripts/ingest_edgar_xbrl.py --limit 100

# 8b. Segments — SEC EDGAR XBRL dimensional segment members -> segment_data
#     (business/geographic revenue+income+assets breakdown). NOTE: SEC's
#     companyfacts endpoint mostly flattens facts to consolidated values;
#     this only picks up segments for filings whose XBRL genuinely carries
#     dimensional members, so coverage is real but partial.
python scripts/ingest_segments.py --limit 100

# 9. Corporate actions — dividends + splits (Polygon.io)
python scripts/ingest_corporate_actions.py --limit 100
#    • Structured ex/record/pay dates + cash amounts / split ratios, keyed
#      off tickers already in the security master (reuses POLYGON_API_KEY,
#      same key as EOD prices). This replaced an earlier wiring mistake:
#      the script used to drive Edgar8KConnector, whose load() actually
#      writes the unrelated `eight_k_events` table (no `security_id`
#      column at all), so `corporate_actions` had zero real writers and
#      `GET /securities/{id}/corporate-actions` was permanently empty.
#      8-K filing-event ingestion for `eight_k_events` still happens — see
#      `scripts/backfill.py` / `src/services/freshness.py`, which call
#      Edgar8KConnector directly for that (separate) purpose. M&A events
#      are still covered by `ingest_ma_deals.py` -> the separate MADeals
#      table, not touched by this script.

# 10. Ownership — 13F (institutional) + Form 4 (insider)
python scripts/ingest_ownership.py --limit 100

# 10b. Beneficial ownership — SEC Schedule 13D (activist) + 13G (passive)
# Unlike 13F/Form 4 above, this does NOT source CIKs from entity_identifiers
# first -- an activist fund/individual is frequently not a pre-existing
# covered entity, so it sweeps EDGAR's keyless daily form index by form type
# + date range instead and resolves the issuer (never the filer) against
# entity_identifiers, skipping filings whose issuer doesn't resolve.
python scripts/ingest_sc13.py --days-back 10 --limit 100

# 11. Short interest — FINRA twice-monthly
python scripts/ingest_short_interest.py

# 12. ESG disclosures — SEC sustainability filings
python scripts/ingest_esg.py --limit 100

# 13. Business relationships — NLP over 10-K item 1
python scripts/ingest_relationships.py --limit 100
```

### Pillar 1 Supplement — Fixed-income, credit, macro-policy, and rollups

These connectors are real and tested but were previously reachable only via
a manual `make` target — never scheduled in `batch_config.py` or documented
here (the same "orphaned engine" failure mode already fixed for Pillar 3).
They are now both scheduled (see §10) and documented below. All are
CIK-driven except where noted, and keyless/free except where noted.

```bash
# Capital structure — SEC EDGAR 10-K XBRL debt aggregates + footnote-parsed
# debt tranches -> capital_structures / debt_tranches. When a parsed tranche
# can be matched (by coupon rate + maturity year) to an existing traded
# fixed-income Security of the same issuer, this also upserts
# fixed_income_details and — if the footnote text contains an explicit
# optional-redemption ("callable ... on or after <date>") clause —
# call_put_schedule. In practice this match rarely fires today because no
# connector in this codebase creates Security rows for corporate bonds
# (OpenFIGI below is ticker-driven and resolves almost exclusively to
# equities) — see the open gap noted in §12 (Troubleshooting).
python scripts/ingest_capital_structure.py --limit 100

# Credit ratings — SEC EDGAR 8-K rating-agency mentions (S&P/Moody's/Fitch)
# -> credit_rating_events (entity-level). When a rating is actually
# extracted from the filing text, this also upserts security-level
# credit_ratings for the issuer's fixed-income securities — 8-Ks disclose
# ratings at the issuer level, not per instrument, so the issuer rating is
# applied to each of the issuer's FI securities (real, extracted data;
# just issuer- rather than CUSIP-granularity).
python scripts/ingest_credit_ratings.py --limit 100

# Treasury securities — US Treasury Fiscal Data API (keyless)
python scripts/ingest_treasury_securities.py

# Executives/directors — SEC EDGAR ownership filings
python scripts/ingest_executives.py --limit 20

# FOMC rate decisions — derived from FRED target-range series (reuses FRED_API_KEY)
python scripts/ingest_fomc.py

# Central-bank policy (Fed/ECB/BOE) — derived from FRED policy-rate series
# (ECB/BOE series are present but, per the connector's own docs, not yet
# validated against live payloads)
python scripts/ingest_central_bank.py

# Money market rates — SOFR / effective + target fed funds / T-bills /
# commercial paper / prime, from FRED (reuses FRED_API_KEY). extract() was
# previously a stub that always returned []; now mirrors the
# fred_credit_spreads.py pattern.
python scripts/ingest_money_market.py

# Rollups — pure computation over already-ingested data, no external calls
python scripts/compute_ownership_summary.py    # -> ownership_summaries
python scripts/compute_technicals.py           # -> technical_study_values
python scripts/compute_esg_temperature.py      # -> esg_temperature_scores
python scripts/compute_debt_maturity.py        # -> debt_maturity_profiles/maturity_buckets
```

All of the above are now registered in `src/scheduler/batch_config.py`
(domain `P1S`, plus `FI`/`D3` for the fixed-income and segments jobs) so a
running scheduler keeps them fresh automatically — see §10.

### Pillar 3 — Intelligence

Company/Industry/Competitive/Sentiment intelligence compute live
(on-miss) from Pillar 1/2 data once an entity is queried — no separate
ingestion step needed for those. The connectors below are for the
qualitative/external-source tables that have no other producer. All are
CIK-driven (pull real issuer CIKs from `entity_identifiers`, like
`ingest_edgar_xbrl.py`) and keyless/free except where noted; run any of
them with `--limit N` for a small test batch first.

```bash
# Governance — SEC DEF 14A proxy statements (free from EDGAR, but the
# filings themselves are unstructured HTML — board/comp/proposal parsing
# is best-effort; proxy_filings itself is reliable)
python scripts/ingest_proxy.py --limit 20

# Insider transactions (P3) — SEC Form 4, same filings ingest_ownership.py
# already reads for insider_holdings; this also writes the richer
# insider_transactions_p3 / insider_signals tables
python scripts/ingest_form4.py --limit 20

# Economic-release calendar — FRED releases API
python scripts/ingest_econ_calendar.py

# Commodity prices — FRED (WTI/Brent/gold/etc; a full commodity universe
# would need a paid data vendor, this covers what FRED tracks)
python scripts/ingest_commodities.py

# Commodity supply/demand — EIA weekly US petroleum/natural-gas stock levels
# (EIA_API_KEY, see §3.2). Covers WTI (US commercial crude stocks ex-SPR),
# GASOLINE (US total gasoline stocks), and NATGAS (Lower-48 working gas in
# storage) -- the commodities that have a genuine US-stocks concept. BRENT
# (an international/UK benchmark) and metals/agriculture are NOT covered --
# no free/keyless equivalent source is wired up for those (LME/COMEX
# warehouse stocks and USDA NASS Quick Stats would be the real sources, both
# left as an open gap). This backs the real (non-heuristic) branch of
# GET /global/commodities/{code}/supply-demand; without this ingested, that
# endpoint still works but honestly reports signal_source:
# "PRICE_HEURISTIC_FALLBACK" instead of "INVENTORY_YOY".
python scripts/ingest_eia_commodity_inventory.py

# Political intelligence — all free, keyless government sources
python scripts/ingest_legislative_bills.py      # Congress.gov bills RSS (GovInfo)
python scripts/ingest_regulatory_actions.py     # Federal Register API
python scripts/ingest_sanctions.py              # OFAC SDN list (CSV)

# Country risk + non-US global macro — World Bank Indicators API
python scripts/ingest_country_risk.py

# Geopolitical events — GDELT 2.0 (IP-throttled, be patient / avoid tight loops)
python scripts/ingest_geopolitical.py

# Filing diffs — section-level 10-K/10-Q diffs from EDGAR
python scripts/ingest_filing_diff.py --limit 10

# Earnings surprises (actual vs consensus EPS) — Finnhub free tier
python scripts/ingest_earnings.py --limit 50
#   NOTE: forward consensus estimates / guidance are NOT covered here —
#   Finnhub's free tier 403s on /stock/price-target and /stock/eps-estimate.
#   Those need a premium plan (Finnhub) or another provider (Refinitiv/
#   FactSet/Zacks); left as an open gap, not fabricated.

# News + sentiment — resumable, safe to run repeatedly or on a loop
python scripts/backfill_news.py --status              # coverage so far
python scripts/backfill_news.py --batch-size 20 --max-minutes 8
python -m scripts.run_news_loop                        # runs backfill_news to completion
python scripts/compute_sentiment.py --max-minutes 10   # news_articles -> sentiment_scores/aggregates

# Macro theme exposure scores — pure local computation (no external calls),
# reuses macro_scenario_engine's tested sector-sensitivity formula under 4
# standardized shocks (GDP growth, inflation, rate hikes, oil prices)
python -m scripts.compute_theme_scores
```

All of the above are also registered in `src/scheduler/batch_config.py`
(domain `P3`) so a running scheduler keeps them fresh automatically —
see §10.

`populate_governance.py` is unrelated to any of this despite the name —
it seeds the internal *data-governance catalog* (`DataCatalogEntry`/
`SourceConnector` metadata rows), not corporate proxy/board data. Safe
to run for catalog completeness, but it does not feed
`/v3/governance/*`.

---

### Pillar 3 Supplement — Newly-built connectors (ESG, fixed-income primary market, estimates, guidance, org structure)

The 8 domains below previously had **no data source wired at all** ("no
data source chosen" gaps). Each now has a real, unit-tested connector.
**Every one of them is flagged `FLAG — UNTESTED AGAINST LIVE DATA` in its
module docstring**: this sandbox has no outbound network access, so
`extract()` was written to-pattern against each source's documented
request/response shape and verified against synthetic fixtures, not a live
payload. Before relying on any of these in production, run each with
`--dry-run --limit 5` first and spot-check the output against the source
directly.

```bash
# ESG controversies — GDELT DOC 2.0 API (keyless, free). Classifies matched
# articles into controversy_type/severity via a documented keyword+tone
# heuristic — an explicit proxy, NOT an authoritative RepRisk/MSCI/
# Sustainalytics-style rating. Optional ESG_CONTROVERSY_FEED_URL env var
# overrides with a paid feed if you have one (any JSON feed emitting
# compatible rows).
python scripts/ingest_esg_controversies.py --limit 20
# python scripts/ingest_esg_controversies.py --feed-url https://your-feed/... # paid-feed override

# ESG environmental/social scores — SEC EDGAR 10-K disclosure text (GHG
# emissions, renewable %, net-zero target year, workforce diversity, safety/
# turnover rates), combined into a documented deterministic 0-100 proxy
# score — NOT an authoritative third-party ESG rating. Optional EPA
# Envirofacts GHGRP enrichment is on by default (keyless,
# EPA_ENVIROFACTS_BASE_URL already defaults to the real endpoint); disable
# with --no-epa if you want disclosure-text-only scores.
python scripts/ingest_esg_environmental.py --limit 20

# Primary-market bond issuances — SEC EDGAR full-text search over
# 424B2/424B3/424B5/FWP filings (prospectus supplements + free-writing
# prospectuses), regex-extracts coupon/maturity/size/bookrunners from the
# filing body. Regex extraction of free-text legal prose is imperfect —
# multi-tranche deals and year-only maturities are left partially/un-parsed
# rather than guessed. Set BOND_ISSUANCES_FEED_URL to override with a paid
# new-issue-monitor feed (Bloomberg, Ipreo/IHS Markit, etc.) instead.
# Also dual-writes fi_intelligence.NewIssuanceEvent from the same parsed
# deal, which backs the Pillar 3 FI Intelligence dashboard's
# GET /v3/fi/issuance/* endpoints (previously had zero producers).
python scripts/ingest_bond_issuances.py --limit 20
# python scripts/ingest_bond_issuances.py --days-back 365  # widen the EDGAR lookback window

# Agency (GSE) bonds — FHLB Office of Finance consolidated-obligation data.
# No documented public API; set FHLB_OF_DATA_URL to the actual CSV/JSON
# export URL (check https://www.fhlb-of.com/ for the current data-download
# link — it changes occasionally, hence no hardcoded default). CSV vs JSON
# is auto-detected. Set AGENCY_BONDS_FEED_URL instead to use a different
# (e.g. paid) feed.
FHLB_OF_DATA_URL=https://www.fhlb-of.com/... python scripts/ingest_agency_bonds.py --limit 20

# FINRA TRACE (corporate bond trade prints) — deliberately NOT a live-feed
# connector. FINRA TRACE requires a registered subscription either way (no
# keyless public feed exists); the realistic free path is FINRA's Academic/
# Historical TRACE (BTDS) program, which is registration-gated but free for
# non-commercial/academic use. That's a one-time HUMAN step outside this
# codebase:
#   1. Register at https://www.finra.org/finra-data/academic-btds (or
#      access via your institution's WRDS subscription, which mirrors the
#      same dataset).
#   2. Download a bulk dissemination extract for your date range of
#      interest — a pipe-delimited text file with columns CUSIP_ID,
#      TRD_EXCTN_DT, TRD_EXCTN_TM, RPTD_PR, YLD_PT, ENTRD_VOL_QT,
#      RPT_SIDE_CD, etc.
#   3. Point the connector at the downloaded file:
FINRA_TRACE_LOCAL_FILE=/path/to/your/trace_extract.txt python scripts/ingest_finra_trace.py --limit 500
# python scripts/ingest_finra_trace.py --file /path/to/your/trace_extract.txt  # same thing, CLI flag
# Academic TRACE files carry CUSIP but no issuer CIK/name, so trades only
# attach to bonds already present in `corporate_bonds` (from
# ingest_bond_issuances.py / ingest_agency_bonds.py / ingest_capital_structure.py);
# trades for genuinely unknown CUSIPs are skipped and logged, never
# fabricated into a fake bond. This is why it is NOT registered in
# batch_config.py — there's nothing useful to schedule until a human has
# actually downloaded a file. Run it manually after each TRACE extract you
# obtain.

# Forward consensus estimates (EPS/revenue) — Alpha Vantage
# (ALPHA_VANTAGE_API_KEY, see §3.2). Free tier is 25 requests/day, so the
# default --limit keeps a single run within that cap; increase gradually as
# your ticker coverage grows across days.
python scripts/ingest_consensus_estimates.py --limit 20

# Guidance tracking — SEC EDGAR 8-K Item 2.02 (results of operations /
# financial condition) filing bodies, regex range/point extraction of
# guidance figures. Set ANTHROPIC_API_KEY (see §3.3) to also run a
# best-effort Claude augmentation pass on top of the regex extraction; it
# no-ops cleanly (falls back to the regex-only result) without a key.
python scripts/ingest_guidance.py --limit 20 --days-back 30

# Subsidiary org tree — SEC Exhibit 21 (list-of-subsidiaries exhibit, filed
# annually alongside the 10-K) -> subsidiaries table, feeding
# GET /complex-structure/entity/{id}'s subsidiary-tree analysis.
python scripts/ingest_subsidiaries.py --limit 20
```

All 7 of the above (everything except FINRA TRACE, for the reason
explained above) are registered in `src/scheduler/batch_config.py` — see
§10.

**What's still a genuine, undocumented-workaround gap** (not fabricated,
just not built): per-share-class voting-rights multipliers and
economic/dividend-rights ratios. `GET /complex-structure/entity/{id}` now
surfaces real disclosed share classes and real `shares_outstanding`
figures, but `votes_per_share`/`economic_rights` default to 1/1.0
(one-share-one-vote, pari passu) for every class because no free source for
actual per-class voting multipliers is wired up — this understates any real
dual-class control wedge (e.g. it would not show a Class B super-voting
share correctly). A proxy-statement (DEF 14A) NLP pass targeting the
"Description of Capital Stock" section would be the natural next step if
this matters for your use case.

---

## 7 — Run analytics batches (Pillar 2 + scoring)

Once Pillar 1 has prices + fundamentals + macro, the analytics engines
can compute ratios, valuations, risk, scores, etc.:

```bash
# Run a single engine
python scripts/run_analytics_batch.py --engine e1            # ratios
python scripts/run_analytics_batch.py --engine e2_multiples
python scripts/run_analytics_batch.py --engine e2_wacc
python scripts/run_analytics_batch.py --engine e2_dcf
python scripts/run_analytics_batch.py --engine e3            # quality / value / growth scores
python scripts/run_analytics_batch.py --engine e5_risk       # VaR / volatility / beta
python scripts/run_analytics_batch.py --engine e7_quant      # factor / regression / cointegration

# Or run everything (good for first-time backfill — slow)
python scripts/run_analytics_batch.py --engine all

# Test what it would do without writing anything
python scripts/run_analytics_batch.py --engine e1 --dry-run --limit 5
```

The API auto-triggers an `--engine all` run on startup if the
`analytics_results` table is empty — see `lifespan()` in
`src/api/app.py`. To disable that, comment out the auto-seed block or
pre-seed manually before the first API boot.

---

## 8 — Start the API

```bash
make dev              # or: uvicorn src.api.app:create_app --factory --reload --host 0.0.0.0 --port 8000
```

Quick sanity checks:

```bash
# Health (no DB required for the 200/503 distinction)
curl -s http://localhost:8000/health

# OpenAPI docs in browser
open http://localhost:8000/docs

# A real query (assuming you ingested entities + Apple is in there)
curl -s "http://localhost:8000/v1/entities/search?q=apple"
```

---

## 9 — Start the frontend

```bash
cd frontend
npm run dev
```

The Vite dev server runs at <http://localhost:5173> by default and
proxies `/v1`, `/v2`, `/v3`, `/v4` API calls to
`http://localhost:8000`. If you change ports update `vite.config.ts`
and the `ALLOWED_ORIGINS` env var.

---

## 10 — Run on a schedule (production)

The batch system has two driver options:

### 10.1 — APScheduler (single-host)

```bash
pip install apscheduler
python scripts/run_scheduler.py
```

This reads `src/scheduler/batch_config.py` (`len(BATCH_JOBS)` jobs covering
Pillar 1, Pillar 2 daily/weekly cycles, the FI yield-curve/credit-spread +
briefing pipeline, the Pillar 1 Supplement fixed-income/credit/macro-policy
connectors + rollups, and the Pillar 3 connectors + theme-scoring job from
§6 above) and runs them in-process.

### 10.2 — Crontab (any Unix host)

```bash
python scripts/run_scheduler.py --crontab > batch.cron
crontab batch.cron
```

This emits crontab entries for every job in `BATCH_JOBS` so you can
hand them to the OS scheduler instead of running an in-process loop.

### 10.3 — Validate config without running anything

```bash
python scripts/run_scheduler.py --validate
```

---

## 11 — Production deployment notes

| Concern | What to do |
|---|---|
| **Auth** | Set `REQUIRE_AUTH=true` and a strong `JWT_SECRET_KEY`. Issue tokens via `POST /auth/login`. Every endpoint will then require `Authorization: Bearer …`. |
| **CORS** | Add your real frontend origin to `ALLOWED_ORIGINS`. |
| **Database** | Use a managed PostgreSQL with backups (RDS, Cloud SQL, Supabase). Bump `DB_POOL_MAX` for higher concurrency. |
| **Cache** | Point `REDIS_URL` at a managed Redis. Cache TTLs are tunable per domain via `CACHE_TTL_*` settings. |
| **Search** | Point `ELASTICSEARCH_URL` at a managed cluster (or Opensearch); the `entities.py` and `securities.py` routers fall back to ILIKE if ES is unreachable. |
| **Object storage** | Set `S3_*` so raw filings, transcripts, and PDF reports survive container restarts. |
| **Rate limits** | Polygon free tier is 5 req/min — switch to a paid plan once you outgrow it. SEC EDGAR enforces 10 req/sec per User-Agent — `SEC_RATE_LIMIT` honors this. |
| **Logs** | Every request writes to the audit log middleware. Pipe stdout to your log aggregator of choice (Datadog, Loki, CloudWatch). |
| **Secrets** | Never commit `.env`. Use the orchestrator's secret store (Kubernetes secrets, AWS Parameter Store, Vault). |

---

## 12 — Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Frontend pages render Apple / NVIDIA placeholder data | Backend hasn't been seeded yet, hooks return 404 → frontend shows the empty-state defaults | Run the Pillar 1 ingest scripts (§6) and `run_analytics_batch.py --engine all` |
| `/v1/securities/search?q=AAPL` returns nothing | OpenFIGI never linked tickers to securities | Re-run `python scripts/ingest_openfigi.py` |
| `/v2/analytics/ratios/{id}` returns 404 | Analytics batch hasn't run for that security | `python scripts/run_analytics_batch.py --engine e1` |
| `/v3/news/...` is empty | News ingestion is not wired to a feed by default; you must point a connector at your news provider (RSS, NewsAPI, Bloomberg feed) | Implement / wire a connector in `src/ingestion/`; the schema (`news_articles`, `article_entity_links`) is already there |
| LLM-powered endpoints return template strings | `ANTHROPIC_API_KEY` is empty | Set the key in `.env`; the LLM client falls back to templates when no key is present |
| Semantic search returns chronological-only results | `GOOGLE_API_KEY` is empty so embeddings aren't generated | Set the key; embeddings backfill on the next ingestion |
| Migrations fail with "table already exists" | Schema was created via something other than Alembic | Drop the database (`docker compose down -v && docker compose up -d`) and re-run `make migrate` |
| `psycopg2`/`asyncpg` connection errors | Postgres not running or different port | `docker compose ps`, check `DATABASE_URL` |
| Frontend shows CORS errors | Frontend origin missing from `ALLOWED_ORIGINS` | Add the origin to `.env`, restart API |
| `expand=fixed_income_details` / `expand=call_put_schedule` on `/v1/securities/{id}` is always empty | No connector in this codebase creates `Security` rows for corporate bonds (`asset_class=FIXED_INCOME`) — `ingest_openfigi.py` is ticker-driven and resolves almost exclusively to equities; `ingest_agency_bonds.py` / `ingest_trace_bonds.py` / `ingest_treasury_securities.py` / `ingest_bond_issuances.py` all write to their own separate models, not `securities`. `ingest_capital_structure.py`'s tranche->security matching (coupon + maturity year) is real and tested but has nothing to match against until a bond-CUSIP security-master connector exists — that's a genuine gap, not fabricated with placeholder values | Add a CUSIP/ISIN-driven bond security-master connector (e.g. an OpenFIGI variant keyed by CUSIP instead of ticker, or a licensed bond reference-data feed) before expecting these fields to populate |
| `ingest_finra_trace.py` logs "no FINRA_TRACE_LOCAL_FILE or FINRA_TRACE_FEED_URL configured" and loads 0 trades | Expected — TRACE has no keyless live feed; you must obtain a local bulk extract first | Register for FINRA Academic/Historical TRACE (or use a WRDS subscription), download an extract, then set `FINRA_TRACE_LOCAL_FILE=/path/to/file` or pass `--file`; see the Pillar 3 Supplement in §6 |
| `ingest_finra_trace.py` loads far fewer trades than the source file has rows | Most CUSIPs in an Academic TRACE extract won't already exist in `corporate_bonds` — the connector intentionally skips trades for unresolvable CUSIPs rather than fabricating a bond/issuer | Run `ingest_bond_issuances.py`, `ingest_agency_bonds.py`, and/or `ingest_capital_structure.py` first to populate `corporate_bonds` for the issuers you care about, then re-run the TRACE ingest |
| `ingest_esg_controversies.py` / `ingest_esg_environmental.py` results look thin or inconsistent | Both are heuristic/proxy scores (GDELT keyword+tone matching; 10-K disclosure-text regex extraction), not authoritative third-party ratings — see the module docstrings and the Pillar 3 Supplement in §6 for exactly what's real vs. estimated | Treat as directional signals; validate against the source filing/articles before trusting a specific score |
| `GET /global/commodities/{code}/supply-demand` returns `"signal_source": "PRICE_HEURISTIC_FALLBACK"` instead of real data | No `commodity_inventories` row exists for that `commodity_code` — either `ingest_eia_commodity_inventory.py` hasn't run, or the commodity isn't one of the 3 it covers (WTI/GASOLINE/NATGAS; BRENT and metals/agriculture have no wired-up free source) | Run `python scripts/ingest_eia_commodity_inventory.py` (needs `EIA_API_KEY`) for a covered commodity; for an uncovered one, the fallback is the honest answer, not a bug |

---

## 13 — TL;DR for the impatient

```bash
# One-shot setup that gets you a populated dev environment with ~100
# US public companies, their last few quarters of fundamentals, EOD
# prices, and computed Pillar 2 analytics.

cp .env.example .env
# edit .env — set SEC_USER_AGENT and at least FRED_API_KEY + POLYGON_API_KEY

make up
make migrate
make seed
python scripts/ingest_edgar.py
python scripts/ingest_openfigi.py
python scripts/ingest_eod_prices.py --limit 100
python scripts/ingest_fred.py
python scripts/ingest_edgar_xbrl.py --limit 100
python scripts/run_analytics_batch.py --engine all

# In two more terminals:
make dev
cd frontend && npm run dev
```

You should have a working terminal at <http://localhost:5173> with
real entities, real prices, real fundamentals, and real computed
ratios / valuations / risk metrics for the first 100 US public
companies you ingested. Add more companies by re-running the EDGAR
detail enrichment (`scripts/ingest_edgar.py`'s `enrich_with_details`
loop) and the EOD / XBRL scripts without a `--limit`.
