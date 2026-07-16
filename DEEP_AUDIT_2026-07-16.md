# Deep Codebase Audit — Data → Analysis → Calculation → Wiring → Reachability

**Date:** 2026-07-16
**Method:** Six parallel specialist audits, each deriving findings from **current source** (`file:line`), using the prior `PILLAR_*`/`DATA_WIRING_AUDIT.md` docs (dated ~2026-07-09/11) only as a checklist to verify and correct. The app was actually imported and its OpenAPI table generated; ingestion/scheduler/frontend wiring traced end-to-end.

---

## 0. The one pattern that explains almost everything

**The code is real and the plumbing compiles — but three separate "last-mile" layers are disconnected, so a large fraction of built functionality never executes in a running deployment.** There is very little that is *crashing*; there is a great deal that is *inert*.

Ranked by how much they hollow out the product:

1. **No scheduler is deployed, and the core master is unscheduled anyway.** `docker-compose.yml` runs only postgres/redis/elasticsearch — there is **no scheduler/cron service**. Even if you run `run_scheduler.py` by hand, the **entity/security master loaders (EDGAR, GLEIF, OpenFIGI) are not in `batch_config.py`** — everything downstream builds CIK/ticker lists from those tables and silently no-ops until the master is seeded out-of-band. And `run_scheduler.py` **crashes on the 6 jobs that carry CLI args** (it treats `"run_analytics_batch.py --engine e1"` as a single filename). → Pillar 1 §A.
2. **Analytics engines with correct math are never invoked or never scheduled, and several result tables have no writer at all.** Only 4 analytics jobs are on cron (e1, e2_multiples, e2_wacc, e3). DCF/comps/quant/risk populate only via a one-time empty-table auto-seed. Attribution, VaR, concentration, factor exposure, drift, compliance-results, corporate-action-queue engines exist and are correct **but nothing calls them and nothing writes their tables** → those endpoints are permanently empty. → Pillars 2 & 4.
3. **The AI layer is entirely inert in a default install.** `anthropic`, `google-genai`, and `transformers` are **not in `pyproject.toml`**, so every LLM narrative returns `None`, semantic search degrades to a substring scan over an un-ingested corpus, and "FinBERT sentiment" is a keyword lexicon. The configured model id `"claude-sonnet-5"` is also invalid. → Pillar 3.
4. **The frontend can't reach ~10 routed pages and silently shows hardcoded numbers on ~8 more.** The command bar is wired to nothing (typing does nothing), NavRail sub-items are decorative text, and several pages substitute `mock*` constants with no demo banner when the (often-empty) real endpoints return nothing. → Frontend.

**Good news, verified from source:** all 90 routers are registered, the app imports cleanly, OpenAPI renders 713 operations with zero collisions, no `.nullslast()`/undefined-name/nonexistent-column crashes remain, `Math.random()` is gone from every chart path, and the whole portfolio **create→store→value** chain plus stress-testing, benchmarks, technicals, and the deterministic intelligence engines (SWOT/moat/Porter/business-model) are genuinely wired and correct. Most prior-doc 🔴 findings are **fixed** and the docs are now stale.

---

## 1. Dimension 1 — Is the data PRESENT, CORRECT, and USEFUL? (Pillar 1)

Writers are overwhelmingly real now. The remaining gaps:

### 🔴 No writer at all → endpoint empty forever
- **GEOGRAPHIC segments** — `src/ingestion/edgar_segments.py:183` hardcodes `segment_type="BUSINESS"` for every row; three consumers filter on `"GEOGRAPHIC"` (`competitive.py:315`, `company_intel_p2.py:177`, `research_primers.py:132`). All geographic-revenue-breakdown surfaces are permanently blank.
- **Composite `esg_score`** — nothing anywhere sets the overall score (only `governance_score`, `environmental_score`, `social_score` get written). ESG "overall score" is null forever.

