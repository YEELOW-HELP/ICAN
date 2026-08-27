"""Stage 3B: Direction Intelligence -- four-output Direction Evaluation
Model (Founder decisions A-M + Research Wave A addendum N-Q).

This module is the arrow that connects the two previously-separate bounded
domains: the Human Potential Profile (Stage 2, `potential_profiles` /
`profile_claims`) and the Career Knowledge Base (Stage 3A, `careers` /
`knowledge_base_versions`). It legitimately references both -- comparing
them is its whole job -- but it never copies raw answer/CV text; it works
from `ProfileClaim`s and curated `Career` data only.

## The four outputs (Founder decision N) -- NEVER one blended score

Per (person, career) the engine produces four structurally separate,
separately stored outputs:

  1. Potential Fit          -- how well the career matches the person
  2. Goal Alignment         -- how well it matches where they want to go
  3. Transition Feasibility -- how realistic the move is NOW
  4. Evidence Confidence    -- how reliable/sufficient the evidence is

Missing data reduces coverage/confidence, never Potential Fit. No public
calibrated percentage. Raw 0..1 values exist only as versioned,
explicitly-experimental internals.

## Ranking (Founder decisions O + G) -- a SEPARATE versioned layer

`RankingPolicy` is a distinct versioned entity. It never defines a hidden
composite score. See `methodology_lab/04_CAREER_FIT_MODEL/MNP_RANKING_POLICY_V0.1.md`.

## Naming (Founder decision M1)

`Direction*` is the V1 vocabulary; the legacy ERD `SCENARIO` /
`SCENARIO_SCORE` / `DIRECTION_DECISION` names are superseded for this
slice.

## Slice 1 exercise status (superseded by Slice 2 below)

- `ScoringConfig`, `RankingPolicy` -- EXERCISED (versioned experimental config).
- `ProfileConstraint` -- EXERCISED via the deterministic derivation in
  `app/services/direction/constraints.py`.
- `DirectionRun` / `Direction` / `DirectionScoreComponent` /
  `DirectionConstraintCheck` / `ClarificationRequest` -- CREATED, not yet
  written by any orchestrator (Slice 2 scope). Creating them now keeps
  Slice 2 migration-free.

## Slice 2: end-to-end orchestrator (`app/services/direction/pipeline.py`)

`generate_directions()` now writes every table above end-to-end: resolves
the READY `PotentialProfile`, pins every version column on `DirectionRun`,
retrieves candidates through `app/services/knowledge/retrieval.py` only,
evaluates the hard constraint gate, computes all four outputs, applies
`RankingPolicy`, deduplicates exact KB collisions, and persists a
deterministic explanation bundle per recommended `Direction` (see the
`explanation_bundle`/`duplicate_of_career_code`/`dedup_reason`/
`diversity_warning` columns added in the Slice 2 migration).

## Slice 3: Critic + real Goal Alignment + consultant review + narrative

`app/services/direction/critic.py` inspects a completed `DirectionRun`
independently of the orchestrator that produced it and persists
`DirectionCriticFinding` rows (BLOCKER/WARNING/INFO). A run with an
unresolved BLOCKER can never be consultant-approved.
`app/services/direction/review.py` implements the `DirectionReview` state
machine (PENDING_REVIEW -> APPROVED | CHANGES_REQUESTED | REJECTED) plus
append-only `ConsultantCorrection` rows -- the original `DirectionRun`/
`Direction` rows are NEVER mutated by a review or correction.
`app/services/direction/narrative.py` adds an optional, tightly-grounded
LLM narrative layer (input: only the deterministic `explanation_bundle`,
never raw CV/answer text) on top of `Direction.narrative_text`/
`narrative_locale`/`narrative_trace_id` (already present since Slice 1)
plus the new `narrative_structured` column below. No `ai_traces` table is
introduced by this either -- narrative provenance stays exactly the
existing trace_id-string pattern.
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


class PolicyStatus(str, enum.Enum):
    """Shared lifecycle for `ScoringConfig` and `RankingPolicy` -- one
    incrementing version, at most one ACTIVE, immutable once referenced by
    a run (the KB/profile versioning idiom)."""

    DRAFT = "draft"
    ACTIVE = "active"
    SUPERSEDED = "superseded"


class OutputFamily(str, enum.Enum):
    """The four separate Direction outputs (Founder decision N). Score
    components are tagged with which output they contribute to; the same
    profile claim may contribute to more than one family through different
    deterministic calculations."""

    POTENTIAL_FIT = "potential_fit"
    GOAL_ALIGNMENT = "goal_alignment"
    TRANSITION_FEASIBILITY = "transition_feasibility"
    EVIDENCE_CONFIDENCE = "evidence_confidence"


class DirectionRunStatus(str, enum.Enum):
    """`INSUFFICIENT_INFORMATION` is a first-class terminal outcome, not a
    failure (Founder decision H): the profile did not clear the minimum
    threshold, so no directions are produced -- and none are manufactured
    to fill the gap."""

    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"
    INSUFFICIENT_INFORMATION = "insufficient_information"


class DirectionPlacement(str, enum.Enum):
    MAIN = "main"
    ALTERNATIVE = "alternative"
    BLOCKED = "blocked"  # failed a confirmed hard constraint -- excluded from eligibility
    NOT_ELIGIBLE = "not_eligible"  # passed the gate but failed a RankingPolicy band gate
    DEDUPED = "deduped"
    UNRANKED = "unranked"  # evaluated, not yet placed


class ScoreComponentStatus(str, enum.Enum):
    """`INSUFFICIENT_DATA` != a low score. A component with no comparable
    structured pair is excluded from family aggregation entirely (Founder
    decision F) -- never counted as a mismatch. `NOT_APPLICABLE` = the
    component structurally does not apply to this career."""

    SCORED = "scored"
    INSUFFICIENT_DATA = "insufficient_data"
    NOT_APPLICABLE = "not_applicable"


class ConstraintCheckResult(str, enum.Enum):
    PASS = "pass"
    BLOCK = "block"
    INSUFFICIENT_DATA = "insufficient_data"


class QualitativeBand(str, enum.Enum):
    """Public/client-facing semantics for every output (Founder decision
    N). The raw 0..1 value is internal + EXPERIMENTAL; only the band is
    shown. `None` (unknown) is NOT `LOW`."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ClarificationReason(str, enum.Enum):
    MISSING_DIMENSION = "missing_dimension"
    LOW_CONFIDENCE_COVERAGE = "low_confidence_coverage"
    UNRESOLVED_CONTRADICTION = "unresolved_contradiction"
    CONSTRAINT_UNCONFIRMED = "constraint_unconfirmed"
    SKILL_VERIFICATION_NEEDED = "skill_verification_needed"  # UNKNOWN required skills (Founder decision P)
    COVERAGE_GAP = "coverage_gap"  # a fit output could not be scored (unknown != LOW)


