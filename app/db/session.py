from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    # Neon's pooled endpoint runs PgBouncer in transaction mode, which is
    # incompatible with asyncpg's server-side prepared statement cache.
    # asyncpg-only: sqlite3 (used for local dev/manual smoke testing --
    # migrations/env.py already has this exact same conditional) rejects
    # this kwarg outright.
    connect_args={"statement_cache_size": 0} if "asyncpg" in settings.database_url else {},
)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session
