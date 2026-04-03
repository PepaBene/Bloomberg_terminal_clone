# Pillar 3 Intelligence — Full Audit Report

**Date:** 2026-04-03
**Scope:** Every engine, router, model, batch script, and frontend component in the Pillar 3 (Intelligence) and Pillar 4 (Research) surface areas
**Method:** Static code analysis — no tests run
**Total Issues Found:** 74

---

## Executive Summary

Pillar 3's database schema, API surface area, and frontend scaffolding are largely production-ready. The vast majority of GET endpoints, data models, and React pages exist and are structurally correct. However, **the entire AI/ML inference layer that would make Pillar 3 meaningfully different from a simple data viewer is not connected**. Every "intelligent" feature — Q&A, briefing generation, semantic search, anomaly scanning, primer refresh, scenario execution, and sentiment scoring — is either a hardcoded stub, a skeleton record writer, or silently falls back to a dumb alternative. Additionally, there are URL registration bugs that make an entire feature sub-tree return 404, widespread mock data in the frontend that is never replaced with live API data, and an ingest pipeline gap that means even the one real ML model (FinBERT) never processes any documents.

---

## Part 1: Universal Issues (Affect All of Pillar 3)

### BUG-001: LLM Client Is a Complete Stub

**File:** `src/ai/llm_client.py`
**Severity:** Critical

The `LLMClient.generate()` method unconditionally returns `None`. There are no imports of `anthropic`, `openai`, `litellm`, or any other LLM SDK. The method body is:

```python
# In production, this would call the Anthropic API.
# For now, return None so callers can fall back to templates.
return None
```

Every feature that depends on this client (Q&A, briefings, primers, investment thesis, company intelligence) receives `None` and either silently falls back to a hardcoded template or returns a placeholder string. There is no environment variable check, no conditional activation, no configuration path to turn on real LLM calls. The client is architecturally wired correctly (injected via dependency injection in routers) but is functionally inert.

**Impact:** Affects 100% of Pillar 3's "intelligent" output features.

---

### BUG-002: No Embedding Infrastructure Connected

**File:** `src/engines/semantic_search_engine.py`
**Severity:** Critical

The `compute_cosine_similarity()` and `rank_results()` functions exist as pure math, but there is **no embedding generation layer** anywhere in the codebase. `rank_results()` requires pre-computed embedding vectors to be passed in as a parameter — it does not generate them itself. No sentence transformer, no OpenAI embeddings client, no vector database (pgvector, Pinecone, Chroma, Qdrant) is loaded or configured. The `ResearchDocument` model has no embedding column.

The actual search endpoint (`POST /research/search`) bypasses `semantic_search_engine.py` entirely and executes:

```sql
SELECT * FROM research_documents
WHERE source_type = :source_type   -- optional
ORDER BY created_at DESC
```

This is a chronological sort with an optional filter. It has zero semantic capability.

**Impact:** The Semantic Search feature is entirely non-functional as advertised.

---

## Part 2: Backend — Stubbed Endpoints and Broken Logic

### BUG-003: Q&A Returns Hardcoded Placeholder

**File:** `src/api/routers/research_qa.py`, line 65
**Severity:** Critical

`POST /v4/research/qa/ask` returns:

```python
return {"answer": "AI-generated answer placeholder.", "confidence": 0.85, "sources": []}
```

The `analyst_qa_engine.py` engine is fully implemented with question parsing, type classification, and prompt assembly. The prompt is built correctly. However `llm_client.generate(prompt)` is called, returns `None`, and the router ignores this and returns the hardcoded string instead of propagating a meaningful error or degraded response.

**Secondary issue:** `sources` is always an empty list. The engine's source-retrieval logic is never invoked from the router.

---

### BUG-004: Briefing Generation Creates Empty Skeleton Records

**File:** `src/api/routers/research_briefings.py`, line 236
**Severity:** Critical

`POST /v4/research/briefings/generate` executes:

```python
briefing = MorningBriefing(
    date=today,
    ai_enabled=False,
    status="PENDING",
    headline="",
    summary="",
    sections={}
)
session.add(briefing)
await session.commit()
return {"message": "On-demand briefing generated.", "briefing_id": briefing.id}
```

`morning_briefing_engine.py` is fully implemented — it fetches market data, calculates movers, assembles a structured prompt — but is never called from this endpoint. The `ai_enabled=False` flag is permanently set. Every call to this endpoint inserts a new skeleton row with empty headline and summary into the database, polluting the `morning_briefings` table. Users who call `/briefings/generate` and then fetch the returned `briefing_id` will receive an empty record.

---

### BUG-005: Semantic Search Suggested Queries Are Hardcoded

**File:** `src/api/routers/research_search.py`, line ~180
**Severity:** High

`GET /v4/research/search/suggested` returns:

```python
return {
    "suggestions": [
        "Q4 earnings surprises",
        "Fed rate decision impact",
        "Supply chain disruptions"
    ]
}
# to be replaced by AI engine
```

