"""Local console setup: additive schema, author grants and private signing key.

Run `python -m scripts.console_setup` to create your personal local superadmin.
Passwords are read with getpass, never passed on the command line or logged.
"""
import asyncio
import argparse
import getpass
import os
import secrets
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def configure_local(db_path: Path):
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path.as_posix()}"
    if not os.environ.get("JWT_SECRET"):
        key_file = db_path.parent / ".console-jwt-key"
        key_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with key_file.open("x", encoding="utf-8") as f:
                f.write(secrets.token_urlsafe(48))
        except FileExistsError:
            pass
        os.environ["JWT_SECRET"] = key_file.read_text(encoding="utf-8").strip()


async def prepare_access():
    from sqlalchemy import select
    from app.api.main import app  # registers existing model metadata
    from app.db.models_person_kb import MnpPerson, MnpPersonAccess
    from app.db.models import AdminUser
    from app.db.models_platform import AuditLog
    from app.db.session import async_session_factory, engine
    async with engine.begin() as conn:
        await conn.run_sync(lambda connection: MnpPersonAccess.__table__.create(connection, checkfirst=True))
    async with async_session_factory() as session:
        logs = (await session.scalars(select(AuditLog).where(
            AuditLog.entity_type == "mnp_person", AuditLog.action == "person_created",
            AuditLog.actor_admin_id.is_not(None)))).all()
        for log in logs:
            try:
                person_id = uuid.UUID(log.entity_id)
            except ValueError:
                continue
            if not await session.get(MnpPerson, person_id) or not await session.get(AdminUser, log.actor_admin_id):
                continue
            if not await session.get(MnpPersonAccess, (person_id, log.actor_admin_id)):
                session.add(MnpPersonAccess(person_id=person_id, admin_id=log.actor_admin_id,
                                            is_creator=True, granted_by=log.actor_admin_id))
                await session.flush()
        await session.commit()
    await engine.dispose()


async def provision(email, password):
    from sqlalchemy import select
    from app.core.security import hash_password
    from app.db.models import AdminRole, AdminUser
    from app.db.models_platform import AuditLog
    from app.db.session import async_session_factory, engine
    async with async_session_factory() as session:
        admin = await session.scalar(select(AdminUser).where(AdminUser.email == email))
        if admin is None:
            admin = AdminUser(email=email, full_name="Власник", role=AdminRole.SUPER_ADMIN,
                              password_hash=hash_password(password), is_active=True)
            session.add(admin)
        else:
            admin.role = AdminRole.SUPER_ADMIN
            admin.password_hash = hash_password(password)
            admin.is_active = True
        await session.flush()
        session.add(AuditLog(actor_admin_id=admin.id, entity_type="staff", entity_id=str(admin.id),
                             action="local_superadmin_provisioned", after_snapshot={"role": "super_admin"}))
        # The known shared demo login must not retain access to the private console.
        demo = await session.scalar(select(AdminUser).where(AdminUser.email == "admin@mnp.local"))
        if demo and demo.id != admin.id:
            demo.is_active = False
        await session.commit()
    await engine.dispose()


async def has_superadmin():
    from sqlalchemy import select
    from app.db.models import AdminRole, AdminUser
    from app.db.session import async_session_factory, engine
    async with async_session_factory() as session:
        exists = await session.scalar(select(AdminUser.id).where(
            AdminUser.role == AdminRole.SUPER_ADMIN, AdminUser.is_active.is_(True)).limit(1))
    await engine.dispose()
    return exists is not None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ensure", action="store_true")
    args = parser.parse_args()
    from scripts.dev_seed import DEFAULT_DB_PATH
    if not DEFAULT_DB_PATH.exists():
        raise SystemExit("Спочатку запустіть dev.py для створення локальної бази")

    ensure_superadmin(DEFAULT_DB_PATH, only_if_missing=args.ensure)


def ensure_superadmin(db_path: Path, only_if_missing=True):
    configure_local(db_path)
    asyncio.run(prepare_access())
    if only_if_missing and asyncio.run(has_superadmin()):
        return
    print("\nПерше налаштування локального суперадміна.", flush=True)
    email = input("Ваш email суперадміна: ").strip().lower()
    if "@" not in email or len(email) > 255 or email == "admin@mnp.local":
        raise SystemExit("Вкажіть особистий email")
    print("Пароль вводиться приховано: символи не відображатимуться. Завершіть введення клавішею Enter.", flush=True)
    password = getpass.getpass("Новий пароль (від 8 символів): ")
    if len(password) < 8 or len(password.encode("utf-8")) > 72:
        raise SystemExit("Пароль: від 8 символів, до 72 байтів")
    if password != getpass.getpass("Повторіть пароль: "):
        raise SystemExit("Паролі не збігаються")
    asyncio.run(provision(email, password))
    print("Суперадміністратора налаштовано. Backend продовжує запуск.", flush=True)


if __name__ == "__main__":
    main()
