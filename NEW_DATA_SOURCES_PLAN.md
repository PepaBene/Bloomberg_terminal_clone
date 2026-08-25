# New Free Data Sources — Integration Plan

## Goals & decisions

| Decision | Chosen |
|---|---|
| Scope | 7 sources identified as real, currently-free, not yet integrated (see "Sources" below) |
| Sequencing | Keyless sources first (no signup blocking progress), then signup-gated sources in parallel once keys are requested |
| Pattern | Every source follows the existing `BaseConnector` extract/validate/transform/resolve/load shape already used by all ~50 connectors in `src/ingestion/` — no new architecture |
| "Populated but not used" rule | Every phase ends with an API router + Pydantic schema wired up, not just a filled table — that gap already bit this project once (composite_scores, consensus_estimates, 13F voting authority all sat unused for a while) |
| Registration | CIK/entity-driven sources go into `scripts/backfill.py`'s `ENTITY_TYPES`/`FILER_TYPES` registry (chunked, resumable, `ingestion_progress`-tracked for free). Global/feed-style sources go into `scripts/run_extra_ingestion.py`'s `STAGE_PARALLEL` (or `STAGE_SEC` if they hit SEC EDGAR) |
| Verification bar | Every connector must be exercised live against the real endpoint (not just unit-tested against a fixture) before being trusted — this session found 4 separate cases where a connector "worked" against fixtures but silently produced zero real rows against the live API (stale FINRA dataset name, wrong 13F XML depth, filename-matching bug, missing engine registration) |

Total elapsed time estimate: **~4–6 weeks for one engineer**, dominated by
the SEC Financial Statement Data Sets bulk-file parser (Phase 2) and entity
resolution for USPTO (Phase 6). The four keyless/quick sources (Phases 0, 1,
3 is signup but trivial once the key arrives) are each closer to 1–2 days.

---

## Process reminder (read before each phase)

This isn't new process — it's what already worked all session, written down
so it doesn't get skipped under time pressure:

1. **Fetch one real response by hand first** (`httpx` in a throwaway
   `python -c` snippet) before writing the connector. Confirm the actual
   field names, nesting, and pagination shape — API docs and this plan's
   own descriptions can be stale or wrong the same way the FINRA/13F/GDELT
   assumptions were.
2. **Write the connector** following `src/ingestion/<source>.py` →
   `BaseConnector` subclass → `extract()`/`validate()`/`transform()`/`load()`.
3. **Migration** for any new table/column, numbered sequentially from `095`.
4. **Register** in `scripts/backfill.py` (entity-driven) or
   `scripts/run_extra_ingestion.py` (feed-driven) — reuse the existing
   chunking/pagination/rate-limiting machinery, don't build new orchestration.
5. **Live smoke test**: run the connector against 3–5 real subjects and
   print the parsed output before trusting it to run unattended.
6. **API layer**: add the model to a router (new or existing, whichever
   fits thematically) + a Pydantic response schema. Confirm the route
   appears in `app.openapi()['paths']` after registering it in `app.py`.
7. **Existing test suite**: `pytest tests/test_ingestion/` for the source
   if a test file exists; write one if the connector is nontrivial enough
   to have parsing edge cases (mirrors what already exists for
   `edgar_esg_environmental`, `edgar_13f`, etc.).

---

## Phase 0 — NY Fed Markets Data API *(keyless, ~1 day)*

Fully public, no signup. Highest value-to-effort of the whole list.

**What it adds:**
- SOFR / EFFR at the actual source-of-record (currently mirrored via FRED)
- Primary dealer statistics and reverse repo volumes — nothing else in
  this codebase carries primary-dealer positioning data at all

