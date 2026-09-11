from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.mongo_runtime.core import Database, current_staff, now, privileged_staff
from app.services.matching_mnp.pure import PersonLevelInput, RequirementInput, compute_weighted_coverage_fit

router = APIRouter(prefix="/v1/mnp/admin", tags=["mnp-admin-match"])

ENTRY_MODES = {"standard", "open_entry", "incomplete"}
LEVELS = {"basic", "working", "strong"}
IMPORTANCE = {"low", "medium", "high", "critical"}
REQUIREMENT_TYPES = {"must_have", "high_value", "differentiator", "optional"}


def _mode(career: dict) -> str:
    value = career.get("entry_requirements_mode")
    return value if value in ENTRY_MODES else "incomplete"


def _skill_label(skill: dict | None) -> str:
    if not skill:
        return "Невідомий навик"
    return skill.get("canonical_name_uk") or skill.get("canonical_name_en") or str(skill.get("_id"))


async def _skill_map(db, ids: set[str]) -> dict[str, dict]:
    if not ids:
        return {}
    rows = [row async for row in db.mnp_skills.find({"_id": {"$in": list(ids)}})]
    return {str(row["_id"]): row for row in rows}


async def _resolve_skill(db, raw: dict) -> tuple[str, dict] | None:
    skill_id = raw.get("id") or raw.get("skill_id")
    if skill_id:
        skill = await db.mnp_skills.find_one({"_id": str(skill_id)})
        if skill:
            return str(skill["_id"]), skill
    name = str(raw.get("name") or raw.get("name_uk") or "").strip()
    if not name:
        return None
    skill = await db.mnp_skills.find_one({"$or": [
        {"canonical_name_uk": {"$regex": f"^{name}$", "$options": "i"}},
        {"canonical_name_en": {"$regex": f"^{name}$", "$options": "i"}},
    ]})
    if skill:
        return str(skill["_id"]), skill
    alias = await db.mnp_skill_aliases.find_one({"alias": {"$regex": f"^{name}$", "$options": "i"}})
    if alias:
        skill = await db.mnp_skills.find_one({"_id": alias.get("skill_id")})
        if skill:
            return str(skill["_id"]), skill
    return None


async def _career_completeness(db, career: dict) -> dict[str, Any]:
    cid = str(career["_id"])
    skills = await db.mnp_career_skill_requirements.count_documents({"career_id": cid})
    requirements = await db.mnp_career_requirements.count_documents({"career_id": cid})
    training = await db.mnp_career_requirements.count_documents({"career_id": cid, "category": {"$in": ["credential", "education", "other"]}})
    transitions = await db.mnp_career_relations.count_documents({"$or": [{"from_career_id": cid}, {"to_career_id": cid}]})
    basics = bool(career.get("canonical_name_uk") and career.get("description_short_uk") and career.get("career_family_id"))
    mode = _mode(career)
    reviewed = bool(career.get("admin_verified_at"))
    sections = {
        "basic": basics,
        "skills": skills > 0 or mode == "open_entry",
        "requirements": requirements > 0 or mode == "open_entry",
        "training": training > 0 or mode == "open_entry",
        "transitions": transitions > 0,
        "verified": reviewed,
    }
    return {
        "sections": sections,
        "percent": round(sum(1 for value in sections.values() if value) / len(sections) * 100),
        "requires_review": bool(career.get("requires_admin_review", not reviewed)),
        "entry_requirements_mode": mode,
    }


@router.get("/skills/search")
async def search_skills(q: str = Query("", max_length=120), db: Database = None, _staff=Depends(current_staff)):
    text = q.strip()
    query = {} if not text else {"$or": [
        {"canonical_name_uk": {"$regex": text, "$options": "i"}},
        {"canonical_name_en": {"$regex": text, "$options": "i"}},
    ]}
    direct = [row async for row in db.mnp_skills.find(query).limit(20)]
    ids = {str(row["_id"]) for row in direct}
    if text:
        async for alias in db.mnp_skill_aliases.find({"alias": {"$regex": text, "$options": "i"}}).limit(20):
            sid = str(alias.get("skill_id"))
            if sid not in ids:
                skill = await db.mnp_skills.find_one({"_id": sid})
                if skill:
                    direct.append(skill)
                    ids.add(sid)
    result = []
    for skill in direct[:20]:
        aliases = [a.get("alias") async for a in db.mnp_skill_aliases.find({"skill_id": str(skill["_id"])}).limit(8)]
        result.append({
            "id": str(skill["_id"]), "name_uk": skill.get("canonical_name_uk"),
            "name_en": skill.get("canonical_name_en"), "skill_type": skill.get("skill_type"),
            "aliases": [a for a in aliases if a],
        })
    return result


