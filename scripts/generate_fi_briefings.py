"""Generate + persist FI market briefings (yield curve + credit) from real FRED data.

Reads ``yield_curve_snapshots`` (populated by ``scripts/ingest_treasury_curve.py``)
and ``credit_spread_indices`` (populated by ``scripts/ingest_credit_spreads.py``) --
both real, keyless-ish FRED sources (a free FRED_API_KEY) -- and calls the
previously-orphaned briefing generators in ``src/engines/fi_intelligence.py``,
persisting one ``FIMarketBriefing`` row per day per briefing_type
(YIELD_CURVE, CREDIT). This is the producer DATA_WIRING_AUDIT.md flagged as
missing: "FI intelligence (briefings, issuer profile) -- Real engine, zero
production callers."

Rating-migration fields (fallen_angels/rising_stars) are left honestly empty --
no bond-issuance/rating-history connector exists yet to source them.

Usage:
    python -m scripts.generate_fi_briefings
    python -m scripts.generate_fi_briefings --dry-run
"""

import argparse
import asyncio
import logging
import sys
import uuid
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from src.ai.llm_client import get_llm_client  # noqa: E402
from src.database import get_session_factory  # noqa: E402
from src.engines import fi_intelligence as fi_engine  # noqa: E402
from src.models.credit_spread import CreditSpreadIndex  # noqa: E402
from src.models.fi_intelligence import FIMarketBriefing  # noqa: E402
from src.models.yield_curve import YieldCurveSnapshot  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CURVE_TYPE = "TREASURY_NOMINAL"
IG_SERIES = "BAMLC0A0CM"
HY_SERIES = "BAMLH0A0HYM2"


