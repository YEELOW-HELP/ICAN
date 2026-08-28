"""Stage 3B Slice 3.5: the effective-reviewed-result read model + the
Client Card read model for the Stage 4 Dashboard.

## Effective review projection

`DirectionRun`/`Direction` rows are the immutable system output.
`ConsultantCorrection` rows are an append-only overlay log. Neither is
ever mutated by this module -- `build_reviewed_direction_view()` is a
pure, read-only projection: it loads both, applies SUPPORTED correction
overlays IN MEMORY in deterministic chronological order (`created_at`
ASC, then `id` ASC as a stable tie-break for same-timestamp corrections),
and returns a typed view that keeps SYSTEM and EFFECTIVE values
explicitly distinguishable side by side -- never collapsed into one
field a caller could mistake for "the only answer".

## What a correction may change (V0.1, Founder Slice 3.5 §3)

- `artifact_type="direction_placement"` -> EFFECTIVE placement ONLY.
  Never touches Potential Fit/Goal Alignment/Transition Feasibility/
  Evidence Confidence -- those are read straight off the immutable
  `Direction` row into `DirectionOutputs`, which this module never
  overlays under any artifact_type.
- `artifact_type="narrative"` -> EFFECTIVE narrative field(s) only.
- `artifact_type in ("profile_flag", "knowledge_flag")` -> surfaces as a
  reviewer flag/note on the view; never rewrites Profile or Career KB
  data (there is nothing in this codebase for it to rewrite anyway --
  Stage 2/3A stay untouched).
- Any other `artifact_type` is UNSUPPORTED: it is never guessed at or
  silently interpreted. It is surfaced separately as an "unapplied"
  correction with an explicit reason, and never changes any EFFECTIVE
  field.

## Publishable result

`get_publishable_direction_result()` is the ONE function a later
client-report layer should call. It composes
`review.get_approved_direction_run()` (already enforces READY + zero
unresolved BLOCKER + an APPROVED review bound to the exact run) with
`build_reviewed_direction_view()` -- it never falls back to an unreviewed
or non-approved run, and raises the same `NoApprovedDirectionRunError`
`review.py` already defines when there is nothing publishable.

## Privacy

Nothing in this module ever reads `Answer`/`CVUpload`/`InterviewMessage`
(raw CV/assessment-transcript content) or an AI Gateway prompt -- not
imported, not queried, structurally unreachable from here. Two distinct
levels of profile detail are exposed, deliberately:

- `ProfileSummaryView` (the Client Card's lightweight overview block) is
  limited to structural counts/bands only -- canonical dimensions
  covered, SUPPORTED claim count, a confidence BAND -- never a raw
  claim's `label`/`normalized_value` text.
- `ProfileClaimView` (Founder Stage 4A §4/§5, consultant-only) DOES
  include `label`/`normalized_value` -- Stage 2's already-normalized
  claim text, not raw CV/answer text (that stays out of both views).
  This is an explicit, Founder-authorized widening for the consultant
  profile-detail screen; `Evidence` stays ID+source_type only even here,
  never a fabricated summary (Founder §5: "Do NOT generate fake evidence
  summaries from missing data").
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_direction import (
    ConsultantCorrection,
    CriticSeverity,
    Direction,
    DirectionCriticFinding,
    DirectionPlacement,
    DirectionReview,
    DirectionRun,
    DirectionRunStatus,
    QualitativeBand,
    RankingPolicy,
    ReviewStatus,
    ScoringConfig,
)
from app.db.models_identity import IdentityUser
from app.db.models_profile import ClaimStatus, PotentialProfile, ProfileClaim, ProfileGenerationStatus
from app.services.direction import review as review_module
from app.services.direction.dimension_mapping import MappingStatus, map_claims
from app.services.direction.dimensions import CanonicalDimension
from app.services.direction.scoring.aggregate import band_for
from app.services.direction.versions import DIRECTION_ENGINE_VERSION
from app.services.exceptions import NoCurrentDirectionRunError
from app.services.knowledge.retrieval import get_career

__all__ = [
    "KNOWN_ARTIFACT_TYPES",
    "DirectionOutputs",
    "AppliedCorrectionInfo",
    "CriticFindingSummary",
    "ReviewedDirectionView",
    "CriticSummary",
    "ReviewedDirectionRunView",
    "build_reviewed_direction_view",
    "get_publishable_direction_result",
    "ProfileSummaryView",
    "ProfileClaimEvidenceRef",
    "ProfileClaimView",
    "ProvenanceView",
    "ClientInfo",
    "ClientCardView",
    "build_client_card",
    "CLIENT_LIST_FILTERS",
    "DirectionClientSummary",
    "list_client_summaries",
]

# The only artifact_type values this projection knows how to apply.
# Anything else is surfaced as "unapplied/unsupported", never guessed at
# (Founder Slice 3.5 §3.D).
KNOWN_ARTIFACT_TYPES = frozenset({"direction_placement", "narrative", "profile_flag", "knowledge_flag"})


@dataclass(frozen=True)
class DirectionOutputs:
    """ALWAYS the immutable system values -- no correction artifact_type
    is ever allowed to change any field here (Founder Slice 3.5 §3.A/B)."""

    potential_fit_raw: float | None
    potential_fit_band: QualitativeBand | None
    goal_alignment_raw: float | None
    goal_alignment_band: QualitativeBand | None
    transition_feasibility_raw: float | None
    transition_feasibility_band: QualitativeBand | None
    evidence_confidence_raw: float | None
    evidence_confidence_band: QualitativeBand | None


@dataclass(frozen=True)
class AppliedCorrectionInfo:
    correction_id: uuid.UUID
    artifact_type: str
    reason_code: str
    reviewer_id: int
    created_at: datetime
    comment: str | None
    applied: bool  # False for an unsupported artifact_type or a flag (recorded, not "applied" to a field)


@dataclass(frozen=True)
class CriticFindingSummary:
    finding_id: uuid.UUID
    severity: CriticSeverity
    code: str
    message: str


@dataclass(frozen=True)
class ReviewedDirectionView:
    direction_id: uuid.UUID
    career_id: uuid.UUID
    career_code: str
    career_title: str | None
    domain: str

    system_placement: DirectionPlacement
    effective_placement: DirectionPlacement

    outputs: DirectionOutputs

    system_narrative: dict | None
    effective_narrative: dict | None

    explanation_bundle: dict | None
    skills_to_verify: list
    trade_off_notes: str | None

    critic_findings: list[CriticFindingSummary] = field(default_factory=list)
    reviewer_flags: list[AppliedCorrectionInfo] = field(default_factory=list)
    applied_corrections: list[AppliedCorrectionInfo] = field(default_factory=list)
    unapplied_corrections: list[AppliedCorrectionInfo] = field(default_factory=list)


@dataclass(frozen=True)
class CriticSummary:
    engine_version: str | None
    blocker_count: int
    warning_count: int
    info_count: int


@dataclass(frozen=True)
class ReviewedDirectionRunView:
    run_id: uuid.UUID
    run_version: int
    user_id: uuid.UUID
    review_status: ReviewStatus | None
    reviewer_id: int | None
    decided_at: datetime | None
    critic_summary: CriticSummary
    directions: list[ReviewedDirectionView]
    run_level_flags: list[AppliedCorrectionInfo] = field(default_factory=list)
    unapplied_corrections: list[AppliedCorrectionInfo] = field(default_factory=list)


async def build_reviewed_direction_view(session: AsyncSession, *, run_id: uuid.UUID) -> ReviewedDirectionRunView:
    run = await session.get(DirectionRun, run_id)
    if run is None:
        raise NoCurrentDirectionRunError(f"DirectionRun {run_id} does not exist")

    review_row = (
        await session.execute(select(DirectionReview).where(DirectionReview.run_id == run_id))
    ).scalar_one_or_none()

    directions = (await session.execute(select(Direction).where(Direction.run_id == run_id))).scalars().all()

    # "Current critic evaluation" (Founder §7) = the evaluation matching
    # the currently-deployed engine version, not superseded historical ones.
    findings = (
        await session.execute(
            select(DirectionCriticFinding).where(
                DirectionCriticFinding.run_id == run_id, DirectionCriticFinding.engine_version == DIRECTION_ENGINE_VERSION
            )
        )
    ).scalars().all()
    findings_by_direction: dict[uuid.UUID | None, list[DirectionCriticFinding]] = {}
    for f in findings:
        findings_by_direction.setdefault(f.direction_id, []).append(f)

    corrections: list[ConsultantCorrection] = []
    if review_row is not None:
        corrections = (
            await session.execute(
                select(ConsultantCorrection)
                .where(ConsultantCorrection.review_id == review_row.id)
                .order_by(ConsultantCorrection.created_at.asc(), ConsultantCorrection.id.asc())
            )
        ).scalars().all()

    # -- apply overlays, in deterministic chronological order --
    effective_placement: dict[uuid.UUID, str] = {}
    effective_narrative: dict[uuid.UUID, dict] = {}
    applied_by_direction: dict[uuid.UUID | None, list[AppliedCorrectionInfo]] = {}
    flags_by_direction: dict[uuid.UUID | None, list[AppliedCorrectionInfo]] = {}
    unapplied_by_direction: dict[uuid.UUID | None, list[AppliedCorrectionInfo]] = {}

    for c in corrections:
        info = AppliedCorrectionInfo(
            correction_id=c.id, artifact_type=c.artifact_type, reason_code=c.reason_code.value,
            reviewer_id=c.reviewer_id, created_at=c.created_at, comment=c.comment, applied=True,
        )
        if c.artifact_type == "direction_placement" and c.direction_id is not None:
            new_placement = (c.corrected_value or {}).get("placement")
            if new_placement:
                effective_placement[c.direction_id] = new_placement  # latest wins -- chronological order
            applied_by_direction.setdefault(c.direction_id, []).append(info)
        elif c.artifact_type == "narrative" and c.direction_id is not None:
            merged = effective_narrative.setdefault(c.direction_id, {})
            merged.update(c.corrected_value or {})
            applied_by_direction.setdefault(c.direction_id, []).append(info)
        elif c.artifact_type in ("profile_flag", "knowledge_flag"):
            flag_info = AppliedCorrectionInfo(
                correction_id=c.id, artifact_type=c.artifact_type, reason_code=c.reason_code.value,
                reviewer_id=c.reviewer_id, created_at=c.created_at, comment=c.comment, applied=False,
            )
            flags_by_direction.setdefault(c.direction_id, []).append(flag_info)
        else:
            unapplied_by_direction.setdefault(c.direction_id, []).append(
                AppliedCorrectionInfo(
                    correction_id=c.id, artifact_type=c.artifact_type, reason_code=c.reason_code.value,
                    reviewer_id=c.reviewer_id, created_at=c.created_at, comment=c.comment, applied=False,
                )
            )

    direction_views: list[ReviewedDirectionView] = []
    for d in directions:
        career = None
        try:
            career = await get_career(session, d.career_id)
        except Exception:
            career = None

        base_narrative = d.narrative_structured
        narrative_overlay = effective_narrative.get(d.id)
        effective_narr = dict(base_narrative or {})
        if narrative_overlay:
            effective_narr.update(narrative_overlay)

        placement_override = effective_placement.get(d.id)
        eff_placement = DirectionPlacement(placement_override) if placement_override else d.placement

        direction_views.append(
            ReviewedDirectionView(
                direction_id=d.id, career_id=d.career_id, career_code=d.career_code,
                career_title=career.title_uk if career is not None else None, domain=d.domain,
                system_placement=d.placement, effective_placement=eff_placement,
                outputs=DirectionOutputs(
                    potential_fit_raw=d.potential_fit_raw_experimental, potential_fit_band=d.potential_fit_band,
                    goal_alignment_raw=d.goal_alignment_raw_experimental, goal_alignment_band=d.goal_alignment_band,
                    transition_feasibility_raw=d.transition_feasibility_raw_experimental,
                    transition_feasibility_band=d.transition_feasibility_band,
                    evidence_confidence_raw=d.evidence_confidence_raw_experimental,
                    evidence_confidence_band=d.evidence_confidence_band,
                ),
                system_narrative=base_narrative, effective_narrative=effective_narr or None,
                explanation_bundle=d.explanation_bundle, skills_to_verify=list(d.skills_to_verify or []),
                trade_off_notes=d.trade_off_notes,
                critic_findings=[
                    CriticFindingSummary(f.id, f.severity, f.code, f.message)
                    for f in findings_by_direction.get(d.id, [])
                ],
                reviewer_flags=flags_by_direction.get(d.id, []),
                applied_corrections=applied_by_direction.get(d.id, []),
                unapplied_corrections=unapplied_by_direction.get(d.id, []),
            )
        )

    run_level_findings = findings_by_direction.get(None, [])
    blocker_count = sum(1 for f in findings if f.severity is CriticSeverity.BLOCKER)
    warning_count = sum(1 for f in findings if f.severity is CriticSeverity.WARNING)
    info_count = sum(1 for f in findings if f.severity is CriticSeverity.INFO)

    return ReviewedDirectionRunView(
        run_id=run.id, run_version=run.version, user_id=run.user_id,
        review_status=review_row.status if review_row is not None else None,
        reviewer_id=review_row.reviewer_id if review_row is not None else None,
        decided_at=review_row.decided_at if review_row is not None else None,
        critic_summary=CriticSummary(
            engine_version=DIRECTION_ENGINE_VERSION if findings or run_level_findings else None,
            blocker_count=blocker_count, warning_count=warning_count, info_count=info_count,
        ),
        directions=direction_views,
        run_level_flags=flags_by_direction.get(None, []),
        unapplied_corrections=[u for group in unapplied_by_direction.values() for u in group],
    )


async def get_publishable_direction_result(session: AsyncSession, *, user_id: uuid.UUID) -> ReviewedDirectionRunView:
    """The ONE function a later client-report layer should consume.
    Raises `NoApprovedDirectionRunError` (never falls back silently to an
    unreviewed/unapproved run) when there is nothing publishable yet."""
    run = await review_module.get_approved_direction_run(session, user_id=user_id)
    return await build_reviewed_direction_view(session, run_id=run.id)


# --------------------------------------------------------------------------
# Client Card read model (Stage 4 Dashboard) -- consultant-facing, works for
# a run in ANY review state, unlike get_publishable_direction_result's
# strict approved-only gate.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ClientInfo:
    user_id: uuid.UUID
    profile_id: uuid.UUID
    profile_version: int
    direction_run_id: uuid.UUID
    direction_run_version: int
    review_status: ReviewStatus | None


@dataclass(frozen=True)
class ProfileSummaryView:
    """Structural counts/bands only -- never a raw claim's
    label/normalized_value text (privacy, Founder Slice 3.5 §9)."""

    supported_claim_count: int
    canonical_dimensions_covered: list[str]
    canonical_dimensions_missing: list[str]
    contradiction_count: int
    confidence_band: QualitativeBand | None


@dataclass(frozen=True)
class ProvenanceView:
    methodology_version: str
    knowledge_base_version_id: uuid.UUID
    scoring_config_version: int
    ranking_policy_version: int
    direction_engine_version: str


@dataclass(frozen=True)
class ProfileClaimEvidenceRef:
    """ID + source_type ONLY -- never a raw evidence summary generated
    from missing data (Founder Stage 4A §5: "Do NOT generate fake evidence
    summaries")."""

    evidence_id: uuid.UUID
    source_type: str


@dataclass(frozen=True)
class ProfileClaimView:
    """Per-claim consultant-facing detail (Founder Stage 4A §4/§5) --
    deliberately a DIFFERENT, more detailed view than `ProfileSummaryView`
    above: `label`/`normalized_value` are Stage 2's already-normalized
    claim text (never raw CV/answer text -- that stays out of this read
    model entirely), shown here because this screen is explicitly
    consultant-only and Founder's brief explicitly asks for it, unlike
    the lighter Client Card summary block."""

    claim_id: uuid.UUID
    legacy_dimension: str
    canonical_dimension: str | None
    canonical_subdimension: str | None
    mapping_status: str
    label: str
    normalized_value: str
    status: str
    confidence: float
    evidence: list[ProfileClaimEvidenceRef] = field(default_factory=list)
    is_contradicted: bool = False


@dataclass(frozen=True)
class ClientCardView:
    client: ClientInfo
    profile_summary: ProfileSummaryView
    profile_claims: list[ProfileClaimView]
    provenance: ProvenanceView
    critic_summary: CriticSummary
    directions: list[ReviewedDirectionView]


async def _build_profile_summary(session: AsyncSession, *, profile_id: uuid.UUID, thresholds: dict) -> ProfileSummaryView:
    claims = (await session.execute(select(ProfileClaim).where(ProfileClaim.profile_id == profile_id))).scalars().all()
    mapped_claims = map_claims(list(claims))
    supported = [mc for mc in mapped_claims if mc.claim_status == ClaimStatus.SUPPORTED.value]
    contradicted = [mc for mc in mapped_claims if mc.claim_status == ClaimStatus.CONTRADICTED.value]
    covered = {mc.canonical_dimension for mc in supported if mc.status is MappingStatus.MAPPED and mc.canonical_dimension is not None}
    missing = [d.value for d in CanonicalDimension if d not in covered]

    avg_confidence = (sum(mc.claim_confidence for mc in supported) / len(supported)) if supported else None
    band = band_for(avg_confidence, thresholds) if avg_confidence is not None else None

    return ProfileSummaryView(
        supported_claim_count=len(supported), canonical_dimensions_covered=sorted(d.value for d in covered),
        canonical_dimensions_missing=missing, contradiction_count=len(contradicted), confidence_band=band,
    )


async def _build_profile_claims(session: AsyncSession, *, profile_id: uuid.UUID) -> list[ProfileClaimView]:
    from app.db.models_profile import Evidence, ProfileClaimEvidence

    claims = (await session.execute(select(ProfileClaim).where(ProfileClaim.profile_id == profile_id))).scalars().all()
    mapped_by_id = {mc.source_claim_id: mc for mc in map_claims(list(claims))}

    evidence_rows = (
        await session.execute(
            select(ProfileClaimEvidence.claim_id, Evidence.id, Evidence.source_type)
            .join(Evidence, Evidence.id == ProfileClaimEvidence.evidence_id)
            .where(ProfileClaimEvidence.claim_id.in_([c.id for c in claims]))
        )
    ).all()
    evidence_by_claim: dict[uuid.UUID, list[ProfileClaimEvidenceRef]] = {}
    for claim_id, evidence_id, source_type in evidence_rows:
        evidence_by_claim.setdefault(claim_id, []).append(
            ProfileClaimEvidenceRef(evidence_id=evidence_id, source_type=source_type.value)
        )

    views: list[ProfileClaimView] = []
    for claim in claims:
        mc = mapped_by_id[claim.id]
        views.append(
            ProfileClaimView(
                claim_id=claim.id, legacy_dimension=mc.legacy_dimension,
                canonical_dimension=mc.canonical_dimension.value if mc.canonical_dimension else None,
                canonical_subdimension=mc.canonical_subdimension, mapping_status=mc.status.value,
                label=claim.label, normalized_value=claim.normalized_value, status=claim.status.value,
                confidence=claim.confidence, evidence=evidence_by_claim.get(claim.id, []),
                is_contradicted=claim.status == ClaimStatus.CONTRADICTED,
            )
        )
    return views


async def build_client_card(
    session: AsyncSession, *, user_id: uuid.UUID, run_id: uuid.UUID | None = None
) -> ClientCardView:
    """`run_id=None` resolves to the user's current `DirectionRun`
    regardless of review status -- a consultant dashboard needs to see a
    PENDING_REVIEW run too, unlike `get_publishable_direction_result`."""
    if run_id is None:
        run = (
            await session.execute(
                select(DirectionRun).where(DirectionRun.user_id == user_id, DirectionRun.is_current.is_(True))
            )
        ).scalar_one_or_none()
        if run is None:
            raise NoCurrentDirectionRunError(f"user {user_id} has no current DirectionRun")
        run_id = run.id
    else:
        run = await session.get(DirectionRun, run_id)
        if run is None:
            raise NoCurrentDirectionRunError(f"DirectionRun {run_id} does not exist")

    reviewed = await build_reviewed_direction_view(session, run_id=run_id)

    scoring_config = await session.get(ScoringConfig, run.scoring_config_id)
    ranking_policy = await session.get(RankingPolicy, run.ranking_policy_id)
    profile = await session.get(PotentialProfile, run.profile_id)

    profile_summary = await _build_profile_summary(
        session, profile_id=run.profile_id, thresholds=(scoring_config.thresholds if scoring_config else {})
    )
    profile_claims = await _build_profile_claims(session, profile_id=run.profile_id)

    return ClientCardView(
        client=ClientInfo(
            user_id=run.user_id, profile_id=run.profile_id, profile_version=profile.version if profile else 0,
            direction_run_id=run.id, direction_run_version=run.version, review_status=reviewed.review_status,
        ),
        profile_summary=profile_summary,
        profile_claims=profile_claims,
        provenance=ProvenanceView(
            methodology_version=run.methodology_version, knowledge_base_version_id=run.knowledge_base_version_id,
            scoring_config_version=scoring_config.version if scoring_config else 0,
            ranking_policy_version=ranking_policy.version if ranking_policy else 0,
            direction_engine_version=run.direction_engine_version,
        ),
        critic_summary=reviewed.critic_summary,
        directions=reviewed.directions,
    )


# --------------------------------------------------------------------------
# Client List (Stage 4A Dashboard) -- one row per assessed user (has a
# PotentialProfile at all), left-joined with their current DirectionRun/
# DirectionReview/current-engine-version Critic finding counts. Deliberately
# simple per-user queries (not batch-optimized) -- fine at pilot scale;
# flagged as a known limitation for real scale later.
# --------------------------------------------------------------------------

CLIENT_LIST_FILTERS = frozenset(
    {"needs_review", "blockers", "changes_requested", "approved", "insufficient_information", "no_directions_yet"}
)


@dataclass(frozen=True)
class DirectionClientSummary:
    user_id: uuid.UUID
    profile_status: str | None
    profile_version: int | None
    direction_run_id: uuid.UUID | None
    direction_run_status: str | None
    direction_run_version: int | None
    review_status: str | None
    blocker_count: int
    warning_count: int
    last_updated: datetime


def _matches_filter(summary: DirectionClientSummary, filter_name: str) -> bool:
    if filter_name == "needs_review":
        return summary.direction_run_status == DirectionRunStatus.READY.value and summary.review_status in (None, ReviewStatus.PENDING_REVIEW.value)
    if filter_name == "blockers":
        return summary.blocker_count > 0
    if filter_name == "changes_requested":
        return summary.review_status == ReviewStatus.CHANGES_REQUESTED.value
    if filter_name == "approved":
        return summary.review_status == ReviewStatus.APPROVED.value
    if filter_name == "insufficient_information":
        return summary.direction_run_status == DirectionRunStatus.INSUFFICIENT_INFORMATION.value
    if filter_name == "no_directions_yet":
        return summary.direction_run_id is None
    return True


async def list_client_summaries(
    session: AsyncSession, *, filter_name: str | None = None
) -> list[DirectionClientSummary]:
    """`filter_name` must be one of `CLIENT_LIST_FILTERS` or `None` (no
    filter) -- an unrecognized value is treated as "no filter" rather than
    raising, since this only ever drives a read-only list view."""
    profiles = (
        await session.execute(
            select(PotentialProfile)
            .join(IdentityUser, IdentityUser.id == PotentialProfile.user_id)
            .where(PotentialProfile.is_current.is_(True), IdentityUser.deleted_at.is_(None))
        )
    ).scalars().all()

    summaries: list[DirectionClientSummary] = []
    for profile in profiles:
        run = (
            await session.execute(
                select(DirectionRun).where(DirectionRun.user_id == profile.user_id, DirectionRun.is_current.is_(True))
            )
        ).scalar_one_or_none()

        review_status = None
        blocker_count = 0
        warning_count = 0
        last_updated = profile.created_at

        if run is not None:
            last_updated = max(last_updated, run.created_at)
            review_row = (
                await session.execute(select(DirectionReview).where(DirectionReview.run_id == run.id))
            ).scalar_one_or_none()
            if review_row is not None:
                review_status = review_row.status.value
                last_updated = max(last_updated, review_row.created_at)

            findings = (
                await session.execute(
                    select(DirectionCriticFinding).where(
                        DirectionCriticFinding.run_id == run.id,
                        DirectionCriticFinding.engine_version == DIRECTION_ENGINE_VERSION,
                    )
                )
            ).scalars().all()
            blocker_count = sum(1 for f in findings if f.severity is CriticSeverity.BLOCKER)
            warning_count = sum(1 for f in findings if f.severity is CriticSeverity.WARNING)

        summaries.append(
            DirectionClientSummary(
                user_id=profile.user_id, profile_status=profile.status.value, profile_version=profile.version,
                direction_run_id=run.id if run else None, direction_run_status=run.status.value if run else None,
                direction_run_version=run.version if run else None, review_status=review_status,
                blocker_count=blocker_count, warning_count=warning_count, last_updated=last_updated,
            )
        )

    if filter_name in CLIENT_LIST_FILTERS:
        summaries = [s for s in summaries if _matches_filter(s, filter_name)]

    summaries.sort(key=lambda s: s.last_updated, reverse=True)
    return summaries