class ClarificationStatus(str, enum.Enum):
    OPEN = "open"
    ADDRESSED = "addressed"
    DISMISSED = "dismissed"


class CriticSeverity(str, enum.Enum):
    """`BLOCKER` prevents consultant approval (`review.approve_run`
    re-checks this at approval time, never trusting a stale check).
    `WARNING` never blocks approval by itself -- a WARNING is not a
    BLOCKER (Slice 3 test invariant #7)."""

    BLOCKER = "blocker"
    WARNING = "warning"
    INFO = "info"


class ReviewStatus(str, enum.Enum):
    """A `DirectionReview` transitions at most once out of PENDING_REVIEW
    (app/services/direction/review.py owns the state machine, mirroring
    app/services/assessment/state_machine.py's "only one module changes
    this status" discipline). A regeneration never resurrects an old
    review -- it gets a brand new `DirectionReview` row at PENDING_REVIEW
    on the new `DirectionRun`."""

    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"


class CorrectionReasonCode(str, enum.Enum):
    """The exact closed set from the Founder Methodology Contract v0.1
    decision K -- engineering may not add an entry to this set."""

    WRONG_INFERENCE = "wrong_inference"
    MISSING_INFERENCE = "missing_inference"
    WRONG_DIMENSION = "wrong_dimension"
    OVERCONFIDENCE = "overconfidence"
    UNDERCONFIDENCE = "underconfidence"
    CONTRADICTION_MISSED = "contradiction_missed"
    CONSTRAINT_MISSED = "constraint_missed"
    UNSUPPORTED_FACT = "unsupported_fact"
    WRONG_DIRECTION_PRIORITY = "wrong_direction_priority"
    CAREER_KNOWLEDGE_PROBLEM = "career_knowledge_problem"
    EVIDENCE_EXTRACTION_PROBLEM = "evidence_extraction_problem"
    WORDING_ONLY = "wording_only"
    OTHER_WITH_COMMENT = "other_with_comment"


