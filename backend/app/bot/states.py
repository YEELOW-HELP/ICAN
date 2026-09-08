from aiogram.fsm.state import State, StatesGroup


class Onboarding(StatesGroup):
    choosing_method = State()


class CVFlow(StatesGroup):
    awaiting_file = State()


class Anketa(StatesGroup):
    city = State()
    city_other = State()
    desired_role = State()
    experience = State()
    employment_format = State()
    work_format = State()
    income = State()


class V1Flow(StatesGroup):
    """States for the new Hybrid assessment flow (Stage 1), gated behind
    settings.bot_flow == "v1". Kept separate from the legacy states above
    so the two flows can never interfere with each other's FSM."""

    awaiting_consent = State()
    awaiting_promo = State()
    awaiting_cv_decision = State()
    awaiting_cv_file = State()
    awaiting_open_answer = State()
    awaiting_structured_answer = State()
