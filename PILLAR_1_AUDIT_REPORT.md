# Pillar 1: Data Foundation — Feature Completeness Audit

## Executive Summary

Pillar 1 covers **Entities**, **Securities**, and **Fundamentals** — the core data foundation. The **backend is fully built** with real database queries (not mocks), but the **frontend only uses 2 of the 48 endpoint constants** through proper hooks on actual pages. Most frontend pages show hardcoded mock data and never contact the backend for Pillar 1 data. Additionally, the database starts **empty** — you must run ingestion scripts to populate it with real data.

---

## Part 1: Backend Router Assessment

### Entities Router (`src/api/routers/entities.py`) — FULLY IMPLEMENTED
All endpoints query the real PostgreSQL database via SQLAlchemy ORM. **No mock data.**

| Endpoint | Method | Status | Notes |
|----------|--------|--------|-------|
| `/v1/entities/search` | GET | **Working** | Uses ILIKE (note: "placeholder until Elasticsearch is wired up") |
| `/v1/entities/{id}` | GET | **Working** | Supports `expand` param (identifiers, names, relationships) |
| `/v1/entities` | GET | **Working** | Supports LEI, CIK, status, country, entity_type filters |
| `/v1/entities/{id}/hierarchy` | GET | **Working** | Returns ultimate parent, immediate parent, subsidiaries |
| `/v1/entities/{id}/securities` | GET | **Working** | Lists securities by issuer entity |
| `/v1/entities/{id}/history` | GET | **Working** | Point-in-time entity change history |
| `/v1/entities/{id}/relationships` | GET | **Working** | Filtered by type and active status |
| `/v1/entities/resolve` | POST | **Working** | Delegates to resolution engine |
| `/v1/entities/bulk-lookup` | POST | **Working** | Batch identifier lookup |

**Missing vs Frontend Constants:**
- Frontend expects `/v1/entities/{id}/subsidiaries` → Backend has `/v1/entities/{id}/hierarchy` (MISMATCH)
- Frontend expects `/v1/entities/{id}/parent-chain` → Backend has `/v1/entities/{id}/hierarchy` (MISMATCH)
- Frontend expects `/v1/entities/{id}/officers` → **NO BACKEND ENDPOINT** (separate `executives.py` router exists but path may differ)
- Frontend expects `/v1/entities/{id}/board` → **NO BACKEND ENDPOINT** (may be in executives.py)
- Frontend expects `/v1/entities/{id}/identifiers` → Not a separate endpoint; available via `expand=identifiers` on detail
- Frontend expects `/v1/entities/{id}/classifications` → **NO BACKEND ENDPOINT** in entities.py (separate `custom_classifications.py`)

### Securities Router (`src/api/routers/securities.py`) — FULLY IMPLEMENTED
All endpoints query the real PostgreSQL database. **No mock data.**

| Endpoint | Method | Status | Notes |
|----------|--------|--------|-------|
| `/v1/securities/search` | GET | **Working** | ILIKE search, "placeholder until ES" |
| `/v1/securities/{id}` | GET | **Working** | Supports expand (identifiers, equity/FI details, credit_ratings) |
| `/v1/securities` | GET | **Working** | Filters: ISIN, CUSIP, FIGI, ticker, asset_class, status |
| `/v1/securities/{id}/identifiers` | GET | **Working** | All identifier mappings |
| `/v1/securities/{id}/issuer` | GET | **Working** | Returns issuer entity |
| `/v1/securities/{id}/related` | GET | **Working** | Same-issuer securities |
| `/v1/securities/{id}/prices` | GET | **Working** | EOD price history with date range |
| `/v1/securities/{id}/prices/latest` | GET | **Working** | Most recent EOD price |
| `/v1/securities/bulk-lookup` | POST | **Working** | Batch identifier lookup |
| `/v1/securities/translate` | POST | **Working** | Cross-identifier translation |

