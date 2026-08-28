"""Matching V1 M1 -- versioned structured (BASIC) assessment data model
(docs/engineering/21_MATCHING_V1_RECONCILIATION_AND_IMPLEMENTATION_PLAN.md,
Founder Review "M1 GO", 2026-08-28).

Architecturally isolated from the existing PRO Hybrid Assessment
(`app/db/models_assessment.py`'s `InterviewSession`/`Answer`/
`InterviewMessage`/`CVUpload`) -- neither module imports the other, and
this module has NO import of `app.ai_gateway` or any AI-backed extraction
service (enforced by `tests/test_basic_assessment_zero_ai.py`). BASIC and
PRO Hybrid are two coexisting assessment modes (`AssessmentMode`), never
merged into one state machine.

Every `AssessmentItem` carries queryable compatibility metadata sourced
from `methodology_lab/05_GOLDEN_TEST/MNP_SCALE_TO_ONET_MAPPING_V0.1.md` via
its scale's `AssessmentScale` row -- a PROXY/MNP_ONLY scale can never be
silently MATCH_ENABLED (see `compute_matching_usage()` below, the single
source of truth for that rule, enforced at seed time and re-checked by
`tests/test_basic_assessment_seed.py`).

M1 scope only: the structured question bank + attempt/answer persistence.
No scoring, no vector matching, no career data -- see doc 21 §5 (M1) for
the full slice boundary.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

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
    Text,
    Uuid,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _str_enum(enum_cls: type[enum.Enum]):
    """`Enum(..., native_enum=False)` alone stores a Python enum member's
    `.name` (e.g. "NOT_STARTED"), not its `.value` (e.g. "not_started") --
    a real SQLAlchemy default that would silently break every
    lowercase-value partial-index predicate and every plain string
    comparison in this module's own services/tests if left unset. This
    project's existing PRO Hybrid enums (`models_assessment.py`) already
    carry that mismatch (its own partial index's WHERE clause never
    actually matches any stored row); rather than touch that
    out-of-scope, historical code, every enum column newly introduced
    here explicitly stores `.value` via `values_callable`, matching this
    module's own migration predicates and every `== "some_value"`
    comparison in `seed.py`/tests."""

    return Enum(enum_cls, native_enum=False, values_callable=lambda obj: [e.value for e in obj])


class AssessmentMode(str, enum.Enum):
    """Which assessment flow produced/consumes a given definition or
    attempt. BASIC_STRUCTURED is new (Matching V1); PRO_HYBRID is a label
    for the existing, unmodified Hybrid Assessment (`InterviewSession`
    lives in `models_assessment.py` and is not touched by this module)."""

    BASIC_STRUCTURED = "basic_structured"
    PRO_HYBRID = "pro_hybrid"


class AttemptStatus(str, enum.Enum):
    """NOT_STARTED -> IN_PROGRESS -> COMPLETED -> CALCULATED. M1 wires only
    the first three transitions (see app/services/basic_assessment/
    attempts.py); CALCULATED is reserved for M2's deterministic profile
    engine, not reachable from any M1 service function."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CALCULATED = "calculated"


class ResponseType(str, enum.Enum):
    LIKERT_5 = "likert_5"
    SINGLE_CHOICE = "single_choice"
    MULTI_CHOICE = "multi_choice"
    BOOLEAN = "boolean"
    NUMERIC = "numeric"


class ScaleFamily(str, enum.Enum):
    """The 7 blocks of `MNP_GOLDEN_TEST_V0.1.md` §1. RIASEC/WORK_STYLE/
    WORK_VALUES/WORK_ENVIRONMENT are Likert vector blocks; GOALS/
    CONSTRAINTS/EXPERIENCE are structured, never Fit inputs."""

    RIASEC = "riasec"
    WORK_STYLE = "work_style"
    WORK_VALUES = "work_values"
    WORK_ENVIRONMENT = "work_environment"
    GOALS = "goals"
    CONSTRAINTS = "constraints"
    EXPERIENCE = "experience"


class MappingStatus(str, enum.Enum):
    """Per-scale MNP<->O*NET compatibility, per
    `MNP_SCALE_TO_ONET_MAPPING_V0.1.md`. Never inferred at runtime -- set
    once at seed time from the methodology document, queryable per scale."""

    DIRECT = "direct"
    DERIVED = "derived"
    PROXY = "proxy"
    MNP_ONLY = "mnp_only"


class MatchingUsage(str, enum.Enum):
    """Whether a scale may feed a career-matching Fit calculation, or is
    profile-display-only. Set exclusively via `compute_matching_usage()`
    below -- never assigned ad hoc."""

    MATCH_ENABLED = "match_enabled"
    PROFILE_ONLY = "profile_only"


