"""Request schemas for the MNP V1 API (`MNP_API_CONTRACTS_V1`). Response
bodies are built directly from the service-layer dataclasses via
`dataclasses.asdict` in `app/api/mnp.py` -- no separate response-schema
duplication."""

from __future__ import annotations

from pydantic import BaseModel


class LanguageAnswerIn(BaseModel):
    language_code: str
    overall_level: str | None = None


class ConstraintAnswerIn(BaseModel):
    constraint_type: str
    value: str
    severity: str = "preference"


class CareerCapitalAnswersIn(BaseModel):
    current_role: str | None = None
    years_of_experience: float | None = None
    responsibilities: str | None = None
    skill_phrases: list[str] = []
    education_level: str | None = None
    education_field: str | None = None
    education_institution: str | None = None
    graduation_year: int | None = None
    credential_names: list[str] = []
    languages: list[LanguageAnswerIn] = []


class CareerIntentAnswersIn(BaseModel):
    goal_type: str | None = None
    location_region: str | None = None
    work_format: str | None = None
    current_income: float | None = None
    target_income: float | None = None
    income_currency: str = "UAH"
    time_horizon: str | None = None
    willingness_change_career: bool | None = None
    preferred_work_object: str | None = None
    autonomy_preference: float | None = None
    teamwork_preference: float | None = None
    customer_interaction_preference: float | None = None
    routine_vs_novelty_preference: float | None = None
    leadership_preference: float | None = None
    physical_activity_preference: float | None = None
    top_work_value_keys: list[str] = []
    learning_hours_per_week: float | None = None
    learning_budget: float | None = None
    willing_new_credential: bool | None = None
    willing_lower_entry_role: bool | None = None
    excluded_career_codes: list[str] = []
    constraints: list[ConstraintAnswerIn] = []


class MatchRunRequestIn(BaseModel):
    ranking_mode: str = "best_for_me"


# Career KB writes now go through the Career KB Editor (app/api/mnp_admin.py),
# which accepts free-form JSON bodies validated in the service layer.
