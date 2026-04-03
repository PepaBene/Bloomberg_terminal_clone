# Pillar 1: Data Foundation — Deep Audit Report v2

## Executive Summary

This report is based on direct source-code inspection of all Pillar 1 backend routers, frontend pages, hooks, API constants, ingestion scripts, and docker infrastructure. The previous audit identified the broad picture; this report goes deeper and includes an exact, actionable remediation plan.

**Root cause of everything**: The frontend constants file (`frontend/src/api/endpoints.ts`) defines paths that were never reconciled against the actual backend router paths. This cascades into every page being broken even when the backend is running with data.

**Scope of damage**:
- 3 of 3 Pillar 1 pages that try to call APIs get 404s due to path mismatches
- 1 page (`CompanyOverview.tsx`) calls `/v4/` endpoints that never existed in any router
- 2 pages (`CompanyOverview.tsx` and `FinancialStatements.tsx`) have hardcoded display logic that ignores API data even when hooks succeed
- Database starts empty on every fresh deploy — no auto-initialization

---

## Part 1: Exact Backend Endpoint Map (What Actually Exists)

### Entities Router — `src/api/routers/entities.py`
Registered with prefix `/v1` in `app.py` (line 71). Router itself uses prefix `/entities`.

| Actual Endpoint | Method | Notes |
|---|---|---|
| `GET /v1/entities/search` | GET | ILIKE search, score=1.0 placeholder |
| `GET /v1/entities/{entity_id}` | GET | `expand` param: identifiers, names, relationships |
| `GET /v1/entities` | GET | Filters: LEI, CIK, status, country, entity_type |
| `GET /v1/entities/{entity_id}/hierarchy` | GET | Returns ultimate_parent, immediate_parent, subsidiaries |
| `GET /v1/entities/{entity_id}/securities` | GET | Lists all securities for issuer |
| `GET /v1/entities/{entity_id}/history` | GET | Point-in-time change history |
| `GET /v1/entities/{entity_id}/relationships` | GET | Filtered by type and active |
| `POST /v1/entities/resolve` | POST | Delegates to resolution engine |
| `POST /v1/entities/bulk-lookup` | POST | Batch identifier lookup |

**No endpoint for**: `/v1/entities/{id}/subsidiaries`, `/v1/entities/{id}/parent-chain`, `/v1/entities/{id}/officers`, `/v1/entities/{id}/board`, `/v1/entities/{id}/identifiers` (standalone), `/v1/entities/{id}/classifications`

### Securities Router — `src/api/routers/securities.py`
Registered with prefix `/v1` (line 87), router prefix `/securities`.

| Actual Endpoint | Method | Notes |
|---|---|---|
| `GET /v1/securities/search` | GET | ILIKE, score=1.0, ticker=None placeholder |
| `GET /v1/securities/{security_id}` | GET | `expand`: identifiers, equity_details, fi_details, credit_ratings, call_put |
| `GET /v1/securities` | GET | Filters: ISIN, CUSIP, FIGI, ticker, asset_class, status |
| `GET /v1/securities/{id}/identifiers` | GET | All identifier mappings |
| `GET /v1/securities/{id}/issuer` | GET | Returns issuer entity |
| `GET /v1/securities/{id}/related` | GET | Same-issuer securities |
| `GET /v1/securities/{id}/prices` | GET | EOD history with date range filter |
| `GET /v1/securities/{id}/prices/latest` | GET | Most recent EOD price |
| `POST /v1/securities/bulk-lookup` | POST | Batch identifier lookup |
| `POST /v1/securities/translate` | POST | Cross-identifier translation |

**No endpoint for**: `/prices/intraday`, `/prices/history` (use `/prices` with date params), `/institutional-holdings`, `/insider-holdings`, `/ownership-summary`, `/technicals`, `/dividends`, `/splits`, `/corporate-actions`, `/exchanges`, `/sectors`

### Fundamentals Router — `src/api/routers/fundamentals.py`
Registered with prefix `/v1` (line 108). No sub-prefix on router itself.

| Actual Endpoint | Method | Notes |
|---|---|---|
| `GET /v1/entities/{entity_id}/filings` | GET | Filterable by filing_type, status |
| `GET /v1/filings/{filing_id}` | GET | Single filing |
| `GET /v1/entities/{entity_id}/fundamentals` | GET | Combined IS+BS+CF by period |
| `GET /v1/entities/{entity_id}/fundamentals/income-statement` | GET | Income statement series |
| `GET /v1/entities/{entity_id}/fundamentals/balance-sheet` | GET | Balance sheet series |
| `GET /v1/entities/{entity_id}/fundamentals/cash-flow` | GET | Cash flow series |
| `GET /v1/entities/{entity_id}/segments` | GET | Segment data |

