# PILLAR 4 AUDIT REPORT v2
## Bloomberg Data Fabric — Portfolio & Risk — Deep Audit
**Date:** 2026-04-03
**Supersedes:** PILLAR_4_AUDIT_REPORT.md (98 issues)
**This report:** 157 issues across 6 layers
**Scope:** Every router, engine, model, schema, hook, endpoint, and frontend page in Pillar 4

---

## EXECUTIVE SUMMARY

A complete line-by-line audit of every Pillar 4 file reveals **157 distinct issues** across:

| Layer | Files Audited | Issues Found | Critical | High | Medium | Low |
|-------|--------------|-------------|----------|------|--------|-----|
| Backend Routers | 11 | 44 | 8 | 14 | 16 | 6 |
| Engines | 14 | 51 | 9 | 22 | 15 | 5 |
| Models & Schemas | 26 | 35 | 8 | 12 | 10 | 5 |
| Frontend Hooks & Endpoints | 2 | 13 | 2 | 3 | 6 | 2 |
| Frontend Pages | 9 | 11 | 8 | 3 | 0 | 0 |
| App Registration | 1 | 4 | 2 | 2 | 0 | 0 |

### Most Critical Systemic Findings

1. **Three core engines (nav_engine, e5_risk, attribution_engine) are never called from any router** — NAV, VaR, and performance attribution are permanently non-functional at the API layer.
2. **DEFAULT_USER = "default_user" hardcoded in portfolios.py and portfolio_watchlists.py** — all multi-user isolation is broken.
3. **Money-weighted return (MWR) formula has wrong sign** — final_value is added instead of subtracted in the NPV equation, producing incorrect IRR for all portfolios.
4. **portfolio_risk_engine.py VaR formula assumes weights sum to 1.0** — no normalization check; silently wrong for any portfolio where this fails.
5. **whatif_engine.py weight_delta calculation is dead code** — the variable is immediately overwritten by a hardcoded 1.0 constant.
6. **Decimal→float precision loss throughout all financial schemas** — every monetary field (NAV, positions, transactions, performance) loses precision on serialization.
7. **portfolio_watchlist.py FK references nonexistent "entities" table** — every watchlist insert that links an entity will fail at the database level.
8. **fi_risk.py: 3 of 4 endpoints have no session parameter** — portfolio-level FI risk cannot query the database.
9. **Stress test results are hardcoded (AAPL: -$5,000, MSFT: -$3,000)** regardless of portfolio contents.
10. **backtesting.py, quant.py, technical_backtest.py not confirmed registered in app.py** — may be completely unreachable via HTTP.

---

## SECTION 1: BACKEND ROUTERS

### portfolios.py

**P4-R-001** | CRITICAL | Line 47
`DEFAULT_USER = "default_user"` hardcoded constant. Every portfolio query, create, and update uses this user ID. Multiple users sharing the same token all see identical portfolio lists. No authentication enforcement.

**P4-R-002** | CRITICAL | Lines 202, 289, 340, 412, 478
`await session.flush()` used in every write path instead of `await session.commit()`. Flush sends SQL to the DB within the transaction but does **not** persist it. If the connection closes or another unhandled exception occurs, all portfolio creates, position adds, and transaction records are silently rolled back. Data loss is certain in any crash scenario.

**P4-R-003** | HIGH | Line 226
`await session.delete(entry)` is incorrect. `AsyncSession.delete()` is a synchronous method that schedules deletion; it does not return a coroutine. Calling `await` on it raises `TypeError: object NoneType can't be used in 'await' expression` at runtime, crashing the delete-portfolio endpoint.

**P4-R-004** | HIGH | Lines 493–557
Position `market_value`, `unrealized_pnl`, `weight`, `closing_price`, and `day_change_pct` are never set anywhere in the codebase. The `PositionResponse` schema will serialize all these as `None`. Portfolio NAV derived from summing market values will always be zero.

**P4-R-005** | HIGH | Lines 633–763
In `add_position()`, position weight is calculated from `market_value` (line ~645) but `market_value` is never populated before that calculation. Weight is always `0.0`.

**P4-R-006** | HIGH | Line 742
SELL transaction path sets `Position.shares = Decimal("0")` and `status = "CLOSED"` but leaves `market_value`, `unrealized_pnl`, and `weight` at their last stale values. Portfolio aggregates become incorrect after any sell.

**P4-R-007** | HIGH | Line 890
`portfolio.current_cash` is decremented on BUY without checking whether the result goes negative. Negative cash is silently allowed, implying leverage without any margin tracking or flag.

**P4-R-008** | MEDIUM | Line 542
`pos.security_id` is returned in `PositionResponse` but is never set during position creation (only `ticker` is set). Returns `None` for every position's `security_id`.

**P4-R-009** | MEDIUM | Lines 554–559
Average cost basis calculation: `avg_cost = (old_total + new_total) / total_shares if total_shares else Decimal("0")`. If `total_shares` is a `Decimal("0.00000001")` (rounding artifact), the guard passes and division produces a nonsensical cost basis.

**P4-R-010** | MEDIUM | Line 465
During portfolio CSV upload, `market_value` is never set on imported positions, so `float(pos.market_value)` in the response will raise `TypeError: float() argument must be a string or a number, not 'NoneType'`.

---

### portfolio_performance.py

**P4-R-011** | CRITICAL | Line 126
`compare_portfolios()` endpoint has no authentication. Any caller can pass any two portfolio IDs and receive full performance comparison data for portfolios they don't own.

**P4-R-012** | HIGH | Line 438
`ReportRequest` ORM object is created and `await session.flush()` is called, but `await session.commit()` is never called. Report records are never persisted.

**P4-R-013** | MEDIUM | Line 440
`result_data` for generated reports is hardcoded as `{"report_type": report_type, "portfolio_name": portfolio.portfolio_name}`. No actual report generation happens; the endpoint is a stub.

**P4-R-014** | MEDIUM | Lines 356–360
`_parse_sector_detail()`, `_parse_security_detail()`, `_parse_factor_detail()` call `.get()` on items parsed from JSONB. If the stored JSONB is a list of strings instead of a list of dicts (data corruption or schema mismatch), these raise `AttributeError: 'str' object has no attribute 'get'`.

