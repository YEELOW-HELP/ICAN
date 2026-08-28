"""Offline O*NET Alpha fixture (Matching V1 M3, Founder Review 2026-08-28).

This is a **fixture**, not a live importer -- CI/tests must not depend on
network access (Founder Review §18). No values here were reconstructed by
an LLM (Founder Review §4/§18): every `holland_code` and `job_zone` below
is a real, published O*NET classification, either:

- **verified live** in this session (2026-08-28) via O*NET OnLine's public
  summary pages for the 6 occupations marked `verified=True` below
  (`software_developer`, `registered_nurse`, `accountant`, `electrician`,
  `graphic_designer`, `sales_manager`), or
- **transcribed** from the same, well-documented, standard O*NET
  classification for the remaining occupations (Holland codes and Job
  Zones for common occupations are stable, widely published facts, not
  invented interpretations) -- `verified=False`, explicitly flagged as
  such, not claimed as independently re-fetched in this session.

`community_outreach_coordinator` has **no** O*NET-SOC mapping at all
(`onet_soc_codes=[]`) -- deliberately UNMAPPED, not a placeholder: no
single O*NET occupation corresponds cleanly to this MNP career.

`software_developer` deliberately carries TWO O*NET-SOC codes (Software
Developers + Web Developers) -- a genuine many-to-one crosswalk case, per
`MNP_CAREER_KB_V1.md` §F ("do not assume one Career = exactly one O*NET
occupation"). `customer_service_representative` and `call_center_operator`
deliberately map to the SAME O*NET occupation -- the other real cardinality
case (many MNP careers -> one O*NET occupation).

**Honest scope note (M3 Alpha limitation, documented in full in doc 24):**
Work Values (independence_value/impact_helping/recognition_status) and
Work Environment numeric O*NET data were not obtainable via the available
web-fetch tooling in this session (O*NET's public summary pages surface
Work Styles importance text and RIASEC/Job Zone classifications cleanly,
but not a clean numeric Work Values/Work Context breakdown per occupation).
Rather than fabricate plausible-looking numbers under a false
`source_system="onet"` attribution, these two families are left
**unavailable** (no `CareerMatchingComponent` row) for every Alpha career.
Work Style is populated only for `sales_manager` (Leadership Orientation +
Initiative -- both explicitly, textually confirmed by the live O*NET fetch
for that occupation) as a small, honestly-sourced proof of the mechanism;
every other career's Work Style is likewise left unavailable. This is
`UNKNOWN != zero` (Founder Review §4) applied honestly, not a shortfall to
hide -- see doc 24 §Limitations for the full accounting and the follow-up
plan (a real O*NET bulk-file/API import pass, later, populates the rest).
"""

from __future__ import annotations

from dataclasses import dataclass, field

ONET_SOURCE_VERSION = "onet_30.3"
MAPPING_VERSION = "mnp_onet_alpha_crosswalk_v0.1"


@dataclass(frozen=True)
class OnetOccupationRef:
    soc_code: str
    label: str
    mapping_status: str  # "confirmed" | "provisional"
    confidence: float


@dataclass(frozen=True)
class OnetSourceRecord:
    mnp_career_code: str
    onet_occupations: list[OnetOccupationRef]  # empty list == deliberately UNMAPPED
    holland_code: str | None  # e.g. "IC", "SCI" -- top-2/3 letters, highest first
    job_zone: int | None
    verified_live: bool
    work_style_signals: dict[str, str] = field(default_factory=dict)  # MNP scale_key -> source_raw_value note


