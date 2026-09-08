"""MNP Career KB -- seed is bootstrap-only, never an authoring system
(brief §1 / §27).

MANUAL ADMIN EDITS MUST NEVER BE OVERWRITTEN BY SEED.
"""

from __future__ import annotations

from sqlalchemy import func, select

from app.db.models_career_kb_mnp import (
    CareerLifecycleStatus,
    MnpCareer,
    MnpCareerProCon,
    MnpCareerRelation,
    MnpCareerSkillRequirement,
    MnpCareerTask,
)
from app.services.career_kb_mnp import editor
from app.services.career_kb_mnp.seed_alpha import seed_alpha_career_kb


async def _accountant(session) -> MnpCareer:
    return await editor.get_career_or_404(
        session,
        (await session.execute(select(MnpCareer.id).where(MnpCareer.code == "accountant"))).scalar_one(),
    )


async def test_reseed_is_idempotent_on_row_counts(session):
    await seed_alpha_career_kb(session)
    acc = await _accountant(session)

    def counts():
        return session.execute(
            select(
                func.count(MnpCareerTask.id).filter(MnpCareerTask.career_id == acc.id),
            )
        )

    n_tasks_1 = (await session.execute(select(func.count()).select_from(MnpCareerTask))).scalar()
    n_skill_1 = (await session.execute(select(func.count()).select_from(MnpCareerSkillRequirement))).scalar()
    n_procon_1 = (await session.execute(select(func.count()).select_from(MnpCareerProCon))).scalar()
    n_rel_1 = (await session.execute(select(func.count()).select_from(MnpCareerRelation))).scalar()

    await seed_alpha_career_kb(session)

    assert (await session.execute(select(func.count()).select_from(MnpCareerTask))).scalar() == n_tasks_1
    assert (await session.execute(select(func.count()).select_from(MnpCareerSkillRequirement))).scalar() == n_skill_1
    assert (await session.execute(select(func.count()).select_from(MnpCareerProCon))).scalar() == n_procon_1
    assert (await session.execute(select(func.count()).select_from(MnpCareerRelation))).scalar() == n_rel_1


async def test_admin_edited_description_survives_reseed(session):
    await seed_alpha_career_kb(session)
    acc = await _accountant(session)
    await editor.update_career_core(
        session, acc, actor_admin_id=1,
        short_description_uk="РЕДАГОВАНО АДМІНОМ — цей текст не має зникнути",
        long_description_uk="Адмінська версія повного опису.",
        name_en="Accountant (admin edit)",
    )
    await session.commit()

    await seed_alpha_career_kb(session)
    await session.refresh(acc)
    assert acc.description_short_uk == "РЕДАГОВАНО АДМІНОМ — цей текст не має зникнути"
    assert acc.description_long_uk == "Адмінська версія повного опису."
    assert acc.canonical_name_en == "Accountant (admin edit)"


async def test_admin_deleted_skill_is_not_re_added_by_reseed(session):
    await seed_alpha_career_kb(session)
    acc = await _accountant(session)
    a_skill = (await session.execute(
        select(MnpCareerSkillRequirement).where(MnpCareerSkillRequirement.career_id == acc.id))).scalars().first()
    skill_id = a_skill.skill_id
    await editor.detach_skill(session, acc, a_skill.id, actor_admin_id=1)
    await session.commit()

    await seed_alpha_career_kb(session)
    still_gone = (await session.execute(select(MnpCareerSkillRequirement).where(
        MnpCareerSkillRequirement.career_id == acc.id,
        MnpCareerSkillRequirement.skill_id == skill_id))).scalar_one_or_none()
    assert still_gone is None


async def test_admin_deleted_relation_is_not_re_added_by_reseed(session):
    await seed_alpha_career_kb(session)
    acc = await _accountant(session)
    rel = (await session.execute(
        select(MnpCareerRelation).where(MnpCareerRelation.from_career_id == acc.id))).scalars().first()
    assert rel is not None  # accountant has a seeded relation
    to_id = rel.to_career_id
    await editor.delete_relation(session, acc, rel.id, actor_admin_id=1)
    await session.commit()

    await seed_alpha_career_kb(session)
    assert (await session.execute(select(MnpCareerRelation).where(
        MnpCareerRelation.from_career_id == acc.id,
        MnpCareerRelation.to_career_id == to_id))).scalar_one_or_none() is None


async def test_admin_archived_career_stays_archived_after_reseed(session):
    await seed_alpha_career_kb(session)
    acc = await _accountant(session)
    await editor.archive_career(session, acc, actor_admin_id=1)
    await session.commit()

    await seed_alpha_career_kb(session)
    await session.refresh(acc)
    assert acc.status == CareerLifecycleStatus.ARCHIVED
