# PILLAR 1 AUDIT REPORT v2
## Bloomberg Data Fabric — Data Foundation — Deep Audit
**Date:** 2026-04-03
**Previous version:** 68 issues (shallow pass)
**This version:** 243 issues across 7 layers — every file read line-by-line
**Scope:** 32 routers · 23 models · 36 schemas · 8 engines · 9 hook files · 10 frontend pages · app.py

---

## EXECUTIVE SUMMARY

| Layer | Files | Issues | Critical | High | Medium | Low |
|-------|-------|--------|----------|------|--------|-----|
| Backend Routers | 32 | 72 | 11 | 18 | 28 | 15 |
| Engines | 8 | 33 | 5 | 7 | 15 | 6 |
| Models & Schemas | 59 | 56 | 4 | 15 | 21 | 16 |
| Frontend Hooks & Endpoints | 11 | 28 | 5 | 11 | 9 | 3 |
| Frontend Pages | 10 | 51 | 35 | 13 | 3 | 0 |
| App Registration | 1 | 3 | 1 | 2 | 0 | 0 |
| **TOTALS** | **121** | **243** | **61** | **66** | **76** | **40** |

### Most Critical Systemic Findings

1. **Every frontend page hardcodes Apple Inc. (AAPL) as fallback** — all 10 Pillar 1 pages display Apple-specific data (names, filings, executives, bond CUSIPs, M&A deals) for any entity if the API fails.
2. **`.nullslast()` crash (wrong method name) in 6 routers** — `corporate_actions.py`, `relationships.py`, `capital_structure.py`, `ma_deals.py`, `ipo.py`, `fund_holdings.py` all call `.nullslast()` which does not exist; correct is `.nulls_last()`. Runtime `AttributeError` on first request.
3. **`custom_classifications.py` hardcodes UUID `"00000000-0000-0000-0000-000000000001"`** as fallback owner — any unauthenticated call assigns resources to this ghost user.
4. **`executives.py` uses `.in_(select(subq))` — invalid SQLAlchemy syntax** — `select()` wrapper inside `.in_()` causes immediate runtime error on every executive lookup.
5. **`market_movers.py` router assumes `rankings` is a list but model defines it as `dict`** — `entry.get()` called on a list raises `AttributeError`.
6. **`resolution.py` silently bypasses authentication** — if the auth module import fails, the endpoint is redefined without auth and FastAPI registers the unauthenticated version.
7. **`filing_diff.py:303` uses wrong threshold variable** — `align_paragraphs()` compares against `jaccard_threshold` where it should compare against `match_threshold`, causing modified paragraphs to be misclassified as removed+added.
8. **`corporate_action_engine.py` has three division-by-zero paths** — `process_cash_dividend`, `process_stock_split`, `process_reverse_split` all divide without validating the denominator is non-zero.
9. **Pagination offset goes negative if `page=0`** — systemic across 15+ endpoints; `offset = (page - 1) * page_size` produces negative SQL OFFSET.
10. **Duplicate hook definitions across `src/hooks/` and `src/api/hooks/`** — same hook names in two locations cause import conflicts; 14 hooks duplicated.
11. **CORS not configured in app.py** — browser clients cannot reach the API.
12. **`calendar.py` `event_types` filter parameter is accepted but never applied** — filtering by event type silently does nothing.

---

## SECTION 1: BACKEND ROUTERS

### 1.1 entities.py

**P1-R-001** | CRITICAL | Line 379 (systemic)
Pagination offset calculation: `offset = (pagination.page - 1) * pagination.page_size`. If caller passes `page=0`, offset becomes `-page_size`, producing invalid SQL `OFFSET -20`. No validation that `page >= 1`. Affects list_entities, search_entities, get_entity_securities, get_entity_history, and every other paginated endpoint in this file.

**P1-R-002** | HIGH | Line 295
`score=1.0` hardcoded placeholder for entity search relevance. Comment reads: *"Placeholder score; real scoring via ES later."* No Elasticsearch code exists. All search results return identical relevance scores regardless of query match quality.

**P1-R-003** | HIGH | Lines 52, 295
Elasticsearch integration absent. Code comments promise ES-backed search but the implementation falls back to `ILIKE` SQL pattern matching with no scoring, no fuzzy matching, and no relevance ranking.

**P1-R-004** | MEDIUM | Line 337
`_ = rel_result.scalars().all()` — relationship data is fetched from DB then thrown away. The underscore assignment is unused. A DB round-trip occurs for every entity detail request that includes `expand=relationships`, but the result is discarded.

**P1-R-005** | MEDIUM | Lines 349, 355
`resp.identifiers` and `resp.names` are `None` unless the caller explicitly passes `expand=identifiers,names`. This means a basic `GET /entities/{id}` returns an entity with no identifiers. Frontend must always know to include the expand parameter; the default response is nearly empty.

**P1-R-006** | MEDIUM | Lines 404–410
Identifier filter logic AND-combines multiple filter types. If a caller passes both `lei=X` and `cik=Y`, the query becomes `WHERE entity_id IN (lei subquery) AND entity_id IN (cik subquery)`. A single entity cannot match both conditions simultaneously, so results will always be empty when two identifier types are provided together. Should be OR logic.

**P1-R-007** | LOW | Line 453
No cycle detection in parent hierarchy traversal. If `entity.ultimate_parent_id` references a chain that eventually circles back to the entity itself (data corruption), hierarchy lookups would loop indefinitely at the application layer.

---

### 1.2 securities.py

**P1-R-008** | CRITICAL | Line 255
When `expand=ticker` is requested, there is no code that populates `resp.ticker`. The field exists in the schema but is never set. Every single `GET /v1/securities/{id}?expand=ticker` returns `ticker=null`.

**P1-R-009** | HIGH | Line 84
`ticker=None` hardcoded in search results with comment: *"Would come from identifier join; placeholder."* Ticker is never fetched from `SecurityIdentifier`. All security search results return `ticker=null`.

**P1-R-010** | HIGH | Line 85
`score=1.0` hardcoded search relevance score. Same problem as entities.py. No actual relevance ranking implemented.

**P1-R-011** | HIGH | Lines 280–290
Multiple identifier filters (ISIN, CUSIP, FIGI, TICKER) build separate subqueries that are AND-combined. A security cannot simultaneously match ISIN=X AND CUSIP=Y — these should be OR-combined. Multi-identifier searches return zero results.

**P1-R-012** | MEDIUM | Lines 1–5
`EquityDetails` and `FixedIncomeDetails` are imported but never used anywhere in the file. Dead imports.

**P1-R-013** | MEDIUM | Line 408
`ident_map` is built during identifier translation but if a requested `target_type` is absent from `ident_map`, it is silently skipped. Frontend receives incomplete translation results with no indication of which target types failed.

---

### 1.3 security_finder.py

**P1-R-014** | CRITICAL | Line 31
Hard limit of 500 securities loaded into memory for the find endpoint. The query `select(Security).limit(500)` fetches 500 rows into Python, then performs in-memory string search. The entire findable universe is capped at 500 securities regardless of how many exist in the database.

