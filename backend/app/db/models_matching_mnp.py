"""MNP V1 -- Matching Engine persistence: `MnpMatchRun` and everything a
run produces (`MNP_DATA_MODEL_V1.md` §17-23, `MNP_MATCHING_MATH_V1.md`,
`MNP_FEASIBILITY_RULES_V1.md`, `MNP_TRANSITION_DISTANCE_V1.md`,
`MNP_SKILL_GAP_AND_PRIORITY_V1.md`, `MNP_ROUTE_ENGINE_V1.md`,
`MNP_OPPORTUNITY_DB_AND_MATCHING_V1.md`, `MNP_LEARNING_DB_V1.md`).

A `MnpMatchRun` pins `methodology_version`/`matching_engine_version`/
`career_kb_version`/`market_data_version` so any historical result is
reproducible even after the Career KB or engine changes later
(MNP_EVIDENCE_AND_CONFIDENCE_MODEL_V1 §24 Auditability)."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
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


class MatchComponentType(str, enum.Enum):
    """MNP_MATCHING_MATH_V1 "Components" / MNP_DATA_MODEL_V1 §19."""

    SKILL_FIT = "skill_fit"
    EXPERIENCE_TRANSFER = "experience_transfer"
    KNOWLEDGE_FIT = "knowledge_fit"
    PREFERENCE_FIT = "preference_fit"
    VALUES_FIT = "values_fit"
    FEASIBILITY = "feasibility"
    MARKET_ATTRACTIVENESS = "market_attractiveness"
    INCOME_POTENTIAL = "income_potential"
    TRANSITION_COST = "transition_cost"


class ComponentBand(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INSUFFICIENT = "insufficient"


class DisplayBand(str, enum.Enum):
    """Numeric score is internal only (Founder Decision #15) -- this is
    the only thing the UI is allowed to read for an overall impression."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FeasibilityStatus(str, enum.Enum):
    """MNP_FEASIBILITY_RULES_V1."""

    READY_NOW = "ready_now"
    NEAR_READY = "near_ready"
    REACHABLE = "reachable"
    LONG_TRANSITION = "long_transition"
    BLOCKED = "blocked"


class TransitionDistance(str, enum.Enum):
    """MNP_TRANSITION_DISTANCE_V1."""

    D0_SAME_CAREER = "d0_same_career"
    D1_PROGRESSION = "d1_progression"
    D2_ADJACENT = "d2_adjacent"
    D3_TRANSFERABLE = "d3_transferable"
    D4_CAREER_CHANGE = "d4_career_change"
    D5_FUNDAMENTAL_RETRAINING = "d5_fundamental_retraining"


class FindingStatus(str, enum.Enum):
    """MNP_DATA_MODEL_V1 §20 FeasibilityFinding.status."""

    PASS = "pass"
    GAP = "gap"
    BLOCKER = "blocker"


class GapType(str, enum.Enum):
    SKILL = "skill"
    KNOWLEDGE = "knowledge"
    EXPERIENCE = "experience"
    CREDENTIAL = "credential"
    LANGUAGE = "language"
    PROOF = "proof"
    POSITIONING = "positioning"


class GapClassification(str, enum.Enum):
    """MNP_SKILL_GAP_AND_PRIORITY_V1 "Classification"."""

    MUST_HAVE = "must_have"
    HIGH_VALUE = "high_value"
    DIFFERENTIATOR = "differentiator"
    OPTIONAL = "optional"


class GapAction(str, enum.Enum):
    """MNP_SKILL_GAP_AND_PRIORITY_V1 "Actions"."""

    LEARN = "learn"
    PRACTICE = "practice"
    PROVE = "prove"
    CERTIFY = "certify"
    REFRAME = "reframe"


class RouteType(str, enum.Enum):
    """MNP_ROUTE_ENGINE_V1 "Scenarios"."""

    SAFE = "safe"
    GROWTH = "growth"
    TRANSFORM = "transform"


class RouteStepType(str, enum.Enum):
    """MNP_ROUTE_ENGINE_V1: TODAY -> existing capital -> reframe/prove ->
    learn/practice/certify -> first evidence -> entry opportunity ->
    target role -> next step."""

    EXISTING_CAPITAL = "existing_capital"
    REFRAME_OR_PROVE = "reframe_or_prove"
    LEARN_PRACTICE_CERTIFY = "learn_practice_certify"
    FIRST_EVIDENCE = "first_evidence"
    ENTRY_OPPORTUNITY = "entry_opportunity"
    TARGET_ROLE = "target_role"
    NEXT_STEP = "next_step"


class OpportunityType(str, enum.Enum):
    """MNP_OPPORTUNITY_DB_AND_MATCHING_V1."""

    VACANCY = "vacancy"
    INTERNSHIP = "internship"
    PROJECT = "project"
    TRAINING = "training"
    GRANT = "grant"
    PROGRAM = "program"
    MENTORSHIP = "mentorship"


class OpportunityStatus(str, enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    UNVERIFIED = "unverified"


class MnpMatchRun(Base):
    """MNP_DATA_MODEL_V1 §17."""

    __tablename__ = "mnp_match_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_career_cards.id"), index=True)
    career_card_version: Mapped[int] = mapped_column(Integer)
    assessment_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_assessment_sessions.id"))
    methodology_version: Mapped[str] = mapped_column(String(32))
    matching_engine_version: Mapped[str] = mapped_column(String(32))
    career_kb_version: Mapped[str] = mapped_column(String(32))
    market_data_version: Mapped[str | None] = mapped_column(String(32))
    ranking_mode: Mapped[str] = mapped_column(String(32), default="best_for_me")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    career_matches: Mapped[list["MnpCareerMatch"]] = relationship(back_populates="match_run", cascade="all, delete-orphan")


