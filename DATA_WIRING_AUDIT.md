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

> **Update (2026-07-09):** All Pillar 3 items below marked **✅ FIXED** were resolved in a wiring/bug-fix pass (see `git log` on `claude/pillar-3-data-wiring-d0159m`). Scope was deliberately limited to code-level wiring and bug fixes — orphaned engines connected, hardcoded placeholders replaced with real computation/AI, model/field mismatches corrected. Items requiring net-new ingestion connectors (news, proxy/board data, executives, earnings estimates, etc.) were explicitly left out of scope and remain open below.

1. **`scripts/ingest_edgar_xbrl.py`, `ingest_corporate_actions.py`, `ingest_ownership.py`, `ingest_esg.py`, `ingest_relationships.py`, `ingest_short_interest.py` never pass a CIK/ticker list to their connectors.** Each connector (`EdgarXBRLConnector`, `Edgar8KConnector`, `Edgar13FConnector`, `EdgarForm4Connector`, `EdgarESGConnector`, `Edgar10KNLPConnector`, `FinraShortInterestConnector`) defaults its CIK-list argument to `None → []` and its `extract()` immediately returns `[]` with a log warning when the list is empty. Every driver script instantiates the connector with **zero arguments** and never queries the DB for entities first. Running the pipeline exactly as `CONNECTING_TO_REAL_DATA.md` §6 documents (steps 8–13) inserts **zero rows** for fundamentals, corporate actions, 13F/Form4 ownership, ESG, and business relationships. This is the single highest-leverage fix in the whole audit — the transform/load logic is already correct, it just needs a `SELECT cik FROM entities` before constructing the connector.
2. ✅ **FIXED** — **`src/ai/llm_client.py:24-40` — `LLMClient.generate()` unconditionally returns `None`**, even when `ANTHROPIC_API_KEY` is set and `self._enabled` is `True`. Comment: "In production, this would call the Anthropic API... actual integration is deferred." Affects `sentiment.py`, `company_intelligence.py`, `company_primer.py` (all `/v1`). Separately, a real, working Anthropic SDK client (`src/services/ai/claude_client.py`, model `claude-sonnet-5`) and Gemini embedding client (`src/services/ai/embedding_client.py`) already exist and are fully unused — wiring these into `llm_client.py` (or replacing it) is a bounded, well-scoped fix.
   `llm_client.py` now calls `ClaudeClient.generate_text()`; all 3 `/v1` routers plus `research_qa.py`, `research_briefings.py`, `research_thesis.py`, and `fi_intelligence.py` now use it for real narrative generation (falling back to `None` when unconfigured, never a fabricated string). `embedding_client.py` is now wired into semantic search (see item 4 below).
3. ✅ **FIXED** — **`Position.market_value`/`unrealized_pnl`/`weight` are never computed anywhere** (`src/api/routers/portfolios.py`). A real engine to do this (`src/engines/nav_engine.py::compute_position_market_value`) exists and is unit-tested but has zero non-test callers. Consequence: portfolio NAV is cash-balance-only forever, and this starves portfolio risk/compliance checks downstream (§7).
   Now wired via `_refresh_portfolio_positions()` in `portfolios.py`, called from every position read/write path (list, add, update, clone, upload-commit, BUY/SELL transactions).
4. ✅ **FIXED** — **`research_qa.py:65`** stores the literal string `"AI-generated answer placeholder."` as the answer to every question asked. **`research_briefings.py:225-243`** stores `"On-demand briefing generated."` for every morning briefing. These are the two most literal "fake AI" instances found — worth fixing or at minimum clearly labeling in the UI before any demo.
   Both now generate real content: `research_qa.py` calls the LLM grounded in the entity's real financial/valuation data (or returns `None`/`AI_DISABLED` honestly without a key); `research_briefings.py` assembles real portfolio price-move, thesis-update, and macro-indicator data and summarizes it via the LLM.
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

