# Data Wiring Audit — Bloomberg Data Fabric

**Date:** 2026-07-05
**Method:** Six parallel deep-reads of the full codebase (Pillar 1–4 backend routers/engines, the entire frontend page/hook surface, and the ingestion layer), each independently tracing every feature from UI → API → engine → DB table → ingestion source. Every finding below cites a file (and usually a line) so it can be re-verified directly.

**Purpose:** answer one question per feature — *if a user opens this page or calls this endpoint today, having followed `CONNECTING_TO_REAL_DATA.md` exactly, do they see real computed data, or something fabricated/stubbed/empty?*

---

## 1. Executive Summary

The platform's foundational data (entities, securities, EOD prices, macro indicators, core fundamentals, ownership, congressional trades) is **genuinely real and well-wired**. Layered on top, roughly half of the analytics/research surface is real computation against that data. The other half falls into one of four failure modes, in order of how often they occur:

1. **Engine built and unit-tested, never called by any router/batch/scheduler job** ("orphaned engine") — by far the most common pattern. The code is often correct; it's just unreachable.
2. **Ingestion connector fully implemented, never actually invoked with real arguments** — e.g. 7 of the 13 documented Pillar-1 ingestion scripts silently no-op because the driver script never supplies the CIK/ticker list the connector needs.
3. **Hardcoded placeholder text or numbers presented as if computed** — the most user-visible failure mode, concentrated in the frontend (silent `?? MOCK_DATA` fallbacks) and in three specific Pillar 3 "AI" endpoints that store literal strings like `"AI-generated answer placeholder."`
4. **Frontend calling a URL that doesn't exist on the backend at all** — a distinct, previously undocumented bug class found across ~15 pages, independent of any mock-data fallback.

None of this is exotic — every gap has a concrete, one-line-citable cause. Section 3 lists the ones worth fixing first.

---

## 2. How to read this document

Every feature is tagged with one status:

| Status | Meaning |
|---|---|
| ✅ **REAL** | Full path verified: real DB query ← real ingested/computed data ← real external source or real user input. |
| 🟡 **PARTIAL** | Some of the feature is real; part of it is stubbed, defaulted, or silently wrong. |
| 🔴 **GAP** | Router/query logic is correct, but the table it reads has no writer anywhere — endpoint will 404/empty forever regardless of setup. |
| ⚫ **STUB** | The endpoint doesn't compute anything — it returns a hardcoded string/number/skeleton by design. |

---

## 3. Fix-First List (highest impact, most tractable)

These aren't necessarily the "worst" bugs, but they're the ones where a small, targeted fix unblocks a large amount of downstream functionality.

1. **`scripts/ingest_edgar_xbrl.py`, `ingest_corporate_actions.py`, `ingest_ownership.py`, `ingest_esg.py`, `ingest_relationships.py`, `ingest_short_interest.py` never pass a CIK/ticker list to their connectors.** Each connector (`EdgarXBRLConnector`, `Edgar8KConnector`, `Edgar13FConnector`, `EdgarForm4Connector`, `EdgarESGConnector`, `Edgar10KNLPConnector`, `FinraShortInterestConnector`) defaults its CIK-list argument to `None → []` and its `extract()` immediately returns `[]` with a log warning when the list is empty. Every driver script instantiates the connector with **zero arguments** and never queries the DB for entities first. Running the pipeline exactly as `CONNECTING_TO_REAL_DATA.md` §6 documents (steps 8–13) inserts **zero rows** for fundamentals, corporate actions, 13F/Form4 ownership, ESG, and business relationships. This is the single highest-leverage fix in the whole audit — the transform/load logic is already correct, it just needs a `SELECT cik FROM entities` before constructing the connector.
2. **`src/ai/llm_client.py:24-40` — `LLMClient.generate()` unconditionally returns `None`**, even when `ANTHROPIC_API_KEY` is set and `self._enabled` is `True`. Comment: "In production, this would call the Anthropic API... actual integration is deferred." Affects `sentiment.py`, `company_intelligence.py`, `company_primer.py` (all `/v1`). Separately, a real, working Anthropic SDK client (`src/services/ai/claude_client.py`, model `claude-sonnet-5`) and Gemini embedding client (`src/services/ai/embedding_client.py`) already exist and are fully unused — wiring these into `llm_client.py` (or replacing it) is a bounded, well-scoped fix.
3. **`Position.market_value`/`unrealized_pnl`/`weight` are never computed anywhere** (`src/api/routers/portfolios.py`). A real engine to do this (`src/engines/nav_engine.py::compute_position_market_value`) exists and is unit-tested but has zero non-test callers. Consequence: portfolio NAV is cash-balance-only forever, and this starves portfolio risk/compliance checks downstream (§7).
4. **`research_qa.py:65`** stores the literal string `"AI-generated answer placeholder."` as the answer to every question asked. **`research_briefings.py:225-243`** stores `"On-demand briefing generated."` for every morning briefing. These are the two most literal "fake AI" instances found — worth fixing or at minimum clearly labeling in the UI before any demo.
5. **Frontend landing page (`MorningBrief.tsx`, route `/`) is 100% fabricated data with zero indication** — all 5 of its queries hit backend routes that don't exist (`/v1/market/indices`, `/market/movers`, `/alerts/recent`, `/econ/calendar`, `/market/sectors`). This is the first thing every user sees.
6. **`AlertsView.tsx`** does `apiAlerts?.stats` / `?.alerts` on what the backend actually returns as a bare array — property access on an array is always `undefined`, so the page falls back to 10 fabricated alerts **even when the live API call succeeds**. Distinct from (and worse than) a normal empty-state fallback.
7. **`NewsView.tsx`** reads field names (`headline`, `time`, `sentiment`, `category`) that don't match the backend's actual schema (`title`, `sentiment_score`, ...). `n.sentiment.toFixed(2)` will throw a runtime `TypeError` and crash the page the instant real news rows exist — currently masked only because `news_articles` is empty.
8. **Two colliding-table-name bugs already fixed today** (see git history: `company_primers`→`research_primers`, and the `stress_test_results`→`portfolio_stress_test_results` rename) — mentioned here only so nobody re-introduces them; not an open item.

