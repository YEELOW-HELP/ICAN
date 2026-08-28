"""Deterministic ranking over a set of `MatchingResult` rows (Matching V1
M4), per `MNP_GOLDEN_TEST_V0.1.md` §24-25's already-approved ordering,
extended with the "when available" semantics Founder Review §12 requires
for the two optional secondary families.

No composite Match score is ever computed (Founder Review §12/§21) --
ranking is a pure ORDERING over the existing per-family statuses/bands/
raw scores, never a blended number.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_basic_profile import ProfileStructuredContext
from app.db.models_knowledge import Career
from app.db.models_matching import FitStatus, MatchFamilyResult, MatchFeasibilityResult, MatchingResult

_BAND_RANK = {"high": 2, "medium": 1, "low": 0}


@dataclass(frozen=True)
class RankedEntry:
    matching_result_id: uuid.UUID
    career_id: uuid.UUID
    career_code: str
    eligible: bool
    interest_status: str
    interest_band: str | None
    interest_raw_score: float | None
    work_style_status: str
    work_style_band: str | None
    work_style_raw_score: float | None
    values_status: str
    values_band: str | None
    values_raw_score: float | None
    feasibility_status: str
    feasibility_raw_score: float | None
    goals_domain_match: bool
    participating_families: tuple[str, ...]  # families with status == SCORED


@dataclass(frozen=True)
class RankingResult:
    """Three explicit groups, never interleaved into one ambiguous list
    (Founder Review §12: "do not punish... do not reward" missing data).
    `ranked` = eligible AND Interest Fit is SCORED (the only group with a
    genuine primary sort criterion). `unranked` = eligible but Interest
    Fit is not SCORED (INSUFFICIENT_DATA/LOW_DIFFERENTIATION) -- sorted
    only by `Career.code`, since there is no comparable data to rank by
    at all. `blocked` = Feasibility BLOCKED -- excluded from eligible
    ranking but always present in the dataset, never deleted."""

    ranked: list[RankedEntry]
    unranked: list[RankedEntry]
    blocked: list[RankedEntry]


def _secondary_tier(band: str | None, raw_score: float | None) -> tuple[int, float]:
    """A family with status != SCORED contributes the neutral pair
    `(-1, -1.0)` at its own tier -- this ties with every OTHER not-scored
    career at that same tier (since -1 always equals -1), and only ever
    differentiates between two careers that are BOTH scored on this
    family. It can never place a not-scored career above OR below a
    scored one purely because of missing data at a LATER, secondary tier
    -- that comparison is already decided by the earlier tiers by the
    time this one is reached for two otherwise-tied careers, and among
    genuinely tied-so-far careers preferring the one with more comparable
    data is a minor, disclosed tie-break preference, not a penalty on the
    primary criterion (Founder Review §12)."""

    if band is None:
        return (-1, -1.0)
    return (_BAND_RANK[band], raw_score if raw_score is not None else 0.0)


def _sort_key_for_ranked(entry: RankedEntry) -> tuple:
    """`MNP_GOLDEN_TEST_V0.1.md` §24: band-then-raw-score for Interest
    Fit (the shared primary criterion within this group by construction),
    then Work Style Fit band+score WHEN available, then Values Fit
    band+score WHEN available, then Feasibility raw score, then the
    Golden Test §25 Goals tie-break, then the final stable `Career.code`
    tie-break. All numeric components negated for a descending sort via
    Python's ascending tuple comparison."""

    ws_band, ws_score = _secondary_tier(entry.work_style_band, entry.work_style_raw_score)
    v_band, v_score = _secondary_tier(entry.values_band, entry.values_raw_score)

    return (
        -_BAND_RANK[entry.interest_band],
        -(entry.interest_raw_score or 0.0),
        -ws_band,
        -ws_score,
        -v_band,
        -v_score,
        -(entry.feasibility_raw_score if entry.feasibility_raw_score is not None else -1.0),
        0 if entry.goals_domain_match else 1,
        entry.career_code,
    )


async def rank_matching_results(
    session: AsyncSession, matching_result_ids: list[uuid.UUID], *, profile_id: uuid.UUID | None = None
) -> RankingResult:
    """`profile_id`, if given, is used only to look up the Goals tie-break
    (desired domains) -- never to alter any Fit score."""

    desired_domains: set[str] = set()
    if profile_id is not None:
        goals_result = await session.execute(
            select(ProfileStructuredContext).where(
                ProfileStructuredContext.profile_id == profile_id,
                ProfileStructuredContext.scale_family == "goals",
                ProfileStructuredContext.scale_key == "desired_domains",
            )
        )
        row = goals_result.scalar_one_or_none()
        if row is not None and row.selected_option_keys:
            desired_domains = set(row.selected_option_keys)

    entries: list[RankedEntry] = []
    for result_id in matching_result_ids:
        matching_result = await session.get(MatchingResult, result_id)
        family_rows = (
            (await session.execute(select(MatchFamilyResult).where(MatchFamilyResult.matching_result_id == result_id)))
            .scalars()
            .all()
        )
        by_family = {row.scale_family.value: row for row in family_rows}
        feasibility_row = (
            await session.execute(select(MatchFeasibilityResult).where(MatchFeasibilityResult.matching_result_id == result_id))
        ).scalar_one()
        career = await session.get(Career, matching_result.career_id)

        interest = by_family["riasec"]
        work_style = by_family["work_style"]
        values = by_family["work_values"]

        participating = tuple(
            family for family, row in (("interest", interest), ("work_style", work_style), ("values", values))
            if row.status == FitStatus.SCORED
        )

        entries.append(
            RankedEntry(
                matching_result_id=result_id,
                career_id=matching_result.career_id,
                career_code=career.code,
                eligible=matching_result.eligible,
                interest_status=interest.status.value,
                interest_band=interest.band.value if interest.band else None,
                interest_raw_score=interest.raw_score,
                work_style_status=work_style.status.value,
                work_style_band=work_style.band.value if work_style.band else None,
                work_style_raw_score=work_style.raw_score,
                values_status=values.status.value,
                values_band=values.band.value if values.band else None,
                values_raw_score=values.raw_score,
                feasibility_status=feasibility_row.status.value,
                feasibility_raw_score=feasibility_row.raw_score,
                goals_domain_match=(career.domain.value in desired_domains) if desired_domains else False,
                participating_families=participating,
            )
        )

    blocked = sorted((e for e in entries if not e.eligible), key=lambda e: e.career_code)
    eligible = [e for e in entries if e.eligible]
    ranked = sorted((e for e in eligible if e.interest_status == "scored"), key=_sort_key_for_ranked)
    unranked = sorted((e for e in eligible if e.interest_status != "scored"), key=lambda e: e.career_code)

    return RankingResult(ranked=ranked, unranked=unranked, blocked=blocked)
