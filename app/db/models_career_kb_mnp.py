"""MNP V1 -- Career Knowledge Base: `MnpCareer` and everything describing
what a career requires/offers (`MNP_DATA_MODEL_V1.md` §12-16,
`MNP_CAREER_PROFILE_SCHEMA_V1.md`). A separate managed module, editable/
versioned per career, independent of the Matching Engine
(`MNP_CAREER_KB_ARCHITECTURE_V1.md`).

Deliberately NOT built on Stage 3A's `careers`/`career_skills`/etc.
(`app/db/models_knowledge.py`): that module versions the ENTIRE catalog as
one atomic snapshot (`KnowledgeBaseVersion`, one `is_current` row for all
careers at once) and has no dedicated Skill entity (skills are generic
`TaxonomyTerm` rows shared across unrelated profile dimensions). MNP wants
per-career DRAFT -> ACTIVE -> ARCHIVED (+ restore) lifecycle
(MNP_CAREER_KB_ARCHITECTURE_V1 "Lifecycle") and a dedicated Skill taxonomy
with 3-level proficiency (MNP_SKILL_SCHEMA_V1). Stage 3A's tables are left
exactly as they are for whatever still depends on them; this module is
additive, `mnp_`-prefixed, zero collision.

`MnpSkill`/`MnpSkillAlias`/etc. live in `models_career_card.py` (created
first, since Skill requirements here reference it)."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models_career_card import _str_enum


class CareerLifecycleStatus(str, enum.Enum):
    """MNP_CAREER_PROFILE_SCHEMA_V1 §3 / MNP_CAREER_KB_ARCHITECTURE_V1
    "Lifecycle": DRAFT -> VALIDATED -> ACTIVE -> REVIEW_DUE ->
    ACTIVE/ARCHIVED. `RESTORED` is not a separate state -- restoring an
    ARCHIVED career just sets status back to ACTIVE (audit log records the
    action, see `MnpAuditLog` usage in the service layer)."""

    DRAFT = "draft"
    VALIDATED = "validated"
    ACTIVE = "active"
    REVIEW_DUE = "review_due"
    ARCHIVED = "archived"


class RequirementType(str, enum.Enum):
    """MNP_SKILL_SCHEMA_V1 §11 / §13 Requirement types."""

    MUST_HAVE = "must_have"
    HIGH_VALUE = "high_value"
    DIFFERENTIATOR = "differentiator"
    OPTIONAL = "optional"


class ImportanceLevel(str, enum.Enum):
    """MNP_SKILL_SCHEMA_V1 §12."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RequirementCategory(str, enum.Enum):
    """MNP_DATA_MODEL_V1 §14 CareerRequirement.category."""

    EDUCATION = "education"
    EXPERIENCE = "experience"
    CREDENTIAL = "credential"
    LANGUAGE = "language"
    LEGAL = "legal"
    OTHER = "other"


class RequirementHardness(str, enum.Enum):
    SOFT = "soft"
    HARD = "hard"


class CareerAliasType(str, enum.Enum):
    MARKET_TITLE = "market_title"
    ABBREVIATION = "abbreviation"
    TRANSLITERATION = "transliteration"
    MISSPELLING = "misspelling"
    TRANSLATION = "translation"


class CareerRelationType(str, enum.Enum):
    """MNP_CAREER_PROFILE_SCHEMA_V1 §22."""

    PROGRESSION = "progression"
    ADJACENT = "adjacent"
    RELATED = "related"
    SAME_FAMILY = "same_family"
    COMMON_TRANSITION = "common_transition"


class ExternalSourceSystem(str, enum.Enum):
    """MNP_DATA_MODEL_V1 §15 -- Lightcast deliberately absent (Founder
    Decision #18)."""

    ESCO = "esco"
    ONET = "onet"
    ISCO = "isco"
    UA_CLASSIFIER = "ua_classifier"


class ExternalMappingType(str, enum.Enum):
    EXACT = "exact"
    CLOSE = "close"
    BROAD = "broad"
    NARROW = "narrow"


class CareerDifficulty(str, enum.Enum):
    """MNP_CAREER_PROFILE_SCHEMA_V1 "Entry" / moat doc §5 "Entry: transition
    difficulty". User-facing Ukrainian labels are resolved in the API, not
    stored here (internal schema = English-first, Founder Language Policy)."""

    EASY = "easy"
    MODERATE = "moderate"
    CHALLENGING = "challenging"
    HARD = "hard"


