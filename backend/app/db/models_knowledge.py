"""Stage 3A: Curated Career Knowledge Base + source provenance (Issue #4,
docs/architecture/02_ERD.md's `CAREER`/`CAREER_SKILL`/`SKILL`/
`CAREER_EDGE`/`MARKET_SIGNAL` -- the ERD sketches these only as
relationship lines with no field-level shape, so this module is the
first real schema design for them, per brief §6 ("design the minimal
production-grade V1 schema", not a blind copy).

Bounded-domain separation (brief §21): this module knows nothing about
`identity_users`, `interview_sessions`, `evidence`, or `profile_claims`.
Career Knowledge and User Evidence/Profile are separate domains; no table
here has a foreign key into the user/assessment/profile schema, and none
ever will.

## Reuse decision: skills are Taxonomy content, not a new Skill table

`docs/engineering/13_FOUNDER_ARCHITECTURE_REVIEW.md` already names "career
taxonomy" as one of the categories the versioned `TAXONOMY`/
`TAXONOMY_VERSION`/`TAXONOMY_TERM` architecture (Stage 2,
`app/db/models_profile.py`) is meant to cover. Per brief §8 ("reuse
existing taxonomy/term architecture... do not create a duplicate skill
universe without justification"), skills are seeded as `TaxonomyTerm` rows
under a new `Taxonomy(key="skills")` (see
`app/services/knowledge/skills.py`) -- `CareerSkill.skill_term_id`
references `taxonomy_terms.id` directly. No new Skill table exists here.

## Versioning model

`KnowledgeBaseVersion` is a single global version counter for the whole
Career Knowledge Base -- the same "one incrementing version, one current
flag, old versions never edited" idiom Stage 2 already established for
`PotentialProfile`. Every `Career` row belongs to exactly one KB version
(`UNIQUE(knowledge_base_version_id, code)` -- the stable `code` is only
unique *within* a version, not globally, since republishing the KB with
updates creates new rows, never edits to old ones). Child tables
(`CareerAlias`/`CareerSkill`/`CareerRequirement`/`CareerWorkContext`/
`CareerRelation`) key off `career_id` and inherit their version
transitively through their parent `Career` row. `CareerFact` carries its
own explicit `knowledge_base_version_id` (brief §13 lists "knowledge
version" as a required fact field directly).
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime, timezone

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
    Uuid,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class KnowledgeBaseVersionStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"


class CareerStatus(str, enum.Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    DRAFT = "draft"


class CareerDomain(str, enum.Enum):
    """Broad classification (brief §7/§15) -- a stable, structural
    top-level grouping, not proprietary methodology content, same
    rationale as Stage 2's `ProfileDimension`."""

    TECHNOLOGY = "technology"
    HEALTHCARE = "healthcare"
    ENGINEERING = "engineering"
    LOGISTICS_TRANSPORT = "logistics_transport"
    SKILLED_TRADES = "skilled_trades"
    SALES = "sales"
    CUSTOMER_SERVICE = "customer_service"
    MANAGEMENT = "management"
    FINANCE = "finance"
    EDUCATION = "education"
    CREATIVE = "creative"
    MARKETING = "marketing"
    SOCIAL_SECTOR = "social_sector"
    ADMINISTRATION = "administration"
    HOSPITALITY_SERVICE = "hospitality_service"
    MANUFACTURING = "manufacturing"


class SkillRequirementType(str, enum.Enum):
    REQUIRED = "required"
    PREFERRED = "preferred"
    USEFUL = "useful"


class RequirementCategory(str, enum.Enum):
    EDUCATION = "education"
    CERTIFICATION = "certification"
    LICENSE = "license"
    LANGUAGE = "language"
    PHYSICAL_ENVIRONMENTAL = "physical_environmental"
    EXPERIENCE = "experience"
    PORTFOLIO = "portfolio"
    EQUIPMENT = "equipment"
    LEGAL_REGULATORY = "legal_regulatory"


class RequirementCertainty(str, enum.Enum):
    """Brief §9's non-negotiable distinction: a requirement is either a
    sourced fact, a curated typical expectation, or explicitly unknown --
    never presented with more certainty than it actually has."""

    HARD_FACTUAL = "hard_factual"
    TYPICAL_RECOMMENDATION = "typical_recommendation"
    UNKNOWN = "unknown"


