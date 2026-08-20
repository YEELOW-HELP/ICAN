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
