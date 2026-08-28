"""Matching V1 M3 -- external crosswalk (Founder Review test items
#5-7)."""

from app.db.models_career_kb import ExternalMappingStatus, ExternalSourceSystem
from app.services.career_kb.crosswalk import get_external_mappings
from app.services.career_kb.seed import seed_alpha_career_matching_profiles
from app.services.knowledge.retrieval import get_career_by_code


async def test_onet_code_stored_as_external_mapping(session):
    """#5."""
    await seed_alpha_career_matching_profiles(session)
    await session.commit()

    career = await get_career_by_code(session, "registered_nurse")
    mappings = await get_external_mappings(session, career.id, source_system=ExternalSourceSystem.ONET)
    assert len(mappings) == 1
    assert mappings[0].external_code == "29-1141.00"
    assert mappings[0].mapping_status == ExternalMappingStatus.CONFIRMED


async def test_many_to_many_mapping_supported(session):
    """#6 -- software_developer carries TWO O*NET-SOC mappings (a genuine
    many-to-one crosswalk case)."""
    await seed_alpha_career_matching_profiles(session)
    await session.commit()

    career = await get_career_by_code(session, "software_developer")
    mappings = await get_external_mappings(session, career.id, source_system=ExternalSourceSystem.ONET)
    codes = {m.external_code for m in mappings}
    assert codes == {"15-1252.00", "15-1254.00"}

    # and the "many MNP careers -> one O*NET occupation" direction:
    csr = await get_career_by_code(session, "customer_service_representative")
    call_center = await get_career_by_code(session, "call_center_operator")
    csr_mappings = await get_external_mappings(session, csr.id, source_system=ExternalSourceSystem.ONET)
    call_center_mappings = await get_external_mappings(session, call_center.id, source_system=ExternalSourceSystem.ONET)
    assert csr_mappings[0].external_code == call_center_mappings[0].external_code == "43-4051.00"


async def test_unmapped_supported_explicitly(session):
    """#7."""
    await seed_alpha_career_matching_profiles(session)
    await session.commit()

    career = await get_career_by_code(session, "community_outreach_coordinator")
    mappings = await get_external_mappings(session, career.id, source_system=ExternalSourceSystem.ONET)
    assert len(mappings) == 1
    assert mappings[0].mapping_status == ExternalMappingStatus.UNMAPPED
    assert mappings[0].external_code is None  # a deliberate marker, not an unpopulated field