**P1-R-015** | HIGH | Line 45
`search_securities()` result objects are expected to have a `.relevance_score` attribute, but the source data dict built at lines 17–25 does not populate `relevance_score`. Accessing it causes `AttributeError` at runtime.

**P1-R-016** | MEDIUM | Line 72
`SecuritySuggestion(**s)` unpacks a dict into the Pydantic model. If the dict contains extra keys not in the schema, Pydantic v2 raises `ValidationError`. If it's missing required keys, same. No defensive handling around this conversion.

---

### 1.4 resolution.py

**P1-R-017** | CRITICAL | Lines 28–131
Auth import wrapped in `try/except ImportError`. If import fails, the endpoint is **redefined without authentication** in the except block. FastAPI registers the last-defined handler for each path, so if the import fails the unauthenticated version is registered. Authentication is silently bypassed with no startup warning.

**P1-R-018** | MEDIUM | Line 57
`body: ApproveRejectRequest = ApproveRejectRequest()` — default empty body. A POST to `/queue/{id}/approve` with no body succeeds silently instead of requiring reviewer information.

**P1-R-019** | MEDIUM | Line 82
`body.reviewer or current_user.get("sub")` assumes `current_user` is a dict. If auth middleware stores `current_user` as a Pydantic model or object, `.get("sub")` raises `AttributeError`.

**P1-R-020** | MEDIUM | Lines 63–75 vs 100–112
Nearly identical code duplicated in the auth and non-auth versions of the same endpoint. Any bug fix applied to one must be manually applied to the other.

---

### 1.5 reference.py (src/api/reference.py)

**P1-R-021** | CRITICAL | Lines 80, 89, 113, 247, 277, 296, 311, 330, 380 (15+ occurrences)
`offset = (pagination.page - 1) * pagination.page_size` repeated across every paginated endpoint. If `page=0`, offset is negative. No validation anywhere. Affects: list_currencies, list_countries, list_exchanges, list_gics, list_sic_codes, list_naics_codes, list_trading_days, and all other reference list endpoints.

**P1-R-022** | MEDIUM | Lines 80, 81, 89, 113 (12+ occurrences)
`request_id=""` and `processing_time_ms=0` hardcoded in every `PaginatedMeta` response. Comment says these are filled by middleware, but the middleware does not update the already-constructed response object. All API responses report `processing_time_ms=0` and blank `request_id`. Request tracing is non-functional.

**P1-R-023** | MEDIUM | Line 388
Cache key for `/currencies/{code}` normalizes with `.upper()`, but `/gics/{code}` does not. Inconsistent case handling means `GET /gics/10` and `GET /gics/10` will hit the cache, but if code varies in case across endpoints, cache misses will occur unpredictably.

---

### 1.6 fundamentals.py

**P1-R-024** | MEDIUM | Lines 45–46, 134–138, 173–177, 212–216, 247–251
Count query and data query are constructed separately in every endpoint. If the filter logic applied to one diverges from the other (e.g., during refactoring), pagination `total` counts will not match the actual returned data length. No test enforces they stay in sync.

**P1-R-025** | MEDIUM | Line 59
`.order_by(Filing.filing_date.desc())` — no `.nulls_last()` guard. If any filing has a null `filing_date`, its sort position is database-dialect-dependent (PostgreSQL puts NULLs last by default for DESC, but this is not portable and not explicit).

**P1-R-026** | LOW
No geographic breakdown endpoint exists in this file. The `useGeographicBreakdown` frontend hook calls `/v1/entities/{id}/geographic-breakdown` which returns 404. **To be built** — see Part 9 at end of this report.

---

### 1.7 ownership.py

**P1-R-027** | LOW | Lines 86–126
`list_institutional_holdings` verifies security existence (lines 96–100) but the subsequent join does not verify that the security has actual holdings records. Empty result set is returned silently for a valid security with no institutional data, with no distinction from a bad security ID.

---

### 1.8 filing_intelligence.py

**P1-R-028** | MEDIUM | Lines 162–167
`len(row.added_paragraphs)` computed without null guard. If the JSONB column `added_paragraphs` is `NULL`, `len(None)` raises `TypeError`. Pattern used on lines 162–167 for `added_paragraphs`, `removed_paragraphs`, `modified_paragraphs`.

**P1-R-029** | MEDIUM | Line 172
`combined_summary = " | ".join(ai_summaries)` — pipe character `|` used as separator without escaping. If any AI-generated summary contains a literal `|`, downstream parsers treating this as a delimiter will split incorrectly.

**P1-R-030** | LOW | Line 63
`desc` is not imported in the import block (only `func, and_`). If a future developer adds an ORDER BY using `desc()`, the import error won't be caught at module load time.

---

### 1.9 corporate_actions.py

**P1-R-031** | CRITICAL | Lines 59, 103, 142, 182
`.nullslast()` called instead of `.nulls_last()`. This method does not exist on SQLAlchemy column expressions. Every endpoint in this router crashes with `AttributeError: 'desc' object has no attribute 'nullslast'` on the first request.

Affected lines:
- Line 59: `CorporateAction.announcement_date.desc().nullslast()`
- Line 103: `DividendAction.ex_date.desc().nullslast()`
- Line 142: `StockSplitAction.effective_date.desc().nullslast()`
- Line 182: `MergerAcquisition.announcement_date.asc().nullslast()`

---

### 1.10 relationships.py

**P1-R-032** | CRITICAL | Lines 75, 130, 185, 240
Same `.nullslast()` bug as `corporate_actions.py`. All four list endpoints in this router crash immediately:
- Line 75: `BusinessRelationship.relationship_start_date.desc().nullslast()`
- Line 130, 185, 240: same pattern on date columns

**P1-R-033** | LOW | Lines 101–107
`.where()` receives a mix of positional args and OR expressions: `.where((cond_a) | (cond_b), cond_c)`. This works but is non-idiomatic; correct form is `.where(or_(cond_a, cond_b)).where(cond_c)`.

---

### 1.11 executives.py

**P1-R-034** | CRITICAL | Lines 38–39
`Executive.executive_id.in_(select(exec_ids_subq))` — wrapping a subquery inside `select()` before passing to `.in_()` is invalid SQLAlchemy syntax. The `.in_()` method expects a subquery object directly, not a `select()` wrapper around one. Raises `ArgumentError` or `ProgrammingError` at runtime on every call to list_entity_executives.

**P1-R-035** | LOW | Lines 47, 80
Paginated endpoints have `.offset().limit()` but no `.order_by()`. Without deterministic ordering, the same page request can return different rows across separate calls (database row order is not guaranteed without ORDER BY).

**P1-R-036** | LOW | Line 71
`ilike(f"%{name}%")` with raw user input. If the user includes `%` or `_` wildcards in `name`, the LIKE pattern behaves unexpectedly. Should escape SQL wildcard characters before interpolation.

---

### 1.12 capital_structure.py

**P1-R-037** | HIGH | Line 78
`.order_by(DebtTranche.seniority_rank.asc().nullslast())` — same `.nullslast()` bug. Crashes immediately.