> **Remaining Pillar 3 work (updated 2026-07-09, second pass).** The orphaned-engine wirings below are now **DONE** — all four intelligence-engine groups plus the global-macro compute path have producers and are tested:
> - ✅ **Industry Intelligence** (`industry_profiles` / `industry_cycle_positions` / `industry_competitive_structures`): `industry.py::_compute_industry_intelligence` aggregates a GICS code's member companies' fundamentals + ROIC/WACC + market caps → `industry_economics` (profile), `compute_competitive_structure` (HHI/concentration), `compute_cycle_position` (over an industry-aggregate per-fiscal-year revenue/margin series). Read endpoints compute-on-miss.
> - ✅ **Competitive Intelligence** (`moat_assessments` / `concentration_risk_assessments` / `competitive_landscape`): `competitive.py::_compute_competitive` sources industry/peer aggregates from the Industry producer above, then runs `assess_moat`, `analyze_competitive_landscape`, and `assess_concentration_risk` (customer/supplier HHI from real `business_relationships` + geographic from `segment_data`). (`moat_history` — the multi-period time series — is still unpopulated; the point-in-time assessment is wired.)
> - ✅ **Deep Company Intelligence `/v3`** (`business_model_analyses` / `capital_allocation_assessments` / `balance_sheet_risk_assessments` / `management_quality_assessments`): `company_intel_p2.py::_compute_and_persist_intelligence` runs all four per-entity engines over assembled fundamentals + analytics; main GET computes on-miss, `POST .../intelligence/refresh` force-recomputes.
> - ✅ **Global-macro compute** (`global_macro_indicators`, `/global/macro/{inflation,growth,recession-probability,dashboard}`): `global_intelligence.py::_ensure_us_macro_indicators` populates US rows from FRED `macro_values` and computes recession probability via the `global_macro` engine. US-only.
>
> **Update (2026-07-09, later same day, commit `924e640` — not reflected in the pass above when it was written):** every ingestion connector this section previously called "still genuinely open" was actually built and is real: `scripts/ingest_proxy.py` (DEF 14A → `proxy_filings`/`board_members`/`executive_compensation`/`shareholder_proposals`, read by `governance_intelligence.py`), `scripts/ingest_form4.py` (Form 4 → `insider_transactions_p3`/`insider_signals`, read by `filing_intelligence.py`), `scripts/ingest_econ_calendar.py` (→ `economic_releases`), `scripts/ingest_commodities.py` (→ `commodity_profiles`/`commodity_prices`), `scripts/ingest_legislative_bills.py`/`ingest_regulatory_actions.py`/`ingest_sanctions.py` (→ `legislative_bills`/`regulatory_actions`/`sanctions_entries`, all read by `global_intelligence.py`), `scripts/ingest_country_risk.py` (World Bank → non-US `global_macro_indicators` + `country_profiles`/`country_risk_scores`), `scripts/ingest_geopolitical.py` (GDELT → `geopolitical_events`), and `scripts/ingest_filing_diff.py` (now stores full filing section text and diffs it — the earlier "no full text stored" blocker is resolved). All are CIK-driven and keyless/free (earnings is the one exception, see below). **The only gap was that none of these were registered in `src/scheduler/batch_config.py` or documented in `CONNECTING_TO_REAL_DATA.md`** — real, working code nobody running the setup guide would discover. Both are now fixed (see §10 update below).
>
> **Update (this session):** two more wiring gaps closed: **`moat_history`** now gets a real per-period time series (roic/wacc/gross_margin backfilled from `AnalyticsResult` + `FinancialPeriod` history inside `_compute_competitive`; classification fields set only on the latest period, since the classifier isn't re-run historically) — `competitive.py::get_moat_history` also now computes-on-miss. **FI market briefings** (`FIMarketBriefing` — yield-curve + credit, flagged as "real engine, zero production callers") now have a producer: `scripts/generate_fi_briefings.py` reads real FRED-sourced `yield_curve_snapshots`/`credit_spread_indices` (both already-working connectors that just weren't scheduled either — see §10) and persists via the previously-orphaned `fi_intelligence.py` engine; the two `/fi/yield-curve/briefing` and `/fi/credit/briefing` GET endpoints compute-on-miss. New-issuance-driven fields (rating-migration fallen-angels/rising-stars, issuer briefings) remain unaddressed — no bond-issuance/rating-history connector exists to source them.
>
> **Update (next session): `slide_outline` and `ThemesDashboard.tsx` fixed.**
> - **`slide_outline`**: rather than force-fit analyst content into `generate_slide_outline()`'s rigid dataclass (which would mean fabricating a schema), `research_thesis.py` now defines and documents a real convention for the free-form `key_drivers`/`primary_risks`/`valuation_scenarios`/`catalysts` JSON (`{"items": [...]}` / `{"current_price", "bull"/"base"/"bear": {...}}`, see `ThesisCreateRequest` docstring) and builds each slide section independently via a new `_build_slide_outline()`, skipping any section not in that shape rather than fabricating placeholder content. Wired into create, update, and a compute-on-miss backfill on `GET .../slides`.
> - **`ThemesDashboard.tsx`**: the dead `useThemeDetail`/`useThemeSecurities` hooks pointed at a `{themeId}` catalog resource the backend never had (themes are exposure-score labels keyed by entity, not standalone objects). Fixed by adding two real endpoints instead of a fake catalog — `GET /research/themes/summary/{theme}` (aggregate stats) and `GET /research/themes/{theme}/securities` (most-exposed entities, now with `entity_name`) — both querying real `macro_theme_scores` rows, and wiring them into an actual click-to-drill-down UI on the page. Also removed `useCreateTheme`/`useUpdateTheme` (no such backend concept — themes aren't user-authored) and a duplicate `useThemes()`. **Separately found and fixed while doing this**: `ThemesDashboard.tsx` had the same array-vs-object-property bug as `AlertsView.tsx` (`apiThemes?.themes` on what the backend returns as a bare array) — the whole page's card/heatmap UI assumed a shape (`{name, tickers, conviction, horizon}` themes, per-sector heatmap) the real `ThemeScoreResponse[]` schema never had; replaced with a UI built from the real per-entity exposure-score fields.
> - **New finding, not fixed**: `macro_theme_scores` (the table both endpoints above read) has **zero producers anywhere in the codebase** — no ingestion script, no engine, nothing ever calls `MacroThemeScore(...)`. This is deeper than the frontend/API-contract bug that was fixed; it means both endpoints are query-complete but will return empty/zero until a theme-exposure-scoring engine is designed and wired (a new analytical methodology — which themes exist, how exposure/direction is scored per entity — not an existing orphaned engine to reconnect). Not attempted this pass; flagged here so it isn't mistaken for done.

> **Still genuinely open:** earnings **estimates/guidance** specifically (consensus EPS/price-target — Finnhub free tier 403s on those two endpoints; actuals via `/stock/earnings` ARE ingested by `ingest_earnings.py`); **FinBERT** is still not installed (`transformers`/`torch` absent from `pyproject.toml` — a dependency/environment decision, not attempted here since it's a large, non-data-source change outside this pass's scope); **non-US global-macro / country-risk** now has a real connector but no compute-on-miss trigger (unlike the US/FRED path) — it requires a live outbound call to the World Bank API, so it's scheduled (weekly) rather than triggered per-request, by design; **`macro_theme_scores` has no producer** (see above).

### 6.1 The "AI" story, precisely

> ✅ **FIXED (2026-07-09):** `src/ai/llm_client.py` now wires `src/services/ai/claude_client.py` and actually generates text. `sentiment.py`, `company_intelligence.py`, `company_primer.py` (v1), `research_qa.py`, `research_briefings.py`, `research_thesis.py`, and `fi_intelligence.py` all now call `.generate()` and use the result (falling back to `None`/honest defaults when `ANTHROPIC_API_KEY` isn't set, never a fabricated string). `src/services/ai/embedding_client.py` is now wired into semantic search's index/query path. The bullets below describe the pre-fix state for the record.

- ~~`src/ai/llm_client.py`~~ — always returns `None` from `.generate()`. Used by exactly 3 routers: `sentiment.py`, `company_intelligence.py`, `company_primer.py` (all `/v1`). In practice these routers fetch the client and never even call `.generate()` on it — they just hardcode the narrative field to `None`/`False` directly.
- ~~**The 8 Pillar-3-Phase-4 `research_*.py` routers use a completely different, third mechanism**~~: no LLM client import at all, just literal hardcoded placeholder strings (`research_qa.py`'s `"AI-generated answer placeholder."`, `research_briefings.py`'s `"On-demand briefing generated."`).
- ~~**`src/services/ai/claude_client.py`** ... and **`src/services/ai/embedding_client.py`** ... are fully built and **completely unused**~~ — zero imports anywhere outside their own module.
- **FinBERT is not actually installed.** `transformers`/`torch` aren't in `pyproject.toml`; `finbert_sentiment.py` always falls through to the keyword-lexicon fallback. "FinBERT-powered sentiment" is aspirational branding today. *(Not addressed — installing FinBERT is a dependency/ingestion change, out of this pass's wiring/bug-fix scope.)*

### 6.2 Feature status

| Feature | Endpoint(s) | Status | Notes |
|---|---|---|---|
| 8-K filing events | `/v3/filings/events/*` | 🔴 GAP (ingestion) — model mismatch ✅ FIXED | `edgar_8k.py` now persists to `EightKEvent` (was `CorporateAction`) — the connector/table mismatch is fixed. Still blocked end-to-end by Fix #1 (§3.1, CIK-list wiring) until that ingestion gap is separately closed. |
| Filing diffs, insider transactions/signals | `/v3/filings/{id}/diff*`, `/insiders*` | 🔴 GAP | No writer for any of these three tables. |
| Governance score | `/v3/governance/{id}/score` | 🟡 PARTIAL — data bug ✅ FIXED | Live-compute fallback is real when board/comp/proxy data exists (which it never does without proxy ingestion, see below). The fabricated-input persist path is removed — `/score` now shares the same live-compute-or-404 logic as `/filings/{id}/proxy/governance` instead of ever persisting a hardcoded score. `ceo_is_chair` now cross-references board chairs against `ExecutiveCompensation.role` instead of checking a dict key that was never set. |
| Proxy/board/compensation/proposals | `/v3/governance/filings/*` | 🔴 GAP | No ingestion for `ProxyFiling`/`BoardMember`/`ExecutiveCompensation`/`ShareholderProposal`. |
| News (latest/search/sector/timeline) | `/v3/news/*` | ✅ REAL (audit correction) | The "zero writers" claim is **stale**: `src/ingestion/finnhub_news.py` (`FinnhubNewsConnector`) is a real writer of `news_articles`/`article_entity_links`, wired through the on-demand freshness service (`freshness.py` → `refresh_global_news` / `refresh_entity(...["news"])`), triggered from `news.py`. Gated on `FINNHUB_API_KEY` (returns empty without it), which is why it looked empty. |
| FI/rating/quality alerts | `/v3/alerts/fi/*`, `/quality-scores`, `/institutional-flow` | ✅ FIXED | `/quality-scores` now evaluates each config's threshold against the entity's actual latest governance score and emits only real breaches with magnitude-based severity; `/institutional-flow` evaluates a measured net flow against the threshold (and correctly returns empty when no measured flow exists rather than inventing volume from the threshold). Was: both repackaged the user's configured threshold value as if it were a fired alert's measured metric, with hardcoded MEDIUM severity. |
| Alerts (fired events) | `/v3/alerts`, `/alerts/{id}` | ✅ FIXED | Config/watchlist CRUD works. `POST /v3/alerts/evaluate` is now the producer: it drives the real `alert_engine` with real 8-K filing events (`eight_k_events`) and real EOD prices (threshold / 52-week high-low), then deduplicates and persists `AlertEvent` rows. `/alerts` and `/alerts/{id}` return real fired events instead of always empty. (Was: `alert_engine.py` real but test-only, no `AlertEvent` producer.) |
| Economic calendar | `/v3/news/calendar/economic*` | 🔴 GAP | Clean query logic, `EconomicRelease` never populated. |
| Earnings surprises/calls/guidance | `/v3/earnings/*` | 🔴 GAP | Cleanest router in the audit (fully real, well-guarded queries) — but all 4 backing tables have zero production writers. |
| Sentiment (screen/digest/peer/anomalies) | `/v3/news/sentiment/*` | ✅ FIXED (producer wired) | Real, well-fixed query/join logic. The upstream producer now exists: `POST /v1/analytics/sentiment/{id}/refresh` scores the entity's ingested `news_articles` (Finnhub) via the keyword engine into `sentiment_scores`, then rolls them up via the previously-orphaned `compute_aggregate_sentiment` into `sentiment_aggregates` (both writes idempotent). Populated once news is ingested (needs `FINNHUB_API_KEY`); `news_articles` itself was already wired (audit's "zero writers" was stale — `finnhub_news.py` is the writer). |
| Sentiment (v1, single-entity) | `/v1/analytics/sentiment/*` | 🟡 PARTIAL ✅ FIXED | `/score` now uses the real LLM client when configured (falls back to keyword heuristic, `ai_enabled` reflects which path actually ran). `avg_sentiment` is now `null` (schema changed to `float | None`) instead of a `0.0` sentinel when no aggregate row exists. |
| Company intelligence (deep: business model, capital allocation, mgmt quality, balance-sheet risk) | `/v3/company/{id}/intelligence*` | ✅ FIXED | All four engines (`business_model_engine`, `capital_allocation_engine`, `balance_sheet_risk_engine`, `management_quality_engine`) are now wired via `_compute_and_persist_intelligence`, computing from real fundamentals/cash-flow/analytics; main GET computes on-miss, `POST .../intelligence/refresh` recomputes. (Was: zero production writers for any of the 4 tables.) |
| Company intelligence (v1, briefing cache) | `/v1/analytics/intelligence/*` | 🟡 PARTIAL ✅ FIXED | Was: self-writes an **empty skeleton** on cache miss (`signal_data={}`, `valuation_data={}`); "refresh" does the identical empty-write. Now: assembles real `signal_data` (price-change/volume z-window from EOD prices, debt-to-equity/interest-coverage from fundamentals) and `valuation_data` (price, EPS, EBITDA, book value/share, EV/dividend from real AnalyticsResult rows) before scoring, and generates a real AI summary when configured. Sub-signals with no ingested source (earnings surprise, insider shares, guidance, analyst revisions) are omitted rather than fabricated. |
| Company primer (v1) | `/v1/analytics/primer/*` | ✅ FIXED | Genuinely populates financials/valuation from real Pillar-1/2 data. `business_description`/`competitive_position` now come from a real LLM call grounded in that data (was hardcoded `None`). `ownership_data` now joins the entity's equity security to real 13F `institutional_holdings` for `institutional_pct` + `top_holders` (was hardcoded `{}`); `insider_pct` is left honestly omitted (no reliable shares-outstanding-normalized source). No staleness/TTL check (still unaddressed). |
| Industry rankings/overview/companies/economics/cycle | `/v3/industry/*` | ✅ FIXED | `_compute_industry_intelligence` aggregates a GICS code's member companies (fundamentals + ROIC/WACC analytics + market caps) into `industry_profiles`/`industry_competitive_structures`/`industry_cycle_positions` via the `industry_economics` + `industry_cycle` engines; the four read endpoints compute-on-miss. (Was: tables never populated.) |
| Competitive moat/concentration/landscape | `/v3/competitive/*` | ✅ FIXED | `_compute_competitive` sources the industry/peer aggregates from the Industry producer, then runs `assess_moat` + `analyze_competitive_landscape` + `assess_concentration_risk` (customer/supplier from real `business_relationships`, geographic from `segment_data`); moat/landscape/concentration endpoints compute-on-miss. `moat_history` now backfills a real per-period series (roic/wacc/gross_margin from `AnalyticsResult`/`FinancialPeriod`; classification fields set only on the latest period) — `get_moat_history` also computes-on-miss. |
| Global macro / country risk / commodities / political | `/v3/global-intelligence/*` (~35 endpoints) | ✅ FIXED (ingestion) | Real queries across 12 tables. All now have real producers: `ingest_country_risk.py` (World Bank, non-US macro + country risk), `ingest_legislative_bills.py`/`ingest_regulatory_actions.py`/`ingest_sanctions.py` (political), `ingest_commodities.py` (FRED), `ingest_geopolitical.py` (GDELT) — see CONNECTING_TO_REAL_DATA.md §6. Non-US macro has no compute-on-miss trigger (unlike the US/FRED path) since it requires a live World Bank API call — it's scheduled weekly instead. `run_commodity_scenario` delegates to the real `commodity_intelligence.run_commodity_scenario` engine (producer/consumer direction + revenue-exposure weighting) instead of a flat `price_change × score` linear product. |
| FI intelligence (briefings, issuer profile) | `/v3/fi-intelligence/*` | ✅ FIXED | `scripts/generate_fi_briefings.py` now produces real `FIMarketBriefing` rows (yield-curve + credit) from FRED-sourced `yield_curve_snapshots`/`credit_spread_indices` via the previously-orphaned `fi_intelligence.py` engine; `/fi/yield-curve/briefing` and `/fi/credit/briefing` compute-on-miss. New-issuance-driven fields (rating-migration fallen-angels/rising-stars, full issuer briefings) remain unaddressed — no bond-issuance/rating-history connector exists. `/fi/issuers/{id}/rating-narrative` builds a real narrative from the issuer's full rating history (oldest → newest issuance ratings, upgrade/downgrade trend), optionally polished by the LLM — was a single hardcoded f-string template. |
| Research primers (Pillar 3, distinct from v1) | `/v4/research/primers/*` | ✅ FIXED | `/refresh` now actually generates a primer: it runs the previously-orphaned `company_primer_engine` over real Pillar 1/2 data (fundamentals, market cap, business segments, 8-K events, linked news), persists a versioned `research_primers` row, and advances the refresh log to DONE. (Was: only inserted a `PENDING` log row nothing advanced.) |
| Morning briefings | `/v4/research/briefings/*` | ✅ FIXED | `POST /generate` now assembles real `portfolio_impact` (price moves for the user's tracked entities from EOD prices), `thesis_updates` (recently-updated `InvestmentThesis` rows), and `macro_context` (latest FRED headline indicators), and generates `executive_summary` via the LLM when configured — was a hardcoded placeholder string regardless of state. |
| Anomaly detection | `/v4/research/anomalies/*` | ✅ FIXED | Real query/aggregation logic. `POST /scan/{id}` now runs a real z-score-based price/volume anomaly detector against EOD price history and persists any newly-detected `DetectedAnomaly` rows, returning `"COMPLETED"` with the actual count — was a complete no-op that always replied `"INITIATED"`. |
| Semantic search | `/v4/research/search` | ✅ FIXED | Query text now applies as a real substring filter (chunk text + title), with cosine-similarity re-ranking against a fresh query embedding when `GOOGLE_API_KEY` is configured and indexed documents carry embeddings. `POST /research/search/index` now generates an embedding server-side via `embedding_client.py` when the caller doesn't supply one. Was: query text never applied as a filter at all; no server-side embedding generation anywhere. |
| Investment thesis | `/v4/research/thesis/*` | 🟡 PARTIAL ✅ PARTIALLY FIXED | Real CRUD; core thesis content (title, summary, drivers, risks) is still analyst-authored from the POST body by design — this is a research-authoring tool, not an auto-writer. `elevator_pitch` now generates via the LLM when configured (was always `null`, no endpoint ever set it); `quality_metrics` now computes real completeness (was always `null`); `ai_enabled` reflects whether AI actually ran (was hardcoded `False`). `slide_outline` now generates via a documented free-form-JSON convention (see §6 update) instead of staying `null` — built independently per section (drivers/valuation/risks/catalysts), skipping any section not in the documented shape. |
| Analyst Q&A | `/v4/research/qa/*` | ✅ FIXED | `POST /ask` now generates a real answer via the LLM, grounded in the entity's real financial/valuation data (assembled the same way `company_primer.py` does) when `entity_id`/context is supplied. Returns `null`/`answer_type="AI_DISABLED"` honestly when no API key is configured — was always the literal string `"AI-generated answer placeholder."` regardless of AI availability. |
| Macro themes / scenarios | `/v4/research/themes/*` | 🟡 PARTIAL ✅ MOSTLY FIXED | `POST /scenarios/{id}/run` now actually computes EPS/margin/rating/price-target impact via `macro_scenario_engine.run_company_scenario()` (a real, unit-tested engine that previously had zero production callers) for entities with real sector/EPS/price data, persists the results, and preserves any previously-cached impacts for entities it can't (re)compute this pass — was: explicitly does not compute, just echoes cached impacts. **Frontend/backend path mismatch**: the reachable mismatch (`ThemesDashboard.tsx`'s `useResearchThemes()` hitting nonexistent `GET /v4/research/themes`) is fixed — it now calls the real `/v4/research/themes/dashboard`. `useThemeDetail`/`useThemeSecurities` are now real too — `GET /research/themes/summary/{theme}` and `GET /research/themes/{theme}/securities` were added (real aggregate/list-by-theme-label queries, no fake catalog) and wired into an actual drill-down UI on the page; the page's whole card/heatmap layout also had the same bare-array-vs-object-property bug as `AlertsView.tsx`, now fixed. **New finding**: `macro_theme_scores` itself has zero producers anywhere — these endpoints are query-complete but will return empty until a theme-exposure-scoring engine is built (not attempted; this is new methodology, not an orphaned engine). |
| Consolidated alerts / earnings intelligence (P4) | `/v4/research/alerts/*` | ✅ FIXED | `POST /earnings-intelligence/{id}/analyze` now computes a real stock-price reaction around the report date from EOD prices, derives directional implications/recommendation from the recorded EPS/revenue surprise, and generates an AI narrative when configured — was: implies action but only re-reads the latest existing row, performing no analysis. |