def compute_matching_usage(mapping_status: MappingStatus) -> MatchingUsage:
    """Founder Review rule 3 (2026-08-28), the single source of truth:
    DIRECT/DERIVED -> MATCH_ENABLED (DERIVED additionally forces
    `AssessmentScale.provisional = True`, see `seed.py`). PROXY/MNP_ONLY
    -> PROFILE_ONLY, always -- a PROXY scale becomes MATCH_ENABLED only
    through a later, separate, explicit methodology decision that defines
    and defends its transformation; this function is never bypassed to
    manufacture a career-side value for an MNP_ONLY construct."""

    if mapping_status in (MappingStatus.DIRECT, MappingStatus.DERIVED):
        return MatchingUsage.MATCH_ENABLED
    return MatchingUsage.PROFILE_ONLY


class AssessmentScale(Base):
    """Scale-level compatibility metadata (Founder Review §11) -- one row
    per (scale_family, scale_key), shared by every `AssessmentItem` that
    measures it. This is the queryable home for mapping_status/
    matching_usage/source provenance; `AssessmentItem` denormalizes only
    `matching_usage` for fast per-item filtering."""

    __tablename__ = "assessment_scales"
    __table_args__ = (UniqueConstraint("scale_family", "scale_key", name="uq_assessment_scale_family_key"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scale_family: Mapped[ScaleFamily] = mapped_column(_str_enum(ScaleFamily), index=True)
    scale_key: Mapped[str] = mapped_column(String(64))
    label_uk: Mapped[str] = mapped_column(String(255))
    mapping_status: Mapped[MappingStatus] = mapped_column(_str_enum(MappingStatus))
    matching_usage: Mapped[MatchingUsage] = mapped_column(_str_enum(MatchingUsage))
    source_system: Mapped[str | None] = mapped_column(String(32))  # "onet" | None
    source_element_id: Mapped[str | None] = mapped_column(String(64))
    source_element_name: Mapped[str | None] = mapped_column(String(255))
    source_version: Mapped[str | None] = mapped_column(String(32))  # e.g. "30.3"
    transformation_version: Mapped[str | None] = mapped_column(String(32))
    provisional: Mapped[bool] = mapped_column(Boolean, default=True)
    methodology_version: Mapped[str] = mapped_column(String(32))  # e.g. "golden_test_v0.1"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[list["AssessmentItem"]] = relationship(back_populates="scale")


class AssessmentDefinition(Base):
    """One versioned assessment bank (e.g. "Matching V1 Alpha Long Form").
    At most one definition per `mode` is `is_active` at a time -- the
    partial unique index below is what makes "the current bank" a DB fact,
    never a business-logic constant."""

    __tablename__ = "assessment_definitions"
    __table_args__ = (
        UniqueConstraint("assessment_version", name="uq_assessment_definition_version"),
        Index(
            "uq_one_active_definition_per_mode",
            "mode",
            unique=True,
            postgresql_where=text("is_active"),
            sqlite_where=text("is_active"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_version: Mapped[str] = mapped_column(String(64))  # e.g. "matching_v1_alpha_long_form_v0.1"
    mode: Mapped[AssessmentMode] = mapped_column(_str_enum(AssessmentMode), index=True)
    methodology_version: Mapped[str] = mapped_column(String(32))  # e.g. "golden_test_v0.1"
    title_uk: Mapped[str] = mapped_column(String(255))
    description_uk: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sections: Mapped[list["AssessmentSection"]] = relationship(
        back_populates="definition", order_by="AssessmentSection.display_order"
    )
    items: Mapped[list["AssessmentItem"]] = relationship(
        back_populates="definition", order_by="AssessmentItem.display_order"
    )


class AssessmentSection(Base):
    """A UI/authoring grouping of items within one definition (RIASEC,
    Work Style, Work Values, Work Environment, Goals, Constraints,
    Experience) -- distinct from `scale_family` so a future definition
    could regroup sections without redefining the scale taxonomy."""

    __tablename__ = "assessment_sections"
    __table_args__ = (UniqueConstraint("definition_id", "section_key", name="uq_assessment_section_key"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    definition_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessment_definitions.id"), index=True)
    section_key: Mapped[str] = mapped_column(String(64))
    title_uk: Mapped[str] = mapped_column(String(255))
    display_order: Mapped[int] = mapped_column(Integer)

    definition: Mapped["AssessmentDefinition"] = relationship(back_populates="sections")
    items: Mapped[list["AssessmentItem"]] = relationship(
        back_populates="section", order_by="AssessmentItem.display_order"
    )


class AssessmentItem(Base):
    """One structured question. `matching_usage` is a denormalized copy of
    its `AssessmentScale.matching_usage` at seed time (never set
    independently -- see `seed.py`), so a filter like "give me only
    MATCH_ENABLED items" needs no join. `reverse_exempt` records, per
    `MNP_BASIC_SHORT_FORM_STRATEGY_V0.1.md` §4, that a scale with no
    natural reverse phrasing was deliberately not given one -- never a
    silent omission."""

    __tablename__ = "assessment_items"
    __table_args__ = (UniqueConstraint("definition_id", "item_key", name="uq_assessment_item_key"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    definition_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessment_definitions.id"), index=True)
    section_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessment_sections.id"), index=True)
    scale_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessment_scales.id"), index=True)
    item_key: Mapped[str] = mapped_column(String(64))  # stable slug, e.g. "riasec_r_1", "ws_autonomy_1"
    scale_family: Mapped[ScaleFamily] = mapped_column(_str_enum(ScaleFamily), index=True)
    scale_key: Mapped[str] = mapped_column(String(64))
    subscale_key: Mapped[str | None] = mapped_column(String(64))
    question_uk: Mapped[str] = mapped_column(Text)
    response_type: Mapped[ResponseType] = mapped_column(_str_enum(ResponseType))
    reverse_scored: Mapped[bool] = mapped_column(Boolean, default=False)
    reverse_exempt: Mapped[bool] = mapped_column(Boolean, default=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    display_order: Mapped[int] = mapped_column(Integer)
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    profile_usage: Mapped[bool] = mapped_column(Boolean, default=True)
    matching_usage: Mapped[MatchingUsage] = mapped_column(_str_enum(MatchingUsage))
    source_reference: Mapped[str] = mapped_column(String(255))  # e.g. "MNP_GOLDEN_TEST_V0.1.md §3"
    methodology_version: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    definition: Mapped["AssessmentDefinition"] = relationship(back_populates="items")
    section: Mapped["AssessmentSection"] = relationship(back_populates="items")
    scale: Mapped["AssessmentScale"] = relationship(back_populates="items")
    options: Mapped[list["AssessmentItemOption"]] = relationship(
        back_populates="item", order_by="AssessmentItemOption.display_order"
    )


class AssessmentItemOption(Base):
    """One selectable option for a SINGLE_CHOICE/MULTI_CHOICE item (e.g. a
    CareerDomain choice for Goals, an education-level choice for
    Constraints). Not used by LIKERT_5/BOOLEAN/NUMERIC items."""

    __tablename__ = "assessment_item_options"
    __table_args__ = (UniqueConstraint("item_id", "option_key", name="uq_assessment_item_option_key"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessment_items.id"), index=True)
    option_key: Mapped[str] = mapped_column(String(64))
    label_uk: Mapped[str] = mapped_column(String(255))
    display_order: Mapped[int] = mapped_column(Integer)

    item: Mapped["AssessmentItem"] = relationship(back_populates="options")


class BasicAssessmentAttempt(Base):
    """One BASIC_STRUCTURED assessment attempt for one user. Mirrors
    `InterviewSession`'s "at most one unfinished session per user" pattern
    (models_assessment.py) but is a wholly separate table -- a user may
    have one open `InterviewSession` (PRO) and one open
    `BasicAssessmentAttempt` (BASIC) simultaneously; the two state
    machines never interact."""

    __tablename__ = "basic_assessment_attempts"
    __table_args__ = (
        Index(
            "uq_one_open_basic_attempt_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("status IN ('not_started', 'in_progress')"),
            sqlite_where=text("status IN ('not_started', 'in_progress')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity_users.id"), index=True)
    definition_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessment_definitions.id"), index=True)
    status: Mapped[AttemptStatus] = mapped_column(
        _str_enum(AttemptStatus), default=AttemptStatus.NOT_STARTED, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    calculated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    answers: Mapped[list["BasicAssessmentAnswer"]] = relationship(
        back_populates="attempt", order_by="BasicAssessmentAnswer.created_at"
    )


class BasicAssessmentAnswer(Base):
    """A structured response to one `AssessmentItem`, within one attempt.
    Immutable once created, exactly like the PRO Hybrid `Answer` model --
    a changed answer to the same item is a *new* row; "latest by
    created_at wins" is the read convention (see
    app/services/basic_assessment/attempts.py). `idempotency_key` +
    `UNIQUE(attempt_id, idempotency_key)` makes duplicate submission safe,
    same mechanism as `Answer.idempotency_key`."""

    __tablename__ = "basic_assessment_answers"
    __table_args__ = (
        UniqueConstraint("attempt_id", "idempotency_key", name="uq_basic_answer_attempt_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("basic_assessment_attempts.id"), index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessment_items.id"), index=True)
    response_type: Mapped[ResponseType] = mapped_column(_str_enum(ResponseType))
    numeric_value: Mapped[int | None] = mapped_column(Integer)  # LIKERT_5 raw 1-5, or NUMERIC
    boolean_value: Mapped[bool | None] = mapped_column(Boolean)
    selected_option_keys: Mapped[list | None] = mapped_column(JSON)  # list[str], SINGLE_/MULTI_CHOICE
    idempotency_key: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now(), index=True
    )

    attempt: Mapped["BasicAssessmentAttempt"] = relationship(back_populates="answers")
