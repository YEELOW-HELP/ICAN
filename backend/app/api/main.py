import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin import router as admin_router
from app.api.crm import router as crm_router
from app.api.mnp import router as mnp_router
from app.api.mnp_admin import router as mnp_admin_router
from app.api.market import router as market_router
from app.api.workspace import router as workspace_router
from app.api.person_kb import router as person_kb_router
from app.db.models import User
from app.db.session import get_session
from app.db.session import async_session_factory
from app.schemas.profile import ProfileOut
from app.services import profile_service
from app.core.paths import FRONTEND_ROOT

logger = logging.getLogger(__name__)


async def _market_refresh_loop() -> None:
    from app.core.config import settings
    from app.services.market_data.dcz import refresh_if_changed

    while True:
        try:
            async with async_session_factory() as session:
                result = await refresh_if_changed(session)
                logger.info("Market data refresh: %s", result)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Market data refresh failed; the API will keep the last verified snapshot")
        await asyncio.sleep(max(1, settings.market_data_refresh_hours) * 3600)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app.core.config import settings

    task = None
    if settings.market_data_auto_refresh:
        task = asyncio.create_task(_market_refresh_loop(), name="dcz-market-refresh")
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


app = FastAPI(title="ICAN Screening MVP", lifespan=lifespan)
app.include_router(admin_router)
app.include_router(crm_router)
app.include_router(mnp_router)
app.include_router(mnp_admin_router)
app.include_router(person_kb_router)
app.include_router(market_router)
app.include_router(workspace_router)

_FRONTEND_DIR = FRONTEND_ROOT / "legacy" / "admin"
if _FRONTEND_DIR.is_dir():
    app.mount("/dashboard", StaticFiles(directory=_FRONTEND_DIR, html=True), name="dashboard")

_MNP_REACT_DIST = FRONTEND_ROOT / "dist"
_MNP_LEGACY_FRONTEND = FRONTEND_ROOT / "legacy" / "mnp"
# The React/Vite application is the new frontend.  Keeping the legacy static
# client as a fallback makes the migration reversible until feature parity is
# confirmed in the consultant-workspace branch.
_MNP_FRONTEND_DIR = _MNP_REACT_DIST if _MNP_REACT_DIST.is_dir() else _MNP_LEGACY_FRONTEND
if _MNP_FRONTEND_DIR.is_dir():
    app.mount("/mnp", StaticFiles(directory=_MNP_FRONTEND_DIR, html=True), name="mnp")


@app.middleware("http")
async def _no_cache_for_mnp_frontend(request, call_next):
    """Prevent a stale product shell during active frontend development."""

    response = await call_next(request)
    if request.url.path.startswith("/mnp/") or request.url.path == "/mnp":
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


async def _get_user_or_404(telegram_id: int, session: AsyncSession) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.get("/users/{telegram_id}/profile", response_model=ProfileOut)
async def get_user_profile(telegram_id: int, session: AsyncSession = Depends(get_session)):
    user = await _get_user_or_404(telegram_id, session)
    profile = await profile_service.get_profile(session, user)
    return profile


@app.get("/users/{telegram_id}/messages")
async def get_user_messages(telegram_id: int, session: AsyncSession = Depends(get_session)):
    user = await _get_user_or_404(telegram_id, session)
    messages = await profile_service.get_messages(session, user)
    return [
        {"role": m.role.value, "content": m.content, "created_at": m.created_at}
        for m in messages
    ]