---

## 7. Pillar 4 — Portfolio Management + Financial Analysis Suite

> **Update (2026-07-09):** All Pillar 4 items below marked **✅ FIXED** were resolved in the same wiring/bug-fix pass as Pillar 3 (see `git log` on `claude/pillar-3-data-wiring-d0159m`). One claimed bug (MWR/IRR sign) was investigated and found to be a **false positive** on closer inspection — see the performance/attribution row for the math.

| Feature | Endpoint(s) | Status | Notes |
|---|---|---|---|
| Portfolio CRUD | `/v4/portfolios/*` | 🟡 PARTIAL ✅ FIXED | POST/GET/PUT/DELETE round-trip correctly (real per-user isolation, real commits). **`Position.market_value`/`unrealized_pnl`/`weight`** are now computed via `nav_engine.compute_position_valuation()` against real EOD prices (a new `_refresh_portfolio_positions()` helper resolves `security_id` by ticker if unset, then recomputes on every read/write path: list, add, update, clone, upload-commit, and each BUY/SELL transaction) — was: never computed anywhere, so NAV was cash-balance-only. |
| Portfolio risk (VaR/stress/compliance) | `/v4/portfolios/{id}/risk/*`, `/compliance/*` | 🟡 PARTIAL ✅ FIXED | Stress tests and pre-trade compliance rules are genuinely real computations. Compliance ratios now benefit from the real `market_value` fix above. Stress-test position inputs now carry a real per-position **asset class** (equity vs. bond, from `Security.asset_class`), a real **beta** (Blume-adjusted OLS regression vs. the market benchmark, reusing `e2_wacc._compute_beta` — a real engine with no prior production caller outside WACC), and real bond **duration/convexity** (via `treasury_analytics.compute_duration_convexity`, from coupon/maturity/YTM) for fixed-income positions — was: every position hardcoded to `asset_class="equity"`, `beta=1.0`, `duration=0.0` regardless of what it actually held. |
| Portfolio performance/attribution | `/v4/portfolios/{id}/performance`, `/attribution` | 🔴 GAP ✅ MOSTLY FIXED | Was: router only ever read `PerformanceSnapshot`; nothing wrote one, so `GET .../performance` returned null forever. Now: a new `_ensure_nav_snapshot_today()` records a real daily `NAVSnapshot` (idempotent per day) from live position/cash data, and `_compute_and_persist_performance()` wires the previously fully-orphaned `performance_engine.py` (TWR, MWR/IRR, Sharpe, Sortino, Calmar, volatility, max drawdown, best/worst day — all real, unit-tested pure computation with zero prior production callers) against that NAV history, persisting a real `PerformanceSnapshot`. Benchmark-relative metrics (benchmark_return, beta, alpha, tracking error, information ratio, up/down capture, batting average) remain `null` — `Portfolio.benchmark_id` is a free-text ticker with no resolved security/price series wired here yet, an honest gap rather than a guess. MWR's sole modeled external cash flow is the portfolio's `initial_cash` at inception (this data model has no deposit/withdrawal transaction type distinct from BUY/SELL, which are internal and NAV-neutral). Historical backfill for the calendar-year (`/returns/calendar`) and rolling (`/returns/rolling`) endpoints — which expect one `PerformanceSnapshot` row per day/month, not just a since-inception snapshot — is **not** included; that's a separate, larger backfill task.<br><br>**Correction to the "dormant MWR/IRR sign bug" claim**: on inspection, `compute_mwr()`'s convention (terminal value as a *positive* inflow) is the mathematically correct standard XIRR formulation. Worked example: invest $100 at t=0, receive $110 back after a year → `-100 + 110/(1+r) = 0` → `r = 0.10` (correct 10% return), which is exactly what the existing passing unit tests (`test_simple_irr`, `test_negative_return`) verify. Flipping the sign as an earlier internal audit (`PILLAR_4_AUDIT_REPORT_v2.md`, finding P4-E-030) proposed would have made every ending NAV read as a *cost* rather than a value received, breaking the correct behavior — so no change was made here. |
| Portfolio watchlists (alerts/digest/earnings calendar) | `/v4/portfolios/watchlists/*` | ✅ REAL | Genuinely fixed since prior audit — real `calendar_events`-backed earnings alerts. |
| Research notes | `/v4/research/notes/*` | ✅ REAL | Clean CRUD, no issues found. |
| Smart-money / notable-filer tracking | `/v1/smart-money/*` | ✅ REAL — data bug ✅ FIXED | Real 13F/Form4/STOCK-Act data, real quarter-over-quarter diffing. `data/notable_investors.json`'s Bill Ackman entry now has `"key": "bill_ackman"` (was `"michael_burry_scion"`, a copy-paste error that 404'd `/investors/bill_ackman`). **No web frontend page exists for this feature** — API/desktop-GUI only (unaddressed, out of scope). |
| Automatic Model Builder | `/v1/models/*` | 🟡 PARTIAL ✅ MOSTLY FIXED | `/build` (caller-supplied metrics) is fully real deterministic scoring. `/company/{id}` now also wires **quality** (ROE from real balance sheet + Piotroski F-Score), **value** (DCF upside/downside from `DCFResult` + relative-valuation percentile from the real comps engine), and **safety** (Altman Z-Score) sub-scores from real batch-computed data — was: only `growth_score` fed from real data, the rest silently defaulting to neutral 50.0. **`sentiment_score` still defaults to neutral** — wiring `smart_money_signal`/`insider_buy_ratio` would need its own quarter-over-quarter diffing query against the 13F/Form4 domain, scoped out of this pass. **No web frontend page** (unaddressed). |
| Complex Financial Structure analysis | `/v1/complex-structure/*` | 🟡 PARTIAL — `is_secured` bug ✅ FIXED | `/analyze` (caller payload) fully real across all 4 dimensions. `/entity/{id}` only ever populates the debt-waterfall dimension — no subsidiary-tree/share-class data source exists anywhere in the platform (unaddressed, needs new ingestion). `is_secured` now checks `seniority_type == "SENIOR_SECURED"` (the real enum values are `SENIOR_SECURED`/`SENIOR_UNSECURED`/`SUBORDINATED`/`JUNIOR_SUBORDINATED` on `seniority_type`) — was checking `instrument_type.startswith("SECURED")`, which real values never match, so `secured_pct` was always `0.0` for every entity. **No web frontend page** (unaddressed). |

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

