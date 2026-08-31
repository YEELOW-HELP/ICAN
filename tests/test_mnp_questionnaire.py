"""MNP V1 BLOCK B -- Minimal Questionnaire: Career Capital + Career
Intent submission, "do not ask what we already know"."""

from sqlalchemy import select

from app.db.models_career_card import (
    CareerGoalType,
    EntryMode,
    EvidenceSourceType,
    MnpCareerGoal,
    MnpConstraint,
    MnpEducation,
    MnpExperience,
    MnpIncomeTarget,
    MnpLanguage,
    MnpPersonSkill,
    MnpPersonWorkValue,
    MnpPreferenceProfile,
    SourceMode,
    WorkFormat,
    WorkObject,
)
from app.db.models_identity import IdentityUser
from app.services.career_card_mnp.card import get_or_create_career_card, start_assessment_session
from app.services.career_kb_mnp.seed_alpha import seed_alpha_career_kb
from app.services.questionnaire_mnp.missing import get_missing_fields
from app.services.questionnaire_mnp.schema import (
    CareerCapitalAnswers,
    CareerIntentAnswers,
    ConstraintAnswer,
    LanguageAnswer,
)
from app.services.questionnaire_mnp.submit import submit_career_capital, submit_career_intent


async def _make_card(session):
    user = IdentityUser(locale="uk")
    session.add(user)
    await session.flush()
    s = await start_assessment_session(session, user_id=user.id, entry_mode=EntryMode.MANUAL)
    card = await get_or_create_career_card(session, user_id=user.id, assessment_session_id=s.id, source_mode=SourceMode.MANUAL)
    await session.commit()
    return card


async def test_career_capital_creates_current_experience_and_evidence(session):
    await seed_alpha_career_kb(session)
    card = await _make_card(session)

    answers = CareerCapitalAnswers(
        current_role="Менеджер з продажу", years_of_experience=3, responsibilities="Ведення переговорів",
        skill_phrases=["Переговори", "CRM"], education_level="bachelor", graduation_year=2019,
        credential_names=["Сертифікат PMI"], languages=[LanguageAnswer("en", "intermediate")],
    )
    await submit_career_capital(session, card, answers)
    await session.commit()

    experiences = (await session.execute(select(MnpExperience).where(MnpExperience.career_card_id == card.id))).scalars().all()
    assert len(experiences) == 1
    assert experiences[0].is_current is True
    assert experiences[0].duration_months == 36
    assert experiences[0].source_type == EvidenceSourceType.QUESTIONNAIRE

    educations = (await session.execute(select(MnpEducation).where(MnpEducation.career_card_id == card.id))).scalars().all()
    assert educations[0].level == "bachelor"

    person_skills = (await session.execute(select(MnpPersonSkill).where(MnpPersonSkill.career_card_id == card.id))).scalars().all()
    assert len(person_skills) == 2

    languages = (await session.execute(select(MnpLanguage).where(MnpLanguage.career_card_id == card.id))).scalars().all()
    assert languages[0].language_code == "en"


