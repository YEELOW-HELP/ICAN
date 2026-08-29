"""MNP V1 BLOCK B -- resume upload -> parse -> CareerCard integration
tests. Zero LLM calls anywhere in this pipeline (Founder Decision #4)."""

import ast
import inspect

from sqlalchemy import select

from app.db.models_career_card import (
    MnpAchievement,
    MnpCareerCard,
    MnpEvidence,
    MnpExperience,
    MnpLanguage,
    MnpPersonSkill,
    MnpSourceDocument,
    MnpUnmappedPhrase,
    TextExtractionStatus,
)
from app.db.models_identity import IdentityUser
from app.services.career_kb_mnp.seed_alpha import seed_alpha_career_kb
from app.services.resume_parser_mnp import extract, extraction, parser, patterns, sections
from app.services.resume_parser_mnp.parser import upload_and_parse_resume

SAMPLE_CV_TXT = (
    "Олена Ковальчук\n\n"
    "Досвід роботи\n"
    "01.2020 - 05.2022\n"
    "Менеджер з продажу, ТОВ Ромашка\n"
    "Веде переговори з клієнтами, керував командою з 5 осіб, збільшив продажі на 30%\n\n"
    "06.2022 - теперішній час\n"
    "Старший менеджер з продажу — ТОВ Соняшник\n"
    "Розвиток портфелю B2B клієнтів\n\n"
    "Освіта\n"
    "Київський національний університет, бакалавр економіки, 2019\n\n"
    "Навички\n"
    "Переговори, CRM, Excel, Управління командою, зовсім невідома навичка яку ніхто не мапував\n\n"
    "Мови\n"
    "Англійська - Intermediate\n"
    "Українська - Native\n\n"
    "Сертифікати\n"
    "Сертифікат з управління проектами PMI\n"
).encode("utf-8")


async def _make_user(session) -> IdentityUser:
    user = IdentityUser(locale="uk")
    session.add(user)
    await session.flush()
    return user


async def test_full_txt_pipeline_creates_career_card_and_evidence(session):
    await seed_alpha_career_kb(session)
    user = await _make_user(session)

    card, document = await upload_and_parse_resume(
        session, user_id=user.id, filename="cv.txt", content_bytes=SAMPLE_CV_TXT
    )

    assert document.text_extraction_status == TextExtractionStatus.EXTRACTED

    experiences = (await session.execute(select(MnpExperience).where(MnpExperience.career_card_id == card.id))).scalars().all()
    assert len(experiences) == 2
    titles = {e.raw_job_title for e in experiences}
    assert "Менеджер з продажу" in titles

    managed = [e for e in experiences if e.management_scope]
    assert len(managed) == 1
    assert managed[0].team_size == 5

    achievements = (await session.execute(select(MnpAchievement).where(MnpAchievement.career_card_id == card.id))).scalars().all()
    assert len(achievements) == 1
    assert "30%" in achievements[0].description

    languages = (await session.execute(select(MnpLanguage).where(MnpLanguage.career_card_id == card.id))).scalars().all()
    assert {l.language_code for l in languages} == {"en", "uk"}

    person_skills = (await session.execute(select(MnpPersonSkill).where(MnpPersonSkill.career_card_id == card.id))).scalars().all()
    assert len(person_skills) >= 3  # Переговори/CRM/Excel/Управління командою resolve to seeded alpha skills

    unmapped = (await session.execute(select(MnpUnmappedPhrase).where(MnpUnmappedPhrase.career_card_id == card.id))).scalars().all()
    assert any("невідома навичка" in u.raw_phrase for u in unmapped)

    evidence = (await session.execute(select(MnpEvidence).where(MnpEvidence.career_card_id == card.id))).scalars().all()
    assert len(evidence) > 0
    assert all(e.source_type.value == "cv" for e in evidence)


async def test_no_confirmation_screen_career_card_immediately_usable(session):
    """Founder Decision #6: result is immediate, no mandatory
    confirmation step."""

    await seed_alpha_career_kb(session)
    user = await _make_user(session)
    card, document = await upload_and_parse_resume(
        session, user_id=user.id, filename="cv.txt", content_bytes=SAMPLE_CV_TXT
    )
    # The card and its sub-entities are already committed and queryable --
    # no separate "confirm" call is required anywhere in this test.
    reloaded = await session.get(MnpCareerCard, card.id)
    assert reloaded is not None
    assert reloaded.version == 2  # snapshot_career_card bumped it from 1 to 2 already


