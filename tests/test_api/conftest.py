"""Shared fixtures for API tests — overrides DB session with test SQLite.

Uses a transaction + savepoint pattern so each test gets full isolation:
a top-level transaction wraps each test and is rolled back in teardown,
while the app's session override uses savepoints (nested transactions)
so that any commit() inside application code only releases the savepoint
rather than the outer transaction.
"""

import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.types import JSON

from src.api.deps import get_session
from src.models.base import Base

# Ensure all models are imported so tables exist
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


TEST_DATABASE_URL = "sqlite+aiosqlite://"


@event.listens_for(Base.metadata, "before_create")
def _remap_jsonb_api(target, connection, **kw):
    if connection.dialect.name == "sqlite":
        for table in target.tables.values():
            for col in table.columns:
                if isinstance(col.type, JSONB):
                    col.type = JSON()


@pytest_asyncio.fixture(scope="module")
async def _api_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def _api_connection(_api_engine):
    """Open a connection and begin a transaction that will be rolled back after the test."""
    async with _api_engine.connect() as connection:
        transaction = await connection.begin()
        yield connection
        await transaction.rollback()


@pytest_asyncio.fixture
async def session(_api_connection) -> AsyncGenerator[AsyncSession, None]:
    """Provide a session bound to the per-test transaction.

    This session uses ``begin_nested()`` so that ``session.commit()``
    only releases a savepoint — the outer transaction is still rolled
    back after each test, giving full isolation.
    """
    sess = AsyncSession(bind=_api_connection, expire_on_commit=False)
    # Start a savepoint so that any commit() inside test code or app code
    # only releases this savepoint rather than the real transaction.
    await sess.begin_nested()

    @event.listens_for(sess.sync_session, "after_transaction_end")
    def _restart_savepoint(session, transaction):
        """Re-open a savepoint after each nested commit so subsequent
        operations continue inside the outer transaction."""
        if transaction.nested and not transaction._parent.nested:
            session.begin_nested()

    yield sess
    await sess.close()


@pytest_asyncio.fixture
async def client(_api_connection, session) -> AsyncGenerator[AsyncClient, None]:
    """Create a test HTTP client with the DB session wired to test SQLite.

    The dependency override returns the *same* session used by the test
    so that data seeded in the test is visible to the API handlers, and
    everything rolls back when the per-test transaction is aborted.
    """
    from src.api.app import create_app

    app = create_app()

    async def _override_session() -> AsyncGenerator[AsyncSession, None]:
        yield session

    app.dependency_overrides[get_session] = _override_session

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c

    app.dependency_overrides.clear()