@router.get("/careers/completeness")
async def careers_completeness(
    filter: str = Query("all"), db: Database = None, _staff=Depends(privileged_staff),
):
    result = []
    async for career in db.mnp_careers.find().sort("canonical_name_uk", 1):
        completeness = await _career_completeness(db, career)
        item = {
            "id": str(career["_id"]), "code": career.get("code"), "name_uk": career.get("canonical_name_uk"),
            "status": career.get("status", "draft"), **completeness,
        }
        sections = completeness["sections"]
        keep = {
            "all": True,
            "active": item["status"] == "active",
            "draft": item["status"] == "draft",
            "incomplete_requirements": completeness["entry_requirements_mode"] == "incomplete",
            "no_skills": not sections["skills"],
            "no_education": not sections["training"],
            "no_transitions": not sections["transitions"],
            "open_entry": completeness["entry_requirements_mode"] == "open_entry",
            "requires_review": completeness["requires_review"],
            "complete": completeness["percent"] == 100,
        }.get(filter, True)
        if keep:
            result.append(item)
    return result


@router.get("/careers/{career_id}/editor")
async def career_editor(career_id: str, db: Database, _staff=Depends(privileged_staff)):
    career = await db.mnp_careers.find_one({"_id": career_id})
    if not career:
        raise HTTPException(404, "Career not found")
    skills = [row async for row in db.mnp_career_skill_requirements.find({"career_id": career_id})]
    skill_docs = await _skill_map(db, {str(row.get("skill_id")) for row in skills})
    requirements = [row async for row in db.mnp_career_requirements.find({"career_id": career_id}).sort("sort_order", 1)]
    transitions = [row async for row in db.mnp_career_relations.find({"$or": [{"from_career_id": career_id}, {"to_career_id": career_id}]})]
    return {
        "career": {k: v for k, v in career.items() if k != "_id"} | {"id": career_id, "entry_requirements_mode": _mode(career)},
        "skills": [({k: v for k, v in row.items() if k != "_id"} | {"id": str(row["_id"]), "skill": skill_docs.get(str(row.get("skill_id")))}) for row in skills],
        "requirements": [{k: v for k, v in row.items() if k != "_id"} | {"id": str(row["_id"])} for row in requirements],
        "transitions": [{k: v for k, v in row.items() if k != "_id"} | {"id": str(row["_id"])} for row in transitions],
        "completeness": await _career_completeness(db, career),
    }


@router.put("/careers/{career_id}/editor")
async def save_career_editor(career_id: str, payload: dict = Body(...), db: Database = None, staff=Depends(privileged_staff)):
    career = await db.mnp_careers.find_one({"_id": career_id})
    if not career:
        raise HTTPException(404, "Career not found")
    mode = payload.get("entry_requirements_mode", _mode(career))
    if mode not in ENTRY_MODES:
        raise HTTPException(400, "Invalid entry_requirements_mode")

    career_patch = dict(payload.get("career") or {})
    allowed_core = {"canonical_name_uk", "canonical_name_en", "description_short_uk", "description_long_uk", "typical_entry_route_uk", "entry_without_experience", "status"}
    patch = {k: v for k, v in career_patch.items() if k in allowed_core}
    patch.update({
        "entry_requirements_mode": mode,
        "requires_admin_review": bool(payload.get("requires_admin_review", True)),
        "updated_at": now(), "updated_by_admin_id": staff["_id"],
    })
    await db.mnp_careers.update_one({"_id": career_id}, {"$set": patch})

    if "skills" in payload:
        normalized = []
        seen: set[str] = set()
        for index, raw in enumerate(payload.get("skills") or []):
            resolved = await _resolve_skill(db, raw)
            if not resolved:
                raise HTTPException(400, f"Unknown skill at row {index + 1}; choose an existing mnp_skills item")
            sid, _skill = resolved
            if sid in seen:
                raise HTTPException(409, "Duplicate skill in career requirements")
            seen.add(sid)
            importance = raw.get("importance", "medium")
            level = raw.get("required_level", "working")
            req_type = raw.get("requirement_type", "high_value")
            if importance not in IMPORTANCE or level not in LEVELS or req_type not in REQUIREMENT_TYPES:
                raise HTTPException(400, f"Invalid skill requirement at row {index + 1}")
            normalized.append({
                "_id": str(raw.get("id") or f"{career_id}:{sid}"), "career_id": career_id, "skill_id": sid,
                "importance": importance, "required_level": level, "requirement_type": req_type,
                "comment": raw.get("comment"), "source": raw.get("source"),
                "review_status": raw.get("review_status", "editorial"), "sort_order": index,
            })
        await db.mnp_career_skill_requirements.delete_many({"career_id": career_id})
        if normalized:
            await db.mnp_career_skill_requirements.insert_many(normalized)

    if "requirements" in payload:
        normalized_req = []
        for index, raw in enumerate(payload.get("requirements") or []):
            normalized_req.append({
                "_id": str(raw.get("id") or f"{career_id}:req:{index}"), "career_id": career_id,
                "category": raw.get("category", "other"), "hardness": raw.get("hardness", "soft"),
                "description": raw.get("description") or raw.get("description_uk") or "",
                "value": raw.get("value"), "comment": raw.get("comment"), "sort_order": index,
                "source": raw.get("source"), "review_status": raw.get("review_status", "editorial"),
            })
        await db.mnp_career_requirements.delete_many({"career_id": career_id})
        if normalized_req:
            await db.mnp_career_requirements.insert_many(normalized_req)

    fresh = await db.mnp_careers.find_one({"_id": career_id})
    return {"saved": True, "career_id": career_id, "completeness": await _career_completeness(db, fresh)}


