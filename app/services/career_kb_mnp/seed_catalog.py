"""MNP Career KB -- starter-catalog importer.

Takes the MNP-curated `catalog_starter.STARTER_CAREERS` (the Work.ua
Career Guide discovery universe, filled with MNP editorial content) and
creates each career in the DB as **DRAFT**.

Rules (Founder brief):
  * BOOTSTRAP / IDEMPOTENT: a career whose `code` already exists is left
    completely untouched -- no manual admin edit is ever overwritten
    (§1 / §27). Existing alpha careers are never modified; only a Work.ua
    discovery reference row is written to the research layer (§19, §25).
  * Every new career starts DRAFT -- never auto-published (§6, §22, §15).
  * NO market data. NO HARD/legal requirement (regulated professions get
    a soft OTHER note + a data-gap; a real blocker needs an authoritative
    source and a curator decision in the Career KB Editor) (§2, §13).
  * Skills / knowledge are de-duplicated against the canonical taxonomy
    (§10, §11).

The Work.ua reference mapping lives ONLY in the research layer
(`data_explorer/workua/reference_mapping.csv`) -- Work.ua ids are never
part of core Career identity (§19).
"""

from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_career_card import MnpSkill, SkillAliasType, SkillStatus, SkillType
from app.db.models_career_kb_mnp import (
    CareerAliasType,
    CareerDifficulty,
    CareerLifecycleStatus,
    CareerPathStepType,
    EntryWithoutExperience,
    ImportanceLevel,
    MnpCareer,
    ProConType,
    RequirementCategory,
    RequirementHardness,
    RequirementType,
)
from app.db.models_platform import AuditLog
from app.services.career_kb_mnp.careers import (
    add_career_alias,
    add_career_path_step,
    add_career_procon,
    add_career_task,
    add_requirement,
    add_skill_requirement,
    create_career,
    get_or_create_career_family,
    set_career_entry,
)
from app.services.career_kb_mnp.catalog_starter import (
    CATALOG_SOURCE,
    CATALOG_SOURCE_VERSION,
    SKILL_ALIASES,
    STARTER_CAREERS,
    STARTER_FAMILIES,
    WORKUA_DISCOVERY_REF,
    WORKUA_REFERENCE,
)
from app.services.career_kb_mnp.skills import activate_skill, add_skill_alias, create_skill

TAXONOMY_VERSION = "mnp_skill_taxonomy_starter_v1"
REFERENCE_CSV = Path(__file__).resolve().parents[3] / "data_explorer" / "workua" / "reference_mapping.csv"

_DIFF = {e.value: e for e in CareerDifficulty}
_EWE = {e.value: e for e in EntryWithoutExperience}
_IMP = {e.value: e for e in ImportanceLevel}
_REQT = {e.value: e for e in RequirementType}
_CAT = {e.value: e for e in RequirementCategory}
_STEP = {e.value: e for e in CareerPathStepType}
_HARD = {e.value: e for e in RequirementHardness}
_SKT = {e.value: e for e in SkillType}


async def _get_or_create_skill(session: AsyncSession, name_en: str, name_uk: str, skill_type: str) -> MnpSkill:
    found = (await session.execute(
        select(MnpSkill).where(MnpSkill.canonical_name_en == name_en))).scalar_one_or_none()
    if found is not None:
        return found
    skill = await create_skill(
        session, canonical_name_en=name_en, canonical_name_uk=name_uk,
        skill_type=_SKT.get(skill_type, SkillType.FUNCTIONAL),
        taxonomy_version=TAXONOMY_VERSION, skill_family="Starter",
    )
    await activate_skill(session, skill)
    for alias in SKILL_ALIASES.get(name_en, []):
        await add_skill_alias(session, skill, alias=alias, language="uk",
                              alias_type=SkillAliasType.UKRAINIAN_MARKET_TERM, source=CATALOG_SOURCE)
    return skill


def _skill_tuple(s: tuple) -> tuple[str, str, str, str, str, str]:
    if len(s) == 3:
        return (*s, "medium", "working", "high_value")
    return s


