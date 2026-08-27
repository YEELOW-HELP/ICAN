"""Skills for the Career Knowledge Base are seeded `TaxonomyTerm` rows
under a dedicated `Taxonomy(key="skills")` -- reusing Stage 2's
`Taxonomy`/`TaxonomyVersion`/`TaxonomyTerm` tables directly rather than
introducing a parallel Skill entity (brief §8, see
app/db/models_knowledge.py's module docstring for the full rationale).

Idempotent get-or-create, same pattern as
app/services/profile/taxonomy.py::ensure_seed_taxonomy.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_profile import Taxonomy, TaxonomyTerm, TaxonomyVersion, TaxonomyVersionStatus

SKILLS_TAXONOMY_KEY = "skills"
SKILLS_TAXONOMY_VERSION_NUMBER = 1

# (term_key, label_uk, label_en) -- a shared cross-domain vocabulary
# sized for the Stage 3A curated seed, not an exhaustive skills ontology.
_SEED_SKILLS: tuple[tuple[str, str, str], ...] = (
    ("communication", "Комунікація", "Communication"),
    ("customer_service_skill", "Обслуговування клієнтів", "Customer service"),
    ("sales_technique", "Техніки продажів", "Sales technique"),
    ("leadership", "Лідерство", "Leadership"),
    ("project_management", "Управління проєктами", "Project management"),
    ("financial_analysis", "Фінансовий аналіз", "Financial analysis"),
    ("accounting_principles", "Основи бухгалтерського обліку", "Accounting principles"),
    ("programming", "Програмування", "Programming"),
    ("it_troubleshooting", "Усунення технічних несправностей", "IT troubleshooting"),
    ("database_management", "Управління базами даних", "Database management"),
    ("cad_design", "CAD-проєктування", "CAD design"),
    ("structural_analysis", "Розрахунок конструкцій", "Structural analysis"),
    ("electrical_systems", "Електричні системи", "Electrical systems"),
    ("plumbing_systems", "Сантехнічні системи", "Plumbing systems"),
    ("vehicle_operation", "Керування транспортним засобом", "Vehicle operation"),
    ("logistics_planning", "Логістичне планування", "Logistics planning"),
    ("inventory_management", "Управління запасами", "Inventory management"),
    ("nursing_care", "Медсестринський догляд", "Nursing care"),
    ("pharmacology_knowledge", "Знання фармакології", "Pharmacology knowledge"),
    ("teaching_pedagogy", "Педагогіка викладання", "Teaching pedagogy"),
    ("curriculum_design", "Розробка навчальних програм", "Curriculum design"),
    ("graphic_design_tools", "Інструменти графічного дизайну", "Graphic design tools"),
    ("video_editing_tools", "Інструменти відеомонтажу", "Video editing tools"),
    ("social_media_management", "Управління соціальними мережами", "Social media management"),
    ("content_writing", "Копірайтинг", "Content writing"),
    ("social_work_practice", "Практика соціальної роботи", "Social work practice"),
    ("community_engagement", "Робота з громадою", "Community engagement"),
    ("administrative_organization", "Адміністративна організація", "Administrative organization"),
    ("office_software", "Офісне програмне забезпечення", "Office software"),
    ("hospitality_service_skill", "Гостинність та сервіс", "Hospitality service"),
    ("culinary_skills", "Кулінарні навички", "Culinary skills"),
    ("quality_control_inspection", "Контроль якості", "Quality control inspection"),
    ("manufacturing_operations", "Виробничі операції", "Manufacturing operations"),
    ("attention_to_detail", "Увага до деталей", "Attention to detail"),
    ("teamwork", "Командна робота", "Teamwork"),
    ("problem_solving", "Розв'язання проблем", "Problem solving"),
    ("physical_stamina", "Фізична витривалість", "Physical stamina"),
)


async def ensure_skills_taxonomy(session: AsyncSession) -> TaxonomyVersion:
    """Get-or-create the v1 "skills" taxonomy and its seed terms,
    returning the active TaxonomyVersion. Safe to call repeatedly."""
    result = await session.execute(select(Taxonomy).where(Taxonomy.key == SKILLS_TAXONOMY_KEY))
    taxonomy = result.scalar_one_or_none()
    if taxonomy is None:
        taxonomy = Taxonomy(
            key=SKILLS_TAXONOMY_KEY,
            name="Skills",
            description="Shared skill vocabulary for the Career Knowledge Base (Stage 3A) -- reused from Stage 2's versioned taxonomy architecture.",
        )
        session.add(taxonomy)
        await session.flush()

    result = await session.execute(
        select(TaxonomyVersion).where(
            TaxonomyVersion.taxonomy_id == taxonomy.id, TaxonomyVersion.version == SKILLS_TAXONOMY_VERSION_NUMBER
        )
    )
    version = result.scalar_one_or_none()
    if version is None:
        version = TaxonomyVersion(
            taxonomy_id=taxonomy.id, version=SKILLS_TAXONOMY_VERSION_NUMBER, status=TaxonomyVersionStatus.ACTIVE
        )
        session.add(version)
        await session.flush()

    result = await session.execute(select(TaxonomyTerm.term_key).where(TaxonomyTerm.taxonomy_version_id == version.id))
    existing_keys = {row[0] for row in result.all()}

    for term_key, label_uk, label_en in _SEED_SKILLS:
        if term_key in existing_keys:
            continue
        session.add(
            TaxonomyTerm(taxonomy_version_id=version.id, term_key=term_key, label_uk=label_uk, label_en=label_en)
        )

    await session.commit()
    await session.refresh(version)
    return version


async def get_skill_term_by_key(session: AsyncSession, *, taxonomy_version_id, term_key: str) -> TaxonomyTerm | None:
    result = await session.execute(
        select(TaxonomyTerm).where(
            TaxonomyTerm.taxonomy_version_id == taxonomy_version_id, TaxonomyTerm.term_key == term_key
        )
    )
    return result.scalar_one_or_none()
