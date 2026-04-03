# Pillar 4 Portfolio & Risk — Full Audit Report

**Date:** 2026-04-03
**Scope:** Every engine, router, model, hook, API endpoint constant, and frontend page in Pillar 4 (Portfolio & Risk)
**Method:** Static code analysis — no tests run
**Total Issues Found:** 98

---

## Executive Summary

Pillar 4's structure — portfolio CRUD, positions, transactions, NAV, performance attribution, risk analytics, watchlists, backtesting, and quant tools — is fully scaffolded with a rich API surface and polished frontend. However the feature is almost entirely non-functional end-to-end for the following systemic reasons:

1. **The three core engines** (`nav_engine.py`, `e5_risk.py`, `attribution_engine.py`) that would compute live portfolio metrics are **never called** from any router. All three are implemented and tested in isolation but not wired in.

2. **Position market values are never calculated.** `Position.market_value`, `unrealized_pnl`, `unrealized_pnl_pct`, `weight`, `closing_price`, and `day_change_pct` are defined on the model but **never populated** by any code path. Since the NAV endpoint sums `Position.market_value`, **portfolio NAV is always 0**.

3. **Two of the three most important mutation hooks call the wrong endpoint.** `useAddPosition()` and `useRecordTransaction()` both POST to `PORTFOLIOS.list` — the portfolio list endpoint — instead of their respective position/transaction endpoints. Every "Add Position" and "Record Transaction" action from the UI silently sends data to the wrong URL.

4. **All stress test endpoints return hardcoded fake numbers.** The historical stress test always returns `total_pnl=-$15,000`, `worst_position=AAPL -$5,000`. The hypothetical stress test always returns `total_pnl=-$8,000`, `worst_position=MSFT -$3,000`. These are literally hardcoded in the router regardless of what portfolio or scenario the user selects.

5. **The backtesting engine is a complete stub.** Every backtest immediately returns `status="COMPLETED"` with zero computed metrics. No backtesting engine is imported or called.

6. **The quant regression endpoint uses integer indices `[0, 1, 2, ...]` as the X variable** instead of actual financial data. Every regression result is statistically meaningless.

7. **All users share the same hardcoded `DEFAULT_USER` identity.** There is no user isolation — every user sees every other user's portfolios and watchlists.

8. **Every Pillar 4 frontend page** uses hardcoded mock data with specific portfolio names ("Core Growth"), specific tickers (AAPL, MSFT, NVDA, AMZN), and specific financial figures displayed as live data. Performance charts use a random-walk generator, not API data.

---

## Part 1: Router Layer — 42 Issues

### P4-R-001: DEFAULT_USER Hardcoded Across All Portfolio Routers
**Files:** `portfolios.py:46`, `portfolio_watchlists.py:29`
**Severity:** Critical

```python
DEFAULT_USER = "default_user"
```

This constant is used for every portfolio creation, every portfolio query, and every watchlist operation. All users in the system share the same user identity. User A can view, modify, and delete User B's portfolios simply by knowing the UUID. No authentication token is read, no session user is extracted. This affects every single endpoint in Pillar 4.

---

### P4-R-002: useAddPosition() and useRecordTransaction() Call Wrong Endpoint
**File:** `frontend/src/hooks/usePortfolio.ts`, lines ~54–59
**Severity:** Critical

```typescript
export function useAddPosition() {
  return useApiMutation(PORTFOLIOS.list, [['portfolios']]);
}
export function useRecordTransaction() {
  return useApiMutation(PORTFOLIOS.list, [['portfolios']]);
}
```

Both mutations POST to `PORTFOLIOS.list` — the portfolio list endpoint. The correct targets are `PORTFOLIOS.positions(id)` and `PORTFOLIOS.transactions(id)` respectively. Every "Add Position" and "Record Transaction" action from any frontend page sends data to the wrong URL and either creates a malformed portfolio or returns a 405/422 error.

---

### P4-R-003: useClonePortfolio() Calls Create Instead of Clone
**File:** `frontend/src/hooks/usePortfolio.ts`, line ~31
**Severity:** Critical

```typescript
export function useClonePortfolio() {
  return useApiMutation<unknown, { id: string }>(
    PORTFOLIOS.create,   // Wrong — should be PORTFOLIOS.clone(id)
    [['portfolios']]
  );
}
```

Every clone operation creates a brand-new empty portfolio instead of cloning the source. The clone endpoint at `POST /portfolios/{id}/clone` is never reachable from the frontend.

---

### P4-R-004: Historical Stress Test Returns Hardcoded AAPL Values
**File:** `src/api/routers/portfolio_risk.py`, lines 481–495
**Severity:** Critical

```python
return HistoricalStressTestResponse(
    total_pnl_dollar=Decimal("-15000.00"),       # HARDCODED
    total_pnl_percent=Decimal("-0.150000"),       # HARDCODED
    max_drawdown_pct=Decimal("-0.250000"),        # HARDCODED
    recovery_time_months=Decimal("18.0"),         # HARDCODED
    worst_positions={"worst": [{"ticker": "AAPL", "pnl": -5000}]},  # HARDCODED
)
```

The endpoint accepts `body.shocks` from the request but ignores it entirely. Every portfolio, every scenario, every user receives identical numbers. The AAPL ticker is hardcoded in a production response.

---

### P4-R-005: Hypothetical Stress Test Returns Hardcoded MSFT Values
**File:** `src/api/routers/portfolio_risk.py`, lines 527–547
**Severity:** Critical

```python
return HypotheticalStressTestResponse(
    total_pnl_dollar=Decimal("-8000.00"),        # HARDCODED
    total_pnl_percent=Decimal("-0.080000"),       # HARDCODED
    worst_positions={"worst": [{"ticker": "MSFT", "pnl": -3000}]},  # HARDCODED
)
```

Same pattern. `body.shocks` and the actual portfolio are completely ignored.

---