class EntryWithoutExperience(str, enum.Enum):
    """Can someone enter this career with no prior professional experience?
    `UNKNOWN` is first-class (Founder Decision #27) -- never silently 'no'."""

    YES = "yes"
    LIMITED = "limited"        # possible for a subset of roles / with training
    NO = "no"
    UNKNOWN = "unknown"


class ProConType(str, enum.Enum):
    ADVANTAGE = "advantage"
    DISADVANTAGE = "disadvantage"


class CareerPathStepType(str, enum.Enum):
    """A typical progression rung. Not a guaranteed route
    (MNP_CAREER_PROFILE_SCHEMA_V1 / Founder Decision §6)."""

    ENTRY = "entry"
    JUNIOR = "junior"
    CORE = "core"
    SENIOR = "senior"
    LEAD = "lead"
    EXECUTIVE = "executive"


class MnpCareerFamily(Base):
    """MNP_CAREER_PROFILE_SCHEMA_V1 §5."""

    __tablename__ = "mnp_career_families"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name_uk: Mapped[str] = mapped_column(String(255))
    name_en: Mapped[str] = mapped_column(String(255))

    careers: Mapped[list["MnpCareer"]] = relationship(back_populates="career_family")


class MnpCareer(Base):
    """MNP_CAREER_PROFILE_SCHEMA_V1 §3. `code` is the stable MNP_CAREER_ID
    business key (never an ESCO/O*NET id -- Founder Decision #16); `id` is
    the storage PK. `career_profile_version` increments on every
    substantive edit to THIS career alone (per-career versioning, unlike
    Stage 3A's whole-catalog snapshot) -- `MnpMatchRun` pins the exact
    version it used, so archiving/editing a career never breaks historical
    reproducibility (MNP_CAREER_PROFILE_SCHEMA_V1 §29/§30)."""

    __tablename__ = "mnp_careers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    canonical_name_uk: Mapped[str] = mapped_column(String(255))
    canonical_name_en: Mapped[str] = mapped_column(String(255))
    description_short_uk: Mapped[str] = mapped_column(Text)
    description_long_uk: Mapped[str | None] = mapped_column(Text)
    career_family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_career_families.id"), index=True)
    status: Mapped[CareerLifecycleStatus] = mapped_column(
        _str_enum(CareerLifecycleStatus), default=CareerLifecycleStatus.DRAFT, index=True
    )
    catalog_priority: Mapped[int] = mapped_column(Integer, default=0)
    career_profile_version: Mapped[int] = mapped_column(Integer, default=1)
    market_data_limited: Mapped[bool] = mapped_column(Boolean, default=True)
    # Entry characteristics (moat doc §5 "Entry"). All nullable / UNKNOWN
    # by default -- an unpopulated career must not imply "easy" or "no".
    difficulty_level: Mapped[CareerDifficulty | None] = mapped_column(_str_enum(CareerDifficulty))
    entry_without_experience: Mapped[EntryWithoutExperience] = mapped_column(
        _str_enum(EntryWithoutExperience), default=EntryWithoutExperience.UNKNOWN
    )
    typical_entry_route_uk: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    career_family: Mapped["MnpCareerFamily"] = relationship(back_populates="careers")
    aliases: Mapped[list["MnpCareerAlias"]] = relationship(back_populates="career", cascade="all, delete-orphan")
    tasks: Mapped[list["MnpCareerTask"]] = relationship(back_populates="career", cascade="all, delete-orphan")
    skill_requirements: Mapped[list["MnpCareerSkillRequirement"]] = relationship(back_populates="career", cascade="all, delete-orphan")
    knowledge_requirements: Mapped[list["MnpCareerKnowledgeRequirement"]] = relationship(back_populates="career", cascade="all, delete-orphan")
    requirements: Mapped[list["MnpCareerRequirement"]] = relationship(back_populates="career", cascade="all, delete-orphan")
    attributes: Mapped[list["MnpCareerAttribute"]] = relationship(back_populates="career", cascade="all, delete-orphan")
    # `MnpExternalMapping.mnp_entity_id` is a polymorphic pointer (career
    # or skill), not a real FK -- no `cascade`/`back_populates` here since
    # the two sides can't be kept in ORM-level sync automatically; this is
    # a read-only reverse view, matching `MnpExternalMapping.career` below.
    external_mappings: Mapped[list["MnpExternalMapping"]] = relationship(
        "MnpExternalMapping",
        primaryjoin="foreign(MnpExternalMapping.mnp_entity_id) == MnpCareer.id",
        viewonly=True,
    )
    relations_from: Mapped[list["MnpCareerRelation"]] = relationship(
        back_populates="from_career", foreign_keys="MnpCareerRelation.from_career_id", cascade="all, delete-orphan"
    )
    pros_cons: Mapped[list["MnpCareerProCon"]] = relationship(back_populates="career", cascade="all, delete-orphan")
    path_steps: Mapped[list["MnpCareerPathStep"]] = relationship(back_populates="career", cascade="all, delete-orphan")