**Missing vs Frontend Constants:**
- Frontend expects `/v1/securities/{id}/prices/intraday` → **NO BACKEND ENDPOINT** (no intraday data source)
- Frontend expects `/v1/securities/{id}/prices/history` → Backend has `/v1/securities/{id}/prices` with date filters (CLOSE ENOUGH)
- Frontend expects `/v1/securities/{id}/institutional-holdings` → Lives in `ownership.py` router, not securities.py (PATH MISMATCH: backend is `/securities/{id}/ownership/institutional`)
- Frontend expects `/v1/securities/{id}/insider-holdings` → Lives in `ownership.py` (PATH MISMATCH: backend is `/securities/{id}/ownership/insider`)
- Frontend expects `/v1/securities/{id}/ownership-summary` → Lives in `ownership.py` (PATH MISMATCH: backend is `/securities/{id}/ownership/summary`)
- Frontend expects `/v1/securities/{id}/short-interest` → Lives in `ownership.py` (PATH MATCH)
- Frontend expects `/v1/securities/{id}/technicals` → **NO BACKEND ENDPOINT** in securities.py (may be in `technical_studies.py`)
- Frontend expects `/v1/securities/{id}/dividends` → **NO BACKEND ENDPOINT** in securities.py (may be in `corporate_actions.py`)
- Frontend expects `/v1/securities/{id}/splits` → **NO BACKEND ENDPOINT** in securities.py
- Frontend expects `/v1/securities/{id}/corporate-actions` → **NO BACKEND ENDPOINT** in securities.py
- Frontend expects `/v1/securities/exchanges` → **NO BACKEND ENDPOINT**
- Frontend expects `/v1/securities/sectors` → **NO BACKEND ENDPOINT**

### Fundamentals Router (`src/api/routers/fundamentals.py`) — FULLY IMPLEMENTED
All endpoints query the real PostgreSQL database. **No mock data.**

| Endpoint | Method | Status | Notes |
|----------|--------|--------|-------|
| `/v1/entities/{id}/filings` | GET | **Working** | Paginated, filterable by type/status |
| `/v1/filings/{filing_id}` | GET | **Working** | Single filing detail |
| `/v1/entities/{id}/fundamentals` | GET | **Working** | Combined IS/BS/CF by period |
| `/v1/entities/{id}/fundamentals/income-statement` | GET | **Working** | Income statement series |
| `/v1/entities/{id}/fundamentals/balance-sheet` | GET | **Working** | Balance sheet series |
| `/v1/entities/{id}/fundamentals/cash-flow` | GET | **Working** | Cash flow series |
| `/v1/entities/{id}/segments` | GET | **Working** | Segment data |

**Missing vs Frontend Constants:**
- Frontend expects `/v1/entities/{id}/income-statements` → Backend is `/v1/entities/{id}/fundamentals/income-statement` (PATH MISMATCH)
- Frontend expects `/v1/entities/{id}/balance-sheets` → Backend is `/v1/entities/{id}/fundamentals/balance-sheet` (PATH MISMATCH)
- Frontend expects `/v1/entities/{id}/cash-flows` → Backend is `/v1/entities/{id}/fundamentals/cash-flow` (PATH MISMATCH)
- Frontend expects `/v1/entities/{id}/ratios` → **NO BACKEND ENDPOINT** in fundamentals.py (may be in analytics.py)
- Frontend expects `/v1/entities/{id}/estimates` → Lives in `estimates.py` with different path structure
- Frontend expects `/v1/entities/{id}/estimates/consensus` → Lives in `estimates.py` as `/securities/{id}/estimates/consensus` (PATH MISMATCH)
- Frontend expects `/v1/entities/{id}/estimates/history` → **NO BACKEND ENDPOINT**
- Frontend expects `/v1/entities/{id}/revenue-breakdown` → **NO BACKEND ENDPOINT**
- Frontend expects `/v1/entities/{id}/geographic-breakdown` → **NO BACKEND ENDPOINT**
- Frontend expects `/v1/entities/{id}/quarterly-trends` → **NO BACKEND ENDPOINT**
- Frontend expects `/v1/entities/{id}/annual-summary` → **NO BACKEND ENDPOINT**
- Frontend expects `/v1/entities/{id}/kpis` → **NO BACKEND ENDPOINT**