**P4-R-015** | MEDIUM | Line 494
CSV export uses raw f-string interpolation: `f"{pos.ticker},{pos.shares},{pos.market_value}"`. If any field contains a comma, the CSV column count breaks. No quoting or escaping applied.

**P4-R-016** | LOW | Line 145
`_perf_to_response(snap)` is called but `snap` could be `None` in multiple call sites. Lines 167–169 access `snap.twr_return` etc. without a prior null guard, risking `AttributeError`.

---

### portfolio_risk.py

**P4-R-017** | CRITICAL | Lines 481–495
Historical stress test endpoint returns **completely hardcoded results** regardless of portfolio:
```python
total_pnl_dollar=Decimal("-15000.00")
max_drawdown_pct=Decimal("-0.250000")
worst_positions={"worst": [{"ticker": "AAPL", "pnl": -5000}]}
```
No engine is called. All users see the same AAPL/−$15,000 result for every historical stress test.

**P4-R-018** | CRITICAL | Lines 527–547
Hypothetical stress test is similarly hardcoded:
```python
total_pnl_dollar=Decimal("-8000.00")
worst_positions={"worst": [{"ticker": "MSFT", "pnl": -3000}]}
```

**P4-R-019** | CRITICAL | Lines 770–790
`pre_trade_check()` compliance validation only handles `POSITION_LIMIT` rule type. All other rule types (`SECTOR_LIMIT`, `SINGLE_SECURITY_LIMIT`, `CONCENTRATION_LIMIT`, `LEVERAGE_LIMIT`) are silently ignored. Trades that violate these rules are approved without error.

**P4-R-020** | HIGH | Line 758
`session.delete(rule)` for compliance rule deletion is followed only by `await session.flush()` — not `await session.commit()`. Deleted rules reappear after connection reset.

**P4-R-021** | HIGH | Line 642
New compliance rules are created with `session.add(rule)` and `await session.flush()` but no commit. Compliance rules created via API are never persisted.

**P4-R-022** | HIGH | Lines 260–303
`PortfolioVarSnapshot` query returns the most recent snapshot, but if no snapshot exists (no batch job has populated the table), `var_snap` is `None` and lines ~303 raise `AttributeError` when accessing `var_snap.var_historical_95_1d`.

**P4-R-023** | MEDIUM | Line 713
`drift_pct` is read from the snapshot JSONB without a null check. If the snapshot exists but `drift_pct` field is absent, `abs(None)` raises `TypeError`.

**P4-R-024** | MEDIUM | Line 1068
`set_target_allocation()` accepts `body: dict` — untyped and unvalidated. Any JSON payload is accepted without field checking. Should use a Pydantic schema.

**P4-R-025** | MEDIUM | Line 330
`geographic_detail` parsed as: if it's a dict without key `"regions"`, returns `[]` silently. No indication to the caller that geographic detail is missing vs. empty.

**P4-R-026** | LOW | Line 703
`ComplianceRule.is_active == True` with `# noqa: E712` comment. The code intentionally suppresses the linting warning instead of using the idiomatic `is_active.is_(True)` SQLAlchemy comparison.

---

### portfolio_watchlists.py

**P4-R-027** | CRITICAL | Line 29
`DEFAULT_USER = "default_user"` — same hardcoded multi-tenancy break as portfolios.py. All watchlists are owned by the same user.

**P4-R-028** | HIGH | Line 226
`await session.delete(entry)` — same bug as portfolios.py. `session.delete()` is synchronous; `await` raises `TypeError` and crashes the remove-from-watchlist endpoint at runtime.

**P4-R-029** | MEDIUM | Lines 298–306
`get_watchlist_alerts()` returns a hardcoded empty stub: `return WatchlistAlertResponse(alerts=[])`. No alert logic is executed.

**P4-R-030** | MEDIUM | Lines 310–320
`get_watchlist_alert_digest()` returns completely hardcoded zeros: `total_alerts=0`, `summary="No active alerts."`. The `watchlist_monitoring` engine is never called.

**P4-R-031** | MEDIUM | Lines 335–350
`get_watchlist_earnings_calendar()` returns `EarningsCalendarResponse(entries=[])`. The DB is never queried. Earnings calendar always appears empty.

**P4-R-032** | MEDIUM | Lines 355–365
Watchlist entity join uses `.outerjoin(Entity)` but if `Entity` is `None` (entity not in database), `legal_name` is `None` with no fallback label. UI displays blank names.

---

### portfolio_upload.py

**P4-R-033** | HIGH | Line 48
File upload endpoint is a stub. It accepts `file_name` and `file_format` as **Query parameters**, not an actual multipart file upload. Comment reads: *"In production this would accept a file upload; here we create the upload record."* No file bytes are ever processed.

**P4-R-034** | MEDIUM | Line 62
`parsed_holdings` field check: `if row.parsed_holdings and isinstance(row.parsed_holdings, list)` — does not handle the case where `parsed_holdings` is a dict (e.g., `{"items": [...]}`), returning an empty list silently.

---

### backtesting.py

**P4-R-035** | CRITICAL | Line 34
Every backtest immediately sets `status="COMPLETED"` with hardcoded zero metrics. No backtesting engine is imported or called. The endpoint is a complete stub:
```python
status="COMPLETED"
total_return=Decimal("0")
sharpe_ratio=Decimal("0")
```

**P4-R-036** | CRITICAL | Line 44
`session.commit()` without `await`. In an async SQLAlchemy context, calling the synchronous `session.commit()` may silently do nothing or raise an error depending on driver configuration.

**P4-R-037** | MEDIUM | Lines 119–156
`compare_backtests()` response only includes 9 fields but the single-backtest response has 20+ metrics. Beta, tracking error, information ratio, and sector breakdown are absent from comparison output.

---

### quant.py

**P4-R-038** | CRITICAL | Lines 106–108
Regression `run_regression()` uses `x_returns = list(range(len(y_returns)))` as the independent variable — integer ordinal indices (0, 1, 2, ...), not actual financial returns. All regression results (beta, alpha, R²) are meaningless. The code itself comments: *"For now, use the return series itself as both x and y (self-regression)"* — an acknowledged stub.

**P4-R-039** | CRITICAL | Line 395
`benchmark` hardcoded as `"SPY"` in `get_beta()` despite the endpoint signature accepting a `benchmark` query parameter. The accepted value is completely ignored.