class MnpCareerAlias(Base):
    """MNP_CAREER_PROFILE_SCHEMA_V1 §4. Never auto-creates a new Career
    (Founder Decision #21)."""

    __tablename__ = "mnp_career_aliases"
    __table_args__ = (UniqueConstraint("career_id", "language", "alias", name="uq_career_alias"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_careers.id"), index=True)
    alias: Mapped[str] = mapped_column(String(255), index=True)
    language: Mapped[str] = mapped_column(String(8), default="uk")
    source: Mapped[str | None] = mapped_column(String(64))
    alias_type: Mapped[CareerAliasType] = mapped_column(_str_enum(CareerAliasType))
    confidence: Mapped[float | None] = mapped_column(Float)
    status: Mapped[CareerLifecycleStatus] = mapped_column(_str_enum(CareerLifecycleStatus), default=CareerLifecycleStatus.ACTIVE)

    career: Mapped["MnpCareer"] = relationship(back_populates="aliases")


class MnpCareerTask(Base):
    """MNP_CAREER_PROFILE_SCHEMA_V1 §7."""

    __tablename__ = "mnp_career_tasks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_careers.id"), index=True)
    task_code: Mapped[str] = mapped_column(String(64))
    title_uk: Mapped[str] = mapped_column(String(500))
    title_en: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    importance: Mapped[ImportanceLevel] = mapped_column(_str_enum(ImportanceLevel))
    frequency: Mapped[str | None] = mapped_column(String(32))
    source: Mapped[str | None] = mapped_column(String(64))
    source_version: Mapped[str | None] = mapped_column(String(32))
    confidence: Mapped[float | None] = mapped_column(Float)

    career: Mapped["MnpCareer"] = relationship(back_populates="tasks")


