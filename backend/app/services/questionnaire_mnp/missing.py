""""Do not ask what is already known" (MNP_MINIMAL_QUESTIONNAIRE_V1
"Principle"). BLOCK D's UI calls this after a CV upload (or at the start
of a no-CV flow) to decide which questionnaire fields to actually show."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_career_card import (
    MnpCareerGoal,
    MnpEducation,
    MnpExperience,
    MnpIncomeTarget,
    MnpLanguage,
    MnpLearningCapacity,
    MnpPreferenceProfile,
)

CAREER_CAPITAL_FIELDS = ("current_role", "education", "languages")
CAREER_INTENT_FIELDS = ("goal", "income_target", "preference_profile", "learning_capacity")


@dataclass(frozen=True)
class MissingFields:
    career_capital: list[str] = field(default_factory=list)
    career_intent: list[str] = field(default_factory=list)


async def get_missing_fields(session: AsyncSession, career_card_id: uuid.UUID) -> MissingFields:
    capital_missing: list[str] = []
    intent_missing: list[str] = []

    has_current_role = (
        await session.execute(
            select(MnpExperience).where(MnpExperience.career_card_id == career_card_id, MnpExperience.is_current.is_(True))
        )
    ).scalars().first() is not None
    if not has_current_role:
        capital_missing.append("current_role")

    has_education = (
        await session.execute(select(MnpEducation).where(MnpEducation.career_card_id == career_card_id))
    ).scalars().first() is not None
    if not has_education:
        capital_missing.append("education")

    has_languages = (
        await session.execute(select(MnpLanguage).where(MnpLanguage.career_card_id == career_card_id))
    ).scalars().first() is not None
    if not has_languages:
        capital_missing.append("languages")

    has_goal = (
        await session.execute(select(MnpCareerGoal).where(MnpCareerGoal.career_card_id == career_card_id))
    ).scalars().first() is not None
    if not has_goal:
        intent_missing.append("goal")

    # MnpIncomeTarget/MnpPreferenceProfile/MnpLearningCapacity are all
    # unique=True on career_card_id (at most one row ever), so
    # scalar_one_or_none() is safe here -- but .scalars().first() is used
    # uniformly with the multi-row tables above, which genuinely CAN have
    # more than one row per card (several jobs/degrees/languages/goals is
    # normal), where scalar_one_or_none() raised MultipleResultsFound.
    has_income = (
        await session.execute(select(MnpIncomeTarget).where(MnpIncomeTarget.career_card_id == career_card_id))
    ).scalars().first() is not None
    if not has_income:
        intent_missing.append("income_target")

    has_preferences = (
        await session.execute(select(MnpPreferenceProfile).where(MnpPreferenceProfile.career_card_id == career_card_id))
    ).scalars().first() is not None
    if not has_preferences:
        intent_missing.append("preference_profile")

    has_learning_capacity = (
        await session.execute(select(MnpLearningCapacity).where(MnpLearningCapacity.career_card_id == career_card_id))
    ).scalars().first() is not None
    if not has_learning_capacity:
        intent_missing.append("learning_capacity")

    return MissingFields(career_capital=capital_missing, career_intent=intent_missing)
