from datetime import timedelta

import pytest

from app.mongo_runtime.auth import Login, UserRegister, register_user, unified_login
from app.mongo_runtime.core import now, token_digest


class Collection:
    def __init__(self, rows=()):
        self.rows = {row["_id"]: dict(row) for row in rows}

    @staticmethod
    def matches(row, query):
        for key, expected in query.items():
            actual = row.get(key)
            if isinstance(expected, dict) and "$ne" in expected:
                if actual == expected["$ne"]:
                    return False
            elif isinstance(expected, dict) and "$gt" in expected:
                if actual is None or actual <= expected["$gt"]:
                    return False
            elif actual != expected:
                return False
        return True

    async def find_one(self, query):
        return next((dict(row) for row in self.rows.values() if self.matches(row, query)), None)

    async def insert_one(self, row):
        self.rows[row["_id"]] = dict(row)

    async def update_one(self, query, update):
        row = next(row for row in self.rows.values() if self.matches(row, query))
        row.update(update.get("$set", {}))


class Database:
    def __init__(self, sessions=()):
        self.admin_users = Collection()
        self.mnp_user_accounts = Collection()
        self.mnp_web_sessions = Collection(sessions)


@pytest.mark.asyncio
async def test_registered_client_uses_the_same_login_form_as_staff():
    db = Database()
    registered = await register_user(
        UserRegister(email="client@example.com", password="client-password"), db, None,
    )

    logged_in = await unified_login(
        Login(email="client@example.com", password="client-password"), db,
    )

    assert registered["account_type"] == "user"
    assert logged_in["account_type"] == "user"
    assert logged_in["user_id"] == registered["user_id"]
    assert logged_in["session_token"] != registered["session_token"]


@pytest.mark.asyncio
async def test_registration_keeps_an_existing_anonymous_profile_identity():
    raw_token = "existing-anonymous-token"
    db = Database([{
        "_id": token_digest(raw_token), "token_hash": token_digest(raw_token),
        "user_id": "existing-user", "revoked_at": None,
        "expires_at": now() + timedelta(days=1),
    }])

    registered = await register_user(
        UserRegister(email="saved@example.com", password="client-password"),
        db, f"Bearer {raw_token}",
    )

    assert registered["user_id"] == "existing-user"
    assert db.mnp_user_accounts.rows["existing-user"]["email"] == "saved@example.com"
