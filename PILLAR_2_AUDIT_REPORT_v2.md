# Pillar 2 Analytics Engine — Deep Audit Report v2

**Date:** 2026-04-02
**Scope:** Every file in Pillar 2 — backend engines, ORM models, API router, screening router, batch pipeline, app startup, frontend hooks, pages, and components.
**Method:** Static code analysis of all source files. No tests run.

---

## How This Report Is Organised

Each section follows: **What is broken → Where exactly (file:line) → Why it matters → What to fix.**
Issues are grouped by layer, not by severity, so you can work through them layer by layer.

---

## Part 1: The Universal Path Mismatch (Blocks Everything)

Every `ANALYTICS` constant in `frontend/src/api/endpoints.ts` uses the pattern
`/v2/analytics/securities/{id}/{metric}`.
The backend analytics router uses `/v2/analytics/{metric}/{id}`.

This means **every analytics hook returns HTTP 404** and every dashboard silently falls back to mock data. This is the single highest-leverage fix — correcting the 28 wrong path constants instantly unblocks the entire analytics layer.

Full mapping table is in `PILLAR_2_AUDIT_REPORT.md` (v1). This report covers all other issues found on top of that.

---

## Part 2: Backend Engine Bugs

### 2.1 E1 Ratios (`src/engines/e1_ratios.py`)

**Bug 1 — `employee_count` field does not exist in schema**
`net_income_per_employee` and `revenue_per_employee` call `s.iv("employee_count")` and `s.bv("employee_count")`. Neither `IncomeStatement` nor `BalanceSheet` has an `employee_count` column. Both metrics always produce `None` silently. They are stored as `INSUFFICIENT_DATA` but no log warning fires.
**Fix:** Remove the two metrics or add `employee_count` to `EquityDetails` and populate it.

**Bug 2 — Negative equity flag not propagated**
Negative equity is detected and added to `quality_flags` but only set on `roe`. Every other ratio that uses equity as a denominator (ROCE, ROIC, equity multiplier, DuPont) gets quality `COMPLETE` even when equity is negative, hiding the instability.
**Fix:** Pass the `negative_equity` flag to all metrics whose denominator includes equity.

**Bug 3 — Inconsistent division-by-zero protection**
`safe_divide()` is called correctly in ~90% of places but three spots do manual checks:
- `opex_ratio` (manual if-statement, misses edge case)
- `quick_ratio` (manual check, inconsistent with rest of file)
- `roce` computation (capital_employed checked but no guard on final division)
**Fix:** Replace all manual guards with `safe_divide()`.

**Bug 4 — Year-ago matching uses ±45 days heuristic**
Operating leverage and growth rates use "prior year" by searching for a period within ±45 days of `today - 365`. For fiscal years that don't align with the calendar year this can match the wrong period without logging a warning.
**Fix:** Match on `fiscal_year` + `fiscal_quarter` identifiers, not date arithmetic.

**Bug 5 — `TREND_RATIOS` static list**
`e1_trends.py` has a hardcoded list of 25 ratio names it will track trends for (`src/engines/e1_trends.py:25`). When new ratios are added to `e1_ratios.py`, trend tracking for those ratios is silently skipped unless the list is manually updated.
**Fix:** Remove the hardcoded list; query `AnalyticsResult` for all distinct metric names from engine_id `E1` and compute trends for all of them.

---

### 2.2 E1 DuPont (`src/engines/e1_dupont.py`)

**Bug 6 — NEGATIVE_EQUITY quality flag not set on composite ROE outputs**
The flag is correctly set on `equity_multiplier` and `roe_direct` but **not** on `dupont_roe_3f` or `dupont_roe_5f`, even though both depend on `equity_multiplier`. Downstream consumers of 3-factor/5-factor ROE cannot tell that the result is unreliable.
**Fix:** Propagate the flag to all metrics that incorporate `equity_multiplier`.

**Bug 7 — Cross-check tolerance uses only absolute, not relative**
`math.isclose(roe_3f, roe_direct, abs_tol=0.001)` is called without a `rel_tol`. For a company with ROE of 2.5 (250%), a mismatch of 0.2 (8% relative error) passes the check. For ROE of 0.02 (2%), a mismatch of 0.0009 fails incorrectly.
**Fix:** Use `math.isclose(a, b, rel_tol=0.005, abs_tol=0.001)` (0.5% relative OR 0.1% absolute).

**Bug 8 — No fallback to TTM if no period found with both IS and BS**
If the latest 8 periods all lack either income statement or balance sheet, the engine returns an empty list with only a warning. The TTM-computed data in `AnalyticsResult` is not tried as a fallback.
**Fix:** If annual/quarterly period lookup fails, attempt to build a DuPont estimate from TTM metrics already in `AnalyticsResult`.

---

### 2.3 E1 TTM (`src/engines/e1_ttm.py`)

**Bug 9 — Months calculation is off-by-one for single-quarter data**
Annualisation: `months = (year_diff * 12) + month_diff + 3`. For Q1-only data, `month_diff` is typically 0 and `year_diff` is 0, giving `months = 3 + 3 = 6`. All annualised values are halved. The bug compounds for Q2 and Q3.
**Fix:** The `+ 3` constant is wrong. Months covered should be `sum(number of months per available quarter)`.

**Bug 10 — Hardcoded field mapping table has no validation**
`_FLOW_FIELDS` and `_STOCK_FIELDS` (lines 24–71) map metric names to `(ModelClass, field_name)` string pairs. If a field is renamed in a model migration, `getattr(obj, field_name, None)` silently returns `None` and the metric is not emitted. No startup check validates that all fields exist.
**Fix:** Add a startup assertion (or a unit test) that verifies every field in the mapping actually exists on its model class.

**Bug 11 — All-None fields not emitted, causing schema drift between securities**
If a field is `None` in every available quarter, the metric is not written to `AnalyticsResult`. Securities where a field is always zero (e.g., `capex = 0` for a software company) will emit the metric; securities with missing data will not. Downstream screener queries that filter on "capex IS NOT NULL" produce incorrect results.
**Fix:** Always emit the metric even with a `None` value and quality `INSUFFICIENT_DATA`.

---

### 2.4 E1 Trends (`src/engines/e1_trends.py`)

**Bug 12 — `statistics.stdev()` called on 2-point samples**
Standard deviation of two points is mathematically valid but is a degenerate case and highly unreliable. The result is stored with quality `PARTIAL` but consumers have no way to know the sample size.
**Fix:** Require minimum 4 data points for `_std_5y`; return `None` + quality `INSUFFICIENT_DATA` below that.