---

## Part 2: Frontend Usage Assessment

### Pages That Actually Use Pillar 1 Hooks

| Page | Hooks Used | Data Rendered? | Mock Fallback? |
|------|-----------|----------------|----------------|
| FinancialStatements.tsx | `useIncomeStatements`, `useBalanceSheets`, `useCashFlows`, `useSegments`, `useRevenueBreakdown` | Yes | Yes — full mock tables |
| OwnershipDashboard.tsx | `useInstitutionalHoldings`, `useInsiderHoldings`, `useOwnershipSummary`, `useShortInterest` | Yes | Yes — full mock tables |

### Pages That SHOULD Use Pillar 1 Hooks But Don't

| Page | What It Shows | Current Data Source | What's Wrong |
|------|---------------|-------------------|-------------|
| **CompanyOverview.tsx** | Company profile, price, KPIs, quarterly financials, quality scores, news | Hardcoded `api.get('/v4/entities/${id}/ratios')` etc. — raw `useQuery` with `/v4/` paths that don't match any backend router | These `/v4/` endpoints don't exist in the backend. The page falls back to extensive mock data (MOCK_COMPANY, MOCK_METRICS, MOCK_QUARTERLY, MOCK_QUALITY, MOCK_NEWS) 100% of the time |
| **ValuationDashboard.tsx** | DuPont analysis, peer comparison, DCF, multiples | Uses Pillar 2 (Analytics) hooks only | OK — this is correct for valuation |

### Pillar 1 Hooks That Exist But Are Never Used on Any Page

| Hook | Endpoint | Used? |
|------|----------|-------|
| `useEntitySearch` | `/v1/entities/search` | Only via Command Bar |
| `useEntity` | `/v1/entities/{id}` | **NEVER** on any page |
| `useEntityRelationships` | `/v1/entities/{id}/relationships` | **NEVER** |
| `useEntitySubsidiaries` | `/v1/entities/{id}/subsidiaries` | **NEVER** |
| `useEntityParentChain` | `/v1/entities/{id}/parent-chain` | **NEVER** |
| `useEntityOfficers` | `/v1/entities/{id}/officers` | **NEVER** |
| `useEntityBoardMembers` | `/v1/entities/{id}/board` | **NEVER** |
| `useEntityHistory` | `/v1/entities/{id}/history` | **NEVER** |
| `useEntityIdentifiers` | `/v1/entities/{id}/identifiers` | **NEVER** |
| `useEntityClassifications` | `/v1/entities/{id}/classifications` | **NEVER** |
| `useSecurity` | `/v1/securities/{id}` | **NEVER** |
| `useSecuritySearch` | `/v1/securities/search` | Only via Command Bar |
| `useSecurityPrices` | `/v1/securities/{id}/prices` | **NEVER** |
| `useSecurityPricesIntraday` | `/v1/securities/{id}/prices/intraday` | **NEVER** |
| `useSecurityPricesHistory` | `/v1/securities/{id}/prices/history` | **NEVER** |
| `useSecurityTechnicals` | `/v1/securities/{id}/technicals` | **NEVER** |
| `useSecurityDividends` | `/v1/securities/{id}/dividends` | **NEVER** |
| `useSecuritySplits` | `/v1/securities/{id}/splits` | **NEVER** |
| `useSecurityCorporateActions` | `/v1/securities/{id}/corporate-actions` | **NEVER** |
| `useSecurityIdentifiers` | `/v1/securities/{id}/identifiers` | **NEVER** |
| `useExchanges` | `/v1/securities/exchanges` | **NEVER** |
| `useSectors` | Endpoint exists in `useEntities.ts` | Used by SectorView (Pillar 3) |
| `useEstimates` | `/v1/entities/{id}/estimates` | **NEVER** |
| `useEstimatesConsensus` | `/v1/entities/{id}/estimates/consensus` | **NEVER** |
| `useEstimatesHistory` | `/v1/entities/{id}/estimates/history` | **NEVER** |
| `useRevenueBreakdown` | `/v1/entities/{id}/revenue-breakdown` | Used in FinancialStatements |
| `useGeographicBreakdown` | `/v1/entities/{id}/geographic-breakdown` | **NEVER** |
| `useQuarterlyTrends` | `/v1/entities/{id}/quarterly-trends` | **NEVER** |
| `useAnnualSummary` | `/v1/entities/{id}/annual-summary` | **NEVER** |
| `useKPIs` | `/v1/entities/{id}/kpis` | **NEVER** |