async def _upsert_briefing(session, briefing_date, briefing_type: str, values: dict) -> None:
    existing = (
        await session.execute(
            select(FIMarketBriefing).where(
                FIMarketBriefing.briefing_date == briefing_date,
                FIMarketBriefing.briefing_type == briefing_type,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        for k, v in values.items():
            setattr(existing, k, v)
    else:
        session.add(FIMarketBriefing(
            id=uuid.uuid4(), briefing_date=briefing_date, briefing_type=briefing_type, **values,
        ))


async def _polish(narrative: str, system_prompt: str) -> tuple[str, bool]:
    llm = get_llm_client()
    if not llm.enabled:
        return narrative, False
    polished = await llm.generate(system_prompt=system_prompt, user_prompt=narrative)
    return (polished, True) if polished else (narrative, False)


async def generate_yield_curve_briefing(session) -> bool:
    """Real 2s10s/3m10y curve briefing from FRED-sourced YieldCurveSnapshot."""
    snaps = (
        await session.execute(
            select(YieldCurveSnapshot)
            .where(YieldCurveSnapshot.curve_type == CURVE_TYPE)
            .order_by(YieldCurveSnapshot.curve_date.desc())
            .limit(1300)  # ~5y of trading days
        )
    ).scalars().all()
    if not snaps:
        logger.warning("No yield_curve_snapshots rows -- run scripts/ingest_treasury_curve.py first.")
        return False

    latest = snaps[0]
    prior = snaps[1] if len(snaps) > 1 else None

    # Stored spreads are in percentage points (e.g. 0.45 = 45 bps); the engine
    # expects basis points.
    history_5y = [float(s.spread_2s10s) * 100 for s in snaps if s.spread_2s10s is not None]
    curve_data = {
        "spread_2s10s_bps": float(latest.spread_2s10s) * 100 if latest.spread_2s10s is not None else 0.0,
        "spread_3m10y_bps": float(latest.spread_3m10y) * 100 if latest.spread_3m10y is not None else None,
        "yield_10y": float(latest.rate_10y) if latest.rate_10y is not None else None,
        "history_5y": history_5y,
    }
    prior_data = None
    if prior is not None and prior.rate_10y is not None:
        prior_data = {"yield_10y": float(prior.rate_10y)}

    briefing = fi_engine.generate_yield_curve_briefing(curve_data, prior_data)

    narrative = (
        f"The 2s10s spread is {briefing.spread_2s10s_bps:+.0f} bps ({briefing.curve_shape} curve)"
        + (
            f", {briefing.spread_percentile_5y:.0f}th percentile of the last 5 years"
            if briefing.spread_percentile_5y is not None else ""
        )
        + ". " + " ".join(briefing.equity_implications)
    )
    narrative, ai_enabled = await _polish(
        narrative,
        "You are a Bloomberg fixed-income research AI assistant. Rewrite the given "
        "yield-curve summary as 2-3 polished sentences, without adding any facts not "
        "present in it.",
    )

    await _upsert_briefing(session, latest.curve_date, "YIELD_CURVE", dict(
        spread_2s10s_bps=briefing.spread_2s10s_bps,
        spread_3m10y_bps=briefing.spread_3m10y_bps,
        curve_shape=briefing.curve_shape,
        narrative=narrative,
        ai_enabled=ai_enabled,
    ))
    logger.info(
        "Yield-curve briefing: %s spread_2s10s=%.0fbps curve=%s",
        latest.curve_date, briefing.spread_2s10s_bps, briefing.curve_shape,
    )
    return True


async def generate_credit_briefing(session) -> bool:
    """Real IG/HY OAS credit-regime briefing from FRED-sourced CreditSpreadIndex."""
    ig_rows = (
        await session.execute(
            select(CreditSpreadIndex)
            .where(CreditSpreadIndex.series_id == IG_SERIES)
            .order_by(CreditSpreadIndex.observation_date.desc())
            .limit(1300)
        )
    ).scalars().all()
    hy_rows = (
        await session.execute(
            select(CreditSpreadIndex)
            .where(CreditSpreadIndex.series_id == HY_SERIES)
            .order_by(CreditSpreadIndex.observation_date.desc())
            .limit(1300)
        )
    ).scalars().all()
    if not ig_rows or not hy_rows:
        logger.warning("No credit_spread_indices rows -- run scripts/ingest_credit_spreads.py first.")
        return False

    ig_by_date = {r.observation_date: float(r.spread_bps) for r in ig_rows}
    hy_by_date = {r.observation_date: float(r.spread_bps) for r in hy_rows}
    common_dates = ig_by_date.keys() & hy_by_date.keys()
    if not common_dates:
        logger.warning("IG/HY credit spread series share no overlapping dates.")
        return False

    as_of = max(common_dates)
    ig_oas = ig_by_date[as_of]
    hy_oas = hy_by_date[as_of]

    prior_candidates = sorted(d for d in common_dates if d <= as_of - timedelta(days=6))
    prior_date = prior_candidates[-1] if prior_candidates else None
    prior_ig = ig_by_date[prior_date] if prior_date else ig_oas
    prior_hy = hy_by_date[prior_date] if prior_date else hy_oas

    history = [{"ig_oas": ig_by_date[d], "hy_oas": hy_by_date[d]} for d in common_dates]

    briefing = fi_engine.generate_credit_market_briefing(
        ig_oas=ig_oas, hy_oas=hy_oas, prior_ig=prior_ig, prior_hy=prior_hy,
        history=history, events=None,
    )

    narrative = (
        f"Credit regime is {briefing.credit_regime}: IG OAS {briefing.ig_oas_bps:.0f} bps "
        f"({briefing.ig_change_1w:+.0f} bps 1w), HY OAS {briefing.hy_oas_bps:.0f} bps "
        f"({briefing.hy_change_1w:+.0f} bps 1w)."
    )
    narrative, ai_enabled = await _polish(
        narrative,
        "You are a Bloomberg fixed-income research AI assistant. Rewrite the given "
        "credit-market summary as 2-3 polished sentences, without adding any facts not "
        "present in it.",
    )

    await _upsert_briefing(session, as_of, "CREDIT", dict(
        ig_oas_bps=briefing.ig_oas_bps,
        hy_oas_bps=briefing.hy_oas_bps,
        ig_oas_1w_change=briefing.ig_change_1w,
        hy_oas_1w_change=briefing.hy_change_1w,
        credit_regime=briefing.credit_regime,
        fallen_angels_this_period=briefing.fallen_angels,
        rising_stars_this_period=briefing.rising_stars,
        narrative=narrative,
        ai_enabled=ai_enabled,
    ))
    logger.info("Credit briefing: %s regime=%s IG=%.0fbps HY=%.0fbps", as_of, briefing.credit_regime, ig_oas, hy_oas)
    return True


async def main() -> None:
    parser = argparse.ArgumentParser(description="Generate FI market briefings from real FRED data")
    parser.add_argument("--dry-run", action="store_true", help="Preview without committing")
    args = parser.parse_args()

    async with get_session_factory()() as session:
        yc_ok = await generate_yield_curve_briefing(session)
        credit_ok = await generate_credit_briefing(session)

        if args.dry_run:
            await session.rollback()
            logger.info("Dry run -- rolled back. yield_curve=%s credit=%s", yc_ok, credit_ok)
        else:
            await session.commit()
            logger.info("FI briefings committed. yield_curve=%s credit=%s", yc_ok, credit_ok)


if __name__ == "__main__":
    asyncio.run(main())
