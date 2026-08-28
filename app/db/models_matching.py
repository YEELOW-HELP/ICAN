"""Matching V1 M4 -- deterministic user x career matching results (Founder
Review "M4 GO", 2026-08-28).

Deliberately NOT built on Stage 3B's `DirectionRun`/`Direction`/
`OutputFamily` (`models_direction.py`) -- that family's `OutputFamily`
enum is hardcoded to the OLD four outputs (POTENTIAL_FIT/GOAL_ALIGNMENT/
TRANSITION_FEASIBILITY/EVIDENCE_CONFIDENCE) and its whole shape assumes
claim-based, potentially-AI-derived scoring. Reusing it for the NEW
five-output Matching V1 model (Interest/Work Style/Values Fit +
Feasibility + Match Coverage) would force a reinterpretation of historical
columns Founder Review explicitly forbade (§16). This module is a wholly
separate, additive family that reuses only `ScoreComponentStatus`'s
existing shape convention (SCORED/INSUFFICIENT_DATA/NOT_APPLICABLE),
extended with `LOW_DIFFERENTIATION`.

`MatchingResult` (one pairwise user-profile x career-vector result) ->
`MatchFamilyResult` (Interest/Work Style/Values, one row each) +
`MatchFeasibilityResult` (one row, different shape -- barrier lists, not a
single score). Every result pins the full version chain (Founder Review
§15) and is immutable once created -- a changed input version produces a
NEW `MatchingResult`, never an edit.

Zero-AI: no module feeding this table family may call `app.ai_gateway`.
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
    Integer,
    String,
    Uuid,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models_basic_assessment import ScaleFamily


def _str_enum(enum_cls: type[enum.Enum]):
    """Same rationale as every other Matching V1 model module."""

    return Enum(enum_cls, native_enum=False, values_callable=lambda obj: [e.value for e in obj])


class FitStatus(str, enum.Enum):
    """Extends the existing `ScoreComponentStatus` shape (Stage 3B) with
    `LOW_DIFFERENTIATION` -- the guarded-cosine failure state (Founder
    Review §1/§3/§4). `INSUFFICIENT_DATA` != a low score; `NOT_APPLICABLE`
    is reserved for a family that structurally cannot apply (unused by M4
    itself, kept for shape-completeness/future use)."""

    SCORED = "scored"
    INSUFFICIENT_DATA = "insufficient_data"
    LOW_DIFFERENTIATION = "low_differentiation"
    NOT_APPLICABLE = "not_applicable"


class FeasibilityStatus(str, enum.Enum):
    FEASIBLE = "feasible"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    INSUFFICIENT_DATA = "insufficient_data"


class FitBand(str, enum.Enum):
    """PROVISIONAL/EXPERIMENTAL cutoffs, per `MNP_GOLDEN_TEST_V0.1.md` §23
    -- never claimed calibrated. `INSUFFICIENT_DATA`/`LOW_DIFFERENTIATION`
    never map to a band at all (band stays NULL for those statuses)."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MatchingResult(Base):
    """One pairwise (user profile x career vector) result. Immutable --
    `UniqueConstraint` on the full version chain makes a re-run with
    identical inputs idempotent (returns the existing row); a genuinely
    changed input (new `DeterministicProfile`, new `CareerMatchingProfile`
    version, new engine/config version) always produces a NEW row."""

    __tablename__ = "matching_results"
    __table_args__ = (
        UniqueConstraint(
            "profile_id", "career_matching_profile_id", "matching_engine_version", "config_version",
            name="uq_matching_result_pair_engine_config",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("deterministic_profiles.id"), index=True)
    career_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("careers.id"), index=True)
    career_matching_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("career_matching_profiles.id"), index=True
    )

    # Full version-pin chain (Founder Review §15) -- every field snapshotted
    # at calculation time, never re-derived from "whatever is current now".
    assessment_version: Mapped[str] = mapped_column(String(64))
    profile_engine_version: Mapped[str] = mapped_column(String(32))
    matching_methodology_version: Mapped[str] = mapped_column(String(32))
    career_vector_version: Mapped[str] = mapped_column(String(32))
    career_source_version: Mapped[str] = mapped_column(String(32))
    matching_engine_version: Mapped[str] = mapped_column(String(32))
    metric_version: Mapped[str] = mapped_column(String(32))
    config_version: Mapped[str] = mapped_column(String(32))

    eligible: Mapped[bool] = mapped_column(Boolean)  # False iff feasibility.status == BLOCKED
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    family_results: Mapped[list["MatchFamilyResult"]] = relationship(back_populates="matching_result")
    feasibility_result: Mapped["MatchFeasibilityResult | None"] = relationship(
        back_populates="matching_result", uselist=False
    )


