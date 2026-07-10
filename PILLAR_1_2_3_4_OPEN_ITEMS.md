# Pillar 1, 2, 3 & 4 — Open Items Tracker

**Date:** 2026-07-10
**Primary source of truth: `DATA_WIRING_AUDIT.md`.** Per explicit direction, the per-pillar `PILLAR_N_AUDIT_REPORT_v2.md` documents are treated as **stale, superseded catalogs** — useful as an exhaustive line-by-line bug list to check off against current code, but not as the authority on what "done" looks like. Where `DATA_WIRING_AUDIT.md` and a `PILLAR_N_AUDIT_REPORT_v2.md` disagree, `DATA_WIRING_AUDIT.md`'s framing (real/wired vs. stubbed/orphaned/fabricated) wins, and the Pillar 1 section below is organized data-wiring-first for that reason — code-level bug status is secondary detail underneath it.
**Method:** Every issue in `PILLAR_1_AUDIT_REPORT_v2.md` (243 issues), `PILLAR_2_AUDIT_REPORT_v2.md` (98 issues), `PILLAR_3_AUDIT_REPORT_v2.md` (147 issues), and `PILLAR_4_AUDIT_REPORT_v2.md` (157 issues) was re-verified against the **current** codebase — not re-read from the documents, but re-derived from source (file:line citations below). For Pillar 1 specifically, a same-day `PILLAR_1_FIXES.md` claims to have fixed every `DATA_WIRING_AUDIT.md` Pillar-1 finding — that self-report was independently re-verified against actual code (see below); two of its claims don't hold up. Other intervening fix passes already reflected in the codebase: the main `DATA_WIRING_AUDIT.md` pass (2026-07-09), a further Pillar-2 commit (`29687c2`, 2026-07-08) that postdates it, and a separate, undocumented frontend/router/engine remediation pass whose commits weren't captured in any audit doc but are visible as inline code comments citing the original issue IDs (e.g. `# E-019 fix`, `# P4-F-013`, `[Bug 42 fix]`, `[Bug 73 fix]`).
**Purpose:** a single place to see what's genuinely still broken vs. what's been fixed, so future work isn't wasted re-discovering already-closed issues or, worse, assuming closed issues are still open.

