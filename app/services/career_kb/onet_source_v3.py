"""Production O*NET numeric source (Matching V1 M4.6 — "Career Vector
Data: Production O*NET Import").

Replaces the hand-typed 24-career `onet_30_3_numeric_fixture.py` (M4.5,
retained unchanged as history) with a **generated, committed** artifact
covering every O*NET-SOC code an MNP career maps to. The artifact
(`onet_source_v3.json`, next to this file) is produced offline by
`scripts/onet_import/` from the official O*NET bulk text database and
checked in so CI never touches the network (Founder Review "M3" §18).

Version split (Founder decision, DATA-002 session):
  * RIASEC (OI), Work Style (WI), Work Context (CX/CT)  ->  O*NET **31.0**
  * Work Values (EX)                                     ->  O*NET **30.2**
    (the last release that still shipped `Work Values.txt`; removed 30.3+),
    and only the 3 DIRECT-mappable MNP keys
    (`independence_value` <- Independence, `impact_helping` <- Relationships,
     `recognition_status` <- Recognition), per
    `MNP_SCALE_TO_ONET_MAPPING_V0.1.md` §C. The other 5 MNP work-values
    keys have no O*NET counterpart and stay unsourced (MNP curation).

Zero-AI: every value here traces to a real O*NET database row (the
`scripts/onet_import` pipeline is a faithful filtered transcription). No
value is AI-reconstructed; a scale genuinely absent for an occupation is
simply missing from the dict, never defaulted.

Licensing / attribution: CC BY 4.0, O*NET Database (v31.0 + v30.2), U.S.
Department of Labor / ETA / National Center for O*NET Development. See
`docs/engineering/27_MATCHING_V1_M4_6_ONET_PRODUCTION_IMPORT.md`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path

# --- version stamps (persisted on CareerMatchingProfile / -Component) -------
ONET_SOURCE_VERSION = "onet_31.0"
CAREER_VECTOR_VERSION_V3 = "career_vector_v0.3"
NUMERIC_MAPPING_VERSION_V3 = "mnp_onet_crosswalk_v0.3"

OI_TRANSFORMATION_VERSION = "onet_oi_numeric_v0.1"          # reused from M4.5 vectors.py
WI_TRANSFORMATION_VERSION = "onet_wi_numeric_v0.1"          # reused from M4.5 vectors.py
CX_TRANSFORMATION_VERSION = "onet_cx_numeric_v0.1"          # reused from M4.5 vectors.py
CT_TRANSFORMATION_VERSION = "onet_ct_numeric_v0.1"          # reused from M4.5 vectors.py
EX_TRANSFORMATION_VERSION = "legacy_onet_work_values_30.2_v0.1"  # NEW in M4.6

WORK_VALUES_SOURCE_LABEL = "onet_30.2"

_ARTIFACT_PATH = Path(__file__).with_name("onet_source_v3.json")

# O*NET element IDs, for CareerMatchingComponent.source_element_id provenance.
RIASEC_ELEMENT_IDS = {
    "R": "1.B.1.a", "I": "1.B.1.b", "A": "1.B.1.c",
    "S": "1.B.1.d", "E": "1.B.1.e", "C": "1.B.1.f",
}
RIASEC_ELEMENT_NAMES = {
    "R": "Realistic", "I": "Investigative", "A": "Artistic",
    "S": "Social", "E": "Enterprising", "C": "Conventional",
}
# raw work-style key -> (O*NET element name, element ID)
WORK_STYLE_ELEMENT_IDS = {
    "leadership": ("Leadership Orientation", "1.D.1.i"),
    "initiative": ("Initiative", "1.D.1.e"),
    "ambiguity_tolerance": ("Tolerance for Ambiguity", "1.D.1.d"),
    "collaboration_social": ("Social Orientation", "1.D.2.f"),
    "collaboration_cooperation": ("Cooperation", "1.D.2.d"),
}
# raw work-context key -> (O*NET element name, element ID, scale ID)
WORK_CONTEXT_ELEMENT_IDS = {
    "collaboration_context": ("Work With or Contribute to a Work Group or Team", "4.C.1.b.1.e", "CX"),
    "customer_interaction_context": ("Deal With External Customers or the Public in General", "4.C.1.b.1.f", "CX"),
    "schedule_predictability": ("Work Schedules", "4.C.3.d.4", "CT"),
    "setting": ("Indoors, Environmentally Controlled", "4.C.2.a.1.a", "CX"),
    "physical_environment_standing": ("Spend Time Standing", "4.C.2.d.1.b", "CX"),
    "physical_environment_walking": ("Spend Time Walking or Running", "4.C.2.d.1.d", "CX"),
}
# MNP work-values key -> (O*NET element name, element ID)  [30.2]
WORK_VALUES_ELEMENT_IDS = {
    "independence_value": ("Independence", "1.B.2.f"),
    "impact_helping": ("Relationships", "1.B.2.d"),
    "recognition_status": ("Recognition", "1.B.2.c"),
}


@dataclass(frozen=True)
class OnetSocData:
    soc: str
    title: str
    job_zone: int | None
    riasec_oi: dict[str, float]       # letter -> raw 1..7
    work_style_wi: dict[str, float]   # raw key -> raw -3..3
    work_context: dict[str, float]    # raw key -> raw (CX 1..5 or CT 1..3)
    work_values_ex: dict[str, float]  # MNP key -> raw 1..7 (30.2)


@cache
def _load() -> dict:
    return json.loads(_ARTIFACT_PATH.read_text(encoding="utf-8"))


def artifact_meta() -> dict:
    return dict(_load()["_meta"])


@cache
def _index() -> dict[str, OnetSocData]:
    out: dict[str, OnetSocData] = {}
    for soc, rec in _load()["occupations"].items():
        out[soc] = OnetSocData(
            soc=soc,
            title=rec["title"],
            job_zone=rec.get("job_zone"),
            riasec_oi=dict(rec.get("riasec_oi", {})),
            work_style_wi=dict(rec.get("work_style_wi", {})),
            work_context=dict(rec.get("work_context", {})),
            work_values_ex=dict(rec.get("work_values_ex", {})),
        )
    return out


def get_onet_data(soc_code: str) -> OnetSocData | None:
    """The numeric source for one O*NET-SOC code, or None if that code is
    not in the scoped artifact (regenerate the artifact after adding a
    CareerExternalMapping to a new code)."""
    return _index().get(soc_code)


def all_soc_codes() -> list[str]:
    return sorted(_index())