class MnpCareerSkillRequirement(Base):
    """MNP_CAREER_PROFILE_SCHEMA_V1 §8 / MNP_SKILL_SCHEMA_V1 §11 -- the
    central input to Skill Fit."""

    __tablename__ = "mnp_career_skill_requirements"
    __table_args__ = (UniqueConstraint("career_id", "skill_id", name="uq_career_skill_requirement"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_careers.id"), index=True)
    skill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_skills.id"), index=True)
    importance: Mapped[ImportanceLevel] = mapped_column(_str_enum(ImportanceLevel))
    required_level: Mapped[str] = mapped_column(String(16))  # MnpSkill ProficiencyLevel value
    requirement_type: Mapped[RequirementType] = mapped_column(_str_enum(RequirementType))
    source: Mapped[str | None] = mapped_column(String(64))
    source_version: Mapped[str | None] = mapped_column(String(32))
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)

    career: Mapped["MnpCareer"] = relationship(back_populates="skill_requirements")
    skill: Mapped["object"] = relationship("MnpSkill")


class MnpCareerKnowledgeRequirement(Base):
    """MNP_CAREER_PROFILE_SCHEMA_V1 §9."""

    __tablename__ = "mnp_career_knowledge_requirements"
    __table_args__ = (UniqueConstraint("career_id", "knowledge_id", name="uq_career_knowledge_requirement"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_careers.id"), index=True)
    knowledge_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_knowledge.id"), index=True)
    importance: Mapped[ImportanceLevel] = mapped_column(_str_enum(ImportanceLevel))
    required_level: Mapped[str] = mapped_column(String(16))
    requirement_type: Mapped[RequirementType] = mapped_column(_str_enum(RequirementType))
    source: Mapped[str | None] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(Float, default=0.5)

    career: Mapped["MnpCareer"] = relationship(back_populates="knowledge_requirements")


class MnpCareerRequirement(Base):
    """MNP_CAREER_PROFILE_SCHEMA_V1 §15-18: education/experience/
    credential/language/legal requirements. `hardness=HARD` +
    high-confidence source is the only thing allowed to produce a
    Feasibility `BLOCKED` (MNP_EVIDENCE_AND_CONFIDENCE_MODEL_V1 §20)."""

    __tablename__ = "mnp_career_requirements"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_careers.id"), index=True)
    category: Mapped[RequirementCategory] = mapped_column(_str_enum(RequirementCategory), index=True)
    description: Mapped[str] = mapped_column(String(500))
    value: Mapped[str | None] = mapped_column(String(255))  # e.g. min level/years/language code
    hardness: Mapped[RequirementHardness] = mapped_column(_str_enum(RequirementHardness))
    country: Mapped[str | None] = mapped_column(String(64))
    source: Mapped[str | None] = mapped_column(String(64))
    source_version: Mapped[str | None] = mapped_column(String(32))
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)

    career: Mapped["MnpCareer"] = relationship(back_populates="requirements")


class MnpCareerAttribute(Base):
    """MNP_CAREER_PROFILE_SCHEMA_V1 §10-13: Work Context / Work Styles /
    Abilities / Interests as flat key-value attributes, all `secondary
    signal` per Founder Decisions #22/#23 -- never a hard gate, never
    promoted into Skill Fit. `attribute_group` distinguishes
    "work_context" / "work_style" / "ability" / "interest" so
    Preference/Values Fit can select just the group it needs."""

    __tablename__ = "mnp_career_attributes"
    __table_args__ = (UniqueConstraint("career_id", "attribute_group", "attribute_key", name="uq_career_attribute"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_careers.id"), index=True)
    attribute_group: Mapped[str] = mapped_column(String(32), index=True)
    attribute_key: Mapped[str] = mapped_column(String(64))
    value_numeric: Mapped[float | None] = mapped_column(Float)  # 0..1 normalized, where applicable
    value_text: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str | None] = mapped_column(String(64))
    confidence: Mapped[float | None] = mapped_column(Float)

    career: Mapped["MnpCareer"] = relationship(back_populates="attributes")


class MnpCareerRelation(Base):
    """MNP_CAREER_PROFILE_SCHEMA_V1 §22 -- career-to-career prior, not a
    personal recommendation."""

    __tablename__ = "mnp_career_relations"
    __table_args__ = (UniqueConstraint("from_career_id", "to_career_id", "relation_type", name="uq_career_relation"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_career_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_careers.id"), index=True)
    to_career_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_careers.id"), index=True)
    relation_type: Mapped[CareerRelationType] = mapped_column(_str_enum(CareerRelationType))
    strength: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str | None] = mapped_column(String(64))

    from_career: Mapped["MnpCareer"] = relationship(back_populates="relations_from", foreign_keys=[from_career_id])
    to_career: Mapped["MnpCareer"] = relationship(foreign_keys=[to_career_id])


class MnpExternalMapping(Base):
    """MNP_DATA_MODEL_V1 §15. External ids are references, never MNP
    identity (Founder Decision #16). Lightcast is not a valid
    `source_system` value in V1 -- deliberately excluded from
    `ExternalSourceSystem` above, not merely unused."""

    __tablename__ = "mnp_external_mappings"
    __table_args__ = (
        UniqueConstraint("entity_type", "mnp_entity_id", "source_system", "external_id", name="uq_external_mapping"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(32))  # "career" | "skill"
    mnp_entity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), index=True)
    source_system: Mapped[ExternalSourceSystem] = mapped_column(_str_enum(ExternalSourceSystem))
    external_id: Mapped[str] = mapped_column(String(128))
    external_label: Mapped[str | None] = mapped_column(String(255))
    mapping_type: Mapped[ExternalMappingType] = mapped_column(_str_enum(ExternalMappingType))
    confidence: Mapped[float | None] = mapped_column(Float)
    source_version: Mapped[str | None] = mapped_column(String(32))

    career: Mapped["MnpCareer | None"] = relationship(
        "MnpCareer",
        primaryjoin="foreign(MnpExternalMapping.mnp_entity_id) == MnpCareer.id",
        viewonly=True,
        uselist=False,
    )


# ---------------------------------------------------------------------------
# Market layer (MNP_UA_MARKET_DATA_MODEL_V1) -- snapshots, never a
# permanent Career field.

class MnpMarketSnapshot(Base):
    __tablename__ = "mnp_market_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_careers.id"), index=True)
    country: Mapped[str] = mapped_column(String(8), default="UA")
    region: Mapped[str | None] = mapped_column(String(128))
    snapshot_date: Mapped[date] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(128))
    source_version: Mapped[str | None] = mapped_column(String(32))
    data_quality: Mapped[str] = mapped_column(String(32), default="MARKET_DATA_LIMITED")
    sample_size: Mapped[int | None] = mapped_column(Integer)
    vacancy_count: Mapped[int | None] = mapped_column(Integer)
    demand_trend: Mapped[str | None] = mapped_column(String(16))  # "up" | "flat" | "down"
    remote_share: Mapped[float | None] = mapped_column(Float)
    entry_level_availability: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    salary_snapshots: Mapped[list["MnpSalarySnapshot"]] = relationship(back_populates="market_snapshot", cascade="all, delete-orphan")