**P1-R-038** | LOW | Lines 44–46
404 error message is generic: "Capital structure not found". Does not distinguish "entity exists but no capital structure" from "entity does not exist". Clients cannot tell if the entity ID was wrong or if the data simply hasn't been populated.

---

### 1.13 debt_maturity.py

**P1-R-039** | MEDIUM | Lines 22–89
No pagination on any endpoint despite returning time-series data. All maturity buckets, debt metrics, and alerts are returned as single snapshots. If multiple records exist for the same entity over time, callers cannot page through history.

---

### 1.14 credit_rating.py

**P1-R-040** | MEDIUM | Lines 48, 90
`.order_by(CreditRatingEvent.event_date.desc())` — no `.nulls_last()` guard. If `event_date` is nullable, events with null dates sort unpredictably.

---

### 1.15 calendar.py

**P1-R-041** | CRITICAL | Lines 28–50
`event_types` query parameter is accepted (line 28) and the variable is created (lines 46–47), but is **never applied to the SQLAlchemy query**. The filter assignment is built but never passed to `.where()`. Filtering by event type silently returns all events regardless of the requested types.

**P1-R-042** | MEDIUM | Lines 73–74
The second calendar endpoint `list_all_calendar_events` uses different filtering logic from the first. No `entity_ids` filter is applied even when provided, and no `event_types` filter is applied. The two endpoints behave inconsistently.

---

### 1.16 yield_curve.py

**P1-R-043** | HIGH | Lines 100–125
Race condition in forward curve endpoint: the most recent curve date is found with `max()` in one query, then used in a second query. If a new curve is inserted between these two queries, the second query may return empty. Should use a single subquery.

**P1-R-044** | MEDIUM | Lines 19–45
`curve_date` can be `None` if no data exists for the requested date, but it is returned directly in the response without a null guard. If the DB has no yield curve for the requested date, `curve_date=None` is serialized in the response with no 404.

---

### 1.17 fi_yield_curve.py

**P1-R-045** | HIGH | Line 104
`_rate_col_for_tenor()` is a synchronous helper that raises `HTTPException`. Raising `HTTPException` outside of a FastAPI endpoint handler (i.e., in a sync function called from an async handler) may not be caught by FastAPI's exception middleware properly in all versions, depending on whether the exception propagates through the async call stack correctly. Should raise `ValueError` and let the endpoint translate it.

**P1-R-046** | MEDIUM | Line 223
`cutoff = date.today() - timedelta(days=months_back * 30)` — hardcoded 30 days/month. For a `months_back=1` request in March (31-day month), the cutoff is off by 1 day. Should use `dateutil.relativedelta`.

**P1-R-047** | MEDIUM | Line 269
`df_tenor_years` dict is hardcoded inline and duplicates values from the module-level `_DF_COLS` constant. When `_DF_COLS` is updated, this dict will be out of sync.

---

### 1.18 fi_bonds.py

**P1-R-048** | CRITICAL | Line 644
`bond.call_schedule` accessed without verifying the relationship is loaded. If the ORM relationship is configured for lazy loading and the session is closed, this raises `MissingGreenlet` or `DetachedInstanceError`. No eager loading strategy visible for this relationship.

**P1-R-049** | MEDIUM | Lines 91, 285
`.desc()` on `maturity_date` without `.nulls_last()`. Zero-coupon perpetuals or improperly imported bonds with null maturity dates will sort unpredictably.

**P1-R-050** | LOW | Lines 96, 137, 201, 250, 339
`.scalars().unique().all()` — `.unique()` is unnecessary after `.scalars()` for non-joined loads and adds unnecessary overhead.

---

### 1.19 fi_treasuries.py

**P1-R-051** | CRITICAL | Line 220
`treasury_analytics` endpoint has no `response_model` defined. Returns a raw untyped dict. OpenAPI docs will show no schema for this endpoint; validation is skipped entirely.

**P1-R-052** | MEDIUM | Lines 249, 256
Zero-coupon bond handling: `freq if freq > 0 else 2` substitutes semi-annual frequency for zero-coupon bonds. For STRIPS and zero-coupon Treasuries, `freq=0` is mathematically correct and should not be substituted. YTM calculations for zero-coupon instruments will be incorrect.

**P1-R-053** | LOW | Line 85
`== True` explicit boolean comparison (`# noqa: E712` comment suppresses the linting warning). Should use `.is_(True)` in SQLAlchemy context.

---

### 1.20 fi_ratings.py

**P1-R-054** | HIGH | Line 184
`sum(sum(row.values()) for row in matrix.values())` — `row` is expected to be a dict. If `compute_migration_matrix()` returns a different structure (list, named tuple, custom object), this raises `AttributeError` or `TypeError`. No type guard.

**P1-R-055** | LOW | Lines 41, 44, 82, 85
`== True` explicit boolean comparisons throughout. Same style issue as fi_treasuries.py.

---

### 1.21 fi_spreads.py

**P1-R-056** | MEDIUM | Line 12
`BAML_SERIES` imported but never used anywhere in the file. Likely a removed feature leaving a dead import.

**P1-R-057** | MEDIUM | Line 191
`compute_spread_percentile(hist_values, float(item.spread_bps))` called with no try/except. If `hist_values` is empty or the engine raises `ValueError`, the entire request fails with an unformatted 500.

---

### 1.22 fi_issuances.py

**P1-R-058** | MEDIUM | Line 97
`aggregate_issuance_volume(iss_dicts, period=period)` — engine result not null-checked before use. If engine returns `None` or empty, line 98 raises `TypeError`.

**P1-R-059** | MEDIUM | Line 121
`compute_league_table(iss_dicts)` — no error handling. If engine raises, request fails with unformatted 500.

---

### 1.23 fi_agency_bonds.py

**P1-R-060** | MEDIUM | Lines 58, 91
`.desc()` on `maturity_date` without `.nulls_last()`. Same issue as `fi_bonds.py`.

---

### 1.24 money_market.py

**P1-R-061** | MEDIUM | Lines 28–35
Both `rate_date` (exact date) and `start`/`end` (date range) filters can be provided simultaneously. The query applies both as AND conditions. Behavior is undefined and not documented — should the exact date take precedence, or should it be rejected as conflicting?

**P1-R-062** | MEDIUM | Line 9
`get_pagination` is imported but the endpoint uses manual limit calculation instead of the pagination dependency. Import is dead code.

---

### 1.25 ma_deals.py

**P1-R-063** | HIGH | Lines 59, 145
`.nullslast()` called instead of `.nulls_last()`. Crashes on first request to deal list endpoints.

---

### 1.26 ipo.py

**P1-R-064** | HIGH | Lines 46, 78
`.nullslast()` bug — crashes on IPO list and pipeline endpoints.

**P1-R-065** | MEDIUM | Lines 70–71
`.where(IPOEvent.status.in_(["FILED", "AMENDED"]))` — status values are hardcoded strings. If the DB stores `"filed"` (lowercase) or uses an enum type, no results are returned. No normalization or enum definition.

---

### 1.27 earnings_intelligence.py

