"""PERSON KB BASE V1 (`docs/person_kb/PERSON_KB_BASE_V1.md`).

The Person-side equivalent of the Career KB (`models_career_kb_mnp.py`):
ONE canonical Person KB root (`MnpPerson`) + fact tables, fed by the three
entry flows (user manual profile, user CV upload+review, admin manual) --
all writing to the SAME tables.

FACT-FIRST: "what do we actually know about this person" -- education,
credentials, experience, activities/projects, skills/tools, languages,
mobility, documents. NOT a psychological portrait / RIASEC / Big Five /
Work Values / Work Styles / aptitude / AI personality inference
(Founder Decision, PERSON_KB_BASE_V1 §1).

Deliberately a NEW root, not the old `MnpCareerCard` (which is a
person-side profile misnamed "Career Card", is wired to the Matching
engine + resume flow, and carries preference/values scope that Person KB
Base V1 excludes). `MnpCareerCard` stays as-is for Matching compatibility;
the canonical Person Source of Truth for new development is `MnpPerson`.

Reuses the canonical Skill taxonomy (`MnpSkill` / `MnpSkillAlias` /
`MnpUnmappedPhrase` in `models_career_card.py`) -- Person skills and
Career-KB skill requirements point at the SAME `mnp_skills` rows. No
parallel Person skill dictionary.

Principles enforced here:
  * UNKNOWN != NO -- every yes/no fact is an explicit tri-state
    (`TriState`), never a bare Boolean.
  * SYSTEM_DETECTED != a confirmed fact -- `PersonEvidenceState` keeps the
    two apart; a CV-extracted row is `SYSTEM_DETECTED` until a human
    confirms it.
  * `raw_job_title` / raw text is the immutable fact; a taxonomy mapping
    is a SEPARATE nullable field, never an overwrite.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models_career_card import _str_enum

PERSON_KB_SCHEMA_VERSION = "person_kb_base_v1"


# --- vocabularies -------------------------------------------------------
class PersonStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class TriState(str, enum.Enum):
    """UNKNOWN != NO. The absence of information is first-class."""

    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


class PersonSource(str, enum.Enum):
    USER_MANUAL = "user_manual"        # the person filled it in themselves
    ADMIN_MANUAL = "admin_manual"      # a team member entered / created it
    ADMIN_EDIT = "admin_edit"          # a team member corrected a value
    CV_IMPORT = "cv_import"            # parser produced a candidate row
    CV_CONFIRMED = "cv_confirmed"      # the person confirmed a CV candidate


class PersonEvidenceState(str, enum.Enum):
    SELF_REPORTED = "self_reported"          # person / admin entered it
    DOCUMENT_SUPPORTED = "document_supported"  # a supporting document is attached
    SYSTEM_DETECTED = "system_detected"      # parser found a candidate -- NOT confirmed
    USER_CONFIRMED = "user_confirmed"        # the person explicitly confirmed a candidate


class EducationLevel(str, enum.Enum):
    SECONDARY = "secondary"
    VOCATIONAL = "vocational"
    INCOMPLETE_HIGHER = "incomplete_higher"
    BACHELOR = "bachelor"
    SPECIALIST = "specialist"
    MASTER = "master"
    PHD = "phd"
    OTHER = "other"
    UNKNOWN = "unknown"


class EducationStatus(str, enum.Enum):
    COMPLETED = "completed"
    ONGOING = "ongoing"
    INCOMPLETE = "incomplete"
    UNKNOWN = "unknown"


class CredentialType(str, enum.Enum):
    COURSE = "course"
    CERTIFICATE = "certificate"
    LICENSE = "license"
    PROFESSIONAL_CREDENTIAL = "professional_credential"
    OTHER = "other"


class ActivityType(str, enum.Enum):
    PROJECT = "project"
    ACADEMIC_PROJECT = "academic_project"
    PRACTICE = "practice"
    INTERNSHIP = "internship"
    VOLUNTEERING = "volunteering"
    STUDENT_ACTIVITY = "student_activity"
    STUDENT_GOVERNMENT = "student_government"
    EVENT_ORGANIZATION = "event_organization"
    PET_PROJECT = "pet_project"
    OTHER = "other"


class LanguageLevel(str, enum.Enum):
    A1 = "a1"
    A2 = "a2"
    B1 = "b1"
    B2 = "b2"
    C1 = "c1"
    C2 = "c2"
    NATIVE = "native"
    UNKNOWN = "unknown"
    OTHER = "other"


class PersonSkillProficiency(str, enum.Enum):
    """Same 3 levels as the Career KB skill schema. NULL = unknown --
    UNKNOWN proficiency is NEVER silently 'beginner'."""

    BASIC = "basic"
    WORKING = "working"
    STRONG = "strong"


class CustomSkillStatus(str, enum.Enum):
    """A skill the person typed that is not (yet) a canonical taxonomy
    term. It never silently becomes a canonical skill."""

    CANONICAL = "canonical"      # canonical_skill_id is set
    PENDING_REVIEW = "pending_review"  # raw text only, waiting for a taxonomy decision
    REJECTED = "rejected"


class WorkFormat(str, enum.Enum):
    ONSITE = "onsite"
    REMOTE = "remote"
    HYBRID = "hybrid"
    ANY = "any"
    UNKNOWN = "unknown"


class PersonDocumentType(str, enum.Enum):
    CV = "cv"
    DIPLOMA = "diploma"
    DIPLOMA_SUPPLEMENT = "diploma_supplement"
    CERTIFICATE = "certificate"
    DRIVER_LICENSE = "driver_license"
    RECOMMENDATION = "recommendation"
    ARBEITSZEUGNIS = "arbeitszeugnis"
    EMPLOYMENT_DOCUMENT = "employment_document"
    PORTFOLIO = "portfolio"
    OTHER = "other"


# --- root --------------------------------------------------------------
class MnpPerson(Base):
    """The canonical Person KB root. One row per person. A stable UUID.

    `identity_user_id` links a self-service profile to the authenticated
    person (Identity, reused as-is); an admin-created profile may have
    none yet.
    """

    __tablename__ = "mnp_persons"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    identity_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("identity_users.id"), unique=True, index=True
    )

    # --- BASIC / contact (only first_name is required; everything else may be blank)
    first_name: Mapped[str] = mapped_column(String(120))
    last_name: Mapped[str | None] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(64))          # stored as the person entered it
    email: Mapped[str | None] = mapped_column(String(255))
    telegram_username: Mapped[str | None] = mapped_column(String(64))  # canonical: without '@' and without URL

    city: Mapped[str | None] = mapped_column(String(120))
    region: Mapped[str | None] = mapped_column(String(120))
    country: Mapped[str | None] = mapped_column(String(120))
    date_of_birth: Mapped[date | None] = mapped_column(Date)

    status: Mapped[PersonStatus] = mapped_column(_str_enum(PersonStatus), default=PersonStatus.DRAFT, index=True)
    source: Mapped[PersonSource] = mapped_column(_str_enum(PersonSource), default=PersonSource.ADMIN_MANUAL)
    profile_version: Mapped[int] = mapped_column(Integer, default=1)

    # --- MOBILITY / work format (I) -- 1:1 on the root, kept simple
    has_driver_license: Mapped[TriState] = mapped_column(_str_enum(TriState), default=TriState.UNKNOWN)
    driver_license_categories: Mapped[str | None] = mapped_column(String(64))  # e.g. "B, C1"
    has_car: Mapped[TriState] = mapped_column(_str_enum(TriState), default=TriState.UNKNOWN)
    willing_to_relocate: Mapped[TriState] = mapped_column(_str_enum(TriState), default=TriState.UNKNOWN)
    work_geography: Mapped[list | None] = mapped_column(JSON)  # ["own_city","region","ukraine","remote","other"]
    work_format: Mapped[WorkFormat] = mapped_column(_str_enum(WorkFormat), default=WorkFormat.UNKNOWN)

    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    educations: Mapped[list["MnpPersonEducation"]] = relationship(back_populates="person", cascade="all, delete-orphan")
    credentials: Mapped[list["MnpPersonCredential"]] = relationship(back_populates="person", cascade="all, delete-orphan")
    experiences: Mapped[list["MnpPersonExperience"]] = relationship(back_populates="person", cascade="all, delete-orphan")
    activities: Mapped[list["MnpPersonActivity"]] = relationship(back_populates="person", cascade="all, delete-orphan")
    skills: Mapped[list["MnpPersonSkillV1"]] = relationship(back_populates="person", cascade="all, delete-orphan")
    languages: Mapped[list["MnpPersonLanguageV1"]] = relationship(back_populates="person", cascade="all, delete-orphan")
    documents: Mapped[list["MnpPersonDocument"]] = relationship(back_populates="person", cascade="all, delete-orphan")


# --- shared columns via a mixin-ish helper (kept explicit for clarity) --
def _fact_cols():  # not a mixin -- SQLAlchemy 2.0 typed columns don't mix cleanly
    return


class MnpPersonEducation(Base):
    __tablename__ = "mnp_person_educations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_persons.id"), index=True)
    education_level: Mapped[EducationLevel] = mapped_column(_str_enum(EducationLevel), default=EducationLevel.UNKNOWN)
    institution_name: Mapped[str | None] = mapped_column(String(255))
    specialty_or_qualification: Mapped[str | None] = mapped_column(String(255))
    start_year: Mapped[int | None] = mapped_column(Integer)
    end_year: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[EducationStatus] = mapped_column(_str_enum(EducationStatus), default=EducationStatus.UNKNOWN)
    description: Mapped[str | None] = mapped_column(Text)
    supporting_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("mnp_person_documents.id"))
    evidence_state: Mapped[PersonEvidenceState] = mapped_column(
        _str_enum(PersonEvidenceState), default=PersonEvidenceState.SELF_REPORTED)
    source: Mapped[PersonSource] = mapped_column(_str_enum(PersonSource), default=PersonSource.USER_MANUAL)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    person: Mapped["MnpPerson"] = relationship(back_populates="educations")


class MnpPersonCredential(Base):
    __tablename__ = "mnp_person_credentials"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_persons.id"), index=True)
    credential_type: Mapped[CredentialType] = mapped_column(_str_enum(CredentialType), default=CredentialType.OTHER)
    title: Mapped[str] = mapped_column(String(255))
    provider: Mapped[str | None] = mapped_column(String(255))
    issue_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    credential_number: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    supporting_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("mnp_person_documents.id"))
    evidence_state: Mapped[PersonEvidenceState] = mapped_column(
        _str_enum(PersonEvidenceState), default=PersonEvidenceState.SELF_REPORTED)
    source: Mapped[PersonSource] = mapped_column(_str_enum(PersonSource), default=PersonSource.USER_MANUAL)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    person: Mapped["MnpPerson"] = relationship(back_populates="credentials")


class MnpPersonExperience(Base):
    """`raw_job_title` and `responsibilities_description` are the immutable
    RAW FACT. A Career KB mapping is `canonical_career_id` -- a SEPARATE
    nullable field; a mapper never rewrites the raw text."""

    __tablename__ = "mnp_person_experiences"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_persons.id"), index=True)
    company_name: Mapped[str | None] = mapped_column(String(255))
    raw_job_title: Mapped[str] = mapped_column(String(255))
    canonical_career_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("mnp_careers.id"))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    is_current: Mapped[TriState] = mapped_column(_str_enum(TriState), default=TriState.UNKNOWN)
    responsibilities_description: Mapped[str | None] = mapped_column(Text)
    achievements: Mapped[str | None] = mapped_column(Text)
    tools_used: Mapped[str | None] = mapped_column(Text)
    industry: Mapped[str | None] = mapped_column(String(255))
    employment_type: Mapped[str | None] = mapped_column(String(64))
    supporting_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("mnp_person_documents.id"))
    evidence_state: Mapped[PersonEvidenceState] = mapped_column(
        _str_enum(PersonEvidenceState), default=PersonEvidenceState.SELF_REPORTED)
    source: Mapped[PersonSource] = mapped_column(_str_enum(PersonSource), default=PersonSource.USER_MANUAL)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    person: Mapped["MnpPerson"] = relationship(back_populates="experiences")


class MnpPersonActivity(Base):
    """Projects / practice / internships / volunteering / student activity
    -- so the Person KB works for students, graduates, veterans, career
    changers and returners, not only people with formal employment."""

    __tablename__ = "mnp_person_activities"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_persons.id"), index=True)
    activity_type: Mapped[ActivityType] = mapped_column(_str_enum(ActivityType), default=ActivityType.OTHER)
    title: Mapped[str] = mapped_column(String(255))
    organization: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str | None] = mapped_column(String(255))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    result_or_achievement: Mapped[str | None] = mapped_column(Text)
    supporting_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("mnp_person_documents.id"))
    evidence_state: Mapped[PersonEvidenceState] = mapped_column(
        _str_enum(PersonEvidenceState), default=PersonEvidenceState.SELF_REPORTED)
    source: Mapped[PersonSource] = mapped_column(_str_enum(PersonSource), default=PersonSource.USER_MANUAL)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    person: Mapped["MnpPerson"] = relationship(back_populates="activities")


class MnpPersonSkillV1(Base):
    """Person <-> canonical Skill (`mnp_skills`). The SAME taxonomy the
    Career KB skill requirements use -- no parallel Person skill
    dictionary. A skill the person typed that is not a taxonomy term is
    kept as `raw_input` with `custom_status = pending_review`."""

    __tablename__ = "mnp_person_skills_v1"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_persons.id"), index=True)
    canonical_skill_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("mnp_skills.id"), index=True)
    raw_input: Mapped[str | None] = mapped_column(String(255))  # what the person typed (custom / unresolved)
    custom_status: Mapped[CustomSkillStatus] = mapped_column(
        _str_enum(CustomSkillStatus), default=CustomSkillStatus.CANONICAL)
    proficiency: Mapped[PersonSkillProficiency | None] = mapped_column(_str_enum(PersonSkillProficiency))
    years_used: Mapped[float | None] = mapped_column(Integer)
    last_used_year: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    supporting_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("mnp_person_documents.id"))
    evidence_state: Mapped[PersonEvidenceState] = mapped_column(
        _str_enum(PersonEvidenceState), default=PersonEvidenceState.SELF_REPORTED)
    source: Mapped[PersonSource] = mapped_column(_str_enum(PersonSource), default=PersonSource.USER_MANUAL)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    person: Mapped["MnpPerson"] = relationship(back_populates="skills")


class MnpPersonLanguageV1(Base):
    __tablename__ = "mnp_person_languages_v1"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_persons.id"), index=True)
    language: Mapped[str] = mapped_column(String(64))  # "Українська", "English", "Deutsch"...
    level: Mapped[LanguageLevel] = mapped_column(_str_enum(LanguageLevel), default=LanguageLevel.UNKNOWN)
    certificate: Mapped[str | None] = mapped_column(String(255))
    supporting_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("mnp_person_documents.id"))
    evidence_state: Mapped[PersonEvidenceState] = mapped_column(
        _str_enum(PersonEvidenceState), default=PersonEvidenceState.SELF_REPORTED)
    source: Mapped[PersonSource] = mapped_column(_str_enum(PersonSource), default=PersonSource.USER_MANUAL)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    person: Mapped["MnpPerson"] = relationship(back_populates="languages")


class MnpPersonDocument(Base):
    """A supporting document. `storage_ref` is an opaque path/key -- raw
    bytes are never in the DB. Reuses the same on-disk storage dir as CRM
    client files / MNP resumes."""

    __tablename__ = "mnp_person_documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_persons.id"), index=True)
    document_type: Mapped[PersonDocumentType] = mapped_column(_str_enum(PersonDocumentType), default=PersonDocumentType.OTHER)
    filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str | None] = mapped_column(String(128))
    file_size: Mapped[int | None] = mapped_column(Integer)
    storage_ref: Mapped[str] = mapped_column(String(500))
    note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    person: Mapped["MnpPerson"] = relationship(back_populates="documents")
