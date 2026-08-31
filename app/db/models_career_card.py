"""MNP V1 -- person-side domain: AssessmentSession, SourceDocument,
CareerCard (+versions) and everything under it (`MNP_DATA_MODEL_V1.md`
§3-11). New, dedicated MNP schema -- deliberately NOT reusing Stage 1/2's
`interview_sessions`/`cv_uploads`/`evidence`/`profiles` tables, which are
shaped for a different, AI-driven assessment flow (LLM extraction,
RIASEC/Work-Style Likert scoring) that `MNP_METHODOLOGY_V1.md` explicitly
supersedes for this product line (Founder Decision #22: RIASEC secondary,
not core; §4: BASIC core uses no LLM tokens).

Every table is `mnp_`-prefixed and every class is `Mnp`-prefixed to avoid
any collision in the shared SQLAlchemy declarative registry (`app/db/
base.py`'s single `Base` across the whole app already has `Career`,
`CareerAlias`, `CareerRelation`, `CareerRequirement`, `Evidence`, `User` --
see `models_identity.py`'s own docstring for the same collision problem
solved the same way for `IdentityUser`).

Foreign key to `identity_users` (Stage 1's channel-agnostic human, reused
as-is -- MNP_DATA_MODEL_V1 does not ask for a new User entity, just a
`user_id`).
"""

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
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _str_enum(enum_cls: type[enum.Enum]) -> Enum:
    """`Enum(..., native_enum=False)` without `values_callable` persists a
    Python enum member's `.name` (uppercase), not its `.value` (lowercase)
    -- silently breaks any plain-string comparison or partial-unique-index
    predicate written against the lowercase value. Every enum column in
    this module goes through this helper."""

    return Enum(enum_cls, native_enum=False, values_callable=lambda obj: [e.value for e in obj])


# ---------------------------------------------------------------------------
# Enums

class EntryMode(str, enum.Enum):
    RESUME = "resume"
    MANUAL = "manual"


class SourceMode(str, enum.Enum):
    RESUME = "resume"
    MANUAL = "manual"
    MIXED = "mixed"


class SessionStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class DocumentType(str, enum.Enum):
    RESUME = "resume"


class TextExtractionStatus(str, enum.Enum):
    PENDING = "pending"
    EXTRACTED = "extracted"
    OCR_REQUIRED = "ocr_required"
    UNSUPPORTED_FORMAT = "unsupported_format"
    CORRUPT_FILE = "corrupt_file"
    NO_TEXT_LAYER = "no_text_layer"
    EMPTY_DOCUMENT = "empty_document"
    PARSE_PARTIAL = "parse_partial"


class ProficiencyLevel(str, enum.Enum):
    """MNP_SKILL_SCHEMA_V1 §5 -- Founder Decision #10. Exactly 3 levels,
    never more, never a numeric substitute shown to the user."""

    BASIC = "basic"
    WORKING = "working"
    STRONG = "strong"


class EvidenceType(str, enum.Enum):
    """MNP_EVIDENCE_AND_CONFIDENCE_MODEL_V1 §3. `MATCH != CONFIDENCE`, and
    `UNKNOWN != ABSENT` -- the absence of an MnpEvidence row for a given
    (entity_type, entity_id) is never treated as a confirmed negative by
    any downstream reader."""

    CLAIMED = "claimed"
    INFERRED = "inferred"
    VERIFIED = "verified"


class EvidenceSourceType(str, enum.Enum):
    """§5 -- person-side source types only (career/market source types
    live on the Career KB side, see `models_career_kb_mnp.py`)."""

    CV = "cv"
    QUESTIONNAIRE = "questionnaire"
    USER_EDIT = "user_edit"
    CERTIFICATE = "certificate"
    PORTFOLIO = "portfolio"
    PROJECT = "project"
    ACHIEVEMENT = "achievement"
    TEST = "test"
    HUMAN_REVIEW = "human_review"


class SkillType(str, enum.Enum):
    """MNP_SKILL_SCHEMA_V1 §4, SS-FQ-001 (approved)."""

    TECHNICAL = "technical"
    TOOL = "tool"
    FUNCTIONAL = "functional"
    MANAGEMENT = "management"
    COMMUNICATION = "communication"
    DIGITAL = "digital"


class SkillStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class SkillAliasType(str, enum.Enum):
    EXACT_SYNONYM = "exact_synonym"
    ABBREVIATION = "abbreviation"
    COMMON_VARIANT = "common_variant"
    UKRAINIAN_MARKET_TERM = "ukrainian_market_term"
    ENGLISH_MARKET_TERM = "english_market_term"
    TOOL_VARIANT = "tool_variant"


class ConstraintSeverity(str, enum.Enum):
    """MNP_DATA_MODEL_V1 §11 Constraint.severity."""

    PREFERENCE = "preference"
    STRONG = "strong"
    HARD = "hard"


class WorkFormat(str, enum.Enum):
    ONSITE = "onsite"
    HYBRID = "hybrid"
    REMOTE = "remote"


class CareerGoalType(str, enum.Enum):
    """MNP_MINIMAL_QUESTIONNAIRE_V1 §"Required decision variables" item 1."""

    FIND_WORK = "find_work"
    CHANGE_CAREER = "change_career"
    INCREASE_INCOME = "increase_income"
    RETURN_TO_MARKET = "return_to_market"
    EXPLORE = "explore"


class WorkObject(str, enum.Enum):
    """Preferred work objects -- Methodology §21 Preference Fit."""

    PEOPLE = "people"
    DATA = "data"
    TECHNOLOGY = "technology"
    THINGS = "things"
    IDEAS = "ideas"


# ---------------------------------------------------------------------------
# Assessment session / source document

class MnpAssessmentSession(Base):
    """MNP_DATA_MODEL_V1 §4. One pass through the CV-or-questionnaire
    pipeline. `reset_from_session_id` links a fresh restart to its
    predecessor without overwriting history (§4: "Reset создаёт новую
    сессию, не перезаписывая историю")."""

    __tablename__ = "mnp_assessment_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity_users.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    entry_mode: Mapped[EntryMode] = mapped_column(_str_enum(EntryMode))
    status: Mapped[SessionStatus] = mapped_column(_str_enum(SessionStatus), default=SessionStatus.IN_PROGRESS)
    methodology_version: Mapped[str] = mapped_column(String(32))
    career_kb_version: Mapped[str | None] = mapped_column(String(32))
    market_snapshot_version: Mapped[str | None] = mapped_column(String(32))
    reset_from_session_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("mnp_assessment_sessions.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    documents: Mapped[list["MnpSourceDocument"]] = relationship(back_populates="session")
    career_card: Mapped["MnpCareerCard | None"] = relationship(back_populates="session", uselist=False)


class MnpSourceDocument(Base):
    """MNP_DATA_MODEL_V1 §5 / MNP_RESUME_PARSER_V1. One uploaded CV
    attempt. `storage_ref` is an opaque pointer (local path or object-store
    key) -- this table never stores the raw bytes."""

    __tablename__ = "mnp_source_documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity_users.id"), index=True)
    assessment_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_assessment_sessions.id"), index=True)
    document_type: Mapped[DocumentType] = mapped_column(_str_enum(DocumentType), default=DocumentType.RESUME)
    filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str | None] = mapped_column(String(128))
    file_size: Mapped[int | None] = mapped_column(Integer)
    storage_ref: Mapped[str] = mapped_column(String(500))
    text_extraction_status: Mapped[TextExtractionStatus] = mapped_column(
        _str_enum(TextExtractionStatus), default=TextExtractionStatus.PENDING
    )
    parser_version: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped["MnpAssessmentSession"] = relationship(back_populates="documents")


# ---------------------------------------------------------------------------
# CareerCard (master profile) + versioning

