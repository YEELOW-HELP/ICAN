"""Stage 2 brief §9: minimal seed taxonomy, versioned, idempotent."""

from sqlalchemy import select

from app.db.models_profile import Taxonomy, TaxonomyTerm, TaxonomyVersion, TaxonomyVersionStatus
from app.services.profile.taxonomy import TAXONOMY_KEY, ensure_seed_taxonomy


async def test_ensure_seed_taxonomy_creates_active_version_with_terms(session_factory):
    async with session_factory() as session:
        version = await ensure_seed_taxonomy(session)

        assert version.status == TaxonomyVersionStatus.ACTIVE
        assert version.version == 1

        taxonomy = await session.get(Taxonomy, version.taxonomy_id)
        assert taxonomy.key == TAXONOMY_KEY

        terms = (await session.execute(select(TaxonomyTerm).where(TaxonomyTerm.taxonomy_version_id == version.id))).scalars().all()
        assert len(terms) > 10  # a real, if minimal, seed -- not a stub
        dimensions_covered = {term.dimension for term in terms}
        assert len(dimensions_covered) >= 8  # most of the 11 profile dimensions have at least one seed term


async def test_ensure_seed_taxonomy_is_idempotent(session_factory):
    async with session_factory() as session:
        first = await ensure_seed_taxonomy(session)
        second = await ensure_seed_taxonomy(session)

        assert first.id == second.id

        taxonomies = (await session.execute(select(Taxonomy))).scalars().all()
        versions = (await session.execute(select(TaxonomyVersion))).scalars().all()
        assert len(taxonomies) == 1
        assert len(versions) == 1

        terms_first_pass = (await session.execute(select(TaxonomyTerm))).scalars().all()
        await ensure_seed_taxonomy(session)
        terms_second_pass = (await session.execute(select(TaxonomyTerm))).scalars().all()
        assert len(terms_first_pass) == len(terms_second_pass)  # no duplicate terms on repeat calls