class MnpSalarySnapshot(Base):
    __tablename__ = "mnp_salary_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    market_snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_market_snapshots.id"), index=True)
    currency: Mapped[str] = mapped_column(String(8), default="UAH")
    period: Mapped[str] = mapped_column(String(16), default="month")
    percentile_25: Mapped[float | None] = mapped_column(Float)
    median: Mapped[float | None] = mapped_column(Float)
    percentile_75: Mapped[float | None] = mapped_column(Float)

    market_snapshot: Mapped["MnpMarketSnapshot"] = relationship(back_populates="salary_snapshots")


class MnpCareerProCon(Base):
    """MNP editorial advantages / disadvantages of a career (Founder
    Decision §5). This is an EDITORIAL layer -- never presented as
    objective statistics. Ukrainian-first (`text_uk` required, `text_en`
    optional reference)."""

    __tablename__ = "mnp_career_pros_cons"
    __table_args__ = (UniqueConstraint("career_id", "type", "sort_order", name="uq_career_procon_order"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_careers.id"), index=True)
    type: Mapped[ProConType] = mapped_column(_str_enum(ProConType), index=True)
    text_uk: Mapped[str] = mapped_column(Text)
    text_en: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(64), default="mnp_editorial_v1")
    source_version: Mapped[str | None] = mapped_column(String(32))
    confidence: Mapped[float | None] = mapped_column(Float)
    review_status: Mapped[str] = mapped_column(String(24), default="editorial")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    career: Mapped["MnpCareer"] = relationship(back_populates="pros_cons")


class MnpCareerPathStep(Base):
    """One rung of a typical career path (Founder Decision §6).
    `MnpCareerRelation` (career<->career prior) is a DIFFERENT thing --
    this is an ordered, informational, editorial progression. A path step
    NEVER auto-creates a separate MnpCareer. Ukrainian-first."""

    __tablename__ = "mnp_career_path_steps"
    __table_args__ = (
        UniqueConstraint("career_id", "path_code", "step_order", name="uq_career_path_step_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_careers.id"), index=True)
    path_code: Mapped[str] = mapped_column(String(64), default="typical")
    step_order: Mapped[int] = mapped_column(Integer)
    step_name_uk: Mapped[str] = mapped_column(String(255))
    step_name_en: Mapped[str | None] = mapped_column(String(255))
    step_type: Mapped[CareerPathStepType] = mapped_column(_str_enum(CareerPathStepType))
    description_uk: Mapped[str | None] = mapped_column(Text)
    description_en: Mapped[str | None] = mapped_column(Text)
    typical_experience_text_uk: Mapped[str | None] = mapped_column(String(128))
    is_current_career_step: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(64), default="mnp_editorial_v1")
    source_version: Mapped[str | None] = mapped_column(String(32))
    review_status: Mapped[str] = mapped_column(String(24), default="editorial")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    career: Mapped["MnpCareer"] = relationship(back_populates="path_steps")