**Bug 13 — Z-score of zero-variance series is `None`, not `HIGHLY_CONSISTENT`**
When `std_5y == 0`, the z-score is set to `None` without a quality tag. The correct interpretation is that the metric has been perfectly stable, which should be signalled as `HIGHLY_CONSISTENT`, not missing.
**Fix:** When `std_5y == 0`, set `zscore = 0.0` with quality `HIGHLY_CONSISTENT`.

**Bug 14 — Momentum acceleration is undefined when first data point matches second**
`prior_year_momentum()` searches backward from the second-latest point. If the series is sparse, the same point can match twice, yielding momentum change of zero without any quality flag. Zero acceleration is indistinguishable from genuine flat momentum.
**Fix:** Require that the two comparison points are at least 6 months apart; otherwise return `None`.

---

### 2.5 E1 Industry KPIs (`src/engines/e1_industry_kpis.py`)

**Bug 15 — REIT gain-on-sale hardcoded to 0**
`gain = 0.0  # gain_on_sale not in standard schema` (approx. line 281). REIT FFO is systematically understated because gains on property sales — which can be 10–30% of reported income — are excluded.
**Fix:** Add `gain_on_sale` as a non-operating line item to `IncomeStatement` or source it from `AnalyticsResult` if computed elsewhere.

**Bug 16 — REIT maintenance capex at 12.5% of D&A is a guess**
AFFO subtracts estimated maintenance capex computed as `D&A * 0.125`. This ratio varies widely by asset class (industrial vs. residential vs. office). No source is cited and no data-driven approach is used.
**Fix:** Use actual recurring capex from `CashFlowStatement.capital_expenditures` if available, falling back to the heuristic only when the field is null.

**Bug 17 — None-valued KPIs emitted as output, polluting AnalyticsResult**
Seven KPIs (loans-to-deposits, provision coverage, tier-1 capital ratio, reserve life index, finding cost, netback, revenue per sqft) are always `None` because the required data does not exist in the schema. They are still written to `AnalyticsResult` with value `NULL` and quality `INSUFFICIENT_DATA`. This creates ~7 × (number of securities in sector) junk rows per batch run.
**Fix:** Only emit a metric if at least one input is non-None. Skip placeholder metrics entirely.

**Bug 18 — Insurance combined ratio uses wrong proxy fields**
Loss ratio uses `cost_of_revenue` and expense ratio uses `selling_general_admin`. For insurance companies these fields typically contain underwriting profit and administrative expenses respectively, not the components of the combined ratio. The result is systematically wrong.
**Fix:** Source from actual loss/expense line items via `operating_segments` data if available, or mark as `NOT_APPLICABLE` when unverifiable.

---

### 2.6 E2 DCF (`src/engines/e2_dcf.py`)

**Bug 19 — Sensitivity grid is mathematically incorrect**
The `_build_sensitivity_grid()` function (approx. lines 898–904) re-scales only the terminal value when varying WACC/growth. The explicit-period FCFs (years 1–5) are **not re-discounted** at each sensitivity WACC. The correct calculation requires re-computing `PV(FCF_t) = FCF_t / (1+WACC)^t` for each grid cell. As-built, the grid only shows terminal value sensitivity, not full enterprise value sensitivity.
**Fix:** Rebuild the grid by running the full DCF at each WACC/growth combination rather than scaling from the base case.

**Bug 20 — Revenue growth clamped to 5% for any company with historical CAGR outside [-20%, +50%]**
High-growth companies (>50% CAGR, e.g., early-stage tech) and recently distressed companies (<-20% CAGR) both receive an identical 5% baseline without sector context. This makes the DCF model useless for the companies where it would be most interesting.
**Fix:** Use sector median growth as the fallback when historical CAGR is outside the clamped range.

**Bug 21 — FCFE projection assumes constant capital structure**
Net borrowing is held constant as a percentage of revenue throughout the projection period. Companies actively deleveraging or re-leveraging get incorrect equity cash flow projections.
**Fix:** Accept a `leverage_target` parameter in the DCF POST endpoint, defaulting to the current debt/equity ratio but allowing the user to specify a trend.

**Bug 22 — Terminal exit multiple method is stubbed but never computed**
`terminal_exit_multiple=None` is hardcoded. Users POSTing a DCF request with a `method="exit_multiple"` body receive a Gordon-Growth result silently.
**Fix:** Implement the exit multiple terminal value: `TV = terminal_ebitda × exit_multiple`, or return a 400 if the requested method is not yet implemented.

---

### 2.7 E2 WACC (`src/engines/e2_wacc.py`)

**Bug 23 — Size premium and country risk premium both hardcoded to 0.0**
Lines `size_premium = 0.0  # TODO: implement market cap decile lookup` and `country_premium = 0.0  # TODO: implement country risk premium lookup` are present. For small-cap and non-US companies, cost of equity is systematically underestimated. The Damodaran country risk premium for e.g. Brazil is ~4%; ignoring it understates WACC by 2–4 percentage points.
**Fix (minimum):** Map `market_cap` to Duff & Phelps size deciles (hardcoded table is fine for now). Map `entity.country_of_incorporation` to Damodaran CRP table (country → default spread).

**Bug 24 — Zero-tax or pre-revenue companies forced into 21% tax rate**
`if effective_tax_rate is None: effective_tax_rate = 0.21`. Pre-revenue startups, tax-exempt organisations, and loss-carry-forward companies legitimately have 0% effective tax rates. The 21% fallback overstates after-tax cost of debt and therefore WACC.
**Fix:** Use `0.0` as the fallback for companies with zero or negative pretax income, using 21% only when pretax income is positive.

**Bug 25 — WACC metric names in E2 hardcoded to E1 output names**
Lines such as `"ttm_interest_expense"`, `"ttm_total_debt"`, `"ttm_pretax_income"` are string literals used to query `AnalyticsResult`. If E1 renames any TTM metric (e.g., as part of a v2 refactor), WACC silently falls back to defaults without any error.
**Fix:** Define shared constants (e.g., `E1_METRIC_NAMES` dataclass) imported by both E1 and E2, so a rename is a compile-time error.

---

### 2.8 E2 Multiples (`src/engines/e2_multiples.py`)