---

## 4. Pillar 1 — Data Foundation

### 4.1 Reference / Entity / Security Master

| Feature | Endpoint(s) | Status | Notes |
|---|---|---|---|
| Reference data (countries/currencies/exchanges/GICS/SIC/NAICS) | `/v1/reference/*` | ✅ REAL | Seeded from `data/*.json` via `scripts/seed_reference.py` — static but genuinely loaded. |
| Trading calendars | `/v1/reference/calendars/*` | 🔴 GAP | No loader exists for `trading_calendars`/`trading_days`; no JSON source either. |
| Entity search/detail/CRUD | `/v1/entities/*` | 🟡 PARTIAL | Real EDGAR + GLEIF-backed data. `_compute_relevance()` is a hardcoded 3-tier constant, not real relevance scoring. |
| Entity hierarchy | `/entities/{id}/hierarchy` | 🔴 GAP | `ultimate_parent_id`/`immediate_parent_id` never set by any ingestion script. |
| Entity history | `/entities/{id}/history` | 🔴 GAP | `record_entity_history()` exists, zero callers. |
| Entity relationships | `/entities/{id}/relationships` | 🔴 GAP | Reads `EntityRelationship`, which nothing writes — the *real* business-relationship data lives in a differently-named table (`BusinessRelationship`, read only by `relationships.py`). Naming collision hides the working feature. |
| Entity resolution queue | `/entities/resolve`, `/resolution/queue` | 🔴 GAP (dead end) | `add_to_queue()` exists but is never called from the resolver, despite a comment in `gleif_entities.py` claiming it is. Queue always empty. |
| Security find/search/detail/prices | `/v1/securities/*`, `/v1/securities/{id}/prices*` | ✅ REAL | OpenFIGI (securities/identifiers) + Polygon (EOD prices) — genuinely end-to-end. Hardcoded fake relevance score, same pattern as entities. |
| Security expand=equity_details/fixed_income_details/credit_ratings/call_put_schedule | `/v1/securities/{id}?expand=...` | 🔴 GAP (3 of 4) | `EquityDetails` created but analytical fields left null (explicit placeholder comment); `FixedIncomeDetails`, security-level `CreditRating`, `CallPutSchedule` have zero writers. |
| Executives | `/entities/{id}/executives`, `/executives/search` | 🔴 GAP | No connector exists at all — not even a stub. |

### 4.2 Fundamentals / Ownership / ESG / Corporate Actions