class ScoringConfig(Base):
    """Versioned weights + thresholds for the four-output scoring engine.
    Immutable once any `DirectionRun` references it. `is_experimental=True`
    for every V1 config (Founder decision F): weights are NON-PRODUCTION
    placeholders (all-equal in v0.1) and must never be presented as
    validated. Exactly one row may be ACTIVE (partial unique index).

    `component_weights`   -- {output_family: {component_key: weight}}
    `enabled_components`  -- {output_family: [component_key, ...]}
    `thresholds`          -- flat dict of named cutoffs/limits
    """

    __tablename__ = "scoring_configs"
    __table_args__ = (
        UniqueConstraint("version", name="uq_scoring_config_version"),
        Index(
            "uq_one_active_scoring_config",
            "status",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(128))
    status: Mapped[PolicyStatus] = mapped_column(
        Enum(PolicyStatus, native_enum=False), default=PolicyStatus.DRAFT, index=True
    )
    is_experimental: Mapped[bool] = mapped_column(Boolean, default=True)
    methodology_version: Mapped[str] = mapped_column(String(64))
    component_weights: Mapped[dict] = mapped_column(JSON)
    thresholds: Mapped[dict] = mapped_column(JSON)
    enabled_components: Mapped[dict] = mapped_column(JSON)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )


class RankingPolicy(Base):
    """The SEPARATE versioned decision layer (Founder decisions O + G). It
    never defines a hidden composite score. `policy` (JSON) holds:
    eligibility rules, qualitative band gates, lexicographic sort
    precedence, tie-breakers, MAIN/ALTERNATIVE maxima, missing-output
    semantics, evidence-confidence requirements, dedup/diversity rules.
    Immutable once referenced by a run; exactly one ACTIVE."""

    __tablename__ = "ranking_policies"
    __table_args__ = (
        UniqueConstraint("version", name="uq_ranking_policy_version"),
        Index(
            "uq_one_active_ranking_policy",
            "status",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(128))
    status: Mapped[PolicyStatus] = mapped_column(
        Enum(PolicyStatus, native_enum=False), default=PolicyStatus.DRAFT, index=True
    )
    is_experimental: Mapped[bool] = mapped_column(Boolean, default=True)
    methodology_version: Mapped[str] = mapped_column(String(64))
    policy: Mapped[dict] = mapped_column(JSON)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )


class ProfileConstraint(Base):
    """A structured, matchable projection of a `ProfileClaim(dimension=
    constraint)` -- what the hard-constraint gate reads, since a raw
    `ProfileClaim` carries no hardness flag and no structured value.
    Derived deterministically (app/services/direction/constraints.py) from
    the current profile's constraint-dimension claims; the source claim is
    always preserved, never rewritten.

    `constraint_subtype` is one of the 12 v0.1 subtypes (Founder decision
    Q). `is_hard` / `is_confirmed` default False and are set ONLY by an
    explicit signal -- v0.1 does not classify a constraint as hard from
    assessment text alone (Career Fit / Direction Evaluation Model 5.4)."""

    __tablename__ = "profile_constraints"
    __table_args__ = (
        UniqueConstraint("profile_id", "source_claim_id", "constraint_subtype", name="uq_profile_constraint_identity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("potential_profiles.id"), index=True)
    source_claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profile_claims.id"), index=True)
    constraint_subtype: Mapped[str] = mapped_column(String(32), index=True)
    constraint_taxonomy_version: Mapped[str] = mapped_column(String(64))
    normalized_value: Mapped[str] = mapped_column(Text)
    is_hard: Mapped[bool] = mapped_column(Boolean, default=False)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )


class DirectionRun(Base):
    """One versioned Direction Intelligence generation attempt for a user
    -- the `PotentialProfile` idiom: per-user `version`, at most one
    `is_current`, immutable history, `supersedes_id` chain. Every version
    field needed to answer "why did the system recommend this to this
    person on this date?" is stamped at creation."""

    __tablename__ = "direction_runs"
    __table_args__ = (
        UniqueConstraint("user_id", "version", name="uq_direction_run_user_version"),
        Index(
            "uq_one_current_direction_run_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("is_current = true"),
            sqlite_where=text("is_current = 1"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity_users.id"), index=True)
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("potential_profiles.id"), index=True)
    knowledge_base_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_base_versions.id"), index=True)
    scoring_config_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scoring_configs.id"), index=True)
    ranking_policy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ranking_policies.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[DirectionRunStatus] = mapped_column(
        Enum(DirectionRunStatus, native_enum=False), default=DirectionRunStatus.GENERATING, index=True
    )
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)

    methodology_version: Mapped[str] = mapped_column(String(64))
    direction_engine_version: Mapped[str] = mapped_column(String(64))
    direction_evaluation_model_version: Mapped[str] = mapped_column(String(64))
    ranking_policy_version: Mapped[str] = mapped_column(String(64))
    dimension_mapping_version: Mapped[str] = mapped_column(String(64))
    subdimension_taxonomy_version: Mapped[str] = mapped_column(String(64))
    constraint_taxonomy_version: Mapped[str] = mapped_column(String(64))
    evidence_standard_version: Mapped[str] = mapped_column(String(64))

    candidate_prompt_version: Mapped[str | None] = mapped_column(String(64))
    narrative_prompt_version: Mapped[str | None] = mapped_column(String(64))
    critic_prompt_version: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(64))
    trace_ids: Mapped[list | None] = mapped_column(JSON)

    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("direction_runs.id"))
    failure_reason: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    directions: Mapped[list["Direction"]] = relationship(back_populates="run")
    clarification_requests: Mapped[list["ClarificationRequest"]] = relationship(back_populates="run")