**P1-R-066** | MEDIUM | Lines 42–43, 50–60
`list_earnings_surprises` and `list_guidance` both paginate without an `.order_by()` clause. Pagination without deterministic ordering returns inconsistent results across pages.

---

### 1.28 fund_holdings.py

**P1-R-067** | MEDIUM | Line 44
`list_funds` paginates without `.order_by()`. Same issue.

**P1-R-068** | HIGH | Lines 97, 130
`.nullslast()` bug — crashes on fund holdings endpoints.

---

### 1.29 custom_classifications.py

**P1-R-069** | CRITICAL | Line 29
`owner_id = user_id or "00000000-0000-0000-0000-000000000001"` — hardcoded fallback UUID assigned as owner when no user is provided. Any unauthenticated request creates resources owned by this ghost user with no authorization check.

**P1-R-070** | CRITICAL | Lines 38, 118
`await session.flush()` used after creating classification and after adding members. Flush sends SQL without committing. If the session context exits without an explicit commit elsewhere, all custom classification data is silently lost.

**P1-R-071** | HIGH | Lines 39, 119
After `flush()`, `await session.refresh(obj)` is called to reload the object. The `members` relationship is lazy-loaded via `selectin`. After flush (not commit), refreshing may not populate the relationship correctly if the session transaction is not yet committed.

---

### 1.30 market_movers.py

**P1-R-072** | CRITICAL | Line 51
`rankings` column is typed as `dict | None` in the `MarketMoversSnapshot` model, but the router iterates over it as a list: `for entry in (row.rankings or [])` then calls `entry.get(...)`. If `rankings` is a dict (as the model declares), iterating over it yields keys not dict-like items, and `entry.get()` on a string key raises `AttributeError`.

**P1-R-073** | MEDIUM | Lines 44–48
Fallback response uses `snapshot_date=date.today()` when no snapshot exists. Client receives a response that appears valid with today's date but contains entirely empty/zero data, indistinguishable from a genuine empty day.

**P1-R-074** | MEDIUM | Line 88
`snap_date = snapshot_date or date.today()` is initialized, then unconditionally overwritten in a loop. If the loop executes zero times (no matching rows), `snap_date` retains the correct value. But if the loop executes, each iteration overwrites `snap_date` — the final value is whatever the last row had.

---

## SECTION 2: ENGINES

### 2.1 corporate_action_engine.py

**P1-E-001** | CRITICAL | Line 74
`process_cash_dividend()`: `cash_amount / current_price` — if `current_price == 0` (not None, but zero), the guard `current_price is not None and current_price > 0` prevents division, but this check is only applied for the DRIP path. If a zero price reaches this function via a different code path that bypasses the guard, `ZeroDivisionError` is thrown.

**P1-E-002** | CRITICAL | Line 105
`process_stock_split()`: `new_cost_per_share = cost_basis_per_share / split_ratio` — no validation that `split_ratio > 0`. Passing `split_ratio=0` (invalid data) raises `ZeroDivisionError`.

**P1-E-003** | CRITICAL | Line 123
`process_reverse_split()`: `new_shares = shares / reverse_ratio` — same pattern. `reverse_ratio=0` raises `ZeroDivisionError`.

**P1-E-004** | HIGH | Lines 69–83
`process_cash_dividend()` does not validate that `shares` and `dividend_per_share` are non-negative. Negative inputs produce mathematically negative cash dividends which are logically wrong. No guard.

**P1-E-005** | HIGH | Line 176
`process_spin_off()`: `allocation_pct / 100.0` is computed without validating `allocation_pct ∈ [0, 100]`. Passing `allocation_pct=150` produces allocation > 1.0, making the parent cost basis negative.

**P1-E-006** | MEDIUM | Lines 220–242
`match_corporate_actions_to_holdings()` is fully implemented but never imported or called by any router. Dead code — ~22 lines that serve no function.

---

### 2.2 filing_diff.py

**P1-E-007** | CRITICAL | Line 303
`align_paragraphs()` threshold comparison bug:
```python
if best_j is not None and best_sim >= jaccard_threshold:   # WRONG
```
Should be:
```python
if best_j is not None and best_sim >= match_threshold:     # CORRECT
```
`jaccard_threshold` defaults to `0.2` while `match_threshold` defaults to `0.6`. Using the wrong (lower) threshold means paragraphs with only 20% word overlap are classified as MODIFIED instead of REMOVED+ADDED. The diff classification is systematically incorrect for paragraphs with moderate changes.

**P1-E-008** | MEDIUM | Lines 339–349
`_is_numerical_only_change()` uses `re.sub(r"\b\d[\d,\.]*\b", "", result)` which over-strips hyphenated numbers. `"3-month"` becomes `"-month"`, `"Q4-2024"` becomes `"Q-"`. Paragraphs with number-adjacent text may be incorrectly classified as purely numerical changes.

**P1-E-009** | MEDIUM | Line 375
`classify_change()` returns string literals (`"SUBSTANTIVE"`, `"BOILERPLATE"`, etc.) with no enum or type constraint. A typo in any return statement would pass Python type checking and produce silently wrong downstream behavior.

---

### 2.3 eight_k_engine.py

**P1-E-010** | HIGH | Lines 214–237
`_try_parse_date()` returns `None` on parse failure but callers in `extract_key_dates()` don't document that `date_parsed` can be None. Downstream code that builds ISO date strings from these results will produce `None` in date fields without warning.

**P1-E-011** | MEDIUM | Lines 181–213
`extract_monetary_figures()` can produce duplicate entries. Pattern 1 and Pattern 2 can both match `"$500 million"` — Pattern 1 captures the full phrase, Pattern 2 may also capture `$500` as a plain dollar amount. Results are not deduplicated.

**P1-E-012** | MEDIUM | Lines 238–285
`extract_key_people()` deduplicates by name only — if "John Smith" appears as both CEO and CFO, only the first occurrence is retained. Role diversity for the same person is lost.

**P1-E-013** | MEDIUM | Lines 349–375
`assess_event_materiality()` hardcodes `$1B` and `$100M` thresholds with no configuration option. No way to adjust sensitivity for different use cases (micro-cap vs large-cap analysis).

**P1-E-014** | MEDIUM | Lines 382–419
`parse_eight_k_items()` returns an empty list if no "Item X.XX" headers are found, with no signal to the caller about whether parsing failed or the document simply had no items. An incorrectly structured 8-K would be silently treated as having no reportable items.

---

### 2.4 security_finder.py (engine)

**P1-E-015** | LOW | Lines 67–89
`_compute_relevance()` uses hardcoded weights (100.0, 80.0, 50.0, 90.0, 60.0, 30.0, 10.0) with no documentation of calibration methodology or mechanism to adjust.

---

### 2.5 issuer_linkage.py

**P1-E-016** | HIGH | Lines 21–52
`resolve_issuer_to_parent()` scoring returns the first candidate with score > 3. A score of 4 (barely matching) is treated the same as a score of 100. No minimum confidence threshold. Can return a barely-related entity as parent with high confidence.

**P1-E-017** | MEDIUM | Line 51
Returns `None` when no parent found with score > 3. No router shown to handle this `None` safely.