class MatchFamilyResult(Base):
    """One Fit family's (Interest/Work Style/Values) result for one
    `MatchingResult`. Never persists the full raw vectors -- only counts,
    the comparable scale-key list, and the computed statistics, per
    Founder Review §4 ("do not persist redundant raw private data if
    references are enough"). The full user/career vectors remain
    reconstructable on demand from `ProfileScaleResult`/
    `CareerMatchingComponent` via `profile_id`/`career_matching_profile_id`
    on the parent `MatchingResult` -- this table is the audit trail of
    *which* dimensions were compared and what the guard concluded, not a
    second copy of the data itself."""

    __tablename__ = "match_family_results"
    __table_args__ = (UniqueConstraint("matching_result_id", "scale_family", name="uq_match_family_result_family"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    matching_result_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("matching_results.id"), index=True)
    scale_family: Mapped[ScaleFamily] = mapped_column(_str_enum(ScaleFamily), index=True)  # RIASEC/WORK_STYLE/WORK_VALUES
    status: Mapped[FitStatus] = mapped_column(_str_enum(FitStatus))
    raw_score: Mapped[float | None] = mapped_column(Float)  # cosine similarity, [0,1]; NULL unless status=SCORED
    band: Mapped[FitBand | None] = mapped_column(_str_enum(FitBand))  # NULL unless status=SCORED
    user_component_count: Mapped[int] = mapped_column(Integer)
    career_component_count: Mapped[int] = mapped_column(Integer)
    comparable_component_count: Mapped[int] = mapped_column(Integer)
    comparable_scale_keys: Mapped[list] = mapped_column(JSON)  # list[str] -- the explainability trace
    coverage_ratio: Mapped[float] = mapped_column(Float)  # comparable / user_component_count
    provisional: Mapped[bool] = mapped_column(Boolean)
    user_stdev: Mapped[float | None] = mapped_column(Float)
    career_stdev: Mapped[float | None] = mapped_column(Float)
    differentiation_threshold: Mapped[float] = mapped_column(Float)  # snapshot of config at calc time

    matching_result: Mapped["MatchingResult"] = relationship(back_populates="family_results")


class MatchFeasibilityResult(Base):
    """One `MatchingResult`'s Transition Feasibility result -- a
    different shape than `MatchFamilyResult` by design (barrier lists,
    not a single comparable-vector score)."""

    __tablename__ = "match_feasibility_results"
    __table_args__ = (UniqueConstraint("matching_result_id", name="uq_match_feasibility_result_pair"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    matching_result_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("matching_results.id"), index=True)
    status: Mapped[FeasibilityStatus] = mapped_column(_str_enum(FeasibilityStatus))
    raw_score: Mapped[float | None] = mapped_column(Float)  # NULL for BLOCKED/INSUFFICIENT_DATA
    band: Mapped[FitBand | None] = mapped_column(_str_enum(FitBand))
    hard_barriers: Mapped[list] = mapped_column(JSON)  # list[str]
    soft_barriers: Mapped[list] = mapped_column(JSON)  # list[str]
    information_gaps: Mapped[list] = mapped_column(JSON)  # list[str]
    skills_to_verify: Mapped[list] = mapped_column(JSON)  # list[{"label": str, "status": "unknown"}]

    matching_result: Mapped["MatchingResult"] = relationship(back_populates="feasibility_result")