---

## Part 3: Critical Endpoint Path Mismatches

These are cases where the frontend calls one URL but the backend serves a different one:

| Frontend Endpoint Constant | Backend Actual Path | Issue |
|---------------------------|--------------------|----|
| `/v1/entities/{id}/income-statements` | `/v1/entities/{id}/fundamentals/income-statement` | Missing `/fundamentals/` prefix and plural vs singular |
| `/v1/entities/{id}/balance-sheets` | `/v1/entities/{id}/fundamentals/balance-sheet` | Missing `/fundamentals/` prefix |
| `/v1/entities/{id}/cash-flows` | `/v1/entities/{id}/fundamentals/cash-flow` | Missing `/fundamentals/` prefix |
| `/v1/securities/{id}/institutional-holdings` | `/v1/securities/{id}/ownership/institutional` | Missing `/ownership/` prefix |
| `/v1/securities/{id}/insider-holdings` | `/v1/securities/{id}/ownership/insider` | Missing `/ownership/` prefix |
| `/v1/securities/{id}/ownership-summary` | `/v1/securities/{id}/ownership/summary` | Different path structure |
| `/v1/entities/{id}/estimates/consensus` | `/v1/securities/{id}/estimates/consensus` | Entity vs Security ID |

These mismatches mean that **even when the backend is running with data, the frontend hooks will get 404s** because they're calling the wrong paths.

---

## Part 4: Data Population — How to Get Real Data

### Infrastructure Required (docker-compose.yml)
```bash
# Start PostgreSQL, Redis, Elasticsearch
docker-compose up -d
```

### Step-by-Step Data Population

#### Step 1: Create Database Schema
```bash
# Run all 80 Alembic migrations
alembic upgrade head
```

#### Step 2: Seed Reference Data (no API keys needed)
```bash
python scripts/seed_reference.py
```
This loads from `data/` JSON files: countries, currencies, exchanges, GICS codes, SIC codes, NAICS codes.

#### Step 3: Ingest Entity Data from SEC EDGAR (FREE, no API key)
```bash
# Set SEC_USER_AGENT in .env first (required by SEC)
# e.g. SEC_USER_AGENT="YourApp yourname@example.com"
python scripts/ingest_edgar.py
```
This populates: entities (companies), entity identifiers (CIK), entity names.

#### Step 4: Ingest Security Identifiers from OpenFIGI (FREE, optional key)
```bash
python scripts/ingest_openfigi.py
```
Maps tickers to FIGI/ISIN/CUSIP. Optional API key increases rate limit.

#### Step 5: Ingest XBRL Financial Statements from EDGAR (FREE)
```bash
python scripts/ingest_edgar_xbrl.py
```
Populates: income statements, balance sheets, cash flows, filings.

#### Step 6: Ingest EOD Prices from Polygon.io (FREE tier available)
```bash
# Set POLYGON_API_KEY in .env
python scripts/ingest_eod_prices.py
```