class Direction(Base):
    """One candidate career evaluated in a run. The four outputs are stored
    as four independent blocks -- never combined into one number before
    all are persisted (Founder decision N). `career_code` is denormalized
    so a direction stays interpretable across KB republishes."""

    __tablename__ = "directions"
    __table_args__ = (UniqueConstraint("run_id", "career_code", name="uq_direction_run_career"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("direction_runs.id"), index=True)
    career_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("careers.id"), index=True)
    career_code: Mapped[str] = mapped_column(String(128))
    domain: Mapped[str] = mapped_column(String(32))
    placement: Mapped[DirectionPlacement] = mapped_column(
        Enum(DirectionPlacement, native_enum=False), default=DirectionPlacement.UNRANKED, index=True
    )
    rank_within_placement: Mapped[int | None] = mapped_column(Integer)
    trade_off_notes: Mapped[str | None] = mapped_column(Text)  # e.g. ALTERNATIVE with LOW Goal Alignment

    # --- Output 1: Potential Fit ---
    potential_fit_raw_experimental: Mapped[float | None] = mapped_column(Float)
    potential_fit_band: Mapped[QualitativeBand | None] = mapped_column(Enum(QualitativeBand, native_enum=False))
    potential_fit_coverage_ratio: Mapped[float | None] = mapped_column(Float)
    potential_fit_scored_component_count: Mapped[int] = mapped_column(Integer, default=0)

    # --- Output 2: Goal Alignment ---
    goal_alignment_raw_experimental: Mapped[float | None] = mapped_column(Float)
    goal_alignment_band: Mapped[QualitativeBand | None] = mapped_column(Enum(QualitativeBand, native_enum=False))
    goal_alignment_coverage_ratio: Mapped[float | None] = mapped_column(Float)
    goal_alignment_scored_component_count: Mapped[int] = mapped_column(Integer, default=0)

    # --- Output 3: Transition Feasibility ---
    transition_feasibility_raw_experimental: Mapped[float | None] = mapped_column(Float)
    transition_feasibility_band: Mapped[QualitativeBand | None] = mapped_column(Enum(QualitativeBand, native_enum=False))
    transition_feasibility_coverage_ratio: Mapped[float | None] = mapped_column(Float)
    transition_feasibility_scored_component_count: Mapped[int] = mapped_column(Integer, default=0)

    # --- Output 4: Evidence Confidence ---
    evidence_confidence_raw_experimental: Mapped[float | None] = mapped_column(Float)
    evidence_confidence_band: Mapped[QualitativeBand | None] = mapped_column(Enum(QualitativeBand, native_enum=False))
    evidence_confidence_coverage_note: Mapped[str | None] = mapped_column(Text)

    # skills classified UNKNOWN (Founder decision P) -- information gaps, not penalties
    skills_to_verify: Mapped[list | None] = mapped_column(JSON)

    # --- Slice 2: deterministic explanation bundle + material-differentiation ---
    # Structured backend data (WHY_FIT/WHY_NOW/TRANSITION/CONFIDENCE/PROVENANCE)
    # for consultant review -- not client-facing prose (plan section 8).
    explanation_bundle: Mapped[dict | None] = mapped_column(JSON)
    # Set only when placement == DEDUPED (app/services/direction/dedup.py):
    # exact title/alias collision only, never a similarity guess.
    duplicate_of_career_code: Mapped[str | None] = mapped_column(String(128))
    dedup_reason: Mapped[str | None] = mapped_column(Text)
    diversity_warning: Mapped[str | None] = mapped_column(Text)

    narrative_text: Mapped[str | None] = mapped_column(Text)
    narrative_locale: Mapped[str | None] = mapped_column(String(8))
    narrative_trace_id: Mapped[str | None] = mapped_column(String(64))
    # Slice 3: structured LLM narrative -- {summary, why_fit, why_now,
    # transition, risks, what_to_verify}. `narrative_text` continues to
    # hold the `summary` field for any caller still reading the plain-text
    # column (see app/services/direction/narrative.py). prompt_version/
    # model live on DirectionRun (narrative_prompt_version/model, already
    # present since Slice 1) -- not duplicated per-Direction.
    narrative_structured: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    run: Mapped["DirectionRun"] = relationship(back_populates="directions")
    score_components: Mapped[list["DirectionScoreComponent"]] = relationship(back_populates="direction")
    constraint_checks: Mapped[list["DirectionConstraintCheck"]] = relationship(back_populates="direction")