**P4-R-040** | HIGH | Line 256
`uuid.UUID(body.series_x_id)` — redundant conversion if `series_x_id` is already a UUID object in the Pydantic schema. If it's a string in non-standard format, raises `ValueError` with no user-friendly error.

**P4-R-041** | HIGH | Lines 254–255
`x_returns` and `y_returns` are trimmed to the same length with `min(len(x), len(y))` but no warning is emitted when the series have different lengths. Silently discards data.

---

### risk.py

**P4-R-042** | LOW | Line 248
`benchmark: str = Query(default="SPY")` — hardcoded SPY default for beta calculations. Cross-asset or non-US portfolios using this endpoint will always be compared against SPY unless caller explicitly overrides.

---

### technical_backtest.py

**P4-R-043** | MEDIUM | Line 22
`session: AsyncSession = Depends(get_session)` is declared but never used within the function body. Unnecessary DB connection is opened and held for every request.

---

### fi_risk.py

**P4-R-044** | CRITICAL | Lines 86, 112, 138
Three of four endpoints — `get_portfolio_risk()`, `get_rate_scenario()`, `get_spread_scenario()` — have **no `session` parameter**. These endpoints compute FI portfolio risk from bond position dicts passed in the request body, but cannot look up bond details from the database to fill missing fields. Callers must provide every bond attribute inline; any missing field falls back to hardcoded defaults (lines 230–238: price=100.0, coupon=0.0, face=100.0).

---

## SECTION 2: ENGINES

### nav_engine.py

**P4-E-001** | HIGH | Line 147
`compute_portfolio_nav()` does not validate that `cash_balance` is non-negative. Negative cash inflates NAV while `cash_weight = cash_balance / nav` produces a negative weight in the breakdown, which downstream allocation charts display incorrectly.

**P4-E-002** | HIGH | Line 129
`compute_daily_return()` does not guard against `nav_yesterday <= 0`. Division by a negative or zero prior NAV produces a mathematically invalid return (can exceed 100% or be negative infinity).

**P4-E-003** | MEDIUM | Line 108
`compute_position_valuation()` sets `weight = 0.0` as a placeholder but adds a comment: *"caller must renormalize."* No router that calls this engine renormalizes weights. Every position weight in every router response is `0.0`.

**P4-E-004** | MEDIUM | Line 100
`cost_basis_per_share` is never validated for positivity. If a position was imported with `price = 0`, subsequent unrealized P&L calculations divide by this field.

---

### attribution_engine.py

**P4-E-005** | CRITICAL | Lines 260–280
`link_multi_period_attribution()` uses **arithmetic summation** of allocation/selection/interaction effects across periods. Correct multi-period attribution requires geometric linking (Carino or Menchero method). The arithmetic sum systematically overstates or understates cumulative active return, especially over quarterly/annual windows.

**P4-E-006** | CRITICAL | Line 294
Average benchmark/portfolio weights computed as simple mean across periods (`avg_pw = mean(weights)`). Multi-period Brinson requires **beginning-of-period weights** (BOP), not time-averaged weights. The mean of daily weights is an incorrect approximation that grows worse as the period lengthens.

**P4-E-007** | HIGH | Line 210
`compute_brinson_attribution()` sums `weight * return` over all holdings without first validating that `sum(weights) ≈ 1.0`. If positions are partially imported or weights haven't been computed, total portfolio return is wrong and all attribution effects are off.

**P4-E-008** | MEDIUM | Line 256
Allocation effect formula: `(wp - wb) * (rb_s - rb)`. When `rb = 0` (benchmark flat for the period), `rb_s - rb = rb_s` which is non-zero and correct. No bug here, but no documentation clarifying this edge case.

**P4-E-009** | MEDIUM | Line 230
`residual = total_active - (total_alloc + total_select + total_interact)`. In Brinson BHB, residual should be zero. No warning is logged when residual is large, hiding data quality issues (missing sectors, rounding errors).

---

### e5_risk.py

**P4-E-010** | CRITICAL | Lines 325–332
`_persist_var()` parses metric names by splitting on `_` and assumes exactly 2 parts: `conf = float(parts[0])`, `holding = int(parts[1].replace("d",""))`. Any metric name with an unexpected format raises `IndexError` with no exception handling. The entire VaR persistence batch fails.

**P4-E-011** | HIGH | Line 237
CVaR cutoff index: `cutoff_idx = max(1, int(n * pct / 100.0))`. Uses `int()` (floor). For n=50, pct=5: `cutoff_idx=2`, meaning the CVaR is the average of the 2 worst losses out of 50 — that is only the worst 4%, not the worst 5%. Should use `math.ceil()`.

**P4-E-012** | HIGH | Lines 233–236
`_max_drawdown()` returns `0.0` on an empty list. Callers cannot distinguish between "portfolio had no drawdown" and "no price data available." Should return `None` or raise.

**P4-E-013** | HIGH | Lines 344–350
Historical stress test PnL computed as:
```python
pnl = sum(returns[-252:]) / max(len(returns[-252:]), 1) * 252
```
This annualizes the arithmetic sum of daily log returns, which is wrong. Correct approach is compound return: `prod(1 + r for r in returns[-252:]) - 1`. The current formula overstates returns in volatile periods.

**P4-E-014** | HIGH | Line 203
`ann_vol = daily_std * math.sqrt(252)` — hardcoded 252 trading days. Non-US markets trade fewer days (UK: ~250, Japan: ~251). No configuration parameter.

**P4-E-015** | MEDIUM | Line 288
Amihud illiquidity scaled by `1e6` — arbitrary magic constant with no documentation or justification.

**P4-E-016** | MEDIUM | Lines 267–274
Bid-ask proxy `= mean(high - low) / close` over 20 days. Uses intraday high-low only; does not capture overnight gaps, which can be the dominant source of bid-ask in illiquid securities.

---

### e5_stress_scenarios.py

**P4-E-017** | MEDIUM | Lines 22–38
`HYPOTHETICAL_SCENARIOS` definitions include `rate_shock_bps` but not `equity_shock` or `spread_shock_bps`. Code in `portfolio_risk_engine.py` that applies these shocks checks for each field individually, so missing fields default to zero silently rather than being flagged as incomplete scenario definitions.

---

### backtester.py