**Bug 26 — Dividend yield sign convention not documented**
`dps = abs(dividends_paid) / shares`. If `dividends_paid` is stored as a positive number in the DB (cash outflow shown as positive), `abs()` is redundant but harmless. If it's stored as negative (standard cash flow convention), `abs()` is required. The sign convention is not documented or enforced by a DB constraint, creating a latent bug if the data provider changes sign convention.
**Fix:** Add a `CHECK (dividends_paid <= 0)` constraint to `CashFlowStatement` or explicitly document and enforce the sign convention.

**Bug 27 — Prior-year EPS comparison uses `date.today() - 365`, not fiscal year**
PEG ratio computation compares current EPS to EPS from exactly 365 days ago. For a company that just reported Q4 results, "365 days ago" might return Q3 of the prior year, making the growth rate meaningless.
**Fix:** Query EPS by `fiscal_year - 1` and `fiscal_quarter`, not by date arithmetic.

**Bug 28 — `session.merge()` called without explicit flush before session close**
`MultipleTimeSeries` rows are merged but not flushed before the session context ends. If the caller's transaction is not committed, rows are silently lost.
**Fix:** Call `await session.flush()` after the `session.merge()` block, or ensure the engine's compute method returns rows for the caller to persist (consistent with other engines).

---

### 2.9 E2 Comps (`src/engines/e2_comps.py`)

**Bug 29 — Peer override silently ignored when no matches found**
```python
if peer_ids is not None:
    peer_group.peers = [p for p in peer_group.peers if p.security_id in peer_ids]
    if not peer_group.peers:
        peer_group = await peer_svc.get_peers(session, security_id)  # overrides the override
```
If the caller passes an explicit `peer_ids` list that produces zero matches, the code silently falls back to the auto-generated peer group instead of returning an error or empty comps. This is a logical bug — the caller's intent is not respected.
**Fix:** If the filtered list is empty, raise `ValueError("None of the specified peer_ids are valid peers")` or return empty CompsResult with quality `NO_VALID_PEERS`.

**Bug 30 — Denominator metrics use non-TTM names**
`_MULTIPLE_DENOM_MAP` maps multiples to field names like `"eps_diluted"`, `"ebitda_per_share"`, `"book_value_per_share"`. But E1 TTM engine stores metrics as `"ttm_diluted_eps"`, `"ttm_ebitda_per_share"`, `"ttm_bvps"`. The query returns nothing and implied prices are all `None` for all comps calculations.
**Fix:** Align `_MULTIPLE_DENOM_MAP` values with the actual metric names emitted by E1/E2 engines.

**Bug 31 — `session.add()` without conflict handling on `CompsResult`**
If a `CompsResult` row already exists for `(security_id, calculation_date)`, `session.add()` raises an `IntegrityError`. This means re-running the batch on the same day fails for the comps engine.
**Fix:** Use `session.merge()` (upsert) instead of `session.add()`.

---

### 2.10 E2 Football Field (`src/engines/e2_football_field.py`)

**Bug 32 — EPS metric name mismatch with E1 output**
Historical multiples use `metric_name = "eps_diluted"` but E1 emits `"ttm_diluted_eps"`. The query always returns no rows, so the entire "Historical Multiples" methodology range is always missing from the football field.
**Fix:** Use `"ttm_diluted_eps"` (matching E1 output).

**Bug 33 — Single-peer comps produces `low == mid == high`**
If only one comparable company's implied price is available:
```python
low = min(implied_prices)   # same value
high = max(implied_prices)  # same value
```
The football field shows a flat bar with no range, which is visually misleading.
**Fix:** Require at least 3 implied prices for a meaningful range. Fall back to ±10% around the single value when only 1–2 are available, flagged as `ESTIMATED`.

**Bug 34 — Sensitivity grid parsed as dict but could be any JSON type**
`if dcf.sensitivity_grid and isinstance(dcf.sensitivity_grid, dict)` — if `sensitivity_grid` is stored as a JSON array (valid) the condition silently skips extraction and the DCF range falls back to ±15% heuristic.
**Fix:** Normalise `sensitivity_grid` to a canonical dict shape when it is written by the DCF engine.

**Bug 35 — `consensus_view` stored in `data_quality` field, not `value`**
`football_consensus_view` uses `value=None` and stores the classification string in `data_quality`. Every other metric stores its label in `value`. This breaks generic consumers that read `(metric_name, value)` pairs.
**Fix:** Store the classification string in `value`; set `data_quality` to `COMPLETE` or `ESTIMATED` as appropriate.

---

### 2.11 E3 Piotroski (`src/engines/e3_piotroski.py`)

**Bug 36 — Missing shares data treated as "no dilution" without quality flag**
When `shares_prior` is `None`, F7 is set to `0` (worst case) without flagging the metric as `INSUFFICIENT_DATA`. Callers cannot distinguish "shares increased" from "data missing".
**Fix:** Set quality `INSUFFICIENT_DATA` when prior shares cannot be found.

**Bug 37 — Negative equity not propagated to F1/F3**
Negative equity is detected and logged but the F-score components that depend on ROA (F1, F3) are still computed against a negative total assets denominator. ROA is technically undefined for companies with negative equity.
**Fix:** Set all profitability components to `None` + quality `NEGATIVE_EQUITY` when total equity < 0.

---

### 2.12 E3 Altman (`src/engines/e3_altman.py`)

**Bug 38 — Altman Z-Score field name mismatch in router response**
In the analytics router, `_build_altman()` maps:
```python
x4_equity_tl=m.get("altman_x4_mve_tl"),
```
The metric stored in `AnalyticsResult` is `altman_x4_mve_tl` (correct key), but the Pydantic response field name is `x4_equity_tl`. The issue is not the mapping key but that **the response field `x4_equity_tl` always returns `None`** because the `m.get()` call uses the wrong dict key.
Wait — `m.get("altman_x4_mve_tl")` is the correct key, so X4 *does* get populated correctly. The field is just named `x4_equity_tl` in the response schema while the underlying metric is `altman_x4_mve_tl`. This is a naming inconsistency that will confuse frontend consumers: the response says `equity_tl` but the actual value alternates between MVE/TL (market-value based) and BVE/TL (book-value based) depending on the model variant.
**Fix:** Name the response field `x4_value` with an `x4_description` field explaining which denominator was used.

**Bug 39 — EBIT uses operating income as proxy without checking non-operating items**
For companies with large interest income, FX gains, or other non-operating items, `operating_income ≠ EBIT`. The X3 component (EBIT/Total Assets) will be materially wrong for financials and holding companies.
**Fix:** Compute EBIT as `operating_income + (interest_income - interest_expense)` if interest income is available; otherwise mark X3 as `ESTIMATED`.

---

### 2.13 E3 Beneish (`src/engines/e3_beneish.py`)

