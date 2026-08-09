"""Layer 2 (AI_THREE_LAYER_REBUILD_PLAN.md §4.1): full-article body_text
extraction from raw HTML via trafilatura.

Unblocks news_dedup's content-fingerprint tier, FinBERT sentiment, and
entity linking -- all three degrade to title+summary (or skip entirely)
without a real article body, since Finnhub's ``/company-news`` response
only ever carries a headline and a short summary, never the full text.
"""
from __future__ import annotations

import logging

import httpx
import trafilatura

from src.config import settings

logger = logging.getLogger(__name__)

FETCH_TIMEOUT_SECONDS = 15.0
# A short article body isn't worth persisting over the summary already on
# hand -- likely a paywall stub, cookie-consent page, or extraction
# misfire rather than real body copy.
MIN_EXTRACTED_LENGTH = 200


def extract_body_text(html: str, *, url: str | None = None) -> str | None:
    """Pull the main article text out of a raw HTML page. Pure (no
    network) -- takes HTML already fetched by the caller. Returns ``None``
    when trafilatura can't find a confident main-content block, or the
    result is implausibly short.
    """
    if not html or not html.strip():
        return None
    try:
        text = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
        )
    except Exception:  # noqa: BLE001 — malformed HTML must never break ingestion
        logger.warning("trafilatura extraction raised for %s", url, exc_info=True)
        return None
    if not text or len(text) < MIN_EXTRACTED_LENGTH:
        return None
    return text


async def fetch_and_extract_body_text(
    url: str, *, timeout: float = FETCH_TIMEOUT_SECONDS
) -> str | None:
    """Fetch ``url`` and extract its main article text. Best-effort: any
    network failure, non-2xx status, or extraction miss returns ``None``
    rather than raising -- a connector's enrichment pass should never fail
    because one source site is unreachable or paywalled.
    """
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": settings.SEC_USER_AGENT},
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text
    except Exception as e:  # noqa: BLE001
        logger.info("body_text fetch failed for %s: %s", url, e)
        return None
    return extract_body_text(html, url=url)
