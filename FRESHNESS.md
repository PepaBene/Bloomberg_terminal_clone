# Data Freshness — never serve stale data

Two mechanisms keep the app current, on top of the one-time [backfill](BACKFILL.md):

1. **On-demand refresh** — viewing a company (or its news) fetches the latest data live.
2. **Scheduled refresh** — a background job re-fetches companies whose data has aged out.

Together: the backfill gets you to complete coverage, on-demand keeps *what you're
looking at* current, and scheduled refresh keeps *everything else* from going stale.

---

## 1. On-demand refresh (fetch-on-view)

**Policy: stale-while-revalidate.** An endpoint serves what's in the DB *now* (fast)
and triggers a refresh so the latest data lands for the next load. Fast sources
(news) are fetched inline. A per-type **TTL** decides when data is stale; a
**cooldown** stops repeated views from triggering a refresh storm.

Implemented in `src/services/freshness.py`, wired into the API:

| You do this | Endpoint | What refreshes | How |
|---|---|---|---|
| Open a company | `GET /v1/entities/{id}` | fundamentals (XBRL), 8-K filings, news | background (serve now, refetch after) |
| Open a company's news | `GET /v3/news/{id}` | that company's news | inline, debounced |
| Open the news feed | `GET /v3/news/latest` | news for 25 major companies | background, debounced |

**Freshness windows** (`TTL_SECONDS` in `freshness.py`) — tune freely:

| Data type | TTL (re-fetch if older) |
|---|---|
| `news` | 15 minutes |
| `corporate_actions` (8-K) | 1 hour |
| `xbrl` (fundamentals) | 12 hours |

**Cooldown:** `COOLDOWN_SECONDS = 5 min` — the same (company, type) is never
re-fetched more than once per 5 minutes, no matter how many people view it. This
is the stampede guard.

The freshness ledger is the **`ingestion_progress`** table (shared with the
backfill): `last_success_at` per `(entity, data_type)` is the single source of
truth for "when was this last refreshed", so on-demand and scheduled refresh
never fight or double-fetch.

### News source

`src/ingestion/finnhub_news.py` pulls company news from Finnhub
(`FINNHUB_API_KEY`) into `news_articles` + `article_entity_links`, deduped by URL.
The global feed is seeded from a list of major tickers (`MAJOR_TICKERS`); any
company you view adds its own news on top.

### The honest trade-off

You can't fetch every SEC filing the instant it's filed on a page load without
making pages slow and blowing through rate limits. So:
- **News** (fast) is fetched *inline* on view — you see fresh headlines immediately.
- **Fundamentals / filings** (slow, SEC-rate-limited) refresh in the *background* —
  the page renders instantly from the DB, and the refetch is ready on the next load.
- The scheduled job (below) is the safety net that keeps everything current even
  for companies nobody has viewed recently.

---

## 2. Scheduled refresh (background, unattended)

`scripts/backfill.py` gained a `--refresh-days N` flag: before a pass, it
re-queues any company last refreshed more than **N days** ago (flips `SUCCESS` →
`PENDING`), so the same rate-safe, resumable machinery re-fetches it and picks up
new quarterly filings, 8-Ks, etc. (Price history is immutable, so it's never
reopened — new trading days are added by the normal cursor.)

```bash
make backfill-refresh          # one pass: fill gaps + refresh anything stale >7d
# or directly:
python -m scripts.backfill --all --refresh-days 7 --max-minutes 10
```

### Unattended (Windows Task Scheduler)

One scheduled task does everything — completes the historical backfill *and* keeps
it fresh — because each run is bounded and resumable:

```powershell
schtasks /create /tn "bdf-refresh" ^
  /tr "\"C:\Users\pepab\Documents\Bloomberg\bloomberg-data-fabric\.venv\Scripts\python.exe\" -m scripts.backfill --all --refresh-days 7 --max-minutes 10" ^
  /sc minute /mo 20 /rl highest
```

Runs every 20 minutes: fills any remaining companies, then rolls through the ones
that have aged past 7 days. Check status any time with `make backfill-status`.

Recompute analytics on a nightly task after data lands:
```powershell
schtasks /create /tn "bdf-analytics" /tr "\"...\.venv\Scripts\python.exe\" -m scripts.run_analytics_batch --engine all" /sc daily /st 02:00
```

---

## Tuning

- **Fresher, more API usage:** lower the `TTL_SECONDS` values and `--refresh-days`.
- **Cheaper, more tolerant of staleness:** raise them.
- **Add a data type to on-demand:** extend `DEFAULT_TYPES` + `_refresh_one` in
  `freshness.py` (and `TTL_SECONDS`).
- **Broaden the global news feed:** add tickers to `MAJOR_TICKERS`.
