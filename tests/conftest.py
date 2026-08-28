import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db import models  # noqa: F401
from app.db import models_crm  # noqa: F401
from app.db import models_identity  # noqa: F401
from app.db import models_access  # noqa: F401
from app.db import models_assessment  # noqa: F401
from app.db import models_platform  # noqa: F401
from app.db import models_profile  # noqa: F401
from app.db import models_knowledge  # noqa: F401
from app.db import models_direction  # noqa: F401
from app.db import models_basic_assessment  # noqa: F401


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory

    await engine.dispose()


@pytest_asyncio.fixture
async def session(session_factory):
    async with session_factory() as s:
        yield s
