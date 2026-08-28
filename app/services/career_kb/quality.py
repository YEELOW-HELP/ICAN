"""Career-vector source-quality classification (Matching V1 M4.5, Founder
Review §13). Read-only, derived entirely from EXISTING metadata fields
already on `CareerMatchingComponent`/`CareerExternalMapping`
(`transformation_version`, `provisional`, `source_system`, and the
crosswalk's own `mapping_status`) -- no schema change, no new persisted
column, per Founder Review's explicit "prefer metadata/versioned source
records over a large redesign."
"""

from __future__ import annotations

CURRENT_OFFICIAL = "current_official"
LEGACY_SOURCE = "legacy_source"
MNP_DERIVED = "mnp_derived"
PROVISIONAL = "provisional"
UNMAPPED = "unmapped"

# transformation_version prefixes that indicate a direct rescale of an
# official, currently-published O*NET numeric scale (M4.5).
_CURRENT_OFFICIAL_PREFIXES = (
    "onet_oi_numeric_",
    "onet_wi_numeric_",
    "onet_cx_numeric_",
    "onet_ct_numeric_",
)
# transformation_version prefixes that indicate the M3 engineering
# fixture (Holland-code approximation / explicit-signal proxy) -- kept as
# LEGACY_ENGINEERING_FALLBACK, never silently reclassified as current.
_LEGACY_PREFIXES = (
    "onet_holland_to_riasec_",
    "onet_explicit_style_signal_",
)


def classify_component_quality(*, transformation_version: str, provisional: bool) -> str:
    """One `CareerMatchingComponent` row's source-quality tier. A
    provisional CURRENT_OFFICIAL value (e.g. a DERIVED scale sourced from
    official data but not yet reviewed) is still reported as
    CURRENT_OFFICIAL for its SOURCE tier -- `provisional` is a separate,
    already-queryable dimension (review status), not conflated here."""

    if any(transformation_version.startswith(p) for p in _CURRENT_OFFICIAL_PREFIXES):
        return CURRENT_OFFICIAL
    if any(transformation_version.startswith(p) for p in _LEGACY_PREFIXES):
        return LEGACY_SOURCE
    return MNP_DERIVED


def classify_mapping_quality(*, mapping_status: str) -> str:
    """One `CareerExternalMapping` row's quality tier, from its own
    `mapping_status` -- UNMAPPED and PROVISIONAL pass through directly;
    CONFIRMED is reported as CURRENT_OFFICIAL since every Alpha crosswalk
    is sourced from the current O*NET 30.3 taxonomy; REJECTED has no
    quality tier of its own (it contributes nothing live)."""

    if mapping_status == "unmapped":
        return UNMAPPED
    if mapping_status == "provisional":
        return PROVISIONAL
    if mapping_status == "confirmed":
        return CURRENT_OFFICIAL
    return MNP_DERIVED