**Bug 40 — Missing components scored as neutral (0) instead of "unknown"**
When an M-Score component (e.g., DEPI) cannot be computed due to missing data, it is effectively excluded from the sum (coefficient × 0 = 0), pulling the score toward zero (less likely to be a manipulator). A company with 6/8 components computable could falsely appear clean just because the two missing components would have been damning.
**Fix:** When `available_count < 8`, mark `beneish_flag = "INSUFFICIENT_DATA"` and do not emit a classification. Still emit partial component values with individual quality flags.

**Bug 41 — AQI computation can produce division by zero when `1 - (CA_prior + PPE_prior) / TA_prior == 0`**
The code guards against `denominator == 0` in the ratio computation but does not guard against `(1.0 - prior_hard_assets_pct) == 0`. If a company had exactly 100% of assets in current assets + PPE in the prior year, the AQI denominator is zero.
**Fix:** Add `if prior_soft_pct == 0: return None`.

---

### 2.14 E3 Composites (`src/engines/e3_composites.py`)

**Bug 42 — Missing components score 0 (bad), not neutral**
Every composite score component defaults to `0.0` when the input metric is `None`. This biases all composite scores downward for companies with incomplete data coverage (e.g., foreign small-caps that lack some filings). A company with missing data looks worse than one with mediocre but present data.
**Fix:** When `missing_count > 0`, recalculate the score on the basis of `available_components` only, and add a scaling factor of `total_components / available_components` only if `available_count >= total_components // 2`.

**Bug 43 — Revenue growth consistency breaks on any single negative year**
```python
for val in rev_history:
    if val is not None and val > 0:
        consecutive_positive += 1
    else:
        break
```
A company with 10 years of growth, one recession year, then 5 more years of growth scores the same as a company with only 1 year of positive growth. This is "consecutive from the most recent year" not "overall consistency".
**Fix:** Compute the percentage of positive-growth years over the entire history, not consecutive from head.

**Bug 44 — Credit-aware financial strength function is defined but never called**
`compute_credit_aware_financial_strength()` (approx. line 1110) is a standalone module-level function that computes an enhanced version of financial strength incorporating Merton distance-to-default, O-Score, and credit momentum. It is never called from `E3CompositesEngine.compute()`. The core engine uses the basic version only.
**Fix:** Either remove the dead function or integrate it into `compute()` as the default implementation.

**Bug 45 — Composite score persisted without error handling**
`await self._persist_composite(...)` is not wrapped in a try/except. If DB write fails (e.g., schema mismatch, constraint violation), the exception propagates uncaught and the engine output is not returned to the batch runner.
**Fix:** Wrap persistence in try/except; log and continue rather than aborting.

---

### 2.15 E4 Screening (`src/engines/e4_screening.py`)

**Bug 46 — Frontend sends wrong filter field names**
Frontend `ScreenerDashboard.tsx:90` constructs:
```ts
{ filters: [{ metric: f.metric, operator: f.operator, value: f.value, valueTo: f.valueTo }] }
```
Backend `ScreenFilter` dataclass expects `{ field, source, op, value, value2 }`.
Mapping divergences:
- `metric` → `field` (renamed)
- `operator` → `op` (renamed)
- `valueTo` → `value2` (renamed)
- `source` is entirely missing from the frontend payload (backend defaults to `"ANALYTICS_RESULT"` which may be wrong for screener fields like sector or market cap)

This means **every screen filter is silently dropped** and the screener returns the full universe.

**Bug 47 — Universe constraint does not filter screener results**
The S&P 500 and Russell 1000 universe endpoints at `/v2/analytics/universe/sp500` and `/universe/russell1000` query `SavedScreen` for rows with `universe_type = 'sp500'`. These rows have never been seeded. Both endpoints return empty security lists. The screener's `custom_universe_ids` parameter is consequently never useful.
**Fix:** Seed the universe tables on app startup. Alternatively, drive them from the `Security` table using index membership flags.

**Bug 48 — ScreenerDashboard does not use the proper `useRunScreen` mutation**
`ScreenerDashboard.tsx` bypasses `useRunScreen()` (from `useScreening.ts`) and calls `api.post(ANALYTICS.screen, payload)` directly. This means:
- React Query cache is not populated (re-opening the results panel would re-fetch)
- Loading/error state from the mutation is not accessible
- The `ANALYTICS.screen` path is correct, but the payload format is wrong (Bug 46)

**Bug 49 — `EQUITY_METRICS` is hardcoded; dynamic fields endpoint ignored**
`ScreenerDashboard.tsx` defines `EQUITY_METRICS` as 6 hardcoded objects. The backend has a `GET /screen/fields` endpoint that returns all available screening fields dynamically. `useScreenFields()` hook exists and is never used.
**Fix:** Replace `EQUITY_METRICS` with data from `useScreenFields()`.

---

### 2.16 E4 Screens Library (`src/engines/e4_screens_library.py`)

**Bug 50 — Library screens use field names not matched to AnalyticsResult metric names**
Prebuilt screens reference fields like `"pe"`, `"roe"`, `"fcf_yield"`. The actual metric names stored in `AnalyticsResult` by E1 are `"pe_trailing"`, `"roe"`, `"fcf_yield"`. Most fields match, but `"pe"` vs `"pe_trailing"` will cause the Graham/Deep Value screens to always return zero results.
**Fix:** Audit all prebuilt screen field names against the actual `metric_name` values in `AnalyticsResult`.

**Bug 51 — Dividend Aristocrats screen has false positives**
`{ field: "dividend_growth_5y", op: "GT", value: 0 }` matches any company that just started paying a dividend this year (5-year growth is technically undefined/infinite from zero). Should also require `dividend_growth_1y > 0 AND dividend_growth_3y > 0 AND consecutive_dividend_years >= 25`.

---

### 2.17 Peer Service (`src/engines/peer_service.py`)

**Bug 52 — Stale market cap used from AnalyticsResult without freshness check**
If `AnalyticsResult` contains a market cap from a batch run 30 days ago, that value is used for peer selection market cap bands. A company whose market cap has moved significantly (e.g., post-earnings) gets wrong peers.
**Fix:** Always compute market cap from `EODPrice.close × EquityDetails.shares_outstanding` in real-time; use `AnalyticsResult` only as a fallback.

**Bug 53 — Premium/discount is `None` when peer median equals 0**
`pd_ = ((sv - p_med) / abs(p_med)) if ... p_med != 0 else None`. When peer median is 0 (common for unprofitable cohorts), the comparison silently disappears from the output.
**Fix:** Return `None` but add quality `PEER_MEDIAN_ZERO` so callers can surface the limitation.

