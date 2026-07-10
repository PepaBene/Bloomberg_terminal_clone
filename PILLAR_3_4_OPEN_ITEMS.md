# Pillar 3 & Pillar 4 — Open Items Tracker

**Date:** 2026-07-10
**Method:** Every issue in `PILLAR_3_AUDIT_REPORT_v2.md` (147 issues) and `PILLAR_4_AUDIT_REPORT_v2.md` (157 issues) was re-verified against the **current** codebase — not re-read from the documents, but re-derived from source (file:line citations below). Two intervening fix passes are already reflected in the codebase: a data-wiring pass (`DATA_WIRING_AUDIT.md`, 2026-07-09) and a separate, undocumented frontend/router/engine remediation pass whose commits weren't captured in any audit doc but are visible as inline code comments citing the original issue IDs (e.g. `# E-019 fix`, `# P4-F-013`).
**Purpose:** a single place to see what's genuinely still broken vs. what's been fixed since the v2 audits, so future work isn't wasted re-discovering already-closed issues or, worse, assuming closed issues are still open.

**Status legend:** 🔴 STILL OPEN · 🟡 PARTIALLY FIXED · ✅ FIXED (listed only where the original doc's premise itself was wrong, or as section totals)

---

## Table of contents

1. [Pillar 3 — Engines](#pillar-3--engines)
2. [Pillar 3 — Routers & app.py registration](#pillar-3--routers--apppy-registration)
3. [Pillar 3 — Models & schemas](#pillar-3--models--schemas-important-caveat-below)
4. [Pillar 3 — Frontend](#pillar-3--frontend)
5. [Pillar 4 — Routers & app.py registration](#pillar-4--routers--apppy-registration)
6. [Pillar 4 — Engines](#pillar-4--engines)
7. [Pillar 4 — Models & schemas](#pillar-4--models--schemas)
8. [Pillar 4 — Frontend](#pillar-4--frontend)
9. [Cross-cutting themes / where to start](#cross-cutting-themes--where-to-start)

---

## Pillar 3 — Engines

*(36 issues in original audit — 30 FIXED, 4 PARTIALLY FIXED, 2 STILL OPEN)*

### 🔴 Still open

| ID | File:line | Issue |
|---|---|---|
| E-035 | `src/engines/news_entity_linker.py:216,530` | Fuzzy-match threshold (0.85) hardcoded; the pipeline orchestrator calls `fuzzy_match(full_text, names)` with no way to override it — no config/env tunability. |
| E-036 | `src/engines/earnings_surprise_intelligence.py:343` | `compute_revision_implications()`: `abs(eps_surprise_pct) + abs(revenue_surprise_pct)` — still flat equal-weight, unlike the sibling fix in `earnings_surprise_engine.py` (E-015, which got materiality weights `{eps:0.5, revenue:0.3, ebitda:0.2}`). This file's parallel function was never updated to match. |

### 🟡 Partially fixed

| ID | File:line | What's fixed / what's not |
|---|---|---|
| E-013 | `earnings_surprise_intelligence.py:458-467,524-532` vs. `:343,583-585` | `generate_key_takeaways`/`generate_narrative_template` now guard `None` before `abs()`. But `compute_revision_implications()` (called from `analyze_earnings_event` at 583-585) takes non-Optional params and still crashes with `TypeError` when `eps.surprise_pct`/`revenue.surprise_pct` is `None` (zero-consensus case). |
| E-017 | `business_model_engine.py:124-130` | Still returns hardcoded `50.0` for <3 data points; now logs a `logger.warning(...)` but the `RevenueQuality` dataclass has no caller-visible flag — downstream consumers can't distinguish "neutral" from "no data." |
| E-023 | `macro_scenario_engine.py` (wired) vs. `macro_thematic_engine.py` (orphaned) | `macro_scenario_engine.py` is genuinely wired into `research_themes.py` (`_compute_theme_scores_for_entity`, scenario endpoints). But `macro_thematic_engine.py` — a separate file with its own `compute_inflation_exposure`/`score_all_themes`/`screen_by_theme` — has **zero** non-test importers anywhere. Fully orphaned still. |
| E-034 | `insider_signals.py:89-104,274-278` vs. `:260` | Per-transaction date parsing is now guarded with try/except + fallback formats. But `as_of = date.fromisoformat(as_of_date_str)` at line 260 remains **unguarded** — a malformed `as_of_date_str` argument still crashes. |

All other 30 engine issues (E-001–E-012, E-014–E-016, E-018–E-022, E-024–E-033) are confirmed **FIXED** with dedicated code changes (e.g. real bounds checks, corrected weight formulas, priority-based tie-breaking, unique-insider counting, CRITICAL-alert rate-limit exemption). Not re-listed here — see prior audit for original descriptions if needed.

---

## Pillar 3 — Routers & app.py registration

*(38 issues — 27 FIXED, 3 PARTIALLY FIXED, 3 STILL OPEN; SQLAlchemy version check confirmed `.desc().nulls_last()` works fine on the installed SQLAlchemy 2.0.51, so R-001/R-019's original "crash" premise was moot even before the fix)*

### 🔴 Still open

| ID | File:line | Issue |
|---|---|---|
| R-023 | `global_intelligence.py:945-982` | `GET /global/commodities/{code}/supply-demand` is still the naive price-deviation heuristic (explicit `# PLACEHOLDER` comment in code). Note: a **different**, sibling endpoint (`POST /global/commodities/{code}/scenario`, lines 985-1063) genuinely does delegate to `commodity_intelligence.run_commodity_scenario` — don't confuse the two. |
| R-028 | `economic_calendar.py:139-141,180,218-221,258-261` | Hardcoded event-type filter lists, never validated against actual DB values. |
| A-008 | `app.py:112-131` (comments) | Router registration order ("Security Finder must be registered BEFORE Securities") still enforced only by code comments, no automated check. |

### 🟡 Partially fixed

| ID | What's fixed / what's not |
|---|---|
| R-005 | `governance_intelligence.py:134-135` now calls `compute_governance_score` (which internally invokes `detect_red_flags`) and `compute_board_diversity`. Still never calls `compute_pay_alignment`, `detect_board_interlocks`, or `analyze_shareholder_proposals` from this router — those 3 of 6 governance functions remain unexposed via API. |
| A-003 | Router-import failures now `logger.warning(...)` instead of silent `except: pass` — visible in logs now, but still don't fail startup or surface to an operator without active log monitoring. |
| A-006 | A dedicated handler now returns 422 for `ValueError`. Still no distinction for 409/other cases — everything else still falls through to generic 500. |

All other 32 items (R-001–R-004, R-006–R-022, R-024–R-027, R-029–R-030, A-001, A-002, A-004, A-005, A-007) are confirmed **FIXED**.

---

## Pillar 3 — Models & schemas ⚠️ important caveat below

*(15 issues — 4 STILL OPEN, 11 PARTIALLY FIXED, 0 fully fixed at both layers)*

> **Critical cross-cutting finding:** the ORM model files (`src/models/*.py`) were edited to address nearly every item below — several even carry comments citing the issue ID (e.g. `# M-003: cascade-delete versions`). **None of these edits are backed by an Alembic migration.** `migrations/versions/033, 043, 047, 065, 066, 070` (the ones that actually define these tables) were never updated — zero `ALTER TABLE`/`alter_column` calls exist anywhere in `migrations/versions/`, and there's no `metadata.create_all()` fallback in the app. **For any database actually built by running migrations, these are Python-type-hint-only changes — the real table schema is unaffected.** Every "PARTIALLY FIXED" item below is partial for exactly this reason unless otherwise noted.

### 🔴 Still open (no fix at either layer)

| ID | File:line | Issue |
|---|---|---|
| M-001 | `src/models/semantic_search.py:39` | `embedding_vector: Mapped[dict \| None] = mapped_column(JSONB)` — still no pgvector `VECTOR` type/extension anywhere in the repo. `embedding_client.py` now produces real embeddings, but they're stored as JSONB and similarity is computed via pure-Python loops (`semantic_search_engine.py:175`, `vector_search.py:15`), not a real vector index. |
| M-004 | `morning_briefing.py:22,47` | `MorningBriefing`/`BriefingPreference.user_id` still plain `String(100)`, no FK (no users table exists to reference). |
| M-005 | `investment_thesis.py:26` | `InvestmentThesis.analyst_id` still no FK; `# TODO: Add ForeignKey("users.id")...` comment unchanged. |
| M-012 | `intelligent_alerts.py:57-61` | Only a non-unique dedup index added; comment explicitly states a hard unique constraint was deliberately avoided to not block legitimate retries. Duplicate alerts can still be inserted. |

### 🟡 Partially fixed (model-only, no migration — or incomplete even at model layer)

| ID | Model-layer status | Migration-layer status |
|---|---|---|
| M-002 (narrow VARCHAR) | Widened: `SentimentScore.source_type`→50, `SearchDocument.source_type`→50, `FilingSection/FilingDiff.section_key`→60, `DetectedAnomaly.anomaly_type`→60 | Migrations 033/065/043 still create the original narrow columns (20/25/20) |
| M-003 (ThesisVersion cascade) | `ondelete="CASCADE"` added | Migration 066 FK has no `ondelete` |
| M-006 (ConsolidatedAlert `updated_at`) | Added | Migration 070 has no such column |
| M-007 (SearchDocument/Query `updated_at`) | Added to both | Migration 065 has neither |
| M-008 (ThesisVersion `updated_at`) | Added | Migration 066 has no such column |
| M-009 (SentimentAggregate DESC index) | `Index(..., postgresql_ops={"as_of_date":"DESC"})` added | Migration 033 has no such index |
| M-010 (SearchDocument source index) | `Index("idx_search_documents_source", "source_type", "source_id")` added | Migration 065 has no such index |
| M-011 (cascade on 5 entity_id FKs) | `ondelete="CASCADE"` added to all 5 (SentimentScore, SentimentAggregate, FilingSection, FilingDiff, ArticleEntityLink) | Migrations 033/043/047 have none of them |
| M-013 (NewsArticle content nullability) | `summary` → `nullable=False` in model | Migration 047 still creates it nullable (model change unenforced); `body_text` still nullable at **both** layers, untouched |
| M-014 (JSONB documentation) | Partial: `alert_categories`/`key_drivers`/`primary_risks`/`valuation_scenarios` now have inline shape comments | `fi_profile` and all 5 JSONB columns in `morning_briefing.py` still undocumented; no `TypedDict` exists anywhere in `src/` — the actual audit ask (typed schemas) was never done |
| M-015 (SentimentScore unique constraint) | `Index(..., unique=True)` added on `(entity_id, source_type, source_reference)` | Migration 033 has only non-unique indexes — duplicate ingestion still possible in a real deployment |

**Bottom line for this section:** until someone writes and runs a migration reconciling `src/models/*.py` with `migrations/versions/`, treat all 11 "partially fixed" items as **effectively still open in any deployed database**.

---

## Pillar 3 — Frontend

*(14 issues — 11 FIXED, 2 PARTIALLY FIXED, 1 STILL OPEN; DATA_WIRING_AUDIT's "clean reference implementation" claim for these pages is mostly right but oversold — verified two exceptions below)*

### 🔴 Still open

| ID | File:line | Issue |
|---|---|---|
| F-001 (partial) | `frontend/src/pages/research/AnomalyView.tsx:20-38,45-46` | Still has hardcoded `anomalyStats`/`anomalies` (AAPL/JPM/TSLA/META/XLE/PFE/VIX) used via `(apiActive as any)?.stats ?? anomalyStats` — the exact original bug pattern, untouched. The other 8 of 9 F-001 pages (`FilingsView`, `GovernanceDashboard`, `CompanyIntelligence`, `PrimerView`, `ThesisBuilder`, `AnalystQA`, `SemanticSearch`, `ThemesDashboard`) are genuinely clean. |
| F-013 | All 9 Pillar-3 pages except `AnalystQA.tsx` | Pervasive `as any` casts remain (FilingsView 6, CompanyIntelligence 8, AnomalyView 4, GovernanceDashboard/PrimerView/ThesisBuilder 3 each, SemanticSearch/ThemesDashboard 1 each). Low severity, never claimed fixed by any doc. |

### 🟡 Partially fixed

| ID | Detail |
|---|---|
| F-012 | Fixed on `GovernanceDashboard`, `CompanyIntelligence`, `PrimerView`, `ThesisBuilder`, `ThemesDashboard` (top-level hooks — some secondary hooks still lack `isError`). **`FilingsView.tsx` is fully open** — none of its 5 hooks destructure `isLoading`/`isError`, despite being listed as a "clean reference implementation" in `DATA_WIRING_AUDIT.md` §8.4. `AnomalyView.tsx`'s secondary `useCriticalAnomalies()` also lacks it. `AnalystQA`/`SemanticSearch` use imperative calls with local state, not hooks — not a violation. |

**Also found, out of the original 14-item scope but worth flagging:** `frontend/src/pages/fi/FIIntelligence.tsx` and `frontend/src/pages/research/BriefingView.tsx` still contain hardcoded Apple/NVDA transcript and theme data — the underlying pattern wasn't eradicated app-wide, just from the 9 files the v2 audit happened to name.

All other items (F-002 through F-011, F-014) are confirmed **FIXED**, including the fabricated AnalystQA chat history, the AAPL/NVDA entity-ID defaults, the SemanticSearch hardcoded results, and ThemesDashboard's full rebuild (real drill-down endpoints + the array-vs-object bug fix).

---

## Pillar 4 — Routers & app.py registration

*(48 issues — most FIXED; SQLAlchemy `await session.delete()` claims in P4-R-003/P4-R-028 were themselves false positives — it's a real coroutine method, not a bug)*

### 🔴 Still open

| ID | File:line | Issue |
|---|---|---|
| P4-R-013 | `portfolio_performance.py:826` | Report generation still a hardcoded 2-field stub (`{"report_type":..., "portfolio_name":...}`), no `reporting_engine.py` wiring. |
| P4-R-014 | `portfolio_performance.py:963-1006` | `_parse_*_detail()` helpers `.get()` on JSONB items with no dict-type guard → `AttributeError` risk on schema drift. |
| P4-R-015 | `portfolio_performance.py` (4 export paths) | CSV export via raw f-string concat, no escaping/quoting. |
| P4-R-024 | `portfolio_risk.py:1291` | `set_target_allocation()` still takes untyped `body: dict`. |
| P4-R-025 | `portfolio_risk.py:253-357` | Geographic detail silently returns `[]`; missing vs. empty indistinguishable. |
| P4-R-026 | `portfolio_risk.py:1022` | `is_active == True  # noqa: E712` unchanged. |
| P4-R-032 | `portfolio_watchlists.py` (3 sites) | No fallback label when entity join is null. |
| P4-R-033 | `portfolio_upload.py:21-30` | Still `Query` params, not real multipart file upload. |
| P4-R-034 | `portfolio_upload.py:71` | `parsed_holdings` dict-shape silently drops to empty list. |
| P4-R-037 | `backtesting.py:144-156` | `compare_backtests()` returns 9 fields vs. ~20 in single-result view. |
| P4-R-040/041 | `quant.py` | Unguarded `uuid.UUID()` parse; silent length-truncation on mismatched series, no warning logged. |
| P4-R-042 | `risk.py:338,350` | `benchmark` query param accepted but fully ignored — beta always uses the fixed market benchmark (worse than originally reported: not even echoed correctly). |
| P4-R-043 | `technical_backtest.py:29` | Unused `session` dependency. |
| P4-R-044 | `fi_risk.py` | 3 of 4 endpoints still have no `session` param — can't look up bond data from DB. |
| P4-A-004 | `app.py` / `quant.py:44` | No router serves `/v4/quant/*` — quant stuck at its own baked-in `/v2/analytics/quant` prefix. |

### 🟡 Partially fixed

| ID | Detail |
|---|---|
| P4-R-009 | Fixed in `add_position()` (real threshold guard). `create_transaction()`'s BUY averaging (line 858) still uses the old weak `if total_shares else Decimal("0")` guard — same rounding-artifact risk. |
| P4-R-023 | Missing-key case now defaults `drift_pct` to `0.0`. Explicit `null` in JSONB still crashes `abs(pd_entry.drift_pct)` at line 1266. |
| P4-R-035 | No longer lies (`PENDING` instead of fake `COMPLETED`), but **no batch worker exists anywhere** — backtests now honestly sit at PENDING forever instead of dishonestly reporting fake zeros. Functionally still non-operational. |
| P4-A-002 | `risk.py` still mounted at `/v2/analytics/risk`, not `/v4` — but appears to be a deliberate Pillar-2 classification; frontend correctly targets the real `/v4` portfolio-risk router, so no live breakage found. |

All other router/app-registration items (P4-R-001/002/003/004–008/010–012/016–022/027–031/036/038/039, P4-A-001, P4-A-003) are confirmed **FIXED**.

---

## Pillar 4 — Engines

*(54 issues — 12 FIXED, 2 PARTIALLY FIXED, 3 confirmed not-bugs-on-recheck, 37 STILL OPEN)*

> **Verified false positive:** P4-E-030 (MWR/IRR "sign bug") — `compute_mwr()`'s convention (terminal value as positive inflow) is the correct standard XIRR formulation. Confirmed independently by re-deriving the math; matches `DATA_WIRING_AUDIT.md`'s own conclusion. Also not bugs: P4-E-008 (documentation-only), P4-E-020 (operator-precedence claim — code is correct as written).

### 🔴 Still open

**Unvalidated inputs / edge cases:**
- P4-E-001 `nav_engine.py:104-144` — no negative `cash_balance` validation
- P4-E-002 `nav_engine.py:160-163` — no `nav_yesterday<=0` guard (only zero-check)
- P4-E-004 `nav_engine.py:63-98` — no `cost_basis_per_share` positivity check
- P4-E-032 `performance_engine.py:95` — `cf["date_offset"]` KeyError risk, no validation
- P4-E-033 `performance_engine.py:438,448` — string date comparison fragility
- P4-E-052 `portfolio_parser.py:25-59` — no try/except around malformed CSV parsing

**Math approximations left as documented gaps:**
- P4-E-005 `attribution_engine.py:335-360` — arithmetic (not geometric/Carino) multi-period attribution linking
- P4-E-006 `attribution_engine.py:387-390` — average weights across periods, not BOP weights
- P4-E-007 `attribution_engine.py:175-238` — no `sum(weights)≈1.0` validation
- P4-E-009 `attribution_engine.py` — no residual warning when Brinson BHB residual is large
- P4-E-012 `e5_risk.py:90-102` — `_max_drawdown` returns `0.0` on empty list (should be `None`)
- P4-E-014 `e5_risk.py:216` — hardcoded `sqrt(252)` trading days
- P4-E-015 `e5_risk.py:355` — Amihud `×1e6` magic constant, undocumented
- P4-E-016 `e5_risk.py:335-342` — bid-ask proxy uses high-low only, misses overnight gaps
- P4-E-017 `e5_stress_scenarios.py:46-82` — missing `equity_shock`/`spread_shock_bps` fields (note: the portfolio-level `portfolio_risk_engine.py:22-51` already has these — different file, not fixed here)
- P4-E-019 `backtester.py:26,102-119` — drawdown duration field mislabeled `duration_days`, assumes daily periods
- P4-E-026 `e7_quant.py:242` — Blume weight `0.67` hardcoded, undocumented
- P4-E-031 `performance_engine.py:125` — `r_new` clamped to max 10.0 (1000% return ceiling)
- P4-E-036 `portfolio_analytics.py:127-133` — HHI assumes weights sum to 1.0
- P4-E-037 `portfolio_analytics.py:75` — explicit `sector=None` grouped as `None` key, not "Unknown"
- P4-E-038 `portfolio_analytics.py:319-320` — uses `/30.44`/`/365.25` instead of `relativedelta`
- P4-E-039 `portfolio_risk_engine.py:126-141` — VaR weight normalization is a 5%-tolerance heuristic, not exact
- P4-E-041 `portfolio_risk_engine.py:562` — 2-sigma drift threshold hardcoded, not tunable
- P4-E-042 `attribution_engine.py:293-295` — factors missing from `factor_returns` silently dropped via set intersection

**Silent degradation:**
- P4-E-022/023/024 `concentration_risk.py:100-133,260-262` — unknown risk-level strings silently score as low-risk; `geographic_spread=0` doesn't trigger high-risk classification
- P4-E-044 `whatif_engine.py:277-278,293,295` — missing weight/beta/volatility silently defaulted (1.0/current_vol)
- P4-E-046 `whatif_engine.py:142-143` — `simulate_trades()` returns `[]` silently on invalid NAV
- P4-E-047 `whatif_engine.py:178-179` — `proposed_nav` negative fallback hides the underlying error

**Misc:**
- P4-E-048 `watchlist_monitoring.py:304-346` — filed_date sort/compare risk on explicit `None` values (missing-key case is mitigated; `None` value is not); dead `_sort_key` helper left behind
- P4-E-049 `watchlist_monitoring.py:450,503,691` — `datetime.utcnow()` naive, still used in 3 places
- P4-E-050 `technical_backtester.py:238-245` — position sizing compounds off remaining capital (geometric decay), undocumented as intentional
- P4-E-051 `technical_backtester.py:204-209` — last signal wins on same timestamp, no conflict resolution

### 🟡 Partially fixed

| ID | Detail |
|---|---|
| P4-E-025 | Real `statsmodels.adfuller` used when available (`e7_quant.py:500-513`); fake heuristic fallback still exists when statsmodels isn't installed, honestly labeled. |
| P4-E-027 | Real Engle-Granger-adjusted `statsmodels.coint` used when available (`:603-609`); non-statsmodels fallback still uses plain (unadjusted) ADF critical values. |

**Fixed at the wiring layer only:** P4-E-003 (`nav_engine.compute_position_valuation()` still sets `weight=0.0` internally by design at `nav_engine.py:93`, but the caller `portfolios.py::_refresh_portfolio_positions` now correctly renormalizes real weights — so this is a non-issue end-to-end).

All other engine items (P4-E-010/011/013/018/021/028/029/034/035/043/045/053/054) are confirmed **FIXED**.

---

## Pillar 4 — Models & schemas

*(29 issues — 7 FIXED, 4 PARTIALLY FIXED, 18 STILL OPEN)*

### 🔴 Still open

| ID | File:line | Issue |
|---|---|---|
| P4-M-001–007 | `src/schemas/{portfolio,position,transaction_schema,nav,performance,backtesting,attribution}.py` | **All 7 Decimal→float precision-loss groups still open.** Every financial schema still serializes `Numeric`/`Decimal` DB columns as `float`. Docstrings now acknowledge the tradeoff, but nothing changed structurally — every monetary field across portfolios/positions/transactions/NAV/performance/backtesting/attribution is affected. |
| P4-M-013 | `src/models/nav_snapshot.py:44-66` | `CorporateActionQueue` still has zero `relationship()` definitions to `NAVSnapshot`/`Position`. |
| P4-M-015 | `src/models/attribution.py:19` | Unique constraint covers `(portfolio_id, attribution_type, period_end)`, not `(portfolio_id, period_start, period_end)` as needed. |
| P4-M-019 | `src/models/portfolio_upload.py` | Still no `user_id` field; the only construction site (`portfolio_upload.py:31-39`) never even sets the existing `created_by` field either. |
| P4-M-020 | `src/models/portfolio_watchlist.py` | No `UniqueConstraint(user_id, watchlist_name)`. |
| P4-M-021–024 | `nav_snapshot.py`, `performance.py`, `attribution.py`, `backtesting.py` | No `CHECK` constraints for date ordering (`period_start<=period_end`/`start_date<=end_date`) anywhere. |
| P4-M-025 | `src/models/quant.py:34-35` | No range `CheckConstraint` on `r_squared`/`adj_r_squared`. |
| P4-M-026 | All models | No `Enum`/`CHECK` constraints on any status/type column. |
| P4-M-028 | `src/models/backtesting.py:13-31` | `BacktestRun` still has no `user_id`/`owner_id` — any user can read any backtest by ID. |

### 🟡 Partially fixed

| ID | Detail |
|---|---|
| P4-M-009 | `ON DELETE CASCADE` added only to `Position.portfolio_id`/`Transaction.portfolio_id`. NAV/Performance/Attribution/Risk/Backtesting FKs to `portfolios.id` still plain, no cascade — `session.delete(portfolio)` will still fail against those tables. |
| P4-M-010 | `Portfolio` now has `positions`/`transactions` relationships, still none to `NAVSnapshot`/`PerformanceSnapshot`/`AttributionResult`. |
| P4-M-027 | `Transaction.created_by` added; `Position`, `PortfolioWatchlistEntry`, `BacktestRun` still have none. `modified_by` doesn't exist anywhere. |
| P4-M-029 | `Portfolio.deleted_at` added (no `is_deleted` flag). No other model has any soft-delete field. |

**The one genuine full fix:** P4-M-008 — an `Entity` model/table now actually exists (`src/models/entity.py`), so `PortfolioWatchlistEntry.entity_id`'s FK resolves.

All other model items (P4-M-011, P4-M-012, P4-M-014, P4-M-016, P4-M-017, P4-M-018) are confirmed **FIXED** (relationships on Position/Transaction; composite indexes via UniqueConstraint on performance/portfolio_risk/nav_snapshot; indexed `user_id` on watchlist).

---

## Pillar 4 — Frontend

*(23 issues — 12 FIXED, 5 PARTIALLY FIXED, 6 STILL OPEN)*

### 🔴 Still open

| ID | Issue |
|---|---|
| P4-F-009 | `endpoints.ts:820-827` `BENCHMARKS.list = '/v1/benchmarks'` — **no benchmarks router/model exists anywhere in the backend at all**, not a prefix mismatch. Breaks `CustomIndexBuilder.tsx` and all quant benchmark hooks permanently. |
| P4-F-010 | No `QUANT` endpoint object in `endpoints.ts`; also newly found: `ANALYTICS.factorExposure` matches no real backend route either. |
| P4-F-011 | No `TECHNICAL_BACKTEST` endpoints defined; zero frontend references to the feature at all. |
| P4-F-012 | No `FI_RISK` portfolio-level endpoints defined; zero frontend references. |
| P4-F-022 | `as any` casts remain in 7 of 9 pages (heaviest: `RiskPage.tsx`, 13 instances). |
| P4-F-023 | `PortfolioList.tsx:94-97` — the TODO error-toast is still literally unimplemented, byte-for-byte identical to the original finding. Same `console.warn`-only pattern repeats on CSV preview/commit failures. |

### 🟡 Partially fixed

| ID | Detail |
|---|---|
| P4-F-013 | `PortfolioDetail.tsx` — NAV-history `Math.random()` generator now dead code, hooks now prefer real data via `??`. But hardcoded portfolio identity ("Core Growth", $2,458,320), 10 static holdings, sector allocation, and all 4 KPI metrics (Sharpe/Drawdown/etc.) still have zero hook backing at all. |
| P4-F-014 | `PerformancePage.tsx` — all 3 `Math.random()` generators confirmed dead code. KPI/calendar/risk-metrics/attribution table hardcoded fallbacks unchanged. |
| P4-F-015 | `RiskPage.tsx` — all 8 hooks now genuinely consumed via `??` merge. `api.request()` bypass at line 131 remains (one action), though its error is now surfaced to the user (a genuine improvement). Hardcoded fallback constants remain; heaviest `as any` usage of all 9 pages. |
| P4-F-017 | `BacktestDashboard.tsx` — hardcoded data removed, error handling added (no longer empty catch). **But** `BACKTESTING` endpoints in `endpoints.ts` (`/v2/analytics/backtest/strategies\|run\|history\|compare`) match **no real backend route** (`backtesting.py` only exposes `/v1/analytics/backtest`, `/{id}/results`, `/holdings`, `/compare`) — page is permanently empty. **New bug introduced**: `dynamicKpis` computes off the permanently-empty results array, producing `"+undefined%"`/`"NaN%"` in the KPI row. |
| P4-F-021 | 3 of ~6 originally-silent failure spots (`RiskPage`, `BacktestDashboard`, `CustomIndexBuilder`) now show inline errors. `PortfolioDetail.tsx`, `WatchlistView.tsx`, `PortfolioList.tsx` remain fully silent (`console.error`/`console.warn` only). No toast component exists anywhere in the app — all error surfacing, where present, is inline `<div>`s. |

All other frontend items (P4-F-001–008, P4-F-016, P4-F-018, P4-F-019, P4-F-020) are confirmed **FIXED**.

---

## Cross-cutting themes / where to start

Ranked by leverage (impact of fix ÷ effort), not by original severity label:

1. **Models/schemas are the weakest layer in both pillars, and Pillar 3's "fixes" are a trap.** Someone edited `src/models/*.py` extensively but never touched `migrations/versions/`. Anyone deploying from migrations gets none of those 11 Pillar-3 model fixes. **First action: reconcile models vs. migrations with a new Alembic revision**, or the model edits are dead weight.
2. **Decimal→float precision loss (Pillar 4, P4-M-001–007)** — untouched across all 7 financial schema groups. Every monetary number in the portfolio system loses precision on serialization. High blast radius, moderate effort (schema type change + serializer).
3. **Backtesting is a dead end in both pillars.** Pillar 4's `backtesting.py` now honestly returns `PENDING` instead of fake `COMPLETED`, but **no batch worker exists anywhere** to ever advance it — and the frontend (`BacktestDashboard.tsx`) calls endpoints that don't even exist on the backend, with a newly-introduced `NaN`/`undefined` KPI display bug on top. This is the single most broken end-to-end feature surfaced across both audits.
4. **Frontend endpoint/backend mismatches with zero backend implementation** (not just wiring bugs): Pillar 4's benchmarks (`P4-F-009`), quant (`P4-F-010`), technical-backtest (`P4-F-011`), FI-risk (`P4-F-012`) all point at routes that were never built. These need a scoping decision (build the backend, or remove the dead frontend code) rather than a wiring fix.
5. **`AnomalyView.tsx` (Pillar 3) is the one page where the original F-001 mock-data bug is fully unfixed** — worth a 10-minute fix to match the pattern already applied to the other 8 pages in the same audit.
6. **Small, cheap, high-clarity fixes** ready to knock out in one pass: `risk.py`'s ignored `benchmark` param (P4-R-042), `fi_risk.py`'s missing `session` params (P4-R-044), `portfolio_watchlists.py`'s missing entity fallback labels (P4-R-032), `PortfolioList.tsx`'s never-implemented TODO toast (P4-F-023), `earnings_surprise_intelligence.py`'s unguarded `abs(None)` crash path (E-013) and unweighted surprise sum (E-036).

---

*This file supersedes nothing — `PILLAR_3_AUDIT_REPORT_v2.md`, `PILLAR_4_AUDIT_REPORT_v2.md`, and `DATA_WIRING_AUDIT.md` remain the historical record of what was originally found and what the 2026-07-09 wiring pass changed. This file is the current-state cross-reference layered on top.*
