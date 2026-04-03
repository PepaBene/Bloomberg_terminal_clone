# Pillar 3 Intelligence — Deep Audit Report v2

**Date:** 2026-04-03
**Scope:** Every engine, router, model, app.py registration, and frontend component in Pillar 3 (Intelligence) and Pillar 4 (Research)
**Method:** Static code analysis of every file — no tests run
**Total Issues Found:** 147
**Prior Report:** PILLAR_3_AUDIT_REPORT.md (74 issues) — this report supersedes it

---

## Executive Summary

The v1 report identified the obvious stubs (LLM client, Q&A placeholder, briefing skeleton). This report goes line by line through every engine, router, model, and frontend page. The findings are considerably worse:

1. **Two runtime crashes** exist in deployed code that have nothing to do with the AI layer: a broken import in `news_propagation.py` that crashes on module load, and a `.nulls_last()` / `desc("string")` SQLAlchemy API misuse in two calendar/news routers that throws `AttributeError` / SQL errors on every request.

2. **The entire governance scoring engine** (6 functions, ~300 lines of real computation) is dead code — the router never calls it.

3. **Sixteen routers** use `session.flush()` without `session.commit()` — mutations that appear to succeed silently discard data on certain connection paths.

4. **Every Pillar 3 frontend page** uses the `(apiData as any)?.field ?? mockData` fallback pattern. The mock data contains hardcoded Apple Inc., AAPL, Tim Cook, specific financial figures, and real board member names — all shown as live data to any user visiting any company page.

5. **Five engines** are fully implemented but not wired to any router: `macro_thematic_engine.py`, `macro_scenario_engine.py`, `news_dedup.py`, `political_intelligence.py` (engine functions), and most of `fi_intelligence.py`.

6. **Three mathematical errors** produce wrong computed values: the CCC improvement sign in `management_quality_engine.py`, the HHI calculation in `industry_cycle.py`, and the ROIC-WACC spread used as a trend proxy in `industry_economics.py`.

---

## Part 1: Engine Layer — 52 Issues

### E-001: news_propagation.py — Broken Import Crashes Module Load
**File:** `src/engines/news_propagation.py`, line 195
**Severity:** Critical

```python
from src.engines.economic_calendar_engine import RELEASE_TYPES
```

`economic_calendar_engine.py` does not exist in `src/engines/`. This import executes at module load time. Any code path that imports `news_propagation` will raise `ImportError` and abort. The `news.py` router likely imports this engine; if it is in a `try/except` in `app.py` the entire news propagation feature group disappears silently at startup. Lines 205–210 have a hardcoded fallback dict, but this is never reached because the module never finishes loading.

**Fix:** Either create `src/engines/economic_calendar_engine.py` with a `RELEASE_TYPES` dict, or replace line 195 with the inline fallback dict and remove the import.

---

### E-002: competitive_landscape.py — Parameter Name Mismatch → AttributeError
**File:** `src/engines/competitive_landscape.py`, line 326–327
**Severity:** Critical

```python
industry_trends.get("revenue_growth")   # line 327
```

The function signature uses `industry_stats` (line 366) as the parameter name, but inside the function body it references `industry_trends`. `industry_trends` is never defined, so every call to `analyze_competitive_landscape()` that passes industry statistics raises `NameError: name 'industry_trends' is not defined`.

---

### E-003: management_quality_engine.py — CCC Score Sign Likely Inverted
**File:** `src/engines/management_quality_engine.py`, lines 189–194
**Severity:** Critical

```python
improvement = (first - second) / abs(first)   # line 189
score = 50.0 + improvement * 250.0             # line 194
```

For Cash Conversion Cycle (CCC), **lower is better**. A company that reduced CCC from 40 to 30 days should score above 50. But the formula computes `(first - second)` = `(40 - 30)` = `+10`, giving a positive improvement — which is correct for this case. However if CCC *increased* from 30 to 40, the formula gives `-10`, scoring below 50 — also seemingly correct. On re-examination: if first=0 (zero CCC, perfect), `abs(first)=0` → division by zero. Additionally, the formula uses `first` as the period-1 value; if the history list is ordered oldest-first, `first` is the oldest (worst baseline), not the most recent. The direction of "improvement" depends entirely on list ordering, which is undocumented. Any list ordered newest-first will produce inverted scores.

---

### E-004: management_quality_engine.py — Division by Zero on Zero Guidance Actual
**File:** `src/engines/management_quality_engine.py`, line 95
**Severity:** Critical

```python
error = abs(actual - guided) / abs(actual)
```

If `actual == 0` (company reported zero earnings, e.g., at breakeven), this divides by zero. There is no guard clause at line 94 or 95.

---

### E-005: management_quality_engine.py — Documented Weights Don't Match Code
**File:** `src/engines/management_quality_engine.py`, lines 323, 333, 336
**Severity:** High

The docstring states scoring is: Execution 35pts, Accounting flags 25pts, Governance 20pts, Compensation 20pts. The code applies:
- Line 323: `execution_score * 0.70` (not a 35-point contribution)
- Line 333: `governance_score * 0.20`
- Line 336: `compensation_score * 0.20`

The weights sum to 1.10, not 1.00. Total possible score can exceed 100 for high-scoring companies.

---

### E-006: industry_cycle.py — HHI Calculation Wrong When Shares Don't Sum to 100
**File:** `src/engines/industry_cycle.py`, lines 230–235
**Severity:** High

```python
normalized = [(s / total) * 100.0 for s in market_shares]
return sum(s * s for s in normalized)
```

