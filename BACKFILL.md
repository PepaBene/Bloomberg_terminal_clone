# Automated Backfill System

Gets **complete data for every company automatically**, within your API rate
limits, and **without losing progress** if a run is interrupted.

A full backfill of all ~8,000 companies is far longer than any single process
can run (SEC 10 req/s, Polygon 5 req/min, etc.). This system solves that by
making the work **resumable and incremental**: it records what's done in the
database, processes only the next un-done items in short bounded passes, and
converges to 100% coverage no matter how many times it's interrupted.

---

## TL;DR

```bash
# One-time: create the progress table + recognize data you already have
make migrate
make backfill-reconcile

# Option A — run it continuously until everything is complete:
make backfill-loop

# Option B — check coverage any time, run one bounded pass:
make backfill-status
make backfill            # one ~8-minute pass across all data types
```

`backfill-loop` is "set it and forget it" — leave it running and it fills every
company. For truly unattended operation (surviving reboots), schedule it with
the OS (see [Unattended](#unattended-set-and-forget)).

---

## What gets backfilled

| Data type | Source | Rate-limited by | Cursor |
|---|---|---|---|
| `xbrl` | SEC EDGAR XBRL (income/balance/cash-flow, filings) | SEC 10/s | per company (CIK) |
| `corporate_actions` | SEC 8-K | SEC 10/s | per company (CIK) |
| `esg` | SEC proxy/governance | SEC 10/s | per company (CIK) |
| `prices` | Polygon grouped-daily EOD | Polygon 5/min | per trading day |

Prices use the grouped-daily endpoint (one request returns **all** US stocks for
a day), so a full multi-year price history is only a few hundred requests —
paced automatically at ~5/min.

---

## How it works

- **`ingestion_progress` table** (migration 083) holds one row per
  `(data_type, subject)` with a status:
  - `SUCCESS` — the subject has data; never fetched again.
  - `NO_DATA` — no data after `MAX_ATTEMPTS` (3) tries; stops retrying (many
    small filers genuinely have no XBRL/8-K).
  - `PENDING` — not done yet; retried on a later pass.
- **Bounded passes.** `scripts/backfill.py` processes the *next* un-done subjects
  in small batches, commits **per batch**, and stops the moment `--max-minutes`
  elapses — so it always exits cleanly *before* any external time limit can kill
  it mid-write. Nothing is ever half-committed or lost.
- **Cursor advances, never repeats.** Selection skips `SUCCESS`/`NO_DATA` and
  orders never-attempted first, so each pass moves forward. Interrupt it any
  time; the next pass resumes exactly where it left off.
- **Rate-limit aware.** Each connector honors its source's limit; prices sleep
  ~13s between days to respect Polygon's 5/min free tier.
- **`--reconcile`** seeds the progress table from data already in the DB, so it
  won't re-fetch what you loaded manually.

---

## Commands

```bash
# Coverage report (per data type: SUCCESS / NO_DATA / PENDING / remaining / %)
python -m scripts.backfill --status

# Mark existing data as done (run once, after the first migrate)
python -m scripts.backfill --reconcile

# One bounded pass across ALL data types (round-robin within the budget)
python -m scripts.backfill --all --max-minutes 8

# Backfill a single type
python -m scripts.backfill --type xbrl --batch-size 25 --max-minutes 8
python -m scripts.backfill --type prices --batch-size 6 --prices-lookback-days 365

# Run continuously until 100% complete (isolated subprocess per pass, so a
# hung/killed pass never kills the loop)
python -m scripts.run_backfill_loop --pass-minutes 8 --sleep-seconds 20
```

Tunables: `--batch-size` (subjects per commit), `--max-minutes` (pass budget),
`--prices-lookback-days` (how much price history to fill).

---

## Unattended (set and forget)

`run_backfill_loop` runs as long as its process lives. To survive logout/reboot,
let the OS scheduler fire bounded passes — because each pass is resumable, this
is completely safe to run on a schedule:

### Windows Task Scheduler
Create a task that runs every ~15 minutes:
```
Program:   C:\Users\pepab\Documents\Bloomberg\bloomberg-data-fabric\.venv\Scripts\python.exe
Arguments: -m scripts.backfill --all --max-minutes 10
Start in:  C:\Users\pepab\Documents\Bloomberg\bloomberg-data-fabric
```
(Or via PowerShell:)
```powershell
schtasks /create /tn "bdf-backfill" /tr "\"C:\...\.venv\Scripts\python.exe\" -m scripts.backfill --all --max-minutes 10" /sc minute /mo 15 /rl highest
```

### cron (Linux/Mac)
```cron
*/15 * * * * cd /path/to/bloomberg-data-fabric && ./.venv/bin/python -m scripts.backfill --all --max-minutes 10 >> backfill.log 2>&1
```

Each firing does ~10 minutes of work and stops; over a day the whole universe
fills in. Check progress any time with `make backfill-status`.

---

## After data lands: analytics

Ratios/valuations/scores are computed *from* the ingested fundamentals+prices:
```bash
python -m scripts.run_analytics_batch --engine all
```
Run this periodically (or on a schedule) once fundamentals coverage grows — it
recomputes for all securities that have the inputs.

---

## Prerequisites (bootstrap, one-time)

The backfill fills *per-company* and *per-day* data. The one-time bulk loads that
define the universe still run first:
```bash
make seed                        # reference data (countries, GICS, trading days)
python -m scripts.ingest_edgar   # entities + CIKs (defines the company universe)
python -m scripts.ingest_openfigi# securities (idempotent: skips already-mapped tickers)
```
Then `make backfill-reconcile` and start the loop.

---

## Extending it

Adding a new company-scoped SEC data type is a two-line registry entry in
`scripts/backfill.py`:
```python
ENTITY_TYPES["ownership_insider"] = EntityCikType(
    "ownership_insider", EdgarForm4Connector, "issuer_ciks",
    "insider_holdings", "entity_id",   # target table + FK to check "has data"
)
```
The orchestrator handles cursoring, committing, progress, and retries generically.