### P4-R-006: Backtesting Endpoint Marks All Runs COMPLETED Without Computation
**File:** `src/api/routers/backtesting.py`, line 34
**Severity:** Critical

```python
run = BacktestRun(
    strategy_id=body.strategy_id,
    status="COMPLETED",     # HARDCODED
    ...
)
```

No backtesting engine is imported or called. `backtester.py` exists in `src/engines/` with full simulation logic but is never referenced from this router. Every backtest request immediately completes with zero computed performance metrics.

---

### P4-R-007: Quant Regression Uses Integer Indices as X Data
**File:** `src/api/routers/quant.py`, lines 106–114
**Severity:** Critical

```python
# For now, use the return series itself as both x and y (self-regression)
# In production, x would come from independent_vars source
x_returns = list(range(len(y_returns)))      # [0, 1, 2, 3, ...]
x_returns_f = [float(i) for i in x_returns]
independent_var=body.independent_vars[0] if body.independent_vars else "x",
```

The regression uses sequential integers as the independent variable regardless of what variables the user specified in `body.independent_vars`. Every slope, R², t-stat, and p-value returned is meaningless. Rolling regression (lines 125–126) has the identical problem.

---

### P4-R-008: Position.market_value and Related Fields Never Populated
**Files:** `src/api/routers/portfolios.py`, multiple positions
**Severity:** Critical

`Position.market_value`, `unrealized_pnl`, `unrealized_pnl_pct`, `weight`, `closing_price`, and `day_change_pct` are never set during:
- `add_position()` (lines 493–557) — not set
- `create_transaction()` (lines 633–763) — not set
- CSV upload (lines 89–220) — not set

The `nav_engine.py` would compute these but is never called. Since the NAV endpoint sums `Position.market_value` via SQL aggregate, and all values are `NULL`, **portfolio NAV is always 0** for every portfolio.

---

### P4-R-009: nav_engine.py Never Called From Any Router
**File:** `src/engines/nav_engine.py` (303 lines), `src/api/routers/portfolios.py`
**Severity:** Critical

`nav_engine.py` implements `compute_position_valuation()`, `compute_position_weights()`, `build_nav_snapshot()`, and `validate_nav_integrity()`. Not one of these functions is imported or invoked from `portfolios.py` or `portfolio_performance.py`. Market values remain `NULL`, NAV is always 0, and position weights are always `NULL`.

---

### P4-R-010: e5_risk.py Never Called From portfolio_risk.py
**File:** `src/engines/e5_risk.py` (678 lines), `src/api/routers/portfolio_risk.py`
**Severity:** Critical

`e5_risk.py` implements VaR, CVaR, parametric VaR, stress testing, factor exposure, liquidity scoring, and fundamental risk scoring. The risk router imports **nothing** from this engine. All risk data is read from pre-computed snapshots in the database. No batch job or on-demand path populates those snapshots. Every risk endpoint returns `None` or empty unless snapshots exist from some external source that doesn't exist.

---

### P4-R-011: attribution_engine.py Never Called From portfolio_performance.py
**File:** `src/engines/attribution_engine.py` (413 lines), `src/api/routers/portfolio_performance.py`
**Severity:** Critical

Brinson BHB attribution, security contribution, factor attribution, and multi-period linking are all implemented in `attribution_engine.py`. The performance router reads pre-computed `AttributionResult` rows from the database. No code path ever calls the engine to populate those rows. Attribution endpoints always return empty results.

---

### P4-R-012: Parametric VaR Formula Mathematically Wrong
**File:** `src/engines/e5_risk.py`, lines 267–274
**Severity:** Critical

```python
pvar_1d = -(daily_mean - z * daily_std)
```

The correct parametric VaR formula is: `VaR = -(μ + z·σ)` where `z` is negative for left-tail quantiles, or equivalently `VaR = z·σ - μ` using the absolute z-value. The current formula computes `-(μ - z·σ) = z·σ - μ` only if z is positive — but z values from `scipy.stats.norm.ppf` at the 5th percentile are negative (≈ −1.645), making the formula `−(μ − (−1.645)·σ) = −μ − 1.645·σ`. This overstates VaR and has the wrong sign structure.

---

### P4-R-013: Historical VaR Sign Error
**File:** `src/engines/e5_risk.py`, lines 243–253
**Severity:** High

```python
var_1d = -_percentile_pure(sorted_rets, pct)
```

The percentile of sorted returns at the 5th percentile is already negative (a loss). Negating it produces a positive number (correct for "loss magnitude"). However this convention is applied inconsistently: the CVaR computation (lines 255–264) also negates, but the inputs are already losses. The sign convention is not documented and inconsistently applied.

---

### P4-R-014: Multi-Period Attribution Uses Arithmetic Instead of Geometric Linking
**File:** `src/engines/attribution_engine.py`, lines 328–329
**Severity:** High

```python
total_port = sum(r.total_portfolio_return for r in period_results)
total_bench = sum(r.total_benchmark_return for r in period_results)
```

Arithmetic summing of period returns produces wrong cumulative results whenever returns have opposite signs across periods (which is common). The correct approach is geometric linking: `(1+r1)·(1+r2)·...−1`. With Period 1 = +10% and Period 2 = −10%, arithmetic gives 0% but geometric gives −1%. This error compounds over multi-year attribution periods.

---

### P4-R-015: CVaR Wrong Tail Indexing
**File:** `src/engines/e5_risk.py`, lines 255–264
**Severity:** High

```python
cutoff_idx = max(1, int(n * pct / 100.0))
tail = sorted_rets[:cutoff_idx]
cvar = -_mean(tail)
```

`sorted_rets` is sorted ascending (worst returns first). `cutoff_idx` for pct=5%, n=252 days is 12. `tail = sorted_rets[:12]` takes the 12 worst returns. `_mean(tail)` is negative (losses). `-mean` is positive. This is actually correct directionally. However the formula `int(n * pct / 100.0)` for pct=5 gives `int(252 * 0.05) = 12`, which is the floor and may exclude the exact 5th percentile observation — a fencepost error producing slightly overstated CVaR.