async def seed_starter_catalog(session: AsyncSession) -> dict:
    """Idempotent. Returns a summary dict."""
    summary = {"created": 0, "skipped_existing": 0, "skills_created": 0, "careers_total": len(STARTER_CAREERS)}

    # families -- reuse existing by code, create the rest
    families: dict[str, object] = {}
    for code, (name_uk, name_en) in STARTER_FAMILIES.items():
        families[code] = await get_or_create_career_family(session, code=code, name_uk=name_uk, name_en=name_en)

    skills_before = (await session.execute(select(MnpSkill))).scalars().all()
    n_skills_before = len(skills_before)

    for code, spec in STARTER_CAREERS.items():
        existing = (await session.execute(
            select(MnpCareer).where(MnpCareer.code == code))).scalar_one_or_none()
        if existing is not None:
            summary["skipped_existing"] += 1
            continue

        career = await create_career(
            session, code=code, canonical_name_uk=spec["name_uk"], canonical_name_en=spec["name_en"],
            description_short_uk=spec["short"], description_long_uk=spec["long"],
            career_family=families[spec["family"]],
        )
        await set_career_entry(
            session, career,
            difficulty_level=_DIFF.get(spec.get("difficulty")),
            entry_without_experience=_EWE.get(spec.get("entry_wo_exp"), EntryWithoutExperience.UNKNOWN),
            typical_entry_route_uk=spec.get("entry_route"),
        )
        await add_career_alias(session, career, alias=spec["name_uk"],
                               alias_type=CareerAliasType.MARKET_TITLE, source=CATALOG_SOURCE)

        for i, title_uk in enumerate(spec["resp"], start=1):
            row = await add_career_task(
                session, career, task_code=f"{code}_r{i}", title_uk=title_uk,
                importance=ImportanceLevel.HIGH, source=CATALOG_SOURCE,
                source_version=CATALOG_SOURCE_VERSION, confidence=0.55,
            )
            row.sort_order = i
            row.review_status = "needs_review"

        for name_en, name_uk, stype, imp, lvl, rtype in (_skill_tuple(s) for s in spec["skills"]):
            skill = await _get_or_create_skill(session, name_en, name_uk, stype)
            row = await add_skill_requirement(
                session, career, skill.id, importance=_IMP.get(imp, ImportanceLevel.MEDIUM),
                required_level=lvl, requirement_type=_REQT.get(rtype, RequirementType.HIGH_VALUE),
                source=CATALOG_SOURCE, source_version=CATALOG_SOURCE_VERSION, confidence=0.55,
            )
            row.review_status = "needs_review"

        for cat, desc_uk, hardness, value in spec["reqs"]:
            row = await add_requirement(
                session, career, category=_CAT[cat], description=desc_uk,
                hardness=_HARD.get(hardness, RequirementHardness.SOFT), value=value, country="UA",
                source=CATALOG_SOURCE, source_version=CATALOG_SOURCE_VERSION, confidence=0.5,
            )
            row.review_status = "needs_review"

        if spec.get("regulated"):
            row = await add_requirement(
                session, career, category=RequirementCategory.OTHER,
                description=("Регульована професія: вимоги до допуску / ліцензії / сертифікації "
                             "потребують підтвердження авторитетним джерелом перед публікацією."),
                hardness=RequirementHardness.SOFT, value=None, country="UA",
                source=CATALOG_SOURCE, source_version=CATALOG_SOURCE_VERSION, confidence=0.4,
            )
            row.review_status = "needs_review"

        for i, text in enumerate(spec["pros"], start=1):
            await add_career_procon(session, career, type=ProConType.ADVANTAGE, text_uk=text, sort_order=i,
                                    source=CATALOG_SOURCE, source_version=CATALOG_SOURCE_VERSION,
                                    confidence=0.5, review_status="needs_review")
        for i, text in enumerate(spec["cons"], start=1):
            await add_career_procon(session, career, type=ProConType.DISADVANTAGE, text_uk=text, sort_order=i,
                                    source=CATALOG_SOURCE, source_version=CATALOG_SOURCE_VERSION,
                                    confidence=0.5, review_status="needs_review")

        for order, step_type, name_uk_, exp_text in spec.get("path", []):
            await add_career_path_step(
                session, career, step_order=order, step_name_uk=name_uk_,
                step_type=_STEP.get(step_type, CareerPathStepType.CORE),
                typical_experience_text_uk=exp_text, source=CATALOG_SOURCE,
                source_version=CATALOG_SOURCE_VERSION, review_status="needs_review",
            )

        await session.flush()
        gaps = "; ".join(spec.get("data_gaps", []))
        session.add(AuditLog(
            entity_type="mnp_career", entity_id=str(career.id), action="catalog_imported",
            after_snapshot={"code": code, "status": "draft", "discovery": WORKUA_DISCOVERY_REF,
                            "workua_slug": spec.get("workua_slug"),
                            "regulated": bool(spec.get("regulated")), "data_gaps": gaps or None},
        ))
        summary["created"] += 1

    n_skills_after = len((await session.execute(select(MnpSkill))).scalars().all())
    summary["skills_created"] = n_skills_after - n_skills_before

    await _write_reference_mapping(session)
    await session.commit()
    return summary


async def _write_reference_mapping(session: AsyncSession) -> None:
    """DB -> research-layer CSV. discovery/reference only; NOT a production
    source of truth, NOT part of Career identity."""
    rows: list[tuple] = []
    for code, spec in STARTER_CAREERS.items():
        slug = spec.get("workua_slug")
        if not slug:
            continue
        rows.append((code, spec["name_uk"], slug, f"https://www.work.ua/career-guide/{slug}/", "new_from_workua"))
    for code, ref in WORKUA_REFERENCE.items():
        rows.append((code, ref["title_uk"], ref["slug"],
                     f"https://www.work.ua/career-guide/{ref['slug']}/", ref["mapping_status"]))
    rows.sort()
    REFERENCE_CSV.parent.mkdir(parents=True, exist_ok=True)
    with REFERENCE_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["mnp_career_code", "workua_title_uk", "workua_slug", "workua_url", "mapping_status"])
        w.writerows(rows)
