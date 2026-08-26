import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.db.base import Base
from app.db import models  # noqa: F401  (registers models on Base.metadata)
from app.db import models_crm  # noqa: F401
from app.db import models_identity  # noqa: F401
from app.db import models_access  # noqa: F401
from app.db import models_assessment  # noqa: F401
from app.db import models_platform  # noqa: F401
from app.db import models_profile  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    # asyncpg-only: Neon's pooled endpoint runs PgBouncer in transaction mode,
    # which is incompatible with asyncpg's server-side prepared statement cache.
    connect_args = {"statement_cache_size": 0} if "asyncpg" in settings.database_url else {}
    connectable = create_async_engine(
        settings.database_url,
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
