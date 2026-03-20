"""Elasticsearch bulk indexing for entities and securities."""

import logging
from typing import Any

from elasticsearch import AsyncElasticsearch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.config import settings
from src.models.entity import Entity, EntityIdentifier, EntityName
from src.models.security import Security, SecurityIdentifier
from src.search.indices import (
    ENTITY_INDEX,
    ENTITY_MAPPING,
    SECURITY_INDEX,
    SECURITY_MAPPING,
)

logger = logging.getLogger(__name__)


async def get_es_client() -> AsyncElasticsearch:
    """Create an Elasticsearch async client."""
    return AsyncElasticsearch(settings.ELASTICSEARCH_URL)


async def ensure_indices(es: AsyncElasticsearch) -> None:
    """Create indices if they don't exist."""
    for index_name, mapping in [
        (ENTITY_INDEX, ENTITY_MAPPING),
        (SECURITY_INDEX, SECURITY_MAPPING),
    ]:
        if not await es.indices.exists(index=index_name):
            await es.indices.create(index=index_name, body=mapping)
            logger.info(f"Created index: {index_name}")


def _entity_to_doc(entity: Entity) -> dict[str, Any]:
    """Convert an Entity model to an ES document."""
    aliases = []
    if hasattr(entity, "names") and entity.names:
        aliases = [n.name_value for n in entity.names]

    identifiers = []
    if hasattr(entity, "identifiers") and entity.identifiers:
        identifiers = [
            {"type": i.identifier_type, "value": i.identifier_value}
            for i in entity.identifiers
        ]

    return {
        "entity_id": str(entity.entity_id),
        "legal_name": entity.legal_name,
        "short_name": entity.short_name,
        "aliases": aliases,
        "entity_type": entity.entity_type,
        "status": entity.status,
        "country": entity.incorporation_country,
        "gics_sector": entity.gics_sector,
        "gics_industry": entity.gics_industry,
        "identifiers": identifiers,
    }


def _security_to_doc(security: Security) -> dict[str, Any]:
    """Convert a Security model to an ES document."""
    doc: dict[str, Any] = {
        "security_id": str(security.security_id),
        "name": security.name,
        "short_name": security.short_name,
        "asset_class": security.asset_class,
        "security_type": security.security_type,
        "exchange": security.primary_exchange_mic,
        "status": security.status,
        "issuer_entity_id": str(security.issuer_entity_id) if security.issuer_entity_id else None,
    }

    if hasattr(security, "identifiers") and security.identifiers:
        for ident in security.identifiers:
            key_map = {
                "TICKER": "ticker",
                "ISIN": "isin",
                "CUSIP": "cusip",
                "FIGI": "figi",
            }
            field = key_map.get(ident.identifier_type)
            if field:
                doc[field] = ident.identifier_value

    return doc


async def index_entity(es: AsyncElasticsearch, entity: Entity) -> None:
    """Index a single entity."""
    doc = _entity_to_doc(entity)
    await es.index(index=ENTITY_INDEX, id=doc["entity_id"], body=doc)


async def index_security(es: AsyncElasticsearch, security: Security) -> None:
    """Index a single security."""
    doc = _security_to_doc(security)
    await es.index(index=SECURITY_INDEX, id=doc["security_id"], body=doc)


async def bulk_index_entities(
    es: AsyncElasticsearch, session: AsyncSession, batch_size: int = 500
) -> int:
    """Bulk index all entities from the database."""
    query = select(Entity).options(
        selectinload(Entity.names),
        selectinload(Entity.identifiers),
    )
    result = await session.execute(query)
    entities = result.scalars().all()

    count = 0
    actions = []
    for entity in entities:
        doc = _entity_to_doc(entity)
        actions.append({"index": {"_index": ENTITY_INDEX, "_id": doc["entity_id"]}})
        actions.append(doc)
        count += 1

        if len(actions) >= batch_size * 2:
            await es.bulk(body=actions)
            actions = []

    if actions:
        await es.bulk(body=actions)

    logger.info(f"Indexed {count} entities")
    return count


async def bulk_index_securities(
    es: AsyncElasticsearch, session: AsyncSession, batch_size: int = 500
) -> int:
    """Bulk index all securities from the database."""
    query = select(Security).options(
        selectinload(Security.identifiers),
    )
    result = await session.execute(query)
    securities = result.scalars().all()

    count = 0
    actions = []
    for security in securities:
        doc = _security_to_doc(security)
        actions.append({"index": {"_index": SECURITY_INDEX, "_id": doc["security_id"]}})
        actions.append(doc)
        count += 1

        if len(actions) >= batch_size * 2:
            await es.bulk(body=actions)
            actions = []

    if actions:
        await es.bulk(body=actions)

    logger.info(f"Indexed {count} securities")
    return count


async def reindex_all(session: AsyncSession) -> dict[str, int]:
    """Full reindex of all entities and securities."""
    es = await get_es_client()
    try:
        await ensure_indices(es)
        entities_count = await bulk_index_entities(es, session)
        securities_count = await bulk_index_securities(es, session)
        return {"entities": entities_count, "securities": securities_count}
    finally:
        await es.close()


async def search_entities(
    query: str,
    filters: dict[str, Any] | None = None,
    size: int = 10,
) -> dict[str, Any]:
    """Search entities using Elasticsearch."""
    es = await get_es_client()
    try:
        must = [
            {
                "multi_match": {
                    "query": query,
                    "fields": [
                        "legal_name^3",
                        "legal_name.autocomplete^2",
                        "short_name^2",
                        "aliases",
                    ],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                }
            }
        ]

        filter_clauses = []
        if filters:
            for field, value in filters.items():
                if value:
                    filter_clauses.append({"term": {field: value}})

        body = {
            "query": {
                "bool": {
                    "must": must,
                    "filter": filter_clauses,
                }
            },
            "size": size,
        }

        result = await es.search(index=ENTITY_INDEX, body=body)
        hits = result.get("hits", {})
        return {
            "total": hits.get("total", {}).get("value", 0),
            "results": [
                {**hit["_source"], "score": hit["_score"]}
                for hit in hits.get("hits", [])
            ],
        }
    finally:
        await es.close()


async def search_securities(
    query: str,
    filters: dict[str, Any] | None = None,
    size: int = 10,
) -> dict[str, Any]:
    """Search securities using Elasticsearch."""
    es = await get_es_client()
    try:
        must = [
            {
                "multi_match": {
                    "query": query,
                    "fields": [
                        "name^3",
                        "name.autocomplete^2",
                        "short_name^2",
                        "ticker^4",
                        "ticker.autocomplete^3",
                        "isin",
                    ],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                }
            }
        ]

        filter_clauses = []
        if filters:
            for field, value in filters.items():
                if value:
                    filter_clauses.append({"term": {field: value}})

        body = {
            "query": {
                "bool": {
                    "must": must,
                    "filter": filter_clauses,
                }
            },
            "size": size,
        }

        result = await es.search(index=SECURITY_INDEX, body=body)
        hits = result.get("hits", {})
        return {
            "total": hits.get("total", {}).get("value", 0),
            "results": [
                {**hit["_source"], "score": hit["_score"]}
                for hit in hits.get("hits", [])
            ],
        }
    finally:
        await es.close()