### 🟠 Real writer, but never scheduled → empty in production
- **Core entity/security master** — `ingest_edgar.py`, `ingest_gleif.py`, `ingest_openfigi.py` are **absent from `batch_config.py`** (Makefile-only). This is the root of the cascade; entity hierarchy/history, resolution queue, and `EquityDetails` populate only when the master is seeded manually.
- **M&A deals, IPO events, N-PORT fund holdings, corporate bonds/TRACE** — real writers, Makefile-only, not on cron → `/deals`, `/ipos`, `/fund-holdings`, `/fi/bonds` stay empty in a normal deployment.
- **`compute_shares_outstanding.py`** — real, fully orphaned (not in cron *or* Makefile).
- **`ingest_earnings_surprises.py`** — dead skeleton (`_assemble_pairs` returns `[]`); Makefile target points at it. Real earnings path is `ingest_earnings.py`.

### 🟡 Correctness / operational
- **Scheduler runner broken for arg-bearing jobs** (`run_scheduler.py` `_run_script`) — 6 jobs crash every fire; `--validate` fails.
- **Untested-against-live-data connectors** (flagged in-code): guidance, consensus estimates, subsidiaries, bond issuances, agency bonds, N-PORT, TRACE live path. Correctness unverifiable in-sandbox.
- **`agency_bonds.py`** no-ops until `FHLB_OF_DATA_URL` set; **ECB/BOE** central-bank series unvalidated; ESG environmental/controversies are honestly-labeled disclosure *proxies*, not vendor ratings.

*(Full domain-by-domain PRESENT/CORRECT/SCHEDULED/SURFACED matrix in the Pillar-1 agent output.)*

---

## 2. Dimensions 2 & 3 — Is everything ANALYZED and CALCULATED? (Pillar 2, + engines in 3 & 4)

Engines mostly do real arithmetic on real inputs. The gaps are wrong formulas, broken read paths, and orphaned/un-scheduled compute.

### 🔴 Not calculated (stub / hardcoded where real math intended)
- **Quant factor-performance table hardcoded to zeros** — `analytics.py:1600-1608` (mtd/qtd/ytd/1y/sharpe/ic = 0.0).
- **`rule_of_40`, `pipeline_proxy` permanently `None`** — wrong metric keys (`e1_industry_kpis.py:112,315` read names RatioEngine never emits). **REIT FFO** understated (`gain_on_sale` key never exists). Energy/mining get zero industry KPIs (`e1_industry_kpis.py:303` returns `[]`).
- **Attribution / VaR / concentration / factor-exposure / drift / compliance-results / corporate-action-queue** (Pillar 4) — engines are correct but **have zero callers and their tables have no writer**; every read endpoint returns empty/`None`. Drift additionally **fabricates zeros** (`portfolio_risk.py:1312-1318`).

### 🟡 Incorrect (wrong numbers)
- **[HEADLINE] Comps EV-multiple implied price inflated by ×shares (~1e9)** — `e2_comps.py:446` multiplies an already-total EBITDA/revenue by shares; corrupts `comps_composite_implied_price`, upside/downside, and football-field (`e2_football_field.py:358`). Highest-leverage single bug.
- **Ohlson O-Score OENEG coefficient wrong** — `e13_credit_quality.py:104` uses `0.285` (the INTWO weight) instead of `−1.72`; pushes P(default) the wrong way for insolvent issuers.
- **E5 historical stress ignores the scenario window** (`e5_risk.py:675-697`) and **echoes the shock constant with no beta/exposure** (`:319-331`) — every security gets identical stress P&L; rate scenarios silently skipped.
- **E7 beta/correlation aligns series by position, not date** (`e7_quant.py:290`); **two E1 growth metrics ×100 mis-scaled** (`e1_ratios.py:727,968`); **DuPont ROE single-quarter, un-annualized** (`e1_dupont.py:132`); **T-bill discount yield uses wrong basis** (`treasury_analytics.py:81`).
- **Screening filters on ANY historical period, not latest** (`e4_screening.py:511`) → stale/false matches; **`altman_zone` unscreenable** → deep-value screen always empty.

