"""Applies Minimal Questionnaire answers to a `MnpCareerCard`
(MNP_MINIMAL_QUESTIONNAIRE_V1 "Output": normalized Career Card fields and
CLAIMED evidence). Career Capital answers get CLAIMED evidence (mirrors
the resume parser, MNP_EVIDENCE_AND_CONFIDENCE_MODEL_V1 §5: QUESTIONNAIRE
is a valid Person source type); Career Intent fields are direct
structured configuration -- not evidentiary claims to be weighed for
skill/experience matching -- so no Evidence row is created for them."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_career_card import (
    ConstraintSeverity,
    EvidenceSourceType,
    EvidenceType,
    MnpCareerCard,
    MnpCareerGoal,
    MnpConstraint,
    MnpCredential,
    MnpEducation,
    MnpExperience,
    MnpIncomeTarget,
    MnpLanguage,
    MnpLearningCapacity,
    MnpPersonWorkValue,
    MnpPreferenceProfile,
)
from app.services.career_card_mnp.card import record_evidence
from app.services.career_card_mnp.skill_application import apply_skill_phrase
from app.services.career_card_mnp.work_values_seed import ensure_work_values_seeded
from app.services.career_kb_mnp.alias_resolution import resolve_job_title_to_career
from app.services.questionnaire_mnp.schema import CareerCapitalAnswers, CareerIntentAnswers

_SOURCE = EvidenceSourceType.QUESTIONNAIRE


async def submit_career_capital(
    session: AsyncSession, career_card: MnpCareerCard, answers: CareerCapitalAnswers,
) -> None:
    if answers.current_role:
        duration_months = int(answers.years_of_experience * 12) if answers.years_of_experience else None
        matched_career = await resolve_job_title_to_career(session, answers.current_role)
        row = MnpExperience(
            career_card_id=career_card.id, raw_job_title=answers.current_role, is_current=True,
            normalized_career_id=matched_career.id if matched_career else None,
            duration_months=duration_months, responsibilities_raw=answers.responsibilities,
            source_type=_SOURCE, confidence=1.0,
        )
        session.add(row)
        await session.flush()
        await record_evidence(
            session, career_card, entity_type="experience", entity_id=row.id, evidence_type=EvidenceType.CLAIMED,
            source_type=_SOURCE, excerpt=answers.responsibilities, strength_internal=0.8,
        )

    for phrase in answers.skill_phrases:
        await apply_skill_phrase(session, career_card, phrase, source_type=_SOURCE, evidence_strength=0.7, confidence=0.7)

    if answers.education_level or answers.education_field or answers.graduation_year:
        row = MnpEducation(
            career_card_id=career_card.id, level=answers.education_level or "unknown",
            field=answers.education_field, institution=answers.education_institution,
            graduation_year=answers.graduation_year, source_type=_SOURCE, confidence=1.0,
        )
        session.add(row)
        await session.flush()
        await record_evidence(
            session, career_card, entity_type="education", entity_id=row.id, evidence_type=EvidenceType.CLAIMED,
            source_type=_SOURCE, strength_internal=0.8,
        )

    for name in answers.credential_names:
        row = MnpCredential(
            career_card_id=career_card.id, credential_type="certification", name=name,
            source_type=_SOURCE, confidence=1.0,
        )
        session.add(row)
        await session.flush()
        await record_evidence(
            session, career_card, entity_type="credential", entity_id=row.id, evidence_type=EvidenceType.CLAIMED,
            source_type=_SOURCE, excerpt=name, strength_internal=0.8,
        )

    for lang in answers.languages:
        row = MnpLanguage(
            career_card_id=career_card.id, language_code=lang.language_code, overall_level=lang.overall_level,
            source_type=_SOURCE, confidence=1.0,
        )
        session.add(row)
        await session.flush()
        await record_evidence(
            session, career_card, entity_type="language", entity_id=row.id, evidence_type=EvidenceType.CLAIMED,
            source_type=_SOURCE, strength_internal=0.8,
        )

    await session.flush()


async def submit_career_intent(
    session: AsyncSession, career_card: MnpCareerCard, answers: CareerIntentAnswers,
) -> None:
    if answers.goal_type is not None:
        session.add(
            MnpCareerGoal(
                career_card_id=career_card.id, goal_type=answers.goal_type, priority=1,
                time_horizon=answers.time_horizon,
            )
        )

    if answers.current_income is not None or answers.target_income is not None:
        existing = await session.execute(
            select(MnpIncomeTarget).where(MnpIncomeTarget.career_card_id == career_card.id)
        )
        income = existing.scalar_one_or_none()
        if income is None:
            income = MnpIncomeTarget(career_card_id=career_card.id)
            session.add(income)
        income.current_income = answers.current_income
        income.target_income = answers.target_income
        income.currency = answers.income_currency

    has_preference_data = any(
        v is not None
        for v in (
            answers.preferred_work_object, answers.work_format, answers.location_region,
            answers.autonomy_preference, answers.teamwork_preference, answers.customer_interaction_preference,
            answers.routine_vs_novelty_preference, answers.leadership_preference, answers.physical_activity_preference,
        )
    )
    if has_preference_data:
        existing = await session.execute(
            select(MnpPreferenceProfile).where(MnpPreferenceProfile.career_card_id == career_card.id)
        )
        pref = existing.scalar_one_or_none()
        if pref is None:
            pref = MnpPreferenceProfile(career_card_id=career_card.id)
            session.add(pref)
        pref.preferred_work_object = answers.preferred_work_object
        pref.work_format = answers.work_format
        pref.location_region = answers.location_region
        pref.autonomy_preference = answers.autonomy_preference
        pref.teamwork_preference = answers.teamwork_preference
        pref.customer_interaction_preference = answers.customer_interaction_preference
        pref.routine_vs_novelty_preference = answers.routine_vs_novelty_preference
        pref.leadership_preference = answers.leadership_preference
        pref.physical_activity_preference = answers.physical_activity_preference

    if answers.top_work_value_keys:
        work_values_by_key = await ensure_work_values_seeded(session)
        for rank, key in enumerate(answers.top_work_value_keys, start=1):
            work_value = work_values_by_key.get(key)
            if work_value is None:
                continue  # unknown key -- ignored, never silently invents a new canonical value
            existing = await session.execute(
                select(MnpPersonWorkValue).where(
                    MnpPersonWorkValue.career_card_id == career_card.id,
                    MnpPersonWorkValue.work_value_id == work_value.id,
                )
            )
            row = existing.scalar_one_or_none()
            if row is None:
                session.add(MnpPersonWorkValue(career_card_id=career_card.id, work_value_id=work_value.id, priority_rank=rank))
            else:
                row.priority_rank = rank

    has_learning_data = any(
        v is not None
        for v in (
            answers.learning_hours_per_week, answers.learning_budget,
            answers.willing_new_credential, answers.willing_lower_entry_role,
        )
    )
    if has_learning_data:
        existing = await session.execute(
            select(MnpLearningCapacity).where(MnpLearningCapacity.career_card_id == career_card.id)
        )
        capacity = existing.scalar_one_or_none()
        if capacity is None:
            capacity = MnpLearningCapacity(career_card_id=career_card.id)
            session.add(capacity)
        capacity.hours_per_week = answers.learning_hours_per_week
        capacity.budget = answers.learning_budget
        capacity.willing_new_credential = answers.willing_new_credential
        capacity.willing_lower_entry_role = answers.willing_lower_entry_role

    for code in answers.excluded_career_codes:
        session.add(
            MnpConstraint(
                career_card_id=career_card.id, constraint_type="excluded_career", value=code,
                severity=ConstraintSeverity.HARD, source_type=_SOURCE, active=True,
            )
        )

    for constraint in answers.constraints:
        session.add(
            MnpConstraint(
                career_card_id=career_card.id, constraint_type=constraint.constraint_type, value=constraint.value,
                severity=ConstraintSeverity(constraint.severity), source_type=_SOURCE, active=True,
            )
        )

    await session.flush()
