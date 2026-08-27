"""MDR-2 / Founder decision B: the legacy ProfileClaim -> canonical MNP
adapter. Read-only, versioned, preserves the legacy dimension, emits
MAPPED / UNMAPPED / NEEDS_CLARIFICATION, never invents a claim.
"""

from app.db.models_profile import ClaimStatus, ProfileDimension
from app.services.direction.dimension_mapping import (
    DIMENSION_MAPPING_VERSION,
    MappingStatus,
    map_claim,
    map_claims,
)
from app.services.direction.dimensions import CanonicalDimension
from tests.direction_test_helpers import fake_claim


def test_direct_dimension_mappings():
    cases = {
        ProfileDimension.INTEREST: CanonicalDimension.INTERESTS,
        ProfileDimension.STRENGTH: CanonicalDimension.STRENGTHS,
        ProfileDimension.SKILL: CanonicalDimension.SKILLS,
        ProfileDimension.VALUE: CanonicalDimension.VALUES,
        ProfileDimension.MOTIVATION: CanonicalDimension.MOTIVATION,
        ProfileDimension.GOAL: CanonicalDimension.GOALS,
        ProfileDimension.EXPERIENCE: CanonicalDimension.EXPERIENCE,
        ProfileDimension.CONSTRAINT: CanonicalDimension.CONSTRAINTS,
    }
    for legacy, canonical in cases.items():
        mc = map_claim(fake_claim(legacy))
        assert mc.status is MappingStatus.MAPPED
        assert mc.canonical_dimension is canonical
        assert mc.legacy_dimension == legacy.value  # original preserved
        assert mc.mapping_version == DIMENSION_MAPPING_VERSION


def test_work_preference_term_specific_and_ambiguous_fallback():
    remote = map_claim(fake_claim(ProfileDimension.WORK_PREFERENCE, term_key="remote_work"))
    assert remote.canonical_dimension is CanonicalDimension.WORK_ENVIRONMENT
    assert remote.canonical_subdimension == "setting"

    structured = map_claim(fake_claim(ProfileDimension.WORK_PREFERENCE, term_key="structured_environment"))
    assert structured.canonical_dimension is CanonicalDimension.WORK_STYLE

    ambiguous = map_claim(fake_claim(ProfileDimension.WORK_PREFERENCE, term_key="something_new"))
    assert ambiguous.status is MappingStatus.NEEDS_CLARIFICATION
    assert ambiguous.canonical_dimension is None


def test_trait_adaptability_maps_but_other_traits_need_clarification():
    adapt = map_claim(fake_claim(ProfileDimension.TRAIT, term_key="adaptability"))
    assert adapt.canonical_dimension is CanonicalDimension.CAREER_ADAPTABILITY

    other = map_claim(fake_claim(ProfileDimension.TRAIT, term_key="extraversion"))
    assert other.status is MappingStatus.NEEDS_CLARIFICATION


def test_contextual_factor_family_maps_to_constraints_others_unmapped():
    fam = map_claim(fake_claim(ProfileDimension.CONTEXTUAL_FACTOR, term_key="family_responsibilities"))
    assert fam.canonical_dimension is CanonicalDimension.CONSTRAINTS
    assert fam.canonical_subdimension == "family_logistics"

    other = map_claim(fake_claim(ProfileDimension.CONTEXTUAL_FACTOR, term_key="language_proficiency"))
    assert other.status is MappingStatus.UNMAPPED
    assert other.canonical_dimension is None


def test_adapter_carries_claim_metadata_without_modifying_the_source():
    claim = fake_claim(
        ProfileDimension.SKILL,
        term_key="programming",
        normalized_value="writes production Python",
        status=ClaimStatus.HYPOTHESIS,
        confidence=0.42,
    )
    original_value = claim.normalized_value
    mc = map_claim(claim)
    assert mc.claim_status == "hypothesis"
    assert mc.claim_confidence == 0.42
    assert mc.normalized_value == "writes production Python"
    assert mc.source_claim_id == claim.id
    # the source claim object is untouched
    assert claim.normalized_value == original_value
    assert claim.status is ClaimStatus.HYPOTHESIS


def test_map_claims_is_one_to_one_never_invents():
    claims = [
        fake_claim(ProfileDimension.INTEREST),
        fake_claim(ProfileDimension.CONTEXTUAL_FACTOR, term_key="unknown_thing"),
    ]
    out = map_claims(claims)
    assert len(out) == 2  # exactly one result per input, nothing added