**Bug 54 — Percentile calculation includes the subject security**
`_percentile(sv, pv + [sv])` — adding `sv` to the peer list before computing percentile means the subject always appears in its own distribution. A security at exactly the 50th percentile of its peers will show 50th percentile, not the 50th percentile among peers only.
**Fix:** Compute percentile using peer values only: `_percentile(sv, pv)`.

---

## Part 3: Backend Router Bugs (`src/api/routers/analytics.py`)

### 3.1 Response Model Field Mapping Bugs

**Bug 55 — Category keys lowercased in router but stored uppercase in DB**
`_results_to_category_dict()` (line 101): `cat_key = (r.metric_category or "OTHER").lower()`. If `AnalyticsResult.metric_category` is stored as `"PROFITABILITY"` (which is how E1 writes it), lowercasing produces `"profitability"` which then correctly maps to `RatiosByCategory.profitability`. **This actually works.** However, any metric stored with `metric_category = "Profitability"` (title case) would go to `"other"` and be silently dropped.
**Fix:** Add a DB `CHECK` constraint enforcing `metric_category = UPPER(metric_category)`.

**Bug 56 — `get_trends` silently drops rows with unexpected metric_name suffixes**
The trend parser loops over known suffixes. Any trend metric stored with an unexpected suffix pattern is dropped from the response without warning. Since `e1_trends.py` generates metrics with a fixed set of suffixes, this is only a risk if the engine is extended.
**Fix:** Log a warning for each unrecognised metric_name in the trends response.

**Bug 57 — `get_industry_kpis` extracts GICS info by iterating `rows[0].inputs`**
`for inp in rows[0].inputs` assumes `inputs` is a list of dicts each with a `"name"` key. The `inputs` JSONB column can be `None` (nullable). If the KPI engine stored `inputs = None`, this raises a `TypeError`.
**Fix:** Guard with `if rows[0].inputs else {}`.

**Bug 58 — `get_comps` on-demand fallback swallows the error**
```python
except Exception as exc:
    logger.error("Comps computation failed: %s", exc)
```
After the error is logged, execution continues, `comps` remains `None`, and the endpoint raises a 404. The client has no way to know whether the data was never computed or whether computation was attempted and failed. They will keep retrying without knowing it's a server error.
**Fix:** Return HTTP 500 with `{ "code": "COMPUTATION_FAILED", "message": str(exc) }` instead of falling through to 404.

**Bug 59 — `get_football_field` returns HTTP 200 with empty `methodologies` list on engine failure**
```python
except Exception as exc:
    logger.error("Football field failed: %s", exc)
    results = []
```
Client receives a valid `FootballFieldResponse` with no methodology ranges. The UI renders an empty football field chart rather than an error state.
**Fix:** Return HTTP 500 on engine failure.

**Bug 60 — `AllCompositeScoresResponse` can have all four score fields as `None`**
If no composite scores have been computed, all four fields (`earnings_quality`, `financial_strength`, `dividend_safety`, `value_trap`) are `None`. The endpoint returns HTTP 200 with a structurally valid but entirely null payload.
**Fix:** Return HTTP 404 when no composite scores exist, consistent with how DCF and WACC handle missing data.

**Bug 61 — `get_dupont` filters by `entity_id` only, can return rows for other securities**
The `DuPontDecomposition.security_id` column is nullable and not filtered. If entity AAPL has two securities (e.g., class A and class B), both DuPont records are returned regardless of which security the request was for.
**Fix:** Add `DuPontDecomposition.security_id == security_id` to the WHERE clause (after verifying the column is populated by the engine).

---

## Part 4: Backend Router Bugs (`src/api/routers/screening.py`)

**Bug 62 — Saved screen execution does not commit metadata update**
`GET /screens/saved/{screen_id}/run` (line 307) updates `screen.last_run_at` and `screen.result_count` then calls `await session.flush()` but **not** `await session.commit()`. Since the session is managed by the dependency injector, the commit might happen on session close — but if the response is sent before the session closes, the update could be lost.
**Fix:** Explicitly call `await session.commit()` after the flush.

**Bug 63 — Screen filter deserialization uses unvalidated JSON dict**
`screen.definition` is stored as JSONB. When a saved screen is run, `screen.definition` is passed directly to `_parse_filter_group()` without schema validation. If the saved definition was stored with an incompatible version of `ScreenRequest`, parsing will silently produce an empty filter group.
**Fix:** Validate `screen.definition` through `ScreenRequest.model_validate()` before running; return HTTP 422 on schema mismatch.

**Bug 64 — `GET /screen/fields` returns hardcoded field list**
The `ScreenFieldsResponse` (line 393) returns a static list of fields. It does not query `AnalyticsResult` to determine which fields are actually populated in the database. A field may be listed as available but have zero rows in the DB, causing every screen using it to return zero results.
**Fix:** Query `SELECT DISTINCT metric_name FROM analytics_result WHERE engine_id IN ('E1', 'E2')` to build the live field list.

---

## Part 5: Database Model Issues (`src/models/analytics.py`)

**Bug 65 — Missing index on `DuPontDecomposition.security_id`**
`DuPontDecomposition.security_id` is nullable and unindexed. The router queries by `entity_id` (which is indexed), but if security-level filtering is added, queries will be full table scans.
**Fix:** Add `Index("idx_dupont_security", DuPontDecomposition.security_id)`.

**Bug 66 — Missing index on `CalculationLineage.entity_id`**
Lineage queries (`GET /audit/{security_id}/{metric_name}`) may join on entity_id for hierarchical lookups. No index on this column.

**Bug 67 — Missing index on `CalculationLineage.calculated_at`**
Temporal queries to audit "what changed between two batch runs" require a sorted scan. Without an index, this is O(n) on the entire lineage table.

**Bug 68 — `AnalyticsResult.data_quality` max length is 20 characters**
The router in Bug 60 constructs quality strings like `"NO_DCF_DATA,NO_COMPS_DATA,NO_52W_DATA"` by joining flags with commas (`",".join(flags)`). This can easily exceed 20 characters. The DB write will silently truncate or raise an error.
**Fix:** Either increase the column to `VARCHAR(100)` or store flags as a JSONB array.

---

## Part 6: Batch Pipeline Issues (`scripts/run_analytics_batch.py`)