@router.post("/careers/{career_id}/verify")
async def verify_career(career_id: str, db: Database, staff=Depends(privileged_staff)):
    result = await db.mnp_careers.update_one({"_id": career_id}, {"$set": {
        "admin_verified_at": now(), "admin_verified_by": staff["_id"], "requires_admin_review": False,
    }})
    if not result.matched_count:
        raise HTTPException(404, "Career not found")
    return {"verified": True}


@router.get("/careers/next-review")
async def next_review(db: Database, _staff=Depends(privileged_staff)):
    async for career in db.mnp_careers.find().sort("canonical_name_uk", 1):
        completeness = await _career_completeness(db, career)
        if completeness["requires_review"] or completeness["percent"] < 100:
            return {"id": str(career["_id"]), "name_uk": career.get("canonical_name_uk"), **completeness}
    return None


@router.post("/match/preview")
async def match_preview(payload: dict = Body(...), db: Database = None, _staff=Depends(current_staff)):
    raw_skills = payload.get("skills") or []
    person_levels: dict[str, PersonLevelInput] = {}
    unresolved: list[str] = []
    for raw in raw_skills:
        resolved = await _resolve_skill(db, raw)
        if not resolved:
            unresolved.append(str(raw.get("name") or raw.get("name_uk") or raw.get("id") or ""))
            continue
        sid, _skill = resolved
        level = raw.get("level") or raw.get("proficiency_level") or "working"
        if level not in LEVELS:
            raise HTTPException(400, f"Invalid skill level: {level}")
        person_levels[sid] = PersonLevelInput(key=sid, proficiency_level=level, evidence_strength=float(raw.get("evidence_strength", 1.0)))

    results = []
    async for career in db.mnp_careers.find({"status": "active"}):
        cid = str(career["_id"])
        mode = _mode(career)
        req_rows = [row async for row in db.mnp_career_skill_requirements.find({"career_id": cid})]
        skill_docs = await _skill_map(db, {str(r.get("skill_id")) for r in req_rows})
        fit_inputs = [RequirementInput(
            key=str(r.get("skill_id")), importance=r.get("importance", "medium"), required_level=r.get("required_level", "working")
        ) for r in req_rows]
        fit = compute_weighted_coverage_fit(fit_inputs, person_levels, explanation_prefix="admin_preview_skill_fit")
        matched, missing_required, missing_desired = [], [], []
        for row in req_rows:
            sid = str(row.get("skill_id")); label = _skill_label(skill_docs.get(sid))
            if sid in person_levels:
                matched.append(label)
            elif row.get("requirement_type") == "must_have":
                missing_required.append(label)
            else:
                missing_desired.append(label)

        career_requirements = [row async for row in db.mnp_career_requirements.find({"career_id": cid}).sort("sort_order", 1)]
        if mode == "incomplete":
            readiness = "Недостатньо даних"
            score = None
        elif mode == "open_entry" and not req_rows and not career_requirements:
            readiness = "Готовий зараз"
            score = fit.score
        elif missing_required:
            readiness = "Потрібно навчання"
            score = fit.score
        elif fit.score is not None and fit.score >= 0.8:
            readiness = "Готовий зараз"
            score = fit.score
        elif fit.score is not None and fit.score >= 0.55:
            readiness = "Близький перехід"
            score = fit.score
        elif fit.score is not None:
            readiness = "Потрібно навчання"
            score = fit.score
        else:
            readiness = "Недостатньо даних"
            score = None

        education = [r.get("description") for r in career_requirements if r.get("category") == "education"]
        training = [r.get("description") for r in career_requirements if r.get("category") in ("credential", "other")]
        results.append({
            "career_id": cid, "code": career.get("code"), "name_uk": career.get("canonical_name_uk"),
            "score": score, "score_percent": round(score * 100) if score is not None else None,
            "fit_band": fit.band, "confidence": fit.confidence_band, "status": readiness,
            "entry_requirements_mode": mode,
            "entry_message": "Можна почати без попереднього досвіду" if mode == "open_entry" else ("Вимоги ще не заповнені" if mode == "incomplete" else None),
            "matched_skills": matched, "missing_required_skills": missing_required,
            "missing_desired_skills": missing_desired, "education_requirements": [x for x in education if x],
            "training_requirements": [x for x in training if x],
            "explanation": fit.explanation_code,
        })

    results.sort(key=lambda x: (x["score"] is not None, x["score"] or -1), reverse=True)
    return {"temporary_profile_saved": False, "unresolved_skills": unresolved, "results": results[:100]}