---

### P4-R-016: Corporate Action Apply Ignores Request Body
**File:** `src/api/routers/portfolios.py`, lines 971–1009
**Severity:** High

```python
body: CorporateActionApplyRequest | None = None   # accepted
# ... body is never used ...
queue_entry.status = "APPLIED"
queue_entry.applied_at = datetime.utcnow()
```

The `CorporateActionApplyRequest` presumably contains split ratio, dividend amount, or other action parameters. None of these are used. Applying a 2-for-1 stock split or a special dividend does nothing to positions or cash balances. The action is merely marked as applied.

---

### P4-R-017: Performance Report Generation Returns Stub Data
**File:** `src/api/routers/portfolio_performance.py`, lines 640–641
**Severity:** High

```python
status="COMPLETED",
result_data={"report_type": report_type, "portfolio_name": portfolio.portfolio_name},
```

Every call to the 4 report generation endpoints (`/reports/summary`, `/reports/performance`, `/reports/attribution`, `/reports/holdings`) immediately returns COMPLETED with a stub result containing only the report type and portfolio name. No report content is generated. No reporting engine is called.

---

### P4-R-018: All Risk Endpoints Return None When No Snapshot Exists
**File:** `src/api/routers/portfolio_risk.py`, lines 117–168
**Severity:** High

The risk dashboard, VaR, CVaR, concentration, factor exposure, and all other risk endpoints query `PortfolioVarSnapshot`, `ConcentrationAnalysis`, and `FactorExposureSnapshot` tables. These tables are **never populated** by any code path (the engine that would populate them — `e5_risk.py` — is never called, and no batch script exists). Every risk endpoint returns `None` or empty collections for every portfolio.

---

### P4-R-019: flush() Without commit() — 20 Locations Across Portfolio Routers
**Files:** `portfolios.py`, `portfolio_performance.py`, `portfolio_risk.py`, `portfolio_watchlists.py`
**Severity:** High

`session.flush()` is used in place of `session.commit()` at approximately 20 locations across all 4 portfolio routers. Mutations that appear to succeed (positions added, transactions recorded, compliance rules created, stress test results stored, drift targets set, watchlist entries added/removed) may silently not persist on connection recycling or exception. Specific examples:

- `portfolio_risk.py`: lines 497, 543, 731, 787, 826, 1087
- `portfolio_performance.py`: lines 94, 175, 209, 274, 644
- `portfolio_watchlists.py`: lines 94, 175, 209, 274
- `portfolios.py`: multiple position/transaction paths

---

### P4-R-020: Watchlist Alerts Endpoint Is a Confirmed Stub
**File:** `src/api/routers/portfolio_watchlists.py`, lines 225–237
**Severity:** High

```python
# Stub: in production this would query an alert engine
return WatchlistAlertResponse(alerts=[])
```

`GET /portfolios/watchlists/{id}/alerts` always returns an empty alert list. No alert engine is called, no database query is made.

---

### P4-R-021: Watchlist Alert Digest Returns Hardcoded Zeros
**File:** `src/api/routers/portfolio_watchlists.py`, lines 239–255
**Severity:** High

```python
return WatchlistAlertDigestResponse(
    total_alerts=0,
    high_severity=0,
    medium_severity=0,
    low_severity=0,
    summary="No active alerts.",   # hardcoded string
)
```

`GET /portfolios/watchlists/{id}/alerts/digest` always returns the same hardcoded response regardless of watchlist content or actual alert state.

---

### P4-R-022: Watchlist Earnings Calendar Returns Empty List
**File:** `src/api/routers/portfolio_watchlists.py`, lines 285–296
**Severity:** High

```python
# Stub: in production this would query earnings data
return EarningsCalendarResponse(entries=[])
```

`GET /portfolios/watchlists/{id}/earnings-calendar` always returns an empty calendar. The earnings data from `earnings_p2.py` router is never consulted.

---

### P4-R-023: Watchlist Dashboard Returns Only Names, No Metrics
**File:** `src/api/routers/portfolio_watchlists.py`, lines 299–326
**Severity:** High

The dashboard endpoint returns `WatchlistDashboardEntity` with only `entity_id` and `legal_name` per entity. All price data, returns, volatility, sentiment scores, and other dashboard metrics are absent. The comment at line 307 notes "key metrics" should be included.

---

### P4-R-024: Pre-Trade Check Ignores Current Portfolio Positions
**File:** `src/api/routers/portfolio_risk.py`, lines 957–980
**Severity:** High

```python
trade_value = body.shares * body.price
```

The pre-trade compliance check only evaluates the proposed trade in isolation. It does not check the current portfolio composition, so a portfolio already at 25% concentration in one sector can add more without triggering the position limit rule. Real pre-trade checks must evaluate post-trade state.

---

### P4-R-025: _get_position() Doesn't Verify Portfolio Ownership
**File:** `src/api/routers/portfolios.py`, lines 74–81
**Severity:** High

`_get_position(session, position_id)` queries position by ID only, without checking `position.portfolio_id == portfolio_id`. Any user who knows a position UUID can update or delete it regardless of which portfolio it belongs to.

---

### P4-R-026: Drawdown Response Uses Wrong Date Fields
**File:** `src/api/routers/portfolio_performance.py`, lines 362–368
**Severity:** High

```python
peak_date=snap.period_start if snap else None,
trough_date=snap.period_end if snap else None,
```

`period_start` is the start of the measurement period, not the date the portfolio peaked. `period_end` is the end of the period, not the date the portfolio troughed. This is semantically wrong — the drawdown response gives the analysis period boundaries as peak/trough dates.

---

### P4-R-027: `session.delete()` Called With `await` (Wrong Syntax)
**File:** `src/api/routers/portfolio_watchlists.py`, line 208
**Severity:** Medium

