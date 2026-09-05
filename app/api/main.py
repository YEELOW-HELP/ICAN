from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin import router as admin_router
from app.api.crm import router as crm_router
from app.api.mnp import router as mnp_router
from app.api.mnp_admin import router as mnp_admin_router
from app.api.person_kb import router as person_kb_router
from app.db.models import User
from app.db.session import get_session
from app.schemas.profile import ProfileOut
from app.services import profile_service

app = FastAPI(title="ICAN Screening MVP")
app.include_router(admin_router)
app.include_router(crm_router)
app.include_router(mnp_router)
app.include_router(mnp_admin_router)
app.include_router(person_kb_router)

_FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "admin_frontend"
if _FRONTEND_DIR.is_dir():
    app.mount("/dashboard", StaticFiles(directory=_FRONTEND_DIR, html=True), name="dashboard")

_MNP_FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "mnp_frontend"
if _MNP_FRONTEND_DIR.is_dir():
    app.mount("/mnp", StaticFiles(directory=_MNP_FRONTEND_DIR, html=True), name="mnp")


@app.middleware("http")
async def _no_cache_for_mnp_frontend(request, call_next):
    """MNP V1's frontend has no build step and ships straight from disk
    -- during active development a browser silently serving a stale
    cached copy of index.html/api.js/app.js after a real fix has already
    shipped is a genuine, repeatedly-observed failure mode (caught during
    Founder Acceptance Testing), not a hypothetical one. Forces
    revalidation on every request for this one static mount; every other
    route is untouched."""

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
