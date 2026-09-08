"""Seeds the 9 canonical Work Value keys (`MNP_METHODOLOGY_V1` §21) --
a small, fixed reference table, not admin-editable in V1."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_career_card import MnpWorkValue

WORK_VALUES: list[tuple[str, str, str]] = [
    ("income", "Дохід", "Income"),
    ("stability", "Стабільність", "Stability"),
    ("autonomy", "Автономія", "Autonomy"),
    ("growth", "Кар'єрне зростання", "Growth"),
    ("recognition", "Визнання", "Recognition"),
    ("social_impact", "Соціальний вплив", "Social Impact"),
    ("creativity", "Творчість", "Creativity"),
    ("work_life_balance", "Баланс роботи і життя", "Work-Life Balance"),
    ("learning", "Навчання", "Learning"),
]


async def ensure_work_values_seeded(session: AsyncSession) -> dict[str, MnpWorkValue]:
    by_key: dict[str, MnpWorkValue] = {}
    for key, label_uk, label_en in WORK_VALUES:
        existing = await session.execute(select(MnpWorkValue).where(MnpWorkValue.key == key))
        found = existing.scalar_one_or_none()
        if found is None:
            found = MnpWorkValue(key=key, label_uk=label_uk, label_en=label_en)
            session.add(found)
            await session.flush()
        by_key[key] = found
    return by_key
