# Pillar 2 Analytics Engine — Complete Feature Audit Report

**Date:** 2026-04-02
**Scope:** All Pillar 2 Analytics features — backend engines, API routers, frontend hooks, and dashboard pages.
**Method:** Static code analysis — no tests run.

---

## Executive Summary

Pillar 2 has solid backend implementation: all 35+ analytics endpoints have real SQL queries and engine implementations. However, **the entire frontend-to-backend connection is broken**. The root cause is a single architectural mismatch: the frontend `ANALYTICS` endpoint constants use a `/v2/analytics/securities/{id}/[metric]` URL pattern, but the backend router organises endpoints as `/v2/analytics/[metric]/{security_id}`.

Out of 29 `ANALYTICS` constants in `endpoints.ts`:
- **1** has the correct path
- **14** have wrong paths (endpoint exists on backend, URL just differs)
- **14** call endpoints that do not exist on the backend at all

Additionally, multiple dashboard pages never wire API responses into their displayed data (they fall back silently to mock data), several pages use completely wrong hooks, and the analytics batch computation pipeline is never triggered automatically.

---

## Part 1: The Universal Path Mismatch

### Root Cause

`frontend/src/api/endpoints.ts` defines all analytics URLs in the form:
```
/v2/analytics/securities/{secId}/{metric}
```

The backend analytics router (`src/api/routers/analytics.py`, prefix `/v2/analytics`) uses:
```
/v2/analytics/{metric}/{security_id}
```

This affects every single analytics endpoint.

### Full Endpoint Mapping

| Feature | Frontend ANALYTICS constant → URL called | Backend actual URL | Status |
|---|---|---|---|
| Ratios | `ratios(id)` → `.../securities/{id}/ratios` | GET `/ratios/{id}` | PATH MISMATCH |
| All Scores | `allScores(id)` → `.../securities/{id}/scores/all` | GET `/scores/{id}` | PATH MISMATCH |
| Composite Scores | `compositeScores(id)` → `.../securities/{id}/composite-scores` | GET `/scores/{id}/composites` | PATH MISMATCH |
| DuPont | `dupont(id)` → `.../securities/{id}/dupont` | GET `/dupont/{id}` | PATH MISMATCH |
| DuPont History | `dupontHistory(id)` → `.../securities/{id}/dupont/history` | GET `/dupont/{id}/history` | PATH MISMATCH |
| Multiples History | `multiplesHistory(id)` → `.../securities/{id}/multiples/history` | GET `/multiples/{id}/history` | PATH MISMATCH |
| Historical Multiples | `historicalMultiples(id)` → `.../securities/{id}/historical-multiples` | GET `/multiples/{id}` | PATH MISMATCH |
| Peer Group | `peerGroup(id)` → `.../securities/{id}/peer-group` | GET `/peers/{id}` | PATH MISMATCH |
| Peer Comparison | `peerComparison(id)` → `.../securities/{id}/peer-comparison` | GET `/ratios/{id}/vs-peers` | PATH MISMATCH |
| DCF (GET) | `dcf(id)` → `.../securities/{id}/dcf` | GET `/dcf/{id}/default` | PATH MISMATCH |
| Football Field | `footballField(id)` → `.../securities/{id}/football-field` | GET `/valuation/{id}/summary` | PATH MISMATCH |
| Screen Fields | `screenFields` → `.../screen/fields` | GET `/screen/fields` | **CORRECT** |
| Screen Prebuilt | `screenPrebuilt` → `.../screen/prebuilt` | GET `/screens/library` | PATH MISMATCH |
| Screen Save | `screenSave` → `.../screen/save` | POST `/screens/save` | PATH MISMATCH |
| Screen History | `screenHistory` → `.../screen/history` | GET `/screens/saved` | PATH MISMATCH |
| Quality Score | `qualityScore(id)` → `.../securities/{id}/quality-score` | No endpoint | MISSING |
| Value Score | `valueScore(id)` → `.../securities/{id}/value-score` | No endpoint | MISSING |
| Growth Score | `growthScore(id)` → `.../securities/{id}/growth-score` | No endpoint | MISSING |
| Momentum Score | `momentumScore(id)` → `.../securities/{id}/momentum-score` | No endpoint | MISSING |
| Volatility Score | `volatilityScore(id)` → `.../securities/{id}/volatility-score` | No endpoint | MISSING |
| Sector Relative | `sectorRelative(id)` → `.../securities/{id}/sector-relative` | No endpoint | MISSING |
| Fair Value | `fairValue(id)` → `.../securities/{id}/fair-value` | No endpoint | MISSING |
| Technical Signals | `technicalSignals(id)` → `.../securities/{id}/technical-signals` | No endpoint | MISSING |
| Seasonality | `seasonality(id)` → `.../securities/{id}/seasonality` | No endpoint | MISSING |
| Factor Exposure | `factorExposure(id)` → `.../securities/{id}/factor-exposure` | No endpoint | MISSING |
| Correlation | `correlation` → `.../correlation` (GET) | No GET endpoint | MISSING |
| Peer Ranking | `peerRanking(id)` → `.../securities/{id}/peer-ranking` | No GET endpoint (POST `/rank` only) | MISSING |
| DCF Sensitivity | `dcfSensitivity(id)` → `.../securities/{id}/dcf/sensitivity` | No GET endpoint | MISSING |
| Screen Run | `screen` → `.../screen` (POST) | POST `/screen` | PATH OK — payload format wrong |