### 🟠 Orphaned / broken read paths (data computed but unreadable, or never computed)
- **CompositeScoreEngine is dead code** — never in `ENGINE_GROUPS`; `composite_scores` never written; 5 endpoints (`/composites`, `/earnings-quality`, `/financial-strength`, `/dividend-safety`, `/value-trap`) 404. Also has a case + dict/list mismatch even if invoked.
- **`/ttm/{id}`** 404s (period label `TTM_{date}` vs reader `"TTM"`); **`/multiples/{id}/history`** empty (case mismatch); **`calculation_lineage` `/audit`** endpoints always 404 (no writer); **`yield_curve_bootstrap.py`** entirely orphaned (and mixed-basis-buggy).
- **DCF / comps / football_field / trends / industry_kpis / risk / quant / flows not on cron** — go stale between XBRL filings (recompute triggers on XBRL refresh only, never on new EOD prices).
- **Pillar-4 orphaned engines with zero refs**: `whatif_engine.py` (no route/page at all), `trade_list_engine.py`, `portfolio_analytics.py`, and the performance-engine period functions (MTD/QTD/YTD/rolling) — so the `period` query param is decorative on every performance endpoint.

---

## 3. Dimension 3b — What the "AI" actually is (Pillar 3)

Three nominal AI backends, **all non-functional in a default install**:
- **LLM narrative (Claude)** — `anthropic` not in `pyproject.toml`, not importable; model id `"claude-sonnet-5"` invalid → every summary/pitch/Q&A answer is `None`, `ai_enabled` always False.
- **Embeddings (Gemini) → semantic search** — `google-genai` not installed; nothing batch-indexes documents → search is `chunk_text ILIKE '%q%'` ordered by recency over an empty corpus. Three separate search stacks exist (`semantic_search_engine`, `vector_search`, ES `indexer`), all orphaned.
- **Sentiment (FinBERT)** — `transformers` not installed → always the keyword lexicon.

**Orphaned intelligence engines** (real, tested, zero production callers; routers ship thinner inline reimplementations): morning-briefing, analyst-QA, anomaly-detection, transcript, earnings-surprise, all three news engines (dedup/link/propagate), investment-thesis. **No scheduled briefing or anomaly job** → those surfaces are empty until a user manually POSTs a scan. **Fake-intelligence** surfaced as real: hardcoded "AI-suggested" search queries (`research_search.py:171`), canned Q&A follow-ups (`research_qa.py:166`), sector-templated "company theme exposure", template-string scenario narratives.

**Genuinely working & wired:** `company_intel_p2` (business-model/management/revenue/growth), `competitive` (SWOT/moat/Porter/concentration), keyword sentiment (scheduled hourly), news backfill (scheduled), filing intelligence (EDGAR-classified). These are deterministic rule/threshold computation over real data — real, just not "AI."

---

## 4. Dimension 4 — Is data WIRED and DISPLAYED in the frontend?

Backend plumbing is clean (all 90 routers registered, app imports, 713 ops, no collisions). The frontend is where display gaps live:

### 🟠 Silent hardcoded-mock fallback (no demo banner — fabrication reads as real)
`RiskPage` (VaR/concentration/stress/compliance/factor/correlation/drift, `:122-174`), `PerformancePage` (attribution/factor-attribution, `:175-195`), `ValuationDashboard` (DuPont + full DCF panel, `:99-134`), `PortfolioList`/`PortfolioDetail`, `RiskDashboard` (sector concentration), `FinancialStatements`, `IndustryDetail`. Because the matching backend tables are the never-written ones from §2, these mocks are what users actually see.

### 🔴 Click-actions that 404
- Custom Stress Test → `POST /v4/portfolios/{id}/risk/stress/custom` (**no such route**; only historical/hypothetical) — `RiskPage.tsx:309`.
- What-If → `/v4/portfolios/{id}/what-if` (**no route**) — `PortfolioDetail.tsx`.

### 🟢 Verified clean
No `Math.random()` in any chart/table path (all removed). Most empty-states are honest (`DemoModeBanner`/`EmptyState`): Screener, Treasury, Credit, Commodity/Country/Political/Global, IPO, News, Flows, MorningBrief.

### Inverse gap — built backend, no frontend consumer
Entire compliance/drift suite, performance attribution/contributors/reports/exports, sentiment, earnings transcripts, economic calendar, several `fi_*` analytics families, technical_studies, corporate_actions, money_market have endpoints with **no UI**. `endpoints.ts` is a ~900-line aspirational catalog where **342 constants resolve to no backend route** (harmless but misleading as a wiring map).

---

## 5. Dimension 5 — Are all PAGES REACHABLE? (no gaps)