class MnpCareerCard(Base):
    """MNP_DATA_MODEL_V1 §6 -- Founder Decision #7/DM-FQ-002 (approved):
    ONE long-lived master card per user, not one card per session.
    `assessment_session_id` records which session most recently updated
    it; `MnpCareerCardVersion` is the immutable snapshot history
    (calculations/MatchRuns reference a specific version, never the live,
    still-editable master row -- §6: "calculations use versioned
    snapshots")."""

    __tablename__ = "mnp_career_cards"
    __table_args__ = (
        Index(
            "uq_one_career_card_per_user",
            "user_id",
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity_users.id"), index=True)
    assessment_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_assessment_sessions.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    source_mode: Mapped[SourceMode] = mapped_column(_str_enum(SourceMode))
    completeness_score_internal: Mapped[float | None] = mapped_column(Float)
    confidence_score_internal: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    session: Mapped["MnpAssessmentSession"] = relationship(back_populates="career_card")
    experiences: Mapped[list["MnpExperience"]] = relationship(back_populates="career_card", cascade="all, delete-orphan")
    educations: Mapped[list["MnpEducation"]] = relationship(back_populates="career_card", cascade="all, delete-orphan")
    achievements: Mapped[list["MnpAchievement"]] = relationship(back_populates="career_card", cascade="all, delete-orphan")
    credentials: Mapped[list["MnpCredential"]] = relationship(back_populates="career_card", cascade="all, delete-orphan")
    languages: Mapped[list["MnpLanguage"]] = relationship(back_populates="career_card", cascade="all, delete-orphan")
    person_skills: Mapped[list["MnpPersonSkill"]] = relationship(back_populates="career_card", cascade="all, delete-orphan")
    person_knowledge: Mapped[list["MnpPersonKnowledge"]] = relationship(back_populates="career_card", cascade="all, delete-orphan")
    goals: Mapped[list["MnpCareerGoal"]] = relationship(back_populates="career_card", cascade="all, delete-orphan")
    income_target: Mapped["MnpIncomeTarget | None"] = relationship(back_populates="career_card", uselist=False, cascade="all, delete-orphan")
    preference_profile: Mapped["MnpPreferenceProfile | None"] = relationship(back_populates="career_card", uselist=False, cascade="all, delete-orphan")
    work_values: Mapped[list["MnpPersonWorkValue"]] = relationship(back_populates="career_card", cascade="all, delete-orphan")
    constraints: Mapped[list["MnpConstraint"]] = relationship(back_populates="career_card", cascade="all, delete-orphan")
    learning_capacity: Mapped["MnpLearningCapacity | None"] = relationship(back_populates="career_card", uselist=False, cascade="all, delete-orphan")
    evidence: Mapped[list["MnpEvidence"]] = relationship(back_populates="career_card", cascade="all, delete-orphan")
    versions: Mapped[list["MnpCareerCardVersion"]] = relationship(back_populates="career_card", cascade="all, delete-orphan")


class MnpCareerCardVersion(Base):
    """Immutable snapshot taken at recalculation time (edit -> new
    version -> `MnpMatchRun` pins `career_card_version`). `snapshot` is the
    full serialized Career Card at that moment -- deliberately denormalized
    JSON so a historical MatchRun stays reproducible even if the live
    tables' shape evolves later (MNP_CAREER_PROFILE_SCHEMA_V1 §29/
    MNP_EVIDENCE_AND_CONFIDENCE_MODEL_V1 §24 Auditability)."""

    __tablename__ = "mnp_career_card_versions"
    __table_args__ = (UniqueConstraint("career_card_id", "version", name="uq_career_card_version"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_career_cards.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    career_card: Mapped["MnpCareerCard"] = relationship(back_populates="versions")


# ---------------------------------------------------------------------------
# Career Capital: Experience / Achievement / Education / Credential / Language

class MnpExperience(Base):
    """MNP_DATA_MODEL_V1 §7 / MNP_METHODOLOGY_V1 §6."""

    __tablename__ = "mnp_experiences"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_career_cards.id"), index=True)
    company_name: Mapped[str | None] = mapped_column(String(255))
    raw_job_title: Mapped[str] = mapped_column(String(255))
    normalized_career_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("mnp_careers.id"))
    industry_raw: Mapped[str | None] = mapped_column(String(255))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    duration_months: Mapped[int | None] = mapped_column(Integer)
    seniority: Mapped[str | None] = mapped_column(String(32))
    responsibilities_raw: Mapped[str | None] = mapped_column(Text)
    management_scope: Mapped[bool | None] = mapped_column(Boolean)
    team_size: Mapped[int | None] = mapped_column(Integer)
    tools_raw: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[EvidenceSourceType] = mapped_column(_str_enum(EvidenceSourceType))
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    career_card: Mapped["MnpCareerCard"] = relationship(back_populates="experiences")
    achievements: Mapped[list["MnpAchievement"]] = relationship(back_populates="experience")


class MnpAchievement(Base):
    __tablename__ = "mnp_achievements"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_career_cards.id"), index=True)
    experience_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("mnp_experiences.id"))
    description: Mapped[str] = mapped_column(Text)
    source_type: Mapped[EvidenceSourceType] = mapped_column(_str_enum(EvidenceSourceType))
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    career_card: Mapped["MnpCareerCard"] = relationship(back_populates="achievements")
    experience: Mapped["MnpExperience | None"] = relationship(back_populates="achievements")


class MnpEducation(Base):
    """MNP_DATA_MODEL_V1 §10."""

    __tablename__ = "mnp_educations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_career_cards.id"), index=True)
    level: Mapped[str] = mapped_column(String(64))
    field: Mapped[str | None] = mapped_column(String(255))
    institution: Mapped[str | None] = mapped_column(String(255))
    qualification: Mapped[str | None] = mapped_column(String(255))
    graduation_year: Mapped[int | None] = mapped_column(Integer)
    country: Mapped[str | None] = mapped_column(String(64))
    recognition: Mapped[str | None] = mapped_column(String(64))
    source_type: Mapped[EvidenceSourceType] = mapped_column(_str_enum(EvidenceSourceType))
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    career_card: Mapped["MnpCareerCard"] = relationship(back_populates="educations")