class RelationType(str, enum.Enum):
    ADJACENT_TO = "adjacent_to"
    PROGRESSION_TO = "progression_to"
    SPECIALIZATION_OF = "specialization_of"
    RELATED_TO = "related_to"
    TRANSITION_POSSIBLE_TO = "transition_possible_to"


class SourceStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DISPUTED = "disputed"


class FactVerificationState(str, enum.Enum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    DISPUTED = "disputed"


class WorkSetting(str, enum.Enum):
    OFFICE = "office"
    REMOTE = "remote"
    FIELD = "field"
    MIXED = "mixed"


class IndoorOutdoor(str, enum.Enum):
    INDOOR = "indoor"
    OUTDOOR = "outdoor"
    BOTH = "both"


class TravelRequirement(str, enum.Enum):
    NONE = "none"
    OCCASIONAL = "occasional"
    FREQUENT = "frequent"


class KnowledgeBaseVersion(Base):
    """The publish-unit for the whole Career Knowledge Base. Exactly one
    row may have `is_current=true` (partial unique index, same idiom as
    Stage 1/2's `uq_one_unfinished_session_per_user` /
    `uq_one_current_profile_per_user`). A DRAFT version is being curated;
    PUBLISHED versions are immutable and queryable forever; publishing a
    new version flips the previous PUBLISHED version to SUPERSEDED and
    clears its `is_current` flag -- never edited or deleted."""

    __tablename__ = "knowledge_base_versions"
    __table_args__ = (
        Index(
            "uq_one_current_knowledge_base_version",
            "is_current",
            unique=True,
            postgresql_where=text("is_current = true"),
            sqlite_where=text("is_current = 1"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version: Mapped[int] = mapped_column(Integer, unique=True)
    status: Mapped[KnowledgeBaseVersionStatus] = mapped_column(
        Enum(KnowledgeBaseVersionStatus, native_enum=False), default=KnowledgeBaseVersionStatus.DRAFT, index=True
    )
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    careers: Mapped[list["Career"]] = relationship(back_populates="knowledge_base_version")


class KnowledgeSource(Base):
    """A reference to where a factual claim came from -- never a copy of
    the source document itself (brief §12: "do not store giant
    copyrighted documents"). `source_type`/`trust_level` are free strings
    (`native_enum=False`-equivalent -- plain `String`, extensible without
    a migration), not a closed enum, since the set of source kinds is
    expected to grow with real curation work."""

    __tablename__ = "knowledge_sources"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_type: Mapped[str] = mapped_column(String(64))  # e.g. "government" | "industry_report" | "internal_curation"
    publisher: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str | None] = mapped_column(String(1000))
    country_region: Mapped[str | None] = mapped_column(String(64))
    publication_date: Mapped[date | None] = mapped_column(Date)
    accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trust_level: Mapped[str | None] = mapped_column(String(32))  # e.g. "high" | "medium" | "low"
    status: Mapped[SourceStatus] = mapped_column(Enum(SourceStatus, native_enum=False), default=SourceStatus.ACTIVE)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Career(Base):
    """One career/direction record within one `KnowledgeBaseVersion`.
    `code` is the stable internal business key (never an external
    taxonomy ID -- brief §16: "External IDs must not become our primary
    business IDs"), unique per version, stable across republishes so a
    consumer can track "the same career" across KB versions by `code`
    even though the row itself is a new one each time.

    Structured characteristics below are all continuous 0.0-1.0 scores
    describing the intrinsic nature of the work (brief §7) -- deliberately
    NOT a fit/suitability score for any particular person; user fit is
    Stage 3B's job entirely. All nullable: an uncurated characteristic is
    absent, never defaulted to a fabricated midpoint."""

    __tablename__ = "careers"
    __table_args__ = (UniqueConstraint("knowledge_base_version_id", "code", name="uq_career_code_per_kb_version"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    knowledge_base_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_base_versions.id"), index=True)
    code: Mapped[str] = mapped_column(String(128), index=True)
    title_uk: Mapped[str] = mapped_column(String(255))
    title_en: Mapped[str | None] = mapped_column(String(255))
    domain: Mapped[CareerDomain] = mapped_column(Enum(CareerDomain, native_enum=False), index=True)
    status: Mapped[CareerStatus] = mapped_column(Enum(CareerStatus, native_enum=False), default=CareerStatus.ACTIVE)
    short_description: Mapped[str] = mapped_column(Text)
    typical_activities: Mapped[str | None] = mapped_column(Text)

    # Matching-relevant intrinsic-task characteristics (brief §7). Never a
    # fit score -- these describe the work, not any particular candidate.
    works_with_people: Mapped[float | None] = mapped_column(Float)
    works_with_data: Mapped[float | None] = mapped_column(Float)
    works_with_technology: Mapped[float | None] = mapped_column(Float)
    creative_component: Mapped[float | None] = mapped_column(Float)
    analytical_component: Mapped[float | None] = mapped_column(Float)
    autonomy_level: Mapped[float | None] = mapped_column(Float)
    structure_routine_level: Mapped[float | None] = mapped_column(Float)  # 0=highly routine, 1=highly variable

    # External taxonomy readiness (brief §16) -- references, never primary IDs.
    external_esco_id: Mapped[str | None] = mapped_column(String(64))
    external_onet_id: Mapped[str | None] = mapped_column(String(64))
    external_isco_id: Mapped[str | None] = mapped_column(String(64))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    knowledge_base_version: Mapped["KnowledgeBaseVersion"] = relationship(back_populates="careers")
    aliases: Mapped[list["CareerAlias"]] = relationship(back_populates="career")
    skills: Mapped[list["CareerSkill"]] = relationship(back_populates="career")
    requirements: Mapped[list["CareerRequirement"]] = relationship(back_populates="career")
    work_context: Mapped["CareerWorkContext | None"] = relationship(back_populates="career", uselist=False)
    facts: Mapped[list["CareerFact"]] = relationship(back_populates="career")


class CareerAlias(Base):
    """Ukrainian-first names/synonyms (brief §18), locale-ready for future
    languages. `normalized_text` is the lowercased/stripped form search
    actually matches on -- kept as a real column (not computed at query
    time) so lookups stay a plain indexed equality/prefix match, no
    per-query normalization logic scattered around callers."""

    __tablename__ = "career_aliases"
    __table_args__ = (UniqueConstraint("career_id", "locale", "normalized_text", name="uq_career_alias_per_locale"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("careers.id"), index=True)
    alias_text: Mapped[str] = mapped_column(String(255))
    locale: Mapped[str] = mapped_column(String(8), default="uk")
    normalized_text: Mapped[str] = mapped_column(String(255), index=True)

    career: Mapped["Career"] = relationship(back_populates="aliases")


class CareerSkill(Base):
    """Links a Career to a skill `TaxonomyTerm` (see module docstring --
    skills are Taxonomy content, not a separate Skill table).
    `source_id` is optional: a curated requirement/preference judgment is
    methodology content, not necessarily a single citable market fact."""

    __tablename__ = "career_skills"
    __table_args__ = (UniqueConstraint("career_id", "skill_term_id", name="uq_career_skill_pair"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("careers.id"), index=True)
    skill_term_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("taxonomy_terms.id"), index=True)
    requirement_type: Mapped[SkillRequirementType] = mapped_column(Enum(SkillRequirementType, native_enum=False))
    expected_level: Mapped[str | None] = mapped_column(String(32))  # e.g. "beginner" | "intermediate" | "advanced"
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("knowledge_sources.id"))
    notes: Mapped[str | None] = mapped_column(Text)

    career: Mapped["Career"] = relationship(back_populates="skills")


class CareerRequirement(Base):
    """Entry barriers (brief §9). `certainty` is the load-bearing field:
    `HARD_FACTUAL` requires `source_id` (enforced in
    app/services/knowledge/careers.py, not a DB CHECK -- consistent with
    this codebase's existing enforcement-at-the-service-layer
    convention), `TYPICAL_RECOMMENDATION` and `UNKNOWN` do not."""

    __tablename__ = "career_requirements"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("careers.id"), index=True)
    category: Mapped[RequirementCategory] = mapped_column(Enum(RequirementCategory, native_enum=False), index=True)
    description: Mapped[str] = mapped_column(Text)
    certainty: Mapped[RequirementCertainty] = mapped_column(Enum(RequirementCertainty, native_enum=False), index=True)
    jurisdiction: Mapped[str | None] = mapped_column(String(64))  # e.g. "UA" -- relevant for license/legal categories
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("knowledge_sources.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    career: Mapped["Career"] = relationship(back_populates="requirements")


class CareerWorkContext(Base):
    """Environment/logistics attributes (brief §10), one row per Career.
    Split from `Career`'s own intrinsic-task characteristics purely for
    readability -- both are "structured career attributes usable without
    parsing prose," just grouped by what they describe (the work itself
    vs. the setting it happens in)."""

    __tablename__ = "career_work_contexts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("careers.id"), unique=True, index=True)
    setting: Mapped[WorkSetting | None] = mapped_column(Enum(WorkSetting, native_enum=False))
    indoor_outdoor: Mapped[IndoorOutdoor | None] = mapped_column(Enum(IndoorOutdoor, native_enum=False))
    travel_required: Mapped[TravelRequirement | None] = mapped_column(Enum(TravelRequirement, native_enum=False))
    shift_work: Mapped[bool | None] = mapped_column(Boolean)
    physical_intensity: Mapped[float | None] = mapped_column(Float)
    teamwork_level: Mapped[float | None] = mapped_column(Float)  # 0=independent, 1=highly collaborative
    customer_interaction_level: Mapped[float | None] = mapped_column(Float)
    client_facing: Mapped[bool | None] = mapped_column(Boolean)
    repetitive_vs_varied: Mapped[float | None] = mapped_column(Float)  # 0=repetitive, 1=highly varied
    schedule_predictability: Mapped[float | None] = mapped_column(Float)
    responsibility_level: Mapped[float | None] = mapped_column(Float)
    stress_level: Mapped[float | None] = mapped_column(Float)

    career: Mapped["Career"] = relationship(back_populates="work_context")


class CareerRelation(Base):
    """A trustworthy, queryable edge between two careers (brief §11) --
    deliberately not pathfinding/Route Builder, just the relationship
    facts a future Route Builder could use. Both ends must belong to the
    same `Career.knowledge_base_version_id` (enforced in the service
    layer, not a DB constraint, since cross-version relations are simply
    never a meaningful thing to create, not merely disallowed)."""

    __tablename__ = "career_relations"
    __table_args__ = (
        UniqueConstraint("from_career_id", "to_career_id", "relation_type", name="uq_career_relation_triple"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_career_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("careers.id"), index=True)
    to_career_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("careers.id"), index=True)
    relation_type: Mapped[RelationType] = mapped_column(Enum(RelationType, native_enum=False), index=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("knowledge_sources.id"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CareerFact(Base):
    """A structured, source-referenced factual assertion about a career
    (brief §13) -- the mechanism that keeps mutable/market-sensitive data
    out of one giant Career JSON blob. `is_market_sensitive=true` facts
    require `source_id` (enforced in the service layer -- brief §20: "if
    those fields are not properly sourced, DO NOT populate them").
    `expires_at` gives freshness a real expiry semantic, not just an
    informal "as_of" date to eyeball."""

    __tablename__ = "career_facts"
    __table_args__ = (
        UniqueConstraint(
            "career_id", "fact_type", "geography", "knowledge_base_version_id", name="uq_career_fact_identity"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("careers.id"), index=True)
    knowledge_base_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_base_versions.id"), index=True)
    fact_type: Mapped[str] = mapped_column(String(128))  # e.g. "work_context.remote_possible" | "requires_license"
    value_text: Mapped[str] = mapped_column(Text)
    value_metadata: Mapped[dict | None] = mapped_column(JSON)  # e.g. {"jurisdiction": "UA"}
    geography: Mapped[str | None] = mapped_column(String(64))
    is_market_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    verification_state: Mapped[FactVerificationState] = mapped_column(
        Enum(FactVerificationState, native_enum=False), default=FactVerificationState.UNVERIFIED
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("knowledge_sources.id"))
    as_of_date: Mapped[date | None] = mapped_column(Date)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    career: Mapped["Career"] = relationship(back_populates="facts")