**No endpoint for**: `/income-statements` (note: wrong path used in frontend), `/balance-sheets`, `/cash-flows`, `/ratios`, `/revenue-breakdown`, `/geographic-breakdown`, `/quarterly-trends`, `/annual-summary`, `/kpis`

### Ownership Router — `src/api/routers/ownership.py`
Registered with prefix `/v1` (line 115). No sub-prefix on router.

| Actual Endpoint | Method | Notes |
|---|---|---|
| `GET /v1/institutions` | GET | Institutional investor profiles list |
| `GET /v1/institutions/{id}` | GET | Single institution profile |
| `GET /v1/securities/{id}/ownership/institutional` | GET | Per-security institutional holders |
| `GET /v1/securities/{id}/ownership/insider` | GET | Per-security insider transactions |
| `GET /v1/securities/{id}/ownership/summary` | GET | Latest ownership summary |
| `GET /v1/securities/{id}/short-interest` | GET | Short interest time series |

### Executives Router — `src/api/routers/executives.py`
Registered with prefix `/v1` (line 269). No sub-prefix.

| Actual Endpoint | Method |
|---|---|
| `GET /v1/entities/{entity_id}/executives` | GET |
| `GET /v1/executives/search` | GET |

### Corporate Actions Router — `src/api/routers/corporate_actions.py`
Registered with prefix `/v1` (line 129).

| Actual Endpoint | Method |
|---|---|
| `GET /v1/securities/{id}/corporate-actions` | GET |
| `GET /v1/securities/{id}/dividends` | GET |
| `GET /v1/securities/{id}/splits` | GET |
| `GET /v1/corporate-actions/calendar` | GET |

### Technical Studies Router — `src/api/routers/technical_studies.py`
Registered with prefix `/v1` (line 276).

| Actual Endpoint | Method |
|---|---|
| `GET /v1/securities/{id}/technicals` | GET |

---

## Part 2: Frontend API Constant Mismatches (Exact)

These are the exact mismatches between `frontend/src/api/endpoints.ts` and actual backend routes:

| Constant | Frontend Calls | Backend Serves | Fix |
|---|---|---|---|
| `FUNDAMENTALS.incomeStatements` | `/v1/entities/${id}/income-statements` | `/v1/entities/${id}/fundamentals/income-statement` | Fix constant |
| `FUNDAMENTALS.balanceSheets` | `/v1/entities/${id}/balance-sheets` | `/v1/entities/${id}/fundamentals/balance-sheet` | Fix constant |
| `FUNDAMENTALS.cashFlows` | `/v1/entities/${id}/cash-flows` | `/v1/entities/${id}/fundamentals/cash-flow` | Fix constant |
| `SECURITIES.institutionalHoldings` | `/v1/securities/${id}/institutional-holdings` | `/v1/securities/${id}/ownership/institutional` | Fix constant |
| `SECURITIES.insiderHoldings` | `/v1/securities/${id}/insider-holdings` | `/v1/securities/${id}/ownership/insider` | Fix constant |
| `SECURITIES.ownershipSummary` | `/v1/securities/${id}/ownership-summary` | `/v1/securities/${id}/ownership/summary` | Fix constant |
| `SECURITIES.pricesHistory` | `/v1/securities/${id}/prices/history` | Use `/v1/securities/${id}/prices` with date params | Fix constant/hook |
| `ENTITIES.subsidiaries` | `/v1/entities/${id}/subsidiaries` | `/v1/entities/${id}/hierarchy` | Fix constant OR add alias endpoint |
| `ENTITIES.parentChain` | `/v1/entities/${id}/parent-chain` | `/v1/entities/${id}/hierarchy` | Fix constant OR add alias endpoint |
| `ENTITIES.officers` | `/v1/entities/${id}/officers` | `/v1/entities/${id}/executives?role_type=EXECUTIVE` | Fix constant |
| `ENTITIES.boardMembers` | `/v1/entities/${id}/board` | `/v1/entities/${id}/executives?role_type=DIRECTOR` | Fix constant |
| `ENTITIES.identifiers` | `/v1/entities/${id}/identifiers` | Use `expand=identifiers` on detail endpoint | Remove or fix |
| `ENTITIES.classifications` | `/v1/entities/${id}/classifications` | **Does not exist** | Remove or add endpoint |
| `SECURITIES.exchanges` | `/v1/securities/exchanges` | **Does not exist** | Add endpoint or remove |
| `SECURITIES.sectors` | `/v1/securities/sectors` | **Does not exist** (sectors in reference router) | Wire to reference router |

---

## Part 3: Frontend Page Issues (Exact)

### CompanyOverview.tsx — **Completely Broken**

**Location**: `frontend/src/pages/company/CompanyOverview.tsx`