This list never changes. There is no personalization, no query history analysis, no trending-topic derivation, no ML ranking. The comment acknowledges the TODO but no implementation path exists.

---

### BUG-006: Anomaly Scan Returns INITIATED Without Running

**File:** `src/api/routers/research_anomalies.py`, lines 335–339
**Severity:** Critical

`POST /v4/research/anomalies/scan/{entity_id}` returns:

```python
return {"status": "INITIATED", "entity_id": entity_id, "scan_id": str(uuid4())}
```

`anomaly_detection_engine.py` contains 7 fully-implemented detector functions (z-score, percentile, IQR, MAD, EMA deviation, cross-asset correlation, earnings quality). None of them are called. No background task is spawned. No database record is created. The returned `scan_id` is a random UUID that does not exist in any table — if the client polls for results using this ID it will receive a 404.

**Secondary issue:** There is no `GET /v4/research/anomalies/scan/{scan_id}/status` endpoint to poll anyway.

---

### BUG-007: Primer Refresh Creates PENDING Log With No Job

**File:** `src/api/routers/research_primers.py`, line ~210
**Severity:** High

`POST /v4/research/primers/{entity_id}/refresh` creates a `PrimerRefreshLog` record with `status="PENDING"` but does not enqueue any async task, Celery job, background thread, or subprocess. The log record stays PENDING forever. `company_primer_engine.py` is fully implemented but never invoked.

---

### BUG-008: Scenario Run Returns Cached Results With No Computation

**File:** `src/api/routers/research_themes.py`, line ~290
**Severity:** High

`POST /v4/research/scenarios/{scenario_id}/run` fetches the scenario from DB and returns its existing `results` field with the comment:

```python
# in production this would trigger computation
```

No computation is triggered. If `results` is null (new scenario), the endpoint returns null data. There is no way for a scenario to ever have computed results.

---

### BUG-009: Company Intelligence Router Writes Empty Records

**File:** `src/api/routers/company_intelligence.py`
**Severity:** High

All three mutation endpoints (`POST /v3/company-intelligence/briefing`, `POST /v3/company-intelligence/analysis`, `POST /v3/company-intelligence/summary`) create `CompanyBriefing` records with empty payloads:

```python
briefing = CompanyBriefing(
    entity_id=entity_id,
    signal_data={},
    valuation_data={},
    risk_data={},
    ai_summary=None,
    status="PENDING"
)
# In production, assemble from DB queries
session.add(briefing)
```

Every POST call inserts a new row with all data fields empty. Over time this creates substantial database noise. Clients that subsequently fetch the generated briefing receive empty payloads. There is no deduplication logic (same entity can accumulate hundreds of empty records).

---

### BUG-010: research_themes Router Registered at Wrong URL Prefix

**File:** `src/api/app.py`, line 653
**Severity:** Critical

```python
app.include_router(research_themes_router, prefix="/v3")
```

All other research/pillar-4 routers are registered at `/v4/research/`. The themes router's own path definitions are `/research/themes/*`, so it resolves to `/v3/research/themes/*`. The frontend's endpoint constants point to `/v4/research/themes/*`. **Every themes and scenarios endpoint returns 404 in production.** This affects:

- `GET /v4/research/themes/` — list all themes (404)
- `GET /v4/research/themes/{id}` — theme detail (404)
- `GET /v4/research/themes/{id}/securities` — securities for theme (404)
- `POST /v4/research/scenarios/{id}/run` — run scenario (404)
- `GET /v4/research/scenarios/` — list scenarios (404)

---

### BUG-011: Sentiment Score Endpoint Never Uses LLM Client

**File:** `src/api/routers/sentiment.py`, line ~95
**Severity:** High

`POST /v3/analytics/sentiment/score` retrieves the LLM client via dependency injection, then performs keyword-count sentiment analysis, sets `ai_enabled=False`, and returns without ever calling `llm_client.generate()`. The LLM client variable is assigned but dead:

```python
llm = get_llm_client()   # injected but unused
# ... keyword counting logic ...
return SentimentScoreResponse(ai_enabled=False, ...)
```

---

### BUG-012: Sentiment GET Endpoint Returns Zeros When No Data Exists

**File:** `src/api/routers/sentiment.py`, line ~60
**Severity:** Medium

`GET /v3/analytics/sentiment/{entity_id}` returns:

```python
return {
    "entity_id": entity_id,
    "avg_sentiment": 0.0,
    "article_count": 0,
    "sentiment_label": "NEUTRAL",
    ...
}
```

when no `SentimentAggregate` row exists. A neutral/zero response is indistinguishable from an entity with genuinely neutral sentiment. There is no `data_available: false` flag or 404/204 response.

---

### BUG-013: FinBERT Has No Ingest Pipeline

**File:** `src/engines/finbert_sentiment.py`
**Severity:** High

The FinBERT model (`ProsusAI/finbert`) is correctly loaded via HuggingFace `pipeline()` with lazy initialization and graceful fallback. **The model itself is real and functional.** However:

1. There is no scheduled job, webhook, or event trigger that passes news articles or filings through FinBERT.
2. The `SentimentScore` and `SentimentAggregate` tables are never populated through any automated pipeline.
3. `finbert_sentiment.py` exports `analyze_text()` and `analyze_batch()` but no router or script calls them for bulk ingest.
4. The only way sentiment data enters the DB is through the manual `POST /sentiment/score` endpoint, which uses keyword counting (BUG-011), not FinBERT.

FinBERT will never run in normal system operation.

---

### BUG-014: research_notes Router — Note Content Never Validated for Length

**File:** `src/api/routers/research_notes.py`
**Severity:** Low

`POST /v4/research/notes` accepts `content` as an unbounded string. The `ResearchNote` model maps `content` to `TEXT` (unlimited). However the frontend sends markdown which may include embedded base64 images. There is no max-size guard, no content sanitization, and no extraction of embedded images to object storage. Large notes will cause slow queries and could exhaust memory during full-table scans.

---

### BUG-015: research_thesis Endpoints — All Read-Only Paths Work, Computation Path Missing

**File:** `src/api/routers/research_thesis.py`
**Severity:** Medium

All GET endpoints are fully implemented. `POST /v4/research/thesis` creates a thesis record correctly. However `investment_thesis_engine.py`'s `compute()` function is never called — the thesis is created as a skeleton and populated only if the client subsequently provides `thesis_text` via a PATCH. The engine's sector-specific risk/driver framework (`SECTOR_TEMPLATES`) and scoring logic are dead code from an operational perspective.

---

### BUG-016: Trending Topics `trend_direction` Always Hardcoded to "UP"

**File:** `src/api/routers/research_search.py`, line ~220
**Severity:** Low

`GET /v4/research/search/trending` derives trending topics from recent document counts (real logic) but hardcodes:

```python
"trend_direction": "UP"
```

for every topic regardless of whether volume is increasing or decreasing compared to the prior period.

---

### BUG-017: Filing Diff Engine — Diff Storage Not Garbage Collected

**File:** `src/engines/filing_diff.py`, `src/api/routers/filing_intelligence.py`
**Severity:** Low

The filing diff engine computes and stores diffs per filing pair. There is no TTL, no archival policy, and no cleanup job. Every diff is stored permanently. For high-frequency filers this will cause unbounded table growth.

---

### BUG-018: Intelligent Alert Engine — Alert Deduplication Window Is Zero

**File:** `src/engines/intelligent_alert_engine.py`
**Severity:** Medium

The deduplication logic checks whether an identical alert was fired in the last `N` seconds, but `N` is hardcoded to `0` (or effectively no window). On burst events (e.g., price spike), the engine will fire identical alerts for every tick within the same evaluation cycle. There is no per-entity throttle or cooldown period.

---

### BUG-019: Governance Scoring — Score Computation Not Called From Router

**File:** `src/engines/governance_scoring.py`, `src/api/routers/governance_intelligence.py`
**Severity:** Medium

`governance_scoring.py` computes board independence, audit quality, compensation alignment, and shareholder rights scores. The `GovernanceIntelligence` router's `GET /v3/governance/{entity_id}/score` endpoint queries the `GovernanceScore` table directly. If no pre-computed row exists, it returns 404. There is no on-demand computation trigger, no batch script that calls the engine, and no fallback to compute-on-request. New entities will always get 404 for governance scores until a batch job is manually run (which does not exist).

---

### BUG-020: Earnings Intelligence — EPS Surprise Calculation Uses Pre-Stored Value

**File:** `src/api/routers/earnings_p2.py`
**Severity:** Medium

`GET /v3/earnings/{entity_id}/surprises` fetches `EarningsSurprise` rows from the DB. These rows are pre-populated at ingest time. If the ingest pipeline fails to compute `surprise_pct` correctly (e.g., consensus estimate was revised after ingest), the stored value is stale and there is no recalculation path. The endpoint has no `recalculate=true` query parameter.

---

## Part 3: Frontend — Hardcoded Mock Data and Broken Connections

### BUG-021: AnalystQA.tsx — Answer Always Placeholder, Sources Always Empty

**File:** `frontend/src/pages/research/AnalystQA.tsx`
**Severity:** Critical

The page calls `useAskQA()` and displays the returned answer. Since the backend returns `"AI-generated answer placeholder."` for every query (BUG-003), all users see this string regardless of their question. Additionally:

- `sources` array is always empty so the "Supporting Sources" panel is always blank
- The confidence meter renders `0.85` hardcoded from the backend stub
- The conversation history section calls `useQAHistory()` which is a real DB query and works, but the displayed answers in history are also all placeholder strings

---

### BUG-022: BriefingView.tsx — Briefing Content Always Empty After Generate

**File:** `frontend/src/pages/research/BriefingView.tsx`
**Severity:** Critical

`handleGenerate()` calls `useGenerateBriefing()` mutation, receives a `briefing_id`, then redirects to view that briefing. Since the generated record has `headline=""` and `summary=""` (BUG-004), the view renders blank. No error is shown.