**Target:** upgrade `money_market_rates` (currently FRED-sourced) with a
`source='NY_FED'` row alongside the existing `source='FRED'` rows (same
table, don't fork it), plus a new `primary_dealer_positions` table.

**Deliverables:**
- [ ] `src/ingestion/nyfed_markets.py` — `NYFedMarketsConnector`
- [ ] Migration `095_primary_dealer_positions.py`
- [ ] `scripts/ingest_nyfed_markets.py`, registered in
      `run_extra_ingestion.py::STAGE_PARALLEL` (global feed, not
      entity-driven — no CIK loop needed)
- [ ] Extend `src/api/routers/money_market.py` (already exists) to surface
      the new source + the dealer-positions table
- [ ] Live-verify against `markets.newyorkfed.org/api/...` before trusting

---

## Phase 1 — SEC Litigation Releases / Administrative Proceedings *(keyless, ~2 days)*

**What it adds:** SEC's own enforcement-action feed — direct
compliance/governance-risk signal per company, distinct from the
Federal-Register-only coverage `ingest_regulatory_actions.py` currently has.

**Target:** new `sec_litigation_releases` table, entity-linked via CIK
where the release names a specific registrant (many don't — store
`entity_id: NULL` for releases that can't be resolved, never fabricate a
link).

**Deliverables:**
- [ ] `src/ingestion/sec_litigation.py` — RSS/JSON parse, same
      `edgar_regulatory_actions.py`-style pattern
- [ ] Migration `096_sec_litigation_releases.py`
- [ ] `scripts/ingest_sec_litigation.py`, registered in
      `run_extra_ingestion.py::STAGE_PARALLEL` (this is SEC's litigation
      RSS feed, not the CIK-driven EDGAR filing API, so it doesn't compete
      for the same rate budget as `STAGE_SEC` — confirm this live before
      assuming it's safe to parallelize)
- [ ] New `src/api/routers/compliance_intelligence.py` or extend an
      existing governance router
- [ ] Entity resolution: match release text against `entities.legal_name`
      the same fuzzy-match approach already used for GDELT/ESG controversies

---

## Phase 2 — SEC Financial Statement Data Sets *(keyless, ~1–2 weeks)*

Biggest single win, biggest chunk of work. Bulk quarterly ZIP files
(`num.txt`, `sub.txt`, `tag.txt`, `pre.txt`) covering every XBRL fact ever
filed — a backstop/cross-check to the existing per-CIK
`edgar_xbrl.py` connector, and a much faster path to bulk historical
backfill than thousands of per-company API calls.

**Target:** doesn't need a new table — this either (a) fills gaps in the
existing `financial_periods`/`income_statements`/`balance_sheets` tables
for companies the live API missed, or (b) is used as a one-time bulk
backfill accelerator. Decide (a) vs (b) after inspecting how much overlap
vs. genuine gap-filling the bulk files provide once fetched.

**Deliverables:**
- [ ] `src/ingestion/sec_financial_statement_datasets.py` — downloads +
      parses the fixed-width/tab-delimited bulk ZIP for one quarter
- [ ] Reconciliation step: for each (CIK, tag, period) in the bulk file,
      check whether `financial_periods` already has it via the live-API
      path before inserting — this is a fill-the-gaps job, not a
      wholesale replace
- [ ] `scripts/ingest_sec_bulk_financials.py --quarter 2026Q2` (one-shot,
      not part of the continuous loops — run manually per quarter or on a
      slower cadence than the rest of backfill)
- [ ] No new API surface needed — feeds tables already exposed

---

## Phase 3 — BLS (Bureau of Labor Statistics) API *(needs free signup, ~2 days once key exists)*

**What it adds:** JOLTS (job openings/quits — a standard leading
indicator), CPI category detail, employment cost index — the current FRED
curation (`src/ingestion/fred_macro.py`) is headline-only (`UNRATE`,
`PAYEMS`), missing this granularity entirely.

**Action item (not code):** request a free BLS API key at
`bls.gov/developers` before this phase starts — it's the one true blocker.

**Deliverables:**
- [ ] `BLS_API_KEY` added to `.env` / `src/config.py`
- [ ] `src/ingestion/bls_macro.py` — mirrors `fred_macro.py`'s seed-series
      pattern (`BLS_SEED_SERIES` list: JOLTS job openings/quits/hires,
      CPI detail categories, ECI)
- [ ] `scripts/ingest_bls.py`, registered in
      `run_extra_ingestion.py::STAGE_PARALLEL`
- [ ] Extend `src/api/routers/macro.py` (already exists) — same
      `global_macro_indicators`-style table, new `source='BLS'` rows

---

## Phase 4 — BEA (Bureau of Economic Analysis) API *(needs free signup, ~2 days once key exists)*

**What it adds:** GDP by industry, state/regional income, trade in
services — FRED's national aggregates without the industry/state
breakdown.

**Action item:** request a free key at `apps.bea.gov/api/signup`.

**Deliverables:**
- [ ] `BEA_API_KEY` added to `.env` / `src/config.py`
- [ ] `src/ingestion/bea_macro.py`
- [ ] Migration if industry/state breakdowns don't fit
      `global_macro_indicators`'s existing shape — check the model first,
      may just need a `geography`/`industry` column added
- [ ] `scripts/ingest_bea.py`, registered in `run_extra_ingestion.py`
- [ ] Same `macro.py` router extension as Phase 3, or a dedicated
      `industry_indicators.py` if the shape doesn't fit cleanly

---

## Phase 5 — Census Bureau Economic Indicators *(needs free signup, ~2 days once key exists)*

**What it adds:** retail trade, business formation statistics, regional
establishment counts — US-regional granularity, same spirit as the
existing World Bank country-risk coverage but domestic.

**Action item:** request a free key at `census.gov/data/developers.html`.

**Deliverables:**
- [ ] `CENSUS_API_KEY` added to `.env` / `src/config.py`
- [ ] `src/ingestion/census_economic.py`
- [ ] Migration: new `regional_economic_indicators` table (state/county
      granularity doesn't fit the existing country-level
      `global_macro_indicators` shape)
- [ ] `scripts/ingest_census.py`, registered in `run_extra_ingestion.py`
- [ ] New `src/api/routers/regional_indicators.py` or extend `macro.py`

---

## Phase 6 — USPTO PatentsView API *(keyless, ~1 week — entity resolution is the real cost)*

**What it adds:** patent filing/grant data by assignee — a genuine
innovation-signal proxy nothing currently covers (not GLEIF, not GDELT,
not any existing connector).

**Target:** new `patent_filings` table, entity-linked via assignee-name
fuzzy match — same class of problem already solved for GLEIF entity
matching and GDELT company-name matching, reuse that matching approach
rather than building a third one.

**Deliverables:**
- [ ] `src/ingestion/uspto_patents.py`
- [ ] Migration `10x_patent_filings.py` (number sequentially at
      implementation time — later phases may have already claimed
      numbers by then)
- [ ] Entity resolution step: assignee name → `entities.entity_id`,
      reusing whichever fuzzy-match helper GLEIF/GDELT settled on — check
      `src/ingestion/edgar_gleif.py` and `edgar_esg_controversies.py`
      first rather than writing a fourth matcher
- [ ] `scripts/ingest_uspto_patents.py`, registered in
      `run_extra_ingestion.py::STAGE_PARALLEL`
- [ ] New `src/api/routers/innovation.py` or extend an existing
      company-intelligence router
- [ ] Could feed a new "innovation signal" input into
      `src/engines/e1_industry_kpis.py` or a growth-profile engine — flag
      for a follow-up analytics phase, not part of this ingestion plan

---

## Explicitly out of scope

Sources researched and ruled out as not currently real/free — don't
revisit without new evidence they've changed: **Yahoo Finance** (unofficial,
ToS-risky, not a stable API), **IEX Cloud** (killed its free tier),
**Nasdaq Data Link** (most useful datasets are now paid), **CDP** (no
meaningful free tier).

---

## Suggested execution order

1. Phase 0 (NY Fed) — keyless, immediate value, smallest scope
2. Phase 1 (SEC Litigation) — keyless, second-smallest scope
3. Request BLS / BEA / Census API keys now (signup takes minutes, approval
   can lag) so Phases 3–5 aren't blocked waiting on email confirmations
4. Phase 6 (USPTO) — keyless, can run in parallel with the signup wait
5. Phase 2 (SEC bulk financials) — biggest phase, schedule once the
   quicker wins are shipped and the team has bandwidth for a multi-day task
6. Phases 3–5 as their respective API keys arrive