**Every single analytics hook in the application will receive a 404 except `useScreenFields`.**

---

## Part 2: Feature-by-Feature Breakdown

---

### Feature 1: Financial Ratios

**Files:** `src/api/routers/analytics.py:116`, `src/engines/e1_ratios.py`, `frontend/src/hooks/useAnalytics.ts:54`

**Backend:** Complete. `GET /ratios/{security_id}` queries pre-computed `AnalyticsResult` rows via `e1_ratios` engine.

**Frontend:** Broken.
- `useAnalyticsRatios(secId)` calls `/v2/analytics/securities/{id}/ratios` → 404 (backend path is `/v2/analytics/ratios/{id}`)
- No dedicated ratios display page; ratios are consumed inside `RatioDashboard` component via `ValuationDashboard`

**Fix required:** Update `ANALYTICS.ratios` path constant.

---

### Feature 2: DuPont Analysis

**Files:** `src/api/routers/analytics.py:309,329`, `src/engines/e1_dupont.py`, `frontend/src/pages/company/ValuationDashboard.tsx:149`

**Backend:** Complete. `GET /dupont/{security_id}` and `GET /dupont/{security_id}/history` both implemented.

**Frontend:** Broken at two levels.
1. `useDuPont(secId)` calls `/v2/analytics/securities/{id}/dupont` → 404 (backend: `/v2/analytics/dupont/{id}`)
2. `useDuPontHistory(secId)` calls wrong path similarly
3. `ValuationDashboard.tsx:157` uses `(apiDupont as any) ?? dupontData` — falls back to mock data silently

**Fix required:** Fix `ANALYTICS.dupont` and `ANALYTICS.dupontHistory` paths.

---

### Feature 3: Multiples History / Historical Multiples

**Files:** `src/api/routers/analytics.py:394,421`, `frontend/src/pages/company/ValuationDashboard.tsx:150,200`

**Backend:** Complete. `GET /multiples/{security_id}` and `GET /multiples/{security_id}/history` both implemented.

**Frontend:** Broken at two levels.
1. `useMultiplesHistory(secId)` calls `/v2/analytics/securities/{id}/multiples/history` → 404
2. `useHistoricalMultiples(secId)` calls `/v2/analytics/securities/{id}/historical-multiples` → 404 (backend: `/v2/analytics/multiples/{id}`)
3. `ValuationDashboard.tsx:200–204` renders `multiplesOverTimeData` — this is a **separate hardcoded array** of 20 data points that is never replaced by any API call. The `activeMultiplesHistory` from the hook goes to `RatioDashboard`, but the "Multiples Over Time (5Y)" chart always shows static data.

**Fix required:** Fix both path constants. Wire the MultiplesOverTime component to use API data.

---

### Feature 4: WACC Calculation

**Files:** `src/api/routers/analytics.py:459,479,498`, `src/engines/e2_wacc.py`

**Backend:** Complete. Three endpoints: `GET /wacc/{id}`, `GET /wacc/{id}/history`, `GET /wacc/{id}/components`.

**Frontend:** No hook, no display page. WACC values shown in `ValuationDashboard` DCF section are hardcoded (`waccValues` array: `[0.07, 0.08, 0.09, 0.10, 0.11, 0.12, 0.13]` — static sensitivity inputs, never fetched).

**Fix required:** Add `ANALYTICS.wacc`, `ANALYTICS.waccComponents` constants. Add `useWacc` hook. Wire WACC into ValuationDashboard and/or DCF sensitivity inputs.

---

### Feature 5: TTM (Trailing Twelve Months) Metrics

**Files:** `src/api/routers/analytics.py:360`, `src/engines/e1_ttm.py`