**Status legend:** 🔴 STILL OPEN · 🟡 PARTIALLY FIXED · ✅ FIXED (listed only where the original doc's premise itself was wrong, or as section totals)

**Adversarial verification pass (2026-07-10, same day):** every "still open" and "partially fixed" item below (~150 items) was independently re-checked by five agents instructed to actively try to refute each claim — find a guard that prevents the crash, an unreachable code path, a misstated file:line, or evidence the claim is simply wrong. Result: **3 confirmed false positives** (all in Pillar 4 engines — struck through and explained inline where they appear) and **~13 items needing a correction** (wrong crash mechanism, an overstated "any model"-style claim, a reachability caveat, a naming nit, etc. — each flagged inline as "⚠️ Correction"). Everything else (135+ items) held up exactly as described, including two claimed frontend "regressions" (Pillar 2 Bugs 79 and 82) that were traced end-to-end from backend schema through to the exact unguarded `.map()` crash site. Treat unmarked items as double-verified; items marked with a correction note as accurate in substance but adjusted in detail.

---

## Table of contents

1. [Pillar 1 — Data wiring & ingestion (primary lens)](#pillar-1--data-wiring--ingestion-primary-lens)
2. [Pillar 1 — Routers (code-level)](#pillar-1--routers-code-level)
3. [Pillar 1 — Engines & app.py](#pillar-1--engines--apppy)
4. [Pillar 1 — Models & schemas](#pillar-1--models--schemas)
5. [Pillar 1 — Frontend](#pillar-1--frontend)
6. [Pillar 2 — Path mismatch & E1/E2 engines](#pillar-2--path-mismatch--e1e2-engines)
7. [Pillar 2 — E3/E4 engines & peer service](#pillar-2--e3e4-engines--peer-service)
8. [Pillar 2 — Routers, models, batch pipeline, app-level](#pillar-2--routers-models-batch-pipeline-app-level)
9. [Pillar 2 — Frontend](#pillar-2--frontend-includes-genuine-regressions)
10. [Pillar 3 — Engines](#pillar-3--engines)
11. [Pillar 3 — Routers & app.py registration](#pillar-3--routers--apppy-registration)
12. [Pillar 3 — Models & schemas](#pillar-3--models--schemas-important-caveat-below)
13. [Pillar 3 — Frontend](#pillar-3--frontend)
14. [Pillar 4 — Routers & app.py registration](#pillar-4--routers--apppy-registration)
15. [Pillar 4 — Engines](#pillar-4--engines)
16. [Pillar 4 — Models & schemas](#pillar-4--models--schemas)
17. [Pillar 4 — Frontend](#pillar-4--frontend)
18. [Cross-cutting themes / where to start](#cross-cutting-themes--where-to-start)

---

## Pillar 1 — Data wiring & ingestion (primary lens)

*(`PILLAR_1_FIXES.md`'s 26 claims re-verified against current code: 15 VERIFIED, 9 PARTIALLY VERIFIED, 2 FALSE/OVERSTATED, plus coverage gaps `PILLAR_1_FIXES.md` never mentions.)*

### 🔴 False / overstated claims — these need real follow-up, not just a re-read

| Claim | Reality |
|---|---|
| **"Corporate actions `security_id` fix"** — `src/ingestion/edgar_8k.py` | **Does not do what's claimed.** The connector was actually switched to write `EightKEvent` (a different model with no `security_id` column at all — confirmed `src/models/filing_intelligence.py:91-119`), not `CorporateAction` with `security_id` now populated. `CorporateAction` — the table `GET /securities/{id}/corporate-actions` actually reads — has **zero writers anywhere in the codebase**. The endpoint is now permanently empty, which is *worse* than the original audit's "security_id always null" finding (empty result vs. wrong filter). |
| **"SegmentData — XBRL segment-fact connector"** — `src/ingestion/edgar_segments.py` + `scripts/ingest_segments.py` | The connector class (`EdgarSegmentsConnector`) is real, but **`scripts/ingest_segments.py` does not exist anywhere in the repo** — confirmed via direct filesystem search. The `Makefile`'s `ingest-segments` target points at this nonexistent module and would fail with `ModuleNotFoundError` if run. This means the geographic-breakdown feature (see Pillar 1 Frontend section — the `/segments?segment_type=GEOGRAPHIC` endpoint plumbing is genuinely fixed) has no way to ever get real data into `SegmentData` — the endpoint will work but stay permanently empty. |

### 🟡 Partially verified — real code, but not scheduled or documented (the "orphaned engine" pattern)

Every item below has genuine, correct transform/load logic and passes its own tests, but is only reachable via a manual `make` target — none are registered in `src/scheduler/batch_config.py` or documented in `CONNECTING_TO_REAL_DATA.md`. This is the exact "real but undiscoverable" failure mode `DATA_WIRING_AUDIT.md` flagged repeatedly for Pillar 3 before that pillar's connectors got scheduled — it has now recurred in Pillar 1's newest work:

- **Tier 3 connectors** (6 of 7): capital structure, credit ratings, treasury securities, executives, FOMC meetings, central-bank policy (ECB/BOE series present but genuinely untested against live payloads, as the fix doc itself discloses). Capital structure and credit ratings additionally lack the unit tests `PILLAR_1_FIXES.md` claims exist.
- **Only credit spreads (FRED BofA/ICE OAS) is fully wired end-to-end** — scheduled in `batch_config.py` and documented in `CONNECTING_TO_REAL_DATA.md` §6. This is the one Tier-3 connector to actually replicate.
- **Tier 2 rollup scripts** (all 4): `OwnershipSummary`, `TechnicalStudyValue`, `ESGTemperatureScore`, debt-maturity rollup — all real, all runnable, all have passing tests, none scheduled/documented.
- **CIK-list wiring** — mechanically correct for 5 of 6 scripts, but `ingest_corporate_actions.py`'s branch feeds the now-dead `Edgar8KConnector→EightKEvent` path (see false-claim row above), undercutting its practical value specifically for corporate actions.
- **Entity hierarchy/GLEIF parents** — genuinely wired, but GLEIF-only coverage; EDGAR-sourced entities have no comparable parent linkage.

### 🔴 Coverage gaps — `DATA_WIRING_AUDIT.md` Pillar-1 findings that `PILLAR_1_FIXES.md` never addresses at all

- **FRED money-market rates** (`fred_money_market.py` stub `extract()`) — not mentioned, still stubbed.
- **3 of 4 `expand=` security detail fields** — `FixedIncomeDetails`, security-level `CreditRating`, `CallPutSchedule` all still have zero writers. Only `EquityDetails.shares_outstanding` (the 4th field) was addressed.
- **`EntityRelationship` vs. `BusinessRelationship` naming collision** — `EntityRelationship` (what `/entities/{id}/relationships` reads) still has zero writers; the real, working data lives in the differently-named `BusinessRelationship` table. Not touched.
- **Corporate actions calendar dates** (`ex_date`/`record_date`/`payment_date` never set) — moot given `CorporateAction` has zero writers regardless (see false-claim row).
- Money-market rates, corporate bonds/TRACE, and bond issuances/agency bonds are at least *honestly* flagged as incomplete in the Tier-3 table ("needs a source decision"/"needs FINRA credentials") — better than a silent gap, but still open.

### ✅ Genuinely fixed (verified against code, not just the self-report)

CIK-list wiring mechanics (5 of 6 scripts) · bond-analytics coupon conversion (no double-conversion) · Decimal-serialized-as-JSON-string schema fix · `security_finder` LIKE injection · `/find/suggest` 422 · `debt_maturity` API rewrite (latest-profile-or-404) · real relevance scoring (entities/securities/security_finder, replacing hardcoded `score=1.0`) · resolution queue wired for UNCERTAIN verdicts · entity history recording · `shares_outstanding` real XBRL fetch · `fi_yield_curve` dead import removed · trading calendars (real NYSE holiday engine, wired into `make seed`).

---

## Pillar 1 — Routers (code-level)

*(74 issues across 30 router files — 62 FIXED, 6 PARTIALLY FIXED, 4 STILL OPEN across both halves; the audit's two headline CRITICAL crash-bug claims — `resolution.py`'s auth-bypass and `executives.py`'s invalid `.in_(select())` — are both confirmed fixed, along with every `.nullslast()` crash cluster.)*

### 🔴 Still open

| ID | File:line | Issue |
|---|---|---|
| P1-R-024 | `fundamentals.py` (5 endpoints) | Count query and data query still built as two independent `select()` statements with filters applied twice in parallel — structural divergence risk unaddressed (currently kept in sync by hand). |
| P1-R-030 | `filing_intelligence.py` | `desc` still not imported — latent only, not a live bug (file never calls the bare `desc()` function, only `.desc()` as a method). |
| P1-R-047 | `fi_yield_curve.py:273` | `df_tenor_years` dict still hardcoded inline, duplicates the module-level `_DF_COLS` keys — can silently drift. |
| P1-R-050 | `fi_bonds.py` (⚠️ correction: 7 endpoints, not 6 — `bond_analytics` was missed in the original count) | Unnecessary `.scalars().unique()` on non-collection queries — cosmetic, not a correctness bug. |

### 🟡 Partially fixed

| ID | Detail |
|---|---|
| P1-R-003 | Real relevance scoring now exists, but there's still no actual Elasticsearch — search still runs ILIKE against Postgres. A real ES indexer (`src/search/indexer.py`) exists but is orphaned, not wired into `entities.py`/`securities.py`/`security_finder.py`. |
| P1-R-022 | `request_id` now real (`uuid.uuid4()`), but `processing_time_ms` still hardcoded `0` — never computed for `reference.py` list endpoints. ⚠️ Correction: the live logic is in `src/api/reference.py` — `src/api/routers/reference.py` is just a re-export barrel. |
| P1-R-029 | Fixed in `_build_diff_response` (now uses `" /// "`), but `get_filing_diff_summary` still joins AI summaries with the original unescaped `" | "`. |
| P1-R-038 | `capital_structure.py`'s main endpoint now distinguishes missing-entity vs. missing-data 404s, but `get_capital_structure_summary` still returns one generic message for both cases. |
| P1-R-065 | `ipo.py` — `.upper()` normalization added, but the underlying `IPO_PIPELINE_STATUSES` constant is still hardcoded magic strings with no enum — the added normalization is a no-op safety net, not the real fix. |
| P1-R-073 | `market_movers.py`'s main `/movers` endpoint now correctly 404s on no data, but `/movers/summary` still fakes `snapshot_date=date.today()` on empty data — indistinguishable from a genuine zero-mover day. |

**New findings beyond the original 74** (discovered while verifying, not in the original audit): `fi_spreads.py` imports `compute_ig_hy_differential` but never calls it — same dead-import class as the fixed P1-R-056. `market_movers.py` was completely rewritten to compute live from `EODPrice` (a good fix), but **broke 4 of its 5 tests** (⚠️ correction: confirmed by actually running `pytest tests/test_api/test_market_movers_api.py -v` — the file has 5 tests total, not 6; result was 4 failed / 1 passed) in `tests/test_api/test_market_movers_api.py`, which still target the now-abandoned `MarketMoversSnapshot` model — including a silent contract change (empty case now 404s instead of the old 200/empty-list the tests expect).

All other router items (P1-R-001, 002, 004–021, 023, 025–028, 031–037, 039–046, 048, 049, 051–064, 066–072, 074) are confirmed **FIXED**, including every `.nullslast()` crash (corporate_actions, relationships, capital_structure, ma_deals, ipo, fund_holdings), the `executives.py` invalid SQLAlchemy syntax, and the `resolution.py` auth-bypass-via-failed-import pattern (verified: no try/except around the auth import exists anymore, single authenticated definition per endpoint).

---

## Pillar 1 — Engines & app.py

*(22 issues — 15 FIXED, 2 PARTIALLY FIXED, 5 STILL OPEN)*

### 🔴 Still open

| ID | File:line | Issue |
|---|---|---|
| P1-E-006 | `corporate_action_engine.py:314-336` | `match_corporate_actions_to_holdings()` fully implemented but still has zero production callers — dead code (only referenced from its own test). |
| P1-E-008 | `filing_diff.py` `_is_numerical_only_change()` | Still over-strips hyphenated numbers — live-reproduced: `"The 3-month period ended"` → `"The -month period ended"`. |
| P1-E-014 | `eight_k_engine.py::parse_eight_k_items` | Still returns `[]` with no signal distinguishing genuine no-items from a parse failure. |
| P1-E-018 | `market_movers.py` engine | Still silently drops null price/prior-close/volume rows with zero logging of how many were excluded. |
| P1-E-019 | `market_movers.py` engine | `most_active` still silently returns `[]` when all securities have `volume=None`, no "quiet day" vs. "no data" signal. |

### 🟡 Partially fixed

| ID | Detail |
|---|---|
| P1-E-009 | A `ChangeClassification` StrEnum was added and used inside `classify_change()`, but the function's return type is still annotated `str`, and sibling fields (`ParagraphAlignment.type`, `SectionDiffResult.classification`) remain raw unconstrained string literals. |
| P1-E-017 | `resolve_issuer_to_parent()` now has a real `min_confidence=0.5` floor — but the entire `issuer_linkage` module has zero production callers, so the None-handling question this item raised doesn't currently arise anywhere in the running app. |

All other engine items (P1-E-001–005, 007, 010–013, 015, 016) and all 3 app.py items (P1-A-001–003 — CORS, lifespan/startup auto-seed, safe `getattr()` on request-state fields) are confirmed **FIXED**.

---

## Pillar 1 — Models & schemas

*(31 issues — 13 FIXED, 13 PARTIALLY FIXED [model-only, no migration — the same recurring pattern seen in every other pillar], 5 STILL OPEN)*

### 🔴 Still open

| ID | File:line | Issue |
|---|---|---|
| P1-M-002 | `src/models/entity.py:86`, `src/resolution/matcher.py` | Audit's original premise (confidence stored 0–100, column caps at 9.99) is factually wrong — confidence is consistently 0–1 scale throughout the codebase. But a **real** bug remains underneath: `matcher.py` computes confidence to 4 decimal places while `Numeric(3,2)` only stores 2 — silent truncation on save (e.g. `0.8534` → `0.85`), untouched in both model and migration. |
| P1-M-025 | `src/models/ipo.py:49-50,65` | `lead_underwriters`/`co_managers`/`source_filings` still unvalidated JSONB — schema now types `lead_underwriters` for output, but `co_managers`/`source_filings` aren't even exposed, and nothing stops invalid structures on write. |
| P1-M-026 | `src/models/ma_deals.py` | `acquirer_financial_advisors`/`regulatory_approvals_required` still unvalidated JSONB. (Note: audit's cited `conditions_to_close` field doesn't exist in the model at all — stale reference, but the "no validation" complaint holds for the fields that do exist.) |
| P1-M-027 | `src/models/relationships.py:64` | `metadata_json` still unvalidated JSONB passthrough. |
| P1-M-030 | `src/models/yield_curve.py:103` | `tenor_years: Numeric(6,2)` still caps at 9999.99 years, unchanged at both model and migration level. |

### 🟡 Partially fixed (model edited, matching Alembic migration never written — same pattern as Pillar 2/3)

P1-M-005 through P1-M-010 (missing FKs on corporate_bond/capital_structure/debt_maturity/credit_rating — all added to models, none to migrations), P1-M-012 (Security→credit_ratings/call_put_schedule cascade added, but **no relationship at all exists** from `Security` to `EODPrice`/price history — untouched), P1-M-018 through P1-M-021 (composite indexes added to models only), P1-M-028 (`data_version` CHECK constraint model-only), P1-M-029 (`volume` changed to `BigInteger` in the model, but migration still creates `Numeric(20,0)` — a fresh DB from migrations still has the wrong type).

**Cross-cutting note:** `PILLAR_1_FIXES.md`'s Decimal→float schema change (to fix Pydantic's Decimal-as-JSON-string serialization bug) only touches `corporate_bond.py`'s market-data fields and *all* numeric fields in `capital_structure.py` — it doesn't conflict with P1-M-001–004 (different files, already correctly typed `Decimal`), but it does reintroduce float precision loss specifically in `capital_structure.py` (including `confidence_score` there), an issue outside this audit's original 31 items but worth knowing about.

All other model items (P1-M-001, 003, 004, 011, 013–017, 022–024, 031) are confirmed **FIXED** at both model and migration level (or needed no migration — pure ORM relationship declarations).

---

## Pillar 1 — Frontend

*(36 issues — hooks: 10 FIXED/1 PARTIAL/2 OPEN + geographic-breakdown build spec now BUILT; pages: 16 FIXED/2 PARTIAL/5 OPEN, all still-open page items are `as any` casts)*

### 🔴 Still open

| ID | File:line | Issue |
|---|---|---|
| P1-F-007 | `frontend/src/api/hooks/useSecurities.ts:88-96` | `useSecurityTranslate()` still a `useMutation` wrapping a POST — named like a read, implemented as a write. |
| P1-F-013 | `frontend/src/hooks/useFI.ts` (~50 hooks) | Still no explicit per-hook `staleTime` — relies solely on the global 5-minute `QueryClient` default, unlike the sibling `api/hooks/useFiBonds.ts` which sets `STALE_24H`/`STALE_1H` explicitly. |
| P1-FP-008, 010, 012, 014, 016, 018 | `FinancialStatements.tsx`, `OwnershipDashboard.tsx`, `FilingsView.tsx` (company/), `ESGDashboard.tsx`, `GovernanceDashboard.tsx`, `FIDashboard.tsx` | `as any`/`as any[]` casts on API responses remain on all 6 pages that originally had them — none were cleaned up in the mock-data remediation pass. |

### 🟡 Partially fixed

| ID | Detail |
|---|---|
| P1-F-008 | Cache invalidation scoped from the bare `['entities']` root down to `['entities','list']`/`['entities','detail']` — better, but `useUpdateEntity` has the specific `id` available in its mutation variables and still doesn't use it for a precise `['entities','detail',id]` invalidation. |
| P1-FP-006 | `FinancialStatements.tsx` — Apple hardcode (`'Apple Inc.'/'AAPL'`) removed, but the replacement `const company = {name:'Loading...', ticker:''}` is **still a static constant never wired to any hook** — the header permanently reads "— Loading..." regardless of which entity is selected. No longer deceptive-as-Apple, but still broken. |
| P1-FP-009 | `OwnershipDashboard.tsx` — mock holder/summary/short-interest/activist objects emptied (no more Vanguard/BlackRock/Elliott names), but two fabricated precise numbers remain hardcoded and unconnected to any API: `insiderPct={0.07}` and `institutionalPct={60.8}`. |

**The headline finding is resolved:** none of the 10 Pillar 1 pages still show Apple/AAPL data as a fallback — every hardcoded mock dataset (CompanyOverview, FinancialStatements, OwnershipDashboard, FilingsView, ESGDashboard, GovernanceDashboard, FIDashboard, BondDetail, IPOMonitor, DealsView) has been emptied, and 4 of the 10 pages (CompanyOverview, BondDetail, IPOMonitor, DealsView) are now fully clean with no remaining issues at all. No "Demo mode" disclosure banner exists on any of them (unlike `ScreenerDashboard.tsx` elsewhere in the app) — the chosen remediation was "show nothing/placeholder" rather than "disclose it's fake," which is honest but less informative to a user than a banner would be.

**Geographic breakdown (Section 7 build spec) — plumbing BUILT, but blocked by the Pillar-1 data-wiring gap above.** Backend `GET /v1/entities/{id}/segments?segment_type=GEOGRAPHIC` now exists exactly per the audit's recommended approach, and `useGeographicBreakdown` correctly points at it. But since `scripts/ingest_segments.py` doesn't exist (see Data Wiring section above), `SegmentData` never gets populated — the endpoint works but will return empty results forever until that connector gap is closed.

All other frontend items (P1-F-001–006, 009–012, P1-FP-001–005, 007, 011, 013, 015, 017, 019–023) are confirmed **FIXED**, including the duplicate-hook-definitions cleanup (one file is now a re-export barrel), all 4 non-null-assertion URL bugs, both barrel `index.ts` files, and every one of the 10 hardcoded Apple mock datasets.

---

---

## Pillar 2 — Path mismatch & E1/E2 engines

*(Part 1 path mismatch + 35 engine bugs — essentially all FIXED; this is the cleanest layer across all three pillars)*

**Universal path mismatch (Part 1) — FULLY FIXED.** All 14 `ANALYTICS.*` path pairs in `frontend/src/api/endpoints.ts` now match `src/api/routers/analytics.py`/`screening.py` route decorators exactly. This was the audit's headline "blocks everything" finding — genuinely resolved.

**All 18 E1 bugs (Bugs 1–18, ratios/DuPont/TTM/trends/industry KPIs) — FIXED**, each with an explicit `[Bug N fix]` code comment: employee-count metrics removed, negative-equity flag propagated to ROIC/ROCE/DuPont composites, manual zero-division guards replaced with `safe_divide()`, fiscal-year-based period matching, dynamic trend-ratio discovery, TTM fallback view, months-covered off-by-one fixed, startup field-mapping validation, all-None metrics still emitted with `INSUFFICIENT_DATA`, minimum-4-points stdev gate, zero-variance→`HIGHLY_CONSISTENT`, 180-day momentum-comparison gap, REIT gain-on-sale/maintenance-capex sourced from real data with `ESTIMATED` fallback flags, junk placeholder KPIs removed, insurance combined-ratio proxy now flagged `ESTIMATED`.

**28 of 35 E2 bugs (DCF/WACC/Multiples/Comps/Football Field) — FIXED**, including the two highest-severity ones: Bug 19 (sensitivity grid now fully re-discounts explicit-period FCFs per cell, not just terminal value) and Bug 23 (size/country risk premiums now from real lookup tables). Also fixed: leverage_target param, exit-multiple terminal method, tax-rate fallback logic, shared E1/E2 metric-name constants, fiscal-year EPS matching, session.flush() after merge, peer-override ValueError on empty match, denominator metric-name alignment (`ttm_diluted_eps`, `bvps`, `dps` — confirmed these match real E1 output), `session.merge()` upsert for CompsResult, football-field EPS metric name, single-peer ±10% spread, sensitivity-grid JSON-array parsing, consensus_view field placement.

**Newer finding (post-audit) — FIXED.** DCF request-schema field names (`revenue_growth_rates` etc.) are now translated via an explicit `_rename` dict in `analytics.py` to the engine's real assumption keys — custom DCF assumptions are no longer silently dropped.

**`DuPontDecomposition` dead-table claim — resolved via architecture change, not a bug fix.** The dedicated `DuPontDecomposition` ORM table is still never constructed (confirmed dead code), but `/dupont/{id}` no longer depends on it — the endpoint was rewritten to read `AnalyticsResult` rows filtered by `metric_category="DUPONT"`, and `DuPontEngine` is wired into the batch pipeline's `e1`/`all` groups. No user-facing 404; `DATA_WIRING_AUDIT.md`'s "permanent 404" claim is stale.

### 🟡 Partially fixed

| Bug | Detail |
|---|---|
| 20 | Out-of-range CAGR ([-20%,+50%]) is now clamped to the nearest bound (fixed) rather than reset to flat 5%. But when historical CAGR is **unavailable entirely** (<2 years of data), it still falls back to a flat 5% with **no sector-median fallback** — that specific complaint remains open for the no-data path. `src/engines/e2_dcf.py:601-610` |
| 26 | Dividend-yield sign convention (`abs()`) is now documented via inline comments at `e2_multiples.py:300` and `e1_ratios.py:913`, but `e1_ratios.py:1275` (`dividend_yield_trailing`) still has no comment — relies on variable naming alone. |

---

## Pillar 2 — E3/E4 engines & peer service

*(19 issues — 18 FIXED, 1 PARTIALLY FIXED)*

**All 10 E3 quality-score bugs (Bugs 36–45) — FIXED**: shares-prior missing now flags `INSUFFICIENT_DATA` instead of assuming no dilution; negative equity now nulls out ROA-dependent F1–F4 instead of computing misleading values; Altman X4 field renamed to `altman_x4_value`+`altman_x4_description` (no longer misleadingly named); EBIT now includes interest income/expense adjustment; Beneish M-Score now requires all 8 components or returns `INSUFFICIENT_DATA` instead of biasing toward "not a manipulator"; AQI division-by-zero guarded; composite scores now prorate by available weight instead of penalizing missing data as 0; revenue-growth consistency now counts positive-years-out-of-5 instead of breaking on first negative year; `compute_credit_aware_financial_strength()` now actually called; composite persistence wrapped in try/except.

**5 of 6 E4 screening bugs — FIXED**: universe endpoints (S&P 500/Russell 1000) now seed on demand by actually running the screening engine; `ScreenerDashboard.tsx` now uses the real `useRunScreen()` mutation and `useScreenFields()` hook instead of hardcoded metrics; prebuilt library screen field names now match real `AnalyticsResult` metric names; Dividend Aristocrats screen now requires 25+ consecutive years and positive 1y/3y/5y growth, not just a single 5y>0 check.

**Peer service — all 3 bugs FIXED**, including a correction to `DATA_WIRING_AUDIT.md` itself: that later audit claimed the comps engine's percentile calculation had "a second, unfixed copy" still including the subject security in its own peer distribution. Verified via `git log -p`: this was fixed in commit `29687c2` (2026-07-08) — **three days after** `DATA_WIRING_AUDIT.md` was written (2026-07-05). Both percentile implementations (`peer_service.py::_percentile` and `e2_comps.py::_percentile_rank`) now correctly exclude the subject security.

**Bug 85 (screener "20 of 20" fake preview count) — FIXED.** Now shows an honest "Demo mode — backend unavailable" banner with `totalCount=null` instead of a misleading real-looking count.

### 🔴 Still open

| Bug | File:line | Issue |
|---|---|---|
| 46 | `frontend/src/pages/screener/ScreenerDashboard.tsx:123-135` vs `src/schemas/screening.py:44` | Field/operator name mapping was fixed (`metric→field`, `operator→op`, `valueTo→value2`), but the frontend still builds the payload as a top-level `{logic, filters: [...]}` instead of the backend's required `{filters: {logic, filters: [...]}}` wrapper — every screen run still gets a 422 and falls back to mock data. **The saving grace: this now correctly triggers the honest "Demo mode" banner (Bug 85, fixed) instead of silently showing fake data as real.** |

---

## Pillar 2 — Routers, models, batch pipeline, app-level

*(24 items — 17 FIXED, 4 PARTIALLY FIXED, 4 STILL OPEN)*

### 🔴 Still open

| Bug | File:line | Issue |
|---|---|---|
| 68 | `src/models/analytics.py:44` vs `migrations/versions/014_analytics_tables.py:34` | **Model-only fix, no migration** (same pattern as Pillar 3's model/migration gap). Model now declares `data_quality: String(100)`, but the migration that actually creates the table still has `String(20)`. Inserting a 35-char comma-joined flag string (`"NO_DCF_DATA,NO_COMPS_DATA,NO_52W_DATA"`) still fails/truncates on any database built from migrations. |
| 74 | `src/api/app.py:70`, `src/config.py:117` | No authentication enforced by default — `REQUIRE_AUTH: bool = False`. |
| — | `scripts/run_analytics_batch.py:55-65` (`ENGINE_GROUPS`) | **Batch pipeline scope gap confirmed still true.** `e2_dcf`, `e2_comps`, `e2_football_field`, `e5_risk`, `e7_quant` remain absent from every `--engine` choice including `all` — they only ever run live/on-demand per API request, never pre-computed or scheduled. |
| — | `src/api/routers/backtesting.py:22-58` | `POST /v2/analytics/backtest` still a stub — creates a `PENDING` `BacktestRun` row with a comment describing a batch worker that would advance it, but **no such worker exists anywhere** in `scripts/` or `src/scheduler/`. Rows never advance past PENDING. (Distinct from, but the same failure pattern as, Pillar 4's `/v1/analytics/backtest`.) |

### 🟡 Partially fixed

| Bug | Detail |
|---|---|
| 55 | Router-level category lowercasing is now case-robust in practice (neutralizes the original bug's effect). But the model declares a DB `CheckConstraint("metric_category = UPPER(metric_category)")` with no corresponding migration — model-only fix again. |
| 64 | `GET /screen/fields` now genuinely queries `SELECT DISTINCT metric_name FROM analytics_results` instead of a pure hardcoded list — but filters `engine_id IN ('E1','E2')` only, silently excluding live, populated E3 quality-score fields (`piotroski_f_score`, `altman_z_score`, `altman_zone`, `beneish_m_score`) from the screenable-fields response. |
| 73 | Startup lifespan handler now auto-seeds analytics via a background batch run when `AnalyticsResult` is empty — but by construction can't cover DCF/Comps/Football Field/E5/E7, since those aren't in any `ENGINE_GROUPS` value (same root cause as the batch-scope item above). |
| 77 | Silent `except: pass` → `logger.warning(...)` fix confirmed for the Pillar 3 router block. **Does not apply to Pillar 2 routers** (`analytics`, `screening`, `flows`, `risk`, `quant`, `scenario`) — those were never wrapped in try/except at all; a broken import there crashes the whole app at startup (fail-fast, arguably safer, but not the documented fix pattern). |

All other items (Bugs 56–63, 65–67 [indexes present in model though also missing from migrations — lower-severity than Bug 68 since a missing index degrades performance rather than breaking correctness], 69–72, the invalid `--engine e6` scheduled job, 75, 76) are confirmed **FIXED**. Notably: the batch runner was rewritten for per-chunk commits + idempotent resume via `ingestion_progress` tracking + per-security 30s timeouts; E3 import failures now crash loudly instead of silently skipping; CORS and DB-backed health checks are both present (though `allow_origins=["*"]` + `allow_credentials=True` together is spec-invalid and worth a follow-up).

---

## Pillar 2 — Frontend (includes genuine regressions)

*(21 items — 10 FIXED, 8 PARTIALLY FIXED, 3 STILL OPEN — and 2 of the 3 still-open items are new crash-risk regressions, not just unfixed originals)*

### 🔴 Still open — including new regressions worse than the original bug

| Bug | File:line | Issue |
|---|---|---|
| 79 | `ValuationDashboard.tsx:111,117`; `RatioDashboard.tsx:106`; `MultiplesOverTime.tsx:84` | **Regression.** Hardcoded `multiplesOverTimeData` array removed, but the replacement code reads a `.history` field that doesn't exist on the real backend response (`GET /v2/analytics/multiples/{id}/history` actually returns `data_points`). The raw non-array API object then gets passed into two components that call `.map()` with no `Array.isArray` guard — **will throw `TypeError` and crash the page** once a security with real multiples data loads. Worse than the original static-mock bug. |
| 80 | `ValuationDashboard.tsx` | Football field data (`apiFootball`/`activeFootballData`) is fetched and computed but **never rendered anywhere** — no `FootballField` component is imported or exists in the codebase at all. Dead code fetching data for a UI element that doesn't exist. |
| 82 | `ValuationDashboard.tsx:112`; `PeerScatter.tsx:92-131` | **Regression.** Hardcoded 5-peer fallback removed, but `activePeers = (apiPeers as any[]) ?? MOCK_PEER_SCATTER` is a bare type cast with no runtime check. The real backend (`GET /v2/analytics/ratios/{id}/vs-peers`) returns an **object** (`{comparisons: [...]}` of per-metric percentile aggregates), not an array of per-peer points at all. Once the API call succeeds, this object flows into `PeerScatter`, which calls `.map()` unguarded → **will throw `TypeError` and crash**. Even with a guard added, the backend doesn't return the right shape (`{ticker,x,y,marketCap}` points) for this to ever work — needs a new/different endpoint, not just a frontend fix. |

### 🟡 Partially fixed

| Bug | Detail |
|---|---|
| 81 | DCF sensitivity: frontend field-name reading fixed (snake_case), but `GET /v2/analytics/dcf/{id}/sensitivity` **doesn't exist in the backend at all** — always errors, matrix never shows real data. (The DCF response itself already contains `sensitivity_grid` sitting unused as an alternative source.) |
| 84 | Screening management paths are now individually correct, but `screens/library`/`screens/saved` return bare JSON arrays while the frontend still expects a `.screens` wrapper key (`apiPrebuilt?.screens`) — Prebuilt Screens panel and Load-screen modal never populate despite correct URLs. |
| 87 | `useFactorExposure`/`useTechnicalSignals` no longer permanently disabled (real `secId` now sourced from store) — but `GET /v2/analytics/factor-exposure/{id}` and `/technical-signals/{id}` don't exist in the backend at all, so Momentum Signals table stays permanently (honestly) empty. |
| 88 | Fake vol-surface formula removed, disclosure label "Illustrative — not from live data" added (both original complaints resolved) — but there's still no real backend wiring for vol-surface data at all. |
| 91 | Backtest KPI tiles now computed dynamically instead of hardcoded — but since `BACKTESTING.strategies`/`.run`/`.history` don't exist in the backend (real routes are a completely different `/v1/analytics/backtest` shape), the results array stays empty and 4 of 6 KPI tiles literally render `"+undefined%"`/`"NaN%"` — a new, more confusing failure mode than the old static mock numbers. |
| 93 | Strategy selector now wired to `useBacktestStrategies()` — but since that endpoint doesn't exist, it falls back to a now-**empty** array (was a static 6-option list before) — dropdown renders with zero options, arguably worse UX than before. |
| 94 | Property-name fix (`.benchmarks` before `.indices`) is correct, but `GET /v1/benchmarks` has no backend implementation at all (same root cause as Pillar 4's P4-F-009) — always 404s. |
| 95 | Now posts to a distinct `BENCHMARKS.create` path instead of the list endpoint — but that endpoint doesn't exist either; create-index always fails, now with a visible error message instead of silently. |

All other items (Bugs 78, 83, 85, 86, 89, 90 [same underlying fix as Pillar 4's P4-F-020], 92, 96, 97, 98) are confirmed **FIXED**.

---

## Pillar 3 — Engines

*(36 issues in original audit — 30 FIXED, 4 PARTIALLY FIXED, 2 STILL OPEN)*

### 🔴 Still open

| ID | File:line | Issue |
|---|---|---|
| E-035 | `src/engines/news_entity_linker.py:216,530` | Fuzzy-match threshold (0.85) hardcoded; the pipeline orchestrator calls `fuzzy_match(full_text, names)` with no way to override it — no config/env tunability. Confirmed accurate as a code fact, but note: this whole module also has zero production importers (test-only), same reachability caveat as E-013/E-034 below. |
| E-036 | `src/engines/earnings_surprise_intelligence.py:343` | `compute_revision_implications()`: `abs(eps_surprise_pct) + abs(revenue_surprise_pct)` — still flat equal-weight, unlike the sibling fix in `earnings_surprise_engine.py` (E-015, which got materiality weights `{eps:0.5, revenue:0.3, ebitda:0.2}`). This file's parallel function was never updated to match. The code-comparison is accurate; both engine files happen to be currently orphaned (no production importers) per the E-013 caveat below. |

### 🟡 Partially fixed

| ID | File:line | What's fixed / what's not |
|---|---|---|
| E-013 | `earnings_surprise_intelligence.py:458-467,524-532` vs. `:343,583-585` | `generate_key_takeaways`/`generate_narrative_template` now guard `None` before `abs()`. But `compute_revision_implications()` (called from `analyze_earnings_event` at 583-585) takes non-Optional params and still crashes with `TypeError` when `eps.surprise_pct`/`revenue.surprise_pct` is `None` (zero-consensus case). ⚠️ Correction: the crash is real if this code runs, but `src/engines/earnings_surprise_intelligence.py` (the whole module) has **zero production callers** — only its own unit tests invoke it. The router-level `analyze_earnings_event` in `research_alerts_p4.py:426` is a separate, unrelated reimplementation that already guards `None` via `(eps_surprise_pct or 0.0)`. This is currently dead code, not a live crash risk. |
| E-017 | `business_model_engine.py:124-130` | Still returns hardcoded `50.0` for <3 data points; now logs a `logger.warning(...)` but the `RevenueQuality` dataclass has no caller-visible flag — downstream consumers can't distinguish "neutral" from "no data." |
| E-023 | `macro_scenario_engine.py` (wired) vs. `macro_thematic_engine.py` (orphaned) | `macro_scenario_engine.py` is genuinely wired into `research_themes.py` (`_compute_theme_scores_for_entity`, scenario endpoints). But `macro_thematic_engine.py` — a separate file with its own `compute_inflation_exposure`/`score_all_themes`/`screen_by_theme` — has **zero** non-test importers anywhere. Fully orphaned still. |
| E-034 | `insider_signals.py:89-104,274-278` vs. `:260` | Per-transaction date parsing is now guarded with try/except + fallback formats. But `as_of = date.fromisoformat(as_of_date_str)` at line 260 remains **unguarded** — a malformed `as_of_date_str` argument still crashes. ⚠️ Correction: same reachability caveat as E-013 — the entire `insider_signals.py` module has zero production callers (the real `/insiders` endpoint in `filing_intelligence.py` imports a different, similarly-named model file, not this engine). Currently dead code, not exercised by any live request path. |

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
| M-004 | `morning_briefing.py:22,47` | `MorningBriefing`/`BriefingPreference.user_id` still plain `String(100)`, no FK. ⚠️ Correction: the "no users table exists" reason is wrong — `src/models/auth.py` defines a real `User` model (`users` table, since migration 013, predates Pillar 3). The actual blocker is a **type mismatch**: `User.user_id` is a UUID primary key, while these fields are `String(100)` (likely storing usernames) — a naive FK add would fail without a data/type migration first. Same correction applies to M-005 below. |
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
| P4-R-042 | `risk.py:338,350,359` | `benchmark` query param accepted but ignored for the actual computation — beta always uses the fixed market benchmark. ⚠️ Correction: it IS echoed back correctly in the response (`benchmark=benchmark` at line 359) — the earlier "not even echoed correctly" addendum was wrong. The real bug is narrower: the response mislabels which benchmark was actually used to compute the number, not a failure to echo the input. |
| P4-R-043 | `technical_backtest.py:29` | Unused `session` dependency. |
| P4-R-044 | `fi_risk.py` | 3 of 4 endpoints still have no `session` param — can't look up bond data from DB. |
| P4-A-004 | `app.py` / `quant.py:44` | No router serves `/v4/quant/*` — quant stuck at its own baked-in `/v2/analytics/quant` prefix. |

### 🟡 Partially fixed

| ID | Detail |
|---|---|
| P4-R-009 | Fixed in `add_position()` (real threshold guard). `create_transaction()`'s BUY averaging (line 858) still uses the old weak `if total_shares else Decimal("0")` guard — same rounding-artifact risk. |
| P4-R-023 | Missing-key case now defaults `drift_pct` to `0.0`. Explicit `null` in JSONB still triggers an unhandled error. ⚠️ Correction: the crash mechanism is misattributed — `PositionDriftEntry.drift_pct` is a non-Optional `float` schema field, so an explicit `null` value causes a Pydantic `ValidationError` inside `_parse_position_drifts` (~line 1148) when constructing the response object, not an `AttributeError`/`TypeError` from `abs()` at line 1266 — execution never reaches that line. Net effect (an unhandled 500) is the same; the "where" was wrong. |
| P4-R-035 | No longer lies (`PENDING` instead of fake `COMPLETED`), but **no batch worker exists anywhere** — backtests now honestly sit at PENDING forever instead of dishonestly reporting fake zeros. Functionally still non-operational. |
| P4-A-002 | `risk.py` still mounted at `/v2/analytics/risk`, not `/v4` — but appears to be a deliberate Pillar-2 classification; frontend correctly targets the real `/v4` portfolio-risk router, so no live breakage found. |

All other router/app-registration items (P4-R-001/002/003/004–008/010–012/016–022/027–031/036/038/039, P4-A-001, P4-A-003) are confirmed **FIXED**.

---

## Pillar 4 — Engines

*(54 issues — 12 FIXED, 2 PARTIALLY FIXED, 3 confirmed not-bugs-on-recheck, 3 MORE confirmed false positives on adversarial re-check [see below], 34 STILL OPEN)*

> **Verified false positive:** P4-E-030 (MWR/IRR "sign bug") — `compute_mwr()`'s convention (terminal value as positive inflow) is the correct standard XIRR formulation. Confirmed independently by re-deriving the math; matches `DATA_WIRING_AUDIT.md`'s own conclusion. Also not bugs: P4-E-008 (documentation-only), P4-E-020 (operator-precedence claim — code is correct as written).

> **Additional false positives found on adversarial re-check (2026-07-10):**
> - **P4-E-001** `nav_engine.py` — a negative `cash_balance` is a legitimate real-world state (margin debit/leverage), not invalid input. Traced every use: it only ever gets added into NAV and divided for `cash_weight`, both of which remain mathematically correct (a negative weight correctly represents leverage). There's nothing to validate against — not a bug.
> - **P4-E-004** `nav_engine.py:63-98` — `cost_basis_per_share` is a pure pass-through field on the output dataclass; `compute_position_valuation` never divides by or otherwise computes with it (only `cost_basis_total` drives the P&L math). No crash or bad-math path exists.
> - **P4-E-033** `performance_engine.py:438,448` — lexicographic comparison of zero-padded `YYYY-MM-DD` ISO date strings is mathematically equivalent to chronological comparison; this is a legitimate, standard technique, not fragile. The docstring documents the `YYYY-MM-DD` contract, and the only real caller always produces correctly-formatted ISO strings (`snapshot_date.isoformat()`).

### 🔴 Still open

**Unvalidated inputs / edge cases:**
- P4-E-002 `nav_engine.py:160-163` — no `nav_yesterday<=0` guard (only zero-check); a negative-but-nonzero prior NAV flips the sign of the computed return, producing an economically backwards result, not just an imprecise one
- P4-E-032 `performance_engine.py:95` — `cf["date_offset"]` KeyError risk, no validation (real, though the one current caller always supplies the key — a future/test caller without it would still crash)
- P4-E-052 `portfolio_parser.py:25-59` — no try/except around malformed CSV parsing (reproduced live: `csv.DictReader` raises `_csv.Error` on malformed input; a global exception handler prevents a hard server crash, but turns a plausible user action into an opaque 500 instead of a validation error)

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
- P4-E-019 `backtester.py:26,102-119` — drawdown duration field (⚠️ correction: actually named `max_drawdown_duration_days`, not literally `duration_days`) counts return-periods regardless of their length — genuinely mislabeled if ever fed non-daily returns, since `periods_per_year` is caller-configurable elsewhere but this counter doesn't account for it
- P4-E-026 `e7_quant.py:242` — Blume weight `0.67` hardcoded, undocumented
- P4-E-031 `performance_engine.py:125` — `r_new` clamped to max 10.0 (1000% return ceiling)
- P4-E-036 `portfolio_analytics.py:127-133` — HHI assumes weights sum to 1.0
- P4-E-037 `portfolio_analytics.py:75` — explicit `sector=None` grouped as `None` key, not "Unknown"
- P4-E-038 `portfolio_analytics.py:319-320` — uses `/30.44`/`/365.25` instead of `relativedelta`
- P4-E-039 `portfolio_risk_engine.py:126-141` — VaR weight normalization is a 5%-tolerance heuristic, not exact
- P4-E-041 `portfolio_risk_engine.py:562` — 2-sigma drift threshold hardcoded, not tunable
- P4-E-042 `attribution_engine.py:293-295` — factors missing from `factor_returns` silently dropped via set intersection

**Silent degradation:**
- P4-E-022/023/024 `concentration_risk.py:100-133,260-262` — unknown risk-level strings silently score as low-risk; `geographic_spread=0` doesn't trigger high-risk classification. Adversarial re-check found the actual bug is even sharper than described: in `classify_supplier_concentration`, the `if geographic_spread<=2: return "MODERATE" / else: return "MODERATE"` branch (lines 124-128) is dead code — both arms return the identical value, so `geographic_spread` never affects the classification at all, regardless of its value.
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
| P4-M-020 | `src/models/portfolio_watchlist.py` | No unique constraint on `(user_id, name)`. ⚠️ Naming correction: the column is actually called `name`, not `watchlist_name` as originally described. |
| P4-M-021–024 | `nav_snapshot.py`, `performance.py`, `attribution.py`, `backtesting.py` | No `CHECK` constraints for date ordering (`period_start<=period_end`/`start_date<=end_date`) anywhere. |
| P4-M-025 | `src/models/quant.py:34-35` | No range `CheckConstraint` on `r_squared`/`adj_r_squared`. |
| P4-M-026 | Pillar 4 models specifically | No `Enum`/`CHECK` constraints on any Pillar-4 (portfolio-domain) status/type column. ⚠️ Correction: the original "no model anywhere in the codebase" framing is too broad and false — `src/models/fundamentals.py:98` (Pillar 1) has `CheckConstraint("data_version IN (...)")` on a genuine status-like column. Scope this finding to Pillar 4's own models, where it holds. |
| P4-M-028 | `src/models/backtesting.py:13-31` | `BacktestRun` still has no `user_id`/`owner_id` — any user can read any backtest by ID. |

### 🟡 Partially fixed

| ID | Detail |
|---|---|
| P4-M-009 | `ON DELETE CASCADE` added only to `Position.portfolio_id`/`Transaction.portfolio_id`. NAV/Performance/Attribution/Risk FKs to `portfolios.id` still plain, no cascade — `session.delete(portfolio)` will still fail against those tables. ⚠️ Correction: Backtesting was miscategorized here — `BacktestRun`/`BacktestResult` have **no `portfolio_id` FK at all** (they're standalone, unrelated to any portfolio), so there's nothing to cascade for that model, not "plain, no cascade" as originally listed. |
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
| P4-F-022 | `as any` casts remain (confirmed exact count on `RiskPage.tsx`: 13, the heaviest). The "7 of 9" denominator wasn't independently reproducible on re-check — counted `RiskPage` 13, `PortfolioDetail` 5, `QuantDashboard` 3, `CustomIndexBuilder` 2, `WatchlistView` 1, `BacktestDashboard` 1, `PortfolioList`/`PerformancePage` 0 — but the substantive claim (heavy usage persists, RiskPage worst) holds regardless of the exact page count. |
| P4-F-023 | `PortfolioList.tsx:94-97` — the TODO error-toast is still literally unimplemented, byte-for-byte identical to the original finding. Same `console.warn`-only pattern repeats on CSV preview/commit failures. |

### 🟡 Partially fixed

| ID | Detail |
|---|---|
| P4-F-013 | `PortfolioDetail.tsx` — NAV-history `Math.random()` generator now dead code. ⚠️ Correction, scope narrowed: portfolio identity, holdings, and sector allocation are **not** "zero hook backing" as originally claimed — `activePortfolio` (`usePortfolio`), `activeHoldings` (`usePortfolioPositions`), and `activeAllocations` (`usePortfolioAllocationsBySector`) are all genuinely merged with real hook data via `??`, the same pattern credited elsewhere as "fixed." Only the 4 KPI metrics (`perfMetrics`: TWR/Sharpe/Drawdown/Beta) are rendered with zero hook consumption at all — that's the real remaining gap, much narrower than originally described. |
| P4-F-014 | `PerformancePage.tsx` — all 3 `Math.random()` generators confirmed dead code. KPI/calendar/risk-metrics/attribution table hardcoded fallbacks unchanged. |
| P4-F-015 | `RiskPage.tsx` — all 8 hooks now genuinely consumed via `??` merge. `api.request()` bypass at line 131 remains (one action), though its error is now surfaced to the user (a genuine improvement). Hardcoded fallback constants remain; heaviest `as any` usage of all 9 pages. |
| P4-F-017 | `BacktestDashboard.tsx` — hardcoded data removed, error handling added (no longer empty catch). **But** `BACKTESTING` endpoints in `endpoints.ts` (`/v2/analytics/backtest/strategies\|run\|history\|compare`) match **no real backend route** (`backtesting.py` only exposes `/v1/analytics/backtest`, `/{id}/results`, `/holdings`, `/compare`) — page is permanently empty. **New bug introduced**: `dynamicKpis` computes off the permanently-empty results array, producing `"+undefined%"`/`"NaN%"` in the KPI row. |
| P4-F-021 | 3 of ~6 originally-silent failure spots (`RiskPage`, `BacktestDashboard`, `CustomIndexBuilder`) now show inline errors. `PortfolioDetail.tsx`, `WatchlistView.tsx`, `PortfolioList.tsx` remain fully silent (`console.error`/`console.warn` only). No toast component exists anywhere in the app — all error surfacing, where present, is inline `<div>`s. |

All other frontend items (P4-F-001–008, P4-F-016, P4-F-018, P4-F-019, P4-F-020) are confirmed **FIXED**.

---

## Cross-cutting themes / where to start

Ranked by leverage (impact of fix ÷ effort), not by original severity label:

1. **Models/schemas are the weakest layer across every pillar, and Pillar 1/2/3's "fixes" are a trap.** Someone edited `src/models/*.py` extensively for Pillar 1 (18 items), Pillar 2 (`data_quality` column, `metric_category` CHECK constraint), and Pillar 3 (11 items) but never touched `migrations/versions/`. Anyone deploying from migrations gets none of those fixes. **First action: reconcile models vs. migrations with a new Alembic revision**, or the model edits are dead weight. This is the single most repeated failure pattern in the whole codebase — it has now been independently confirmed in all four pillars.
2. **Self-reported fix docs need independent verification, not just a re-read — `PILLAR_1_FIXES.md` is a concrete example.** Its "Corporate actions `security_id` fix" claim is actively false: the connector was switched to write a different table entirely, and the table the API actually reads (`CorporateAction`) still has zero writers — the endpoint went from "wrong filter" to "permanently empty," which is worse than the bug it claimed to fix. Its "SegmentData connector" claim cites a driver script (`scripts/ingest_segments.py`) that doesn't exist in the repo at all. Treat any "Fixes Applied" document as a hypothesis to verify against code, the same discipline applied to the original audits throughout this file.
3. **Decimal→float precision loss (Pillar 4, P4-M-001–007)** — untouched across all 7 financial schema groups. Every monetary number in the portfolio system loses precision on serialization. High blast radius, moderate effort (schema type change + serializer). Pillar 1's version of this problem is smaller in scope but shows the same instinct: a targeted Decimal→float reversion in `capital_structure.py`/`corporate_bond.py` fixed a real Pydantic serialization bug but reintroduced float precision loss as a side effect.
4. **Backtesting is a dead end in every pillar that has one.** Pillar 2's `/v2/analytics/backtest`, Pillar 4's `/v1/analytics/backtest`, and Pillar 4's frontend `BacktestDashboard.tsx` (which calls a *third*, entirely nonexistent set of endpoints) are three independent broken implementations of the same feature. All three honestly return `PENDING`/empty instead of fake data now, but **no batch worker exists anywhere** in the repo to ever advance a PENDING backtest, and the Pillar 4 frontend has a newly-introduced `NaN`/`undefined` KPI display bug on top. This is the single most broken end-to-end feature surfaced across all four audits — worth consolidating into one real implementation rather than fixing three broken ones.
5. **The "real code, but nobody scheduled or documented it" pattern is now confirmed in three of four pillars.** Pillar 3 had this fixed as part of the main `DATA_WIRING_AUDIT.md` pass (11 connectors registered in `batch_config.py`/documented in `CONNECTING_TO_REAL_DATA.md`). Pillar 1's brand-new work from today (6 of 7 Tier-3 connectors, all 4 Tier-2 rollup scripts) has **not** received that same treatment — real, tested code reachable only via a manual `make` target. Since Pillar 3 already has the playbook for closing this exact gap, applying it to Pillar 1's new connectors should be comparatively cheap.
6. **Frontend endpoint/backend mismatches with zero backend implementation** (not just wiring bugs, an actual missing feature) cluster around the same few concepts across pillars: **benchmarks** (`/v1/benchmarks` — Pillar 2 Bugs 94/95 and Pillar 4 P4-F-009 are the *same* missing router hit from two different pages), **quant** (`/factor-exposure`, `/technical-signals`, `/correlation`'s zeroed-out metrics — Pillar 2 Bugs 87/93 and Pillar 4 P4-F-010), **technical-backtest** (P4-F-011), **FI-risk** (P4-F-012). These need one scoping decision each (build the backend, or remove the dead frontend code) rather than a wiring fix.
7. **The "remove hardcoded mock, fall back to real API data" pass introduced real regressions in `ValuationDashboard.tsx` (Pillar 2, Bugs 79/82).** Two of its three still-open frontend bugs are now **worse** than the original static-mock version: unguarded `.map()` calls on API responses that are objects, not arrays, will throw `TypeError` and crash the page the moment a security with real multiples/peer data loads — masked today only because the underlying endpoints' response shape was never checked against what the component expects. Same failure class as `BacktestDashboard.tsx`'s `NaN%` tiles (item 4) — worth a systematic sweep for `(x as any[])` casts with no `Array.isArray` guard across all four pillars' frontends, since this pattern reproduced independently at least 3 times. Pillar 1's frontend pass avoided this specific trap (no regressions found), for comparison — it just left `as any` casts in place rather than introducing new unguarded array assumptions.
8. **`AnomalyView.tsx` (Pillar 3) is the one page where the original F-001 mock-data bug is fully unfixed** — worth a 10-minute fix to match the pattern already applied to the other 8 pages in the same audit, and to the equivalent 10-page sweep that fully succeeded in Pillar 1.
9. **Small, cheap, high-clarity fixes** ready to knock out in one pass: `risk.py`'s ignored `benchmark` param (P4-R-042), `fi_risk.py`'s missing `session` params (P4-R-044), `portfolio_watchlists.py`'s missing entity fallback labels (P4-R-032), `PortfolioList.tsx`'s never-implemented TODO toast (P4-F-023), `earnings_surprise_intelligence.py`'s unweighted surprise sum (E-036), Pillar 2's screener payload wrapper key (Bug 46, one JSON key away from working), Pillar 2's `/screen/fields` E3-field exclusion (Bug 64), Pillar 1's `fi_yield_curve.py` duplicated tenor dict (P1-R-047), and the `market_movers.py` test suite that needs updating to match its own rewritten router (Pillar 1).
10. **A cluster of Pillar 3 "still crashes on bad input" engines turned out to be dead code, not live risk.** The adversarial verification pass found `earnings_surprise_intelligence.py`, `insider_signals.py`, and `news_entity_linker.py` all share a pattern: the described crash/limitation is real if the code runs, but the entire module has **zero production callers** — only unit tests invoke it (E-013, E-034, E-035, E-036). This doesn't make the bugs not-worth-fixing, but it does change the priority: fix them when/if these engines get wired into a router, not before. Worth checking whether any other "confirmed" engine bug in this file has the same orphaned-module characteristic before scheduling work against it.

---

*This file supersedes nothing — `PILLAR_1_AUDIT_REPORT_v2.md`, `PILLAR_2_AUDIT_REPORT_v2.md`, `PILLAR_3_AUDIT_REPORT_v2.md`, `PILLAR_4_AUDIT_REPORT_v2.md`, `PILLAR_1_FIXES.md`, and `DATA_WIRING_AUDIT.md` remain the historical record of what was originally found and what each fix pass changed. This file is the current-state cross-reference layered on top, with `DATA_WIRING_AUDIT.md` treated as the primary authority per current direction.*