**Problem A — Calls `/v4/` endpoints (lines 241–281)**:
```typescript
// Line 241: Non-existent /v4/ prefix
queryFn: () => api.get(`/v4/entities/${resolvedId}/profile`),

// Line 250: Non-existent
queryFn: () => api.get(`/v4/entities/${resolvedId}/ratios`),

// Line 259: Non-existent
queryFn: () => api.get(`/v4/entities/${resolvedId}/financials/quarterly`),

// Line 268: Non-existent
queryFn: () => api.get(`/v4/entities/${resolvedId}/quality`),

// Line 277: Non-existent
queryFn: () => api.get(`/v4/entities/${resolvedId}/news`),
```
All 5 calls get 404s → always fall back to MOCK_COMPANY, MOCK_METRICS, MOCK_QUARTERLY, MOCK_QUALITY, MOCK_NEWS.

**Problem B — Static mock data never tries API (lines 564, 667)**:
```typescript
// Filings — never uses API hook, always renders MOCK_FILINGS
{MOCK_FILINGS.map((f) => (...))}

// Top holders — never uses API hook, always renders MOCK_HOLDERS
{MOCK_HOLDERS.map((h) => (...))}
```

**Problem C — Ticker/name come from mock regardless of entity**:
```typescript
const company = companyData ?? MOCK_COMPANY;
// company.name, company.ticker used in header — always "Apple Inc." / "AAPL"
```

**What each section should use (correct mapping)**:
| Section | Should Use | Endpoint |
|---|---|---|
| Company header (name, ticker, sector) | `useEntity(id)` | `GET /v1/entities/{id}` |
| Price / change % | `useSecurityPrices(secId)` latest | `GET /v1/securities/{id}/prices/latest` |
| Key metrics (P/E, EV/EBITDA, etc.) | `useRatios` from **Analytics** (Pillar 2) | `GET /v2/analytics/securities/{id}/ratios` |
| Quality scores | `useCompositeScores` (already partially wired) | `GET /v2/analytics/securities/{id}/composite-scores` |
| Quarterly financials chart | `useIncomeStatements` (after path fix) | `GET /v1/entities/{id}/fundamentals/income-statement?period_type=QUARTERLY` |
| Corporate actions | `useCorporateActionsUpcoming` (already wired) | Pillar 4 hook |
| Recent filings | `useFilings(entityId)` | `GET /v1/entities/{id}/filings` |
| Top institutional holders | `useInstitutionalHoldings(secId)` (after path fix) | `GET /v1/securities/{id}/ownership/institutional` |
| News | News hook (Pillar 4) — already partially wired | Pillar 4 router |

### FinancialStatements.tsx — **Hooks Wired But Ignored**

**Location**: `frontend/src/pages/company/FinancialStatements.tsx`

The page calls the hooks correctly and even conditionally renders API data for segments and revenue breakdown. However the three core statement tables always use the hardcoded `incomeStatementRows`, `balanceSheetRows`, `cashFlowRows` arrays regardless of API results. The hooks fail with 404 anyway (wrong paths), but even if they returned data the display logic wouldn't use it.

**Problem A — Hooks have wrong path** (through `endpoints.ts` constants):
- `useIncomeStatements` → calls `/v1/entities/${id}/income-statements` → 404 (should be `.../fundamentals/income-statement`)
- `useBalanceSheets` → calls `/v1/entities/${id}/balance-sheets` → 404
- `useCashFlows` → calls `/v1/entities/${id}/cash-flows` → 404

**Problem B — Display ignores API data**:
```typescript
// The component renders incomeStatementRows (static), not transformed API data
<StatementTable rows={incomeRows} periods={periods} ... />
// incomeRows = incomeStatementRows slice (static mock data)
```
There is no code path that maps `IncomeStatementResponse` fields from the API to `StatementRowData` format for the table. The API response structure and display structure are both defined but never connected.

### OwnershipDashboard.tsx — **Hooks Wired With Wrong Paths**

**Location**: `frontend/src/pages/company/OwnershipDashboard.tsx`

Uses the correct hook imports but the underlying constants point to wrong paths.

| Hook | Frontend Path | Backend Path | Status |
|---|---|---|---|
| `useInstitutionalHoldings` | `/v1/securities/${id}/institutional-holdings` | `/v1/securities/${id}/ownership/institutional` | 404 |
| `useInsiderHoldings` | `/v1/securities/${id}/insider-holdings` | `/v1/securities/${id}/ownership/insider` | 404 |
| `useOwnershipSummary` | `/v1/securities/${id}/ownership-summary` | `/v1/securities/${id}/ownership/summary` | 404 |
| `useShortInterest` | `/v1/securities/${id}/short-interest` | `/v1/securities/${id}/short-interest` | **CORRECT** |

Also: company name/ticker is hardcoded as "Apple Inc."/"AAPL" — not driven from `useEntity`.

### GovernanceDashboard.tsx — **Uses Pillar 4 Hooks for Board Data**