`MorningBrief.tsx`, `AlertsView.tsx` (shape mismatch, not URL), `Settings.tsx`, `CustomIndexBuilder.tsx`, `BacktestDashboard.tsx`, `CustomData.tsx`, `FlowsDashboard.tsx`, `DealsView.tsx`, `IPOMonitor.tsx`, `FIScreenerDashboard.tsx`, `SectorView.tsx`, `QuantDashboard.tsx` (2 of 3 hooks), `CompanyOverview.tsx` (5 inline calls), `GlobalDashboard.tsx`/`CountryRisk.tsx`/`PoliticalMonitor.tsx` (hooks wired to semantically wrong or disabled endpoints). ~~`ThemesDashboard.tsx` (3 endpoints)~~ — **fixed** (see §6 update): was the same shape-mismatch bug as `AlertsView.tsx`, plus two genuinely-missing endpoints that are now real.

### 8.3 `Math.random()`-driven charts (never hook-backed, by construction)

`YieldCurveDeepDive.tsx` (2s10s spread + OAS), `TreasuryDashboard.tsx` (spread history), `CreditMarket.tsx` (IG OAS), `CommodityDashboard.tsx` (price chart), `MorningBrief.tsx` (S&P intraday). `PortfolioDetail.tsx`/`PerformancePage.tsx` have similar generators present as **dead code** (confirmed disconnected, not actually rendered) — leave as-is or delete, don't reconnect.