class DirectionScoreComponent(Base):
    """One score component's result for one direction, tagged with its
    `output_family` (Founder decision F). `raw_score` is populated only
    when `status == SCORED`; an `INSUFFICIENT_DATA` / `NOT_APPLICABLE`
    component is excluded from that family's aggregation entirely (Founder
    decision F). A profile claim may appear as a component in more than one
    family via different deterministic calculations -- hence the UNIQUE is
    (direction_id, output_family, component_key)."""

    __tablename__ = "direction_score_components"
    __table_args__ = (
        UniqueConstraint("direction_id", "output_family", "component_key", name="uq_direction_score_component"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    direction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("directions.id"), index=True)
    output_family: Mapped[OutputFamily] = mapped_column(Enum(OutputFamily, native_enum=False), index=True)
    component_key: Mapped[str] = mapped_column(String(64))
    status: Mapped[ScoreComponentStatus] = mapped_column(Enum(ScoreComponentStatus, native_enum=False))
    raw_score: Mapped[float | None] = mapped_column(Float)
    weight_applied: Mapped[float] = mapped_column(Float, default=0.0)
    scoring_config_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("scoring_configs.id"))
    rationale: Mapped[str] = mapped_column(Text)
    contributing_claim_ids: Mapped[list | None] = mapped_column(JSON)
    contributing_career_attributes: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    direction: Mapped["Direction"] = relationship(back_populates="score_components")


class DirectionConstraintCheck(Base):
    """Hard Constraint Gate result: one row per (direction, profile
    constraint) considered. `result == BLOCK` AND `is_hard == true` is the
    ONLY thing that removes a career from recommendation eligibility -- and
    it does so regardless of any score (Career Fit / Direction Evaluation
    Model section 2)."""

    __tablename__ = "direction_constraint_checks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    direction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("directions.id"), index=True)
    profile_constraint_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("profile_constraints.id"))
    constraint_subtype: Mapped[str] = mapped_column(String(32))
    career_attribute_ref: Mapped[str | None] = mapped_column(String(128))
    result: Mapped[ConstraintCheckResult] = mapped_column(Enum(ConstraintCheckResult, native_enum=False), index=True)
    is_hard: Mapped[bool] = mapped_column(Boolean, default=False)
    explanation: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    direction: Mapped["Direction"] = relationship(back_populates="constraint_checks")


