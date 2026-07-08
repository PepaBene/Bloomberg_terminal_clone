# Manual Testing Checklist — Bloomberg Data Fabric

A step-by-step, click-through checklist for the running app (backend `http://localhost:8000`, frontend `http://localhost:5173`). Each item is pass/fail against a stated **expected result**. Where a page is known to have a wiring gap (per `DATA_WIRING_AUDIT.md`), that's called out inline as **⚠ Known gap** so you don't waste time chasing an already-documented issue — but do still check the box once you've confirmed the *symptom* matches what's documented (if it doesn't match, that's a new bug, not the known one).

Legend: `[ ]` untested · check it off when verified · note any deviation from "Expected" directly under the item.

---

## 0. Prerequisites

- [ ] `docker compose ps` shows `postgres`/`redis`/`elasticsearch` all healthy.
- [ ] `alembic current` reports the latest head migration.
- [ ] Backend: `curl http://localhost:8000/health` → `{"status":"ok","database":"connected"}`.
- [ ] Frontend: `http://localhost:5173` loads without a blank white screen.
- [ ] Browser devtools console is open and pinned to "Errors" for the entire session — note any red errors per page below, even if the UI looks fine.
- [ ] Network tab open, filtered to XHR/Fetch — for each page, spot-check that requests go to the URL you expect (not a 404).

### 0.1 Seed real data first (or expect empty states everywhere)

Run in order (see `CONNECTING_TO_REAL_DATA.md` for full detail):

- [ ] `make seed` (reference data)
- [ ] `python scripts/ingest_edgar.py` (entities)
- [ ] `python scripts/ingest_openfigi.py` (securities)
- [ ] `python scripts/ingest_eod_prices.py --limit 100` (prices)
- [ ] `python scripts/ingest_fred.py` (macro)
- [ ] `python scripts/run_analytics_batch.py --engine all` (ratios/valuation/scores)
- [ ] `python scripts/ingest_congress.py` (congressional trades — for Smart Money testing)

**⚠ Known gap:** `python scripts/ingest_edgar_xbrl.py`, `ingest_corporate_actions.py`, `ingest_ownership.py`, `ingest_esg.py`, `ingest_relationships.py`, `ingest_short_interest.py` will all report success but **insert zero rows** — a wiring bug (see `DATA_WIRING_AUDIT.md` §3, Fix #1), not a data-availability problem. Don't spend time debugging your `.env`/API keys over this — it's a code bug, confirmed.

- [ ] After seeding, pick one real, liquid ticker to use as your standard test subject throughout this checklist (e.g. whatever landed in your first 100 EDGAR entities — check via `curl "http://localhost:8000/v1/entities/search?q=apple"` or similar). Write it here: `_______`

---

## 1. Landing Page

**Route:** `/`

- [ ] Page loads without console errors.
- [ ] **⚠ Known gap:** every widget (indices, movers, alerts, econ calendar, sector performance, intraday chart) is expected to show **fabricated data with no loading/error state** — all 5 backing API calls hit routes that don't exist on the backend. Confirm this is what you see (fake-looking but "clean" data, no error banner) — if instead you see a genuine error or blank page, that's a *different*, new bug worth logging.
- [ ] Confirm in the Network tab that these calls indeed 404: `/v1/market/indices`, `/v1/market/movers`, `/v1/alerts/recent`, `/v1/econ/calendar`, `/v1/market/sectors`.

---

## 2. Company pages

Navigate to each with your test ticker selected.

### 2.1 Company Overview — `/company`
- [ ] Header loads with entity name/ticker.
- [ ] Quarterly financials bar chart — **check known bug**: chart may render empty even though data was fetched (a wiring bug feeds it a permanently-empty constant instead of the real fetched data). Check Network tab: did `/v1/fundamentals` calls return real data even though the chart is blank?
- [ ] Sentiment gauge — confirm it always shows the same fixed value (0.42) regardless of ticker (**known hardcoded value**, not a real gauge yet).
- [ ] Piotroski/Altman/Beneish breakdown widgets — confirm these are static all-zero (not wired to real scores on this page — the *real* scores are computed and available via `/v2/analytics/scores/*`, just not surfaced here).
- [ ] Price chart (`StockCandlestick`) — confirm it's empty (never wired to price data on this page).
- [ ] News section — confirm it's empty (no working endpoint feeds it).

### 2.2 Financial Statements — `/company/financials`
- [ ] Income statement / balance sheet / cash flow tables populate with real numbers for your test ticker (assuming `ingest_edgar_xbrl.py` bug is fixed — otherwise expect empty, see §0.1 known gap).
- [ ] Segments/revenue breakdown — expect empty (`SegmentData` has no ingestion path at all — this is a deeper gap than the general XBRL bug).
- [ ] **Known bug:** page header shows literal "Loading..." text permanently instead of the real company name — confirm.

### 2.3 Valuation — `/company/valuation`
- [ ] DuPont, multiples history, DCF model, DCF sensitivity all attempt to load.
- [ ] Peer comparison table — confirm `peerMedians` (P/E ~29.0, EV/EBITDA ~19.2) show identically regardless of which ticker/peer group you pick (**known hardcoded fallback**).
- [ ] DCF: trigger a recompute. Confirm the explicit error banner appears/disappears correctly (this part was previously fixed and should work).
- [ ] Football field chart — confirm it fetches but doesn't necessarily render (verify this against `DATA_WIRING_AUDIT.md` §5.2 — the "football field" endpoint always recomputes live server-side; the frontend's `activeFootballData` is fetched then discarded, so this widget is expected blank).

