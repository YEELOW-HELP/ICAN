"""Read the MNP Career Knowledge Base (read-only) into plain dicts.

Used by (a) the ESCO/O*NET Explorer to show "SOURCE FACT vs MNP
INTERPRETATION" and (b) the `MNP_CAREER_KB_V1.xlsx` exporter. Never
touches a production database and never writes anything.

The approved MNP V1 KB currently ships as an in-code seed
(`app/services/career_kb_mnp/seed_alpha.py`, 5 ACTIVE careers). We run
that seed into an ephemeral in-memory SQLite and read it back. If a real
MNP DB is ever available, point `MNP_DATABASE_URL` at it (still
read-only). No AI anywhere.

The MNP Career KB entities this reads (production source of truth, brief
"§1 SOURCE OF TRUTH" / "§2 CAREER DATASET"):

    mnp_careers                    -> Career
    mnp_career_families            -> category / family
    mnp_career_aliases             -> aliases
    mnp_career_tasks               -> responsibilities  (MNP_CAREER_PROFILE_SCHEMA_V1 §7)
    mnp_career_skill_requirements  -> Career<->Skill     (+ mnp_skills for human names)
    mnp_career_knowledge_requirements
    mnp_career_requirements        -> education/experience/language/credential/legal
    mnp_career_attributes          -> work context/style/ability/interest (secondary signal)
    mnp_career_relations           -> Career<->Career prior  (not the career path)
    mnp_career_path_steps          -> ordered typical career path  (Founder Decision §6)
    mnp_career_pros_cons           -> MNP editorial advantages/disadvantages  (Founder Decision §5)
    mnp_external_mappings          -> ESCO/O*NET/ISCO/UA_CLASSIFIER references
    mnp_market_snapshots / mnp_salary_snapshots  -> market layer (snapshots, never a Career field)

Career entry characteristics (`difficulty_level`, `entry_without_experience`,
`typical_entry_route_uk`) are columns on `mnp_careers`.

Provenance is NOT a separate table: every row above carries its own
`source` / `source_version` / `confidence`. The exporter flattens those
into the 90_PROVENANCE sheet.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
# import every model module so create_all() sees the full metadata
from app.db import (  # noqa: F401
    models, models_access, models_assessment, models_career_card, models_career_kb_mnp,
    models_crm, models_identity, models_knowledge, models_matching_mnp, models_platform,
    models_profile,
)
from app.db.models_career_card import MnpKnowledge, MnpSkill
from app.db.models_career_kb_mnp import (
    MnpCareer, MnpCareerAlias, MnpCareerAttribute, MnpCareerFamily, MnpCareerKnowledgeRequirement,
    MnpCareerPathStep, MnpCareerProCon, MnpCareerRelation, MnpCareerRequirement,
    MnpCareerSkillRequirement, MnpExternalMapping, MnpCareerTask, MnpMarketSnapshot, MnpSalarySnapshot,
)


def _v(x):
    return x.value if hasattr(x, "value") else x


@dataclass
class MnpCareerSnapshot:
    id: str
    code: str
    canonical_name_uk: str
    canonical_name_en: str
    description_short_uk: str
    description_long_uk: str | None
    status: str
    career_profile_version: int
    catalog_priority: int
    market_data_limited: bool
    family_code: str | None
    family_name_uk: str | None
    family_name_en: str | None
    updated_at: str | None
    difficulty_level: str | None = None
    entry_without_experience: str | None = None
    typical_entry_route_uk: str | None = None
    aliases: list[dict] = field(default_factory=list)
    tasks: list[dict] = field(default_factory=list)                 # -> 40_RESPONSIBILITIES
    skill_requirements: list[dict] = field(default_factory=list)    # -> 20_SKILLS
    knowledge_requirements: list[dict] = field(default_factory=list)
    requirements: list[dict] = field(default_factory=list)          # -> 30_REQUIREMENTS
    attributes: list[dict] = field(default_factory=list)
    relations: list[dict] = field(default_factory=list)             # career<->career prior
    path_steps: list[dict] = field(default_factory=list)            # -> 50_CAREER_PATHS
    pros_cons: list[dict] = field(default_factory=list)             # -> 60_PROS_CONS
    external_mappings: list[dict] = field(default_factory=list)     # -> 80_EXTERNAL_REFS (entity_type=career)
    skill_external_mappings: list[dict] = field(default_factory=list)
    market_snapshots: list[dict] = field(default_factory=list)      # -> 70_MARKET_DATA


async def _read(session) -> list[MnpCareerSnapshot]:
    from app.services.career_kb_mnp.seed_alpha import seed_alpha_career_kb

    await seed_alpha_career_kb(session)

    skills = {s.id: s for s in (await session.execute(select(MnpSkill))).scalars()}
    knowledge = {k.id: k for k in (await session.execute(select(MnpKnowledge))).scalars()}
    families = {f.id: f for f in (await session.execute(select(MnpCareerFamily))).scalars()}
    careers_by_id = {c.id: c for c in (await session.execute(select(MnpCareer))).scalars()}

    # skill external mappings, keyed by skill id
    skill_xmaps: dict = {}
    for em in (await session.execute(
        select(MnpExternalMapping).where(MnpExternalMapping.entity_type == "skill")
    )).scalars():
        skill_xmaps.setdefault(em.mnp_entity_id, []).append(em)

    out: list[MnpCareerSnapshot] = []
    for c in careers_by_id.values():
        fam = families.get(c.career_family_id)
        snap = MnpCareerSnapshot(
            id=str(c.id), code=c.code,
            canonical_name_uk=c.canonical_name_uk, canonical_name_en=c.canonical_name_en,
            description_short_uk=c.description_short_uk, description_long_uk=c.description_long_uk,
            status=_v(c.status), career_profile_version=c.career_profile_version,
            catalog_priority=c.catalog_priority, market_data_limited=c.market_data_limited,
            family_code=fam.code if fam else None,
            family_name_uk=fam.name_uk if fam else None, family_name_en=fam.name_en if fam else None,
            updated_at=c.updated_at.isoformat() if c.updated_at else None,
            difficulty_level=_v(c.difficulty_level) if c.difficulty_level else None,
            entry_without_experience=_v(c.entry_without_experience),
            typical_entry_route_uk=c.typical_entry_route_uk,
        )
        for a in (await session.execute(select(MnpCareerAlias).where(MnpCareerAlias.career_id == c.id))).scalars():
            snap.aliases.append({"alias": a.alias, "language": a.language, "type": _v(a.alias_type),
                                 "source": a.source, "confidence": a.confidence})

        for t in (await session.execute(select(MnpCareerTask).where(MnpCareerTask.career_id == c.id))).scalars():
            snap.tasks.append({
                "responsibility_id": t.task_code, "title_uk": t.title_uk, "title_en": t.title_en,
                "description": t.description, "importance": _v(t.importance), "frequency": t.frequency,
                "source": t.source, "source_version": t.source_version, "confidence": t.confidence,
                "entity_id": str(t.id),
            })

        for sr in (await session.execute(select(MnpCareerSkillRequirement).where(MnpCareerSkillRequirement.career_id == c.id))).scalars():
            sk = skills.get(sr.skill_id)
            xm = skill_xmaps.get(sr.skill_id, [])
            snap.skill_requirements.append({
                "skill_id": str(sr.skill_id),
                "skill_code": (xm[0].external_id if xm else None),   # first external ref, if any; else None
                "skill_en": sk.canonical_name_en if sk else None,
                "skill_uk": sk.canonical_name_uk if sk else None,
                "skill_type": _v(sk.skill_type) if sk else None,
                "requirement_level": _v(sr.requirement_type), "importance": _v(sr.importance),
                "requirement_type": _v(sr.requirement_type),      # kept for existing callers
                "proficiency_level": _v(sr.required_level), "required_level": _v(sr.required_level),
                "source_type": sr.source, "source": sr.source, "source_reference": sr.source_version,
                "source_version": sr.source_version, "confidence": sr.confidence,
                "valid_from": sr.valid_from.isoformat() if sr.valid_from else None,
                "valid_to": sr.valid_to.isoformat() if sr.valid_to else None,
                "entity_id": str(sr.id),
            })

        for kr in (await session.execute(select(MnpCareerKnowledgeRequirement).where(MnpCareerKnowledgeRequirement.career_id == c.id))).scalars():
            kn = knowledge.get(kr.knowledge_id)
            snap.knowledge_requirements.append({
                "knowledge_en": kn.canonical_name_en if kn else None,
                "knowledge_uk": kn.canonical_name_uk if kn else None,
                "importance": _v(kr.importance), "required_level": _v(kr.required_level),
                "requirement_type": _v(kr.requirement_type), "source": kr.source, "confidence": kr.confidence,
                "entity_id": str(kr.id),
            })

        for rq in (await session.execute(select(MnpCareerRequirement).where(MnpCareerRequirement.career_id == c.id))).scalars():
            snap.requirements.append({
                "requirement_type": _v(rq.category), "category": _v(rq.category),
                "requirement_name": rq.description, "description": rq.description,
                "required": True, "level": rq.value, "value": rq.value,
                "hardness": _v(rq.hardness), "hard_blocker": (_v(rq.hardness) == "hard"),
                "country": rq.country, "source_type": rq.source, "source": rq.source,
                "source_reference": rq.source_version, "source_version": rq.source_version,
                "confidence": rq.confidence,
                "valid_from": rq.valid_from.isoformat() if rq.valid_from else None,
                "valid_to": rq.valid_to.isoformat() if rq.valid_to else None,
                "entity_id": str(rq.id),
            })

        for at in (await session.execute(select(MnpCareerAttribute).where(MnpCareerAttribute.career_id == c.id))).scalars():
            snap.attributes.append({
                "group": at.attribute_group, "key": at.attribute_key,
                "value_numeric": at.value_numeric, "value_text": at.value_text,
                "source": at.source, "confidence": at.confidence, "entity_id": str(at.id),
            })

        for rel in (await session.execute(select(MnpCareerRelation).where(MnpCareerRelation.from_career_id == c.id))).scalars():
            tgt = careers_by_id.get(rel.to_career_id)
            snap.relations.append({
                "to_career_code": tgt.code if tgt else None,
                "to_career_name_uk": tgt.canonical_name_uk if tgt else None,
                "relation_type": _v(rel.relation_type), "strength": rel.strength,
                "source": rel.source, "entity_id": str(rel.id),
            })

        for ps in (await session.execute(select(MnpCareerPathStep).where(MnpCareerPathStep.career_id == c.id))).scalars():
            snap.path_steps.append({
                "path_code": ps.path_code, "step_order": ps.step_order,
                "step_name_uk": ps.step_name_uk, "step_name_en": ps.step_name_en,
                "step_type": _v(ps.step_type), "description_uk": ps.description_uk,
                "description_en": ps.description_en,
                "typical_experience_text_uk": ps.typical_experience_text_uk,
                "is_current_career_step": ps.is_current_career_step,
                "source": ps.source, "source_version": ps.source_version,
                "review_status": ps.review_status, "entity_id": str(ps.id),
            })

        for pc in (await session.execute(select(MnpCareerProCon).where(MnpCareerProCon.career_id == c.id))).scalars():
            snap.pros_cons.append({
                "type": _v(pc.type), "text_uk": pc.text_uk, "text_en": pc.text_en,
                "sort_order": pc.sort_order, "source": pc.source, "source_version": pc.source_version,
                "confidence": pc.confidence, "review_status": pc.review_status, "entity_id": str(pc.id),
            })

        for em in (await session.execute(select(MnpExternalMapping).where(MnpExternalMapping.mnp_entity_id == c.id))).scalars():
            snap.external_mappings.append({
                "source_system": _v(em.source_system), "external_id": em.external_id,
                "external_label": em.external_label, "mapping_type": _v(em.mapping_type),
                "confidence": em.confidence, "source_version": em.source_version, "entity_id": str(em.id),
            })

        for ms in (await session.execute(select(MnpMarketSnapshot).where(MnpMarketSnapshot.career_id == c.id))).scalars():
            sals = (await session.execute(select(MnpSalarySnapshot).where(MnpSalarySnapshot.market_snapshot_id == ms.id))).scalars().all()
            for sal in (sals or [None]):
                snap.market_snapshots.append({
                    "country": ms.country, "region": ms.region, "snapshot_date": ms.snapshot_date.isoformat(),
                    "source": ms.source, "source_version": ms.source_version, "data_quality": ms.data_quality,
                    "vacancy_count": ms.vacancy_count, "demand_trend": ms.demand_trend,
                    "remote_share": ms.remote_share, "sample_size": ms.sample_size,
                    "currency": sal.currency if sal else None, "period": sal.period if sal else None,
                    "salary_p25": sal.percentile_25 if sal else None,
                    "salary_median": sal.median if sal else None,
                    "salary_p75": sal.percentile_75 if sal else None,
                    "collected_at": ms.created_at.isoformat() if ms.created_at else None,
                    "entity_id": str(ms.id),
                })

        out.append(snap)

    out.sort(key=lambda s: s.code)   # deterministic
    return out


def load_mnp_careers() -> list[MnpCareerSnapshot]:
    url = os.environ.get("MNP_DATABASE_URL", "sqlite+aiosqlite:///:memory:")

    async def _main() -> list[MnpCareerSnapshot]:
        engine = create_async_engine(url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        sm = async_sessionmaker(engine, expire_on_commit=False)
        async with sm() as session:
            result = await _read(session)
        await engine.dispose()
        return result

    return asyncio.run(_main())
