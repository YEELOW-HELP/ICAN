"""MNP V1 -- Career Detail assembler: ONE structured, Ukrainian-first view
of a career, built from the production Career KB tables and reused by the
public API, the website and the `MNP_CAREER_KB_V1.xlsx` export (brief §3:
"Production Career KB DB is the single source of truth" -- no independent
copies of career content anywhere).

Founder Language Policy: every user-facing value is Ukrainian. Internal
codes (`*_code`) travel alongside the Ukrainian label for the frontend to
key on, but the frontend never shows a raw enum or a UUID (brief §11).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models_career_card import MnpKnowledge, MnpSkill
from app.db.models_career_kb_mnp import (
    CareerLifecycleStatus,
    MnpCareer,
    MnpCareerKnowledgeRequirement,
    MnpCareerPathStep,
    MnpCareerProCon,
    MnpCareerRelation,
    MnpCareerRequirement,
    MnpCareerSkillRequirement,
    ProConType,
)
from app.services.career_kb_mnp.seed_alpha import is_soft_skill

MARKET_STATUS_UK = "Недостатньо ринкових даних"
CAREER_PATH_LABEL_UK = "Типовий кар'єрний шлях"
NO_CONFIRMED_DATA_UK = "Немає підтверджених даних"

_IMPORTANCE_UK = {"low": "Низька", "medium": "Середня", "high": "Висока", "critical": "Критична"}
_REQ_TYPE_UK = {
    "must_have": "Обов'язкова", "high_value": "Дуже бажана",
    "differentiator": "Перевага", "optional": "Додатково",
}
_LEVEL_UK = {"basic": "Базовий", "working": "Впевнений", "strong": "Високий"}
_DIFFICULTY_UK = {
    "easy": "Низька", "moderate": "Середня", "challenging": "Висока", "hard": "Дуже висока",
}
_ENTRY_WITHOUT_EXP_UK = {
    "yes": "Так",
    "limited": "Частково — для окремих ролей або після навчання",
    "no": "Ні",
    "unknown": NO_CONFIRMED_DATA_UK,
}
_HARDNESS_UK = {"soft": "Бажана", "hard": "Обов'язкова (підтверджено)"}
_RELATION_UK = {
    "progression": "Наступний крок у кар'єрі",
    "adjacent": "Суміжна професія",
    "related": "Пов'язана професія",
    "same_family": "Та сама сфера",
    "common_transition": "Частий перехід",
}
_STATUS_UK = {
    "draft": "Чернетка", "validated": "Перевірено", "active": "Опубліковано",
    "review_due": "Потребує перегляду", "archived": "В архіві",
}
# RequirementCategory value -> (section key, Ukrainian section title)
_REQ_SECTIONS: list[tuple[str, str]] = [
    ("education", "Освіта"),
    ("experience", "Досвід"),
    ("language", "Мова"),
    ("credential", "Сертифікація"),
    ("legal", "Ліцензія та дозволи"),
    ("other", "Інші вимоги"),
]
_PATH_STEP_TYPE_UK = {
    "entry": "Старт", "junior": "Початковий рівень", "core": "Основний рівень",
    "senior": "Досвідчений рівень", "lead": "Керівний рівень", "executive": "Топ-рівень",
}
_IMPORTANCE_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


async def build_career_detail(session: AsyncSession, career: MnpCareer) -> dict:
    """Assemble the full structured Career Detail for one career. All text
    is Ukrainian-first; `*_code` fields carry the raw enum for the client
    to key on but are never displayed."""

    # -- skills (hard/soft split derives from skill type) --
    skill_reqs = (
        await session.execute(
            select(MnpCareerSkillRequirement)
            .where(MnpCareerSkillRequirement.career_id == career.id)
            .options(selectinload(MnpCareerSkillRequirement.skill))
        )
    ).scalars().all()

    hard_skills: list[dict] = []
    soft_skills: list[dict] = []
    for req in skill_reqs:
        skill: MnpSkill = req.skill
        entry = {
            "code": skill.canonical_name_en,
            "name_uk": skill.canonical_name_uk,
            "name_en": skill.canonical_name_en,
            "requirement_code": req.requirement_type.value,
            "requirement_uk": _REQ_TYPE_UK.get(req.requirement_type.value, req.requirement_type.value),
            "level_code": req.required_level,
            "level_uk": _LEVEL_UK.get(req.required_level, req.required_level),
            "importance_code": req.importance.value,
            "importance_uk": _IMPORTANCE_UK.get(req.importance.value, req.importance.value),
        }
        (soft_skills if is_soft_skill(skill.skill_type) else hard_skills).append(entry)

    hard_skills.sort(key=lambda s: (_IMPORTANCE_RANK.get(s["importance_code"], 9), s["name_uk"]))
    soft_skills.sort(key=lambda s: (_IMPORTANCE_RANK.get(s["importance_code"], 9), s["name_uk"]))

    # -- knowledge --
    knowledge_rows = (
        await session.execute(
            select(MnpCareerKnowledgeRequirement, MnpKnowledge)
            .join(MnpKnowledge, MnpKnowledge.id == MnpCareerKnowledgeRequirement.knowledge_id)
            .where(MnpCareerKnowledgeRequirement.career_id == career.id)
        )
    ).all()
    knowledge = [
        {
            "name_uk": k.canonical_name_uk, "name_en": k.canonical_name_en,
            "importance_code": kr.importance.value,
            "importance_uk": _IMPORTANCE_UK.get(kr.importance.value, kr.importance.value),
        }
        for kr, k in sorted(
            knowledge_rows, key=lambda t: (_IMPORTANCE_RANK.get(t[0].importance.value, 9), t[1].canonical_name_uk)
        )
    ]

    # -- responsibilities --
    responsibilities = [
        {
            "title_uk": t.title_uk,
            "description_uk": t.description or None,
            "importance_code": t.importance.value,
            "importance_uk": _IMPORTANCE_UK.get(t.importance.value, t.importance.value),
        }
        for t in sorted(career.tasks, key=lambda t: (_IMPORTANCE_RANK.get(t.importance.value, 9), t.task_code))
    ]

    # -- requirements grouped by category (every section always present) --
    req_rows = (
        await session.execute(
            select(MnpCareerRequirement).where(MnpCareerRequirement.career_id == career.id)
        )
    ).scalars().all()
    requirements: dict[str, dict] = {}
    for key, title_uk in _REQ_SECTIONS:
        items = [
            {
                "title_uk": r.description,
                "value_code": r.value,
                "hardness_code": r.hardness.value,
                "hardness_uk": _HARDNESS_UK.get(r.hardness.value, r.hardness.value),
                "confirmed": r.hardness.value == "hard" and bool(r.source),
            }
            for r in req_rows if r.category.value == key
        ]
        requirements[key] = {
            "title_uk": title_uk,
            "items": items,
            "empty_label_uk": NO_CONFIRMED_DATA_UK if not items else None,
        }

    # -- pros / cons (MNP editorial layer) --
    procon_rows = (
        await session.execute(
            select(MnpCareerProCon).where(MnpCareerProCon.career_id == career.id)
        )
    ).scalars().all()
    advantages = [
        p.text_uk for p in sorted(
            (p for p in procon_rows if p.type == ProConType.ADVANTAGE), key=lambda p: p.sort_order
        )
    ]
    disadvantages = [
        p.text_uk for p in sorted(
            (p for p in procon_rows if p.type == ProConType.DISADVANTAGE), key=lambda p: p.sort_order
        )
    ]

    # -- career path (typical, not guaranteed) --
    step_rows = (
        await session.execute(
            select(MnpCareerPathStep).where(MnpCareerPathStep.career_id == career.id)
        )
    ).scalars().all()
    steps = [
        {
            "order": s.step_order,
            "name_uk": s.step_name_uk,
            "description_uk": s.description_uk,
            "typical_experience_uk": s.typical_experience_text_uk,
            "type_code": s.step_type.value,
            "type_uk": _PATH_STEP_TYPE_UK.get(s.step_type.value, s.step_type.value),
            "is_current": s.is_current_career_step,
        }
        for s in sorted(step_rows, key=lambda s: s.step_order)
    ]

    # -- related careers (real MNP careers, ACTIVE, no fabricated match score) --
    relation_rows = (
        await session.execute(
            select(MnpCareerRelation)
            .where(MnpCareerRelation.from_career_id == career.id)
            .options(selectinload(MnpCareerRelation.to_career))
        )
    ).scalars().all()
    related = [
        {
            "code": rel.to_career.code,
            "name_uk": rel.to_career.canonical_name_uk,
            "relation_code": rel.relation_type.value,
            "relation_uk": _RELATION_UK.get(rel.relation_type.value, rel.relation_type.value),
        }
        for rel in relation_rows
        if rel.to_career is not None and rel.to_career.status == CareerLifecycleStatus.ACTIVE
    ]
    related.sort(key=lambda r: r["name_uk"])

    # -- external references (reference/enrichment only; may be empty) --
    external_references = [
        {
            "system": m.source_system.value,
            "external_id": m.external_id,
            "label": m.external_label,
            "mapping_code": m.mapping_type.value,
        }
        for m in sorted(career.external_mappings, key=lambda m: (m.source_system.value, m.external_id))
    ]

    # -- provenance: one row per material block --
    def _prov(block: str, present: bool) -> dict:
        return {"block": block, "source": "mnp_editorial_v1" if present else None, "confirmed": present}

    provenance = [
        _prov("Опис і обов'язки", bool(responsibilities)),
        _prov("Навички", bool(hard_skills or soft_skills)),
        _prov("Знання", bool(knowledge)),
        _prov("Вимоги", any(sec["items"] for sec in requirements.values())),
        _prov("Переваги та недоліки", bool(advantages or disadvantages)),
        _prov("Кар'єрний шлях", bool(steps)),
        {"block": "Ринкові дані", "source": None, "confirmed": False},
        _prov("Зовнішні довідники", bool(external_references)),
    ]

    family_uk = career.career_family.name_uk if career.career_family else None

    return {
        "id": str(career.id),
        "code": career.code,
        "identity": {
            "name_uk": career.canonical_name_uk,
            "name_en": career.canonical_name_en,
            "category_uk": family_uk,
            "status_code": career.status.value,
            "status_uk": _STATUS_UK.get(career.status.value, career.status.value),
            "profile_version": career.career_profile_version,
        },
        "overview": {
            "title_uk": f"Що робить {career.canonical_name_uk.lower()}",
            "short_description_uk": career.description_short_uk,
            "long_description_uk": career.description_long_uk,
        },
        "responsibilities": responsibilities,
        "skills": {"hard": hard_skills, "soft": soft_skills},
        "knowledge": knowledge,
        "requirements": requirements,
        "entry": {
            "difficulty_code": career.difficulty_level.value if career.difficulty_level else None,
            "difficulty_uk": (
                _DIFFICULTY_UK.get(career.difficulty_level.value, career.difficulty_level.value)
                if career.difficulty_level else NO_CONFIRMED_DATA_UK
            ),
            "without_experience_code": career.entry_without_experience.value,
            "without_experience_uk": _ENTRY_WITHOUT_EXP_UK.get(
                career.entry_without_experience.value, NO_CONFIRMED_DATA_UK
            ),
            "typical_route_uk": career.typical_entry_route_uk,
        },
        "pros_cons": {"advantages": advantages, "disadvantages": disadvantages},
        "career_path": {"label_uk": CAREER_PATH_LABEL_UK, "steps": steps},
        "related_careers": related,
        "market": {
            "status_uk": MARKET_STATUS_UK,
            "data_limited": bool(career.market_data_limited),
            "data_quality": "MARKET_DATA_LIMITED",
            "salary": None,
            "demand": None,
        },
        "external_references": external_references,
        "provenance": provenance,
    }


async def get_career_detail_by_id(session: AsyncSession, career_id: uuid.UUID) -> dict | None:
    career = (
        await session.execute(
            select(MnpCareer).where(MnpCareer.id == career_id).options(
                selectinload(MnpCareer.career_family),
                selectinload(MnpCareer.tasks),
                selectinload(MnpCareer.external_mappings),
            )
        )
    ).scalar_one_or_none()
    if career is None or career.status == CareerLifecycleStatus.ARCHIVED:
        return None
    return await build_career_detail(session, career)


async def list_active_careers(session: AsyncSession) -> list[dict]:
    rows = (
        await session.execute(
            select(MnpCareer)
            .where(MnpCareer.status == CareerLifecycleStatus.ACTIVE)
            .options(selectinload(MnpCareer.career_family))
            .order_by(MnpCareer.catalog_priority.desc(), MnpCareer.canonical_name_uk)
        )
    ).scalars().all()
    return [
        {
            "id": str(c.id),
            "code": c.code,
            "name_uk": c.canonical_name_uk,
            "category_uk": c.career_family.name_uk if c.career_family else None,
            "description_short_uk": c.description_short_uk,
            "difficulty_uk": (
                _DIFFICULTY_UK.get(c.difficulty_level.value) if c.difficulty_level else NO_CONFIRMED_DATA_UK
            ),
            "market_data_limited": bool(c.market_data_limited),
        }
        for c in rows
    ]
