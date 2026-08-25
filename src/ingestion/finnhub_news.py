"""Finnhub company-news connector.

Fetches the latest news for a company and populates ``news_articles`` +
``article_entity_links`` so the app's news endpoints serve real, current
headlines. Used by the on-demand freshness service (when a user opens a company
or news view) and by scheduled refresh.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import date, datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.ingestion.news_enrichment import enrich_new_articles
from src.ingestion.rate_limiter import RateLimiter
from src.models.news_article import ArticleEntityLink, NewsArticle

logger = logging.getLogger(__name__)

FINNHUB_NEWS_URL = "https://finnhub.io/api/v1/company-news"


class FinnhubNewsConnector:
    """Pulls company news from Finnhub for a single company at a time."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or getattr(settings, "FINNHUB_API_KEY", "")
        # Finnhub free tier allows 60 req/min; stay comfortably under.
        self.rate_limiter = RateLimiter(max_requests=30, per_seconds=60.0)

    async def _fetch(self, symbol: str, frm: str, to: str) -> list[dict]:
        if not self.api_key:
            logger.warning("FINNHUB_API_KEY not set — skipping news fetch")
            return []
        await self.rate_limiter.acquire()
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                FINNHUB_NEWS_URL,
                params={"symbol": symbol, "from": frm, "to": to, "token": self.api_key},
            )
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else []

    async def fetch_for_entity(
        self, session: AsyncSession, entity_id: uuid.UUID, symbol: str, *, days: int = 7
    ) -> int:
        """Fetch recent news for ``symbol`` and link it to ``entity_id``.

        Returns the number of newly-inserted articles. Idempotent: existing
        articles (by source_url) and existing entity links are reused.
        """
        if not symbol:
            return 0
        to = date.today()
        frm = to - timedelta(days=days)
        try:
            articles = await self._fetch(symbol, frm.isoformat(), to.isoformat())
        except Exception as e:  # network / rate-limit / bad symbol — non-fatal
            logger.warning("Finnhub news fetch failed for %s: %s", symbol, e)
            return 0

        new_count = 0
        new_article_ids: list[uuid.UUID] = []
        for art in articles:
            url = (art.get("url") or "").strip()
            headline = (art.get("headline") or "").strip()
            if not url or not headline:
                continue

            ts = art.get("datetime")
            try:
                pub = datetime.fromtimestamp(int(ts), timezone.utc).date() if ts else to
            except (ValueError, OSError, TypeError):
                pub = to

            # Reuse the article if we've already stored this URL (autoflush makes
            # in-batch duplicates resolve to the same row).
            article_id = await session.scalar(
                select(NewsArticle.id).where(NewsArticle.source_url == url)
            )
            if article_id is None:
                article_id = uuid.uuid4()
                session.add(
                    NewsArticle(
                        id=article_id,
                        source_url=url[:1000],
                        title=headline[:500],
                        summary=(art.get("summary") or headline),
                        source_name=(art.get("source") or "Finnhub")[:100],
                        publish_date=pub,
                        ingest_date=to,
                        news_type="COMPANY_NEWS",
                        content_hash=hashlib.sha256(url.encode()).hexdigest(),
                        is_propagated=False,
                    )
                )
                new_count += 1
                new_article_ids.append(article_id)

            link_exists = await session.scalar(
                select(ArticleEntityLink.id).where(
                    ArticleEntityLink.article_id == article_id,
                    ArticleEntityLink.entity_id == entity_id,
                )
            )
            if link_exists is None:
                session.add(
                    ArticleEntityLink(
                        id=uuid.uuid4(),
                        article_id=article_id,
                        entity_id=entity_id,
                        relevance_score=1.0,
                        is_primary=True,
                        mention_count=1,
                    )
                )

        await session.commit()
        if new_count:
            logger.info("Finnhub news: %s → %d new articles", symbol, new_count)
            try:
                enriched = await enrich_new_articles(
                    session, new_article_ids, primary_entity_id=entity_id,
                )
                logger.info(
                    "Finnhub news: enriched %d/%d new articles for %s",
                    enriched, len(new_article_ids), symbol,
                )
            except Exception as e:  # noqa: BLE001 — enrichment is best-effort, never blocks ingestion
                logger.warning("News enrichment failed for %s: %s", symbol, e)
        return new_count
