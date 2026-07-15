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
import src.models.earnings_transcript  # noqa: F401  (Pillar 3 Phase 2)
import src.models.economic_calendar  # noqa: F401  (Pillar 3 Phase 2)
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
import src.models.subsidiary  # noqa: F401  (Complex Structure data-source build)


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


@pytest_asyncio.fixture
async def test_user(session: AsyncSession):
    """A real, active User row (M-004/M-005: full-auth tests need a real
    account to authenticate as, not just an arbitrary user_id string)."""
    import uuid as _uuid

    from src.api.auth.security import hash_password
    from src.models.auth import User

    user = User(
        user_id=_uuid.uuid4(),
        username=f"test_user_{_uuid.uuid4().hex[:8]}",
        email=f"{_uuid.uuid4().hex[:8]}@test.example",
        hashed_password=hash_password("test-password-123"),
        role="ANALYST",
        is_active=True,
    )
    session.add(user)
    await session.flush()
    return user


@pytest_asyncio.fixture
async def auth_headers(test_user) -> dict[str, str]:
    """Bearer-token Authorization header for `test_user`."""
    from src.api.auth.jwt import create_access_token

    token = create_access_token(data={"sub": test_user.username, "role": test_user.role})
    return {"Authorization": f"Bearer {token}"}
