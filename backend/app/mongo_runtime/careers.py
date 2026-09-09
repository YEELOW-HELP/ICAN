from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.mongo_runtime.core import Database, privileged_staff

router = APIRouter(prefix="/v1/mnp")


async def _list_item(db, career: dict) -> dict:
    family = await db.mnp_career_families.find_one({"_id": career.get("career_family_id")})
    return {
        "id": str(career["_id"]), "code": career.get("code"),
        "name_uk": career.get("canonical_name_uk"),
        "category_uk": family.get("name_uk") if family else None,
        "status": career.get("status", "draft"),
        "profile_version": career.get("career_profile_version", 1),
        "short_description_uk": career.get("description_short_uk"),
    }


@router.get("/careers")
async def list_careers(db: Database):
    result = []
    async for career in db.mnp_careers.find({"status": "active"}).sort("catalog_priority", 1):
        result.append(await _list_item(db, career))
    return result


@router.get("/careers/{career_id}")
async def career_detail(career_id: str, db: Database):
    career = await db.mnp_careers.find_one({"_id": career_id, "status": "active"})
    if not career:
        raise HTTPException(404, "Career not found")
    tasks = [{"id": str(x["_id"]), "title_uk": x.get("title_uk"), "description": x.get("description")}
             async for x in db.mnp_career_tasks.find({"career_id": career_id}).sort("sort_order", 1)]
    requirements = [{key: value for key, value in x.items() if key != "_id"}
                    async for x in db.mnp_career_requirements.find({"career_id": career_id}).sort("sort_order", 1)]
    skills = []
    async for relation in db.mnp_career_skill_requirements.find({"career_id": career_id}):
        skill = await db.mnp_skills.find_one({"_id": relation.get("skill_id")})
        if skill:
            skills.append({"id": str(skill["_id"]), "name_uk": skill.get("canonical_name_uk"),
                           "importance": relation.get("importance"), "type": skill.get("skill_type")})
    return {
        "identity": {"id": str(career["_id"]), "code": career.get("code"),
                     "name_uk": career.get("canonical_name_uk"), "status": career.get("status")},
        "overview": {"short_description_uk": career.get("description_short_uk"),
                     "long_description_uk": career.get("description_long_uk")},
        "responsibilities": tasks,
        "skills": {"hard": [x for x in skills if x.get("type") != "soft"],
                   "soft": [x for x in skills if x.get("type") == "soft"]},
        "requirements": requirements,
        "entry": {"typical_route_uk": career.get("typical_entry_route_uk"),
                  "without_experience": career.get("entry_without_experience")},
        "market": {"data_limited": career.get("market_data_limited", True)},
    }


@router.get("/admin/careers")
async def admin_careers(db: Database, _staff=Depends(privileged_staff)):
    return [await _list_item(db, row) async for row in db.mnp_careers.find().sort("canonical_name_uk", 1)]