### 2.4 Ownership — `/company/ownership`
- [ ] Institutional holdings, insider holdings tables — expect populated once XBRL/13F/Form4 ingestion bug (§0.1) is fixed; otherwise empty.
- [ ] `insiderPct`/`institutionalPct` badges — confirm these show fixed 7%/60.8% regardless of real data (**known hardcoded**).
- [ ] Fund holdings table — expect always empty (fund-holdings endpoint is called with the wrong ID type; also no fund ingestion exists at all).

### 2.5 Filings — `/company/filings`
- [ ] Filing events, filing diffs (10-K YoY), insider transactions, risk factors, MD&A sections.
- [ ] Confirm the "No risk factor data available" / "No MD&A data available" empty-state messages appear correctly when data is missing (this page has good empty-state handling — verify it's honest, not silently fake).
- [ ] **⚠ Known gap:** all of these will likely be empty regardless of ingestion — 8-K events are written to the wrong DB table by the ingestion connector, and filing-diff/insider tables have no writer at all.

### 2.6 Credit Profile — `/company/credit`
- [ ] **⚠ Known gap — most concerning page in this section.** Expect to see ~10 fully-populated, realistic-looking widgets (covenants, credit metrics, ratio panels, maturity wall, equity-credit data, leverage trajectory) **regardless of whether any bond/credit data has been ingested for your test ticker** — these are unconditional hardcoded fallbacks, not real data. Confirm this by checking the Network tab: do the underlying `/v1/fi/*` calls actually return data, or are they empty/404 while the page still shows full charts? If the page shows data with no corresponding successful API call, that confirms the known bug.

### 2.7 Company Intelligence — `/company/intelligence`
- [ ] Business model, capital allocation, management quality, balance sheet risk, revenue drivers, cost structure, margin analysis sections — expect all empty (no ingestion for any of these tables) with proper "no data" messaging (this page has good empty-state UX — confirm it's honest).
- [ ] Moat assessment, SWOT, Porter's Five Forces — same, expect empty with proper messaging.
- [ ] Sentiment gauge — same hardcoded 0.42 as Company Overview.

### 2.8 ESG — `/company/esg`
- [ ] Governance metrics populate if ESG ingestion bug is fixed (governance-only scores); Environmental/Social scores and composite ESG score/rating should show as empty/null (by design — the connector never computes these).
- [ ] Controversies panel shows "No active controversies" (correct empty state, not a bug — there's genuinely no controversies data source).

### 2.9 Governance — `/company/governance`
- [ ] Board, compensation, shareholder proposals — expect empty with proper loading/error/empty-state UI (this page is one of the cleanest in the app).
- [ ] Governance score widget — if you see a score, verify whether it's computed live (real) or was previously cached from a hardcoded-input bug (`DATA_WIRING_AUDIT.md` §6.2) — check the value looks suspiciously "neutral"/default rather than ticker-specific.

---

## 3. Screener

### 3.1 Equity Screener — `/screener`
- [ ] Page loads showing `MOCK_STOCKS` (20 fake tickers) by default.
- [ ] Set a filter and click "Run". Expect a request to `/v2/analytics/screen*`.
- [ ] **Known bug**: the run will likely 422 (wrong request body shape) and the page falls back to mock data with a **"Demo mode" banner** — confirm the banner appears. This is the one page in the app that's honest about faking data.
- [ ] If you fix the request-shape bug yourself, confirm real screening actually works against real `AnalyticsResult` data.

### 3.2 Fixed Income Screener — `/screener/fi`
- [ ] Page loads showing `mockBonds` (8 fake CUSIPs).
- [ ] Run any screen — expect a 404 (wrong endpoint path entirely) and **no demo banner at all** (worse UX than the equity screener — confirm this asymmetry).

---

## 4. Sector

### 4.1 Sector Overview — `/sector`
- [ ] **⚠ Known gap:** expect a fully-populated 11-sector table with fabricated d1/wtd/mtd/ytd/P-E figures, permanently, regardless of backend state — both backing hooks call broken/misconfigured endpoints. No loading/error indication at all. Confirm this matches (page looks "done" but is 100% fake).

### 4.2 Industry Detail — `/sector/:gicsCode`
- [ ] Select any GICS code. Confirm the Network tab shows successful 200 responses.
- [ ] **⚠ Known bug:** despite successful API responses, the page shows identical static semiconductor-company data (NVDA/TSM/AVGO/AMD/INTC/QCOM) for **every** GICS code — a response-shape mismatch, not a missing-data issue. Try 2-3 different GICS codes and confirm the "top companies" list never changes.

---

## 5. Fixed Income

### 5.1 FI Dashboard — `/fi`
- [ ] Yield curve table populates from real data (if treasury data is ingested — currently a known gap, expect empty).
- [ ] Yield curve **chart** — confirm it's blank even if the table above it has data (known disconnect: chart data isn't wired to the same source as the table).

### 5.2 Treasury Dashboard — `/fi/treasuries`
- [ ] Confirm heavy use of realistic hardcoded fallbacks: rate-sensitivity panel (100% static, no hook at all) and auction records.
- [ ] Spread-history chart — confirm it's visibly a random walk (regenerates differently on every page refresh) — confirms it's `Math.random()`-driven, never real.

### 5.3 Bond Detail — `/fi/bonds/:cusip`
- [ ] Navigate directly with a real CUSIP if you have one from `fi_bonds` ingestion (currently a known gap — expect blank fields, not fake data, on this page specifically — it's one of the cleaner ones).

### 5.4 Credit Market — `/fi/credit`
- [ ] Confirm the "AI Credit Briefing" paragraph always shows text (never an empty state) — it's calling the *wrong* hook (yield-curve endpoint mislabeled as a briefing endpoint), so this is always the fallback text.
- [ ] Confirm named distressed issuers (Rite Aid, Community Health, Carvana) appear with specific default-probability numbers regardless of any real ingestion — these are hardcoded.
- [ ] OAS chart — confirm random-walk behavior on refresh (synthetic).

### 5.5 Issuance Monitor — `/fi/issuance`
- [ ] Confirm weekly stats/pipeline/recent-issues show specific named real issuers (Amazon, Goldman, Microsoft, JPMorgan) with fabricated spread numbers — these are static regardless of backend state, with zero visual indication.

### 5.6 FI Intelligence — `/fi/intelligence`
- [ ] **⚠ Highest-severity known finding in the whole frontend audit.** Open the transcript viewer. Confirm it shows a fabricated Apple/Tim Cook earnings-call transcript with invented quotes and zero backing API call. This should be flagged/fixed before any external demo of this page.

---

## 6. Portfolio

### 6.1 Create a real portfolio first
- [ ] `POST /v4/portfolios` via the UI ("New Portfolio" or similar) — confirm a portfolio is actually created (check `GET /v4/portfolios` shows it, and/or query the DB directly).
- [ ] Add at least 2 positions (a BUY transaction) to your new portfolio.

### 6.2 Portfolio List — `/portfolio`
- [ ] Confirm your newly-created portfolio appears in the real list.
- [ ] Kill the backend momentarily (or throttle network to force an error) and confirm the page falls back to **`MOCK_PORTFOLIOS`** (7 fake named portfolios like "Core Growth") with **no visual indication** that these are fake — this is a known bug (`retry:0` + `?? MOCK_PORTFOLIOS`). Restart the backend before continuing.

### 6.3 Portfolio Detail — `/portfolio/:id`
- [ ] Open your real portfolio. Confirm holdings/positions you added actually show up (not the static 10-fake-ticker mock).
- [ ] **Critical check** — for a position you bought, confirm `market_value`/`unrealized_pnl`/weight are **NOT** computed (known gap: `Position.market_value` is never calculated anywhere in the backend — expect `0` or blank, confirming NAV = cash balance only).
- [ ] Performance metrics row (TWR/Sharpe/MaxDD/Beta) — confirm these are static regardless of your real portfolio's actual composition (no backing hook exists for this specific row).
- [ ] NAV history chart — confirm it correctly shows blank/empty rather than fake random data (this part was fixed).

### 6.4 Performance Page — `/portfolio/:id/performance`
- [ ] **⚠ Known gap:** confirm `GET .../performance` returns null/empty — nothing in the codebase computes and persists a performance snapshot, regardless of how much trading history your test portfolio has.
- [ ] Confirm cumulative-returns/drawdown/rolling-returns charts correctly render **empty** (not fake) — this part was fixed.
- [ ] Confirm the KPI row, calendar-returns table, risk-metrics table, and both attribution tables **do** show realistic fake numbers regardless of real data (not yet fixed, unlike the charts).

### 6.5 Risk Page — `/portfolio/:id/risk`
- [ ] **⚠ Known gap — least-remediated page in the portfolio section.** Confirm every panel (VaR, concentration, stress, compliance, factor exposure, correlation, drift) shows realistic fake data regardless of your real portfolio's composition — this page was NOT fixed the way its sibling `/risk` dashboard was.
- [ ] Run a custom stress scenario (if the UI exposes it) and confirm whether the result changes at all based on your portfolio's real holdings, or stays static.

---

## 7. Watchlist

### 7.1 — `/watchlist`
- [ ] Create a watchlist, add a real ticker to it.
- [ ] Reload the page. **Known gap:** confirm the table starts **empty** even though you just added an item to it server-side — the page never actually fetches the saved watchlist contents back (`entities` state is local-only, never hydrated from `GET`). This will look like your addition "didn't save" even though it did (verify server-side via a direct API call).
- [ ] Search-suggestions dropdown — confirm "No results found" appears correctly for a nonsense query (this part works).

---

## 8. Risk Dashboard (standalone)

### 8.1 — `/risk`
- [ ] Confirm this page (distinct from `/portfolio/:id/risk`) shows honest `—`/empty placeholders instead of fake numbers when data is missing — this is the **correctly remediated** sibling of the portfolio risk page. Use it as your reference for what "done right" looks like.

---

## 9. Macro

### 9.1 Macro Dashboard — `/macro`
- [ ] Confirm GDP/inflation/NFP/unemployment/indicator KPIs show realistic values regardless of whether `ingest_fred.py` has actually run — no loading/error state distinguishes real from fallback data here.
- [ ] Re-run with FRED data ingested and confirm whether the numbers actually change (if they don't change after real ingestion, that confirms the fallback is masking real data).

### 9.2 Yield Curve Deep Dive — `/macro/yield-curve`
- [ ] Confirm the "1 Month Ago" curve overlay never changes regardless of date range selected (static).
- [ ] Confirm both the spread-history and forward-curve OAS charts visibly change on every page refresh (confirms `Math.random()`-driven, not real).

### 9.3 Central Bank Monitor — `/macro/central-banks`
- [ ] Confirm central bank list, dot plot, market pricing, and 5Y Fed-funds history all show data with no loading/error handling (fallback data, since no central-bank ingestion exists).

---

## 10. Global

### 10.1 Global Dashboard — `/global`
- [ ] **Known bug:** confirm the panel labeled "Commodities" is actually showing FX rate data (wrong hook wired to wrong panel — check the actual values, they should look like currency pairs, not commodity prices).
- [ ] Confirm the central-banks panel never changes regardless of country/filter selected (100% static, no hook backing it at all).

### 10.2 Country Risk — `/global/countries`
- [ ] Select any country. **Known bug:** confirm the risk detail never loads (the hook that would fetch country-specific risk is called with no country-code argument, so the query is permanently disabled) — geopolitical events panel always shows the same static mock regardless of country selected.
- [ ] "Countries Tracked" / "High Risk" KPI numbers — confirm these never change (fully static, no hook).

### 10.3 Commodity Dashboard — `/global/commodities`
- [ ] Confirm the price chart visibly changes on every refresh (random walk, never real).
- [ ] Confirm the exposure map is fully static regardless of commodity selected.

### 10.4 Political Monitor — `/global/political`
- [ ] Click through all 4 tabs (elections, regulatory, bills, sanctions). **Known bug:** confirm all 4 show the same underlying geopolitical-events data reshaped incorrectly, or static mock data — real endpoints exist on the backend for bills/sanctions specifically but nothing on the frontend calls them.

---

## 11. Research

### 11.1 Research Hub — `/research`
- [ ] Select an entity. Confirm intelligence data loads or shows "No intelligence data available" honestly. This page is clean — flag anything that looks fake.

### 11.2 Company Primers — `/research/primers`
- [ ] Select an entity with no existing primer — confirm "No primer available... Generate Primer" appears (honest empty state).
- [ ] Generate a primer. Confirm financial/valuation sections populate with real numbers (this part is genuinely wired). Confirm the narrative/executive-summary text is `None`/empty or a template placeholder — not real AI-generated prose (known: LLM client always returns `None`).

### 11.3 Morning Briefings — `/research/briefings`
- [ ] Generate an on-demand briefing. **Known bug:** confirm the executive summary is literally the string "On-demand briefing generated." regardless of actual market/portfolio state.
- [ ] Confirm `marketContext`/`keyThemes`/`portfolioImpact` sections show realistic fake S&P futures/VIX/portfolio-weight numbers rather than an honest empty state.
- [ ] Briefing history list — confirm this one correctly shows empty when there's no history (not faked).

### 11.4 Anomaly Detection — `/research/anomalies`
- [ ] **Known bug:** confirm the anomaly stats and anomaly list show specific fake events (AAPL volume spike, JPM CDS widening, PFE insider buy) rather than an honest empty state.
- [ ] Trigger a manual scan for your test entity. **Known bug:** confirm it just shows "INITIATED" and never actually produces a result — the scan endpoint is a complete no-op.
- [ ] "Critical Anomalies" section — confirm this one is correctly gated on real data (shows empty honestly).

### 11.5 Semantic Search — `/research/search`
- [ ] Search for two very different, unrelated terms (e.g. "climate risk" vs "debt covenant"). **Known bug:** confirm the results are identical/chronological regardless of query — the query text is never actually applied as a search filter server-side.
- [ ] Confirm the "No results found" state appears correctly at least for a query with zero indexed documents.

### 11.6 Investment Thesis — `/research/thesis`
- [ ] Generate a thesis for your test entity, supplying real content in the form fields.
- [ ] Confirm the thesis you entered is saved and displayed back correctly (real CRUD).
- [ ] Confirm no field is auto-generated by AI — you should have had to type everything yourself (known: no LLM wiring here, client-supplied content only).
- [ ] Update the thesis's conviction level and confirm `conviction_change` is correctly computed and shown in the version history (this was previously a bug, now fixed — verify).

### 11.7 Analyst Q&A — `/research/qa`
- [ ] Ask any question about your test entity.
- [ ] **Known bug — most literal "fake AI" in the app:** confirm the answer is the exact literal string "AI-generated answer placeholder." regardless of what you asked.
- [ ] Ask a completely different, unrelated question and confirm you get the identical placeholder answer both times.

### 11.8 Macro Themes — `/research/themes`
- [ ] **Known bug:** open devtools Network tab, confirm at least one request 404s (frontend calls `GET /v4/research/themes` as a list endpoint and `/themes/{id}/securities`, neither of which exist on the backend — check for these specific 404s).
- [ ] If you can reach a scenario detail, run it and confirm no actual computation happens — it just returns whatever was previously cached.

---

## 12. Flows / Custom / Deals / IPO / Quant / Alerts / News / Settings

### 12.1 Flows — `/flows`
- [ ] **Known bug:** confirm "whale trades" table shows 5 specific fabricated trades attributed to real firms (Berkshire, Bridgewater, Citadel, Renaissance, Soros) with zero visual indication they're fake — all 3 backing queries hit wrong/nonexistent paths.

### 12.2 Custom Data — `/custom`
- [ ] Try uploading a file. **Known bug:** confirm the upload silently fails (wrong endpoint path) with no error shown to the user.
- [ ] Confirm the import-history table shows 7 specific fake rows with 2026 dates regardless of any real upload attempt.

### 12.3 Deals — `/deals` and IPO Monitor — `/market/ipo`
- [ ] Confirm both pages show honest `—`/empty placeholders rather than fake numbers (both call wrong/nonexistent endpoints, but degrade cleanly, unlike most other broken-endpoint pages) — note the lack of any loading skeleton or explicit "no data" messaging though.

### 12.4 Quant Dashboard — `/quant`
- [ ] Confirm the correlation matrix loads with real computed data (this one hook is wired correctly).
- [ ] Confirm the Factor Performance table shows literally 0.00% for every single factor — this is real backend behavior (the backend itself hardcodes these to 0.0 with a "real return series would go here" comment), not just a frontend fallback.
- [ ] Confirm the momentum/vol-surface sections carry an honest "Illustrative — not from live data" disclosure label (a good pattern — check it's actually visible, not buried).

### 12.5 Backtest Dashboard — `/quant/backtest`
- [ ] Submit a backtest run.
- [ ] **Known bug:** confirm the run is accepted (submission succeeds) but results never appear no matter how long you wait — the backend creates a `PENDING` row and nothing ever processes it. Refresh a few times over a couple minutes to confirm it truly never resolves, it's not just slow.
- [ ] Check the KPI row above your results — confirm you see literal `"+undefined%"` or `"NaN%"` text rendered instead of a placeholder dash (a real, easy-to-spot rendering bug from dividing by zero results).

### 12.6 Custom Index Builder — `/quant/index-builder`
- [ ] Confirm the page loads with an empty index list (clean empty-array fallback, not fake data) and static `—` KPI placeholders.

### 12.7 Alerts — `/alerts`
- [ ] **Known bug — confirm this even if the backend genuinely has real alert data:** the page does `.stats`/`.alerts` property access on what the backend actually returns as a bare array, so it **always** falls back to 10 fabricated alerts (AAPL, JPM CDS, VIX, MSFT, TSLA, META, PFE, Ford) — check the Network tab, confirm the raw response is an array (not `{stats:..., alerts:...}`), and confirm the UI shows the fake list regardless.

### 12.8 News — `/news`
- [ ] If any real news articles exist in the DB (there likely aren't any — no ingestion path exists), confirm whether the page **crashes** rather than rendering — the frontend reads field names (`headline`, `sentiment`, etc.) that don't match the backend schema, so `n.sentiment.toFixed(2)` should throw once a real row without that exact shape arrives. If the page is currently blank/empty instead of crashing, that's because there's genuinely no data yet — try inserting one test row directly via the DB to trigger this and confirm the crash, since it's currently masked.

### 12.9 Settings — `/settings`
- [ ] Change your theme preference and save. **Known bug:** confirm the change appears to "work" in the UI but doesn't actually persist anywhere (all 3 backing endpoints — classifications, profile, api-keys — hit nonexistent/wrong paths; writes silently swallow their errors).
- [ ] Confirm the API-keys table shows 4 fake masked keys regardless of your account's real state.
- [ ] Reload the page and confirm your "saved" theme change did not actually persist server-side (only survives if cached client-side).

---

## 13. Features with no web frontend page yet (test via `/docs` or `curl`)

These exist as working (or partially working) backend APIs but have no React page — test them directly against the OpenAPI docs at `http://localhost:8000/docs`.

### 13.1 Smart Money — `/v1/smart-money/*`
- [ ] `GET /v1/smart-money/investors` — confirm the curated registry loads (Michael Burry, Warren Buffett, Bill Ackman, Nancy Pelosi, Jamie Dimon, etc.)
- [ ] `GET /v1/smart-money/investors/bill_ackman` — **known bug:** confirm this 404s.
- [ ] `GET /v1/smart-money/investors/michael_burry_scion` — confirm this incorrectly returns Bill Ackman's profile (confirms the copy-paste key bug in `data/notable_investors.json`).
- [ ] `GET /v1/smart-money/congress` (after `ingest_congress.py`) — confirm real congressional trade data with disclosure-lag and committee-conflict flags computed.
- [ ] `GET /v1/smart-money/flow/{ticker}` for your test ticker — confirm it aggregates real filer data (or gracefully skips filers with no data, rather than crashing).

### 13.2 Auto Model Builder — `/v1/models/*`
- [ ] `POST /v1/models/build` with a full manually-supplied metrics payload for scope `COMPANY` — confirm a real, deterministic composite score comes back.
- [ ] `GET /v1/models/company/{entity_id}` for your test entity — confirm `growth_score` reflects real income-statement data, but confirm `quality`/`value`/`safety`/`sentiment` sub-scores are all exactly 50.0 (known: neutral defaults, not wired to DCF/comps/Altman/smart-money).

### 13.3 Complex Structure Analysis — `/v1/complex-structure/*`
- [ ] `POST /v1/complex-structure/analyze` with a full manual payload (subsidiaries, share classes, off-balance-sheet, debt tranches) — confirm a real composite score across all 4 dimensions.
- [ ] `GET /v1/complex-structure/entity/{entity_id}` for an entity with real debt tranches ingested — confirm subsidiary/share-class/off-balance-sheet dimensions are always empty defaults, and confirm `secured_pct` is always `0.0` even for tranches you know are secured (known bug: checks the wrong enum field).

---

## 14. Cross-cutting checks (do these last, across the whole app)

- [ ] Grep your own browser session: did any page ever show a hard crash (white screen / React error boundary) rather than a graceful degradation? Note the page and the console stack trace.
- [ ] For every page flagged "known gap" above, confirm the *category* of gap matches what's documented (mock fallback vs. broken URL vs. genuine empty state) — if a page's behavior doesn't match its documented gap, that's a new regression worth filing separately.
- [ ] Toggle `REQUIRE_AUTH=true` in `.env`, restart the backend, and confirm every endpoint now requires a Bearer token (`POST /auth/token` to get one) — this mode is off by default and easy to forget to test.
- [ ] Confirm CORS: with the frontend on a different origin/port than `5173`, confirm requests fail until you add that origin to `ALLOWED_ORIGINS`.
- [ ] Restart the backend with an empty database (`docker compose down -v && docker compose up -d && alembic upgrade head`, no seeding) and spot-check 5 pages from different sections above — confirm they show genuine empty states rather than crashing, distinguishing "no data yet" pages from the "fabricated data regardless of state" pages you catalogued above.
