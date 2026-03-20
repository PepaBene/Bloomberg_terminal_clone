"""Test configuration and fixtures."""

import asyncio
import uuid
from collections.abc import AsyncGenerator
from datetime import date, datetime, timezone

import pytest
import pytest_asyncio
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


# Patch JSONB columns to use plain JSON under SQLite
@event.listens_for(Base.metadata, "before_create")
def _remap_jsonb(target, connection, **kw):
    if connection.dialect.name == "sqlite":
        for table in target.tables.values():
            for col in table.columns:
                if isinstance(col.type, JSONB):
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