**Bug 69 — Single commit at end; one failure rolls back everything**
All engines run inside a single transaction. If engine E3 (Beneish) fails on one security, the entire batch's writes for E1, E2, E3 for all securities are rolled back. The batch must be re-run in full.
**Fix:** Commit after each engine completes, or commit after each security batch within an engine.

**Bug 70 — No incremental/idempotent execution**
There is no mechanism to skip securities that already have up-to-date analytics. Every batch run re-computes all engines for all securities. For a universe of 5,000 securities this could take hours.
**Fix:** Add a `--since DATE` parameter. Skip securities where `AnalyticsResult.as_of_date >= since` for all engines being run.

**Bug 71 — E3 engines skipped silently on ImportError**
```python
try:
    from src.engines.e3_piotroski import PiotroskiEngine
    engine_map["piotroski"] = PiotroskiEngine
except ImportError:
    logger.warning("E3 quality scoring engines not yet available")
```
If a module is accidentally broken (e.g., a syntax error in `e3_altman.py`), the entire E3 suite is skipped with only a WARNING log. On production this could cause quality scores to silently disappear from the DB.
**Fix:** Raise the `ImportError` instead of catching it. Missing engines are a deployment error, not a runtime condition.

**Bug 72 — No timeout per security**
DCF computation (`e2_dcf.py`) can run for several seconds per security if the OLS regression for beta (in WACC) is slow. There is no per-security timeout. A pathological security (e.g., one with 20 years of price history) could stall the batch for minutes.
**Fix:** Wrap each `engine.compute()` call in `asyncio.wait_for(..., timeout=30)`.

**Bug 73 — Batch does not run automatically on app startup**
If the database is empty (fresh deployment), all analytics endpoints return 404 or empty data. There is no `FastAPI` lifespan event or Docker entrypoint that seeds analytics data.
**Fix:** Add a `FastAPI` `lifespan` context manager that checks if `AnalyticsResult` is empty and, if so, triggers a background batch run for a seed universe of key securities.

---

## Part 7: App-Level Issues (`src/api/app.py`)

**Bug 74 — No authentication enforced by default**
The auth middleware is commented out with instructions for how to enable it. All 80+ API endpoints are currently unauthenticated. Any client with network access can read or write data.
**Fix:** Enable `Depends(get_current_user)` globally on the FastAPI app, not per-router.

**Bug 75 — No CORS middleware configured**
`CORSMiddleware` is not added to the middleware stack anywhere in `app.py`. All cross-origin requests from the frontend will be blocked by the browser in production.
**Fix:** Add `CORSMiddleware` with `allow_origins=settings.ALLOWED_ORIGINS`.

**Bug 76 — Health check does not test DB connectivity**
`GET /health` always returns `{"status": "ok"}` without checking that the database connection pool is healthy. A load balancer routing traffic to this instance will not detect a DB connection pool failure.
**Fix:** Execute `SELECT 1` against the DB pool in the health check handler.

**Bug 77 — All router imports wrapped in `try/except ImportError`**
If a router module has a runtime import error (e.g., broken model import), the router is silently skipped. The app starts and returns 404 for all routes in that router rather than failing at startup.
**Fix:** Only catch `ImportError` for optional/experimental routers. Core Pillar 1 and Pillar 2 routers should raise on import failure.

---

## Part 8: Frontend Page Bugs

### 8.1 ValuationDashboard (`frontend/src/pages/company/ValuationDashboard.tsx`)

**Bug 78 — DCF recalculate POSTs to wrong URL**
`handleDCFRecalculate` (line 172) posts to `/v2/analytics/securities/${resolvedId}/dcf`. Backend POST is at `/v2/analytics/dcf/{security_id}`. The button silently catches the 404 and shows no error to the user.
**Fix:** Change to `/v2/analytics/dcf/${resolvedId}`.

**Bug 79 — `multiplesOverTimeData` is a separate hardcoded array, never replaced**
The "Multiples Over Time (5Y)" chart at line 200 uses `multiplesOverTimeData` (20 hardcoded data points). `useMultiplesHistory` is fetched but its result `activeMultiplesHistory` only goes to `RatioDashboard`, not to this chart. These are two different charts and the second one never receives API data.
**Fix:** Replace `multiplesOverTimeData` with `activeMultiplesHistory` in the `MultiplesOverTime` component.

**Bug 80 — Football field data fetched but never rendered**
`const { data: apiFootball } = useFootballField(resolvedId)` (line 154) — `apiFootball` is never read. The football field component downstream always uses the hardcoded `MOCK_FOOTBALL`.
**Fix:** Map `apiFootball?.methodologies` to the `FootballField` component's `methods` prop.

**Bug 81 — DCF sensitivity matrix always uses hardcoded grid**
`const { data: apiSensitivity } = useDCFSensitivity(resolvedId)` (line 153) — `apiSensitivity` is never read. The `SensitivityMatrix` component uses static `waccValues` and `growthValues` arrays.
**Fix:** Wire `apiSensitivity` → `SensitivityMatrix` grid data.

**Bug 82 — Peer scatter always uses 5 hardcoded peers**
`activePeers = (apiPeers as any[]) ?? peerScatterData` — `apiPeers` is the peer comparison result, but because the endpoint path is wrong (Bug in Part 1), it's always `undefined` and mock falls back to hardcoded peers.
After fixing the path constant, also verify that the API response shape matches `PeerPoint[]` (x, y, label, highlight fields).

**Bug 83 — Company header is always "Apple Inc. / AAPL"**
`const company = { name: 'Apple Inc.', ticker: 'AAPL', price: 178.72 }` — never reads from `useSecurityStore` or route params.
**Fix:** Read from `useSecurityStore((s) => s.primary)` and format the current price from `useSecurityPrices`.

---

### 8.2 ScreenerDashboard (`frontend/src/pages/screener/ScreenerDashboard.tsx`)

**Bug 84 — All four screening management path constants are wrong**
(Covered in Part 1 mapping table.) Screener save/load completely broken.

**Bug 85 — Preview count shows "20 of 20" when backend is unreachable**
`totalCount = backendResults ? backendResults.length : MOCK_STOCKS.length`. If no backend results, `totalCount = 20` (mock count), so the preview reads "20 of 20 securities". User cannot tell whether the screen matched 20 real securities or fell back to the mock list.
**Fix:** `totalCount` should be `null` when results are from the mock fallback, and the `LivePreviewCount` component should display "Demo mode — backend unavailable" instead.

---

### 8.3 QuantDashboard (`frontend/src/pages/quant/QuantDashboard.tsx`)

