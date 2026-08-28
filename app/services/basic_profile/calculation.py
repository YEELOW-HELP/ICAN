"""Deterministic BASIC profile calculation (Matching V1 M2).

Pure arithmetic over already-persisted `BasicAssessmentAnswer` rows --
ZERO LLM tokens, zero calls to any AI-backed service. Every formula here
implements, without modification, the math already specified in:

  methodology_lab/05_GOLDEN_TEST/MNP_GOLDEN_TEST_V0.1.md
    §5-7  reverse scoring, per-scale scoring, missing-answer handling
    §15   Coverage (hardened: schema-driven, not hardcoded 29)
  methodology_lab/05_GOLDEN_TEST/MNP_MATCHING_METRIC_BENCHMARK_V0.1.md
    §6    minimum-dispersion differentiation gate

No new psychometric formula is invented here. Where the methodology docs
are silent on a genuinely new mechanical question (e.g. how to tie-break
the RIASEC ordering), the choice is a plain, documented engineering
convention, never a methodology interpretation -- see `_order_riasec()`.
"""

from __future__ import annotations

import math
import re
import statistics
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_basic_assessment import (
    AssessmentDefinition,
    AssessmentItem,
    AssessmentScale,
    AttemptStatus,
    BasicAssessmentAnswer,
    BasicAssessmentAttempt,
    ScaleFamily,
)
from app.db.models_basic_profile import (
    CoverageBand,
    DeterministicProfile,
    DifferentiationState,
    ProfileScaleResult,
    ProfileStatus,
    ProfileStructuredContext,
    ProfileVectorDifferentiation,
)
from app.services.basic_assessment.attempts import latest_answers_by_item
from app.services.basic_assessment.definitions import get_active_items
from app.services.basic_profile.config import (
    COVERAGE_FULL_MIN,
    COVERAGE_PARTIAL_MIN,
    DIFFERENTIATION_MIN_SCALE_COVERAGE,
    DIFFERENTIATION_STDEV_THRESHOLD,
    PROFILE_ENGINE_VERSION,
    SUFFICIENT_ANSWER_RATIO,
)
from app.services.exceptions import BasicAttemptNotCompletedError

LIKERT_FAMILIES = (
    ScaleFamily.RIASEC,
    ScaleFamily.WORK_STYLE,
    ScaleFamily.WORK_VALUES,
    ScaleFamily.WORK_ENVIRONMENT,
)
STRUCTURED_FAMILIES = (ScaleFamily.GOALS, ScaleFamily.CONSTRAINTS, ScaleFamily.EXPERIENCE)

_DIFFERENTIATION_PRECEDENCE = {
    DifferentiationState.NORMAL: 0,
    DifferentiationState.LOW_DIFFERENTIATION: 1,
    DifferentiationState.INSUFFICIENT_DATA: 2,
}


def _derive_assessment_code(assessment_version: str) -> str:
    """Strips a trailing "_v<version>" suffix, e.g.
    "matching_v1_alpha_long_form_v0.1" -> "matching_v1_alpha_long_form".
    A plain engineering convention, not a methodology rule -- if a future
    assessment_version does not match this shape, the code falls back to
    the version string unchanged rather than raising."""

    match = re.match(r"^(.*)_v\d+(?:\.\d+)*$", assessment_version)
    return match.group(1) if match else assessment_version


def _reverse_corrected(raw: int, reverse_scored: bool) -> int:
    """Golden Test doc §5 -- exact formula, 5-point scale."""

    return 6 - raw if reverse_scored else raw


def _order_riasec(components: dict[str, float]) -> list[str]:
    """Deterministic primary/secondary/... ordering: descending
    normalized value, ties broken by ascending scale_key (alphabetical
    letter order: A,C,E,I,R,S). This is a plain, auditable engineering
    tie-break, not a psychometric interpretation -- no archetype or
    personality label is derived from it (Founder Review §4)."""

    return [key for key, _ in sorted(components.items(), key=lambda kv: (-kv[1], kv[0]))]


