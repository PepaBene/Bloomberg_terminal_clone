# AI Quality Rebuild + Reuters / Bloomberg Web Search

## Goals & decisions

| Decision | Chosen |
|---|---|
| News data tier | Free + AI web search (Anthropic `web_search` + GDELT + NewsAPI.org, restricted to reuters.com / bloomberg.com / ft.com / wsj.com) |
| Quality scope | Rebuild the `src/ai/` stack from scratch — RAG, agents, tool use, streaming |
| Eval scope | Golden examples + LLM-as-judge regression suite |

The plan is organised so every phase ships something testable.
Phases 0–2 are pre-requisites for the rebuild; Phases 3–5 are the
rebuild itself; Phase 6 is the news layer; Phase 7 is hardening.

Total elapsed time estimate: **~9–12 weeks for one engineer** (roughly
half quality rebuild, half web search + ingestion + hardening).

---

## Phase 0 — Eval harness and observability *(week 1)*

You can't improve quality you can't measure. Build the ruler first.

### 0.1 Golden examples

```
evals/
├── golden/
│   ├── analyst_qa/                # 30 Q&A pairs across factual / comparative / scenario types
│   ├── morning_briefing/          # 10 portfolios × expected headline ranking
│   ├── company_primer/            # 15 companies × expected sections/facts
│   ├── investment_thesis/         # 10 thesis examples × expected drivers/risks
│   ├── anomaly_narrative/         # 20 anomaly events × expected narrative properties
│   └── semantic_search/           # 30 queries × expected document hits
└── runner.py                      # async batch runner with snapshot diffing
```

Each example is a YAML with `inputs`, `must_include`, `must_not_include`,
`max_tokens`, `expected_citations[]`, and a free-text `notes` rubric for
the LLM judge.

### 0.2 LLM-as-judge

A second Claude call grades each output against rubric criteria
(faithfulness to source, citation correctness, hallucination check,
date awareness, tone). Score 0–10 per criterion; CI fails on regression
> 0.5 from the baseline.

### 0.3 Cost & latency telemetry

Every LLM call goes through a tracer that records `prompt_id`,
`prompt_version`, `model`, `input_tokens`, `output_tokens`, `cache_hits`,
`latency_ms`, `cost_usd` to a new `ai_call_log` table. Dashboards built
on top expose:

- p50 / p95 / p99 latency per feature
- $/feature/day
- cache hit rate
- regression rate (eval failures over time)

### 0.4 Deliverables

- [ ] `evals/runner.py` runs on every PR
- [ ] CI gate: eval score regression > 0.5 fails build
- [ ] `ai_call_log` table + middleware
- [ ] Grafana / Datadog dashboard (or simple HTML report)

---

## Phase 1 — New `src/ai/` foundation *(weeks 2–3)*

Replace `src/ai/llm_client.py` and `src/services/ai/{claude,embedding}_client.py`
with a layered stack.

```
src/ai/
├── __init__.py
├── client.py                 # Claude wrapper (sync/async, streaming, structured)
├── router.py                 # Model tiering: haiku → sonnet → opus
├── prompts/
│   ├── registry.py           # YAML loader, version pinning
│   └── v1/                   # versioned prompt files
│       ├── analyst_qa.system.yaml
│       ├── morning_briefing.system.yaml
│       ├── company_primer.system.yaml
│       └── ...
├── retrieval/
│   ├── chunker.py            # text → chunks (semantic-aware splits, not naive)
│   ├── embedder.py           # Gemini Embedding 2 wrapper, batched
│   ├── store.py              # pgvector-backed similarity search
│   └── retriever.py          # top-k + re-ranker (BM25 hybrid)
├── tools/
│   ├── base.py               # Tool protocol for Claude tool_use loop
│   ├── web_search.py         # Anthropic web_search tool wrapper
│   ├── sql_query.py          # safe read-only SQL over the DB
│   ├── filing_lookup.py      # fetch a 10-K/10-Q/8-K section by entity+year
│   └── citation_check.py     # verify a claim against retrieved chunks
├── guardrails/
│   ├── citation_required.py  # every numerical claim must cite a source_id
│   ├── pii_filter.py         # redact insider personal info before logging
│   └── date_consistency.py   # reject responses with future-dated facts
├── cache.py                  # Anthropic prompt-cache + Redis full-response cache
└── streaming.py              # SSE response wrapper for chat endpoints
```

