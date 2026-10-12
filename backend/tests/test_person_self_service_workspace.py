"""The client can manage only career data attached to their own profile."""

import pytest
from fastapi import HTTPException

from app.mongo_runtime import cv_analysis, persons
from tests.test_mongo_dropbox_cv import Database


@pytest.mark.asyncio
async def test_self_service_career_fields_are_saved_and_used_for_analysis():
    db = Database()
    db.mnp_persons.rows["person-1"]["identity_user_id"] = "self-1"

    profile = await persons.save_self({
        "career_goal": "Знайти стабільну роботу",
        "desired_roles": "Офіс-менеджер або адміністратор",
        "job_preferences": "Повний день",
    }, db, {"user_id": "self-1"})
    excerpt = await cv_analysis.questionnaire_excerpt(db, profile)

    assert profile["core"]["career_goal"] == "Знайти стабільну роботу"
    assert "Кар’єрна мета: Знайти стабільну роботу" in excerpt
    assert "Бажані професії: Офіс-менеджер або адміністратор" in excerpt


@pytest.mark.asyncio
async def test_self_service_fact_crud_is_owner_scoped_and_whitelisted():
    db = Database()
    db.mnp_persons.rows["person-1"]["identity_user_id"] = "self-1"

    profile = await persons.self_add_fact("experiences", {
        "raw_job_title": "Касир",
        "company_name": "Магазин",
        "canonical_skill_id": "must-not-be-user-controlled",
        "person_id": "another-person",
    }, db, {"user_id": "self-1"})
    fact = profile["experiences"][0]
    stored = db[persons.FACTS["experiences"]].rows[fact["id"]]
    assert stored["person_id"] == "person-1"
    assert "canonical_skill_id" not in stored

    profile = await persons.self_edit_fact(
        "experiences", fact["id"], {"raw_job_title": "Старший касир"},
        db, {"user_id": "self-1"},
    )
    assert profile["experiences"][0]["raw_job_title"] == "Старший касир"

    with pytest.raises(HTTPException) as denied:
        await persons.self_edit_fact(
            "experiences", fact["id"], {"raw_job_title": "Чуже значення"},
            db, {"user_id": "self-2"},
        )
    assert denied.value.status_code == 404

    profile = await persons.self_delete_fact(
        "experiences", fact["id"], db, {"user_id": "self-1"},
    )
    assert profile["experiences"] == []