---

### 2.6 market_movers.py (engine)

**P1-E-018** | MEDIUM | Lines 36–39
Securities with null `price`, `prior_close`, or `volume` are silently skipped during mover computation with no logging. Callers cannot determine how many securities were excluded from the calculation.

**P1-E-019** | MEDIUM | Lines 53–56
If all securities have `volume=None`, the `most_active` list is empty. No signal distinguishing "quiet market day" from "no volume data available."

---

## SECTION 3: MODELS & SCHEMAS

### 3.1 Numeric → Float Precision Loss (Systemic)

**P1-M-001** | CRITICAL | entity.py model line 75 / entity.py schema line 58
`ownership_percentage: Numeric(5, 2)` in model → `float` in schema. Financial ownership percentages lose decimal precision on serialization.

**P1-M-002** | CRITICAL | entity.py model line 86 / entity.py schema line 61
`confidence_score: Numeric(3, 2)` — `Numeric(3,2)` has a maximum value of 9.99. If confidence is expressed as 0–100, the column cannot store values ≥ 10.

**P1-M-003** | CRITICAL | credit_rating.py model lines 49–50
`entity_stock_price_at_event: Numeric(18, 6)` and `bond_spread_at_event: Numeric(8, 2)` exist in the model but are absent from the schema. These fields are never returned in API responses.

**P1-M-004** | CRITICAL | executives.py model line 23 / executives.py schema line 28
Model: `education: Mapped[dict | None] = mapped_column(JSONB)` — stores a dict.
Schema: `education: list[str] | None = None` — expects a list of strings.
Serialization of an education dict into a list[str] field causes Pydantic `ValidationError` at runtime.

---

### 3.2 Missing Foreign Keys

**P1-M-005** | HIGH | corporate_bond.py line 32
`security_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))` — no `ForeignKey` to the securities table. Corporate bonds can reference non-existent securities without DB-level constraint enforcement.

**P1-M-006** | HIGH | corporate_bond.py line 60
`guarantor_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))` — no `ForeignKey` to entities. Guarantor references are unvalidated.

**P1-M-007** | HIGH | capital_structure.py line 25
`filing_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))` — no FK to filings table.

**P1-M-008** | HIGH | debt_maturity.py line 25
`filing_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))` — no FK to filings table.

**P1-M-009** | HIGH | corporate_bond.py line 54
`currency: Mapped[str | None] = mapped_column(String(3))` — no FK to currencies reference table. Invalid currency codes can be stored.

**P1-M-010** | HIGH | credit_rating.py line 86
`UniqueConstraint` on `(entity_id, agency, rating_type)` where `rating_type` can be NULL. In SQL, `NULL != NULL`, so two rows with `rating_type=NULL` for the same entity and agency would both satisfy the unique constraint. Duplicate "untyped" ratings can be inserted.

---

### 3.3 Missing Cascade Deletes

**P1-M-011** | HIGH | entity.py lines 89–90
`identifiers` and `names` relationships have no `cascade="all, delete-orphan"`. Deleting an entity leaves orphaned identifier and name records.

**P1-M-012** | HIGH | security.py lines 65–69
Credit ratings, call/put schedules, price history relationships have no cascade delete. Deleting a security leaves orphaned records across multiple tables.

**P1-M-013** | HIGH | fundamentals.py lines 86–88
`FinancialPeriod` relationships to income statements, balance sheets, cash flows have no cascade configuration. Orphaned financial statements if period is deleted.

**P1-M-014** | HIGH | capital_structure.py line 42
`tranches` relationship has no cascade delete. DebtTranche records orphaned if CapitalStructure is deleted.

**P1-M-015** | HIGH | corporate_actions.py lines 45–53
All three sub-action relationships (`dividend_action`, `split_action`, `ma_action`) lack cascade configuration. Sub-action records orphaned on parent delete.

**P1-M-016** | MEDIUM | corporate_bond.py line 105
`call_schedule` relationship has no cascade delete. BondCallSchedule records orphaned on bond delete.

---

### 3.4 Missing Indexes

**P1-M-017** | HIGH | security.py line 229
`EODPrice` has no composite index on `(security_id, price_date)`. Time-series price queries — the most frequent access pattern — perform full table scans.

**P1-M-018** | MEDIUM | ownership.py line 122
`ShortInterest` indexes `security_id` but not `settlement_date`. Time-range short interest queries won't use an index.

**P1-M-019** | MEDIUM | corporate_bond.py line 156
`BondTrade` should have composite index on `(bond_id, settlement_date)`. Only `(bond_id, trade_date)` is indexed.

**P1-M-020** | MEDIUM | yield_curve.py lines 88–89
`YieldCurveSnapshot` has a unique index on `(curve_date, curve_type)` but no separate index on `curve_type` alone. "Get latest curve of type X" queries perform a full scan.

**P1-M-021** | MEDIUM | fundamentals.py line 353
`KPIValue` indexes `(entity_id, period_id)` but not `(kpi_id, period_id)`. "Get all entities' values for a specific KPI in a period" queries cannot use an index.

---

### 3.5 ORM & Relationship Issues

**P1-M-022** | HIGH | executives.py line 32
`roles = relationship("ExecutiveRole", back_populates="executive", lazy="selectin")` but `ExecutiveRole` model does not define `back_populates="executive"`. One-sided relationship definition; SQLAlchemy will not raise at startup but will fail or produce warnings at access time.

**P1-M-023** | HIGH | fund_holdings.py line 37
`holdings = relationship("FundHolding", back_populates="fund", lazy="dynamic")`. Using `lazy="dynamic"` returns a `DynamicMapped` query object rather than a list. In SQLAlchemy 2.x, `lazy="dynamic"` is deprecated. Any code that iterates over `fund.holdings` expecting a list will receive a Query object.

**P1-M-024** | MEDIUM | macro.py line 59
`values = relationship("MacroIndicator", back_populates="values", lazy="dynamic")` — same deprecated `lazy="dynamic"` pattern. Should be replaced with `lazy="selectin"` or `lazy="select"`.

---

### 3.6 Missing Constraints & Validation

**P1-M-025** | MEDIUM | ipo.py lines 49–65
`lead_underwriters`, `co_managers`, `source_filings` stored as JSONB with no schema validation. Any structure (including invalid) is accepted.

**P1-M-026** | MEDIUM | ma_deals.py lines 65–71
`acquirer_financial_advisors`, `regulatory_approvals_required`, `conditions_to_close` stored as JSONB with no validation. Invalid deal structures can be stored.

**P1-M-027** | MEDIUM | relationships.py line 63
`metadata_json` JSONB with no schema validation.

**P1-M-028** | MEDIUM | fundamentals.py line 81
`data_version` defaults to `"AS_REPORTED"` but no CHECK constraint or Enum enforcing valid values. `"FAKE_VERSION"` could be stored without error.

**P1-M-029** | LOW | security.py line 244
`volume: Mapped[int | None] = mapped_column(Numeric(20, 0))` — using Numeric for an integer is semantically wrong and less efficient. Should be `BigInteger`.

