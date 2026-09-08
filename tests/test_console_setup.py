"""The owner bootstrap provisions only the selected local database."""
import pytest
from sqlalchemy import select

from app.core.security import hash_password, verify_password
from app.db.models import AdminRole, AdminUser
from app.db import session as db_session
from scripts.console_setup import configure_local, has_superadmin, provision


def test_local_signing_key_is_persistent_and_environment_is_respected(tmp_path, monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setenv("DATABASE_URL", "unused-test-value")
    database = tmp_path / "local.sqlite"
    configure_local(database)
    import os
    first = os.environ["JWT_SECRET"]
    assert len(first) >= 48
    monkeypatch.delenv("JWT_SECRET")
    configure_local(database)
    assert os.environ["JWT_SECRET"] == first
    monkeypatch.setenv("JWT_SECRET", "explicit-test-secret")
    configure_local(database)
    assert os.environ["JWT_SECRET"] == "explicit-test-secret"


@pytest.mark.asyncio
async def test_personal_owner_setup_disables_shared_demo(session_factory, monkeypatch):
    monkeypatch.setattr(db_session, "async_session_factory", session_factory)
    class Disposable:
        async def dispose(self):
            pass
    monkeypatch.setattr(db_session, "engine", Disposable())
    async with session_factory() as session:
        session.add(AdminUser(email="admin@mnp.local", password_hash=hash_password("demo-password"),
                               role=AdminRole.ADMIN, is_active=True))
        await session.commit()
    assert await has_superadmin() is False
    await provision("owner@example.com", "private-test-password")
    assert await has_superadmin() is True
    async with session_factory() as session:
        owner = await session.scalar(select(AdminUser).where(AdminUser.email == "owner@example.com"))
        demo = await session.scalar(select(AdminUser).where(AdminUser.email == "admin@mnp.local"))
        assert owner.role == AdminRole.SUPER_ADMIN and owner.is_active
        assert verify_password("private-test-password", owner.password_hash)
        assert demo.is_active is False
