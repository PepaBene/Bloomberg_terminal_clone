# Pillar 1 — Fixes Applied

This documents the fixes made to address every Pillar-1 finding from `DATA_WIRING_AUDIT.md`.
Scope was explicitly limited to **Pillar 1**. Test baseline before fixes: **38 failed / 4,445 passed**.

Fixes fall into three tiers:
- **Tier 1 — genuine bugs & wiring of existing code** — fully fixed and test-verified.
- **Tier 2 — computed rollups & rule-based loaders (no external source)** — fully implemented and test-verified.
- **Tier 3 — brand-new external-data connectors** — built to the established `BaseConnector` pattern with mocked-HTTP unit tests; flagged where live-data/credentials/a source-decision are still needed (cannot be end-to-end validated here).

---

## Tier 1 — Bugs & wiring (fully fixed, test-verified)

| Finding | Fix | File(s) |
|---|---|---|
| **CIK-list wiring bug** — 6 ingestion scripts constructed connectors with no CIK list, so `extract()` always no-op'd | Each script now queries `EntityIdentifier` (type `CIK`) and passes the list (respecting `--limit`) to the connector | `scripts/ingest_edgar_xbrl.py`, `ingest_corporate_actions.py`, `ingest_ownership.py`, `ingest_esg.py`, `ingest_relationships.py`, `ingest_short_interest.py` |
| **Bond analytics coupon convention** — router passed percentage-convention coupon (5.0) into an engine expecting a decimal fraction → ~100× error | Convert `coupon_rate / 100.0` at the router boundary | `src/api/routers/fi_bonds.py` |
| **`Decimal` serialized as JSON string** — `ytm`, `last_trade_price`, `total_debt` returned as strings, breaking numeric clients/tests | Numeric response fields typed as `float` | `src/schemas/corporate_bond.py`, `src/schemas/capital_structure.py` |
| **`security_finder` LIKE injection** — user `q` used unescaped in ILIKE | Apply `escape_like()` in both endpoints | `src/api/routers/security_finder.py` |
| **`/securities/find/suggest` 422** — response missing required `display` field | Populate `display` from short/long name | `src/api/routers/security_finder.py` |
| **`debt_maturity` API** — returned a paginated envelope, never 404'd, missing fields the schema/tests expect | Rewrote endpoints to return the latest profile (with buckets) or 404 | `src/api/routers/debt_maturity.py` |
| **Corporate actions `security_id`** — 8-K rows only set `entity_id`, so the router (which filters by `security_id`) never saw them | 8-K load now resolves and sets `security_id` (prefers common stock) | `src/ingestion/edgar_8k.py` |
| **Relevance scoring** — entities/securities returned a hardcoded constant | Real match-quality score (exact > prefix > substring) | `src/api/routers/entities.py`, `securities.py`, `security_finder.py` |
| **Resolution queue never populated** — `add_to_queue()` had no caller | Wired into the resolver for `UNCERTAIN` verdicts | `src/resolution/resolver.py` |
| **Entity history never recorded** — `record_entity_history()` had no caller | Wired into the EDGAR/GLEIF upsert paths | `src/ingestion/edgar_entities.py`, `gleif_entities.py` |
| **`shares_outstanding` no-op** — placeholder never populated `EquityDetails` | Real XBRL `dei:EntityCommonStockSharesOutstanding` fetch wired into the enrich loop (unblocks Pillar-2 `factor_size`) | `src/ingestion/edgar_securities.py` |
| **Entity hierarchy / relationships / GLEIF parents** | GLEIF parent-LEI linkage + relationships endpoint corrected | `src/ingestion/gleif_entities.py`, `src/api/routers/entities.py` |
| **`fi_yield_curve` dead import** — `enhanced_bootstrap` imported, never used | Removed (the endpoint correctly serves stored zero rates) | `src/api/routers/fi_yield_curve.py` |

---

## Tier 2 — Rollups & loaders (fully implemented, test-verified)