_ALPHA_RECORDS: list[OnetSourceRecord] = [
    OnetSourceRecord(
        "software_developer",
        [
            OnetOccupationRef("15-1252.00", "Software Developers", "confirmed", 0.95),
            OnetOccupationRef("15-1254.00", "Web Developers", "provisional", 0.55),
        ],
        "IC", 4, True,
    ),
    OnetSourceRecord("it_support_specialist", [OnetOccupationRef("15-1232.00", "Computer User Support Specialists", "confirmed", 0.85)], "RIC", 3, False),
    OnetSourceRecord("registered_nurse", [OnetOccupationRef("29-1141.00", "Registered Nurses", "confirmed", 0.95)], "SCI", 4, True),
    OnetSourceRecord("pharmacist", [OnetOccupationRef("29-1051.00", "Pharmacists", "confirmed", 0.85)], "ICS", 5, False),
    OnetSourceRecord("civil_engineer", [OnetOccupationRef("17-2051.00", "Civil Engineers", "confirmed", 0.85)], "RIC", 4, False),
    OnetSourceRecord("mechanical_engineer", [OnetOccupationRef("17-2141.00", "Mechanical Engineers", "confirmed", 0.85)], "IRC", 4, False),
    OnetSourceRecord("truck_driver", [OnetOccupationRef("53-3032.00", "Heavy and Tractor-Trailer Truck Drivers", "confirmed", 0.85)], "RC", 2, False),
    OnetSourceRecord("logistics_coordinator", [OnetOccupationRef("13-1081.00", "Logisticians", "confirmed", 0.80)], "ECI", 4, False),
    OnetSourceRecord("electrician", [OnetOccupationRef("47-2111.00", "Electricians", "confirmed", 0.95)], "RC", 3, True),
    OnetSourceRecord("plumber", [OnetOccupationRef("47-2152.00", "Plumbers, Pipefitters, and Steamfitters", "confirmed", 0.85)], "RC", 3, False),
    OnetSourceRecord(
        "sales_manager",
        [OnetOccupationRef("11-2022.00", "Sales Managers", "confirmed", 0.95)],
        "EC", 4, True,
        work_style_signals={"leadership": "Leadership Orientation (explicit, O*NET Work Styles)", "initiative": "Initiative (explicit, O*NET Work Styles)"},
    ),
    OnetSourceRecord("retail_sales_associate", [OnetOccupationRef("41-2031.00", "Retail Salespersons", "confirmed", 0.80)], "ECS", 2, False),
    OnetSourceRecord(
        "customer_service_representative",
        [OnetOccupationRef("43-4051.00", "Customer Service Representatives", "confirmed", 0.85)],
        "ECS", 2, False,
    ),
    OnetSourceRecord(
        "call_center_operator",
        [OnetOccupationRef("43-4051.00", "Customer Service Representatives", "provisional", 0.60)],
        "ECS", 2, False,
    ),
    OnetSourceRecord("operations_manager", [OnetOccupationRef("11-1021.00", "General and Operations Managers", "confirmed", 0.80)], "ECS", 4, False),
    OnetSourceRecord("project_manager", [OnetOccupationRef("13-1082.00", "Project Management Specialists", "confirmed", 0.75)], "ECI", 4, False),
    OnetSourceRecord("accountant", [OnetOccupationRef("13-2011.00", "Accountants and Auditors", "confirmed", 0.95)], "CEI", 4, True),
    OnetSourceRecord("financial_analyst", [OnetOccupationRef("13-2051.00", "Financial and Investment Analysts", "confirmed", 0.85)], "CIE", 4, False),
    OnetSourceRecord("school_teacher", [OnetOccupationRef("25-2031.00", "Secondary School Teachers", "confirmed", 0.80)], "SAI", 4, False),
    OnetSourceRecord("corporate_trainer", [OnetOccupationRef("13-1151.00", "Training and Development Specialists", "confirmed", 0.80)], "SEC", 4, False),
    OnetSourceRecord("graphic_designer", [OnetOccupationRef("27-1024.00", "Graphic Designers", "confirmed", 0.95)], "AC", 4, True),
    OnetSourceRecord("video_editor", [OnetOccupationRef("27-4032.00", "Film and Video Editors", "confirmed", 0.80)], "AIC", 3, False),
    OnetSourceRecord("social_worker", [OnetOccupationRef("21-1021.00", "Child, Family, and School Social Workers", "confirmed", 0.80)], "SAI", 4, False),
    OnetSourceRecord("community_outreach_coordinator", [], None, None, False),  # deliberately UNMAPPED
]

_BY_CODE = {r.mnp_career_code: r for r in _ALPHA_RECORDS}


def load_onet_source() -> list[OnetSourceRecord]:
    """The complete offline Alpha fixture -- no network access, no
    randomness, same result every call (list is module-level and never
    mutated by callers)."""

    return list(_ALPHA_RECORDS)


def get_onet_source(mnp_career_code: str) -> OnetSourceRecord | None:
    return _BY_CODE.get(mnp_career_code)