class ClarificationRequest(Base):
    """Emitted when a run is `INSUFFICIENT_INFORMATION`, a fit output could
    not be scored, an important contradiction is unresolved, or required
    skills are `UNKNOWN` (Founder decision P). Stage 3B only EMITS these --
    it never reopens the Stage 1 assessment state machine (Founder decision
    M3)."""

    __tablename__ = "clarification_requests"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("direction_runs.id"), index=True)
    reason: Mapped[ClarificationReason] = mapped_column(Enum(ClarificationReason, native_enum=False))
    canonical_dimension: Mapped[str | None] = mapped_column(String(48))
    related_claim_ids: Mapped[list | None] = mapped_column(JSON)
    suggested_question_topic: Mapped[str] = mapped_column(Text)
    status: Mapped[ClarificationStatus] = mapped_column(
        Enum(ClarificationStatus, native_enum=False), default=ClarificationStatus.OPEN
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    run: Mapped["DirectionRun"] = relationship(back_populates="clarification_requests")


class DirectionCriticFinding(Base):
    """One deterministic Critic finding (app/services/direction/critic.py)
    against a completed `DirectionRun`. `direction_id` is null for a
    run-level finding (e.g. "insufficient direction diversity"), set for a
    finding about one specific `Direction`. Never stores raw CV/answer
    text -- `related_*_ids` are references, `message` is a deterministic,
    templated description built only from IDs/counts/bands, never from
    quoted free-text claim content.

    `identity_key` (Slice 3.5 hardening) makes a finding's identity
    idempotent per (run_id, engine_version, direction_id, severity, code,
    related-entity identity) -- `critic.py::_compute_identity_key` computes
    it; `run_critic()` skips inserting a row whose `identity_key` already
    exists for this `run_id`, so re-running the SAME critic engine version
    on the SAME run never creates duplicate findings. A different, later
    `engine_version` gets its own `identity_key`s and therefore its own,
    additional finding set -- historical findings from a superseded engine
    version are never deleted."""

    __tablename__ = "direction_critic_findings"
    __table_args__ = (
        UniqueConstraint("run_id", "identity_key", name="uq_direction_critic_finding_identity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("direction_runs.id"), index=True)
    direction_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("directions.id"), index=True)
    severity: Mapped[CriticSeverity] = mapped_column(Enum(CriticSeverity, native_enum=False), index=True)
    code: Mapped[str] = mapped_column(String(64), index=True)
    message: Mapped[str] = mapped_column(Text)
    related_claim_ids: Mapped[list | None] = mapped_column(JSON)
    related_evidence_ids: Mapped[list | None] = mapped_column(JSON)
    related_career_ids: Mapped[list | None] = mapped_column(JSON)
    related_requirement_ids: Mapped[list | None] = mapped_column(JSON)
    engine_version: Mapped[str] = mapped_column(String(64))
    identity_key: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )


class DirectionReview(Base):
    """The consultant-review workflow state for one `DirectionRun` (at
    most one review per run -- a regeneration creates a NEW `DirectionRun`
    and therefore a NEW review, never reopens an old one). The underlying
    `DirectionRun`/`Direction` rows are immutable; only this row's
    workflow fields (`status`/`reviewer_id`/`comment`/`decided_at`)
    change, exactly like `InterviewSession.status` in Stage 1 -- the
    content it is reviewing never moves."""

    __tablename__ = "direction_reviews"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("direction_runs.id"), unique=True, index=True)
    status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, native_enum=False), default=ReviewStatus.PENDING_REVIEW, index=True
    )
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"))
    comment: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    corrections: Mapped[list["ConsultantCorrection"]] = relationship(back_populates="review")


class ConsultantCorrection(Base):
    """Append-only (Founder Methodology Contract v0.1 decision K) -- never
    UPDATE or DELETE a row here, mirroring `AuditLog`'s discipline. Both
    `original_value` and `corrected_value` are captured at correction time
    so the correction is self-explanatory without re-deriving "what did it
    used to say" from history. Every provenance/version field is
    denormalized onto the row (not just referenced via the run) so the
    correction remains a complete, self-contained audit record even if the
    referenced run/config/policy rows are inspected out of context."""

    __tablename__ = "consultant_corrections"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    review_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("direction_reviews.id"), index=True)
    direction_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("directions.id"), index=True)
    # e.g. "direction_placement" | "direction_metadata" | "narrative" |
    # "profile_flag" | "knowledge_flag" -- free string, extensible without
    # a migration (same rationale as KnowledgeSource.source_type).
    artifact_type: Mapped[str] = mapped_column(String(32))
    original_value: Mapped[dict | None] = mapped_column(JSON)
    corrected_value: Mapped[dict | None] = mapped_column(JSON)
    reason_code: Mapped[CorrectionReasonCode] = mapped_column(Enum(CorrectionReasonCode, native_enum=False), index=True)
    comment: Mapped[str | None] = mapped_column(Text)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"))
    related_claim_ids: Mapped[list | None] = mapped_column(JSON)
    related_evidence_ids: Mapped[list | None] = mapped_column(JSON)
    methodology_version: Mapped[str] = mapped_column(String(64))
    knowledge_base_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_base_versions.id"))
    scoring_config_version: Mapped[int] = mapped_column(Integer)
    ranking_policy_version: Mapped[int] = mapped_column(Integer)
    direction_engine_version: Mapped[str] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(64))
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    review: Mapped["DirectionReview"] = relationship(back_populates="corrections")
