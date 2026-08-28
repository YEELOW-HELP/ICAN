"""Official O*NET 30.3 NUMERIC source fixture (Matching V1 M4.5, Founder
Review "M4.5 GO", 2026-08-28) -- CURRENT_OFFICIAL data quality tier.

Unlike `onet_alpha_fixture.py` (M3, Holland-code approximation, retained
unchanged as `LEGACY_ENGINEERING_FALLBACK` -- see that module's docstring
and `app/services/career_kb/quality.py`), every number below was
extracted directly from the **official O*NET 30.3 database release**
(`db_30_3_text.zip`, downloaded from `https://www.onetcenter.org/dl_files/
database/db_30_3_text.zip` on 2026-08-28), not reconstructed, guessed, or
paraphrased from a rendered webpage. Three source files were used:

  "Career Interest Types.txt"   Scale ID `OI`  (Occupational Interests)
  "Work Styles.txt"             Scale ID `WI`  (Work Styles Impact)
  "Work Context.txt"            Scale ID `CX`  (Context, most elements)
                                 Scale ID `CT`  (Context — "Work Schedules"
                                 only; a DIFFERENT scale than the other
                                 Work Context elements, per the official
                                 `Scales Reference.txt` -- confirmed
                                 empirically, never assumed)

**Official scale ranges** (from `Scales Reference.txt`, verbatim):
  OI  1 to 7    (Occupational Interests)
  WI  -3 to 3   (Work Styles Impact -- signed: negative = detrimental to
                 performance in this occupation, positive = beneficial,
                 0 = neutral/irrelevant. This is NOT the retired 1-5
                 "Importance" scale -- confirmed empirically: "Work
                 Styles.txt" contains ONLY `DR`/`WI` scale IDs, never
                 `IM`, for O*NET 30.3.)
  CX  1 to 5    (Context)
  CT  1 to 3    (Context -- "Work Schedules" specifically)

**Real, disclosed finding from this pass:** the O*NET 30.3 Work Context
domain does NOT contain a "Structured Work" / "Unstructured Work" element
at all (confirmed by enumerating every element name in "Work Context.txt")
-- `MNP_SCALE_TO_ONET_MAPPING_V0.1.md` §B's claimed DERIVED source for
MNP's `structure_preference` scale does not exist in the current release.
No substitute was invented; `structure_preference` remains UNAVAILABLE in
this pass (Founder Review §5: "If a transformation is not defensible:
leave the component unavailable"). Flagged here for a future amendment to
that mapping document.

**Work Values:** no "Work Values" file exists anywhere in the O*NET 30.3
text database release at all (confirmed by listing every extracted file
name) -- not merely deprecated-but-present. Per Founder Review §7, Values
Fit remains INSUFFICIENT_DATA; nothing is populated here for that family.

**Primary-mapping rule** (Founder Review §3): where an MNP career
crosswalks to more than one O*NET-SOC code (only `software_developer`,
to Software Developers 15-1252.00 CONFIRMED + Web Developers 15-1254.00
PROVISIONAL), only the CONFIRMED primary code's numeric data is used here
-- the secondary PROVISIONAL mapping remains crosswalk provenance only,
never blended in. No confidence-weighted averaging is implemented in this
pass (no such rule is yet Founder-approved).

Two O*NET-SOC codes genuinely lack Work Context data in this release:
`13-1082.00` (Project Management Specialists) and `13-2051.00` (Financial
and Investment Analysts) -- both real O*NET occupations with populated
Interests/Work Styles, simply not yet incumbent/expert-rated for Work
Context. Left unavailable, not fabricated.

Licensing: O*NET 30.3 data is available under a Creative Commons
Attribution 4.0 International License, attributed to the O*NET 30.3
Database, U.S. Department of Labor, Employment and Training
Administration, National Center for O*NET Development.
"""

from __future__ import annotations

from dataclasses import dataclass, field

ONET_NUMERIC_SOURCE_VERSION = "onet_30.3_raw_numeric"
NUMERIC_MAPPING_VERSION = "mnp_onet_alpha_crosswalk_v0.2"
CAREER_VECTOR_VERSION_V2 = "career_vector_v0.2"

# Official scale ranges, Scales Reference.txt, verbatim.
SCALE_RANGES = {
    "OI": (1.0, 7.0),
    "WI": (-3.0, 3.0),
    "CX": (1.0, 5.0),
    "CT": (1.0, 3.0),
}

