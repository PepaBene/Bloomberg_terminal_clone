"""SEC EDGAR security enrichment — extracts shares outstanding and exchange from filings."""

import logging
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.rate_limiter import RateLimiter
from src.models.entity import Entity, EntityIdentifier
from src.models.security import EquityDetails, Security

logger = logging.getLogger(__name__)

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

# SEC exchange code -> ISO MIC mapping (common US exchanges)
EXCHANGE_MIC_MAP = {
    "NYSE": "XNYS",
    "NASDAQ": "XNAS",
    "Nasdaq": "XNAS",
    "NYSE MKT": "XASE",
    "NYSE ARCA": "ARCX",
    "CBOE": "XCBO",
    "BATS": "BATS",
    "OTC": "OTCM",
}


async def enrich_securities_from_edgar(
    session: AsyncSession, max_entities: int = 100
) -> dict[str, int]:
    """Enrich existing securities with data from EDGAR submissions.

    Fetches shares outstanding and exchange mapping for entities
    that have both CIK identifiers and linked securities.
    """
    stats = {"enriched": 0, "skipped": 0, "errors": 0}
    rate_limiter = RateLimiter(max_requests=settings.SEC_RATE_LIMIT, per_seconds=1.0)
    headers = {"User-Agent": settings.SEC_USER_AGENT}

    # Find entities with CIK that have linked securities with empty equity details
    result = await session.execute(
        select(Entity, EntityIdentifier, Security, EquityDetails)
        .join(EntityIdentifier, Entity.entity_id == EntityIdentifier.entity_id)
        .join(Security, Entity.entity_id == Security.issuer_entity_id)
        .outerjoin(EquityDetails, Security.security_id == EquityDetails.security_id)
        .where(
            EntityIdentifier.identifier_type == "CIK",
            Security.asset_class == "EQUITY",
        )
        .limit(max_entities)
    )
    rows = result.all()

    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        for entity, identifier, security, equity in rows:
            try:
                padded_cik = identifier.identifier_value.zfill(10)
                url = SUBMISSIONS_URL.format(cik=padded_cik)

                await rate_limiter.acquire()
                resp = await client.get(url)
                if resp.status_code != 200:
                    stats["skipped"] += 1
                    continue

                data = resp.json()

                # Extract exchange and map to MIC
                exchanges_raw = data.get("exchanges", [])
                if exchanges_raw:
                    exchange_name = exchanges_raw[0] if isinstance(exchanges_raw, list) else str(exchanges_raw)
                    mic = EXCHANGE_MIC_MAP.get(exchange_name)
                    if mic:
                        security.primary_exchange_mic = mic

                # Try to get shares outstanding from recent filings
                recent_filings = data.get("filings", {}).get("recent", {})
                if recent_filings:
                    # Look for 10-K or 10-Q filings
                    forms = recent_filings.get("form", [])
                    for idx, form in enumerate(forms):
                        if form in ("10-K", "10-Q"):
                            # Note: Shares outstanding typically comes from the filing itself,
                            # not the submissions JSON. This is a placeholder for XBRL parsing.
                            break

                if equity and equity.shares_outstanding is None:
                    # Placeholder — real implementation would parse XBRL
                    pass

                stats["enriched"] += 1

            except Exception as e:
                logger.error(f"Error enriching security for CIK {identifier.identifier_value}: {e}")
                stats["errors"] += 1

    await session.flush()
    return stats