**Backend:** Complete. `GET /ttm/{security_id}` implemented.

**Frontend:** No hook, no display. No `ANALYTICS.ttm` constant.

**Fix required:** Add hook and wire to a display surface (could be a header KPI strip in ValuationDashboard or FinancialStatements).

---

### Feature 6: DCF Model

**Files:** `src/api/routers/analytics.py:1053,1088`, `src/engines/e2_dcf.py`, `frontend/src/pages/company/ValuationDashboard.tsx:149,168`

**Backend:** Partially complete.
- GET `/dcf/{security_id}/default` — fetches last-computed DCF
- POST `/dcf/{security_id}` — runs DCF with custom assumptions in request body
- **No** GET endpoint for sensitivity analysis (only computed as part of POST response)

**Frontend:** Multiple issues.
1. `useDCFModel(secId)` calls GET `/v2/analytics/securities/{id}/dcf` → 404 (backend: GET `/v2/analytics/dcf/{id}/default`)
2. `useDCFSensitivity(secId)` calls GET `/v2/analytics/securities/{id}/dcf/sensitivity` → 404 (no such backend endpoint)
3. `ValuationDashboard.tsx:168–181` `handleDCFRecalculate` POSTs to `/v2/analytics/securities/${resolvedId}/dcf` → 404 (backend POST is `/v2/analytics/dcf/{id}`)
4. The sensitivity matrix (`priceMatrix`) is **always the hardcoded mock** `waccValues × growthValues` grid. `apiSensitivity` is never used in rendering.
5. The DCF recalculate button silently catches the 404 error and shows nothing to the user.

**Fix required:** Fix GET path for `ANALYTICS.dcf`. Add POST DCF mutation hook. Wire sensitivity response into `SensitivityMatrix` component. Add user feedback on recalculate errors.

---

### Feature 7: Football Field / Valuation Summary

**Files:** `src/api/routers/analytics.py:1178`, `src/engines/e2_football_field.py`, `frontend/src/pages/company/ValuationDashboard.tsx:154`

**Backend:** Complete. `GET /valuation/{security_id}/summary` returns football field ranges.

**Frontend:** Broken.
1. `useFootballField(secId)` calls `/v2/analytics/securities/{id}/football-field` → 404 (backend: `/v2/analytics/valuation/{id}/summary`)
2. `apiFootball` result is fetched but **never used in rendering** — the displayed football field data is always the hardcoded `MOCK_FOOTBALL` array.

**Fix required:** Fix `ANALYTICS.footballField` path. Wire `apiFootball` data into the `FootballField` component render.

---

### Feature 8: Comparable Company Analysis (Comps)

**Files:** `src/api/routers/analytics.py:1112,1148`, `src/engines/e2_comps.py`

**Backend:** Complete. `GET /comps/{security_id}` and `GET /comps/{security_id}/summary` both implemented.

**Frontend:** No hook, no display. No `ANALYTICS.comps` constant. Comps data is never shown.

**Fix required:** Add `ANALYTICS.comps` constant and `useComps` hook. Add comps display section to ValuationDashboard or a dedicated page.

---

### Feature 9: Peer Group

**Files:** `src/api/routers/analytics.py:751`, `frontend/src/hooks/useAnalytics.ts:98`

**Backend:** Complete. `GET /peers/{security_id}` returns the peer group for a security.

**Frontend:** Broken.
- `usePeerGroup(secId)` calls `/v2/analytics/securities/{id}/peer-group` → 404 (backend: `/v2/analytics/peers/{id}`)

**Fix required:** Fix `ANALYTICS.peerGroup` path.

---

### Feature 10: Peer Comparison (Ratios vs Peers)

**Files:** `src/api/routers/analytics.py:153`, `frontend/src/pages/company/ValuationDashboard.tsx:151,209`

**Backend:** Complete. `GET /ratios/{security_id}/vs-peers` returns peer ratio comparison.

**Frontend:** Broken at two levels.
1. `usePeerComparison(secId)` calls `/v2/analytics/securities/{id}/peer-comparison` → 404 (backend: `/v2/analytics/ratios/{id}/vs-peers`)
2. `ValuationDashboard.tsx:209` `PeerScatter` uses `activePeers = (apiPeers as any[]) ?? peerScatterData` — falls back to 5 hardcoded mock peers.

**Fix required:** Fix `ANALYTICS.peerComparison` path. Verify that `peerScatterData` format matches what the API returns.

---

### Feature 11: Peer Ranking

**Files:** `src/api/routers/screening.py:195`, `frontend/src/hooks/useAnalytics.ts:172`