# RIASEC Content Model Element IDs (Career Interest Types.txt).
RIASEC_ELEMENT_IDS = {
    "R": "1.B.1.a", "I": "1.B.1.b", "A": "1.B.1.c", "S": "1.B.1.d", "E": "1.B.1.e", "C": "1.B.1.f",
}
_RIASEC_ELEMENT_NAMES = {
    "R": "Realistic", "I": "Investigative", "A": "Artistic", "S": "Social", "E": "Enterprising", "C": "Conventional",
}

# MNP Work Style scale_key -> (O*NET Element Name, Element ID). Only the
# DIRECT/DERIVED scales this fixture actually sources data for.
WORK_STYLE_ELEMENT_IDS = {
    "leadership": ("Leadership Orientation", "1.D.1.i"),
    "initiative": ("Initiative", "1.D.1.e"),
    "ambiguity_tolerance": ("Tolerance for Ambiguity", "1.D.1.d"),
    "collaboration_social": ("Social Orientation", "1.D.2.f"),  # composite input for `collaboration`
    "collaboration_cooperation": ("Cooperation", "1.D.2.d"),  # composite input for `collaboration`
}

# MNP Work Environment scale_key -> (O*NET Element Name, Element ID, Scale ID).
WORK_ENVIRONMENT_ELEMENT_IDS = {
    "collaboration_context": ("Work With or Contribute to a Work Group or Team", "4.C.1.b.1.e", "CX"),
    "customer_interaction_context": ("Deal With External Customers or the Public in General", "4.C.1.b.1.f", "CX"),
    "schedule_predictability": ("Work Schedules", "4.C.3.d.4", "CT"),
    "setting": ("Indoors, Environmentally Controlled", "4.C.2.a.1.a", "CX"),
    "physical_environment_standing": ("Spend Time Standing", "4.C.2.d.1.b", "CX"),  # composite input
    "physical_environment_walking": ("Spend Time Walking or Running", "4.C.2.d.1.d", "CX"),  # composite input
}


@dataclass(frozen=True)
class NumericSourceRecord:
    mnp_career_code: str
    primary_onet_soc_code: str | None  # None only for the UNMAPPED career
    riasec_oi: dict[str, float] = field(default_factory=dict)  # {"R": raw_1_to_7, ...}
    work_style_wi: dict[str, float] = field(default_factory=dict)  # element key -> raw -3..3
    work_context: dict[str, tuple[float, str]] = field(default_factory=dict)  # element key -> (raw, scale_id)


