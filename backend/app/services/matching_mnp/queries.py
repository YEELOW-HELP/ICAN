"""Read contracts for BLOCK D screens: assembles a `MnpMatchRun`'s
results (Featured TOP-3 / TOP-10 / full catalog) and one career's full
Compatibility view (`MNP_CAREER_COMPATIBILITY_REPORT_V1`) into plain,
JSON-serializable structures. No formula lives here -- purely a read/
assembly layer over what `engine.py` already persisted."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_career_kb_mnp import MnpCareer
from app.db.models_matching_mnp import (
    MnpCareerMatch,
    MnpCareerRoute,
    MnpFeasibilityFinding,
    MnpMatchComponent,
    MnpPersonalGap,
    MnpRouteStep,
)


@dataclass(frozen=True)
class ComponentView:
    component_type: str
    status: str  # "scored" | "insufficient_data"
    band: str | None
    confidence: str


@dataclass(frozen=True)
class CareerMatchSummary:
    career_match_id: uuid.UUID
    career_id: uuid.UUID
    career_code: str
    career_name_uk: str
    rank: int
    display_band: str
    feasibility_status: str
    transition_distance: str
    is_featured: bool
    components: list[ComponentView]


@dataclass(frozen=True)
class MatchRunResultsView:
    featured: list[CareerMatchSummary] = field(default_factory=list)  # TOP-3, confidence-gated
    ranked_top10: list[CareerMatchSummary] = field(default_factory=list)
    blocked: list[CareerMatchSummary] = field(default_factory=list)


async def _to_summary(session: AsyncSession, match: MnpCareerMatch) -> CareerMatchSummary:
    career = await session.get(MnpCareer, match.career_id)
    components = (
        await session.execute(select(MnpMatchComponent).where(MnpMatchComponent.career_match_id == match.id))
    ).scalars().all()
    return CareerMatchSummary(
        career_match_id=match.id, career_id=match.career_id, career_code=career.code,
        career_name_uk=career.canonical_name_uk, rank=match.rank_overall, display_band=match.display_band.value,
        feasibility_status=match.feasibility_status.value, transition_distance=match.transition_distance.value,
        is_featured=match.is_featured,
        components=[
            ComponentView(component_type=c.component_type.value, status=("scored" if c.score_internal is not None else "insufficient_data"), band=(c.band.value if c.band else None), confidence=c.confidence.value)
            for c in components
        ],
    )


async def get_match_run_results(session: AsyncSession, match_run_id: uuid.UUID) -> MatchRunResultsView:
    matches = (
        await session.execute(select(MnpCareerMatch).where(MnpCareerMatch.match_run_id == match_run_id))
    ).scalars().all()

    featured_matches = sorted((m for m in matches if m.is_featured), key=lambda m: m.rank_overall)
    ranked_matches = sorted((m for m in matches if m.rank_overall > 0), key=lambda m: m.rank_overall)[:10]
    blocked_matches = [m for m in matches if m.feasibility_status.value == "blocked"]

    return MatchRunResultsView(
        featured=[await _to_summary(session, m) for m in featured_matches],
        ranked_top10=[await _to_summary(session, m) for m in ranked_matches],
        blocked=[await _to_summary(session, m) for m in blocked_matches],
    )


@dataclass(frozen=True)
class GapView:
    reference_label: str
    classification: str
    action: str


@dataclass(frozen=True)
class FeasibilityFindingView:
    finding_type: str
    severity: str
    status: str
    requirement_description: str | None


@dataclass(frozen=True)
class RouteStepView:
    order: int
    step_type: str
    title: str
    description: str | None


@dataclass(frozen=True)
class CareerCompatibilityView:
    """MNP_CAREER_COMPATIBILITY_REPORT_V1's 12 sections, everything the
    read side needs -- BLOCK D's UI/API layer decides HOW to render it."""

    career_code: str
    career_name_uk: str
    description_short_uk: str
    feasibility_status: str
    transition_distance: str
    components: list[ComponentView]
    matched_skill_labels: list[str]
    gaps: list[GapView]
    feasibility_findings: list[FeasibilityFindingView]
    market_data_limited: bool
    route_type: str | None
    route_steps: list[RouteStepView]


async def get_career_compatibility(session: AsyncSession, career_match_id: uuid.UUID) -> CareerCompatibilityView:
    match = await session.get(MnpCareerMatch, career_match_id)
    career = await session.get(MnpCareer, match.career_id)

    components = (
        await session.execute(select(MnpMatchComponent).where(MnpMatchComponent.career_match_id == match.id))
    ).scalars().all()
    component_views = [
        ComponentView(component_type=c.component_type.value, status=("scored" if c.score_internal is not None else "insufficient_data"), band=(c.band.value if c.band else None), confidence=c.confidence.value)
        for c in components
    ]
    skill_component = next((c for c in components if c.component_type.value == "skill_fit"), None)
    matched_skill_labels: list[str] = []
    if skill_component and skill_component.detail:
        # `detail["matched"]` holds skill_id strings (pure.py's own
        # bookkeeping keys, not user-facing text) -- resolve each back to
        # its canonical Ukrainian name before this ever reaches a screen.
        from app.db.models_career_card import MnpSkill

        matched_ids = [uuid.UUID(k) for k in skill_component.detail.get("matched", [])]
        if matched_ids:
            skill_rows = (await session.execute(select(MnpSkill).where(MnpSkill.id.in_(matched_ids)))).scalars().all()
            matched_skill_labels = [s.canonical_name_uk for s in skill_rows]

    gaps = (
        await session.execute(select(MnpPersonalGap).where(MnpPersonalGap.career_match_id == match.id))
    ).scalars().all()
    gap_views = [GapView(reference_label=g.reference_label, classification=g.classification, action=g.action) for g in sorted(gaps, key=lambda g: g.priority_internal, reverse=True)[:5]]

    findings = (
        await session.execute(select(MnpFeasibilityFinding).where(MnpFeasibilityFinding.career_match_id == match.id))
    ).scalars().all()
    from app.db.models_career_kb_mnp import MnpCareerRequirement

    finding_views = []
    for f in findings:
        description = None
        if f.requirement_id:
            requirement = await session.get(MnpCareerRequirement, f.requirement_id)
            description = requirement.description if requirement else None
        finding_views.append(FeasibilityFindingView(finding_type=f.finding_type, severity=f.severity, status=f.status.value, requirement_description=description))

    route = (
        await session.execute(select(MnpCareerRoute).where(MnpCareerRoute.career_match_id == match.id))
    ).scalar_one_or_none()
    route_steps: list[RouteStepView] = []
    route_type = None
    if route is not None:
        route_type = route.route_type.value
        steps = (
            await session.execute(select(MnpRouteStep).where(MnpRouteStep.route_id == route.id).order_by(MnpRouteStep.order))
        ).scalars().all()
        route_steps = [RouteStepView(order=s.order, step_type=s.step_type.value, title=s.title, description=s.description) for s in steps]

    return CareerCompatibilityView(
        career_code=career.code, career_name_uk=career.canonical_name_uk, description_short_uk=career.description_short_uk,
        feasibility_status=match.feasibility_status.value, transition_distance=match.transition_distance.value,
        components=component_views, matched_skill_labels=matched_skill_labels, gaps=gap_views,
        feasibility_findings=finding_views, market_data_limited=career.market_data_limited,
        route_type=route_type, route_steps=route_steps,
    )
