"""Read the MNP Career Knowledge Base (read-only) into plain dicts, so the
Explorer / Excel can show "SOURCE FACT vs MNP INTERPRETATION" (brief §12)
without touching any production database.

The approved MNP V1 KB currently ships as an in-code seed
(`app/services/career_kb_mnp/seed_alpha.py`, 5 ACTIVE careers). We run
that seed into an ephemeral in-memory SQLite and read it back — no
production DB, no writes anywhere, no AI. If a real MNP DB is ever wired
up, point `MNP_DATABASE_URL` at it instead (still read-only).
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
from app.db.models_career_kb_mnp import (
    MnpCareer, MnpCareerAlias, MnpCareerAttribute, MnpCareerRequirement, MnpCareerTask,
    MnpCareerKnowledgeRequirement, MnpCareerSkillRequirement, MnpExternalMapping,
)
from app.db.models_career_card import MnpKnowledge, MnpSkill


@dataclass
class MnpCareerSnapshot:
    code: str
    canonical_name_uk: str
    canonical_name_en: str
    description_short_uk: str
    status: str
    career_profile_version: int
    market_data_limited: bool
    family_code: str | None
    aliases: list[dict] = field(default_factory=list)
    tasks: list[dict] = field(default_factory=list)
    skill_requirements: list[dict] = field(default_factory=list)
    knowledge_requirements: list[dict] = field(default_factory=list)
    requirements: list[dict] = field(default_factory=list)
    attributes: list[dict] = field(default_factory=list)
    external_mappings: list[dict] = field(default_factory=list)


def _v(x):
    return x.value if hasattr(x, "value") else x


async def _read(session) -> list[MnpCareerSnapshot]:
    from app.services.career_kb_mnp.seed_alpha import seed_alpha_career_kb

    await seed_alpha_career_kb(session)

    skills = {s.id: s for s in (await session.execute(select(MnpSkill))).scalars()}
    knowledge = {k.id: k for k in (await session.execute(select(MnpKnowledge))).scalars()}
    out: list[MnpCareerSnapshot] = []

    careers = (await session.execute(select(MnpCareer))).scalars().all()
    for c in careers:
        snap = MnpCareerSnapshot(
            code=c.code, canonical_name_uk=c.canonical_name_uk, canonical_name_en=c.canonical_name_en,
            description_short_uk=c.description_short_uk, status=_v(c.status),
            career_profile_version=c.career_profile_version, market_data_limited=c.market_data_limited,
            family_code=None,
        )
        for a in (await session.execute(select(MnpCareerAlias).where(MnpCareerAlias.career_id == c.id))).scalars():
            snap.aliases.append({"alias": a.alias, "language": a.language, "type": _v(a.alias_type)})
        for t in (await session.execute(select(MnpCareerTask).where(MnpCareerTask.career_id == c.id))).scalars():
            snap.tasks.append({"code": t.task_code, "title_uk": t.title_uk, "importance": _v(t.importance), "source": t.source})
        for sr in (await session.execute(select(MnpCareerSkillRequirement).where(MnpCareerSkillRequirement.career_id == c.id))).scalars():
            sk = skills.get(sr.skill_id)
            snap.skill_requirements.append({
                "skill_en": sk.canonical_name_en if sk else None,
                "skill_uk": sk.canonical_name_uk if sk else None,
                "skill_type": sk.skill_type.value if sk else None,
                "importance": _v(sr.importance), "required_level": _v(sr.required_level),
                "requirement_type": _v(sr.requirement_type), "source": sr.source, "confidence": sr.confidence,
            })
        for kr in (await session.execute(select(MnpCareerKnowledgeRequirement).where(MnpCareerKnowledgeRequirement.career_id == c.id))).scalars():
            kn = knowledge.get(kr.knowledge_id)
            snap.knowledge_requirements.append({
                "knowledge_en": kn.canonical_name_en if kn else None,
                "importance": _v(kr.importance), "source": kr.source,
            })
        for rq in (await session.execute(select(MnpCareerRequirement).where(MnpCareerRequirement.career_id == c.id))).scalars():
            snap.requirements.append({
                "category": _v(rq.category), "description": rq.description,
                "hardness": _v(rq.hardness), "value": rq.value, "source": rq.source, "confidence": rq.confidence,
            })
        for at in (await session.execute(select(MnpCareerAttribute).where(MnpCareerAttribute.career_id == c.id))).scalars():
            snap.attributes.append({
                "group": at.attribute_group, "key": at.attribute_key,
                "value_numeric": at.value_numeric, "source": at.source, "confidence": at.confidence,
            })
        for em in (await session.execute(select(MnpExternalMapping).where(MnpExternalMapping.mnp_entity_id == c.id))).scalars():
            snap.external_mappings.append({
                "source_system": _v(em.source_system), "external_id": em.external_id,
                "external_label": em.external_label, "mapping_type": _v(em.mapping_type),
                "confidence": em.confidence, "source_version": em.source_version,
            })
        out.append(snap)
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