class MnpCareerMatch(Base):
    """MNP_DATA_MODEL_V1 §18. `overall_score_internal` and
    `confidence_internal` are never shown to the user directly (Founder
    Decision #15) -- only `display_band`, `feasibility_status` and
    `transition_distance` reach the UI as-is."""

    __tablename__ = "mnp_career_matches"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    match_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_match_runs.id"), index=True)
    career_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_careers.id"), index=True)
    rank_overall: Mapped[int] = mapped_column(Integer)
    overall_score_internal: Mapped[float] = mapped_column(Float)
    display_band: Mapped[DisplayBand] = mapped_column(_str_enum(DisplayBand))
    feasibility_status: Mapped[FeasibilityStatus] = mapped_column(_str_enum(FeasibilityStatus))
    transition_distance: Mapped[TransitionDistance] = mapped_column(_str_enum(TransitionDistance))
    confidence_internal: Mapped[ComponentBand] = mapped_column(_str_enum(ComponentBand))
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)

    match_run: Mapped["MnpMatchRun"] = relationship(back_populates="career_matches")
    components: Mapped[list["MnpMatchComponent"]] = relationship(back_populates="career_match", cascade="all, delete-orphan")
    feasibility_findings: Mapped[list["MnpFeasibilityFinding"]] = relationship(back_populates="career_match", cascade="all, delete-orphan")
    gaps: Mapped[list["MnpPersonalGap"]] = relationship(back_populates="career_match", cascade="all, delete-orphan")
    routes: Mapped[list["MnpCareerRoute"]] = relationship(back_populates="career_match", cascade="all, delete-orphan")


class MnpMatchComponent(Base):
    """MNP_DATA_MODEL_V1 §19. One row per `MatchComponentType` per
    `MnpCareerMatch` -- the multidimensional Match Vector
    (MNP_MATCHING_MATH_V1 "Output": never one aggregate percentage shown
    to the user)."""

    __tablename__ = "mnp_match_components"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_match_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_career_matches.id"), index=True)
    component_type: Mapped[MatchComponentType] = mapped_column(_str_enum(MatchComponentType), index=True)
    score_internal: Mapped[float | None] = mapped_column(Float)
    band: Mapped[ComponentBand] = mapped_column(_str_enum(ComponentBand))
    confidence: Mapped[ComponentBand] = mapped_column(_str_enum(ComponentBand))
    explanation_code: Mapped[str | None] = mapped_column(String(64))
    detail: Mapped[dict | None] = mapped_column(JSON)  # matched/gap skill lists etc. for explainability

    career_match: Mapped["MnpCareerMatch"] = relationship(back_populates="components")


class MnpFeasibilityFinding(Base):
    """MNP_DATA_MODEL_V1 §20. `finding_type` mirrors `RequirementCategory`
    (education/experience/credential/language/legal/other)."""

    __tablename__ = "mnp_feasibility_findings"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_match_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_career_matches.id"), index=True)
    finding_type: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(16))  # "soft" | "hard"
    requirement_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("mnp_career_requirements.id"))
    status: Mapped[FindingStatus] = mapped_column(_str_enum(FindingStatus))
    explanation_code: Mapped[str] = mapped_column(String(64))
    evidence_ref: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))

    career_match: Mapped["MnpCareerMatch"] = relationship(back_populates="feasibility_findings")