**Secondary issues:**
- `useBriefingHistory()` is fetched but its result is never rendered — the sidebar history panel shows hardcoded dummy entries
- There is no polling mechanism to check if a briefing transitions from PENDING to COMPLETE status

---

### BUG-023: SemanticSearch.tsx — No Semantic Search Occurs

**File:** `frontend/src/pages/research/SemanticSearch.tsx`
**Severity:** Critical

The page renders a search input and calls `useResearchSearch()`. Since the backend performs `ORDER BY created_at` (BUG-002), results are always sorted by recency regardless of semantic relevance. Relevance scores returned are `null` — the frontend conditionally renders the score badge only if non-null, so no score is ever shown. The "relevance" ordering the user sees is purely chronological.

**Secondary issues:**
- Suggested queries panel calls `useSuggestedSearches()` but displays the 3 hardcoded backend strings (BUG-005)
- The "Semantic Match %" progress bars in the results list are never populated because `relevance_score` is always null

---

### BUG-024: AnomalyView.tsx — Scan Triggers But Results Never Appear

**File:** `frontend/src/pages/research/AnomalyView.tsx`
**Severity:** Critical

`handleRunScan()` calls `useTriggerAnomalyScan()` and receives `{ status: "INITIATED", scan_id: "..." }`. The component stores the `scan_id` and begins polling `useAnomalyStatus(scan_id)`. Since no database record is created (BUG-006) and no status endpoint exists, the poll returns 404 on every tick. The component shows "Scanning..." indefinitely with no timeout or error state. The page never transitions to showing results.

---

### BUG-025: ThemesDashboard.tsx — All Requests Return 404

**File:** `frontend/src/pages/research/ThemesDashboard.tsx`
**Severity:** Critical

All hooks (`useResearchThemes()`, `useResearchTheme()`, `useResearchScenarios()`) hit `/v4/research/themes/*`. Due to BUG-010, the backend serves these routes at `/v3/research/themes/*`. Every request returns 404. The page displays loading skeletons indefinitely or falls back to an empty state with no error messaging.

---

### BUG-026: PrimerView.tsx — Refresh Produces No Updated Content

**File:** `frontend/src/pages/research/PrimerView.tsx`
**Severity:** High

`handleRefresh()` calls the primer refresh mutation, receives a success response, and shows a "Refresh requested" toast. Since the backend creates only a PENDING log (BUG-007), the primer content never updates. The user cannot distinguish this from a successful refresh that is still processing. There is no webhook or SSE notification that would update the UI when (if) the primer completes.

**Secondary issues:**
- `primer.sections` is rendered by iterating a hardcoded array of section keys; if the API returns different section names they are silently dropped
- The "Last Updated" timestamp is taken from `primer.updated_at` which is never updated after the initial creation

---

### BUG-027: ThesisBuilder.tsx — Compute Button Does Nothing

**File:** `frontend/src/pages/research/ThesisBuilder.tsx`
**Severity:** High

The "Compute Investment Thesis" button calls `useRunThesisComputation()` which POSTs to the thesis endpoint. Since `investment_thesis_engine.py` is never called by the router (BUG-015), the returned thesis has empty `drivers`, `risks`, and `target_price`. The component has no fallback display for empty thesis data — it renders empty lists and `undefined` prices.

---

### BUG-028: CompanyIntelligence.tsx — Six Hooks Fetched, Results All Ignored

**File:** `frontend/src/pages/company/CompanyIntelligence.tsx`
**Severity:** High

The following hooks are declared and their requests are sent but the returned data is never used to render anything:

```typescript
const { data: revenueDrivers } = useRevenueDrivers(entityId);
const { data: costStructure } = useCostStructure(entityId);
const { data: marginAnalysis } = useMarginAnalysis(entityId);
const { data: moatAssessment } = useMoatAssessment(entityId);
const { data: swot } = useSWOT(entityId);
const { data: porterForces } = usePorterForces(entityId);
```

Every JSX section that would render these datasets contains hardcoded placeholder content instead. Six unnecessary API calls are made on every page load.

---

### BUG-029: GovernanceDashboard.tsx — Proxy Data Hook Result Ignored

**File:** `frontend/src/pages/company/GovernanceDashboard.tsx`
**Severity:** Medium

`useGovernanceProxy(entityId)` is called but its result is not rendered. The proxy proposals table shows hardcoded rows. The actual proxy voting data (if any exists in the DB) is never displayed.

---

### BUG-030: FilingsView.tsx — MDNA Section Always Placeholder Text

**File:** `frontend/src/pages/company/FilingsView.tsx`
**Severity:** Medium

`useFilingMDNA(filingId)` is called but its result is ignored. The MD&A tab renders:

```tsx
<p>Management's Discussion and Analysis content will appear here...</p>
```

regardless of whether real MD&A content was extracted and stored.

---

### BUG-031: MorningBrief.tsx — Market Data Section Hardcoded

**File:** `frontend/src/pages/research/MorningBrief.tsx`
**Severity:** High

