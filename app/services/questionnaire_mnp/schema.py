"""Input DTOs for the Minimal Questionnaire (`MNP_MINIMAL_QUESTIONNAIRE_V1`).
Plain dataclasses -- framework-agnostic, like the rest of this repo's
service layer; a future API layer (BLOCK D, MNP_API_CONTRACTS_V1) wraps
these in Pydantic request models."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.db.models_career_card import CareerGoalType, WorkFormat, WorkObject


@dataclass(frozen=True)
class LanguageAnswer:
    language_code: str
    overall_level: str | None = None


@dataclass(frozen=True)
class ConstraintAnswer:
    constraint_type: str
    value: str
    severity: str = "preference"  # PREFERENCE | STRONG | HARD


@dataclass(frozen=True)
class CareerCapitalAnswers:
    """MNP_MINIMAL_QUESTIONNAIRE_V1 "Without-CV Career Capital minimum".
    Every field is optional -- BLOCK D only asks for what a prior CV
    upload didn't already establish ("do not ask what we already know")."""

    current_role: str | None = None
    years_of_experience: float | None = None
    responsibilities: str | None = None
    skill_phrases: list[str] = field(default_factory=list)
    education_level: str | None = None
    education_field: str | None = None
    education_institution: str | None = None
    graduation_year: int | None = None
    credential_names: list[str] = field(default_factory=list)
    languages: list[LanguageAnswer] = field(default_factory=list)


@dataclass(frozen=True)
class CareerIntentAnswers:
    """MNP_MINIMAL_QUESTIONNAIRE_V1 "Required decision variables"."""

    goal_type: CareerGoalType | None = None
    location_region: str | None = None
    work_format: WorkFormat | None = None
    current_income: float | None = None
    target_income: float | None = None
    income_currency: str = "UAH"
    time_horizon: str | None = None
    willingness_change_career: bool | None = None
    preferred_work_object: WorkObject | None = None
    autonomy_preference: float | None = None
    teamwork_preference: float | None = None
    customer_interaction_preference: float | None = None
    routine_vs_novelty_preference: float | None = None
    leadership_preference: float | None = None
    physical_activity_preference: float | None = None
    top_work_value_keys: list[str] = field(default_factory=list)  # ranked, index 0 = highest priority
    learning_hours_per_week: float | None = None
    learning_budget: float | None = None
    willing_new_credential: bool | None = None
    willing_lower_entry_role: bool | None = None
    excluded_career_codes: list[str] = field(default_factory=list)
    constraints: list[ConstraintAnswer] = field(default_factory=list)
