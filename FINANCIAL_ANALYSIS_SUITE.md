# Financial Analysis Suite

Three capabilities added on top of the existing data fabric, all using the
platform's **free public data** (SEC EDGAR 13F-HR & Form 4, US STOCK Act
congressional disclosures, FRED macro series). No paid data feeds are required.

---

## 1. Smart-Money / Notable-Filer tracking — `SMRT`

Follow named investors, corporate insiders, and politicians and turn their
disclosed activity into comparable, directional follow-signals.

- **Curated registry** (`data/notable_investors.json`) maps people to their
  free data source:
  - `GURU_13F` — institutional managers via 13F-HR (e.g. **Michael Burry** /
    Scion, **Warren Buffett** / Berkshire, **Bill Ackman** / Pershing Square)
  - `INSIDER_FORM4` — corporate insiders via Form 4 (e.g. **Jamie Dimon** / JPM)
  - `POLITICIAN` — members of Congress via STOCK Act PTRs (e.g. **Nancy Pelosi**)
- **Engine** (`src/engines/smart_money.py`, pure): position-conviction scoring,
  quarter-over-quarter 13F diffing (new / exited / increased / decreased,
  concentration, turnover), STOCK Act trade classification (size buckets,
  disclosure-lag / late-filing flags, committee-jurisdiction conflict),
  unified follow-signals, cross-investor consensus, and per-ticker
  smart-money flow aggregation.
- **Congressional data**: `src/models/congressional_trades.py`,
  `src/ingestion/congress_trades.py` (House + Senate feeds, configurable URLs),
  `scripts/ingest_congress.py` / `make ingest-congress`.

**API** (`/v1/smart-money/...`): `investors`, `investors/{key}`,
`filers/{key}/profile`, `congress`, `consensus`, `flow/{ticker}`.

## 2. Automatic Model Builder — `MODL`

Auto-assembles scored analytical models across five scopes from pre-fetched
data — **ECONOMIC, MARKET, INDUSTRY, CORPORATE, COMPANY**. Each model returns
a consistent envelope: sections (metrics + qualitative read), key drivers,
explicit assumptions, sub-scores, a 0–100 composite, and a rating/summary.

- **Engine**: `src/engines/auto_model_builder.py` (pure; composes cleanly with
  existing engines such as DCF, comps, DuPont, Altman, macro scenarios).
- **API** (`/v1/models/...`): `scopes`, `build` (any scope from supplied
  metrics), `company/{entity_id}` (auto-pulls fundamentals then models).

## 3. Complex Financial Structure analysis — `STRC`

Analyzes the structural complexity that ratio analysis misses:

- Corporate / subsidiary org tree (holding-company depth, offshore mix)
- Multi-class equity (voting-vs-economic control "wedge", dual-class)
- Off-balance-sheet & VIE exposure (leases, guarantees, SPEs)
- Debt subordination waterfall (seniority, secured %, structural
  subordination across opco/holdco)
- Blended 0–100 complexity score with flags

- **Engine**: `src/engines/complex_structure.py` (pure; builds on the existing
  capital-structure tranches without duplicating them).
- **API** (`/v1/complex-structure/...`): `analyze` (from payload),
  `entity/{entity_id}` (pulls stored debt tranches).

---

## Terminal commands

New Bloomberg-style mnemonics: `SMRT`, `MODL`, `STRC` (registered in the
command parser and main-window command map).

## Tests

- `tests/test_engines/test_smart_money.py`
- `tests/test_engines/test_auto_model_builder.py`
- `tests/test_engines/test_complex_structure.py`
- `tests/test_ingestion/test_congress_trades.py`
- `tests/test_api/test_smart_money_api.py`