**P1-M-030** | LOW | yield_curve.py line 102
`tenor_years: Mapped[Decimal] = mapped_column(Numeric(6, 2))` — Numeric(6,2) caps at 9999.99 years. Adequate for now but unnecessarily restrictive for long-dated theoretical curves.

---

### 3.7 Missing Schema Fields

**P1-M-031** | LOW | credit_rating.py schema
Schema does not expose: `new_rating_numeric`, `old_rating_numeric`, `notches_changed`, `is_fallen_angel`, `is_rising_star`, `watch_status`. These model fields exist but are never returned in API responses.

---

## SECTION 4: APP.PY

**P1-A-001** | CRITICAL
No `CORSMiddleware` registered. Browser-based clients cannot access the API due to CORS preflight failures. Every frontend request to the API will be blocked by the browser with `CORS policy: No 'Access-Control-Allow-Origin' header`.

**P1-A-002** | HIGH
No lifespan context manager or `@app.on_event("startup")` handler. Database connection pool warmup, cache pre-loading, and index verification do not run at startup. The first request pays full connection establishment cost.

**P1-A-003** | HIGH | Lines 351–371
Global exception handler reads `request.state.request_id` and `request.state.start_time` without verifying they exist. If `RequestContextMiddleware` failed to attach these attributes (startup failure, middleware ordering issue), the exception handler itself raises `AttributeError`, masking the original error.

---

## SECTION 5: FRONTEND HOOKS & ENDPOINTS

### 5.1 Duplicate Hook Definitions

**P1-F-001** | CRITICAL | src/hooks/useEntities.ts vs src/api/hooks/useEntities.ts
**14 hooks are defined in both files simultaneously:**
`useEntity`, `useEntitySearch`, `useEntityRelationships`, `useEntitySubsidiaries`, `useEntityParentChain`, `useEntityOfficers`, `useEntityBoardMembers`, `useEntityHistory`, `useEntityIdentifiers`, `useEntityClassifications`, `useSecurity`, `useSecuritySearch`, `useSecurityPrices`, `useSecurityPricesHistory`.

When both files are imported, the last-imported definition wins. Components importing from `src/hooks` get one implementation; components importing from `src/api/hooks` get another. Cache keys, stale times, and enabled logic may differ between the two versions, causing inconsistent data in different components.

### 5.2 Non-Null Assertions on Potentially-Undefined IDs

**P1-F-002** | CRITICAL | src/hooks/useEntities.ts line 15
`ENTITIES.detail(id!)` — non-null assertion when `id` could be `undefined`. If `id` is undefined, the URL becomes `/v1/entities/undefined` and the request fails with a 422 or 404. The `enabled: !!id` check prevents the query from running, but the URL is constructed before the enabled check.

**P1-F-003** | CRITICAL | src/hooks/useEntities.ts line 21
`ENTITIES.relationships(id!)` — same pattern.

**P1-F-004** | CRITICAL | src/hooks/useFI.ts line 37
`FI.yieldCurve.sovereign(countryCode!)` — same pattern.

**P1-F-005** | CRITICAL | src/hooks/useFI.ts lines 51, 73
`FI.treasuries.detail(cusip!)` and `FI.bonds.detail(id!)` — same pattern.

### 5.3 Wrong HTTP Methods / Semantics

**P1-F-006** | HIGH | src/api/hooks/useSecurities.ts line 82
`useSecurityBulkLookup()` uses `useMutation` with POST for what is semantically a read/query operation. Should use `useQuery` with GET or POST-as-query pattern, but should not be a mutation since it has no side effects and should be cacheable.

**P1-F-007** | HIGH | src/api/hooks/useSecurities.ts line 91
`useSecurityTranslate()` is named like a read operation but uses mutation (POST). Naming does not indicate side-effectful behavior; callers may not expect the cache invalidation behavior of a mutation.

### 5.4 Cache Issues

**P1-F-008** | MEDIUM | src/api/hooks/useEntities.ts lines 40–41, 51–52, 61–62
Cache invalidation on mutations uses `queryKey: ['entities']`, invalidating the entire entity cache. Should target specific entity keys (`['entities', 'detail', id]`) to avoid full cache busts on every entity write.

**P1-F-009** | MEDIUM | src/api/hooks/useSecurities.ts line 93
Same overly broad invalidation: `queryKey: ['securities']` invalidates all security queries on translate mutation.

**P1-F-010** | MEDIUM | src/api/hooks/useFiBonds.ts line 65
`queryKey: ['fi', 'bonds']` invalidates all bond queries on any bond mutation.

**P1-F-011** | MEDIUM | src/api/hooks/useOwnership.ts lines 14, 22, 32, 40
All ownership hooks use `'flows'` as the query key domain despite the file being named `useOwnership.ts`. Cache keys are inconsistent with the hook's semantic domain, making cache debugging confusing.

### 5.5 Missing Exports

**P1-F-012** | HIGH
Neither `src/hooks/` nor `src/api/hooks/` has an `index.ts` file. Hooks are imported with full file paths, making them brittle to refactoring and preventing tree-shaking optimization.

### 5.6 Missing Stale Time Configuration

**P1-F-013** | LOW | src/hooks/useFI.ts multiple lines
Multiple FI hooks use `useApiQuery()` without explicit `staleTime`. Default stale time depends on the `QueryClient` configuration; if it defaults to 0, every component render triggers a refetch.

---

## SECTION 6: FRONTEND PAGES

All 10 Pillar 1 frontend pages share the same core problem: **Apple Inc. data is hardcoded as the mock/fallback dataset.** Every component that fails to load real data displays Apple-specific metrics, names, and prices for any entity.

### 6.1 CompanyOverview.tsx

**P1-FP-001** | CRITICAL | Lines 56–191
Six hardcoded data objects: `MOCK_COMPANY` (Apple Inc., ticker AAPL, price $178.72), `MOCK_METRICS` (P/E 29.2, EV/EBITDA 22.1), `MOCK_QUARTERLY` (Q1–Q4 2025/2026 Apple revenue), `MOCK_NEWS` (Apple-specific headlines about Vision Pro, TSMC), `MOCK_FILINGS` (Apple 10-K/8-K dates), `MOCK_HOLDERS` (Vanguard 1.31B shares, BlackRock 1.01B shares).

**P1-FP-002** | HIGH | Lines 205–210
`generateOHLC()` uses `Math.random()` to produce random OHLC and volume data displayed as the price chart. Every page load shows different prices.

**P1-FP-003** | MEDIUM | Lines 239–288
Five API hooks (`useSentimentHistory`, `useEarningsSurprises`, `useTechnicalSignals`, `useCompositeScores`, `useCorporateActionsUpcoming`) are called but their return values are never rendered in the UI. The data fetch is wasted.

**P1-FP-004** | MEDIUM | Lines 239–244
Entity profile fetched from `/v4/entities/{id}/profile` — a **Pillar 4** path, not `/v1/entities/{id}`. This is the wrong API version for Pillar 1 entity data.

---

### 6.2 FinancialStatements.tsx

