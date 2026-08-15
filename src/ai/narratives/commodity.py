"""Layer 2 §4.7 Pillar-3 follow-through: "Commodity (context) | Commodity
news/supply-demand narrative to complement FRED prices."

Real structured data already existed for this row (``CommodityPrice``/
``CommodityInventory``, both scheduled and ingested) but had no narrative
layer over it -- this assembles that data plus any corroborating
COMMODITY-tagged news into a short grounded narrative, same
context-assemble -> prompt-render -> ``complete_text`` shape as the
legacy narrative features (``company_primer``/``morning_briefing``), and
the same compute-on-miss caching shape as ``src/ai/interpret/store.py``
(simpler here: no analytics-version freshness concept, just "is there
already a row for today").
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.models import model_for_tier
from src.ai.prompts import load_prompt
from src.models.commodity_intelligence import CommodityInventory, CommodityPrice, CommodityProfile
from src.models.news_article import NewsArticle
from src.models.pillar3_narratives import CommodityNarrative

logger = logging.getLogger(__name__)

# How far back to look for corroborating COMMODITY-tagged news, and how
# many candidate articles to scan -- a bounded window query, same
# philosophy as news_enrichment.py's CLUSTER_WINDOW_DAYS: cheap even as
# news_articles grows, not a full-table scan.
NEWS_WINDOW_DAYS = 14
NEWS_SCAN_LIMIT = 200
NEWS_MATCH_LIMIT = 5
PRICE_LOOKBACK_ROWS = 30


@dataclass(frozen=True)
class CommodityContext:
    """Everything real (never fabricated) this narrative can be grounded
    in for one commodity, as of "now"."""

    commodity_code: str
    commodity_name: str
    unit: str | None
    latest_price: float | None
    price_date: date | None
    pct_change_period: float | None
    period_days: int
    inventory: dict | None
    news_headlines: list[str] = field(default_factory=list)
    news_article_ids: list[str] = field(default_factory=list)


async def assemble_commodity_context(session: AsyncSession, commodity_code: str) -> CommodityContext | None:
    """Returns ``None`` when there's no price history at all for this
    commodity -- nothing real to narrate."""
    profile = (
        await session.execute(
            select(CommodityProfile).where(CommodityProfile.commodity_code == commodity_code)
        )
    ).scalar_one_or_none()

    prices = (
        await session.execute(
            select(CommodityPrice)
            .where(CommodityPrice.commodity_code == commodity_code)
            .order_by(CommodityPrice.price_date.desc())
            .limit(PRICE_LOOKBACK_ROWS)
        )
    ).scalars().all()
    if not prices:
        return None

    latest, oldest = prices[0], prices[-1]
    pct_change = None
    if latest.close_price is not None and oldest.close_price is not None and float(oldest.close_price) != 0:
        pct_change = round(
            (float(latest.close_price) - float(oldest.close_price)) / float(oldest.close_price) * 100, 2,
        )

    inventory_row = (
        await session.execute(
            select(CommodityInventory)
            .where(CommodityInventory.commodity_code == commodity_code)
            .order_by(CommodityInventory.as_of_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    inventory = None
    if inventory_row is not None:
        inventory = {
            "stock_level": float(inventory_row.stock_level),
            "stock_unit": inventory_row.stock_unit,
            "metric_name": inventory_row.metric_name,
            "as_of_date": inventory_row.as_of_date.isoformat(),
        }

    commodity_name = (profile.commodity_name if profile else None) or commodity_code

    # Best-effort corroborating news: a COMMODITY-tagged article whose
    # title/summary mentions this commodity by name. JSONB list
    # containment isn't portable across this suite's SQLite test engine
    # and Postgres in production, so this filters in Python over a
    # bounded recent window rather than a dialect-specific SQL operator --
    # same shape as news_enrichment.py's own cluster-candidate query.
    since = date.today() - timedelta(days=NEWS_WINDOW_DAYS)
    candidates = (
        await session.execute(
            select(NewsArticle)
            .where(NewsArticle.publish_date >= since)
            .order_by(NewsArticle.publish_date.desc())
            .limit(NEWS_SCAN_LIMIT)
        )
    ).scalars().all()
    name_lower = commodity_name.lower()
    matched = [
        a for a in candidates
        if "COMMODITY" in (a.topics or [])
        and (name_lower in a.title.lower() or name_lower in (a.summary or "").lower())
    ][:NEWS_MATCH_LIMIT]

    return CommodityContext(
        commodity_code=commodity_code, commodity_name=commodity_name,
        unit=profile.unit if profile else None,
        latest_price=float(latest.close_price) if latest.close_price is not None else None,
        price_date=latest.price_date, pct_change_period=pct_change, period_days=len(prices),
        inventory=inventory,
        news_headlines=[a.title for a in matched],
        news_article_ids=[str(a.id) for a in matched],
    )


async def generate_commodity_narrative(client, context: CommodityContext) -> str | None:
    prompt = load_prompt("commodity_narrative")
    return await client.complete_text(
        user=prompt.render(
            commodity_name=context.commodity_name,
            unit=context.unit or "unit not specified",
            latest_price=context.latest_price if context.latest_price is not None else "unavailable",
            price_date=context.price_date.isoformat() if context.price_date else "unknown",
            pct_change_period=context.pct_change_period if context.pct_change_period is not None else "unavailable",
            period_days=context.period_days,
            inventory_summary=context.inventory or "No inventory data available.",
            news_summary=context.news_headlines or "No recent related news found.",
        ),
        system=prompt.system, tier=prompt.tier, max_tokens=prompt.max_tokens, feature=prompt.feature,
    )


async def get_or_compute_commodity_narrative(
    session: AsyncSession,
    client,
    commodity_code: str,
    *,
    as_of: date | None = None,
    force_refresh: bool = False,
) -> CommodityNarrative | None:
    """Compute-on-miss entry point. Returns ``None`` when there's nothing
    cached and no way to compute a fresh read (no price data, AI
    disabled, or the call failed) -- never raises, matching
    ``src.ai.interpret.store``'s "omit rather than fail" contract.

    Looks up any existing row for ``(commodity_code, as_of)`` regardless
    of ``force_refresh`` -- not just to decide cache-hit-or-not, but so a
    refresh UPDATEs that row instead of trying to INSERT a second one and
    violating the table's unique constraint on that pair.
    """
    as_of = as_of or date.today()
    existing = (
        await session.execute(
            select(CommodityNarrative).where(
                CommodityNarrative.commodity_code == commodity_code,
                CommodityNarrative.as_of_date == as_of,
            )
        )
    ).scalar_one_or_none()
    if existing is not None and not force_refresh:
        return existing
    if not client.enabled:
        return existing

    context = await assemble_commodity_context(session, commodity_code)
    if context is None:
        return existing

    try:
        narrative_text = await generate_commodity_narrative(client, context)
    except Exception:  # noqa: BLE001
        logger.warning("generate_commodity_narrative failed for %s", commodity_code, exc_info=True)
        return existing
    if not narrative_text:
        return existing

    prompt = load_prompt("commodity_narrative")
    fields = dict(
        narrative=narrative_text,
        price_summary={
            "latest_price": context.latest_price, "price_date": context.price_date.isoformat() if context.price_date else None,
            "pct_change_period": context.pct_change_period, "period_days": context.period_days,
            "inventory": context.inventory,
        },
        news_article_ids=context.news_article_ids,
        model=model_for_tier(prompt.tier), prompt_id=prompt.id, prompt_version=prompt.version,
    )
    if existing is not None:
        for key, value in fields.items():
            setattr(existing, key, value)
        row = existing
    else:
        row = CommodityNarrative(id=uuid.uuid4(), commodity_code=commodity_code, as_of_date=as_of, **fields)
        session.add(row)
    await session.flush()
    return row