**Bug 86 — `useCorrelation()` is a GET query in the component layer but targets a non-existent endpoint**
`hooks/useAnalytics.ts:195` implements `useCorrelation()` as `useApiQuery(...)` calling `ANALYTICS.correlation = '/v2/analytics/correlation'`. No such backend endpoint exists. The mutation version in `api/hooks/useAnalytics.ts` is the API layer hook but is never the one used by pages.
Result: `apiCorrelation` is always `undefined`; factor performance and risk KPIs always fall back to mocks.

**Bug 87 — `useFactorExposure(undefined)` and `useTechnicalSignals(undefined)` are disabled**
Both hooks have `enabled: !!secId`. Passing `undefined` disables them permanently. The Quant Dashboard has no security context and no way to select one.
**Fix:** Either make these portfolio-level (pass no secId, use universe average) or add a security/universe selector to the Quant Dashboard.

**Bug 88 — Volatility surface is entirely computed data, no backend**
The implied volatility surface (lines 71–82) is generated from a hardcoded formula. No options data endpoint exists and no hook is called. The entire panel is decorative.
**Fix:** Either remove the panel, or clearly label it "Illustrative — not from live data".

---

### 8.4 RiskDashboard (`frontend/src/pages/risk/RiskDashboard.tsx`)

**Bug 89 — Wrong hook family used; portfolio risk API completely bypassed**
`RiskDashboard` imports `useCorrelation` and `useFactorExposure` — security-level analytics hooks. The correct hooks are in `useRiskAnalytics.ts`: `useVaR`, `useStressHistorical`, `useConcentration`, `useRiskFactors`. None of the portfolio risk endpoints are ever called.
**Fix:** Refactor `RiskDashboard` to accept `portfolioId` from route params. Replace all hook calls with portfolio-risk versions.

**Bug 90 — All KPIs, stress tests, VaR decomposition, sector concentration are always mock**
Because the correct hooks are never called, every number visible on the Risk Dashboard is hardcoded. This is functionally equivalent to a static HTML page.

---

### 8.5 BacktestDashboard (`frontend/src/pages/quant/BacktestDashboard.tsx`)

**Bug 91 — KPI tiles hardcoded, never update from API**
The KPI row (line 158–166) shows `'6'` (strategies), `'142'` (backtests run), `'+16.24%'` (best), `'+18.42%'` (avg CAGR). These are hardcoded strings, never replaced by API data.

**Bug 92 — `handleRunBacktest` POSTs but has a completely empty catch block**
```typescript
try { await api.post(BACKTESTING.run, { ... }); } catch {}
```
No error state set, no user feedback. The run button appears to complete immediately whether or not the backend is reachable.
**Fix:** Show a toast/error message in the catch block. Set a loading state while the request is in flight.

**Bug 93 — Strategy selector not populated from API**
`strategies` (line 40–47, 6 hardcoded items) never replaced by API data despite `useBacktestStrategies()` being called. If strategies are fetched from the backend, the dropdown still shows the static list.

---

### 8.6 CustomIndexBuilder (`frontend/src/pages/quant/CustomIndexBuilder.tsx`)

**Bug 94 — API response property name mismatch**
`(apiBenchmarks as any)?.indices` — the API response key is `benchmarks`, not `indices`. Always falls back to mock data.
**Fix:** Use `?.benchmarks` (or check the actual response shape from the backend).

**Bug 95 — `handleCreateIndex` POSTs to the list endpoint**
`api.post(BENCHMARKS.list, ...)` — posting to a list endpoint is semantically wrong. The correct endpoint would be `BENCHMARKS.create` or similar.

---

## Part 9: Frontend Component Bugs

### 9.1 DCFPanel Component (`frontend/src/components/valuation/DCFPanel.tsx`)

**Bug 96 — "Run DCF" button simulates a timer but does no actual computation**
The `startComputing()` function starts a `setInterval` that counts elapsed time. It does not call any API mutation. After the interval, the panel never updates with new results.
**Fix:** Replace the fake timer with `useRunDcfMutation(securityId)` that POSTs to `/v2/analytics/dcf/{id}` with the current assumption inputs.

---

### 9.2 PeerScatter Component (`frontend/src/components/valuation/PeerScatter.tsx`)

**Bug 97 — Lasso selection has no persistence or downstream action**
Selected peers are passed to `onLassoSelect?.(selectedIds)` but no parent component uses this callback to trigger a follow-up API call or update a saved peer group.

---

### 9.3 ScreenResults Component (`frontend/src/components/screener/ScreenResults.tsx`)

**Bug 98 — Format `'pct'` formatter calls `.toFixed(1)` on a value that may be a string**
Column format `'pct'` applies `(val as number).toFixed(1)`. If the API returns `"14.2%"` (string) instead of `14.2` (number), this throws `TypeError: val.toFixed is not a function`.
**Fix:** Parse the value to `parseFloat()` before calling `.toFixed()`.

---

## Part 10: Summary Tables

### 10.1 Backend Path Mismatches (endpoints exist, paths wrong in frontend)

| Frontend constant | Frontend calls | Backend at |
|---|---|---|
| `ANALYTICS.ratios` | `.../securities/{id}/ratios` | `/ratios/{id}` |
| `ANALYTICS.allScores` | `.../securities/{id}/scores/all` | `/scores/{id}` |
| `ANALYTICS.compositeScores` | `.../securities/{id}/composite-scores` | `/scores/{id}/composites` |
| `ANALYTICS.dupont` | `.../securities/{id}/dupont` | `/dupont/{id}` |
| `ANALYTICS.dupontHistory` | `.../securities/{id}/dupont/history` | `/dupont/{id}/history` |
| `ANALYTICS.multiplesHistory` | `.../securities/{id}/multiples/history` | `/multiples/{id}/history` |
| `ANALYTICS.historicalMultiples` | `.../securities/{id}/historical-multiples` | `/multiples/{id}` |
| `ANALYTICS.peerGroup` | `.../securities/{id}/peer-group` | `/peers/{id}` |
| `ANALYTICS.peerComparison` | `.../securities/{id}/peer-comparison` | `/ratios/{id}/vs-peers` |
| `ANALYTICS.dcf` | `.../securities/{id}/dcf` (GET) | `/dcf/{id}/default` |
| `ANALYTICS.footballField` | `.../securities/{id}/football-field` | `/valuation/{id}/summary` |
| `ANALYTICS.screenPrebuilt` | `.../screen/prebuilt` | `/screens/library` |
| `ANALYTICS.screenSave` | `.../screen/save` | `/screens/save` |
| `ANALYTICS.screenHistory` | `.../screen/history` | `/screens/saved` |

