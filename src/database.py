"""Database engine and session management."""

from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings

_engine = None
_session_factory = None


def get_engine():
    """Lazily create the async engine."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.DATABASE_URL,
            pool_size=settings.DB_POOL_MIN,
            max_overflow=settings.DB_POOL_MAX - settings.DB_POOL_MIN,
            pool_pre_ping=True,
            echo=False,
        )
        if _engine.dialect.name == "postgresql":
            # M-001: register the pgvector asyncpg codec on every new
            # connection so SearchDocument.embedding round-trips as a
            # real list[float] instead of asyncpg raising on the
            # unrecognized `vector` OID.
            @event.listens_for(_engine.sync_engine, "connect")
            def _register_vector_codec(dbapi_connection, connection_record):
                from pgvector.asyncpg import register_vector

                dbapi_connection.run_async(lambda conn: register_vector(conn))

    return _engine


def get_session_factory():
    """Lazily create the session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


