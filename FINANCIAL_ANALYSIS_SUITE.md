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

## Terminal UI (desktop GUI)

New Bloomberg-style mnemonics with full PySide6 panels:

- `SMRT` → `SmartMoneyPanel` — notable-investor registry + congressional trades
- `MODL` → `AutoModelPanel` — composite score, rating, sub-scores, drivers
- `STRC` → `ComplexStructurePanel` — subsidiary tree / share classes /
  off-balance-sheet / debt waterfall tabs

These are wired into the window via the panel registry in
`src/gui/windows/main_window.py` and backed by `DataService` methods
(`load_notable_investors`, `load_congress_trades`, `run_auto_model`,
`run_complex_structure`).

### GUI wiring fix (platform-wide)

Auditing UI coverage uncovered that the existing 22 panels were defined but
**never registered** — `navigate_to()` only produced "Panel not yet
implemented" placeholders, and it called `load_data()` while panels implement
`activate()`. This is now fixed with a panel registry + correct `activate()`
dispatch, so every built panel is reachable. Two latent per-panel crashes
(`Qt.QMargins` → `QMargins` in `gp_panel` and `ecfc_panel`) and six built but
unreachable panels (OWN/ESG/RV/QUAL/SI/RESO, missing from the command map)
were also fixed.

### Full UI coverage

Five features previously had a backend API but no desktop panel; they now do:

- `DDIS` → `DebtMaturityPanel` (debt maturity profile + buckets)
- `CRPR` → `CreditRatingPanel` (current ratings + rating actions)
- `ISSD` → `IssuancePanel` (primary-market bond issuance)
- `PORT` → `PortfolioPanel` (managed portfolios)
- `HELP` → `HelpPanel` (command reference)

**Every command mnemonic now opens a real panel — zero placeholders remain.**
The new panels are reachable from the command bar and from the View / Analytics
/ Fixed Income / Finance Suite / Help menus.

## Tests

- `tests/test_engines/test_smart_money.py`
- `tests/test_engines/test_auto_model_builder.py`
- `tests/test_engines/test_complex_structure.py`
- `tests/test_ingestion/test_congress_trades.py`
- `tests/test_api/test_smart_money_api.py`
- `tests/test_gui/test_panel_wiring.py` (headless; skipped without the `gui` extra)