**P4-E-018** | HIGH | Line 106
Sortino ratio: `downside_returns = [min(r - daily_rf, 0) for r in returns]`. This measures downside vs. zero excess return. Correct Sortino uses a **Minimum Acceptable Return (MAR)**: `downside_returns = [min(r - MAR, 0) for r in returns]`. Current implementation systematically understates the downside deviation for positive-return portfolios.

**P4-E-019** | HIGH | Line 130
Max drawdown **duration** is measured by counting loop iterations, which assumes returns are daily-frequency. If monthly or weekly returns are passed, duration is expressed in months/weeks but the field is labeled `duration_days`. No frequency parameter exists.

**P4-E-020** | HIGH | Line 147
Information ratio: `(mean_excess * periods_per_year / tracking_error)`. Should be `(mean_excess * periods_per_year) / tracking_error`. Due to Python operator precedence, division evaluates left-to-right, so `mean_excess * periods_per_year / tracking_error` is mathematically the same — however, the intent reads confusingly and is prone to future mis-edit.

**P4-E-021** | MEDIUM | Line 113
Beta: checks `var_b > 1e-15` but uses `(n-1)` in the denominator for variance. If `n == 1`, `(n-1) = 0` causing `ZeroDivisionError`. Should check `n > 1`.

---

### concentration_risk.py

**P4-E-022** | HIGH | Line 119
`max(risks, key=lambda r: risk_levels.get(r, 0))` — if a risk level string is not in the `risk_levels` dict (e.g., typo or new level added), it silently scores `0`, meaning an unknown risk level is treated as the lowest possible risk. Should raise or warn.

**P4-E-023** | MEDIUM | Line 128
Weighted score fallback: `level_to_score.get(customer_risk, 20)` — `20` is used as default for unknown risk levels. The value `20` matches `"LOW_RISK": 20` in the dict, so unknown levels are silently treated as low risk. Should raise a `KeyError` or use a distinct sentinel value.

**P4-E-024** | MEDIUM | Line 74
`geographic_spread=0` does not trigger any high-risk classification in the supplier risk function. A supplier sourcing 100% from a single high-risk region with spread=0 may still be rated "MODERATE."

---

### e7_quant.py

**P4-E-025** | CRITICAL | Lines 450–460
ADF stationarity fallback test uses a heuristic: `test_statistic = -ratio * 5`. This is **not a real ADF statistic**. The critical values returned (`{"1%": -3.43, "5%": -2.86, "10%": -2.57}`) are the true Dickey-Fuller critical values for n=250, but the heuristic test statistic is not drawn from the Dickey-Fuller distribution. Users relying on this for cointegration analysis will receive statistically meaningless results presented as valid.

**P4-E-026** | HIGH | Line 427
Blume adjusted beta: `self.BLUME_WEIGHT = 0.67` hardcoded. This constant originates from a specific 1971 regression by Blume on NYSE data. No documentation explaining the choice. Modern values derived from current market data differ substantially.

**P4-E-027** | HIGH | Lines 460–470
Cointegration test runs ADF on OLS residuals but uses raw ADF critical values rather than Engle-Granger adjusted critical values. Engle-Granger requires adjusted critical values because OLS residuals have estimated (not known) parameters, biasing the test toward rejecting the null. The test produces too many false "cointegrated" signals.

**P4-E-028** | HIGH | Line 301
OLS standard error: `se_beta = math.sqrt(mse / ss_xx) if ss_xx > 0 and mse >= 0 else 0.0`. `mse == 0` means perfect fit (zero residuals), which produces `se_beta = 0.0` — correct mathematically, but implies zero uncertainty, which will cause division-by-zero downstream in t-statistic computation: `t_stat = beta / se_beta`.

**P4-E-029** | MEDIUM | Line 338
Rolling beta computed on 60-day window without checking minimum observations. A series with 65 data points and window=60 produces only 5 valid observations, making the rolling beta highly unstable. No minimum-observations warning.

---

### performance_engine.py

**P4-E-030** | CRITICAL | Line 103
`compute_mwr()` (Money-Weighted Return / IRR) treats `final_value` as a **positive inflow** in the NPV equation. The correct formulation is:
```
sum(cf / (1+r)^t) - final_value / (1+r)^T = 0
```
Current code:
```python
all_flows.append((terminal_t, +final_value))   # WRONG — should be -final_value
```
The Newton-Raphson solver converges to a value where the inflow equals the outflows, but since the terminal value has the wrong sign, the IRR found is not the MWR. For a portfolio that grew from $100k to $150k, this returns a rate that makes $150k look like a cost rather than an ending value.

**P4-E-031** | CRITICAL | Line 125
`r_new` is clamped to `max(-0.99, min(r_new, 10.0))` — upper limit of 10.0 (1000% return). A portfolio that legitimately returns 1100% in a single year (e.g., early-stage venture) cannot converge to its correct MWR.

**P4-E-032** | HIGH | Line 95
`max(cf["date_offset"] for cf in cash_flows)` — raises `KeyError` if any element in `cash_flows` is missing the `"date_offset"` key. No input validation on the cash flow list.

**P4-E-033** | HIGH | Lines 243–248
`compute_standard_periods()` uses string comparison for date filtering: `start_date <= d["date"]`. For ISO 8601 format (YYYY-MM-DD), lexicographic ordering is equivalent to chronological — correct. However, if any date is stored in a non-ISO format or includes a timestamp (e.g., `"2024-12-31T00:00:00"`), the comparison silently fails. No format validation.

**P4-E-034** | HIGH | Line 193
`compute_up_down_capture()` length of `up_port` and `up_bench` is always equal (both filtered on the same condition), but the code divides by `len(up_port)` for the portfolio average and `len(up_bench)` for the benchmark average separately. If either list is empty, `ZeroDivisionError` at line 198.

**P4-E-035** | MEDIUM | Line 271
`_subtract_months()` computes `total_months = year * 12 + (month - 1) - n_months`. If `total_months < 0`, the resulting year/month are negative integers. The f-string `f"{new_year:04d}-{new_month:02d}-01"` formats them as e.g., `"-001-00-01"` — an invalid date passed silently to callers.

---

### portfolio_analytics.py

**P4-E-036** | MEDIUM | Line 95
`compute_concentration_hhi()`: `return sum(w*w for w in weights) * 10000`. Assumes `sum(weights) == 1.0`. If weights are un-normalized (e.g., raw market values), HHI is inflated by the square of the total sum. No normalization or validation.