**Backend:** Ranking exists only as POST `/rank` (in screening router).

**Frontend:** `usePeerRanking(secId)` calls GET `/v2/analytics/securities/{id}/peer-ranking` → 404. There is no backend GET endpoint for peer ranking by security ID.

**Fix required:** Either add a GET endpoint to analytics router, or replace `usePeerRanking` with a mutation that POSTs to `/v2/analytics/rank`.

---

### Feature 12: Quality Scores (Piotroski / Altman / Beneish)

**Files:** `src/api/routers/analytics.py:891,925,947,969,991`, `frontend/src/hooks/useAnalytics.ts:34`

**Backend:** Complete. Five endpoints: `GET /scores/{id}` (all three), plus individual `/scores/{id}/piotroski`, `/altman`, `/beneish`, and `/scores/{id}/history`.

**Frontend:** Broken.
- `useAllScores(secId)` calls `/v2/analytics/securities/{id}/scores/all` → 404 (backend: `/v2/analytics/scores/{id}`)
- No individual hooks for Piotroski, Altman, or Beneish scores
- No frontend page rendering score breakdowns with individual factor details

**Fix required:** Fix `ANALYTICS.allScores` path. Add `ANALYTICS.piotroski`, `ANALYTICS.altman`, `ANALYTICS.beneish` constants and hooks.

---

### Feature 13: Composite Scores (Earnings Quality / Financial Strength / Dividend Safety / Value Trap)

**Files:** `src/api/routers/analytics.py:1228,1272,1297,1322,1347`, `frontend/src/hooks/useAnalytics.ts:25`

**Backend:** Complete. `GET /scores/{id}/composites` plus four individual composite endpoints.

**Frontend:** Broken.
- `useCompositeScores(secId)` calls `/v2/analytics/securities/{id}/composite-scores` → 404 (backend: `/v2/analytics/scores/{id}/composites`)
- No individual composite score hooks

**Fix required:** Fix `ANALYTICS.compositeScores` path. Add individual composite hooks if needed for detail views.

---

### Feature 14: Individual Sub-Scores (Quality / Value / Growth / Momentum / Volatility)

**Files:** `frontend/src/api/endpoints.ts:86–90`, `frontend/src/hooks/useAnalytics.ts:20–47`

**Backend:** None of these five endpoints exist. The backend has Piotroski/Altman/Beneish quality scores and a `/scores/{id}/composites` endpoint, but no individual quality/value/growth/momentum/volatility sub-score endpoints.

**Frontend:** Five hooks (`useQualityScore`, `useValueScore`, `useGrowthScore`, `useMomentumScore`, `useVolatilityScore`) call five non-existent endpoints. Always 404.

**Fix required:** Either add backend endpoints for each sub-score dimension, or map these hooks to existing composite score endpoints and extract the relevant sub-score from the response.

---

### Feature 15: Sector Relative Analysis

**Files:** `frontend/src/api/endpoints.ts:91`, `frontend/src/hooks/useAnalytics.ts:116`

**Backend:** No endpoint exists.

**Frontend:** `useSectorRelative(secId)` calls `/v2/analytics/securities/{id}/sector-relative` → 404.

**Fix required:** Add backend endpoint, or remove unused hook.

---

### Feature 16: Fair Value

**Files:** `frontend/src/api/endpoints.ts:93`, `frontend/src/hooks/useAnalytics.ts:88`

**Backend:** No endpoint exists.

**Frontend:** `useFairValue(secId)` calls `/v2/analytics/securities/{id}/fair-value` → 404.

**Fix required:** Add backend endpoint (could aggregate from DCF, comps, multiples), or remove.

---

### Feature 17: Industry KPIs

**Files:** `src/api/routers/analytics.py:675,718`, `src/engines/e1_industry_kpis.py`

**Backend:** Complete. `GET /kpis/{security_id}` and `GET /kpis/{security_id}/history`.

**Frontend:** No `ANALYTICS.kpis` constant. No hook. KPIs are never fetched or displayed in analytics context (note: `FUNDAMENTALS.kpis` in Pillar 1 is a different path).

**Fix required:** Add `ANALYTICS.industryKpis` constant and `useIndustryKpis` hook. Display in a dashboard section.

---

### Feature 18: Trend Analysis

**Files:** `src/api/routers/analytics.py:591`, `src/engines/e1_trends.py`

**Backend:** Complete. `GET /trends/{security_id}`.

**Frontend:** No `ANALYTICS.trends` constant. Never fetched or displayed.

**Fix required:** Add constant and hook. Add trend display to a dashboard page.