async def test_career_intent_creates_goal_income_preferences_values_learning_constraints(session):
    card = await _make_card(session)

    answers = CareerIntentAnswers(
        goal_type=CareerGoalType.CHANGE_CAREER, time_horizon="6_months", location_region="Київ",
        work_format=WorkFormat.HYBRID, current_income=20000, target_income=35000,
        preferred_work_object=WorkObject.PEOPLE, autonomy_preference=0.7,
        top_work_value_keys=["income", "growth", "stability"],
        learning_hours_per_week=5, learning_budget=5000, willing_new_credential=True,
        willing_lower_entry_role=False, excluded_career_codes=["truck_driver"],
        constraints=[ConstraintAnswer(constraint_type="relocation", value="cannot relocate", severity="strong")],
    )
    await submit_career_intent(session, card, answers)
    await session.commit()

    goal = (await session.execute(select(MnpCareerGoal).where(MnpCareerGoal.career_card_id == card.id))).scalar_one()
    assert goal.goal_type == CareerGoalType.CHANGE_CAREER

    income = (await session.execute(select(MnpIncomeTarget).where(MnpIncomeTarget.career_card_id == card.id))).scalar_one()
    assert income.target_income == 35000

    pref = (await session.execute(select(MnpPreferenceProfile).where(MnpPreferenceProfile.career_card_id == card.id))).scalar_one()
    assert pref.work_format == WorkFormat.HYBRID
    assert pref.location_region == "Київ"

    values = (
        await session.execute(select(MnpPersonWorkValue).where(MnpPersonWorkValue.career_card_id == card.id))
    ).scalars().all()
    assert len(values) == 3
    ranks = {v.priority_rank for v in values}
    assert ranks == {1, 2, 3}

    constraints = (await session.execute(select(MnpConstraint).where(MnpConstraint.career_card_id == card.id))).scalars().all()
    types = {c.constraint_type for c in constraints}
    assert "excluded_career" in types
    assert "relocation" in types


async def test_income_target_upsert_not_duplicated_on_resubmit(session):
    card = await _make_card(session)
    await submit_career_intent(session, card, CareerIntentAnswers(target_income=30000))
    await submit_career_intent(session, card, CareerIntentAnswers(target_income=40000))
    await session.commit()

    rows = (await session.execute(select(MnpIncomeTarget).where(MnpIncomeTarget.career_card_id == card.id))).scalars().all()
    assert len(rows) == 1
    assert rows[0].target_income == 40000


async def test_missing_fields_all_missing_on_blank_card(session):
    card = await _make_card(session)
    missing = await get_missing_fields(session, card.id)
    assert "current_role" in missing.career_capital
    assert "goal" in missing.career_intent


async def test_missing_fields_shrinks_after_cv_upload(session):
    await seed_alpha_career_kb(session)
    from app.services.resume_parser_mnp.parser import upload_and_parse_resume

    user = IdentityUser(locale="uk")
    session.add(user)
    await session.flush()
    text = "Досвід роботи\n2020 - теперішній час\nМенеджер\nробота\n\nОсвіта\nУніверситет, бакалавр, 2019\n".encode("utf-8")
    card, _ = await upload_and_parse_resume(session, user_id=user.id, filename="cv.txt", content_bytes=text)

    missing = await get_missing_fields(session, card.id)
    assert "current_role" not in missing.career_capital  # CV already answered it
    assert "education" not in missing.career_capital
    assert "languages" in missing.career_capital  # CV had none -- still needed
    assert "goal" in missing.career_intent  # CV never answers Career Intent


async def test_missing_fields_does_not_crash_on_multiple_rows(session):
    """Regression: a CV with two jobs and two degrees (both entirely
    normal -- a person can have more than one of either) must not raise
    sqlalchemy.exc.MultipleResultsFound. Caught during Founder Acceptance
    Testing -- get_missing_fields previously used scalar_one_or_none()
    (which requires 0 or 1 rows) on tables with no such uniqueness
    constraint."""

    await seed_alpha_career_kb(session)
    from app.services.resume_parser_mnp.parser import upload_and_parse_resume

    user = IdentityUser(locale="uk")
    session.add(user)
    await session.flush()
    text = (
        "Досвід роботи\n"
        "2018 - 2020\nМенеджер А\nробота\n"
        "2020 - теперішній час\nМенеджер Б\nробота\n\n"
        "Освіта\n"
        "Університет 1, бакалавр, 2015\n"
        "Університет 2, магістр, 2018\n"
    ).encode("utf-8")
    card, _ = await upload_and_parse_resume(session, user_id=user.id, filename="cv.txt", content_bytes=text)

    missing = await get_missing_fields(session, card.id)  # must not raise
    assert "current_role" not in missing.career_capital
    assert "education" not in missing.career_capital
