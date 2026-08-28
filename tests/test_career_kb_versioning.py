"""Matching V1 M3 -- versioning, immutability, provenance, provisional
state (Founder Review test items #19-24)."""

import pytest

from app.services.career_kb.seed import CAREER_VECTOR_VERSION, seed_alpha_career_matching_profiles
from app.services.career_kb.vectors import create_career_matching_profile
from app.services.knowledge.retrieval import get_career_by_code


async def test_repeated_import_identical(session):
    """#19."""
    profiles1 = await seed_alpha_career_matching_profiles(session)
    await session.commit()
    profiles2 = await seed_alpha_career_matching_profiles(session)
    await session.commit()

    ids1 = sorted(p.id for p in profiles1)
    ids2 = sorted(p.id for p in profiles2)
    assert ids1 == ids2


async def test_source_version_change_creates_versioned_profile(session):
    """#20."""
    await seed_alpha_career_matching_profiles(session)
    await session.commit()

    career = await get_career_by_code(session, "software_developer")
    original = await create_career_matching_profile(
        session, career_id=career.id, career_vector_version=CAREER_VECTOR_VERSION,
        matching_methodology_version="golden_test_v0.1", source_version="onet_30.3", mapping_version="mnp_onet_alpha_crosswalk_v0.1",
    )

    new_version = await create_career_matching_profile(
        session, career_id=career.id, career_vector_version=CAREER_VECTOR_VERSION,
        matching_methodology_version="golden_test_v0.1", source_version="onet_31.0",  # a hypothetical new O*NET release
        mapping_version="mnp_onet_alpha_crosswalk_v0.1",
    )
    await session.commit()

    assert new_version.id != original.id
    assert new_version.profile_version == original.profile_version + 1
    assert new_version.supersedes_id == original.id
    assert new_version.is_current is True


async def test_previous_profile_immutable(session):
    """#21."""
    await seed_alpha_career_matching_profiles(session)
    await session.commit()
    career = await get_career_by_code(session, "software_developer")

    from sqlalchemy import select
    from app.db.models_career_kb import CareerMatchingProfile

    original = (
        await session.execute(
            select(CareerMatchingProfile).where(
                CareerMatchingProfile.career_id == career.id, CareerMatchingProfile.is_current.is_(True)
            )
        )
    ).scalar_one()
    original_created_at = original.created_at
    original_source_version = original.source_version

    await create_career_matching_profile(
        session, career_id=career.id, career_vector_version=CAREER_VECTOR_VERSION,
        matching_methodology_version="golden_test_v0.1", source_version="onet_31.0", mapping_version="mnp_onet_alpha_crosswalk_v0.1",
    )
    await session.commit()

    await session.refresh(original)
    assert original.created_at.replace(tzinfo=None) == original_created_at.replace(tzinfo=None)
    assert original.source_version == original_source_version
    assert original.is_current is False  # superseded, but every other field untouched


async def test_one_current_matching_profile_per_career(session):
    """#22 -- DB-level partial unique index."""
    from app.db.models_career_kb import CareerMatchingProfile

    await seed_alpha_career_matching_profiles(session)
    await session.commit()
    career = await get_career_by_code(session, "software_developer")

    duplicate = CareerMatchingProfile(
        career_id=career.id, profile_version=999, career_vector_version="dup",
        matching_methodology_version="golden_test_v0.1", source_version="dup", mapping_version="dup",
        localization_version="dup", provisional=True, is_current=True,
    )
    session.add(duplicate)
    with pytest.raises(Exception):
        await session.flush()
    await session.rollback()


async def test_provenance_preserved(session):
    """#23."""
    await seed_alpha_career_matching_profiles(session)
    await session.commit()
    career = await get_career_by_code(session, "electrician")

    from app.services.career_kb.queries import get_career_matching_profile

    view = await get_career_matching_profile(session, career.id)
    assert view.source_version == "onet_30.3"
    assert view.mapping_version == "mnp_onet_alpha_crosswalk_v0.1"
    assert view.career_vector_version == CAREER_VECTOR_VERSION
    r_component = next(c for c in view.interests.components if c.scale_key == "R")
    assert r_component.source_system == "onet"
    assert r_component.source_element_id == "47-2111.00"


async def test_provisional_true_for_alpha(session):
    """#24."""
    await seed_alpha_career_matching_profiles(session)
    await session.commit()
    career = await get_career_by_code(session, "software_developer")

    from app.services.career_kb.queries import get_career_matching_profile

    view = await get_career_matching_profile(session, career.id)
    assert view.provisional is True  # unconditionally, for every Alpha career
