"""Minimal seed taxonomy for Stage 2 (brief §9/§3). This is deliberately
NOT the final МОЖУ methodology -- just enough versioned, seeded terms to
validate the Evidence -> Claim -> Profile pipeline end to end. Real
methodology content is Methodology's future work
(docs/engineering/11_TECHNICAL_DEBT_REGISTER.md Item 11), applied as new
`TaxonomyTerm` rows / a new `TaxonomyVersion`, never a Python enum change
or a parallel taxonomy system.

Seeding is an idempotent, application-level `ensure_*` function -- not
baked into the Alembic migration -- because taxonomy *content* is
explicitly expected to evolve as data (new terms, new versions) long
before the next schema migration, unlike Stage 1's `product_plans` seed
(BASIC/PREMIUM), which really is fixed structural configuration. Calling
this twice is a no-op after the first call.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_profile import ProfileDimension, Taxonomy, TaxonomyTerm, TaxonomyVersion, TaxonomyVersionStatus

TAXONOMY_KEY = "potential_dimensions"
TAXONOMY_VERSION_NUMBER = 1

# (term_key, dimension, label_uk, label_en) -- a small, explicit seed, a
# handful of terms per dimension, not an exhaustive vocabulary.
_SEED_TERMS: tuple[tuple[str, ProfileDimension, str, str], ...] = (
    ("systems_thinking", ProfileDimension.STRENGTH, "Системне мислення", "Systems thinking"),
    ("leadership_coordination", ProfileDimension.STRENGTH, "Лідерство / координація", "Leadership / coordination"),
    ("communication", ProfileDimension.STRENGTH, "Комунікація", "Communication"),
    ("attention_to_detail", ProfileDimension.STRENGTH, "Увага до деталей", "Attention to detail"),
    ("people_facing_work", ProfileDimension.INTEREST, "Робота з людьми", "People-facing work"),
    ("technical_problem_solving", ProfileDimension.INTEREST, "Технічні задачі", "Technical problem-solving"),
    ("creative_expression", ProfileDimension.INTEREST, "Творчість", "Creative expression"),
    ("autonomy", ProfileDimension.VALUE, "Автономність", "Autonomy"),
    ("stability", ProfileDimension.VALUE, "Стабільність", "Stability"),
    ("impact", ProfileDimension.VALUE, "Вплив / користь", "Impact"),
    ("growth", ProfileDimension.MOTIVATION, "Розвиток", "Growth"),
    ("achievement", ProfileDimension.MOTIVATION, "Досягнення", "Achievement"),
    ("helping_others", ProfileDimension.MOTIVATION, "Допомога іншим", "Helping others"),
    ("programming", ProfileDimension.SKILL, "Програмування", "Programming"),
    ("project_management", ProfileDimension.SKILL, "Управління проєктами", "Project management"),
    ("sales", ProfileDimension.SKILL, "Продажі", "Sales"),
    ("extraversion", ProfileDimension.TRAIT, "Екстраверсія", "Extraversion"),
    ("conscientiousness", ProfileDimension.TRAIT, "Сумлінність", "Conscientiousness"),
    ("adaptability", ProfileDimension.TRAIT, "Адаптивність", "Adaptability"),
    ("team_environment", ProfileDimension.WORK_PREFERENCE, "Командна робота", "Team environment"),
    ("remote_work", ProfileDimension.WORK_PREFERENCE, "Віддалена робота", "Remote work"),
    ("structured_environment", ProfileDimension.WORK_PREFERENCE, "Структуроване середовище", "Structured environment"),
    ("location_constraint", ProfileDimension.CONSTRAINT, "Локація", "Location constraint"),
    ("schedule_constraint", ProfileDimension.CONSTRAINT, "Графік", "Schedule constraint"),
    ("income_requirement", ProfileDimension.CONSTRAINT, "Вимоги до доходу", "Income requirement"),
    ("career_change", ProfileDimension.GOAL, "Зміна напрямку кар'єри", "Career change"),
    ("skill_development", ProfileDimension.GOAL, "Розвиток навичок", "Skill development"),
    ("stability_seeking", ProfileDimension.GOAL, "Пошук стабільності", "Stability seeking"),
    ("entry_level", ProfileDimension.EXPERIENCE, "Початковий рівень", "Entry level"),
    ("mid_level", ProfileDimension.EXPERIENCE, "Середній рівень", "Mid level"),
    ("senior_level", ProfileDimension.EXPERIENCE, "Досвідчений рівень", "Senior level"),
    ("family_responsibilities", ProfileDimension.CONTEXTUAL_FACTOR, "Сімейні обов'язки", "Family responsibilities"),
    ("language_proficiency", ProfileDimension.CONTEXTUAL_FACTOR, "Рівень мови", "Language proficiency"),
)


async def ensure_seed_taxonomy(session: AsyncSession) -> TaxonomyVersion:
    """Get-or-create the v1 potential_dimensions taxonomy and its seed
    terms, returning the active TaxonomyVersion. Safe to call on every
    profile generation -- cheap reads once seeded, no duplicate rows on
    repeat calls (checked by key/term_key, not inserted unconditionally)."""
    result = await session.execute(select(Taxonomy).where(Taxonomy.key == TAXONOMY_KEY))
    taxonomy = result.scalar_one_or_none()
    if taxonomy is None:
        taxonomy = Taxonomy(
            key=TAXONOMY_KEY,
            name="Potential dimensions",
            description="Stage 2 seed taxonomy for the Human Potential Profile pipeline -- not final methodology.",
        )
        session.add(taxonomy)
        await session.flush()

    result = await session.execute(
        select(TaxonomyVersion).where(
            TaxonomyVersion.taxonomy_id == taxonomy.id, TaxonomyVersion.version == TAXONOMY_VERSION_NUMBER
        )
    )
    version = result.scalar_one_or_none()
    if version is None:
        version = TaxonomyVersion(
            taxonomy_id=taxonomy.id, version=TAXONOMY_VERSION_NUMBER, status=TaxonomyVersionStatus.ACTIVE
        )
        session.add(version)
        await session.flush()

    result = await session.execute(select(TaxonomyTerm.term_key).where(TaxonomyTerm.taxonomy_version_id == version.id))
    existing_keys = {row[0] for row in result.all()}

    for term_key, dimension, label_uk, label_en in _SEED_TERMS:
        if term_key in existing_keys:
            continue
        session.add(
            TaxonomyTerm(
                taxonomy_version_id=version.id,
                term_key=term_key,
                label_uk=label_uk,
                label_en=label_en,
                dimension=dimension.value,
            )
        )

    await session.commit()
    await session.refresh(version)
    return version
