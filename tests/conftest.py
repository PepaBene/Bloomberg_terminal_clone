"""Test configuration and fixtures."""

import asyncio
import uuid
from collections.abc import AsyncGenerator
from datetime import date, datetime, timezone

import pytest
import pytest_asyncio
from pgvector.sqlalchemy import Vector
from sqlalchemy import event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.types import JSON

from src.models.base import Base

# ---------------------------------------------------------------------------
# SQLite compatibility: map JSONB → JSON so model tests work without Postgres
# ---------------------------------------------------------------------------
# Import all models so Base.metadata knows every table
import src.models.reference  # noqa: F401
import src.models.entity  # noqa: F401
import src.models.security  # noqa: F401
import src.models.quality  # noqa: F401
import src.models.governance  # noqa: F401
import src.models.macro  # noqa: F401
import src.models.fundamentals  # noqa: F401
import src.models.estimates  # noqa: F401
import src.models.ownership  # noqa: F401
import src.models.esg  # noqa: F401
import src.models.corporate_actions  # noqa: F401
import src.models.relationships  # noqa: F401
import src.models.auth  # noqa: F401
import src.models.analytics  # noqa: F401  (Pillar 2)
import src.models.screening  # noqa: F401  (Pillar 2 - E4)
import src.models.flows  # noqa: F401  (Pillar 2 - E6)
import src.models.risk  # noqa: F401  (Pillar 2 - E5)
import src.models.quant  # noqa: F401  (Pillar 2 - E7)
import src.models.scenario  # noqa: F401  (Pillar 2 - E8)
import src.models.capital_structure  # noqa: F401  (Pillar 1 Supplement)
import src.models.debt_maturity  # noqa: F401  (Pillar 1 Supplement)
import src.models.credit_rating  # noqa: F401  (Pillar 1 Supplement)
import src.models.calendar  # noqa: F401  (Pillar 1 Supplement)
import src.models.yield_curve  # noqa: F401  (Pillar 1 Supplement P2)
import src.models.fed_meeting  # noqa: F401  (Pillar 1 Supplement P2)
import src.models.ma_deals  # noqa: F401  (Pillar 1 Supplement P3)
import src.models.ipo  # noqa: F401  (Pillar 1 Supplement P3)
import src.models.earnings_intelligence  # noqa: F401  (Pillar 1 Supplement P3)
import src.models.fund_holdings  # noqa: F401  (Pillar 1 Supplement P4)
import src.models.executives  # noqa: F401  (Pillar 1 Supplement P4)
import src.models.technical_studies  # noqa: F401  (Pillar 1 Supplement P5)
import src.models.custom_classifications  # noqa: F401  (Pillar 1 Supplement P5)
import src.models.esg_temperature  # noqa: F401  (Pillar 1 Supplement P5)
import src.models.yield_curve_analytics  # noqa: F401  (Pillar 2 Supplement P1)
import src.models.default_risk  # noqa: F401  (Pillar 2 Supplement P2)
import src.models.backtesting  # noqa: F401  (Pillar 2 Supplement P3)
import src.models.benchmark  # noqa: F401  (Pillar 2 Frontend Bugs 93-95)
import src.models.custom_index  # noqa: F401  (Pillar 2 Supplement P4)
import src.models.portfolio_upload  # noqa: F401  (Pillar 2 Supplement P4)
import src.models.market_movers  # noqa: F401  (Pillar 2 Supplement P5)
import src.models.custom_data  # noqa: F401  (Pillar 2 Supplement P6)
import src.models.company_intelligence  # noqa: F401  (Pillar 2 Supplement P7)
import src.models.sentiment  # noqa: F401  (Pillar 2 Supplement P8)
import src.models.treasury  # noqa: F401  (D11 FI Supplement P2)
import src.models.corporate_bond  # noqa: F401  (D11 FI Supplement P4)
import src.models.agency_bond  # noqa: F401  (D11 FI Supplement P8)
import src.models.credit_spread  # noqa: F401  (D11 FI Supplement P6)
import src.models.bond_issuance  # noqa: F401  (D11 FI Supplement P7)
import src.models.filing_intelligence  # noqa: F401  (Pillar 3 Phase 1)
import src.models.insider_intelligence  # noqa: F401  (Pillar 3 Phase 1)
import src.models.governance_intelligence  # noqa: F401  (Pillar 3 Phase 1)
import src.models.news_article  # noqa: F401  (Pillar 3 Phase 1)
import src.models.industry_intelligence  # noqa: F401  (Pillar 3 Phase 3A)
import src.models.competitive_intelligence  # noqa: F401  (Pillar 3 Phase 3A)
import src.models.country_risk  # noqa: F401  (Pillar 3 Phase 3B)
import src.models.global_macro  # noqa: F401  (Pillar 3 Phase 3B)
import src.models.commodity_intelligence  # noqa: F401  (Pillar 3 Phase 3B)
import src.models.political_intelligence  # noqa: F401  (Pillar 3 Phase 3B)
import src.models.fi_intelligence  # noqa: F401  (Pillar 3 Phase 3C)
import src.models.alert_expansion  # noqa: F401  (Pillar 3 Phase 3C)
import src.models.company_primer_model  # noqa: F401  (Pillar 3 Phase 4A)
import src.models.morning_briefing  # noqa: F401  (Pillar 3 Phase 4A)
import src.models.anomaly_detection  # noqa: F401  (Pillar 3 Phase 4A)
import src.models.semantic_search  # noqa: F401  (Pillar 3 Phase 4B)
import src.models.investment_thesis  # noqa: F401  (Pillar 3 Phase 4B)
import src.models.analyst_qa  # noqa: F401  (Pillar 3 Phase 4B)
import src.models.macro_themes  # noqa: F401  (Pillar 3 Phase 4C)
import src.models.scenario_impact  # noqa: F401  (Pillar 3 Phase 4C)
import src.models.intelligent_alerts  # noqa: F401  (Pillar 3 Phase 4C)
import src.models.portfolio  # noqa: F401  (Pillar 4 Phase 1)
import src.models.position  # noqa: F401  (Pillar 4 Phase 1)
import src.models.transaction  # noqa: F401  (Pillar 4 Phase 1)
import src.models.nav_snapshot  # noqa: F401  (Pillar 4 Phase 1)
import src.models.portfolio_watchlist  # noqa: F401  (Pillar 4 Phase 1)
import src.models.performance  # noqa: F401  (Pillar 4 Phase 2)
import src.models.attribution  # noqa: F401  (Pillar 4 Phase 2)
import src.models.portfolio_risk  # noqa: F401  (Pillar 4 Phase 3)
import src.models.compliance  # noqa: F401  (Pillar 4 Phase 3)
import src.models.congressional_trades  # noqa: F401  (Financial Analysis Suite)
import src.models.ai_call_log  # noqa: F401  (AI core — Phase 0 telemetry)
import src.models.subsidiary  # noqa: F401  (Complex Structure data-source build)