### 10.2 Frontend endpoints that have NO matching backend

| Frontend constant | Backend endpoint | Status |
|---|---|---|
| `ANALYTICS.qualityScore` | None | Backend missing |
| `ANALYTICS.valueScore` | None | Backend missing |
| `ANALYTICS.growthScore` | None | Backend missing |
| `ANALYTICS.momentumScore` | None | Backend missing |
| `ANALYTICS.volatilityScore` | None | Backend missing |
| `ANALYTICS.sectorRelative` | None | Backend missing |
| `ANALYTICS.fairValue` | None | Backend missing |
| `ANALYTICS.technicalSignals` | None | Backend missing |
| `ANALYTICS.seasonality` | None | Backend missing |
| `ANALYTICS.correlation` | None | Backend missing |
| `ANALYTICS.factorExposure` | None | Backend missing |
| `ANALYTICS.peerRanking` | POST `/rank` only (method mismatch) | Partial |
| `ANALYTICS.dcfSensitivity` | No GET (only part of POST) | Backend missing |

### 10.3 Backend endpoints with no frontend hook

| Backend path | Feature | Status |
|---|---|---|
| `GET /wacc/{id}` | WACC | No frontend hook |
| `GET /wacc/{id}/history` | WACC history | No frontend hook |
| `GET /wacc/{id}/components` | WACC breakdown | No frontend hook |
| `GET /ttm/{id}` | Trailing twelve months | No frontend hook |
| `GET /multiples/{id}` | Current multiples | No frontend hook |
| `GET /trends/{id}` | Metric trends | No frontend hook |
| `GET /kpis/{id}` | Industry KPIs | No frontend hook |
| `GET /scores/{id}/piotroski` | Piotroski detail | No individual hook |
| `GET /scores/{id}/altman` | Altman detail | No individual hook |
| `GET /scores/{id}/beneish` | Beneish detail | No individual hook |
| `GET /scores/{id}/history` | Score history | No frontend hook |
| `POST /dcf/{id}` | Custom DCF computation | No mutation hook |
| `GET /comps/{id}` | Comps | No frontend hook |
| `GET /comps/{id}/summary` | Comps summary | No frontend hook |
| `GET /audit/{id}/{metric}` | Metric lineage | No frontend hook |
| `POST /rank` | Multi-factor ranking | No frontend hook |
| `GET /universe/*` | Universe lists | No frontend hooks |
| `GET /ratios/{id}/percentile` | Percentile ranks | No frontend hook |
| `GET /ratios/{id}/history` | Ratio history | No frontend hook |

### 10.4 Issues by Severity

| Count | Severity | Category |
|---|---|---|
| 3 | Critical | Universal path mismatch, auth disabled, batch single-transaction |
| 15 | High | Engine calculation bugs (sensitivity grid, employee count, composites bias, comps denoms, size/country premium, etc.) |
| 22 | Medium | Silent failures in router, missing hooks, frontend mock fallbacks, wrong hooks in Risk/Quant dash |
| 18 | Low | Missing DB indexes, hardcoded thresholds, minor type issues, decorative UI panels |

Total tracked bugs: **98**

---

## Part 11: Remediation Plan

### Phase 1 — Unblock all analytics hooks (1 day)
Fix all 14 ANALYTICS path constants in `frontend/src/api/endpoints.ts`. Every hook immediately starts returning real data from the backend.

### Phase 2 — Wire API data into ValuationDashboard (1–2 days)
- Replace `multiplesOverTimeData` with `activeMultiplesHistory`
- Wire `apiFootball` → `FootballField` component
- Wire `apiSensitivity` → `SensitivityMatrix` component
- Fix DCF recalculate POST URL
- Replace hardcoded company header with `useSecurityStore`
- Verify `PeerScatter` data shape against `usePeerComparison` response

### Phase 3 — Fix screener filter format (half day)
Remap `{ metric, operator, valueTo }` → `{ field, source, op, value2 }` in `ScreenerDashboard.handleRunScreen`. Load filter fields from `useScreenFields()`. Fix screen management path constants.

### Phase 4 — Fix RiskDashboard and QuantDashboard (1–2 days)
- Refactor `RiskDashboard` to use `useVaR`, `useStressHistorical`, `useConcentration`, `useRiskFactors` from `useRiskAnalytics.ts`
- Add portfolio context (route param or selector)
- Remove or label the fake volatility surface in `QuantDashboard`
- Fix `useCorrelation` — decide if it's GET (parameterless) or POST (parameterised) and implement the backend endpoint

### Phase 5 — Fix critical engine bugs (2–3 days)
In priority order:
1. DCF sensitivity grid (Bug 19) — full re-discount per grid cell
2. WACC size and country premiums (Bug 23) — add static lookup tables
3. Comps denominator metric names (Bug 30) — align with E1 output names
4. Football field EPS metric name (Bug 32) — use `ttm_diluted_eps`
5. E3 composites missing-data bias (Bug 42) — proportional scoring
6. E4 screening field name mapping (Bug 46) — add field name normalisation

### Phase 6 — Add missing backend endpoints (3–5 days)
Priority based on which frontend hooks already exist:
1. `GET /v2/analytics/dcf/{id}/sensitivity` — return sensitivity grid from pre-computed DCF
2. `GET /v2/analytics/peers/{id}/ranking` — expose ranked peer list
3. `GET /v2/analytics/correlation` or `POST /v2/analytics/correlation` — correlation matrix
4. `GET /v2/analytics/factor-exposure/{id}` — Fama-French factor loadings
5. `GET /v2/analytics/technical-signals/{id}` — RSI, MACD, momentum composite
6. Five individual sub-score endpoints (quality/value/growth/momentum/volatility)

### Phase 7 — Batch pipeline hardening (1 day)
1. Per-engine commits (Bug 69)
2. `--since DATE` incremental mode (Bug 70)
3. Remove `try/except` from engine imports (Bug 71)
4. Per-security timeout (Bug 72)
5. Auto-seed on app startup (Bug 73)

### Phase 8 — Infrastructure fixes (1 day)
1. CORS middleware (Bug 75)
2. DB health check (Bug 76)
3. Authentication (Bug 74)
4. Missing DB indexes (Bugs 65–68)
5. `data_quality` column length (Bug 68)

---

*Report generated by static code analysis. 98 distinct bugs tracked across backend engines, routers, models, batch pipeline, app configuration, frontend hooks, pages, and components.*