async def calculate_basic_profile(session: AsyncSession, attempt: BasicAssessmentAttempt) -> DeterministicProfile:
    """Idempotent for a given (attempt, PROFILE_ENGINE_VERSION) pair --
    re-calling this against an attempt that already has a profile for the
    current engine version returns that existing, immutable row unchanged.
    A genuinely new profile row is only ever created for a NEW
    (attempt_id, profile_engine_version) combination -- historical
    profiles are never overwritten."""

    if attempt.status not in (AttemptStatus.COMPLETED, AttemptStatus.CALCULATED):
        raise BasicAttemptNotCompletedError(
            f"attempt {attempt.id} is {attempt.status.value}, cannot calculate a profile until COMPLETED"
        )

    existing = await session.execute(
        select(DeterministicProfile).where(
            DeterministicProfile.attempt_id == attempt.id,
            DeterministicProfile.profile_engine_version == PROFILE_ENGINE_VERSION,
        )
    )
    existing_profile = existing.scalar_one_or_none()
    if existing_profile is not None:
        return existing_profile

    definition = await session.get(AssessmentDefinition, attempt.definition_id)
    items = await get_active_items(session, definition)
    answers = await latest_answers_by_item(session, attempt)

    scale_ids = {item.scale_id for item in items}
    scales_result = await session.execute(select(AssessmentScale).where(AssessmentScale.id.in_(scale_ids)))
    scale_by_id: dict[uuid.UUID, AssessmentScale] = {s.id: s for s in scales_result.scalars().all()}

    items_by_scale: dict[uuid.UUID, list[AssessmentItem]] = defaultdict(list)
    for item in items:
        items_by_scale[item.scale_id].append(item)

    now = datetime.now(timezone.utc)

    # --- Likert scale scoring (RIASEC / Work Style / Work Values / Work Environment) ---
    scale_results: list[ProfileScaleResult] = []
    # scale_family -> {scale_key: normalized_value} for SUFFICIENTLY-ANSWERED scales only
    vector_components: dict[ScaleFamily, dict[str, float]] = defaultdict(dict)
    required_likert_scale_ids: set[uuid.UUID] = set()
    scored_required_count = 0

    for scale_id, scale_items in items_by_scale.items():
        scale = scale_by_id[scale_id]
        if scale.scale_family not in LIKERT_FAMILIES:
            continue

        active_items = [i for i in scale_items if i.active]
        is_required_scale = bool(active_items) and any(i.required for i in active_items)
        if is_required_scale:
            required_likert_scale_ids.add(scale_id)

        corrected_values: list[int] = []
        answered_count = 0
        for item in active_items:
            answer = answers.get(item.id)
            if answer is None or answer.numeric_value is None:
                continue
            corrected_values.append(_reverse_corrected(answer.numeric_value, item.reverse_scored))
            answered_count += 1

        items_total = len(active_items)
        threshold = math.ceil(SUFFICIENT_ANSWER_RATIO * items_total) if items_total else 0
        sufficiently_answered = items_total > 0 and answered_count >= threshold

        raw_mean = statistics.mean(corrected_values) if sufficiently_answered and corrected_values else None
        normalized_value = ((raw_mean - 1) / 4) if raw_mean is not None else None

        scale_results.append(
            ProfileScaleResult(
                scale_id=scale.id,
                scale_family=scale.scale_family,
                scale_key=scale.scale_key,
                raw_mean=raw_mean,
                normalized_value=normalized_value,
                items_answered=answered_count,
                items_total=items_total,
                sufficiently_answered=sufficiently_answered,
                mapping_status=scale.mapping_status,
                matching_usage=scale.matching_usage,
                provisional=scale.provisional,
            )
        )

        if sufficiently_answered and is_required_scale:
            scored_required_count += 1
        if sufficiently_answered and normalized_value is not None:
            vector_components[scale.scale_family][scale.scale_key] = normalized_value

    # --- Coverage: schema-driven, never hardcoded (Golden Test doc §15, hardened) ---
    enabled_required_scales = len(required_likert_scale_ids)
    coverage = (scored_required_count / enabled_required_scales) if enabled_required_scales else 0.0
    if coverage >= COVERAGE_FULL_MIN:
        coverage_band = CoverageBand.FULL
    elif coverage >= COVERAGE_PARTIAL_MIN:
        coverage_band = CoverageBand.PARTIAL
    else:
        coverage_band = CoverageBand.INSUFFICIENT

    # --- Context completeness: Goals/Constraints/Experience, SEPARATE from Coverage ---
    structured_items = [
        item for item in items if item.scale_family in STRUCTURED_FAMILIES and item.active and item.required
    ]
    answered_structured = sum(1 for item in structured_items if item.id in answers)
    context_completeness = (answered_structured / len(structured_items)) if structured_items else 0.0

    # --- Structured context persistence: raw facts, never invented Likert scores ---
    structured_context_rows: list[ProfileStructuredContext] = []
    for item in items:
        if item.scale_family not in STRUCTURED_FAMILIES:
            continue
        answer = answers.get(item.id)
        if answer is None:
            continue
        structured_context_rows.append(
            ProfileStructuredContext(
                item_id=item.id,
                scale_family=item.scale_family,
                scale_key=item.scale_key,
                response_type=item.response_type,
                numeric_value=answer.numeric_value,
                boolean_value=answer.boolean_value,
                selected_option_keys=answer.selected_option_keys,
                answered_at=answer.created_at,
            )
        )

    # --- Differentiation: one check per vector family, per the Founder-approved guard ---
    differentiation_rows: list[ProfileVectorDifferentiation] = []
    worst_state = DifferentiationState.NORMAL
    for family in LIKERT_FAMILIES:
        family_scale_ids = {sid for sid, s in scale_by_id.items() if s.scale_family == family}
        if not family_scale_ids:
            continue
        family_results = [r for r in scale_results if r.scale_family == family]
        sufficiently_answered_count = sum(1 for r in family_results if r.sufficiently_answered)
        scale_coverage_ratio = sufficiently_answered_count / len(family_scale_ids)
        components = vector_components.get(family, {})

        if scale_coverage_ratio < DIFFERENTIATION_MIN_SCALE_COVERAGE or len(components) < 2:
            state = DifferentiationState.INSUFFICIENT_DATA
            stdev_value = None
        else:
            stdev_value = statistics.pstdev(list(components.values()))
            state = (
                DifferentiationState.LOW_DIFFERENTIATION
                if stdev_value < DIFFERENTIATION_STDEV_THRESHOLD
                else DifferentiationState.NORMAL
            )

        differentiation_rows.append(
            ProfileVectorDifferentiation(
                scale_family=family,
                stdev=stdev_value,
                threshold=DIFFERENTIATION_STDEV_THRESHOLD,
                state=state,
            )
        )
        if _DIFFERENTIATION_PRECEDENCE[state] > _DIFFERENTIATION_PRECEDENCE[worst_state]:
            worst_state = state

    interest_ordering = _order_riasec(vector_components.get(ScaleFamily.RIASEC, {}))

    profile = DeterministicProfile(
        user_id=attempt.user_id,
        attempt_id=attempt.id,
        definition_id=definition.id,
        assessment_code=_derive_assessment_code(definition.assessment_version),
        assessment_version=definition.assessment_version,
        methodology_version=definition.methodology_version,
        profile_engine_version=PROFILE_ENGINE_VERSION,
        status=ProfileStatus.READY,
        is_current=True,
        coverage=coverage,
        coverage_band=coverage_band,
        context_completeness=context_completeness,
        differentiation_state=worst_state,
        interest_ordering=interest_ordering,
        calculated_at=now,
    )

    # Supersede any prior current profile for this user (a genuinely new
    # engine/methodology version, or a retake's new attempt) -- the prior
    # row is never edited or deleted, only its is_current flag flips.
    prior_current = await session.execute(
        select(DeterministicProfile).where(
            DeterministicProfile.user_id == attempt.user_id, DeterministicProfile.is_current.is_(True)
        )
    )
    prior = prior_current.scalar_one_or_none()
    if prior is not None:
        prior.is_current = False
        profile.supersedes_id = prior.id

    session.add(profile)
    await session.flush()

    for row in scale_results:
        row.profile_id = profile.id
        session.add(row)
    for row in differentiation_rows:
        row.profile_id = profile.id
        session.add(row)
    for row in structured_context_rows:
        row.profile_id = profile.id
        session.add(row)

    if attempt.status == AttemptStatus.COMPLETED:
        attempt.status = AttemptStatus.CALCULATED
        attempt.calculated_at = now

    await session.flush()
    return profile


async def recalculate_basic_profile(session: AsyncSession, attempt: BasicAssessmentAttempt) -> DeterministicProfile:
    """Thin, explicit alias over `calculate_basic_profile` -- exists as its
    own named entry point per Founder Review's suggested interface list,
    but carries no different behavior: a recalculation is only ever a new
    row when `PROFILE_ENGINE_VERSION` (or the attempt's own
    `assessment_version`/`methodology_version`) has genuinely changed
    since the last calculation. It can never overwrite or force-refresh a
    profile still valid under the current engine version -- immutability
    of historical results is unconditional."""

    return await calculate_basic_profile(session, attempt)