---

### Feature 19: Technical Signals

**Files:** `frontend/src/api/endpoints.ts:94`, `frontend/src/hooks/useAnalytics.ts:148`

**Backend:** No `/technical-signals` endpoint exists in analytics router. The Pillar 1 securities router has `GET /v1/securities/{id}/technicals` (different endpoint for raw technicals data).

**Frontend:** `useTechnicalSignals(secId)` calls `/v2/analytics/securities/{id}/technical-signals` → 404.

- `QuantDashboard.tsx:107` calls `useTechnicalSignals(undefined)` — the hook is disabled because `secId` is falsy, so it never even makes a request.
- `CompanyOverview.tsx:286` calls `useTechnicalSignals(resolvedId)` — always 404.

**Fix required:** Either build a technical signals analytics endpoint (momentum indicators, RSI, MACD), or wire these pages to `SECURITIES.technicals` (the Pillar 1 raw technicals).

---

### Feature 20: Seasonality Analysis

**Files:** `frontend/src/api/endpoints.ts:95`, `frontend/src/hooks/useAnalytics.ts:154`

**Backend:** No endpoint exists.

**Frontend:** `useSeasonality(secId)` calls non-existent endpoint. Hook exists but is never called from any page.

**Fix required:** Add backend endpoint or remove.

---

### Feature 21: Factor Exposure

**Files:** `frontend/src/api/endpoints.ts:97`, `frontend/src/hooks/useAnalytics.ts:160`

**Backend:** No endpoint exists.

**Frontend:** `useFactorExposure(secId)` calls `/v2/analytics/securities/{id}/factor-exposure` → 404.

- `QuantDashboard.tsx:106` calls `useFactorExposure(undefined)` — disabled because `secId` is undefined.
- `RiskDashboard.tsx:67` calls `useFactorExposure(undefined)` — same, always disabled.

Both dashboards always render hardcoded `factorExposure` mock data.

**Fix required:** Add backend factor exposure engine and endpoint, or map this to a portfolio-level factor endpoint.

---

### Feature 22: Correlation

**Files:** `frontend/src/api/endpoints.ts:96`, `frontend/src/hooks/useAnalytics.ts:195`, `frontend/src/api/hooks/useAnalytics.ts:255`

**Backend:** No GET or POST correlation endpoint exists at `/v2/analytics/correlation`.

**Frontend (two-layer conflict):**
- Component-layer `hooks/useAnalytics.ts:195` exports `useCorrelation()` as a GET query (`useApiQuery`) calling `ANALYTICS.correlation` → 404
- API-layer `api/hooks/useAnalytics.ts:255` exports `useCorrelation()` as a POST mutation (`useMutation`) — inconsistent implementation
- `QuantDashboard.tsx:105` and `RiskDashboard.tsx:66` call `useCorrelation() as { data: any }` expecting query data, but the component-layer version has no real data (404)

Both pages fall back entirely to mock data for every panel they display.

**Fix required:** Add backend correlation endpoint. Decide whether correlation is a GET (cached, no params) or POST (parameterized). Reconcile the two-layer hook conflict.

---

### Feature 23: Screening

**Files:** `src/api/routers/screening.py`, `frontend/src/pages/screener/ScreenerDashboard.tsx`, `frontend/src/hooks/useAnalytics.ts:170`

**Backend:** Complete. Fully functional screening engine with filter-group logic.

**Frontend:** Multiple breakages:

**23a. Filter payload format mismatch (breaks all screens)**
Backend `e4_screening.py` `ScreenFilter` expects: `{ field, source, op, value, value2 }`
`ScreenerDashboard.tsx:90` sends: `{ filters: [{ metric, operator, value, valueTo }] }`
The field names are different (`metric` vs `field`, `operator` vs `op`, `valueTo` vs `value2`), and `source` is always missing.

**23b. Screen management endpoint path mismatches**
- `ANALYTICS.screenPrebuilt` → `/screen/prebuilt` | backend: `GET /screens/library`
- `ANALYTICS.screenSave` → `/screen/save` | backend: `POST /screens/save`
- `ANALYTICS.screenHistory` → `/screen/history` | backend: `GET /screens/saved`

**23c. Dashboard bypasses the proper mutation hook**
`ScreenerDashboard.tsx:86–95` uses a manual `api.post(ANALYTICS.screen, payload)` instead of `useRunScreen()` from `useScreening.ts`.

**23d. Hardcoded filter fields**
`EQUITY_METRICS` (6 hardcoded metrics) never replaced by `useScreenFields()` which would return the dynamic list of available fields from the backend.