**Location**: `frontend/src/pages/company/GovernanceDashboard.tsx`

Uses `useGovernanceBoard`, `useGovernanceCompensation` etc. which are AI-generated governance intelligence (Pillar 4). The actual structured board/executives data lives in the executives router (`/v1/entities/{id}/executives`) and is never accessed by this page. Falls back to `MOCK_BOARD`, `MOCK_COMPENSATION`, `MOCK_PROPOSALS`.

The Pillar 4 governance hooks are fine for narrative content, but the structured board table should be sourced from `useEntityOfficers`/`useEntityBoardMembers` hooks (pointing to `/v1/entities/{id}/executives`).

### FilingsView.tsx — **Uses Pillar 4 Intelligence Hooks, Not Pillar 1 Filings**

**Location**: `frontend/src/pages/company/FilingsView.tsx`

The "Recent Filings" table should be driven by `useFilings` from Pillar 1 (`GET /v1/entities/{id}/filings`). Instead it uses `useFilingEvents` which is a Pillar 4 filing intelligence hook (AI-processed filing events, not raw EDGAR filings). The static `filings` array is used as fallback.

The Pillar 4 hooks (`useFilingDiffs`, `useFilingInsiders`, `useFilingRiskFactors`, `useFilingMDNA`) are appropriate for the diff viewer and insider sections. But the filings list should use the Pillar 1 endpoint.

---

## Part 4: Hooks That Should Be Removed (No Backend or No Data)

These hooks exist in `useSecurities.ts` and `useFundamentals.ts` but have no corresponding backend endpoint and no realistic data source. Keeping them creates confusion.

| Hook | Reason to Remove |
|---|---|
| `useSecurityPricesIntraday` | No backend endpoint, no intraday data source. The frontend constant `SECURITIES.pricesIntraday` → `/v1/securities/${id}/prices/intraday` gets a 404. No free intraday data source is integrated. |
| `useGeographicBreakdown` | No backend endpoint, no XBRL parsing for geographic segments. Constant maps to nonexistent `/v1/entities/${id}/geographic-breakdown`. |
| `useAnnualSummary` | No backend endpoint. Would require computed analytics that don't exist. |
| `useQuarterlyTrends` | No backend endpoint. Redundant with `useIncomeStatements` filtered by `period_type=QUARTERLY`. |
| `useKpis` | No backend endpoint. KPIs come from analytics engine (Pillar 2), not Pillar 1. |

These should be removed from `useSecurities.ts` / `useFundamentals.ts` and their constants removed from `endpoints.ts`. Pages that reference them should use the correct analytics hooks (Pillar 2) instead.

---

## Part 5: Missing "Estimates" Module

The frontend `endpoints.ts` defines estimate constants that aren't in any Pillar 1 section:
```typescript
// These appear in fundamentals hooks as useEstimates, useEstimatesConsensus
FUNDAMENTALS.estimates(entityId) → `/v1/entities/${entityId}/estimates`
FUNDAMENTALS.estimatesConsensus(entityId) → `/v1/entities/${entityId}/estimates/consensus`
```

There is no `estimates.py` router anywhere. There is no estimates data source. The backend stub mentioned in the previous report doesn't exist in the router directory. These should be removed from Pillar 1 scope — analyst estimates require paid data (Bloomberg Terminal, FactSet, Capital IQ).

---

## Part 6: Database Initialization — No Auto-Populate Mechanism

**Problem**: `docker-compose.yml` starts Postgres, Redis, and Elasticsearch but contains no service that:
- Runs `alembic upgrade head` (migrations)
- Seeds reference data
- Populates entities, securities, or fundamentals

On every fresh `docker-compose up`, all tables are empty. The app backend starts but all queries return empty results.

**Current manual process**:
1. `docker-compose up -d`
2. `alembic upgrade head` (must be run manually)
3. `python scripts/seed_reference.py`
4. `python scripts/ingest_edgar.py` (needs `SEC_USER_AGENT` in `.env`)
5. `python scripts/ingest_openfigi.py` (optional API key)
6. `python scripts/ingest_edgar_xbrl.py` (for financial statements)
7. `python scripts/ingest_eod_prices.py` (needs `POLYGON_API_KEY`)
8. `python scripts/ingest_ownership.py` (13F filings)
9. `python scripts/ingest_short_interest.py` (FINRA)

---

## Part 7: Data Available vs. Frontend Requirements

This maps what data exists (after ingestion) to what pages actually need to show:

| Frontend Need | Data Available? | Source | Notes |
|---|---|---|---|
| Company name, sector, country | Yes (after EDGAR ingest) | entities table | |
| Ticker symbol | Yes (after OpenFIGI ingest) | security_identifiers | |
| EOD price, % change | Yes (after Polygon ingest) | eod_prices table | No intraday |
| Income statement (annual/quarterly) | Yes (after XBRL ingest) | income_statements table | |
| Balance sheet | Yes | balance_sheets table | |
| Cash flow | Yes | cash_flow_statements table | |
| Filings list | Yes (after EDGAR ingest) | filings table | |
| Institutional holdings | Yes (after EDGAR 13F) | institutional_holdings table | |
| Insider transactions | Yes (after EDGAR Form 4) | insider_holdings table | |
| Short interest | Yes (after FINRA ingest) | short_interest table | |
| Board / executives | Yes (after governance ingest) | executives, executive_roles | `populate_governance.py` |
| P/E, EV/EBITDA, ratios | Computed | analytics engine | Must run `run_analytics_batch.py` |
| Quality scores | Computed | analytics engine | Must run `run_analytics_batch.py` |
| Revenue breakdown by segment | Yes (partial) | segment_data table | XBRL segments |
| Geographic breakdown | No | — | No ingestion script |
| Analyst estimates | No | — | Paid data required |
| Intraday prices | No | — | No free source integrated |

---

## Part 8: Complete Remediation Plan

### Phase 1 — Fix Path Mismatches (1–2 days, no new code)

Everything in this phase is a string change in a single file.

**Step 1.1 — Fix `frontend/src/api/endpoints.ts`**

Change these 6 constants to match actual backend paths:

```typescript
// FUNDAMENTALS section
incomeStatements: (entityId: string) => `/v1/entities/${entityId}/fundamentals/income-statement`,
balanceSheets: (entityId: string) => `/v1/entities/${entityId}/fundamentals/balance-sheet`,
cashFlows: (entityId: string) => `/v1/entities/${entityId}/fundamentals/cash-flow`,

// SECURITIES section
institutionalHoldings: (id: string) => `/v1/securities/${id}/ownership/institutional`,
insiderHoldings: (id: string) => `/v1/securities/${id}/ownership/insider`,
ownershipSummary: (id: string) => `/v1/securities/${id}/ownership/summary`,

// SECURITIES.pricesHistory — rename and repoint
pricesHistory: (id: string, start?: string, end?: string) =>
  `/v1/securities/${id}/prices${start ? `?start=${start}` : ''}`,
  // OR just remove this and have callers use SECURITIES.prices with params

// ENTITIES section — fix officers/board to point to executives
officers: (id: string) => `/v1/entities/${id}/executives?role_type=EXECUTIVE`,
boardMembers: (id: string) => `/v1/entities/${id}/executives?role_type=DIRECTOR`,

// Remove these (no backend endpoint exists):
// - ENTITIES.identifiers (use expand=identifiers on detail)
// - ENTITIES.classifications
// - SECURITIES.pricesIntraday
// - SECURITIES.exchanges (until added to reference router)
// - SECURITIES.sectors (wire to /v1/reference/sectors if exists)
// - FUNDAMENTALS.quarterlyTrends
// - FUNDAMENTALS.annualSummary
// - FUNDAMENTALS.kpis
// - FUNDAMENTALS.geographicBreakdown
// - FUNDAMENTALS.ratios (use ANALYTICS.ratios from Pillar 2)
```

**Step 1.2 — Remove dead hooks from `useSecurities.ts` and `useFundamentals.ts`**

Remove: `useSecurityPricesIntraday`, `useGeographicBreakdown`, `useAnnualSummary`, `useQuarterlyTrends`, `useKpis`, `useEntityIdentifiers`, `useEntityClassifications` (until endpoints are added).

**Step 1.3 — After Step 1.1, `FinancialStatements.tsx` hooks will get real responses but display still uses static mock. Wire the data (see Phase 2).**

---

### Phase 2 — Wire CompanyOverview.tsx to Real Data (2–3 days)

This is the most impactful change. The page must stop calling `/v4/` paths.

**Step 2.1 — Replace `/v4/` entity profile call**:
```typescript
// Remove:
const { data: companyData } = useQuery({
  queryFn: () => api.get(`/v4/entities/${resolvedId}/profile`),
});
const company = companyData ?? MOCK_COMPANY;

// Replace with:
import { useEntity } from '@/hooks';
const { data: entityData, isLoading: loadingEntity } = useEntity(resolvedId ?? '');
// Map EntityResponse to CompanyInfo shape
const company: CompanyInfo = entityData ? {
  name: entityData.legal_name,
  ticker: entityData.primary_ticker ?? '—',   // from identifiers expand
  exchange: entityData.primary_exchange ?? '—',
  sector: entityData.gics_sector ?? '—',
  industry: entityData.gics_industry ?? '—',
  price: latestPrice?.close_price ?? 0,
  changePct: latestPrice?.change_pct ?? 0,
} : MOCK_COMPANY;
```