class MnpCredential(Base):
    """MNP_DATA_MODEL_V1 §10 -- certifications, licenses, permits."""

    __tablename__ = "mnp_credentials"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_career_cards.id"), index=True)
    credential_type: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    issuer: Mapped[str | None] = mapped_column(String(255))
    issued_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    country: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str | None] = mapped_column(String(32))
    source_type: Mapped[EvidenceSourceType] = mapped_column(_str_enum(EvidenceSourceType))
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    career_card: Mapped["MnpCareerCard"] = relationship(back_populates="credentials")


class MnpLanguage(Base):
    __tablename__ = "mnp_languages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_career_cards.id"), index=True)
    language_code: Mapped[str] = mapped_column(String(8))
    overall_level: Mapped[str | None] = mapped_column(String(16))
    speaking_level: Mapped[str | None] = mapped_column(String(16))
    reading_level: Mapped[str | None] = mapped_column(String(16))
    writing_level: Mapped[str | None] = mapped_column(String(16))
    certified_level: Mapped[str | None] = mapped_column(String(32))
    source_type: Mapped[EvidenceSourceType] = mapped_column(_str_enum(EvidenceSourceType))
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    career_card: Mapped["MnpCareerCard"] = relationship(back_populates="languages")


# ---------------------------------------------------------------------------
# Evidence (person-side; career-side evidence is a separate concern per
# MNP_EVIDENCE_AND_CONFIDENCE_MODEL_V1 §5's Career source-type list, and
# lives alongside the Career KB module instead)

class MnpEvidence(Base):
    """MNP_EVIDENCE_AND_CONFIDENCE_MODEL_V1 §4. `entity_type`/`entity_id`
    is a polymorphic pointer (e.g. entity_type="person_skill",
    entity_id=<MnpPersonSkill.id>) -- deliberately not a DB-level FK to
    any one target table, since evidence can attach to many different
    Career Card sub-entities (same rationale Stage 2's own `Evidence.
    source_id` docstring already uses in this codebase)."""

    __tablename__ = "mnp_evidence"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_career_cards.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), index=True)
    evidence_type: Mapped[EvidenceType] = mapped_column(_str_enum(EvidenceType))
    source_type: Mapped[EvidenceSourceType] = mapped_column(_str_enum(EvidenceSourceType))
    source_ref: Mapped[str | None] = mapped_column(String(500))
    excerpt: Mapped[str | None] = mapped_column(Text)
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("mnp_source_documents.id"))
    strength_internal: Mapped[float] = mapped_column(Float, default=0.5)
    parser_confidence: Mapped[float | None] = mapped_column(Float)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_by: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    career_card: Mapped["MnpCareerCard"] = relationship(back_populates="evidence")


# ---------------------------------------------------------------------------
# Skills (canonical taxonomy) + PersonSkill

class MnpSkill(Base):
    """MNP_SKILL_SCHEMA_V1 §3. `id` (UUID) is the storage PK; the row
    itself *is* the MNP_SKILL_ID -- never an ESCO/O*NET id (§10: "Mapping
    не меняет identity MNP Skill")."""

    __tablename__ = "mnp_skills"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canonical_name_en: Mapped[str] = mapped_column(String(255))
    canonical_name_uk: Mapped[str] = mapped_column(String(255))
    skill_type: Mapped[SkillType] = mapped_column(_str_enum(SkillType), index=True)
    status: Mapped[SkillStatus] = mapped_column(_str_enum(SkillStatus), default=SkillStatus.DRAFT, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    taxonomy_version: Mapped[str] = mapped_column(String(32))
    parent_skill_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("mnp_skills.id"))
    skill_family: Mapped[str | None] = mapped_column(String(64), index=True)
    notes_internal: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    aliases: Mapped[list["MnpSkillAlias"]] = relationship(back_populates="skill", cascade="all, delete-orphan")