# Extracted verbatim from the official O*NET 30.3 text database
# ("Career Interest Types.txt", "Work Styles.txt", "Work Context.txt"),
# 2026-08-28. Primary O*NET-SOC code per MNP career per the primary-mapping
# rule above (matches `onet_alpha_fixture.py`'s CONFIRMED mapping in every
# case except none -- no PROVISIONAL-only primary was substituted).
NUMERIC_RECORDS: list[NumericSourceRecord] = [
    NumericSourceRecord("software_developer", "15-1252.00",
        {"R": 3.61, "I": 6.05, "A": 2.37, "S": 1.81, "E": 1.87, "C": 5.62},
        {"leadership": 1.13, "initiative": 1.59, "ambiguity_tolerance": 1.72, "collaboration_social": 0.86, "collaboration_cooperation": 1.20},
        {"collaboration_context": (4.56, "CX"), "customer_interaction_context": (1.93, "CX"), "schedule_predictability": (1.02, "CT"), "setting": (3.20, "CX"), "physical_environment_standing": (1.47, "CX"), "physical_environment_walking": (1.29, "CX")},
    ),
    NumericSourceRecord("it_support_specialist", "15-1232.00",
        {"R": 4.13, "I": 3.77, "A": 1.00, "S": 3.31, "E": 2.36, "C": 6.02},
        {"leadership": 0.25, "initiative": 1.26, "ambiguity_tolerance": 1.22, "collaboration_social": 1.74, "collaboration_cooperation": 1.99},
        {"collaboration_context": (4.07, "CX"), "customer_interaction_context": (2.01, "CX"), "schedule_predictability": (1.00, "CT"), "setting": (4.86, "CX"), "physical_environment_standing": (2.18, "CX"), "physical_environment_walking": (2.17, "CX")},
    ),
    NumericSourceRecord("registered_nurse", "29-1141.00",
        {"R": 3.46, "I": 4.71, "A": 1.34, "S": 5.57, "E": 2.38, "C": 4.75},
        {"leadership": 1.48, "initiative": 1.32, "ambiguity_tolerance": 1.41, "collaboration_social": 2.24, "collaboration_cooperation": 2.64},
        {"collaboration_context": (4.90, "CX"), "customer_interaction_context": (4.52, "CX"), "schedule_predictability": (1.13, "CT"), "setting": (4.56, "CX"), "physical_environment_standing": (3.01, "CX"), "physical_environment_walking": (3.17, "CX")},
    ),
    NumericSourceRecord("pharmacist", "29-1051.00",
        {"R": 2.82, "I": 5.67, "A": 1.48, "S": 4.88, "E": 2.62, "C": 4.56},
        {"leadership": 1.08, "initiative": 1.38, "ambiguity_tolerance": 0.33, "collaboration_social": 1.58, "collaboration_cooperation": 2.30},
        {"collaboration_context": (4.98, "CX"), "customer_interaction_context": (4.68, "CX"), "schedule_predictability": (1.03, "CT"), "setting": (5.00, "CX"), "physical_environment_standing": (4.36, "CX"), "physical_environment_walking": (2.50, "CX")},
    ),
    NumericSourceRecord("civil_engineer", "17-2051.00",
        {"R": 6.43, "I": 5.15, "A": 2.21, "S": 1.69, "E": 2.66, "C": 4.61},
        {"leadership": 2.01, "initiative": 1.59, "ambiguity_tolerance": 1.33, "collaboration_social": 0.86, "collaboration_cooperation": 1.44},
        {"collaboration_context": (4.38, "CX"), "customer_interaction_context": (3.57, "CX"), "schedule_predictability": (1.33, "CT"), "setting": (4.40, "CX"), "physical_environment_standing": (2.19, "CX"), "physical_environment_walking": (2.05, "CX")},
    ),
    NumericSourceRecord("mechanical_engineer", "17-2141.00",
        {"R": 6.39, "I": 5.12, "A": 2.02, "S": 1.22, "E": 1.97, "C": 4.83},
        {"leadership": 1.06, "initiative": 1.44, "ambiguity_tolerance": 1.24, "collaboration_social": 0.61, "collaboration_cooperation": 1.03},
        {"collaboration_context": (4.40, "CX"), "customer_interaction_context": (3.16, "CX"), "schedule_predictability": (1.12, "CT"), "setting": (4.57, "CX"), "physical_environment_standing": (2.40, "CX"), "physical_environment_walking": (2.24, "CX")},
    ),
    NumericSourceRecord("truck_driver", "53-3032.00",
        {"R": 7.00, "I": 1.92, "A": 1.00, "S": 1.33, "E": 1.30, "C": 4.10},
        {"leadership": -0.28, "initiative": 0.74, "ambiguity_tolerance": 0.47, "collaboration_social": -0.14, "collaboration_cooperation": 0.71},
        {"collaboration_context": (3.60, "CX"), "customer_interaction_context": (3.75, "CX"), "schedule_predictability": (1.63, "CT"), "setting": (1.96, "CX"), "physical_environment_standing": (2.21, "CX"), "physical_environment_walking": (2.18, "CX")},
    ),
    NumericSourceRecord("logistics_coordinator", "13-1081.00",
        {"R": 2.35, "I": 3.81, "A": 1.10, "S": 2.33, "E": 5.02, "C": 5.44},
        {"leadership": 1.95, "initiative": 1.75, "ambiguity_tolerance": 1.29, "collaboration_social": 1.52, "collaboration_cooperation": 2.10},
        {"collaboration_context": (4.58, "CX"), "customer_interaction_context": (3.96, "CX"), "schedule_predictability": (1.17, "CT"), "setting": (4.08, "CX"), "physical_environment_standing": (2.25, "CX"), "physical_environment_walking": (1.92, "CX")},
    ),
    NumericSourceRecord("electrician", "47-2111.00",
        {"R": 7.00, "I": 2.70, "A": 1.24, "S": 1.32, "E": 1.81, "C": 4.09},
        {"leadership": 0.83, "initiative": 1.00, "ambiguity_tolerance": 0.00, "collaboration_social": 0.38, "collaboration_cooperation": 1.00},
        {"collaboration_context": (4.54, "CX"), "customer_interaction_context": (3.84, "CX"), "schedule_predictability": (1.33, "CT"), "setting": (3.27, "CX"), "physical_environment_standing": (4.55, "CX"), "physical_environment_walking": (4.23, "CX")},
    ),
    NumericSourceRecord("plumber", "47-2152.00",
        {"R": 7.00, "I": 2.20, "A": 1.00, "S": 1.16, "E": 1.00, "C": 3.72},
        {"leadership": 0.36, "initiative": 0.80, "ambiguity_tolerance": -0.11, "collaboration_social": 0.25, "collaboration_cooperation": 0.82},
        {"collaboration_context": (4.05, "CX"), "customer_interaction_context": (3.04, "CX"), "schedule_predictability": (1.39, "CT"), "setting": (3.11, "CX"), "physical_environment_standing": (4.69, "CX"), "physical_environment_walking": (3.86, "CX")},
    ),
    NumericSourceRecord("sales_manager", "11-2022.00",
        {"R": 1.49, "I": 1.67, "A": 1.36, "S": 3.37, "E": 7.00, "C": 5.53},
        {"leadership": 2.71, "initiative": 2.07, "ambiguity_tolerance": 1.51, "collaboration_social": 2.54, "collaboration_cooperation": 1.77},
        {"collaboration_context": (4.65, "CX"), "customer_interaction_context": (4.71, "CX"), "schedule_predictability": (1.38, "CT"), "setting": (4.45, "CX"), "physical_environment_standing": (2.40, "CX"), "physical_environment_walking": (1.85, "CX")},
    ),
    NumericSourceRecord("retail_sales_associate", "41-2031.00",
        {"R": 3.20, "I": 1.00, "A": 1.98, "S": 2.96, "E": 6.13, "C": 5.17},
        {"leadership": 0.81, "initiative": 1.53, "ambiguity_tolerance": 0.64, "collaboration_social": 2.60, "collaboration_cooperation": 1.88},
        {"collaboration_context": (4.35, "CX"), "customer_interaction_context": (4.60, "CX"), "schedule_predictability": (1.15, "CT"), "setting": (4.16, "CX"), "physical_environment_standing": (4.07, "CX"), "physical_environment_walking": (3.76, "CX")},
    ),
    NumericSourceRecord("customer_service_representative", "43-4051.00",
        {"R": 1.97, "I": 1.63, "A": 1.00, "S": 3.77, "E": 5.08, "C": 6.32},
        {"leadership": -0.38, "initiative": 0.55, "ambiguity_tolerance": 0.27, "collaboration_social": 2.26, "collaboration_cooperation": 2.34},
        {"collaboration_context": (4.03, "CX"), "customer_interaction_context": (4.79, "CX"), "schedule_predictability": (1.12, "CT"), "setting": (4.83, "CX"), "physical_environment_standing": (3.23, "CX"), "physical_environment_walking": (1.94, "CX")},
    ),
    NumericSourceRecord("call_center_operator", "43-4051.00",  # only mapping, PROVISIONAL -- same source row as CSR
        {"R": 1.97, "I": 1.63, "A": 1.00, "S": 3.77, "E": 5.08, "C": 6.32},
        {"leadership": -0.38, "initiative": 0.55, "ambiguity_tolerance": 0.27, "collaboration_social": 2.26, "collaboration_cooperation": 2.34},
        {"collaboration_context": (4.03, "CX"), "customer_interaction_context": (4.79, "CX"), "schedule_predictability": (1.12, "CT"), "setting": (4.83, "CX"), "physical_environment_standing": (3.23, "CX"), "physical_environment_walking": (1.94, "CX")},
    ),
    NumericSourceRecord("operations_manager", "11-1021.00",
        {"R": 2.20, "I": 2.37, "A": 1.29, "S": 3.38, "E": 7.00, "C": 5.34},
        {"leadership": 2.93, "initiative": 2.22, "ambiguity_tolerance": 1.64, "collaboration_social": 1.97, "collaboration_cooperation": 1.84},
        {"collaboration_context": (4.62, "CX"), "customer_interaction_context": (4.49, "CX"), "schedule_predictability": (1.16, "CT"), "setting": (4.39, "CX"), "physical_environment_standing": (2.90, "CX"), "physical_environment_walking": (2.53, "CX")},
    ),
    NumericSourceRecord("project_manager", "13-1082.00",
        {"R": 1.48, "I": 2.75, "A": 1.57, "S": 3.32, "E": 6.30, "C": 5.55},
        {"leadership": 2.55, "initiative": 2.00, "ambiguity_tolerance": 1.78, "collaboration_social": 2.11, "collaboration_cooperation": 2.30},
        {},  # no Work Context data exists for 13-1082.00 in O*NET 30.3
    ),
    NumericSourceRecord("accountant", "13-2011.00",
        {"R": 1.14, "I": 3.57, "A": 1.08, "S": 2.13, "E": 3.87, "C": 7.00},
        {"leadership": 0.83, "initiative": 1.00, "ambiguity_tolerance": -0.15, "collaboration_social": 0.50, "collaboration_cooperation": 0.73},
        {"collaboration_context": (4.21, "CX"), "customer_interaction_context": (3.77, "CX"), "schedule_predictability": (1.27, "CT"), "setting": (4.63, "CX"), "physical_environment_standing": (1.80, "CX"), "physical_environment_walking": (1.56, "CX")},
    ),
    NumericSourceRecord("financial_analyst", "13-2051.00",
        {"R": 1.00, "I": 5.06, "A": 1.78, "S": 2.25, "E": 5.09, "C": 5.54},
        {"leadership": 1.00, "initiative": 1.50, "ambiguity_tolerance": 1.83, "collaboration_social": 1.43, "collaboration_cooperation": 1.00},
        {},  # no Work Context data exists for 13-2051.00 in O*NET 30.3
    ),
    NumericSourceRecord("school_teacher", "25-2031.00",
        {"R": 2.73, "I": 3.19, "A": 3.77, "S": 7.00, "E": 2.90, "C": 3.61},
        {"leadership": 1.61, "initiative": 1.53, "ambiguity_tolerance": 1.56, "collaboration_social": 2.33, "collaboration_cooperation": 2.30},
        {"collaboration_context": (4.24, "CX"), "customer_interaction_context": (3.34, "CX"), "schedule_predictability": (1.16, "CT"), "setting": (4.56, "CX"), "physical_environment_standing": (3.28, "CX"), "physical_environment_walking": (2.58, "CX")},
    ),
    NumericSourceRecord("corporate_trainer", "13-1151.00",
        {"R": 2.03, "I": 4.03, "A": 3.19, "S": 5.64, "E": 3.68, "C": 3.76},
        {"leadership": 1.81, "initiative": 1.93, "ambiguity_tolerance": 1.33, "collaboration_social": 2.36, "collaboration_cooperation": 2.30},
        {"collaboration_context": (4.27, "CX"), "customer_interaction_context": (3.13, "CX"), "schedule_predictability": (1.26, "CT"), "setting": (4.17, "CX"), "physical_environment_standing": (2.65, "CX"), "physical_environment_walking": (1.78, "CX")},
    ),
    NumericSourceRecord("graphic_designer", "27-1024.00",
        {"R": 3.38, "I": 2.86, "A": 7.00, "S": 2.16, "E": 3.43, "C": 3.92},
        {"leadership": 0.32, "initiative": 1.18, "ambiguity_tolerance": 1.33, "collaboration_social": 0.88, "collaboration_cooperation": 1.14},
        {"collaboration_context": (4.44, "CX"), "customer_interaction_context": (3.05, "CX"), "schedule_predictability": (1.35, "CT"), "setting": (4.32, "CX"), "physical_environment_standing": (1.89, "CX"), "physical_environment_walking": (1.47, "CX")},
    ),
    NumericSourceRecord("video_editor", "27-4032.00",
        {"R": 3.14, "I": 1.91, "A": 5.61, "S": 1.96, "E": 3.08, "C": 3.75},
        {"leadership": 0.16, "initiative": 1.18, "ambiguity_tolerance": 1.49, "collaboration_social": 0.72, "collaboration_cooperation": 1.53},
        {"collaboration_context": (4.50, "CX"), "customer_interaction_context": (3.00, "CX"), "schedule_predictability": (1.03, "CT"), "setting": (4.98, "CX"), "physical_environment_standing": (1.84, "CX"), "physical_environment_walking": (1.70, "CX")},
    ),
    NumericSourceRecord("social_worker", "21-1021.00",
        {"R": 1.70, "I": 3.32, "A": 2.90, "S": 6.85, "E": 2.94, "C": 3.57},
        {"leadership": 1.00, "initiative": 1.89, "ambiguity_tolerance": 1.56, "collaboration_social": 2.38, "collaboration_cooperation": 3.00},
        {"collaboration_context": (4.77, "CX"), "customer_interaction_context": (4.27, "CX"), "schedule_predictability": (1.34, "CT"), "setting": (4.20, "CX"), "physical_environment_standing": (2.43, "CX"), "physical_environment_walking": (2.12, "CX")},
    ),
    NumericSourceRecord("community_outreach_coordinator", None, {}, {}, {}),  # UNMAPPED, per M3 -- unchanged
]

_BY_CODE = {r.mnp_career_code: r for r in NUMERIC_RECORDS}


def load_numeric_source() -> list[NumericSourceRecord]:
    """The complete offline O*NET 30.3 numeric fixture -- no network
    access, no randomness, same result every call."""

    return list(NUMERIC_RECORDS)


def get_numeric_source(mnp_career_code: str) -> NumericSourceRecord | None:
    return _BY_CODE.get(mnp_career_code)
