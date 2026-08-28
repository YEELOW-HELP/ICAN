"""Matching V1 M2 -- deterministic BASIC profile persistence (Founder
Review "M2 GO", 2026-08-28).

Deliberately NOT built on `app/db/models_profile.py`'s `PotentialProfile`/
`ProfileClaim`/`Evidence` -- that family's whole shape (evidence-grounded
claims, `extraction_method in {"deterministic","llm_extraction"}`,
`prompt_version`) is a PRO Hybrid / AI-provenance model, and mixing BASIC's
zero-AI, pure-Likert-arithmetic provenance into it would blur exactly the
distinction Founder Review asked to keep sharp. This module is a wholly
separate, additive table family: `DeterministicProfile` (audited from
`PotentialProfile`'s "one row per generation, versioned, `is_current`
partial-unique-per-user" idiom, reused deliberately for consistency) +
`ProfileScaleResult` (one row per scored Likert scale) +
`ProfileVectorDifferentiation` (one row per vector family's differentiation
check) + `ProfileStructuredContext` (Goals/Constraints/Experience,
persisted as structured facts, never invented Likert scores).

Zero-AI: this module does not import `app.ai_gateway` or any PRO Hybrid
extraction/synthesis service (enforced by
`tests/test_basic_profile_zero_ai.py`, the same AST + behavioral pattern
as M1's `test_basic_assessment_zero_ai.py`).
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models_basic_assessment import MappingStatus, MatchingUsage, ResponseType, ScaleFamily


def _str_enum(enum_cls: type[enum.Enum]):
    """Same rationale as `models_basic_assessment.py::_str_enum` --
    without `values_callable`, SQLAlchemy's `Enum(..., native_enum=False)`
    stores a member's `.name` ("NORMAL"), not its `.value` ("normal"),
    which would silently break every plain string comparison in this
    module's own services/tests."""

    return Enum(enum_cls, native_enum=False, values_callable=lambda obj: [e.value for e in obj])


class ProfileStatus(str, enum.Enum):
    READY = "ready"


class CoverageBand(str, enum.Enum):
    """Golden Test doc §15 three-band model, applied to the schema-driven
    Coverage ratio (never a hardcoded 29 in the denominator -- see
    `app/services/basic_profile/calculation.py`)."""

    FULL = "full"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"


class DifferentiationState(str, enum.Enum):
    """Per-vector-family data-quality flag, per the Founder-approved
    minimum-dispersion guard (`MNP_MATCHING_METRIC_BENCHMARK_V0.1.md` §6,
    `stdev >= 0.10`, PROVISIONAL/VERSIONED/CONFIGURABLE/EXPERIMENTAL).
    Never a Fit score, never blended into one -- this is a data-quality
    signal about the USER'S OWN profile, computed before any career
    comparison exists."""

    NORMAL = "normal"
    LOW_DIFFERENTIATION = "low_differentiation"
    INSUFFICIENT_DATA = "insufficient_data"


