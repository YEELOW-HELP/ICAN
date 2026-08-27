"""Stage 3B Slice 3 §2/§3: the deterministic Critic (Founder Methodology
Contract v0.1 decision I -- "v0.1 critic is deterministic first").

`run_critic()` inspects a completed `DirectionRun` and its persisted
`Direction`/`DirectionScoreComponent`/`DirectionConstraintCheck` rows
INDEPENDENTLY of the orchestrator that produced them -- a second,
separate pass, exactly so a real orchestrator bug (not just a
methodology gap) has a chance of being caught before a consultant ever
sees the run. No arbitrary semantic-similarity thresholds (decision I) --
every numeric cutoff here comes from the versioned, EXPERIMENTAL
`ScoringConfig.thresholds` (see `config.py`'s `critic_*` keys), never a
bare number in this module.

A `DirectionRun` with an unresolved BLOCKER finding may never be
consultant-approved (`app/services/direction/review.py::approve_run`
re-checks this independently at approval time).

Findings never carry raw CV/answer text -- only IDs, counts, bands, and a
deterministic, templated `message` string built from those.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_direction import (
    ConstraintCheckResult,
    CriticSeverity,
    Direction,
    DirectionConstraintCheck,
    DirectionCriticFinding,
    DirectionPlacement,
    DirectionRun,
    DirectionScoreComponent,
    OutputFamily,
    QualitativeBand,
    RankingPolicy,
    ScoreComponentStatus,
    ScoringConfig,
)
from app.db.models_knowledge import CareerWorkContext
from app.db.models_profile import Evidence, ProfileClaim
from app.services.direction.versions import DIRECTION_ENGINE_VERSION
from app.services.events import emit_event
from app.services.knowledge.retrieval import get_career, get_career_requirements
from app.services.exceptions import CareerNotFoundError, NoCurrentDirectionRunError

__all__ = ["CriticCode", "run_critic"]

_RECOMMENDED_PLACEMENTS = (DirectionPlacement.MAIN, DirectionPlacement.ALTERNATIVE)


class CriticCode:
    BLOCKED_CAREER_IN_RECOMMENDATION = "blocked_career_in_recommendation"
    CAREER_NOT_IN_PINNED_KB = "career_not_in_pinned_kb"
    EXPLANATION_REFERENCES_NONEXISTENT_CLAIM = "explanation_references_nonexistent_claim"
    EXPLANATION_REFERENCES_NONEXISTENT_EVIDENCE = "explanation_references_nonexistent_evidence"
    EXPLANATION_REFERENCES_NONEXISTENT_CAREER = "explanation_references_nonexistent_career"
    EXPLANATION_REFERENCES_UNSUPPORTED_REQUIREMENT = "explanation_references_unsupported_requirement"
    SCORE_CONFLICTS_WITH_COMPONENTS = "score_conflicts_with_components"
    MISSING_PROVENANCE_VERSION = "missing_provenance_version"
    DUPLICATE_CAREER_IN_RECOMMENDATIONS = "duplicate_career_in_recommendations"
    INVALID_RANKING_PLACEMENT = "invalid_ranking_placement"

    LOW_EVIDENCE_CONFIDENCE = "low_evidence_confidence"
    LOW_COVERAGE = "low_coverage"
    UNRESOLVED_CONTRADICTION = "unresolved_contradiction"
    GOAL_ALIGNMENT_UNKNOWN = "goal_alignment_unknown"
    TRANSITION_FEASIBILITY_UNKNOWN = "transition_feasibility_unknown"
    MANY_SKILLS_TO_VERIFY = "many_skills_to_verify"
    LOW_GOAL_ALIGNMENT_ON_ALTERNATIVE = "low_goal_alignment_on_alternative"
    LOW_TRANSITION_FEASIBILITY_ON_ALTERNATIVE = "low_transition_feasibility_on_alternative"
    INSUFFICIENT_DIRECTION_DIVERSITY = "insufficient_direction_diversity"
    WEAK_KB_PROVENANCE = "weak_kb_provenance"


@dataclass(frozen=True)
class _Finding:
    direction_id: uuid.UUID | None
    severity: CriticSeverity
    code: str
    message: str
    related_claim_ids: list[str] | None = None
    related_evidence_ids: list[str] | None = None
    related_career_ids: list[str] | None = None
    related_requirement_ids: list[str] | None = None


async def run_critic(session: AsyncSession, *, run_id: uuid.UUID) -> list[DirectionCriticFinding]:
    """Deterministic, re-runnable: calling this twice for the same run
    produces the same findings from the same persisted data (it does not
    delete/replace previous findings -- callers that want a fresh pass
    should treat existing findings as historical, consistent with this
    codebase's append-only-audit conventions)."""
    run = await session.get(DirectionRun, run_id)
    if run is None:
        raise NoCurrentDirectionRunError(f"DirectionRun {run_id} does not exist")

    directions = (await session.execute(select(Direction).where(Direction.run_id == run_id))).scalars().all()
    findings: list[_Finding] = []

    findings.extend(await _check_run_level(session, run=run, directions=directions))
    for direction in directions:
        findings.extend(await _check_direction(session, run=run, direction=direction))

    rows = [
        DirectionCriticFinding(
            run_id=run_id, direction_id=f.direction_id, severity=f.severity, code=f.code, message=f.message,
            related_claim_ids=f.related_claim_ids, related_evidence_ids=f.related_evidence_ids,
            related_career_ids=f.related_career_ids, related_requirement_ids=f.related_requirement_ids,
            engine_version=DIRECTION_ENGINE_VERSION,
        )
        for f in findings
    ]
    session.add_all(rows)
    await session.commit()
    for row in rows:
        await session.refresh(row)

    blocker_count = sum(1 for r in rows if r.severity is CriticSeverity.BLOCKER)
    warning_count = sum(1 for r in rows if r.severity is CriticSeverity.WARNING)
    emit_event(
        "direction_critic_completed", run_id=str(run_id), blocker_count=blocker_count, warning_count=warning_count,
        total_findings=len(rows),
    )
    return rows


async def _check_run_level(session: AsyncSession, *, run: DirectionRun, directions: list[Direction]) -> list[_Finding]:
    findings: list[_Finding] = []

    # BLOCKER: missing required provenance/version on the run itself.
    required_version_fields = (
        "methodology_version", "direction_engine_version", "direction_evaluation_model_version",
        "ranking_policy_version", "dimension_mapping_version", "subdimension_taxonomy_version",
        "constraint_taxonomy_version", "evidence_standard_version",
    )
    missing = [f for f in required_version_fields if not getattr(run, f)]
    if missing or run.scoring_config_id is None or run.ranking_policy_id is None or run.knowledge_base_version_id is None:
        findings.append(
            _Finding(
                None, CriticSeverity.BLOCKER, CriticCode.MISSING_PROVENANCE_VERSION,
                f"DirectionRun {run.id} is missing required provenance/version fields: {missing}",
            )
        )

    # BLOCKER: duplicate career recommended more than once.
    recommended = [d for d in directions if d.placement in _RECOMMENDED_PLACEMENTS]
    seen_career_ids: dict[uuid.UUID, Direction] = {}
    for d in recommended:
        if d.career_id in seen_career_ids:
            findings.append(
                _Finding(
                    d.id, CriticSeverity.BLOCKER, CriticCode.DUPLICATE_CAREER_IN_RECOMMENDATIONS,
                    f"career_id {d.career_id} appears more than once among MAIN/ALTERNATIVE recommendations "
                    f"in run {run.id} ({seen_career_ids[d.career_id].career_code!r} and {d.career_code!r})",
                    related_career_ids=[str(d.career_id)],
                )
            )
        else:
            seen_career_ids[d.career_id] = d

    # BLOCKER: invalid RankingPolicy placement -- pool sizes exceeded.
    ranking_policy = await session.get(RankingPolicy, run.ranking_policy_id)
    policy = (ranking_policy.policy or {}) if ranking_policy is not None else {}
    main_max = int(policy.get("main_max", 3))
    alt_max = int(policy.get("alternative_max", 3))
    main_count = sum(1 for d in directions if d.placement is DirectionPlacement.MAIN)
    alt_count = sum(1 for d in directions if d.placement is DirectionPlacement.ALTERNATIVE)
    if main_count > main_max or alt_count > alt_max:
        findings.append(
            _Finding(
                None, CriticSeverity.BLOCKER, CriticCode.INVALID_RANKING_PLACEMENT,
                f"run {run.id} has {main_count} MAIN (max {main_max}) and {alt_count} ALTERNATIVE (max {alt_max}) -- pool size exceeded",
            )
        )

    # WARNING: insufficient direction diversity -- any DEDUPED collision found.
    if any(d.placement is DirectionPlacement.DEDUPED for d in directions):
        findings.append(
            _Finding(
                None, CriticSeverity.WARNING, CriticCode.INSUFFICIENT_DIRECTION_DIVERSITY,
                f"run {run.id} folded one or more exact-duplicate KB careers via dedup -- verify Career KB curation",
            )
        )

    return findings


async def _check_direction(session: AsyncSession, *, run: DirectionRun, direction: Direction) -> list[_Finding]:
    findings: list[_Finding] = []
    thresholds = await _active_thresholds(session, run)

    # BLOCKER: career does not belong to the pinned/published KB.
    try:
        career = await get_career(session, direction.career_id)
    except CareerNotFoundError:
        findings.append(
            _Finding(
                direction.id, CriticSeverity.BLOCKER, CriticCode.CAREER_NOT_IN_PINNED_KB,
                f"direction {direction.id} references career_id {direction.career_id}, which does not exist",
                related_career_ids=[str(direction.career_id)],
            )
        )
        career = None
    if career is not None and career.knowledge_base_version_id != run.knowledge_base_version_id:
        findings.append(
            _Finding(
                direction.id, CriticSeverity.BLOCKER, CriticCode.CAREER_NOT_IN_PINNED_KB,
                f"direction {direction.id}'s career {career.id} belongs to KnowledgeBaseVersion "
                f"{career.knowledge_base_version_id}, not the run's pinned {run.knowledge_base_version_id}",
                related_career_ids=[str(career.id)],
            )
        )

    # BLOCKER: a hard-blocked career appears in a recommendation.
    checks = (
        await session.execute(select(DirectionConstraintCheck).where(DirectionConstraintCheck.direction_id == direction.id))
    ).scalars().all()
    is_hard_blocked = any(c.result == ConstraintCheckResult.BLOCK and c.is_hard for c in checks)
    if is_hard_blocked and direction.placement in _RECOMMENDED_PLACEMENTS:
        findings.append(
            _Finding(
                direction.id, CriticSeverity.BLOCKER, CriticCode.BLOCKED_CAREER_IN_RECOMMENDATION,
                f"direction {direction.id} ({direction.career_code}) has a confirmed hard-constraint BLOCK but "
                f"placement={direction.placement.value}",
            )
        )

    # BLOCKER: persisted score conflicts with its own component data.
    components = (
        await session.execute(select(DirectionScoreComponent).where(DirectionScoreComponent.direction_id == direction.id))
    ).scalars().all()
    for family, persisted_raw in (
        (OutputFamily.POTENTIAL_FIT, direction.potential_fit_raw_experimental),
        (OutputFamily.GOAL_ALIGNMENT, direction.goal_alignment_raw_experimental),
        (OutputFamily.TRANSITION_FEASIBILITY, direction.transition_feasibility_raw_experimental),
    ):
        family_components = [c for c in components if c.output_family is family]
        scored = [c for c in family_components if c.status is ScoreComponentStatus.SCORED and c.raw_score is not None]
        if not scored:
            if persisted_raw is not None:
                findings.append(
                    _Finding(
                        direction.id, CriticSeverity.BLOCKER, CriticCode.SCORE_CONFLICTS_WITH_COMPONENTS,
                        f"direction {direction.id} {family.value} raw={persisted_raw} but zero SCORED components exist",
                    )
                )
            continue
        weight_sum = sum(c.weight_applied for c in scored)
        recomputed = (sum(c.raw_score * c.weight_applied for c in scored) / weight_sum) if weight_sum > 0 else None
        if persisted_raw is None or recomputed is None or abs(persisted_raw - recomputed) > 1e-6:
            findings.append(
                _Finding(
                    direction.id, CriticSeverity.BLOCKER, CriticCode.SCORE_CONFLICTS_WITH_COMPONENTS,
                    f"direction {direction.id} {family.value} persisted raw={persisted_raw} does not match "
                    f"recomputed weighted mean {recomputed} from its own SCORED components",
                )
            )

    # BLOCKER: missing required provenance on the direction itself.
    if not direction.career_id or not direction.career_code:
        findings.append(
            _Finding(
                direction.id, CriticSeverity.BLOCKER, CriticCode.MISSING_PROVENANCE_VERSION,
                f"direction {direction.id} is missing career_id/career_code",
            )
        )

    # Explanation-bundle provenance checks (BLOCKER) -- only where a bundle exists.
    if direction.explanation_bundle:
        findings.extend(await _check_explanation_provenance(session, direction=direction, career=career))

    # WARNING checks -- scoped to MAIN/ALTERNATIVE (Critic informs review of
    # what's actually being recommended).
    if direction.placement in _RECOMMENDED_PLACEMENTS:
        findings.extend(_check_direction_warnings(direction, thresholds=thresholds))
        if career is not None:
            findings.extend(await _check_kb_provenance_warning(session, direction=direction, career=career, thresholds=thresholds))

    return findings


async def _check_explanation_provenance(session: AsyncSession, *, direction: Direction, career) -> list[_Finding]:
    findings: list[_Finding] = []
    provenance = (direction.explanation_bundle or {}).get("provenance", {})

    claim_ids_raw = provenance.get("contributing_claim_ids") or []
    claim_ids: list[uuid.UUID] = []
    for cid in claim_ids_raw:
        try:
            claim_ids.append(uuid.UUID(cid))
        except (ValueError, TypeError):
            continue
    if claim_ids:
        existing = set(
            (await session.execute(select(ProfileClaim.id).where(ProfileClaim.id.in_(claim_ids)))).scalars().all()
        )
        missing_claims = [cid for cid in claim_ids if cid not in existing]
        if missing_claims:
            findings.append(
                _Finding(
                    direction.id, CriticSeverity.BLOCKER, CriticCode.EXPLANATION_REFERENCES_NONEXISTENT_CLAIM,
                    f"direction {direction.id}'s explanation_bundle references {len(missing_claims)} ProfileClaim id(s) that do not exist",
                    related_claim_ids=[str(c) for c in missing_claims],
                )
            )

    evidence_ids_raw = provenance.get("evidence_ids") or []
    evidence_ids: list[uuid.UUID] = []
    for eid in evidence_ids_raw:
        try:
            evidence_ids.append(uuid.UUID(eid))
        except (ValueError, TypeError):
            continue
    if evidence_ids:
        existing = set(
            (await session.execute(select(Evidence.id).where(Evidence.id.in_(evidence_ids)))).scalars().all()
        )
        missing_evidence = [eid for eid in evidence_ids if eid not in existing]
        if missing_evidence:
            findings.append(
                _Finding(
                    direction.id, CriticSeverity.BLOCKER, CriticCode.EXPLANATION_REFERENCES_NONEXISTENT_EVIDENCE,
                    f"direction {direction.id}'s explanation_bundle references {len(missing_evidence)} Evidence id(s) that do not exist",
                    related_evidence_ids=[str(e) for e in missing_evidence],
                )
            )

    provenance_career_id = provenance.get("career_id")
    if provenance_career_id and provenance_career_id != str(direction.career_id):
        findings.append(
            _Finding(
                direction.id, CriticSeverity.BLOCKER, CriticCode.EXPLANATION_REFERENCES_NONEXISTENT_CAREER,
                f"direction {direction.id}'s explanation_bundle.provenance.career_id "
                f"{provenance_career_id!r} does not match its own career_id {direction.career_id}",
            )
        )

    requirement_ids_raw = provenance.get("career_requirement_ids") or []
    if requirement_ids_raw and career is not None:
        real_requirement_ids = {str(r.id) for r in await get_career_requirements(session, career.id)}
        unsupported = [rid for rid in requirement_ids_raw if rid not in real_requirement_ids]
        if unsupported:
            findings.append(
                _Finding(
                    direction.id, CriticSeverity.BLOCKER, CriticCode.EXPLANATION_REFERENCES_UNSUPPORTED_REQUIREMENT,
                    f"direction {direction.id}'s explanation_bundle references {len(unsupported)} CareerRequirement "
                    f"id(s) not actually attached to career {career.id}",
                    related_requirement_ids=unsupported,
                )
            )

    return findings


def _check_direction_warnings(direction: Direction, *, thresholds: dict) -> list[_Finding]:
    findings: list[_Finding] = []
    low_coverage = float(thresholds.get("critic_low_coverage_ratio", 0.5))
    many_verify = int(thresholds.get("critic_many_skills_to_verify_count", 3))

    if direction.evidence_confidence_band is QualitativeBand.LOW:
        findings.append(_Finding(direction.id, CriticSeverity.WARNING, CriticCode.LOW_EVIDENCE_CONFIDENCE, f"direction {direction.id} has LOW Evidence Confidence"))

    for family_name, ratio in (
        ("potential_fit", direction.potential_fit_coverage_ratio),
        ("goal_alignment", direction.goal_alignment_coverage_ratio),
        ("transition_feasibility", direction.transition_feasibility_coverage_ratio),
    ):
        if ratio is not None and ratio < low_coverage:
            findings.append(
                _Finding(
                    direction.id, CriticSeverity.WARNING, CriticCode.LOW_COVERAGE,
                    f"direction {direction.id} {family_name} coverage_ratio={ratio:.2f} is below {low_coverage}",
                )
            )

    contradiction_count = ((direction.explanation_bundle or {}).get("confidence") or {}).get("contradiction_count", 0)
    if contradiction_count:
        findings.append(
            _Finding(direction.id, CriticSeverity.WARNING, CriticCode.UNRESOLVED_CONTRADICTION, f"direction {direction.id} has {contradiction_count} unresolved contradiction(s) among its supporting claims")
        )

    if direction.goal_alignment_band is None:
        findings.append(_Finding(direction.id, CriticSeverity.WARNING, CriticCode.GOAL_ALIGNMENT_UNKNOWN, f"direction {direction.id} has unknown (None) Goal Alignment"))
    if direction.transition_feasibility_band is None:
        findings.append(_Finding(direction.id, CriticSeverity.WARNING, CriticCode.TRANSITION_FEASIBILITY_UNKNOWN, f"direction {direction.id} has unknown (None) Transition Feasibility"))

    skills_to_verify = direction.skills_to_verify or []
    if len(skills_to_verify) >= many_verify:
        findings.append(
            _Finding(direction.id, CriticSeverity.WARNING, CriticCode.MANY_SKILLS_TO_VERIFY, f"direction {direction.id} has {len(skills_to_verify)} skills_to_verify (>= {many_verify})")
        )

    if direction.placement is DirectionPlacement.ALTERNATIVE:
        if direction.goal_alignment_band is QualitativeBand.LOW:
            findings.append(_Finding(direction.id, CriticSeverity.WARNING, CriticCode.LOW_GOAL_ALIGNMENT_ON_ALTERNATIVE, f"ALTERNATIVE direction {direction.id} has LOW Goal Alignment"))
        if direction.transition_feasibility_band is QualitativeBand.LOW:
            findings.append(_Finding(direction.id, CriticSeverity.WARNING, CriticCode.LOW_TRANSITION_FEASIBILITY_ON_ALTERNATIVE, f"ALTERNATIVE direction {direction.id} has LOW Transition Feasibility"))

    return findings


async def _check_kb_provenance_warning(session: AsyncSession, *, direction: Direction, career, thresholds: dict) -> list[_Finding]:
    # Local import: pipeline.py imports critic.py's sibling modules
    # transitively at module load time in some call orders, so importing
    # this one specific helper lazily here avoids a circular-import trap.
    from app.services.direction.pipeline import _kb_completeness

    weak_cutoff = float(thresholds.get("critic_weak_kb_completeness_ratio", 0.5))
    wc_row = (
        await session.execute(select(CareerWorkContext).where(CareerWorkContext.career_id == career.id))
    ).scalar_one_or_none()
    completeness = _kb_completeness(career, wc_row)
    if completeness < weak_cutoff:
        return [
            _Finding(
                direction.id, CriticSeverity.WARNING, CriticCode.WEAK_KB_PROVENANCE,
                f"direction {direction.id}'s career {career.code} has weak curated-data completeness "
                f"({completeness:.2f} < {weak_cutoff})",
                related_career_ids=[str(career.id)],
            )
        ]
    return []


async def _active_thresholds(session: AsyncSession, run: DirectionRun) -> dict:
    config = await session.get(ScoringConfig, run.scoring_config_id)
    return (config.thresholds or {}) if config is not None else {}
