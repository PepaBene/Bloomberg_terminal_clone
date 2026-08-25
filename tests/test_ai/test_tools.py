"""Unit tests for src/ai/tools/*.

check_claim_support/web_search_tool_spec are pure. DataQueryTool/
CitationCheckTool.run are exercised against the SQLite test engine.
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.ai.tools.citation_check import CitationCheckTool, check_claim_support
from src.ai.tools.data_query import DataQueryTool
from src.ai.tools.web_search import DEFAULT_ALLOWED_DOMAINS, web_search_tool_spec


# --------------------------------------------------------------------------- #
# web_search (pure)
# --------------------------------------------------------------------------- #
def test_web_search_tool_spec_defaults():
    spec = web_search_tool_spec()
    assert spec["type"] == "web_search_20250305"
    assert spec["name"] == "web_search"
    assert spec["allowed_domains"] == DEFAULT_ALLOWED_DOMAINS
    assert "reuters.com" in spec["allowed_domains"]
    assert "sec.gov" in spec["allowed_domains"]


def test_web_search_tool_spec_custom_domains_and_uses():
    spec = web_search_tool_spec(max_uses=2, allowed_domains=["example.com"])
    assert spec["max_uses"] == 2
    assert spec["allowed_domains"] == ["example.com"]


# --------------------------------------------------------------------------- #
# citation_check (pure part)
# --------------------------------------------------------------------------- #
def test_check_claim_support_high_overlap():
    claim = "Revenue grew 12% to $4.2 billion in the third quarter"
    source = "The company reported that revenue grew 12% to $4.2 billion in Q3, driven by cloud demand."
    assert check_claim_support(claim, source) >= 0.6


def test_check_claim_support_low_overlap():
    claim = "Revenue grew 45% due to a new acquisition in Europe"
    source = "The weather in Paris was sunny with a light breeze."
    assert check_claim_support(claim, source) < 0.3


def test_check_claim_support_empty_inputs():
    assert check_claim_support("", "some source text") == 0.0
    assert check_claim_support("some claim", "") == 0.0
    assert check_claim_support("", "") == 0.0


# --------------------------------------------------------------------------- #
# CitationCheckTool (DB-backed)
# --------------------------------------------------------------------------- #
async def test_citation_check_tool_supported_claim(engine):
    from src.models.semantic_search import SearchDocument

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    doc_id = uuid.uuid4()
    async with factory() as session:
        session.add(SearchDocument(
            id=doc_id, source_type="unit_test", source_id="doc-1",
            chunk_index=0, chunk_text="Apple reported record iPhone revenue of $50 billion this quarter.",
        ))
        await session.commit()

    async with factory() as session:
        tool = CitationCheckTool(session)
        result = await tool.run(
            claim="Apple reported record iPhone revenue of $50 billion",
            document_ids=[str(doc_id)],
        )
    assert "supported=True" in result.content


async def test_citation_check_tool_unsupported_claim(engine):
    from src.models.semantic_search import SearchDocument

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    doc_id = uuid.uuid4()
    async with factory() as session:
        session.add(SearchDocument(
            id=doc_id, source_type="unit_test", source_id="doc-2",
            chunk_index=0, chunk_text="The weather in Paris was sunny today.",
        ))
        await session.commit()

    async with factory() as session:
        tool = CitationCheckTool(session)
        result = await tool.run(
            claim="Revenue grew 200% due to a acquisition in Asia",
            document_ids=[str(doc_id)],
        )
    assert "supported=False" in result.content


async def test_citation_check_tool_missing_document(session):
    tool = CitationCheckTool(session)
    result = await tool.run(claim="anything", document_ids=[str(uuid.uuid4())])
    assert "NOT grounded" in result.content


async def test_citation_check_tool_invalid_document_id(session):
    tool = CitationCheckTool(session)
    result = await tool.run(claim="anything", document_ids=["not-a-uuid"])
    assert "NOT grounded" in result.content


# --------------------------------------------------------------------------- #
# DataQueryTool (DB-backed)
# --------------------------------------------------------------------------- #
async def _seed_entity_and_metrics(session) -> uuid.UUID:
    from src.models.analytics import AnalyticsResult
    from src.models.entity import Entity
    from src.models.security import Security

    entity_id = uuid.uuid4()
    session.add(Entity(
        entity_id=entity_id, entity_type="PUBLIC_COMPANY",
        legal_name="MegaCorp Inc.", status="ACTIVE", source="TEST",
    ))
    security_id = uuid.uuid4()
    session.add(Security(
        security_id=security_id, security_type="COMMON_STOCK",
        issuer_entity_id=entity_id, name="MegaCorp Common Stock",
        status="ACTIVE", asset_class="EQUITY",
    ))
    await session.flush()
    session.add(AnalyticsResult(
        result_id=uuid.uuid4(), security_id=security_id, entity_id=entity_id,
        engine_id="E1", metric_name="ROE", metric_category="PROFITABILITY",
        value=18.2, unit="PERCENT", period="FY2025", as_of_date=date(2026, 1, 1),
    ))
    session.add(AnalyticsResult(
        result_id=uuid.uuid4(), security_id=security_id, entity_id=entity_id,
        engine_id="E1", metric_name="CURRENT_RATIO", metric_category="LIQUIDITY",
        value=1.8, unit="RATIO", period="FY2025", as_of_date=date(2026, 2, 1),
    ))
    await session.flush()
    return entity_id


async def test_data_query_tool_fetches_all_metrics(session):
    entity_id = await _seed_entity_and_metrics(session)
    tool = DataQueryTool(session)
    result = await tool.run(entity_id=str(entity_id))
    assert not result.is_error
    assert "ROE=18.2" in result.content
    assert "CURRENT_RATIO=1.8" in result.content


async def test_data_query_tool_filters_by_metric_name(session):
    entity_id = await _seed_entity_and_metrics(session)
    tool = DataQueryTool(session)
    result = await tool.run(entity_id=str(entity_id), metric_name="roe")
    assert "ROE=18.2" in result.content
    assert "CURRENT_RATIO" not in result.content


async def test_data_query_tool_no_data_for_unknown_entity(session):
    tool = DataQueryTool(session)
    result = await tool.run(entity_id=str(uuid.uuid4()))
    assert "No analytics_results" in result.content


async def test_data_query_tool_invalid_entity_id(session):
    tool = DataQueryTool(session)
    result = await tool.run(entity_id="not-a-uuid")
    assert result.is_error is True
