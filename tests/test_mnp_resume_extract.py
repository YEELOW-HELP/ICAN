"""MNP V1 BLOCK B -- pure resume-extraction unit tests (no DB, no I/O).
Deterministic: same input text always produces the same structured
output (MNP_RESUME_PARSER_V1 "Acceptance")."""

from datetime import date

from app.services.resume_parser_mnp.extract import (
    parse_credentials_section,
    parse_education_section,
    parse_experience_section,
    parse_languages_section,
    parse_resume_sections,
    parse_skills_section,
)
from app.services.resume_parser_mnp.sections import split_into_sections


def test_split_into_sections_recognizes_uk_ru_en_headers():
    text = "Ім'я\n\nДосвід роботи\nline1\n\nEducation\nline2\n\nНавички\nline3"
    sections = split_into_sections(text)
    assert sections["header"] == ["Ім'я", ""]
    assert sections["experience"] == ["line1", ""]
    assert sections["education"] == ["line2", ""]
    assert sections["skills"] == ["line3"]


def test_parse_experience_extracts_title_company_dates():
    lines = ["01.2020 - 05.2022", "Менеджер з продажу, ТОВ Ромашка", "Веде переговори з клієнтами"]
    result = parse_experience_section(lines)
    assert len(result) == 1
    exp = result[0]
    assert exp.raw_job_title == "Менеджер з продажу"
    assert exp.company_name == "ТОВ Ромашка"
    assert exp.start_date == date(2020, 1, 1)
    assert exp.end_date == date(2022, 5, 1)
    assert exp.is_current is False


def test_parse_experience_detects_current_role():
    lines = ["06.2022 - теперішній час", "Старший менеджер"]
    result = parse_experience_section(lines)
    assert result[0].is_current is True
    assert result[0].end_date is None


def test_parse_experience_detects_explicit_team_size():
    lines = ["2020-2022", "Керівник", "керував командою з 5 осіб"]
    result = parse_experience_section(lines)
    assert result[0].team_size == 5
    assert result[0].management_scope is True


def test_parse_experience_never_infers_management_without_explicit_number():
    """MNP_RESUME_PARSER_V1 principle applied to management_scope:
    explicit only, never inferred from a bare title like "Manager"."""

    lines = ["2020-2022", "Manager of Sales Department"]
    result = parse_experience_section(lines)
    assert result[0].team_size is None
    assert result[0].management_scope is False


def test_parse_experience_multiple_jobs_split_into_separate_blocks():
    lines = [
        "01.2020 - 05.2022", "Job A", "did things",
        "06.2022 - present", "Job B", "did other things",
    ]
    result = parse_experience_section(lines)
    assert len(result) == 2
    assert result[0].raw_job_title == "Job A"
    assert result[1].raw_job_title == "Job B"
    assert result[1].is_current is True


def test_parse_education_extracts_level_and_year():
    lines = ["Київський національний університет, бакалавр економіки, 2019"]
    result = parse_education_section(lines)
    assert result[0].level == "bachelor"
    assert result[0].graduation_year == 2019


def test_parse_education_missing_level_is_none_not_guessed():
    lines = ["Деякий навчальний заклад, 2015"]
    result = parse_education_section(lines)
    assert result[0].level is None
    assert result[0].graduation_year == 2015


def test_parse_skills_splits_and_dedupes():
    lines = ["Переговори, CRM, Excel, Переговори"]
    result = parse_skills_section(lines)
    assert result == ["Переговори", "CRM", "Excel"]


def test_parse_skills_drops_long_non_skill_sentences():
    lines = ["Excel, " + "довге речення яке не є навичкою " * 5]
    result = parse_skills_section(lines)
    assert result == ["Excel"]


def test_parse_languages_extracts_code_and_level():
    lines = ["Англійська - Intermediate", "Українська - Native"]
    result = parse_languages_section(lines)
    assert result[0].language_code == "en"
    assert result[0].overall_level == "intermediate"
    assert result[1].language_code == "uk"
    assert result[1].overall_level == "native"


def test_parse_languages_unknown_level_stays_none_not_assumed():
    lines = ["Польська"]
    result = parse_languages_section(lines)
    assert result[0].language_code == "pl"
    assert result[0].overall_level is None


def test_parse_credentials_one_per_line():
    lines = ["Сертифікат PMI", "Сертифікат Scrum Master"]
    result = parse_credentials_section(lines)
    assert [c.name for c in result] == ["Сертифікат PMI", "Сертифікат Scrum Master"]


def test_full_pipeline_deterministic_same_input_same_output():
    text = (
        "Досвід роботи\n01.2020 - 05.2022\nМенеджер, Компанія А\nробота\n\n"
        "Освіта\nУніверситет, бакалавр, 2019\n\n"
        "Навички\nExcel, CRM\n\n"
        "Мови\nАнглійська - Advanced\n"
    )
    result1 = parse_resume_sections(split_into_sections(text))
    result2 = parse_resume_sections(split_into_sections(text))
    assert result1 == result2