The top market summary cards (S&P 500, Nasdaq, 10Y Treasury, VIX) display hardcoded values:

```tsx
{ label: 'S&P 500', value: '4,783.45', change: '+0.42%' },
{ label: 'Nasdaq', value: '14,921.23', change: '+0.67%' },
```

These are never updated from the API. `useMacroDashboard()` is called but its result is not wired to these cards. A user viewing this page always sees stale fixture data as the market summary.

---

### BUG-032: ResearchHub.tsx — Activity Feed and Quick Stats All Hardcoded

**File:** `frontend/src/pages/research/ResearchHub.tsx`
**Severity:** Medium

The "Recent Activity" feed and the stats tiles ("Active Themes: 12", "Today's Anomalies: 3", "Briefings: 5") are hardcoded. No API hooks for these aggregates are called. The research hub effectively displays static marketing copy.

---

### BUG-033: AnalystQA.tsx — No Loading or Error States on Submission

**File:** `frontend/src/pages/research/AnalystQA.tsx`
**Severity:** Medium

The `handleSubmit()` function has:

```typescript
try {
  const result = await askQuestion(query);
  setAnswer(result);
} catch {}
```

Empty `catch {}` means all API errors are silently swallowed. The submit button has no loading spinner. On slow connections the user can double-submit, causing duplicate question records in the DB.

---

### BUG-034: BriefingView.tsx — Briefing History Never Rendered

**File:** `frontend/src/pages/research/BriefingView.tsx`
**Severity:** Low

`useBriefingHistory()` is fetched (real DB query, works correctly) but the sidebar that should show past briefings renders a hardcoded list of 3 dummy entries with dates from 2024. The fetched history data is assigned to a variable that is never used in JSX.

---

### BUG-035: All Intelligence Pages — No Skeleton/Error State for 404 from Theme Router Bug

**File:** Multiple Pillar 3 pages
**Severity:** Medium

When any endpoint returns 404 (e.g., all theme endpoints due to BUG-010, governance scores due to BUG-019), the frontend React Query error state is not handled. Pages silently remain in loading state or render empty containers without informing the user that data is unavailable.

---

## Part 4: Data Model and Schema Issues

### BUG-036: ResearchDocument Has No Embedding Column

**File:** `src/models/research.py`
**Severity:** High

There is no `embedding` column (e.g., `VECTOR(1536)` for pgvector or `ARRAY` type) on `ResearchDocument`. Even if an embedding model were connected tomorrow, there is no place to store computed vectors. A schema migration would be required before semantic search can be implemented.

---

### BUG-037: MorningBriefing.sections Is JSON With No Schema Enforcement

**File:** `src/models/research.py`
**Severity:** Low

`MorningBriefing.sections` is stored as unstructured JSON. The morning briefing engine produces a specific structure (`market_overview`, `top_movers`, `macro_events`, etc.) but nothing enforces this at the model layer. If the engine's output format changes, old records become incompatible with the frontend parser without any migration.

---

### BUG-038: SentimentScore Table — No Unique Constraint on (entity_id, source, article_id)

**File:** `src/models/intelligence.py`
**Severity:** Medium

`SentimentScore` has no unique constraint on `(entity_id, source_identifier)`. Running sentiment analysis twice on the same article creates duplicate rows. Aggregation queries will double-count sentiment, inflating `article_count` and biasing `avg_sentiment`.

---

### BUG-039: PrimerRefreshLog — No Timeout or Stale Detection

**File:** `src/models/research.py`
**Severity:** Low

`PrimerRefreshLog` records stay in `status="PENDING"` forever (BUG-007). There is no `expires_at` column, no TTL index, and no cleanup job. A query for "active refresh jobs" will always return an ever-growing list of stale PENDING records.

---

### BUG-040: CompanyBriefing — No Unique Constraint on (entity_id, briefing_type, date)

**File:** `src/models/intelligence.py`
**Severity:** Medium

Every POST to the company intelligence endpoints inserts a new `CompanyBriefing` row (BUG-009). Without a unique constraint, the table accumulates unlimited duplicate empty records per entity. There is no soft-delete or supersede mechanism.

---

## Part 5: Integration and Configuration Issues

### BUG-041: No Batch Script for Pillar 3 Engines

**Severity:** High

Pillar 2 has `scripts/run_analytics_batch.py`. There is no equivalent batch runner for Pillar 3. The following engines produce data that must be pre-computed but have no invocation path:

- `anomaly_detection_engine.py` — populate `AnomalyAlert` table
- `governance_scoring.py` — populate `GovernanceScore` table
- `finbert_sentiment.py` — populate `SentimentScore` / `SentimentAggregate` tables
- `morning_briefing_engine.py` — create daily `MorningBriefing` records
- `company_primer_engine.py` — create/refresh `CompanyPrimer` records
- `investment_thesis_engine.py` — compute thesis data for `InvestmentThesis` records

Without a batch script, these tables will remain empty in any deployed environment.

---

