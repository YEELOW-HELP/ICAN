from __future__ import annotations

from app.schemas.profile import ProfileDraft

_LABELS: list[tuple[str, str]] = [
    ("desired_role", "Шукаєш"),
    ("total_experience", "Досвід"),
    ("city", "Місто"),
    ("education", "Освіта"),
    ("skills", "Навички"),
    ("languages", "Мови"),
    ("work_format", "Формат"),
    ("employment_format", "Зайнятість"),
    ("schedule", "Графік"),
    ("desired_min_income", "Дохід"),
    ("constraints", "Обмеження"),
    ("other_notes", "Інше"),
]


def render_profile_card(profile: ProfileDraft, *, title: str = "Твій профіль") -> str:
    """Render the same structured summary regardless of whether the profile
    came from a CV, free-form chat, or the button questionnaire — the three
    intake paths must converge on one recognizable view (per product spec)."""
    lines = [title, ""]

    for field, label in _LABELS:
        value = getattr(profile, field, None)
        if not value:
            continue
        if isinstance(value, list):
            value = ", ".join(value)
        if field == "desired_min_income" and profile.desired_currency:
            value = f"{value} {profile.desired_currency}"
        lines.append(f"{label}: {value}")

    if len(lines) == 2:
        lines.append("(поки що дані відсутні)")

    return "\n".join(lines)