# Patch JSONB (and pgvector Vector) columns to use plain JSON under SQLite —
# SQLite has no native JSONB or vector type, and tests don't need real ANN
# search, just round-tripping a list[float].
@event.listens_for(Base.metadata, "before_create")
def _remap_jsonb(target, connection, **kw):
    if connection.dialect.name == "sqlite":
        for table in target.tables.values():
            for col in table.columns:
                if isinstance(col.type, (JSONB, Vector)):
                    col.type = JSON()


# Use an in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite://"


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine():
    """Create test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


# ── Factory Fixtures ────────────────────────────────────────────────


@pytest.fixture
def country_data():
    """Sample country data."""
    return {
        "country_code_alpha2": "US",
        "country_code_alpha3": "USA",
        "country_code_numeric": "840",
        "name": "United States",
        "official_name": "United States of America",
        "capital": "Washington, D.C.",
        "continent": "North America",
        "region": "Americas",
        "subregion": "Northern America",
        "currency_code": "USD",
        "development_status": "DEVELOPED",
        "is_active": True,
    }


@pytest.fixture
def currency_data():
    """Sample currency data."""
    return {
        "currency_code": "USD",
        "name": "US Dollar",
        "numeric_code": "840",
        "minor_unit": 2,
        "is_active": True,
    }


@pytest.fixture
def entity_data():
    """Sample entity data."""
    return {
        "entity_id": uuid.uuid4(),
        "entity_type": "PUBLIC_COMPANY",
        "legal_name": "Apple Inc.",
        "short_name": "Apple",
        "status": "ACTIVE",
        "incorporation_country": "US",
        "incorporation_state": "CA",
        "fiscal_year_end": "09-30",
        "reporting_currency": "USD",
        "accounting_standard": "US_GAAP",
        "source": "SEC_EDGAR",
        "confidence_score": 0.99,
    }


@pytest.fixture
def security_data():
    """Sample security data."""
    return {
        "security_id": uuid.uuid4(),
        "security_type": "COMMON_STOCK",
        "name": "Apple Inc. Common Stock",
        "short_name": "AAPL",
        "status": "ACTIVE",
        "asset_class": "EQUITY",
        "primary_exchange_mic": "XNAS",
        "primary_currency": "USD",
    }
