"""MNP Career KB Editor V1 -- operational authoring layer.

After this module exists, `seed_alpha.py` is a *bootstrap/test fixture
only*: the Career KB DB + this editor are the single operational source
of truth. Every public reader (API, Website, Matching, Excel export)
reads whatever is currently in the DB -- there is no hardcoded content, no
Excel->DB path, no seed that overwrites manual edits.

Every mutation here:
  * goes through the service layer (never raw SQL from the API/frontend);
  * bumps `MnpCareer.career_profile_version` when it changes material
    Career data (not on view/search/export);
  * writes one `AuditLog` row (reusing the existing append-only audit --
    `actor_admin_id` = who, `occurred_at` = when, before/after snapshots
    = old/new value). No second audit system.

Founder Language Policy: user-facing fields are Ukrainian; enum values /
codes are English. No runtime translation.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_career_card import (
    MnpKnowledge,
    MnpSkill,
    MnpSkillAlias,
    SkillAliasType,
    SkillStatus,
    SkillType,
)
from app.db.models_career_kb_mnp import (
    CareerAliasType,
    CareerDifficulty,
    CareerLifecycleStatus,
    CareerPathStepType,
    CareerRelationType,
    EntryWithoutExperience,
    ExternalMappingType,
    ExternalSourceSystem,
    ImportanceLevel,
    MnpCareer,
    MnpCareerFamily,
    MnpCareerKnowledgeRequirement,
    MnpCareerPathStep,
    MnpCareerProCon,
    MnpCareerRelation,
    MnpCareerRequirement,
    MnpCareerSkillRequirement,
    MnpCareerTask,
    MnpExternalMapping,
    ProConType,
    RequirementCategory,
    RequirementHardness,
    RequirementType,
)
from app.db.models_platform import AuditLog
from app.services.audit import record_audit
from app.services.career_kb_mnp.skills import normalize_phrase
from app.services.exceptions import (
    MnpCareerNotFoundError,
    MnpDuplicateCareerCodeError,
    MnpInvalidLifecycleTransitionError,
)

_UNSET: Any = object()

# ---------------------------------------------------------------------------
# Source / review vocabularies (English codes; the UI shows Ukrainian labels)
SOURCE_TYPES = ["mnp_editorial_v1", "expert_review", "official_ua", "esco", "onet", "other"]
REVIEW_STATES = ["editorial", "expert_reviewed", "needs_review", "approved", "rejected"]
# source_type values that REQUIRE a source_reference (§19)
_SOURCE_REQUIRES_REF = {"official_ua", "esco", "onet", "other"}


class CareerKbValidationError(ValueError):
    """A curator-facing validation failure (surfaced as HTTP 400/409)."""


def _v(x: Any) -> Any:
    return x.value if hasattr(x, "value") else x


def _clean_source(source_type: str | None, source_reference: str | None) -> tuple[str, str | None]:
    st = (source_type or "mnp_editorial_v1").strip().lower()
    if st not in SOURCE_TYPES:
        raise CareerKbValidationError(f"unknown source_type {source_type!r}")
    ref = (source_reference or "").strip() or None
    if st == "mnp_editorial_v1" and ref is None:
        ref = "mnp_editorial_v1"
    if st in _SOURCE_REQUIRES_REF and not ref:
        raise CareerKbValidationError(f"source_reference is required when source_type is {st!r}")
    return st, ref


def _check_review(review_status: str | None) -> str:
    rs = (review_status or "editorial").strip().lower()
    if rs not in REVIEW_STATES:
        raise CareerKbValidationError(f"unknown review_status {review_status!r}")
    return rs


async def _audit(
    session: AsyncSession, *, actor_admin_id: int | None, entity_type: str, entity_id: uuid.UUID | str,
    action: str, career: MnpCareer, before: dict | None = None, after: dict | None = None,
) -> None:
    payload_after = dict(after or {})
    payload_after.setdefault("career_id", str(career.id))
    payload_after.setdefault("career_code", career.code)
    payload_after.setdefault("career_profile_version", career.career_profile_version)
    await record_audit(
        session, entity_type=entity_type, entity_id=str(entity_id), action=action,
        actor_admin_id=actor_admin_id, before=before, after=payload_after,
    )


def _bump(career: MnpCareer) -> None:
    career.career_profile_version += 1


# ===========================================================================
# Career lookup
# ===========================================================================
async def get_career_or_404(session: AsyncSession, career_id: uuid.UUID) -> MnpCareer:
    from sqlalchemy.orm import selectinload

    career = (await session.execute(
        select(MnpCareer).where(MnpCareer.id == career_id).options(selectinload(MnpCareer.career_family))
    )).scalar_one_or_none()
    if career is None:
        raise MnpCareerNotFoundError(f"no MnpCareer {career_id}")
    return career


# ===========================================================================
# 1. CAREER CORE  (§5, §8)
# ===========================================================================
async def create_career_draft(
    session: AsyncSession, *, actor_admin_id: int | None, code: str, name_uk: str,
    category_uk: str, name_en: str | None = None, short_description_uk: str = "",
    long_description_uk: str | None = None, difficulty_level: str | None = None,
    entry_without_experience: str | None = None, typical_entry_route_uk: str | None = None,
) -> MnpCareer:
    code = code.strip()
    if not code or not code.replace("_", "").isalnum():
        raise CareerKbValidationError("career_code must be a non-empty snake_case identifier")
    if not name_uk.strip():
        raise CareerKbValidationError("name_uk is required")
    if (await session.execute(select(MnpCareer).where(MnpCareer.code == code))).scalar_one_or_none() is not None:
        raise MnpDuplicateCareerCodeError(f"career_code {code!r} already exists")

    family = await _get_or_create_family(session, category_uk)
    career = MnpCareer(
        code=code, canonical_name_uk=name_uk.strip(), canonical_name_en=(name_en or name_uk).strip(),
        description_short_uk=short_description_uk.strip(), description_long_uk=(long_description_uk or None),
        career_family_id=family.id, status=CareerLifecycleStatus.DRAFT, career_profile_version=1,
        market_data_limited=True,
    )
    if difficulty_level:
        career.difficulty_level = CareerDifficulty(difficulty_level)
    if entry_without_experience:
        career.entry_without_experience = EntryWithoutExperience(entry_without_experience)
    if typical_entry_route_uk:
        career.typical_entry_route_uk = typical_entry_route_uk.strip()
    session.add(career)
    await session.flush()
    await session.refresh(career, ["career_family"])
    # a career alias for its own market title keeps alias-resolution working
    session.add(_alias_row(career, name_uk.strip()))
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, entity_type="mnp_career", entity_id=career.id,
                 action="created", career=career, after={"code": code, "status": "draft"})
    return career


def _alias_row(career: MnpCareer, alias: str):
    from app.db.models_career_kb_mnp import MnpCareerAlias
    return MnpCareerAlias(
        career_id=career.id, alias=alias, language="uk", alias_type=CareerAliasType.MARKET_TITLE,
        source="mnp_editorial_v1", status=CareerLifecycleStatus.ACTIVE,
    )


async def update_career_core(
    session: AsyncSession, career: MnpCareer, *, actor_admin_id: int | None,
    name_uk: str = _UNSET, name_en: str = _UNSET, category_uk: str = _UNSET,
    short_description_uk: str = _UNSET, long_description_uk: str | None = _UNSET,
    difficulty_level: str | None = _UNSET, entry_without_experience: str | None = _UNSET,
    typical_entry_route_uk: str | None = _UNSET,
) -> MnpCareer:
    before = _career_core_snapshot(career)

    if name_uk is not _UNSET:
        if not str(name_uk).strip():
            raise CareerKbValidationError("name_uk cannot be empty")
        career.canonical_name_uk = str(name_uk).strip()
    if name_en is not _UNSET:
        career.canonical_name_en = str(name_en).strip() or career.canonical_name_uk
    if short_description_uk is not _UNSET:
        career.description_short_uk = str(short_description_uk).strip()
    if long_description_uk is not _UNSET:
        career.description_long_uk = (str(long_description_uk).strip() or None) if long_description_uk else None
    if difficulty_level is not _UNSET:
        career.difficulty_level = CareerDifficulty(difficulty_level) if difficulty_level else None
    if entry_without_experience is not _UNSET:
        career.entry_without_experience = EntryWithoutExperience(entry_without_experience or "unknown")
    if typical_entry_route_uk is not _UNSET:
        career.typical_entry_route_uk = (str(typical_entry_route_uk).strip() or None) if typical_entry_route_uk else None
    if category_uk is not _UNSET and str(category_uk).strip():
        family = await _get_or_create_family(session, str(category_uk).strip())
        career.career_family_id = family.id

    await session.flush()
    await session.refresh(career, ["career_family"])
    after = _career_core_snapshot(career)
    if after != before:
        _bump(career)
        await session.flush()
        await _audit(session, actor_admin_id=actor_admin_id, entity_type="mnp_career", entity_id=career.id,
                     action="core_updated", career=career, before=before, after=after)
    return career


def _career_core_snapshot(c: MnpCareer) -> dict:
    return {
        "name_uk": c.canonical_name_uk, "name_en": c.canonical_name_en,
        "short_description_uk": c.description_short_uk, "long_description_uk": c.description_long_uk,
        "category_uk": c.career_family.name_uk if c.career_family else None,
        "difficulty_level": _v(c.difficulty_level), "entry_without_experience": _v(c.entry_without_experience),
        "typical_entry_route_uk": c.typical_entry_route_uk,
    }


async def _get_or_create_family(session: AsyncSession, name_uk: str) -> MnpCareerFamily:
    name_uk = name_uk.strip()
    existing = (await session.execute(
        select(MnpCareerFamily).where(MnpCareerFamily.name_uk == name_uk))).scalar_one_or_none()
    if existing is not None:
        return existing
    code = normalize_phrase(name_uk).replace(" ", "_")[:60] or f"family_{uuid.uuid4().hex[:8]}"
    if (await session.execute(select(MnpCareerFamily).where(MnpCareerFamily.code == code))).scalar_one_or_none():
        code = f"{code}_{uuid.uuid4().hex[:6]}"
    fam = MnpCareerFamily(code=code, name_uk=name_uk, name_en=name_uk)
    session.add(fam)
    await session.flush()
    return fam


# ===========================================================================
# 2. LIFECYCLE  (§22 publish, §23 archive)
# ===========================================================================
PUBLISH_MIN = {
    "name_uk": "назва професії українською",
    "career_code": "код професії",
    "short_description_uk": "короткий опис",
    "long_description_uk": "повний опис",
    "responsibilities": "щонайменше один обов'язок",
    "skills": "щонайменше одна навичка",
}


async def check_publish_readiness(session: AsyncSession, career: MnpCareer) -> list[str]:
    missing: list[str] = []
    if not career.canonical_name_uk.strip():
        missing.append(PUBLISH_MIN["name_uk"])
    if not career.code.strip():
        missing.append(PUBLISH_MIN["career_code"])
    if not career.description_short_uk.strip():
        missing.append(PUBLISH_MIN["short_description_uk"])
    if not (career.description_long_uk or "").strip():
        missing.append(PUBLISH_MIN["long_description_uk"])
    n_resp = (await session.execute(
        select(MnpCareerTask.id).where(MnpCareerTask.career_id == career.id))).scalars().first()
    if n_resp is None:
        missing.append(PUBLISH_MIN["responsibilities"])
    n_skill = (await session.execute(
        select(MnpCareerSkillRequirement.id).where(MnpCareerSkillRequirement.career_id == career.id))).scalars().first()
    if n_skill is None:
        missing.append(PUBLISH_MIN["skills"])
    return missing


async def publish_career(session: AsyncSession, career: MnpCareer, *, actor_admin_id: int | None) -> MnpCareer:
    if career.status == CareerLifecycleStatus.ACTIVE:
        return career
    if career.status not in (CareerLifecycleStatus.DRAFT, CareerLifecycleStatus.VALIDATED,
                             CareerLifecycleStatus.REVIEW_DUE, CareerLifecycleStatus.ARCHIVED):
        raise MnpInvalidLifecycleTransitionError(f"cannot publish from {career.status.value}")
    missing = await check_publish_readiness(session, career)
    if missing:
        raise CareerKbValidationError("Не можна опублікувати: бракує — " + "; ".join(missing))
    before = {"status": career.status.value}
    from datetime import datetime, timezone
    career.status = CareerLifecycleStatus.ACTIVE
    if career.published_at is None:
        career.published_at = datetime.now(timezone.utc)
    _bump(career)
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, entity_type="mnp_career", entity_id=career.id,
                 action="published", career=career, before=before, after={"status": "active"})
    return career


async def archive_career(session: AsyncSession, career: MnpCareer, *, actor_admin_id: int | None) -> MnpCareer:
    if career.status == CareerLifecycleStatus.ARCHIVED:
        return career
    before = {"status": career.status.value}
    career.status = CareerLifecycleStatus.ARCHIVED
    _bump(career)
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, entity_type="mnp_career", entity_id=career.id,
                 action="archived", career=career, before=before, after={"status": "archived"})
    return career


async def unarchive_career(session: AsyncSession, career: MnpCareer, *, actor_admin_id: int | None) -> MnpCareer:
    if career.status != CareerLifecycleStatus.ARCHIVED:
        return career
    before = {"status": career.status.value}
    career.status = CareerLifecycleStatus.DRAFT
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, entity_type="mnp_career", entity_id=career.id,
                 action="unarchived", career=career, before=before, after={"status": "draft"})
    return career


# ===========================================================================
# 3. RESPONSIBILITIES  (§9)
# ===========================================================================
async def _next_sort(session: AsyncSession, model, career_id: uuid.UUID) -> int:
    rows = (await session.execute(select(model.sort_order).where(model.career_id == career_id))).scalars().all()
    return (max(rows) + 1) if rows else 1


async def add_responsibility(
    session: AsyncSession, career: MnpCareer, *, actor_admin_id: int | None, title_uk: str,
    description_uk: str | None = None, importance: str = "medium", frequency: str | None = None,
    source_type: str | None = None, source_reference: str | None = None, review_status: str | None = None,
) -> MnpCareerTask:
    if not title_uk.strip():
        raise CareerKbValidationError("title_uk is required")
    st, ref = _clean_source(source_type, source_reference)
    row = MnpCareerTask(
        career_id=career.id, task_code=f"{career.code}_r{uuid.uuid4().hex[:8]}",
        title_uk=title_uk.strip(), description=(description_uk or None),
        importance=ImportanceLevel(importance), frequency=(frequency or None),
        sort_order=await _next_sort(session, MnpCareerTask, career.id),
        source=st, source_version=ref, confidence=0.7, review_status=_check_review(review_status),
    )
    session.add(row)
    _bump(career)
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, entity_type="mnp_career_task", entity_id=row.id,
                 action="created", career=career, after={"title_uk": row.title_uk})
    return row


async def update_responsibility(
    session: AsyncSession, career: MnpCareer, task_id: uuid.UUID, *, actor_admin_id: int | None,
    title_uk: str = _UNSET, description_uk: str | None = _UNSET, importance: str = _UNSET,
    frequency: str | None = _UNSET, source_type: str | None = _UNSET, source_reference: str | None = _UNSET,
    review_status: str | None = _UNSET,
) -> MnpCareerTask:
    row = await _child_or_404(session, MnpCareerTask, task_id, career.id)
    before = {"title_uk": row.title_uk, "description_uk": row.description, "importance": _v(row.importance),
              "frequency": row.frequency, "source_type": row.source, "source_reference": row.source_version,
              "review_status": row.review_status}
    if title_uk is not _UNSET:
        if not str(title_uk).strip():
            raise CareerKbValidationError("title_uk cannot be empty")
        row.title_uk = str(title_uk).strip()
    if description_uk is not _UNSET:
        row.description = (str(description_uk).strip() or None) if description_uk else None
    if importance is not _UNSET:
        row.importance = ImportanceLevel(importance)
    if frequency is not _UNSET:
        row.frequency = (frequency or None)
    if source_type is not _UNSET or source_reference is not _UNSET:
        st, ref = _clean_source(
            row.source if source_type is _UNSET else source_type,
            row.source_version if source_reference is _UNSET else source_reference,
        )
        row.source, row.source_version = st, ref
    if review_status is not _UNSET:
        row.review_status = _check_review(review_status)
    _bump(career)
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, entity_type="mnp_career_task", entity_id=row.id,
                 action="updated", career=career, before=before,
                 after={"title_uk": row.title_uk, "description_uk": row.description,
                        "importance": _v(row.importance), "review_status": row.review_status})
    return row


async def delete_responsibility(
    session: AsyncSession, career: MnpCareer, task_id: uuid.UUID, *, actor_admin_id: int | None,
) -> None:
    row = await _child_or_404(session, MnpCareerTask, task_id, career.id)
    before = {"title_uk": row.title_uk}
    await session.delete(row)
    _bump(career)
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, entity_type="mnp_career_task", entity_id=task_id,
                 action="deleted", career=career, before=before)


async def reorder_responsibility(
    session: AsyncSession, career: MnpCareer, task_id: uuid.UUID, *, actor_admin_id: int | None, direction: str,
) -> list[MnpCareerTask]:
    return await _reorder(session, MnpCareerTask, career, task_id, direction=direction,
                          actor_admin_id=actor_admin_id, entity_type="mnp_career_task")


# ===========================================================================
# shared child helpers
# ===========================================================================
async def _child_or_404(session: AsyncSession, model, row_id: uuid.UUID, career_id: uuid.UUID):
    row = await session.get(model, row_id)
    if row is None or row.career_id != career_id:
        raise MnpCareerNotFoundError(f"{model.__tablename__} {row_id} not found for this career")
    return row


async def _reorder(
    session: AsyncSession, model, career: MnpCareer, row_id: uuid.UUID, *, direction: str,
    actor_admin_id: int | None, entity_type: str, order_attr: str = "sort_order",
) -> list:
    if direction not in ("up", "down"):
        raise CareerKbValidationError("direction must be 'up' or 'down'")
    rows = (await session.execute(
        select(model).where(model.career_id == career.id).order_by(getattr(model, order_attr))
    )).scalars().all()
    idx = next((i for i, r in enumerate(rows) if r.id == row_id), None)
    if idx is None:
        raise MnpCareerNotFoundError("row not found for this career")
    swap = idx - 1 if direction == "up" else idx + 1
    if 0 <= swap < len(rows):
        a, b = rows[idx], rows[swap]
        av, bv = getattr(a, order_attr), getattr(b, order_attr)
        setattr(a, order_attr, bv)
        setattr(b, order_attr, av)
        _bump(career)
        await session.flush()
        await _audit(session, actor_admin_id=actor_admin_id, entity_type=entity_type, entity_id=row_id,
                     action="reordered", career=career, after={"direction": direction})
        rows = (await session.execute(
            select(model).where(model.career_id == career.id).order_by(getattr(model, order_attr))
        )).scalars().all()
    return list(rows)


# ===========================================================================
# 4. SKILLS  (§10)
# ===========================================================================
async def search_skills(session: AsyncSession, q: str, *, limit: int = 20) -> list[MnpSkill]:
    q = (q or "").strip()
    if not q:
        return (await session.execute(
            select(MnpSkill).where(MnpSkill.status == SkillStatus.ACTIVE)
            .order_by(MnpSkill.canonical_name_uk).limit(limit))).scalars().all()
    norm = normalize_phrase(q)
    like = f"%{q}%"
    by_name = (await session.execute(
        select(MnpSkill).where(
            MnpSkill.status != SkillStatus.ARCHIVED,
            or_(MnpSkill.canonical_name_uk.ilike(like), MnpSkill.canonical_name_en.ilike(like)),
        ).limit(limit))).scalars().all()
    hits = {s.id: s for s in by_name}
    for alias in (await session.execute(
        select(MnpSkillAlias).where(MnpSkillAlias.alias.ilike(like)).limit(limit))).scalars().all():
        if alias.skill_id not in hits:
            sk = await session.get(MnpSkill, alias.skill_id)
            if sk is not None and sk.status != SkillStatus.ARCHIVED:
                hits[sk.id] = sk
    # exact normalized match first
    ordered = sorted(hits.values(), key=lambda s: (normalize_phrase(s.canonical_name_uk) != norm,
                                                   s.canonical_name_uk))
    return ordered[:limit]


async def create_canonical_skill(
    session: AsyncSession, *, actor_admin_id: int | None, name_uk: str, name_en: str,
    skill_type: str, description: str | None = None,
) -> MnpSkill:
    name_uk, name_en = name_uk.strip(), name_en.strip()
    if not name_uk or not name_en:
        raise CareerKbValidationError("both name_uk and name_en are required for a canonical skill")
    dup = await search_skills(session, name_uk, limit=5)
    for s in dup:
        if normalize_phrase(s.canonical_name_uk) == normalize_phrase(name_uk):
            raise CareerKbValidationError(f"skill «{s.canonical_name_uk}» already exists")
    skill = MnpSkill(
        canonical_name_en=name_en, canonical_name_uk=name_uk, skill_type=SkillType(skill_type),
        status=SkillStatus.ACTIVE, description=(description or None),
        taxonomy_version="mnp_editor_v1", skill_family="Editor",
    )
    session.add(skill)
    await session.flush()
    await record_audit(session, entity_type="mnp_skill", entity_id=str(skill.id), action="created",
                       actor_admin_id=actor_admin_id, after={"name_uk": name_uk, "name_en": name_en})
    return skill


async def attach_skill(
    session: AsyncSession, career: MnpCareer, skill_id: uuid.UUID, *, actor_admin_id: int | None,
    importance: str = "medium", required_level: str = "working", requirement_type: str = "high_value",
    source_type: str | None = None, source_reference: str | None = None, review_status: str | None = None,
) -> MnpCareerSkillRequirement:
    skill_id = uuid.UUID(str(skill_id))
    skill = await session.get(MnpSkill, skill_id)
    if skill is None:
        raise CareerKbValidationError("skill not found")
    if (await session.execute(select(MnpCareerSkillRequirement).where(
            MnpCareerSkillRequirement.career_id == career.id,
            MnpCareerSkillRequirement.skill_id == skill_id))).scalar_one_or_none() is not None:
        raise CareerKbValidationError(f"«{skill.canonical_name_uk}» вже додано до цієї професії")
    if required_level not in ("basic", "working", "strong"):
        raise CareerKbValidationError("required_level must be basic|working|strong")
    st, ref = _clean_source(source_type, source_reference)
    row = MnpCareerSkillRequirement(
        career_id=career.id, skill_id=skill_id, importance=ImportanceLevel(importance),
        required_level=required_level, requirement_type=RequirementType(requirement_type),
        source=st, source_version=ref, confidence=0.7, review_status=_check_review(review_status),
    )
    session.add(row)
    _bump(career)
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, entity_type="mnp_career_skill_requirement",
                 entity_id=row.id, action="created", career=career,
                 after={"skill": skill.canonical_name_uk, "skill_type": _v(skill.skill_type)})
    return row


async def update_skill_requirement(
    session: AsyncSession, career: MnpCareer, req_id: uuid.UUID, *, actor_admin_id: int | None,
    importance: str = _UNSET, required_level: str = _UNSET, requirement_type: str = _UNSET,
    source_type: str | None = _UNSET, source_reference: str | None = _UNSET, review_status: str | None = _UNSET,
) -> MnpCareerSkillRequirement:
    row = await _child_or_404(session, MnpCareerSkillRequirement, req_id, career.id)
    before = {"importance": _v(row.importance), "required_level": row.required_level,
              "requirement_type": _v(row.requirement_type), "source_type": row.source,
              "source_reference": row.source_version, "review_status": row.review_status}
    if importance is not _UNSET:
        row.importance = ImportanceLevel(importance)
    if required_level is not _UNSET:
        if required_level not in ("basic", "working", "strong"):
            raise CareerKbValidationError("required_level must be basic|working|strong")
        row.required_level = required_level
    if requirement_type is not _UNSET:
        row.requirement_type = RequirementType(requirement_type)
    if source_type is not _UNSET or source_reference is not _UNSET:
        st, ref = _clean_source(row.source if source_type is _UNSET else source_type,
                                row.source_version if source_reference is _UNSET else source_reference)
        row.source, row.source_version = st, ref
    if review_status is not _UNSET:
        row.review_status = _check_review(review_status)
    _bump(career)
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, entity_type="mnp_career_skill_requirement",
                 entity_id=row.id, action="updated", career=career, before=before,
                 after={"importance": _v(row.importance), "required_level": row.required_level,
                        "requirement_type": _v(row.requirement_type), "review_status": row.review_status})
    return row


async def detach_skill(
    session: AsyncSession, career: MnpCareer, req_id: uuid.UUID, *, actor_admin_id: int | None,
) -> None:
    row = await _child_or_404(session, MnpCareerSkillRequirement, req_id, career.id)
    skill = await session.get(MnpSkill, row.skill_id)
    before = {"skill": skill.canonical_name_uk if skill else str(row.skill_id)}
    await session.delete(row)
    _bump(career)
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, entity_type="mnp_career_skill_requirement",
                 entity_id=req_id, action="deleted", career=career, before=before)


# ===========================================================================
# 5. KNOWLEDGE  (§11)
# ===========================================================================
async def search_knowledge(session: AsyncSession, q: str, *, limit: int = 20) -> list[MnpKnowledge]:
    q = (q or "").strip()
    stmt = select(MnpKnowledge).order_by(MnpKnowledge.canonical_name_uk).limit(limit)
    if q:
        like = f"%{q}%"
        stmt = select(MnpKnowledge).where(
            or_(MnpKnowledge.canonical_name_uk.ilike(like), MnpKnowledge.canonical_name_en.ilike(like))
        ).limit(limit)
    return (await session.execute(stmt)).scalars().all()


async def create_knowledge(
    session: AsyncSession, *, actor_admin_id: int | None, name_uk: str, name_en: str,
) -> MnpKnowledge:
    name_uk, name_en = name_uk.strip(), name_en.strip()
    if not name_uk or not name_en:
        raise CareerKbValidationError("both name_uk and name_en are required")
    for k in await search_knowledge(session, name_uk, limit=5):
        if normalize_phrase(k.canonical_name_uk) == normalize_phrase(name_uk):
            raise CareerKbValidationError(f"knowledge «{k.canonical_name_uk}» already exists")
    row = MnpKnowledge(canonical_name_en=name_en, canonical_name_uk=name_uk, status=SkillStatus.ACTIVE)
    session.add(row)
    await session.flush()
    await record_audit(session, entity_type="mnp_knowledge", entity_id=str(row.id), action="created",
                       actor_admin_id=actor_admin_id, after={"name_uk": name_uk})
    return row


async def attach_knowledge(
    session: AsyncSession, career: MnpCareer, knowledge_id: uuid.UUID, *, actor_admin_id: int | None,
    importance: str = "medium", required_level: str = "working", requirement_type: str = "must_have",
    source_type: str | None = None, source_reference: str | None = None, review_status: str | None = None,
) -> MnpCareerKnowledgeRequirement:
    knowledge_id = uuid.UUID(str(knowledge_id))
    kn = await session.get(MnpKnowledge, knowledge_id)
    if kn is None:
        raise CareerKbValidationError("knowledge not found")
    if (await session.execute(select(MnpCareerKnowledgeRequirement).where(
            MnpCareerKnowledgeRequirement.career_id == career.id,
            MnpCareerKnowledgeRequirement.knowledge_id == knowledge_id))).scalar_one_or_none() is not None:
        raise CareerKbValidationError(f"«{kn.canonical_name_uk}» вже додано")
    st, ref = _clean_source(source_type, source_reference)
    row = MnpCareerKnowledgeRequirement(
        career_id=career.id, knowledge_id=knowledge_id, importance=ImportanceLevel(importance),
        required_level=required_level, requirement_type=RequirementType(requirement_type),
        source=st, source_version=ref, confidence=0.7, review_status=_check_review(review_status),
    )
    session.add(row)
    _bump(career)
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, entity_type="mnp_career_knowledge_requirement",
                 entity_id=row.id, action="created", career=career, after={"knowledge": kn.canonical_name_uk})
    return row


async def update_knowledge_requirement(
    session: AsyncSession, career: MnpCareer, req_id: uuid.UUID, *, actor_admin_id: int | None,
    importance: str = _UNSET, required_level: str = _UNSET, requirement_type: str = _UNSET,
    source_type: str | None = _UNSET, source_reference: str | None = _UNSET, review_status: str | None = _UNSET,
) -> MnpCareerKnowledgeRequirement:
    row = await _child_or_404(session, MnpCareerKnowledgeRequirement, req_id, career.id)
    before = {"importance": _v(row.importance), "required_level": row.required_level,
              "requirement_type": _v(row.requirement_type), "review_status": row.review_status}
    if importance is not _UNSET:
        row.importance = ImportanceLevel(importance)
    if required_level is not _UNSET:
        row.required_level = required_level
    if requirement_type is not _UNSET:
        row.requirement_type = RequirementType(requirement_type)
    if source_type is not _UNSET or source_reference is not _UNSET:
        st, ref = _clean_source(row.source if source_type is _UNSET else source_type,
                                row.source_version if source_reference is _UNSET else source_reference)
        row.source, row.source_version = st, ref
    if review_status is not _UNSET:
        row.review_status = _check_review(review_status)
    _bump(career)
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, entity_type="mnp_career_knowledge_requirement",
                 entity_id=row.id, action="updated", career=career, before=before,
                 after={"importance": _v(row.importance), "review_status": row.review_status})
    return row


async def detach_knowledge(
    session: AsyncSession, career: MnpCareer, req_id: uuid.UUID, *, actor_admin_id: int | None,
) -> None:
    row = await _child_or_404(session, MnpCareerKnowledgeRequirement, req_id, career.id)
    await session.delete(row)
    _bump(career)
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, entity_type="mnp_career_knowledge_requirement",
                 entity_id=req_id, action="deleted", career=career)


# ===========================================================================
# 6. REQUIREMENTS  (§12)
# ===========================================================================
async def add_requirement(
    session: AsyncSession, career: MnpCareer, *, actor_admin_id: int | None, category: str,
    description_uk: str, value: str | None = None, hardness: str = "soft", country: str | None = "UA",
    source_type: str | None = None, source_reference: str | None = None, review_status: str | None = None,
) -> MnpCareerRequirement:
    if not description_uk.strip():
        raise CareerKbValidationError("description_uk is required")
    hardness = hardness.strip().lower()
    if hardness not in ("soft", "hard"):
        raise CareerKbValidationError("hardness must be soft|hard")
    st, ref = _clean_source(source_type, source_reference)
    if hardness == "hard" and st == "mnp_editorial_v1":
        raise CareerKbValidationError(
            "жорстка (HARD) вимога має спиратися на авторитетне джерело (official_ua / esco / onet), "
            "а не на редакційну оцінку")
    row = MnpCareerRequirement(
        career_id=career.id, category=RequirementCategory(category), description=description_uk.strip(),
        value=(value or None), hardness=RequirementHardness(hardness), country=(country or None),
        sort_order=await _next_sort(session, MnpCareerRequirement, career.id),
        source=st, source_version=ref, confidence=0.65, review_status=_check_review(review_status),
    )
    session.add(row)
    _bump(career)
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, entity_type="mnp_career_requirement", entity_id=row.id,
                 action="created", career=career, after={"category": category, "description_uk": row.description,
                                                         "hardness": hardness})
    return row


async def update_requirement(
    session: AsyncSession, career: MnpCareer, req_id: uuid.UUID, *, actor_admin_id: int | None,
    category: str = _UNSET, description_uk: str = _UNSET, value: str | None = _UNSET, hardness: str = _UNSET,
    country: str | None = _UNSET, source_type: str | None = _UNSET, source_reference: str | None = _UNSET,
    review_status: str | None = _UNSET,
) -> MnpCareerRequirement:
    row = await _child_or_404(session, MnpCareerRequirement, req_id, career.id)
    before = {"category": _v(row.category), "description_uk": row.description, "value": row.value,
              "hardness": _v(row.hardness), "country": row.country, "source_type": row.source,
              "source_reference": row.source_version, "review_status": row.review_status}
    if category is not _UNSET:
        row.category = RequirementCategory(category)
    if description_uk is not _UNSET:
        if not str(description_uk).strip():
            raise CareerKbValidationError("description_uk cannot be empty")
        row.description = str(description_uk).strip()
    if value is not _UNSET:
        row.value = (str(value).strip() or None) if value else None
    if hardness is not _UNSET:
        if hardness not in ("soft", "hard"):
            raise CareerKbValidationError("hardness must be soft|hard")
        row.hardness = RequirementHardness(hardness)
    if country is not _UNSET:
        row.country = (country or None)
    if source_type is not _UNSET or source_reference is not _UNSET:
        st, ref = _clean_source(row.source if source_type is _UNSET else source_type,
                                row.source_version if source_reference is _UNSET else source_reference)
        row.source, row.source_version = st, ref
    if review_status is not _UNSET:
        row.review_status = _check_review(review_status)
    if _v(row.hardness) == "hard" and (row.source or "mnp_editorial_v1") == "mnp_editorial_v1":
        raise CareerKbValidationError("жорстка вимога потребує авторитетного джерела")
    _bump(career)
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, entity_type="mnp_career_requirement", entity_id=row.id,
                 action="updated", career=career, before=before,
                 after={"category": _v(row.category), "description_uk": row.description,
                        "hardness": _v(row.hardness), "review_status": row.review_status})
    return row


async def delete_requirement(
    session: AsyncSession, career: MnpCareer, req_id: uuid.UUID, *, actor_admin_id: int | None,
) -> None:
    row = await _child_or_404(session, MnpCareerRequirement, req_id, career.id)
    before = {"category": _v(row.category), "description_uk": row.description}
    await session.delete(row)
    _bump(career)
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, entity_type="mnp_career_requirement", entity_id=req_id,
                 action="deleted", career=career, before=before)


# ===========================================================================
# 7. CAREER PATH  (§13)
# ===========================================================================
async def add_path_step(
    session: AsyncSession, career: MnpCareer, *, actor_admin_id: int | None, step_name_uk: str,
    step_type: str = "core", description_uk: str | None = None, typical_experience_text_uk: str | None = None,
    is_current_career_step: bool = False, path_code: str = "typical",
    source_type: str | None = None, source_reference: str | None = None, review_status: str | None = None,
) -> MnpCareerPathStep:
    if not step_name_uk.strip():
        raise CareerKbValidationError("step_name_uk is required")
    st, ref = _clean_source(source_type, source_reference)
    orders = (await session.execute(select(MnpCareerPathStep.step_order).where(
        MnpCareerPathStep.career_id == career.id, MnpCareerPathStep.path_code == path_code))).scalars().all()
    row = MnpCareerPathStep(
        career_id=career.id, path_code=path_code, step_order=(max(orders) + 1 if orders else 1),
        step_name_uk=step_name_uk.strip(), step_type=CareerPathStepType(step_type),
        description_uk=(description_uk or None),
        typical_experience_text_uk=(typical_experience_text_uk or None),
        is_current_career_step=bool(is_current_career_step),
        source=st, source_version=ref, review_status=_check_review(review_status),
    )
    session.add(row)
    if row.is_current_career_step:
        await _clear_other_current_steps(session, career.id, keep_id=None)
    _bump(career)
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, entity_type="mnp_career_path_step", entity_id=row.id,
                 action="created", career=career, after={"step_name_uk": row.step_name_uk})
    return row


async def _clear_other_current_steps(session: AsyncSession, career_id: uuid.UUID, keep_id) -> None:
    for s in (await session.execute(select(MnpCareerPathStep).where(
            MnpCareerPathStep.career_id == career_id,
            MnpCareerPathStep.is_current_career_step.is_(True)))).scalars().all():
        if s.id != keep_id:
            s.is_current_career_step = False


async def update_path_step(
    session: AsyncSession, career: MnpCareer, step_id: uuid.UUID, *, actor_admin_id: int | None,
    step_name_uk: str = _UNSET, step_type: str = _UNSET, description_uk: str | None = _UNSET,
    typical_experience_text_uk: str | None = _UNSET, is_current_career_step: bool = _UNSET,
    source_type: str | None = _UNSET, source_reference: str | None = _UNSET, review_status: str | None = _UNSET,
) -> MnpCareerPathStep:
    row = await _child_or_404(session, MnpCareerPathStep, step_id, career.id)
    before = {"step_name_uk": row.step_name_uk, "step_type": _v(row.step_type),
              "description_uk": row.description_uk, "typical_experience_text_uk": row.typical_experience_text_uk,
              "is_current_career_step": row.is_current_career_step, "review_status": row.review_status}
    if step_name_uk is not _UNSET:
        if not str(step_name_uk).strip():
            raise CareerKbValidationError("step_name_uk cannot be empty")
        row.step_name_uk = str(step_name_uk).strip()
    if step_type is not _UNSET:
        row.step_type = CareerPathStepType(step_type)
    if description_uk is not _UNSET:
        row.description_uk = (str(description_uk).strip() or None) if description_uk else None
    if typical_experience_text_uk is not _UNSET:
        row.typical_experience_text_uk = (typical_experience_text_uk or None)
    if is_current_career_step is not _UNSET:
        row.is_current_career_step = bool(is_current_career_step)
        if row.is_current_career_step:
            await _clear_other_current_steps(session, career.id, keep_id=row.id)
    if source_type is not _UNSET or source_reference is not _UNSET:
        st, ref = _clean_source(row.source if source_type is _UNSET else source_type,
                                row.source_version if source_reference is _UNSET else source_reference)
        row.source, row.source_version = st, ref
    if review_status is not _UNSET:
        row.review_status = _check_review(review_status)
    _bump(career)
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, entity_type="mnp_career_path_step", entity_id=row.id,
                 action="updated", career=career, before=before,
                 after={"step_name_uk": row.step_name_uk, "is_current_career_step": row.is_current_career_step})
    return row


async def delete_path_step(
    session: AsyncSession, career: MnpCareer, step_id: uuid.UUID, *, actor_admin_id: int | None,
) -> None:
    row = await _child_or_404(session, MnpCareerPathStep, step_id, career.id)
    before = {"step_name_uk": row.step_name_uk}
    await session.delete(row)
    _bump(career)
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, entity_type="mnp_career_path_step", entity_id=step_id,
                 action="deleted", career=career, before=before)


async def reorder_path_step(
    session: AsyncSession, career: MnpCareer, step_id: uuid.UUID, *, actor_admin_id: int | None, direction: str,
) -> list[MnpCareerPathStep]:
    return await _reorder(session, MnpCareerPathStep, career, step_id, direction=direction,
                          actor_admin_id=actor_admin_id, entity_type="mnp_career_path_step",
                          order_attr="step_order")


# ===========================================================================
# 8. PROS / CONS  (§14)
# ===========================================================================
async def add_procon(
    session: AsyncSession, career: MnpCareer, *, actor_admin_id: int | None, type: str, text_uk: str,
    source_type: str | None = None, source_reference: str | None = None, review_status: str | None = None,
) -> MnpCareerProCon:
    if not text_uk.strip():
        raise CareerKbValidationError("text_uk is required")
    pc_type = ProConType(type)
    st, ref = _clean_source(source_type, source_reference)
    orders = (await session.execute(select(MnpCareerProCon.sort_order).where(
        MnpCareerProCon.career_id == career.id, MnpCareerProCon.type == pc_type))).scalars().all()
    row = MnpCareerProCon(
        career_id=career.id, type=pc_type, text_uk=text_uk.strip(),
        sort_order=(max(orders) + 1 if orders else 1),
        source=st, source_version=ref, confidence=0.6, review_status=_check_review(review_status),
    )
    session.add(row)
    _bump(career)
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, entity_type="mnp_career_procon", entity_id=row.id,
                 action="created", career=career, after={"type": _v(pc_type), "text_uk": row.text_uk})
    return row


async def update_procon(
    session: AsyncSession, career: MnpCareer, pc_id: uuid.UUID, *, actor_admin_id: int | None,
    text_uk: str = _UNSET, type: str = _UNSET, source_type: str | None = _UNSET,
    source_reference: str | None = _UNSET, review_status: str | None = _UNSET,
) -> MnpCareerProCon:
    row = await _child_or_404(session, MnpCareerProCon, pc_id, career.id)
    before = {"type": _v(row.type), "text_uk": row.text_uk, "source_type": row.source,
              "source_reference": row.source_version, "review_status": row.review_status}
    if text_uk is not _UNSET:
        if not str(text_uk).strip():
            raise CareerKbValidationError("text_uk cannot be empty")
        row.text_uk = str(text_uk).strip()
    if type is not _UNSET and ProConType(type) != row.type:
        new_type = ProConType(type)
        orders = (await session.execute(select(MnpCareerProCon.sort_order).where(
            MnpCareerProCon.career_id == career.id, MnpCareerProCon.type == new_type))).scalars().all()
        row.type = new_type
        row.sort_order = (max(orders) + 1 if orders else 1)
    if source_type is not _UNSET or source_reference is not _UNSET:
        st, ref = _clean_source(row.source if source_type is _UNSET else source_type,
                                row.source_version if source_reference is _UNSET else source_reference)
        row.source, row.source_version = st, ref
    if review_status is not _UNSET:
        row.review_status = _check_review(review_status)
    _bump(career)
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, entity_type="mnp_career_procon", entity_id=row.id,
                 action="updated", career=career, before=before,
                 after={"type": _v(row.type), "text_uk": row.text_uk, "review_status": row.review_status})
    return row


async def delete_procon(
    session: AsyncSession, career: MnpCareer, pc_id: uuid.UUID, *, actor_admin_id: int | None,
) -> None:
    row = await _child_or_404(session, MnpCareerProCon, pc_id, career.id)
    before = {"type": _v(row.type), "text_uk": row.text_uk}
    await session.delete(row)
    _bump(career)
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, entity_type="mnp_career_procon", entity_id=pc_id,
                 action="deleted", career=career, before=before)


async def reorder_procon(
    session: AsyncSession, career: MnpCareer, pc_id: uuid.UUID, *, actor_admin_id: int | None, direction: str,
) -> list[MnpCareerProCon]:
    if direction not in ("up", "down"):
        raise CareerKbValidationError("direction must be 'up' or 'down'")
    row = await _child_or_404(session, MnpCareerProCon, pc_id, career.id)
    siblings = (await session.execute(select(MnpCareerProCon).where(
        MnpCareerProCon.career_id == career.id, MnpCareerProCon.type == row.type
    ).order_by(MnpCareerProCon.sort_order))).scalars().all()
    idx = next(i for i, r in enumerate(siblings) if r.id == pc_id)
    swap = idx - 1 if direction == "up" else idx + 1
    if 0 <= swap < len(siblings):
        a, b = siblings[idx], siblings[swap]
        a.sort_order, b.sort_order = b.sort_order, a.sort_order
        _bump(career)
        await session.flush()
        await _audit(session, actor_admin_id=actor_admin_id, entity_type="mnp_career_procon", entity_id=pc_id,
                     action="reordered", career=career, after={"direction": direction})
    return (await session.execute(select(MnpCareerProCon).where(
        MnpCareerProCon.career_id == career.id, MnpCareerProCon.type == row.type
    ).order_by(MnpCareerProCon.sort_order))).scalars().all()


# ===========================================================================
# 9. RELATED CAREERS  (§15)
# ===========================================================================
async def add_relation(
    session: AsyncSession, career: MnpCareer, *, actor_admin_id: int | None, to_career_id: uuid.UUID,
    relation_type: str, strength: float | None = None, source_type: str | None = None,
    source_reference: str | None = None, review_status: str | None = None,
) -> MnpCareerRelation:
    to_career_id = uuid.UUID(str(to_career_id))
    if to_career_id == career.id:
        raise CareerKbValidationError("професія не може бути пов'язана сама з собою")
    target = await session.get(MnpCareer, to_career_id)
    if target is None:
        raise CareerKbValidationError("цільова професія не існує")
    rtype = CareerRelationType(relation_type)
    if (await session.execute(select(MnpCareerRelation).where(
            MnpCareerRelation.from_career_id == career.id,
            MnpCareerRelation.to_career_id == to_career_id,
            MnpCareerRelation.relation_type == rtype))).scalar_one_or_none() is not None:
        raise CareerKbValidationError("такий зв'язок уже існує")
    st, ref = _clean_source(source_type, source_reference)
    row = MnpCareerRelation(
        from_career_id=career.id, to_career_id=to_career_id, relation_type=rtype,
        strength=strength, source=st, source_version=ref, review_status=_check_review(review_status),
    )
    session.add(row)
    _bump(career)
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, entity_type="mnp_career_relation", entity_id=row.id,
                 action="created", career=career,
                 after={"to_career_code": target.code, "relation_type": relation_type})
    return row


async def update_relation(
    session: AsyncSession, career: MnpCareer, rel_id: uuid.UUID, *, actor_admin_id: int | None,
    relation_type: str = _UNSET, strength: float | None = _UNSET, source_type: str | None = _UNSET,
    source_reference: str | None = _UNSET, review_status: str | None = _UNSET,
) -> MnpCareerRelation:
    row = await session.get(MnpCareerRelation, rel_id)
    if row is None or row.from_career_id != career.id:
        raise MnpCareerNotFoundError("relation not found for this career")
    before = {"relation_type": _v(row.relation_type), "strength": row.strength,
              "source_type": row.source, "review_status": row.review_status}
    if relation_type is not _UNSET:
        row.relation_type = CareerRelationType(relation_type)
    if strength is not _UNSET:
        row.strength = strength
    if source_type is not _UNSET or source_reference is not _UNSET:
        st, ref = _clean_source(row.source if source_type is _UNSET else source_type,
                                row.source_version if source_reference is _UNSET else source_reference)
        row.source, row.source_version = st, ref
    if review_status is not _UNSET:
        row.review_status = _check_review(review_status)
    _bump(career)
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, entity_type="mnp_career_relation", entity_id=row.id,
                 action="updated", career=career, before=before,
                 after={"relation_type": _v(row.relation_type), "review_status": row.review_status})
    return row


async def delete_relation(
    session: AsyncSession, career: MnpCareer, rel_id: uuid.UUID, *, actor_admin_id: int | None,
) -> None:
    row = await session.get(MnpCareerRelation, rel_id)
    if row is None or row.from_career_id != career.id:
        raise MnpCareerNotFoundError("relation not found for this career")
    await session.delete(row)
    _bump(career)
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, entity_type="mnp_career_relation", entity_id=rel_id,
                 action="deleted", career=career)


# ===========================================================================
# 10. EXTERNAL REFERENCES  (§16)
# ===========================================================================
async def add_external_ref(
    session: AsyncSession, career: MnpCareer, *, actor_admin_id: int | None, external_system: str,
    external_id: str, external_label: str | None = None, mapping_type: str = "close",
    confidence: float | None = None, source_reference: str | None = None,
    review_status: str | None = None, note: str | None = None,
) -> MnpExternalMapping:
    system = ExternalSourceSystem(external_system)
    if not external_id.strip():
        raise CareerKbValidationError("external_id is required")
    if (await session.execute(select(MnpExternalMapping).where(
            MnpExternalMapping.entity_type == "career", MnpExternalMapping.mnp_entity_id == career.id,
            MnpExternalMapping.source_system == system,
            MnpExternalMapping.external_id == external_id.strip()))).scalar_one_or_none() is not None:
        raise CareerKbValidationError("такий зовнішній ідентифікатор уже додано")
    row = MnpExternalMapping(
        entity_type="career", mnp_entity_id=career.id, source_system=system,
        external_id=external_id.strip(), external_label=(external_label or None),
        mapping_type=ExternalMappingType(mapping_type), confidence=confidence,
        source_version=(source_reference or None),
        review_status=_check_review_ext(review_status), note=(note or None),
    )
    session.add(row)
    _bump(career)
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, entity_type="mnp_external_mapping", entity_id=row.id,
                 action="created", career=career,
                 after={"external_system": external_system, "external_id": row.external_id})
    return row


_EXT_REVIEW_STATES = ["candidate", "confirmed", "rejected", "needs_review"]


def _check_review_ext(rs: str | None) -> str:
    rs = (rs or "candidate").strip().lower()
    if rs not in _EXT_REVIEW_STATES:
        raise CareerKbValidationError(f"unknown review_status {rs!r}")
    return rs


async def update_external_ref(
    session: AsyncSession, career: MnpCareer, ext_id: uuid.UUID, *, actor_admin_id: int | None,
    external_label: str | None = _UNSET, mapping_type: str = _UNSET, confidence: float | None = _UNSET,
    source_reference: str | None = _UNSET, review_status: str | None = _UNSET, note: str | None = _UNSET,
) -> MnpExternalMapping:
    row = await session.get(MnpExternalMapping, ext_id)
    if row is None or row.mnp_entity_id != career.id or row.entity_type != "career":
        raise MnpCareerNotFoundError("external reference not found for this career")
    before = {"external_label": row.external_label, "mapping_type": _v(row.mapping_type),
              "confidence": row.confidence, "source_reference": row.source_version,
              "review_status": row.review_status, "note": row.note}
    if external_label is not _UNSET:
        row.external_label = (external_label or None)
    if mapping_type is not _UNSET:
        row.mapping_type = ExternalMappingType(mapping_type)
    if confidence is not _UNSET:
        row.confidence = confidence
    if source_reference is not _UNSET:
        row.source_version = (source_reference or None)
    if review_status is not _UNSET:
        row.review_status = _check_review_ext(review_status)
    if note is not _UNSET:
        row.note = (note or None)
    _bump(career)
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, entity_type="mnp_external_mapping", entity_id=row.id,
                 action="updated", career=career, before=before,
                 after={"mapping_type": _v(row.mapping_type), "review_status": row.review_status})
    return row


async def delete_external_ref(
    session: AsyncSession, career: MnpCareer, ext_id: uuid.UUID, *, actor_admin_id: int | None,
) -> None:
    row = await session.get(MnpExternalMapping, ext_id)
    if row is None or row.mnp_entity_id != career.id or row.entity_type != "career":
        raise MnpCareerNotFoundError("external reference not found for this career")
    await session.delete(row)
    _bump(career)
    await session.flush()
    await _audit(session, actor_admin_id=actor_admin_id, entity_type="mnp_external_mapping", entity_id=ext_id,
                 action="deleted", career=career)


# ===========================================================================
# EDITOR VIEW  -- raw editable values + child-row ids (admin only)
# ===========================================================================
async def get_career_editor_view(session: AsyncSession, career: MnpCareer) -> dict:
    await session.refresh(career, ["career_family"])

    tasks = (await session.execute(select(MnpCareerTask).where(MnpCareerTask.career_id == career.id)
             .order_by(MnpCareerTask.sort_order, MnpCareerTask.task_code))).scalars().all()
    skills = (await session.execute(select(MnpCareerSkillRequirement, MnpSkill)
              .join(MnpSkill, MnpSkill.id == MnpCareerSkillRequirement.skill_id)
              .where(MnpCareerSkillRequirement.career_id == career.id))).all()
    knows = (await session.execute(select(MnpCareerKnowledgeRequirement, MnpKnowledge)
             .join(MnpKnowledge, MnpKnowledge.id == MnpCareerKnowledgeRequirement.knowledge_id)
             .where(MnpCareerKnowledgeRequirement.career_id == career.id))).all()
    reqs = (await session.execute(select(MnpCareerRequirement).where(MnpCareerRequirement.career_id == career.id)
            .order_by(MnpCareerRequirement.sort_order))).scalars().all()
    steps = (await session.execute(select(MnpCareerPathStep).where(MnpCareerPathStep.career_id == career.id)
             .order_by(MnpCareerPathStep.step_order))).scalars().all()
    procons = (await session.execute(select(MnpCareerProCon).where(MnpCareerProCon.career_id == career.id)
               .order_by(MnpCareerProCon.type, MnpCareerProCon.sort_order))).scalars().all()
    rels = (await session.execute(select(MnpCareerRelation).where(MnpCareerRelation.from_career_id == career.id)
            .options())).scalars().all()
    exts = (await session.execute(select(MnpExternalMapping).where(
        MnpExternalMapping.entity_type == "career", MnpExternalMapping.mnp_entity_id == career.id))).scalars().all()

    rel_targets = {}
    for rel in rels:
        t = await session.get(MnpCareer, rel.to_career_id)
        rel_targets[rel.id] = (t.code if t else None, t.canonical_name_uk if t else None)

    return {
        "id": str(career.id),
        "core": {
            "career_code": career.code,
            "name_uk": career.canonical_name_uk,
            "name_en": career.canonical_name_en,
            "category_uk": career.career_family.name_uk if career.career_family else None,
            "short_description_uk": career.description_short_uk,
            "long_description_uk": career.description_long_uk,
            "difficulty_level": _v(career.difficulty_level),
            "entry_without_experience": _v(career.entry_without_experience),
            "typical_entry_route_uk": career.typical_entry_route_uk,
            "status": career.status.value,
            "profile_version": career.career_profile_version,
        },
        "responsibilities": [{
            "id": str(t.id), "title_uk": t.title_uk, "description_uk": t.description,
            "importance": _v(t.importance), "frequency": t.frequency, "sort_order": t.sort_order,
            "source_type": t.source, "source_reference": t.source_version, "review_status": t.review_status,
        } for t in tasks],
        "skills": [{
            "id": str(sr.id), "skill_id": str(sk.id), "name_uk": sk.canonical_name_uk,
            "name_en": sk.canonical_name_en, "skill_type": _v(sk.skill_type),
            "is_soft": _v(sk.skill_type) in ("communication", "management"),
            "importance": _v(sr.importance), "required_level": sr.required_level,
            "requirement_type": _v(sr.requirement_type), "source_type": sr.source,
            "source_reference": sr.source_version, "review_status": sr.review_status,
        } for sr, sk in skills],
        "knowledge": [{
            "id": str(kr.id), "knowledge_id": str(kn.id), "name_uk": kn.canonical_name_uk,
            "name_en": kn.canonical_name_en, "importance": _v(kr.importance),
            "required_level": kr.required_level, "requirement_type": _v(kr.requirement_type),
            "source_type": kr.source, "source_reference": kr.source_version, "review_status": kr.review_status,
        } for kr, kn in knows],
        "requirements": [{
            "id": str(r.id), "category": _v(r.category), "description_uk": r.description, "value": r.value,
            "hardness": _v(r.hardness), "country": r.country, "sort_order": r.sort_order,
            "source_type": r.source, "source_reference": r.source_version, "review_status": r.review_status,
        } for r in reqs],
        "career_path": [{
            "id": str(s.id), "path_code": s.path_code, "step_order": s.step_order,
            "step_name_uk": s.step_name_uk, "step_type": _v(s.step_type), "description_uk": s.description_uk,
            "typical_experience_text_uk": s.typical_experience_text_uk,
            "is_current_career_step": s.is_current_career_step,
            "source_type": s.source, "source_reference": s.source_version, "review_status": s.review_status,
        } for s in steps],
        "pros_cons": [{
            "id": str(p.id), "type": _v(p.type), "text_uk": p.text_uk, "sort_order": p.sort_order,
            "source_type": p.source, "source_reference": p.source_version, "review_status": p.review_status,
        } for p in procons],
        "related_careers": [{
            "id": str(rel.id), "to_career_id": str(rel.to_career_id),
            "to_career_code": rel_targets[rel.id][0], "to_career_name_uk": rel_targets[rel.id][1],
            "relation_type": _v(rel.relation_type), "strength": rel.strength,
            "source_type": rel.source, "source_reference": rel.source_version, "review_status": rel.review_status,
        } for rel in rels],
        "external_references": [{
            "id": str(e.id), "external_system": _v(e.source_system), "external_id": e.external_id,
            "external_label": e.external_label, "mapping_type": _v(e.mapping_type),
            "confidence": e.confidence, "source_reference": e.source_version,
            "review_status": e.review_status, "note": e.note,
        } for e in exts],
        "market": {"editable": False, "status_uk": "Ринкові дані ще не підключені",
                   "data_quality": "MARKET_DATA_LIMITED"},
        "vocab": {
            "source_types": SOURCE_TYPES, "review_states": REVIEW_STATES,
            "ext_review_states": _EXT_REVIEW_STATES,
            "importance": [e.value for e in ImportanceLevel],
            "requirement_type": [e.value for e in RequirementType],
            "proficiency": ["basic", "working", "strong"],
            "difficulty": [e.value for e in CareerDifficulty],
            "entry_without_experience": [e.value for e in EntryWithoutExperience],
            "requirement_category": [e.value for e in RequirementCategory],
            "hardness": ["soft", "hard"],
            "path_step_type": [e.value for e in CareerPathStepType],
            "procon_type": [e.value for e in ProConType],
            "relation_type": [e.value for e in CareerRelationType],
            "external_system": [e.value for e in ExternalSourceSystem],
            "mapping_type": [e.value for e in ExternalMappingType],
            "skill_type": [e.value for e in SkillType],
        },
    }


# ===========================================================================
# 11. HISTORY  (§18)
# ===========================================================================
_CAREER_AUDIT_TYPES = (
    "mnp_career", "mnp_career_task", "mnp_career_skill_requirement", "mnp_career_knowledge_requirement",
    "mnp_career_requirement", "mnp_career_path_step", "mnp_career_procon", "mnp_career_relation",
    "mnp_external_mapping",
)


async def get_career_history(session: AsyncSession, career: MnpCareer, *, limit: int = 200) -> list[dict]:
    rows = (await session.execute(
        select(AuditLog).where(AuditLog.entity_type.in_(_CAREER_AUDIT_TYPES))
        .order_by(AuditLog.occurred_at.desc()).limit(1000)
    )).scalars().all()
    out: list[dict] = []
    for r in rows:
        after = r.after_snapshot or {}
        if str(after.get("career_id")) != str(career.id) and r.entity_id != str(career.id):
            continue
        out.append({
            "entity_type": r.entity_type,
            "action": r.action,
            "changed_by_admin_id": r.actor_admin_id,
            "changed_at": r.occurred_at.isoformat() if r.occurred_at else None,
            "old_value": r.before_snapshot,
            "new_value": {k: v for k, v in after.items() if k not in ("career_id", "career_code")},
        })
        if len(out) >= limit:
            break
    return out