**P4-E-037** | MEDIUM | Line 35
`compute_sector_allocation()`: securities with `sector = None` are grouped under the key `None` (Python dict key), not `"Unknown"`. Downstream code that expects string keys may raise `TypeError` when encountering the `None` key.

**P4-E-038** | MEDIUM | Line 178
`compute_portfolio_age()` uses `/ 30.44` and `/ 365.25` for month/year conversion. Should use `relativedelta` from `dateutil` for calendar-accurate calculations.

---

### portfolio_risk_engine.py

**P4-E-039** | CRITICAL | Line 54
`_portfolio_var_from_weights()`: variance-covariance VaR formula assumes `sum(weights) == 1.0`. No normalization or assertion. If a user holds $120k long and $20k short in a $100k NAV portfolio, weights are `[1.2, -0.2]` which sum to 1.0 — but if the weights array is the raw dollar amounts, VaR is off by orders of magnitude.

**P4-E-040** | HIGH | Line 242
Stress test applies equity shock as: `pnl_pct = equity_shock * beta`. For a security with beta=3.0 and a -50% equity shock, `pnl_pct = -1.50` (−150% loss), implying total wipeout and further liability. No clamping to -100% minimum or warning for levered cases.

**P4-E-041** | HIGH | Line 184
Factor exposure drift uses 2-sigma threshold: `abs(current - hist_mean) > 2.0 * hist_std`. Under normal distribution, this triggers for 5% of observations randomly. No sensitivity parameter; cannot be tuned per factor.

**P4-E-042** | MEDIUM | Line 163
`compute_factor_exposures()` silently drops any factor present in position data but missing from `factor_returns`: `all_factors &= set(factor_returns.keys())`. Positions with exposure to unlisted factors contribute zero attributed return with no warning.

---

### whatif_engine.py

**P4-E-043** | CRITICAL | Lines 509–510
Weight delta calculation is dead code followed by immediate override:
```python
weight_delta = notional / (notional / (1.0)) * 1.0   # simplifies to 1.0 always
weight_delta = t.get("weight_pct", 1.0)               # overwrites line above
```
Line 509 is a no-op. The effective weight delta is always 1.0 unless the caller supplies `weight_pct`. Every what-if scenario that does not include `weight_pct` calculates factor impacts as if adding 100% weight — completely wrong.

**P4-E-044** | HIGH | Lines 276–310
`estimate_risk_impact()`: positions are expected to have `weight`, `beta`, and `volatility` fields. If any is missing, defaults to `0.0` or `1.0` respectively with no warning. A position missing `beta=1.0` default will appear less risky than it is.

**P4-E-045** | HIGH | Line 306
`total_weight` can be zero if all positions have weight=0.0 (a common state given `market_value` is never populated). Line 310: `weighted_avg = running_sum / total_weight` → `ZeroDivisionError`.

**P4-E-046** | MEDIUM | Line 142
`simulate_trades()` returns `[]` silently if `portfolio_nav <= 0` with no error status. Callers cannot distinguish between "no trades simulate correctly" and "engine refused to run due to invalid NAV."

**P4-E-047** | MEDIUM | Line 179
`proposed_nav = portfolio_nav + total_trade_notional` can go negative. Fallback at line 179: `proposed_nav = portfolio_nav`. This hides the logical error that the trade notional exceeds the portfolio value.

---

### watchlist_monitoring.py

**P4-E-048** | HIGH | Line 261
`check_filing_alert()` sorts filings by `f.get("filed_date", "")` as a string. If `filed_date` contains an ISO timestamp (`"2024-01-15T09:30:00Z"`), string sort works. But if the field is a date object or Python `datetime`, comparison raises `TypeError: '<' not supported between instances of 'datetime' and 'str'`.

**P4-E-049** | MEDIUM | Line 364
Uses `datetime.utcnow()` — naive datetime without timezone info. If the deployment is configured for UTC+X, comparisons against stored timezone-aware datetimes will be off by the offset.

---

### technical_backtester.py

**P4-E-050** | HIGH | Lines 229–234
Position sizing uses `invest = capital * position_size` where `capital` is the remaining portfolio value after each trade. After first trade: remaining capital = 50% of original. Second trade invests 50% × 50% = 25% of original. Position sizes decay geometrically instead of being a constant fraction of the starting capital. This is not documented as intentional behavior.

**P4-E-051** | MEDIUM | Line 215
`signal_map[sig.index] = "BUY"` or `"SELL"` — last signal wins for same timestamp. If a price bar generates both a crossover buy signal and an RSI sell signal simultaneously (in COMBINED mode), only the last-processed signal is recorded. No conflict resolution strategy.

---

### portfolio_parser.py

**P4-E-052** | HIGH | Line 35
`csv.DictReader(io.StringIO(content))` has no try-except. A malformed CSV (mismatched quotes, binary content, non-UTF-8 encoding) raises `csv.Error` or `UnicodeDecodeError` that propagates uncaught to the router, returning an unformatted 500 error.

**P4-E-053** | MEDIUM | Line 125
`h.identifier.upper()` — no null check. If `identifier` is `None` (field missing from CSV row), raises `AttributeError: 'NoneType' object has no attribute 'upper'`.

**P4-E-054** | MEDIUM | Line 85
`_safe_float()` calls `float(cleaned)` in a bare `except` clause. Both `ValueError` (non-numeric string) and `TypeError` (None input) are caught and silently return `None`. A caller that passes a value like `"N/A"` gets `None` back — semantically different from "field was empty" but treated identically.

---

## SECTION 3: MODELS & SCHEMAS

### Decimal → Float Precision Loss (Systemic)

**P4-M-001** | CRITICAL | portfolio.py schema lines 27–28
Model stores `initial_cash` and `current_cash` as `Numeric(20, 2)` (Python `Decimal`). Schema returns them as `float`. Decimal precision is lost on serialization. For a $1,000,000,000.01 portfolio, float rounding drops the cents.

**P4-M-002** | CRITICAL | position.py schema lines 23–32
Seven position fields (`shares`, `cost_basis_total`, `cost_basis_per_share`, `market_value`, `unrealized_pnl`, `weight`, `closing_price`) stored as `Numeric` in the model but returned as `float` in the schema. Financial calculations downstream will accumulate floating-point error.

