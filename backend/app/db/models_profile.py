"""Stage 2: Evidence + Human Potential Profile (Issue #2,
docs/architecture/02_ERD.md's `EVIDENCE`/`POTENTIAL_PROFILE`/`PROFILE_CLAIM`/
`TAXONOMY`/`TAXONOMY_VERSION`/`TAXONOMY_TERM`).

The core distinction this module encodes (Stage 2 brief §2): RAW DATA
(`Answer`/`CVUpload`, Stage 1) -> EVIDENCE (a normalized, source-referenced
observation) -> PROFILE_CLAIM (a claim ABOUT the person, grounded in one or
more Evidence rows, carrying its own confidence/status) -> POTENTIAL_PROFILE
(a versioned collection of claims). None of these tables ever duplicate raw
answer/CV text -- `Evidence.source_type`/`source_id` reference the original
Stage 1 row (`Answer.id` or `CVUpload.id`); `InterviewMessage` is never used
as a Stage 2 evidence source at all (source precedence -- see
docs/engineering/15_STAGE_2_EVIDENCE_PROFILE_IMPLEMENTATION.md).

Taxonomy content (`TaxonomyTerm` rows) is seed *data*
(app/services/profile/taxonomy.py), not Python enums -- only the small,
stable set of structural claim *dimensions* (`ProfileDimension`, Stage 2
brief §3) is an enum, since that list is architectural, not proprietary
methodology content.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
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


class TaxonomyVersionStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class EvidenceSourceType(str, enum.Enum):
    """Where one Evidence row was extracted from. `native_enum=False`
    (string-backed, no DB CHECK) so future values (`consultant`,
    `external` -- Stage 2 brief §4, not implemented yet) are additive data,
    never a migration."""

    STRUCTURED_ANSWER = "structured_answer"
    OPEN_ANSWER = "open_answer"
    CV = "cv"
    DERIVED = "derived"


class ProfileDimension(str, enum.Enum):
    """The structural claim categories Stage 2 must support (brief §3) --
    a stable architectural list, not methodology content. The actual
    *terms* within a dimension (e.g. which specific strength) are seeded
    `TaxonomyTerm` rows, never hardcoded here."""

    STRENGTH = "strength"
    INTEREST = "interest"
    VALUE = "value"
    MOTIVATION = "motivation"
    SKILL = "skill"
    TRAIT = "trait"
    WORK_PREFERENCE = "work_preference"
    CONSTRAINT = "constraint"
    GOAL = "goal"
    EXPERIENCE = "experience"
    CONTEXTUAL_FACTOR = "contextual_factor"


class ClaimStatus(str, enum.Enum):
    """Confidence is about evidentiary grounding, never about fit (Stage 2
    brief §8) -- these four states describe how well-supported a claim is,
    nothing else."""

    SUPPORTED = "supported"
    HYPOTHESIS = "hypothesis"
    CONTRADICTED = "contradicted"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class ProfileGenerationStatus(str, enum.Enum):
    """One `PotentialProfile` row's own generation lifecycle -- distinct
    from `InterviewSession.status` (see the module docstring in
    app/services/profile/generation.py for how the two relate)."""

    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class Taxonomy(Base):
    """One category of versioned vocabulary (e.g. "potential_dimensions").
    Mirrors `docs/architecture/02_ERD.md`'s `TAXONOMY`/`TAXONOMY_VERSION`/
    `TAXONOMY_TERM` exactly -- no parallel taxonomy system."""

    __tablename__ = "taxonomies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    versions: Mapped[list["TaxonomyVersion"]] = relationship(back_populates="taxonomy")


class TaxonomyVersion(Base):
    __tablename__ = "taxonomy_versions"
    __table_args__ = (UniqueConstraint("taxonomy_id", "version", name="uq_taxonomy_version_number"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    taxonomy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("taxonomies.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[TaxonomyVersionStatus] = mapped_column(
        Enum(TaxonomyVersionStatus, native_enum=False), default=TaxonomyVersionStatus.DRAFT
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    taxonomy: Mapped["Taxonomy"] = relationship(back_populates="versions")
    terms: Mapped[list["TaxonomyTerm"]] = relationship(back_populates="taxonomy_version")


class TaxonomyTerm(Base):
    __tablename__ = "taxonomy_terms"
    __table_args__ = (UniqueConstraint("taxonomy_version_id", "term_key", name="uq_taxonomy_term_key_per_version"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    taxonomy_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("taxonomy_versions.id"), index=True)
    parent_term_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("taxonomy_terms.id"))
    term_key: Mapped[str] = mapped_column(String(128))
    label_uk: Mapped[str] = mapped_column(String(255))
    label_en: Mapped[str | None] = mapped_column(String(255))
    dimension: Mapped[str | None] = mapped_column(String(32))  # ProfileDimension.value, informational/query-only
    term_metadata: Mapped[dict | None] = mapped_column(JSON)

    taxonomy_version: Mapped["TaxonomyVersion"] = relationship(back_populates="terms")


class Evidence(Base):
    """A normalized, source-referenced observation -- NOT a claim about the
    person (Stage 2 brief §2/§5: "Evidence != Claim"). Never duplicates raw
    answer/CV text; `source_type` + `source_id` point back to the Stage 1
    row (`Answer.id` or `CVUpload.id`) that produced it. `session_id` is
    the "profile-generation context" the brief requires -- evidence is
    extracted once per session and reused across profile regenerations,
    not re-extracted per profile version.

    `UNIQUE(session_id, source_type, source_id, evidence_type)` makes
    evidence extraction idempotent: re-running extraction over the same
    session never creates duplicate evidence for the same (source,
    evidence_type) pair."""

    __tablename__ = "evidence"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "source_type", "source_id", "evidence_type", name="uq_evidence_source_per_type"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity_users.id"), index=True)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("interview_sessions.id"), index=True)
    source_type: Mapped[EvidenceSourceType] = mapped_column(Enum(EvidenceSourceType, native_enum=False))
    # Polymorphic reference (Answer.id or CVUpload.id depending on
    # source_type) -- deliberately not a DB-level FK to either table, same
    # rationale as the ERD's EVIDENCE.source_ref.
    source_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), index=True)
    evidence_type: Mapped[str] = mapped_column(String(64))  # e.g. "leadership_signal" -- a TaxonomyTerm.term_key
    taxonomy_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("taxonomy_versions.id"))
    normalized_text: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    extraction_method: Mapped[str] = mapped_column(String(32))  # "deterministic" | "llm_extraction"
    trace_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    claim_links: Mapped[list["ProfileClaimEvidence"]] = relationship(back_populates="evidence")


class PotentialProfile(Base):
    """One versioned generation attempt. Immutable once its status leaves
    `GENERATING`: a regeneration is a new row (`version` = previous max + 1
    for this user), never an edit to an existing one. `is_current` marks
    the one profile a reader should treat as authoritative for this user
    -- enforced to be at most one via a partial unique index, the same
    idiom already used for `uq_one_unfinished_session_per_user` in Stage
    1. A FAILED attempt keeps its row (audit trail) and is never current.
    """

    __tablename__ = "potential_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", "version", name="uq_potential_profile_user_version"),
        Index(
            "uq_one_current_profile_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("is_current = true"),
            sqlite_where=text("is_current = 1"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity_users.id"), index=True)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("interview_sessions.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[ProfileGenerationStatus] = mapped_column(
        Enum(ProfileGenerationStatus, native_enum=False), default=ProfileGenerationStatus.GENERATING, index=True
    )
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    methodology_version: Mapped[str] = mapped_column(String(64))  # e.g. "potential_dimensions:v1"
    prompt_version: Mapped[str] = mapped_column(String(64))  # profile-synthesis prompt tag
    trace_id: Mapped[str | None] = mapped_column(String(64))
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("potential_profiles.id"))
    summary_text: Mapped[str | None] = mapped_column(Text)
    summary_locale: Mapped[str | None] = mapped_column(String(8))
    failure_reason: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    claims: Mapped[list["ProfileClaim"]] = relationship(back_populates="profile", order_by="ProfileClaim.created_at")


class ProfileClaim(Base):
    """A claim ABOUT the person, grounded in one or more `Evidence` rows
    via `ProfileClaimEvidence` -- never the same thing as evidence itself.
    `superseded_by_claim_id`/`correction_reason` are unused by Stage 2
    logic but exist so a future (Stage 3) human-correction workflow
    doesn't need a schema migration to represent "AI claim -> human
    correction -> final claim -> reason" (brief §20)."""

    __tablename__ = "profile_claims"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("potential_profiles.id"), index=True)
    dimension: Mapped[ProfileDimension] = mapped_column(Enum(ProfileDimension, native_enum=False), index=True)
    taxonomy_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("taxonomy_versions.id"))
    term_key: Mapped[str | None] = mapped_column(String(128))
    label: Mapped[str] = mapped_column(String(255))
    normalized_value: Mapped[str] = mapped_column(Text)
    score: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    status: Mapped[ClaimStatus] = mapped_column(Enum(ClaimStatus, native_enum=False), index=True)
    generated_by: Mapped[str] = mapped_column(String(64))  # prompt_version, or "consultant:<admin_id>" later
    trace_id: Mapped[str | None] = mapped_column(String(64))
    superseded_by_claim_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("profile_claims.id"))
    correction_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    profile: Mapped["PotentialProfile"] = relationship(back_populates="claims")
    evidence_links: Mapped[list["ProfileClaimEvidence"]] = relationship(back_populates="claim")


class ProfileClaimEvidence(Base):
    """Many-to-many: one claim can cite multiple evidence items, one
    evidence item can support multiple claims. This is the concrete
    mechanism behind "why do we think this is true?" (brief §6)."""

    __tablename__ = "profile_claim_evidence"
    __table_args__ = (UniqueConstraint("claim_id", "evidence_id", name="uq_claim_evidence_pair"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profile_claims.id"), index=True)
    evidence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evidence.id"), index=True)

    claim: Mapped["ProfileClaim"] = relationship(back_populates="evidence_links")
    evidence: Mapped["Evidence"] = relationship(back_populates="claim_links")
