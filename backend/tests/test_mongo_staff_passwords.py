import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import ValidationError

from app.core.security import hash_password, verify_password
from app.mongo_runtime import core
from app.mongo_runtime.auth import StaffPasswordReset, reset_staff_password
from app.mongo_runtime.core import ADMIN, SUPER_ADMIN


class FakeCollection:
    def __init__(self, documents=None):
        self.documents = {item["_id"]: dict(item) for item in documents or []}
        self.inserted = []

    async def find_one(self, query):
        return self.documents.get(query.get("_id"))

    async def update_one(self, query, update):
        document = self.documents[query["_id"]]
        document.update(update.get("$set", {}))
        for key, amount in update.get("$inc", {}).items():
            document[key] = document.get(key, 0) + amount

    async def insert_one(self, document):
        self.inserted.append(dict(document))


class FakeDatabase:
    def __init__(self, users):
        self.admin_users = FakeCollection(users)
        self.audit_logs = FakeCollection()


@pytest.mark.asyncio
async def test_superadmin_can_reset_any_staff_password_without_logging_it():
    actor = {"_id": 1, "role": SUPER_ADMIN}
    old_hash = hash_password("old-password")
    db = FakeDatabase([{"_id": 2, "role": ADMIN, "password_hash": old_hash, "token_version": 0}])

    response = await reset_staff_password(
        2, StaffPasswordReset(new_password="new-password"), db, actor,
    )

    changed = db.admin_users.documents[2]
    assert response == {"detail": "Пароль змінено", "reauthentication_required": False}
    assert verify_password("new-password", changed["password_hash"])
    assert changed["token_version"] == 1
    assert db.audit_logs.inserted[0]["action"] == "staff_password_reset"
    assert "new-password" not in repr(db.audit_logs.inserted)


@pytest.mark.asyncio
async def test_superadmin_can_reset_own_password_and_must_sign_in_again():
    actor = {"_id": 1, "role": SUPER_ADMIN}
    db = FakeDatabase([{"_id": 1, "role": SUPER_ADMIN, "password_hash": hash_password("old-password")}])

    response = await reset_staff_password(
        1, StaffPasswordReset(new_password="new-password"), db, actor,
    )

    assert response["reauthentication_required"] is True
    assert db.admin_users.documents[1]["token_version"] == 1


@pytest.mark.asyncio
async def test_non_superadmin_cannot_reset_passwords():
    with pytest.raises(HTTPException) as error:
        await reset_staff_password(
            2, StaffPasswordReset(new_password="new-password"), FakeDatabase([]),
            {"_id": 3, "role": ADMIN},
        )
    assert error.value.status_code == 403


def test_reset_password_requires_at_least_eight_characters():
    with pytest.raises(ValidationError):
        StaffPasswordReset(new_password="1234567")


@pytest.mark.asyncio
async def test_password_change_invalidates_older_tokens(monkeypatch):
    db = FakeDatabase([{
        "_id": 2, "role": ADMIN, "is_active": True,
        "password_hash": hash_password("new-password"), "token_version": 1,
    }])
    monkeypatch.setattr(core, "decode_access_token", lambda _token: {"sub": "2", "ver": 0})

    with pytest.raises(HTTPException) as error:
        await core.current_staff(
            db,
            HTTPAuthorizationCredentials(scheme="Bearer", credentials="old-token"),
        )

    assert error.value.status_code == 401