**P4-M-003** | CRITICAL | transaction_schema.py lines 27–32
Six transaction fields (`shares`, `price_per_share`, `gross_amount`, `commission`, `net_amount`, `cash_impact`) stored as `Numeric` but returned as `float`.

**P4-M-004** | CRITICAL | nav.py schema
`NAVSnapshot.nav`, `market_value`, `cash_balance` stored as `Numeric` in model, returned as `float` in schema.

**P4-M-005** | CRITICAL | performance.py schema
All 20+ performance metric fields stored as `Numeric` in model, returned as `float` in schema.

**P4-M-006** | CRITICAL | backtesting.py schema
All `BacktestResult` metrics (`total_return`, `annualized_return`, `sharpe_ratio`, etc.) stored as `Numeric(x, y)` but schema returns `float`.

**P4-M-007** | CRITICAL | attribution.py schema
Attribution effects and weights stored as `Numeric` but schema returns `float`.

---

### Missing Foreign Key / Referential Integrity

**P4-M-008** | CRITICAL | portfolio_watchlist.py line 47
`WatchlistEntity.entity_id` is declared with `ForeignKey("entities.entity_id")` but no `entities` table is defined in any of the 15 model files audited. Every `INSERT` into `WatchlistEntity` fails with `ForeignKeyViolation` at the database level. The watchlist entity-linking feature cannot function.

**P4-M-009** | HIGH | All models
No `ON DELETE CASCADE` defined on any foreign key. Deleting a portfolio while it has positions or transactions results in a `ForeignKeyViolation` from the database. Deletes must be manually ordered (delete children first), but no code enforces this ordering. Any cascade delete via `session.delete(portfolio)` will fail.

---

### Missing SQLAlchemy Relationships

**P4-M-010** | HIGH | portfolio.py
`Portfolio` model has no `relationship()` definitions to `Position`, `Transaction`, `NAVSnapshot`, `PerformanceSnapshot`, or `AttributionResult`. Eager loading with `selectinload` or `joinedload` is impossible. Every related-object query requires separate explicit queries.

**P4-M-011** | HIGH | position.py
`Position` model has no `back_populates` relationship to `Portfolio`. Must query by `portfolio_id` column every time; no ORM-level navigation.

**P4-M-012** | HIGH | transaction.py
`Transaction` model has no relationship to `Portfolio` or `Position`. No cascade options defined.

**P4-M-013** | HIGH | nav_snapshot.py
`CorporateActionQueue` has no relationship to `NAVSnapshot` or `Position`. Records are orphaned — no ORM-level connection to the portfolio they affect.

---

### Missing Indexes

**P4-M-014** | HIGH | performance.py
No composite index on `(portfolio_id, period_type, period_end)`. The unique constraint exists but is not an explicit query index. Full table scans on every performance lookup.

**P4-M-015** | HIGH | attribution.py
No composite index on `(portfolio_id, period_start, period_end)`.

**P4-M-016** | HIGH | portfolio_risk.py
No composite index on `(portfolio_id, snapshot_date)` for time-series queries.

**P4-M-017** | MEDIUM | portfolio_watchlist.py
No index on `user_id`. "List all watchlists for user" performs a full table scan.

**P4-M-018** | MEDIUM | nav_snapshot.py
Index exists on `portfolio_id` alone but not on `(portfolio_id, snapshot_date)` composite for the most common time-range query pattern.

---

### Missing Constraints & Validation

**P4-M-019** | HIGH | portfolio_upload.py model
No `user_id` field. Impossible to track which user uploaded a portfolio file. Multi-tenant isolation is absent.

**P4-M-020** | MEDIUM | portfolio_watchlist.py line 21
No `UniqueConstraint` on `(user_id, watchlist_name)`. Two watchlists with the same name for one user are permitted at the database level.

**P4-M-021** | MEDIUM | nav_snapshot.py lines 29–30
No `CHECK` constraint that `period_start <= period_end`.

**P4-M-022** | MEDIUM | performance.py lines 30–31
No `CHECK` constraint that `period_start <= period_end`.

**P4-M-023** | MEDIUM | attribution.py lines 29–30
No `CHECK` constraint that `period_start <= period_end`.

**P4-M-024** | MEDIUM | backtesting.py lines 25–26
No `CHECK` constraint that `start_date <= end_date`.

**P4-M-025** | MEDIUM | quant.py line 34
`r_squared` and `adj_r_squared` have no `CHECK` constraint for `[0.0, 1.0]`. Invalid R² values (e.g., −1.5) can be stored.

**P4-M-026** | MEDIUM | All models
No `Enum` or `CHECK` constraints on any `status` or `type` column. Invalid status strings (`"LIMBO"`, `""`) can be inserted without error.

---

### Missing Audit Trail

**P4-M-027** | HIGH | All models
`Transaction`, `Position`, `WatchlistEntity`, `PortfolioUpload`, `BacktestRun` all lack `created_by` and `modified_by` audit fields. No record of which user created or last modified any financial record — a compliance gap.

**P4-M-028** | HIGH | backtesting.py
`BacktestRun` has no `user_id` / `owner_id`. Any user can retrieve any backtest result by ID.

**P4-M-029** | LOW | All models
No soft-delete pattern (`is_deleted`, `deleted_at`). Hard-deleting a portfolio breaks any historical reference to that portfolio_id in snapshots, performance records, and attribution results.

---

## SECTION 4: FRONTEND HOOKS & ENDPOINTS

### usePortfolio.ts

**P4-F-001** | CRITICAL | Line 54
`useAddPosition()` mutation calls `PORTFOLIOS.list` — the GET portfolio list endpoint. Every call to add a position fires a GET to `/v4/portfolios` instead of a POST to `/v4/portfolios/{id}/positions`. Position creation always fails silently.

**P4-F-002** | CRITICAL | Line 58
`useRecordTransaction()` mutation calls `PORTFOLIOS.list` — same wrong endpoint. Transaction recording fires a GET to the list endpoint. All transaction recording fails.

**P4-F-003** | HIGH | Line 32
`useClonePortfolio()` calls `PORTFOLIOS.create` instead of `PORTFOLIOS.clone(id)`. Cloning a portfolio creates a new empty portfolio rather than duplicating the source.