**23e. `MOCK_STOCKS` always shown when backend fails**
`totalCount = backendResults ? backendResults.length : MOCK_STOCKS.length` — when the backend 404s, the preview count shows "20 of 20" which is the mock count, not the real universe size.

**Fix required:** Fix all screen path constants. Rewrite filter serialisation to use `field`/`op`/`source`/`value2`. Use `useRunScreen()` mutation. Load fields dynamically from `useScreenFields()`.

---

### Feature 24: Quant Dashboard

**Files:** `frontend/src/pages/quant/QuantDashboard.tsx`

**Status: 100% mock data — no API integration working.**

Issues:
1. `useCorrelation()` (line 105): calls non-existent endpoint, always `undefined` — `activeFactorPerf` always falls back to `factorPerformance` mock
2. `useFactorExposure(undefined)` (line 106): hook is disabled (secId is falsy) — always `undefined`
3. `useTechnicalSignals(undefined)` (line 107): hook is disabled — `activeMomentum` always falls back to `momentumSignals` mock
4. Implied Volatility Surface: entire panel is computed from a hardcoded formula, no backend endpoint, no hook called

**Fix required:** Add proper quant-domain endpoints. Connect `useCorrelation` to a parameterized endpoint. Pass a real universe/security list to `useFactorExposure` and `useTechnicalSignals`. Build a volatility surface endpoint or remove the panel.

---

### Feature 25: Risk Dashboard

**Files:** `frontend/src/pages/risk/RiskDashboard.tsx`, `frontend/src/api/hooks/useRiskAnalytics.ts`

**Status: 100% mock data — wrong hooks used, no API integration working.**

`RiskDashboard.tsx` is supposed to display portfolio-level risk metrics (VaR, stress tests, sector concentration, factor exposure). However:

1. It imports `useCorrelation` and `useFactorExposure` — security-level analytics hooks — instead of the portfolio risk hooks
2. `useRiskAnalytics.ts` correctly wraps `PORTFOLIO_RISK` endpoints (`useVaR`, `useStressHistorical`, `useRiskFactors`, `useConcentration`, etc.) — none of these are used in `RiskDashboard`
3. The page has no `portfolioId` parameter — it passes `undefined` to `useFactorExposure`, which disables the query
4. All KPI tiles, stress test table, VaR decomposition chart, and sector concentration chart are always hardcoded mock data

**Fix required:** Refactor `RiskDashboard` to accept a portfolio ID (from route params or `useSecurityStore`). Use `useVaR`, `useStressHistorical`, `useConcentration`, `useRiskFactors` (from `useRiskAnalytics.ts`) instead of `useCorrelation`/`useFactorExposure`.

---

### Feature 26: Rank Screen (Multi-Factor Ranking)

**Files:** `src/api/routers/screening.py:195`

**Backend:** Complete. POST `/rank` accepts a list of tickers and ranking factors with weights.

**Frontend:** No hook or UI for this feature. The `QuantDashboard` "Factor Performance" section would logically use this, but does not.

**Fix required:** Add `ANALYTICS.rank` constant and `useRankScreen` mutation hook. Add a ranking UI or integrate into `QuantDashboard`.

---

### Feature 27: Universe Endpoints

**Files:** `src/api/routers/screening.py:317,334,351,368`

**Backend:** Implemented. `GET /universe/us-equities`, `GET /universe/sp500`, `GET /universe/russell1000`, `POST /universe/custom`. However — S&P 500 and Russell 1000 endpoints query `SavedScreen` table for `universe_type = 'sp500'` / `'russell1000'`, which returns empty unless the database has been seeded with these records.

**Frontend:** No hooks. No UI for universe selection in screener (user cannot scope a screen to "S&P 500 only").

**Fix required:** Seed universe data. Add `ANALYTICS.universe*` constants. Add universe selector dropdown to `ScreenerDashboard`.

---

### Feature 28: Analytics Batch Computation Pipeline

**Files:** `scripts/run_analytics_batch.py`, `src/engines/`

**Backend:** All analytics data is **pre-computed by a batch script** and stored in the `AnalyticsResult` table. The batch must be run before any analytics endpoint can return real data. If the batch has never run, every analytics endpoint returns empty results or 404.

**Issues:**
- No automatic batch execution on app startup
- No mechanism in the API to trigger a batch for a specific security on-demand
- No frontend indicator showing which securities have analytics data computed
- DCF is the only endpoint with on-demand computation (POST `/dcf/{id}`)

