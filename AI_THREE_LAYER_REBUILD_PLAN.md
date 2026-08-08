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

**Next in Phase 0:**
- Tool-use agent loop (`agents/loop.py`) + first tools (`data_query`,
  `web_search`, `citation_check`).
- Guardrails (`citations`, `dates`, `redaction`) + cost-budget enforcement.
- SSE streaming helper (`streaming.py`) for chat/briefings/deep-research.
- Eval harness skeleton (golden examples + LLM-as-judge).
- Then migrate the 9 legacy narrative features off inline prompts onto the
  registry + structured output, and retire `src/services/ai/*`.