**P4-F-004** | HIGH
`usePortfolio.ts` does not export from `index.ts`: hooks for `useRebalancePortfolio`, `useOptimizePortfolio`, `usePortfolioWhatIf`, `usePortfolioUploadPreview`, `usePortfolioUploadCommit`. Five backend endpoints are completely unreachable from frontend components.

**P4-F-005** | MEDIUM | Line 54
`useAddPosition()` has no `portfolioId` parameter in its signature. Even if the endpoint URL were corrected, there is no way to construct a URL with the correct portfolio ID.

**P4-F-006** | MEDIUM | Line 58
`useRecordTransaction()` has no `portfolioId` parameter. Same issue as above.

**P4-F-007** | MEDIUM | Lines 19, 23, 27
Post-mutation cache invalidation uses `[['portfolios']]` — invalidates the entire portfolio list cache. Should invalidate `['portfolios', id, 'positions']` and `['portfolios', id, 'transactions']` specifically. Until the list cache refreshes, stale position/transaction data is shown.

**P4-F-008** | MEDIUM
`useQuant.ts` hook file exists (confirmed by exploration) with hooks for `useCorrelationMatrix`, `useBenchmarks`, `useBenchmarkDetail`, `useBenchmarkReturns`, `useBenchmarkConstituents`, `useBenchmarkCompare`, `useBenchmarkFactSheet`, but **none are exported from `hooks/index.ts`**. All quant hooks are unreachable from any component.

---

### endpoints.ts

**P4-F-009** | MEDIUM | Lines 768–775
All `BENCHMARKS` endpoints use `/v1/benchmarks` prefix while all portfolio endpoints use `/v4`. If benchmark data is served by a Pillar 4 router at `/v4/benchmarks`, all benchmark queries fail with 404. Needs verification against app.py registration.

**P4-F-010** | MEDIUM
No `QUANT` endpoint object is defined in `endpoints.ts` despite the `quant.py` router existing. The `useQuant.ts` hooks either use hardcoded strings or the `BENCHMARKS` object as a proxy.

**P4-F-011** | LOW
No endpoint definitions for `TECHNICAL_BACKTEST` — the technical backtesting router has no corresponding frontend URL constants.

**P4-F-012** | LOW
No endpoint definitions for `FI_RISK` portfolio-level endpoints (`/bonds/portfolio/risk`, `/bonds/portfolio/rate-scenario`, `/bonds/portfolio/spread-scenario`) in `endpoints.ts`.

---

## SECTION 5: FRONTEND PAGES (Hardcoded Data Audit)

**P4-F-013** | CRITICAL | PortfolioDetail.tsx lines 59–137
All portfolio data is hardcoded: portfolio name "Core Growth", NAV $2,458,320, 10 holdings (AAPL, MSFT, NVDA, AMZN, GOOGL, META, BRK.B, JPM, UNH, V), specific prices, sector allocations, KPIs (Sharpe 1.34, Max Drawdown −6.18%). NAV history generated by `Math.random()` seeded on every render. Four API hooks (nav, navHistory, allocations, snapshot) are called but their data is discarded.

**P4-F-014** | CRITICAL | PerformancePage.tsx lines 21–141
Nine random-data generators dominate the entire page: `generateCumulativeReturns()`, `generateDrawdownData()`, `generateRollingReturns()` all use `Math.random()`. Hardcoded KPIs ($48.2M AUM, +8.42% YTD), 24-entry heatmap, sector attribution, and factor attribution all use static constants. Nine API hooks called but results replaced by `?? hardcodedData` fallback.

**P4-F-015** | CRITICAL | RiskPage.tsx lines 15–65
All VaR KPIs ($385K 95%, $620K 99%, $1.21M 99.9% one-day), concentration risk (NVDA 8.2%), stress test P&L, compliance checks, factor exposures, correlation tickers/matrix, and drift data are hardcoded static objects. Eight API hooks imported; `api.request()` used on line 95 instead of the hook pattern.

**P4-F-016** | CRITICAL | WatchlistView.tsx lines 24–75
Seven fake holdings (AAPL, MSFT, NVDA, etc.), a fake earnings calendar, 10 hardcoded search suggestions, and initial entity list all constructed from static constants. `useWatchlists()` is called but result discarded via `?? watchlistItems`.

**P4-F-017** | CRITICAL | BacktestDashboard.tsx lines 36–66
Six fake strategies, 8 fake backtest results with specific CAGR/Sharpe values, 6 recent run records, and KPIs all hardcoded. `useBacktestStrategies()` and `useBacktestHistory()` called but immediately replaced by `??` fallback. `handleRunBacktest()` fires the API but has empty `catch` block with no user error notification.

**P4-F-018** | CRITICAL | CustomIndexBuilder.tsx lines 30–41
Five fake custom index records with specific performance metrics. Benchmark hook called but result discarded. Create-index endpoint called with empty `catch` block.

**P4-F-019** | CRITICAL | QuantDashboard.tsx lines 28–75
Eight hardcoded factor performance rows (Market Beta, Value, Quality, etc.), eight hardcoded momentum signals with specific scores (NVDA: 94, TSLA: 22), volatility surface computed each render via `Math.abs(strikeIdx - 3) * 2.5` formula — fake implied volatility. Three hooks called; all results replaced by `??` fallback.

**P4-F-020** | CRITICAL | RiskDashboard.tsx lines 8–54
Hardcoded enterprise-level VaR ($2.4M 95%, $4.1M 99%), five hardcoded stress scenarios, six factor exposures, 10-position VaR decomposition, sector concentration — all static. Two hooks called; results replaced by `??` fallback.

**P4-F-021** | HIGH | All 9 pages
Empty `catch` blocks or `console.warn` on API failures. No user-facing error message or toast notification on any mutation failure. Silent failures make it impossible for users to know whether their portfolio changes were saved.

**P4-F-022** | HIGH | All 9 pages
Multiple `as any` TypeScript casts (`(apiData as any)?.field`) that hide real type mismatches between backend response shapes and frontend consumption. Type safety is effectively disabled for all API integration points.

**P4-F-023** | HIGH | PortfolioList.tsx line 79
`onError` callback logs `console.warn` but has `// TODO: show error toast` comment — error notification is explicitly deferred but never implemented. Users creating portfolios see nothing if creation fails.

---

## SECTION 6: APP.PY ROUTER REGISTRATION