**Step 2.2 — Replace `/v4/` ratios/KPI call**:
```typescript
// Remove:
const { data: kpiData } = useQuery({
  queryFn: () => api.get(`/v4/entities/${resolvedId}/ratios`),
});

// Replace with (using Pillar 2 analytics — already defined in ANALYTICS constants):
import { useCompositeScores } from '@/hooks';
// compositeScores already used on line 287! Remove the duplicate /v4/ call.
// Map composite scores to MetricItem[] for KeyMetricsGrid
```

**Step 2.3 — Replace `/v4/` quarterly financials**:
```typescript
// Remove:
const { data: quarterlyRaw } = useQuery({
  queryFn: () => api.get(`/v4/entities/${resolvedId}/financials/quarterly`),
});

// Replace with (after path fix in Phase 1):
import { useIncomeStatements } from '@/hooks';
const { data: isData } = useIncomeStatements(entityId, { period_type: 'QUARTERLY', limit: 4 });
// Map IncomeStatementResponse[] to QuarterlyFinancial[] for bar chart
```

**Step 2.4 — Replace static `MOCK_FILINGS` table**:
```typescript
// Remove static:
{MOCK_FILINGS.map((f) => (...))}

// Replace with:
import { useFilings } from '@/hooks';
const { data: filingsData } = useFilings(entityId);
const filings = (filingsData as any)?.data ?? MOCK_FILINGS;
{filings.map((f: any, i: number) => (
  <tr key={i}>
    <td>{f.filing_date}</td>
    <td>{f.filing_type}</td>
    <td>{f.period_end_date ?? 'N/A'}</td>
    <td>{f.description ?? '—'}</td>
  </tr>
))}
```

**Step 2.5 — Replace static `MOCK_HOLDERS` table**:
```typescript
// Remove static:
{MOCK_HOLDERS.map((h) => (...))}

// Replace with (after securityId is resolved):
import { useInstitutionalHoldings } from '@/hooks';
const { data: holdersData } = useInstitutionalHoldings(securityId);
const holders = (holdersData as any)?.data ?? MOCK_HOLDERS;
{holders.slice(0, 5).map((h: any, i: number) => (...))}
```

**Step 2.6 — Remove `/v4/` quality and news calls**:
- Quality scores: `useCompositeScores` is already called on line 287. Remove the duplicate `/v4/` call (lines 266–272) and use the existing `compositeScores` data.
- News: Replace with news hook from Pillar 4 (already exists as `useNewsSearch` or `useEntityNews`).

---

### Phase 3 — Wire FinancialStatements.tsx to Use API Data (1–2 days)

**Problem**: The page calls hooks and gets data but renders static `incomeStatementRows`, `balanceSheetRows`, `cashFlowRows` arrays regardless.

**Step 3.1 — Add data transformation**:
After Phase 1 path fixes, hooks will return real data. Add a transform function:

```typescript
// Transform API IncomeStatementResponse[] → StatementRowData[]
function toIncomeRows(data: IncomeStatementResponse[]): StatementRowData[] {
  if (!data?.length) return incomeStatementRows; // fallback to mock
  const periods = data.map(d => d.period?.period_label ?? '—');
  return [
    {
      key: 'revenue', label: 'Revenue', indent: 0, isBold: true,
      values: data.map(d => d.total_revenue ?? 0),
    },
    { key: 'cogs', label: 'Cost of Revenue', indent: 0,
      values: data.map(d => d.cost_of_revenue ?? 0) },
    { key: 'gross-profit', label: 'Gross Profit', indent: 0, isBold: true,
      values: data.map(d => d.gross_profit ?? 0) },
    { key: 'op-income', label: 'Operating Income', indent: 0, isBold: true,
      values: data.map(d => d.operating_income ?? 0) },
    { key: 'net-income', label: 'Net Income', indent: 0, isBold: true,
      values: data.map(d => d.net_income ?? 0) },
    { key: 'eps-diluted', label: 'EPS (Diluted)', indent: 0,
      values: data.map(d => d.eps_diluted ?? 0) },
  ];
}
```

**Step 3.2 — Wire to actual display**:
```typescript
const { data: isRaw } = useIncomeStatements(entityId, { period_type: periodMode === 'annual' ? 'ANNUAL' : 'QUARTERLY' });
const incomeRows = isRaw?.data?.length ? toIncomeRows(isRaw.data) : incomeStatementRows;
// Replace static slice: const incomeRows = incomeStatementRows.slice(0, periodCount);
//   → const incomeRows = (from API or mock).slice(0, periodCount);
```

Same for balance sheet and cash flow.

---

### Phase 4 — Fix OwnershipDashboard.tsx (0.5 days)

After Phase 1 path fixes, hooks will return real data. Two remaining issues:

