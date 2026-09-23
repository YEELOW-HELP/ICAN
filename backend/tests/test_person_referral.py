"""Referral channel is independent of the technical profile creation source."""

import pytest
from fastapi import HTTPException

from app.mongo_runtime import persons
from app.mongo_runtime.core import ADMIN, MANAGER, SUPER_ADMIN
from tests.test_mongo_dropbox_cv import Collection, Database


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [MANAGER, ADMIN, SUPER_ADMIN])
@pytest.mark.parametrize("source", [None, *sorted(persons.REFERRAL_SOURCES)])
async def test_referral_create_and_read(source, role):
    db = Database()
    db.mnp_person_access = Collection()
    actor = {"_id": 7, "role": role}
    payload = {"first_name": "Олена"}
    if source:
        payload["referral_source"] = source
    if source == "other":
        payload["referral_details"] = "  Оголошення в громаді  "
    created = await persons.create_person(payload, db, actor)
    loaded = await persons.get_person(created["id"], db, actor)
    assert loaded["core"]["referral_source"] == source
    assert loaded["core"]["referral_details"] == ("Оголошення в громаді" if source == "other" else None)
    assert loaded["core"]["source"] == "consultant"
    assert loaded["core"]["status"] == "case"


@pytest.mark.asyncio
async def test_referral_edit_clear_and_preserve_on_unrelated_update():
    db = Database()
    actor = {"_id": 7, "role": MANAGER}
    legacy = await persons.get_person("person-1", db, actor)
    assert legacy["core"]["referral_source"] is None
    await persons.update_person("person-1", {"referral_source": "other", "referral_details": "Подія"}, db, actor)
    changed = await persons.update_person("person-1", {"referral_details": "Нова подія"}, db, actor)
    assert changed["core"]["referral_details"] == "Нова подія"
    changed = await persons.update_person("person-1", {"notes": "Консультація"}, db, actor)
    assert changed["core"]["referral_details"] == "Нова подія"
    changed = await persons.update_person("person-1", {"referral_source": "instagram"}, db, actor)
    assert changed["core"]["referral_details"] is None
    changed = await persons.update_person("person-1", {"referral_source": None}, db, actor)
    assert changed["core"]["referral_source"] is None
    assert changed["core"]["notes"] == "Консультація"
    assert changed["core"]["status"] == "active"
    with pytest.raises(HTTPException) as denied:
        await persons.update_person("person-1", {"referral_source": "telegram"}, db, {"_id": 8, "role": MANAGER})
    assert denied.value.status_code == 404
    assert db.mnp_persons.rows["person-1"]["referral_source"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [
    {"referral_source": []}, {"referral_source": {}}, {"referral_source": "bogus"},
    {"referral_source": "other"}, {"referral_source": "other", "referral_details": "  "},
    {"referral_source": "other", "referral_details": 3},
    {"referral_source": "other", "referral_details": "x" * 301},
])
async def test_invalid_referral_rejected_before_writes(payload):
    db = Database()
    db.mnp_person_access = Collection()
    actor = {"_id": 7, "role": MANAGER}
    with pytest.raises(HTTPException) as error:
        await persons.create_person({"first_name": "Олена", **payload}, db, actor)
    assert error.value.status_code == 422
    assert len(db.mnp_persons.rows) == 1
    assert not db.mnp_person_access.rows
    before = dict(db.mnp_persons.rows["person-1"])
    with pytest.raises(HTTPException) as error:
        await persons.update_person("person-1", payload, db, actor)
    assert error.value.status_code == 422
    assert db.mnp_persons.rows["person-1"] == before


@pytest.mark.asyncio
async def test_self_service_validates_referral_and_keeps_creation_source():
    db = Database()
    created = await persons.save_self({"first_name": "Олена", "referral_source": "telegram"}, db, {"user_id": "self-1"})
    assert created["core"]["referral_source"] == "telegram"
    assert created["core"]["source"] == "self_service"
    with pytest.raises(HTTPException) as error:
        await persons.save_self({"referral_source": "other"}, db, {"user_id": "self-1"})
    assert error.value.status_code == 422
    assert db.mnp_persons.rows[created["id"]]["referral_source"] == "telegram"
