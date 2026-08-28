"""Matching V1 M3 -- Career Vector Knowledge Base (Founder Review "M3 GO",
2026-08-28).

Additive layer BESIDE the existing Stage 3A `Career`/`CareerRequirement`/
`CareerWorkContext`/`CareerSkill`/`CareerFact` (`models_knowledge.py`) --
`Career.code` remains the sole internal canonical identity, never
replaced, never rewritten. `CareerExternalMapping` is the ONLY place an
external taxonomy code (O*NET-SOC, later ESCO) is recorded; it is a
many-to-many crosswalk, never a primary key, never assumed 1:1.

`CareerMatchingProfile` -> `CareerMatchingComponent` is the career-side
mirror of `DeterministicProfile` -> `ProfileScaleResult` (M2), reusing the
SAME `ScaleFamily`/`MappingStatus`/`MatchingUsage` enums from
`models_basic_assessment.py` so both sides of a future user<->career
comparison (M4) speak the identical vocabulary. A `CareerMatchingComponent`
is NEVER created for a PROFILE_ONLY scale (Founder Review §8/§9, hard
invariant) -- enforced by `app/services/career_kb/vectors.py`'s single
gate function, not re-decided per-component.

Zero-AI: no module feeding this table family may reconstruct an O*NET
value via AI -- every `CareerMatchingComponent.normalized_value` traces to
either a real O*NET source record (`source_element_id`/`source_raw_value`
populated) or is left NULL (`UNKNOWN != zero`, Founder Review §4).
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models_basic_assessment import MappingStatus, MatchingUsage, ScaleFamily


def _str_enum(enum_cls: type[enum.Enum]):
    """Same rationale as `models_basic_assessment.py`/`models_basic_profile.py`
    -- without `values_callable`, SQLAlchemy's `Enum(..., native_enum=False)`
    stores a member's `.name`, not its `.value`."""

    return Enum(enum_cls, native_enum=False, values_callable=lambda obj: [e.value for e in obj])


class ExternalSourceSystem(str, enum.Enum):
    """Only ONET is populated in M3 -- Work.ua is reference-only per the
    binding Founder rule (`MNP_WORKUA_DATA_USE_DECISION_V0.1.md`); no
    Work.ua source_system value exists here because none may be imported
    yet. ESCO is a documented future extension point, not implemented."""

    ONET = "onet"


class ExternalMappingStatus(str, enum.Enum):
    """CONFIRMED/PROVISIONAL both feed live vector computation (PROVISIONAL
    visibly flagged); UNMAPPED is a deliberate, auditable "we looked and
    found no defensible mapping" statement -- never silently absent.
    REJECTED preserves a mapping attempt a curator explicitly rejected,
    for audit history."""

    CONFIRMED = "confirmed"
    PROVISIONAL = "provisional"
    UNMAPPED = "unmapped"
    REJECTED = "rejected"