**The command bar is inert** — `TopBar.tsx:590` mounts `<CommandBar>` with no `onSearch`/`onSelect`/`results` props; `parseCommand` + `useCommandBar.executeCommand` are fully built but wired to nothing. The primary Bloomberg-style nav/lookup surface does nothing. **NavRail sub-items are decorative** (`FlyoutTooltip` renders non-interactive `<div>`s). So any page without an in-page `navigate()` link is URL-only.

### Fully orphaned pages (routed, no nav entry, no in-page link, dead command bar)
`/deals` (DealsView), `/market/ipo` (IPOMonitor), `/custom` (CustomData), `/quant` (QuantDashboard) — and because it's the only referrer, the whole quant subtree: `/quant/backtest`, `/quant/index-builder`; `/research/themes` (ThemesDashboard — omitted from `ResearchHub.CARD_ROUTES`). All are functional pages hitting real endpoints — just unreachable by clicking.

### Reachable only by typing the URL (no click path)
Company subtree: `/company/financials`, `/valuation`, `/credit`, `/intelligence`, `/esg`, `/governance` (no company tab strip). Also `/fi/intelligence`, `/fi/bonds/:cusip` (BondInventoryTable rendered without `onBondClick` — rows inert), `/macro/yield-curve`, `/macro/central-banks`, `/global/countries|commodities|political`, `/sector/:gicsCode` (SectorView has no drill-down navigate), `/portfolio/:id/performance`, `/portfolio/:id/risk`.

---

## 6. Prioritized fix list (highest leverage first)

**Make the product actually run (deployment/scheduling):**
1. Add a scheduler service to `docker-compose.yml` (or a cron), and **fix `run_scheduler.py` arg-splitting** so the 6 arg-bearing jobs don't crash.
2. **Schedule the entity/security master** (`ingest_edgar`/`gleif`/`openfigi`) in `batch_config.py` — nothing downstream has data without it.
3. Schedule the orphaned-but-real connectors you want live: M&A, IPO, N-PORT, TRACE (+ decide TRACE/agency-bond source).

**Fix wrong numbers (correctness):**
4. **Comps `×shares` EV bug** (`e2_comps.py:446`) — corrupts comps + football-field for every issuer.
5. **Ohlson OENEG coefficient** (`e13_credit_quality.py:104`), **E5 stress** (window + beta/exposure), **E7 date alignment**, **two E1 ×100 metrics**, **screening latest-period filter**, **altman_zone screenability**.
6. Broken read paths: **wire CompositeScoreEngine** into batch (+ fix case/shape), **`/ttm` label**, **`/multiples/history` case**.

**Compute the Pillar-4 analytics that are declared but never run:**
7. Invoke + persist attribution, VaR, concentration, factor exposure, drift, compliance results (engines already correct); add a scheduled NAV-capture job so performance history isn't traffic-dependent.

**Wire the frontend the user can't reach or is being misled by:**
8. **Wire the command bar** (`onSearch`/`onSelect` → `useCommandBar.executeCommand`).
9. Add click paths to the ~10 orphaned/URL-only pages (company tab strip, nav entries for Deals/IPO/Quant/Custom/Themes, `onBondClick`, portfolio perf/risk links).
10. Replace silent `mock*` fallbacks with `DemoModeBanner`/empty-states (RiskPage, PerformancePage, ValuationDashboard DuPont/DCF, PortfolioList/Detail, RiskDashboard, FinancialStatements); remove or implement the two 404 click-actions (custom stress, what-if).

**Decide the AI story (Pillar 3):**
11. Either add `anthropic`/`google-genai`/`transformers` to deps + fix the model id and stand up doc indexing, **or** stop labeling the deterministic engines "AI" and remove the inert LLM/embedding/FinBERT branches. Also replace the hardcoded "AI-suggested"/"quality"/"follow-up" constants.

---

## 7. Where the prior audit docs are now wrong (so you don't re-chase closed items)
The `PILLAR_*_v2.md` (dated ~2026-04) and `DATA_WIRING_AUDIT.md`/`PLATFORM_INTEGRATION_AUDIT_REPORT.md` (~2026-07-09/11) are **stale**: the `.nullslast()` crash cluster, `executives.py` `.in_(select())`, corporate-actions `security_id`, `EntityRelationship` naming collision, hardcoded relevance scores, and `Math.random()` chart fabrication are all **fixed** in current source. Router registration is 100% clean. Treat those docs as a historical checklist only — this document supersedes them.