### 1.1 Prompt registry

```yaml
# src/ai/prompts/v1/analyst_qa.system.yaml
version: 1
model: claude-sonnet-4-6
max_tokens: 4096
temperature: 0.2
cache: true
system: |
  You are a Bloomberg-style financial research assistant. You answer
  questions only using the documents provided in the <context> tags.
  Every numerical claim must be followed by a citation in [doc_id]
  format. If the context does not contain the answer, say so —
  do not speculate, do not use prior knowledge.
input_schema: AnalystQARequest
output_schema: AnalystQAResponse
```

Loader: `prompts.load("analyst_qa", version=1)`. Old versions are
preserved so we can A/B test changes.

### 1.2 Retrieval (RAG)

The single biggest quality win. Most current AI features pass
structured DB rows to the LLM but not the underlying text — so the
model has to invent prose from numbers. RAG flips that:

1. **Ingest-time:** every filing section / earnings transcript turn / news
   article / research note gets chunked (~500 tokens, semantic boundaries),
   embedded, stored in `search_documents` with a `pgvector VECTOR(3072)`
   column (replacing the current `JSONB` per the audit's M-001).
2. **Query-time:** retriever pulls top-20 chunks with cosine similarity,
   re-ranks via BM25 lexical match for ticker / number queries, returns
   top-6 to the LLM with full provenance metadata.
3. **Citations:** prompt requires `[doc_id]` after each claim; a
   post-processor verifies every citation actually appears in the
   retrieved set and rejects ungrounded responses.

### 1.3 Model routing

| Tier | Model | Used for |
|---|---|---|
| Light | claude-haiku-4-5 | anomaly narratives, alert summaries, single-paragraph commentary |
| Synthesis | claude-sonnet-4-6 | morning briefings, Q&A, primers, thesis text, semantic search synthesis |
| Heavy | claude-opus-4-7 | thesis validation, multi-document scenario analysis, on-demand by user |

Routing is per-feature in the prompt registry; users can override.

### 1.4 Tool-use loop

Claude's tool-use API (not just plain prompts) lets the model:
- decide to call `filing_lookup(entity_id, "ITEM_1A", year=2024)` mid-response
- request `sql_query("SELECT * FROM analytics_results WHERE …")` to get fresh numbers
- run `web_search(...)` to confirm a recent event
- call `citation_check([claim])` before finalizing the response

Implementation: a single `agent.run(prompt, tools=[…])` helper that
loops on `tool_use` blocks until the model emits a final answer.

### 1.5 Streaming

All chat endpoints (`/v4/research/qa/ask`, `/v4/research/qa/follow-up`)
become SSE. Briefings stream section-by-section.

### 1.6 Caching

- **Anthropic prompt cache:** mark system prompts and large context
  blocks (>1024 tokens) as cacheable for ~10× cost reduction on repeat
  requests
- **Redis full-response cache:** key on `sha256(prompt_id + version +
  serialized_inputs)`, TTL by feature (briefings: 1h, primers: 24h,
  Q&A: no cache)

### 1.7 Deliverables

- [ ] `src/ai/` skeleton merged
- [ ] pgvector migration (`embedding_vector` column → `VECTOR(3072)`)
- [ ] `prompts/v1/*.yaml` for 12 features
- [ ] Tool-use agent runs on `/v4/research/qa/ask` end-to-end
- [ ] Streaming `/v4/research/qa/ask` with SSE
- [ ] Eval baseline captured before any feature migrates

---

## Phase 2 — Migrate every existing AI feature *(weeks 4–6)*

For each feature: write the new prompt, update the engine to retrieve
context and call the new agent, run the eval suite, ship behind a
`USE_AI_V2` flag, flip the flag once eval scores ≥ baseline + 1.0.

Migration order (cheapest to most complex):

1. **Anomaly narratives** (`anomaly_detection_engine`) — short, single-fact
2. **Earnings surprise commentary** (`earnings_surprise_intelligence`)
3. **Filing diff summaries** (`filing_diff`)
4. **Cross-asset narratives** (`cross_asset_narrative`)
5. **Intelligent alert synthesis** (`intelligent_alert_engine`)
6. **Company primers** (`company_primer_engine`) — multi-section
7. **Morning briefings** (`morning_briefing_engine`) — personalized, retrieval-heavy
8. **Investment thesis** (`investment_thesis_engine`) — high-stakes, opus tier
9. **Macro themes & scenarios** (`macro_thematic_engine`, `macro_scenario_engine`)
10. **Analyst Q&A** (`analyst_qa_engine`) — most complex, fully agentic
11. **Semantic search** (`semantic_search_engine`) — replace cosine-only with hybrid retriever + LLM synthesis
12. **FinBERT sentiment** — keep FinBERT but add a Sonnet "second opinion"
    layer that scores ambiguous cases (probability gap < 0.3)

Each migration commit:
- Adds a versioned prompt YAML
- Updates the engine to use `agent.run`
- Adds 3–5 new golden examples specific to that feature
- Updates the model routing entry
- Removes the legacy template fallback (template still lives in the
  prompt as the user-prompt skeleton, but synthesis is LLM-driven)

### Deliverables

- [ ] All 12 features routed through `src/ai/`
- [ ] Legacy `src/ai/llm_client.py` and `src/services/ai/*` deleted
- [ ] Eval scores ≥ baseline + 1.0 on every feature
- [ ] User-visible: every `ai_*` field is now grounded in citations

---

## Phase 3 — Web news ingestion *(weeks 7–8)*

Three layered sources, populating the existing `news_articles` and
`article_entity_links` tables so the rest of the pipeline (FinBERT
sentiment, entity linking, briefings, watchlist alerts) automatically
picks them up.

### 3.1 Anthropic `web_search` tool *(primary, on-demand)*

```python
# src/ai/tools/web_search.py
WEB_SEARCH_DOMAINS = [
    "reuters.com", "bloomberg.com", "ft.com", "wsj.com",
    "marketwatch.com", "cnbc.com", "barrons.com", "economist.com",
    "sec.gov", "federalreserve.gov", "ecb.europa.eu", "bankofengland.co.uk",
]

WebSearchTool = {
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": 5,
    "allowed_domains": WEB_SEARCH_DOMAINS,
}
```

Surfaced to users as a new endpoint:

```
POST /v4/research/news/search
{
  "query": "fed pivot inflation expectations",
  "entity_id": "...",            # optional: scope to entity
  "from_date": "2025-04-01",     # optional
  "max_results": 10
}
```

Server:
1. Calls Claude with `web_search` tool enabled and the domain allowlist
2. Claude searches, reads, summarizes, returns a structured list of
   articles with `url`, `title`, `source`, `published_at`, `summary`,
   `sentiment`, `entities_mentioned`, `citations`
3. Server inserts each result into `news_articles` (deduped by URL)
4. Returns the structured response to the client

### 3.2 GDELT real-time event ingestion *(continuous, bulk)*

GDELT publishes a new event file every 15 minutes free of charge —
~3M global news events / day with entity tags, tone scores, and event
codes. We ingest the firehose and filter for our universe:

```
src/ingestion/gdelt_news.py
scripts/ingest_gdelt.py          # runs every 15 min via scheduler
```

Filters:
- Only events tagging an entity in our `entities` table (by name match
  or LEI / ticker if available)
- Only sources on our financial-news allowlist
- Pushes into `news_articles` with `news_type='realtime_feed'`

### 3.3 NewsAPI.org *(daily backfill)*

Free tier: 100 requests/day, headlines + URLs only (no full body).
Used as a recall safety net so we don't miss a major event GDELT and
the on-demand search both happen to skip:

```
src/ingestion/newsapi_news.py
scripts/ingest_newsapi.py        # runs nightly
```

Per ticker on the watchlist or in any active portfolio:
- Pull top 10 headlines from the past 24h
- Dedupe vs. existing `news_articles.url`
- Insert with `news_type='headline_only'` (frontend renders a "click
  through to source" link instead of a body)

### 3.4 Watchlist + entity-page integration

Once articles flow into `news_articles`:
- Existing FinBERT pipeline (Phase 1's enhanced version) scores them
- `watchlist_monitoring.evaluate_watchlist_alerts` already detects news
  alerts — it now sees real Reuters/Bloomberg headlines instead of empty
- `morning_briefing_engine` now has overnight news to summarize
- Entity pages (`CompanyOverview`, `CompanyIntelligence`) get a
  "Recent news" section pulled from `news_articles WHERE entity_id=…`

### 3.5 Background "watch" jobs

For every entity in any user's watchlist, schedule a once-an-hour
web_search query for breaking news. Results feed alerts.

### Deliverables

- [ ] `src/ai/tools/web_search.py` integrated into agent
- [ ] `POST /v4/research/news/search` endpoint shipping
- [ ] `src/ingestion/gdelt_news.py` running every 15 min
- [ ] `src/ingestion/newsapi_news.py` running nightly
- [ ] Hourly watchlist news watch job
- [ ] Frontend "Recent News" panel on entity pages with cite-back links
- [ ] Eval suite extended with 20 web-search Q&A pairs

---

## Phase 4 — Hardening *(week 9)*

### 4.1 Guardrails

- **Citation enforcement:** reject responses where any sentence with a
  number lacks a `[doc_id]` citation (regex check + secondary LLM check)
- **Hallucination check:** for every claim about a company / number /
  date, run a `citation_check` tool call; if the cited doc does not
  contain the claim, regenerate
- **Date consistency:** strip / refuse responses with dates after
  `today` (catches "by 2027" hallucinations on stale prompts)
- **PII redaction:** hash insider names in `ai_call_log` to keep
  audit logs PII-clean

### 4.2 Cost ceilings

Per-user / per-tenant daily token budget enforced at the
`AICallLogger` level; 429 with `Retry-After` when exceeded.
Default: 10M tokens/user/day on Sonnet, unlimited on Haiku.

### 4.3 Failure modes

- Anthropic API down → cached response if fresh, else structured-only
  response with `ai_enabled=False`
- Web search returns no results → endpoint returns `[]` with
  `search_attempted=true` (not 404)
- Embedding service down → semantic search falls back to BM25
  (lexical) over the same `search_documents` table

### 4.4 Migration cleanup

- Drop the `src/ai/llm_client.py` shim
- Drop the `src/services/ai/` submodule
- Update `CONNECTING_TO_REAL_DATA.md` with the new `ANTHROPIC_API_KEY`
  / `GOOGLE_API_KEY` / `NEWSAPI_KEY` requirements and feature flags

---

## Phase 5 — Optional next steps

Not part of the core plan but flagged for after the rebuild ships:

- **Multi-turn conversation memory** with vector recall — for follow-up
  Q&A that references "the company we discussed earlier"
- **Personal model fine-tuning** — fine-tune a smaller open model
  (e.g. Mistral-7B) on user feedback signals to handle the bulk of
  Q&A traffic at <1¢ per query, with Claude as the fallback for hard
  questions
- **Re-ranker upgrade** — replace BM25 hybrid with a cross-encoder
  (e.g. `cohere/rerank-english-v3.0`) for ~10pt NDCG@10 lift
- **Audio earnings calls** — ingest earnings call audio, transcribe
  via Claude (or Whisper), feed into `earnings_transcripts` so they
  become searchable / sentiment-scoreable

---

## Cost estimate *(rough)*

| Item | Monthly |
|---|---|
| Anthropic (Sonnet at expected volume, with prompt cache) | $200 – $1,500 |
| Anthropic web_search tool (per-search billing) | $50 – $300 |
| Google Gemini Embedding 2 (one-time backfill + incremental) | $20 – $100 |
| GDELT | free |
| NewsAPI.org free tier | free |
| pgvector | free (lives in your existing Postgres) |

Volume assumptions: ~500 active users, 50 AI calls each per day, 20%
hitting Sonnet vs Haiku. Linear scaling.

---

## Open questions for you

1. **Auth model for AI calls** — should we add per-user token budgets
   (default 10M / day) before we ship the rebuild, or after?
2. **Eval gating in CI** — block PRs on eval regression, or run nightly
   and post a comment? Blocking is safer; nightly is faster.
3. **Streaming default** — every chat endpoint streams by default, or
   opt-in via `?stream=true`?
4. **Watchlist news watch frequency** — hourly is reasonable for a
   demo; for a real terminal we'd want every 15 min (matches GDELT
   cadence). The cost difference is ~4×.
5. **Web-search domain list** — comfortable with the 12 domains in
   §3.1, or want to add specific ones (e.g. seekingalpha.com,
   investorrelations sites, regional papers)?

Let me know on any of these and I'll start with Phase 0.
