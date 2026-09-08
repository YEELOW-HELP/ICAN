from app.bot import anketa
from app.bot.states import Anketa


def test_next_state_walks_the_full_order():
    assert anketa.next_state(Anketa.city.state) == Anketa.desired_role
    assert anketa.next_state(Anketa.desired_role.state) == Anketa.experience
    assert anketa.next_state(Anketa.experience.state) == Anketa.employment_format
    assert anketa.next_state(Anketa.employment_format.state) == Anketa.work_format
    assert anketa.next_state(Anketa.work_format.state) == Anketa.income


def test_next_state_returns_none_after_last_step():
    assert anketa.next_state(Anketa.income.state) is None


def test_build_profile_maps_answers_to_fields():
    answers = {
        "city": "Харків",
        "desired_role": "бухгалтер",
        "experience": "5+ років",
        "employment_format": "full-time",
        "work_format": "remote",
        "income": "35000 грн",
    }

    profile = anketa.build_profile(answers)

    assert profile.city == "Харків"
    assert profile.desired_role == "бухгалтер"
    assert profile.total_experience == "5+ років"
    assert profile.employment_format == "full-time"
    assert profile.work_format == "remote"
    assert profile.desired_min_income == "35000 грн"


def test_build_profile_leaves_missing_answers_null():
    profile = anketa.build_profile({"city": "Київ"})
    assert profile.city == "Київ"
    assert profile.desired_role is None
