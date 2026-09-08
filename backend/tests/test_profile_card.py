from app.bot.profile_card import render_profile_card
from app.schemas.profile import ProfileDraft


def test_render_profile_card_includes_only_known_fields():
    profile = ProfileDraft(
        desired_role="бухгалтер",
        city="Харків",
        total_experience="8 років",
        skills=["1С", "BAS", "Excel"],
        desired_min_income="35000",
        desired_currency="грн",
    )

    card = render_profile_card(profile)

    assert "Шукаєш: бухгалтер" in card
    assert "Місто: Харків" in card
    assert "Досвід: 8 років" in card
    assert "Навички: 1С, BAS, Excel" in card
    assert "Дохід: 35000 грн" in card
    assert "Освіта" not in card  # not set, must not appear as an empty line


def test_render_profile_card_handles_empty_profile():
    card = render_profile_card(ProfileDraft())
    assert "поки що дані відсутні" in card
