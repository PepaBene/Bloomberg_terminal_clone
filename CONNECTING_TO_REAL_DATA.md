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

# 7. Treasury yield curve — directly from Treasury.gov (no API key needed)
python -m src.ingestion.treasury_yield_curve

# 8. Fundamentals — SEC EDGAR XBRL (income statement, balance sheet, cash flow)
python scripts/ingest_edgar_xbrl.py --limit 100

# 9. Corporate actions — 8-K filings
python scripts/ingest_corporate_actions.py --limit 100

# 10. Ownership — 13F (institutional) + Form 4 (insider)
python scripts/ingest_ownership.py --limit 100

# 11. Short interest — FINRA twice-monthly
python scripts/ingest_short_interest.py

# 12. ESG disclosures — SEC sustainability filings
python scripts/ingest_esg.py --limit 100

# 13. Business relationships — NLP over 10-K item 1
python scripts/ingest_relationships.py --limit 100
```

### Pillar 3 — Intelligence

Most Pillar 3 connectors run as part of the ingestion + batch flow
above (8-K extraction, transcript NLP, FinBERT sentiment, governance
extraction from proxy filings). To populate the governance models
specifically:

```bash
python scripts/populate_governance.py
```

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

This reads `src/scheduler/batch_config.py` (16 jobs covering all of
Pillar 1 + Pillar 2 daily / weekly cycles) and runs them in-process.

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