### BUG-042: LLM Environment Variables Not Documented or Checked

**File:** `src/ai/llm_client.py`
**Severity:** Medium

When the LLM client is eventually implemented, it will need API keys (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc.) and model configuration. Currently there is no `settings.py` entry, no `.env.example` entry, and no startup check that validates these are present. The client would fail at runtime with an unhelpful `KeyError` or `AttributeError`.

---

### BUG-043: No Rate Limiting on AI Endpoints

**Severity:** Medium

Endpoints that will eventually call LLMs (`/qa/ask`, `/briefings/generate`, `/primers/refresh`) have no rate limiting middleware. A user could call `/qa/ask` in a tight loop and exhaust LLM API quotas in seconds. There is no per-user, per-entity, or global rate limit configured.

---

### BUG-044: app.py — All Pillar 3 Router Imports in Silent try/except

**File:** `src/api/app.py`
**Severity:** Medium

```python
try:
    from .routers import filing_intelligence_router
    app.include_router(filing_intelligence_router, prefix="/v3")
except Exception:
    pass  # silently skip
```

This pattern wraps every Pillar 3 router. If any router has an import error (e.g., a missing dependency after a partial deployment), it is silently skipped and the entire feature group disappears from the API without any log warning or startup failure. This makes debugging broken deployments extremely difficult.

---

## Part 6: Features That Are Production-Ready

The following Pillar 3 features are fully implemented and functional end-to-end:

| Feature | Router | Status |
|---|---|---|
| Filing Events (8-K, periodic) | `filing_intelligence.py` | ✅ Complete |
| Filing Diffs | `filing_intelligence.py` | ✅ Complete |
| Filing Risk Factors extraction | `filing_intelligence.py` | ✅ Complete |
| Governance Proxy data | `governance_intelligence.py` | ✅ Complete (GET only) |
| Governance Compensation data | `governance_intelligence.py` | ✅ Complete |
| ESG Scores & History | `governance_intelligence.py` | ✅ Complete |
| News feed & trending | `news.py` | ✅ Complete |
| Alert rules CRUD | `alerts.py` | ✅ Complete |
| Alert history | `alerts.py` | ✅ Complete |
| Earnings surprises (pre-stored) | `earnings_p2.py` | ✅ Complete |
| Earnings calendar | `earnings_p2.py` | ✅ Complete |
| Earnings transcripts | `earnings_p2.py` | ✅ Complete |
| Competitive peers | `company_intel_p2.py` | ✅ Complete |
| Market share data | `company_intel_p2.py` | ✅ Complete |
| Supply chain data | `company_intel_p2.py` | ✅ Complete |
| Research notes CRUD | `research_notes.py` | ✅ Complete |
| Research thesis CRUD (skeleton) | `research_thesis.py` | ✅ GET/POST/PATCH work |
| Q&A history, feedback, stats | `research_qa.py` | ✅ Complete (non-AI paths) |
| Briefing history, preferences | `research_briefings.py` | ✅ Complete (non-AI paths) |

---

## Part 7: Issue Summary Table