**Step 4.1 — Use entity data for company header**:
```typescript
// Replace hardcoded:
const company = { name: 'Apple Inc.', ticker: 'AAPL' };

// With:
const { data: entityData } = useEntity(resolvedId ?? '');
const company = { name: entityData?.legal_name ?? '—', ticker: '—' };
```

**Step 4.2 — Map API response shapes to component props**:
The `OwnershipSummary` component expects `Holder[]` with `{ name, shares, pctOwned, change, value }`.
The API returns `InstitutionalHoldingResponse`. A small transform function is needed.

---

### Phase 5 — Wire GovernanceDashboard.tsx Board Section (0.5 days)

The structured board table should come from the executives endpoint:

```typescript
// Add to GovernanceDashboard.tsx:
import { useEntityBoardMembers } from '@/hooks';
const { data: apiBoard } = useEntityBoardMembers(resolvedId ?? '');

// After path fix in Phase 1, this calls /v1/entities/{id}/executives?role_type=DIRECTOR
// Map ExecutiveResponse[] to the board table display
const board = apiBoard?.data?.map((e: any) => ({
  name: e.full_name,
  role: e.current_title,
  independent: e.is_independent ?? true,
  tenure: /* calculate from start_date */ 0,
  committees: e.committees ?? [],
})) ?? MOCK_BOARD;
```

---

### Phase 6 — Fix FilingsView.tsx to Use Pillar 1 Filings (0.5 days)

```typescript
// Replace useFilingEvents with useFilings for the filing list:
import { useFilings } from '@/hooks';
const { data: apiFilingsList } = useFilings(resolvedId ?? '');
const activeFilings = apiFilingsList?.data ?? filings;

// Keep Pillar 4 hooks for intelligence sections (diffs, insider signals, etc.)
```

---

### Phase 7 — Database Auto-Initialization (1 day)

**Step 7.1 — Add init service to `docker-compose.yml`**:
```yaml
  db-init:
    build:
      context: .
      dockerfile: Dockerfile.init
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      - DATABASE_URL=postgresql+asyncpg://bloomberg:bloomberg_dev@postgres/bloomberg
      - SEC_USER_AGENT=${SEC_USER_AGENT:-bloomberg-data-fabric contact@example.com}
    volumes:
      - .:/app
    working_dir: /app
    command: >
      sh -c "
        echo 'Running migrations...' &&
        alembic upgrade head &&
        echo 'Seeding reference data...' &&
        python scripts/seed_reference.py &&
        echo 'Ingesting EDGAR entities (first 500)...' &&
        python scripts/ingest_edgar.py --limit 500 &&
        echo 'Database initialization complete.'
      "
    restart: on-failure
```

**Step 7.2 — Create `Makefile` target for full data population**:
```makefile
# Makefile
init-db: ## Initialize DB with migrations and seed data
	docker-compose run --rm db-init

populate-full: ## Run all ingestion scripts (requires API keys in .env)
	docker-compose exec app python scripts/seed_reference.py
	docker-compose exec app python scripts/ingest_edgar.py
	docker-compose exec app python scripts/ingest_openfigi.py
	docker-compose exec app python scripts/ingest_edgar_xbrl.py
	docker-compose exec app python scripts/ingest_eod_prices.py
	docker-compose exec app python scripts/ingest_ownership.py
	docker-compose exec app python scripts/ingest_short_interest.py
	docker-compose exec app python scripts/populate_governance.py
	docker-compose exec app python scripts/run_analytics_batch.py
```

**Step 7.3 — Add `.env.example` with all required keys**:
```bash
# .env.example
SEC_USER_AGENT=YourApp yourname@example.com
POLYGON_API_KEY=          # Free at polygon.io
FRED_API_KEY=             # Free at fred.stlouisfed.org
OPENFIGI_API_KEY=         # Optional, increases rate limit
DATABASE_URL=postgresql+asyncpg://bloomberg:bloomberg_dev@localhost/bloomberg
REDIS_URL=redis://localhost:6379
ELASTICSEARCH_URL=http://localhost:9200
```

---

### Phase 8 — Add Missing Backend Endpoints (2 days)

These are endpoints the frontend reasonably needs but the backend is missing:

**Step 8.1 — Add `GET /v1/securities/exchanges`** to `securities.py` or `reference.py`:
```python
@router.get("/exchanges", response_model=list[ExchangeResponse])
async def list_exchanges(session: AsyncSession = Depends(get_session)):
    """Return all exchanges from reference data."""
    result = await session.execute(select(Exchange).order_by(Exchange.name))
    return [ExchangeResponse.model_validate(e) for e in result.scalars().all()]
```

**Step 8.2 — Add `GET /v1/securities/sectors`** — Wire to existing GICS reference data in `reference.py`.

