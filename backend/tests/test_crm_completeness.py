from app.db.models_crm import CareerConsultation, Client, ClientProfile, SourceChannel
from app.services.crm.completeness import check_ready_for_matching, check_screening_complete


def _client(**kwargs):
    return Client(source_channel=SourceChannel.PHONE, **kwargs)


def _profile(**kwargs):
    return ClientProfile(**kwargs)


def test_screening_incomplete_lists_missing_fields():
    client = _client()
    result = check_screening_complete(client, None, [])
    assert result.ready is False
    assert "Профіль клієнта не заповнено" in result.missing


def test_screening_complete_when_all_fields_present():
    client = _client(phone="+380501112233", country="Україна", city="Харків")
    profile = _profile(
        currently_employed=False,
        primary_target="бухгалтер",
        min_salary="30000",
        employment_types=["full-time"],
        work_formats=["remote"],
        schedules=["5/2"],
        constraints_comment="немає обмежень",
    )
    from app.db.models_crm import ClientSkill

    result = check_screening_complete(client, profile, [ClientSkill(skill_name="Excel")])
    assert result.ready is True
    assert result.missing == []


def test_ready_for_matching_requires_consultant_conclusion():
    client = _client(country="Україна", city="Харків")
    profile = _profile(
        currently_employed=True,
        primary_target="бухгалтер",
        min_salary="30000",
        salary_currency="грн",
        employment_types=["full-time"],
        work_formats=["remote"],
        schedules=["5/2"],
        work_cities=["Харків"],
        constraints_comment="немає",
    )
    from app.db.models_crm import ClientLanguage, ClientSkill, WorkExperience

    result = check_ready_for_matching(
        client,
        profile,
        [WorkExperience(position="Бухгалтер")],
        [ClientSkill(skill_name="Excel")],
        [ClientLanguage(language="українська")],
        consultation=None,
    )

    assert result.ready is False
    assert "Career Consultant Conclusion" in result.missing


def test_ready_for_matching_true_when_everything_present():
    client = _client(country="Україна", city="Харків")
    profile = _profile(
        currently_employed=True,
        primary_target="бухгалтер",
        min_salary="30000",
        salary_currency="грн",
        employment_types=["full-time"],
        work_formats=["remote"],
        schedules=["5/2"],
        work_cities=["Харків"],
        constraints_comment="немає",
    )
    from app.db.models_crm import ClientLanguage, ClientSkill, WorkExperience

    consultation = CareerConsultation(conclusion="Готовий до підбору вакансій бухгалтера")

    result = check_ready_for_matching(
        client,
        profile,
        [WorkExperience(position="Бухгалтер")],
        [ClientSkill(skill_name="Excel")],
        [ClientLanguage(language="українська")],
        consultation=consultation,
    )

    assert result.ready is True
    assert result.missing == []