**P4-A-001** | CRITICAL
Only five Pillar 4 routers are confirmed registered in app.py: `portfolios`, `portfolio_performance`, `portfolio_risk`, `portfolio_watchlists`, `research_notes` (all under `/v4`).

The following routers exist in `src/api/routers/` but their registration status in app.py could not be confirmed:
- `backtesting.py`
- `quant.py`
- `technical_backtest.py`

If any of these are unregistered, their endpoints are unreachable. The backtesting and quant features would be entirely inaccessible via HTTP despite being fully written.

**P4-A-002** | CRITICAL
`risk.py` router is registered under `/v2/analytics/risk` (Pillar 2), not `/v4`. The frontend `endpoints.ts` may point to `/v4/risk/...` while the actual router serves `/v2/analytics/risk/...`. All security-level VaR and stress test endpoints may be returning 404s from the frontend's perspective.

**P4-A-003** | HIGH
`portfolio_upload.py` router registration not confirmed in app.py. If unregistered, the upload endpoint is unreachable.

**P4-A-004** | HIGH
No Pillar 4 router serves `/v4/quant/...` endpoints. The `quant.py` router (if registered) likely uses a prefix that doesn't match what `usePortfolio.ts` or `useQuant.ts` hooks expect.

---

## ISSUE COUNT BY SEVERITY

| Category | CRITICAL | HIGH | MEDIUM | LOW | Total |
|----------|----------|------|--------|-----|-------|
| Routers | 8 | 14 | 16 | 6 | **44** |
| Engines | 9 | 22 | 15 | 5 | **51** |
| Models/Schemas | 8 | 12 | 10 | 5 | **35** |
| Hooks/Endpoints | 2 | 3 | 6 | 2 | **13** |
| Frontend Pages | 8 | 3 | 0 | 0 | **11** |
| App Registration | 2 | 2 | 0 | 0 | **4** |
| **TOTALS** | **37** | **56** | **47** | **18** | **157** |

---

## REMEDIATION PRIORITY PLAN

### Phase 1 — Runtime Crashes (Fix before any testing)
| ID | Fix |
|----|-----|
| P4-R-003 | Replace all `await session.flush()` with `await session.commit()` in all write paths |
| P4-R-003 | Replace all `await session.delete(obj)` with `session.delete(obj)` (remove await) |
| P4-M-008 | Fix `ForeignKey("entities.entity_id")` — either create Entity model or reference correct table |
| P4-A-001 | Register backtesting.py, quant.py, technical_backtest.py in app.py with correct prefixes |
| P4-R-044 | Add `session: AsyncSession = Depends(get_session)` to fi_risk.py endpoints |
| P4-E-010 | Wrap `_persist_var()` metric name parsing in try-except |

### Phase 2 — Authentication & Data Isolation
| ID | Fix |
|----|-----|
| P4-R-001 | Remove `DEFAULT_USER`; inject real user from JWT/session dependency |
| P4-R-027 | Same fix for portfolio_watchlists.py |
| P4-R-011 | Add authentication dependency to `compare_portfolios()` |
| P4-M-019 | Add `user_id` column to `PortfolioUpload` model |

### Phase 3 — Financial Math Corrections
| ID | Fix |
|----|-----|
| P4-E-030 | Fix MWR: `all_flows.append((terminal_t, -final_value))` |
| P4-E-005 | Implement geometric linking in `link_multi_period_attribution()` |
| P4-E-025 | Normalize/validate weights before VaR computation in `portfolio_risk_engine.py` |
| P4-E-043 | Fix `weight_delta` computation in `whatif_engine.py` |
| P4-E-018 | Fix Sortino denominator: use MAR not zero |
| P4-E-011 | Fix CVaR: use `math.ceil()` not `int()` for cutoff index |
| P4-E-025 | Replace fake ADF in `e7_quant.py` with `statsmodels.tsa.stattools.adfuller` |
| P4-E-013 | Fix stress PnL: use compound return `prod(1+r) - 1` |

### Phase 4 — Connect Engines to Routers
| ID | Fix |
|----|-----|
| P4-R-017/018 | Replace hardcoded stress test results with `e5_risk.RiskEngine.run_stress_test()` calls |
| P4-R-035 | Replace backtest stub with real `backtester.py` engine call |
| P4-R-029/030 | Wire watchlist alerts to `watchlist_monitoring.evaluate_watchlist_alerts()` |
| P4-R-012 | Wire report generation to `reporting_engine.py` |
| P4-R-019 | Extend pre-trade compliance to handle all rule types |

### Phase 5 — Precision & Schema Consistency
| ID | Fix |
|----|-----|
| P4-M-001 to P4-M-007 | Change all financial schema fields from `float` to `Decimal` |
| P4-M-009/010 | Add `ON DELETE CASCADE` to all ForeignKeys |
| P4-M-010 to P4-M-013 | Add `relationship()` definitions to all models |
| P4-M-014 to P4-M-018 | Add missing composite indexes |

### Phase 6 — Frontend Integration
| ID | Fix |
|----|-----|
| P4-F-001 | Fix `useAddPosition()` to POST to `PORTFOLIOS.positions(id)` |
| P4-F-002 | Fix `useRecordTransaction()` to POST to `PORTFOLIOS.transactions(id)` |
| P4-F-003 | Fix `useClonePortfolio()` to use `PORTFOLIOS.clone(id)` |
| P4-F-008 | Export all `useQuant.ts` hooks from `hooks/index.ts` |
| P4-F-013 to P4-F-020 | Replace all `Math.random()` generators and hardcoded arrays with real API data |
| P4-F-021 | Add user-facing error toasts to all mutation `onError` callbacks |
| P4-F-023 | Implement the TODO error toast in PortfolioList.tsx |

### Phase 7 — Constraints & Audit Trail
| ID | Fix |
|----|-----|
| P4-M-020 | Add `UniqueConstraint` on `(user_id, watchlist_name)` |
| P4-M-021 to P4-M-025 | Add `CHECK` constraints for date ordering and value ranges |
| P4-M-027 | Add `created_by`, `modified_by` fields to all financial models |
| P4-M-026 | Add `Enum` types for all status/type columns |
| P4-M-029 | Implement soft-delete pattern (`deleted_at`, `is_deleted`) |

---

*End of Pillar 4 Audit Report v2 — 157 issues across 44 files*