class MnpPersonalGap(Base):
    """MNP_DATA_MODEL_V1 §21 / MNP_SKILL_GAP_AND_PRIORITY_V1."""

    __tablename__ = "mnp_personal_gaps"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_match_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_career_matches.id"), index=True)
    gap_type: Mapped[GapType] = mapped_column(_str_enum(GapType))
    reference_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))  # skill_id / knowledge_id / requirement_id
    reference_label: Mapped[str] = mapped_column(String(255))
    classification: Mapped[GapClassification] = mapped_column(_str_enum(GapClassification))
    action: Mapped[GapAction] = mapped_column(_str_enum(GapAction))
    priority_internal: Mapped[float] = mapped_column(Float)
    estimated_time: Mapped[str | None] = mapped_column(String(64))
    estimated_cost: Mapped[float | None] = mapped_column(Float)

    career_match: Mapped["MnpCareerMatch"] = relationship(back_populates="gaps")


class MnpCareerRoute(Base):
    """MNP_DATA_MODEL_V1 §22 / MNP_ROUTE_ENGINE_V1."""

    __tablename__ = "mnp_career_routes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_match_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_career_matches.id"), index=True)
    route_type: Mapped[RouteType] = mapped_column(_str_enum(RouteType))
    status: Mapped[str] = mapped_column(String(32), default="proposed")
    duration_estimate: Mapped[str | None] = mapped_column(String(64))
    cost_estimate: Mapped[float | None] = mapped_column(Float)

    career_match: Mapped["MnpCareerMatch"] = relationship(back_populates="routes")
    steps: Mapped[list["MnpRouteStep"]] = relationship(back_populates="route", cascade="all, delete-orphan", order_by="MnpRouteStep.order")


class MnpRouteStep(Base):
    __tablename__ = "mnp_route_steps"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    route_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_career_routes.id"), index=True)
    order: Mapped[int] = mapped_column(Integer)
    step_type: Mapped[RouteStepType] = mapped_column(_str_enum(RouteStepType))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    target_skill_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("mnp_skills.id"))
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("mnp_opportunities.id"))
    duration_estimate: Mapped[str | None] = mapped_column(String(64))
    completion_rule: Mapped[str | None] = mapped_column(String(255))

    route: Mapped["MnpCareerRoute"] = relationship(back_populates="steps")


class MnpLearningOpportunity(Base):
    """MNP_LEARNING_DB_V1."""

    __tablename__ = "mnp_learning_opportunities"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str | None] = mapped_column(String(1000))
    country: Mapped[str | None] = mapped_column(String(64))
    format: Mapped[str | None] = mapped_column(String(32))  # online/offline/hybrid
    cost: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str | None] = mapped_column(String(8))
    duration: Mapped[str | None] = mapped_column(String(64))
    credential: Mapped[str | None] = mapped_column(String(255))
    eligibility: Mapped[str | None] = mapped_column(Text)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[OpportunityStatus] = mapped_column(_str_enum(OpportunityStatus), default=OpportunityStatus.UNVERIFIED)

    skill_mappings: Mapped[list["MnpLearningOpportunitySkill"]] = relationship(back_populates="learning_opportunity", cascade="all, delete-orphan")


class MnpLearningOpportunitySkill(Base):
    """Which `MnpSkill`(s) a `MnpLearningOpportunity` closes -- the join
    the Route Engine reads to link a LEARN/CERTIFY gap action to a real
    provider (MNP_LEARNING_DB_V1: "skills/knowledge mapped")."""

    __tablename__ = "mnp_learning_opportunity_skills"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    learning_opportunity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_learning_opportunities.id"), index=True)
    skill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_skills.id"), index=True)

    learning_opportunity: Mapped["MnpLearningOpportunity"] = relationship(back_populates="skill_mappings")


class MnpOpportunity(Base):
    """MNP_OPPORTUNITY_DB_AND_MATCHING_V1."""

    __tablename__ = "mnp_opportunities"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mnp_careers.id"), index=True)
    opportunity_type: Mapped[OpportunityType] = mapped_column(_str_enum(OpportunityType))
    provider: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(500))
    location: Mapped[str | None] = mapped_column(String(128))
    is_remote: Mapped[bool] = mapped_column(Boolean, default=False)
    url: Mapped[str | None] = mapped_column(String(1000))
    starts_at: Mapped[date | None] = mapped_column(Date)
    expires_at: Mapped[date | None] = mapped_column(Date)
    status: Mapped[OpportunityStatus] = mapped_column(_str_enum(OpportunityStatus), default=OpportunityStatus.UNVERIFIED)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