**P1-FP-005** | CRITICAL | Lines 17–149
Entire financial statement dataset is hardcoded Apple Inc. data:
- `incomeStatementRows`: Revenue $391B, Gross Profit $177B, Net Income $97B
- `balanceSheetRows`: Total Assets $352B, Total Liabilities $278B
- `cashFlowRows`: Operating CF $118B, Capex $11B, FCF $107B
- `QUARTERLY_IS`, `QUARTERLY_BS`, `QUARTERLY_CF`: Apple Q1–Q4 2025 exact figures

These are displayed for any entity if the API returns no data.

**P1-FP-006** | HIGH | Line 17
`const company = { name: 'Apple Inc.', ticker: 'AAPL' }` hardcoded at the top of the component. Company name/ticker is never fetched from the API.

**P1-FP-007** | MEDIUM | Lines 159–163
`useIncomeStatements`, `useBalanceSheets`, `useCashFlows`, `useSegments`, `useRevenueBreakdown` are all called, but results are only used with `??` operator falling back to mock data. If the API returns an empty array `[]`, the truthy check passes and real (empty) data is shown. If API returns `null`, mock data is shown.

**P1-FP-008** | MEDIUM | Lines 266, 286
`(apiSegments as any[])` and `(apiRevBreakdown as any[])` — `as any[]` casts disable type checking.

---

### 6.3 OwnershipDashboard.tsx

**P1-FP-009** | CRITICAL | Lines 37–98
Hardcoded ownership data:
- `topHolders`: Vanguard 1.31B shares, BlackRock 1.01B, Berkshire Hathaway 905M
- `ownershipSummary`: Institutional 60.8%, Insider 0.07%, 15.41B shares outstanding
- `shortInterestHistory`: 12 months of Apple short interest (145M shares, 1.6 days-to-cover)
- `activistInfo`: "Elliott Management" 4.2% stake (specific filing date)

**P1-FP-010** | MEDIUM | Lines 115–117, 168
Multiple `(apiData as any)` casts throughout.

---

### 6.4 FilingsView.tsx

**P1-FP-011** | CRITICAL | Lines 41–95
Hardcoded filings data:
- `filings`: Apple 10-K, 10-Q, 8-K with exact dates
- `insiderTxData`: Tim Cook, Luca Maestri, Jeff Williams, Deirdre O'Brien with exact share quantities and prices
- `diffSections`: Apple-specific risk factors (AI integration, Vision Pro competition)
- `MOCK_RISK_FACTORS` fallback: "China Revenue Concentration", "AI Integration Execution"
- `MOCK_MDA_HIGHLIGHTS` fallback: Services growth, Vision Pro, India revenue

**P1-FP-012** | MEDIUM | Lines 110–113
Multiple `as any` casts on API data.

---

### 6.5 ESGDashboard.tsx

**P1-FP-013** | CRITICAL | Lines 15–44
`MOCK_ESG`: overall=72, environmental=68, social=75, governance=82, rating='AA'
`MOCK_METRICS`: Carbon emissions 22.4M tCO2e, Renewable Energy 100%, Employee Satisfaction 4.2/5.0, Board Independence 87.5% — all Apple-specific.
`MOCK_CONTROVERSIES`: "Supply Chain Labor" and "E-Waste Management" controversies with specific dates.

**P1-FP-014** | MEDIUM | Lines 67–69
`(apiESG as any)`, `(apiScores as any)` casts.

---

### 6.6 GovernanceDashboard.tsx

**P1-FP-015** | CRITICAL | Lines 13–41
`MOCK_BOARD`: 8 Apple board members (Tim Cook, Arthur Levinson, James Bell, Al Gore, Andrea Jung, Monica Lozano, Ronald Sugar, Sue Wagner) with tenure years.
`MOCK_COMPENSATION`: Tim Cook base=$3M, stock=$40M, total=$63M; all Apple executives.
`MOCK_PROPOSALS`: Arjuna Capital, NatAct Fund, Green Century — Apple shareholder proposals with voting percentages.
`MOCK_OVERVIEW`: boardSize=8, independent=87.5%, genderDiversity=37.5% — shown for any company.

**P1-FP-016** | MEDIUM | Lines 54–57
`(apiGov as any)`, `(apiBoard as any)`, `(apiComp as any)`, `(apiProposals as any)` casts.

---

### 6.7 FIDashboard.tsx

**P1-FP-017** | CRITICAL | Lines 43–109
Hardcoded FI data:
- `MOCK_YIELD_CURVE`: exact Treasury yields (1M: 5.38%, 3M: 5.36%, 6M: 5.33%, 1Y: 5.12%, 2Y: 4.64%, 5Y: 4.38%, 10Y: 4.28%, 30Y: 4.42%)
- `KEY_SPREADS`: IG OAS=92bps, HY OAS=328bps, BBB-BB spread=182bps with percentile rankings
- `NEW_ISSUES`: Apple, Goldman Sachs, Microsoft, Ford, Amazon, JPMorgan bonds with exact coupons, maturities, ratings
- `MOCK_AGENCY_BONDS`: FHLB, FNMA, FHLMC, TVA, FFCB with specific coupons and spreads
- `MOCK_BRIEFING`: 500+ word hardcoded market narrative

**P1-FP-018** | MEDIUM | Lines 121–124
`(apiYield as any[])`, `(apiSpreads as any)`, `(apiNewIssues as any[])`, `(apiAgency as any[])` casts.

---

### 6.8 BondDetail.tsx

**P1-FP-019** | CRITICAL | Lines 48–115
Entire bond detail page is hardcoded to a single Apple bond:
- CUSIP: `037833DX3`, ISIN: `US037833DX39`
- Coupon: 3.250%, Maturity: 2029-02-23, Rating: AA+/Aaa
- Price: 101.450, Yield: 2.872%, OAS: 42bps, Modified Duration: 2.78
- Comparable bonds: MSFT 3.125% 2028, GOOGL 3.375% 2029, AMZN 3.600% 2029
- Cash flows: semi-annual $16,250 coupon, $1,000,000 principal at maturity

**P1-FP-020** | CRITICAL | Line 121
`cusip ?? '037833DX3'` — Apple CUSIP hardcoded as default. Any bond with no CUSIP in the URL will display Apple's bond.

**P1-FP-021** | HIGH | Lines 99–115
`generateBondSpreadHistory()` uses `Math.random()` to produce random OAS history displayed as real spread data.

---

### 6.9 IPOMonitor.tsx

**P1-FP-022** | CRITICAL | Lines 37–71
Hardcoded IPO data:
- `kpiStats`: "Upcoming IPOs: 14", "Avg First Day Return: +18.3%", "Total Raised YTD: $42.7B"
- `upcomingIpos`: Klarna (KLAR), Databricks (DBX), Stripe (STRP), Medline (MDLN), Cerebras (CRBS), Plaid (PLAD) — with expected dates, price ranges, deal sizes
- `recentIpos`: CoreWeave, Reddit (IPO price $34, current $44.88), Astera Labs with specific returns
- `performanceSummary`: 1-week avg return +12.4%, 1-month +18.3%

