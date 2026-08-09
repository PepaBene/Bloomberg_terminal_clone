# Three-Layer AI Rebuild Plan

> Full teardown and rebuild of the AI stack around three purpose-built layers:
> **(1) Interpreter**, **(2) News / Information**, **(3) Financial Adviser**.
> This plan supersedes `AI_QUALITY_AND_NEWS_PLAN.md` (kept for reference; its
> eval-harness and pgvector ideas are folded in here).

---

## 0. The vision, restated

| Layer | Purpose | Reads | Produces |
|---|---|---|---|
| **1 — Interpreter** | Interpret every individual computed figure the terminal produces (ratios, cash flows, earnings, balance sheet, sector, market, global, macro), its trend, causes and consequences — and how each piece connects to the others. | All analytics/computation tables + `calculation_lineage` (the connection graph). | Grounded, cited **interpretations** attached to every metric/entity/sector/macro subject. |
| **2 — News / Information** (foundation) | Continuously acquire articles, blogs, filings, and alternative information from many sources; score trustworthiness; link to companies/markets/sectors; analyze, interpret, summarize; surface non-consensus / easily-missed signals. Includes an **on-demand deep-research** button and a **no-AI mode** (ranked links from trusted wires). **Owns acquisition of everything Pillar 3 surfaces.** | The web + wires + filings + our entity graph. | Enriched `news_articles`, source-trust scores, cluster analyses, **deep-research reports**, and the qualitative feeds behind Pillar 3. |
| **3 — Financial Adviser** | A conversational agent that suggests concrete actions, grounded in all data, Layer-1 interpretations, Layer-2 news/research, and the user's portfolio. | Everything above + portfolio/risk/performance + the (currently dark) what-if / rebalance / trade-list engines. | Streamed chat + persisted **recommendations** with rationale, impact analysis, and compliance checks. |

A note on **"insider / non-mainstream information"**: this plan implements *legal* edge — non-consensus interpretation, alternative data (job postings, app reviews, shipping, expert commentary, filing-text mining, congressional/insider *disclosures*), and source-corroborated early signals. It explicitly does **not** attempt to obtain or act on material non-public information. See §11 open questions.

---

## 1. Current state (what we are replacing)

**AI client** — `src/ai/llm_client.py` exposes exactly one method: `generate(system, user, max_tokens) → str | None`, delegating to `src/services/ai/claude_client.py` (hardcoded `claude-sonnet-5`). No streaming, no working structured output (`generate_structured` is dead code on a non-standard signature), no retries/backoff, no rate-limit handling, no token/cost tracking, no response cache. The API key is read in three inconsistent places. Prompts are inline f-strings duplicated across 9 routers; there is no prompt registry.

**Embeddings** — `src/services/ai/embedding_client.py` (Google `gemini-embedding-002`, 3072-dim). Stored in `search_documents.embedding_vector` as **JSONB**; similarity is brute-force cosine in Python (`vector_search.py`) over a 5×-overfetch, **no ANN index**. Blocks real semantic scale.

**"AI" engines** — the ~130 files in `src/engines/` are almost entirely deterministic. Real LLM calls happen in 9 routers producing short narrative fields; everything labelled *intelligence / scenario / anomaly / narrative* is heuristic scoring.

**Dormant, high-value code (built, tested, wired to nothing):**
- News: `news_dedup.py` (Jaccard ≥0.8 + 64-bit simhash), `news_entity_linker.py` (ticker/CIK/CUSIP/ISIN → exact → alias → fuzzy cascade, plus topic + materiality classification), `news_propagation.py` (supply-chain/customer/competitive/sector/geographic/macro ripple, 2-hop decay), `finbert_sentiment.py` (real `ProsusAI/finbert` + momentum/anomaly).
- Portfolio: `whatif_engine.py` (pre-trade current-vs-proposed across weights/VaR/factors/compliance/costs), `trade_list_engine.py` (rebalance→orders→CSV/FIX/EMS), `drift_engine.py` (`analyze_drift` + `suggest_rebalance_trades`).
> Wiring these in is the cheapest quality win in the whole plan.

**News reality** — only Finnhub `/company-news`, single-entity linking, short `summary` (no `body_text`), keyword sentiment. No Reuters/Bloomberg/FT/WaPo, no web fetch, no trust scoring, no deep research.

**Pillar 3 reality** — ~150 endpoints across Company / Industry / Competitive / Global-Political / Commodity / Sentiment / News / Governance / Earnings / Filing / Research. Company/Industry/Competitive/Sentiment/single-entity-News compute today (heuristic); Global-macro is US-only; **Governance, Political, Commodity-data, Earnings, Filing-diff, Insiders, Econ-calendar are query-complete but have no ingestion** — they return empty. These gaps are exactly what Layer 2 will fill.

**Schema gaps** — no pgvector, no `ai_call_log`, no conversation/message store, no `users` FK (identity is free-form `user_id` strings). `calculation_lineage` + `analytics_results.inputs` already store derivation lineage — reuse as Layer-1's connection graph.

**Frontend** — React 19 + Tauri desktop, react-query v5, zustand, react-router v7. A non-streaming chat UI already exists (`pages/research/AnalystQA.tsx`, `components/research/QAChat.tsx`) with two integration bugs (posts to `/v3` not `/v4`; reads `answer` not `answer_text`). No SSE anywhere. Mock-with-API-fallback is pervasive (`NewsView`, `MorningBrief`).

---

## 2. Target architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React/Tauri)                             │
│  metric-level "Interpret" popovers · News+Research center · Adviser chat   │
│                         (+ SSE streaming client)                           │
└───────────────┬───────────────────┬───────────────────┬──────────────────┘
                │                   │                   │
        ┌───────▼──────┐    ┌───────▼───────┐   ┌───────▼────────┐
        │  LAYER 1     │    │  LAYER 2      │   │  LAYER 3       │
        │ Interpreter  │    │ News / Info   │   │ Adviser        │
        │  agent       │    │  + Research   │   │  agent (chat)  │
        └───────┬──────┘    └───────┬───────┘   └───────┬────────┘
                └───────────────────┴────────┬──────────┘
                                             │  all three built on ↓
        ┌────────────────────────────────────▼─────────────────────────────┐
        │                      src/ai/  (new AI core)                        │
        │  client(stream,structured,cache,retry) · model router (haiku/     │
        │  sonnet/opus) · prompt registry(YAML,versioned) · tool-use loop · │
        │  retrieval(pgvector HNSW + BM25 hybrid) · guardrails · telemetry · │
        │  cost budgets · SSE                                                │
        └────────────────────────────────────┬─────────────────────────────┘
                                             │
        ┌────────────────────────────────────▼─────────────────────────────┐
        │  DATA: analytics_results · calculation_lineage · fundamentals ·   │
        │  news_articles(+trust) · sentiment · portfolio · Pillar-3 tables ·│
        │  NEW: interpretations · research_reports · news_sources ·         │
        │  ai_call_log · conversations/messages · advice_recommendations    │
        └───────────────────────────────────────────────────────────────────┘
