from __future__ import annotations

from aiogram.fsm.state import State
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.states import Anketa
from app.schemas.profile import ProfileDraft

CITY_OPTIONS = ["Харків", "Київ", "Віддалено", "Інше"]
EXPERIENCE_OPTIONS = ["Без досвіду", "До 1 року", "1-3 роки", "3-5 років", "5+ років"]
EMPLOYMENT_OPTIONS = [("Повна зайнятість", "full-time"), ("Часткова зайнятість", "part-time")]
WORK_FORMAT_OPTIONS = [
    ("Офіс", "onsite"),
    ("Гібрид", "hybrid"),
    ("Віддалено", "remote"),
    ("Гнучкий графік", "flexible"),
]


def _keyboard(prefix: str, options: list) -> InlineKeyboardMarkup:
    rows = []
    for opt in options:
        text, value = opt if isinstance(opt, tuple) else (opt, opt)
        rows.append([InlineKeyboardButton(text=text, callback_data=f"anketa:{prefix}:{value}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


CITY_KEYBOARD = _keyboard("city", CITY_OPTIONS)
EXPERIENCE_KEYBOARD = _keyboard("exp", EXPERIENCE_OPTIONS)
EMPLOYMENT_KEYBOARD = _keyboard("emp", EMPLOYMENT_OPTIONS)
WORK_FORMAT_KEYBOARD = _keyboard("work", WORK_FORMAT_OPTIONS)

# Linear order the questionnaire walks through. `Anketa.city_other` is a side
# branch (entered only when "Інше" is picked) and isn't part of this list.
ORDER: list[State] = [
    Anketa.city,
    Anketa.desired_role,
    Anketa.experience,
    Anketa.employment_format,
    Anketa.work_format,
    Anketa.income,
]

FIELD_MAP = {"city": "city", "exp": "experience", "emp": "employment_format", "work": "work_format"}

PROMPTS: dict[str, tuple[str, InlineKeyboardMarkup | None]] = {
    Anketa.city.state: ("Де шукаєш роботу?", CITY_KEYBOARD),
    Anketa.desired_role.state: ("Яку роботу шукаєш?", None),
    Anketa.experience.state: ("Досвід роботи?", EXPERIENCE_KEYBOARD),
    Anketa.employment_format.state: ("Формат зайнятості?", EMPLOYMENT_KEYBOARD),
    Anketa.work_format.state: ("Формат роботи?", WORK_FORMAT_KEYBOARD),
    Anketa.income.state: ("Бажаний мінімальний дохід (сума і валюта)?", None),
}


def prompt_for(state: State) -> tuple[str, InlineKeyboardMarkup | None]:
    return PROMPTS[state.state]


def next_state(current: str) -> State | None:
    states = [s.state for s in ORDER]
    idx = states.index(current)
    if idx + 1 < len(states):
        return ORDER[idx + 1]
    return None


def build_profile(answers: dict[str, str]) -> ProfileDraft:
    return ProfileDraft(
        city=answers.get("city"),
        desired_role=answers.get("desired_role"),
        total_experience=answers.get("experience"),
        employment_format=answers.get("employment_format"),
        work_format=answers.get("work_format"),
        desired_min_income=answers.get("income"),
    )