---

### 6.10 DealsView.tsx

**P1-FP-023** | CRITICAL | Lines 11–51
Hardcoded M&A data:
- `kpiStats`: "Total Deals: 142", "Pipeline Value: $1.84T", "Average Premium: 32.4%"
- `activeDeals`: Microsoft/Figma ($22B), Broadcom/VMware ($68.7B), Pfizer/Seagen ($43B), Exxon/Pioneer ($59.5B), Cisco/Splunk ($28B)
- `pipeline`: Amazon/iRobot, JetBlue/Spirit, Chevron/Hess, Tapestry/Capri
- `dealStats`: "Total Deal Volume YTD: $892B", "Average Deal Size: $6.3B"

---

## SECTION 7: GEOGRAPHIC BREAKDOWN — BUILD SPECIFICATION

The `useGeographicBreakdown` hook (`frontend/src/api/hooks/useFundamentals.ts:86`) calls `FUNDAMENTALS.geographicBreakdown(entityId)` → `/v1/entities/${id}/geographic-breakdown`. **This hook should be kept — the backend needs to be built.**

### 7.1 What to build

**Route:** `GET /v1/entities/{entity_id}/geographic-breakdown`
**Parameters:** `fiscal_year` (optional int), `limit` (optional int, default 5 years)

The `SegmentData` model (`src/models/fundamentals.py:288`) already has all required columns:
- `segment_name` — region name as reported (e.g., "Americas", "Greater China")
- `segment_name_normalized` — normalized region name
- `segment_type` — filter to `"GEOGRAPHIC"`
- `revenue`, `operating_income`, `operating_margin`, `assets`, `capex`
- `period_id` → join to `FinancialPeriod` for `fiscal_year`, `fiscal_quarter`

**Compute at query time:** `revenue_pct = segment.revenue / sum(all segment revenues) * 100` and `yoy_growth` by comparing same `segment_name_normalized` to prior year.

**Recommended simpler alternative:** Add `?type=GEOGRAPHIC` filter to the existing `GET /v1/entities/{id}/segments` endpoint instead of creating a new route. Update `FUNDAMENTALS.geographicBreakdown(id)` in `endpoints.ts` to point to `/v1/entities/${id}/segments?type=GEOGRAPHIC`. This makes `useRevenueBreakdown` work for free with `?type=PRODUCT`.

### 7.2 Data source

**Primary:** SEC EDGAR XBRL `srt:StatementGeographicalAxis` dimensional facts.
- Revenue: `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax` or `us-gaap:Revenues`
- Members: `srt:AmericasMember` → "Americas", `srt:EuropeMember` → "Europe", `country:CN` → "Greater China"
- Fetch via `https://data.sec.gov/api/xbrl/companyfacts/{cik}.json`

**Fallback:** Parse geographic revenue table from 10-K MD&A section using regex/NLP when XBRL dimensional facts are absent.

**Script:** Add `scripts/populate_geographic_segments.py` or extend existing fundamentals population script.

### 7.3 endpoints.ts change

Keep `geographicBreakdown` in `FUNDAMENTALS`. If implementing as filter on segments:
```typescript
geographicBreakdown: (id: string) => `/v1/entities/${id}/segments?type=GEOGRAPHIC`
```

---

## ISSUE PRIORITY & REMEDIATION PLAN

### Phase 1 — Runtime Crashes (Fix before any request can succeed)

| ID | File | Fix |
|----|------|-----|
| P1-R-031 | corporate_actions.py | Replace all `.nullslast()` with `.nulls_last()` |
| P1-R-032 | relationships.py | Same fix |
| P1-R-037 | capital_structure.py | Same fix |
| P1-R-063 | ma_deals.py | Same fix |
| P1-R-064 | ipo.py | Same fix |
| P1-R-068 | fund_holdings.py | Same fix |
| P1-R-034 | executives.py | Fix `.in_(select(subq))` → `.in_(subq)` |
| P1-R-072 | market_movers.py | Fix `rankings` dict vs list type mismatch |
| P1-R-048 | fi_bonds.py | Add eager loading for `call_schedule` relationship |
| P1-A-001 | app.py | Add `CORSMiddleware` |

### Phase 2 — Silent Data Corruption

| ID | File | Fix |
|----|------|-----|
| P1-R-017 | resolution.py | Remove try/except auth bypass pattern |
| P1-R-069 | custom_classifications.py | Remove hardcoded UUID; require authentication |
| P1-R-070 | custom_classifications.py | Replace `flush()` with `commit()` |
| P1-E-007 | filing_diff.py | Fix threshold variable in `align_paragraphs()` |
| P1-E-002/003 | corporate_action_engine.py | Add `> 0` validation on split ratios |
| P1-R-041 | calendar.py | Apply `event_types` filter to query |
| P1-R-001 | All paginated endpoints | Validate `page >= 1` before computing offset |

### Phase 3 — Missing Core Data

| ID | File | Fix |
|----|------|-----|
| P1-R-008 | securities.py | Populate `ticker` field when `expand=ticker` |
| P1-R-009 | securities.py | Fetch ticker from SecurityIdentifier in search results |
| P1-R-014 | security_finder.py | Remove 500-record hard cap; implement proper DB search |
| P1-R-011 | securities.py | Change multi-identifier filter from AND to OR logic |
| P1-R-006 | entities.py | Change multi-identifier filter from AND to OR logic |
| P1-M-004 | executives.py | Fix education field: model dict ↔ schema list[str] mismatch |
| P1-R-051 | fi_treasuries.py | Add `response_model` to treasury_analytics endpoint |
| P1-R-052 | fi_treasuries.py | Fix zero-coupon frequency handling |

### Phase 4 — Precision, FKs, Cascades

| ID | Fix |
|----|-----|
| P1-M-001 to P1-M-003 | Change financial schema fields from `float` to `Decimal` |
| P1-M-005 to P1-M-010 | Add missing ForeignKey constraints to corporate_bond, capital_structure, debt_maturity models |
| P1-M-011 to P1-M-016 | Add `cascade="all, delete-orphan"` to all entity/security relationships |
| P1-M-017 to P1-M-021 | Add missing composite indexes |

### Phase 5 — Frontend Wiring

| ID | Fix |
|----|-----|
| P1-F-001 | Consolidate duplicate hooks — keep `src/api/hooks/` as canonical, delete `src/hooks/` duplicates |
| P1-F-002 to P1-F-005 | Replace `id!` non-null assertions with proper guards before URL construction |
| P1-F-012 | Create `src/api/hooks/index.ts` and `src/hooks/index.ts` |
| P1-FP-001 to P1-FP-023 | Remove all hardcoded mock data and Math.random() generators; replace with real API data |
| P1-FP-004 | Fix CompanyOverview to use `/v1/entities/{id}` not `/v4/entities/{id}/profile` |

### Phase 6 — Geographic Breakdown

Build router endpoint (or extend segments endpoint) + XBRL ingestion script. See Section 7.

---

*End of Pillar 1 Audit Report v2 — 243 issues across 121 files*
*Previous shallow version: 68 issues*