class CareerExternalMapping(Base):
    """Many-to-many crosswalk between one `Career` and zero-or-more
    external taxonomy codes. `external_code` is NULL only for a
    `mapping_status=UNMAPPED` row (a deliberate marker, not an
    unpopulated field) or `REJECTED` (the code that was rejected is kept
    for audit). `Career.code` is never touched by this table."""

    __tablename__ = "career_external_mappings"
    __table_args__ = (
        UniqueConstraint(
            "career_id", "source_system", "external_code", name="uq_career_external_mapping_code"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("careers.id"), index=True)
    source_system: Mapped[ExternalSourceSystem] = mapped_column(_str_enum(ExternalSourceSystem), index=True)
    external_code: Mapped[str | None] = mapped_column(String(64))  # e.g. O*NET-SOC "15-1252.00"; NULL for UNMAPPED
    external_label: Mapped[str | None] = mapped_column(String(255))  # e.g. "Software Developers"
    external_url: Mapped[str | None] = mapped_column(String(1000))
    mapping_status: Mapped[ExternalMappingStatus] = mapped_column(_str_enum(ExternalMappingStatus), index=True)
    mapping_version: Mapped[str] = mapped_column(String(32))
    confidence: Mapped[float | None] = mapped_column(Float)  # nullable until reviewed
    reviewed_by: Mapped[str | None] = mapped_column(String(255))  # curator identifier, free text for M3
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    career: Mapped["Career"] = relationship()  # noqa: F821 -- Career lives in models_knowledge.py


class CareerMatchingProfile(Base):
    """One versioned career-vector generation for one `Career`. Immutable
    once created; a changed source/mapping/methodology version creates a
    NEW row and supersedes the prior `is_current` one -- exact mirror of
    `DeterministicProfile`'s (M2) versioning idiom, applied to the career
    side."""

    __tablename__ = "career_matching_profiles"
    __table_args__ = (
        UniqueConstraint(
            "career_id", "career_vector_version", "mapping_version", "source_version",
            name="uq_career_matching_profile_versions",
        ),
        Index(
            "uq_one_current_career_matching_profile",
            "career_id",
            unique=True,
            postgresql_where=text("is_current"),
            sqlite_where=text("is_current"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("careers.id"), index=True)
    profile_version: Mapped[int] = mapped_column(Integer)  # 1, 2, 3... per career, monotonically increasing
    career_vector_version: Mapped[str] = mapped_column(String(32))  # e.g. "career_vector_v0.1"
    matching_methodology_version: Mapped[str] = mapped_column(String(32))  # e.g. "golden_test_v0.1"
    source_version: Mapped[str] = mapped_column(String(32))  # e.g. "onet_30.3"
    mapping_version: Mapped[str] = mapped_column(String(32))  # e.g. "mnp_scale_to_onet_mapping_v0.1"
    localization_version: Mapped[str] = mapped_column(String(32), default="mnp_localization_v0.1")
    provisional: Mapped[bool] = mapped_column(Boolean, default=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("career_matching_profiles.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    career: Mapped["Career"] = relationship()  # noqa: F821
    components: Mapped[list["CareerMatchingComponent"]] = relationship(back_populates="profile")


class CareerMatchingComponent(Base):
    """One scale's career-side value. NEVER created for a PROFILE_ONLY
    scale (`matching_usage` is always `MATCH_ENABLED` here by construction
    -- the column exists for symmetry/auditability with
    `ProfileScaleResult`, not because a PROFILE_ONLY row is ever inserted).
    `normalized_value IS NULL` means the component is genuinely
    unavailable (no defensible source data) -- never defaulted to 0 or any
    other fabricated midpoint."""

    __tablename__ = "career_matching_components"
    __table_args__ = (
        UniqueConstraint("profile_id", "scale_family", "scale_key", name="uq_career_matching_component_scale"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("career_matching_profiles.id"), index=True)
    scale_family: Mapped[ScaleFamily] = mapped_column(_str_enum(ScaleFamily), index=True)
    scale_key: Mapped[str] = mapped_column(String(64))
    normalized_value: Mapped[float | None] = mapped_column(Float)  # [0,1] or NULL (unavailable, never 0)
    mapping_status: Mapped[MappingStatus] = mapped_column(_str_enum(MappingStatus))
    matching_usage: Mapped[MatchingUsage] = mapped_column(_str_enum(MatchingUsage))  # always MATCH_ENABLED
    provisional: Mapped[bool] = mapped_column(Boolean, default=True)
    source_system: Mapped[str | None] = mapped_column(String(32))  # "onet" | None if MNP_ONLY-derived (never here)
    source_element_id: Mapped[str | None] = mapped_column(String(64))  # e.g. O*NET-SOC code contributing this value
    source_element_name: Mapped[str | None] = mapped_column(String(255))  # e.g. "Interests — Investigative"
    source_raw_value: Mapped[str | None] = mapped_column(String(64))  # e.g. "IC" (Holland code) or "5" (Job Zone)
    transformation_version: Mapped[str] = mapped_column(String(32))  # e.g. "onet_holland_to_riasec_v0.1"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profile: Mapped["CareerMatchingProfile"] = relationship(back_populates="components")