#### Step 7: Ingest Ownership from EDGAR 13F (FREE)
```bash
python scripts/ingest_ownership.py
```
Populates: institutional holdings, insider transactions.

#### Step 8: Ingest Macro Data from FRED (FREE, key required)
```bash
# Set FRED_API_KEY in .env (free at https://fred.stlouisfed.org/docs/api/api_key.html)
python scripts/ingest_fred.py
```

#### Step 9: Ingest ESG Data from Filings (FREE)
```bash
python scripts/ingest_esg.py
```

### Data Source Summary

| Data Source | Cost | API Key Required? | What It Provides |
|------------|------|-------------------|-----------------|
| **SEC EDGAR** | Free | No (just User-Agent) | Entities, filings, financials, ownership, insider trades, ESG |
| **FRED** | Free | Yes (free key) | Macroeconomic indicators, yield curves, credit spreads |
| **Polygon.io** | Free tier (5 req/s) | Yes (free key) | EOD stock prices |
| **OpenFIGI** | Free (25 req/min) | Optional (increases to 250 req/min) | Security identifier mapping (FIGI/ISIN/CUSIP/ticker) |
| **GLEIF** | Free | No | Legal Entity Identifiers (LEI) |
| **FINRA** | Free | No | Short interest data, TRACE bond trades |
| **US Treasury** | Free | No | Treasury securities, yield curve |

### What Is NOT Available For Free
- **Real-time/streaming prices** — No free source integrated. The app only has EOD prices from Polygon.
- **Intraday prices** — Frontend has `useSecurityPricesIntraday` hook but no backend endpoint or data source exists.
- **Analyst estimates/consensus** — Backend has `estimates_stub.py` (schema only). Would need Bloomberg Terminal, FactSet, or S&P Capital IQ.
- **Revenue/geographic breakdowns** — No ingestion script exists. Would need to be parsed from XBRL filings (partially possible from EDGAR).
- **KPIs, quality scores, annual summaries** — These are computed analytics, not raw data. The analytics engine batch (`scripts/run_analytics_batch.py`) may compute some of these.

---

## Part 5: Summary of Issues to Fix

### Critical (App won't work end-to-end)
1. **Endpoint path mismatches** — Frontend calls different URLs than backend serves (6+ mismatches listed above). Fix either frontend constants or backend router paths.
2. **CompanyOverview.tsx uses /v4/ paths** — Calls `/v4/entities/{id}/ratios`, `/v4/entities/{id}/financials/quarterly`, `/v4/entities/{id}/quality`, `/v4/entities/{id}/news` which don't exist in any backend router. Should use proper hooks.
3. **Database is empty on fresh install** — Must run migration + ingestion scripts.

### High (Features show mock data only)
4. **26 Pillar 1 hooks are never used** on any page — Entity detail, relationships, subsidiaries, officers, board, history, identifiers, classifications, security detail, prices, technicals, dividends, splits, corporate actions, exchanges, estimates, geographic breakdown, quarterly trends, annual summary, KPIs.
5. **No intraday price data** — Hook exists, no backend endpoint or data source.
6. **No analyst estimates** — Hook exists, backend is a stub file only.
7. **Search uses ILIKE** — Both entity and security search note "placeholder until Elasticsearch is wired up." Works but won't scale or produce relevant results.

### Medium (Missing computed data)
8. **Revenue breakdown/geographic breakdown** — No ingestion script. Would need XBRL segment parsing enhancement.
9. **KPIs and quality scores** — Computed by analytics batch, but frontend uses hardcoded `/v4/` paths.
10. **Exchanges and sectors list** — No backend endpoint to return reference data lists.

### Low (Polish)
11. **Entity officers/board** — Backend `executives.py` router exists but frontend hook paths may not match.
12. **Security technicals** — Backend `technical_studies.py` exists but paths likely don't match.
13. **Dividends/splits/corporate actions per security** — Backend `corporate_actions.py` exists but paths differ.