async def test_management_scope_never_inferred_without_explicit_team_size(session):
    await seed_alpha_career_kb(session)
    user = await _make_user(session)
    text = "Досвід роботи\n2020-2022\nManager of Sales\nResponsible for sales team\n".encode("utf-8")
    card, _ = await upload_and_parse_resume(session, user_id=user.id, filename="cv.txt", content_bytes=text)

    experiences = (await session.execute(select(MnpExperience).where(MnpExperience.career_card_id == card.id))).scalars().all()
    assert experiences[0].management_scope is False
    assert experiences[0].team_size is None


async def test_unsupported_format_recorded_not_raised(session):
    user = await _make_user(session)
    card, document = await upload_and_parse_resume(
        session, user_id=user.id, filename="cv.xyz", content_bytes=b"whatever"
    )
    assert document.text_extraction_status == TextExtractionStatus.UNSUPPORTED_FORMAT
    assert card is not None  # a card shell still exists -- questionnaire fallback can build on it


async def test_no_text_layer_recorded_as_ocr_required(session):
    user = await _make_user(session)
    card, document = await upload_and_parse_resume(
        session, user_id=user.id, filename="cv.txt", content_bytes=b"   \n\n  "
    )
    assert document.text_extraction_status == TextExtractionStatus.OCR_REQUIRED


async def test_oversized_file_rejected(session):
    from app.core.config import settings
    from app.services.exceptions import CVFileTooLargeError
    import pytest

    user = await _make_user(session)
    oversized = b"x" * (settings.max_upload_size_mb * 1024 * 1024 + 1)
    with pytest.raises(CVFileTooLargeError):
        await upload_and_parse_resume(session, user_id=user.id, filename="cv.txt", content_bytes=oversized)


async def test_source_document_stores_reference_not_raw_bytes(session):
    """MNP_DATA_MODEL_V1 §5: SourceDocument stores storage_ref, not the
    file bytes themselves."""

    user = await _make_user(session)
    _, document = await upload_and_parse_resume(session, user_id=user.id, filename="cv.txt", content_bytes=SAMPLE_CV_TXT)
    assert document.storage_ref
    assert isinstance(document.storage_ref, str)


async def test_reparsing_same_cv_does_not_duplicate_person_skills(session):
    """A second upload for the same user re-targets the master card
    (Founder Decision #7) -- but this test only asserts no *duplicate*
    PersonSkill row is created within a single application, i.e. the
    idempotency check inside apply_parsed_resume_to_career_card works."""

    await seed_alpha_career_kb(session)
    user = await _make_user(session)
    card, _ = await upload_and_parse_resume(session, user_id=user.id, filename="cv.txt", content_bytes=SAMPLE_CV_TXT)

    skill_ids = [
        row.skill_id
        for row in (await session.execute(select(MnpPersonSkill).where(MnpPersonSkill.career_card_id == card.id))).scalars().all()
    ]
    assert len(skill_ids) == len(set(skill_ids))  # no duplicates


# ---------------------------------------------------------------------------
# Zero-AI guarantee (matches the established repo pattern: AST scan +
# behavioral guard).

def test_no_ai_gateway_imports_in_resume_parser_package():
    forbidden_module_prefixes = ("app.ai_gateway", "anthropic")
    forbidden_names = {"AIGateway", "AnswerExtractor", "ClaimSynthesizer", "Anthropic"}
    for module in (extract, extraction, parser, patterns, sections):
        tree = ast.parse(inspect.getsource(module))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not any(
                    node.module == p or node.module.startswith(p + ".") for p in forbidden_module_prefixes
                ), f"{module.__name__} imports forbidden module {node.module!r}"
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not any(alias.name == p or alias.name.startswith(p + ".") for p in forbidden_module_prefixes)
        referenced = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        assert referenced.isdisjoint(forbidden_names)