### 8.4 Clean reference implementations (use these as the template for fixes elsewhere)

`PrimerView.tsx`, `ThesisBuilder.tsx`, `SemanticSearch.tsx`, `AnalystQA.tsx`, `ResearchHub.tsx`, `CompanyIntelligence.tsx`, `GovernanceDashboard.tsx`, `RiskDashboard.tsx` (`/risk`), `FilingsView.tsx`, `BondDetail.tsx`. All show proper loading states, honest `—`/empty rendering, and (in the Research folder especially) code comments documenting a specific prior mock-data bug that was already fixed — a good pattern to replicate.

### 8.5 The one page that discloses its fallback to the user

`ScreenerDashboard.tsx` shows a "Demo mode" banner when a real screen run fails and mock data is substituted. It's the only page in the entire app that does this, and even it only shows the banner *after* a failed run, not on initial load. Worth generalizing this pattern (a small `<DemoModeBanner/>` component driven by `isError`) across every other page listed in §8.1–8.2.

---

## 9. Ingestion Layer — Source-of-Truth Summary

Of the 13 ingestion steps `CONNECTING_TO_REAL_DATA.md` §6 documents, only **6 are actually functional as written**: EDGAR entity ingestion, GLEIF, OpenFIGI, Polygon EOD prices, FRED macro, and congressional trades (STOCK Act). The other 7 are fully-implemented but structurally unreachable due to Fix #1 in §3.

