"""Configurable employment stages and per-person offer text."""

import httpx
import pytest
from fastapi import HTTPException

from app.mongo_runtime import persons
from app.mongo_runtime.core import ADMIN, MANAGER, current_staff, database, privileged_staff
from app.mongo_runtime.main import app
from tests.test_mongo_dropbox_cv import Database


@pytest.mark.asyncio
async def test_admin_stage_crud_and_person_assignment():
    db = Database()
    admin = {"_id": 1, "role": ADMIN}
    manager = {"_id": 7, "role": MANAGER}
    created = await persons.create_employment_stage({"name": "  Проходить   співбесіду  "}, db, admin)
    assert created["name"] == "Проходить співбесіду"
    assert created["is_active"] is True

    changed = await persons.update_person_employment(
        "person-1", {"stage_id": created["id"], "offer_text": "  Надіслати дві вакансії  "}, db, manager,
    )
    assert changed["employment"] == {
        "stage_id": created["id"], "stage_name": "Проходить співбесіду",
        "stage_active": True, "offer_text": "Надіслати дві вакансії",
    }
    assert changed["core"]["status"] == "active"

    renamed = await persons.update_employment_stage(created["id"], {"name": "Співбесіду заплановано"}, db, admin)
    assert renamed["name"] == "Співбесіду заплановано"
    loaded = await persons.get_person("person-1", db, manager)
    assert loaded["employment"]["stage_name"] == "Співбесіду заплановано"

    removed = await persons.delete_employment_stage(created["id"], db, admin)
    assert removed == {"archived": True, "used_by": 1}
    loaded = await persons.get_person("person-1", db, manager)
    assert loaded["employment"]["stage_name"] == "Співбесіду заплановано"
    assert loaded["employment"]["stage_active"] is False
    assert await persons.list_employment_stages(db, manager) == []
    assert (await persons.list_employment_stages(db, admin))[0]["is_active"] is False


@pytest.mark.asyncio
async def test_unused_stage_is_deleted_and_invalid_assignments_are_rejected():
    db = Database()
    admin = {"_id": 1, "role": ADMIN}
    manager = {"_id": 7, "role": MANAGER}
    created = await persons.create_employment_stage({"name": "У пошуку вакансій"}, db, admin)
    result = await persons.delete_employment_stage(created["id"], db, admin)
    assert result == {"archived": False, "used_by": 0}
    assert not db.mnp_employment_stages.rows

    original = dict(db.mnp_persons.rows["person-1"])
    for payload in (
        {"stage_id": "missing"}, {"stage_id": []}, {"offer_text": {}},
        {"offer_text": "x" * (persons.EMPLOYMENT_OFFER_MAX_LENGTH + 1)}, {}, {"unexpected": "x"},
    ):
        with pytest.raises(HTTPException) as error:
            await persons.update_person_employment("person-1", payload, db, manager)
        assert error.value.status_code == 422
        assert db.mnp_persons.rows["person-1"] == original


@pytest.mark.asyncio
async def test_manager_cannot_manage_stage_dictionary_through_api():
    db = Database()
    app.dependency_overrides[database] = lambda: db
    app.dependency_overrides[current_staff] = lambda: {"_id": 7, "role": MANAGER}
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/v1/mnp/admin/employment-stages", json={"name": "Працевлаштовано"})
            assert response.status_code == 403
            assert not db.mnp_employment_stages.rows
    finally:
        app.dependency_overrides.pop(database, None)
        app.dependency_overrides.pop(current_staff, None)


@pytest.mark.asyncio
async def test_stage_and_offer_require_person_access():
    db = Database()
    stage = await persons.create_employment_stage({"name": "Запропоновано вакансії"}, db, {"_id": 1, "role": ADMIN})
    with pytest.raises(HTTPException) as denied:
        await persons.update_person_employment(
            "person-1", {"stage_id": stage["id"], "offer_text": "Вакансія"}, db,
            {"_id": 8, "role": MANAGER},
        )
    assert denied.value.status_code == 404
    assert "employment_stage_id" not in db.mnp_persons.rows["person-1"]


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [
    {}, {"name": ""}, {"name": " "}, {"name": 1}, {"name": "x" * 81},
    {"name": "Етап", "extra": True},
])
async def test_invalid_stage_names(payload):
    db = Database()
    with pytest.raises(HTTPException) as error:
        await persons.create_employment_stage(payload, db, {"_id": 1, "role": ADMIN})
    assert error.value.status_code == 422
    assert not db.mnp_employment_stages.rows
