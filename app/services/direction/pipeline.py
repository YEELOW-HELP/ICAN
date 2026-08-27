"""Stage 3B Slice 2: end-to-end Direction Generation orchestrator
(Issue #3).

`generate_directions()` is the single entry point that turns a READY
`PotentialProfile` into a persisted `DirectionRun` with ranked
`Direction` rows -- the full vertical:

    READY PotentialProfile
    -> eligibility gate (threshold.py)
    -> Career KB candidate retrieval (candidates.py, retrieval.py only)
    -> hard constraint evaluation (constraints.py)
    -> four-output scoring (scoring/*)
    -> RankingPolicy (ranking.py)
    -> exact-duplicate folding (dedup.py)
    -> persisted DirectionRun + Direction + DirectionScoreComponent +
       DirectionConstraintCheck (+ ClarificationRequest when insufficient)
    -> deterministic explanation bundle per MAIN/ALTERNATIVE Direction

Every sub-step is a pure function from Slice 1 -- this module's only new
responsibility is wiring them together with real DB reads/writes,
version-pinning, and the versioned-immutable-history lifecycle already
established by `app/services/profile/generation.py`
(`ProfileGenerationInProgressError` -> `DirectionGenerationInProgressError`;
a failed attempt's row is kept for audit and never becomes current; the
previous successful run is never mutated by a failed regeneration).

No direct Career KB ORM write anywhere in this module -- candidate
retrieval and detail lookups go exclusively through
`app.services.knowledge.retrieval` / `app.services.direction.candidates`.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_direction import (
    ClarificationReason,
    ClarificationRequest,
    Direction,
    DirectionConstraintCheck,
    DirectionPlacement,
    DirectionRun,
    DirectionRunStatus,
    DirectionScoreComponent,
    OutputFamily,
    ProfileConstraint,
    ScoreComponentStatus,
)
from app.db.models_profile import ClaimStatus, Evidence, ProfileClaim, ProfileClaimEvidence, TaxonomyTerm
from app.services.direction.candidates import generate_candidates
from app.services.direction.confidence import classify_evidence_tier, dominant_tier
from app.services.direction.config import get_active_ranking_policy, get_active_scoring_config
from app.services.direction.constraints import derive_profile_constraints, gate_blocks, run_hard_constraint_gate
from app.services.direction.dedup import find_duplicate_groups
from app.services.direction.dimension_mapping import MappingStatus, map_claims
from app.services.direction.ranking import DirectionOutcomeBundle, _sort_key, rank_directions
from app.services.direction.scoring.aggregate import aggregate_family
from app.services.direction.scoring.base import (
    CAREER_CHARACTERISTIC_KEYS,
    WORK_CONTEXT_KEYS,
    CareerRequirementRef,
    CareerSkillRef,
    ScoreContext,
)
from app.services.direction.scoring.evidence_confidence import EvidenceConfidenceContext, compute_evidence_confidence
from app.services.direction.threshold import ThresholdReason, evaluate_minimum_profile
from app.services.direction.versions import (
    CONSTRAINT_TAXONOMY_VERSION,
    DIMENSION_MAPPING_VERSION,
    DIRECTION_ENGINE_VERSION,
    DIRECTION_EVALUATION_MODEL_VERSION,
    EVIDENCE_STANDARD_VERSION,
    METHODOLOGY_VERSION,
    RANKING_POLICY_VERSION,
    SUBDIMENSION_TAXONOMY_VERSION,
)
from app.services.events import emit_event
from app.services.exceptions import DirectionGenerationInProgressError, NoCurrentProfileError
from app.services.knowledge.retrieval import CareerDetails, get_career_details
from app.services.knowledge.versioning import get_current_knowledge_version, get_knowledge_version
from app.services.profile.generation import get_current_profile

__all__ = ["generate_directions"]

# Skills are Stage 2 `app.db.models_profile.TaxonomyTerm` rows -- Stage 3A's
# `CareerSkill.skill_term_id` references `taxonomy_terms.id` directly (see
# models_knowledge's module docstring, "skills are Taxonomy content, not a
# new Skill table"). There is no separate knowledge-side TaxonomyTerm.

_THRESHOLD_REASON_TO_CLARIFICATION = {
    ThresholdReason.PROFILE_NOT_READY: ClarificationReason.MISSING_DIMENSION,
    ThresholdReason.INSUFFICIENT_SUPPORTED_CLAIMS: ClarificationReason.LOW_CONFIDENCE_COVERAGE,
    ThresholdReason.INSUFFICIENT_DIMENSION_COVERAGE: ClarificationReason.MISSING_DIMENSION,
}


async def generate_directions(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    knowledge_base_version_id: uuid.UUID | None = None,
    hard_confirmed_claim_ids: set[uuid.UUID] | None = None,
) -> DirectionRun:
    """Generate (or attempt to generate) one Direction Intelligence run for
    a user.

    `hard_confirmed_claim_ids` is the ONLY way a constraint claim is
    treated as hard+confirmed (see `constraints.derive_profile_constraints`)
    -- v0.1 has no automatic classifier from assessment text, by Founder
    decision. Absent a real signal source (a later slice's consultant-
    confirmation step), pass `None` and every derived constraint stays
    soft, exactly as it does in an unconfirmed profile.

    Raises `DirectionGenerationInProgressError` if a GENERATING run already
    exists for this user, `NoCurrentProfileError` if the user has no
    `PotentialProfile` at all (there is nothing to pin `DirectionRun.
    profile_id` to). A profile that exists but is not yet READY, or is
    READY but below the minimum-evidence threshold, still produces a
    persisted `DirectionRun` -- with `status=INSUFFICIENT_INFORMATION` and
    `ClarificationRequest` rows, never a failure and never a fabricated
    recommendation.
    """
    in_flight = (
        await session.execute(
            select(DirectionRun.id).where(
                DirectionRun.user_id == user_id, DirectionRun.status == DirectionRunStatus.GENERATING
            )
        )
    ).scalar_one_or_none()
    if in_flight is not None:
        raise DirectionGenerationInProgressError(f"user {user_id} already has a direction generation in progress")

    profile = await get_current_profile(session, user_id=user_id)
    if profile is None:
        raise NoCurrentProfileError(f"user {user_id} has no PotentialProfile -- generate one before Direction Intelligence")

    scoring_config = await get_active_scoring_config(session)
    ranking_policy = await get_active_ranking_policy(session)
    kb_version = (
        await get_knowledge_version(session, knowledge_base_version_id)
        if knowledge_base_version_id is not None
        else await get_current_knowledge_version(session)
    )

    claims = (
        await session.execute(select(ProfileClaim).where(ProfileClaim.profile_id == profile.id))
    ).scalars().all()
    mapped_claims = map_claims(list(claims))

    next_version = (
        await session.execute(select(func.coalesce(func.max(DirectionRun.version), 0)).where(DirectionRun.user_id == user_id))
    ).scalar_one() + 1
    previous_current = (
        await session.execute(
            select(DirectionRun).where(DirectionRun.user_id == user_id, DirectionRun.is_current.is_(True))
        )
    ).scalar_one_or_none()

    run = DirectionRun(
        user_id=user_id,
        profile_id=profile.id,
        knowledge_base_version_id=kb_version.id,
        scoring_config_id=scoring_config.id,
        ranking_policy_id=ranking_policy.id,
        version=next_version,
        status=DirectionRunStatus.GENERATING,
        is_current=False,
        methodology_version=METHODOLOGY_VERSION,
        direction_engine_version=DIRECTION_ENGINE_VERSION,
        direction_evaluation_model_version=DIRECTION_EVALUATION_MODEL_VERSION,
        ranking_policy_version=RANKING_POLICY_VERSION,
        dimension_mapping_version=DIMENSION_MAPPING_VERSION,
        subdimension_taxonomy_version=SUBDIMENSION_TAXONOMY_VERSION,
        constraint_taxonomy_version=CONSTRAINT_TAXONOMY_VERSION,
        evidence_standard_version=EVIDENCE_STANDARD_VERSION,
        supersedes_id=previous_current.id if previous_current is not None else None,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    emit_event(
        "direction_generation_started", user_id=str(user_id), run_id=str(run.id),
        profile_id=str(profile.id), knowledge_base_version_id=str(kb_version.id), version=run.version,
    )

    threshold_result = evaluate_minimum_profile(
        profile_status=profile.status.value,
        profile_is_current=profile.is_current,
        mapped_claims=mapped_claims,
        thresholds=scoring_config.thresholds,
    )

    if not threshold_result.passed:
        await _persist_insufficient_information(session, run, threshold_result, previous_current)
        emit_event(
            "direction_generation_completed", user_id=str(user_id), run_id=str(run.id),
            status=DirectionRunStatus.INSUFFICIENT_INFORMATION.value, direction_count=0,
        )
        return run

    try:
        directions_created = await _generate_and_persist_directions(
            session,
            run=run,
            profile_id=profile.id,
            mapped_claims=mapped_claims,
            kb_version_id=kb_version.id,
            scoring_config=scoring_config,
            ranking_policy=ranking_policy,
            hard_confirmed_claim_ids=hard_confirmed_claim_ids or set(),
        )

        await _mark_previous_not_current(session, user_id=user_id, keep_run_id=run.id)
        run.status = DirectionRunStatus.READY
        run.is_current = True
        run.generated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(run)

        emit_event(
            "direction_generation_completed", user_id=str(user_id), run_id=str(run.id),
            status=DirectionRunStatus.READY.value, direction_count=directions_created,
        )
        return run

    except Exception as exc:
        # Never persist raw exception text (Section 24 precedent) -- only
        # the exception's type. The previous successful run (if any) was
        # never touched by `_mark_previous_not_current`, which only runs
        # on the success path above -- it stays `is_current`.
        run.status = DirectionRunStatus.FAILED
        run.failure_reason = f"{type(exc).__name__} during direction generation"
        await session.commit()
        emit_event(
            "direction_generation_failed", user_id=str(user_id), run_id=str(run.id), error_type=type(exc).__name__,
        )
        raise


async def _persist_insufficient_information(session, run: DirectionRun, threshold_result, previous_current) -> None:
    reason = _THRESHOLD_REASON_TO_CLARIFICATION.get(threshold_result.reason, ClarificationReason.MISSING_DIMENSION)
    if threshold_result.reason == ThresholdReason.PROFILE_NOT_READY:
        topic = "The current PotentialProfile is not READY/current yet -- Direction Intelligence needs a completed profile."
        dimension = None
    elif threshold_result.reason == ThresholdReason.INSUFFICIENT_SUPPORTED_CLAIMS:
        topic = (
            f"Only {threshold_result.supported_claim_count}/{threshold_result.required_supported_claims} "
            "required SUPPORTED claims exist."
        )
        dimension = None
    else:
        missing = threshold_result.missing_dimension_hint
        dimension = missing[0] if missing else None
        topic = (
            f"Only {len(threshold_result.canonical_dimensions_covered)}/{threshold_result.required_canonical_dimensions} "
            f"required canonical dimensions covered. Missing: {', '.join(missing)}."
        )

    session.add(
        ClarificationRequest(
            run_id=run.id, reason=reason, canonical_dimension=dimension,
            related_claim_ids=[], suggested_question_topic=topic,
        )
    )
    await _mark_previous_not_current(session, user_id=run.user_id, keep_run_id=run.id)
    run.status = DirectionRunStatus.INSUFFICIENT_INFORMATION
    run.is_current = True
    run.generated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(run)


async def _mark_previous_not_current(session, *, user_id: uuid.UUID, keep_run_id: uuid.UUID) -> None:
    current_rows = (
        await session.execute(select(DirectionRun).where(DirectionRun.user_id == user_id, DirectionRun.is_current.is_(True)))
    ).scalars().all()
    for row in current_rows:
        if row.id != keep_run_id:
            row.is_current = False
    await session.flush()


async def _resolve_skill_term_keys(session: AsyncSession, term_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not term_ids:
        return {}
    rows = (
        await session.execute(select(TaxonomyTerm.id, TaxonomyTerm.term_key).where(TaxonomyTerm.id.in_(term_ids)))
    ).all()
    return {row[0]: row[1] for row in rows}


def _kb_completeness(career, work_context) -> float:
    values = [getattr(career, k) for k in CAREER_CHARACTERISTIC_KEYS]
    if work_context is not None:
        values += [getattr(work_context, k) for k in WORK_CONTEXT_KEYS]
    else:
        values += [None] * len(WORK_CONTEXT_KEYS)
    if not values:
        return 0.0
    return sum(1 for v in values if v is not None) / len(values)


async def _generate_and_persist_directions(
    session: AsyncSession,
    *,
    run: DirectionRun,
    profile_id: uuid.UUID,
    mapped_claims: list,
    kb_version_id: uuid.UUID,
    scoring_config,
    ranking_policy,
    hard_confirmed_claim_ids: set[uuid.UUID],
) -> int:
    shortlist_cap = int((scoring_config.thresholds or {}).get("candidate_shortlist_cap", 0)) or None
    candidates = await generate_candidates(session, knowledge_base_version_id=kb_version_id, shortlist_cap=shortlist_cap)
    emit_event(
        "direction_candidates_generated", user_id=str(run.user_id), run_id=str(run.id), candidate_count=len(candidates)
    )
    if not candidates:
        return 0

    details_by_code: dict[str, CareerDetails] = {}
    for candidate in candidates:
        details_by_code[candidate.career_code] = await get_career_details(session, candidate.career_id)

    # -- profile-level (career-independent) evidence-confidence inputs --
    contradiction_count = sum(
        1
        for mc in mapped_claims
        if mc.status is MappingStatus.MAPPED and mc.claim_status == ClaimStatus.CONTRADICTED.value
    )

    # -- hard constraint specs + persisted ProfileConstraint rows (once per profile) --
    constraint_specs = derive_profile_constraints(mapped_claims, hard_confirmed_claim_ids=hard_confirmed_claim_ids)
    profile_constraint_id_by_key = await _persist_profile_constraints(session, profile_id=profile_id, specs=constraint_specs)

    # -- resolve CareerSkill.skill_term_id -> term_key once for every candidate --
    all_term_ids = {skill.skill_term_id for details in details_by_code.values() for skill in details.skills}
    term_key_by_id = await _resolve_skill_term_keys(session, all_term_ids)

    per_candidate: dict[str, dict] = {}
    for candidate in candidates:
        details = details_by_code[candidate.career_code]
        career = details.career

        ctx = ScoreContext(
            mapped_claims=tuple(mapped_claims),
            career_code=career.code,
            career_domain=career.domain.value,
            career_characteristics={k: getattr(career, k) for k in CAREER_CHARACTERISTIC_KEYS},
            work_context=(
                {k: getattr(details.work_context, k) for k in WORK_CONTEXT_KEYS} if details.work_context else {}
            ),
            career_skills=tuple(
                CareerSkillRef(term_key=term_key_by_id[s.skill_term_id], requirement_type=s.requirement_type.value)
                for s in details.skills
                if s.skill_term_id in term_key_by_id
            ),
            career_requirements=tuple(
                CareerRequirementRef(category=r.category.value, certainty=r.certainty.value) for r in details.requirements
            ),
        )

        pf_components = _score_family(OutputFamily.POTENTIAL_FIT, scoring_config, ctx)
        ga_components = _score_family(OutputFamily.GOAL_ALIGNMENT, scoring_config, ctx)
        tf_components = _score_family(OutputFamily.TRANSITION_FEASIBILITY, scoring_config, ctx)

        pf_outcome = aggregate_family(
            OutputFamily.POTENTIAL_FIT, pf_components,
            weights=scoring_config.component_weights.get("potential_fit", {}), thresholds=scoring_config.thresholds,
        )
        ga_outcome = aggregate_family(
            OutputFamily.GOAL_ALIGNMENT, ga_components,
            weights=scoring_config.component_weights.get("goal_alignment", {}), thresholds=scoring_config.thresholds,
        )
        tf_outcome = aggregate_family(
            OutputFamily.TRANSITION_FEASIBILITY, tf_components,
            weights=scoring_config.component_weights.get("transition_feasibility", {}), thresholds=scoring_config.thresholds,
        )

        ec_outcome, ec_evidence_ids = await _compute_evidence_confidence(
            session,
            all_components=(*pf_components, *ga_components, *tf_components),
            mapped_claims=mapped_claims,
            fit_outputs_with_raw=sum(1 for fo in (pf_outcome, ga_outcome, tf_outcome) if fo.raw is not None),
            contradiction_count=contradiction_count,
            kb_completeness=_kb_completeness(career, details.work_context),
            thresholds=scoring_config.thresholds,
        )

        constraint_outcomes = run_hard_constraint_gate(
            constraint_specs, career_ref=career.code, career_requirements=details.requirements
        )
        hard_blocked = gate_blocks(constraint_outcomes)

        tf_skill_component = next((c for c in tf_components if c.component_key == "tf_skill_gap"), None)
        skills_to_verify = (
            list(tf_skill_component.contributing_career_attributes.get("skills_to_verify", []))
            if tf_skill_component
            else []
        )

        per_candidate[career.code] = dict(
            career=career,
            details=details,
            pf_components=pf_components,
            ga_components=ga_components,
            tf_components=tf_components,
            pf_outcome=pf_outcome,
            ga_outcome=ga_outcome,
            tf_outcome=tf_outcome,
            ec_outcome=ec_outcome,
            ec_evidence_ids=ec_evidence_ids,
            constraint_outcomes=constraint_outcomes,
            hard_blocked=hard_blocked,
            skills_to_verify=skills_to_verify,
        )

    # -- material differentiation: exact-collision dedup only, never a guessed threshold --
    careers_list = [v["career"] for v in per_candidate.values()]
    aliases_by_career = {v["career"].id: v["details"].aliases for v in per_candidate.values()}
    duplicate_groups = find_duplicate_groups(careers_list, aliases_by_career)

    excluded_codes: set[str] = set()
    dedup_info: dict[str, tuple[str, str]] = {}  # code -> (canonical_code, reason)
    diversity_warning_codes: set[str] = set()
    for group in duplicate_groups:
        bundles_in_group = [
            DirectionOutcomeBundle(
                career_code=code, domain=per_candidate[code]["career"].domain.value,
                hard_blocked=per_candidate[code]["hard_blocked"], potential_fit=per_candidate[code]["pf_outcome"],
                goal_alignment=per_candidate[code]["ga_outcome"], transition_feasibility=per_candidate[code]["tf_outcome"],
                evidence_confidence=per_candidate[code]["ec_outcome"],
            )
            for code in group
        ]
        canonical = min(bundles_in_group, key=_sort_key).career_code
        for code in group:
            if code != canonical:
                excluded_codes.add(code)
                dedup_info[code] = (
                    canonical,
                    f"Exact KB title/alias collision with career_code={canonical!r} in the same KnowledgeBaseVersion "
                    "-- the stronger-scoring recommendation was kept (deterministic exact-match dedup only, no "
                    "similarity threshold).",
                )
        diversity_warning_codes.add(canonical)

    eligible_bundles = [
        DirectionOutcomeBundle(
            career_code=code, domain=v["career"].domain.value, hard_blocked=v["hard_blocked"],
            potential_fit=v["pf_outcome"], goal_alignment=v["ga_outcome"], transition_feasibility=v["tf_outcome"],
            evidence_confidence=v["ec_outcome"],
        )
        for code, v in per_candidate.items()
        if code not in excluded_codes
    ]
    ranked = {r.career_code: r for r in rank_directions(eligible_bundles, policy=ranking_policy.policy)}

    directions_created = 0
    for code, v in per_candidate.items():
        career = v["career"]
        if code in excluded_codes:
            canonical_code, reason = dedup_info[code]
            placement = DirectionPlacement.DEDUPED
            rank_within = None
            trade_off_notes = None
            duplicate_of = canonical_code
            dedup_reason = reason
            diversity_warning = None
        else:
            ranked_entry = ranked[code]
            placement = ranked_entry.placement
            rank_within = ranked_entry.rank_within_placement
            trade_off_notes = ranked_entry.trade_off_notes
            duplicate_of = None
            dedup_reason = None
            diversity_warning = (
                "A duplicate-titled KB entry for this career was folded into this recommendation "
                "(see other DEDUPED directions in this run)."
                if code in diversity_warning_codes and placement in (DirectionPlacement.MAIN, DirectionPlacement.ALTERNATIVE)
                else None
            )

        direction = Direction(
            run_id=run.id, career_id=career.id, career_code=career.code, domain=career.domain.value,
            placement=placement, rank_within_placement=rank_within, trade_off_notes=trade_off_notes,
            potential_fit_raw_experimental=v["pf_outcome"].raw, potential_fit_band=v["pf_outcome"].band,
            potential_fit_coverage_ratio=v["pf_outcome"].coverage_ratio,
            potential_fit_scored_component_count=v["pf_outcome"].scored_component_count,
            goal_alignment_raw_experimental=v["ga_outcome"].raw, goal_alignment_band=v["ga_outcome"].band,
            goal_alignment_coverage_ratio=v["ga_outcome"].coverage_ratio,
            goal_alignment_scored_component_count=v["ga_outcome"].scored_component_count,
            transition_feasibility_raw_experimental=v["tf_outcome"].raw, transition_feasibility_band=v["tf_outcome"].band,
            transition_feasibility_coverage_ratio=v["tf_outcome"].coverage_ratio,
            transition_feasibility_scored_component_count=v["tf_outcome"].scored_component_count,
            evidence_confidence_raw_experimental=v["ec_outcome"].raw_experimental,
            evidence_confidence_band=v["ec_outcome"].band, evidence_confidence_coverage_note=v["ec_outcome"].coverage_note,
            skills_to_verify=v["skills_to_verify"], duplicate_of_career_code=duplicate_of, dedup_reason=dedup_reason,
            diversity_warning=diversity_warning,
        )
        session.add(direction)
        await session.flush()
        directions_created += 1

        for component in (*v["pf_components"], *v["ga_components"], *v["tf_components"]):
            session.add(
                DirectionScoreComponent(
                    direction_id=direction.id, output_family=component.family, component_key=component.component_key,
                    status=component.status, raw_score=component.raw_score,
                    weight_applied=(
                        float(scoring_config.component_weights.get(component.family.value, {}).get(component.component_key, 1.0))
                        if component.status is ScoreComponentStatus.SCORED
                        else 0.0
                    ),
                    scoring_config_id=scoring_config.id, rationale=component.rationale,
                    contributing_claim_ids=[str(c) for c in component.contributing_claim_ids],
                    contributing_career_attributes=component.contributing_career_attributes,
                )
            )

        for outcome in v["constraint_outcomes"]:
            key = (outcome.source_claim_id, outcome.constraint_subtype)
            session.add(
                DirectionConstraintCheck(
                    direction_id=direction.id, profile_constraint_id=profile_constraint_id_by_key.get(key),
                    constraint_subtype=outcome.constraint_subtype, career_attribute_ref=outcome.career_attribute_ref,
                    result=outcome.result, is_hard=outcome.is_hard, explanation=outcome.explanation,
                )
            )

        if placement in (DirectionPlacement.MAIN, DirectionPlacement.ALTERNATIVE):
            direction.explanation_bundle = _build_explanation_bundle(
                career=career, details=v["details"], pf_components=v["pf_components"], ga_components=v["ga_components"],
                tf_components=v["tf_components"], ec_outcome=v["ec_outcome"], ec_evidence_ids=v["ec_evidence_ids"],
                skills_to_verify=v["skills_to_verify"], trade_off_notes=trade_off_notes,
                contradiction_count=contradiction_count, kb_version_id=kb_version_id, scoring_config=scoring_config,
                ranking_policy=ranking_policy,
            )

        await session.commit()

    return directions_created


def _score_family(family: OutputFamily, scoring_config, ctx: ScoreContext) -> list:
    from app.services.direction.scoring.components import score_family as _score

    keys = scoring_config.enabled_components.get(family.value, [])
    return _score(keys, ctx)


async def _compute_evidence_confidence(
    session: AsyncSession,
    *,
    all_components,
    mapped_claims,
    fit_outputs_with_raw: int,
    contradiction_count: int,
    kb_completeness: float,
    thresholds: dict,
):
    contributing_ids: set[uuid.UUID] = set()
    for component in all_components:
        if component.status is ScoreComponentStatus.SCORED:
            contributing_ids.update(cid for cid in component.contributing_claim_ids if cid is not None)

    claim_confidence_by_id = {mc.source_claim_id: mc.claim_confidence for mc in mapped_claims}
    supporting_confidences = [claim_confidence_by_id[cid] for cid in contributing_ids if cid in claim_confidence_by_id]

    evidence_by_claim: dict[uuid.UUID, list[Evidence]] = {}
    evidence_ids: list[uuid.UUID] = []
    if contributing_ids:
        rows = (
            await session.execute(
                select(ProfileClaimEvidence.claim_id, Evidence)
                .join(Evidence, Evidence.id == ProfileClaimEvidence.evidence_id)
                .where(ProfileClaimEvidence.claim_id.in_(contributing_ids))
            )
        ).all()
        for claim_id, evidence in rows:
            evidence_by_claim.setdefault(claim_id, []).append(evidence)
            evidence_ids.append(evidence.id)

    tiers = [
        classify_evidence_tier(evidence_by_claim.get(cid, []), is_contradictory=False) for cid in contributing_ids
    ]
    distinct_source_types = {e.source_type.value for items in evidence_by_claim.values() for e in items}

    ctx = EvidenceConfidenceContext(
        supporting_claim_confidences=supporting_confidences,
        dominant_evidence_tier=dominant_tier(tiers),
        distinct_source_type_count=len(distinct_source_types),
        fit_outputs_with_raw=fit_outputs_with_raw,
        contradiction_count=contradiction_count,
        kb_completeness=kb_completeness,
    )
    return compute_evidence_confidence(ctx, thresholds=thresholds), evidence_ids


async def _persist_profile_constraints(session: AsyncSession, *, profile_id: uuid.UUID, specs) -> dict:
    if not specs:
        return {}
    existing = (
        await session.execute(select(ProfileConstraint).where(ProfileConstraint.profile_id == profile_id))
    ).scalars().all()
    existing_keys = {(row.source_claim_id, row.constraint_subtype): row.id for row in existing}

    for spec in specs:
        key = (spec.source_claim_id, spec.constraint_subtype)
        if key in existing_keys:
            continue
        row = ProfileConstraint(
            profile_id=profile_id, source_claim_id=spec.source_claim_id, constraint_subtype=spec.constraint_subtype,
            constraint_taxonomy_version=spec.constraint_taxonomy_version, normalized_value=spec.normalized_value,
            is_hard=spec.is_hard, is_confirmed=spec.is_confirmed, confidence=spec.confidence,
        )
        session.add(row)
        await session.flush()
        existing_keys[key] = row.id

    await session.commit()
    return existing_keys


def _top_components(components, *, limit: int = 3) -> list[dict]:
    scored = [c for c in components if c.status is ScoreComponentStatus.SCORED and c.raw_score is not None]
    scored.sort(key=lambda c: c.raw_score, reverse=True)
    return [
        {"component_key": c.component_key, "raw_score_experimental": c.raw_score, "rationale": c.rationale}
        for c in scored[:limit]
    ]


def _build_explanation_bundle(
    *,
    career,
    details: CareerDetails,
    pf_components,
    ga_components,
    tf_components,
    ec_outcome,
    ec_evidence_ids,
    skills_to_verify,
    trade_off_notes,
    contradiction_count,
    kb_version_id,
    scoring_config,
    ranking_policy,
) -> dict:
    """Structured backend explanation data for consultant review and a
    later narrative-generation slice -- deliberately NOT polished client
    prose (plan section 8)."""
    all_contributing_claim_ids: set[uuid.UUID] = set()
    for component in (*pf_components, *ga_components, *tf_components):
        all_contributing_claim_ids.update(cid for cid in component.contributing_claim_ids if cid is not None)

    tf_skill = next((c for c in tf_components if c.component_key == "tf_skill_gap"), None)
    confirmed_gaps = list(tf_skill.contributing_career_attributes.get("confirmed_missing", [])) if tf_skill else []
    transferable = _top_components(tf_components)

    return {
        "why_fit": {"strongest_supported_factors": _top_components(pf_components)},
        "why_now": {
            "goal_alignment_factors": _top_components(ga_components),
            "note": None if any(c.status is ScoreComponentStatus.SCORED for c in ga_components) else (
                "No structured career-side Goal Alignment data available yet (v0.1 known limitation)."
            ),
        },
        "transition": {
            "transferable_factors": transferable,
            "confirmed_gaps": confirmed_gaps,
            "skills_to_verify": list(skills_to_verify),
            "trade_offs": trade_off_notes,
        },
        "confidence": {
            "band": ec_outcome.band.value if ec_outcome.band else None,
            "coverage_note": ec_outcome.coverage_note,
            "contradiction_count": contradiction_count,
        },
        "provenance": {
            "contributing_claim_ids": sorted(str(c) for c in all_contributing_claim_ids),
            "evidence_ids": sorted({str(e) for e in ec_evidence_ids}),
            "career_id": str(career.id),
            "career_requirement_ids": [str(r.id) for r in details.requirements],
            "knowledge_base_version_id": str(kb_version_id),
            "scoring_config_version": scoring_config.version,
            "ranking_policy_version": ranking_policy.version,
            "methodology_version": METHODOLOGY_VERSION,
        },
    }