| Feature | Endpoint(s) | Status | Notes |
|---|---|---|---|
| Filings, income/balance/cash-flow statements | `/v1/filings`, `/fundamentals*` | 🔴 GAP (via Fix #1) | Router logic is clean; connector never receives a CIK list (see §3.1). |
| Segments/geographic breakdown | `/entities/{id}/segments` | 🔴 GAP | No writer for `SegmentData`. |
| Institutional/insider holdings, short interest | `/v1/ownership/*`, `/short-interest` | 🔴 GAP (via Fix #1) | Same CIK-list bug as fundamentals. |
| Ownership summary rollup | `/ownership/summary` | 🔴 GAP | No engine/job ever produces `OwnershipSummary`. |
| ESG scores/metrics | `/entities/{id}/esg*` | 🟡 PARTIAL (via Fix #1, then design-limited) | Connector is governance-only by design even once wired — `esg_score`, `environmental_score`, `social_score` always null. |
| ESG controversies | `/entities/{id}/esg/controversies` | 🔴 GAP | No writer. |
| ESG temperature score | `/entities/{id}/esg-temperature` | 🔴 GAP | Real deterministic Paris-alignment math exists (`esg_temperature.py`) but nothing calls it and persists a row. |
| Corporate actions | `/securities/{id}/corporate-actions` | 🔴 GAP (structural) | Ingested rows exist but never get `security_id` set (only `entity_id`) — endpoint filters on the one column that's always null. |
| Dividends/splits/M&A actions | `/dividends`, `/splits` | 🔴 GAP | No connector produces these subtypes; only the generic `CorporateAction` row. |
| Corporate actions calendar | `/corporate-actions/calendar` | 🔴 GAP (structural) | `ex_date`/`record_date`/`payment_date` never set — any date filter excludes 100% of rows. |
| Business relationships (customers/suppliers/competitors) | `/business-relationships*` | ✅ REAL | Genuinely wired 10-K NLP pipeline. |
| Central bank policy/meetings | `/macro/central-banks*` | 🔴 GAP | No writer anywhere. |
| Macro indicators | `/macro/indicators*` | ✅ REAL | FRED, 15 series, genuinely end-to-end. |

### 4.3 Capital Structure / Credit / Deals / Fixed Income

Every item below shares one root cause: **a connector class exists with correct transform/load logic, but its `extract()` is an explicit stub returning `[]`, and it's never invoked by any script** — or no connector was ever written at all.

| Feature | Endpoint(s) | Status | Root cause |
|---|---|---|---|
| Capital structure / debt tranches | `/capital-structure*` | 🔴 GAP | `edgar_capital_structure.py` stub `extract()`, uncalled. |
| Debt maturity profile | `/debt-maturity*` | 🔴 GAP | No connector at all. |
| Credit rating events | `/entities/{id}/credit-ratings*` | 🔴 GAP | `edgar_credit_ratings.py` stub `extract()`, uncalled. |
| M&A deals | `/ma-deals*` | 🔴 GAP | No connector at all. |
| IPO events | `/ipo*` | 🔴 GAP | No connector at all. |
| Earnings surprises / guidance | `/earnings/*` | 🔴 GAP | No connector; engine is pure-compute on caller-supplied values only. |
| Fund holdings | `/fund-holdings*` | 🔴 GAP | No N-PORT connector was ever built. |
| Technical indicators (SMA/EMA/RSI/MACD/etc.) | `/securities/{id}/technicals*` | 🔴 GAP | Real math engine exists over real EOD prices, but nothing batch-computes and persists `TechnicalStudyValue`. |
| Treasury yield curve | `/macro/yield-curve*` | 🔴 GAP | `treasury_yield_curve.py` stub `extract()`; the doc's own manual command for this doesn't actually populate data. |
| Money market rates | `/macro/money-markets` | 🔴 GAP | `fred_money_market.py` stub `extract()`, uncalled. |
| FOMC meetings | `/central-bank/fed*` | 🔴 GAP | No connector at all. |
| Treasury securities (on-the-run, auctions) | `/fi/treasuries*` | 🔴 GAP | `treasury_securities.py` — every method is an explicit stub. |
| Corporate bonds / bond prices / TRACE | `/fi/bonds*`, `/bond-prices*` | 🔴 GAP | `finra_trace.py` exists in name only — never references the actual bond/price models. No connector populates `CorporateBond` at all. |
| Credit spread indices | `/fi/spreads*` | 🔴 GAP | `fred_credit_spreads.py` — no `load()` method exists at all, weakest connector found. |
| Bond issuances / agency bonds | `/fi/issuances*`, `/fi/agency-bonds*` | 🔴 GAP | No connector exists for either. |

**Genuinely real Pillar-1 exception in this cluster:** Treasury bond analytics computation itself (`src/engines/treasury_analytics.py`) is correct, unit-consistent math — it's just starved of input data.

---

## 5. Pillar 2 — Analytics Engines

### 5.1 Batch pipeline scope (important context for everything below)

`scripts/run_analytics_batch.py --engine all` does **not** run everything `CONNECTING_TO_REAL_DATA.md` §7 claims. The real `--engine` choices are `e1, e1_trends, e1_kpis, e2_multiples, e2_wacc, e3, all` — **`e2_dcf`, `e2_comps`, `e2_football_field`, `e5_risk`, `e7_quant` are never wired into the batch runner at all**, under any engine value. They only ever run live, on-demand, per API request (which mostly works — see below) — they can never be pre-computed or scheduled. Separately, `src/scheduler/batch_config.py` schedules a job for `--engine e6` (institutional flows), which **isn't a valid argparse choice** — that scheduled job fails every single time it fires.

### 5.2 Feature status

| Feature | Endpoint(s) | Status | Notes |
|---|---|---|---|
| Ratios / TTM / Trends / Industry KPIs | `/v2/analytics/*` | ✅ REAL | Batch-computed from real fundamentals+prices. Most of a prior 98-bug audit is now genuinely fixed. |
| DuPont decomposition | `/dupont/{id}*` | 🔴 GAP | Engine computes fine into generic `AnalyticsResult`, but nothing ever constructs the dedicated `DuPontDecomposition` row the endpoint actually queries — **permanent 404**. |
| Multiples / WACC | `/multiples/{id}`, `/wacc/{id}` | ✅ REAL | Batch-computed, correctly fixed since prior audit. |
| DCF | `/dcf/{id}` (POST) | 🟡 PARTIAL | Computation and persistence are real. Custom user-supplied assumptions are silently dropped — the request schema's field names (`revenue_growth_rates`, etc.) don't match the engine's actual override keys, so a "customized" DCF silently runs with defaults. |
| Comps | `/comps/{id}` | 🟡 PARTIAL | Real, on-demand. P/B and dividend-yield multiples always `None` (denominator-name mismatch: looks up `ttm_bvps`/`ttm_dividends_per_share`, real names are `bvps`/`dps`). Percentile calc still includes the subject company in its own peer set (inflates rank toward median) via a second, unfixed copy of the percentile function. |
| Football Field valuation summary | `/valuation/{id}/summary` | 🟡 PARTIAL | Always recomputed live (never persisted — by design, not a bug). DCF-bar sensitivity extraction expects the wrong JSON shape from `DCFResult.sensitivity_grid`, so it silently falls back to a flat ±15% heuristic instead of real per-cell sensitivities. `consensus_view` in the response reads the wrong field and is always `"COMPLETE"`/`"INSUFFICIENT_DATA"`. |
| Piotroski / Altman / Beneish / Composite scores | `/v2/analytics/scores/*` | ✅ REAL | Batch-computed, correctly fixed. |
| Screening | `/v2/analytics/screen*` | ✅ REAL (backend) / 🟡 broken caller | Real SQL-compiled filters. Frontend `ScreenerDashboard.tsx` POSTs the wrong request shape (flat array instead of nested `{filters: {...}}`), 422s, falls back to a labeled "Demo mode" of mock stocks — the one page in the app that discloses this to the user. |
| Institutional flows | `/v2/analytics/flows/*` | 🟡 PARTIAL | Single-security lookup computes live and is real. All bulk/market/sector/alert endpoints depend on `InstitutionalFlowSignal`/`FlowAlert`, which can only be populated by the never-batchable `e6` engine (see §5.1) — permanently empty in any real deployment. |
| Market movers | `/v2/analytics/movers` | 🔴 GAP | Real engine, zero production callers. |
| Events calendar (engine version) | `/v2/analytics/events-calendar` (distinct from the working `calendar.py`/`economic_calendar.py`) | ⚫ STUB | Router's own code always returns `total_events=0` regardless of query — never queries the DB. A working parallel calendar exists elsewhere; this specific router shadows it uselessly. |
| Risk (VaR/vol/skew/CVaR/stress) | `/v2/analytics/risk/*` | ✅ REAL (mostly) | Computed live from real EOD prices. `factor_size` exposure and `/beta` endpoint depend on `AnalyticsResult` rows (`shares_outstanding`, `beta_market`) that nothing ever writes — always null. |
| Quant (regression/correlation/stationarity/cointegration) | `/v2/analytics/quant/*` | ✅ REAL (standalone) / 🔴 GAP (summary) | Standalone stat endpoints are real. `/summary/{id}` and `/beta/{id}` depend on `QuantEngine.compute()`, which is never called anywhere — always null. `run_regression` itself uses a plain time-index as "x" (documented self-regression stub, not a real independent variable). |
| Scenario / shock testing | `/v2/analytics/scenario/*` | ✅ REAL | Genuinely re-runs DCF projections live, independent of the batch gap. |
| Backtesting | `/v2/analytics/backtest` (POST) | ⚫ STUB | Creates a `PENDING` row; no worker anywhere ever advances it. `/results` 404s forever. |
| Technical backtest | `/technical-backtest*` | ✅ REAL | Real signal generation and performance metrics, but stateless (no persistence, caller supplies prices). |
| Default risk scoring | `/v2/analytics/default-risk/*` | 🔴 GAP | Real Merton DD engine, zero production callers. |
| Custom data expressions | `/v1/analytics/custom-fields*` | ✅ REAL (as a calculator) | Real expression engine; caller must supply every variable manually — no Pillar-1 auto-wiring. |
| Custom index | `/v1/custom-index*` | 🔴 GAP | Real weighting/performance engine, never called; no endpoint even exists to add constituents. |
| Portfolio upload (this router specifically) | `/v2/analytics/portfolio-upload` | ⚫ STUB | Explicitly admitted in its own docstring. A **separate, fully-working** upload flow exists in `portfolios.py` (`/upload/preview`, `/upload/commit`) — use that one. |

### 5.3 Fixed Income Analytics Cluster (E9–E15)

**Systemic gap:** no ingestion connector exists anywhere for bond master/pricing data. Every CUSIP-keyed endpoint below 404s on a freshly-set-up install, independent of the analytics logic quality.

| Router | Status | Notes |
|---|---|---|
| `fi_bond_analytics` | ✅ REAL (logic) | Blocked purely by the ingestion gap above. |
| `fi_duration` | 🟡 PARTIAL | Real duration/convexity math; Key Rate Duration engine built but never wired to any endpoint. |
| `fi_spread_analytics` | 🔴 GAP | Z-spread/OAS hardcoded `None`; G-spread is a passthrough field, not computed. |
| `fi_credit_quality` | 🔴 GAP | Momentum inputs hardcoded to `0.0` → always classifies "STABLE" regardless of issuer; Ohlson O-Score imported, never called. |
| `fi_risk` | ✅ REAL | Solid; uses issuance-time rating rather than current (minor inconsistency vs. `fi_credit_quality`). |
| `fi_screening` | ✅ REAL | Solid; unpaginated full scan is a scale concern, not correctness. |
| `fi_issuer_profile` | 🟡 PARTIAL | Maturity wall/debt stack real when data exists; refinancing-risk score half-weighted on hardcoded constants. |
| `fi_cross_asset` | 🔴 GAP | Real threshold logic, but entity-scoped endpoints mostly run on generic query-param defaults, not the entity's real data. |

---

## 6. Pillar 3 — Research & Intelligence

### 6.1 The "AI" story, precisely

- **`src/ai/llm_client.py`** — always returns `None` from `.generate()`. Used by exactly 3 routers: `sentiment.py`, `company_intelligence.py`, `company_primer.py` (all `/v1`). In practice these routers fetch the client and never even call `.generate()` on it — they just hardcode the narrative field to `None`/`False` directly.
- **The 8 Pillar-3-Phase-4 `research_*.py` routers use a completely different, third mechanism**: no LLM client import at all, just literal hardcoded placeholder strings (`research_qa.py`'s `"AI-generated answer placeholder."`, `research_briefings.py`'s `"On-demand briefing generated."`).
- **`src/services/ai/claude_client.py`** (real `claude-sonnet-5` wrapper, already updated per this session's earlier work) and **`src/services/ai/embedding_client.py`** (real Gemini embedding wrapper) are fully built and **completely unused** — zero imports anywhere outside their own module.
- **FinBERT is not actually installed.** `transformers`/`torch` aren't in `pyproject.toml`; `finbert_sentiment.py` always falls through to the keyword-lexicon fallback. "FinBERT-powered sentiment" is aspirational branding today.

### 6.2 Feature status

| Feature | Endpoint(s) | Status | Notes |
|---|---|---|---|
| 8-K filing events | `/v3/filings/events/*` | 🔴 GAP | `edgar_8k.py` (real SEC connector) persists to the wrong model (`CorporateAction`, not `EightKEvent`) — connector/table mismatch. |
| Filing diffs, insider transactions/signals | `/v3/filings/{id}/diff*`, `/insiders*` | 🔴 GAP | No writer for any of these three tables. |
| Governance score | `/v3/governance/{id}/score` | 🟡 PARTIAL (data bug) | Live-compute fallback is real when board/comp/proxy data exists (which it never does, see below) — but a separate code path in the same file computes from **fully hardcoded** input and **persists the fabricated result to the DB**, poisoning the cache for future real reads. Also: `ceo_is_chair` heuristic is silently broken (checks a dict key that's never set). |
| Proxy/board/compensation/proposals | `/v3/governance/filings/*` | 🔴 GAP | No ingestion for `ProxyFiling`/`BoardMember`/`ExecutiveCompensation`/`ShareholderProposal`. |
| News (latest/search/sector/timeline) | `/v3/news/*` | 🔴 GAP | Query logic is solid; `NewsArticle`/`ArticleEntityLink` have zero writers anywhere (matches the doc's own admission). |
| FI/rating/quality alerts | `/v3/alerts/fi/*`, `/quality-scores`, `/institutional-flow` | 🟡 PARTIAL | Real queries against real tables, but two endpoints repackage **user-configured alert thresholds** as if they were fired alert events (hardcoded severity, no actual evaluation against live data). |
| Alerts (fired events) | `/v3/alerts`, `/alerts/{id}` | 🔴 GAP | Config/watchlist CRUD works. `AlertEvent` (the actual fired alerts) has no producer anywhere — `alert_engine.py` is real but test-only. |
| Economic calendar | `/v3/news/calendar/economic*` | 🔴 GAP | Clean query logic, `EconomicRelease` never populated. |
| Earnings surprises/calls/guidance | `/v3/earnings/*` | 🔴 GAP | Cleanest router in the audit (fully real, well-guarded queries) — but all 4 backing tables have zero production writers. |
| Sentiment (screen/digest/peer/anomalies) | `/v3/news/sentiment/*` | 🔴 GAP | Real, well-fixed query/join logic (percentile peer comparison genuinely computed) — blocked entirely by the empty `news_articles`/`sentiment_aggregates` upstream. |
| Sentiment (v1, single-entity) | `/v1/analytics/sentiment/*` | 🟡 PARTIAL | `ai_enabled` hardcoded `False`; `avg_sentiment=0.0` sentinel returned instead of 404/null when no row exists (indistinguishable from a real neutral score). |
| Company intelligence (deep: business model, capital allocation, mgmt quality, balance-sheet risk) | `/v3/company/{id}/intelligence*` | 🔴 GAP | Zero production writers for any of the 4 backing tables — total gap, all 13 endpoints. |
| Company intelligence (v1, briefing cache) | `/v1/analytics/intelligence/*` | ⚫ STUB | Self-writes an **empty skeleton** on cache miss (`signal_data={}`, `valuation_data={}`); "refresh" does the identical empty-write. |
| Company primer (v1) | `/v1/analytics/primer/*` | ✅ REAL (mostly) | Genuinely populates financials/valuation from real Pillar-1/2 data. `ownership_data={}` still empty (acknowledged in code); AI narrative fields hardcoded `None`; no staleness/TTL check. |
| Industry rankings/overview/companies/economics/cycle | `/v3/industry/*` | 🔴 GAP | Router logic fully fixed and correct; tables never populated by any script. |
| Competitive moat/concentration/landscape | `/v3/competitive/*` | 🔴 GAP | Same pattern — fixed logic, no ingestion. |
| Global macro / country risk / commodities / political | `/v3/global-intelligence/*` (~35 endpoints) | 🟡 PARTIAL | Real queries across 12 tables, none populated by ingestion. `run_commodity_scenario` uses admitted placeholder linear arithmetic, not a real elasticity model. |
| FI intelligence (briefings, issuer profile) | `/v3/fi-intelligence/*` | 🔴 GAP | Real engine, zero production callers; one endpoint's "rating narrative" is a hardcoded f-string template, acknowledged in a code comment. |
| Research primers (Pillar 3, distinct from v1) | `/v4/research/primers/*` | 🔴 GAP | Reads `research_primers` table (recently renamed today to resolve a collision with the v1 `company_primers` table) — zero writers; `/refresh` inserts a `PENDING` log row nothing ever advances. |
| Morning briefings | `/v4/research/briefings/*` | ⚫ STUB | `POST /generate` inserts a hardcoded placeholder string as the "executive summary," regardless of actual portfolio/news state. |
| Anomaly detection | `/v4/research/anomalies/*` | 🔴 GAP + ⚫ | Real query/aggregation logic; `POST /scan/{id}` is a complete no-op (`{"scan_status": "INITIATED"}` and nothing else) — never actually detects anything. |
| Semantic search | `/v4/research/search` | 🔴 GAP (worse than "no embeddings") | Query text is **never applied as a filter at all** (not even ILIKE) — results are unconditionally chronological regardless of the search string or whether `GOOGLE_API_KEY` is set. No server-side embedding generation exists anywhere. |
| Investment thesis | `/v4/research/thesis/*` | 🟡 PARTIAL | Real CRUD; client must supply all narrative content manually (`generate_thesis` builds purely from the POST body, `ai_enabled` hardcoded `False`). |
| Analyst Q&A | `/v4/research/qa/*` | ⚫ STUB | Every answer is the literal string `"AI-generated answer placeholder."` — no question parsing at all. |
| Macro themes / scenarios | `/v4/research/themes/*` | 🟡 PARTIAL | Real reads/writes; `run_scenario` explicitly does not compute, just returns cached impacts. **Frontend/backend path mismatch**: `ThemesDashboard.tsx` expects `GET /v4/research/themes` (list) and `/themes/{id}/securities`, neither of which exist — live 404 risk independent of the data gap. |
| Consolidated alerts / earnings intelligence (P4) | `/v4/research/alerts/*` | 🔴 GAP | `POST /{id}/analyze` implies action but only reads the latest existing row — performs no analysis. |

---

## 7. Pillar 4 — Portfolio Management + Financial Analysis Suite

| Feature | Endpoint(s) | Status | Notes |
|---|---|---|---|
| Portfolio CRUD | `/v4/portfolios/*` | 🟡 PARTIAL | POST/GET/PUT/DELETE round-trip correctly (real per-user isolation, real commits). **`Position.market_value`/`unrealized_pnl`/`weight` never computed anywhere** (Fix #3) — NAV is cash-balance-only. `security_id` also never populated on position creation. |
| Portfolio risk (VaR/stress/compliance) | `/v4/portfolios/{id}/risk/*`, `/compliance/*` | 🟡 PARTIAL | Stress tests and pre-trade compliance rules are genuinely real computations (fixed since the prior audit) — but starved of real market values (inherits the bug above), and use a hardcoded `beta=1.0`/`duration=0.0` for every position regardless of its real factor exposure. |
| Portfolio performance/attribution | `/v4/portfolios/{id}/performance`, `/attribution` | 🔴 GAP | Router only ever *reads* `PerformanceSnapshot`; nothing in the entire codebase computes and writes one — **`GET .../performance` returns null forever** for every portfolio. Dormant MWR/IRR sign bug in the engine (adds terminal value as a positive cash flow instead of negative) will surface the moment this pipeline is wired up. |
| Portfolio watchlists (alerts/digest/earnings calendar) | `/v4/portfolios/watchlists/*` | ✅ REAL | Genuinely fixed since prior audit — real `calendar_events`-backed earnings alerts. |
| Research notes | `/v4/research/notes/*` | ✅ REAL | Clean CRUD, no issues found. |
| Smart-money / notable-filer tracking | `/v1/smart-money/*` | ✅ REAL | Real 13F/Form4/STOCK-Act data, real quarter-over-quarter diffing. One data bug: `data/notable_investors.json` has a copy-paste error — Bill Ackman's registry `key` is `"michael_burry_scion"`, so `/investors/bill_ackman` 404s. **No web frontend page exists for this feature** — API/desktop-GUI only. |
| Automatic Model Builder | `/v1/models/*` | 🟡 PARTIAL | `/build` (caller-supplied metrics) is fully real deterministic scoring. `/company/{id}` only feeds the `growth_score` sub-score from real data — `quality`/`value`/`safety`/`sentiment` silently fall back to neutral 50.0 defaults because the router never pulls in DCF/comps/Altman/smart-money outputs. **No web frontend page.** |
| Complex Financial Structure analysis | `/v1/complex-structure/*` | 🟡 PARTIAL | `/analyze` (caller payload) fully real across all 4 dimensions. `/entity/{id}` only ever populates the debt-waterfall dimension — no subsidiary-tree/share-class data source exists anywhere in the platform. Also a real bug: `is_secured` checks `instrument_type.startswith("SECURED")`, but real values start with `"SENIOR_..."` — `secured_pct` is always `0.0` for every real entity; should check `seniority_type` instead. **No web frontend page.** |

---

## 8. Frontend — Mock Data & Wiring Audit

Full page-by-page detail lives in the agent transcripts; this section summarizes the patterns and the highest-severity individual findings. 49 pages were audited; roughly a third are clean (proper hooks, honest empty states), a third have silent mock-data fallbacks, and the rest have a mix of broken endpoint URLs and mock fallbacks together.

### 8.1 Pages that are effectively 100% fake regardless of backend state

| Page | Route | Why |
|---|---|---|
| `MorningBrief.tsx` | `/` (the landing page) | All 5 queries hit nonexistent backend routes. |
| `SectorView.tsx` | `/sector` | Both hooks hit a nonexistent route or a route missing a required param — permanently fake sector table. |
| `Settings.tsx` | `/settings` | All 3 endpoints (classifications, profile, api-keys) hit nonexistent/wrong paths — "saving" a setting silently does nothing. |
| `CreditProfile.tsx` | `/company/credit` | ~10 realistic static blocks (covenants, credit metrics, maturity wall, leverage trajectory) render unconditionally, no hook gating at all. |
| `FIIntelligence.tsx` | `/fi/intelligence` | Contains a **fabricated Apple/Tim Cook earnings-call transcript with invented quotes**, rendered with zero backing API call — the single most concerning individual finding in the frontend audit. |

### 8.2 Pages calling a URL that doesn't exist on the backend (distinct bug class from mock fallback)

`MorningBrief.tsx`, `AlertsView.tsx` (shape mismatch, not URL), `Settings.tsx`, `CustomIndexBuilder.tsx`, `BacktestDashboard.tsx`, `CustomData.tsx`, `FlowsDashboard.tsx`, `DealsView.tsx`, `IPOMonitor.tsx`, `FIScreenerDashboard.tsx`, `SectorView.tsx`, `QuantDashboard.tsx` (2 of 3 hooks), `ThemesDashboard.tsx` (3 endpoints), `CompanyOverview.tsx` (5 inline calls), `GlobalDashboard.tsx`/`CountryRisk.tsx`/`PoliticalMonitor.tsx` (hooks wired to semantically wrong or disabled endpoints).

### 8.3 `Math.random()`-driven charts (never hook-backed, by construction)

`YieldCurveDeepDive.tsx` (2s10s spread + OAS), `TreasuryDashboard.tsx` (spread history), `CreditMarket.tsx` (IG OAS), `CommodityDashboard.tsx` (price chart), `MorningBrief.tsx` (S&P intraday). `PortfolioDetail.tsx`/`PerformancePage.tsx` have similar generators present as **dead code** (confirmed disconnected, not actually rendered) — leave as-is or delete, don't reconnect.

### 8.4 Clean reference implementations (use these as the template for fixes elsewhere)

`PrimerView.tsx`, `ThesisBuilder.tsx`, `SemanticSearch.tsx`, `AnalystQA.tsx`, `ResearchHub.tsx`, `CompanyIntelligence.tsx`, `GovernanceDashboard.tsx`, `RiskDashboard.tsx` (`/risk`), `FilingsView.tsx`, `BondDetail.tsx`. All show proper loading states, honest `—`/empty rendering, and (in the Research folder especially) code comments documenting a specific prior mock-data bug that was already fixed — a good pattern to replicate.

### 8.5 The one page that discloses its fallback to the user

`ScreenerDashboard.tsx` shows a "Demo mode" banner when a real screen run fails and mock data is substituted. It's the only page in the entire app that does this, and even it only shows the banner *after* a failed run, not on initial load. Worth generalizing this pattern (a small `<DemoModeBanner/>` component driven by `isError`) across every other page listed in §8.1–8.2.

---

## 9. Ingestion Layer — Source-of-Truth Summary

Of the 13 ingestion steps `CONNECTING_TO_REAL_DATA.md` §6 documents, only **6 are actually functional as written**: EDGAR entity ingestion, GLEIF, OpenFIGI, Polygon EOD prices, FRED macro, and congressional trades (STOCK Act). The other 7 are fully-implemented but structurally unreachable due to Fix #1 in §3.

| Working today | Broken (Fix #1 — CIK-list wiring) | Stub `extract()`, never called | No connector exists at all |
|---|---|---|---|
| EDGAR entities | XBRL fundamentals | Treasury yield curve | Executives, M&A deals, IPO events, Fund holdings |
| GLEIF | 8-K corporate actions | FRED money market | Debt maturity, FOMC meetings |
| OpenFIGI | 13F/Form4 ownership | Capital structure | Corporate bonds/TRACE, Bond issuances, Agency bonds |
| Polygon EOD prices | ESG (governance-only anyway) | Credit ratings | News, Estimates/guidance |
| FRED macro | Business relationships | FRED credit spreads | Trading calendars, Central bank policy |
| Congressional trades | FINRA short interest | Treasury securities (every method stubbed) | Governance catalog (`populate_governance.py` never touches the DB at all) |

**Two documentation bugs found in `CONNECTING_TO_REAL_DATA.md` itself:** the manual index-constituents snippet (§6 step 4) imports a class name (`IndexConstituentsConnector`) that doesn't exist (real name is singular, `IndexConstituentConnector`) and would `ImportError` if run as written; and even fixed, the `indices=['SPX']` kwarg it passes is silently ignored.

A full table-by-table cross-reference (all ~163 tables, each tagged with its writer or lack thereof) is preserved in the audit transcripts and can be regenerated on request — condensed into the tables above for readability.

---

## 10. What "done" looks like, if you want to close these gaps

Roughly in priority order:

1. Fix the CIK-list wiring bug (§3.1) — unlocks fundamentals, corporate actions, ownership, ESG, business relationships with no other code changes.
2. Fix the 4-5 frontend pages with outright broken URLs that affect the most-trafficked screens (landing page, alerts, news, settings).
3. Decide the AI story deliberately: either wire `src/services/ai/claude_client.py` into the 3 `/v1` routers + 8 `/v4/research/*` routers (replacing the stub/placeholder strings), or clearly label those fields as "not yet available" in the UI so they don't read as broken.
4. Fix `Position.market_value` computation — unblocks portfolio NAV, performance, and the compliance/risk ratios that depend on real NAV.
5. Everything in the "orphaned engine" category (§4–§6) is optional, lower-urgency polish — each one is a single well-defined wiring task (call the engine from a batch job or router), not a rewrite.