**Step 8.3 — Add `GET /v1/entities/{id}/subsidiaries`** alias in `entities.py`:
```python
@router.get("/{entity_id}/subsidiaries", response_model=list[EntityBriefResponse])
async def get_entity_subsidiaries(entity_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    """Shortcut for hierarchy subsidiaries list."""
    # Reuse the hierarchy query, return only subsidiaries
    ...
```

**Step 8.4 — Add `GET /v1/entities/{id}/parent-chain`** similarly.

---

## Part 9: Summary — Issues by Priority

### Critical (App Non-Functional Without These)
| # | Issue | File(s) | Fix |
|---|---|---|---|
| C1 | 6 path mismatches in `endpoints.ts` cause all financial hooks to 404 | `frontend/src/api/endpoints.ts` | Phase 1 |
| C2 | `CompanyOverview.tsx` calls `/v4/` paths — 5 non-existent endpoints | `CompanyOverview.tsx` lines 241–281 | Phase 2 |
| C3 | `FinancialStatements.tsx` hooks fixed by C1 but display ignores API data | `FinancialStatements.tsx` | Phase 3 |
| C4 | Database starts empty — no auto-init | `docker-compose.yml` | Phase 7 |

### High (Pages Show Mock Data 100% of the Time)
| # | Issue | File(s) | Fix |
|---|---|---|---|
| H1 | `CompanyOverview.tsx` filings section always renders `MOCK_FILINGS` | `CompanyOverview.tsx` line 564 | Phase 2 step 4 |
| H2 | `CompanyOverview.tsx` holders section always renders `MOCK_HOLDERS` | `CompanyOverview.tsx` line 667 | Phase 2 step 5 |
| H3 | `OwnershipDashboard.tsx` 3 of 4 hooks have wrong paths | `OwnershipDashboard.tsx` | Phase 1+4 |
| H4 | Company name/ticker hardcoded "Apple Inc."/"AAPL" in 4 pages | CompanyOverview, OwnershipDashboard, FinancialStatements, FilingsView | Phase 2,3,4,6 |
| H5 | `GovernanceDashboard.tsx` board section uses Pillar 4 AI hooks instead of executives data | `GovernanceDashboard.tsx` | Phase 5 |

### Medium (Misleading Endpoints / Missing Features)
| # | Issue | File(s) | Fix |
|---|---|---|---|
| M1 | `useEntityOfficers/BoardMembers` hooks call wrong paths for executives | `useEntities.ts`, `endpoints.ts` | Phase 1 step 1 |
| M2 | `useSecurityPricesIntraday` exists but has no backend or data source | `useSecurities.ts`, `endpoints.ts` | Remove in Phase 1 |
| M3 | `useGeographicBreakdown`, `useAnnualSummary`, `useKpis` etc. — dead hooks | `useFundamentals.ts`, `endpoints.ts` | Remove in Phase 1 |
| M4 | `FilingsView.tsx` uses filing intelligence hook for filing list instead of Pillar 1 | `FilingsView.tsx` | Phase 6 |
| M5 | `SECURITIES.exchanges` and `SECURITIES.sectors` constants have no backend endpoint | `endpoints.ts` | Phase 8 |
| M6 | `ENTITIES.subsidiaries/parentChain` call missing backend paths | `endpoints.ts` | Phase 1/8 |

### Low (Polish / Scale)
| # | Issue | Notes |
|---|---|---|
| L1 | Search returns `score=1.0` for all results — no relevance ranking | ES is in docker-compose but not wired |
| L2 | Securities search `ticker=None` — ticker not populated in search results | Would need identifier join |
| L3 | `useEstimates` family — no backend, no data source | Remove from Pillar 1 scope; mark as "future paid data" |
| L4 | `ENTITIES.identifiers` hook — not a separate endpoint; available via `expand=identifiers` | Merge into `useEntity` call |

---

## Part 10: Recommended Execution Order

1. **Phase 7 first** — get the database populated before testing anything else
2. **Phase 1** — fix all `endpoints.ts` path mismatches (pure string edits, zero risk)
3. **Phase 2** — fix `CompanyOverview.tsx` (highest visibility page)
4. **Phase 3** — wire `FinancialStatements.tsx` display to API data
5. **Phase 4** — fix `OwnershipDashboard.tsx` fallback logic
6. **Phase 5** — wire `GovernanceDashboard.tsx` board section
7. **Phase 6** — fix `FilingsView.tsx` filing list
8. **Phase 8** — add the few genuinely missing backend endpoints (exchanges, sectors, subsidiaries alias)

**Total estimated effort**: 7–10 developer days for a complete end-to-end wired Pillar 1.

After completing Phases 1–7, the app will show real data for: entity name/profile, financial statements (IS/BS/CF), institutional holdings, insider activity, short interest, filings, and board/executives. The only sections that will still fall back to mock are: KPIs/ratios (need analytics batch run), quality scores (same), price chart (needs Polygon key + ingestion), and any AI-narrative sections in Pillar 4.