class MnpSkillAlias(Base):
    """MNP_SKILL_SCHEMA_V1 §9. Unknown phrases never auto-create a
    canonical skill or alias row (SS-FQ-004, approved) -- they go to a
    review queue instead (`MnpUnmappedPhrase`, see the parser module)."""

    __tablename__ = "mnp_skill_aliases"
    __table_args__ = (UniqueConstraint("skill_id", "language", "alias", name="uq_skill_alias"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    skill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_skills.id"), index=True)
    alias: Mapped[str] = mapped_column(String(255), index=True)
    language: Mapped[str] = mapped_column(String(8), default="uk")
    alias_type: Mapped[SkillAliasType] = mapped_column(_str_enum(SkillAliasType))
    source: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[SkillStatus] = mapped_column(_str_enum(SkillStatus), default=SkillStatus.ACTIVE)
    confidence: Mapped[float | None] = mapped_column(Float)

    skill: Mapped["MnpSkill"] = relationship(back_populates="aliases")


class MnpPersonSkill(Base):
    """MNP_SKILL_SCHEMA_V1 §6. One skill may have several `MnpEvidence`
    rows (entity_type="person_skill", entity_id=this row's id) -- this
    table's own `evidence_strength`/`confidence` are the ALREADY-AGGREGATED
    view a reader needs without re-walking every Evidence row each time."""

    __tablename__ = "mnp_person_skills"
    __table_args__ = (UniqueConstraint("career_card_id", "skill_id", name="uq_person_skill"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_career_cards.id"), index=True)
    skill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_skills.id"), index=True)
    proficiency_level: Mapped[ProficiencyLevel] = mapped_column(_str_enum(ProficiencyLevel))
    evidence_strength: Mapped[float] = mapped_column(Float, default=0.5)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    years_used: Mapped[float | None] = mapped_column(Float)
    last_used_at: Mapped[date | None] = mapped_column(Date)
    source_type: Mapped[EvidenceSourceType] = mapped_column(_str_enum(EvidenceSourceType))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    career_card: Mapped["MnpCareerCard"] = relationship(back_populates="person_skills")
    skill: Mapped["MnpSkill"] = relationship()


class MnpUnmappedPhrase(Base):
    """Review queue for raw CV/questionnaire phrases the parser could not
    map to any `MnpSkill` alias (MNP_SKILL_SCHEMA_V1 §8/SS-FQ-004,
    MNP_RESUME_PARSER_V1 "Output": "unmapped phrases"). Never silently
    promoted to a canonical Skill -- an ADMIN/EDITOR reviews it."""

    __tablename__ = "mnp_unmapped_phrases"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_career_cards.id"), index=True)
    raw_phrase: Mapped[str] = mapped_column(String(500))
    context: Mapped[str | None] = mapped_column(String(64))  # e.g. "skills_section", "responsibilities"
    resolved_skill_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("mnp_skills.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------------
# Knowledge (kept separate from Skill, per MNP_DATA_MODEL_V1 §10 / SKILL
# SCHEMA §23 "knowledge не хранится как Skill")

class MnpKnowledge(Base):
    __tablename__ = "mnp_knowledge"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canonical_name_en: Mapped[str] = mapped_column(String(255))
    canonical_name_uk: Mapped[str] = mapped_column(String(255))
    status: Mapped[SkillStatus] = mapped_column(_str_enum(SkillStatus), default=SkillStatus.DRAFT)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MnpPersonKnowledge(Base):
    __tablename__ = "mnp_person_knowledge"
    __table_args__ = (UniqueConstraint("career_card_id", "knowledge_id", name="uq_person_knowledge"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_career_cards.id"), index=True)
    knowledge_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_knowledge.id"), index=True)
    proficiency_level: Mapped[ProficiencyLevel] = mapped_column(_str_enum(ProficiencyLevel))
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    source_type: Mapped[EvidenceSourceType] = mapped_column(_str_enum(EvidenceSourceType))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    career_card: Mapped["MnpCareerCard"] = relationship(back_populates="person_knowledge")


# ---------------------------------------------------------------------------
# Career Intent: Goal / IncomeTarget / PreferenceProfile / WorkValue / Constraint / LearningCapacity

class MnpCareerGoal(Base):
    __tablename__ = "mnp_career_goals"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_career_cards.id"), index=True)
    goal_type: Mapped[CareerGoalType] = mapped_column(_str_enum(CareerGoalType))
    priority: Mapped[int] = mapped_column(Integer, default=1)
    time_horizon: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    career_card: Mapped["MnpCareerCard"] = relationship(back_populates="goals")


class MnpIncomeTarget(Base):
    __tablename__ = "mnp_income_targets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_career_cards.id"), unique=True, index=True)
    current_income: Mapped[float | None] = mapped_column(Float)
    target_income: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="UAH")
    period: Mapped[str] = mapped_column(String(16), default="month")

    career_card: Mapped["MnpCareerCard"] = relationship(back_populates="income_target")


class MnpPreferenceProfile(Base):
    """MNP_DATA_MODEL_V1 §11 / Methodology §21 Preference Fit inputs."""

    __tablename__ = "mnp_preference_profiles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_career_cards.id"), unique=True, index=True)
    preferred_work_object: Mapped[WorkObject | None] = mapped_column(_str_enum(WorkObject))
    autonomy_preference: Mapped[float | None] = mapped_column(Float)  # 0..1, low->high
    teamwork_preference: Mapped[float | None] = mapped_column(Float)
    customer_interaction_preference: Mapped[float | None] = mapped_column(Float)
    routine_vs_novelty_preference: Mapped[float | None] = mapped_column(Float)  # 0=routine, 1=novelty
    leadership_preference: Mapped[float | None] = mapped_column(Float)
    physical_activity_preference: Mapped[float | None] = mapped_column(Float)
    work_format: Mapped[WorkFormat | None] = mapped_column(_str_enum(WorkFormat))
    location_region: Mapped[str | None] = mapped_column(String(128))

    career_card: Mapped["MnpCareerCard"] = relationship(back_populates="preference_profile")


class MnpWorkValue(Base):
    """Catalog of the 9 work-value keys from Methodology §21 (income,
    stability, autonomy, growth, recognition, social_impact, creativity,
    work_life_balance, learning) -- a small fixed reference table, not
    admin-editable in V1."""

    __tablename__ = "mnp_work_values"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(32), unique=True)
    label_uk: Mapped[str] = mapped_column(String(128))
    label_en: Mapped[str] = mapped_column(String(128))


class MnpPersonWorkValue(Base):
    __tablename__ = "mnp_person_work_values"
    __table_args__ = (UniqueConstraint("career_card_id", "work_value_id", name="uq_person_work_value"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_career_cards.id"), index=True)
    work_value_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_work_values.id"), index=True)
    priority_rank: Mapped[int] = mapped_column(Integer)  # 1 = top value

    career_card: Mapped["MnpCareerCard"] = relationship(back_populates="work_values")
    work_value: Mapped["MnpWorkValue"] = relationship()


class MnpConstraint(Base):
    """MNP_DATA_MODEL_V1 §11 Constraint. `constraint_type` is a free
    string (location/legal/physical/schedule/family/etc.) -- kept open
    since Golden personas (IDP, veteran transition, return-to-Ukraine)
    surface constraint kinds not worth a closed enum in V1."""

    __tablename__ = "mnp_constraints"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_career_cards.id"), index=True)
    constraint_type: Mapped[str] = mapped_column(String(64))
    value: Mapped[str] = mapped_column(String(500))
    severity: Mapped[ConstraintSeverity] = mapped_column(_str_enum(ConstraintSeverity))
    source_type: Mapped[EvidenceSourceType] = mapped_column(_str_enum(EvidenceSourceType))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    career_card: Mapped["MnpCareerCard"] = relationship(back_populates="constraints")


class MnpLearningCapacity(Base):
    __tablename__ = "mnp_learning_capacities"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_career_cards.id"), unique=True, index=True)
    hours_per_week: Mapped[float | None] = mapped_column(Float)
    max_months: Mapped[int | None] = mapped_column(Integer)
    budget: Mapped[float | None] = mapped_column(Float)
    willing_new_credential: Mapped[bool | None] = mapped_column(Boolean)
    willing_lower_entry_role: Mapped[bool | None] = mapped_column(Boolean)

    career_card: Mapped["MnpCareerCard"] = relationship(back_populates="learning_capacity")
