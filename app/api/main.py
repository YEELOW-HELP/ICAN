from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.session import get_session
from app.schemas.profile import ProfileOut
from app.services import profile_service

app = FastAPI(title="ICAN Screening MVP")


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
