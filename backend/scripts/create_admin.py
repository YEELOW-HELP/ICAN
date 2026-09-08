"""Create or update an admin-dashboard login. There's no self-registration by
design (ТЗ п.11/15) — accounts are provisioned out-of-band by whoever runs this.

Usage:
    python -m scripts.create_admin admin@example.com "a-strong-password" admin
    python -m scripts.create_admin manager@example.com "a-strong-password" manager
"""

import asyncio
import sys

from sqlalchemy import select

from app.core.security import hash_password
from app.db.models import AdminRole, AdminUser
from app.db.session import async_session_factory


async def main(email: str, password: str, role: str) -> None:
    role_enum = AdminRole(role.lower())

    async with async_session_factory() as session:
        result = await session.execute(select(AdminUser).where(AdminUser.email == email))
        admin = result.scalar_one_or_none()

        if admin is None:
            admin = AdminUser(email=email, password_hash=hash_password(password), role=role_enum)
            session.add(admin)
            action = "Created"
        else:
            admin.password_hash = hash_password(password)
            admin.role = role_enum
            action = "Updated"

        await session.commit()
        print(f"{action} admin account: {email} ({role_enum.value})")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        raise SystemExit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3]))
