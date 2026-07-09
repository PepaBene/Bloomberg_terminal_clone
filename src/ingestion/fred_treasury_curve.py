"""FRED Treasury Constant-Maturity yield-curve connector.

Fetches the daily US Treasury CMT par-yield series from FRED (DGS1MO … DGS30),
assembles one :class:`YieldCurveSnapshot` per business day, bootstraps the
zero-coupon curve, and stores everything as ``TREASURY_NOMINAL`` snapshots.

Rate units
----------
FRED returns constant-maturity yields in **percent** (e.g. ``4.35`` = 4.35%).
Every consumer of ``YieldCurveSnapshot`` in this codebase treats the stored
rates as **decimals** (e.g. ``0.0435``):

* ``src/engines/e11_spread_analytics.py`` computes ``spread * 10_000`` for the
  G-spread and discounts cash flows with ``(1 + z + s)`` for the Z-spread.
* ``src/api/routers/fi_yield_curve.py::apply_fi_scenario`` shifts rates by
  ``shift_bps / 10000.0`` and adds the delta directly to the stored rate.

So we divide the FRED percent value by 100 before storing.
"""

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.base import BaseConnector
from src.ingestion.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

FRED_BASE_URL = "https://api.stlouisfed.org/fred"

# FRED CMT series -> (par-rate column, zero-rate column, DF column|None, tenor in years)
# DF columns only exist for 1Y, 2Y, 5Y, 10Y, 20Y, 30Y on the model.
TREASURY_SERIES: list[tuple[str, str, str, str | None, float]] = [
    ("DGS1MO", "rate_1m", "zero_1m", None, 1.0 / 12.0),
    ("DGS3MO", "rate_3m", "zero_3m", None, 0.25),
    ("DGS6MO", "rate_6m", "zero_6m", None, 0.5),
    ("DGS1", "rate_1y", "zero_1y", "df_1y", 1.0),
    ("DGS2", "rate_2y", "zero_2y", "df_2y", 2.0),
    ("DGS3", "rate_3y", "zero_3y", None, 3.0),
    ("DGS5", "rate_5y", "zero_5y", "df_5y", 5.0),
    ("DGS7", "rate_7y", "zero_7y", None, 7.0),
    ("DGS10", "rate_10y", "zero_10y", "df_10y", 10.0),
    ("DGS20", "rate_20y", "zero_20y", "df_20y", 20.0),
    ("DGS30", "rate_30y", "zero_30y", "df_30y", 30.0),
]

CURVE_TYPE = "TREASURY_NOMINAL"


def _interp_par(t: float, par_pts: list[tuple[float, float]]) -> float:
    """Linear interpolation (flat extrapolation) of a par yield at tenor *t*."""
    if t <= par_pts[0][0]:
        return par_pts[0][1]
    if t >= par_pts[-1][0]:
        return par_pts[-1][1]
    for i in range(len(par_pts) - 1):
        t0, y0 = par_pts[i]
        t1, y1 = par_pts[i + 1]
        if t0 <= t <= t1:
            return y0 + (t - t0) / (t1 - t0) * (y1 - y0)
    return par_pts[-1][1]


def _bootstrap_semiannual(par_pts: list[tuple[float, float]]) -> dict[float, tuple[float, float]]:
    """Standard par → zero bootstrap on a semiannual grid.

    Interpolates par yields onto a 6-month grid, solves for discount factors
    assuming semiannual coupons priced at par, then converts each DF to an
    **annually-compounded** zero rate ``z`` such that ``(1 + z)^(-t) == DF`` —
    the exact convention the Z-spread engine uses when discounting cash flows
    with ``(1 + z + s)^(-t)``.

    Returns ``{tenor_years: (zero_rate_decimal, discount_factor)}`` for every
    grid point.
    """
    par_pts = sorted(par_pts)
    t_max = par_pts[-1][0]
    n = int(round(t_max * 2))
    if n < 1:
        return {}

    dfs: dict[int, float] = {}
    out: dict[float, tuple[float, float]] = {}
    for i in range(1, n + 1):
        t = i * 0.5
        c = _interp_par(t, par_pts)
        cpn = c / 2.0
        prior = sum(dfs[j] for j in range(1, i))
        df = (1.0 - cpn * prior) / (1.0 + cpn)
        dfs[i] = df
        if df > 0:
            z = df ** (-1.0 / t) - 1.0
        else:
            z = c
        out[round(t, 4)] = (z, df)
    return out