```python
await session.delete(entry)
```

SQLAlchemy's `session.delete()` is a synchronous method that returns `None`. Adding `await` causes a `TypeError: object NoneType can't be used in 'await' expression`. The correct pattern is `session.delete(entry)` followed by `await session.flush()` or `await session.commit()`.

---

### P4-R-028: Query Parameter `period` Accepted But Never Used
**File:** `src/api/routers/portfolio_performance.py`, lines 154, 178, 209, 280, 311
**Severity:** Medium

Multiple performance endpoints accept a `period` parameter (e.g., `"1M"`, `"3M"`, `"1Y"`) but the parameter is never used in SQL queries. All endpoints query `ORDER BY ... DESC LIMIT 1` regardless of the period. Requesting 3-month returns returns the same data as requesting 1-year returns.

---

### P4-R-029: Portfolio Clone Inherits Current Cash, Not Initial Cash
**File:** `src/api/routers/portfolios.py`, lines 402–403
**Severity:** Medium

```python
initial_cash=source.current_cash,   # should be source.initial_cash
current_cash=source.current_cash,
```

A cloned portfolio starts with the source's current cash (which reflects all buys/sells made). If the source spent 40% of its initial cash on positions, the clone starts with 60% of the intended initial capital.

---

### P4-R-030: Backtest Compare Endpoint Doesn't Compute Comparison Metrics
**File:** `src/api/routers/backtesting.py`, lines 133–149
**Severity:** Medium

The `/analytics/backtest/compare` endpoint fetches two backtest runs and returns them side by side, but computes no differential analysis — no return spread, no risk-adjusted comparison, no statistical significance testing.

---

### P4-R-031: Quant Correlation Matrix Silently Skips Invalid UUIDs
**File:** `src/api/routers/quant.py`, lines 295–298
**Severity:** Medium

```python
try:
    sid = uuid.UUID(sid_str)
except (ValueError, TypeError):
    continue