| ID | Area | Severity | Description |
|---|---|---|---|
| BUG-001 | AI Layer | Critical | LLM client generate() returns None unconditionally |
| BUG-002 | AI Layer | Critical | No embedding generation or vector DB connected |
| BUG-003 | Backend | Critical | Q&A returns hardcoded placeholder string |
| BUG-004 | Backend | Critical | Briefing generate writes empty skeleton to DB |
| BUG-005 | Backend | High | Suggested queries hardcoded, never personalized |
| BUG-006 | Backend | Critical | Anomaly scan returns INITIATED, no actual scan run |
| BUG-007 | Backend | High | Primer refresh creates PENDING log, no job triggered |
| BUG-008 | Backend | High | Scenario run returns cached data with no computation |
| BUG-009 | Backend | High | Company intel endpoints write empty records to DB |
| BUG-010 | Backend | Critical | research_themes_router registered at /v3, frontend expects /v4 — all 404 |
| BUG-011 | Backend | High | Sentiment score endpoint never calls LLM client |
| BUG-012 | Backend | Medium | Sentiment GET returns 0s when no data, indistinguishable from real neutrality |
| BUG-013 | Backend | High | FinBERT model loaded but no ingest pipeline calls it |
| BUG-014 | Backend | Low | Research notes accept unbounded content with no size limit |
| BUG-015 | Backend | Medium | Investment thesis engine never called, thesis always empty |
| BUG-016 | Backend | Low | Trending topics trend_direction hardcoded "UP" |
| BUG-017 | Backend | Low | Filing diffs stored permanently, no garbage collection |
| BUG-018 | Backend | Medium | Alert deduplication window is zero, burst events fire duplicate alerts |
| BUG-019 | Backend | Medium | Governance scores return 404 for any entity without pre-computed row |
| BUG-020 | Backend | Medium | Earnings surprise pct stale if consensus revised after ingest |
| BUG-021 | Frontend | Critical | Q&A page always shows placeholder answer and empty sources |
| BUG-022 | Frontend | Critical | Briefing generate produces blank content, no polling for completion |
| BUG-023 | Frontend | Critical | Semantic search returns chronological results, not semantic |
| BUG-024 | Frontend | Critical | Anomaly scan shows "Scanning..." indefinitely, never resolves |
| BUG-025 | Frontend | Critical | Themes dashboard all requests return 404 |
| BUG-026 | Frontend | High | Primer refresh shows success toast but content never updates |
| BUG-027 | Frontend | High | Thesis compute button — engine not called, returned thesis empty |
| BUG-028 | Frontend | High | CompanyIntelligence.tsx: 6 hooks fetched, results all ignored |
| BUG-029 | Frontend | Medium | GovernanceDashboard proxy hook result ignored |
| BUG-030 | Frontend | Medium | FilingsView MDNA section always placeholder text |
| BUG-031 | Frontend | High | MorningBrief market data hardcoded, never from API |
| BUG-032 | Frontend | Medium | ResearchHub activity feed and stats hardcoded |
| BUG-033 | Frontend | Medium | AnalystQA empty catch block, no loading state, allows double-submit |
| BUG-034 | Frontend | Low | BriefingView history fetched but never rendered |
| BUG-035 | Frontend | Medium | No error/skeleton states for 404 responses |
| BUG-036 | Schema | High | ResearchDocument has no embedding column for vector search |
| BUG-037 | Schema | Low | MorningBriefing.sections has no schema enforcement |
| BUG-038 | Schema | Medium | SentimentScore has no unique constraint, allows duplicate article scoring |
| BUG-039 | Schema | Low | PrimerRefreshLog PENDING records never expire or get cleaned up |
| BUG-040 | Schema | Medium | CompanyBriefing has no unique constraint, accumulates empty duplicates |
| BUG-041 | Infra | High | No batch runner script for any Pillar 3 engine |
| BUG-042 | Infra | Medium | LLM API keys not documented or validated at startup |
| BUG-043 | Infra | Medium | No rate limiting on AI-powered endpoints |
| BUG-044 | Infra | Medium | Pillar 3 router imports silently swallowed, broken routers disappear invisibly |

---

## Part 8: Remediation Plan

### Phase 1 — Critical Path: Fix One-Line Bugs (1 day)

1. **BUG-010**: Change `prefix="/v3"` to `prefix="/v4"` for `research_themes_router` in `app.py`
2. **BUG-004**: Stop persisting empty briefing records; return 202 Accepted with a job ID only after actual computation begins
3. **BUG-009**: Add a guard: if engine returns empty data, return 422 rather than writing empty DB row
4. **BUG-012**: Return 204 No Content (or include `data_available: false` field) when no sentiment data exists

### Phase 2 — LLM Client Integration (3–5 days)

1. Implement `LLMClient.generate()` with Anthropic Claude API (or OpenAI) using `ANTHROPIC_API_KEY` from environment
2. Add startup check that logs a warning if the key is missing and sets `AI_ENABLED=False` globally
3. Wire `analyst_qa_engine.py` → LLM call → return real answer in `research_qa.py`
4. Wire `morning_briefing_engine.py` → LLM call → populate briefing record in `research_briefings.py`
5. Wire `company_primer_engine.py` → LLM call → populate primer in `research_primers.py`
6. Wire `investment_thesis_engine.py` → LLM call → populate thesis in `research_thesis.py`
7. Wire `sentiment.py` → LLM-enhanced scoring (supplement FinBERT, not replace)

### Phase 3 — Async Job Queue (3–5 days)

1. Add a job queue (Celery + Redis, or FastAPI BackgroundTasks for low volume) for:
   - Briefing generation (BUG-004/BUG-022)
   - Anomaly scanning (BUG-006/BUG-024)
   - Primer refresh (BUG-007/BUG-026)
   - Scenario computation (BUG-008)
2. Implement status polling endpoints for all long-running jobs
3. Add frontend polling/SSE integration in `BriefingView.tsx`, `AnomalyView.tsx`, `PrimerView.tsx`

### Phase 4 — Semantic Search Infrastructure (5–7 days)

1. Add `embedding VECTOR(1536)` column to `ResearchDocument` via migration (requires pgvector extension)
2. Create an embedding ingest job that calls OpenAI `text-embedding-3-small` or a local model for all existing + new documents
3. Wire `semantic_search_engine.py` cosine similarity logic to use the stored vectors
4. Fix `suggested queries` endpoint to derive from query history and trending topics

### Phase 5 — FinBERT Ingest Pipeline (2–3 days)

1. Create `scripts/run_sentiment_batch.py` that:
   - Fetches all `NewsItem` and `FilingDocument` records without a `SentimentScore`
   - Calls `finbert_sentiment.analyze_batch()` in chunks
   - Writes `SentimentScore` rows and aggregates `SentimentAggregate` per entity
2. Schedule this via cron or event trigger on new document ingest
3. Add unique constraint on `(entity_id, source_identifier)` in `SentimentScore` (BUG-038)