```

The three layers are **agents over one shared AI core**. Layer 2's output feeds Layer 1's qualitative context and Layer 3's evidence; Layer 1's interpretations feed Layer 3's reasoning. Everything is grounded in DB rows with citations.

### 2.1 The new AI core (`src/ai/`) — replaces `src/ai/` + `src/services/ai/`

```
src/ai/
├── client.py            # unified async Anthropic client: stream, structured (tool-forced
│                        #   JSON via Pydantic), prompt-cache markers, retry+backoff, timeout
├── router.py            # task → model tier; per-call override
├── models.py            # tier constants (see 2.2) + pricing table for telemetry
├── prompts/
│   ├── registry.py      # YAML loader, version pinning, cache-control hints
│   └── v1/*.yaml        # every prompt versioned; no inline prompts anywhere
├── retrieval/
│   ├── chunker.py       # semantic-boundary chunking (filings, transcripts, news, notes)
│   ├── embedder.py      # Gemini gemini-embedding-002 (3072); batched, async-wrapped
│   ├── store.py         # pgvector VECTOR(3072) + HNSW; upsert/query
│   └── retriever.py     # hybrid: vector KNN + BM25 lexical, RRF fusion, re-rank
├── tools/               # Claude tool-use tools (shared by all agents)
│   ├── base.py          # Tool protocol + registry
│   ├── data_query.py    # read-only, allow-listed SQL / typed accessors over analytics
│   ├── fundamentals.py  # get statements / ratios / valuation for entity+period
│   ├── analytics.py     # get computed metrics + lineage for a subject
│   ├── filing_lookup.py # fetch a 10-K/10-Q/8-K/proxy section
│   ├── web_search.py    # Anthropic web_search, domain-allowlisted (trusted wires)
│   ├── web_fetch.py     # fetch + readability body extraction
│   ├── portfolio.py     # whatif / drift-rebalance / trade-list / compliance (Layer 3)
│   └── citation_check.py# verify a claim against retrieved/cited rows
├── agents/
│   ├── loop.py          # generic tool-use agent loop (runs until final answer)
│   ├── interpreter.py   # Layer 1
│   ├── researcher.py    # Layer 2 (analysis + deep research)
│   └── adviser.py       # Layer 3 (chat, multi-turn, memory)
├── guardrails/
│   ├── citations.py     # numeric claims must cite a source row/doc
│   ├── dates.py         # reject future-dated facts vs as_of
│   ├── hallucination.py # citation_check pass on entity/number/date claims
│   └── redaction.py     # PII hashing before telemetry
├── telemetry.py         # AICallLogger → ai_call_log; per-user/day token budgets
├── cache.py             # Anthropic prompt cache + Redis full-response cache
└── streaming.py         # SSE envelope for chat + section-streamed briefings
```

### 2.2 Model tiering (current model IDs)

| Tier | Model | Used for |
|---|---|---|
| Light | `claude-haiku-4-5` | per-metric interpretation snippets, per-article summary/sentiment, alert synthesis |
| Synthesis | `claude-sonnet-5` | entity/sector/macro interpretation rollups, news-cluster analysis, briefings, adviser default |
| Deep | `claude-opus-4-8` | deep-research synthesis, high-stakes adviser recommendations, multi-document scenario reasoning |

Embeddings stay **Gemini `gemini-embedding-002` (3072-dim)** but move to pgvector (option to switch to a finance-tuned embedder later — see §11). Routing lives in the prompt registry per feature; users/endpoints can override upward.

---

## 3. Layer 1 — Interpreter

**Goal:** for every computed figure, answer *what it means, where it's trending, why (causes), and what it implies (consequences)* — and connect it to the rest.

### 3.1 Inputs (the "informations")
The interpreter reads the full analytics surface, grouped:
- **Fundamentals & ratios** — `analytics_results` (200+ ratios), `dupont_decompositions`, TTM, `e1_trends` (1/3/5y direction, momentum, z-score).
- **Valuation** — `dcf_results`, `wacc_results`, `comps_results`, `multiple_time_series`, football-field range.
- **Quality/forensic** — Altman / Beneish / Piotroski / `composite_scores`.
- **Risk** — `var_results`, `factor_exposures`, `stress_test_results`.
- **Credit/FI** — `default_risk_scores`, spreads/OAS percentiles, duration, credit ratings, cross-asset signals.
- **Flows/ownership** — `institutional_flow_signals`, `insider_signals`, `ownership_summaries`, smart-money.
- **Technical/quant** — technical studies, β/correlation/stationarity, backtests.
- **Macro/global/sector** — `global_macro_indicators`, macro theme scores, `industry_profiles`/`industry_cycle_positions`, country risk.
- **ESG/governance** — ESG temperature, governance scores.
- **Portfolio** — NAV/performance/attribution/risk snapshots.

### 3.2 The connection graph (key design decision)
Do **not** invent connections. Use two substrates:
1. **`calculation_lineage` + `analytics_results.inputs` JSONB** — already store the exact derivation DAG (which inputs fed which metric). This is machine-truth for equity analytics.
2. A curated **cross-domain edge map** (`src/ai/interpret/graph.py`) for causal links the lineage doesn't encode, e.g.:
   `macro rates → credit spreads → default risk → WACC(Kd) → DCF value`;
   `ratios → DuPont → ROE decomposition`;
   `ownership flows → smart-money → conviction`;
   `sector cycle → company KPIs`; `country risk → geographic revenue → valuation`.

The interpreter walks these edges to produce *connected* insight ("margin compression is driven by X, and because it feeds WACC it lowers the DCF fair value by ~Y").

### 3.3 Process
For a subject (entity, sector/GICS, market, macro region):
1. Assemble metrics + peer/historical context + lineage neighborhood.
2. **Per-metric interpretation** (Light tier, batched, structured output): meaning, trend label, good/bad vs peers & history, primary driver(s) from lineage, confidence, cited source rows.
3. **Connected synthesis** (Synthesis tier): tie the individual reads together along the graph into causes→consequences narrative; flag the 3–5 most decision-relevant links.
4. Attach Layer-2 qualitative context when available (e.g. a news catalyst explaining a metric move).
5. Persist to `interpretations`, cache, and expose.

### 3.4 Output & storage — new `interpretations` table
`(id, subject_type[ENTITY|SECURITY|SECTOR|MACRO|PORTFOLIO], subject_id, scope[METRIC|GROUP|SUBJECT], metric_key, as_of, interpretation Text, trend, direction, drivers JSONB, consequences JSONB, connections JSONB[edges], confidence, citations JSONB, model, prompt_version, ai_enabled, created_at)`.
- Metric-level rows power hover/expand "Interpret this number" popovers everywhere a figure is shown.
- Subject-level rows power an "Interpretation" panel on entity/sector/macro pages.

### 3.5 Execution model
On-demand (entity page → compute-on-miss, cached by `(subject, as_of, analytics_version)`), plus batch nightly for the active universe/watchlists/portfolios, plus event-driven refresh when analytics recompute (hook into `ingestion_progress`/freshness). Reuses the resumable `ingestion_progress` ledger pattern already in the repo.

---

## 4. Layer 2 — News / Information (the foundation)

Delivered in five capabilities. It must work **with and without AI**, and it **owns acquisition for Pillar 3**.

### 4.1 Multi-source ingestion (continuous)
New connectors under `src/ingestion/` writing into a richer `news_articles` (with real `body_text`):
- **Trusted wires / press** — Reuters, Bloomberg, FT, WSJ, AP, Washington Post, CNBC, MarketWatch, Economist via RSS + Anthropic `web_search` (domain-allowlisted) + optional licensed APIs (see §10).
- **Regulatory/primary** — SEC filings-as-news bridge (8-K/10-K/proxy → news feed), Federal Register, central-bank releases; **GDELT articles** into `news_articles` (today it only writes `geopolitical_events`); **NewsAPI.org** as a recall net.
- **PR wires** — Business Wire / PR Newswire / GlobeNewswire.
- **Non-consensus / alternative** — curated finance blogs/Substack, expert commentary, StockTwits/X sentiment, alt-data text (job postings, app-store reviews), earnings-call transcripts (feeds the already-built `analyze_earnings_call`).
- **Body extraction** — readability/trafilatura fills `body_text` (unblocks the dormant dedup/linker/FinBERT engines that need full text).

### 4.2 Trust & credibility (new `news_sources` table)
`(source_name, domain, tier[WIRE|TIER1|TIER2|BLOG|SOCIAL|PR], reliability_weight, region, is_paywalled, notes)`. Per-article **credibility score** = source tier × corroboration count (how many independent trusted sources report the same event within a window) × factuality signals. Non-consensus items are kept but flagged with a confidence discount and a "needs corroboration" state. Trust weight feeds sentiment aggregation and materiality.

### 4.3 Wire the dormant engines (cheap, high-leverage)
Turn on, in the ingestion path: `news_dedup.deduplicate` (URL→Jaccard→simhash), `news_entity_linker.link_entities` (multi-entity, fuzzy, topic, materiality) replacing the connector's single-entity linking, `news_propagation.propagate_event` (writes `propagation_events`), and real FinBERT `score_text` over full `body_text` (with keyword fallback preserved).

### 4.4 AI analysis
Per-article and per-**cluster** (dedup groups related coverage): trust-weighted summary, interpretation, entity/sector/market connections (via propagation graph), materiality, sentiment, and a **"what many miss"** angle (non-consensus read, corroboration status). Light tier per article; Synthesis tier per cluster and for daily/entity digests.

### 4.5 No-AI mode (required)
A deterministic path: for any entity/sector/market, return **ranked links from trusted wires** (Reuters, Bloomberg, FT, WaPo, …) using RSS + allow-listed search + the entity linker + `news_sources` trust ranking — zero LLM. Frontend renders "click through to source." This is the always-on baseline; AI analysis layers on top when enabled/affordable.

### 4.6 On-demand Deep Research (button)
`POST /v5/research/deep` for `{subject_type, subject_id | free_text, focus?}`. A multi-step `researcher` agent (web_search + web_fetch + internal data tools, optionally fanned out) that gathers the **qualitative "later-relevant" information not in our structured data** — management commentary, competitive dynamics, regulatory/political exposure, supply-chain and customer signals, controversies, expert/alternative views — corroborates across sources with trust weighting, and returns a **cited report**. Persist to new `research_reports` `(id, subject, focus, sections JSONB, sources JSONB, confidence, model, created_at, status)`. Streams progress over SSE. (May optionally be run as an internal fan-out for depth.)

### 4.7 Pillar-3 ownership mapping
Layer 2 becomes the acquisition + qualitative-enrichment engine feeding Pillar 3. The quantitative scoring engines (company/industry/competitive intelligence) **stay**, but Layer 2 fills their empty inputs and adds qualitative context, and Layer 1 interprets the results:

| Pillar-3 area | Layer-2 responsibility |
|---|---|
| News, Sentiment | Already Layer 2 — now multi-source + trust-weighted + FinBERT. |
| Governance | Ingest proxy/board/comp (DEF 14A) + red-flag text mining → fills `governance_*` tables. |
| Political / Regulatory | Federal Register, bills, sanctions, enforcement → fills `political_intelligence` tables (today empty). |
| Commodity (context) | Commodity news/supply-demand narrative to complement FRED prices. |
| Earnings (qualitative) | Earnings-call transcripts + guidance narrative → earnings-call sentiment/topics/credibility. |
| Filing intelligence | 8-K classification + year-over-year filing diff **needs full filing text** — Layer 2 stores it and runs the diff. |
| Insiders | Narrative around Form 4 / congressional disclosures; corroborating news. |
| Company/Industry/Competitive | Deep-research + news enrichment attached to the existing heuristic scores; Layer-1 interpretation on top. |

---

## 5. Layer 3 — Financial Adviser

**Goal:** a conversational agent that suggests concrete, grounded actions.

### 5.1 Expose the dark engines (prerequisite)
Wire `whatif_engine`, `drift_engine` (`analyze_drift` + `suggest_rebalance_trades`), and `trade_list_engine` to endpoints, and expose them (plus the live compliance pre-trade check) as **Layer-3 tools**. This alone gives the adviser real "what happens if I do X" and "how should I rebalance" capability that exists today but is unreachable.

### 5.2 The adviser agent
`adviser.py` runs the tool-use loop with access to: portfolio state (positions/NAV/risk/performance/attribution), Layer-1 `interpretations`, Layer-2 news/`research_reports`, analytics tools, and the portfolio-action tools. Given a goal or question it: gathers context → reasons → proposes actions → runs each proposed trade through `whatif` (impact on VaR/factors/costs) and **compliance pre-trade** → returns ranked, cited recommendations.

### 5.3 Chat (multi-turn, streaming)
New `conversations` `(id, user_id, title, created_at)` and `conversation_messages` `(id, conversation_id, role, content, tool_calls JSONB, citations JSONB, tokens, created_at)`. SSE streaming. Reuse the existing `AnalystQA` page + `QAChat` component (fix the `/v3`→`/v5` and `answer_text` bugs), add a dedicated `/adviser` route, and a conversational memory/recall over prior messages.

### 5.4 Recommendations store & guardrails
`advice_recommendations` `(id, user_id, portfolio_id, kind[REBALANCE|RISK|OPPORTUNITY|THESIS|HEDGE], action JSONB, rationale Text, evidence JSONB[links to interpretations/news/analytics], whatif_impact JSONB, compliance JSONB, confidence, status[PROPOSED|ACCEPTED|DISMISSED], created_at)`. Guardrails: every recommendation cites evidence, passes compliance, includes a not-financial-advice disclaimer, and respects per-user cost budgets.

---

## 6. Shared foundation details

- **Structured output** everywhere via tool-forced JSON validated by Pydantic (kills the fragile `LABEL|SCORE|CONFIDENCE` string parsing).
- **RAG / pgvector** — migrate `search_documents.embedding_vector` JSONB → `VECTOR(3072)` + HNSW; hybrid retriever (vector + BM25, RRF). This is the single biggest quality lever and unblocks semantic search, interpretation context, and adviser evidence.
- **Prompt registry** — all prompts YAML-versioned; no inline prompts; A/B-able.
- **Guardrails** — citation enforcement, date consistency, hallucination `citation_check`, PII redaction.
- **Telemetry & budgets** — `ai_call_log` (prompt_id, version, model, tokens, cache_hits, latency, cost, user, feature); per-user/day token ceilings → 429 with `Retry-After`.
- **Caching** — Anthropic prompt-cache on system prompts + large context; Redis full-response cache keyed on `sha256(prompt_id+version+inputs)` with per-feature TTL.
- **Eval harness** — golden examples + LLM-as-judge (faithfulness, citations, hallucination, date-awareness) run in CI; capture baseline before migrating each feature.
- **Failure modes** — API down → fresh cache or structured-only (`ai_enabled=False`); embeddings down → BM25 fallback; web search empty → `[]` with `search_attempted=true`.

---

## 7. Database changes (migrations)

New tables: `interpretations`, `research_reports`, `news_sources`, `ai_call_log`, `conversations`, `conversation_messages`, `advice_recommendations`.
Altered: `search_documents.embedding_vector` → `VECTOR(3072)` + HNSW index (`CREATE EXTENSION vector`); `news_articles` gains populated `body_text`, `source_trust`, `credibility_score`, `cluster_id`, `is_non_consensus`, `corroboration_count`.
Reuse: `ingestion_progress` ledger for interpreter batch + new news connectors. Optionally wire a real `users` FK anchor for conversations/recommendations (today identity is free-form strings).

---

## 8. Frontend changes

- **SSE client** — add streaming to the `fetch` client; `useChat`-style hook for the adviser and section-streamed briefings/deep-research.
- **Layer 1** — "Interpret" popover on any metric; an Interpretation panel on entity/sector/macro pages.
- **Layer 2** — a News/Information center: trusted-source link mode (no-AI) toggle, cluster view, credibility/corroboration badges, and a **Deep Research** button with streamed progress.
- **Layer 3** — a dedicated `/adviser` route (reusing `QAChat`) with streaming, cited recommendations, and inline what-if/compliance results. Fix the two existing QA integration bugs; remove mock-data fallbacks in `NewsView`/`MorningBrief` in favor of honest empty states.

---

## 9. Phased roadmap

| Phase | Scope | Key deliverables | Depends on |
|---|---|---|---|
| **0. Core + eval** | New `src/ai/` core, pgvector migration, prompt registry, tool-use loop, telemetry (`ai_call_log`), guardrails, SSE, eval harness. Delete `src/ai/llm_client.py` + `src/services/ai/*` once callers move. | Streaming structured client; hybrid retriever on pgvector; eval baseline in CI. | — |
| **1. Layer 1** | Interpreter agent, connection graph, `interpretations` table, compute-on-miss + batch, metric popover API. | Grounded per-metric + subject interpretations, cited. | 0 |
| **2. Layer 2** | Multi-source ingestion + `body_text`; `news_sources` trust; **wire dormant dedup/linker/propagation/FinBERT**; no-AI trusted-link mode; AI cluster analysis; **deep-research** endpoint + `research_reports`; Pillar-3 gap ingestion (governance/political/commodity/earnings/filing/insider). | Real multi-wire news, trust scoring, deep research, Pillar-3 fed. | 0 (1 for enrichment) |
| **3. Layer 3** | Expose whatif/drift/trade-list; adviser agent; `conversations`/`messages`; `advice_recommendations`; streaming chat. | Conversational adviser with cited, compliance-checked actions. | 0,1,2 |
| **4. Frontend** | SSE client; interpret popovers; News/Research center; `/adviser` route; fix QA bugs; kill mocks. | The three layers usable end-to-end. | 1,2,3 |
| **5. Hardening** | Guardrail enforcement, cost budgets, failure modes, eval gates per feature, legacy cleanup, docs. | Production-grade. | all |

**Fast early wins (can front-load):** wire the dormant news + portfolio engines; pgvector migration; `ai_call_log`. These are low-risk and unblock everything.

---

## 10. Data sources & cost

- **Free-first path (recommended start):** RSS + Anthropic `web_search` (domain-allowlisted to Reuters/Bloomberg/FT/WSJ/WaPo/AP/…), GDELT, NewsAPI.org, SEC/EDGAR, FRED, Federal Register, OFAC — all already-available or free. Body extraction via readability/trafilatura.
- **Licensed path (optional, later):** official Reuters/Bloomberg/Dow Jones/AP APIs for full-text redistribution rights and lower-latency wires. Materially higher cost; only if the free path proves insufficient.
- **LLM/embeddings:** Anthropic (Haiku/Sonnet/Opus tiered, prompt-cached) + Gemini embeddings; per-feature Redis cache and per-user budgets keep spend bounded. Rough envelope similar to the prior plan: LLM $200–1,500/mo, web_search $50–300/mo, embeddings one-time backfill + incremental, GDELT/NewsAPI/pgvector free.

---

## 11. Decisions & open questions

**Decided (2026-07-09):**
1. **Build order** — ✅ Start **Phase 0** (new `src/ai/` core) now.
2. **News tier** — ✅ **Free-first**: RSS + Anthropic `web_search` allow-listed to Reuters/Bloomberg/FT/WSJ/WaPo/AP, GDELT, NewsAPI, SEC, FRED, Federal Register; readability body extraction. Connectors are written so licensed wire APIs can drop in later.
3. **Information edge** — ✅ Legal alternative data + non-consensus analysis + public disclosures, **plus paid expert-network / primary-research feeds** (still public/legal). Explicitly **no MNPI**. Expert-network integration carries added cost + a compliance-review gate (§4.1, §10).

**Still open:**
4. **Embeddings** — keep Gemini `gemini-embedding-002` (3072) or switch to a finance-tuned embedder (e.g. Voyage-finance)? (Recommend: keep now, revisit in Phase 5.)
5. **Identity** — wire a real `users` FK for conversations/recommendations, or keep free-form `user_id` strings for now? (Recommend: light `users` anchor in Phase 3.)
6. **Eval gating** — block PRs on regression vs nightly report? (Recommend: block on Layer-1/3 features, nightly for the rest.)
7. **Streaming default** — on by default for chat/briefings/deep-research (recommend) vs opt-in.
8. **Expert networks** — which provider(s), and confirm the compliance-review process before that feed goes live.

---

## 12. Build log

### Phase 0 — in progress

**Done & tested (2026-07-09):**
- New AI core under `src/ai/`: `models.py` (tier→model→pricing), `client.py`
  (`AIClient`: async text / tool-forced **structured** output / **streaming**,
  retry+backoff, prompt-cache markers, model tiering, telemetry), `router.py`
  (feature→tier), `prompts/` (YAML versioned registry + `analyst_qa`,
  `sentiment_score`, `interpret_metric` v1).
- Telemetry: `telemetry.py` + `ai_call_log` model + migration `092_ai_call_log.py`
  (corrected from an earlier `084` reference in this log — that was the wrong
  number; migrations landed around/after it in the meantime)
  + daily-token-usage helper (for the budget guardrail).
- `src/ai/llm_client.py` rewritten as a **compatibility shim** over the new core:
  preserves `get_llm_client()` / `.enabled` / `generate(system, user, max_tokens)`
  so all 9 existing LLM routers keep working — now with retries + telemetry.
- Verified: 10 new unit tests pass; all 9 LLM-dependent routers import cleanly;
  graceful degradation holds (no `anthropic` pkg / no key → `enabled=False`,
  helpers no-op) exactly as before.

**Done & tested (2026-08-08):**
- Retrieval/RAG: `src/ai/retrieval/{chunker,embedder,store,retriever}.py`.
  - `chunker.py` — paragraph→sentence→hard-char cascade chunker with **real**
    overlap (the legacy `vector_search.chunk_text` accepted an `overlap` param
    but never applied it) and per-chunk char-offset provenance.
  - `embedder.py` — wraps the existing `EmbeddingClient` (Gemini
    `gemini-embedding-002`), standardized on a new `INDEXED_DIMENSIONS = 1536`
    (requested server-side via the API's `output_dimensionality`, not a
    client-side truncation) — the legacy `embedding` column is 3072-dim, which
    pgvector cannot index (HNSW/IVFFlat cap at 2000 dims; see migration 087's
    own comment on why no index was built then).
  - Migration `094_search_documents_embedding_1536.py` adds
    `search_documents.embedding_1536 vector(1536)` **with a real HNSW cosine
    index** — the first actual ANN index on this table. Legacy `embedding`
    (3072, unindexed) and `embedding_vector` (JSONB) columns untouched.
  - `store.py` — `upsert_chunks` (full-replace per `(source_type, source_id)`,
    ORM insert/delete) + `vector_search` (ORM `.cosine_distance()` against
    `embedding_1536`) + `fetch_candidate_pool` (dialect-agnostic lexical pool).
  - `retriever.py` — hybrid: independent vector-KNN and BM25 (`rank_bm25`)
    rankings fused via Reciprocal Rank Fusion, not a rerank-within-vector-hits
    pass (a ticker/exact-figure query can be a strong lexical match with
    mediocre cosine similarity). `bm25_rank`/`reciprocal_rank_fusion` are pure
    and fully unit-tested; `hybrid_search`/`vector_search` need live
    Postgres+pgvector and a configured `GOOGLE_API_KEY` — **not exercised
    against either in this sandbox** (SQLite test engine remaps `Vector` →
    plain `JSON`, which has no `cosine_distance` comparator at all).
  - Added missing deps to `pyproject.toml`: `anthropic`, `google-genai`,
    `rank-bm25` (used directly), `sse-starlette` (for the next item, SSE
    streaming).
  - 14 new unit tests, all passing (chunker incl. the overlap-actually-works
    regression test, BM25 ranking, RRF fusion, `upsert_chunks` against the
    SQLite test engine). Full `tests/test_ai/` + `tests/test_models/` +
    `tests/test_api/test_research_search_api.py` suites re-verified green.

- Tool-use agent loop (`agents/loop.py`) + first tools (`tools/{base,
  data_query,web_search,citation_check}.py`).
  - `agents/loop.py` — the multi-turn extension `AIClient.complete()` doesn't
    have: calls the model, executes any client `tool_use` blocks via a
    registry, feeds `tool_result`s back, repeats until a final text-only
    answer or `max_iterations`. Duck-typed against an `AIClientLike`
    protocol (not the concrete class) specifically so it's testable with a
    fake client — real Anthropic responses aren't needed to verify the loop's
    control flow.
  - `tools/base.py` documents the split this loop depends on: **client
    tools** (`BaseTool` subclasses, executed locally) vs **server tools**
    (e.g. `web_search`, resolved by Anthropic itself within one response —
    `AIResponse.from_raw()` only collects `type=="tool_use"` blocks, so
    server-tool blocks never reach local dispatch; no special-casing needed).
  - `tools/data_query.py` — one safe typed action (fetch an entity's
    `analytics_results`), not a free-form SQL executor (an LLM-facing raw-SQL
    tool is a real injection risk) — the pattern to extend, not the full
    surface Layer 1's `fundamentals.py`/`analytics.py` will eventually need.
  - `tools/web_search.py` — Anthropic's `web_search_20250305` server tool,
    domain-allowlisted to the wires/regulators decided in §10/§11.
  - `tools/citation_check.py` — `check_claim_support()` (pure token-overlap
    heuristic, not a second LLM call) lets the agent self-check a claim
    against its cited chunk(s) before finalizing; reused as-is by the
    guardrails layer (next item) as a post-hoc enforcement gate.
  - 20 new tests: the loop's control flow (tool execution, message
    threading, unknown-tool/tool-exception handling, max-iterations,
    disabled-client raise, server-tool pass-through) verified against a
    hand-rolled fake client — not just the disabled-path check the earlier
    Phase 0 tests were limited to. `data_query`/`citation_check` DB paths
    verified against the SQLite test engine.

- Guardrails (`guardrails/{citations,dates,redaction,budget}.py`), all pure
  except `budget.check_budget` (DB-backed, reuses the existing
  `telemetry.daily_token_usage`).
  - `citations.py` — `find_uncited_numeric_claims` (any sentence with a
    digit needs *some* `[marker]` citation) + `verify_citations` (for cited
    sentences, does the claim actually hold up against the source text
    behind its marker(s)? reuses `tools/citation_check.py`'s
    `check_claim_support`). Deliberately agnostic to the citation marker
    format — callers supply a `{marker: source_text}` map built from
    whatever they already retrieved, rather than this module assuming
    `search_documents.id` UUIDs appear verbatim in the model's prose.
  - `dates.py` — `find_future_dated_claims` catches the "by 2027"
    hallucination pattern (ISO dates, "Month DD, YYYY", and a conservative
    bare-year fallback), one issue per sentence.
  - `redaction.py` — `redact_names` hashes named individuals (e.g. an
    insider discussed in a Form-4-grounded answer) before telemetry
    persists prompt/response text; same name always redacts to the same
    token, longest-name-first so full names aren't partially clobbered by a
    shorter substring match.
  - `budget.py` — `check_budget` raises `BudgetExceededError` (for an API
    route to turn into 429 + `Retry-After`) once a user crosses
    `DEFAULT_DAILY_TOKEN_BUDGET = 10_000_000`; light-tier calls and
    no-user-context (batch jobs) are exempt; fails open (never raises) if
    the usage lookup itself errors, matching `daily_token_usage`'s own
    fail-to-0 contract — a telemetry outage must not take down the features
    it observes.
  - 23 new tests, all passing (pure-function coverage for citations/dates/
    redaction; `budget` exercised against real `ai_call_log` rows written
    via `record_call` on the SQLite test engine).

- SSE streaming helper (`streaming.py`): `format_sse`/`stream_tokens_as_sse`
  wrap `AIClient.stream()`'s plain text-delta iterator into SSE wire format
  (multi-line data correctly split across repeated `data:` lines, always
  terminated by a `done` or `error` event so the client has a definitive
  end signal even on mid-stream failure). `stream_sections_as_sse` adds
  `section_start`/`section_end` brackets for briefings. `sse_response`
  wraps either in a plain FastAPI `StreamingResponse` (no `sse-starlette`
  dependency needed for the core path — that package stays available in
  pyproject for later if an endpoint wants its ping/reconnect-id support).
  10 new tests, all passing.

- Eval harness skeleton (`evals/{schema,judge,runner}.py` + `evals/golden/`),
  at repo root per this plan's own layout (not under `src/ai/`).
  - `schema.py` — `GoldenExample` (Pydantic) + `load_golden_examples(category)`
    loader; unknown/empty category returns `[]` rather than raising (most
    categories start empty and grow 3-5 examples per feature migration, per
    §2's own convention — not fully authored upfront).
  - `judge.py` — `judge_response()` scores a generated response 0-10 on
    faithfulness / citation correctness / hallucination / date awareness /
    tone via `AIClient.complete_structured` (validated `JudgeScore`, not
    parsed free text). `build_judge_prompt()` is split out pure so the exact
    wording fed to the judge is reviewable/testable without a live call.
  - `runner.py` — `check_deterministic()` (pure: must_include/
    must_not_include/max_tokens) always runs; `run_category()` additionally
    judges each example when a live, enabled client is passed (skips
    gracefully otherwise — usable with no Anthropic key, this sandbox
    included). `save_baseline`/`load_baseline`/`check_regression()` diff a
    run's `avg_judge_overall` against a stored baseline, flagging a
    regression `> 0.5` — the CI gate threshold the superseded plan's
    Phase 0.2 decided on.
  - Seed corpus: 13 real golden examples across all 6 categories (3
    analyst_qa across factual/comparative/scenario types, 2 each for the
    rest) — a working starting corpus + test fixtures, not the plan's full
    target counts (30/10/15/10/20/30 = 115), which are meant to grow
    incrementally as each feature migrates in the next item, same as the
    category-loader's own doc comment says.
  - Fixed a latent gap while here: `PyYAML` was never declared in
    `pyproject.toml` despite `src/ai/prompts/registry.py` already importing
    `yaml` directly (only worked because something else pulled it in
    transitively) — now declared explicitly.
  - 26 new tests, all passing.

- Migrated all 9 legacy narrative routers (10 call sites) off inline
  f-string prompts + `get_llm_client()` onto the registry + `AIClient`, and
  retired what could safely be retired from `src/services/ai/*`.
  - Ported each call site's exact existing system/user prompt text verbatim
    into a new versioned YAML under `src/ai/prompts/v1/` -- this pass changes
    *plumbing* (registry-backed, versioned, routed through `AIClient`'s
    retries/telemetry/prompt-caching), not prompt *content*; rewriting
    prompts with RAG-retrieved context, evals, and a `USE_AI_V2`-gated
    rollout is genuinely Phase 2 work, not this item.
  - `research_qa.py`'s prompt is `analyst_qa_legacy` (not the pre-existing
    `analyst_qa` v1 prompt from Phase 0's first commit) -- that prompt already
    demands `[doc_id]` citations against RAG-retrieved context research_qa.py
    doesn't have yet, so reusing it now would silently change behavior
    (and, unfulfillable, produce citations to nothing) ahead of the real
    Phase 2 migration it was written for.
  - `sentiment.py` moved to `complete_structured` (`SentimentClassification`
    Pydantic model) instead of `complete_text` + the old
    `_parse_llm_sentiment` regex/split parser on a `LABEL|SCORE|CONFIDENCE`
    text line -- this is the "structured output" half of the item, and the
    one call site with a real parser to eliminate. The `sentiment_score`
    prompt got a new v2 (structured-classification framing; v1's
    delimited-format instructions are moot once `complete_structured`
    forces the shape via a tool schema) -- v1 had no production caller yet,
    so nothing's behavior changed underneath it.
  - `research_thesis.py`'s elevator-pitch call got its own new
    `investment_thesis_pitch` feature/tier (SYNTHESIS) rather than reusing
    the existing `investment_thesis` entry (DEEP/opus) -- that tier was
    sized for full thesis generation/validation, not a `<400`-char one-liner;
    forcing it through opus would have been a real, avoidable cost mismatch
    introduced by the migration itself, not preserved legacy behavior.
  - Every other call site reuses an existing `router.FEATURE_TIER` entry for
    telemetry bucketing (`feature=`), with a distinct `prompt_id`/version
    per call site (`AICallRecord` already carries both independently) --
    e.g. `company_primer.py`'s two calls and `research_primers.py`'s one
    all bucket under `feature="company_primer"` for cost tracking while
    keeping separate prompt content.
  - `src/services/ai/` retirement: `claude_client.py` was migrated too
    (`src/ingestion/guidance_extraction.py`'s optional AI-augmentation pass
    was its only other caller -- `client.generate_structured(prompt, model)`
    → `AIClient.complete_structured(response_model=..., user=..., tier=...)`)
    and then deleted, along with the already-dead `vector_search.py` (no
    production caller at all, confirmed by the migration survey -- its
    chunking/cosine-similarity role is now `src/ai/retrieval/`'s). Only
    `embedding_client.py` remains, correctly -- both `src/ai/retrieval/
    embedder.py` and `src/api/routers/research_search.py` still depend on
    it directly, and it was never meant to be replaced (Phase 0's retrieval
    item wraps it, doesn't reimplement it).
  - `tests/test_services/test_ai_services.py` trimmed to just
    `TestEmbeddingClient`; the retired modules' coverage already lives in
    `tests/test_ai/test_retrieval.py` (chunking) and
    `tests/test_ai/test_ai_core.py` (the Claude client).
  - Verified: all 9 routers import cleanly; every new/changed prompt loads
    and renders correctly via the registry; the 9 routers' own API test
    suites pass (149/159 -- the 10 failures are a pre-existing,
    unrelated `CompanyPrimer(primer_id=...)` test-fixture bug in
    `test_research_primers_api.py`, confirmed via `git diff` touching
    neither that test file nor the model, and the model has no `primer_id`
    field at all); `tests/test_ai/` + `tests/test_evals/` + affected
    ingestion/services suites all green.

**Phase 0 complete.** Next: Phase 1 (Layer 1 — Interpreter), which is the
first phase that actually builds on this core end-to-end (connection graph,
per-metric interpretation, the `interpretations` table).

### Phase 1 — complete

- **`interpretations` table** (`src/models/interpretation.py`, migration
  095): polymorphic `subject_type`/`subject_id` (plain strings, not a FK --
  Phase 1 only populates ENTITY subjects, but SECTOR/MACRO/PORTFOLIO are
  real future subject types per §3.1, so a hard FK to `entities` would have
  to be undone later) plus `scope` (METRIC/GROUP/SUBJECT), nullable
  `metric_key` (NULL for GROUP/SUBJECT rows), `as_of`, and
  `analytics_version` -- the freshness fingerprint the cache keys off of.
  Lookup index is intentionally non-unique: a unique index on a nullable
  column doesn't enforce "one row per (subject, scope, as_of)" the way it
  looks like it should (Postgres treats NULLs as distinct), so uniqueness
  is enforced in application code (`store.py`'s upsert-by-lookup) instead
  of being (incompletely) delegated to the schema.
- **Connection graph** (`src/ai/interpret/graph.py`): a small, curated,
  pure-Python graph of causal edges between financial/macro concepts
  (macro rates → credit spreads → default risk → cost of debt → WACC →
  DCF; DuPont ratios → ROE; ownership flows → conviction; sector cycle →
  KPIs; country risk → valuation; ESG → governance → cost of equity) --
  deliberately curated, not learned/inferred, per §3.2's design call: a
  wrong causal edge silently asserted by a model is worse than a smaller
  but trustworthy fixed set. `find_paths`/`connected_subgraph` let the
  interpreter agent pull in only the neighborhood relevant to whatever
  metric it's explaining, not the whole graph.
- **Subject context assembly** (`src/ai/interpret/context.py`):
  `assemble_entity_context` gathers "latest snapshot per metric" across the
  6 of ~10 §3.1 input domains that have confirmed entity_id-direct schema
  linkage (fundamentals/ratios + quality via `AnalyticsResult`, credit via
  `DefaultRiskScore`, ownership via `InsiderSignal`, macro exposure via
  `MacroThemeScore`, ESG/governance via `ESGTemperatureScore` +
  `GovernanceAssessment`). Valuation, security-keyed risk/technical, and
  SECTOR/MACRO/PORTFOLIO subject types are confirmed-real but not yet
  wired -- mechanical follow-ups, not scoped out for design reasons.
  **Design bug found and fixed here during testing:** `as_of` originally
  defaulted to `date.today()`, but `as_of` is part of the cache key
  `store.py` looks up on -- a "today" default would silently mint a
  brand-new, always-a-cache-miss row every single day even when nothing
  in the underlying analytics had changed, defeating compute-on-miss
  entirely. Fixed to derive `as_of` from the data's own latest
  `as_of_date` instead, so the cache key is stable for as long as the
  data is; `analytics_version` (a `count:latest_date` fingerprint) is
  what actually detects a real change and forces recomputation.
- **Interpreter agent** (`src/ai/interpret/interpreter.py`):
  `interpret_metric` (LIGHT tier, one metric + its 1-hop graph neighbors →
  structured `MetricInterpretationOutput` via `complete_structured`) and
  `synthesize_subject` (SYNTHESIS tier, all of an entity's metric
  interpretations → a cross-metric `SubjectSynthesisOutput` narrative).
  `interpret_metrics_batch` runs metrics concurrently
  (`asyncio.gather` + semaphore, best-effort per metric so one bad
  response doesn't sink the batch).
- **Compute-on-miss store** (`src/ai/interpret/store.py`):
  `get_or_compute_entity_interpretation` (full pipeline: reuse any metric
  row whose `analytics_version` still matches, recompute only the
  stale/missing ones, then synthesize the subject narrative once all
  metric outputs are available) and `get_or_compute_metric_interpretation`
  (the lightweight single-metric path for a per-figure "interpret this"
  popover -- doesn't wait on every other metric or the subject synthesis).
  **Second bug found and fixed here:** the single-metric path originally
  fell back to serving the *stale* `existing` row when the AI client was
  disabled or the call failed; that's inconsistent with the entity-level
  path, which simply omits a metric it can't freshly compute rather than
  risk serving a read that may now contradict the current analytics.
  Fixed to return `None` in both cases, and locked in with a regression
  test (`test_get_or_compute_metric_stale_cache_with_disabled_client_returns_none_not_stale_row`).
- **API** (`src/api/routers/interpret.py`, registered at `/v5` in
  `app.py` -- the plan's own version prefix for Three-Layer endpoints):
  `GET /interpret/entities/{entity_id}` (full compute-on-miss sweep +
  subject synthesis) and `GET /interpret/entities/{entity_id}/metrics/{metric_key}`
  (single-metric popover; 404 for an unknown metric, 503 when nothing
  cached and the AI client is unavailable to compute one).
- **Nightly batch job** (`scripts/interpret_batch.py`, registered in
  `src/scheduler/batch_config.py` as `interpreter_batch`, `0 9 * * *`,
  domain `AI`, `sla_minutes=1440`): resumable via the same
  `ingestion_progress` raw-SQL ledger pattern `scripts/backfill.py` already
  established for every other resumable batch type (`data_type="interpreter"`,
  `subject_key=str(entity_id)`). Universe defaults to every entity with at
  least one `portfolio_watchlist_entries` row (the "active universe" §3.5
  calls for), with `--entity-ids`/`--all`/`--limit` overrides for manual
  runs and a small test universe respectively. Because
  `get_or_compute_entity_interpretation` already skips the LLM entirely
  for any metric whose cached row is still fresh, a nightly re-run against
  an unchanged entity is cheap -- the job is really sweeping for
  newly-stale or never-interpreted entities, not doing a full nightly
  recompute of everything. Portfolio *holdings* (`positions`) are
  confirmed NOT yet folded into the universe -- `Position` has no direct
  `entity_id` column, only a ticker/security keyed to a portfolio, so
  folding holdings in needs an extra `Security.issuer_entity_id` join this
  pass doesn't do. `scripts/interpret_batch.py` itself, like
  `scripts/backfill.py`, has no direct unit test coverage: its Postgres-only
  raw SQL (`bindparam(expanding=True)`, `ON CONFLICT`, `CAST(... AS
  timestamptz)`) doesn't compile against the SQLite test engine, so it was
  verified via `py_compile` + `ast.parse` instead, consistent with the
  precedent already set for `backfill.py`.
- Verified: `tests/test_models/test_interpretation.py` (3),
  `tests/test_ai/test_interpret_graph.py` (17),
  `tests/test_ai/test_interpret_context.py` (14),
  `tests/test_ai/test_interpreter.py` (21),
  `tests/test_ai/test_interpret_store.py` (14, including the two
  regression tests for the caching bugs above), and
  `tests/test_api/test_interpret_api.py` (7) all green (76/76). The only
  `tests/test_scheduler/test_batch_config.py` failures are the same
  pre-existing, unrelated "missing analytics_* jobs" gaps already present
  before this phase (confirmed via `git stash` diff -- untouched by the
  `interpreter_batch` entry).

**Phase 1 complete.** Next: Phase 2 (Layer 2 — News/Information), per the
roadmap -- not started without explicit direction, matching how Phase 1
itself waited for confirmation after the Phase 0 recap.

### Phase 2 — complete

A background infrastructure survey (before writing any code) found the
plan's own premise partly out of date: 4 of the 5 "dormant engines" §4.3
asks to wire up (`news_dedup`, `news_entity_linker`, `news_propagation`,
`finbert_sentiment`) already existed as fully-built, fully-tested, pure
computation modules with **zero production callers** -- `finnhub_news.py`
reimplemented a cruder single-entity link inline instead of calling
`news_entity_linker`. `propagation_events`, the table §4.3 implies needs
creating, already existed and was migrated (051). Phase 0's `embedding_1536`
column already supersedes §6.2's `search_documents.embedding_vector ->
VECTOR(3072)` migration item. This reframed most of Phase 2 into *wiring*
existing engines rather than new engineering -- reflected below.

- **§4.2 Trust & credibility**: new `news_sources` table (reference/lookup
  table, natural-key PK like `Currency`/`Exchange`, seeded from
  `data/news_sources.json` via the established `reference_loader.py`
  pattern) + `news_articles` gains `source_trust`/`credibility_score`/
  `cluster_id`/`is_non_consensus`/`corroboration_count`. New
  `src/engines/news_credibility.py`: `find_cluster_match` reuses
  `news_dedup`'s URL/title-Jaccard/simhash tiers as a "does this
  corroborate an existing article" query rather than `deduplicate()`'s
  "drop duplicates" -- Layer 2 wants every article kept, just clustered.
  `cluster_id` is self-referential (a representative's row points at
  itself), so "every article has a cluster_id" holds uniformly once
  enriched.
- **§4.3 Wire the dormant engines**: `src/ingestion/news_enrichment.py`
  orchestrates all four into `finnhub_news.py`'s ingestion path:
  `build_entity_lookup` (ticker/CUSIP/ISIN resolve via `Security.
  issuer_entity_id`, NOT `EntityIdentifier` -- those are security-level,
  only CIK is entity-level) feeds real multi-entity `link_entities`
  (replacing the crude single-link); corroboration clustering +
  credibility scoring per article; real FinBERT `score_text` (keyword
  fallback preserved, per the engine's own existing degrade path);
  entity-to-entity propagation (SUPPLY_CHAIN/CUSTOMER/COMPETITIVE hop-1
  via real `BusinessRelationship` rows -- SECTOR/MACRO propagation
  deferred, needs a full GICS-sector entity roster this pass doesn't
  build).
- **§4.1 body_text extraction**: `src/ingestion/article_extraction.py`,
  trafilatura-based, unblocking dedup's content-fingerprint tier, FinBERT,
  and entity linking, all of which degrade to title+summary without it.
- **§4.5 No-AI mode**: deterministic ranked-links endpoint (RSS + trust
  ranking, zero LLM) -- the always-on baseline the plan requires.
- **§4.1 Multi-source ingestion**: three connectors bridging existing
  regulatory/geopolitical data into `news_articles` (which nothing wrote
  into before except Finnhub): SEC filings-as-news, GDELT articles (GDELT
  previously only wrote `geopolitical_events`, confirmed via survey),
  Federal Register regulatory actions.
- **§4.4 AI analysis**: two-phase per-article (LIGHT tier, trust-weighted
  summary/interpretation/non-consensus-angle, connections grounded in
  this article's own `PropagationEvent` rows) and per-cluster (SYNTHESIS
  tier, consensus vs. divergent views across a cluster's corroborating
  coverage -- rides on the representative article's row since a cluster
  has no owning row of its own) analysis, both compute-on-miss cached
  directly on `news_articles`.
- **§4.6 On-demand Deep Research**: new `research_reports` table +
  two-phase `gather_research` (multi-step `run_agent` tool loop -- new
  `web_fetch` client tool alongside the existing `web_search` server
  tool and `data_query`, DEEP tier) then `structure_report` (separate
  `complete_structured` synthesis pass over the gathered transcript).
  `run_agent` gained an optional `on_step` hook (its first production
  caller) so `POST /v5/research/deep` can stream progress over SSE via an
  `asyncio.Queue` bridge, using its own `get_session_factory()` session
  rather than the request-scoped one (FastAPI tears down `Depends`
  generators before a `StreamingResponse`'s body actually runs).
- **§4.7 Pillar-3 follow-through**: of the table's 8 rows, News/Sentiment
  and Political/Regulatory were covered above; Filing intelligence and
  Earnings (qualitative) already had live engines (`EdgarFilingDiffConnector`,
  `analyze_earnings_call`) predating this phase. **Governance** was the
  one row confirmed genuinely empty: `governance_assessments` had zero
  writers despite `src/engines/governance_scoring.py` -- a full, tested,
  10-red-flag scoring engine -- already existing with no caller, same
  "built but dormant" pattern as §4.3's four engines. New
  `scripts/compute_governance_assessments.py` wires it: per proxy filing,
  derives board independence/tenure/diversity/interlocks from
  `board_members`, CEO pay-ratio/LTIP-mix from `executive_compensation`,
  and scores via the existing engine. Five structural red flags
  (dual-class, poison pill, staggered board, majority voting,
  related-party) need DEF 14A prose the current ingestion doesn't parse
  -- deliberately left un-guessed (the engine's own `.get(key)` semantics
  already treat an absent key as "no evidence," except
  `has_majority_voting`, which the engine itself defaults to flagging
  when unknown). Commodity narrative and insider/congressional-disclosure
  narrative bridging are the two rows genuinely not attempted in this
  pass -- real, scoped follow-ups, not silently dropped.
- The survey's other correction: `political_intelligence`'s three tables
  (`legislative_bills`/`regulatory_actions`/`sanctions_entries`) already
  had live, scheduled ingestion contrary to the plan's "today empty"
  assumption -- confirmed by reading the actual connector code and
  scheduler registration, not just the model definitions.
- Verified across the phase: every increment landed with its own test
  suite (news_sources/credibility: 28, enrichment pipeline: 17, no-AI
  mode + multi-source connectors: covered in their own commits, article
  analysis: 22, cluster analysis: 28, Deep Research: 25, governance
  scoring: 9) plus broad `tests/test_ai/`, `tests/test_api/`,
  `tests/test_models/` sweeps after each commit, all green against the
  same pre-existing, unrelated failure set already documented in Phase 0/1
  (`CompanyPrimer(primer_id=...)` fixture bug, `test_batch_config.py`'s
  missing `analytics_*` job entries).

**Phase 2 complete.** Next: Phase 3 (Layer 3 — Financial Adviser), per the
roadmap -- not started without explicit direction.

### Phase 3 — complete

A pre-work survey (same discipline as Phase 2's) found the exact same
"built but dormant" pattern again: `whatif_engine.py`, `drift_engine.py`,
`trade_list_engine.py`, and `compliance_engine.py` are all fully-built,
tested, pure-computation modules with zero production callers. Pre-trade
compliance DOES have a live, tested endpoint
(`portfolio_risk.py::pre_trade_check`) -- but it's ~90 lines of inline
rule evaluation duplicating what `compliance_engine.py` already does, not
a call into that module. The survey also found the existing
`/v4/portfolios/{id}/drift` endpoints are read-only over a `DriftSnapshot`
row that nothing in this codebase ever actually computes -- `POST
.../drift/target` only ever writes zeros, so "current drift" has never
been a real number anywhere in this app until this phase.

- **§5.1 Expose the dark engines**: `src/services/portfolio_advisory.py`
  wires all three engines to live `Position`/`Portfolio`/
  `ComplianceRule`/`PortfolioVarSnapshot`/`DriftSnapshot` data --
  `compute_whatif`, `compute_drift` (the actual fix for the
  never-computed-drift gap above), `build_trade_list`, and
  `check_pretrade_compliance` (the existing live endpoint's rule logic,
  *extracted* so the endpoint and the new adviser tool share one
  implementation instead of two that could drift apart -- verified
  against the endpoint's own existing, unmodified tests). New
  `POST /v5/portfolios/{id}/{whatif,drift-analysis,trade-list}` expose
  these directly; new `src/ai/tools/portfolio.py`
  (`PortfolioSnapshotTool`/`WhatIfTool`/`DriftAnalysisTool`/
  `PreTradeComplianceTool`) expose the identical service functions as
  Layer-3 agent tools, so a human hitting the API and the adviser
  reasoning about a trade always see the same numbers. Documented,
  deliberate gaps: no per-ticker factor loadings or VaR/correlation data
  in this app (whatif's risk/factor dimensions degrade to the engine's
  own documented fallbacks), `Position` has no `sector` column (drift's
  sector dimension is skipped).
- **§5.2 The adviser agent**: three new context tools
  (`src/ai/tools/entity_context.py`) give the adviser read access to
  Layer 1 (`InterpretationLookupTool`) and Layer 2
  (`RecentNewsTool`/`ResearchReportLookupTool`) -- pure reads, never
  triggering new AI computation mid-conversation. `src/ai/adviser/
  adviser.py` is two-phase, matching this codebase's established
  gather-then-structure pattern: `gather_advice` (`run_agent` at
  SYNTHESIS tier with all the above tools + `WhatIf`/`DriftAnalysis`/
  `PreTradeCompliance`/`DataQuery`/web_search) then
  `extract_recommendations` (a separate `complete_structured` call at
  DEEP tier over the transcript, pulling out zero or more concrete
  recommendations -- zero is a valid, common outcome for a purely
  informational turn). The one design point worth restating: `verify_
  recommendation` re-runs the REAL `whatif`/`compliance` checks against
  live data for any recommendation with a well-formed trade action,
  never trusting the LLM's own account of what its tools said
  mid-conversation -- the same "never trust the model for a number it
  could look up" principle every other layer in this codebase follows.
  `run_agent` (built in Phase 2.7, one caller so far) gained its second
  production caller here.
- **§5.3 Chat**: new `conversations`/`conversation_messages` tables.
  `POST /v5/adviser/conversations/{id}/messages` streams over SSE
  (`step` events per agent turn, then a terminal `done` with
  `{reply, disclaimer, recommendations}` or `error`) -- same
  own-session-via-`get_session_factory()` shape Phase 2.7 established,
  plus the cost-budget guardrail (`guardrails/budget.py::check_budget`,
  built in Phase 0, never previously wired to any caller) as a
  pre-flight check before the agent loop starts. "Conversational
  memory/recall" is prior turns rendered as a text transcript prepended
  to the new message, since `run_agent` only takes a single seed `user`
  string. Frontend: fixed both bugs the plan named in `QAChat.tsx`
  (wrong endpoint prefix -- turned out to be `/v3` vs. the REAL mount
  point `/v4`, not `/v5` as the plan assumed, since that's the
  *existing* `research_qa.py` Q&A endpoint, not this phase's new chat;
  and `answer_text`, which the component read as `data.answer`, a field
  that doesn't exist on `QAResponse`) and the same field-name bug in
  `AnalystQA.tsx`. A dedicated `/adviser` frontend route was not built --
  this session's Phase 0-3 work has been backend-only throughout, and
  building a new page is a distinct, larger effort than fixing two
  existing field-name bugs.
- **§5.4 Recommendations store & guardrails**: new `advice_recommendations`
  table. `src/ai/adviser/store.py` enforces two of the four guardrails
  as a hard filter before persistence: a recommendation with no cited
  evidence is dropped (same standard `guardrails/citations.py` already
  enforces elsewhere), and one whose real (not LLM-reported) compliance
  check came back not-approved is dropped. The other two guardrails are
  enforced elsewhere: cost budgets pre-flight in the chat endpoint
  (§5.3), the not-financial-advice disclaimer is a fixed constant
  attached to every chat response rather than baked into stored
  rationale text.
- **A real bug caught and fixed along the way**: `src/ai/research/
  store.py`'s `run_and_persist_research` (built in Phase 2.7) only ever
  called `session.flush()`, never `session.commit()`, inside the SSE
  streaming generator's own per-run session. Verified directly (flush +
  close a session, then read from a fresh one off the same factory --
  the row is gone) that this meant every completed Deep Research
  report's actual content was silently never persisted; only the
  initial PENDING row (committed separately, at the request-scoped
  session level, before streaming even starts) ever survived. Fixed by
  committing after each state transition, which also makes progress
  durable if the process dies mid-run rather than only at the very end.
  Caught while building this phase's own, correctly-committing chat
  streaming endpoint and noticing the asymmetry with the precedent it
  was copying.
- Verified across the phase: whatif/drift/trade-list service layer (26
  tests) + advisor API (9) + portfolio tools (11), adviser agent (14) +
  context tools (11), recommendations store (12) + model (2), chat
  conversation store (6) + API (8) + models (3) -- 102 new tests total.
  Broad sweeps after every commit: `tests/test_ai/` + `tests/test_models/`
  + `tests/test_services/` + the affected API suites +
  `tests/test_scheduler/`, consistently green against the same
  pre-existing failure set documented since Phase 0 (`CompanyPrimer(
  primer_id=...)` fixture bug, `test_batch_config.py`'s missing
  `analytics_*` job entries) -- zero regressions introduced across all
  four sub-phases.

**Phase 3 complete. All three layers of AI_THREE_LAYER_REBUILD_PLAN.md are
now built** (Layer 1 — Interpreter, Layer 2 — News/Information, Layer 3 —
Financial Adviser). Remaining work per the plan is polish/breadth, not new
layers: §6's shared-foundation items not yet exercised end-to-end (Redis
response caching, prompt-cache verification under load, the eval harness
running in CI rather than ad hoc), §8's frontend changes (this session's
work has been backend-only throughout -- new endpoints exist with no UI
wired to most of them yet), and the explicitly-deferred gaps documented
inline through Phases 2-3 (SECTOR/MACRO news propagation, per-ticker
factor/VaR data for whatif, DEF 14A structural-provision text-mining for
governance red flags, commodity/insider-narrative Pillar-3 bridging).