class DeterministicProfile(Base):
    """One versioned deterministic-calculation attempt over one
    `BasicAssessmentAttempt`. Immutable once created -- a recalculation
    with the SAME `profile_engine_version` is idempotent (returns the
    existing row, per `UniqueConstraint(attempt_id, profile_engine_version)`
    below); a recalculation after a genuine engine/methodology version bump
    creates a NEW row and supersedes the old one via `supersedes_id` +
    `is_current`, mirroring `PotentialProfile`'s exact versioning idiom
    (audited from `models_profile.py` before designing this table, per
    Founder Review instruction 11)."""

    __tablename__ = "deterministic_profiles"
    __table_args__ = (
        UniqueConstraint(
            "attempt_id", "profile_engine_version", name="uq_deterministic_profile_attempt_engine_version"
        ),
        Index(
            "uq_one_current_basic_profile_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("is_current"),
            sqlite_where=text("is_current"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity_users.id"), index=True)
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("basic_assessment_attempts.id"), index=True)
    definition_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessment_definitions.id"), index=True)
    assessment_code: Mapped[str] = mapped_column(String(64))  # e.g. "matching_v1_alpha_long_form"
    assessment_version: Mapped[str] = mapped_column(String(64))  # e.g. "matching_v1_alpha_long_form_v0.1"
    methodology_version: Mapped[str] = mapped_column(String(32))  # e.g. "golden_test_v0.1"
    profile_engine_version: Mapped[str] = mapped_column(String(32))  # e.g. "basic_profile_engine_v0.1"
    status: Mapped[ProfileStatus] = mapped_column(_str_enum(ProfileStatus), default=ProfileStatus.READY)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("deterministic_profiles.id"))
    coverage: Mapped[float] = mapped_column(Float)  # scored_required_scales / enabled_required_scales, [0,1]
    coverage_band: Mapped[CoverageBand] = mapped_column(_str_enum(CoverageBand))
    context_completeness: Mapped[float] = mapped_column(Float)  # Goals/Constraints/Experience, SEPARATE from coverage
    differentiation_state: Mapped[DifferentiationState] = mapped_column(
        _str_enum(DifferentiationState)
    )  # worst-case across the 4 vector families -- see ProfileVectorDifferentiation for per-family detail
    interest_ordering: Mapped[list | None] = mapped_column(JSON)  # RIASEC scale_keys, descending, deterministic tie-break
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    scale_results: Mapped[list["ProfileScaleResult"]] = relationship(back_populates="profile")
    differentiations: Mapped[list["ProfileVectorDifferentiation"]] = relationship(back_populates="profile")
    structured_context: Mapped[list["ProfileStructuredContext"]] = relationship(back_populates="profile")


class ProfileScaleResult(Base):
    """One scored Likert scale's result (RIASEC/Work Style/Work Values/
    Work Environment). PROFILE_ONLY scales get a row here exactly like
    MATCH_ENABLED ones -- `matching_usage` is carried as provenance
    metadata, never a reason to omit a measured user characteristic from
    their own profile (Founder Review §5/§6)."""

    __tablename__ = "profile_scale_results"
    __table_args__ = (UniqueConstraint("profile_id", "scale_id", name="uq_profile_scale_result_scale"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("deterministic_profiles.id"), index=True)
    scale_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessment_scales.id"), index=True)
    scale_family: Mapped[ScaleFamily] = mapped_column(_str_enum(ScaleFamily), index=True)
    scale_key: Mapped[str] = mapped_column(String(64))
    raw_mean: Mapped[float | None] = mapped_column(Float)  # mean of reverse-corrected 1-5 responses; null if UNSCORED
    normalized_value: Mapped[float | None] = mapped_column(Float)  # (raw_mean-1)/4 in [0,1]; null if UNSCORED
    items_answered: Mapped[int] = mapped_column(Integer)
    items_total: Mapped[int] = mapped_column(Integer)
    sufficiently_answered: Mapped[bool] = mapped_column(Boolean)  # Golden Test §7 threshold
    # Denormalized scale-metadata snapshot, exactly as it stood at calc time --
    # never re-derived from AssessmentScale at read time, so a later
    # methodology revision never silently rewrites a historical profile's
    # own provenance.
    mapping_status: Mapped[MappingStatus] = mapped_column(_str_enum(MappingStatus))
    matching_usage: Mapped[MatchingUsage] = mapped_column(_str_enum(MatchingUsage))
    provisional: Mapped[bool] = mapped_column(Boolean)

    profile: Mapped["DeterministicProfile"] = relationship(back_populates="scale_results")


class ProfileVectorDifferentiation(Base):
    """One vector family's (RIASEC/Work Style/Work Values/Work
    Environment) minimum-dispersion check result. `threshold` is snapshot
    at calc time from config (never hardcoded twice) so a later threshold
    change is visible per-profile, never silently reinterpreted."""

    __tablename__ = "profile_vector_differentiation"
    __table_args__ = (UniqueConstraint("profile_id", "scale_family", name="uq_profile_vector_diff_family"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("deterministic_profiles.id"), index=True)
    scale_family: Mapped[ScaleFamily] = mapped_column(_str_enum(ScaleFamily))
    stdev: Mapped[float | None] = mapped_column(Float)  # null when INSUFFICIENT_DATA (vector not computable)
    threshold: Mapped[float] = mapped_column(Float)
    state: Mapped[DifferentiationState] = mapped_column(_str_enum(DifferentiationState))

    profile: Mapped["DeterministicProfile"] = relationship(back_populates="differentiations")


class ProfileStructuredContext(Base):
    """One Goals/Constraints/Experience answer, snapshotted as structured
    profile context -- never converted into an invented Likert score,
    never assigned a hard/soft severity beyond what the raw option value
    itself already encodes (Founder Review §8: "Do NOT infer hard
    constraints from confidence or free text")."""

    __tablename__ = "profile_structured_context"
    __table_args__ = (UniqueConstraint("profile_id", "item_id", name="uq_profile_structured_context_item"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("deterministic_profiles.id"), index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessment_items.id"), index=True)
    scale_family: Mapped[ScaleFamily] = mapped_column(_str_enum(ScaleFamily), index=True)
    scale_key: Mapped[str] = mapped_column(String(64))
    response_type: Mapped[ResponseType] = mapped_column(_str_enum(ResponseType))
    numeric_value: Mapped[int | None] = mapped_column(Integer)
    boolean_value: Mapped[bool | None] = mapped_column(Boolean)
    selected_option_keys: Mapped[list | None] = mapped_column(JSON)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    profile: Mapped["DeterministicProfile"] = relationship(back_populates="structured_context")