### Phase 6 — Pillar 3 Batch Runner (1–2 days)

1. Create `scripts/run_intelligence_batch.py` covering:
   - Daily `MorningBriefing` generation
   - `GovernanceScore` computation for all entities
   - `AnomalyAlert` computation for all securities
   - Stale primer refresh (primers older than N days)
2. Add incremental mode (only process entities updated since last run)
3. Per-entity error isolation (BUG-041)

### Phase 7 — Frontend Data Wiring (3–5 days)

1. **MorningBrief.tsx**: Wire `useMacroDashboard()` result to market summary cards (BUG-031)
2. **CompanyIntelligence.tsx**: Render the 6 fetched hook results in their respective sections (BUG-028)
3. **BriefingView.tsx**: Render `useBriefingHistory()` in sidebar (BUG-034)
4. **FilingsView.tsx**: Render `useFilingMDNA()` result in MD&A tab (BUG-030)
5. **GovernanceDashboard.tsx**: Render `useGovernanceProxy()` in proxy table (BUG-029)
6. **ResearchHub.tsx**: Replace hardcoded stats with real aggregate API calls (BUG-032)
7. **AnalystQA.tsx**: Add loading state and error handling to submit (BUG-033)
8. All pages: Add 404/error states for failed API calls (BUG-035)

### Phase 8 — Schema and Infrastructure Hardening (1–2 days)

1. Add unique constraint on `SentimentScore(entity_id, source_identifier)` (BUG-038)
2. Add unique constraint on `CompanyBriefing(entity_id, briefing_type, date)` (BUG-040)
3. Add `expires_at` to `PrimerRefreshLog` and a cleanup job (BUG-039)
4. Add content length validation to research notes endpoint (BUG-014)
5. Add per-user rate limiting middleware on AI endpoints (BUG-043)
6. Remove `try/except pass` from all router imports in `app.py` — fail fast (BUG-044)
7. Fix alert deduplication window (BUG-018)

---

## Appendix: File Reference Index

| File | Issues |
|---|---|
| `src/ai/llm_client.py` | BUG-001 |
| `src/engines/semantic_search_engine.py` | BUG-002 |
| `src/engines/finbert_sentiment.py` | BUG-013 |
| `src/engines/anomaly_detection_engine.py` | BUG-006 (not called) |
| `src/engines/governance_scoring.py` | BUG-019 (not called) |
| `src/engines/morning_briefing_engine.py` | BUG-004 (not called) |
| `src/engines/company_primer_engine.py` | BUG-007 (not called) |
| `src/engines/investment_thesis_engine.py` | BUG-015 (not called) |
| `src/engines/intelligent_alert_engine.py` | BUG-018 |
| `src/api/routers/research_qa.py` | BUG-003, BUG-033 |
| `src/api/routers/research_briefings.py` | BUG-004 |
| `src/api/routers/research_search.py` | BUG-005, BUG-016 |
| `src/api/routers/research_anomalies.py` | BUG-006 |
| `src/api/routers/research_primers.py` | BUG-007 |
| `src/api/routers/research_themes.py` | BUG-008, BUG-025 |
| `src/api/routers/research_thesis.py` | BUG-015 |
| `src/api/routers/company_intelligence.py` | BUG-009, BUG-040 |
| `src/api/routers/sentiment.py` | BUG-011, BUG-012 |
| `src/api/routers/filing_intelligence.py` | BUG-017 |
| `src/api/routers/alerts.py` | BUG-018 |
| `src/api/routers/governance_intelligence.py` | BUG-019 |
| `src/api/routers/earnings_p2.py` | BUG-020 |
| `src/api/app.py` | BUG-010, BUG-044 |
| `src/models/research.py` | BUG-036, BUG-037, BUG-039 |
| `src/models/intelligence.py` | BUG-038, BUG-040 |
| `frontend/src/pages/research/AnalystQA.tsx` | BUG-021, BUG-033 |
| `frontend/src/pages/research/BriefingView.tsx` | BUG-022, BUG-034 |
| `frontend/src/pages/research/SemanticSearch.tsx` | BUG-023 |
| `frontend/src/pages/research/AnomalyView.tsx` | BUG-024 |
| `frontend/src/pages/research/ThemesDashboard.tsx` | BUG-025 |
| `frontend/src/pages/research/PrimerView.tsx` | BUG-026 |
| `frontend/src/pages/research/ThesisBuilder.tsx` | BUG-027 |
| `frontend/src/pages/company/CompanyIntelligence.tsx` | BUG-028 |
| `frontend/src/pages/company/GovernanceDashboard.tsx` | BUG-029 |
| `frontend/src/pages/company/FilingsView.tsx` | BUG-030 |
| `frontend/src/pages/research/MorningBrief.tsx` | BUG-031 |
| `frontend/src/pages/research/ResearchHub.tsx` | BUG-032 |
| `scripts/` (missing) | BUG-041 |
| `src/api/app.py` (env config) | BUG-042, BUG-043 |