If `market_shares` is `[30, 25, 15]` (top 3 players, shares that don't sum to 100), `total=70`. The normalization re-scales to `[42.9, 35.7, 21.4]` summing to 100, producing HHI ≈ 3204. The correct HHI for `[30, 25, 15]` over the full market would depend on what the remaining 30% represents. Re-normalizing to 100% artificially inflates HHI for partial share data, making fragmented markets look concentrated.

---

### E-007: industry_economics.py — ROIC Spread Used as Trend Proxy
**File:** `src/engines/industry_economics.py`, lines 82, 158–159
**Severity:** High

```python
roic_trend = spread if spread is not None else 0.0   # line 158
```

A level (ROIC-WACC spread at a point in time) is used as a trend (direction of change). A company with a +5% ROIC spread that has been declining for 3 years is labelled "positive trend" because the current spread is positive. A company with -1% spread that just turned the corner from -10% is labelled "negative trend". The comment at line 155 acknowledges this but the code proceeds with the wrong approach.

---

### E-008: capital_allocation_engine.py — Array Index Without Bounds Check
**File:** `src/engines/capital_allocation_engine.py`, line 168
**Severity:** High

```python
ratios[-1]
```

At line 164, `goodwill_history` is checked for length (`len(goodwill_history) >= 4`), but if the earlier branch (line 162) is taken with shorter history, `ratios[-1]` may be called on an empty list, raising `IndexError`.

---

### E-009: global_macro.py — YTD Rate Changes Labelled as Current Stance
**File:** `src/engines/global_macro.py`, lines 120–147
**Severity:** High

```python
if ytd_bps > 0:
    stance = "HAWKISH"
```

Year-to-date cumulative rate changes reflect the history of past decisions, not the current policy stance. A central bank that hiked 300bps through June and then paused for 6 months would be labelled HAWKISH through year-end despite being on hold. The `last_action` field is available in the data but is not used for stance classification.

---

### E-010: country_risk.py — Sanctions Base Score of 20 for Zero Programs
**File:** `src/engines/country_risk.py`, line 261
**Severity:** High

```python
if programs <= 2:
    base_score = 20.0 + programs * 10
```

A country with zero active sanctions programs gets a base sanctions risk score of 20 (out of 100). This is non-zero and will inflate the overall country risk for sanctions-clean countries. The formula should yield 0 for `programs == 0`.

---

### E-011: country_risk.py — KeyError on Segment Dicts Without Required Keys
**File:** `src/engines/country_risk.py`, lines 414, 420, 426
**Severity:** High

```python
country_code=seg["country_code"],   # KeyError if missing
exposure_pct=float(seg["pct"]),     # KeyError if missing
```

Geographic segment dicts sourced from the database may not contain `country_code` or `pct` keys if they were stored in a different schema. There is no `.get()` with a default, no try/except, and no pre-validation. Any segment missing either key crashes the function.

---

### E-012: eight_k_engine.py — Duplicate "appointed" in Action Keywords
**File:** `src/engines/eight_k_engine.py`, line 307
**Severity:** Medium

```python
action_keywords = ["appointed", "resigned", "terminated", "appointed"]
```

Index 3 is `"appointed"` instead of a different action (e.g., `"promoted"` or `"elected"`). Regex group 4 will always resolve to "appointed" instead of the intended fourth action type.

---

### E-013: earnings_surprise_intelligence.py — Crashes If surprise_pct Is None
**File:** `src/engines/earnings_surprise_intelligence.py`, line 328
**Severity:** High

```python
f"{abs(eps_analysis.surprise_pct):.1f}%"
```

`surprise_pct` can be `None` when consensus is zero (see E-014). Calling `abs(None)` raises `TypeError`. There is no None check before this f-string format call.

---

### E-014: earnings_surprise_engine.py — Zero Consensus Treated as 100% Surprise
**File:** `src/engines/earnings_surprise_engine.py`, lines 87–88
**Severity:** Medium

```python
if consensus == 0:
    return SurpriseResult(surprise_pct=100.0 if actual > 0 else 0.0)
```

A company with no analyst coverage (consensus = 0) that reports any positive earnings is given a 100% surprise. This is semantically incorrect — no consensus means no surprise can be computed — and it will create outlier data in surprise aggregations.

---

### E-015: earnings_surprise_engine.py — Majority Vote Flawed for Mixed Results
**File:** `src/engines/earnings_surprise_engine.py`, lines 93–110
**Severity:** Medium

If EPS beats (+15%), revenue misses (−5%), and EBITDA misses (−3%), the majority logic marks this as a miss (2-of-3 misses). But EPS is the most material metric by analyst focus. The equal-weight majority vote produces misleading beat/miss classification for companies where one metric dominates.

---

### E-016: competitive_landscape.py — share_trend / margin_trend Never Set by Caller
**File:** `src/engines/competitive_landscape.py`, line 320
**Severity:** Medium

`identify_competitive_threats()` accesses `entity_data.get("share_trend")` and `entity_data.get("margin_trend")`. These keys are never populated by `analyze_competitive_landscape()` (the orchestrator) before calling this function. Both always return `None`, so competitive threat detection based on share/margin trends is permanently disabled.

---

### E-017: business_model_engine.py — Cyclicality Returns Hardcoded Neutral for Short History
**File:** `src/engines/business_model_engine.py`, lines 188–195
**Severity:** Medium

```python
if len(revenue_history) < 3:
    return 50.0   # Unknown/insufficient data
```

The function returns exactly 50.0 (neutral) with no flag or indicator that this is a data-quality fallback. Any company with fewer than 3 years of history appears to have perfectly neutral cyclicality, which is likely wrong for IPO-stage or recently restructured companies.

---

### E-018: business_model_engine.py — Moat Detection Requires Exactly 2+ Keyword Hits
**File:** `src/engines/business_model_engine.py`, lines 271–322
**Severity:** Medium

The moat detection uses substring matching against a keyword dictionary. Line 322 discards any detected moat with fewer than 2 keyword hits. A company with one very strong moat keyword gets `detected_moat = None`. The threshold is arbitrary and undocumented.

---

### E-019: global_macro.py — Ambiguous Central Bank Statement Gets Arbitrary Classification
**File:** `src/engines/global_macro.py`, line 88
**Severity:** Medium

`classify_policy_stance()` iterates `STANCE_KEYWORDS.items()` and returns the first matching stance. If a Fed statement contains both "inflation concern" (→ HAWKISH) and "rate cut" (→ DOVISH), the outcome is determined by dictionary insertion order, not semantic priority. Pre-Python 3.7 this was non-deterministic; in 3.7+ it's deterministic but arbitrary.

---

### E-020: industry_cycle.py — Revenue Acceleration Not a True Second Derivative
**File:** `src/engines/industry_cycle.py`, lines 45–46
**Severity:** Medium

```python
recent = statistics.mean(growth_rates[len(growth_rates) // 2:])
prior  = statistics.mean(growth_rates[:len(growth_rates) // 2])
```

This computes the difference between two period averages, not a true acceleration (second derivative). For volatile growth series, this is unreliable. True acceleration requires polynomial regression or consecutive-period differences.

---

### E-021: moat_assessment.py — Evidence List Empty for Companies Scoring 48 on All Metrics
**File:** `src/engines/moat_assessment.py`, lines 547–551
**Severity:** Low

Evidence is only appended when a sub-score exceeds 50. A company with consistent 48/100 moat scores (significant moat evidence but below threshold) returns an empty evidence list, giving the false impression of no evidence found.

---

### E-022: global_macro.py — Returns 0.0 For No Inflation Data Instead of None
**File:** `src/engines/global_macro.py`, line 234
**Severity:** Low

```python
global_median = round(median(headlines), 2) if headlines else 0.0
```

Zero inflation is a valid and meaningful economic reading. Returning 0.0 when no data exists is semantically indistinguishable from genuine zero inflation, corrupting any downstream comparison.

---

### E-023: macro_thematic_engine.py / macro_scenario_engine.py — Not Wired to Any Router
**File:** Both engine files
**Severity:** High

Both `macro_thematic_engine.py` and `macro_scenario_engine.py` are fully implemented but are not imported by any router file. Their computations are inaccessible through the API. `macro_scenario_engine.py` line 340–361 also builds scenario narratives via string templating rather than LLM generation, consistent with the universal AI gap.

---

### E-024: fi_intelligence.py — entity_id Hardcoded as Empty String
**File:** `src/engines/fi_intelligence.py`, line 342
**Severity:** Medium

```python
entity_id=""
```

`build_issuer_credit_profile()` is called with a hardcoded empty string as the entity ID. Any DB insertion or lookup using this value will either fail or pollute the database with records keyed to an empty string.

---

### E-025: political_intelligence.py — Sort on Missing Date Key → KeyError
**File:** `src/engines/political_intelligence.py`, line 320–334
**Severity:** Medium

```python
sorted(actions, key=lambda s: s["date_imposed"])
```

If any sanction dict lacks a `"date_imposed"` key, this raises `KeyError`. Sanctions data sourced from external feeds frequently has missing or null dates.

---

### E-026: cross_asset_narrative.py — Fallen Angel Detection Too Restrictive
**File:** `src/engines/cross_asset_narrative.py`, lines 80–98
**Severity:** Low

`detect_fallen_angel_overhang()` returns `None` if rating is not in the BBB tier OR if momentum is not DETERIORATING. An issuer rated BBB+ with STABLE momentum but 60% forced-seller ownership (high fallen angel overhang risk) is silently discarded. The function should return a MEDIUM risk result for high forced-seller scenarios regardless of momentum.

---

### E-027: transcript_engine.py — Sentence Splitter Breaks on Abbreviations
**File:** `src/engines/transcript_engine.py`, line 285
**Severity:** Low

`_split_sentences()` splits on period + space. "Dr. Smith said revenues grew" splits into "Dr." and "Smith said revenues grew." Hedging ratios and forward-looking statement counts built on this splitter will have inflated numerators for any transcript that uses honorifics or abbreviations.

---

### E-028: transcript_engine.py — "AI" Filtered Out as Too-Short Word
**File:** `src/engines/transcript_engine.py`, line 502
**Severity:** Low

```python
if len(word) < 3: continue
```

"AI" (2 characters) is filtered out of topic extraction. In technology/AI company transcripts this is one of the most significant topic words.

---

### E-029: alert_expansion.py — Fallen Angel Check Only Matches BBB-, Ignores Moody's/Fitch
**File:** `src/engines/alert_expansion.py`, line 89
**Severity:** Medium

```python
current_rating != "BBB-"
```

This only checks S&P BBB-. The Moody's equivalent is Baa3, and Fitch uses BBB- (same notation). If ratings data stores Moody's notation, the fallen angel threshold check always passes, generating false positives or missing real fallen angels.

---

### E-030: alert_expansion.py — Insider Cluster Counts Transactions, Not Unique Insiders
**File:** `src/engines/alert_expansion.py`, line 329
**Severity:** Medium

```python
if insider_buys >= 3:
    # "cluster buy" alert
```

If a single CEO buys 5 times in 30 days, `insider_buys=5` triggers the cluster alert as if 5 different insiders purchased. A cluster of one person is not a cluster signal.

---

### E-031: alert_expansion.py — Short Interest Spike Not Scale-Adjusted
**File:** `src/engines/alert_expansion.py`, line 323
**Severity:** Low

```python
if short_change > 25.0:
```

A 25% increase in short interest from 5% to 6.25% (absolute) is vastly different from 25% increase from 50% to 62.5%. The threshold is not adjusted for base short interest level.

---

### E-032: alert_engine.py — Only First Matching Rule Fires per Event
**File:** `src/engines/alert_engine.py`, line 128
**Severity:** Medium

```python
break   # after first rule match
```

If an 8-K event matches both a CRITICAL rule and a HIGH rule configured for the same entity, only the first rule (by iteration order) fires. The second alert is silently dropped. For watchlist entities with multiple overlapping rules, this causes alert gaps.

---

### E-033: alert_engine.py — Rate Limiting Silently Drops Alerts Including CRITICAL
**File:** `src/engines/alert_engine.py`, lines 285–290
**Severity:** Medium

The per-entity alert cap silently discards alerts when the limit is reached. There is no "alerts suppressed" indicator in the response. CRITICAL alerts for a busy entity can be dropped without any record. The cap should at minimum preserve CRITICAL severity alerts regardless of volume.

---

### E-034: insider_signals.py — date.fromisoformat() Crashes on Malformed Dates
**File:** `src/engines/insider_signals.py`, lines 96, 113, 119, 188, 195
**Severity:** Medium

`date.fromisoformat(txn["transaction_date"])` has no try/except wrapper. SEC Form 4 transaction dates from third-party feeds sometimes arrive in formats like "20240115" (no hyphens) or "01/15/2024", which raise `ValueError` and abort the entire function call.

---

### E-035: news_entity_linker.py — Fuzzy Match Threshold Not Configurable
**File:** `src/engines/news_entity_linker.py`, line 137
**Severity:** Low

The 0.85 similarity threshold is hardcoded. "Goldman Sachs" would match "Goldman Sachs Group" at ~0.89 (passes), but "Apple" vs "Apple Inc." might score ~0.77 (fails). The threshold should be configurable per entity type or match scenario.

---

### E-036: earnings_surprise_intelligence.py — EPS and Revenue Surprise Weighted Equally
**File:** `src/engines/earnings_surprise_intelligence.py`, line 241
**Severity:** Low

```python
combined = abs(eps_surprise_pct) + abs(revenue_surprise_pct)
```

For most equity analysts, an EPS surprise of ±5% is far more significant than a revenue surprise of ±5%. The simple sum treats them identically, producing misleading combined revision signals.

---

---

## Part 2: Router Layer — 55 Issues

### R-001: economic_calendar.py — .nulls_last() Throws AttributeError at Runtime
**File:** `src/api/routers/economic_calendar.py`, line 49
**Severity:** Critical

```python
.order_by(EconomicRelease.surprise_magnitude.desc().nulls_last())
```

SQLAlchemy's `ColumnElement.desc()` returns an `UnaryExpression` which does **not** have a `.nulls_last()` method. The correct syntax is `nullslast(EconomicRelease.surprise_magnitude.desc())` or `EconomicRelease.surprise_magnitude.desc().nulls_last()` only works in SQLAlchemy ≥ 2.0 with specific column types. If this router is imported, every call to `GET /news/calendar/economic/surprises` raises `AttributeError`.

---

### R-002: news.py — desc("mention_count") String Literal Causes SQL Error
**File:** `src/api/routers/news.py`, line 109
**Severity:** Critical

```python
.order_by(desc("mention_count"))
```

`desc()` with a string literal generates an ORDER BY clause using the raw string as a column name. The actual column is on a subquery alias, not a table column. This produces an invalid SQL query and every call to `GET /news/most-mentioned` returns a database error.

---

### R-003: fi_intelligence.py — .in_(["YIELD_CURVE", None]) Wrong SQLAlchemy Syntax
**File:** `src/api/routers/fi_intelligence.py`, lines 53, 89, 125
**Severity:** Critical

```python
FIMarketBriefing.briefing_type.in_(["YIELD_CURVE", None])
```

`Column.in_()` with `None` in the list generates `briefing_type IN ('YIELD_CURVE', NULL)` which is invalid SQL — `IS NULL` must be used for null comparisons. SQLAlchemy may silently drop the None or raise, but the filter logic is wrong regardless. Three yield curve endpoints are affected.

---

### R-004: global_intelligence.py — Incomplete Function Body
**File:** `src/api/routers/global_intelligence.py`, lines 571–585
**Severity:** Critical

`get_country_indicators()` function is defined but its body is truncated mid-SELECT statement. The function likely raises a `SyntaxError` at import time, or if the file loaded despite the truncation, every call to `GET /global/macro/{country_code}/indicators` returns a 500 error.

---

### R-005: governance_intelligence.py — governance_scoring.py Never Called — 6 Functions Dead Code
**File:** `src/api/routers/governance_intelligence.py`, `src/engines/governance_scoring.py`
**Severity:** Critical

`governance_scoring.py` contains these fully-implemented functions:
- `detect_red_flags()`
- `compute_governance_score()`
- `compute_pay_alignment()`
- `compute_board_diversity()`
- `detect_board_interlocks()`
- `analyze_shareholder_proposals()`

**None** are called from `governance_intelligence.py`. The router returns pre-stored rows from the database. Since no batch job populates those rows (see BUG-041 from v1), governance scores are computed by neither path — the engine exists and is never invoked, and the DB is never populated. The entire governance scoring feature is non-functional end-to-end.

---

### R-006: governance_scoring.py — has_majority_voting Defaults to True (False Negatives)
**File:** `src/engines/governance_scoring.py`, line 221
**Severity:** High

```python
if not governance_data.get("has_majority_voting", True):
```

The default is `True` ("company has majority voting"), meaning if the field is absent from the data, the red flag is **not** raised. Companies that never provided this governance disclosure will appear to have majority voting protections. The default should be `False` to err on the side of caution.

---

### R-007: filing_intelligence.py — None Dereference After scalar_one_or_none()
**File:** `src/api/routers/filing_intelligence.py`, lines 214–222, 251–268
**Severity:** High

```python
year_old = await session.scalar(...)  # may return None
# ... no None check ...
WHERE FilingDiff.year_old == year_old  # crashes if None
```

`scalar_one_or_none()` may return `None` if no rows match. At lines 222 and 268, this value is used directly in a SQL WHERE clause without a prior None check, raising a database error or returning wrong results.

---

### R-008: sentiment_p2.py — Watchlist Digest Is a Confirmed Stub
**File:** `src/api/routers/sentiment_p2.py`, line 77
**Severity:** High

The docstring explicitly states: *"In a full implementation this would filter by user's watchlist entities. Currently returns the same as the general digest."* The function body is identical to `get_daily_digest()`. No watchlist filtering is applied. `GET /news/digest/watchlist` is functionally identical to `GET /news/digest`.

---

### R-009: sentiment_p2.py — 7D and 90D Sentiment Always None
**File:** `src/api/routers/sentiment_p2.py`, lines 54–63
**Severity:** High

```python
sentiment_7d=None,
sentiment_90d=None,
```

In `screen_by_sentiment()`, the 7-day and 90-day sentiment fields are always `None`. Only 30-day sentiment is populated. The response schema exposes these fields but they are permanently null.

---

### R-010: sentiment_p2.py — peer_rank_pct Mapped to peer_median Field
**File:** `src/api/routers/sentiment_p2.py`, lines 300–305
**Severity:** Medium

```python
peer_median=row.peer_rank_pct,
```

`peer_rank_pct` (a percentile rank, 0–100) is assigned to the `peer_median` response field (which should be an absolute sentiment score, typically –1.0 to +1.0). Clients receive percentile rank data in a field they interpret as a median sentiment value.

---

### R-011: research_notes.py — DEFAULT_USER Hardcoded, Breaks Multi-Tenancy
**File:** `src/api/routers/research_notes.py`, line 50
**Severity:** Critical

```python
user_id = DEFAULT_USER
```

`DEFAULT_USER` is a hardcoded string constant. Every research note created, updated, or deleted is attributed to the same user regardless of who made the request. In any multi-user deployment, notes from different users overwrite each other's ownership, and user-scoped queries return everyone's notes.

---

### R-012: All Research Routers — flush() Without commit() (16 locations)
**Files:** research_qa.py:67, research_briefings.py:179, research_search.py:48, research_anomalies.py:172/182/200/220, research_primers.py:142/167, research_themes.py:112/144, research_notes.py:62/148/167/187, research_thesis.py:226/265, research_alerts_p4.py:239/287
**Severity:** High

`session.flush()` sends SQL to the database within the current transaction but does **not** commit. With `autocommit=False` (SQLAlchemy default), the transaction is rolled back if the connection is closed, an exception occurs, or the connection pool recycles the connection. In practice, data from any of these 16 mutation endpoints may silently disappear. The correct pattern is `session.commit()` after all mutations. Note: `company_primer.py` is the only research router that correctly uses `commit()`.

---

### R-013: company_primer.py — Generates Primer From Empty Dicts
**File:** `src/api/routers/company_primer.py`, lines 70–81
**Severity:** High

```python
financial_data = {}
valuation_data = {}
ownership_data = {}
risk_data = {}
# comment: "In production, assemble from DB"
generate_primer(..., financial_data=financial_data, ...)
```

`generate_primer()` is called with all four data dicts empty. The engine has no data to work with and will produce a primer with all financial sections blank. The LLM client is imported on line 69 but never used (`ai_description=None`, `ai_competitive=None` on lines 80–81).

---

### R-014: fi_intelligence.py — Auction Endpoint Has No Auction Filter
**File:** `src/api/routers/fi_intelligence.py`, line 109
**Severity:** High

`GET /fi/yield-curve/auctions` is documented as returning "auction-related yield curve data" but the query has no WHERE clause filtering for auctions. It returns the latest 10 `FIMarketBriefing` records regardless of content, identical to the general briefing endpoint.

---

### R-015: fi_intelligence.py — Rating Narrative Is a Hardcoded Template
**File:** `src/api/routers/fi_intelligence.py`, line 207
**Severity:** Medium

```python
rating_narrative = f"Latest issuance rated {latest_issuance.rating}"
```

`GET /fi/issuers/{entity_id}/rating-narrative` returns a one-sentence hardcoded string. No analysis, trend, or context is generated. The endpoint implies narrative intelligence but delivers a database field interpolation.

---

### R-016: alerts_expansion.py — credit_regime Assigned to severity Field
**File:** `src/api/routers/alerts_expansion.py`, line 130
**Severity:** High

```python
severity=row.credit_regime
```

`credit_regime` contains values like `"TIGHT"`, `"NORMAL"`, `"LOOSE"`. The `SpreadMoveResponse.severity` field expects `"HIGH"`, `"MEDIUM"`, `"LOW"`. Every response from `GET /alerts/fi/regime` has an invalid severity value.

---

### R-017: alerts_expansion.py — Random UUID Generated for Missing entity_id
**File:** `src/api/routers/alerts_expansion.py`, lines 152, 162
**Severity:** High

```python
uuid.UUID(entity_id) if entity_id else uuid.uuid4()
```

When `entity_scope.get("entity_id")` returns `None`, a random UUID is generated as a fallback. The client receives an `entity_id` that does not exist in the database. Any follow-up query using this UUID returns 404.

---

### R-018: alerts_expansion.py — Flow Direction Derived From Threshold, Not Actual Flow
**File:** `src/api/routers/alerts_expansion.py`, line 165
**Severity:** Medium

```python
direction="INFLOW" if row.threshold_value and float(row.threshold_value) > 0 else "OUTFLOW"
```

`threshold_value` is the alert trigger threshold (the configured limit), not the actual observed flow direction. A threshold of `+50M` does not mean the flow was an inflow. Direction should be derived from the actual flow data field.

---

### R-019: industry.py — .nulls_last() AttributeError
**File:** `src/api/routers/industry.py`, line ~95
**Severity:** Critical

Same pattern as R-001. `.nulls_last()` called on a SQLAlchemy `UnaryExpression` in the industry rankings endpoint.

---

### R-020: industry.py — get_industry_companies Returns No Companies
**File:** `src/api/routers/industry.py`, lines 160–168
**Severity:** High

`GET /industry/{gics_code}/companies` is documented as returning companies in a given industry. The endpoint returns only `{ company_count, gics_code, gics_name }` — no company list, no tickers, no entity IDs. The endpoint name is misleading and the response is useless for the stated purpose.

---

### R-021: industry.py — rank_industries Loads All Rows Then Deduplicates in Python
**File:** `src/api/routers/industry.py`, lines 76–93
**Severity:** Medium

The rankings endpoint fetches all `IndustryProfile` rows across all dates into memory, then deduplicates in Python to keep only the latest per GICS code. For large datasets this loads every historical snapshot. The correct approach is `DISTINCT ON (gics_code) ORDER BY gics_code, as_of_date DESC` or a `ROW_NUMBER()` window function.

---

### R-022: global_intelligence.py — All Geopolitical Events Loaded Into Memory for Filtering
**File:** `src/api/routers/global_intelligence.py`, lines 256–276
**Severity:** High

`get_country_events()` fetches ALL `GeopoliticalEvent` rows, then filters by `country_code` in Python. For a geopolitical events table with thousands of records, this loads the entire table on every request. The filter should be pushed to SQL using `GeopoliticalEvent.countries_involved.contains(country_code)` or a proper JSONB operator.

---

### R-023: global_intelligence.py — Supply/Demand Signal Is Fake Arithmetic
**File:** `src/api/routers/global_intelligence.py`, lines 701–704
**Severity:** Medium

`GET /global/commodities/{code}/supply-demand` computes supply/demand balance by multiplying price trend by arbitrary factors (1.05 and 0.95). There is no actual supply or demand data. The endpoint returns a number derived from price alone, mislabelled as "supply-demand indicator."

---

### R-024: news.py — N+1 Query Pattern in News Stats
**File:** `src/api/routers/news.py`, lines 126–171
**Severity:** Medium

`GET /news/stats` executes 5 separate database queries in sequence. These could be combined into a single query using subqueries. Under load this multiplies database round-trips.

---

### R-025: earnings_p2.py — 0.0 Hardcoded for Missing Tone
**File:** `src/api/routers/earnings_p2.py`, lines 270, 276
**Severity:** Medium

```python
overall_tone=float(r.overall_tone) if r.overall_tone is not None else 0.0
```

`0.0` is a valid sentiment score meaning exactly neutral. When a transcript has no tone data, it is indistinguishable from a transcript with a computed neutral tone. Should be `None` with an explicit `has_tone_data` boolean field.

---

### R-026: company_intel_p2.py — AI Summaries Joined With " | "
**File:** `src/api/routers/company_intel_p2.py`, lines 107–110
**Severity:** Low

```python
ai_summary = " | ".join(ai_summaries) if ai_summaries else None
```

Multiple AI summary strings are concatenated with a pipe delimiter. No consuming frontend parser expects this format. If a summary contains the text " | " as part of a sentence, it would incorrectly be treated as a section separator.

---

### R-027: research_thesis.py — conviction_change Never Calculated
**File:** `src/api/routers/research_thesis.py`, line 263
**Severity:** Low

`GET /v4/research/thesis/{id}/versions` returns `conviction_change` per version. The field is read from `version.conviction_change`, but this field is never populated during `update_thesis()`. All version diffs show `conviction_change=None`.

---

### R-028: economic_calendar.py — Hardcoded Event Type Lists Not Validated Against DB
**File:** `src/api/routers/economic_calendar.py`, lines 73, 97, 122, 147
**Severity:** Low

Each calendar endpoint filters by a hardcoded list of event type strings (e.g., `["FOMC", "FOMC_MEETING", "CENTRAL_BANK"]`). If the actual values stored in `CalendarEvent.event_type` use different naming conventions, these endpoints return empty results without error.

---

### R-029: governance_intelligence.py — red_flags Iteration Assumes List of Dicts
**File:** `src/api/routers/governance_intelligence.py`, lines 137, 168
**Severity:** Medium

```python
for rf in row.red_flags:
    rf.get("severity", "LOW")
```

If `row.red_flags` is a non-list JSON value (e.g., a dict or string from a schema drift), iteration raises `TypeError`. If individual items are not dicts, `.get()` raises `AttributeError`.

---

### R-030: sentiment_p2.py — bulk_news Accepts Untyped dict Body
**File:** `src/api/routers/sentiment_p2.py`, lines 135–158
**Severity:** Low

`POST /news/bulk` accepts `body: dict` with no Pydantic model. Missing required fields like `entity_ids` are silently defaulted to empty lists. Malformed requests return 200 OK with empty data instead of 422 Unprocessable Entity.

---

---

## Part 3: Data Model Layer — 18 Issues

### M-001: SearchDocument Uses dict/JSON for Embedding Vector
**File:** `src/models/semantic_search.py` (or equivalent), line ~28
**Severity:** Critical

`embedding_vector` is typed as `dict | None` and stored in a JSONB column. Vector similarity search requires a true vector type (`VECTOR(1536)` via the `pgvector` extension). JSONB has no cosine similarity operator. Even if the embedding generation layer were built tomorrow, the storage type must be changed via migration before semantic search can work.

---

### M-002: String Columns Too Narrow for Real Data
**Files:** Multiple model files
**Severity:** High

| Column | Current Size | Potential Content Length | Risk |
|--------|-------------|--------------------------|------|
| `SentimentScore.source_type` | VARCHAR(20) | "earnings_call_qa_analyst_question" (39 chars) | Truncation |
| `SearchDocument.source_type` | VARCHAR(25) | "earnings_call_prepared_remarks_ceo" (34 chars) | Truncation |
| `DetectedAnomaly.anomaly_type` | VARCHAR(25) | "earnings_estimate_revision_surprise_negative" (44 chars) | Truncation |
| `FilingSection.section_key` | VARCHAR(20) | "Item 1B Unresolved Staff Comments" (33 chars) | Truncation |

Data truncation at the database layer produces silent corruption — the insert succeeds but the stored value is wrong.

---

### M-003: ThesisVersion Missing CASCADE DELETE
**File:** `src/models/investment_thesis.py` (or equivalent), line ~48
**Severity:** High

`ThesisVersion` has a foreign key to `InvestmentThesis.id` with no `ON DELETE CASCADE`. Deleting a thesis record leaves orphaned version records that reference a non-existent parent, causing referential integrity violations and polluting version history queries.

---

### M-004: MorningBriefing / BriefingPreference user_id Has No FK Constraint
**File:** `src/models/morning_briefing.py` (or equivalent), lines ~18, 36
**Severity:** Medium

`user_id: Mapped[str]` on both models has no foreign key constraint to a users table. Briefings and preferences remain in the database permanently after a user is deleted, accumulating as orphaned rows.

---

### M-005: InvestmentThesis analyst_id Has No FK Constraint
**File:** `src/models/investment_thesis.py`, line ~35
**Severity:** Medium

Same issue as M-004. `analyst_id` is a free-form string with no referential integrity.

---

### M-006: ConsolidatedAlert Missing updated_at
**File:** `src/models/intelligent_alerts.py`, line ~15
**Severity:** Medium

When an alert is acknowledged, there is no `updated_at` timestamp to record when the state change occurred. Audit queries for "recently acknowledged alerts" cannot be answered.

---

### M-007: SearchDocument / SearchQuery Missing updated_at
**File:** `src/models/semantic_search.py`, lines ~15, 38
**Severity:** Medium

When a document is re-indexed or its embedding is recomputed, there is no update timestamp. Queries like "find documents indexed in the last 24 hours" operate on `created_at` which never changes.

---

### M-008: ThesisVersion Missing updated_at
**File:** `src/models/investment_thesis.py`, line ~46
**Severity:** Low

Version records represent point-in-time snapshots and arguably should be immutable. However if version metadata is ever corrected, there is no record of when.

---

### M-009: SentimentAggregate Missing Descending Date Index
**File:** `src/models/sentiment.py`, line ~50
**Severity:** Medium

The existing unique constraint on `(entity_id, as_of_date, timeframe)` may not be used efficiently for `ORDER BY as_of_date DESC LIMIT 1` queries (latest sentiment per entity). A partial index `WHERE timeframe = '30D' ORDER BY as_of_date DESC` would serve the most common access pattern.

---

### M-010: SearchDocument Missing (source_type, source_id) Index
**File:** `src/models/semantic_search.py`, line ~23
**Severity:** Medium

The most common chunk retrieval query ("get all chunks for document X") filters on `source_type` and `source_id`. Without an index on this pair, every chunk retrieval is a full table scan.

---

### M-011: Missing Cascade Deletes on Intelligence Entity FK References
**Files:** `src/models/sentiment.py`, `src/models/filing_intelligence.py`, `src/models/news_article.py`
**Severity:** Medium

`SentimentScore`, `SentimentAggregate`, `FilingSection`, `FilingDiff`, and `ArticleEntityLink` all reference `entity_id` via foreign keys with no `ON DELETE CASCADE`. Deleting an entity leaves all associated intelligence records as orphaned rows.

---

### M-012: ConsolidatedAlert Missing Unique Constraint
**File:** `src/models/intelligent_alerts.py`, line ~15
**Severity:** Medium

Without a unique constraint on `(entity_id, alert_type, created_at::date)` or similar, burst events can insert identical alerts. The alert inbox shows duplicates with no deduplication.

---

### M-013: NewsArticle Content Not Required Despite Being Core Data
**File:** `src/models/news_article.py`, lines ~29–30
**Severity:** Low

Both `summary` and `body_text` are nullable. An ingested news article can have no text content. These should be non-nullable (or at minimum one of them required) to ensure there is always something to analyze.

---

### M-014: JSONB Columns Across All Intelligence Models Have No Schema Documentation
**Files:** Multiple
**Severity:** Low

At least 20 JSON/JSONB columns across intelligence models (`alert_categories`, `source_alert_ids`, `secondary_alerts`, `key_drivers`, `primary_risks`, `valuation_scenarios`, `fallen_angels_this_period`, `rising_stars_this_period`, `fi_profile`, etc.) have no docstring, comment, or companion TypedDict class documenting their expected structure. Schema drift in these columns produces silent failures in any router that accesses nested keys.

---

### M-015: SentimentScore No Unique Constraint on (entity_id, source_identifier)
**Identified in v1 as BUG-038 — confirmed still present**
**Severity:** Medium

Repeated sentiment ingest of the same article creates duplicate rows. Aggregate queries double-count sentiment scores.

---

---

## Part 4: app.py Registration Layer — 8 Issues

### A-001: research_themes_router Registered at /v3 (Should Be /v4)
**File:** `src/api/app.py`, line 653
**Severity:** Critical

```python
app.include_router(research_themes_router, prefix="/v3")
```

All other research (Pillar 4) routers use prefix `/v4`. The themes router's own paths start with `/research/themes/`, so it resolves to `/v3/research/themes/*`. The frontend `endpoints.ts` constants point to `/v4/research/themes/*`. Every themes and scenarios endpoint returns 404 in production.

---

### A-002: No CORS Middleware
**File:** `src/api/app.py`
**Severity:** Critical

No `CORSMiddleware` is added. All cross-origin requests from the React frontend (different port or domain) are blocked by browsers before they reach the API. The application cannot function in any browser-based deployment without this.

---

### A-003: All Pillar 3 Router Imports in Silent try/except
**File:** `src/api/app.py`, multiple lines
**Severity:** High

Every Pillar 3 router import is wrapped in:
```python
try:
    from .routers import xyz_router
    app.include_router(xyz_router, ...)
except Exception:
    pass
```

A broken router (import error, syntax error, broken engine import like E-001) silently disappears from the application without any log warning or startup failure. Broken routers are undetectable without manually testing every endpoint.

---

### A-004: Health Check Always Returns 200 Without Testing Database
**File:** `src/api/app.py`, line ~730
**Severity:** Medium

```python
@app.get("/health")
async def health_check():
    return {"status": "ok"}
```

No database connectivity check. Load balancers and container orchestrators that use this endpoint to determine readiness will route traffic to instances with broken database connections.

---

### A-005: No Startup Event to Validate Dependencies
**File:** `src/api/app.py`
**Severity:** Medium

There is no `@app.on_event("startup")` handler. The application starts successfully even if the database is unreachable, environment variables are missing, or required models cannot be imported. Startup failures are only discovered on the first incoming request.

---

### A-006: Global Exception Handler Treats All Exceptions as 500
**File:** `src/api/app.py`, lines ~737–760
**Severity:** Low

The catch-all handler returns HTTP 500 for all unhandled exceptions, including cases that should be 422 (validation) or 409 (conflict). This makes client error debugging difficult.

---

### A-007: Six Analytics Routers May Be Missing Versioned Prefix
**File:** `src/api/app.py`, lines 149–173
**Severity:** Medium

`analytics_router`, `screening_router`, `flows_router`, `risk_router`, `quant_router`, and `scenario_router` appear to be registered without a `/v1` or `/v2` prefix. If the frontend expects these at `/v2/analytics/...` but they're mounted at `/analytics/...`, all analytics endpoints return 404. This requires confirmation against the actual router path definitions.

---

### A-008: Router Registration Order Relies on Convention, Not Enforcement
**File:** `src/api/app.py`, lines 72, 500, 657, 666, 675
**Severity:** Low

Five comments document ordering requirements ("Security Finder must be registered BEFORE Securities", etc.). There is no automated enforcement. A future developer reordering the file could silently break path resolution.

---

---

## Part 5: Frontend Layer — 14 Issues

### F-001: All Pillar 3 Pages Use Apple Inc. Data as Default Fallback
**Files:** FilingsView.tsx, GovernanceDashboard.tsx, CompanyIntelligence.tsx, PrimerView.tsx, ThesisBuilder.tsx, AnalystQA.tsx, AnomalyView.tsx, SemanticSearch.tsx, ThemesDashboard.tsx
**Severity:** Critical

Every Pillar 3 frontend page has a hardcoded mock data constant that is shown via the `(apiData as any)?.field ?? mockData` fallback pattern. These constants contain:

- **Real Apple board member names** (Tim Cook, Arthur Levinson, Al Gore, Andrea Jung)
- **Real Apple executive compensation** (Tim Cook $3M base, Luca Maestri $1M base)
- **Real Apple proxy voting results** (Right to Repair Report: 33.8%, Civil Rights Audit: 28.4%)
- **Real Apple financial figures** (Services revenue $96B, buybacks $90.1B, iPhone 52% of revenue)
- **Company-specific SWOT/Porter analyses** ("iPhone concentration risk")
- **Apple-specific risk factors** (Vision Pro execution, App Store antitrust, TSMC supply chain)
- Specific tickers across 9 pages: AAPL, NVDA, AVGO, AMD, MSFT, INTC, QCOM, TLT, XLF, JPM, TSLA, META, PFE, VIX, MU, TXN

Any user visiting any company page sees Apple or NVIDIA data as the "live" data whenever the API returns undefined. This is not a loading state — the mock data is rendered immediately, indistinguishable from real data.

---

### F-002: ResearchHub.tsx Calls a Non-Existent Endpoint
**File:** `frontend/src/pages/research/ResearchHub.tsx`, line 131
**Severity:** High

```typescript
queryFn: () => api.get('/v4/research/modules'),
```

`/v4/research/modules` is not defined in `endpoints.ts` and does not exist in any backend router. This request returns 404 on every page load.

---

### F-003: AnalystQA.tsx — Mock Chat History Displayed on Load With Fabricated Conversations
**File:** `frontend/src/pages/research/AnalystQA.tsx`, lines 19–44
**Severity:** High

The initial page render shows a hardcoded chat history with multi-turn Q&A conversations about AAPL, NVDA, MSFT, GOOGL, META, AMD, QCOM, JPM, and PFE. Specific fabricated figures like "$105.3B returned to shareholders" and "FY2025 EPS consensus" are displayed as if they were real AI responses to real historical questions. A user who has never asked any questions sees a rich conversation history populated with false data.

---

### F-004: AnomalyView.tsx — useCriticalAnomalies Result Never Rendered
**File:** `frontend/src/pages/research/AnomalyView.tsx`, lines 41–42
**Severity:** Medium

`useCriticalAnomalies()` is called and stored in `apiCritical` but this variable is never referenced anywhere in the component JSX or logic. The API call is made on every page load for no purpose.

---

### F-005: PrimerView.tsx — useRecentPrimers Result Never Rendered
**File:** `frontend/src/pages/research/PrimerView.tsx`, line 36
**Severity:** Medium

`useRecentPrimers()` is called and stored in `apiRecent` but never rendered. The "Recent Primers" sidebar that would use this data shows hardcoded entries instead.

---

### F-006: ThesisBuilder.tsx — Default entityId Falls Back to 'NVDA'
**File:** `frontend/src/pages/research/ThesisBuilder.tsx`, line 42
**Severity:** High

```typescript
const resolvedId = entityId ?? 'NVDA';
```

Any navigation to the thesis builder without an entity ID parameter causes all API calls to use NVDA. The hardcoded thesis object on lines 14–36 then provides a full NVIDIA thesis with specific price targets ($1050), specific dates (2026-05-28, 2026-03-17), and specific catalyst events as the fallback.

---

### F-007: PrimerView.tsx — Default entityId Falls Back to 'AAPL'
**File:** `frontend/src/pages/research/PrimerView.tsx`, line 34
**Severity:** High

```typescript
const resolvedId = entityId ?? 'AAPL';
```

Same pattern. Missing entity ID routes all requests to Apple's primer data.

---

### F-008: SemanticSearch.tsx — Hardcoded Semiconductor Stocks Shown on Load
**File:** `frontend/src/pages/research/SemanticSearch.tsx`, lines 10–21
**Severity:** High

The initial state shows 5 hardcoded search results for INTC, QCOM, AMD, TXN, and MU with specific financial metrics and "42 results" total. Before any search is performed, users see these specific companies as if they represent the search results for the page's pre-loaded query.

---

### F-009: GovernanceDashboard.tsx — Mock Data Always Shown, No Loading Indication
**File:** `frontend/src/pages/company/GovernanceDashboard.tsx`, lines 54–57
**Severity:** High

```typescript
const board = (apiBoard as any[]) ?? MOCK_BOARD;
const compensation = (apiComp as any[]) ?? MOCK_COMPENSATION;
const proposals = (apiProposals as any[]) ?? MOCK_PROPOSALS;
```

React Query returns `undefined` before data arrives. The `??` operator immediately falls through to mock data. There is no loading skeleton or spinner — the Apple board member names and Tim Cook's salary appear instantly and users have no way to know the real data hasn't loaded yet.

---

### F-010: CompanyIntelligence.tsx — 12 Instances of Apple-Specific Hardcoded Fallbacks
**File:** `frontend/src/pages/company/CompanyIntelligence.tsx`, lines 59–125
**Severity:** High

Hardcoded Apple-specific data used as fallbacks:
- iPhone revenue mix (52.1%), Services mix (22.8%), Mac (8.5%), iPad (6.3%), Wearables (7.1%)
- FY2025/2024/2023 buyback values ($90.1B, $77.6B, $77.5B)
- Management scores (Capital Allocation 9.1/10, Execution Consistency 8.7/10)
- Net Debt/EBITDA: 0.4x, Interest Coverage: 29.3x, Current Ratio: 0.99
- SWOT analysis with Apple-specific threats ("App Store regulatory pressure")
- Porter's Five Forces scores for Apple's industry context

All shown via `??` fallback for any entity.

---

### F-011: ThemesDashboard.tsx — No Loading/Error States, All Mock Data
**File:** `frontend/src/pages/research/ThemesDashboard.tsx`, lines 36–40
**Severity:** High

`useResearchThemes()` is called but `isLoading`, `isError`, and `error` are never extracted. Additionally, due to A-001 (wrong prefix), the API returns 404. The component falls through to hardcoded mock themes for NVDA, AVGO, AMD, MSFT, QCOM, INTC, TLT, XLF, XLRE, XLY, WMT, TGT, ENPH, FSLR, NEE — displayed as "live" research themes.

---

### F-012: All Pillar 3 Pages — Missing isLoading/isError From Hook Destructuring
**Files:** FilingsView.tsx, GovernanceDashboard.tsx, CompanyIntelligence.tsx, AnomalyView.tsx, SemanticSearch.tsx, PrimerView.tsx, ThemesDashboard.tsx, ThesisBuilder.tsx, AnalystQA.tsx
**Severity:** Medium

No Pillar 3 page destructures `isLoading` or `isError` from any hook call. The pattern is uniformly:
```typescript
const { data: apiXxx } = useHook(id) as { data: any };
```

React Query's error and loading states are discarded. API failures are invisible to the user; they see mock data with no error indicator.

---

### F-013: All Pillar 3 Pages — Pervasive as any Type Assertions Bypass TypeScript
**Files:** All Pillar 3 frontend pages
**Severity:** Low

Every API response is immediately cast with `as { data: any }` and then field-accessed with `(apiData as any)?.field`. This defeats TypeScript's type checking entirely. API contract violations — wrong field names, wrong types, missing fields — are undetectable at compile time.

---

### F-014: Empty catch {} Blocks in 5 Research Pages
**Files:** ThesisBuilder.tsx:65, AnomalyView.tsx:52, PrimerView.tsx:46/50, AnalystQA.tsx:71, SemanticSearch.tsx:38
**Severity:** Medium

Empty or near-empty `catch {}` blocks silently swallow all API errors. Failures in thesis generation, anomaly acknowledgement, primer refresh, primer download, Q&A submission, and search are invisible. No logging, no user feedback, no state reset.

---

---

## Part 6: Issues Carried Over From v1 (Confirmed Still Present)

The following 7 critical issues from `PILLAR_3_AUDIT_REPORT.md` are confirmed present and unchanged:

| ID (v1) | Issue | Confirmed |
|---------|-------|-----------|
| BUG-001 | LLM client generate() returns None unconditionally | ✅ |
| BUG-002 | No embedding generation or vector DB connected | ✅ |
| BUG-003 | Q&A returns hardcoded placeholder string | ✅ |
| BUG-004 | Briefing generate writes empty skeleton record to DB | ✅ |
| BUG-006 | Anomaly scan returns INITIATED, no actual scan | ✅ |
| BUG-007 | Primer refresh creates PENDING log, no job triggered | ✅ |
| BUG-009 | Company intel endpoints write empty records to DB | ✅ |

---

## Part 7: Complete Issue Index

| ID | Layer | File | Line(s) | Severity | Summary |
|----|-------|------|---------|----------|---------|
| E-001 | Engine | news_propagation.py | 195 | Critical | Broken import crashes module load |
| E-002 | Engine | competitive_landscape.py | 326–327 | Critical | Parameter name mismatch → NameError |
| E-003 | Engine | management_quality_engine.py | 189–194 | Critical | CCC score direction may be inverted |
| E-004 | Engine | management_quality_engine.py | 95 | Critical | Division by zero on zero guidance actual |
| E-005 | Engine | management_quality_engine.py | 323, 333, 336 | High | Weights sum to 1.10, not 1.00 |
| E-006 | Engine | industry_cycle.py | 230–235 | High | HHI wrong for partial market share data |
| E-007 | Engine | industry_economics.py | 82, 158–159 | High | Level used as trend proxy (mathematically wrong) |
| E-008 | Engine | capital_allocation_engine.py | 168 | High | Array index without bounds check |
| E-009 | Engine | global_macro.py | 120–147 | High | YTD hike total ≠ current stance |
| E-010 | Engine | country_risk.py | 261 | High | 0 sanctions → score of 20 (not 0) |
| E-011 | Engine | country_risk.py | 414, 420, 426 | High | KeyError on missing country_code/pct keys |
| E-012 | Engine | eight_k_engine.py | 307 | Medium | Duplicate "appointed" in action_keywords[3] |
| E-013 | Engine | earnings_surprise_intelligence.py | 328 | High | Crashes if surprise_pct is None |
| E-014 | Engine | earnings_surprise_engine.py | 87–88 | Medium | Zero consensus → 100% surprise |
| E-015 | Engine | earnings_surprise_engine.py | 93–110 | Medium | Majority vote ignores metric materiality |
| E-016 | Engine | competitive_landscape.py | 320 | Medium | share_trend/margin_trend never set by caller |
| E-017 | Engine | business_model_engine.py | 188–195 | Medium | Cyclicality hardcoded 50.0 for <3 data points |
| E-018 | Engine | business_model_engine.py | 271–322 | Medium | Moat detection requires 2+ keyword hits |
| E-019 | Engine | global_macro.py | 88 | Medium | Ambiguous statement → arbitrary stance |
| E-020 | Engine | industry_cycle.py | 45–46 | Medium | Revenue acceleration not true 2nd derivative |
| E-021 | Engine | moat_assessment.py | 547–551 | Low | Evidence empty for borderline scores (all <50) |
| E-022 | Engine | global_macro.py | 234 | Low | 0.0 returned for missing data ≠ zero inflation |
| E-023 | Engine | macro_thematic/scenario | — | High | Fully-implemented engines not wired to any router |
| E-024 | Engine | fi_intelligence.py | 342 | Medium | entity_id hardcoded as empty string |
| E-025 | Engine | political_intelligence.py | 320–334 | Medium | Sort by date key without None check → KeyError |
| E-026 | Engine | cross_asset_narrative.py | 80–98 | Low | Fallen angel detection too restrictive |
| E-027 | Engine | transcript_engine.py | 285 | Low | Sentence splitter breaks on abbreviations |
| E-028 | Engine | transcript_engine.py | 502 | Low | "AI" (2 chars) filtered out as stopword |
| E-029 | Engine | alert_expansion.py | 89 | Medium | Fallen angel only checks S&P BBB-, not Moody's Baa3 |
| E-030 | Engine | alert_expansion.py | 329 | Medium | Cluster counts transactions, not unique insiders |
| E-031 | Engine | alert_expansion.py | 323 | Low | Short interest spike not scale-adjusted |
| E-032 | Engine | alert_engine.py | 128 | Medium | Only first matching rule fires per event |
| E-033 | Engine | alert_engine.py | 285–290 | Medium | Rate limiting silently drops CRITICAL alerts |
| E-034 | Engine | insider_signals.py | 96, 113, 119, 188, 195 | Medium | ValueError on malformed ISO dates (no try/except) |
| E-035 | Engine | news_entity_linker.py | 137 | Low | Fuzzy match threshold not configurable |
| E-036 | Engine | earnings_surprise_intelligence.py | 241 | Low | EPS and revenue surprise weighted equally |
| R-001 | Router | economic_calendar.py | 49 | Critical | .nulls_last() → AttributeError |
| R-002 | Router | news.py | 109 | Critical | desc("string") → SQL error |
| R-003 | Router | fi_intelligence.py | 53, 89, 125 | Critical | .in_(["X", None]) wrong SQL syntax |
| R-004 | Router | global_intelligence.py | 571–585 | Critical | Incomplete function body |
| R-005 | Router | governance_intelligence.py | all | Critical | governance_scoring.py never called — dead code |
| R-006 | Engine | governance_scoring.py | 221 | High | has_majority_voting defaults to True (false negatives) |
| R-007 | Router | filing_intelligence.py | 214, 251 | High | None dereference after scalar_one_or_none() |
| R-008 | Router | sentiment_p2.py | 77 | High | Watchlist digest is confirmed stub |
| R-009 | Router | sentiment_p2.py | 54–63 | High | 7D and 90D sentiment always None |
| R-010 | Router | sentiment_p2.py | 300–305 | Medium | peer_rank_pct mapped to peer_median field |
| R-011 | Router | research_notes.py | 50 | Critical | DEFAULT_USER hardcoded, breaks multi-tenancy |
| R-012 | Router | 16 research routers | various | High | flush() without commit() — data may not persist |
| R-013 | Router | company_primer.py | 70–81 | High | Generates primer from empty dicts; LLM never used |
| R-014 | Router | fi_intelligence.py | 109 | High | Auction endpoint has no auction filter |
| R-015 | Router | fi_intelligence.py | 207 | Medium | Rating narrative is a hardcoded f-string template |
| R-016 | Router | alerts_expansion.py | 130 | High | credit_regime value in severity field (type mismatch) |
| R-017 | Router | alerts_expansion.py | 152, 162 | High | Random UUID for missing entity_id |
| R-018 | Router | alerts_expansion.py | 165 | Medium | Flow direction from threshold, not actual flow |
| R-019 | Router | industry.py | ~95 | Critical | .nulls_last() → AttributeError |
| R-020 | Router | industry.py | 160–168 | High | get_industry_companies returns no companies |
| R-021 | Router | industry.py | 76–93 | Medium | rank_industries loads all rows then deduplicates in Python |
| R-022 | Router | global_intelligence.py | 256–276 | High | All events loaded into memory for country filter |
| R-023 | Router | global_intelligence.py | 701–704 | Medium | Supply/demand signal is fake price-based arithmetic |
| R-024 | Router | news.py | 126–171 | Medium | N+1 query pattern in news stats |
| R-025 | Router | earnings_p2.py | 270, 276 | Medium | 0.0 for missing tone indistinguishable from neutral |
| R-026 | Router | company_intel_p2.py | 107–110 | Low | AI summaries joined with " | " |
| R-027 | Router | research_thesis.py | 263 | Low | conviction_change never calculated |
| R-028 | Router | economic_calendar.py | 73, 97, 122, 147 | Low | Hardcoded event type lists not validated against DB |
| R-029 | Router | governance_intelligence.py | 137, 168 | Medium | red_flags iteration assumes list-of-dicts |
| R-030 | Router | sentiment_p2.py | 135–158 | Low | bulk_news accepts untyped dict body |
| M-001 | Model | semantic_search.py | ~28 | Critical | embedding_vector is dict/JSONB, not VECTOR type |
| M-002 | Model | Multiple | — | High | VARCHAR columns too narrow for real content |
| M-003 | Model | investment_thesis.py | ~48 | High | ThesisVersion missing CASCADE DELETE |
| M-004 | Model | morning_briefing.py | ~18, 36 | Medium | user_id has no FK constraint |
| M-005 | Model | investment_thesis.py | ~35 | Medium | analyst_id has no FK constraint |
| M-006 | Model | intelligent_alerts.py | ~15 | Medium | ConsolidatedAlert missing updated_at |
| M-007 | Model | semantic_search.py | ~15, 38 | Medium | SearchDocument/Query missing updated_at |
| M-008 | Model | investment_thesis.py | ~46 | Low | ThesisVersion missing updated_at |
| M-009 | Model | sentiment.py | ~50 | Medium | SentimentAggregate missing DESC date index |
| M-010 | Model | semantic_search.py | ~23 | Medium | Missing (source_type, source_id) index |
| M-011 | Model | Multiple intelligence | — | Medium | Missing CASCADE DELETE on entity_id FK refs |
| M-012 | Model | intelligent_alerts.py | ~15 | Medium | ConsolidatedAlert missing unique constraint |
| M-013 | Model | news_article.py | ~29–30 | Low | Article body/summary nullable despite being core |
| M-014 | Model | Multiple | — | Low | 20+ JSONB columns undocumented |
| M-015 | Model | sentiment.py | — | Medium | SentimentScore no unique on (entity_id, source_id) |
| A-001 | App | app.py | 653 | Critical | research_themes_router at /v3 (should be /v4) |
| A-002 | App | app.py | — | Critical | No CORS middleware |
| A-003 | App | app.py | multiple | High | All P3 router imports in silent try/except |
| A-004 | App | app.py | ~730 | Medium | Health check doesn't test DB |
| A-005 | App | app.py | — | Medium | No startup event |
| A-006 | App | app.py | ~737 | Low | All exceptions treated as 500 |
| A-007 | App | app.py | 149–173 | Medium | Analytics routers may be missing versioned prefix |
| A-008 | App | app.py | multiple | Low | Router registration order relies on convention |
| F-001 | Frontend | 9 pages | various | Critical | Apple/NVIDIA data hardcoded as default fallback |
| F-002 | Frontend | ResearchHub.tsx | 131 | High | Calls /v4/research/modules (doesn't exist) |
| F-003 | Frontend | AnalystQA.tsx | 19–44 | High | Fabricated chat history displayed on load |
| F-004 | Frontend | AnomalyView.tsx | 41–42 | Medium | useCriticalAnomalies result never rendered |
| F-005 | Frontend | PrimerView.tsx | 36 | Medium | useRecentPrimers result never rendered |
| F-006 | Frontend | ThesisBuilder.tsx | 42 | High | Default entityId → 'NVDA' |
| F-007 | Frontend | PrimerView.tsx | 34 | High | Default entityId → 'AAPL' |
| F-008 | Frontend | SemanticSearch.tsx | 10–21 | High | 5 hardcoded semiconductor stocks shown on load |
| F-009 | Frontend | GovernanceDashboard.tsx | 54–57 | High | Mock data shown immediately, no loading state |
| F-010 | Frontend | CompanyIntelligence.tsx | 59–125 | High | 12 Apple-specific fallback constants |
| F-011 | Frontend | ThemesDashboard.tsx | 36–40 | High | No loading/error states, all mock data |
| F-012 | Frontend | All P3 pages | — | Medium | isLoading/isError never extracted from hooks |
| F-013 | Frontend | All P3 pages | — | Low | Pervasive as any bypasses TypeScript |
| F-014 | Frontend | 5 research pages | various | Medium | Empty catch {} blocks hide all API errors |

**Total: 147 issues**

---

## Part 8: Remediation Plan

### Phase 1 — Fix Runtime Crashes (1 day)

These must be fixed before any testing is possible:

1. **E-001**: Create `src/engines/economic_calendar_engine.py` with `RELEASE_TYPES` dict, or inline the fallback directly and remove the import
2. **E-002**: Rename `industry_trends` to `industry_stats` in `competitive_landscape.py:327`
3. **R-001**: Replace `.nulls_last()` with `nullslast()` in `economic_calendar.py:49`
4. **R-002**: Replace `desc("mention_count")` with proper column reference in `news.py:109`
5. **R-003**: Replace `.in_(["YIELD_CURVE", None])` with `or_()` condition in `fi_intelligence.py:53,89,125`
6. **R-004**: Complete the truncated function body in `global_intelligence.py:571–585`
7. **R-019**: Fix `.nulls_last()` in `industry.py`
8. **A-001**: Change `prefix="/v3"` to `prefix="/v4"` for `research_themes_router`
9. **A-002**: Add `CORSMiddleware` to `app.py`

### Phase 2 — Critical Data and Logic Fixes (2–3 days)

1. **E-003/E-004**: Add division-by-zero guard in `management_quality_engine.py`; audit CCC formula direction
2. **E-011**: Wrap `seg["country_code"]` and `seg["pct"]` in `.get()` with defaults in `country_risk.py`
3. **E-013**: Add None check before `abs(eps_analysis.surprise_pct)` in `earnings_surprise_intelligence.py`
4. **R-005**: Wire `governance_scoring.py` into `governance_intelligence.py` router — call `compute_governance_score()` when no pre-computed row exists
5. **R-006**: Change `has_majority_voting` default from `True` to `False`
6. **R-007**: Add None check after `scalar_one_or_none()` calls in `filing_intelligence.py`
7. **R-011**: Replace `DEFAULT_USER` with auth context user ID in `research_notes.py`
8. **R-012**: Replace all 16 `session.flush()` with `session.commit()` across research routers
9. **M-001**: Add `pgvector` extension, migrate `embedding_vector` to `VECTOR(1536)` type
10. **M-002**: Expand all narrow VARCHAR columns to accommodate realistic content lengths

### Phase 3 — LLM Integration (3–5 days)

1. Implement `LLMClient.generate()` with real API key validation
2. Wire `analyst_qa_engine.py` → LLM → `research_qa.py`
3. Wire `morning_briefing_engine.py` → LLM → `research_briefings.py`
4. Wire `company_primer_engine.py` → LLM + real data assembly → `company_primer.py` (fix lines 70–81)
5. Wire `investment_thesis_engine.py` → LLM → `research_thesis.py`
6. Wire `macro_scenario_engine.py` narrative → LLM
7. Add async job queue for all long-running operations (briefing, anomaly scan, primer refresh)

### Phase 4 — Semantic Search Infrastructure (5–7 days)

1. Add embedding generation step (OpenAI `text-embedding-3-small` or local model) to document ingest
2. Wire `semantic_search_engine.py` cosine similarity to use `VECTOR` column
3. Fix `research_search.py:40–45` to use semantic ranking
4. Replace hardcoded suggested queries with query history analysis

### Phase 5 — Unwire Mock Data From Frontend (3–5 days)

1. Remove all hardcoded company-specific constants from every Pillar 3 page
2. Replace `(apiData as any)?.field ?? mockData` with proper loading skeleton + error state
3. Extract `isLoading`, `isError` from every hook call
4. Replace empty `catch {}` blocks with error state + toast notifications
5. Fix `ResearchHub.tsx:131` to use a real endpoint
6. Remove `entityId ?? 'AAPL'` and `entityId ?? 'NVDA'` defaults — show empty state instead

### Phase 6 — Engine Wiring Batch Script (2–3 days)

1. Create `scripts/run_intelligence_batch.py` to invoke:
   - `governance_scoring.py` for all entities
   - `anomaly_detection_engine.py` for all securities
   - `finbert_sentiment.py` ingest pipeline for all unprocessed documents
   - `morning_briefing_engine.py` daily
   - `macro_thematic_engine.py` and `macro_scenario_engine.py`
2. Add incremental mode (only entities updated since last run)

### Phase 7 — Mathematical and Logic Fixes (2–3 days)

1. **E-006**: Fix HHI to work with partial market share data
2. **E-007**: Fix ROIC trend to use time-series delta, not level
3. **E-009**: Fix policy stance to use `last_action` not `ytd_bps`
4. **E-010**: Fix sanctions base score to return 0 for 0 programs
5. **E-020**: Replace half-mean difference with proper acceleration formula
6. **R-020**: Fix `get_industry_companies` to return actual company list
7. **R-016**: Fix `alerts_expansion.py:130` type mismatch (regime → severity mapping)
8. **R-017**: Return null entity_id instead of random UUID
9. **R-022**: Push country filter to SQL in `global_intelligence.py`

### Phase 8 — Schema and Index Hardening (1–2 days)

1. Add missing CASCADE DELETE on all intelligence FK references
2. Add `updated_at` to `ConsolidatedAlert`, `SearchDocument`, `SearchQuery`, `ThesisVersion`
3. Add unique constraint on `(entity_id, alert_type, date)` in `ConsolidatedAlert`
4. Add FK constraints on `user_id` and `analyst_id`
5. Add descending date index on `SentimentAggregate`
6. Add `(source_type, source_id)` index on `SearchDocument`
7. Document all JSONB column schemas as TypedDicts

---

## Appendix: Engines With No Router Integration

The following fully-implemented engines are not reachable through any API endpoint:

| Engine | Lines of Code | Capability |
|--------|-------------|------------|
| `macro_thematic_engine.py` | ~420 | Company exposure to 7 macro themes |
| `macro_scenario_engine.py` | ~370 | EPS/margin impact from macro scenarios |
| `governance_scoring.py` | ~548 | 6 governance scoring functions |
| `news_dedup.py` | ~120 | Three-tier article deduplication |
| `transcript_engine.py` | ~526 | Full earnings call analysis |
| `earnings_surprise_engine.py` | ~416 | Historical surprise patterns |
| `earnings_surprise_intelligence.py` | ~388 | Post-earnings event analysis |
| `insider_signals.py` | ~319 | Insider trading signal engine |
| `eight_k_engine.py` | ~563 | 8-K event parsing and classification |