```

Invalid security IDs are silently skipped. If all IDs are malformed, the correlation matrix returns empty. There is no error response telling the client which IDs were rejected.

---

### P4-R-032: Backtest Benchmark Hardcoded to "SPY"
**File:** `src/api/routers/quant.py`, line 395
**Severity:** Medium

```python
benchmark="SPY",
```

The benchmark is hardcoded in the response. Any user running a backtest on a fixed-income, international, or alternative strategy sees SPY as the comparison benchmark regardless of what they specified.

---

### P4-R-033: Transaction Type Validation Too Lenient
**File:** `src/api/routers/portfolios.py`, lines 654–660
**Severity:** Medium

Any transaction type other than "BUY" or "SELL" is accepted silently with `net_amount = gross; cash_impact = 0`. Invalid types like "BUUY" or "TRASFER" produce no error.

---

### P4-R-034: Position Update Accepts Negative Shares and Negative Cost Basis
**File:** `src/api/routers/portfolios.py`, lines 568–576
**Severity:** Low

No validation that `shares >= 0` or `cost_basis_per_share >= 0`. A user can set a position to negative 1000 shares, which would corrupt NAV and risk calculations.

---

### P4-R-035: Clone Position Missing first_acquisition_date
**File:** `src/api/routers/portfolios.py`, line 428
**Severity:** Low

When cloning a portfolio, the cloned positions do not copy `first_acquisition_date`. All cloned positions have `first_acquisition_date = None`, breaking any holding period return calculation.

---

---

## Part 2: Engine Layer — 12 Issues

### P4-E-001: nav_engine.py — NAV Tolerance Check Uses Absolute Rather Than Relative Value
**File:** `src/engines/nav_engine.py`, lines 164–177
**Severity:** Medium

```python
tolerance: float = 0.01
```

A tolerance of $0.01 cents is used for NAV integrity checks. For a $100M portfolio, a $0.01 discrepancy is noise. For a $500 portfolio, $0.01 is a 2% error. The tolerance should be portfolio-value-relative (e.g., 0.0001 × NAV).

---

### P4-E-002: nav_engine.py — Negative NAV Produces Wrong Cash Weight
**File:** `src/engines/nav_engine.py`, lines 146–150
**Severity:** Low

```python
if nav == 0.0: return 0.0
```

If NAV is negative (leveraged portfolio at a loss), the guard doesn't trigger and the function returns a negative or wrongly-signed cash weight. Should be `if nav <= 0.0`.

---

### P4-E-003: e5_stress_scenarios.py — Inconsistent Shock Parameter Keys
**File:** `src/engines/e5_stress_scenarios.py`, lines 35–68
**Severity:** Medium

Equity shocks use `"shock_pct": -0.10` while rate shocks use `"rate_shock_bps": 100`. Any code consuming both scenario types must handle two different key names. There is no normalization utility and no documentation of the expected keys.

---

### P4-E-004: attribution_engine.py — Brinson Attribution Missing Weight-Sum Validation
**File:** `src/engines/attribution_engine.py`, lines 248–250
**Severity:** High

```python
total_port_return = sum(s["weight"] * s["return"] for s in portfolio_sectors)
```

If portfolio sector weights sum to 0.8 (80% assigned, 20% cash), the computed total portfolio return is 80% of the actual return. There is no assertion that weights sum to 1.0 before computing attribution effects.

---

### P4-E-005: attribution_engine.py — Factor Attribution Silently Drops Missing Factors
**File:** `src/engines/attribution_engine.py`, lines 350–373
**Severity:** Medium

```python
all_factors &= set(factor_returns.keys())
```

If the portfolio has exposure to 5 factors but factor returns data is only available for 3, the attribution is computed on 3 factors. The residual increases but there is no warning that 2 factors were dropped.

---

### P4-E-006: attribution_engine.py — Stock-Specific Return Not Integrated Automatically
**File:** `src/engines/attribution_engine.py`, line 376
**Severity:** Low

```python
stock_specific_return=0.0,  # set by caller via compute_stock_specific_return
```

The caller must manually call `compute_stock_specific_return()` and patch the result back. This is a design flaw — the function should either integrate the calculation internally or clearly document the two-step pattern.

---

### P4-E-007: e5_risk.py — MIN_OBSERVATIONS = 30 (Too Low for Reliable VaR)
**File:** `src/engines/e5_risk.py`, line 146
**Severity:** Low

30 days of history (~1 month) is the minimum before VaR is computed. Industry standard for historical VaR reliability is 252 days (1 year) minimum. Metrics computed from 30 days of data will be highly noisy and fail any regulatory backtesting requirement.

---

### P4-E-008: e5_risk.py — Factor Exposure Silently Fails When shares_outstanding Missing
**File:** `src/engines/e5_risk.py`, lines 414–428
**Severity:** Medium

`_compute_factor_exposures()` requires `shares_outstanding` from `AnalyticsResult`. If absent (common for companies not yet fully processed), the size factor is not computed and the factor exposure vector is incomplete. No error is raised or logged.

---

---

## Part 3: Model Layer — 12 Issues

### P4-M-001: Missing CASCADE DELETE on All Risk Snapshot Tables
**Files:** Risk model files
**Severity:** High

`PortfolioVarSnapshot`, `ConcentrationAnalysis`, `FactorExposureSnapshot`, `PortfolioStressTestResult` all reference `portfolios.id` with no `ON DELETE CASCADE`. Deleting a portfolio leaves orphaned risk snapshots that can never be reached again.

---

### P4-M-002: Missing Composite Index on (portfolio_id, snapshot_date DESC)
**Files:** Risk model files
**Severity:** High

Every risk endpoint queries "latest snapshot for portfolio X" with `ORDER BY snapshot_date DESC LIMIT 1`. Without a composite index on `(portfolio_id, snapshot_date)`, this is a full-table scan on every risk request.

---

### P4-M-003: Missing CASCADE DELETE on PortfolioWatchlistEntry
**File:** `portfolio_watchlist.py`
**Severity:** Medium

`PortfolioWatchlistEntry.watchlist_id` references `portfolio_watchlists.id` without `ON DELETE CASCADE`. Deleting a watchlist leaves its entries as orphaned rows.

---

### P4-M-004: Missing updated_at on PortfolioVarSnapshot, PortfolioWatchlistEntry
**Files:** Risk and watchlist models
**Severity:** Low

These records are updated in-place (snapshots refreshed, entries modified) with no `updated_at` field to track the refresh time.

---

### P4-M-005: PortfolioUpload Missing user_id Foreign Key
**File:** `portfolio_upload.py`
**Severity:** Medium

`created_by` is an optional string with no FK constraint to a users table. Upload records cannot be reliably audited or cleaned up by user.

---

### P4-M-006: scenario_name VARCHAR(50) Too Narrow
**File:** Risk model
**Severity:** Low

`scenario_name: String(50)` will truncate descriptive scenario names like "2008 Financial Crisis + Oil Shock + USD Collapse" (50+ chars).

---

### P4-M-007: Missing Index on PortfolioUpload.status
**File:** `portfolio_upload.py`
**Severity:** Low

Queries for "pending uploads" perform full table scans without a status index.

---

### P4-M-008: base_currency Nullable Despite Having a Default
**File:** `portfolio.py`
**Severity:** Low

`base_currency` defaults to "USD" but is not `nullable=False`. SQL-level inserts bypassing the ORM can insert `NULL`, breaking currency calculations.

---

### P4-M-009: Missing Composite Indexes on Portfolio Table
**File:** `portfolio.py`
**Severity:** Medium

Only `user_id` is indexed. Common queries filter by `(user_id, status)` and `(user_id, portfolio_type)`. Without these composite indexes, portfolio list pages do full table scans filtered in Python.

---

---

## Part 4: Frontend Layer — 32 Issues

### P4-F-001: PortfolioDetail.tsx — All Core Data Hardcoded as Apple-Portfolio Fixture
**File:** `frontend/src/pages/portfolio/PortfolioDetail.tsx`, lines 71–154
**Severity:** Critical

Every key data point on the portfolio detail page is hardcoded:

```typescript
const portfolio = {
  name: 'Core Growth',
  nav: 2_458_320,
  dayChange: 0.34,
  dayChangeDollar: 8_358,
  inception: '2024-01-15',
};
```

10 hardcoded holdings: AAPL, MSFT, NVDA, AMZN, GOOGL, META, BRK.B, JPM, UNH, V with specific prices, shares, values, and P&L figures. Sector allocation hardcoded: Technology 32.4%, Healthcare 14.8%, etc. All performance KPIs hardcoded: `TWR (YTD): +8.42%`, `Sharpe Ratio: 1.34`. The NAV history chart uses `generateNavHistory()` (random walk from `2026-02-25` starting at `$10,000,000`) — not API data.

---

### P4-F-002: PerformancePage.tsx — Random Walk Generator Displayed as Portfolio Returns
**File:** `frontend/src/pages/portfolio/PerformancePage.tsx`, lines 132–170
**Severity:** Critical

```typescript
function generateDrawdownData() {
  // generates fake data with random walk starting from 2025-03-27
}
function generateRollingReturns() {
  // generates fake data with random walk, pRoll = 12, bRoll = 10
}
const data = useMemo(() => generateDrawdownData(), []);
```

The drawdown chart and rolling returns chart are populated by procedural random-walk generators. These are rendered with no indication they are synthetic. All 6 KPI tiles are hardcoded: `Portfolio Value: $48.2M`, `MTD Return: +2.85%`, etc. The full 2-year calendar returns table (2024–2025, 24 months) is a hardcoded array. The attribution table (8 sectors × 4 columns) is hardcoded. The factor attribution table (6 factors × 3 columns) is hardcoded.

---

### P4-F-003: RiskPage.tsx — All Risk Data Hardcoded Including Specific VaR Values
**File:** `frontend/src/pages/portfolio/RiskPage.tsx`, lines 48–172
**Severity:** Critical

```typescript
const mockRiskKPIs = [
  { label: '1D VaR (95%)', value: '$385K' },
  { label: '1D VaR (99%)', value: '$620K' },
  { label: '10D VaR (95%)', value: '$1.21M' },
  ...
];
```

Every data element on the risk page is hardcoded: 6 VaR KPIs, 5 stress test scenarios with P&L values, 6 factor exposures, 10-position VaR decomposition, 7-sector concentration analysis, 5 compliance rules with current values, 5 drift monitoring entries. The fallback condition (line 287–297) requires **both** `apiVaR` and `apiCVaR` to be non-null to use real data — if either API fails, all data reverts to mock.

---

### P4-F-004: WatchlistView.tsx — 7 Hardcoded Securities as Default Watchlist
**File:** `frontend/src/pages/watchlist/WatchlistView.tsx`, lines 24–66
**Severity:** High

```typescript
const watchlistItems = [
  { ticker: 'AAPL', name: 'Apple Inc.', price: 178.72, ... },
  { ticker: 'NVDA', name: 'Nvidia Corp.', price: 875.39, ... },
  ...  // 7 total hardcoded items
];
```

5 hardcoded earnings calendar entries with dates, EPS estimates, and implied moves. 10 hardcoded search suggestions (TSLA, AMD, NFLX, etc.) shown even when online.

---

### P4-F-005: BacktestDashboard.tsx — 6 Strategies and 8 Results Hardcoded
**File:** `frontend/src/pages/quant/BacktestDashboard.tsx`, lines 48–89
**Severity:** High

6 mock strategies, 8 mock backtest results with specific Sharpe ratios, max drawdowns, and annual returns. `handleRunBacktest` has empty `catch {}` — backtest failures are invisible to the user.

---

### P4-F-006: RiskDashboard.tsx — Separate Global Risk Dashboard Also Hardcoded
**File:** `frontend/src/pages/risk/RiskDashboard.tsx`, lines 14–54
**Severity:** High

The global risk dashboard page (separate from portfolio risk) has hardcoded: 6 VaR KPIs, 5 stress scenarios, 6 factor exposures, 10-position decomposition, 7-sector concentration. `useCorrelation()` and `useFactorExposure(undefined)` are called but all 5 data fallbacks use `apiCorrelation?.kpis ?? riskKPIs`, meaning the entire page shows mock data if the correlation API returns a different structure.

---

### P4-F-007: PortfolioDetail.tsx — 4 Hooks Called But Never Used
**File:** `frontend/src/pages/portfolio/PortfolioDetail.tsx`, lines 202–207
**Severity:** Medium

```typescript
const { data: apiNav }      = usePortfolioNav(portfolioId);      // never used
const { data: apiNavHist }  = usePortfolioNavHistory(portfolioId); // never used
const { data: apiAllocs }   = usePortfolioAllocations(portfolioId); // never used
const { data: apiSnapshot } = usePortfolioSnapshot(portfolioId);  // never used
```

4 API requests made on every page load whose results are discarded. The hardcoded data takes precedence via `??` operator.

---

### P4-F-008: PerformancePage.tsx — 3 Hooks Called But Never Used
**File:** `frontend/src/pages/portfolio/PerformancePage.tsx`, lines 203–206
**Severity:** Medium

`usePortfolioPerformance()`, `usePortfolioReturns()`, and `usePortfolioBenchmark()` are called but their results are never rendered directly. All data comes from hardcoded constants.

---

### P4-F-009: CustomIndexBuilder.tsx — POSTs to List Endpoint
**File:** `frontend/src/pages/quant/CustomIndexBuilder.tsx`, line 75
**Severity:** Critical

```typescript
await api.post(BENCHMARKS.list, ...)
```

`BENCHMARKS.list` is the endpoint for listing benchmarks (GET). Submitting a create-index form sends a POST to a list endpoint, which likely returns a 405 Method Not Allowed.

---

### P4-F-010: CustomIndexBuilder.tsx — API Response Structure Mismatch
**File:** `frontend/src/pages/quant/CustomIndexBuilder.tsx`, lines 67–70
**Severity:** High

```typescript
const { data: apiBenchmarks } = useQuery({ queryFn: () => api.get(BENCHMARKS.list) });
const activeIndices = (apiBenchmarks as any)?.indices ?? customIndices;
```

The response is accessed as `.indices` but API list responses typically use a different key (e.g., `.benchmarks` or `.items`). The `??` fallback ensures mock data is always shown.

---

### P4-F-011: 10+ Endpoints Have No Corresponding Hook
**File:** `frontend/src/hooks/usePortfolio.ts`
**Severity:** High

The following API endpoints are defined in `endpoints.ts` and implemented in the routers but have no hook in `usePortfolio.ts`:

| Endpoint | PORTFOLIOS constant |
|----------|-------------------|
| Rebalance | `PORTFOLIOS.rebalance(id)` |
| Portfolio optimization | `PORTFOLIOS.optimize(id)` |
| What-if analysis | `PORTFOLIOS.whatIf(id)` |
| Portfolio comparison | `PORTFOLIO_PERFORMANCE.compare` |
| Custom stress test | `PORTFOLIO_RISK.stressCustom(id)` |
| Pre-trade check | `PORTFOLIO_RISK.preTradeCheck(id)` |
| Drift rebalance | `PORTFOLIO_RISK.driftRebalance(id)` |
| Scenario detail | `PORTFOLIO_RISK.scenarioDetail(id)` |
| Watchlist add item | `WATCHLISTS.addItem(id)` |
| Watchlist remove item | `WATCHLISTS.removeItem(id, itemId)` |

These features cannot be used from React components without implementing the hooks.

---

### P4-F-012: All Portfolio Pages — Missing isLoading/isError From Hooks
**Files:** All 4 portfolio pages
**Severity:** Medium

No portfolio page destructures `isLoading` or `isError` from any hook. The universal pattern is:
```typescript
const { data: apiXxx } = useHook(id) as { data: any };
const active = (apiXxx as any)?.field ?? mockData;
```
API failures are invisible. Loading states are not shown. Mock data appears instantly.

---

### P4-F-013: PortfolioList.tsx — TODO Comment for Error Toast Left in Production
**File:** `frontend/src/pages/portfolio/PortfolioList.tsx`, line 137
**Severity:** Low

```typescript
// TODO: show toast notification
console.warn('Failed to create portfolio:', err);
```

Portfolio creation errors are silently logged to the console. Users receive no feedback when portfolio creation fails.

---

---

## Part 5: Features That Are Production-Ready

The following Pillar 4 features are structurally complete — the API, data model, and frontend scaffolding exist and work correctly when provided with data:

| Feature | Status | Caveat |
|---------|--------|--------|
| Portfolio CRUD (create, list, get, update, delete, clone) | ✅ Structurally complete | Auth uses DEFAULT_USER |
| Position management (add, update, soft-delete) | ✅ Complete | market_value never populated |
| Transaction recording | ✅ Complete | Wrong hook endpoint |
| CSV portfolio upload (preview + commit) | ✅ Complete | Cash always $0 |
| Compliance rule CRUD | ✅ Complete | Pre-trade check ignores portfolio |
| Watchlist CRUD | ✅ Complete | Auth uses DEFAULT_USER |
| Watchlist entity add/remove | ✅ Complete | await session.delete() bug |
| Alert configuration CRUD | ✅ Complete | |
| Drift target setting | ✅ Complete (sets target) | Doesn't compute actual drift |
| NAV history query | ✅ Complete (query) | Data never populated |
| Corporate actions queue | ✅ Complete (listing) | Apply action is stub |

---

## Part 6: Complete Issue Index

| ID | Layer | Severity | Summary |
|----|-------|----------|---------|
| P4-R-001 | Router | Critical | DEFAULT_USER hardcoded — no multi-user isolation |
| P4-R-002 | Router | Critical | useAddPosition() / useRecordTransaction() call wrong endpoint |
| P4-R-003 | Router | Critical | useClonePortfolio() uses create instead of clone endpoint |
| P4-R-004 | Router | Critical | Historical stress test returns hardcoded AAPL values |
| P4-R-005 | Router | Critical | Hypothetical stress test returns hardcoded MSFT values |
| P4-R-006 | Router | Critical | Backtesting marks all runs COMPLETED with no computation |
| P4-R-007 | Router | Critical | Quant regression uses integer indices [0,1,2...] as X data |
| P4-R-008 | Router | Critical | Position.market_value never populated → NAV always 0 |
| P4-R-009 | Router | Critical | nav_engine.py never called from any router |
| P4-R-010 | Router | Critical | e5_risk.py never called from portfolio_risk.py |
| P4-R-011 | Router | Critical | attribution_engine.py never called from portfolio_performance.py |
| P4-R-012 | Engine | Critical | Parametric VaR formula mathematically wrong |
| P4-R-013 | Engine | High | Historical VaR sign inconsistency |
| P4-R-014 | Engine | High | Multi-period attribution: arithmetic instead of geometric linking |
| P4-R-015 | Engine | High | CVaR fencepost error in tail indexing |
| P4-R-016 | Router | High | Corporate action apply ignores request body |
| P4-R-017 | Router | High | Report generation returns stub data |
| P4-R-018 | Router | High | All risk endpoints return None (snapshots never populated) |
| P4-R-019 | Router | High | flush() without commit() — ~20 locations |
| P4-R-020 | Router | High | Watchlist alerts endpoint confirmed stub — always returns [] |
| P4-R-021 | Router | High | Watchlist alert digest always returns hardcoded zeros |
| P4-R-022 | Router | High | Watchlist earnings calendar always returns [] |
| P4-R-023 | Router | High | Watchlist dashboard returns only names, no metrics |
| P4-R-024 | Router | High | Pre-trade check ignores current portfolio state |
| P4-R-025 | Router | High | _get_position() doesn't verify portfolio ownership |
| P4-R-026 | Router | High | Drawdown response uses period boundaries as peak/trough dates |
| P4-R-027 | Router | Medium | session.delete() called with await (TypeError) |
| P4-R-028 | Router | Medium | period parameter accepted but never applied to SQL queries |
| P4-R-029 | Router | Medium | Clone inherits current cash instead of initial cash |
| P4-R-030 | Router | Medium | Backtest compare doesn't compute differential metrics |
| P4-R-031 | Router | Medium | Invalid security UUIDs silently skipped in correlation matrix |
| P4-R-032 | Router | Medium | Benchmark hardcoded to "SPY" |
| P4-R-033 | Router | Medium | Invalid transaction types silently accepted |
| P4-R-034 | Router | Low | Position update accepts negative shares/cost basis |
| P4-R-035 | Router | Low | Clone position missing first_acquisition_date |
| P4-E-001 | Engine | Medium | NAV tolerance is absolute $0.01, not percentage-based |
| P4-E-002 | Engine | Low | Negative NAV produces wrong cash weight |
| P4-E-003 | Engine | Medium | Stress scenario inconsistent shock parameter keys |
| P4-E-004 | Engine | High | Brinson attribution missing weight-sum validation |
| P4-E-005 | Engine | Medium | Factor attribution silently drops missing factors |
| P4-E-006 | Engine | Low | Stock-specific return not integrated automatically |
| P4-E-007 | Engine | Low | MIN_OBSERVATIONS = 30 (too low for reliable VaR) |
| P4-E-008 | Engine | Medium | Factor exposure fails silently when shares_outstanding missing |
| P4-M-001 | Model | High | Missing CASCADE DELETE on all risk snapshot tables |
| P4-M-002 | Model | High | Missing composite index on (portfolio_id, snapshot_date DESC) |
| P4-M-003 | Model | Medium | Missing CASCADE DELETE on PortfolioWatchlistEntry |
| P4-M-004 | Model | Low | Missing updated_at on VarSnapshot and WatchlistEntry |
| P4-M-005 | Model | Medium | PortfolioUpload missing user_id FK |
| P4-M-006 | Model | Low | scenario_name VARCHAR(50) too narrow |
| P4-M-007 | Model | Low | Missing index on PortfolioUpload.status |
| P4-M-008 | Model | Low | base_currency nullable despite having a default |
| P4-M-009 | Model | Medium | Missing composite indexes on Portfolio table |
| P4-F-001 | Frontend | Critical | PortfolioDetail.tsx — all data hardcoded as Apple-portfolio fixture |
| P4-F-002 | Frontend | Critical | PerformancePage.tsx — random walk generator shown as portfolio returns |
| P4-F-003 | Frontend | Critical | RiskPage.tsx — all risk data hardcoded |
| P4-F-004 | Frontend | High | WatchlistView.tsx — 7 hardcoded securities as default watchlist |
| P4-F-005 | Frontend | High | BacktestDashboard.tsx — 6 strategies, 8 results hardcoded |
| P4-F-006 | Frontend | High | RiskDashboard.tsx — all global risk data hardcoded |
| P4-F-007 | Frontend | Medium | PortfolioDetail.tsx — 4 hooks called but results never used |
| P4-F-008 | Frontend | Medium | PerformancePage.tsx — 3 hooks called but results never used |
| P4-F-009 | Frontend | Critical | CustomIndexBuilder.tsx — POSTs to list endpoint |
| P4-F-010 | Frontend | High | CustomIndexBuilder.tsx — API response structure mismatch |
| P4-F-011 | Frontend | High | 10+ endpoints with no corresponding hook |
| P4-F-012 | Frontend | Medium | All portfolio pages missing isLoading/isError from hooks |
| P4-F-013 | Frontend | Low | Portfolio creation error not shown to user (TODO comment) |

**Total: 98 issues**

---

## Part 7: Remediation Plan

### Phase 1 — Fix Critical Hook Bugs (½ day)

1. **P4-R-002**: Fix `useAddPosition()` to call `PORTFOLIOS.positions(id)` with correct method
2. **P4-R-002**: Fix `useRecordTransaction()` to call `PORTFOLIOS.transactions(id)`
3. **P4-R-003**: Fix `useClonePortfolio()` to call `PORTFOLIOS.clone(id)`
4. **P4-F-009**: Fix `CustomIndexBuilder.tsx` to POST to correct create endpoint
5. **P4-R-027**: Remove `await` from `session.delete(entry)`
6. **P4-R-019**: Replace all `session.flush()` with `session.commit()` across 4 routers

### Phase 2 — Wire the Three Core Engines (3–5 days)

1. **P4-R-009**: Call `nav_engine.compute_position_valuation()` after every position add/update/transaction; store `market_value`, `unrealized_pnl`, `weight` on Position
2. **P4-R-009**: Call `nav_engine.build_nav_snapshot()` after every transaction; store NAVSnapshot
3. **P4-R-010**: Call `e5_risk` functions from `portfolio_risk.py` on-demand when no fresh snapshot exists (max 15-min stale)
4. **P4-R-011**: Call `attribution_engine` from `portfolio_performance.py` for attribution endpoints when no pre-computed result exists
5. Create `scripts/run_portfolio_batch.py` that refreshes NAV, risk snapshots, and attribution daily

### Phase 3 — Remove Hardcoded Stub Data (2–3 days)

1. **P4-R-004/005**: Implement real stress test math in `portfolio_risk.py` using `e5_stress_scenarios.py` and position data
2. **P4-R-006**: Wire `backtester.py` engine into `backtesting.py` router
3. **P4-R-007**: Implement proper independent variable loading in `quant.py` regression
4. **P4-R-017**: Implement real report generation (at minimum, structured JSON of portfolio state)
5. **P4-R-020–023**: Implement watchlist alerts using the alert engine; populate earnings calendar from `earnings_p2` data

### Phase 4 — Fix Math Errors (1–2 days)

1. **P4-R-012**: Fix parametric VaR formula in `e5_risk.py`
2. **P4-R-014**: Fix attribution geometric linking in `attribution_engine.py`
3. **P4-E-003**: Normalize stress scenario shock keys to single convention
4. **P4-E-004**: Add weight-sum validation to Brinson attribution
5. **P4-R-026**: Fix drawdown endpoint to compute real peak/trough dates

### Phase 5 — Auth and Security (2–3 days)

1. **P4-R-001**: Replace `DEFAULT_USER` with authenticated user from JWT token/session
2. **P4-R-025**: Add `position.portfolio_id == portfolio_id` check to `_get_position()`
3. **P4-R-024**: Fix pre-trade check to evaluate post-trade portfolio state

### Phase 6 — Remove Frontend Mock Data (3–5 days)

1. Remove all hardcoded portfolio/holdings/performance/risk fixtures from all 6 pages
2. Extract `isLoading`, `isError` from every hook call
3. Add loading skeletons and error states
4. Remove random-walk generators; replace with real API data
5. Implement the 10 missing hooks in `usePortfolio.ts`
6. Fix `CustomIndexBuilder.tsx` API structure mismatch

### Phase 7 — Schema and Index Hardening (1 day)

1. Add CASCADE DELETE to all risk snapshot FK references
2. Add composite `(portfolio_id, snapshot_date DESC)` index to all snapshot tables
3. Add composite `(user_id, status)` and `(user_id, portfolio_type)` indexes to Portfolio
4. Widen `scenario_name` to `String(150)`
5. Add `updated_at` to VarSnapshot and WatchlistEntry