| Feature | What was built | File(s) |
|---|---|---|
| **Trading calendars** | Deterministic NYSE holiday engine (Gregorian computus for Good Friday, weekend-observation rule, Juneteenth-from-2022) + trading-day generation; FK-safe; wired into `make seed`. 7 unit tests. | `src/ingestion/reference_loader.py`, `data/trading_calendars.json`, `tests/test_ingestion/test_trading_calendars.py` |
| **OwnershipSummary rollup** | Aggregates institutional/insider/short-interest into `ownership_summaries` | `src/engines/ownership_summary_engine.py`, `scripts/compute_ownership_summary.py` |
| **TechnicalStudyValue persistence** | Computes indicators over `EODPrice` and persists | `scripts/compute_technicals.py` (engine unchanged) |
| **ESGTemperatureScore persistence** | Runs the Paris-alignment engine and persists | `scripts/compute_esg_temperature.py` |
| **SegmentData** | XBRL segment-fact connector | `src/ingestion/edgar_segments.py`, `scripts/ingest_segments.py` |
| **Debt-maturity rollup** | Buckets `DebtTranche` rows into `DebtMaturityProfile`/`MaturityBucket` | `src/engines/debt_maturity_engine.py`, `scripts/compute_debt_maturity.py`, `tests/test_engines/test_debt_maturity_engine.py` |

---

## Tier 3 — New external connectors (pattern-complete + mock-tested)

All target real free sources, follow the `BaseConnector` pattern, and have mocked-HTTP/sample-payload unit tests proving the transform + DB-write path. Status flags are honest about live-data limits.

| Connector | Source | Status |
|---|---|---|
| **Capital structure** | SEC XBRL/10-K debt | `extract()` implemented + driver script |
| **Credit ratings** | SEC 8-K Item 2.06/8.01 | `extract()` implemented + driver script |
| **Credit spreads** | FRED BofA/ICE OAS series | implemented (FRED pattern) + driver script |
| **Treasury securities** | Treasury Fiscal Data API (keyless) | implemented + tested |
| **TRACE corporate bonds** | FINRA TRACE | pattern-complete — **needs FINRA credentials + live validation** |
| **Agency bonds / issuances** | configurable feed | pattern-complete — **needs a data-source decision** |
| **Executives** | SEC Form 3/4/5 reporting-owner | fully implemented + mock-tested |
| **FOMC meetings** | FRED DFEDTARU/DFEDTARL | fully implemented + mock-tested (rate-change meetings only) |
| **Central-bank policy** | FRED policy-rate series | Fed fully tested; **ECB/BOE series IDs need live validation** |
| **Earnings surprises** | actual EPS vs consensus | compute+load tested — **needs a consensus-estimate feed** |
| **M&A deals** | SEC 8-K Item 1.01/2.01 | deal-event tested — **needs exhibit parsing for value/multiples** |
| **IPO events** | SEC S-1/424B | lifecycle tested — **needs prospectus parsing for price/shares** |
| **Fund holdings (N-PORT)** | SEC N-PORT XML | mock-tested on sample — **needs live N-PORT validation** |
| **ESG controversies** | configurable feed | tested — **needs a source decision (no free structured feed exists)** |

Each connector has a `make` target (see `Makefile`).

---

## Deliberately not changed

- **2 `custom_classifications` API tests** fail due to pre-existing **test-isolation fragility** (order-dependent tests assuming an empty shared in-memory DB) — not an audit finding or a production bug. Refactoring the shared-`StaticPool` conftest to fix them risks destabilizing the 4,400+ passing tests, so it was left and documented.

## Test-isolation note

The tier-3 ingestion tests originally used `session.commit()`, which permanently poisons the shared in-memory `StaticPool` DB and leaked rows into existing model tests (`test_ipo`, `test_fed_meeting`, `test_macro`). Changed to `session.flush()` so rows roll back per-test while remaining visible within the test — eliminating that contamination.