**Fix required:** Add a startup trigger (e.g., a FastAPI lifespan event or Docker entrypoint) that runs the analytics batch for any securities that lack recent data in `AnalyticsResult`. Alternatively, wire each engine to compute on-demand if no pre-computed result exists.

---

### Feature 29: Score History

**Files:** `src/api/routers/analytics.py:991`

**Backend:** Complete. `GET /scores/{security_id}/history`.

**Frontend:** No hook or display. Score trends are never shown.

**Fix required:** Add `ANALYTICS.scoreHistory` constant and hook. Add a score history chart to a dashboard page.

---

### Feature 30: Audit / Lineage

**Files:** `src/api/routers/analytics.py:540,562`

**Backend:** Complete. `GET /audit/{security_id}/{metric_name}` and `/audit/{security_id}/{metric_name}/history`.

**Frontend:** No hook or UI. Metric lineage is never surfaced.

**Fix required:** This is a power-user feature; acceptable to defer, but a hook should be added for debuggability.

---

## Part 3: Summary by Severity

### Critical — Breaks entire feature (user sees mock data or errors)

1. **All ANALYTICS path constants are wrong** — every hook returns 404; all dashboards fall back to mocks
2. **Screen filter payload format mismatch** — screener silently ignores filters, shows wrong results
3. **DCF recalculate button posts to wrong URL** — fails silently, user gets no feedback
4. **RiskDashboard uses wrong hooks** — entire dashboard is permanently disconnected from the portfolio risk API

### High — Feature exists but is never rendered

5. **ValuationDashboard: football field always mock** — `apiFootball` fetched but never wired to display
6. **ValuationDashboard: sensitivity matrix always mock** — `apiSensitivity` fetched but never wired
7. **ValuationDashboard: peer table always mock** — 5 hardcoded peers, API data ignored
8. **ValuationDashboard: MultiplesOverTime panel always mock** — separate static array, not linked to `useMultiplesHistory`
9. **QuantDashboard: all three panels always mock** — `useCorrelation(undefined)`, `useFactorExposure(undefined)`, `useTechnicalSignals(undefined)` all disabled or calling non-existent endpoints
10. **Analytics batch not triggered on startup** — endpoints return empty until batch is run manually

### Medium — Backend done, no frontend hooks or display at all

11. **WACC** — 3 backend endpoints, no frontend hook or display
12. **TTM Metrics** — backend done, no frontend hook
13. **Comps / Comparable Analysis** — 2 backend endpoints, no frontend hook, not shown
14. **Industry KPIs** — 2 backend endpoints, no frontend hook
15. **Trend Analysis** — backend done, no frontend hook
16. **Score History** — backend done, no frontend hook
17. **Rank Screen** — backend done, no frontend hook or UI
18. **Universe Endpoints** — backend done (but unseeded), no frontend hooks, no universe selector in screener
19. **Screener: EQUITY_METRICS hardcoded** — `useScreenFields()` hook exists but screener uses static list

### Low — Feature partially scaffolded but no backend yet

20. **5 individual sub-scores** (Quality/Value/Growth/Momentum/Volatility) — hooks exist, no backend endpoints
21. **Sector Relative Analysis** — hook exists, no backend endpoint
22. **Fair Value** — hook exists, no backend endpoint
23. **Seasonality** — hook exists, no backend endpoint
24. **Factor Exposure** — hook exists (security-level), no backend endpoint
25. **Correlation** — hook exists (two conflicting implementations: GET vs POST), no backend endpoint
26. **Technical Signals** — hook exists (analytics-level), but calls wrong API tier; Pillar 1 `/v1/securities/{id}/technicals` exists
27. **Peer Ranking** — hook exists (GET), backend only has POST `/rank` — method mismatch

---

## Part 4: Remediation Plan

### Phase 1: Fix endpoint constants (unblocks all features at once)

Update `frontend/src/api/endpoints.ts` ANALYTICS section to match actual backend paths:

```typescript
// Current → Fixed
ratios: (id) => `/v2/analytics/securities/${id}/ratios`
  → `/v2/analytics/ratios/${id}`

allScores: (id) => `/v2/analytics/securities/${id}/scores/all`
  → `/v2/analytics/scores/${id}`

compositeScores: (id) => `/v2/analytics/securities/${id}/composite-scores`
  → `/v2/analytics/scores/${id}/composites`

dupont: (id) => `/v2/analytics/securities/${id}/dupont`
  → `/v2/analytics/dupont/${id}`

dupontHistory: (id) => `/v2/analytics/securities/${id}/dupont/history`
  → `/v2/analytics/dupont/${id}/history`

multiplesHistory: (id) => `/v2/analytics/securities/${id}/multiples/history`
  → `/v2/analytics/multiples/${id}/history`

historicalMultiples: (id) => `/v2/analytics/securities/${id}/historical-multiples`
  → `/v2/analytics/multiples/${id}`

peerGroup: (id) => `/v2/analytics/securities/${id}/peer-group`
  → `/v2/analytics/peers/${id}`

peerComparison: (id) => `/v2/analytics/securities/${id}/peer-comparison`
  → `/v2/analytics/ratios/${id}/vs-peers`

dcf: (id) => `/v2/analytics/securities/${id}/dcf`          // GET
  → `/v2/analytics/dcf/${id}/default`

footballField: (id) => `/v2/analytics/securities/${id}/football-field`
  → `/v2/analytics/valuation/${id}/summary`

screenPrebuilt: `/v2/analytics/screen/prebuilt`
  → `/v2/analytics/screens/library`

screenSave: `/v2/analytics/screen/save`
  → `/v2/analytics/screens/save`

screenHistory: `/v2/analytics/screen/history`
  → `/v2/analytics/screens/saved`
```

### Phase 2: Wire API data into ValuationDashboard display

- Replace `multiplesOverTimeData` (hardcoded) with `activeMultiplesHistory`
- Wire `apiFootball` data into the football field component
- Wire `apiSensitivity` data into `SensitivityMatrix`
- Wire `apiPeers` data into `PeerScatter` (peer comparison table)
- Fix DCF recalculate POST URL
- Replace hardcoded `company` header with `useSecurityStore` data

### Phase 3: Fix Screener filter format

Update `ScreenerDashboard.tsx handleRunScreen` to map filter objects:
```typescript
const payload = {
  logic: 'AND',
  filters: filters.map(f => ({
    field: f.metric,
    source: 'ANALYTICS_RESULT',
    op: f.operator.toUpperCase(),   // '>' → 'GT', '<' → 'LT', '=' → 'EQ', 'between' → 'BETWEEN'
    value: f.value,
    value2: f.valueTo,
  }))
};
```

Also: load `EQUITY_METRICS` dynamically from `useScreenFields()`.

### Phase 4: Fix RiskDashboard

Replace `useCorrelation` + `useFactorExposure(undefined)` with:
- `useVaR(portfolioId)`, `useConcentration(portfolioId)`, `useStressHistorical(portfolioId)`, `useRiskFactors(portfolioId)` from `useRiskAnalytics.ts`
- Source `portfolioId` from route params or a portfolio selector

### Phase 5: Fix QuantDashboard

- Replace `useCorrelation()` with a real endpoint once added, or remove
- Add security/universe context for `useFactorExposure` and `useTechnicalSignals`
- Replace static volatility surface with a real options data endpoint or label it clearly as illustrative

### Phase 6: Add missing backend endpoints

Priority order:
1. GET `/v2/analytics/scores/{id}/quality-score` (composite quality sub-score) — maps to Piotroski
2. GET `/v2/analytics/scores/{id}/value-score` — maps to multiples / valuation engine
3. GET `/v2/analytics/scores/{id}/growth-score` — maps to trends engine
4. GET `/v2/analytics/scores/{id}/momentum-score` — maps to technical studies
5. GET `/v2/analytics/scores/{id}/volatility-score` — maps to technical studies
6. POST `/v2/analytics/correlation` — correlation matrix for a list of securities
7. GET `/v2/analytics/factor-exposure/{id}` — Fama-French factor loadings
8. GET `/v2/analytics/seasonality/{id}` — monthly return seasonality
9. GET `/v2/analytics/technical-signals/{id}` — RSI, MACD, Bollinger, momentum score
10. GET `/v2/analytics/dcf/{id}/sensitivity` — standalone sensitivity endpoint (or return it in GET default response)

### Phase 7: Add missing frontend hooks and constants

Add `ANALYTICS` constants for:
- `wacc`, `waccHistory`, `waccComponents`
- `ttm`
- `comps`
- `industryKpis`
- `trends`
- `piotroski`, `altman`, `beneish`
- `scoreHistory`
- `rank` (POST mutation)
- `universe` (sp500, russell1000)
- `dcfPost` (POST mutation for custom assumptions)

### Phase 8: Batch computation auto-trigger

In `src/api/app.py` lifespan or a startup event:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run analytics batch for any securities missing recent data
    await run_analytics_batch_incremental()
    yield
```

Or add a FastAPI background task endpoint: `POST /v2/analytics/batch/run` that triggers batch for specified securities.

---

*Report generated by static code analysis. No tests were run.*
