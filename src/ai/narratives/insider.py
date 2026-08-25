"""Layer 2 §4.7 Pillar-3 follow-through: "Insiders | Narrative around
Form 4 / congressional disclosures; corroborating news."

Real structured data already existed for this row (``InsiderSignal``,
computed from ``InsiderTransactionP3``/Form 4 filings, and
``CongressionalTrade``, STOCK Act PTR disclosures -- both scheduled and
ingested) but had no narrative layer over it. Same shape as
``src/ai/narratives/commodity.py``: context-assemble -> prompt-render ->
``complete_text``, compute-on-miss cached one row per (entity, date).
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.models import model_for_tier
from src.ai.prompts import load_prompt
from src.models.congressional_trades import CongressionalTrade
from src.models.entity import Entity
from src.models.insider_intelligence import InsiderSignal
from src.models.pillar3_narratives import InsiderNarrative
from src.models.security import Security, SecurityIdentifier

logger = logging.getLogger(__name__)

SIGNAL_SCAN_LIMIT = 20
CONGRESSIONAL_LOOKBACK_LIMIT = 5


@dataclass(frozen=True)
class InsiderContext:
    """Everything real (never fabricated) this narrative can be grounded
    in for one entity, as of "now"."""

    entity_id: uuid.UUID
    company_name: str
    ticker: str | None
    signals: list[dict] = field(default_factory=list)
    congressional_trades: list[dict] = field(default_factory=list)


async def _resolve_ticker(session: AsyncSession, entity_id: uuid.UUID) -> str | None:
    row = (
        await session.execute(
            select(SecurityIdentifier.identifier_value)
            .join(Security, Security.security_id == SecurityIdentifier.security_id)
            .where(
                Security.issuer_entity_id == entity_id,
                SecurityIdentifier.identifier_type == "TICKER",
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    return row


async def assemble_insider_context(session: AsyncSession, entity_id: uuid.UUID) -> InsiderContext | None:
    """Returns ``None`` when the entity doesn't exist, or has neither an
    insider signal nor a resolvable ticker with congressional trades --
    nothing real to narrate."""
    entity = await session.get(Entity, entity_id)
    if entity is None:
        return None

    signal_rows = (
        await session.execute(
            select(InsiderSignal)
            .where(InsiderSignal.entity_id == entity_id)
            .order_by(InsiderSignal.signal_date.desc())
            .limit(SIGNAL_SCAN_LIMIT)
        )
    ).scalars().all()
    latest_by_type: dict[str, InsiderSignal] = {}
    for row in signal_rows:
        latest_by_type.setdefault(row.signal_type, row)
    signals = [
        {
            "signal_type": s.signal_type, "signal_date": s.signal_date.isoformat(),
            "signal_strength": s.signal_strength,
            "net_shares_30d": float(s.net_shares_30d) if s.net_shares_30d is not None else None,
            "net_value_30d": float(s.net_value_30d) if s.net_value_30d is not None else None,
            "net_value_90d": float(s.net_value_90d) if s.net_value_90d is not None else None,
            "net_value_365d": float(s.net_value_365d) if s.net_value_365d is not None else None,
            "insider_count_buying_30d": s.insider_count_buying_30d,
            "insider_count_selling_30d": s.insider_count_selling_30d,
        }
        for s in latest_by_type.values()
    ]

    ticker = await _resolve_ticker(session, entity_id)
    congressional_trades: list[dict] = []
    if ticker:
        trade_rows = (
            await session.execute(
                select(CongressionalTrade)
                .where(CongressionalTrade.ticker == ticker)
                .order_by(CongressionalTrade.transaction_date.desc())
                .limit(CONGRESSIONAL_LOOKBACK_LIMIT)
            )
        ).scalars().all()
        congressional_trades = [
            {
                "politician_name": t.politician_name, "transaction_type": t.transaction_type,
                "transaction_date": t.transaction_date.isoformat(),
                "amount_range_low": float(t.amount_range_low) if t.amount_range_low is not None else None,
                "amount_range_high": float(t.amount_range_high) if t.amount_range_high is not None else None,
                "is_late_disclosure": t.is_late_disclosure,
            }
            for t in trade_rows
        ]

    if not signals and not congressional_trades:
        return None

    return InsiderContext(
        entity_id=entity_id, company_name=entity.legal_name, ticker=ticker,
        signals=signals, congressional_trades=congressional_trades,
    )


async def generate_insider_narrative(client, context: InsiderContext) -> str | None:
    prompt = load_prompt("insider_narrative")
    return await client.complete_text(
        user=prompt.render(
            company_name=context.company_name,
            signal_summary=context.signals or "No recent insider signal data available.",
            congressional_summary=context.congressional_trades or "No recent congressional disclosures found.",
        ),
        system=prompt.system, tier=prompt.tier, max_tokens=prompt.max_tokens, feature=prompt.feature,
    )


async def get_or_compute_insider_narrative(
    session: AsyncSession,
    client,
    entity_id: uuid.UUID,
    *,
    as_of: date | None = None,
    force_refresh: bool = False,
) -> InsiderNarrative | None:
    """Compute-on-miss entry point. Returns ``None`` when there's nothing
    cached and no way to compute a fresh read (unknown entity, no
    signal/congressional data, AI disabled, or the call failed) -- never
    raises, matching ``src.ai.interpret.store``'s "omit rather than fail"
    contract.

    Looks up any existing row for ``(entity_id, as_of)`` regardless of
    ``force_refresh`` -- not just to decide cache-hit-or-not, but so a
    refresh UPDATEs that row instead of trying to INSERT a second one and
    violating the table's unique constraint on that pair.
    """
    as_of = as_of or date.today()
    existing = (
        await session.execute(
            select(InsiderNarrative).where(
                InsiderNarrative.entity_id == entity_id, InsiderNarrative.as_of_date == as_of,
            )
        )
    ).scalar_one_or_none()
    if existing is not None and not force_refresh:
        return existing
    if not client.enabled:
        return existing

    context = await assemble_insider_context(session, entity_id)
    if context is None:
        return existing

    try:
        narrative_text = await generate_insider_narrative(client, context)
    except Exception:  # noqa: BLE001
        logger.warning("generate_insider_narrative failed for entity %s", entity_id, exc_info=True)
        return existing
    if not narrative_text:
        return existing

    prompt = load_prompt("insider_narrative")
    fields = dict(
        narrative=narrative_text,
        signal_summary={"signals": context.signals, "ticker": context.ticker},
        congressional_summary={"trades": context.congressional_trades},
        model=model_for_tier(prompt.tier), prompt_id=prompt.id, prompt_version=prompt.version,
    )
    if existing is not None:
        for key, value in fields.items():
            setattr(existing, key, value)
        row = existing
    else:
        row = InsiderNarrative(id=uuid.uuid4(), entity_id=entity_id, as_of_date=as_of, **fields)
        session.add(row)
    await session.flush()
    return row