> **Correction:** Treasury yield curve and FRED credit spreads were fixed in an earlier pass (`fred_treasury_curve.py`/`fred_credit_spreads.py` both have real `load()` methods and working scripts — `scripts/ingest_treasury_curve.py`/`scripts/ingest_credit_spreads.py`) but were never registered in `src/scheduler/batch_config.py`, so they never ran unattended — same class of gap as the undocumented Pillar-3 connectors below. Both are now scheduled (see §10 update) and feed `scripts/generate_fi_briefings.py` (§6). Moved out of the "stub" column below.

| Working today | Broken (Fix #1 — CIK-list wiring) | Stub `extract()`, never called | No connector exists at all |
|---|---|---|---|
| EDGAR entities | XBRL fundamentals | FRED money market | Executives, M&A deals, IPO events, Fund holdings |
| GLEIF | 8-K corporate actions | Capital structure | Corporate bonds/TRACE, Bond issuances, Agency bonds |
| OpenFIGI | 13F/Form4 ownership | Credit ratings | News, forward consensus estimates/guidance |
| Polygon EOD prices | ESG (governance-only anyway) | Treasury securities (every method stubbed) | Trading calendars, Central bank policy |
| FRED macro | Business relationships | | |
| Congressional trades | FINRA short interest | | |
| Treasury yield curve (FRED) | | | |
| FRED credit spreads | | | |

Also now working (Pillar 3, added in `924e640`, scheduled this session — see §6 update and CONNECTING_TO_REAL_DATA.md §6): proxy/governance (DEF 14A), Form4 insider transactions P3, economic-release calendar, commodities (FRED), legislative bills / regulatory actions / sanctions, country risk + non-US macro (World Bank), geopolitical events (GDELT), filing diffs. The one still-genuine gap in this group is forward consensus estimates/guidance (Finnhub free tier blocks it).

`Governance catalog` (`populate_governance.py`) is a separate, unrelated concept — see CONNECTING_TO_REAL_DATA.md §6 for the distinction from corporate proxy/board governance.

**Two documentation bugs found in `CONNECTING_TO_REAL_DATA.md` itself:** the manual index-constituents snippet (§6 step 4) imports a class name (`IndexConstituentsConnector`) that doesn't exist (real name is singular, `IndexConstituentConnector`) and would `ImportError` if run as written; and even fixed, the `indices=['SPX']` kwarg it passes is silently ignored.

A full table-by-table cross-reference (all ~163 tables, each tagged with its writer or lack thereof) is preserved in the audit transcripts and can be regenerated on request — condensed into the tables above for readability.

---

## 10. What "done" looks like, if you want to close these gaps

Roughly in priority order:

1. Fix the CIK-list wiring bug (§3.1) — unlocks fundamentals, corporate actions, ownership, ESG, business relationships with no other code changes.
2. Fix the 4-5 frontend pages with outright broken URLs that affect the most-trafficked screens (landing page, alerts, news, settings).
3. ✅ **DONE (2026-07-09)** — Decide the AI story deliberately: either wire `src/services/ai/claude_client.py` into the 3 `/v1` routers + 8 `/v4/research/*` routers (replacing the stub/placeholder strings), or clearly label those fields as "not yet available" in the UI so they don't read as broken.
   `claude_client.py` is now wired into `llm_client.py` and used by all 3 `/v1` routers plus `research_qa.py`, `research_briefings.py`, `research_thesis.py`, and `fi_intelligence.py`. `embedding_client.py` is wired into semantic search. Fields fall back to honest `null`/`AI_DISABLED` (never a fabricated string) when `ANTHROPIC_API_KEY`/`GOOGLE_API_KEY` aren't set.
4. ✅ **DONE (2026-07-09)** — Fix `Position.market_value` computation — unblocks portfolio NAV, performance, and the compliance/risk ratios that depend on real NAV.
   `nav_engine.compute_position_valuation()` is now wired into `portfolios.py` (a new `_refresh_portfolio_positions()` helper, called from every position read/write path), and `performance_engine.py` is now wired into `portfolio_performance.py` for real TWR/MWR/risk-metric computation. Portfolio risk stress tests now also carry real per-position beta/duration instead of hardcoded 1.0/0.0.
5. ✅ **DONE (this session)** — Register every real-but-unscheduled connector (the 11 Pillar-3 connectors from `924e640`, plus the pre-existing treasury-curve/credit-spreads connectors) in `src/scheduler/batch_config.py`, and document all of them with example commands in `CONNECTING_TO_REAL_DATA.md` §6. This was the single biggest remaining "invisible but real" gap — working code nobody running the setup guide would ever discover.
6. ✅ **DONE (this session)** — Wire `moat_history` (real per-period series), `FIMarketBriefing` (yield-curve + credit, via `scripts/generate_fi_briefings.py`), and company-primer `ownership_data` (real 13F join) — three more orphaned-engine/table gaps closed with existing free data, no new connectors needed.
7. ✅ **DONE (this session, follow-up)** — `slide_outline` (documented free-form-JSON convention + per-section adapter, see §6) and `ThemesDashboard.tsx` (real `/summary`/`/securities` endpoints + fixed the array-vs-object bug + wired an actual drill-down UI, see §6) are both fixed.
8. Remaining, deliberately not attempted: forward consensus estimates/guidance (blocked — needs a paid data source); FinBERT install (`transformers`/`torch`, a dependency decision, not a data-wiring one); `macro_theme_scores` has no producer anywhere — a new theme-exposure-scoring engine would need to be designed, not just reconnected (see §6); bond-issuance-dependent parts of FI issuer profiles (no connector exists, needs a source decision).
9. Everything remaining in the "orphaned engine" category (§4–§6) is optional, lower-urgency polish — each one is a single well-defined wiring task (call the engine from a batch job or router), not a rewrite.