class FredTreasuryCurveConnector(BaseConnector):
    """Ingest the daily US Treasury nominal yield curve from FRED."""

    name = "FRED Treasury Curve"
    connector_type = "BATCH_API"
    data_domain = "YIELD_CURVE"

    def __init__(
        self,
        api_key: str | None = None,
        lookback_days: int = 90,
    ):
        self.api_key = api_key or getattr(settings, "FRED_API_KEY", "")
        # Fetch a bit more history than requested so ~90 business days survive
        # after weekend/holiday gaps are filtered out.
        self.lookback_days = lookback_days
        rate_limit = getattr(settings, "FRED_RATE_LIMIT", 120)
        self.rate_limiter = RateLimiter(max_requests=rate_limit, per_seconds=60.0)
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def _fred_get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        """Make a rate-limited GET request to the FRED API."""
        await self.rate_limiter.acquire()
        client = await self._get_client()
        all_params = {"api_key": self.api_key, "file_type": "json"}
        if params:
            all_params.update(params)
        resp = await client.get(f"{FRED_BASE_URL}/{path}", params=all_params)
        resp.raise_for_status()
        return resp.json()

    async def extract(self) -> list[dict[str, Any]]:
        """Pull each CMT series' recent observations from FRED.

        Returns one record per calendar date that has at least one tenor,
        keyed by the model column names with rates already in decimal form.
        """
        if not self.api_key:
            logger.warning("FRED_API_KEY not set — skipping treasury curve extraction")
            return []

        # ~1.5x buffer for weekends/holidays so we keep ~lookback_days business days.
        start = (date.today() - timedelta(days=int(self.lookback_days * 1.6) + 5)).isoformat()

        # date -> {rate_col: Decimal}
        by_date: dict[str, dict[str, Decimal]] = {}

        for series_id, rate_col, _zero_col, _df_col, _tenor in TREASURY_SERIES:
            try:
                obs_data = await self._fred_get(
                    "series/observations",
                    params={"series_id": series_id, "observation_start": start},
                )
                observations = obs_data.get("observations", [])
                kept = 0
                for obs in observations:
                    raw = obs.get("value")
                    obs_date = obs.get("date")
                    if not obs_date or raw is None or raw == ".":
                        continue
                    try:
                        pct = Decimal(raw)
                    except (ValueError, ArithmeticError):
                        continue
                    # percent -> decimal
                    by_date.setdefault(obs_date, {})[rate_col] = pct / Decimal("100")
                    kept += 1
                logger.info("  FRED CMT: %s — %d observations", series_id, kept)
            except Exception as e:  # noqa: BLE001
                logger.error("  FRED CMT: failed to fetch %s: %s", series_id, e)

        records = [
            {"curve_date": date.fromisoformat(d), **cols}
            for d, cols in sorted(by_date.items())
        ]
        logger.info("  FRED CMT: assembled %d dated curve records", len(records))
        return records

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Keep only records that have a date and at least two tenor points."""
        valid = []
        for rec in records:
            if not rec.get("curve_date"):
                continue
            n_rates = sum(
                1 for _, rate_col, _, _, _ in TREASURY_SERIES if rec.get(rate_col) is not None
            )
            if n_rates < 2:
                continue
            valid.append(rec)
        return valid

    async def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Compute derived spreads and bootstrap the zero/discount curve."""
        for rec in records:
            self._add_spreads(rec)
            self._add_bootstrap(rec)
        return records

    @staticmethod
    def _add_spreads(rec: dict[str, Any]) -> None:
        r2 = rec.get("rate_2y")
        r10 = rec.get("rate_10y")
        r3m = rec.get("rate_3m")
        r5 = rec.get("rate_5y")
        r30 = rec.get("rate_30y")

        if r2 is not None and r10 is not None:
            rec["spread_2s10s"] = r10 - r2
            rec["curve_slope"] = r10 - r2
            rec["is_inverted"] = (r10 - r2) < 0
        if r3m is not None and r10 is not None:
            rec["spread_3m10y"] = r10 - r3m
        if r5 is not None and r30 is not None:
            rec["spread_5s30s"] = r30 - r5

    @staticmethod
    def _add_bootstrap(rec: dict[str, Any]) -> None:
        """Bootstrap zero rates + discount factors from the par rates present."""
        par_pts: list[tuple[float, float]] = []
        for _series, rate_col, _zero_col, _df_col, tenor in TREASURY_SERIES:
            val = rec.get(rate_col)
            if val is not None:
                par_pts.append((tenor, float(val)))

        if len(par_pts) < 2:
            return

        try:
            grid = _bootstrap_semiannual(par_pts)
        except Exception as e:  # noqa: BLE001
            logger.debug("bootstrap failed for %s: %s", rec.get("curve_date"), e)
            return

        for _series, rate_col, zero_col, df_col, tenor in TREASURY_SERIES:
            par_val = rec.get(rate_col)
            if par_val is None:
                continue
            key = round(tenor, 4)
            if key in grid:
                z, df = grid[key]
            else:
                # Sub-6-month money-market tenors are effectively zero-coupon:
                # the zero rate equals the par (bond-equivalent) yield.
                z = float(par_val)
                df = (1.0 + z) ** (-tenor)
            rec[zero_col] = Decimal(str(round(z, 6)))
            if df_col is not None:
                rec[df_col] = Decimal(str(round(df, 8)))

    async def load(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> dict[str, int]:
        """Idempotently upsert one snapshot per (curve_date, curve_type)."""
        from src.models.yield_curve import YieldCurveSnapshot

        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}

        # Columns we are allowed to write from a record (excludes curve_date/type).
        writable_cols = set()
        for _s, rate_col, zero_col, df_col, _t in TREASURY_SERIES:
            writable_cols.add(rate_col)
            writable_cols.add(zero_col)
            if df_col:
                writable_cols.add(df_col)
        writable_cols.update(
            {"spread_2s10s", "spread_3m10y", "spread_5s30s", "curve_slope"}
        )

        for rec in records:
            try:
                curve_date = rec["curve_date"]
                existing = await session.execute(
                    select(YieldCurveSnapshot).where(
                        YieldCurveSnapshot.curve_date == curve_date,
                        YieldCurveSnapshot.curve_type == CURVE_TYPE,
                    )
                )
                snapshot = existing.scalar_one_or_none()

                if snapshot is None:
                    snapshot = YieldCurveSnapshot(
                        curve_date=curve_date,
                        curve_type=CURVE_TYPE,
                        source="FRED",
                    )
                    for col in writable_cols:
                        if rec.get(col) is not None:
                            setattr(snapshot, col, rec[col])
                    snapshot.is_inverted = bool(rec.get("is_inverted", False))
                    session.add(snapshot)
                    stats["inserted"] += 1
                else:
                    for col in writable_cols:
                        if rec.get(col) is not None:
                            setattr(snapshot, col, rec[col])
                    snapshot.is_inverted = bool(rec.get("is_inverted", False))
                    snapshot.source = "FRED"
                    stats["updated"] += 1

                await session.flush()
            except Exception as e:  # noqa: BLE001
                logger.error("  Failed to load curve %s: %s", rec.get("curve_date"), e)
                stats["errors"] += 1

        await session.flush()
        return stats

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
